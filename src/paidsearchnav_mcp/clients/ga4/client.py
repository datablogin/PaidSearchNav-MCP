"""GA4 Data API client for real-time analytics integration.

This module provides access to the GA4 Data API for real-time metrics
and analytics data to supplement BigQuery export data.
"""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

try:
    from google.analytics.data_v1beta import BetaAnalyticsDataClient
    from google.analytics.data_v1beta.types import (
        BatchRunReportsRequest,
        DateRange,
        Dimension,
        Filter,
        FilterExpression,
        Metric,
        OrderBy,
        RunRealtimeReportRequest,
        RunReportRequest,
    )
    from google.api_core.exceptions import (
        GoogleAPIError,
        TooManyRequests,
    )

    GA4_API_AVAILABLE = True
except ImportError:
    GA4_API_AVAILABLE = False
    BetaAnalyticsDataClient = None
    GoogleAPIError = Exception
    TooManyRequests = Exception

from paidsearchnav.core.config import GA4Config
from paidsearchnav.platforms.ga4.auth import GA4Authenticator
from paidsearchnav.platforms.ga4.cache import GA4CacheManager

logger = logging.getLogger(__name__)


class GA4APIError(Exception):
    """Exception raised for GA4 API errors."""

    pass


class GA4RateLimitError(GA4APIError):
    """Exception raised when GA4 API rate limits are exceeded."""

    pass


class GA4DataClient:
    """Client for real-time GA4 Data API access."""

    def __init__(self, config: GA4Config):
        """Initialize the GA4 Data API client.

        Args:
            config: GA4 configuration
        """
        if not GA4_API_AVAILABLE:
            raise ImportError(
                "Google Analytics Data API is required for GA4 integration. "
                "Install with: pip install google-analytics-data"
            )

        self.config = config
        self.authenticator = GA4Authenticator(config)
        self.cache_manager = GA4CacheManager(config)
        self._client: Optional[BetaAnalyticsDataClient] = None
        self._request_count = 0
        self._last_request_time = 0.0

    @property
    def client(self) -> BetaAnalyticsDataClient:
        """Get the authenticated GA4 client."""
        if self._client is None:
            self._client = self.authenticator.get_client()
        return self._client

    async def get_realtime_metrics(
        self,
        dimensions: List[str],
        metrics: List[str],
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 1000,
    ) -> Dict[str, Any]:
        """Get real-time metrics from GA4.

        Args:
            dimensions: List of dimension names (e.g., ['country', 'source'])
            metrics: List of metric names (e.g., ['activeUsers', 'conversions'])
            filters: Optional filters to apply
            limit: Maximum number of rows to return

        Returns:
            Dictionary containing the report data

        Raises:
            GA4APIError: If the API request fails
        """
        # Validate dimensions and metrics
        self.config.validate_dimensions_and_metrics(dimensions, metrics)

        try:
            # Check cache first
            cached_response = await self.cache_manager.get_cached_response(
                request_type="realtime",
                start_date="realtime",
                end_date="realtime",
                dimensions=dimensions,
                metrics=metrics,
                filters=filters,
            )

            if cached_response:
                logger.debug(
                    f"Returning cached real-time data for property {self.config.property_id}"
                )
                return cached_response

            await self._check_rate_limits()

            request = RunRealtimeReportRequest(
                property=f"properties/{self.config.property_id}",
                dimensions=[Dimension(name=dim) for dim in dimensions],
                metrics=[Metric(name=metric) for metric in metrics],
                limit=limit,
            )

            # Add filters if provided
            if filters:
                request.dimension_filter = self._build_filter_expression(filters)

            logger.info(
                f"Making real-time GA4 API request for property {self.config.property_id}"
            )

            response = self.client.run_realtime_report(request)
            self._track_request()

            formatted_response = self._format_response(response)

            # Cache response (shorter TTL for real-time data)
            await self.cache_manager.store_response(
                request_type="realtime",
                start_date="realtime",
                end_date="realtime",
                dimensions=dimensions,
                metrics=metrics,
                response_data=formatted_response,
                filters=filters,
                custom_ttl_seconds=60,  # 1 minute cache for real-time data
            )

            return formatted_response

        except TooManyRequests as e:
            logger.warning(f"GA4 API rate limit exceeded: {e}")
            raise GA4RateLimitError(f"GA4 API rate limit exceeded: {e}")
        except GoogleAPIError as e:
            logger.error(f"GA4 API error: {e}")
            raise GA4APIError(f"GA4 API request failed: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in GA4 real-time request: {e}")
            raise GA4APIError(f"Unexpected GA4 API error: {e}")

    async def get_historical_metrics(
        self,
        start_date: str,
        end_date: str,
        dimensions: List[str],
        metrics: List[str],
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 10000,
        order_by: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Get historical metrics from GA4.

        Args:
            start_date: Start date in YYYY-MM-DD format or GA4 date constant
            end_date: End date in YYYY-MM-DD format or GA4 date constant
            dimensions: List of dimension names
            metrics: List of metric names
            filters: Optional filters to apply
            limit: Maximum number of rows to return
            order_by: Optional list of fields to order by

        Returns:
            Dictionary containing the report data

        Raises:
            GA4APIError: If the API request fails
        """
        # Validate input parameters
        self.config.validate_date_range(start_date, end_date)
        self.config.validate_dimensions_and_metrics(dimensions, metrics)

        try:
            await self._check_rate_limits()

            request = RunReportRequest(
                property=f"properties/{self.config.property_id}",
                date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
                dimensions=[Dimension(name=dim) for dim in dimensions],
                metrics=[Metric(name=metric) for metric in metrics],
                limit=limit,
            )

            # Add filters if provided
            if filters:
                request.dimension_filter = self._build_filter_expression(filters)

            # Add ordering if provided
            if order_by:
                request.order_bys = [
                    OrderBy(dimension=OrderBy.DimensionOrderBy(dimension_name=field))
                    if field in dimensions
                    else OrderBy(metric=OrderBy.MetricOrderBy(metric_name=field))
                    for field in order_by
                ]

            logger.info(
                f"Making historical GA4 API request for property {self.config.property_id} "
                f"from {start_date} to {end_date}"
            )

            response = self.client.run_report(request)
            self._track_request()

            return self._format_response(response)

        except TooManyRequests as e:
            logger.warning(f"GA4 API rate limit exceeded: {e}")
            raise GA4RateLimitError(f"GA4 API rate limit exceeded: {e}")
        except GoogleAPIError as e:
            logger.error(f"GA4 API error: {e}")
            raise GA4APIError(f"GA4 API request failed: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in GA4 historical request: {e}")
            raise GA4APIError(f"Unexpected GA4 API error: {e}")

    async def batch_get_reports(
        self, report_requests: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Get multiple reports in a single batch request.

        Args:
            report_requests: List of report request configurations

        Returns:
            List of formatted report responses

        Raises:
            GA4APIError: If the batch request fails
        """
        try:
            await self._check_rate_limits()

            # Convert report requests to GA4 format
            ga4_requests = []
            for req in report_requests:
                ga4_request = RunReportRequest(
                    property=f"properties/{self.config.property_id}",
                    date_ranges=[
                        DateRange(
                            start_date=req.get("start_date", "yesterday"),
                            end_date=req.get("end_date", "yesterday"),
                        )
                    ],
                    dimensions=[
                        Dimension(name=dim) for dim in req.get("dimensions", [])
                    ],
                    metrics=[Metric(name=metric) for metric in req.get("metrics", [])],
                    limit=req.get("limit", 10000),
                )

                if req.get("filters"):
                    ga4_request.dimension_filter = self._build_filter_expression(
                        req["filters"]
                    )

                ga4_requests.append(ga4_request)

            batch_request = BatchRunReportsRequest(
                property=f"properties/{self.config.property_id}", requests=ga4_requests
            )

            logger.info(
                f"Making batch GA4 API request with {len(ga4_requests)} reports "
                f"for property {self.config.property_id}"
            )

            response = self.client.batch_run_reports(batch_request)
            self._track_request()

            # Format each report response
            formatted_responses = []
            for report in response.reports:
                formatted_responses.append(self._format_response(report))

            return formatted_responses

        except TooManyRequests as e:
            logger.warning(f"GA4 API rate limit exceeded: {e}")
            raise GA4RateLimitError(f"GA4 API rate limit exceeded: {e}")
        except GoogleAPIError as e:
            logger.error(f"GA4 API error: {e}")
            raise GA4APIError(f"GA4 batch request failed: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in GA4 batch request: {e}")
            raise GA4APIError(f"Unexpected GA4 API error: {e}")

    def get_session_metrics(
        self,
        start_date: str = "7daysAgo",
        end_date: str = "yesterday",
        source_medium_filter: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get session metrics for campaign analysis.

        Args:
            start_date: Start date for analysis
            end_date: End date for analysis
            source_medium_filter: Optional source/medium filter

        Returns:
            Session metrics data
        """
        dimensions = ["source", "medium", "country", "deviceCategory"]
        metrics = [
            "sessions",
            "bounceRate",
            "averageSessionDuration",
            "conversions",
            "totalRevenue",
            "sessionConversionRate",
        ]

        filters = {}
        if source_medium_filter:
            filters["sourceMedium"] = source_medium_filter

        # This is synchronous but will be wrapped in async context
        try:
            request = RunReportRequest(
                property=f"properties/{self.config.property_id}",
                date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
                dimensions=[Dimension(name=dim) for dim in dimensions],
                metrics=[Metric(name=metric) for metric in metrics],
                limit=10000,
            )

            if filters:
                request.dimension_filter = self._build_filter_expression(filters)

            response = self.client.run_report(request)
            self._track_request()

            return self._format_response(response)

        except Exception as e:
            logger.error(f"Error getting session metrics: {e}")
            raise GA4APIError(f"Failed to get session metrics: {e}")

    def _build_filter_expression(self, filters: Dict[str, Any]) -> FilterExpression:
        """Build GA4 filter expression from dictionary.

        Args:
            filters: Dictionary of dimension filters

        Returns:
            GA4 FilterExpression object
        """
        # Simple implementation for string filters
        # Can be extended for more complex filter types
        filter_expressions = []

        for dimension_name, value in filters.items():
            if isinstance(value, str):
                dimension_filter = Filter(
                    field_name=dimension_name,
                    string_filter=Filter.StringFilter(value=value),
                )
                filter_expressions.append(FilterExpression(filter=dimension_filter))

        # Combine with AND logic if multiple filters
        if len(filter_expressions) == 1:
            return filter_expressions[0]
        elif len(filter_expressions) > 1:
            return FilterExpression(
                and_group=FilterExpression.FilterExpressionList(
                    expressions=filter_expressions
                )
            )
        else:
            return FilterExpression()

    def _format_response(self, response) -> Dict[str, Any]:
        """Format GA4 API response into a standardized dictionary.

        Args:
            response: GA4 API response object

        Returns:
            Formatted response dictionary
        """
        formatted_data = {
            "rows": [],
            "row_count": response.row_count if hasattr(response, "row_count") else 0,
            "dimensions": [],
            "metrics": [],
            "metadata": {},
        }

        # Extract dimension headers
        if hasattr(response, "dimension_headers"):
            formatted_data["dimensions"] = [
                header.name for header in response.dimension_headers
            ]

        # Extract metric headers
        if hasattr(response, "metric_headers"):
            formatted_data["metrics"] = [
                header.name for header in response.metric_headers
            ]

        # Extract data rows
        if hasattr(response, "rows"):
            for row in response.rows:
                formatted_row = {}

                # Add dimension values
                if hasattr(row, "dimension_values"):
                    for i, dim_value in enumerate(row.dimension_values):
                        if i < len(formatted_data["dimensions"]):
                            formatted_row[formatted_data["dimensions"][i]] = (
                                dim_value.value
                            )

                # Add metric values
                if hasattr(row, "metric_values"):
                    for i, metric_value in enumerate(row.metric_values):
                        if i < len(formatted_data["metrics"]):
                            metric_name = formatted_data["metrics"][i]
                            formatted_row[metric_name] = metric_value.value

                formatted_data["rows"].append(formatted_row)

        # Add metadata
        if hasattr(response, "metadata"):
            formatted_data["metadata"] = {
                "currency_code": getattr(response.metadata, "currency_code", "USD"),
                "time_zone": getattr(response.metadata, "time_zone", "UTC"),
            }

        return formatted_data

    async def _check_rate_limits(self) -> None:
        """Check and enforce rate limits for GA4 API requests."""
        if not self.config.enable_rate_limiting:
            return

        current_time = time.time()

        # Simple rate limiting - ensure minimum time between requests
        min_interval = 60.0 / self.config.requests_per_minute
        time_since_last = current_time - self._last_request_time

        if time_since_last < min_interval:
            sleep_time = min_interval - time_since_last
            logger.info(f"Rate limiting: sleeping {sleep_time:.2f}s")
            await asyncio.sleep(sleep_time)

    def _track_request(self) -> None:
        """Track API request for rate limiting and monitoring."""
        self._request_count += 1
        self._last_request_time = time.time()

        logger.debug(f"GA4 API request #{self._request_count} completed")

    def get_conversion_metrics(
        self,
        start_date: str = "7daysAgo",
        end_date: str = "yesterday",
        conversion_events: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Get conversion metrics for campaign attribution.

        Args:
            start_date: Start date for analysis
            end_date: End date for analysis
            conversion_events: List of specific conversion events to track

        Returns:
            Conversion metrics data
        """
        dimensions = ["source", "medium", "campaignName", "country"]
        metrics = ["conversions", "totalRevenue", "sessionConversionRate"]

        # Add event-specific metrics if conversion events specified
        if conversion_events:
            for event in conversion_events:
                metrics.append(f"conversions:{event}")

        try:
            request = RunReportRequest(
                property=f"properties/{self.config.property_id}",
                date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
                dimensions=[Dimension(name=dim) for dim in dimensions],
                metrics=[Metric(name=metric) for metric in metrics],
                limit=10000,
            )

            response = self.client.run_report(request)
            self._track_request()

            return self._format_response(response)

        except Exception as e:
            logger.error(f"Error getting conversion metrics: {e}")
            raise GA4APIError(f"Failed to get conversion metrics: {e}")

    def get_geo_performance_metrics(
        self,
        start_date: str = "7daysAgo",
        end_date: str = "yesterday",
        country_filter: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get geographic performance metrics.

        Args:
            start_date: Start date for analysis
            end_date: End date for analysis
            country_filter: Optional country filter

        Returns:
            Geographic performance data
        """
        dimensions = ["country", "region", "city", "source", "medium"]
        metrics = [
            "sessions",
            "bounceRate",
            "averageSessionDuration",
            "conversions",
            "totalRevenue",
            "newUsers",
            "returningUsers",
        ]

        filters = {}
        if country_filter:
            filters["country"] = country_filter

        try:
            request = RunReportRequest(
                property=f"properties/{self.config.property_id}",
                date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
                dimensions=[Dimension(name=dim) for dim in dimensions],
                metrics=[Metric(name=metric) for metric in metrics],
                limit=10000,
            )

            if filters:
                request.dimension_filter = self._build_filter_expression(filters)

            response = self.client.run_report(request)
            self._track_request()

            return self._format_response(response)

        except Exception as e:
            logger.error(f"Error getting geo performance metrics: {e}")
            raise GA4APIError(f"Failed to get geo performance metrics: {e}")

    def get_landing_page_metrics(
        self,
        start_date: str = "7daysAgo",
        end_date: str = "yesterday",
        page_filter: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get landing page performance metrics.

        Args:
            start_date: Start date for analysis
            end_date: End date for analysis
            page_filter: Optional page path filter

        Returns:
            Landing page performance data
        """
        dimensions = ["landingPage", "source", "medium", "country"]
        metrics = [
            "sessions",
            "bounceRate",
            "averageSessionDuration",
            "conversions",
            "totalRevenue",
            "exitRate",
        ]

        filters = {}
        if page_filter:
            filters["landingPage"] = page_filter

        try:
            request = RunReportRequest(
                property=f"properties/{self.config.property_id}",
                date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
                dimensions=[Dimension(name=dim) for dim in dimensions],
                metrics=[Metric(name=metric) for metric in metrics],
                limit=10000,
            )

            if filters:
                request.dimension_filter = self._build_filter_expression(filters)

            response = self.client.run_report(request)
            self._track_request()

            return self._format_response(response)

        except Exception as e:
            logger.error(f"Error getting landing page metrics: {e}")
            raise GA4APIError(f"Failed to get landing page metrics: {e}")

    def test_connection(self) -> Tuple[bool, str]:
        """Test the GA4 API connection and property access.

        Returns:
            Tuple of (success, message)
        """
        try:
            # Test authentication
            if not self.authenticator.test_authentication():
                return False, "GA4 authentication failed"

            # Test property access
            if not self.authenticator.validate_property_access(self.config.property_id):
                return False, f"No access to GA4 property {self.config.property_id}"

            # Test basic API call
            request = RunReportRequest(
                property=f"properties/{self.config.property_id}",
                date_ranges=[DateRange(start_date="yesterday", end_date="yesterday")],
                dimensions=[Dimension(name="date")],
                metrics=[Metric(name="sessions")],
                limit=1,
            )

            response = self.client.run_report(request)

            return True, "GA4 API connection successful"

        except Exception as e:
            return False, f"GA4 connection test failed: {e}"

    def get_request_stats(self) -> Dict[str, Any]:
        """Get request statistics for monitoring.

        Returns:
            Dictionary with request statistics
        """
        return {
            "total_requests": self._request_count,
            "last_request_time": self._last_request_time,
            "property_id": self.config.property_id,
            "rate_limiting_enabled": self.config.enable_rate_limiting,
        }

    async def get_all_historical_metrics(
        self,
        start_date: str,
        end_date: str,
        dimensions: List[str],
        metrics: List[str],
        filters: Optional[Dict[str, Any]] = None,
        batch_size: int = 10000,
        max_results: int = 100000,
    ) -> Dict[str, Any]:
        """Get all historical metrics with automatic pagination.

        Args:
            start_date: Start date in YYYY-MM-DD format or GA4 date constant
            end_date: End date in YYYY-MM-DD format or GA4 date constant
            dimensions: List of dimension names
            metrics: List of metric names
            filters: Optional filters to apply
            batch_size: Number of rows per API call
            max_results: Maximum total rows to retrieve

        Returns:
            Dictionary containing all paginated data
        """
        # Validate input parameters
        self.config.validate_date_range(start_date, end_date)
        self.config.validate_dimensions_and_metrics(dimensions, metrics)

        all_rows = []
        offset = 0

        while len(all_rows) < max_results:
            batch_data = await self.get_historical_metrics(
                start_date=start_date,
                end_date=end_date,
                dimensions=dimensions,
                metrics=metrics,
                filters=filters,
                limit=min(batch_size, max_results - len(all_rows)),
            )

            batch_rows = batch_data.get("rows", [])
            if not batch_rows:
                break  # No more data available

            all_rows.extend(batch_rows)
            offset += len(batch_rows)

            # If we got fewer rows than requested, we've reached the end
            if len(batch_rows) < batch_size:
                break

        return {
            "rows": all_rows,
            "row_count": len(all_rows),
            "metadata": batch_data.get("metadata", {}),
            "total_batches": (len(all_rows) // batch_size) + 1,
            "pagination_complete": len(all_rows) < max_results,
        }
