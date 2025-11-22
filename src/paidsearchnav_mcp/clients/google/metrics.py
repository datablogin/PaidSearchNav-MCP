"""API efficiency metrics tracking for Google Ads API operations."""

import logging
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class APICallMetrics:
    """Metrics for a single API call."""

    call_id: str
    operation_type: str
    customer_id: str
    query: Optional[str]
    start_time: float
    end_time: float
    response_time: float
    record_count: int
    page_count: int
    success: bool
    error_type: Optional[str] = None
    error_message: Optional[str] = None

    @property
    def timestamp(self) -> str:
        """Get ISO timestamp for the call."""
        return datetime.fromtimestamp(self.start_time).isoformat()


@dataclass
class OperationMetrics:
    """Aggregated metrics for a specific operation type."""

    operation_type: str
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    total_response_time: float = 0.0
    total_records: int = 0
    total_pages: int = 0
    pagination_errors: int = 0
    other_errors: int = 0
    first_call_time: Optional[float] = None
    last_call_time: Optional[float] = None

    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage."""
        return (self.successful_calls / max(self.total_calls, 1)) * 100

    @property
    def average_response_time(self) -> float:
        """Calculate average response time."""
        return self.total_response_time / max(self.successful_calls, 1)

    @property
    def average_records_per_call(self) -> float:
        """Calculate average records per successful call."""
        return self.total_records / max(self.successful_calls, 1)

    @property
    def average_pages_per_call(self) -> float:
        """Calculate average pages per successful call."""
        return self.total_pages / max(self.successful_calls, 1)

    @property
    def pagination_error_rate(self) -> float:
        """Calculate pagination error rate percentage."""
        return (self.pagination_errors / max(self.total_calls, 1)) * 100


class APIEfficiencyMetrics:
    """Track API call efficiency and performance metrics for Google Ads API."""

    def __init__(self, max_call_history: int = 1000):
        """Initialize metrics tracker.

        Args:
            max_call_history: Maximum number of individual call records to retain
        """
        self.max_call_history = max_call_history
        self.call_history: List[APICallMetrics] = []
        self.operation_metrics: Dict[str, OperationMetrics] = defaultdict(
            lambda: OperationMetrics(operation_type="unknown")
        )
        self._call_counter = 0
        self._active_calls: Dict[str, Dict[str, Any]] = {}

    def start_call(
        self, operation_type: str, customer_id: str, query: Optional[str] = None
    ) -> str:
        """Start tracking an API call.

        Args:
            operation_type: Type of operation (e.g., "search", "get_campaigns")
            customer_id: Google Ads customer ID
            query: GAQL query string (optional)

        Returns:
            call_id for use with end_call()
        """
        self._call_counter += 1
        call_id = (
            f"{operation_type}_{customer_id}_{self._call_counter}_{int(time.time())}"
        )

        # Store call data in a single dict instead of individual attributes
        self._active_calls[call_id] = {
            "start_time": time.time(),
            "operation_type": operation_type,
            "customer_id": customer_id,
            "query": query,
        }

        return call_id

    def end_call(
        self,
        call_id: str,
        record_count: int = 0,
        page_count: int = 1,
        success: bool = True,
        error_type: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> APICallMetrics:
        """End tracking an API call and record metrics.

        Args:
            call_id: ID returned from start_call()
            record_count: Number of records retrieved
            page_count: Number of pages retrieved
            success: Whether the call was successful
            error_type: Type of error if call failed
            error_message: Error message if call failed

        Returns:
            APICallMetrics object with call details
        """
        # Retrieve call data from active calls dictionary
        call_data = self._active_calls.get(
            call_id,
            {
                "start_time": time.time(),
                "operation_type": "unknown",
                "customer_id": "unknown",
                "query": None,
            },
        )
        start_time = call_data["start_time"]
        operation_type = call_data["operation_type"]
        customer_id = call_data["customer_id"]
        query = call_data["query"]

        end_time = time.time()
        response_time = end_time - start_time

        # Create call metrics
        call_metrics = APICallMetrics(
            call_id=call_id,
            operation_type=operation_type,
            customer_id=customer_id,
            query=query,
            start_time=start_time,
            end_time=end_time,
            response_time=response_time,
            record_count=record_count,
            page_count=page_count,
            success=success,
            error_type=error_type,
            error_message=error_message,
        )

        # Add to call history (with size limit)
        self.call_history.append(call_metrics)
        if len(self.call_history) > self.max_call_history:
            self.call_history.pop(0)

        # Update operation metrics
        op_metrics = self.operation_metrics[operation_type]
        op_metrics.operation_type = operation_type
        op_metrics.total_calls += 1

        if success:
            op_metrics.successful_calls += 1
            op_metrics.total_response_time += response_time
            op_metrics.total_records += record_count
            op_metrics.total_pages += page_count
        else:
            op_metrics.failed_calls += 1

            # Categorize errors with more specific pagination error detection
            if error_type and any(
                keyword in error_type
                for keyword in ["PAGE_SIZE", "INVALID_PAGE_SIZE", "PAGINATION"]
            ):
                op_metrics.pagination_errors += 1
            else:
                op_metrics.other_errors += 1

        # Update timing
        if op_metrics.first_call_time is None:
            op_metrics.first_call_time = start_time
        op_metrics.last_call_time = end_time

        # Clean up active call data
        if call_id in self._active_calls:
            del self._active_calls[call_id]

        logger.debug(
            f"API call completed: {operation_type}, {response_time:.3f}s, {record_count} records, success={success}"
        )

        return call_metrics

    def track_simple_call(
        self,
        operation_type: str,
        customer_id: str,
        response_time: float,
        record_count: int = 0,
        page_count: int = 1,
        success: bool = True,
        error_type: Optional[str] = None,
        error_message: Optional[str] = None,
        query: Optional[str] = None,
    ) -> APICallMetrics:
        """Track a completed API call with all metrics in one call.

        Args:
            operation_type: Type of operation
            customer_id: Google Ads customer ID
            response_time: Time taken for the call in seconds
            record_count: Number of records retrieved
            page_count: Number of pages retrieved
            success: Whether the call was successful
            error_type: Type of error if call failed
            error_message: Error message if call failed
            query: GAQL query string (optional)

        Returns:
            APICallMetrics object with call details
        """
        self._call_counter += 1
        call_id = f"{operation_type}_{customer_id}_{self._call_counter}"

        current_time = time.time()
        start_time = current_time - response_time

        call_metrics = APICallMetrics(
            call_id=call_id,
            operation_type=operation_type,
            customer_id=customer_id,
            query=query,
            start_time=start_time,
            end_time=current_time,
            response_time=response_time,
            record_count=record_count,
            page_count=page_count,
            success=success,
            error_type=error_type,
            error_message=error_message,
        )

        # Add to call history
        self.call_history.append(call_metrics)
        if len(self.call_history) > self.max_call_history:
            self.call_history.pop(0)

        # Update operation metrics
        op_metrics = self.operation_metrics[operation_type]
        op_metrics.operation_type = operation_type
        op_metrics.total_calls += 1

        if success:
            op_metrics.successful_calls += 1
            op_metrics.total_response_time += response_time
            op_metrics.total_records += record_count
            op_metrics.total_pages += page_count
        else:
            op_metrics.failed_calls += 1

            if error_type and any(
                keyword in error_type
                for keyword in ["PAGE_SIZE", "INVALID_PAGE_SIZE", "PAGINATION"]
            ):
                op_metrics.pagination_errors += 1
            else:
                op_metrics.other_errors += 1

        if op_metrics.first_call_time is None:
            op_metrics.first_call_time = start_time
        op_metrics.last_call_time = current_time

        return call_metrics

    def get_overall_metrics(self) -> Dict[str, Any]:
        """Get overall efficiency metrics across all operations.

        Returns:
            Dictionary with comprehensive efficiency metrics
        """
        if not self.operation_metrics:
            return {
                "total_operations": 0,
                "total_calls": 0,
                "overall_success_rate": 0.0,
                "overall_error_rate": 0.0,
                "pagination_error_rate": 0.0,
                "average_response_time": 0.0,
                "average_records_per_call": 0.0,
                "total_records_retrieved": 0,
                "operations": {},
            }

        total_calls = sum(om.total_calls for om in self.operation_metrics.values())
        successful_calls = sum(
            om.successful_calls for om in self.operation_metrics.values()
        )
        total_response_time = sum(
            om.total_response_time for om in self.operation_metrics.values()
        )
        total_records = sum(om.total_records for om in self.operation_metrics.values())
        pagination_errors = sum(
            om.pagination_errors for om in self.operation_metrics.values()
        )

        return {
            "total_operations": len(self.operation_metrics),
            "total_calls": total_calls,
            "successful_calls": successful_calls,
            "failed_calls": total_calls - successful_calls,
            "overall_success_rate": (successful_calls / max(total_calls, 1)) * 100,
            "overall_error_rate": (
                (total_calls - successful_calls) / max(total_calls, 1)
            )
            * 100,
            "pagination_error_rate": (pagination_errors / max(total_calls, 1)) * 100,
            "average_response_time": total_response_time / max(successful_calls, 1),
            "average_records_per_call": total_records / max(successful_calls, 1),
            "total_records_retrieved": total_records,
            "operations": {
                op_type: {
                    "total_calls": om.total_calls,
                    "success_rate": om.success_rate,
                    "average_response_time": om.average_response_time,
                    "average_records_per_call": om.average_records_per_call,
                    "pagination_error_rate": om.pagination_error_rate,
                }
                for op_type, om in self.operation_metrics.items()
            },
        }

    def get_operation_metrics(self, operation_type: str) -> Optional[OperationMetrics]:
        """Get metrics for a specific operation type.

        Args:
            operation_type: Type of operation to get metrics for

        Returns:
            OperationMetrics object or None if not found
        """
        return self.operation_metrics.get(operation_type)

    def get_recent_calls(self, limit: int = 10) -> List[APICallMetrics]:
        """Get recent API calls for debugging.

        Args:
            limit: Maximum number of recent calls to return

        Returns:
            List of recent APICallMetrics objects
        """
        return self.call_history[-limit:] if self.call_history else []

    def get_efficiency_report(self) -> Dict[str, Any]:
        """Get comprehensive efficiency report matching issue requirements.

        This method provides the KPI metrics specified in issue 392:
        - API Call Count
        - Response Time
        - Error Rate
        - Data Retrieval Efficiency
        - Rate Limit Usage (placeholder)

        Returns:
            Comprehensive efficiency report
        """
        overall_metrics = self.get_overall_metrics()

        # Add KPI-specific metrics
        report = overall_metrics.copy()
        report.update(
            {
                # KPI: API Call Count
                "api_call_count": overall_metrics["total_calls"],
                # KPI: Response Time
                "average_response_time_seconds": overall_metrics[
                    "average_response_time"
                ],
                "response_time_target_2s_met": overall_metrics["average_response_time"]
                < 2.0,
                # KPI: Error Rate
                "error_rate_percentage": overall_metrics["overall_error_rate"],
                "pagination_error_rate_percentage": overall_metrics[
                    "pagination_error_rate"
                ],
                "error_rate_target_1_percent_met": overall_metrics[
                    "pagination_error_rate"
                ]
                < 1.0,
                # KPI: Data Retrieval Efficiency
                "records_per_call": overall_metrics["average_records_per_call"],
                "efficiency_target_500_records_met": overall_metrics[
                    "average_records_per_call"
                ]
                > 500,
                # KPI: Rate Limit Usage (placeholder - would need integration with rate limiter)
                "rate_limit_usage_percentage": None,  # To be implemented with rate limiter
                "rate_limit_target_80_percent_met": None,
                # Additional debugging info
                "call_history_size": len(self.call_history),
                "recent_calls": [
                    {
                        "operation": call.operation_type,
                        "response_time": call.response_time,
                        "records": call.record_count,
                        "success": call.success,
                        "error_type": call.error_type,
                    }
                    for call in self.get_recent_calls(5)
                ],
            }
        )

        return report

    def clear_metrics(self):
        """Clear all metrics and reset counters."""
        self.call_history.clear()
        self.operation_metrics.clear()
        self._active_calls.clear()
        self._call_counter = 0

    def log_summary(self, logger_instance: Optional[logging.Logger] = None):
        """Log a summary of current metrics.

        Args:
            logger_instance: Logger to use (defaults to module logger)
        """
        log = logger_instance or logger

        metrics = self.get_overall_metrics()

        log.info("API Efficiency Summary:")
        log.info(f"  Total API calls: {metrics['total_calls']}")
        log.info(f"  Success rate: {metrics['overall_success_rate']:.1f}%")
        log.info(f"  Average response time: {metrics['average_response_time']:.3f}s")
        log.info(
            f"  Average records per call: {metrics['average_records_per_call']:.1f}"
        )
        log.info(f"  Pagination error rate: {metrics['pagination_error_rate']:.1f}%")

        if metrics["operations"]:
            log.info("  Per-operation breakdown:")
            for op_type, op_metrics in metrics["operations"].items():
                log.info(
                    f"    {op_type}: {op_metrics['total_calls']} calls, "
                    f"{op_metrics['success_rate']:.1f}% success, "
                    f"{op_metrics['average_response_time']:.3f}s avg"
                )


# Global instance for easy access across the application
_global_metrics: Optional[APIEfficiencyMetrics] = None


def get_global_metrics() -> APIEfficiencyMetrics:
    """Get or create the global metrics instance."""
    global _global_metrics
    if _global_metrics is None:
        _global_metrics = APIEfficiencyMetrics()
    return _global_metrics


def reset_global_metrics():
    """Reset the global metrics instance."""
    global _global_metrics
    _global_metrics = None
