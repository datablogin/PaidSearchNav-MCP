"""Tests for database monitoring API endpoints."""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from paidsearchnav_mcp.api.v1.database import (
    DatabaseHealth,
    DatabaseMetrics,
    get_database_health,
    get_database_metrics,
    get_db_connection,
    reset_connection_pool,
)
from paidsearchnav_mcp.integrations.database import DatabaseConnection
from tests.utils import create_auth_headers


class TestDatabaseEndpoints:
    """Test suite for database monitoring endpoints."""

    @pytest.fixture
    def mock_request(self):
        """Create a mock request object."""
        request = Mock()
        request.app.state = Mock()
        return request

    @pytest.fixture
    def mock_user(self):
        """Create a mock authenticated user."""
        return {
            "id": "test_user",
            "email": "test@example.com",
            "is_admin": True,
        }

    @pytest.fixture
    def mock_db_connection(self):
        """Create a mock database connection."""
        db = Mock(spec=DatabaseConnection)
        db._pool_monitor = Mock()
        db.get_pool_health = Mock()
        db.drain_connections = AsyncMock()
        db.close = AsyncMock()
        db.initialize = AsyncMock()
        return db

    def test_get_db_connection_existing(self, mock_request, mock_db_connection):
        """Test getting existing database connection from app state."""
        mock_request.app.state.db_connection = mock_db_connection

        result = get_db_connection(mock_request)

        assert result == mock_db_connection

    def test_get_db_connection_lazy_init(self, mock_request):
        """Test lazy initialization of database connection."""
        # No db_connection in app state initially
        delattr(mock_request.app.state, "db_connection")

        with patch("paidsearchnav.api.v1.database.DatabaseConnection") as mock_db_class:
            mock_db_instance = Mock()
            mock_db_class.return_value = mock_db_instance

            result = get_db_connection(mock_request)

            assert result == mock_db_instance
            assert mock_request.app.state.db_connection == mock_db_instance
            mock_db_class.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_database_health_success(
        self, mock_request, mock_user, mock_db_connection
    ):
        """Test successful database health check."""
        health_data = {
            "status": "healthy",
            "message": "All systems operational",
            "metrics": {"pool_size": 10, "checked_out": 3},
            "warnings": [],
            "recommendations": [],
        }
        mock_db_connection.get_pool_health.return_value = health_data

        result = await get_database_health(
            request=mock_request,
            current_user=mock_user,
            db=mock_db_connection,
        )

        assert isinstance(result, DatabaseHealth)
        assert result.status == "healthy"
        assert result.message == "All systems operational"
        assert result.metrics == {"pool_size": 10, "checked_out": 3}
        assert result.warnings == []
        assert result.recommendations == []

    @pytest.mark.asyncio
    async def test_get_database_health_warning(
        self, mock_request, mock_user, mock_db_connection
    ):
        """Test database health check with warnings."""
        health_data = {
            "status": "warning",
            "metrics": {"pool_size": 10, "checked_out": 9},
            "warnings": ["High pool utilization: 90%"],
            "recommendations": ["Consider increasing pool_size"],
        }
        mock_db_connection.get_pool_health.return_value = health_data

        result = await get_database_health(
            request=mock_request,
            current_user=mock_user,
            db=mock_db_connection,
        )

        assert result.status == "warning"
        assert len(result.warnings) == 1
        assert "High pool utilization" in result.warnings[0]
        assert len(result.recommendations) == 1

    @pytest.mark.asyncio
    async def test_get_database_health_error(
        self, mock_request, mock_user, mock_db_connection
    ):
        """Test database health check error handling."""
        mock_db_connection.get_pool_health.side_effect = Exception("Connection failed")

        with pytest.raises(HTTPException) as exc_info:
            await get_database_health(
                request=mock_request,
                current_user=mock_user,
                db=mock_db_connection,
            )

        assert exc_info.value.status_code == 500
        assert exc_info.value.detail == "Failed to get database health"

    @pytest.mark.asyncio
    async def test_get_database_metrics_with_monitor(
        self, mock_request, mock_user, mock_db_connection
    ):
        """Test getting database metrics with pool monitor."""
        metrics_data = {
            "pool_size": 20,
            "checked_in": 15,
            "checked_out": 5,
            "overflow": 2,
            "total": 22,
            "utilization_percent": 25.0,
            "pool_type": "QueuePool",
            "database": "main",
        }
        mock_db_connection._pool_monitor.collect_metrics.return_value = metrics_data

        result = await get_database_metrics(
            request=mock_request,
            current_user=mock_user,
            db=mock_db_connection,
        )

        assert isinstance(result, DatabaseMetrics)
        assert result.pool_size == 20
        assert result.pool_available == 15
        assert result.pool_in_use == 5
        assert result.pool_overflow == 2
        assert result.pool_total == 22
        assert result.pool_utilization_percent == 25.0
        assert result.pool_type == "QueuePool"
        assert result.database == "main"

    @pytest.mark.asyncio
    async def test_get_database_metrics_without_monitor(
        self, mock_request, mock_user, mock_db_connection
    ):
        """Test getting database metrics without pool monitor (SQLite)."""
        mock_db_connection._pool_monitor = None
        mock_db_connection.database_url = "sqlite:///test.db"

        result = await get_database_metrics(
            request=mock_request,
            current_user=mock_user,
            db=mock_db_connection,
        )

        assert result.pool_type == "NullPool"
        assert result.pool_size == 0
        assert result.pool_available == 0
        assert result.pool_in_use == 0

    @pytest.mark.asyncio
    async def test_get_database_metrics_error(
        self, mock_request, mock_user, mock_db_connection
    ):
        """Test database metrics error handling."""
        mock_db_connection._pool_monitor.collect_metrics.side_effect = Exception(
            "Metrics collection failed"
        )

        with pytest.raises(HTTPException) as exc_info:
            await get_database_metrics(
                request=mock_request,
                current_user=mock_user,
                db=mock_db_connection,
            )

        assert exc_info.value.status_code == 500
        assert exc_info.value.detail == "Failed to get database metrics"

    @pytest.mark.asyncio
    async def test_reset_connection_pool_success(
        self, mock_request, mock_user, mock_db_connection
    ):
        """Test successful connection pool reset."""
        result = await reset_connection_pool(
            request=mock_request,
            current_user=mock_user,
            db=mock_db_connection,
        )

        assert result["status"] == "success"
        assert "graceful drainage" in result["message"]

        # Verify the correct sequence of operations
        mock_db_connection.drain_connections.assert_called_once_with(timeout=30.0)
        mock_db_connection.close.assert_called_once()
        mock_db_connection.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_reset_connection_pool_drain_error(
        self, mock_request, mock_user, mock_db_connection
    ):
        """Test connection pool reset with drain error."""
        mock_db_connection.drain_connections.side_effect = Exception("Drain failed")

        with pytest.raises(HTTPException) as exc_info:
            await reset_connection_pool(
                request=mock_request,
                current_user=mock_user,
                db=mock_db_connection,
            )

        assert exc_info.value.status_code == 500
        assert exc_info.value.detail == "Failed to reset connection pool"

    @pytest.mark.asyncio
    async def test_reset_connection_pool_init_error(
        self, mock_request, mock_user, mock_db_connection
    ):
        """Test connection pool reset with initialization error."""
        mock_db_connection.initialize.side_effect = Exception("Init failed")

        with pytest.raises(HTTPException) as exc_info:
            await reset_connection_pool(
                request=mock_request,
                current_user=mock_user,
                db=mock_db_connection,
            )

        assert exc_info.value.status_code == 500
        assert exc_info.value.detail == "Failed to reset connection pool"


class TestDatabaseEndpointIntegration:
    """Integration tests using FastAPI test client."""

    @pytest.fixture
    def app(self):
        """Create a test FastAPI app with database endpoints."""
        from fastapi import FastAPI

        from paidsearchnav.api.v1.database import router

        app = FastAPI()
        app.include_router(router, prefix="/api/v1")

        # Mock dependencies
        app.state.db_connection = Mock(spec=DatabaseConnection)

        return app

    @pytest.fixture
    def client(self, app):
        """Create a test client."""
        return TestClient(app)

    @pytest.fixture
    def auth_headers(self):
        """Create authentication headers."""
        return create_auth_headers()

    def test_health_endpoint(self, client, app, auth_headers):
        """Test /health endpoint integration."""
        from paidsearchnav.api.dependencies import get_current_user

        # Override the dependency
        async def mock_get_user():
            return {"id": "test_user"}

        app.dependency_overrides[get_current_user] = mock_get_user
        app.state.db_connection.get_pool_health.return_value = {
            "status": "healthy",
            "metrics": {},
            "warnings": [],
            "recommendations": [],
        }

        response = client.get("/api/v1/database/health", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_metrics_endpoint(self, client, app, auth_headers):
        """Test /metrics endpoint integration."""
        from paidsearchnav.api.dependencies import get_current_user

        # Override the dependency
        async def mock_get_user():
            return {"id": "test_user"}

        app.dependency_overrides[get_current_user] = mock_get_user
        app.state.db_connection._pool_monitor = Mock()
        app.state.db_connection._pool_monitor.collect_metrics.return_value = {
            "pool_size": 10,
            "checked_in": 7,
            "checked_out": 3,
            "overflow": 0,
            "total": 10,
            "utilization_percent": 30.0,
            "pool_type": "QueuePool",
            "database": "test",
        }

        response = client.get("/api/v1/database/metrics", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["pool_size"] == 10
        assert data["pool_utilization_percent"] == 30.0

    def test_reset_pool_endpoint(self, client, app, auth_headers):
        """Test /reset-pool endpoint integration."""
        from paidsearchnav.api.dependencies import get_current_user

        # Override the dependency
        async def mock_get_user():
            return {"id": "test_user"}

        app.dependency_overrides[get_current_user] = mock_get_user
        app.state.db_connection.drain_connections = AsyncMock()
        app.state.db_connection.close = AsyncMock()
        app.state.db_connection.initialize = AsyncMock()

        response = client.post("/api/v1/database/reset-pool", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"

    def test_endpoint_unauthorized(self, client):
        """Test endpoints require authentication."""
        endpoints = [
            ("/api/v1/database/health", "get"),
            ("/api/v1/database/metrics", "get"),
            ("/api/v1/database/reset-pool", "post"),
        ]

        for endpoint, method in endpoints:
            if method == "get":
                response = client.get(endpoint)
            else:
                response = client.post(endpoint)

            assert response.status_code == 403  # No auth token provided
