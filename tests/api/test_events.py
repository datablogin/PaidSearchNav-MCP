"""Tests for server-sent events endpoints."""

import json
from unittest.mock import Mock, patch

import pytest
from httpx import AsyncClient


class TestEventsEndpoints:
    """Test SSE (Server-Sent Events) API endpoints."""

    @pytest.mark.asyncio
    async def test_sse_connection_success(
        self, async_client: AsyncClient, auth_headers: dict, mock_repository: Mock
    ):
        """Test successful SSE connection establishment."""
        # This test verifies that the SSE endpoint accepts connections
        # Note: Full SSE testing requires special handling for streaming responses

        # Start the SSE connection (this will be a streaming response)
        with patch("paidsearchnav.api.v1.events.event_generator") as mock_generator:
            # Mock the generator to yield a few events then stop
            async def mock_events(*args, **kwargs):
                yield json.dumps(
                    {"type": "connected", "data": {"customer_id": "1234567890"}}
                )
                yield json.dumps(
                    {"type": "heartbeat", "data": {"timestamp": "2024-01-01T00:00:00"}}
                )

            mock_generator.return_value = mock_events()

            # The response will be a streaming response
            # In a real test environment, we'd need to handle this differently
            response = await async_client.get(
                "/api/v1/events",
                headers={**auth_headers, "Accept": "text/event-stream"},
            )

            # Basic validation - actual SSE testing would require streaming client
            assert response.status_code == 200
            assert (
                response.headers["content-type"] == "text/event-stream; charset=utf-8"
            )
            assert response.headers["cache-control"] == "no-cache"

    @pytest.mark.asyncio
    async def test_sse_no_auth(self, async_client: AsyncClient):
        """Test SSE connection without authentication."""
        response = await async_client.get(
            "/api/v1/events", headers={"Accept": "text/event-stream"}
        )

        assert response.status_code == 403
        assert "Not authenticated" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_sse_with_audit_filter(
        self, async_client: AsyncClient, auth_headers: dict, mock_repository: Mock
    ):
        """Test SSE connection with audit ID filter."""
        # Mock audit
        mock_repository.get_audit.return_value = {
            "id": "test-audit-123",
            "customer_id": "1234567890",
            "status": "running",
        }

        with patch("paidsearchnav.api.v1.events.event_generator") as mock_generator:

            async def mock_events(*args, **kwargs):
                yield json.dumps(
                    {
                        "type": "connected",
                        "data": {
                            "customer_id": "1234567890",
                            "audit_id": "test-audit-123",
                        },
                    }
                )

            mock_generator.return_value = mock_events()

            response = await async_client.get(
                "/api/v1/events?audit_id=test-audit-123",
                headers={**auth_headers, "Accept": "text/event-stream"},
            )

            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_sse_audit_not_found(
        self, async_client: AsyncClient, auth_headers: dict, mock_repository: Mock
    ):
        """Test SSE with non-existent audit ID."""
        mock_repository.get_audit.return_value = None

        response = await async_client.get(
            "/api/v1/events?audit_id=non-existent", headers=auth_headers
        )

        assert response.status_code == 404
        assert "Audit" in response.json()["detail"]
        assert "not found" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_sse_audit_no_permission(
        self, async_client: AsyncClient, auth_headers: dict, mock_repository: Mock
    ):
        """Test SSE for audit from different customer."""
        # Mock audit belongs to different customer
        mock_repository.get_audit.return_value = {
            "id": "test-audit-123",
            "customer_id": "different-customer-456",
            "status": "running",
        }

        response = await async_client.get(
            "/api/v1/events?audit_id=test-audit-123", headers=auth_headers
        )

        assert response.status_code == 403
        assert "permission" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_event_generator_audit_progress(self, mock_repository: Mock):
        """Test event generator produces audit progress events."""
        from paidsearchnav.api.v1.events import event_generator

        # Mock request
        mock_request = Mock()

        # Mock is_disconnected as async function
        disconnect_count = 0

        async def mock_is_disconnected():
            nonlocal disconnect_count
            disconnect_count += 1
            return disconnect_count > 2

        mock_request.is_disconnected = mock_is_disconnected

        # Mock audit with changing progress
        mock_repository.get_audit.side_effect = [
            {"id": "test-audit-123", "status": "running", "progress": 25},
            {"id": "test-audit-123", "status": "running", "progress": 50},
            {"id": "test-audit-123", "status": "completed", "progress": 100},
        ]

        events = []
        async for event in event_generator(
            request=mock_request,
            customer_id="1234567890",
            audit_id="test-audit-123",
            repository=mock_repository,
        ):
            events.append(json.loads(event))
            if len(events) >= 3:
                break

        # Verify events
        assert events[0]["type"] == "connected"
        assert any(e["type"] == "audit_progress" for e in events)

        # Find progress events
        progress_events = [e for e in events if e["type"] == "audit_progress"]
        assert len(progress_events) > 0
        assert progress_events[0]["data"]["progress"] in [25, 50, 100]

    @pytest.mark.asyncio
    async def test_event_generator_heartbeat(self):
        """Test event generator sends heartbeat events."""
        from paidsearchnav.api.v1.events import event_generator

        # Mock request
        mock_request = Mock()
        disconnect_count = 0

        async def mock_is_disconnected():
            nonlocal disconnect_count
            disconnect_count += 1
            return disconnect_count > 2

        mock_request.is_disconnected = mock_is_disconnected

        events = []
        async for event in event_generator(
            request=mock_request,
            customer_id="1234567890",
            audit_id=None,
            repository=None,
        ):
            event_data = json.loads(event)
            events.append(event_data)
            if event_data["type"] == "heartbeat":
                break

        # Verify heartbeat was sent
        heartbeat_events = [e for e in events if e["type"] == "heartbeat"]
        assert len(heartbeat_events) > 0
        assert "timestamp" in heartbeat_events[0]["data"]

    @pytest.mark.asyncio
    async def test_event_generator_error_handling(self, mock_repository: Mock):
        """Test event generator handles errors gracefully."""
        from paidsearchnav.api.v1.events import event_generator

        # Mock request
        mock_request = Mock()

        # Mock is_disconnected as async function
        async def mock_is_disconnected():
            return False

        mock_request.is_disconnected = mock_is_disconnected

        # Mock repository to raise an error
        mock_repository.get_audit.side_effect = Exception("Database error")

        events = []
        try:
            async for event in event_generator(
                request=mock_request,
                customer_id="1234567890",
                audit_id="test-audit-123",
                repository=mock_repository,
            ):
                events.append(json.loads(event))
                # Stop after error event
                if events[-1]["type"] == "error":
                    break
        except Exception:
            pass

        # Should have received an error event
        error_events = [e for e in events if e["type"] == "error"]
        assert len(error_events) > 0
        assert "message" in error_events[0]["data"]

    @pytest.mark.asyncio
    async def test_sse_headers(self, async_client: AsyncClient, auth_headers: dict):
        """Test SSE response includes proper headers."""
        with patch("paidsearchnav.api.v1.events.event_generator") as mock_generator:

            async def mock_events(*args, **kwargs):
                yield json.dumps({"type": "connected", "data": {}})

            mock_generator.return_value = mock_events()

            response = await async_client.get(
                "/api/v1/events",
                headers={**auth_headers, "Accept": "text/event-stream"},
            )

            assert response.status_code == 200
            assert (
                response.headers["content-type"] == "text/event-stream; charset=utf-8"
            )
            assert response.headers["cache-control"] == "no-cache"
            assert response.headers["connection"] == "keep-alive"
            assert response.headers["x-accel-buffering"] == "no"
