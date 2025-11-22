"""Performance tests for WebSocket real-time functionality."""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from paidsearchnav.api.models.responses import WebSocketMessage
from paidsearchnav.api.v1.websocket import ConnectionManager


class TestWebSocketPerformance:
    """Test WebSocket performance with multiple concurrent connections."""

    @pytest.mark.asyncio
    async def test_connection_manager_init(self):
        """Test connection manager initialization."""
        cm = ConnectionManager()
        # Test behavior: no connections means no messages sent
        audit_id = "test-init"
        message = WebSocketMessage(
            type="test_init",
            data={"test": "init"},
            timestamp=datetime.now(timezone.utc),
        )
        # Should not raise exception even with no connections
        await cm.send_message(audit_id, message)

    @pytest.mark.asyncio
    async def test_small_concurrent_connections(self):
        """Test WebSocket with 5 concurrent connections."""
        cm = ConnectionManager()
        audit_id = "performance-test-audit"

        # Create 5 mock websockets
        websockets = [AsyncMock() for _ in range(5)]

        # Connect all websockets
        for ws in websockets:
            await cm.connect(ws, audit_id)

        assert len(cm.active_connections[audit_id]) == 5

        # Send message to all connections
        message = WebSocketMessage(
            type="performance_test",
            data={"message": "Testing 5 connections"},
            timestamp=datetime.now(timezone.utc),
        )

        await cm.send_message(audit_id, message)

        # Verify all connections received the message
        for ws in websockets:
            ws.send_json.assert_called_once_with(message.model_dump())

    @pytest.mark.asyncio
    async def test_large_concurrent_connections(self):
        """Test WebSocket with 100 concurrent connections."""
        cm = ConnectionManager()
        audit_id = "large-performance-test"

        # Create 100 mock websockets
        websockets = [AsyncMock() for _ in range(100)]

        # Connect all websockets
        for ws in websockets:
            await cm.connect(ws, audit_id)

        assert len(cm.active_connections[audit_id]) == 100

        # Send message to all connections
        message = WebSocketMessage(
            type="large_performance_test",
            data={"message": "Testing 100 connections", "load_test": True},
            timestamp=datetime.now(timezone.utc),
        )

        await cm.send_message(audit_id, message)

        # Verify all connections received the message
        for ws in websockets:
            ws.send_json.assert_called_once_with(message.model_dump())

    @pytest.mark.asyncio
    async def test_high_message_volume_performance(self):
        """Test performance with high message volume."""
        cm = ConnectionManager()
        audit_id = "high-volume-test"

        # Create 20 connections
        websockets = [AsyncMock() for _ in range(20)]
        for ws in websockets:
            await cm.connect(ws, audit_id)

        # Send 100 messages rapidly
        messages_sent = 0
        for i in range(100):
            message = WebSocketMessage(
                type="high_volume_test",
                data={"message_id": i, "batch": "performance"},
                timestamp=datetime.now(timezone.utc),
            )
            await cm.send_message(audit_id, message)
            messages_sent += 1

        # Verify all websockets received all messages
        for ws in websockets:
            assert ws.send_json.call_count == messages_sent

    @pytest.mark.asyncio
    async def test_connection_scalability(self):
        """Test connection scalability across multiple audits."""
        cm = ConnectionManager()

        # Create connections for 10 different audits
        audits_and_connections = []
        for i in range(10):
            audit_id = f"audit-{i}"
            websockets = [AsyncMock() for _ in range(5)]

            for ws in websockets:
                await cm.connect(ws, audit_id)

            audits_and_connections.append((audit_id, websockets))

        # Verify all audits have connections
        assert len(cm.active_connections) == 10
        for audit_id, websockets in audits_and_connections:
            assert len(cm.active_connections[audit_id]) == 5

        # Send messages to each audit
        for audit_id, websockets in audits_and_connections:
            message = WebSocketMessage(
                type="scalability_test",
                data={"audit_id": audit_id},
                timestamp=datetime.now(timezone.utc),
            )
            await cm.send_message(audit_id, message)

        # Verify each audit's connections received only their messages
        for audit_id, websockets in audits_and_connections:
            for ws in websockets:
                ws.send_json.assert_called_once()

    @pytest.mark.asyncio
    async def test_connection_cleanup_performance(self):
        """Test performance of connection cleanup operations."""
        cm = ConnectionManager()

        # Create many connections
        connections = []
        for i in range(50):
            audit_id = f"cleanup-test-{i}"
            websocket = AsyncMock()
            await cm.connect(websocket, audit_id)
            connections.append((audit_id, websocket))

        # Verify all connections exist
        assert len(cm.active_connections) == 50

        # Disconnect all connections
        for audit_id, websocket in connections:
            cm.disconnect(websocket, audit_id)

        # Verify all connections are cleaned up
        assert len(cm.active_connections) == 0

    @pytest.mark.asyncio
    async def test_concurrent_message_sending(self):
        """Test concurrent message sending to different audits."""
        cm = ConnectionManager()

        # Create connections for 5 audits
        audit_connections = {}
        for i in range(5):
            audit_id = f"concurrent-test-{i}"
            websockets = [AsyncMock() for _ in range(3)]

            for ws in websockets:
                await cm.connect(ws, audit_id)

            audit_connections[audit_id] = websockets

        # Send messages concurrently to all audits
        async def send_messages_to_audit(audit_id):
            for i in range(10):
                message = WebSocketMessage(
                    type="concurrent_test",
                    data={"audit_id": audit_id, "message_id": i},
                    timestamp=datetime.now(timezone.utc),
                )
                await cm.send_message(audit_id, message)

        # Run concurrent sends
        await asyncio.gather(
            *[send_messages_to_audit(audit_id) for audit_id in audit_connections.keys()]
        )

        # Verify all connections received all messages
        for audit_id, websockets in audit_connections.items():
            for ws in websockets:
                assert ws.send_json.call_count == 10

    @pytest.mark.asyncio
    async def test_mixed_connection_operations(self):
        """Test performance with mixed connect/disconnect/send operations."""
        cm = ConnectionManager()
        audit_id = "mixed-operations-test"

        # Start with some connections
        active_websockets = []
        for i in range(10):
            ws = AsyncMock()
            await cm.connect(ws, audit_id)
            active_websockets.append(ws)

        # Perform mixed operations
        for i in range(20):
            # Send a message
            message = WebSocketMessage(
                type="mixed_ops_test",
                data={"operation": i},
                timestamp=datetime.now(timezone.utc),
            )
            await cm.send_message(audit_id, message)

            # Occasionally disconnect and reconnect
            if i % 5 == 0 and active_websockets:
                # Disconnect one
                ws_to_disconnect = active_websockets.pop()
                cm.disconnect(ws_to_disconnect, audit_id)

                # Connect a new one
                new_ws = AsyncMock()
                await cm.connect(new_ws, audit_id)
                active_websockets.append(new_ws)

        # Verify final state
        assert len(cm.active_connections[audit_id]) == len(active_websockets)

        # Verify active connections received messages
        for ws in active_websockets:
            # Should have received some messages (depends on when they were connected)
            assert ws.send_json.call_count > 0
