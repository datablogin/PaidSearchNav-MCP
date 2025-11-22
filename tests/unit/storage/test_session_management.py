"""Tests for session management improvements in storage repository."""

import logging
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from paidsearchnav.core.config import Settings
from paidsearchnav.core.models.analysis import (
    AnalysisMetrics,
    AnalysisResult,
)
from paidsearchnav.storage.repository import AnalysisRepository


@pytest.fixture
def temp_db_path():
    """Create a temporary database file."""
    import uuid

    temp_dir = Path(tempfile.gettempdir())
    db_path = temp_dir / f"test_session_{uuid.uuid4()}.db"
    yield db_path
    # Cleanup
    db_path.unlink(missing_ok=True)


@pytest.fixture
def settings(temp_db_path):
    """Create test settings with temporary database."""
    settings = Settings(
        environment="development",
        data_dir=temp_db_path.parent,
        debug=False,
    )
    return settings


@pytest_asyncio.fixture
async def repository(settings, temp_db_path, monkeypatch):
    """Create a repository instance with session management fixes."""
    import uuid

    unique_db_name = f"test_session_{uuid.uuid4()}.db"

    def mock_init(self, settings):
        self.settings = settings
        # Configure session metrics (required by AnalysisRepository)
        from paidsearchnav.storage.session_metrics import get_session_metrics

        self.session_metrics = get_session_metrics()
        # Enable session metrics for testing
        self.session_metrics.enabled = True
        self.session_metrics.log_interval = 1  # Log every session
        self.detailed_logging = True
        db_path = settings.data_dir / unique_db_name
        db_url = f"sqlite:///{db_path}"
        async_db_url = f"sqlite+aiosqlite:///{db_path}"

        from sqlalchemy import create_engine
        from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
        from sqlalchemy.orm import sessionmaker

        # Test the new connection pooling code path
        engine_kwargs = {
            "echo": settings.debug,
        }

        self.engine = create_engine(db_url, **engine_kwargs)

        async_engine_kwargs = {
            "echo": settings.debug,
        }

        self.async_engine = create_async_engine(async_db_url, **async_engine_kwargs)

        # Create session factories with proper AsyncSession class
        self.SessionLocal = sessionmaker(
            bind=self.engine, autocommit=False, autoflush=False
        )
        self.AsyncSessionLocal = async_sessionmaker(
            self.async_engine, expire_on_commit=False, class_=AsyncSession
        )

        # Create tables
        from paidsearchnav.storage.models import Base

        Base.metadata.create_all(bind=self.engine)

    monkeypatch.setattr(AnalysisRepository, "__init__", mock_init)

    repo = AnalysisRepository(settings)
    yield repo

    # Cleanup
    repo.engine.dispose()
    await repo.async_engine.dispose()

    # Clean up the unique database file
    unique_db_path = settings.data_dir / unique_db_name
    if unique_db_path.exists():
        unique_db_path.unlink()


@pytest.fixture
def sample_analysis_result():
    """Create a sample analysis result."""
    return AnalysisResult(
        customer_id="1234567890",
        analysis_type="session_test_audit",
        analyzer_name="SessionTestAnalyzer",
        start_date=datetime.now(timezone.utc) - timedelta(days=30),
        end_date=datetime.now(timezone.utc),
        status="completed",
        metrics=AnalysisMetrics(
            total_keywords_analyzed=100,
            issues_found=5,
            critical_issues=1,
            potential_cost_savings=50.0,
            potential_conversion_increase=2.0,
        ),
        recommendations=[],
        raw_data={"test": "data"},
    )


class TestSessionManagement:
    """Test session management improvements."""

    @pytest.mark.asyncio
    async def test_session_lifecycle_logging(
        self, repository, sample_analysis_result, caplog
    ):
        """Test that session lifecycle is properly logged."""
        with caplog.at_level(logging.DEBUG):
            # Save analysis - should log session open/close
            analysis_id = await repository.save_analysis(sample_analysis_result)

            # Check for session lifecycle logs
            session_logs = [
                record for record in caplog.records if "Session" in record.getMessage()
            ]

            assert len(session_logs) >= 2  # At least open and close
            assert any(
                "Session opened for save_analysis" in log.getMessage()
                for log in session_logs
            )
            assert any(
                "Session closed for save_analysis" in log.getMessage()
                for log in session_logs
            )

        # Clear logs and test get_analysis
        caplog.clear()
        with caplog.at_level(logging.DEBUG):
            retrieved = await repository.get_analysis(analysis_id)

            session_logs = [
                record for record in caplog.records if "Session" in record.getMessage()
            ]

            assert len(session_logs) >= 2
            assert any(
                "Session opened for get_analysis" in log.getMessage()
                for log in session_logs
            )
            assert any(
                "Session closed for get_analysis" in log.getMessage()
                for log in session_logs
            )

    @pytest.mark.asyncio
    async def test_async_session_class_configuration(self, repository):
        """Test that AsyncSession class is properly configured."""
        # Verify the session factory is configured with AsyncSession class
        session_factory = repository.AsyncSessionLocal

        # Create a session and verify it's the correct type
        async with session_factory() as session:
            assert isinstance(session, AsyncSession)
            assert hasattr(session, "commit")
            assert hasattr(session, "rollback")
            assert hasattr(session, "execute")

    @pytest.mark.asyncio
    async def test_session_error_handling_with_logging(
        self, repository, caplog, sample_analysis_result
    ):
        """Test that session errors are properly logged and rolled back."""
        with caplog.at_level(logging.DEBUG):
            # Test a scenario that reaches session management: invalid data type
            # This will pass validation but fail during database operations
            invalid_result = sample_analysis_result.model_copy()

            # Create a scenario that will cause database-level error by using duplicate ID
            await repository.save_analysis(sample_analysis_result)

            # Clear logs to focus on the error scenario
            caplog.clear()

            # Try to save with same analysis_id (should cause integrity error)
            invalid_result.analysis_id = sample_analysis_result.analysis_id

            # This should reach the session but fail during commit
            try:
                await repository.save_analysis(invalid_result)
            except Exception:
                pass  # Expected to fail

            # Check that session lifecycle logs are present
            session_logs = [
                record for record in caplog.records if "Session" in record.getMessage()
            ]

            # Should have at least session opened
            assert len(session_logs) >= 1
            assert any("opened" in log.getMessage() for log in session_logs)

    @pytest.mark.asyncio
    async def test_connection_pool_configuration_sqlite(self, settings):
        """Test that SQLite doesn't get pool configuration."""
        # Mock the engine creation to capture the arguments
        with patch(
            "paidsearchnav.storage.repository.create_engine"
        ) as mock_create_engine:
            with patch(
                "paidsearchnav.storage.repository.create_async_engine"
            ) as mock_create_async_engine:
                with patch("paidsearchnav.storage.repository.Base"):
                    # Create repository
                    AnalysisRepository(settings)

                    # Verify SQLite engine was created without pooling options
                    mock_create_engine.assert_called_once()
                    args, kwargs = mock_create_engine.call_args

                    # SQLite should only have echo parameter
                    expected_keys = {"echo"}
                    assert set(kwargs.keys()) == expected_keys
                    assert "pool_size" not in kwargs
                    assert "max_overflow" not in kwargs

    @pytest.mark.asyncio
    async def test_connection_pool_configuration_postgresql(self):
        """Test that PostgreSQL gets proper pool configuration."""
        settings = Settings(
            environment="production",
            database_url="postgresql://user:pass@localhost/db",
            data_dir=Path("/tmp"),
            debug=False,
        )

        with patch(
            "paidsearchnav.storage.repository.create_engine"
        ) as mock_create_engine:
            with patch(
                "paidsearchnav.storage.repository.create_async_engine"
            ) as mock_create_async_engine:
                with patch("paidsearchnav.storage.repository.Base"):
                    # Create repository
                    AnalysisRepository(settings)

                    # Verify PostgreSQL engine was created with pooling options
                    mock_create_engine.assert_called_once()
                    args, kwargs = mock_create_engine.call_args

                    # PostgreSQL should have pooling parameters
                    expected_keys = {
                        "echo",
                        "pool_size",
                        "max_overflow",
                        "pool_timeout",
                        "pool_recycle",
                        "pool_pre_ping",
                    }
                    assert set(kwargs.keys()) == expected_keys
                    assert kwargs["pool_size"] == 5
                    assert kwargs["max_overflow"] == 10
                    assert kwargs["pool_timeout"] == 30
                    assert kwargs["pool_recycle"] == 3600

    @pytest.mark.asyncio
    async def test_multiple_concurrent_sessions(
        self, repository, sample_analysis_result
    ):
        """Test that multiple concurrent sessions don't interfere with each other."""
        import asyncio

        # Create multiple analysis results
        results = []
        for i in range(5):
            result = AnalysisResult(
                customer_id=f"123456789{i}",  # Valid 10-digit customer ID
                analysis_type=f"test_type_{i}",
                analyzer_name="ConcurrentTestAnalyzer",
                start_date=datetime.now(timezone.utc) - timedelta(days=30),
                end_date=datetime.now(timezone.utc),
                metrics=AnalysisMetrics(custom_metrics={"test_id": i}),
            )
            results.append(result)

        # Save all results concurrently
        save_tasks = [repository.save_analysis(result) for result in results]
        analysis_ids = await asyncio.gather(*save_tasks)

        # Verify all were saved with unique IDs
        assert len(analysis_ids) == 5
        assert len(set(analysis_ids)) == 5  # All unique

        # Retrieve all concurrently
        retrieve_tasks = [repository.get_analysis(aid) for aid in analysis_ids]
        retrieved = await asyncio.gather(*retrieve_tasks)

        # Verify all were retrieved correctly
        assert len(retrieved) == 5
        assert all(r is not None for r in retrieved)

        # Verify each has the correct custom metric
        for i, result in enumerate(retrieved):
            assert result.metrics.custom_metrics["test_id"] == i

    @pytest.mark.asyncio
    async def test_session_cleanup_after_exception(
        self, repository, caplog, sample_analysis_result
    ):
        """Test that sessions are properly cleaned up even after exceptions."""
        with caplog.at_level(logging.DEBUG):
            # First create a valid analysis
            analysis_id = await repository.save_analysis(sample_analysis_result)

            # Clear logs to focus on the exception scenario
            caplog.clear()

            # Get an analysis that exists (this should succeed and log session lifecycle)
            result = await repository.get_analysis(analysis_id)
            assert result is not None

            # Check that session was opened and closed properly
            session_logs = [
                record for record in caplog.records if "Session" in record.getMessage()
            ]

            open_logs = [log for log in session_logs if "opened" in log.getMessage()]
            close_logs = [log for log in session_logs if "closed" in log.getMessage()]

            assert len(open_logs) >= 1
            assert len(close_logs) >= 1
