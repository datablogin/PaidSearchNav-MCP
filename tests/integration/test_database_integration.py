"""Tests for database integration module."""

import asyncio
import os
import random
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
import sqlalchemy as sa
from sqlalchemy.exc import OperationalError

from paidsearchnav.integrations.database import (
    AnalysisStorageService,
    DatabaseConnection,
)


def get_unique_customer_id():
    """Generate a unique customer ID for test isolation."""
    return f"{random.randint(10000000, 99999999)}"


class TestDatabaseConnection:
    """Test cases for DatabaseConnection class."""

    @pytest_asyncio.fixture
    async def temp_db(self):
        """Create a temporary SQLite database."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        yield f"sqlite+aiosqlite:///{db_path}"

        # Cleanup
        try:
            os.unlink(db_path)
        except Exception:
            pass

    @pytest_asyncio.fixture
    async def db_connection(self, temp_db):
        """Create a database connection instance."""
        conn = DatabaseConnection(database_url=temp_db)
        await conn.initialize()
        yield conn
        await conn.close()

    def test_database_url_conversion(self):
        """Test database URL conversion for async drivers."""
        conn = DatabaseConnection()

        # Mock the database_url for each test
        from unittest.mock import MagicMock

        # Test SQLite conversion
        mock_secret = MagicMock()
        mock_secret.get_secret_value.return_value = "sqlite:///test.db"
        conn.config.database_url = mock_secret
        assert conn._get_database_url() == "sqlite+aiosqlite:///test.db"

        # Test PostgreSQL conversion
        mock_secret.get_secret_value.return_value = "postgresql://user:pass@host/db"
        assert conn._get_database_url() == "postgresql+asyncpg://user:pass@host/db"

        # Test postgres:// conversion
        mock_secret.get_secret_value.return_value = "postgres://user:pass@host/db"
        assert conn._get_database_url() == "postgresql+asyncpg://user:pass@host/db"

    @pytest.mark.asyncio
    async def test_initialize(self, temp_db):
        """Test database initialization."""
        conn = DatabaseConnection(database_url=temp_db)

        # Should not be initialized yet
        assert conn._engine is None
        assert conn._session_factory is None

        # Initialize
        await conn.initialize()

        # Should be initialized
        assert conn._engine is not None
        assert conn._session_factory is not None

        # Tables should be created
        async with conn.get_session() as session:
            # Check if analysis_results table exists
            result = await session.execute(
                sa.text(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='analysis_results'"
                )
            )
            assert result.scalar() == "analysis_results"

        await conn.close()

    @pytest.mark.asyncio
    async def test_execute_query(self, db_connection):
        """Test query execution."""
        # Test simple query
        result = await db_connection.execute_query("SELECT 1 as value")
        assert len(result) == 1
        assert result[0]["value"] == 1

        # Test query with positional parameters
        result = await db_connection.execute_query(
            "SELECT ? as value1, ? as value2", ("test1", "test2")
        )
        assert len(result) == 1
        assert result[0]["value1"] == "test1"
        assert result[0]["value2"] == "test2"

        # Test query with named parameters
        result = await db_connection.execute_query(
            "SELECT :val1 as value1, :val2 as value2",
            {"val1": "test1", "val2": "test2"},
        )
        assert len(result) == 1
        assert result[0]["value1"] == "test1"
        assert result[0]["value2"] == "test2"

    @pytest.mark.asyncio
    async def test_execute_query_retry(self, temp_db):
        """Test query execution with retry logic."""
        conn = DatabaseConnection(database_url=temp_db)
        await conn.initialize()

        # Mock execute to fail twice then succeed
        call_count = 0

        async def mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise OperationalError("Connection failed", None, None)
            # Return a mock result that behaves like SQLAlchemy result
            mock_result = MagicMock()
            mock_result.fetchall.return_value = [{"value": 1}]
            return mock_result

        with patch.object(conn, "_retry_delay", 0.01):  # Speed up test
            with patch.object(conn, "get_session") as mock_get_session:
                mock_session = AsyncMock()
                mock_session.__aenter__.return_value = mock_session
                mock_session.__aexit__.return_value = None
                mock_session.execute.side_effect = mock_execute
                mock_get_session.return_value = mock_session

                # Should succeed after retries
                result = await conn.execute_query("SELECT 1")
                assert call_count == 3
                assert len(result) == 1
                assert result[0]["value"] == 1

        await conn.close()

    @pytest.mark.asyncio
    async def test_get_session(self, db_connection):
        """Test session management."""
        # Test successful transaction
        async with db_connection.get_session() as session:
            assert session is not None
            # Session should be active
            assert session.is_active

        # Test transaction rollback on error
        with pytest.raises(ValueError):
            async with db_connection.get_session() as session:
                # This should cause rollback
                raise ValueError("Test error")

    @pytest.mark.asyncio
    async def test_close(self, db_connection):
        """Test connection closing."""
        # Connection should be active
        assert db_connection._engine is not None

        # Close connection
        await db_connection.close()

        # Connection should be closed
        assert db_connection._engine is None
        assert db_connection._session_factory is None

    @pytest.mark.asyncio
    async def test_connection_not_initialized_error(self):
        """Test error when using connection before initialization."""
        conn = DatabaseConnection()

        # Should raise error when not initialized
        with pytest.raises(RuntimeError, match="Database connection not initialized"):
            await conn.execute_query("SELECT 1")

        with pytest.raises(RuntimeError, match="Database connection not initialized"):
            async with conn.get_session():
                pass


class TestAnalysisStorageService:
    """Test cases for AnalysisStorageService class."""

    @pytest_asyncio.fixture
    async def temp_db(self):
        """Create a temporary SQLite database."""
        import uuid

        # Use unique filename for each test
        db_path = f"/tmp/test_storage_{uuid.uuid4().hex}.db"

        yield f"sqlite+aiosqlite:///{db_path}"

        # Cleanup
        try:
            os.unlink(db_path)
        except Exception:
            pass

    @pytest_asyncio.fixture
    async def storage_service(self, temp_db):
        """Create a storage service instance."""
        conn = DatabaseConnection(database_url=temp_db)
        service = AnalysisStorageService(connection=conn)
        await service.initialize()
        yield service
        await service.close()

    @pytest.mark.asyncio
    async def test_initialize(self, temp_db):
        """Test storage service initialization."""
        conn = DatabaseConnection(database_url=temp_db)
        service = AnalysisStorageService(connection=conn)

        # Should not be initialized yet
        assert service._repository is None

        # Initialize
        await service.initialize()

        # Should be initialized
        assert service._repository is not None

        await service.close()

    @pytest.mark.asyncio
    async def test_store_analysis(self, storage_service):
        """Test storing analysis results."""
        customer_id = get_unique_customer_id()

        # Store analysis
        analysis_id = await storage_service.store_analysis(
            customer_id=customer_id,
            analysis_type="cost_efficiency",
            data={
                "total_cost": 1000.0,
                "total_conversions": 50,
                "conversion_rate": 0.05,
                "average_cpc": 2.0,
                "insights": ["High CPC detected"],
            },
        )

        assert analysis_id is not None
        assert isinstance(analysis_id, str)

        # Verify it was stored
        analysis = await storage_service.get_analysis(customer_id, "cost_efficiency")
        assert analysis is not None
        assert analysis["customer_id"] == customer_id
        assert analysis["analysis_type"] == "cost_efficiency"
        assert analysis["result_data"]["total_cost"] == 1000.0

    @pytest.mark.asyncio
    async def test_store_analyses_batch(self, storage_service):
        """Test batch storage of analyses."""
        customer_id_1 = get_unique_customer_id()
        customer_id_2 = get_unique_customer_id()

        analyses = [
            {
                "customer_id": customer_id_1,
                "analysis_type": "cost_efficiency",
                "data": {
                    "total_cost": 1000.0,
                    "total_conversions": 50,
                    "conversion_rate": 0.05,
                    "average_cpc": 2.0,
                },
            },
            {
                "customer_id": customer_id_1,
                "analysis_type": "keyword_quality",
                "data": {
                    "quality_score": 7.5,
                    "low_quality_keywords": 10,
                },
            },
            {
                "customer_id": customer_id_2,
                "analysis_type": "cost_efficiency",
                "data": {
                    "total_cost": 500.0,
                    "total_conversions": 30,
                    "conversion_rate": 0.06,
                    "average_cpc": 1.5,
                },
            },
        ]

        # Store batch
        analysis_ids = await storage_service.store_analyses_batch(analyses)

        assert len(analysis_ids) == 3
        assert all(isinstance(aid, str) for aid in analysis_ids)

        # Verify all were stored
        results = await storage_service.list_analyses(customer_id_1, limit=10)
        assert len(results) >= 2

    @pytest.mark.asyncio
    async def test_get_analysis_with_cache(self, storage_service):
        """Test retrieving analysis with caching."""
        customer_id = get_unique_customer_id()

        # Store analysis
        analysis_id = await storage_service.store_analysis(
            customer_id=customer_id,
            analysis_type="cost_efficiency",
            data={"total_cost": 1000.0},
        )

        # First retrieval (not cached)
        assert len(storage_service._cache) == 0
        analysis1 = await storage_service.get_analysis(customer_id, "cost_efficiency")
        assert analysis1 is not None
        assert len(storage_service._cache) == 1

        # Second retrieval (should be cached)
        analysis2 = await storage_service.get_analysis(customer_id, "cost_efficiency")
        assert analysis2 == analysis1
        assert len(storage_service._cache) == 1

        # Retrieval without cache
        analysis3 = await storage_service.get_analysis(
            customer_id, "cost_efficiency", use_cache=False
        )
        assert analysis3 is not None
        # Cache should not have changed
        assert len(storage_service._cache) == 1

    @pytest.mark.asyncio
    async def test_get_analysis_not_found(self, storage_service):
        """Test retrieving non-existent analysis."""
        analysis = await storage_service.get_analysis("99999999", "nonexistent")
        assert analysis is None

    @pytest.mark.asyncio
    async def test_list_analyses(self, storage_service):
        """Test listing analyses."""
        # Use unique customer_id to avoid conflicts with other tests
        customer_id = get_unique_customer_id()

        # Store multiple analyses
        for i in range(5):
            await storage_service.store_analysis(
                customer_id=customer_id, analysis_type=f"type_{i}", data={"index": i}
            )

        # List all
        results = await storage_service.list_analyses(customer_id, limit=10)
        assert len(results) == 5

        # List with limit
        results = await storage_service.list_analyses(customer_id, limit=2)
        assert len(results) == 2

        # List with type filter
        results = await storage_service.list_analyses(
            customer_id, analysis_type="type_1", limit=10
        )
        assert len(results) == 1
        assert results[0]["analysis_type"] == "type_1"

    @pytest.mark.asyncio
    async def test_delete_analysis(self, storage_service):
        """Test deleting analysis."""
        # Use unique customer_id to avoid conflicts
        customer_id = get_unique_customer_id()

        # Store analysis
        analysis_id = await storage_service.store_analysis(
            customer_id=customer_id,
            analysis_type="cost_efficiency",
            data={"total_cost": 1000.0},
        )

        # Cache it
        await storage_service.get_analysis(customer_id, "cost_efficiency")
        assert len(storage_service._cache) == 1

        # Delete it
        deleted = await storage_service.delete_analysis(analysis_id)
        assert deleted is True
        assert len(storage_service._cache) == 0  # Cache should be cleared

        # Verify it's gone
        analysis = await storage_service.get_analysis(customer_id, "cost_efficiency")
        assert analysis is None

        # Delete non-existent
        deleted = await storage_service.delete_analysis("nonexistent")
        assert deleted is False

    @pytest.mark.asyncio
    async def test_compare_analyses(self, storage_service):
        """Test comparing analyses."""
        customer_id = get_unique_customer_id()

        # Store two analyses
        id1 = await storage_service.store_analysis(
            customer_id=customer_id,
            analysis_type="cost_efficiency",
            data={
                "total_cost": 1000.0,
                "total_conversions": 50,
            },
        )

        id2 = await storage_service.store_analysis(
            customer_id=customer_id,
            analysis_type="cost_efficiency",
            data={
                "total_cost": 1200.0,
                "total_conversions": 55,
            },
        )

        # Compare them
        comparison = await storage_service.compare_analyses(
            customer_id=customer_id, analysis_id_1=id1, analysis_id_2=id2
        )

        assert comparison is not None
        assert "changes" in comparison
        assert comparison["changes"]["total_cost"]["old"] == 1000.0
        assert comparison["changes"]["total_cost"]["new"] == 1200.0

    @pytest.mark.asyncio
    async def test_get_performance_metrics(self, storage_service):
        """Test getting performance metrics."""
        customer_id = get_unique_customer_id()

        # Add some cache entries
        await storage_service.store_analysis(
            customer_id=customer_id,
            analysis_type="cost_efficiency",
            data={"total_cost": 1000.0},
        )
        await storage_service.get_analysis(customer_id, "cost_efficiency")

        # Get metrics
        metrics = await storage_service.get_performance_metrics()

        assert "cache_size" in metrics
        assert metrics["cache_size"] == 1
        assert "cache_ttl" in metrics
        assert metrics["cache_ttl"] == 300

        # Pool metrics might be available depending on implementation
        if "pool_size" in metrics:
            assert isinstance(metrics["pool_size"], int)

    @pytest.mark.asyncio
    async def test_service_not_initialized_error(self):
        """Test error when using service before initialization."""
        service = AnalysisStorageService()

        # Should raise error when not initialized
        with pytest.raises(RuntimeError, match="Storage service not initialized"):
            await service.store_analysis("123", "test", {})

        with pytest.raises(RuntimeError, match="Storage service not initialized"):
            await service.get_analysis("123", "test")


@pytest.mark.integration
class TestDatabaseIntegrationWithPostgreSQL:
    """Integration tests with PostgreSQL (requires running database)."""

    @pytest_asyncio.fixture
    async def pg_connection(self):
        """Create PostgreSQL connection if available."""
        # Skip if PostgreSQL is not available
        pg_url = os.getenv("TEST_POSTGRESQL_URL")
        if not pg_url:
            pytest.skip("PostgreSQL not available for testing")

        conn = DatabaseConnection(database_url=pg_url)
        await conn.initialize()

        # Clean up any existing test data
        await conn.execute_query(
            "DELETE FROM analysis_results WHERE customer_id LIKE 'test_%'"
        )

        yield conn

        # Cleanup
        await conn.execute_query(
            "DELETE FROM analysis_results WHERE customer_id LIKE 'test_%'"
        )
        await conn.close()

    @pytest.mark.asyncio
    async def test_postgresql_connection_pooling(self, pg_connection):
        """Test connection pooling with PostgreSQL."""
        # Get initial metrics
        metrics1 = await pg_connection.execute_query(
            "SELECT count(*) as count FROM pg_stat_activity WHERE datname = current_database()"
        )
        initial_connections = metrics1[0]["count"]

        # Execute multiple queries concurrently
        tasks = []
        for i in range(10):
            tasks.append(
                pg_connection.execute_query(f"SELECT {i} as value, pg_sleep(0.1)")
            )

        results = await asyncio.gather(*tasks)
        assert len(results) == 10

        # Check that pooling limited connections
        metrics2 = await pg_connection.execute_query(
            "SELECT count(*) as count FROM pg_stat_activity WHERE datname = current_database()"
        )
        peak_connections = metrics2[0]["count"]

        # Should use pool instead of creating 10+ connections
        assert peak_connections <= initial_connections + pg_connection.pool_size

    @pytest.mark.asyncio
    async def test_postgresql_transaction_isolation(self, pg_connection):
        """Test transaction isolation with PostgreSQL."""
        # Use unique customer ID for this test
        customer_id = f"test_iso_{get_unique_customer_id()}"

        # Start two concurrent transactions
        async def transaction1():
            async with pg_connection.get_session() as session:
                # Insert a record
                await session.execute(
                    sa.text(
                        "INSERT INTO analysis_results (customer_id, analysis_type, data) "
                        f"VALUES ('{customer_id}', 'test', '{{}}' ::jsonb)"
                    )
                )
                # Wait a bit
                await asyncio.sleep(0.1)
                # Check count
                result = await session.execute(
                    sa.text(
                        f"SELECT COUNT(*) as count FROM analysis_results WHERE customer_id = '{customer_id}'"
                    )
                )
                return result.scalar()

        async def transaction2():
            async with pg_connection.get_session() as session:
                # Try to read while transaction1 is in progress
                await asyncio.sleep(0.05)  # Let transaction1 start
                result = await session.execute(
                    sa.text(
                        f"SELECT COUNT(*) as count FROM analysis_results WHERE customer_id = '{customer_id}'"
                    )
                )
                return result.scalar()

        # Run transactions concurrently
        count1, count2 = await asyncio.gather(transaction1(), transaction2())

        # Transaction2 should not see uncommitted changes from transaction1
        assert count1 == 1  # Transaction1 sees its own insert
        assert count2 == 0  # Transaction2 doesn't see uncommitted insert
