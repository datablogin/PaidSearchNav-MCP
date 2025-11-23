"""Tests for account lockout security mechanism."""

import time
from datetime import datetime, timezone

from paidsearchnav_mcp.api.auth_security import (
    AccountLockoutManager,
    check_account_lockout,
    get_lockout_manager,
    record_failed_login,
    record_successful_login,
)


class TestAccountLockout:
    """Test account lockout functionality."""

    def setup_method(self):
        """Set up fresh lockout manager for each test."""
        # Create a new lockout manager for each test
        self.lockout_manager = AccountLockoutManager(
            max_attempts=5,
            lockout_duration=900,  # 15 minutes
            attempt_window=300,  # 5 minutes
        )

    def test_failed_login_tracking(self):
        """Test that failed login attempts are tracked."""
        user_id = "test_user"
        ip = "192.168.1.1"

        # Initially no failed attempts
        assert self.lockout_manager.get_failed_attempts_count(user_id) == 0
        assert self.lockout_manager.get_remaining_attempts(user_id) == 5

        # Record failed attempt
        self.lockout_manager.record_failed_attempt(user_id, ip)

        # Should have 1 failed attempt
        assert self.lockout_manager.get_failed_attempts_count(user_id) == 1
        assert self.lockout_manager.get_remaining_attempts(user_id) == 4

    def test_account_lockout_after_max_attempts(self):
        """Test that account gets locked after max failed attempts."""
        user_id = "test_user"
        ip = "192.168.1.1"

        # Record 4 failed attempts (below threshold)
        for _ in range(4):
            self.lockout_manager.record_failed_attempt(user_id, ip)

        # Should not be locked yet
        is_locked, _ = self.lockout_manager.is_account_locked(user_id)
        assert not is_locked

        # Record 5th failed attempt (reaches threshold)
        self.lockout_manager.record_failed_attempt(user_id, ip)

        # Should now be locked
        is_locked, unlock_time = self.lockout_manager.is_account_locked(user_id)
        assert is_locked
        assert unlock_time is not None
        assert unlock_time > datetime.now(timezone.utc)

    def test_successful_login_clears_attempts(self):
        """Test that successful login clears failed attempts."""
        user_id = "test_user"
        ip = "192.168.1.1"

        # Record some failed attempts
        for _ in range(3):
            self.lockout_manager.record_failed_attempt(user_id, ip)

        assert self.lockout_manager.get_failed_attempts_count(user_id) == 3

        # Record successful login
        self.lockout_manager.record_successful_attempt(user_id)

        # Failed attempts should be cleared
        assert self.lockout_manager.get_failed_attempts_count(user_id) == 0
        assert self.lockout_manager.get_remaining_attempts(user_id) == 5

    def test_successful_login_unlocks_account(self):
        """Test that successful login unlocks a locked account."""
        user_id = "test_user"
        ip = "192.168.1.1"

        # Lock the account
        for _ in range(5):
            self.lockout_manager.record_failed_attempt(user_id, ip)

        is_locked, _ = self.lockout_manager.is_account_locked(user_id)
        assert is_locked

        # Successful login should unlock
        self.lockout_manager.record_successful_attempt(user_id)

        is_locked, _ = self.lockout_manager.is_account_locked(user_id)
        assert not is_locked

    def test_lockout_expiration(self):
        """Test that lockouts expire after the configured duration."""
        user_id = "test_user"
        ip = "192.168.1.1"

        # Create lockout manager with short duration for testing
        short_lockout_manager = AccountLockoutManager(
            max_attempts=2,
            lockout_duration=1,  # 1 second
            attempt_window=60,
        )

        # Lock the account
        for _ in range(2):
            short_lockout_manager.record_failed_attempt(user_id, ip)

        is_locked, _ = short_lockout_manager.is_account_locked(user_id)
        assert is_locked

        # Wait for lockout to expire with a bit more buffer for CI
        time.sleep(1.5)

        # Should no longer be locked
        is_locked, _ = short_lockout_manager.is_account_locked(user_id)
        assert not is_locked

    def test_attempt_window_cleanup(self):
        """Test that old attempts outside the window are cleaned up."""
        user_id = "test_user"
        ip = "192.168.1.1"

        # Create manager with short window for testing
        short_window_manager = AccountLockoutManager(
            max_attempts=5,
            lockout_duration=900,
            attempt_window=1,  # 1 second window
        )

        # Record an attempt
        short_window_manager.record_failed_attempt(user_id, ip)
        assert short_window_manager.get_failed_attempts_count(user_id) == 1

        # Wait for window to expire with buffer for CI
        time.sleep(1.5)

        # Should be cleaned up when checking count
        assert short_window_manager.get_failed_attempts_count(user_id) == 0

    def test_force_unlock(self):
        """Test manual account unlocking (admin function)."""
        user_id = "test_user"
        ip = "192.168.1.1"

        # Lock the account
        for _ in range(5):
            self.lockout_manager.record_failed_attempt(user_id, ip)

        is_locked, _ = self.lockout_manager.is_account_locked(user_id)
        assert is_locked

        # Force unlock
        was_locked = self.lockout_manager.force_unlock_account(user_id)
        assert was_locked

        # Should no longer be locked
        is_locked, _ = self.lockout_manager.is_account_locked(user_id)
        assert not is_locked

        # Force unlocking non-locked account should return False
        was_locked = self.lockout_manager.force_unlock_account(user_id)
        assert not was_locked

    def test_lockout_statistics(self):
        """Test lockout statistics for monitoring."""
        user1 = "user1"
        user2 = "user2"
        ip = "192.168.1.1"

        # Lock one account
        for _ in range(5):
            self.lockout_manager.record_failed_attempt(user1, ip)

        # Add failed attempts for another user (not locked)
        for _ in range(3):
            self.lockout_manager.record_failed_attempt(user2, ip)

        stats = self.lockout_manager.get_lockout_stats()

        assert stats["currently_locked_accounts"] == 1
        assert (
            stats["accounts_with_failed_attempts"] == 2
        )  # user1 locked, user2 has attempts
        assert stats["total_failed_attempts"] == 8  # 5 + 3
        assert stats["max_attempts_allowed"] == 5
        assert stats["lockout_duration_minutes"] == 15

    def test_ip_tracking(self):
        """Test that IP addresses are tracked with attempts."""
        user_id = "test_user"

        # Record attempts from different IPs
        self.lockout_manager.record_failed_attempt(user_id, "192.168.1.1")
        self.lockout_manager.record_failed_attempt(user_id, "192.168.1.2")
        self.lockout_manager.record_failed_attempt(user_id, "10.0.0.1")

        # Should still track total attempts regardless of IP
        assert self.lockout_manager.get_failed_attempts_count(user_id) == 3

        # Internal structure should track IPs (this is implementation detail)
        attempts = self.lockout_manager._failed_attempts.get(user_id, [])
        ips = [attempt[1] for attempt in attempts]
        assert "192.168.1.1" in ips
        assert "192.168.1.2" in ips
        assert "10.0.0.1" in ips


class TestAccountLockoutIntegration:
    """Integration tests for account lockout with convenience functions."""

    def test_convenience_functions(self):
        """Test the global convenience functions."""
        user_id = "integration_test_user"
        ip = "192.168.1.100"

        # Use convenience functions
        is_locked, _ = check_account_lockout(user_id)
        assert not is_locked

        # Record failed attempts
        for _ in range(5):
            record_failed_login(user_id, ip)

        # Should be locked
        is_locked, unlock_time = check_account_lockout(user_id)
        assert is_locked
        assert unlock_time is not None

        # Successful login should unlock
        record_successful_login(user_id)

        is_locked, _ = check_account_lockout(user_id)
        assert not is_locked

    def test_global_instance_consistency(self):
        """Test that all convenience functions use the same global instance."""
        user_id = "global_test_user"
        ip = "192.168.1.200"

        # Get the global manager
        manager = get_lockout_manager()

        # Record attempt using convenience function
        record_failed_login(user_id, ip)

        # Should be reflected in global manager
        assert manager.get_failed_attempts_count(user_id) == 1

        # And in convenience function
        is_locked, _ = check_account_lockout(user_id)
        assert not is_locked  # Only 1 attempt, not locked yet
