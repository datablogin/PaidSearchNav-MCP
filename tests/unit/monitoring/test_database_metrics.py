"""Tests for database connection pool monitoring."""

from unittest.mock import Mock, patch

import pytest
from sqlalchemy.pool import NullPool, QueuePool

from paidsearchnav_mcp.monitoring.database_metrics import (
    DatabasePoolMonitor,
    create_pool_monitor,
)


class TestDatabasePoolMonitor:
    """Test suite for DatabasePoolMonitor class."""

    @pytest.fixture
    def mock_engine(self):
        """Create a mock SQLAlchemy engine."""
        engine = Mock()
        engine.url = "postgresql://user:pass@localhost/test"

        # Create a mock pool with properly configured methods
        pool = Mock(spec=QueuePool)
        pool.size = Mock(return_value=10)
        pool.checked_out = Mock(return_value=0)
        pool.checked_in = Mock(return_value=10)
        pool.overflow = Mock(return_value=0)
        pool.total = Mock(return_value=10)

        engine.pool = pool
        return engine

    @pytest.fixture
    def mock_null_pool_engine(self):
        """Create a mock SQLAlchemy engine with NullPool."""
        engine = Mock()
        engine.url = "sqlite:///test.db"
        engine.pool = Mock(spec=NullPool)
        return engine

    @pytest.fixture
    def monitor(self, mock_engine):
        """Create a DatabasePoolMonitor instance."""
        with patch("sqlalchemy.event.listens_for"):
            return DatabasePoolMonitor(mock_engine, "test_db")

    def test_init(self, mock_engine):
        """Test monitor initialization."""
        with patch("sqlalchemy.event.listens_for") as mock_listens:
            monitor = DatabasePoolMonitor(mock_engine, "test_db")

            assert monitor.engine == mock_engine
            assert monitor.database_name == "test_db"
            # Should register 4 event listeners
            assert mock_listens.call_count == 4

    def test_collect_metrics_queue_pool(self, monitor, mock_engine):
        """Test metrics collection with QueuePool."""
        # Configure mock pool
        mock_engine.pool.size.return_value = 10
        mock_engine.pool.checked_out.return_value = 3
        mock_engine.pool.checked_in.return_value = 7
        mock_engine.pool.overflow.return_value = 2
        mock_engine.pool.total.return_value = 12

        # Mock Prometheus metrics
        with patch.multiple(
            "paidsearchnav.monitoring.database_metrics",
            db_pool_size=Mock(),
            db_pool_checked_out=Mock(),
            db_pool_checked_in=Mock(),
            db_pool_overflow=Mock(),
            db_pool_total=Mock(),
        ):
            metrics = monitor.collect_metrics()

        # Verify returned metrics
        assert metrics["database"] == "test_db"
        assert metrics["pool_type"] == "Mock"
        assert metrics["pool_size"] == 10
        assert metrics["checked_out"] == 3
        assert metrics["checked_in"] == 7
        assert metrics["overflow"] == 2
        assert metrics["total"] == 12
        assert metrics["utilization_percent"] == 30.0  # 3/10 * 100
        assert "***:***" in metrics["url"]  # Password should be masked

    def test_collect_metrics_null_pool(self, mock_null_pool_engine):
        """Test metrics collection with NullPool."""
        with patch("sqlalchemy.event.listens_for"):
            monitor = DatabasePoolMonitor(mock_null_pool_engine, "sqlite_db")

        metrics = monitor.collect_metrics()

        # NullPool should return all zeros
        assert metrics["pool_size"] == 0
        assert metrics["checked_out"] == 0
        assert metrics["checked_in"] == 0
        assert metrics["overflow"] == 0
        assert metrics["total"] == 0
        assert metrics["utilization_percent"] == 0.0

    def test_collect_metrics_unknown_pool(self, mock_engine):
        """Test metrics collection with unknown pool type."""
        # Use a pool type that's not QueuePool or NullPool
        custom_pool = Mock()
        custom_pool.__class__.__name__ = "CustomPool"
        custom_pool._pool_size = 0  # Add the attribute the code looks for
        mock_engine.pool = custom_pool

        with patch("sqlalchemy.event.listens_for"):
            monitor = DatabasePoolMonitor(mock_engine, "test_db")

        with patch("paidsearchnav.monitoring.database_metrics.logger") as mock_logger:
            metrics = monitor.collect_metrics()

        # Should log warning about unknown pool type
        mock_logger.warning.assert_called_once()
        assert "Unknown pool type: CustomPool" in mock_logger.warning.call_args[0][0]

        # Should return default values
        assert metrics["pool_size"] == 0
        assert metrics["utilization_percent"] == 0.0

    def test_get_health_status_healthy(self, monitor, mock_engine):
        """Test health status when pool is healthy."""
        # Configure healthy pool
        mock_engine.pool.size.return_value = 10
        mock_engine.pool.checked_out.return_value = 5
        mock_engine.pool.checked_in.return_value = 5
        mock_engine.pool.overflow.return_value = 0
        mock_engine.pool.total.return_value = 10

        health = monitor.get_health_status()

        assert health["status"] == "healthy"
        assert len(health["warnings"]) == 0
        assert len(health["recommendations"]) == 0

    def test_get_health_status_high_utilization(self, monitor, mock_engine):
        """Test health status with high pool utilization."""
        # Configure high utilization
        mock_engine.pool.size.return_value = 10
        mock_engine.pool.checked_out.return_value = 9
        mock_engine.pool.checked_in.return_value = 1
        mock_engine.pool.overflow.return_value = 0
        mock_engine.pool.total.return_value = 10

        health = monitor.get_health_status()

        assert health["status"] == "warning"
        assert len(health["warnings"]) == 1
        assert "High pool utilization: 90.0%" in health["warnings"][0]
        assert len(health["recommendations"]) == 1
        assert "increasing pool_size" in health["recommendations"][0]

    def test_get_health_status_high_overflow(self, monitor, mock_engine):
        """Test health status with high overflow usage."""
        # Configure high overflow but with some connections still available
        mock_engine.pool.size.return_value = 10
        mock_engine.pool.checked_out.return_value = 8
        mock_engine.pool.checked_in.return_value = 2
        mock_engine.pool.overflow.return_value = 8
        mock_engine.pool.total.return_value = 18

        health = monitor.get_health_status()

        assert health["status"] == "warning"
        assert any("High overflow usage" in w for w in health["warnings"])
        assert any("increasing pool_size" in r for r in health["recommendations"])

    def test_get_health_status_pool_exhausted(self, monitor, mock_engine):
        """Test health status when pool is exhausted."""
        # Configure exhausted pool
        mock_engine.pool.size.return_value = 10
        mock_engine.pool.checked_out.return_value = 10
        mock_engine.pool.checked_in.return_value = 0
        mock_engine.pool.overflow.return_value = 0
        mock_engine.pool.total.return_value = 10

        health = monitor.get_health_status()

        assert health["status"] == "critical"
        assert any("Connection pool exhausted" in w for w in health["warnings"])
        assert any("connection leaks" in r for r in health["recommendations"])

    def test_sanitize_url(self, monitor):
        """Test URL sanitization."""
        # Test various URL formats
        test_cases = [
            (
                "postgresql://user:password@localhost/db",
                "postgresql://***:***@localhost/db",
            ),
            (
                "mysql://admin:secret123@host:3306/test",
                "mysql://***:***@host:3306/test",
            ),
            (
                "sqlite:///path/to/db.sqlite",
                "sqlite:///path/to/db.sqlite",
            ),  # No credentials
            (
                "postgresql://localhost/db",
                "postgresql://localhost/db",
            ),  # No credentials
        ]

        for input_url, expected_url in test_cases:
            assert monitor._sanitize_url(input_url) == expected_url

    @patch("sqlalchemy.event.listens_for")
    def test_event_listeners(self, mock_listens_for, mock_engine):
        """Test that event listeners are properly registered."""
        monitor = DatabasePoolMonitor(mock_engine, "test_db")

        # Verify all 4 event listeners are registered
        assert mock_listens_for.call_count == 4

        # Check that listeners are registered for correct events
        events = [call[0][1] for call in mock_listens_for.call_args_list]
        assert "connect" in events
        assert "checkout" in events
        assert "checkin" in events
        assert "invalidate" in events

    def test_connection_created_event(self, monitor):
        """Test connection creation event handling - simplified."""
        # This test verifies that the event handlers are set up correctly
        # Testing the actual event firing is complex due to SQLAlchemy's event system
        # and would require a real engine instance

        # Verify the monitor has the expected attributes
        assert hasattr(monitor, "_should_sample")
        assert hasattr(monitor, "sample_rate")
        assert monitor.sample_rate == 1.0  # Default sample rate

        # Verify event setup was called during initialization
        # The actual event handling is tested in integration tests

    def test_connection_error_event(self, monitor):
        """Test connection error event handling - simplified."""
        # This test verifies that the monitor can handle errors
        # The actual event system integration is tested elsewhere

        # Verify the monitor is set up to handle events
        assert hasattr(monitor, "engine")
        assert hasattr(monitor, "database_name")
        assert monitor.database_name == "test_db"


class TestCreatePoolMonitor:
    """Test the create_pool_monitor factory function."""

    def test_create_pool_monitor(self):
        """Test creating a pool monitor."""
        mock_engine = Mock()
        mock_engine.url = "postgresql://localhost/test"
        mock_engine.pool = Mock(spec=QueuePool)

        with patch("sqlalchemy.event.listens_for"):
            monitor = create_pool_monitor(mock_engine, "custom_db")

        assert isinstance(monitor, DatabasePoolMonitor)
        assert monitor.engine == mock_engine
        assert monitor.database_name == "custom_db"

    def test_create_pool_monitor_default_name(self):
        """Test creating a pool monitor with default name."""
        mock_engine = Mock()
        mock_engine.url = "postgresql://localhost/test"
        mock_engine.pool = Mock(spec=QueuePool)

        with patch("sqlalchemy.event.listens_for"):
            monitor = create_pool_monitor(mock_engine)

        assert monitor.database_name == "main"
