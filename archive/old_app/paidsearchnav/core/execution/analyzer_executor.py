"""Analyzer execution framework with comprehensive error handling and monitoring."""

import asyncio
import atexit
import json
import logging
import sys
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from paidsearchnav.core.exceptions import APIError, AuthenticationError, RateLimitError
from paidsearchnav.core.execution.fallback_system import (
    CheckpointSystem,
    FallbackDataSource,
    GracefulDegradationManager,
)
from paidsearchnav.core.interfaces import Analyzer
from paidsearchnav.core.models.analysis import AnalysisResult
from paidsearchnav.services.file_validation import FileValidator


class DateTimeEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles datetime objects."""

    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


logger = logging.getLogger(__name__)


@contextmanager
def temporary_file_handler(output_path: Path):
    """Context manager for safe temporary file handling with guaranteed cleanup."""
    temp_path = output_path.with_suffix(f"{output_path.suffix}.tmp")

    # Register cleanup with atexit as backup
    def cleanup():
        if temp_path.exists():
            try:
                temp_path.unlink()
            except Exception:
                pass

    atexit.register(cleanup)

    try:
        yield temp_path
        # If we get here, move temp file to final location
        if temp_path.exists():
            temp_path.rename(output_path)
    finally:
        # Cleanup temp file if it still exists
        if temp_path.exists():
            try:
                temp_path.unlink()
            except Exception:
                pass
        # Unregister cleanup since we handled it
        try:
            atexit.unregister(cleanup)
        except ValueError:
            pass  # Already unregistered


class AnalyzerExecutionError(Exception):
    """Raised when analyzer execution fails."""

    def __init__(
        self,
        message: str,
        correlation_id: str,
        analyzer_name: str,
        original_error: Optional[Exception] = None,
    ):
        self.correlation_id = correlation_id
        self.analyzer_name = analyzer_name
        self.original_error = original_error
        super().__init__(message)


class ExecutionResult:
    """Result of analyzer execution."""

    def __init__(
        self,
        success: bool,
        correlation_id: str,
        analyzer_name: str,
        customer_id: str,
        output_file: Optional[Path] = None,
        error: Optional[str] = None,
        error_file: Optional[Path] = None,
        execution_time: Optional[float] = None,
        result_data: Optional[AnalysisResult] = None,
        is_fallback: bool = False,
        fallback_reason: Optional[str] = None,
    ):
        self.success = success
        self.correlation_id = correlation_id
        self.analyzer_name = analyzer_name
        self.customer_id = customer_id
        self.output_file = output_file
        self.error = error
        self.error_file = error_file
        self.execution_time = execution_time
        self.result_data = result_data
        self.is_fallback = is_fallback
        self.fallback_reason = fallback_reason


class AnalyzerExecutor:
    """Robust analyzer execution with comprehensive error handling and graceful degradation."""

    def __init__(
        self,
        max_retries: int = 3,
        retry_delay_base: float = 2.0,
        retry_delay_max: float = 30.0,
        min_output_size: int = 100,
        timeout_seconds: int = 300,
        analyzer_timeouts: Optional[Dict[str, int]] = None,
        enable_fallback: bool = True,
        enable_checkpoints: bool = True,
        cache_retention_days: int = 7,
        max_memory_mb: int = 500,
        circuit_breaker_threshold: int = 5,
        circuit_breaker_timeout: int = 300,
    ):
        """Initialize the analyzer executor.

        Args:
            max_retries: Maximum number of retry attempts
            retry_delay_base: Base delay between retries in seconds
            retry_delay_max: Maximum delay between retries in seconds
            min_output_size: Minimum acceptable output file size in bytes
            timeout_seconds: Default timeout for analyzer execution
            analyzer_timeouts: Analyzer-specific timeout overrides (analyzer_name -> timeout_seconds)
            enable_fallback: Enable fallback data system
            enable_checkpoints: Enable checkpoint system for long operations
            cache_retention_days: Number of days to retain cached fallback data
            max_memory_mb: Maximum memory usage for analysis results in MB
            circuit_breaker_threshold: Number of consecutive failures before circuit breaker opens
            circuit_breaker_timeout: Seconds to wait before attempting to close circuit breaker
        """
        self.max_retries = max_retries
        self.retry_delay_base = retry_delay_base
        self.retry_delay_max = retry_delay_max
        self.min_output_size = min_output_size
        self.timeout_seconds = timeout_seconds
        self.analyzer_timeouts = analyzer_timeouts or {}
        self.max_memory_bytes = max_memory_mb * 1024 * 1024
        self.file_validator = FileValidator()

        # Circuit breaker for failing analyzers
        self.circuit_breaker_threshold = circuit_breaker_threshold
        self.circuit_breaker_timeout = circuit_breaker_timeout
        self._analyzer_failures: Dict[str, List[datetime]] = {}
        self._circuit_breaker_opened: Dict[str, datetime] = {}

        # Metrics collection
        self._execution_metrics: Dict[str, Dict[str, Any]] = {}
        self._success_counts: Dict[str, int] = {}
        self._failure_counts: Dict[str, int] = {}
        self._execution_times: Dict[str, List[float]] = {}

        # Graceful degradation components
        if enable_fallback:
            self.fallback_data_source = FallbackDataSource(
                cache_retention_days=cache_retention_days
            )
            self.degradation_manager = GracefulDegradationManager(
                self.fallback_data_source
            )
        else:
            self.fallback_data_source = None
            self.degradation_manager = None

        if enable_checkpoints:
            self.checkpoint_system = CheckpointSystem()
        else:
            self.checkpoint_system = None

    async def execute_analyzer(
        self,
        analyzer: Analyzer,
        customer_id: str,
        start_date: datetime,
        end_date: datetime,
        output_path: Union[str, Path],
        **kwargs: Any,
    ) -> ExecutionResult:
        """Execute analyzer with comprehensive error handling and validation.

        Args:
            analyzer: The analyzer to execute
            customer_id: Google Ads customer ID
            start_date: Analysis start date
            end_date: Analysis end date
            output_path: Path where output should be written
            **kwargs: Additional analyzer parameters

        Returns:
            ExecutionResult containing success status and details
        """
        correlation_id = str(uuid.uuid4())
        analyzer_name = analyzer.get_name()
        output_path = Path(output_path)

        # Check circuit breaker before execution
        if self._is_circuit_breaker_open(analyzer_name):
            logger.warning(
                f"Circuit breaker open for {analyzer_name}, skipping execution",
                extra={"correlation_id": correlation_id, "analyzer": analyzer_name},
            )
            return ExecutionResult(
                success=False,
                correlation_id=correlation_id,
                analyzer_name=analyzer_name,
                customer_id=customer_id,
                error=f"Circuit breaker open for {analyzer_name}",
            )

        logger.info(
            f"Starting analyzer execution - Correlation ID: {correlation_id}",
            extra={
                "correlation_id": correlation_id,
                "analyzer": analyzer_name,
                "customer_id": customer_id,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "output_path": str(output_path),
            },
        )

        start_time = datetime.now()

        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Attempt execution with retries
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(
                    f"Executing {analyzer_name} - Attempt {attempt}/{self.max_retries}",
                    extra={
                        "correlation_id": correlation_id,
                        "attempt": attempt,
                        "analyzer": analyzer_name,
                    },
                )

                # Execute analyzer with timeout (use analyzer-specific if available)
                analyzer_timeout = self.analyzer_timeouts.get(
                    analyzer_name, self.timeout_seconds
                )
                result = await asyncio.wait_for(
                    analyzer.analyze(customer_id, start_date, end_date, **kwargs),
                    timeout=analyzer_timeout,
                )

                # Validate result
                if not result:
                    raise AnalyzerExecutionError(
                        "Analyzer returned None result", correlation_id, analyzer_name
                    )

                # Validate result has content
                if not self._validate_result_content(result):
                    raise AnalyzerExecutionError(
                        "Analyzer returned empty or invalid result",
                        correlation_id,
                        analyzer_name,
                    )

                # Write and validate output file
                await self._write_and_validate_output(
                    result,
                    output_path,
                    correlation_id,
                    analyzer_name,
                    customer_id,
                    start_date,
                    end_date,
                )

                execution_time = (datetime.now() - start_time).total_seconds()

                # Cache successful result for future fallback use
                if self.fallback_data_source:
                    try:
                        result_dict = self._convert_result_to_dict(
                            result,
                            correlation_id,
                            analyzer_name,
                            customer_id,
                            start_date,
                            end_date,
                        )
                        await self.fallback_data_source.cache_successful_result(
                            analyzer_name, customer_id, result_dict
                        )
                    except Exception as cache_error:
                        logger.warning(
                            f"Failed to cache successful result: {cache_error}"
                        )

                logger.info(
                    f"Analyzer execution successful - Correlation ID: {correlation_id}",
                    extra={
                        "correlation_id": correlation_id,
                        "analyzer": analyzer_name,
                        "execution_time": execution_time,
                        "output_file": str(output_path),
                        "recommendations_count": len(result.recommendations),
                    },
                )

                # Record successful execution for circuit breaker and metrics
                self._record_analyzer_success(analyzer_name)
                self._record_execution_metrics(analyzer_name, execution_time, True)

                return ExecutionResult(
                    success=True,
                    correlation_id=correlation_id,
                    analyzer_name=analyzer_name,
                    customer_id=customer_id,
                    output_file=output_path,
                    execution_time=execution_time,
                    result_data=result,
                )

            except asyncio.TimeoutError as e:
                error_msg = (
                    f"Analyzer execution timed out after {self.timeout_seconds}s"
                )
                logger.error(
                    error_msg,
                    extra={
                        "correlation_id": correlation_id,
                        "analyzer": analyzer_name,
                        "attempt": attempt,
                        "timeout": self.timeout_seconds,
                    },
                )

                if attempt == self.max_retries:
                    return await self._handle_final_failure(
                        AnalyzerExecutionError(
                            error_msg, correlation_id, analyzer_name, e
                        ),
                        output_path,
                        correlation_id,
                        analyzer_name,
                        customer_id,
                        start_time,
                    )

            except (APIError, AuthenticationError, RateLimitError) as e:
                error_msg = f"API error during analyzer execution: {str(e)}"
                logger.error(
                    error_msg,
                    extra={
                        "correlation_id": correlation_id,
                        "analyzer": analyzer_name,
                        "attempt": attempt,
                        "error_type": type(e).__name__,
                        "error_details": str(e),
                    },
                )

                if attempt == self.max_retries:
                    return await self._handle_final_failure(
                        AnalyzerExecutionError(
                            error_msg, correlation_id, analyzer_name, e
                        ),
                        output_path,
                        correlation_id,
                        analyzer_name,
                        customer_id,
                        start_time,
                    )

                # Wait before retry for API issues
                retry_delay = min(
                    self.retry_delay_base * (2 ** (attempt - 1)), self.retry_delay_max
                )
                logger.info(
                    f"Retrying in {retry_delay}s due to API error",
                    extra={
                        "correlation_id": correlation_id,
                        "retry_delay": retry_delay,
                    },
                )
                await asyncio.sleep(retry_delay)

            except Exception as e:
                error_msg = f"Unexpected error during analyzer execution: {str(e)}"
                logger.error(
                    error_msg,
                    extra={
                        "correlation_id": correlation_id,
                        "analyzer": analyzer_name,
                        "attempt": attempt,
                        "error_type": type(e).__name__,
                        "error_details": str(e),
                    },
                    exc_info=True,
                )

                if attempt == self.max_retries:
                    return await self._handle_final_failure(
                        AnalyzerExecutionError(
                            error_msg, correlation_id, analyzer_name, e
                        ),
                        output_path,
                        correlation_id,
                        analyzer_name,
                        customer_id,
                        start_time,
                    )

                # Shorter delay for unexpected errors
                retry_delay = min(
                    self.retry_delay_base * attempt, self.retry_delay_max / 2
                )
                logger.info(
                    f"Retrying in {retry_delay}s due to unexpected error",
                    extra={
                        "correlation_id": correlation_id,
                        "retry_delay": retry_delay,
                    },
                )
                await asyncio.sleep(retry_delay)

        # This should never be reached due to the loop structure, but just in case
        # Try graceful degradation as final fallback
        if self.degradation_manager:
            try:
                logger.info(f"Attempting graceful degradation for {analyzer_name}")
                fallback_result = (
                    await self.degradation_manager.handle_analyzer_failure(
                        analyzer_name,
                        customer_id,
                        start_date,
                        end_date,
                        AnalyzerExecutionError(
                            "Max retries exceeded", correlation_id, analyzer_name
                        ),
                    )
                )

                # Write fallback result
                await self._write_and_validate_output(
                    fallback_result,
                    output_path,
                    correlation_id,
                    analyzer_name,
                    customer_id,
                    start_date,
                    end_date,
                    is_fallback=True,
                    fallback_reason="Primary execution failed after max retries",
                )

                execution_time = (datetime.now() - start_time).total_seconds()

                logger.warning(
                    f"Used graceful degradation for {analyzer_name}",
                    extra={
                        "correlation_id": correlation_id,
                        "execution_time": execution_time,
                        "fallback_type": "graceful_degradation",
                    },
                )

                return ExecutionResult(
                    success=True,  # Mark as success since we provided fallback
                    correlation_id=correlation_id,
                    analyzer_name=analyzer_name,
                    customer_id=customer_id,
                    output_file=output_path,
                    execution_time=execution_time,
                    result_data=fallback_result,
                    is_fallback=True,
                    fallback_reason="Max retries exceeded",
                )

            except Exception as fallback_error:
                logger.error(f"Graceful degradation also failed: {fallback_error}")

        return await self._handle_final_failure(
            AnalyzerExecutionError(
                "Max retries exceeded and graceful degradation failed",
                correlation_id,
                analyzer_name,
            ),
            output_path,
            correlation_id,
            analyzer_name,
            customer_id,
            start_time,
        )

    def _validate_result_content(self, result: AnalysisResult) -> bool:
        """Validate that the analysis result has meaningful content.

        Args:
            result: The analysis result to validate

        Returns:
            True if result has sufficient content, False otherwise
        """
        if not result:
            return False

        # Check that basic fields are present
        if not result.customer_id or not result.analyzer_name:
            return False

        # Check that we have either recommendations or meaningful metrics
        has_recommendations = result.recommendations and len(result.recommendations) > 0
        has_metrics = result.metrics and result.metrics.total_search_terms_analyzed > 0

        # Consider result valid if it has either recommendations or processed data
        return (
            has_recommendations
            or has_metrics
            or (result.raw_data and len(str(result.raw_data)) > 50)
        )

    async def _write_and_validate_output(
        self,
        result: AnalysisResult,
        output_path: Path,
        correlation_id: str,
        analyzer_name: str,
        customer_id: str,
        start_date: datetime,
        end_date: datetime,
        is_fallback: bool = False,
        fallback_reason: Optional[str] = None,
    ) -> None:
        """Write analysis result to file and validate the output.

        Args:
            result: Analysis result to write
            output_path: Path to write the output file
            correlation_id: Execution correlation ID
            analyzer_name: Name of the analyzer
            customer_id: Customer ID
            start_date: Analysis start date
            end_date: Analysis end date

        Raises:
            AnalyzerExecutionError: If file writing or validation fails
        """
        # Check memory usage before serialization
        self._check_memory_usage(result, correlation_id)

        # Convert result to serializable format
        result_dict = self._convert_result_to_dict(
            result,
            correlation_id,
            analyzer_name,
            customer_id,
            start_date,
            end_date,
            is_fallback,
            fallback_reason,
        )

        # Use context manager for safe file handling with guaranteed cleanup
        with temporary_file_handler(output_path) as temp_path:
            try:
                # Write to temporary file
                with open(temp_path, "w", encoding="utf-8") as f:
                    json.dump(
                        result_dict,
                        f,
                        indent=2,
                        ensure_ascii=False,
                        cls=DateTimeEncoder,
                    )

                # Validate file was written correctly
                file_size = temp_path.stat().st_size

                if file_size < self.min_output_size:
                    raise AnalyzerExecutionError(
                        f"Output file too small: {file_size} bytes (minimum {self.min_output_size})",
                        correlation_id,
                        analyzer_name,
                    )

                # Validate JSON structure
                with open(temp_path, "r", encoding="utf-8") as f:
                    try:
                        validation_data = json.load(f)
                        if not validation_data or not validation_data.get(
                            "execution_metadata", {}
                        ).get("success"):
                            raise AnalyzerExecutionError(
                                "Output file contains invalid or incomplete data",
                                correlation_id,
                                analyzer_name,
                            )
                    except json.JSONDecodeError as e:
                        raise AnalyzerExecutionError(
                            f"Output file contains invalid JSON: {str(e)}",
                            correlation_id,
                            analyzer_name,
                            e,
                        )

                logger.info(
                    "Output file validated and saved successfully",
                    extra={
                        "correlation_id": correlation_id,
                        "file_size": file_size,
                        "output_path": str(output_path),
                    },
                )

            except Exception as e:
                if isinstance(e, AnalyzerExecutionError):
                    raise
                else:
                    raise AnalyzerExecutionError(
                        f"Failed to write output file: {str(e)}",
                        correlation_id,
                        analyzer_name,
                        e,
                    )

    def _convert_result_to_dict(
        self,
        result: AnalysisResult,
        correlation_id: str,
        analyzer_name: str,
        customer_id: str,
        start_date: datetime,
        end_date: datetime,
        is_fallback: bool = False,
        fallback_reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Convert analysis result to JSON-serializable dictionary.

        Args:
            result: Analysis result to convert
            correlation_id: Execution correlation ID
            analyzer_name: Name of the analyzer
            customer_id: Customer ID
            start_date: Analysis start date
            end_date: Analysis end date

        Returns:
            JSON-serializable dictionary
        """
        try:
            result_dict = {
                "execution_metadata": {
                    "correlation_id": correlation_id,
                    "analyzer": analyzer_name,
                    "customer_id": customer_id,
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "timestamp": datetime.now().isoformat(),
                    "success": True,
                    "is_fallback": is_fallback,
                    "fallback_reason": fallback_reason,
                },
                "analysis_metadata": {
                    "analysis_type": result.analysis_type,
                    "analyzer_name": result.analyzer_name,
                    "recommendations_count": len(result.recommendations),
                },
                "metrics": self._serialize_metrics(result.metrics)
                if result.metrics
                else {},
                "recommendations": [
                    self._serialize_recommendation(rec)
                    for rec in result.recommendations
                ],
                "raw_data": self._serialize_raw_data(result.raw_data)
                if result.raw_data
                else {},
                "errors": result.errors if hasattr(result, "errors") else [],
            }

            # Add analyzer-specific fields using safe __dict__ access
            excluded_fields = {
                "analysis_type",
                "analyzer_name",
                "metrics",
                "recommendations",
                "raw_data",
                "errors",
                "customer_id",
                "start_date",
                "end_date",
            }

            if hasattr(result, "__dict__"):
                for attr_name, attr_value in result.__dict__.items():
                    if (
                        not attr_name.startswith("_")
                        and attr_name not in excluded_fields
                        and attr_value is not None
                    ):
                        try:
                            # Attempt to serialize the attribute
                            converted_value = self._convert_datetime_fields(attr_value)
                            json.dumps(converted_value, cls=DateTimeEncoder)
                            result_dict[attr_name] = converted_value
                        except (TypeError, ValueError):
                            # Skip non-serializable attributes
                            continue

            return result_dict

        except Exception as e:
            logger.error(
                f"Error converting result to dict: {str(e)}",
                extra={"correlation_id": correlation_id},
            )
            # Return minimal valid result
            return {
                "execution_metadata": {
                    "correlation_id": correlation_id,
                    "analyzer": analyzer_name,
                    "customer_id": customer_id,
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "timestamp": datetime.now().isoformat(),
                    "success": True,
                },
                "analysis_metadata": {
                    "analysis_type": getattr(result, "analysis_type", "unknown"),
                    "analyzer_name": analyzer_name,
                    "recommendations_count": len(result.recommendations)
                    if result.recommendations
                    else 0,
                },
                "metrics": {},
                "recommendations": [],
                "raw_data": {"serialization_error": str(e)},
                "errors": [],
            }

    def _is_circuit_breaker_open(self, analyzer_name: str) -> bool:
        """Check if circuit breaker is open for analyzer."""
        if analyzer_name not in self._circuit_breaker_opened:
            return False

        opened_time = self._circuit_breaker_opened[analyzer_name]
        if (
            datetime.now() - opened_time
        ).total_seconds() > self.circuit_breaker_timeout:
            # Circuit breaker timeout expired, close it
            del self._circuit_breaker_opened[analyzer_name]
            return False

        return True

    def _record_analyzer_failure(self, analyzer_name: str) -> None:
        """Record analyzer failure and check if circuit breaker should open."""
        now = datetime.now()

        if analyzer_name not in self._analyzer_failures:
            self._analyzer_failures[analyzer_name] = []

        # Add current failure
        self._analyzer_failures[analyzer_name].append(now)

        # Keep only failures from last hour
        recent_failures = [
            f
            for f in self._analyzer_failures[analyzer_name]
            if (now - f).total_seconds() < 3600
        ]
        self._analyzer_failures[analyzer_name] = recent_failures

        # Open circuit breaker if threshold exceeded
        if len(recent_failures) >= self.circuit_breaker_threshold:
            self._circuit_breaker_opened[analyzer_name] = now
            logger.warning(
                f"Circuit breaker opened for {analyzer_name} after {len(recent_failures)} failures"
            )

    def _record_execution_metrics(
        self, analyzer_name: str, execution_time: float, success: bool
    ) -> None:
        """Record execution metrics for monitoring."""
        # Update success/failure counts
        if success:
            self._success_counts[analyzer_name] = (
                self._success_counts.get(analyzer_name, 0) + 1
            )
        else:
            self._failure_counts[analyzer_name] = (
                self._failure_counts.get(analyzer_name, 0) + 1
            )

        # Track execution times (keep last 100 for rolling average)
        if analyzer_name not in self._execution_times:
            self._execution_times[analyzer_name] = []
        self._execution_times[analyzer_name].append(execution_time)
        if len(self._execution_times[analyzer_name]) > 100:
            self._execution_times[analyzer_name] = self._execution_times[analyzer_name][
                -100:
            ]

    def get_execution_metrics(self) -> Dict[str, Dict[str, Any]]:
        """Get execution metrics for all analyzers."""
        metrics = {}

        for analyzer_name in set(
            list(self._success_counts.keys()) + list(self._failure_counts.keys())
        ):
            success_count = self._success_counts.get(analyzer_name, 0)
            failure_count = self._failure_counts.get(analyzer_name, 0)
            total_count = success_count + failure_count

            execution_times = self._execution_times.get(analyzer_name, [])
            avg_execution_time = (
                sum(execution_times) / len(execution_times) if execution_times else 0
            )

            metrics[analyzer_name] = {
                "success_count": success_count,
                "failure_count": failure_count,
                "success_rate": success_count / total_count if total_count > 0 else 0,
                "average_execution_time": avg_execution_time,
                "total_executions": total_count,
                "circuit_breaker_open": self._is_circuit_breaker_open(analyzer_name),
            }

        return metrics

    def _record_analyzer_success(self, analyzer_name: str) -> None:
        """Record successful execution and reset failure count."""
        if analyzer_name in self._analyzer_failures:
            del self._analyzer_failures[analyzer_name]
        if analyzer_name in self._circuit_breaker_opened:
            del self._circuit_breaker_opened[analyzer_name]
            logger.info(
                f"Circuit breaker closed for {analyzer_name} after successful execution"
            )

    def _check_memory_usage(self, obj: Any, correlation_id: str) -> None:
        """Check if object exceeds memory limits."""
        try:
            size = sys.getsizeof(obj)
            if size > self.max_memory_bytes:
                raise AnalyzerExecutionError(
                    f"Result exceeds memory limit: {size / (1024 * 1024):.1f}MB > {self.max_memory_bytes / (1024 * 1024):.1f}MB",
                    correlation_id,
                    "MemoryCheck",
                )
        except Exception:
            # If we can't measure, assume it's okay
            pass

    def _convert_datetime_fields(self, obj: Any) -> Any:
        """Recursively convert datetime objects to ISO format strings."""
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, dict):
            return {k: self._convert_datetime_fields(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [self._convert_datetime_fields(item) for item in obj]
        else:
            return obj

    def _serialize_metrics(self, metrics: Any) -> Dict[str, Any]:
        """Safely serialize metrics object."""
        try:
            if hasattr(metrics, "__dict__"):
                return {
                    k: self._convert_datetime_fields(v)
                    for k, v in metrics.__dict__.items()
                    if not k.startswith("_")
                }
            else:
                return self._convert_datetime_fields(dict(metrics)) if metrics else {}
        except Exception:
            return {"serialization_error": "Could not serialize metrics"}

    def _serialize_recommendation(self, rec: Any) -> Dict[str, Any]:
        """Safely serialize a recommendation object."""
        try:
            rec_dict = {
                "type": rec.type.value if hasattr(rec.type, "value") else str(rec.type),
                "priority": rec.priority.value
                if hasattr(rec.priority, "value")
                else str(rec.priority),
                "title": rec.title,
                "description": rec.description,
            }

            # Add optional fields if they exist
            for field in [
                "campaign_id",
                "ad_group_id",
                "keyword_id",
                "estimated_impact",
                "implementation_effort",
                "estimated_cost_savings",
                "estimated_conversion_increase",
                "estimated_revenue_increase",
                "action_data",
            ]:
                if hasattr(rec, field):
                    value = getattr(rec, field)
                    if value is not None:
                        rec_dict[field] = self._convert_datetime_fields(value)

            return rec_dict
        except Exception as e:
            return {
                "type": "UNKNOWN",
                "priority": "UNKNOWN",
                "title": "Serialization Error",
                "description": f"Could not serialize recommendation: {str(e)}",
                "serialization_error": str(e),
            }

    def _serialize_raw_data(self, raw_data: Any) -> Dict[str, Any]:
        """Safely serialize raw data."""
        try:
            if isinstance(raw_data, dict):
                converted_data = self._convert_datetime_fields(raw_data)
                return {
                    k: v for k, v in converted_data.items() if self._is_serializable(v)
                }
            else:
                converted_data = self._convert_datetime_fields(raw_data)
                return (
                    {"data": converted_data}
                    if self._is_serializable(converted_data)
                    else {}
                )
        except Exception:
            return {"serialization_error": "Could not serialize raw data"}

    def _is_serializable(self, obj: Any) -> bool:
        """Check if an object is JSON serializable."""
        try:
            json.dumps(obj, cls=DateTimeEncoder)
            return True
        except (TypeError, ValueError):
            return False

    async def _handle_final_failure(
        self,
        error: AnalyzerExecutionError,
        output_path: Path,
        correlation_id: str,
        analyzer_name: str,
        customer_id: str,
        start_time: datetime,
    ) -> ExecutionResult:
        """Handle final failure after all retries exhausted.

        Args:
            error: The final error that caused failure
            output_path: Path where output should have been written
            correlation_id: Execution correlation ID
            analyzer_name: Name of the analyzer
            customer_id: Customer ID
            start_time: Execution start time

        Returns:
            ExecutionResult indicating failure
        """
        execution_time = (datetime.now() - start_time).total_seconds()

        # Record failure for circuit breaker and metrics
        self._record_analyzer_failure(analyzer_name)
        self._record_execution_metrics(analyzer_name, execution_time, False)

        # Write error file instead of leaving zero-length file
        error_file_path = output_path.with_name(
            f"{output_path.stem}_ERROR{output_path.suffix}"
        )

        try:
            error_data = {
                "execution_metadata": {
                    "correlation_id": correlation_id,
                    "analyzer": analyzer_name,
                    "customer_id": customer_id,
                    "timestamp": datetime.now().isoformat(),
                    "success": False,
                    "execution_time": execution_time,
                },
                "error": {
                    "message": str(error),
                    "type": type(error).__name__,
                    "analyzer": analyzer_name,
                    "attempts": self.max_retries,
                },
                "original_error": {
                    "type": type(error.original_error).__name__
                    if error.original_error
                    else None,
                    "message": str(error.original_error)
                    if error.original_error
                    else None,
                }
                if error.original_error
                else None,
            }

            with open(error_file_path, "w", encoding="utf-8") as f:
                json.dump(error_data, f, indent=2, ensure_ascii=False)

            logger.error(
                "Analyzer execution failed permanently - Error file created",
                extra={
                    "correlation_id": correlation_id,
                    "analyzer": analyzer_name,
                    "error_file": str(error_file_path),
                    "execution_time": execution_time,
                },
            )

        except Exception as file_error:
            logger.error(
                f"Failed to write error file: {str(file_error)}",
                extra={"correlation_id": correlation_id},
            )
            error_file_path = None

        # Remove any zero-length output file that might have been created
        if output_path.exists() and output_path.stat().st_size == 0:
            try:
                output_path.unlink()
                logger.info(
                    f"Removed zero-length file: {output_path}",
                    extra={"correlation_id": correlation_id},
                )
            except Exception:
                pass  # Best effort cleanup

        return ExecutionResult(
            success=False,
            correlation_id=correlation_id,
            analyzer_name=analyzer_name,
            customer_id=customer_id,
            error=str(error),
            error_file=error_file_path,
            execution_time=execution_time,
        )

    async def execute_multiple_analyzers(
        self,
        analyzers: List[Analyzer],
        customer_id: str,
        start_date: datetime,
        end_date: datetime,
        output_dir: Union[str, Path],
        concurrent_limit: int = 3,
        **kwargs: Any,
    ) -> List[ExecutionResult]:
        """Execute multiple analyzers with concurrency control.

        Args:
            analyzers: List of analyzers to execute
            customer_id: Google Ads customer ID
            start_date: Analysis start date
            end_date: Analysis end date
            output_dir: Directory to write output files
            concurrent_limit: Maximum number of concurrent executions
            **kwargs: Additional analyzer parameters

        Returns:
            List of ExecutionResult objects
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        semaphore = asyncio.Semaphore(concurrent_limit)

        async def execute_single(analyzer: Analyzer) -> ExecutionResult:
            async with semaphore:
                output_file = (
                    output_dir
                    / f"live_{analyzer.get_name().lower().replace(' ', '_')}_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                )
                return await self.execute_analyzer(
                    analyzer, customer_id, start_date, end_date, output_file, **kwargs
                )

        # Execute all analyzers concurrently with limit
        tasks = [execute_single(analyzer) for analyzer in analyzers]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert any exceptions to error results
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                analyzer = analyzers[i]
                correlation_id = str(uuid.uuid4())
                logger.error(
                    f"Analyzer execution failed with exception: {str(result)}",
                    extra={
                        "correlation_id": correlation_id,
                        "analyzer": analyzer.get_name(),
                    },
                )
                final_results.append(
                    ExecutionResult(
                        success=False,
                        correlation_id=correlation_id,
                        analyzer_name=analyzer.get_name(),
                        customer_id=customer_id,
                        error=str(result),
                    )
                )
            else:
                final_results.append(result)

        return final_results


class QuotaManager:
    """Manages API quota to prevent exhaustion during analyzer execution."""

    def __init__(
        self, daily_quota_limit: int = 50000, rate_limit_per_minute: int = 500
    ):
        """Initialize quota manager.

        Args:
            daily_quota_limit: Daily API quota limit
            rate_limit_per_minute: Rate limit per minute
        """
        self.daily_quota_limit = daily_quota_limit
        self.rate_limit_per_minute = rate_limit_per_minute
        self._quota_usage = 0
        self._last_reset = datetime.now().date()
        self._minute_usage = 0
        self._minute_start = datetime.now().replace(second=0, microsecond=0)

    async def check_quota_available(self, estimated_calls: int) -> bool:
        """Check if quota is available for estimated calls.

        Args:
            estimated_calls: Estimated number of API calls needed

        Returns:
            True if quota is available, False otherwise
        """
        await self._reset_if_needed()

        # Check daily quota
        if self._quota_usage + estimated_calls > self.daily_quota_limit:
            logger.warning(
                f"Insufficient daily quota. Current: {self._quota_usage}, "
                f"Estimated: {estimated_calls}, Limit: {self.daily_quota_limit}"
            )
            return False

        # Check per-minute rate limit
        if self._minute_usage + estimated_calls > self.rate_limit_per_minute:
            logger.warning(
                f"Rate limit would be exceeded. Current minute: {self._minute_usage}, "
                f"Estimated: {estimated_calls}, Limit: {self.rate_limit_per_minute}"
            )
            return False

        return True

    async def reserve_quota(self, calls_used: int) -> None:
        """Reserve quota for API calls.

        Args:
            calls_used: Number of API calls used
        """
        await self._reset_if_needed()
        self._quota_usage += calls_used
        self._minute_usage += calls_used

        logger.debug(
            f"Quota reserved: {calls_used} calls. "
            f"Daily usage: {self._quota_usage}/{self.daily_quota_limit}, "
            f"Minute usage: {self._minute_usage}/{self.rate_limit_per_minute}"
        )

    async def _reset_if_needed(self) -> None:
        """Reset quota counters if needed."""
        now = datetime.now()

        # Reset daily quota
        if now.date() > self._last_reset:
            self._quota_usage = 0
            self._last_reset = now.date()
            logger.info("Daily quota reset")

        # Reset minute quota
        current_minute = now.replace(second=0, microsecond=0)
        if current_minute > self._minute_start:
            self._minute_usage = 0
            self._minute_start = current_minute

    def get_quota_status(self) -> Dict[str, Any]:
        """Get current quota status.

        Returns:
            Dictionary with quota status information
        """
        return {
            "daily_usage": self._quota_usage,
            "daily_limit": self.daily_quota_limit,
            "daily_remaining": self.daily_quota_limit - self._quota_usage,
            "minute_usage": self._minute_usage,
            "minute_limit": self.rate_limit_per_minute,
            "minute_remaining": self.rate_limit_per_minute - self._minute_usage,
            "quota_percentage": (self._quota_usage / self.daily_quota_limit) * 100,
        }
