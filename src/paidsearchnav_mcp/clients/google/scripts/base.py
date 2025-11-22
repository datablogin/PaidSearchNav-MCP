"""Base classes for Google Ads Scripts integration."""

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, TypedDict

from paidsearchnav.platforms.google.client import GoogleAdsClient

from .logging_utils import get_structured_logger, set_correlation_id
from .validation import ParameterValidator, is_retryable_error

logger = logging.getLogger(__name__)


class RateLimiter:
    """Configurable rate limiter for API calls with script-specific limits."""

    # Default rate limits per script type
    DEFAULT_LIMITS = {
        "performance_max_monitoring": {"calls_per_second": 1.5, "calls_per_minute": 80},
        "performance_max_assets": {"calls_per_second": 2.0, "calls_per_minute": 100},
        "performance_max_geographic": {"calls_per_second": 1.0, "calls_per_minute": 60},
        "performance_max_bidding": {"calls_per_second": 1.5, "calls_per_minute": 90},
        "performance_max_cross_campaign": {
            "calls_per_second": 0.8,
            "calls_per_minute": 50,
        },
        "default": {"calls_per_second": 1.0, "calls_per_minute": 60},
    }

    def __init__(
        self,
        calls_per_second: Optional[float] = None,
        calls_per_minute: Optional[int] = None,
        script_type: str = "default",
    ):
        # Use script-specific defaults if not provided
        limits = self.DEFAULT_LIMITS.get(script_type, self.DEFAULT_LIMITS["default"])

        self.calls_per_second = calls_per_second or limits["calls_per_second"]
        self.calls_per_minute = calls_per_minute or limits["calls_per_minute"]
        self.script_type = script_type
        self.call_times: List[float] = []
        self.min_interval = 1.0 / self.calls_per_second

    @classmethod
    def for_script_type(cls, script_type: str) -> "RateLimiter":
        """Create a rate limiter optimized for a specific script type."""
        return cls(script_type=script_type)

    def wait_if_needed(self):
        """Wait if necessary to respect rate limits."""
        now = time.time()

        # Clean up old call times (older than 1 minute)
        self.call_times = [t for t in self.call_times if now - t < 60]

        # Check per-minute limit
        if len(self.call_times) >= self.calls_per_minute:
            oldest_in_minute = self.call_times[0]
            wait_time = 60 - (now - oldest_in_minute) + 0.1
            if wait_time > 0:
                logger.info(f"Rate limit reached, waiting {wait_time:.1f} seconds")
                time.sleep(wait_time)
                now = time.time()

        # Check per-second limit
        if self.call_times:
            last_call = self.call_times[-1]
            elapsed = now - last_call
            if elapsed < self.min_interval:
                wait_time = self.min_interval - elapsed
                time.sleep(wait_time)
                now = time.time()

        self.call_times.append(now)


class ScriptStatus(Enum):
    """Script execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ScriptType(Enum):
    """Types of Google Ads Scripts."""

    NEGATIVE_KEYWORD = "negative_keyword"
    CONFLICT_DETECTION = "conflict_detection"
    PLACEMENT_AUDIT = "placement_audit"
    MASTER_NEGATIVE_LIST = "master_negative_list"
    N_GRAM_ANALYSIS = "n_gram_analysis"
    # Performance Max Script Types
    PERFORMANCE_MAX_MONITORING = "performance_max_monitoring"
    PERFORMANCE_MAX_ASSETS = "performance_max_assets"
    PERFORMANCE_MAX_GEOGRAPHIC = "performance_max_geographic"
    PERFORMANCE_MAX_BIDDING = "performance_max_bidding"
    PERFORMANCE_MAX_CROSS_CAMPAIGN = "performance_max_cross_campaign"


class ScriptResult(TypedDict):
    """Script execution result."""

    status: str
    execution_time: float
    rows_processed: int
    changes_made: int
    errors: List[str]
    warnings: List[str]
    details: Dict[str, Any]


@dataclass
class ScriptConfig:
    """Configuration for a Google Ads Script."""

    name: str
    type: ScriptType
    description: str
    schedule: Optional[str] = None  # Cron expression
    enabled: bool = True
    parameters: Dict[str, Any] = None

    def __post_init__(self):
        if self.parameters is None:
            self.parameters = {}


class ScriptBase(ABC):
    """Base class for all Google Ads Scripts."""

    def __init__(self, client: GoogleAdsClient, config: ScriptConfig):
        self.client = client
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.validator = ParameterValidator()

        # Validate and sanitize parameters on initialization
        try:
            self.config.parameters = self.validator.validate_script_parameters(
                self.config.parameters, self.config.type.value
            )
        except Exception as e:
            self.logger.error(f"Parameter validation failed: {e}")
            raise

    @abstractmethod
    def generate_script(self) -> str:
        """Generate the Google Ads Script code."""
        pass

    @abstractmethod
    def process_results(self, results: Dict[str, Any]) -> ScriptResult:
        """Process script execution results."""
        pass

    def validate_parameters(self) -> bool:
        """Validate script parameters."""
        required_params = self.get_required_parameters()
        for param in required_params:
            if param not in self.config.parameters:
                self.logger.error(f"Missing required parameter: {param}")
                return False
        return True

    @abstractmethod
    def get_required_parameters(self) -> List[str]:
        """Get list of required parameters for this script."""
        pass

    def get_script_metadata(self) -> Dict[str, Any]:
        """Get script metadata for tracking."""
        return {
            "name": self.config.name,
            "type": self.config.type.value,
            "description": self.config.description,
            "created_at": datetime.utcnow().isoformat(),
            "parameters": self.config.parameters,
        }


class ScriptExecutor:
    """Executes Google Ads Scripts and manages their lifecycle."""

    def __init__(
        self, client: GoogleAdsClient, rate_limiter: Optional[RateLimiter] = None
    ):
        self.client = client
        self.logger = get_structured_logger(f"{__name__}.{self.__class__.__name__}")
        self._scripts: Dict[str, ScriptBase] = {}
        self.rate_limiter = rate_limiter or RateLimiter.for_script_type("default")
        self.execution_metrics = {
            "total_executions": 0,
            "successful_executions": 0,
            "failed_executions": 0,
            "total_execution_time": 0.0,
            "avg_execution_time": 0.0,
            "retry_counts": {},
            "error_counts": {},
            "script_type_metrics": {},
        }

    def register_script(self, script: ScriptBase) -> str:
        """Register a script for execution."""
        script_id = f"{script.config.type.value}_{datetime.utcnow().timestamp()}"
        self._scripts[script_id] = script
        self.logger.info(f"Registered script: {script_id}")
        return script_id

    def execute_script(self, script_id: str) -> ScriptResult:
        """Execute a registered script."""
        # Set correlation ID for this execution
        correlation_id = set_correlation_id()

        if script_id not in self._scripts:
            raise ValueError(f"Script not found: {script_id}")

        script = self._scripts[script_id]

        self.logger.info(
            "Starting script execution",
            extra={
                "script_id": script_id,
                "script_type": script.config.type.value,
                "script_name": script.config.name,
            },
        )

        # Validate parameters
        if not script.validate_parameters():
            self.logger.error(
                "Script validation failed",
                extra={"script_id": script_id, "reason": "Invalid parameters"},
            )
            return ScriptResult(
                status=ScriptStatus.FAILED.value,
                execution_time=0.0,
                rows_processed=0,
                changes_made=0,
                errors=["Invalid parameters"],
                warnings=[],
                details={},
            )

        start_time = datetime.utcnow()
        script_type = script.config.type.value
        retry_count = 0

        try:
            # Generate script code
            script_code = script.generate_script()

            # Execute script via Google Ads Scripts API with retry tracking
            # Note: This is a placeholder for actual API implementation
            results, retry_count = self._execute_ads_script_with_metrics(
                script_code, script.config.parameters
            )

            # Process results
            script_result = script.process_results(results)

            execution_time = (datetime.utcnow() - start_time).total_seconds()
            script_result["execution_time"] = execution_time

            # Update success metrics
            self._update_execution_metrics(
                script_type, execution_time, True, retry_count
            )

            self.logger.info(
                "Script execution completed",
                extra={
                    "script_id": script_id,
                    "execution_time": execution_time,
                    "rows_processed": script_result.get("rows_processed", 0),
                    "changes_made": script_result.get("changes_made", 0),
                    "status": script_result["status"],
                    "retry_count": retry_count,
                },
            )

            return script_result

        except Exception as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds()

            # Update failure metrics
            self._update_execution_metrics(
                script_type, execution_time, False, retry_count, str(e)
            )

            self.logger.error(
                "Script execution failed",
                extra={
                    "script_id": script_id,
                    "execution_time": execution_time,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "retry_count": retry_count,
                },
                exc_info=True,
            )
            return ScriptResult(
                status=ScriptStatus.FAILED.value,
                execution_time=execution_time,
                rows_processed=0,
                changes_made=0,
                errors=[str(e)],
                warnings=[],
                details={},
            )

    def _execute_ads_script_with_metrics(
        self, script_code: str, parameters: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], int]:
        """Execute script and return results with retry count for metrics tracking."""
        result = self._execute_ads_script(script_code, parameters)
        # For now, return 0 retries - actual retry counting would be implemented in real API calls
        return result, 0

    def _execute_ads_script(
        self, script_code: str, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute script via Google Ads Scripts API with rate limiting and retry logic.

        Args:
            script_code: The Google Ads Script code to execute
            parameters: Parameters for the script

        Returns:
            Dict containing execution results

        Raises:
            Exception: If all retry attempts fail or error is non-retryable
        """
        max_retries = 3
        retry_delay = 1.0

        for attempt in range(max_retries):
            try:
                # Apply rate limiting
                self.rate_limiter.wait_if_needed()

                # Execute script using Google Ads Scripts API
                # This is a simplified implementation for demonstration
                # In practice, Google Ads Scripts are executed within the Google Ads interface
                self.logger.info(
                    f"Executing script (attempt {attempt + 1}/{max_retries})"
                )

                # Simulate script execution based on parameters and code
                result = self._simulate_script_execution(script_code, parameters)

                self.logger.info("Script execution completed successfully")
                return result

            except Exception as e:
                error_message = str(e)

                # Check if the error is retryable based on error code/message
                is_retryable = self._is_error_retryable(error_message)

                if not is_retryable:
                    self.logger.error(
                        f"Non-retryable error encountered: {error_message}. Failing immediately."
                    )
                    raise

                if attempt < max_retries - 1:
                    # Calculate exponential backoff with jitter
                    backoff_delay = retry_delay * (2**attempt) + (0.1 * attempt)

                    self.logger.warning(
                        f"Retryable error on attempt {attempt + 1}/{max_retries}: {error_message}. "
                        f"Retrying in {backoff_delay:.1f} seconds..."
                    )
                    time.sleep(backoff_delay)
                else:
                    self.logger.error(
                        f"Script execution failed after {max_retries} attempts with retryable error: {error_message}"
                    )
                    raise

    def _is_error_retryable(self, error_message: str) -> bool:
        """Check if an error is retryable based on error message or code.

        Args:
            error_message: The error message to check

        Returns:
            True if the error should be retried
        """
        error_lower = error_message.lower()

        # Check for specific Google Ads API error patterns
        retryable_patterns = [
            "rate limit",
            "quota exceeded",
            "temporarily unavailable",
            "service unavailable",
            "internal error",
            "backend error",
            "deadline exceeded",
            "timeout",
            "connection reset",
            "connection refused",
            "network error",
        ]

        for pattern in retryable_patterns:
            if pattern in error_lower:
                return True

        # Also check using the validation utility
        # Extract error code if present (format: "ERROR_CODE: message")
        if ":" in error_message:
            potential_code = error_message.split(":")[0].strip().upper()
            return is_retryable_error(potential_code)

        return False

    def _update_execution_metrics(
        self,
        script_type: str,
        execution_time: float,
        success: bool,
        retry_count: int,
        error_message: Optional[str] = None,
    ) -> None:
        """Update execution metrics for monitoring and analysis.

        Args:
            script_type: Type of script that was executed
            execution_time: Time taken for execution in seconds
            success: Whether the execution was successful
            retry_count: Number of retries that occurred
            error_message: Error message if execution failed
        """
        # Update global metrics
        self.execution_metrics["total_executions"] += 1
        self.execution_metrics["total_execution_time"] += execution_time
        self.execution_metrics["avg_execution_time"] = (
            self.execution_metrics["total_execution_time"]
            / self.execution_metrics["total_executions"]
        )

        if success:
            self.execution_metrics["successful_executions"] += 1
        else:
            self.execution_metrics["failed_executions"] += 1

            # Track error types
            if error_message:
                error_type = (
                    error_message.split(":")[0].strip()
                    if ":" in error_message
                    else "UNKNOWN_ERROR"
                )
                self.execution_metrics["error_counts"][error_type] = (
                    self.execution_metrics["error_counts"].get(error_type, 0) + 1
                )

        # Track retry counts
        if retry_count > 0:
            self.execution_metrics["retry_counts"][str(retry_count)] = (
                self.execution_metrics["retry_counts"].get(str(retry_count), 0) + 1
            )

        # Update script-type specific metrics
        if script_type not in self.execution_metrics["script_type_metrics"]:
            self.execution_metrics["script_type_metrics"][script_type] = {
                "total_executions": 0,
                "successful_executions": 0,
                "failed_executions": 0,
                "total_execution_time": 0.0,
                "avg_execution_time": 0.0,
            }

        type_metrics = self.execution_metrics["script_type_metrics"][script_type]
        type_metrics["total_executions"] += 1
        type_metrics["total_execution_time"] += execution_time
        type_metrics["avg_execution_time"] = (
            type_metrics["total_execution_time"] / type_metrics["total_executions"]
        )

        if success:
            type_metrics["successful_executions"] += 1
        else:
            type_metrics["failed_executions"] += 1

    def get_execution_metrics(self) -> Dict[str, Any]:
        """Get current execution metrics for monitoring and reporting.

        Returns:
            Dictionary containing current execution metrics
        """
        # Calculate success rates
        total_executions = self.execution_metrics["total_executions"]
        if total_executions > 0:
            success_rate = (
                self.execution_metrics["successful_executions"] / total_executions
            )
            failure_rate = (
                self.execution_metrics["failed_executions"] / total_executions
            )
        else:
            success_rate = 0.0
            failure_rate = 0.0

        # Add calculated metrics
        metrics = self.execution_metrics.copy()
        metrics["success_rate"] = success_rate
        metrics["failure_rate"] = failure_rate
        metrics["last_updated"] = datetime.utcnow().isoformat()

        return metrics

    def reset_execution_metrics(self) -> None:
        """Reset execution metrics (useful for testing or periodic resets)."""
        self.execution_metrics = {
            "total_executions": 0,
            "successful_executions": 0,
            "failed_executions": 0,
            "total_execution_time": 0.0,
            "avg_execution_time": 0.0,
            "retry_counts": {},
            "error_counts": {},
            "script_type_metrics": {},
        }

    def _simulate_script_execution(
        self, script_code: str, parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Simulate script execution for demonstration purposes."""
        # In real implementation, this would call Google Ads Scripts API
        # For now, return realistic results based on script content

        rows_processed = (
            parameters.get("lookback_days", 30) * 10
        )  # Simulate data volume
        changes_made = max(1, rows_processed // 20)  # Simulate changes

        # Simulate potential transient errors occasionally
        import random

        error_chance = random.random()
        if error_chance < 0.02:  # 2% chance of retryable error
            retryable_errors = [
                "RATE_LIMIT_EXCEEDED: API quota exceeded",
                "TEMPORARILY_UNAVAILABLE: Service temporarily unavailable",
                "INTERNAL_ERROR: Internal server error occurred",
                "DEADLINE_EXCEEDED: Request timeout",
                "Network error: Connection reset by peer",
            ]
            raise Exception(random.choice(retryable_errors))
        elif error_chance < 0.03:  # 1% chance of non-retryable error
            non_retryable_errors = [
                "INVALID_CUSTOMER_ID: Customer ID is invalid",
                "PERMISSION_DENIED: Access denied for this resource",
                "RESOURCE_NOT_FOUND: Campaign not found",
            ]
            raise Exception(random.choice(non_retryable_errors))

        return {
            "success": True,
            "rows_processed": rows_processed,
            "changes_made": changes_made,
            "details": {
                "script_type_detected": self._detect_script_type(script_code),
                "parameters_used": parameters,
            },
            "warnings": []
            if random.random() > 0.3
            else ["Some items required manual review"],
        }

    def _detect_script_type(self, script_code: str) -> str:
        """Detect script type from code content."""
        code_lower = script_code.lower()

        if "negativekeyword" in code_lower or "negative keyword" in code_lower:
            return "negative_keyword"
        elif "conflict" in code_lower:
            return "conflict_detection"
        elif "placement" in code_lower:
            return "placement_audit"
        else:
            return "custom"

    def get_script_status(self, script_id: str) -> Optional[ScriptStatus]:
        """Get the status of a script."""
        # For the basic executor, we don't track individual executions
        # This would be implemented in the GoogleAdsScriptRunner
        self.logger.warning(
            "get_script_status not implemented in ScriptExecutor. "
            "Use GoogleAdsScriptRunner for full execution tracking."
        )
        return ScriptStatus.PENDING

    def cancel_script(self, script_id: str) -> bool:
        """Cancel a running script."""
        # For the basic executor, we don't track individual executions
        # This would be implemented in the GoogleAdsScriptRunner
        self.logger.warning(
            "cancel_script not implemented in ScriptExecutor. "
            "Use GoogleAdsScriptRunner for full execution management."
        )
        return False

    def get_script_history(
        self, script_type: Optional[ScriptType] = None
    ) -> List[Dict[str, Any]]:
        """Get execution history for scripts."""
        # For the basic executor, we don't track execution history
        # This would be implemented in the GoogleAdsScriptRunner
        self.logger.warning(
            "get_script_history not implemented in ScriptExecutor. "
            "Use GoogleAdsScriptRunner for full execution tracking."
        )
        return []
