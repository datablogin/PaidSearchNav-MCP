"""Database connection pool monitoring metrics."""

import logging
import random
import re
import time
from typing import Any, Dict

from prometheus_client import Counter, Gauge, Histogram
from sqlalchemy.pool import NullPool, QueuePool

logger = logging.getLogger(__name__)

# Pre-compiled regex patterns for performance
URL_PASSWORD_PATTERN = re.compile(r"://[^:]+:[^@]+@")

# Sampling configuration
DEFAULT_SAMPLE_RATE = 0.1  # Sample 10% of events under high load
HIGH_LOAD_THRESHOLD = 100  # Consider high load above 100 events/second
METRICS_WINDOW_SIZE = 60  # Track events over 60 seconds

# Prometheus metrics for database connection pools
db_pool_size = Gauge(
    "paidsearchnav_db_pool_size",
    "Total number of connections in the pool",
    ["database"],
)

db_pool_checked_out = Gauge(
    "paidsearchnav_db_pool_checked_out",
    "Number of connections currently checked out",
    ["database"],
)

db_pool_checked_in = Gauge(
    "paidsearchnav_db_pool_checked_in",
    "Number of connections currently checked in (available)",
    ["database"],
)

db_pool_overflow = Gauge(
    "paidsearchnav_db_pool_overflow",
    "Number of overflow connections currently in use",
    ["database"],
)

db_pool_total = Gauge(
    "paidsearchnav_db_pool_total", "Total connections (pool + overflow)", ["database"]
)

db_connection_wait_time = Histogram(
    "paidsearchnav_db_connection_wait_seconds",
    "Time spent waiting for a database connection",
    ["database"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)

db_connection_errors = Counter(
    "paidsearchnav_db_connection_errors_total",
    "Total number of database connection errors",
    ["database", "error_type"],
)

db_connection_created = Counter(
    "paidsearchnav_db_connections_created_total",
    "Total number of new database connections created",
    ["database"],
)

db_connection_recycled = Counter(
    "paidsearchnav_db_connections_recycled_total",
    "Total number of database connections recycled",
    ["database"],
)


class DatabasePoolMonitor:
    """Monitor and collect metrics for database connection pools."""

    def __init__(self, engine, database_name: str = "main", sample_rate: float = 1.0):
        """Initialize the monitor with a SQLAlchemy engine.

        Args:
            engine: SQLAlchemy engine instance
            database_name: Name to identify this database in metrics
            sample_rate: Initial sampling rate (1.0 = 100%, 0.1 = 10%)
        """
        self.engine = engine
        self.database_name = database_name
        self.sample_rate = sample_rate
        self._event_count = 0
        self._event_window_start = time.time()
        self._last_metrics_update = 0
        self._metrics_update_interval = 1.0  # Update metrics at most once per second
        self._setup_pool_events()

    def _should_sample(self) -> bool:
        """Determine if this event should be sampled based on current load."""
        # Always sample if rate is 1.0
        if self.sample_rate >= 1.0:
            return True

        # Use random sampling
        return random.random() < self.sample_rate

    def _adjust_sample_rate(self):
        """Adjust sampling rate based on event frequency."""
        current_time = time.time()
        window_duration = current_time - self._event_window_start

        # Reset window if needed
        if window_duration >= METRICS_WINDOW_SIZE:
            events_per_second = self._event_count / window_duration

            # Adjust sampling rate based on load
            if events_per_second > HIGH_LOAD_THRESHOLD:
                # Under high load, reduce sampling
                self.sample_rate = max(DEFAULT_SAMPLE_RATE, self.sample_rate * 0.9)
                logger.info(
                    f"High load detected ({events_per_second:.1f} events/s), "
                    f"adjusted sample rate to {self.sample_rate:.2f}"
                )
            elif events_per_second < HIGH_LOAD_THRESHOLD / 2:
                # Under low load, increase sampling back towards 1.0
                self.sample_rate = min(1.0, self.sample_rate * 1.1)

            # Reset counters
            self._event_count = 0
            self._event_window_start = current_time

    def _setup_pool_events(self):
        """Set up event listeners for connection pool events."""
        from sqlalchemy import event

        # Track connection creation
        @event.listens_for(self.engine, "connect")
        def receive_connect(dbapi_conn, connection_record):
            if self._should_sample():
                db_connection_created.labels(database=self.database_name).inc()
                logger.debug(f"New connection created for {self.database_name}")

        # Track connection checkout
        @event.listens_for(self.engine, "checkout")
        def receive_checkout(dbapi_conn, connection_record, connection_proxy):
            self._event_count += 1
            self._adjust_sample_rate()

            # Rate-limit metrics collection
            current_time = time.time()
            if (
                current_time - self._last_metrics_update
                >= self._metrics_update_interval
            ):
                if self._should_sample():
                    self.collect_metrics()
                    self._last_metrics_update = current_time

        # Track connection checkin
        @event.listens_for(self.engine, "checkin")
        def receive_checkin(dbapi_conn, connection_record):
            self._event_count += 1

            # Rate-limit metrics collection
            current_time = time.time()
            if (
                current_time - self._last_metrics_update
                >= self._metrics_update_interval
            ):
                if self._should_sample():
                    self.collect_metrics()
                    self._last_metrics_update = current_time

        # Track connection invalidation
        @event.listens_for(self.engine, "invalidate")
        def receive_invalidate(dbapi_conn, connection_record, exception):
            if exception and self._should_sample():
                error_type = type(exception).__name__
                db_connection_errors.labels(
                    database=self.database_name, error_type=error_type
                ).inc()
                logger.warning(
                    f"Connection invalidated for {self.database_name}: {error_type}"
                )

    def collect_metrics(self) -> Dict[str, Any]:
        """Collect current pool metrics and update Prometheus metrics.

        Returns:
            Dictionary containing current pool metrics
        """
        metrics = {
            "database": self.database_name,
            "pool_type": type(self.engine.pool).__name__,
            "url": self._sanitize_url(str(self.engine.url)),
        }

        pool = self.engine.pool

        # Handle different pool types
        if isinstance(pool, NullPool):
            # NullPool doesn't maintain connections
            metrics.update(
                {
                    "pool_size": 0,
                    "checked_out": 0,
                    "checked_in": 0,
                    "overflow": 0,
                    "total": 0,
                }
            )
        elif isinstance(pool, QueuePool):
            # QueuePool provides detailed statistics
            metrics.update(
                {
                    "pool_size": pool.size(),
                    "checked_out": pool.checked_out(),
                    "checked_in": pool.checked_in(),
                    "overflow": pool.overflow(),
                    "total": pool.total(),
                }
            )

            # Update Prometheus metrics
            db_pool_size.labels(database=self.database_name).set(pool.size())
            db_pool_checked_out.labels(database=self.database_name).set(
                pool.checked_out()
            )
            db_pool_checked_in.labels(database=self.database_name).set(
                pool.checked_in()
            )
            db_pool_overflow.labels(database=self.database_name).set(pool.overflow())
            db_pool_total.labels(database=self.database_name).set(pool.total())
        else:
            # Generic pool handling
            logger.warning(f"Unknown pool type: {type(pool).__name__}")
            metrics.update(
                {
                    "pool_size": getattr(pool, "_pool_size", 0),
                    "checked_out": 0,
                    "checked_in": 0,
                    "overflow": 0,
                    "total": 0,
                }
            )

        # Calculate utilization percentage
        if metrics["pool_size"] > 0:
            metrics["utilization_percent"] = (
                metrics["checked_out"] / metrics["pool_size"] * 100
            )
        else:
            metrics["utilization_percent"] = 0.0

        # Add sampling info to metrics
        metrics["sampling_rate"] = self.sample_rate
        metrics["events_per_second"] = (
            self._event_count / (time.time() - self._event_window_start)
            if time.time() > self._event_window_start
            else 0
        )

        return metrics

    def get_health_status(self) -> Dict[str, Any]:
        """Get health status of the connection pool.

        Returns:
            Dictionary containing health status and recommendations
        """
        metrics = self.collect_metrics()

        health = {
            "status": "healthy",
            "metrics": metrics,
            "warnings": [],
            "recommendations": [],
        }

        # Check for high utilization
        if metrics["utilization_percent"] > 80:
            health["status"] = "warning"
            health["warnings"].append(
                f"High pool utilization: {metrics['utilization_percent']:.1f}%"
            )
            health["recommendations"].append(
                "Consider increasing pool_size or investigating slow queries"
            )

        # Check for excessive overflow usage
        if metrics["overflow"] > metrics["pool_size"] * 0.5:
            health["status"] = "warning"
            health["warnings"].append(
                f"High overflow usage: {metrics['overflow']} connections"
            )
            health["recommendations"].append(
                "Consider increasing pool_size to reduce overflow usage"
            )

        # Check if all connections are exhausted
        if (
            metrics["checked_in"] == 0
            and metrics["checked_out"] >= metrics["pool_size"]
        ):
            health["status"] = "critical"
            health["warnings"].append("Connection pool exhausted")
            health["recommendations"].append(
                "Immediately investigate connection leaks or increase pool limits"
            )

        return health

    def _sanitize_url(self, url: str) -> str:
        """Remove sensitive information from database URLs.

        Args:
            url: Database URL string

        Returns:
            Sanitized URL without credentials
        """
        # Use pre-compiled regex pattern for better performance
        return URL_PASSWORD_PATTERN.sub("://***:***@", url)


def create_pool_monitor(engine, database_name: str = "main") -> DatabasePoolMonitor:
    """Create a database pool monitor for the given engine.

    Args:
        engine: SQLAlchemy engine instance
        database_name: Name to identify this database in metrics

    Returns:
        DatabasePoolMonitor instance
    """
    return DatabasePoolMonitor(engine, database_name)
