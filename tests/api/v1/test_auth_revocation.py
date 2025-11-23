"""Tests for authentication token revocation functionality."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from jose import jwt

from paidsearchnav_mcp.api.token_blacklist import get_token_blacklist
from paidsearchnav_mcp.core.config import Settings

# Test constants
TEST_USER_ID = "test-user-123"
TEST_EMAIL = "test@example.com"


@pytest.fixture
def mock_repository():
    """Mock API repository with customer data."""
    repo = MagicMock()
    repo.get_customers_for_user = AsyncMock(
        return_value=[
            {"customer_id": "1234567890", "name": "Test Customer 1"},
            {"customer_id": "0987654321", "name": "Test Customer 2"},
        ]
    )
    return repo


@pytest.fixture
def test_jwt_token(mock_settings: Settings, base_datetime: datetime) -> str:
    """Create a test JWT token."""
    payload = {
        "sub": TEST_USER_ID,
        "email": TEST_EMAIL,
        "exp": base_datetime + timedelta(hours=1),
        "iat": base_datetime,
    }
    return jwt.encode(
        payload, mock_settings.jwt_secret_key.get_secret_value(), algorithm="HS256"
    )


@pytest.mark.asyncio
async def test_revoke_token_success(
    async_client: AsyncClient,
    mock_settings: Settings,
    mock_repository,
    test_jwt_token: str,
):
    """Test successful token revocation."""
    # Mock repository and token manager
    with (
        patch(
            "paidsearchnav.api.dependencies.get_repository",
            return_value=mock_repository,
        ),
        patch(
            "paidsearchnav.platforms.google.auth.OAuth2TokenManager"
        ) as mock_token_manager,
    ):
        # Setup token manager mocks
        mock_manager_instance = MagicMock()
        mock_manager_instance.has_valid_tokens.side_effect = [
            True,
            True,
        ]  # Both customers have tokens
        mock_manager_instance.revoke_tokens.return_value = None
        mock_token_manager.return_value = mock_manager_instance

        # Revoke the token
        response = await async_client.delete(
            "/api/v1/auth/revoke",
            headers={"Authorization": f"Bearer {test_jwt_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Tokens revoked successfully"
        assert data["data"]["user_id"] == TEST_USER_ID
        assert "revoked_at" in data["data"]

        # Verify Google OAuth tokens were revoked for both customers
        assert mock_manager_instance.has_valid_tokens.call_count == 2
        assert mock_manager_instance.revoke_tokens.call_count == 2
        mock_manager_instance.revoke_tokens.assert_any_call("1234567890")
        mock_manager_instance.revoke_tokens.assert_any_call("0987654321")

        # Verify token is blacklisted
        blacklist = get_token_blacklist()
        assert blacklist.is_token_blacklisted(test_jwt_token)


@pytest.mark.asyncio
async def test_revoke_token_without_customers(
    async_client: AsyncClient, mock_settings: Settings, test_jwt_token: str
):
    """Test token revocation when user has no customers."""
    # Mock repository with no customers
    mock_repo = MagicMock()
    mock_repo.get_customers_for_user = AsyncMock(return_value=[])

    with patch("paidsearchnav.api.dependencies.get_repository", return_value=mock_repo):
        # Revoke the token
        response = await async_client.delete(
            "/api/v1/auth/revoke",
            headers={"Authorization": f"Bearer {test_jwt_token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Tokens revoked successfully"

        # Verify token is still blacklisted even without customers
        blacklist = get_token_blacklist()
        assert blacklist.is_token_blacklisted(test_jwt_token)


@pytest.mark.asyncio
async def test_revoke_token_partial_failure(
    async_client: AsyncClient,
    mock_settings: Settings,
    mock_repository,
    test_jwt_token: str,
):
    """Test token revocation with partial Google OAuth revocation failure."""
    # Mock repository and token manager with partial failure
    with (
        patch(
            "paidsearchnav.api.dependencies.get_repository",
            return_value=mock_repository,
        ),
        patch(
            "paidsearchnav.platforms.google.auth.OAuth2TokenManager"
        ) as mock_token_manager,
    ):
        # Setup token manager mocks
        mock_manager_instance = MagicMock()
        mock_manager_instance.has_valid_tokens.side_effect = [True, True]
        # First revoke succeeds, second fails
        mock_manager_instance.revoke_tokens.side_effect = [
            None,
            Exception("Network error"),
        ]
        mock_token_manager.return_value = mock_manager_instance

        # Revoke the token
        response = await async_client.delete(
            "/api/v1/auth/revoke",
            headers={"Authorization": f"Bearer {test_jwt_token}"},
        )

        # Should still succeed overall
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Tokens revoked successfully"

        # Verify first customer was revoked
        mock_manager_instance.revoke_tokens.assert_any_call("1234567890")

        # JWT token should still be blacklisted
        blacklist = get_token_blacklist()
        assert blacklist.is_token_blacklisted(test_jwt_token)


@pytest.mark.asyncio
async def test_revoke_token_no_auth_header(async_client: AsyncClient):
    """Test token revocation without authentication header."""
    response = await async_client.delete("/api/v1/auth/revoke")
    assert response.status_code == 403
    assert "Not authenticated" in response.json()["detail"]


@pytest.mark.asyncio
async def test_revoke_token_invalid_token(async_client: AsyncClient):
    """Test token revocation with invalid token."""
    response = await async_client.delete(
        "/api/v1/auth/revoke",
        headers={"Authorization": "Bearer invalid_token"},
    )
    assert response.status_code == 401
    assert "Could not validate credentials" in response.json()["detail"]


@pytest.mark.asyncio
async def test_revoked_token_access_denied(
    async_client: AsyncClient, mock_settings: Settings, test_jwt_token: str
):
    """Test that revoked tokens are denied access to other endpoints."""
    # Mock empty repository
    mock_repo = MagicMock()
    mock_repo.get_customers_for_user = AsyncMock(return_value=[])

    with patch("paidsearchnav.api.dependencies.get_repository", return_value=mock_repo):
        # Revoke the token
        response = await async_client.delete(
            "/api/v1/auth/revoke",
            headers={"Authorization": f"Bearer {test_jwt_token}"},
        )
        assert response.status_code == 200

    # Try to access a protected endpoint with the revoked token
    response = await async_client.get(
        "/api/v1/audits",
        headers={"Authorization": f"Bearer {test_jwt_token}"},
    )

    # Should be denied
    assert response.status_code == 401
    assert "Token has been revoked" in response.json()["detail"]


@pytest.mark.asyncio
async def test_blacklist_cleanup():
    """Test that blacklist properly cleans up expired tokens."""
    import time

    from paidsearchnav.api.token_blacklist import TokenBlacklist

    # Create a fresh blacklist instance for this test
    blacklist = TokenBlacklist()

    # Set cleanup interval to very high so it doesn't auto-cleanup
    blacklist._cleanup_interval = 86400  # 24 hours

    # Add tokens with different expiration times based on current timestamp
    # Use datetime.fromtimestamp to ensure consistency with time.time()
    now_ts = time.time()

    # Add an expired token (1 hour ago)
    expired_time = datetime.fromtimestamp(now_ts - 3600)
    blacklist.blacklist_token("expired_token_test", expired_time)

    # Add a valid token (1 hour from now)
    valid_time = datetime.fromtimestamp(now_ts + 3600)
    blacklist.blacklist_token("valid_token_test", valid_time)

    # Check initial state
    assert blacklist.get_blacklist_size() == 2
    assert blacklist.is_token_blacklisted("expired_token_test")
    assert blacklist.is_token_blacklisted("valid_token_test")

    # Force cleanup
    removed = blacklist.force_cleanup()

    # Should have removed the expired token
    assert removed == 1
    assert blacklist.get_blacklist_size() == 1
    assert not blacklist.is_token_blacklisted("expired_token_test")
    assert blacklist.is_token_blacklisted("valid_token_test")


@pytest.mark.asyncio
async def test_concurrent_token_operations():
    """Test thread safety of blacklist operations."""
    import threading

    from paidsearchnav.api.token_blacklist import TokenBlacklist

    # Create a fresh blacklist instance for this test
    blacklist = TokenBlacklist()
    tokens_added = []
    tokens_lock = threading.Lock()

    def add_tokens():
        for i in range(100):
            token = f"token_{threading.current_thread().name}_{i}"
            blacklist.blacklist_token(token, datetime.utcnow() + timedelta(hours=1))
            with tokens_lock:
                tokens_added.append(token)

    # Run multiple threads
    threads = []
    for i in range(5):
        t = threading.Thread(target=add_tokens, name=f"thread_{i}")
        threads.append(t)
        t.start()

    # Wait for all threads
    for t in threads:
        t.join()

    # Verify all tokens were added
    assert len(tokens_added) == 500
    for token in tokens_added:
        assert blacklist.is_token_blacklisted(token)
