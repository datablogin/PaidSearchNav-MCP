"""Simplified tests for WebSocket endpoints - focused and fast."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import WebSocketDisconnect
from jose import jwt
from pydantic import SecretStr

from paidsearchnav_mcp.api.models.responses import WebSocketMessage
from paidsearchnav_mcp.api.v1.websocket import ConnectionManager, broadcast_audit_update
from paidsearchnav_mcp.core.config import Settings


class TestConnectionManager:
    """Test WebSocket connection manager."""

    def test_init(self):
        """Test connection manager initialization."""
        cm = ConnectionManager()
        assert cm.active_connections == {}

    @pytest.mark.asyncio
    async def test_connect_success(self):
        """Test successful WebSocket connection."""
        cm = ConnectionManager()
        mock_websocket = AsyncMock()
        audit_id = "test-audit-123"

        await cm.connect(mock_websocket, audit_id)

        mock_websocket.accept.assert_called_once()
        assert audit_id in cm.active_connections
        assert mock_websocket in cm.active_connections[audit_id]

    @pytest.mark.asyncio
    async def test_connect_multiple_to_same_audit(self):
        """Test multiple connections to the same audit."""
        cm = ConnectionManager()
        mock_websocket1 = AsyncMock()
        mock_websocket2 = AsyncMock()
        audit_id = "test-audit-123"

        await cm.connect(mock_websocket1, audit_id)
        await cm.connect(mock_websocket2, audit_id)

        assert audit_id in cm.active_connections
        assert len(cm.active_connections[audit_id]) == 2
        assert mock_websocket1 in cm.active_connections[audit_id]
        assert mock_websocket2 in cm.active_connections[audit_id]

    def test_disconnect_existing_connection(self):
        """Test disconnecting existing connection."""
        cm = ConnectionManager()
        mock_websocket = AsyncMock()
        audit_id = "test-audit-123"

        # Setup connection
        cm.active_connections[audit_id] = {mock_websocket}

        cm.disconnect(mock_websocket, audit_id)

        assert audit_id not in cm.active_connections

    @pytest.mark.asyncio
    async def test_send_message_to_existing_connections(self):
        """Test sending message to existing connections."""
        cm = ConnectionManager()
        mock_websocket1 = AsyncMock()
        mock_websocket2 = AsyncMock()
        audit_id = "test-audit-123"

        # Setup connections
        cm.active_connections[audit_id] = {mock_websocket1, mock_websocket2}

        message = WebSocketMessage(
            type="test", data={"message": "Hello"}, timestamp=datetime.utcnow()
        )

        await cm.send_message(audit_id, message)

        mock_websocket1.send_json.assert_called_once_with(message.model_dump())
        mock_websocket2.send_json.assert_called_once_with(message.model_dump())

    @pytest.mark.asyncio
    async def test_send_message_handles_disconnected_clients(self):
        """Test sending message handles disconnected clients."""
        cm = ConnectionManager()
        mock_websocket1 = AsyncMock()
        mock_websocket2 = AsyncMock()
        audit_id = "test-audit-123"

        # Setup connections
        cm.active_connections[audit_id] = {mock_websocket1, mock_websocket2}

        # Make one websocket fail
        mock_websocket1.send_json.side_effect = Exception("Connection lost")

        message = WebSocketMessage(
            type="test", data={"message": "Hello"}, timestamp=datetime.utcnow()
        )

        await cm.send_message(audit_id, message)

        # Failed connection should be removed
        assert mock_websocket1 not in cm.active_connections[audit_id]
        assert mock_websocket2 in cm.active_connections[audit_id]
        mock_websocket2.send_json.assert_called_once_with(message.model_dump())


class TestWebSocketAuthentication:
    """Test WebSocket authentication logic."""

    @pytest.fixture
    def mock_settings(self):
        """Mock settings for testing."""
        return Settings(
            jwt_secret_key=SecretStr("test-secret-key"),
            jwt_algorithm="HS256",
            jwt_expire_minutes=30,
        )

    @pytest.fixture
    def valid_token(self, mock_settings):
        """Create a valid JWT token for testing."""
        payload = {
            "sub": "test-user-123",
            "exp": datetime.utcnow() + timedelta(minutes=30),
        }
        return jwt.encode(
            payload,
            mock_settings.jwt_secret_key.get_secret_value(),
            algorithm=mock_settings.jwt_algorithm,
        )

    @pytest.fixture
    def expired_token(self, mock_settings):
        """Create an expired JWT token for testing."""
        payload = {
            "sub": "test-user-123",
            "exp": datetime.utcnow() - timedelta(minutes=1),
        }
        return jwt.encode(
            payload,
            mock_settings.jwt_secret_key.get_secret_value(),
            algorithm=mock_settings.jwt_algorithm,
        )

    @pytest.mark.asyncio
    async def test_websocket_connection_rejects_missing_token(self, mock_settings):
        """Test WebSocket connection rejects requests without authentication token."""
        mock_websocket = AsyncMock()
        audit_id = "test-audit-123"

        with patch(
            "paidsearchnav.api.v1.websocket.get_settings", return_value=mock_settings
        ):
            from paidsearchnav.api.v1.websocket import audit_updates

            await audit_updates(mock_websocket, audit_id, None, mock_settings)

            mock_websocket.close.assert_called_once_with(
                code=1008, reason="Token required"
            )

    @pytest.mark.asyncio
    async def test_websocket_connection_rejects_malformed_token(self, mock_settings):
        """Test WebSocket connection rejects malformed JWT tokens."""
        mock_websocket = AsyncMock()
        audit_id = "test-audit-123"
        invalid_token = "invalid.token.here"

        with patch(
            "paidsearchnav.api.v1.websocket.get_settings", return_value=mock_settings
        ):
            from paidsearchnav.api.v1.websocket import audit_updates

            await audit_updates(mock_websocket, audit_id, invalid_token, mock_settings)

            mock_websocket.close.assert_called_once_with(
                code=1008, reason="Invalid token"
            )

    @pytest.mark.asyncio
    async def test_websocket_connection_rejects_expired_token(
        self, mock_settings, expired_token
    ):
        """Test WebSocket connection rejects expired JWT tokens."""
        mock_websocket = AsyncMock()
        audit_id = "test-audit-123"

        with patch(
            "paidsearchnav.api.v1.websocket.get_settings", return_value=mock_settings
        ):
            from paidsearchnav.api.v1.websocket import audit_updates

            await audit_updates(mock_websocket, audit_id, expired_token, mock_settings)

            mock_websocket.close.assert_called_once_with(
                code=1008, reason="Invalid token"
            )

    @pytest.mark.asyncio
    async def test_websocket_connection_rejects_token_without_subject(
        self, mock_settings
    ):
        """Test WebSocket connection rejects JWT tokens missing subject claim."""
        mock_websocket = AsyncMock()
        audit_id = "test-audit-123"

        # Token without 'sub' claim
        payload = {"exp": datetime.utcnow() + timedelta(minutes=30)}
        token = jwt.encode(
            payload,
            mock_settings.jwt_secret_key.get_secret_value(),
            algorithm=mock_settings.jwt_algorithm,
        )

        with patch(
            "paidsearchnav.api.v1.websocket.get_settings", return_value=mock_settings
        ):
            from paidsearchnav.api.v1.websocket import audit_updates

            await audit_updates(mock_websocket, audit_id, token, mock_settings)

            mock_websocket.close.assert_called_once_with(
                code=1008, reason="Invalid token"
            )


class TestWebSocketAuthorization:
    """Test WebSocket authorization for audit access."""

    @pytest.fixture
    def mock_settings(self):
        """Mock settings for testing."""
        settings = Settings(
            jwt_secret_key=SecretStr("test-secret-key"),
            jwt_algorithm="HS256",
            jwt_expire_minutes=30,
        )
        return settings

    @pytest.fixture
    def valid_token(self, mock_settings):
        """Create a valid JWT token for testing."""
        payload = {
            "sub": "test-user-123",
            "exp": datetime.utcnow() + timedelta(minutes=30),
        }
        return jwt.encode(
            payload,
            mock_settings.jwt_secret_key.get_secret_value(),
            algorithm=mock_settings.jwt_algorithm,
        )

    @pytest.mark.asyncio
    async def test_websocket_rejects_nonexistent_audit(
        self, mock_settings, valid_token
    ):
        """Test WebSocket connection rejects access to non-existent audit."""
        mock_websocket = AsyncMock()
        audit_id = "non-existent-audit"

        # Mock repository to return None for non-existent audit
        mock_repository = AsyncMock()
        mock_repository.get_audit.return_value = None

        # Mock websocket app state
        mock_websocket.app.state.repository = mock_repository

        with patch(
            "paidsearchnav.api.v1.websocket.get_settings", return_value=mock_settings
        ):
            from paidsearchnav.api.v1.websocket import audit_updates

            await audit_updates(mock_websocket, audit_id, valid_token, mock_settings)

            mock_websocket.close.assert_called_once_with(
                code=1008, reason="Audit not found"
            )
            # Verify audit was queried
            mock_repository.get_audit.assert_called_once_with(audit_id)

    @pytest.mark.asyncio
    async def test_websocket_rejects_unauthorized_audit_access(
        self, mock_settings, valid_token
    ):
        """Test WebSocket connection rejects access to unauthorized audit."""
        mock_websocket = AsyncMock()
        audit_id = "test-audit-123"
        user_id = "test-user-123"

        # Mock repository - audit exists but user has no access
        mock_repository = AsyncMock()
        mock_repository.get_audit.return_value = {
            "id": audit_id,
            "customer_id": "other-customer-456",
            "status": "running",
        }
        mock_repository.user_has_customer_access.return_value = False

        # Mock websocket app state
        mock_websocket.app.state.repository = mock_repository

        with patch(
            "paidsearchnav.api.v1.websocket.get_settings", return_value=mock_settings
        ):
            from paidsearchnav.api.v1.websocket import audit_updates

            await audit_updates(mock_websocket, audit_id, valid_token, mock_settings)

            mock_websocket.close.assert_called_once_with(
                code=1008, reason="Unauthorized access to audit"
            )
            # Verify audit and access were checked
            mock_repository.get_audit.assert_called_once_with(audit_id)
            mock_repository.user_has_customer_access.assert_called_once_with(
                user_id, "other-customer-456"
            )

    @pytest.mark.asyncio
    async def test_websocket_allows_authorized_audit_access(
        self, mock_settings, valid_token
    ):
        """Test WebSocket connection allows access to authorized audit."""
        mock_websocket = AsyncMock()
        audit_id = "test-audit-123"
        user_id = "test-user-123"

        # Mock to disconnect immediately after successful connection
        mock_websocket.receive_text.side_effect = WebSocketDisconnect()

        # Mock repository - audit exists and user has access
        mock_repository = AsyncMock()
        mock_repository.get_audit.return_value = {
            "id": audit_id,
            "customer_id": "test-customer-123",
            "status": "running",
        }
        mock_repository.user_has_customer_access.return_value = True

        # Mock websocket app state
        mock_websocket.app.state.repository = mock_repository

        with patch(
            "paidsearchnav.api.v1.websocket.get_settings", return_value=mock_settings
        ):
            with patch("paidsearchnav.api.v1.websocket.manager") as mock_manager:
                mock_manager.connect = AsyncMock()
                mock_manager.disconnect = AsyncMock()

                from paidsearchnav.api.v1.websocket import audit_updates

                await audit_updates(
                    mock_websocket, audit_id, valid_token, mock_settings
                )

                # Verify connection was established (not closed for auth reasons)
                mock_websocket.close.assert_not_called()
                mock_manager.connect.assert_called_once_with(mock_websocket, audit_id)

                # Verify audit and access were checked
                mock_repository.get_audit.assert_called_once_with(audit_id)
                mock_repository.user_has_customer_access.assert_called_once_with(
                    user_id, "test-customer-123"
                )

    @pytest.mark.asyncio
    async def test_websocket_authorization_sequence(self, mock_settings, valid_token):
        """Test WebSocket authorization occurs after authentication and before connection."""
        mock_websocket = AsyncMock()
        audit_id = "test-audit-123"
        user_id = "test-user-123"

        # Track call order
        call_order = []

        # Mock repository
        mock_repository = AsyncMock()

        async def mock_get_audit(aid):
            call_order.append(("get_audit", aid))
            return {
                "id": aid,
                "customer_id": "test-customer-123",
                "status": "running",
            }

        async def mock_user_has_customer_access(uid, cid):
            call_order.append(("user_has_customer_access", uid, cid))
            return True

        mock_repository.get_audit = mock_get_audit
        mock_repository.user_has_customer_access = mock_user_has_customer_access

        # Mock websocket app state
        mock_websocket.app.state.repository = mock_repository

        # Mock to disconnect immediately after connection
        mock_websocket.receive_text.side_effect = WebSocketDisconnect()

        with patch(
            "paidsearchnav.api.v1.websocket.get_settings", return_value=mock_settings
        ):
            with patch("paidsearchnav.api.v1.websocket.manager") as mock_manager:

                async def mock_connect(ws, aid):
                    call_order.append(("connect", aid))

                mock_manager.connect = mock_connect
                mock_manager.disconnect = AsyncMock()

                from paidsearchnav.api.v1.websocket import audit_updates

                await audit_updates(
                    mock_websocket, audit_id, valid_token, mock_settings
                )

                # Verify correct call order: authentication → get_audit → check access → connect
                assert call_order == [
                    ("get_audit", audit_id),
                    ("user_has_customer_access", user_id, "test-customer-123"),
                    ("connect", audit_id),
                ]


class TestWebSocketMessages:
    """Test WebSocket message handling including ping/pong and JSON parsing."""

    @pytest.fixture
    def mock_settings(self):
        """Mock settings for message tests."""
        return Settings(
            jwt_secret_key=SecretStr("test-secret-key"),
            jwt_algorithm="HS256",
            jwt_expire_minutes=30,
        )

    @pytest.fixture
    def valid_token(self, mock_settings):
        """Create a valid JWT token for message tests."""
        payload = {
            "sub": "test-user-123",
            "exp": datetime.utcnow() + timedelta(minutes=30),
        }
        return jwt.encode(
            payload,
            mock_settings.jwt_secret_key.get_secret_value(),
            algorithm=mock_settings.jwt_algorithm,
        )

    @pytest.mark.asyncio
    async def test_websocket_ping_pong_mechanism(self, mock_settings, valid_token):
        """Test WebSocket ping/pong message handling."""
        mock_websocket = AsyncMock()
        audit_id = "test-audit-123"

        # Mock to receive ping message, then disconnect
        ping_message = '{"type": "ping"}'
        mock_websocket.receive_text.side_effect = [ping_message, WebSocketDisconnect()]

        # Mock repository for auth checks
        mock_repository = AsyncMock()
        mock_repository.get_audit.return_value = {
            "id": audit_id,
            "customer_id": "test-customer-123",
            "status": "running",
        }
        mock_repository.user_has_customer_access.return_value = True

        # Mock websocket app state
        mock_websocket.app.state.repository = mock_repository

        with patch(
            "paidsearchnav.api.v1.websocket.get_settings", return_value=mock_settings
        ):
            with patch("paidsearchnav.api.v1.websocket.manager") as mock_manager:
                mock_manager.connect = AsyncMock()
                mock_manager.disconnect = AsyncMock()

                from paidsearchnav.api.v1.websocket import audit_updates

                await audit_updates(
                    mock_websocket, audit_id, valid_token, mock_settings
                )

                # Verify pong response was sent
                send_calls = mock_websocket.send_json.call_args_list
                pong_found = False
                for call in send_calls:
                    message = call[0][0]
                    if message["type"] == "pong":
                        pong_found = True
                        assert "timestamp" in message["data"]
                        break

                assert pong_found, "Pong response not found in WebSocket messages"

    @pytest.mark.asyncio
    async def test_websocket_invalid_json_handling(self, mock_settings, valid_token):
        """Test WebSocket handling of malformed JSON messages."""
        mock_websocket = AsyncMock()
        audit_id = "test-audit-123"

        # Mock to receive invalid JSON, then disconnect
        mock_websocket.receive_text.side_effect = [
            "invalid json data",
            WebSocketDisconnect(),
        ]

        # Mock repository for auth checks
        mock_repository = AsyncMock()
        mock_repository.get_audit.return_value = {
            "id": audit_id,
            "customer_id": "test-customer-123",
            "status": "running",
        }
        mock_repository.user_has_customer_access.return_value = True

        # Mock websocket app state
        mock_websocket.app.state.repository = mock_repository

        with patch(
            "paidsearchnav.api.v1.websocket.get_settings", return_value=mock_settings
        ):
            with patch("paidsearchnav.api.v1.websocket.manager") as mock_manager:
                mock_manager.connect = AsyncMock()
                mock_manager.disconnect = AsyncMock()

                from paidsearchnav.api.v1.websocket import audit_updates

                await audit_updates(
                    mock_websocket, audit_id, valid_token, mock_settings
                )

                # Verify error message was sent
                send_calls = mock_websocket.send_json.call_args_list
                error_found = False
                for call in send_calls:
                    message = call[0][0]
                    if message["type"] == "error":
                        error_found = True
                        assert message["data"]["message"] == "Invalid JSON"
                        break

                assert error_found, "Error response not found for invalid JSON"

    @pytest.mark.asyncio
    async def test_websocket_timeout_ping_mechanism(self, mock_settings, valid_token):
        """Test WebSocket timeout handling sends ping."""
        import asyncio

        mock_websocket = AsyncMock()
        audit_id = "test-audit-123"

        # Mock to timeout once, then disconnect
        mock_websocket.receive_text.side_effect = [
            asyncio.TimeoutError(),
            WebSocketDisconnect(),
        ]

        # Mock repository for auth checks
        mock_repository = AsyncMock()
        mock_repository.get_audit.return_value = {
            "id": audit_id,
            "customer_id": "test-customer-123",
            "status": "running",
        }
        mock_repository.user_has_customer_access.return_value = True

        # Mock websocket app state
        mock_websocket.app.state.repository = mock_repository

        with patch(
            "paidsearchnav.api.v1.websocket.get_settings", return_value=mock_settings
        ):
            with patch("paidsearchnav.api.v1.websocket.manager") as mock_manager:
                mock_manager.connect = AsyncMock()
                mock_manager.disconnect = AsyncMock()

                from paidsearchnav.api.v1.websocket import audit_updates

                await audit_updates(
                    mock_websocket, audit_id, valid_token, mock_settings
                )

                # Verify ping was sent on timeout
                send_calls = mock_websocket.send_json.call_args_list
                ping_found = False
                for call in send_calls:
                    message = call[0][0]
                    if message["type"] == "ping":
                        ping_found = True
                        assert "timestamp" in message["data"]
                        break

                assert ping_found, "Ping not sent on timeout"

    @pytest.mark.asyncio
    async def test_websocket_initial_connection_message(
        self, mock_settings, valid_token
    ):
        """Test WebSocket sends initial connection message."""
        mock_websocket = AsyncMock()
        audit_id = "test-audit-123"

        # Mock to disconnect immediately after connection
        mock_websocket.receive_text.side_effect = WebSocketDisconnect()

        # Mock repository for auth checks
        mock_repository = AsyncMock()
        mock_repository.get_audit.return_value = {
            "id": audit_id,
            "customer_id": "test-customer-123",
            "status": "running",
        }
        mock_repository.user_has_customer_access.return_value = True

        # Mock websocket app state
        mock_websocket.app.state.repository = mock_repository

        with patch(
            "paidsearchnav.api.v1.websocket.get_settings", return_value=mock_settings
        ):
            with patch("paidsearchnav.api.v1.websocket.manager") as mock_manager:
                mock_manager.connect = AsyncMock()
                mock_manager.disconnect = AsyncMock()

                from paidsearchnav.api.v1.websocket import audit_updates

                await audit_updates(
                    mock_websocket, audit_id, valid_token, mock_settings
                )

                # Verify initial connection message was sent
                send_calls = mock_websocket.send_json.call_args_list
                assert len(send_calls) >= 1, "No messages sent on connection"

                initial_message = send_calls[0][0][0]
                assert initial_message["type"] == "connected"
                assert initial_message["data"]["audit_id"] == audit_id
                assert "timestamp" in initial_message["data"]

    @pytest.mark.asyncio
    async def test_websocket_disconnect_handling(self):
        """Test WebSocket disconnect handling."""
        mock_websocket = AsyncMock()
        audit_id = "test-audit-123"

        # Mock settings
        mock_settings = Settings(
            jwt_secret_key=SecretStr("test-secret-key"),
            jwt_algorithm="HS256",
            jwt_expire_minutes=30,
        )

        # Valid token
        payload = {
            "sub": "test-user-123",
            "exp": datetime.utcnow() + timedelta(minutes=30),
        }
        valid_token = jwt.encode(
            payload,
            mock_settings.jwt_secret_key.get_secret_value(),
            algorithm=mock_settings.jwt_algorithm,
        )

        # Mock receive_text to raise WebSocketDisconnect immediately
        mock_websocket.receive_text.side_effect = WebSocketDisconnect()

        # Mock repository for auth checks
        mock_repository = AsyncMock()
        mock_repository.get_audit.return_value = {
            "id": audit_id,
            "customer_id": "test-customer-123",
            "status": "running",
        }
        mock_repository.user_has_customer_access.return_value = True

        # Mock websocket app state
        mock_websocket.app.state.repository = mock_repository

        with patch(
            "paidsearchnav.api.v1.websocket.get_settings", return_value=mock_settings
        ):
            with patch("paidsearchnav.api.v1.websocket.manager") as mock_manager:
                mock_manager.connect = AsyncMock()
                mock_manager.disconnect = AsyncMock()

                from paidsearchnav.api.v1.websocket import audit_updates

                await audit_updates(
                    mock_websocket, audit_id, valid_token, mock_settings
                )

                # Verify connection was established
                mock_manager.connect.assert_called_once_with(mock_websocket, audit_id)
                # Verify disconnect was called
                mock_manager.disconnect.assert_called_once_with(
                    mock_websocket, audit_id
                )


class TestBroadcastFunction:
    """Test broadcast audit update function."""

    @pytest.mark.asyncio
    async def test_broadcast_audit_update(self):
        """Test broadcast_audit_update function."""
        audit_id = "test-audit-123"
        update_type = "progress"
        data = {"progress": 50, "message": "Processing keywords"}

        with patch("paidsearchnav.api.v1.websocket.manager") as mock_manager:
            # Make send_message async
            mock_manager.send_message = AsyncMock()

            await broadcast_audit_update(audit_id, update_type, data)

            mock_manager.send_message.assert_called_once()
            call_args = mock_manager.send_message.call_args
            assert call_args[0][0] == audit_id

            message = call_args[0][1]
            assert message.type == update_type
            assert message.data == data
            assert isinstance(message.timestamp, datetime)


class TestConcurrentConnections:
    """Test concurrent WebSocket connections."""

    @pytest.mark.asyncio
    async def test_multiple_concurrent_connections(self):
        """Test multiple concurrent WebSocket connections."""
        cm = ConnectionManager()
        audit_id = "test-audit-123"

        # Create multiple mock websockets
        websockets = [AsyncMock() for _ in range(5)]

        # Connect all websockets
        for ws in websockets:
            await cm.connect(ws, audit_id)

        assert len(cm.active_connections[audit_id]) == 5

        # Send message to all
        message = WebSocketMessage(
            type="test", data={"message": "Hello"}, timestamp=datetime.utcnow()
        )
        await cm.send_message(audit_id, message)

        # Verify all received message
        for ws in websockets:
            ws.send_json.assert_called_once_with(message.model_dump())

    @pytest.mark.asyncio
    async def test_connection_cleanup_on_partial_failure(self):
        """Test connection cleanup when some connections fail."""
        cm = ConnectionManager()
        audit_id = "test-audit-123"

        # Create websockets with some that will fail
        good_ws1 = AsyncMock()
        good_ws2 = AsyncMock()
        bad_ws1 = AsyncMock()
        bad_ws2 = AsyncMock()

        # Make some websockets fail
        bad_ws1.send_json.side_effect = Exception("Connection lost")
        bad_ws2.send_json.side_effect = Exception("Connection lost")

        # Connect all
        for ws in [good_ws1, good_ws2, bad_ws1, bad_ws2]:
            await cm.connect(ws, audit_id)

        assert len(cm.active_connections[audit_id]) == 4

        # Send message
        message = WebSocketMessage(
            type="test", data={"message": "Hello"}, timestamp=datetime.utcnow()
        )
        await cm.send_message(audit_id, message)

        # Verify failed connections were removed
        assert len(cm.active_connections[audit_id]) == 2
        assert good_ws1 in cm.active_connections[audit_id]
        assert good_ws2 in cm.active_connections[audit_id]
        assert bad_ws1 not in cm.active_connections[audit_id]
        assert bad_ws2 not in cm.active_connections[audit_id]

    @pytest.mark.asyncio
    async def test_broadcast_to_multiple_audits(self):
        """Test broadcasting to multiple different audits."""
        cm = ConnectionManager()

        # Setup connections for different audits
        audit1_ws = AsyncMock()
        audit2_ws = AsyncMock()
        audit3_ws = AsyncMock()

        await cm.connect(audit1_ws, "audit-1")
        await cm.connect(audit2_ws, "audit-2")
        await cm.connect(audit3_ws, "audit-3")

        # Send message to specific audit
        message = WebSocketMessage(
            type="test", data={"message": "Hello"}, timestamp=datetime.utcnow()
        )
        await cm.send_message("audit-2", message)

        # Verify only audit-2 received message
        audit1_ws.send_json.assert_not_called()
        audit2_ws.send_json.assert_called_once_with(message.model_dump())
        audit3_ws.send_json.assert_not_called()


class TestResourceManagement:
    """Test resource management and cleanup."""

    def test_connection_manager_memory_usage(self):
        """Test connection manager doesn't leak memory."""
        cm = ConnectionManager()

        # Add many connections
        for i in range(100):
            audit_id = f"audit-{i}"
            ws = AsyncMock()
            cm.active_connections[audit_id] = {ws}

        assert len(cm.active_connections) == 100

        # Remove all connections
        for i in range(100):
            audit_id = f"audit-{i}"
            ws = list(cm.active_connections[audit_id])[0]
            cm.disconnect(ws, audit_id)

        assert len(cm.active_connections) == 0

    def test_global_manager_singleton(self):
        """Test global manager is singleton."""
        from paidsearchnav.api.v1.websocket import manager as manager1
        from paidsearchnav.api.v1.websocket import manager as manager2

        assert manager1 is manager2
