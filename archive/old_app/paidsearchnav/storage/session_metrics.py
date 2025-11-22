"""Session metrics and counters for optimized logging in high-throughput scenarios."""

import logging
import threading
import time
from collections import OrderedDict, defaultdict
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class SessionMetrics:
    """Thread-safe session metrics collector for optimized logging.

    Note: In long-running processes, customer-specific counters may accumulate.
    Call cleanup_old_metrics() periodically or use max_customer_entries to limit growth.
    """

    def __init__(
        self,
        log_interval: float = 60.0,
        enabled: bool = True,
        max_customer_entries: int = 10000,
        cleanup_interval: float = 3600.0,  # 1 hour
    ):
        """Initialize session metrics.

        Args:
            log_interval: Interval in seconds to log aggregated metrics
            enabled: Whether to enable detailed metrics collection
            max_customer_entries: Maximum number of customer-specific entries to track
            cleanup_interval: Interval for automatic cleanup of old entries (seconds)
        """
        self.enabled = enabled
        self.log_interval = log_interval
        self.max_customer_entries = max_customer_entries
        self.cleanup_interval = cleanup_interval
        self._lock = threading.Lock()
        self._counters: Dict[str, int] = defaultdict(int)
        self._active_sessions: Dict[str, int] = defaultdict(int)
        self._customer_counters: OrderedDict[str, int] = OrderedDict()
        self._last_log_time = time.time()
        self._last_cleanup_time = time.time()
        self._start_time = time.time()

    def session_opened(self, operation: str, customer_id: Optional[str] = None) -> None:
        """Record a session opening."""
        if not self.enabled:
            return

        with self._lock:
            self._counters[f"{operation}_opened"] += 1
            self._active_sessions[operation] += 1

            if customer_id:
                self._track_customer_session(customer_id)

            # Log aggregated metrics if interval exceeded
            self._maybe_log_metrics()
            # Cleanup old entries if needed
            self._maybe_cleanup_metrics()

    def session_closed(self, operation: str, success: bool = True) -> None:
        """Record a session closing."""
        if not self.enabled:
            return

        with self._lock:
            self._counters[f"{operation}_closed"] += 1
            self._active_sessions[operation] = max(
                0, self._active_sessions[operation] - 1
            )

            if success:
                self._counters[f"{operation}_success"] += 1
            else:
                self._counters[f"{operation}_failed"] += 1

            self._maybe_log_metrics()
            self._maybe_cleanup_metrics()

    def get_active_sessions(self, operation: Optional[str] = None) -> int:
        """Get count of currently active sessions."""
        with self._lock:
            if operation:
                return self._active_sessions.get(operation, 0)
            return sum(self._active_sessions.values())

    def get_total_sessions(self, operation: Optional[str] = None) -> int:
        """Get total sessions opened."""
        with self._lock:
            if operation:
                return self._counters.get(f"{operation}_opened", 0)
            return sum(v for k, v in self._counters.items() if k.endswith("_opened"))

    def _maybe_log_metrics(self) -> None:
        """Log metrics if interval has passed (must be called with lock held)."""
        current_time = time.time()
        if current_time - self._last_log_time >= self.log_interval:
            self._log_metrics()
            self._last_log_time = current_time

    def _log_metrics(self) -> None:
        """Log aggregated metrics (must be called with lock held)."""
        if not self._counters and not self._active_sessions:
            return

        uptime = time.time() - self._start_time
        total_sessions = sum(
            v for k, v in self._counters.items() if k.endswith("_opened")
        )
        total_active = sum(self._active_sessions.values())

        logger.info(
            f"Session metrics - Uptime: {uptime:.1f}s, "
            f"Total sessions: {total_sessions}, "
            f"Active sessions: {total_active}"
        )

        # Log per-operation metrics
        operations = set()
        for key in self._counters:
            if "_opened" in key:
                operations.add(key.replace("_opened", ""))

        for op in operations:
            opened = self._counters.get(f"{op}_opened", 0)
            closed = self._counters.get(f"{op}_closed", 0)
            success = self._counters.get(f"{op}_success", 0)
            failed = self._counters.get(f"{op}_failed", 0)
            active = self._active_sessions.get(op, 0)

            if opened > 0:
                logger.debug(
                    f"Operation '{op}' - "
                    f"Opened: {opened}, Closed: {closed}, "
                    f"Success: {success}, Failed: {failed}, "
                    f"Active: {active}"
                )

    def force_log_metrics(self) -> None:
        """Force immediate logging of metrics."""
        with self._lock:
            self._log_metrics()

    def reset_metrics(self) -> None:
        """Reset all metrics counters."""
        with self._lock:
            self._counters.clear()
            self._active_sessions.clear()
            self._customer_counters.clear()
            self._start_time = time.time()
            self._last_log_time = time.time()
            self._last_cleanup_time = time.time()

    def _track_customer_session(self, customer_id: str) -> None:
        """Track customer session with LRU-like behavior (must be called with lock held)."""
        # Update or add customer to the end (most recent)
        if customer_id in self._customer_counters:
            count = self._customer_counters.pop(customer_id)
            self._customer_counters[customer_id] = count + 1
        else:
            self._customer_counters[customer_id] = 1

        # Limit the size by removing oldest entries
        while len(self._customer_counters) > self.max_customer_entries:
            oldest_customer = next(iter(self._customer_counters))
            del self._customer_counters[oldest_customer]
            # Also remove from main counters
            counter_key = f"customer_{oldest_customer}_sessions"
            if counter_key in self._counters:
                del self._counters[counter_key]

        # Update main counter
        self._counters[f"customer_{customer_id}_sessions"] = self._customer_counters[
            customer_id
        ]

    def _maybe_cleanup_metrics(self) -> None:
        """Cleanup old metrics if interval has passed (must be called with lock held)."""
        current_time = time.time()
        if current_time - self._last_cleanup_time >= self.cleanup_interval:
            self._cleanup_old_metrics()
            self._last_cleanup_time = current_time

    def _cleanup_old_metrics(self) -> None:
        """Remove inactive entries from metrics (must be called with lock held)."""
        # Clean up operation-specific counters for operations with no active sessions
        counters_to_remove = []
        for key in self._counters:
            if key.endswith(("_opened", "_closed", "_success", "_failed")):
                operation = key.rsplit("_", 1)[0]
                # Remove metrics for operations that have no active sessions
                if self._active_sessions.get(operation, 0) == 0:
                    counters_to_remove.append(key)

        for key in counters_to_remove:
            del self._counters[key]

        logger.debug(f"Cleaned up {len(counters_to_remove)} inactive metric entries")

    def cleanup_old_metrics(self) -> None:
        """Manually trigger cleanup of old metrics."""
        with self._lock:
            self._cleanup_old_metrics()


# Global session metrics instance
_session_metrics: Optional[SessionMetrics] = None


def get_session_metrics() -> SessionMetrics:
    """Get the global session metrics instance."""
    global _session_metrics
    if _session_metrics is None:
        _session_metrics = SessionMetrics()
    return _session_metrics


def configure_session_metrics(
    log_interval: float = 60.0,
    enabled: bool = True,
    max_customer_entries: int = 10000,
    cleanup_interval: float = 3600.0,
) -> None:
    """Configure the global session metrics instance."""
    global _session_metrics
    _session_metrics = SessionMetrics(
        log_interval=log_interval,
        enabled=enabled,
        max_customer_entries=max_customer_entries,
        cleanup_interval=cleanup_interval,
    )
