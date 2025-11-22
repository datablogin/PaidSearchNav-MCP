"""Comprehensive tests for WebSocket real-time functionality.

This module tests WebSocket real-time features including:
- Performance with multiple concurrent connections
- Event serialization and broadcasting
- Message queuing and filtering
- Long-running connection memory management
"""

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from paidsearchnav.api.models.responses import WebSocketMessage
from paidsearchnav.api.v1.websocket import ConnectionManager, broadcast_audit_update


class TestWebSocketPerformance:
    """Test WebSocket performance with multiple concurrent connections."""

    @pytest.mark.asyncio
    async def test_50_concurrent_connections(self):
        """Test WebSocket with 50 concurrent connections."""
        cm = ConnectionManager()
        audit_id = "performance-test-audit"

        # Create 50 mock websockets
        websockets = [AsyncMock() for _ in range(50)]

        # Connect all websockets
        for ws in websockets:
            await cm.connect(ws, audit_id)

        assert len(cm.active_connections[audit_id]) == 50

        # Send message to all connections
        message = WebSocketMessage(
            type="performance_test",
            data={"message": "Testing 50 connections", "load_test": True},
            timestamp=datetime.now(timezone.utc),
        )

        await cm.send_message(audit_id, message)

        # Verify all connections received the message
        for ws in websockets:
            ws.send_json.assert_called_once_with(message.model_dump())

    @pytest.mark.asyncio
    async def test_concurrent_connections_with_failures(self):
        """Test WebSocket with connections including some failures."""
        cm = ConnectionManager()
        audit_id = "failure-test-audit"

        # Create 20 websockets, make 5 fail
        good_websockets = [AsyncMock() for _ in range(15)]
        bad_websockets = [AsyncMock() for _ in range(5)]

        # Make bad websockets fail
        for ws in bad_websockets:
            ws.send_json.side_effect = Exception("Connection lost")

        # Connect all websockets
        all_websockets = good_websockets + bad_websockets
        for ws in all_websockets:
            await cm.connect(ws, audit_id)

        assert len(cm.active_connections[audit_id]) == 20

        # Send message
        message = WebSocketMessage(
            type="failure_test",
            data={"message": "Testing with failures"},
            timestamp=datetime.now(timezone.utc),
        )

        await cm.send_message(audit_id, message)

        # Verify failed connections were cleaned up
        assert len(cm.active_connections[audit_id]) == 15

        # Verify good connections still work
        for ws in good_websockets:
            assert ws in cm.active_connections[audit_id]

    @pytest.mark.asyncio
    async def test_message_throughput_performance(self):
        """Test message delivery throughput."""
        cm = ConnectionManager()
        audit_id = "throughput-test"

        # Create 10 connections
        websockets = [AsyncMock() for _ in range(10)]
        for ws in websockets:
            await cm.connect(ws, audit_id)

        # Send 20 messages
        for i in range(20):
            message = WebSocketMessage(
                type="throughput_test",
                data={"message_id": i},
                timestamp=datetime.now(timezone.utc),
            )
            await cm.send_message(audit_id, message)

        # Verify all websockets received all messages
        for ws in websockets:
            assert ws.send_json.call_count == 20


class TestWebSocketEventHandling:
    """Test WebSocket event handling and serialization."""

    @pytest.mark.asyncio
    async def test_audit_progress_events(self):
        """Test audit progress event broadcasting."""
        audit_id = "audit-progress-test"

        # Test basic progress events
        progress_events = [
            {"type": "audit_started", "data": {"audit_id": audit_id}},
            {
                "type": "analyzer_progress",
                "data": {"analyzer": "keyword_match", "progress": 50},
            },
            {"type": "audit_completed", "data": {"audit_id": audit_id}},
        ]

        with patch("paidsearchnav.api.v1.websocket.manager") as mock_manager:
            mock_manager.send_message = AsyncMock()

            # Broadcast each progress event
            for event in progress_events:
                await broadcast_audit_update(audit_id, event["type"], event["data"])

            # Verify all events were sent
            assert mock_manager.send_message.call_count == len(progress_events)

    @pytest.mark.asyncio
    async def test_completion_notifications(self):
        """Test completion notification events."""
        audit_id = "completion-test"

        completion_data = {
            "audit_id": audit_id,
            "status": "completed",
            "total_findings": 45,
            "analyzers_completed": ["keyword_match", "search_terms"],
        }

        with patch("paidsearchnav.api.v1.websocket.manager") as mock_manager:
            mock_manager.send_message = AsyncMock()

            await broadcast_audit_update(audit_id, "audit_completed", completion_data)

            mock_manager.send_message.assert_called_once()
            call_args = mock_manager.send_message.call_args
            assert call_args[0][0] == audit_id

            message = call_args[0][1]
            assert message.type == "audit_completed"
            assert message.data == completion_data

    @pytest.mark.asyncio
    async def test_error_event_propagation(self):
        """Test error event propagation through WebSocket."""
        audit_id = "error-test"

        error_data = {
            "analyzer": "keyword_match",
            "error": "API rate limit exceeded",
            "error_code": "RATE_LIMIT_EXCEEDED",
        }

        with patch("paidsearchnav.api.v1.websocket.manager") as mock_manager:
            mock_manager.send_message = AsyncMock()

            await broadcast_audit_update(audit_id, "analyzer_error", error_data)

            mock_manager.send_message.assert_called_once()
            call_args = mock_manager.send_message.call_args
            sent_audit_id, sent_message = call_args[0]
            assert sent_audit_id == audit_id
            assert sent_message.type == "analyzer_error"
            assert "error" in sent_message.data
            assert "error_code" in sent_message.data

    @pytest.mark.asyncio
    async def test_event_serialization(self):
        """Test event serialization for WebSocket messages."""
        # Test data types serialization
        test_data = {
            "nested_dict": {
                "metrics": {
                    "cost": 1234.56,
                    "clicks": 789,
                },
                "keywords": ["keyword1", "keyword2"],
            },
            "list_of_dicts": [
                {"id": 1, "name": "finding1", "severity": "high"},
                {"id": 2, "name": "finding2", "severity": "medium"},
            ],
            "null_value": None,
            "boolean_value": True,
            "float_value": 3.14159,
        }

        message = WebSocketMessage(
            type="complex_data_test",
            data=test_data,
            timestamp=datetime.now(timezone.utc),
        )

        # Verify the message can be serialized
        serialized = message.model_dump()
        assert isinstance(serialized, dict)
        assert serialized["type"] == "complex_data_test"
        assert "data" in serialized
        assert "timestamp" in serialized

        # Verify JSON serialization works
        json_str = json.dumps(serialized, default=str)
        assert isinstance(json_str, str)

        # Verify deserialization works
        deserialized = json.loads(json_str)
        assert deserialized["type"] == "complex_data_test"
        assert deserialized["data"]["boolean_value"] is True
        assert deserialized["data"]["null_value"] is None


class TestWebSocketMessageFlow:
    """Test WebSocket message flow and queuing."""

    @pytest.mark.asyncio
    async def test_message_queuing_during_disconnection(self):
        """Test message handling when connections are temporarily unavailable."""
        cm = ConnectionManager()
        audit_id = "queue-test"

        # Create websocket that will be disconnected
        websocket = AsyncMock()
        await cm.connect(websocket, audit_id)

        # Simulate disconnection by removing from active connections
        cm.disconnect(websocket, audit_id)

        # Try to send message to disconnected audit
        message = WebSocketMessage(
            type="queued_message",
            data={"message": "This should not be sent"},
            timestamp=datetime.now(timezone.utc),
        )

        # This should not raise an exception
        await cm.send_message(audit_id, message)

        # Websocket should not have received the message
        websocket.send_json.assert_not_called()

    @pytest.mark.asyncio
    async def test_message_filtering_by_audit_id(self):
        """Test message filtering by audit ID."""
        cm = ConnectionManager()

        # Create connections for different audits
        audit1_ws = AsyncMock()
        audit2_ws = AsyncMock()
        audit3_ws = AsyncMock()

        await cm.connect(audit1_ws, "audit-1")
        await cm.connect(audit2_ws, "audit-2")
        await cm.connect(audit3_ws, "audit-3")

        # Send messages to specific audits
        message1 = WebSocketMessage(
            type="audit1_message",
            data={"target": "audit-1"},
            timestamp=datetime.now(timezone.utc),
        )
        message2 = WebSocketMessage(
            type="audit2_message",
            data={"target": "audit-2"},
            timestamp=datetime.now(timezone.utc),
        )

        await cm.send_message("audit-1", message1)
        await cm.send_message("audit-2", message2)

        # Verify correct message filtering
        audit1_ws.send_json.assert_called_once_with(message1.model_dump())
        audit2_ws.send_json.assert_called_once_with(message2.model_dump())
        audit3_ws.send_json.assert_not_called()

    @pytest.mark.asyncio
    async def test_message_broadcasting_to_multiple_clients(self):
        """Test message broadcasting to multiple clients for same audit."""
        cm = ConnectionManager()
        audit_id = "broadcast-test"

        # Create multiple connections for same audit
        websockets = [AsyncMock() for _ in range(5)]
        for ws in websockets:
            await cm.connect(ws, audit_id)

        # Send broadcast message
        message = WebSocketMessage(
            type="broadcast_message",
            data={"message": "Hello all clients", "broadcast": True},
            timestamp=datetime.now(timezone.utc),
        )

        await cm.send_message(audit_id, message)

        # Verify all clients received the message
        for ws in websockets:
            ws.send_json.assert_called_once_with(message.model_dump())


class TestWebSocketResourceManagement:
    """Test WebSocket resource management and memory usage."""

    @pytest.mark.asyncio
    async def test_long_running_connection_memory_usage(self):
        """Test memory usage with long-running connections."""
        cm = ConnectionManager()
        audit_id = "memory-test"

        # Create connection
        websocket = AsyncMock()
        await cm.connect(websocket, audit_id)

        # Simulate connection with multiple messages
        for i in range(100):
            message = WebSocketMessage(
                type="memory_test",
                data={"message_id": i, "data": "test"},
                timestamp=datetime.now(timezone.utc),
            )
            await cm.send_message(audit_id, message)

        # Verify connection is still active
        assert audit_id in cm.active_connections
        assert websocket in cm.active_connections[audit_id]

        # Verify all messages were sent
        assert websocket.send_json.call_count == 100

        # Clean up connection
        cm.disconnect(websocket, audit_id)

        # Verify cleanup by testing behavior: disconnected websocket gets no messages
        cleanup_message = WebSocketMessage(
            type="cleanup_test",
            data={"test": "cleanup_verification"},
            timestamp=datetime.now(timezone.utc),
        )
        await cm.send_message(audit_id, cleanup_message)
        # Should not receive the cleanup message (disconnected)
        assert websocket.send_json.call_count == 100  # Only the original 100 messages

    @pytest.mark.asyncio
    async def test_connection_cleanup_prevents_memory_leaks(self):
        """Test connection cleanup prevents memory leaks."""
        cm = ConnectionManager()

        # Create and remove many connections using proper API
        websockets = []
        for i in range(100):
            audit_id = f"audit-{i}"
            websocket = AsyncMock()

            # Add connection using proper API
            await cm.connect(websocket, audit_id)
            websockets.append((websocket, audit_id))

            # Remove connection
            cm.disconnect(websocket, audit_id)

        # Verify cleanup by testing behavior: no messages sent to disconnected sockets
        test_message = WebSocketMessage(
            type="cleanup_test",
            data={"test": "cleanup"},
            timestamp=datetime.now(timezone.utc),
        )

        # Should not raise exception and no websockets should receive messages
        for _, audit_id in websockets:
            await cm.send_message(audit_id, test_message)

        # Verify no websockets received messages (they were disconnected)
        for websocket, _ in websockets:
            websocket.send_json.assert_not_called()


class TestWebSocketIntegration:
    """Test WebSocket integration with other components."""

    @pytest.mark.asyncio
    async def test_websocket_with_audit_lifecycle(self):
        """Test WebSocket integration with audit lifecycle."""
        cm = ConnectionManager()
        audit_id = "integration-test"

        # Create connection
        websocket = AsyncMock()
        await cm.connect(websocket, audit_id)

        # Simulate audit lifecycle events
        lifecycle_events = [
            ("audit_started", {"audit_id": audit_id}),
            ("analyzer_progress", {"analyzer": "keyword_match", "progress": 50}),
            ("analyzer_completed", {"analyzer": "keyword_match", "findings": 15}),
            ("audit_completed", {"audit_id": audit_id, "total_findings": 15}),
        ]

        with patch("paidsearchnav.api.v1.websocket.manager", cm):
            for event_type, event_data in lifecycle_events:
                await broadcast_audit_update(audit_id, event_type, event_data)

        # Verify all lifecycle events were sent
        assert websocket.send_json.call_count == len(lifecycle_events)

        # Verify event ordering
        sent_events = [
            call[0][0]["type"] for call in websocket.send_json.call_args_list
        ]
        expected_events = [event[0] for event in lifecycle_events]
        assert sent_events == expected_events
