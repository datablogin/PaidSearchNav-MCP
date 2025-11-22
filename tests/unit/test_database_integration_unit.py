"""Unit tests for database integration module."""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from paidsearchnav_mcp.integrations.database import (
    AnalysisStorageService,
    DatabaseConnection,
)


class TestDatabaseConnectionUnit:
    """Unit tests for DatabaseConnection class."""

    def test_init_default_values(self):
        """Test initialization with default values."""
        conn = DatabaseConnection()

        assert conn.pool_size == 10
        assert conn.max_overflow == 20
        assert conn.pool_timeout == 30.0
        assert conn.echo is False
        assert conn._retry_count == 3
        assert conn._retry_delay == 1.0

    def test_init_custom_values(self):
        """Test initialization with custom values."""
        conn = DatabaseConnection(
            database_url="postgresql+asyncpg://test",
            pool_size=5,
            max_overflow=10,
            pool_timeout=15.0,
            echo=True,
        )

        assert conn.database_url == "postgresql+asyncpg://test"
        assert conn.pool_size == 5
        assert conn.max_overflow == 10
        assert conn.pool_timeout == 15.0
        assert conn.echo is True

    @patch("paidsearchnav.integrations.database.get_settings")
    def test_get_database_url_from_config(self, mock_get_settings):
        """Test getting database URL from config."""
        mock_config = MagicMock()
        mock_secret = MagicMock()
        mock_secret.get_secret_value.return_value = "sqlite:///test.db"
        mock_config.database_url = mock_secret
        mock_get_settings.return_value = mock_config

        conn = DatabaseConnection()
        url = conn._get_database_url()

        assert url == "sqlite+aiosqlite:///test.db"

    def test_get_database_url_conversions(self):
        """Test various database URL conversions."""
        conn = DatabaseConnection()

        # Mock the database_url for each test
        # SQLite
        mock_secret = MagicMock()
        mock_secret.get_secret_value.return_value = "sqlite:///test.db"
        conn.config.database_url = mock_secret
        assert conn._get_database_url() == "sqlite+aiosqlite:///test.db"

        # PostgreSQL
        mock_secret.get_secret_value.return_value = "postgresql://user:pass@host/db"
        assert conn._get_database_url() == "postgresql+asyncpg://user:pass@host/db"

        # Postgres (old format)
        mock_secret.get_secret_value.return_value = "postgres://user:pass@host/db"
        assert conn._get_database_url() == "postgresql+asyncpg://user:pass@host/db"

        # Already async
        mock_secret.get_secret_value.return_value = (
            "postgresql+asyncpg://user:pass@host/db"
        )
        assert conn._get_database_url() == "postgresql+asyncpg://user:pass@host/db"

    @patch("paidsearchnav.integrations.database.create_async_engine")
    @patch("paidsearchnav.integrations.database.sessionmaker")
    @pytest.mark.asyncio
    async def test_initialize_success(self, mock_sessionmaker, mock_create_engine):
        """Test successful initialization."""
        # Set up mock engine with async context manager for begin()
        mock_engine = MagicMock()
        mock_begin = AsyncMock()
        mock_begin.__aenter__ = AsyncMock(return_value=mock_begin)
        mock_begin.__aexit__ = AsyncMock(return_value=None)
        mock_begin.run_sync = AsyncMock()  # For creating tables
        mock_engine.begin = MagicMock(return_value=mock_begin)

        mock_create_engine.return_value = mock_engine

        conn = DatabaseConnection(database_url="sqlite+aiosqlite:///test.db")
        await conn.initialize()

        # Engine should be created with correct parameters
        mock_create_engine.assert_called_once()
        call_args = mock_create_engine.call_args
        assert call_args[0][0] == "sqlite+aiosqlite:///test.db"
        assert call_args[1]["echo"] is False
        assert call_args[1]["pool_pre_ping"] is True

        # Session factory should be created
        mock_sessionmaker.assert_called_once_with(
            mock_engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

        # Tables should be created
        mock_engine.begin.assert_called_once()
        mock_begin.run_sync.assert_called_once()

    @patch("paidsearchnav.integrations.database.create_async_engine")
    @pytest.mark.asyncio
    async def test_initialize_failure(self, mock_create_engine):
        """Test initialization failure."""
        mock_create_engine.side_effect = Exception("Connection failed")

        conn = DatabaseConnection()
        with pytest.raises(Exception, match="Connection failed"):
            await conn.initialize()

    @patch("paidsearchnav.integrations.database.sa.text")
    @pytest.mark.asyncio
    async def test_execute_query_with_dict_params(self, mock_text):
        """Test query execution with dictionary parameters."""
        conn = DatabaseConnection()
        conn._engine = MagicMock()
        conn._session_factory = MagicMock()

        # Mock session
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_session.execute.return_value = mock_result

        # Mock context manager
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None
        conn._session_factory.return_value = mock_session

        # Execute query
        await conn.execute_query("SELECT * FROM test WHERE id = :id", {"id": 123})

        # Verify text was created and bindparams called
        mock_text.assert_called_with("SELECT * FROM test WHERE id = :id")
        mock_text.return_value.bindparams.assert_called_with(id=123)

    @pytest.mark.asyncio
    async def test_execute_query_not_initialized(self):
        """Test query execution when not initialized."""
        conn = DatabaseConnection()

        with pytest.raises(RuntimeError, match="Database connection not initialized"):
            await conn.execute_query("SELECT 1")

    @patch("paidsearchnav.integrations.database.asyncio.sleep")
    @pytest.mark.asyncio
    async def test_execute_query_retry_logic(self, mock_sleep):
        """Test query retry logic."""
        conn = DatabaseConnection()
        conn._engine = MagicMock()
        conn._session_factory = MagicMock()
        conn._retry_count = 3
        conn._retry_delay = 0.1

        # Mock session that fails twice then succeeds
        call_count = 0

        async def mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise OperationalError("Connection lost", None, None)
            result = MagicMock()
            result.fetchall.return_value = [{"value": 1}]
            return result

        mock_session = AsyncMock()
        mock_session.execute.side_effect = mock_execute
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None
        conn._session_factory.return_value = mock_session

        # Should succeed after retries
        result = await conn.execute_query("SELECT 1")
        assert len(result) == 1
        assert result[0]["value"] == 1
        assert call_count == 3

        # Verify sleep was called with increasing delays
        assert mock_sleep.call_count == 2
        mock_sleep.assert_any_call(0.1)
        mock_sleep.assert_any_call(0.2)

    @pytest.mark.asyncio
    async def test_get_session_context_manager(self):
        """Test get_session context manager."""
        conn = DatabaseConnection()
        conn._session_factory = MagicMock()

        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None
        conn._session_factory.return_value = mock_session

        # Test successful transaction
        async with conn.get_session() as session:
            assert session == mock_session

        mock_session.commit.assert_called_once()
        mock_session.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_session_rollback_on_error(self):
        """Test session rollback on error."""
        conn = DatabaseConnection()
        conn._session_factory = MagicMock()

        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session
        mock_session.__aexit__.return_value = None
        conn._session_factory.return_value = mock_session

        # Test rollback on error
        with pytest.raises(ValueError):
            async with conn.get_session() as session:
                raise ValueError("Test error")

        mock_session.rollback.assert_called_once()
        mock_session.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_close(self):
        """Test closing connection."""
        conn = DatabaseConnection()
        mock_engine = AsyncMock()
        conn._engine = mock_engine
        conn._session_factory = MagicMock()

        await conn.close()

        mock_engine.dispose.assert_called_once()
        assert conn._engine is None
        assert conn._session_factory is None


class TestAnalysisStorageServiceUnit:
    """Unit tests for AnalysisStorageService class."""

    def test_init_default(self):
        """Test initialization with defaults."""
        service = AnalysisStorageService()

        assert service.connection is not None
        assert isinstance(service.connection, DatabaseConnection)
        assert service._repository is None
        assert service._cache == {}
        assert service._cache_ttl == 300

    def test_init_with_connection(self):
        """Test initialization with provided connection."""
        conn = DatabaseConnection()
        service = AnalysisStorageService(connection=conn)

        assert service.connection == conn

    @patch("paidsearchnav.integrations.database.AnalysisRepository")
    @pytest.mark.asyncio
    async def test_initialize(self, mock_repository_class):
        """Test service initialization."""
        service = AnalysisStorageService()
        service.connection._engine = MagicMock()  # Simulate initialized connection

        await service.initialize()

        # Repository should be created
        mock_repository_class.assert_called_once_with(
            settings=service.connection.config
        )
        assert service._repository == mock_repository_class.return_value

    @pytest.mark.asyncio
    async def test_initialize_connection_not_ready(self):
        """Test initialization when connection not ready."""
        service = AnalysisStorageService()
        service.connection.initialize = AsyncMock()

        await service.initialize()

        # Should initialize connection first
        service.connection.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_store_analysis(self):
        """Test storing analysis."""
        service = AnalysisStorageService()
        mock_repo = AsyncMock()
        mock_repo.save_analysis.return_value = "analysis-123"
        service._repository = mock_repo

        # Store analysis
        analysis_id = await service.store_analysis(
            customer_id="12345678",
            analysis_type="cost_efficiency",
            data={"total_cost": 1000.0},
        )

        assert analysis_id == "analysis-123"
        # Verify that save_analysis was called with an AnalysisResult object
        mock_repo.save_analysis.assert_called_once()

        # Get the actual argument passed
        called_args = mock_repo.save_analysis.call_args[0]
        analysis_result = called_args[0]

        # Verify the AnalysisResult object has the expected properties
        assert analysis_result.customer_id == "12345678"
        assert analysis_result.analysis_type == "cost_efficiency"
        assert analysis_result.raw_data == {"total_cost": 1000.0}

        # Cache should be cleared for this customer
        service._cache["12345678:cost_efficiency"] = (time.time(), {"old": "data"})
        await service.store_analysis(
            customer_id="12345678",
            analysis_type="cost_efficiency",
            data={"total_cost": 2000.0},
        )
        assert "12345678:cost_efficiency" not in service._cache

    @pytest.mark.asyncio
    async def test_store_analysis_not_initialized(self):
        """Test storing analysis when not initialized."""
        service = AnalysisStorageService()

        with pytest.raises(RuntimeError, match="Storage service not initialized"):
            await service.store_analysis("123", "test", {})

    @pytest.mark.asyncio
    async def test_store_analyses_batch(self):
        """Test batch storage."""
        service = AnalysisStorageService()
        mock_repo = AsyncMock()
        mock_repo.save_analysis.side_effect = ["analysis-1", "analysis-2"]
        service._repository = mock_repo

        # Store batch
        analyses = [
            {
                "customer_id": "12345678",  # Valid Google Ads customer ID (7-10 digits)
                "analysis_type": "test1",
                "data": {"value": 1},
            },
            {
                "customer_id": "87654321",
                "analysis_type": "test2",
                "data": {"value": 2},
            },
        ]

        ids = await service.store_analyses_batch(analyses)

        assert len(ids) == 2
        assert ids[0] == "analysis-1"
        assert ids[1] == "analysis-2"

        # Verify save_analysis was called twice with AnalysisResult objects
        assert mock_repo.save_analysis.call_count == 2

        # Check first call
        first_call_arg = mock_repo.save_analysis.call_args_list[0][0][0]
        assert first_call_arg.customer_id == "12345678"
        assert first_call_arg.analysis_type == "test1"
        assert first_call_arg.raw_data == {"value": 1}

        # Check second call
        second_call_arg = mock_repo.save_analysis.call_args_list[1][0][0]
        assert second_call_arg.customer_id == "87654321"
        assert second_call_arg.analysis_type == "test2"
        assert second_call_arg.raw_data == {"value": 2}

    @pytest.mark.asyncio
    async def test_get_analysis_from_cache(self):
        """Test getting analysis from cache."""
        service = AnalysisStorageService()
        service._repository = AsyncMock()

        # Add to cache with timestamp
        cached_data = {"id": "123", "data": {"cached": True}}
        service._cache["12345678:cost_efficiency"] = (time.time(), cached_data)

        # Get from cache
        result = await service.get_analysis("12345678", "cost_efficiency")

        assert result == cached_data
        # Repository should not be called
        service._repository.list_analyses.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_analysis_from_repository(self):
        """Test getting analysis from repository."""
        from datetime import datetime

        from paidsearchnav.core.models.analysis import AnalysisMetrics, AnalysisResult

        service = AnalysisStorageService()
        mock_repo = AsyncMock()

        # Create a mock AnalysisResult object
        mock_analysis = AnalysisResult(
            analysis_id="123",
            customer_id="12345678",
            analysis_type="cost_efficiency",
            analyzer_name="test_analyzer",
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow(),
            status="completed",
            metrics=AnalysisMetrics(),
            recommendations=[],
            raw_data={"from_repo": True},
        )

        mock_repo.list_analyses.return_value = [mock_analysis]
        service._repository = mock_repo

        # Get from repository
        result = await service.get_analysis("12345678", "cost_efficiency")

        assert result is not None
        assert result["analysis_id"] == "123"
        assert result["customer_id"] == "12345678"
        assert result["result_data"]["from_repo"] is True

        mock_repo.list_analyses.assert_called_once_with(
            customer_id="12345678",
            analysis_type="cost_efficiency",
            limit=1,
        )

        # Should be cached now with timestamp
        assert "12345678:cost_efficiency" in service._cache
        timestamp, cached_value = service._cache["12345678:cost_efficiency"]
        assert cached_value == result

    @pytest.mark.asyncio
    async def test_get_analysis_not_found(self):
        """Test getting non-existent analysis."""
        service = AnalysisStorageService()
        mock_repo = AsyncMock()
        mock_repo.list_analyses.return_value = []
        service._repository = mock_repo

        result = await service.get_analysis("12345678", "nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_list_analyses(self):
        """Test listing analyses."""
        from datetime import datetime

        from paidsearchnav.core.models.analysis import AnalysisMetrics, AnalysisResult

        service = AnalysisStorageService()
        mock_repo = AsyncMock()

        # Create mock AnalysisResult objects
        mock_analyses = [
            AnalysisResult(
                analysis_id="1",
                customer_id="12345678",
                analysis_type="cost_efficiency",
                analyzer_name="test_analyzer",
                start_date=datetime.utcnow(),
                end_date=datetime.utcnow(),
                status="completed",
                metrics=AnalysisMetrics(),
                recommendations=[],
                raw_data={"id": "1"},
            ),
            AnalysisResult(
                analysis_id="2",
                customer_id="12345678",
                analysis_type="cost_efficiency",
                analyzer_name="test_analyzer",
                start_date=datetime.utcnow(),
                end_date=datetime.utcnow(),
                status="completed",
                metrics=AnalysisMetrics(),
                recommendations=[],
                raw_data={"id": "2"},
            ),
        ]

        mock_repo.list_analyses.return_value = mock_analyses
        service._repository = mock_repo

        result = await service.list_analyses(
            customer_id="12345678", limit=5, analysis_type="cost_efficiency"
        )

        assert len(result) == 2
        assert result[0]["analysis_id"] == "1"
        assert result[1]["analysis_id"] == "2"

        mock_repo.list_analyses.assert_called_once_with(
            customer_id="12345678",
            analysis_type="cost_efficiency",
            limit=5,
        )

    @pytest.mark.asyncio
    async def test_delete_analysis(self):
        """Test deleting analysis."""
        from datetime import datetime

        from paidsearchnav.core.models.analysis import AnalysisMetrics, AnalysisResult

        service = AnalysisStorageService()
        mock_repo = AsyncMock()

        # Mock get_analysis to return an analysis so we know which cache key to clear
        mock_analysis = AnalysisResult(
            analysis_id="analysis-123",
            customer_id="12345678",
            analysis_type="test",
            analyzer_name="test_analyzer",
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow(),
            status="completed",
            metrics=AnalysisMetrics(),
            recommendations=[],
            raw_data={"test": "data"},
        )
        mock_repo.get_analysis.return_value = mock_analysis
        mock_repo.delete_analysis.return_value = True
        service._repository = mock_repo

        # Add the specific cache entry that should be cleared
        service._cache["12345678:test"] = (time.time(), {"data": "cached"})

        result = await service.delete_analysis("analysis-123")

        assert result is True
        mock_repo.delete_analysis.assert_called_once_with("analysis-123")
        # Specific cache entry should be cleared
        assert "12345678:test" not in service._cache

    @pytest.mark.asyncio
    async def test_compare_analyses(self):
        """Test comparing analyses."""
        from datetime import datetime

        from paidsearchnav.core.models.analysis import AnalysisMetrics, AnalysisResult

        service = AnalysisStorageService()
        mock_repo = AsyncMock()

        # Mock the base comparison
        comparison_data = {"changes": {"recommendations_added": 2}}
        mock_repo.compare_analyses.return_value = comparison_data

        # Mock get_analysis for both analyses
        analysis_1 = AnalysisResult(
            analysis_id="id1",
            customer_id="12345678",
            analysis_type="cost_efficiency",
            analyzer_name="test",
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow(),
            status="completed",
            metrics=AnalysisMetrics(),
            recommendations=[],
            raw_data={"cost": 100, "conversions": 10},
        )

        analysis_2 = AnalysisResult(
            analysis_id="id2",
            customer_id="12345678",
            analysis_type="cost_efficiency",
            analyzer_name="test",
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow(),
            status="completed",
            metrics=AnalysisMetrics(),
            recommendations=[],
            raw_data={"cost": 150, "conversions": 15},
        )

        mock_repo.get_analysis.side_effect = [analysis_1, analysis_2]
        service._repository = mock_repo

        result = await service.compare_analyses(
            customer_id="12345678", analysis_id_1="id1", analysis_id_2="id2"
        )

        assert result is not None
        assert "changes" in result
        assert result["changes"]["cost"]["old"] == 100
        assert result["changes"]["cost"]["new"] == 150
        assert result["changes"]["conversions"]["old"] == 10
        assert result["changes"]["conversions"]["new"] == 15

        mock_repo.compare_analyses.assert_called_once_with(
            analysis_id_1="id1", analysis_id_2="id2"
        )

    @pytest.mark.asyncio
    async def test_get_performance_metrics(self):
        """Test getting performance metrics."""
        service = AnalysisStorageService()
        service.connection._engine = MagicMock()

        # Mock pool with metrics
        mock_pool = MagicMock()
        mock_pool.size.return_value = 10
        mock_pool.checked_in_connections.return_value = 8
        mock_pool.checked_out_connections.return_value = 2
        service.connection._engine.pool = mock_pool

        # Add cache entries (with timestamp tuples)
        service._cache["key1"] = (time.time(), "value1")
        service._cache["key2"] = (time.time(), "value2")

        metrics = await service.get_performance_metrics()

        assert metrics["cache_size"] == 2
        assert metrics["cache_ttl"] == 300
        assert metrics["pool_size"] == 10
        assert metrics["pool_available"] == 8
        assert metrics["pool_in_use"] == 2

    @pytest.mark.asyncio
    async def test_close(self):
        """Test closing service."""
        service = AnalysisStorageService()
        service.connection.close = AsyncMock()
        service._cache["key"] = "value"

        await service.close()

        # Cache should be cleared
        assert len(service._cache) == 0
        # Connection should be closed
        service.connection.close.assert_called_once()
