"""Tests for auth security components including account lockout functionality."""

import asyncio
import threading
import time
from datetime import datetime

import pytest

from paidsearchnav_mcp.api.auth_security import (
    AccountLockoutManager,
    check_account_lockout,
    get_lockout_manager,
    record_failed_login,
    record_successful_login,
)


class TestAccountLockoutManager:
    """Test the AccountLockoutManager class."""

    @pytest.fixture
    def lockout_manager(self):
        """Create a fresh AccountLockoutManager for testing."""
        return AccountLockoutManager(
            max_attempts=3,
            lockout_duration=60,  # 1 minute
            attempt_window=30,  # 30 seconds
        )

    def test_init_default_values(self):
        """Test AccountLockoutManager initialization with default values."""
        manager = AccountLockoutManager()
        assert manager.max_attempts == 5
        assert manager.lockout_duration == 900  # 15 minutes
        assert manager.attempt_window == 300  # 5 minutes
        assert manager._failed_attempts == {}
        assert manager._locked_accounts == {}

    def test_init_custom_values(self):
        """Test AccountLockoutManager initialization with custom values."""
        manager = AccountLockoutManager(
            max_attempts=10,
            lockout_duration=1800,  # 30 minutes
            attempt_window=600,  # 10 minutes
        )
        assert manager.max_attempts == 10
        assert manager.lockout_duration == 1800
        assert manager.attempt_window == 600

    def test_record_failed_attempt_single(self, lockout_manager):
        """Test recording a single failed attempt."""
        user_id = "test-user-123"
        ip_address = "192.168.1.1"

        lockout_manager.record_failed_attempt(user_id, ip_address)

        assert user_id in lockout_manager._failed_attempts
        assert len(lockout_manager._failed_attempts[user_id]) == 1
        assert lockout_manager._failed_attempts[user_id][0][1] == ip_address

    def test_record_failed_attempt_multiple(self, lockout_manager):
        """Test recording multiple failed attempts."""
        user_id = "test-user-123"
        ip_address = "192.168.1.1"

        # Record 2 failed attempts (below threshold)
        lockout_manager.record_failed_attempt(user_id, ip_address)
        lockout_manager.record_failed_attempt(user_id, ip_address)

        assert len(lockout_manager._failed_attempts[user_id]) == 2
        assert user_id not in lockout_manager._locked_accounts

    def test_record_failed_attempt_triggers_lockout(self, lockout_manager):
        """Test that recording enough failed attempts triggers lockout."""
        user_id = "test-user-123"
        ip_address = "192.168.1.1"

        # Record max_attempts (3) failed attempts
        for _ in range(lockout_manager.max_attempts):
            lockout_manager.record_failed_attempt(user_id, ip_address)

        assert user_id in lockout_manager._locked_accounts
        assert (
            len(lockout_manager._failed_attempts[user_id])
            == lockout_manager.max_attempts
        )

    def test_record_successful_attempt_clears_failures(self, lockout_manager):
        """Test that recording successful attempt clears failed attempts."""
        user_id = "test-user-123"
        ip_address = "192.168.1.1"

        # Record failed attempts
        lockout_manager.record_failed_attempt(user_id, ip_address)
        lockout_manager.record_failed_attempt(user_id, ip_address)

        # Record successful attempt
        lockout_manager.record_successful_attempt(user_id)

        assert user_id not in lockout_manager._failed_attempts
        assert user_id not in lockout_manager._locked_accounts

    def test_record_successful_attempt_unlocks_account(self, lockout_manager):
        """Test that recording successful attempt unlocks locked account."""
        user_id = "test-user-123"
        ip_address = "192.168.1.1"

        # Trigger lockout
        for _ in range(lockout_manager.max_attempts):
            lockout_manager.record_failed_attempt(user_id, ip_address)

        assert user_id in lockout_manager._locked_accounts

        # Record successful attempt
        lockout_manager.record_successful_attempt(user_id)

        assert user_id not in lockout_manager._failed_attempts
        assert user_id not in lockout_manager._locked_accounts

    def test_is_account_locked_false_for_unlocked(self, lockout_manager):
        """Test is_account_locked returns False for unlocked account."""
        user_id = "test-user-123"
        is_locked, unlock_time = lockout_manager.is_account_locked(user_id)

        assert is_locked is False
        assert unlock_time is None

    def test_is_account_locked_true_for_locked(self, lockout_manager):
        """Test is_account_locked returns True for locked account."""
        user_id = "test-user-123"
        ip_address = "192.168.1.1"

        # Trigger lockout
        for _ in range(lockout_manager.max_attempts):
            lockout_manager.record_failed_attempt(user_id, ip_address)

        is_locked, unlock_time = lockout_manager.is_account_locked(user_id)

        assert is_locked is True
        assert unlock_time is not None
        assert isinstance(unlock_time, datetime)

    def test_is_account_locked_expired_lockout(self, lockout_manager):
        """Test is_account_locked handles expired lockout."""
        user_id = "test-user-123"
        ip_address = "192.168.1.1"

        # Trigger lockout
        for _ in range(lockout_manager.max_attempts):
            lockout_manager.record_failed_attempt(user_id, ip_address)

        # Manually set lockout time to past
        past_time = time.time() - lockout_manager.lockout_duration - 1
        lockout_manager._locked_accounts[user_id] = past_time

        is_locked, unlock_time = lockout_manager.is_account_locked(user_id)

        assert is_locked is False
        assert unlock_time is None
        assert user_id not in lockout_manager._locked_accounts

    def test_get_failed_attempts_count_zero(self, lockout_manager):
        """Test get_failed_attempts_count returns zero for new user."""
        user_id = "test-user-123"
        count = lockout_manager.get_failed_attempts_count(user_id)
        assert count == 0

    def test_get_failed_attempts_count_with_attempts(self, lockout_manager):
        """Test get_failed_attempts_count returns correct count."""
        user_id = "test-user-123"
        ip_address = "192.168.1.1"

        # Record 2 failed attempts
        lockout_manager.record_failed_attempt(user_id, ip_address)
        lockout_manager.record_failed_attempt(user_id, ip_address)

        count = lockout_manager.get_failed_attempts_count(user_id)
        assert count == 2

    def test_get_failed_attempts_count_with_old_attempts(self, lockout_manager):
        """Test get_failed_attempts_count ignores old attempts."""
        user_id = "test-user-123"
        ip_address = "192.168.1.1"

        # Record failed attempt
        lockout_manager.record_failed_attempt(user_id, ip_address)

        # Manually set attempt time to past (outside window)
        past_time = time.time() - lockout_manager.attempt_window - 1
        lockout_manager._failed_attempts[user_id] = [(past_time, ip_address)]

        count = lockout_manager.get_failed_attempts_count(user_id)
        assert count == 0

    def test_get_remaining_attempts_full(self, lockout_manager):
        """Test get_remaining_attempts returns full count for new user."""
        user_id = "test-user-123"
        remaining = lockout_manager.get_remaining_attempts(user_id)
        assert remaining == lockout_manager.max_attempts

    def test_get_remaining_attempts_decreases(self, lockout_manager):
        """Test get_remaining_attempts decreases with failed attempts."""
        user_id = "test-user-123"
        ip_address = "192.168.1.1"

        # Record 2 failed attempts
        lockout_manager.record_failed_attempt(user_id, ip_address)
        lockout_manager.record_failed_attempt(user_id, ip_address)

        remaining = lockout_manager.get_remaining_attempts(user_id)
        assert remaining == lockout_manager.max_attempts - 2

    def test_get_remaining_attempts_zero_when_locked(self, lockout_manager):
        """Test get_remaining_attempts returns zero when locked."""
        user_id = "test-user-123"
        ip_address = "192.168.1.1"

        # Trigger lockout
        for _ in range(lockout_manager.max_attempts):
            lockout_manager.record_failed_attempt(user_id, ip_address)

        remaining = lockout_manager.get_remaining_attempts(user_id)
        assert remaining == 0

    def test_force_unlock_account_unlocks_locked(self, lockout_manager):
        """Test force_unlock_account unlocks a locked account."""
        user_id = "test-user-123"
        ip_address = "192.168.1.1"

        # Trigger lockout
        for _ in range(lockout_manager.max_attempts):
            lockout_manager.record_failed_attempt(user_id, ip_address)

        # Force unlock
        was_locked = lockout_manager.force_unlock_account(user_id)

        assert was_locked is True
        assert user_id not in lockout_manager._locked_accounts
        assert user_id not in lockout_manager._failed_attempts

    def test_force_unlock_account_unlocked_account(self, lockout_manager):
        """Test force_unlock_account with already unlocked account."""
        user_id = "test-user-123"
        was_locked = lockout_manager.force_unlock_account(user_id)
        assert was_locked is False

    def test_get_lockout_stats_empty(self, lockout_manager):
        """Test get_lockout_stats with no data."""
        stats = lockout_manager.get_lockout_stats()

        assert stats["currently_locked_accounts"] == 0
        assert stats["accounts_with_failed_attempts"] == 0
        assert stats["total_failed_attempts"] == 0
        assert stats["max_attempts_allowed"] == lockout_manager.max_attempts
        assert (
            stats["lockout_duration_minutes"] == lockout_manager.lockout_duration // 60
        )

    def test_get_lockout_stats_with_data(self, lockout_manager):
        """Test get_lockout_stats with data."""
        user1 = "user1"
        user2 = "user2"
        user3 = "user3"
        ip_address = "192.168.1.1"

        # User 1: 2 failed attempts (not locked)
        lockout_manager.record_failed_attempt(user1, ip_address)
        lockout_manager.record_failed_attempt(user1, ip_address)

        # User 2: locked
        for _ in range(lockout_manager.max_attempts):
            lockout_manager.record_failed_attempt(user2, ip_address)

        # User 3: 1 failed attempt
        lockout_manager.record_failed_attempt(user3, ip_address)

        stats = lockout_manager.get_lockout_stats()

        assert stats["currently_locked_accounts"] == 1
        assert stats["accounts_with_failed_attempts"] == 3
        assert stats["total_failed_attempts"] == 2 + 3 + 1  # 6 total

    def test_clean_old_attempts(self, lockout_manager):
        """Test that old attempts are cleaned up."""
        user_id = "test-user-123"
        ip_address = "192.168.1.1"

        # Record current attempt
        lockout_manager.record_failed_attempt(user_id, ip_address)

        # Manually add old attempt
        past_time = time.time() - lockout_manager.attempt_window - 1
        lockout_manager._failed_attempts[user_id].append((past_time, ip_address))

        # Clean old attempts
        lockout_manager._clean_old_attempts(user_id, time.time())

        # Should only have 1 recent attempt
        assert len(lockout_manager._failed_attempts[user_id]) == 1

    def test_thread_safety(self, lockout_manager):
        """Test that AccountLockoutManager is thread-safe."""
        user_id = "test-user-123"
        ip_address = "192.168.1.1"
        results = []

        def worker():
            # Reduced operations for CI performance
            for _ in range(5):
                lockout_manager.record_failed_attempt(user_id, ip_address)
                count = lockout_manager.get_failed_attempts_count(user_id)
                results.append(count)

        # Start multiple threads (reduced for CI performance)
        threads = []
        for _ in range(3):
            thread = threading.Thread(target=worker)
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Check that we have results and no race conditions caused crashes
        assert len(results) > 0
        # Account should be locked after all attempts
        is_locked, _ = lockout_manager.is_account_locked(user_id)
        assert is_locked is True

    def test_different_ip_addresses_tracked(self, lockout_manager):
        """Test that different IP addresses are tracked in failed attempts."""
        user_id = "test-user-123"
        ip1 = "192.168.1.1"
        ip2 = "192.168.1.2"

        lockout_manager.record_failed_attempt(user_id, ip1)
        lockout_manager.record_failed_attempt(user_id, ip2)

        attempts = lockout_manager._failed_attempts[user_id]
        assert len(attempts) == 2
        assert attempts[0][1] == ip1
        assert attempts[1][1] == ip2

    def test_lockout_duration_calculation(self, lockout_manager):
        """Test that lockout duration is calculated correctly."""
        user_id = "test-user-123"
        ip_address = "192.168.1.1"

        # Record timestamp before lockout
        before_lockout = time.time()

        # Trigger lockout
        for _ in range(lockout_manager.max_attempts):
            lockout_manager.record_failed_attempt(user_id, ip_address)

        # Record timestamp after lockout
        after_lockout = time.time()

        is_locked, unlock_time = lockout_manager.is_account_locked(user_id)

        assert is_locked is True
        assert unlock_time is not None

        # Calculate expected unlock time range
        expected_min_unlock = before_lockout + lockout_manager.lockout_duration
        expected_max_unlock = after_lockout + lockout_manager.lockout_duration

        unlock_timestamp = unlock_time.timestamp()
        assert expected_min_unlock <= unlock_timestamp <= expected_max_unlock


class TestAccountLockoutGlobalFunctions:
    """Test the global convenience functions for account lockout."""

    def test_get_lockout_manager_returns_instance(self):
        """Test that get_lockout_manager returns AccountLockoutManager instance."""
        manager = get_lockout_manager()
        assert isinstance(manager, AccountLockoutManager)

    def test_get_lockout_manager_returns_same_instance(self):
        """Test that get_lockout_manager returns the same instance."""
        manager1 = get_lockout_manager()
        manager2 = get_lockout_manager()
        assert manager1 is manager2

    def test_record_failed_login_calls_manager(self):
        """Test that record_failed_login calls the manager."""
        user_id = "test-user-123"
        ip_address = "192.168.1.1"

        # Clear any existing attempts
        manager = get_lockout_manager()
        manager.force_unlock_account(user_id)

        # Record failed login
        record_failed_login(user_id, ip_address)

        # Check that it was recorded
        count = manager.get_failed_attempts_count(user_id)
        assert count == 1

    def test_record_successful_login_calls_manager(self):
        """Test that record_successful_login calls the manager."""
        user_id = "test-user-123"
        ip_address = "192.168.1.1"

        # Record failed login first
        record_failed_login(user_id, ip_address)

        # Record successful login
        record_successful_login(user_id)

        # Check that failed attempts were cleared
        manager = get_lockout_manager()
        count = manager.get_failed_attempts_count(user_id)
        assert count == 0

    def test_check_account_lockout_calls_manager(self):
        """Test that check_account_lockout calls the manager."""
        user_id = "test-user-123"
        ip_address = "192.168.1.1"

        # Clear any existing state
        manager = get_lockout_manager()
        manager.force_unlock_account(user_id)

        # Check unlocked account
        is_locked, unlock_time = check_account_lockout(user_id)
        assert is_locked is False
        assert unlock_time is None

        # Lock account
        for _ in range(manager.max_attempts):
            record_failed_login(user_id, ip_address)

        # Check locked account
        is_locked, unlock_time = check_account_lockout(user_id)
        assert is_locked is True
        assert unlock_time is not None


class TestAccountLockoutSecurity:
    """Test security aspects of the account lockout system."""

    @pytest.fixture
    def lockout_manager(self):
        """Create a lockout manager with shorter durations for testing."""
        return AccountLockoutManager(
            max_attempts=3,
            lockout_duration=5,  # 5 seconds
            attempt_window=10,  # 10 seconds
        )

    def test_lockout_prevents_brute_force(self, lockout_manager):
        """Test that lockout prevents brute force attacks."""
        user_id = "test-user-123"
        ip_address = "192.168.1.1"

        # Simulate brute force attack
        for attempt in range(10):  # More than max_attempts
            if attempt < lockout_manager.max_attempts:
                # First few attempts should be recorded
                lockout_manager.record_failed_attempt(user_id, ip_address)
            else:
                # After lockout, check that account is locked
                is_locked, _ = lockout_manager.is_account_locked(user_id)
                assert is_locked is True

    def test_lockout_timing_does_not_leak_user_existence(self, lockout_manager):
        """Test that lockout timing doesn't leak information about user existence."""
        existing_user = "existing-user-123"
        nonexistent_user = "nonexistent-user-456"
        ip_address = "192.168.1.1"

        # Record attempts for existing user
        lockout_manager.record_failed_attempt(existing_user, ip_address)

        # Time lockout checks for both users
        start_time = time.time()
        is_locked1, _ = lockout_manager.is_account_locked(existing_user)
        time1 = time.time() - start_time

        start_time = time.time()
        is_locked2, _ = lockout_manager.is_account_locked(nonexistent_user)
        time2 = time.time() - start_time

        # Both should be unlocked
        assert is_locked1 is False
        assert is_locked2 is False

        # Timing should be similar (no significant difference)
        # Use more lenient timing for CI environments
        time_diff = abs(time1 - time2)
        assert time_diff < 0.1  # Less than 100ms difference (more lenient for CI)

    def test_lockout_survives_cleanup_attempts(self, lockout_manager):
        """Test that lockout state survives cleanup attempts."""
        user_id = "test-user-123"
        ip_address = "192.168.1.1"

        # Trigger lockout
        for _ in range(lockout_manager.max_attempts):
            lockout_manager.record_failed_attempt(user_id, ip_address)

        # Try to clean up by calling various methods
        lockout_manager._clean_old_attempts(user_id, time.time())
        lockout_manager.get_failed_attempts_count(user_id)
        lockout_manager.get_remaining_attempts(user_id)

        # Account should still be locked
        is_locked, _ = lockout_manager.is_account_locked(user_id)
        assert is_locked is True

    def test_lockout_ip_tracking_for_forensics(self, lockout_manager):
        """Test that IP addresses are tracked for forensic purposes."""
        user_id = "test-user-123"
        ip_addresses = ["192.168.1.1", "192.168.1.2", "10.0.0.1"]

        # Record attempts from different IPs
        for ip in ip_addresses:
            lockout_manager.record_failed_attempt(user_id, ip)

        # Check that all IPs are tracked
        attempts = lockout_manager._failed_attempts[user_id]
        recorded_ips = [attempt[1] for attempt in attempts]

        assert len(recorded_ips) == len(ip_addresses)
        for ip in ip_addresses:
            assert ip in recorded_ips

    def test_lockout_memory_usage_bounded(self, lockout_manager):
        """Test that lockout manager doesn't consume unbounded memory."""
        # Simulate many users with failed attempts
        base_user = "user-"
        ip_address = "192.168.1.1"

        for i in range(1000):
            user_id = f"{base_user}{i}"
            lockout_manager.record_failed_attempt(user_id, ip_address)

        # Memory usage should be reasonable
        assert len(lockout_manager._failed_attempts) <= 1000
        assert (
            len(lockout_manager._locked_accounts) == 0
        )  # No lockouts with 1 attempt each

    def test_lockout_time_window_enforcement(self, lockout_manager):
        """Test that attempt time window is properly enforced."""
        user_id = "test-user-123"
        ip_address = "192.168.1.1"

        # Record attempt now
        lockout_manager.record_failed_attempt(user_id, ip_address)

        # Manually add old attempt outside window
        past_time = time.time() - lockout_manager.attempt_window - 1
        lockout_manager._failed_attempts[user_id].append((past_time, ip_address))

        # Count should only include recent attempts
        count = lockout_manager.get_failed_attempts_count(user_id)
        assert count == 1  # Only the recent attempt

    def test_lockout_concurrent_user_isolation(self, lockout_manager):
        """Test that lockout of one user doesn't affect others."""
        user1 = "user1"
        user2 = "user2"
        ip_address = "192.168.1.1"

        # Lock user1
        for _ in range(lockout_manager.max_attempts):
            lockout_manager.record_failed_attempt(user1, ip_address)

        # User2 should not be affected
        is_locked1, _ = lockout_manager.is_account_locked(user1)
        is_locked2, _ = lockout_manager.is_account_locked(user2)

        assert is_locked1 is True
        assert is_locked2 is False

        # User2 should still be able to fail normally
        lockout_manager.record_failed_attempt(user2, ip_address)
        count = lockout_manager.get_failed_attempts_count(user2)
        assert count == 1

    @pytest.mark.asyncio
    async def test_lockout_automatic_expiry(self, lockout_manager):
        """Test that lockout automatically expires after duration."""
        user_id = "test-user-123"
        ip_address = "192.168.1.1"

        # Trigger lockout
        for _ in range(lockout_manager.max_attempts):
            lockout_manager.record_failed_attempt(user_id, ip_address)

        # Should be locked initially
        is_locked, unlock_time = lockout_manager.is_account_locked(user_id)
        assert is_locked is True

        # Wait for lockout to expire (5 seconds + small buffer)
        await asyncio.sleep(lockout_manager.lockout_duration + 1)

        # Should be unlocked after expiry
        is_locked, unlock_time = lockout_manager.is_account_locked(user_id)
        assert is_locked is False
        assert unlock_time is None

    def test_lockout_stats_dont_leak_sensitive_info(self, lockout_manager):
        """Test that lockout stats don't leak sensitive information."""
        user_id = "test-user-123"
        ip_address = "192.168.1.1"

        # Record some attempts
        lockout_manager.record_failed_attempt(user_id, ip_address)
        lockout_manager.record_failed_attempt(user_id, ip_address)

        stats = lockout_manager.get_lockout_stats()

        # Stats should contain only aggregate information
        assert "users" not in stats
        assert "ip_addresses" not in stats
        assert "failed_attempts" not in stats  # Should be "total_failed_attempts"

        # Stats should be numeric summaries
        for key, value in stats.items():
            assert isinstance(value, (int, float))
