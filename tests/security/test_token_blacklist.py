"""Tests for JWT token blacklist functionality."""

import time
from datetime import datetime, timedelta, timezone

from paidsearchnav.api.token_blacklist import (
    TokenBlacklist,
    blacklist_token,
    get_token_blacklist,
    is_token_blacklisted,
)


class TestTokenBlacklist:
    """Test JWT token blacklist functionality."""

    def setup_method(self):
        """Set up fresh blacklist for each test."""
        # Create a new blacklist instance for each test
        self.blacklist = TokenBlacklist()

    def test_token_blacklisting(self):
        """Test that tokens can be blacklisted and checked."""
        token = "test_token_123"
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

        # Token should not be blacklisted initially
        assert not self.blacklist.is_token_blacklisted(token)

        # Blacklist the token
        self.blacklist.blacklist_token(token, expires_at)

        # Token should now be blacklisted
        assert self.blacklist.is_token_blacklisted(token)

    def test_token_expiration_cleanup(self):
        """Test that expired tokens are cleaned up."""
        token = "expired_token"
        expires_at = datetime.now(timezone.utc) - timedelta(hours=1)  # Already expired

        # Blacklist an expired token
        self.blacklist.blacklist_token(token, expires_at)

        # Force cleanup
        removed_count = self.blacklist.force_cleanup()

        # Should have removed the expired token
        assert removed_count == 1
        assert not self.blacklist.is_token_blacklisted(token)

    def test_multiple_tokens(self):
        """Test blacklisting multiple tokens."""
        tokens = ["token1", "token2", "token3"]
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

        # Blacklist all tokens
        for token in tokens:
            self.blacklist.blacklist_token(token, expires_at)

        # All should be blacklisted
        for token in tokens:
            assert self.blacklist.is_token_blacklisted(token)

        # Blacklist size should be 3
        assert self.blacklist.get_blacklist_size() == 3

    def test_thread_safety(self):
        """Test that blacklist operations are thread-safe."""
        import concurrent.futures

        tokens = [f"token_{i}" for i in range(100)]
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

        def blacklist_token_worker(token):
            self.blacklist.blacklist_token(token, expires_at)
            return self.blacklist.is_token_blacklisted(token)

        # Blacklist tokens concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(blacklist_token_worker, tokens))

        # All operations should succeed
        assert all(results)
        assert self.blacklist.get_blacklist_size() == 100

    def test_convenience_functions(self):
        """Test the global convenience functions."""
        token = "convenience_test_token"
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

        # Use convenience functions
        assert not is_token_blacklisted(token)
        blacklist_token(token, expires_at)
        assert is_token_blacklisted(token)

        # Should affect global instance
        global_blacklist = get_token_blacklist()
        assert global_blacklist.is_token_blacklisted(token)

    def test_automatic_cleanup(self):
        """Test that automatic cleanup works periodically."""
        # This test would be more complex to test the time-based cleanup
        # For now, we test the force cleanup mechanism

        valid_token = "valid_token"
        expired_token = "expired_token"

        valid_expires = datetime.now(timezone.utc) + timedelta(hours=1)
        expired_expires = datetime.now(timezone.utc) - timedelta(hours=1)

        self.blacklist.blacklist_token(valid_token, valid_expires)
        self.blacklist.blacklist_token(expired_token, expired_expires)

        # Both should be in blacklist initially
        assert self.blacklist.get_blacklist_size() == 2

        # Force cleanup
        removed = self.blacklist.force_cleanup()

        # Should remove only expired token
        assert removed == 1
        assert self.blacklist.is_token_blacklisted(valid_token)
        assert not self.blacklist.is_token_blacklisted(expired_token)


class TestTokenBlacklistIntegration:
    """Integration tests for token blacklist with authentication flow."""

    def test_blacklist_integration(self):
        """Test integration with authentication dependencies."""
        # This would require mocking FastAPI dependencies
        # For now, test that the functions exist and work

        token = "integration_test_token"
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)

        # Simulate authentication flow
        assert not is_token_blacklisted(token)

        # Simulate token revocation
        blacklist_token(token, expires_at)

        # Token should now be blacklisted
        assert is_token_blacklisted(token)

        # Simulate cleanup after expiration
        # In real usage, this would happen automatically
        blacklist_instance = get_token_blacklist()

        # Manually expire the token for testing
        blacklist_instance._token_expiry[token] = time.time() - 1
        blacklist_instance.force_cleanup()

        # Token should no longer be blacklisted
        assert not is_token_blacklisted(token)
