"""BigQuery client with timeout and retry capabilities."""

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

from google.cloud import bigquery
from google.cloud.exceptions import GoogleCloudError

from .timeout_config import CustomerTier, OperationTimeouts, get_timeout_config

logger = logging.getLogger(__name__)


class BigQueryTimeoutError(Exception):
    """Custom timeout error for BigQuery operations."""

    pass


class BigQueryTimeoutClient:
    """BigQuery client wrapper with configurable timeouts and retry logic."""

    def __init__(
        self,
        client: bigquery.Client,
        default_tier: CustomerTier = CustomerTier.STANDARD,
    ):
        """
        Initialize timeout-aware BigQuery client.

        Args:
            client: Underlying BigQuery client
            default_tier: Default customer tier for timeout configuration
        """
        self.client = client
        self.default_tier = default_tier
        # Simple cache for timeout configurations to avoid repeated lookups
        self._timeout_cache: Dict[tuple, OperationTimeouts] = {}

    def _get_timeout_config(
        self,
        customer_tier: Optional[CustomerTier] = None,
        operation_type: Optional[str] = None,
    ) -> OperationTimeouts:
        """Get timeout configuration for operation with caching."""
        tier = customer_tier or self.default_tier
        cache_key = (tier, operation_type)

        # Check cache first
        if cache_key in self._timeout_cache:
            return self._timeout_cache[cache_key]

        # Get configuration and cache it
        config = get_timeout_config(tier, operation_type)
        self._timeout_cache[cache_key] = config
        return config

    async def query_with_timeout(
        self,
        query: str,
        job_config: Optional[bigquery.QueryJobConfig] = None,
        customer_tier: Optional[CustomerTier] = None,
        operation_type: Optional[str] = None,
    ) -> bigquery.QueryJob:
        """
        Execute query with timeout and retry logic.

        Args:
            query: SQL query to execute
            job_config: Optional job configuration
            customer_tier: Customer tier for timeout configuration
            operation_type: Operation type for specific timeout adjustments

        Returns:
            Completed query job

        Raises:
            BigQueryTimeoutError: If query times out
            GoogleCloudError: If query fails after retries
        """
        config = self._get_timeout_config(customer_tier, operation_type)

        # Update job config with timeout
        if job_config is None:
            job_config = bigquery.QueryJobConfig()

        # Set job timeout in milliseconds
        job_config.job_timeout_ms = config.query_timeout * 1000

        for attempt in range(config.max_retry_attempts):
            try:
                logger.info(
                    f"Executing BigQuery query (attempt {attempt + 1}/{config.max_retry_attempts})"
                )

                # Start the query job
                query_job = self.client.query(query, job_config=job_config)

                # Wait for completion with timeout protection and exponential backoff
                start_time = time.time()
                timeout_deadline = start_time + config.query_timeout
                poll_count = 0

                while True:
                    # Reload job status
                    query_job.reload()

                    # Check if job is done first to avoid race condition
                    if query_job.done():
                        break

                    # Check timeout after reload to ensure we have latest status
                    current_time = time.time()
                    if current_time > timeout_deadline:
                        # Cancel the job if possible
                        try:
                            query_job.cancel()
                            logger.info(
                                f"Cancelled job {query_job.job_id} due to timeout"
                            )
                        except Exception as e:
                            logger.warning(f"Failed to cancel timed-out job: {e}")

                        raise BigQueryTimeoutError(
                            f"Query timed out after {config.query_timeout} seconds"
                        )

                    # Exponential backoff for polling to reduce API calls
                    poll_count += 1
                    if poll_count <= 3:
                        # Fast polling for first few checks
                        sleep_time = config.job_poll_interval
                    else:
                        # Exponential backoff: min(initial * 2^(n-3), max_interval)
                        sleep_time = min(
                            config.job_poll_interval * (2 ** (poll_count - 3)),
                            30,  # Max 30 seconds between polls
                        )

                    await asyncio.sleep(sleep_time)

                # Check for errors after completion
                if query_job.error_result:
                    raise GoogleCloudError(f"Query failed: {query_job.error_result}")

                logger.info(
                    f"Query completed successfully in {time.time() - start_time:.2f}s"
                )
                return query_job

            except BigQueryTimeoutError:
                raise  # Don't retry timeout errors
            except GoogleCloudError as e:
                logger.warning(f"Query attempt {attempt + 1} failed: {e}")

                if attempt == config.max_retry_attempts - 1:
                    raise

                # Wait before retry
                await asyncio.sleep(config.retry_delay * (attempt + 1))

        raise GoogleCloudError("Query failed after all retry attempts")

    async def export_to_csv_with_timeout(
        self,
        query: str,
        destination_uri: Optional[str] = None,
        customer_tier: Optional[CustomerTier] = None,
    ) -> Union[bigquery.QueryJob, bigquery.ExtractJob, List[Dict[str, Any]]]:
        """
        Export query results to CSV with timeout handling.

        Args:
            query: SQL query to execute
            destination_uri: Optional Cloud Storage URI for export
            customer_tier: Customer tier for timeout configuration

        Returns:
            Query job or results list depending on destination

        Raises:
            BigQueryTimeoutError: If export times out
        """
        config = self._get_timeout_config(customer_tier, "large_export")

        try:
            # Try BigQuery export first
            query_job = await self.query_with_timeout(
                query, customer_tier=customer_tier, operation_type="large_export"
            )

            if destination_uri:
                # Export to Cloud Storage
                extract_job = self.client.extract_table(
                    query_job.destination,
                    destination_uri,
                    job_config=bigquery.ExtractJobConfig(
                        destination_format=bigquery.DestinationFormat.CSV
                    ),
                )

                # Wait for export completion
                start_time = time.time()
                while not extract_job.done():
                    if time.time() - start_time > config.export_timeout:
                        extract_job.cancel()
                        raise BigQueryTimeoutError("Export timed out")

                    await asyncio.sleep(config.job_poll_interval)
                    extract_job.reload()

                return extract_job
            else:
                # Return results directly with memory safety
                results = []
                row_count = 0
                max_rows = 100000  # Limit to prevent memory issues

                for row in query_job.result():
                    if row_count >= max_rows:
                        logger.warning(
                            f"Export truncated at {max_rows} rows to prevent memory issues"
                        )
                        break
                    results.append(dict(row))
                    row_count += 1

                return results

        except BigQueryTimeoutError:
            logger.warning(
                "BigQuery export timed out, falling back to direct CSV generation"
            )
            return await self._fallback_csv_export(query, customer_tier)

    async def _fallback_csv_export(
        self,
        query: str,
        customer_tier: Optional[CustomerTier] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fallback CSV export when BigQuery times out.

        Args:
            query: SQL query to execute
            customer_tier: Customer tier for timeout configuration

        Returns:
            Query results as list of dictionaries
        """
        config = self._get_timeout_config(customer_tier)

        # Use shorter timeout and simpler query for fallback
        fallback_config = bigquery.QueryJobConfig(
            job_timeout_ms=config.query_timeout * 500,  # Half the normal timeout
            use_query_cache=True,
            use_legacy_sql=False,
        )

        try:
            query_job = await self.query_with_timeout(
                query,
                job_config=fallback_config,
                customer_tier=customer_tier,
            )

            # Convert to list of dictionaries with memory-safe iteration
            results = []
            row_count = 0
            max_rows = 100000  # Limit to prevent memory issues

            for row in query_job.result():
                if row_count >= max_rows:
                    logger.warning(
                        f"Fallback export truncated at {max_rows} rows to prevent memory issues"
                    )
                    break
                results.append(dict(row))
                row_count += 1

            logger.info(f"Fallback export completed with {len(results)} rows")
            return results

        except Exception as e:
            logger.error(f"Fallback export also failed: {e}")
            raise BigQueryTimeoutError("Both primary and fallback exports failed")

    @asynccontextmanager
    async def connection_timeout(
        self, customer_tier: Optional[CustomerTier] = None
    ) -> AsyncGenerator[None, None]:
        """
        Context manager for connection timeout handling.

        Args:
            customer_tier: Customer tier for timeout configuration
        """
        config = self._get_timeout_config(customer_tier)

        try:
            # Set connection timeout (this is mainly for demonstration)
            # In practice, BigQuery client connection timeout is handled at HTTP level
            start_time = time.time()
            yield

        except Exception as e:
            elapsed = time.time() - start_time
            if elapsed > config.connection_timeout:
                logger.error(f"Connection timed out after {elapsed:.2f}s")
                raise BigQueryTimeoutError(
                    f"Connection timeout ({config.connection_timeout}s)"
                )
            raise

    def get_job_status_with_timeout(
        self,
        job_id: str,
        customer_tier: Optional[CustomerTier] = None,
    ) -> Dict[str, Any]:
        """
        Get job status with timeout protection.

        Args:
            job_id: BigQuery job ID
            customer_tier: Customer tier for timeout configuration

        Returns:
            Job status information
        """
        config = self._get_timeout_config(customer_tier)

        try:
            start_time = time.time()
            job = self.client.get_job(job_id, timeout=config.auth_timeout)

            status_info = {
                "job_id": job.job_id,
                "state": job.state,
                "created": job.created.isoformat() if job.created else None,
                "started": job.started.isoformat() if job.started else None,
                "ended": job.ended.isoformat() if job.ended else None,
                "error_result": job.error_result,
                "total_bytes_processed": getattr(job, "total_bytes_processed", None),
                "elapsed_seconds": time.time() - start_time,
            }

            return status_info

        except Exception as e:
            logger.error(f"Failed to get job status: {e}")
            raise BigQueryTimeoutError(f"Job status check timed out or failed: {e}")


def create_timeout_client(
    project_id: Optional[str] = None,
    customer_tier: CustomerTier = CustomerTier.STANDARD,
) -> BigQueryTimeoutClient:
    """
    Create a BigQuery client with timeout capabilities.

    Args:
        project_id: Google Cloud project ID
        customer_tier: Default customer tier for timeout configuration

    Returns:
        Timeout-aware BigQuery client
    """
    base_client = bigquery.Client(project=project_id)
    return BigQueryTimeoutClient(base_client, customer_tier)
