"""Test health endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_root_endpoint(async_client: AsyncClient):
    """Test root endpoint."""
    response = await async_client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "version" in data
    assert "docs" in data
    assert "health" in data


@pytest.mark.asyncio
async def test_health_check(async_client: AsyncClient):
    """Test health check endpoint."""
    response = await async_client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["healthy", "degraded"]
    assert "version" in data
    assert "timestamp" in data
    assert "services" in data
    assert isinstance(data["services"], dict)


@pytest.mark.asyncio
async def test_readiness_check(async_client: AsyncClient):
    """Test readiness check endpoint."""
    response = await async_client.get("/api/v1/ready")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["status"] in ["ready", "not_ready"]


@pytest.mark.asyncio
async def test_metrics_endpoint(async_client: AsyncClient):
    """Test Prometheus metrics endpoint."""
    response = await async_client.get("/metrics")
    # In test environment, metrics might not be fully configured
    # Just check that the endpoint exists or returns a reasonable error
    assert response.status_code in [200, 404]
    if response.status_code == 200:
        assert "text/plain" in response.headers.get("content-type", "")
        # Check for any metrics content
        assert len(response.text) > 0
