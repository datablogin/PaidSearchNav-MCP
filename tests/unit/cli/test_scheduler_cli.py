"""Tests for scheduler CLI commands."""

import os
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest
from click.testing import CliRunner

from paidsearchnav.scheduler.cli import (
    parse_date_flexible,
    sanitize_error_message,
    scheduler,
)


@pytest.fixture
def cli_runner():
    """Create CLI runner for testing."""
    return CliRunner()


@pytest.fixture
def mock_google_ads_env():
    """Mock Google Ads environment variables for tests."""
    env_vars = {
        "PSN_GOOGLE_ADS_DEVELOPER_TOKEN": "fake-12345-developer-token",
        "PSN_GOOGLE_ADS_CLIENT_ID": "fake-67890-client-id",
        "PSN_GOOGLE_ADS_CLIENT_SECRET": "fake-abcdef-client-secret",
        "PSN_GOOGLE_ADS_REFRESH_TOKEN": "fake-ghijkl-refresh-token",
        "PSN_GOOGLE_ADS_LOGIN_CUSTOMER_ID": "1234567890",
        "PSN_STORAGE_CONNECTION_STRING": "sqlite:///:memory:",
    }
    return env_vars


@pytest.fixture
def mock_scheduler_api():
    """Create mock SchedulerAPI for testing."""
    mock_api = AsyncMock()
    # Set default return values
    mock_api.trigger_audit.return_value = {
        "execution_id": "exec_123",
        "job_id": "job_123",
        "status": "pending",
    }
    mock_api.schedule_audit.return_value = {
        "job_id": "scheduled_audit_1234567890",
        "customer_id": "1234567890",
        "schedule": "0 0 1 */3 *",
        "status": "scheduled",
    }
    mock_api.cancel_job.return_value = {
        "job_id": "job_123",
        "success": True,
        "status": "cancelled",
    }
    return mock_api


@pytest.fixture
def mock_job_history():
    """Create mock job history data."""
    mock_result = [
        {
            "execution_id": "exec_123",
            "job_id": "job_123",
            "customer_id": "1234567890",
            "status": "completed",
            "started_at": datetime.now().isoformat(),
            "completed_at": datetime.now().isoformat(),
        }
    ]
    return mock_result


class TestSanitizeErrorMessage:
    """Test error message sanitization functionality."""

    def test_sanitize_password_in_error_message(self):
        """Test that password is redacted from error messages."""
        error = Exception("Connection failed: password=secret123")
        result = sanitize_error_message(error)
        assert "password=[REDACTED]" in result
        assert "secret123" not in result

    def test_sanitize_api_key_in_error_message(self):
        """Test that API key is redacted from error messages."""
        error = Exception("Authentication failed: api_key=abc123def")
        result = sanitize_error_message(error)
        assert "api_key=[REDACTED]" in result
        assert "abc123def" not in result

    def test_sanitize_token_in_error_message(self):
        """Test that token is redacted from error messages."""
        error = Exception("Invalid token: bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9")
        result = sanitize_error_message(error)
        assert "bearer [REDACTED]" in result
        assert "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9" not in result

    def test_sanitize_multiple_secrets_in_error_message(self):
        """Test that multiple secrets are redacted from error messages."""
        error = Exception("Auth failed: password=secret token=abc123 key=xyz789")
        result = sanitize_error_message(error)
        assert "password=[REDACTED]" in result
        assert "token=[REDACTED]" in result
        assert "key=[REDACTED]" in result
        assert "secret" not in result
        assert "abc123" not in result
        assert "xyz789" not in result

    def test_sanitize_preserves_safe_content(self):
        """Test that safe content is preserved in error messages."""
        error = Exception("Connection timeout: Unable to reach host example.com")
        result = sanitize_error_message(error)
        assert "Connection timeout: Unable to reach host example.com" == result


class TestSchedulerCLI:
    """Test scheduler CLI functionality."""

    def test_scheduler_help(self, cli_runner):
        """Test scheduler help command."""
        result = cli_runner.invoke(scheduler, ["--help"])

        assert result.exit_code == 0
        assert "Manage audit scheduling" in result.output
        assert "run" in result.output
        assert "schedule" in result.output
        assert "status" in result.output
        assert "history" in result.output
        assert "cancel" in result.output
        assert "start" in result.output

    def test_run_help(self, cli_runner):
        """Test run command help."""
        result = cli_runner.invoke(scheduler, ["run", "--help"])

        assert result.exit_code == 0
        assert "Trigger an audit run immediately" in result.output
        assert "--customer-id" in result.output
        assert "--start-date" in result.output
        assert "--end-date" in result.output
        assert "--analyzers" in result.output

    def test_schedule_help(self, cli_runner):
        """Test schedule command help."""
        result = cli_runner.invoke(scheduler, ["schedule", "--help"])

        assert result.exit_code == 0
        assert "Schedule recurring audits" in result.output
        assert "--customer-id" in result.output
        assert "--schedule" in result.output
        assert "--analyzers" in result.output
        assert "--disabled" in result.output

    def test_status_help(self, cli_runner):
        """Test status command help."""
        result = cli_runner.invoke(scheduler, ["status", "--help"])

        assert result.exit_code == 0
        assert "Get job status" in result.output
        assert "JOB_ID" in result.output

    def test_history_help(self, cli_runner):
        """Test history command help."""
        result = cli_runner.invoke(scheduler, ["history", "--help"])

        assert result.exit_code == 0
        assert "Get job history" in result.output
        assert "--customer-id" in result.output
        assert "--job-type" in result.output
        assert "--status" in result.output
        assert "--page" in result.output
        assert "--page-size" in result.output

    def test_cancel_help(self, cli_runner):
        """Test cancel command help."""
        result = cli_runner.invoke(scheduler, ["cancel", "--help"])

        assert result.exit_code == 0
        assert "Cancel a scheduled job" in result.output
        assert "JOB_ID" in result.output

    def test_start_help(self, cli_runner):
        """Test start command help."""
        result = cli_runner.invoke(scheduler, ["start", "--help"])

        assert result.exit_code == 0
        assert "Start the scheduler service" in result.output

    def test_run_command_basic_success(self, cli_runner, mock_google_ads_env):
        """Test successful run command execution."""
        with patch.dict(os.environ, mock_google_ads_env):
            with patch("paidsearchnav.scheduler.cli.SchedulerAPI") as mock_api_class:
                # Setup mock
                mock_api = AsyncMock()
                mock_api.trigger_audit.return_value = {
                    "execution_id": "exec_123",
                    "job_id": "job_123",
                    "status": "pending",
                }
                mock_api_class.return_value = mock_api

                # Run command
                result = cli_runner.invoke(
                    scheduler, ["run", "--customer-id", "1234567890"]
                )

                # Verify
                assert result.exit_code == 0
                assert "Started audit: exec_123" in result.output
                assert "Status: pending" in result.output

    def test_run_command_with_analyzers(self, cli_runner, mock_google_ads_env):
        """Test run command with specific analyzers."""
        with patch.dict(os.environ, mock_google_ads_env):
            with patch("paidsearchnav.scheduler.cli.SchedulerAPI") as mock_api_class:
                # Setup mock
                mock_api = AsyncMock()
                mock_api.trigger_audit.return_value = {
                    "execution_id": "exec_123",
                    "job_id": "job_123",
                    "status": "pending",
                }
                mock_api_class.return_value = mock_api

                # Run command
                result = cli_runner.invoke(
                    scheduler,
                    [
                        "run",
                        "--customer-id",
                        "1234567890",
                        "--analyzers",
                        "keyword_match",
                        "--analyzers",
                        "search_terms",
                    ],
                )

                # Verify
                assert result.exit_code == 0
                assert "Started audit: exec_123" in result.output

    def test_run_command_error(self, cli_runner, mock_google_ads_env):
        """Test run command error handling."""
        with patch.dict(os.environ, mock_google_ads_env):
            with patch("paidsearchnav.scheduler.cli.SchedulerAPI") as mock_api_class:
                # Setup mock to raise error
                mock_api = AsyncMock()
                mock_api.trigger_audit.side_effect = Exception("API error")
                mock_api_class.return_value = mock_api

                # Run command
                result = cli_runner.invoke(
                    scheduler, ["run", "--customer-id", "1234567890"]
                )

                # Verify - the CLI now handles exceptions gracefully
                assert result.exit_code == 1
                assert (
                    "❌ Failed to trigger audit: An unexpected error occurred"
                    in result.output
                )

    def test_run_command_invalid_date_format(self, cli_runner):
        """Test run command with invalid date format."""
        result = cli_runner.invoke(
            scheduler,
            [
                "run",
                "--customer-id",
                "1234567890",
                "--start-date",
                "invalid-date",
            ],
        )

        # The CLI now handles ValueError gracefully
        assert result.exit_code == 1
        assert "❌ Invalid date format:" in result.output

    def test_run_command_timeout_error(self, cli_runner, mock_google_ads_env):
        """Test run command timeout error handling."""
        with patch.dict(os.environ, mock_google_ads_env):
            with patch("paidsearchnav.scheduler.cli.SchedulerAPI") as mock_api_class:
                # Setup mock to raise timeout error
                mock_api = AsyncMock()
                mock_api.trigger_audit.side_effect = TimeoutError("Request timed out")
                mock_api_class.return_value = mock_api

                # Run command
                result = cli_runner.invoke(
                    scheduler, ["run", "--customer-id", "1234567890"]
                )

                # Verify timeout error handling
                assert result.exit_code == 1
                assert "❌ Request timed out:" in result.output
                assert "longer timeout" in result.output

    def test_run_command_permission_error(self, cli_runner, mock_google_ads_env):
        """Test run command permission error handling."""
        with patch.dict(os.environ, mock_google_ads_env):
            with patch("paidsearchnav.scheduler.cli.SchedulerAPI") as mock_api_class:
                # Setup mock to raise permission error
                mock_api = AsyncMock()
                mock_api.trigger_audit.side_effect = PermissionError("Access denied")
                mock_api_class.return_value = mock_api

                # Run command
                result = cli_runner.invoke(
                    scheduler, ["run", "--customer-id", "1234567890"]
                )

                # Verify permission error handling
                assert result.exit_code == 1
                assert "❌ Permission denied:" in result.output
                assert "file permissions" in result.output

    def test_run_command_file_not_found_error(self, cli_runner, mock_google_ads_env):
        """Test run command file not found error handling."""
        with patch.dict(os.environ, mock_google_ads_env):
            with patch("paidsearchnav.scheduler.cli.SchedulerAPI") as mock_api_class:
                # Setup mock to raise file not found error
                mock_api = AsyncMock()
                mock_api.trigger_audit.side_effect = FileNotFoundError(
                    "Config file not found"
                )
                mock_api_class.return_value = mock_api

                # Run command
                result = cli_runner.invoke(
                    scheduler, ["run", "--customer-id", "1234567890"]
                )

                # Verify file not found error handling
                assert result.exit_code == 1
                assert "❌ Configuration file not found:" in result.output
                assert "configuration file path" in result.output

    def test_run_command_end_date_before_start_date(
        self, cli_runner, mock_google_ads_env
    ):
        """Test run command with end date before start date."""
        with patch.dict(os.environ, mock_google_ads_env):
            with patch("paidsearchnav.scheduler.cli.SchedulerAPI") as mock_api_class:
                # Setup mock
                mock_api = AsyncMock()
                mock_api.trigger_audit.return_value = {
                    "execution_id": "exec_123",
                    "job_id": "job_123",
                    "status": "pending",
                }
                mock_api_class.return_value = mock_api

                # Run command
                result = cli_runner.invoke(
                    scheduler,
                    [
                        "run",
                        "--customer-id",
                        "1234567890",
                        "--start-date",
                        "2025-06-01",
                        "--end-date",
                        "2025-01-01",
                    ],
                )

                # The API should be called regardless - validation happens server-side
                assert result.exit_code == 0
                mock_api.trigger_audit.assert_called_once()

    def test_run_command_connection_error(self, cli_runner, mock_google_ads_env):
        """Test run command connection error handling."""
        with patch.dict(os.environ, mock_google_ads_env):
            with patch("paidsearchnav.scheduler.cli.SchedulerAPI") as mock_api_class:
                # Setup mock to raise connection error
                mock_api = AsyncMock()
                mock_api.trigger_audit.side_effect = ConnectionError(
                    "Network unreachable"
                )
                mock_api_class.return_value = mock_api

                # Run command
                result = cli_runner.invoke(
                    scheduler, ["run", "--customer-id", "1234567890"]
                )

                # Verify connection error handling
                assert result.exit_code == 1
                assert "❌ Connection failed:" in result.output
                assert "network connection" in result.output


class TestSchedulerStatusCommand:
    """Test scheduler status command functionality."""

    def test_status_command_success(self, cli_runner, mock_google_ads_env):
        """Test successful status command execution."""
        with patch.dict(os.environ, mock_google_ads_env):
            with patch("paidsearchnav.scheduler.cli.SchedulerAPI") as mock_api_class:
                # Setup mock
                mock_api = AsyncMock()
                mock_job_status = Mock()
                mock_job_status.job_id = "job_123"
                mock_job_status.status = "completed"
                mock_job_status.started_at = datetime.now().isoformat()
                mock_job_status.completed_at = datetime.now().isoformat()
                mock_job_status.error = None
                mock_job_status.result = {"success": True}
                mock_api.get_job_status.return_value = mock_job_status
                mock_api_class.return_value = mock_api

                # Run command
                result = cli_runner.invoke(scheduler, ["status", "job_123"])

                # Verify
                assert result.exit_code == 0
                assert "Job ID: job_123" in result.output
                assert "Status: completed" in result.output
                assert "Started:" in result.output
                assert "Completed:" in result.output

    def test_status_command_not_found(self, cli_runner, mock_google_ads_env):
        """Test status command when job not found."""
        with patch.dict(os.environ, mock_google_ads_env):
            with patch("paidsearchnav.scheduler.cli.SchedulerAPI") as mock_api_class:
                # Setup mock
                mock_api = AsyncMock()
                mock_api.get_job_status.side_effect = ValueError("Job not found")
                mock_api_class.return_value = mock_api

                # Run command
                result = cli_runner.invoke(scheduler, ["status", "job_999"])

                # Verify
                assert result.exit_code == 1
                assert "❌ Invalid job ID: Job not found" in result.output

    def test_status_command_connection_error(self, cli_runner, mock_google_ads_env):
        """Test status command connection error handling."""
        with patch.dict(os.environ, mock_google_ads_env):
            with patch("paidsearchnav.scheduler.cli.SchedulerAPI") as mock_api_class:
                # Setup mock to raise connection error
                mock_api = AsyncMock()
                mock_api.get_job_status.side_effect = ConnectionError("Network timeout")
                mock_api_class.return_value = mock_api

                # Run command
                result = cli_runner.invoke(scheduler, ["status", "job_123"])

                # Verify
                assert result.exit_code == 1
                assert "❌ Connection failed:" in result.output
                assert "network connection" in result.output


class TestSchedulerHistoryCommand:
    """Test scheduler history command functionality."""

    def test_history_command_success(self, cli_runner, mock_google_ads_env):
        """Test successful history command execution."""
        with patch.dict(os.environ, mock_google_ads_env):
            with patch("paidsearchnav.scheduler.cli.SchedulerAPI") as mock_api_class:
                # Setup mock
                mock_api = AsyncMock()
                mock_api.get_job_history.return_value = [
                    {
                        "execution_id": "exec_123",
                        "job_id": "job_123",
                        "customer_id": "1234567890",
                        "status": "completed",
                        "started_at": datetime.now().isoformat(),
                        "completed_at": datetime.now().isoformat(),
                    }
                ]
                mock_api_class.return_value = mock_api

                # Run command
                result = cli_runner.invoke(scheduler, ["history"])

                # Verify
                assert result.exit_code == 0
                assert "Showing 1 executions:" in result.output
                assert "Execution ID: exec_123" in result.output
                assert "Job: job_123" in result.output
                assert "Customer: 1234567890" in result.output
                assert "Status: completed" in result.output

    def test_history_command_empty_results(self, cli_runner, mock_google_ads_env):
        """Test history command with no results."""
        with patch.dict(os.environ, mock_google_ads_env):
            with patch("paidsearchnav.scheduler.cli.SchedulerAPI") as mock_api_class:
                # Setup mock
                mock_api = AsyncMock()
                mock_api.get_job_history.return_value = []
                mock_api_class.return_value = mock_api

                # Run command
                result = cli_runner.invoke(scheduler, ["history"])

                # Verify
                assert result.exit_code == 0
                assert "No execution history found." in result.output

    def test_history_command_with_filters(self, cli_runner, mock_google_ads_env):
        """Test history command with filters."""
        with patch.dict(os.environ, mock_google_ads_env):
            with patch("paidsearchnav.scheduler.cli.SchedulerAPI") as mock_api_class:
                # Setup mock
                mock_api = AsyncMock()
                mock_api.get_job_history.return_value = []
                mock_api_class.return_value = mock_api

                # Run command
                result = cli_runner.invoke(
                    scheduler,
                    ["history", "--customer-id", "1234567890", "--status", "completed"],
                )

                # Verify
                assert result.exit_code == 0
                mock_api.get_job_history.assert_called_once_with(
                    customer_id="1234567890",
                    job_type=None,
                    status="completed",
                    page=1,
                    page_size=20,
                )

    def test_history_command_connection_error(self, cli_runner, mock_google_ads_env):
        """Test history command connection error handling."""
        with patch.dict(os.environ, mock_google_ads_env):
            with patch("paidsearchnav.scheduler.cli.SchedulerAPI") as mock_api_class:
                # Setup mock to raise connection error
                mock_api = AsyncMock()
                mock_api.get_job_history.side_effect = ConnectionError(
                    "API unavailable"
                )
                mock_api_class.return_value = mock_api

                # Run command
                result = cli_runner.invoke(scheduler, ["history"])

                # Verify
                assert result.exit_code == 1
                assert "❌ Connection failed:" in result.output
                assert "network connection" in result.output


class TestSchedulerScheduleCommand:
    """Test scheduler schedule command functionality."""

    def test_schedule_command_basic_success(self, cli_runner, mock_google_ads_env):
        """Test successful schedule command execution."""
        with patch.dict(os.environ, mock_google_ads_env):
            with patch("paidsearchnav.scheduler.cli.SchedulerAPI") as mock_api_class:
                # Setup mock
                mock_api = AsyncMock()
                mock_api.schedule_audit.return_value = {
                    "job_id": "scheduled_audit_1234567890",
                    "customer_id": "1234567890",
                    "schedule": "0 0 1 */3 *",
                    "status": "scheduled",
                }
                mock_api_class.return_value = mock_api

                # Run command
                result = cli_runner.invoke(
                    scheduler,
                    [
                        "schedule",
                        "--customer-id",
                        "1234567890",
                        "--schedule",
                        "0 0 1 */3 *",
                    ],
                )

                # Verify
                assert result.exit_code == 0
                assert "Job ID: scheduled_audit_1234567890" in result.output
                assert "Customer: 1234567890" in result.output
                assert "Schedule: 0 0 1 */3 *" in result.output
                assert "Status: scheduled" in result.output

    def test_schedule_command_disable(self, cli_runner, mock_google_ads_env):
        """Test schedule command with disable option."""
        with patch.dict(os.environ, mock_google_ads_env):
            with patch("paidsearchnav.scheduler.cli.SchedulerAPI") as mock_api_class:
                # Setup mock
                mock_api = AsyncMock()
                mock_api.schedule_audit.return_value = {
                    "job_id": "scheduled_audit_1234567890",
                    "customer_id": "1234567890",
                    "schedule": "0 0 1 */3 *",
                    "status": "disabled",
                }
                mock_api_class.return_value = mock_api

                # Run command
                result = cli_runner.invoke(
                    scheduler,
                    [
                        "schedule",
                        "--customer-id",
                        "1234567890",
                        "--schedule",
                        "0 0 1 */3 *",
                        "--disabled",
                    ],
                )

                # Verify
                assert result.exit_code == 0
                # Should have called with enabled=False
                calls = mock_api.schedule_audit.call_args_list
                assert len(calls) == 1
                assert calls[0][0][0].enabled is False

    def test_schedule_command_invalid_cron(self, cli_runner, mock_google_ads_env):
        """Test schedule command with invalid cron expression."""
        with patch.dict(os.environ, mock_google_ads_env):
            with patch("paidsearchnav.scheduler.cli.SchedulerAPI") as mock_api_class:
                # Setup mock to raise error
                mock_api = AsyncMock()
                mock_api.schedule_audit.side_effect = ValueError(
                    "Invalid cron expression"
                )
                mock_api_class.return_value = mock_api

                # Run command
                result = cli_runner.invoke(
                    scheduler,
                    [
                        "schedule",
                        "--customer-id",
                        "1234567890",
                        "--schedule",
                        "invalid",
                    ],
                )

                # Verify
                assert result.exit_code == 1
                assert "❌ Invalid schedule expression:" in result.output

    def test_schedule_command_error(self, cli_runner, mock_google_ads_env):
        """Test schedule command error handling."""
        with patch.dict(os.environ, mock_google_ads_env):
            with patch("paidsearchnav.scheduler.cli.SchedulerAPI") as mock_api_class:
                # Setup mock to raise error
                mock_api = AsyncMock()
                mock_api.schedule_audit.side_effect = Exception("Schedule error")
                mock_api_class.return_value = mock_api

                # Run command
                result = cli_runner.invoke(
                    scheduler,
                    [
                        "schedule",
                        "--customer-id",
                        "1234567890",
                        "--schedule",
                        "0 0 1 */3 *",
                    ],
                )

                # Verify - the CLI now handles exceptions gracefully
                assert result.exit_code == 1
                assert (
                    "❌ Failed to schedule audit: An unexpected error occurred"
                    in result.output
                )

    def test_schedule_command_connection_error(self, cli_runner, mock_google_ads_env):
        """Test schedule command connection error handling."""
        with patch.dict(os.environ, mock_google_ads_env):
            with patch("paidsearchnav.scheduler.cli.SchedulerAPI") as mock_api_class:
                # Setup mock to raise connection error
                mock_api = AsyncMock()
                mock_api.schedule_audit.side_effect = ConnectionError(
                    "Database connection failed"
                )
                mock_api_class.return_value = mock_api

                # Run command
                result = cli_runner.invoke(
                    scheduler,
                    [
                        "schedule",
                        "--customer-id",
                        "1234567890",
                        "--schedule",
                        "0 0 1 */3 *",
                    ],
                )

                # Verify
                assert result.exit_code == 1
                assert "❌ Connection failed:" in result.output
                assert "network connection" in result.output


class TestSchedulerCancelCommand:
    """Test scheduler cancel command functionality."""

    def test_cancel_command_success(self, cli_runner, mock_google_ads_env):
        """Test successful cancel command execution."""
        with patch.dict(os.environ, mock_google_ads_env):
            with patch("paidsearchnav.scheduler.cli.SchedulerAPI") as mock_api_class:
                # Setup mock
                mock_api = AsyncMock()
                mock_api.cancel_job.return_value = {
                    "job_id": "job_123",
                    "success": True,
                    "status": "cancelled",
                }
                mock_api_class.return_value = mock_api

                # Run command
                result = cli_runner.invoke(scheduler, ["cancel", "job_123"])

                # Verify
                assert result.exit_code == 0
                assert "✅ Successfully cancelled job: job_123" in result.output

    def test_cancel_command_not_found(self, cli_runner, mock_google_ads_env):
        """Test cancel command when job not found."""
        with patch.dict(os.environ, mock_google_ads_env):
            with patch("paidsearchnav.scheduler.cli.SchedulerAPI") as mock_api_class:
                # Setup mock
                mock_api = AsyncMock()
                mock_api.cancel_job.return_value = {
                    "job_id": "job_123",
                    "success": False,
                    "status": "not_found",
                }
                mock_api_class.return_value = mock_api

                # Run command
                result = cli_runner.invoke(scheduler, ["cancel", "job_123"])

                # Verify
                assert result.exit_code == 0
                assert "❌ Failed to cancel job: job_123 (not_found)" in result.output
                assert "already completed or been cancelled" in result.output

    def test_cancel_command_connection_error(self, cli_runner, mock_google_ads_env):
        """Test cancel command connection error handling."""
        with patch.dict(os.environ, mock_google_ads_env):
            with patch("paidsearchnav.scheduler.cli.SchedulerAPI") as mock_api_class:
                # Setup mock to raise connection error
                mock_api = AsyncMock()
                mock_api.cancel_job.side_effect = ConnectionError("Service unavailable")
                mock_api_class.return_value = mock_api

                # Run command
                result = cli_runner.invoke(scheduler, ["cancel", "job_123"])

                # Verify
                assert result.exit_code == 1
                assert "❌ Connection failed:" in result.output
                assert "network connection" in result.output


class TestSchedulerStartCommand:
    """Test scheduler start command functionality."""

    def test_start_command_disabled_scheduler(self, cli_runner):
        """Test start command when scheduler is disabled."""
        with patch("paidsearchnav.scheduler.cli.get_settings") as mock_get_settings:
            # Mock disabled scheduler
            mock_settings = Mock()
            mock_settings.scheduler.enabled = False
            mock_get_settings.return_value = mock_settings

            # Run command
            result = cli_runner.invoke(scheduler, ["start"])

            # Verify scheduler disabled message
            assert result.exit_code == 1
            assert "❌ Scheduler is disabled in configuration" in result.output

    def test_start_command_connection_error(self, cli_runner):
        """Test start command when database connection fails."""
        with patch("paidsearchnav.scheduler.cli.get_settings") as mock_get_settings:
            with patch(
                "paidsearchnav.scheduler.cli.AnalysisRepository"
            ) as mock_repo_class:
                # Mock enabled scheduler
                mock_settings = Mock()
                mock_settings.scheduler.enabled = True
                mock_get_settings.return_value = mock_settings

                # Mock repository initialization failure
                mock_repo_class.side_effect = ConnectionError(
                    "Failed to connect to database"
                )

                # Run command
                result = cli_runner.invoke(scheduler, ["start"])

                # Verify connection error handling
                assert result.exit_code == 1
                assert "❌ Connection failed:" in result.output
                assert "database connection" in result.output


class TestDateParsingFunctionality:
    """Test flexible date parsing functionality."""

    def test_parse_date_flexible_iso_format(self):
        """Test parsing ISO date formats."""
        # Basic ISO format
        result = parse_date_flexible("2024-01-15")
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 0
        assert result.minute == 0
        assert result.second == 0

        # ISO with time (should be normalized to start of day)
        result = parse_date_flexible("2024-01-15T10:30:00")
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 0
        assert result.minute == 0
        assert result.second == 0

    def test_parse_date_flexible_us_format(self):
        """Test parsing US date formats."""
        # MM/DD/YYYY
        result = parse_date_flexible("01/15/2024")
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15

        # M/D/YYYY
        result = parse_date_flexible("1/15/2024")
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15

        # MM-DD-YYYY
        result = parse_date_flexible("01-15-2024")
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15

    def test_parse_date_flexible_european_format(self):
        """Test parsing European date formats."""
        # DD/MM/YYYY - Use unambiguous date where day > 12
        result = parse_date_flexible("15/01/2024")
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15

        # DD.MM.YYYY
        result = parse_date_flexible("15.01.2024")
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15

        # Note: For ambiguous dates like 5/1/2024, dateutil defaults to US format (MM/DD)
        # This is expected behavior and not a bug in our implementation
        result = parse_date_flexible("31/01/2024")  # Unambiguous European format
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 31

    def test_parse_date_flexible_natural_language(self):
        """Test parsing natural language date formats."""
        # January 15, 2024
        result = parse_date_flexible("January 15, 2024")
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15

        # Jan 15 2024
        result = parse_date_flexible("Jan 15 2024")
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15

        # 15 Jan 2024
        result = parse_date_flexible("15 Jan 2024")
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15

    @pytest.mark.parametrize("relative_date", ["today", "yesterday", "tomorrow"])
    def test_parse_date_flexible_relative_dates(self, relative_date):
        """Test parsing relative date terms."""
        from datetime import date, timedelta

        result = parse_date_flexible(relative_date)

        # Verify the result is a datetime object
        assert isinstance(result, datetime)

        # Verify it's normalized to start of day
        assert result.hour == 0
        assert result.minute == 0
        assert result.second == 0

        # Verify the date makes sense
        today = date.today()
        if relative_date == "today":
            assert result.date() == today
        elif relative_date == "yesterday":
            assert result.date() == today - timedelta(days=1)
        elif relative_date == "tomorrow":
            assert result.date() == today + timedelta(days=1)

    def test_parse_date_flexible_error_handling(self):
        """Test error handling for invalid date formats."""
        # Empty string
        with pytest.raises(ValueError, match="Date string cannot be empty"):
            parse_date_flexible("")

        # Whitespace only
        with pytest.raises(ValueError, match="Date string cannot be empty"):
            parse_date_flexible("   ")

        # Invalid date
        with pytest.raises(ValueError, match="Unable to parse date"):
            parse_date_flexible("not-a-date")

        # Invalid format with helpful error message
        with pytest.raises(ValueError) as exc_info:
            parse_date_flexible("invalid-date-format")

        error_msg = str(exc_info.value)
        assert "Unable to parse date 'invalid-date-format'" in error_msg
        assert "Supported formats include:" in error_msg
        assert "ISO format:" in error_msg
        assert "US format:" in error_msg
        assert "European format:" in error_msg
        assert "Natural language:" in error_msg
        assert "Relative:" in error_msg

    def test_parse_date_flexible_whitespace_handling(self):
        """Test handling of whitespace in date strings."""
        # Leading/trailing whitespace
        result = parse_date_flexible("  2024-01-15  ")
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15

        # Multiple spaces
        result = parse_date_flexible("Jan  15  2024")
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15

    def test_run_command_with_flexible_date_formats(
        self, cli_runner, mock_google_ads_env
    ):
        """Test run command with various date formats."""
        with patch.dict(os.environ, mock_google_ads_env):
            with patch("paidsearchnav.scheduler.cli.SchedulerAPI") as mock_api_class:
                mock_api = AsyncMock()
                mock_api.trigger_audit.return_value = {
                    "execution_id": "exec_123",
                    "job_id": "job_123",
                    "status": "pending",
                }
                mock_api_class.return_value = mock_api

                # Test ISO format
                result = cli_runner.invoke(
                    scheduler,
                    [
                        "run",
                        "--customer-id",
                        "1234567890",
                        "--start-date",
                        "2024-01-15",
                        "--end-date",
                        "2024-01-31",
                    ],
                )
                assert result.exit_code == 0
                assert "✅ Started audit:" in result.output

                # Test US format
                result = cli_runner.invoke(
                    scheduler,
                    [
                        "run",
                        "--customer-id",
                        "1234567890",
                        "--start-date",
                        "01/15/2024",
                        "--end-date",
                        "01/31/2024",
                    ],
                )
                assert result.exit_code == 0
                assert "✅ Started audit:" in result.output

                # Test natural language
                result = cli_runner.invoke(
                    scheduler,
                    [
                        "run",
                        "--customer-id",
                        "1234567890",
                        "--start-date",
                        "Jan 15 2024",
                        "--end-date",
                        "Jan 31 2024",
                    ],
                )
                assert result.exit_code == 0
                assert "✅ Started audit:" in result.output

    def test_run_command_with_invalid_flexible_date(
        self, cli_runner, mock_google_ads_env
    ):
        """Test run command with invalid date that provides helpful error message."""
        with patch.dict(os.environ, mock_google_ads_env):
            result = cli_runner.invoke(
                scheduler,
                [
                    "run",
                    "--customer-id",
                    "1234567890",
                    "--start-date",
                    "not-a-real-date",
                ],
            )

            # Should fail with helpful error message
            assert result.exit_code == 1
            assert "❌ Invalid date format:" in result.output
            assert "Unable to parse date 'not-a-real-date'" in result.output
            assert "Supported formats include:" in result.output


class TestAdvancedSchedulerCLI:
    """Test advanced scheduler CLI commands."""

    def test_logs_help(self, cli_runner):
        """Test logs command help."""
        result = cli_runner.invoke(scheduler, ["logs", "--help"])

        assert result.exit_code == 0
        assert "View detailed job logs" in result.output
        assert "--job-id" in result.output
        assert "--audit-id" in result.output
        assert "--customer-id" in result.output
        assert "--follow" in result.output
        assert "--tail" in result.output
        assert "--since" in result.output
        assert "--level" in result.output
        assert "--output" in result.output
        assert "--export" in result.output

    def test_retry_help(self, cli_runner):
        """Test retry command help."""
        result = cli_runner.invoke(scheduler, ["retry", "--help"])

        assert result.exit_code == 0
        assert "Retry failed jobs" in result.output
        assert "--job-id" in result.output
        assert "--audit-id" in result.output
        assert "--force" in result.output
        assert "--analyzer" in result.output
        assert "--dry-run" in result.output

    def test_pause_help(self, cli_runner):
        """Test pause command help."""
        result = cli_runner.invoke(scheduler, ["pause", "--help"])

        assert result.exit_code == 0
        assert "Pause scheduled jobs" in result.output
        assert "--schedule-id" in result.output
        assert "--customer-id" in result.output
        assert "--all" in result.output
        assert "--reason" in result.output
        assert "--notify" in result.output

    def test_resume_help(self, cli_runner):
        """Test resume command help."""
        result = cli_runner.invoke(scheduler, ["resume", "--help"])

        assert result.exit_code == 0
        assert "Resume paused schedules" in result.output
        assert "--schedule-id" in result.output
        assert "--customer-id" in result.output
        assert "--all" in result.output
        assert "--reason" in result.output
        assert "--notify" in result.output

    def test_stats_help(self, cli_runner):
        """Test stats command help."""
        result = cli_runner.invoke(scheduler, ["stats", "--help"])

        assert result.exit_code == 0
        assert "Show scheduler performance statistics" in result.output
        assert "--customer-id" in result.output
        assert "--date-range" in result.output
        assert "--format" in result.output
        assert "--export" in result.output
        assert "--include" in result.output

    def test_resources_help(self, cli_runner):
        """Test resources command help."""
        result = cli_runner.invoke(scheduler, ["resources", "--help"])

        assert result.exit_code == 0
        assert "Show scheduler resource utilization" in result.output

    def test_queue_status_help(self, cli_runner):
        """Test queue-status command help."""
        result = cli_runner.invoke(scheduler, ["queue-status", "--help"])

        assert result.exit_code == 0
        assert "Show scheduler queue status" in result.output

    def test_logs_command_success(self, cli_runner, mock_google_ads_env):
        """Test successful logs command execution."""
        with patch.dict(os.environ, mock_google_ads_env):
            with patch("paidsearchnav.scheduler.cli.SchedulerAPI") as mock_api_class:
                with patch("paidsearchnav.scheduler.cli._get_logs") as mock_get_logs:
                    # Setup mocks
                    mock_api = AsyncMock()
                    mock_api_class.return_value = mock_api

                    mock_logs = [
                        {
                            "timestamp": datetime(2024, 1, 15, 10, 30),
                            "job_id": "job_123",
                            "level": "INFO",
                            "message": "Job completed successfully",
                            "context": {"customer_id": "1234567890"},
                        }
                    ]
                    mock_get_logs.return_value = mock_logs

                    # Run command
                    result = cli_runner.invoke(
                        scheduler, ["logs", "--customer-id", "1234567890"]
                    )

                    # Verify
                    assert result.exit_code == 0
                    assert "INFO job_123: Job completed successfully" in result.output

    def test_logs_command_with_export(self, cli_runner, mock_google_ads_env, tmp_path):
        """Test logs command with export option."""
        with patch.dict(os.environ, mock_google_ads_env):
            with patch("paidsearchnav.scheduler.cli.SchedulerAPI") as mock_api_class:
                with patch("paidsearchnav.scheduler.cli._get_logs") as mock_get_logs:
                    # Setup mocks
                    mock_api = AsyncMock()
                    mock_api_class.return_value = mock_api

                    mock_logs = [
                        {
                            "timestamp": datetime(2024, 1, 15, 10, 30),
                            "job_id": "job_123",
                            "level": "INFO",
                            "message": "Job completed successfully",
                            "context": {},
                        }
                    ]
                    mock_get_logs.return_value = mock_logs

                    # Create export file path
                    export_file = tmp_path / "logs.txt"

                    # Run command
                    result = cli_runner.invoke(
                        scheduler, ["logs", "--export", str(export_file)]
                    )

                    # Verify
                    assert result.exit_code == 0
                    assert f"Logs exported to {export_file}" in result.output
                    assert export_file.exists()

    def test_logs_command_json_output(self, cli_runner, mock_google_ads_env):
        """Test logs command with JSON output."""
        with patch.dict(os.environ, mock_google_ads_env):
            with patch("paidsearchnav.scheduler.cli.SchedulerAPI") as mock_api_class:
                with patch("paidsearchnav.scheduler.cli._get_logs") as mock_get_logs:
                    # Setup mocks
                    mock_api = AsyncMock()
                    mock_api_class.return_value = mock_api

                    mock_logs = [
                        {
                            "timestamp": datetime(2024, 1, 15, 10, 30),
                            "job_id": "job_123",
                            "level": "INFO",
                            "message": "Job completed successfully",
                            "context": {},
                        }
                    ]
                    mock_get_logs.return_value = mock_logs

                    # Run command
                    result = cli_runner.invoke(scheduler, ["logs", "--output", "json"])

                    # Verify
                    assert result.exit_code == 0
                    assert '"job_id": "job_123"' in result.output
                    assert '"level": "INFO"' in result.output

    def test_logs_command_no_logs_found(self, cli_runner, mock_google_ads_env):
        """Test logs command when no logs found."""
        with patch.dict(os.environ, mock_google_ads_env):
            with patch("paidsearchnav.scheduler.cli.SchedulerAPI") as mock_api_class:
                with patch("paidsearchnav.scheduler.cli._get_logs") as mock_get_logs:
                    # Setup mocks
                    mock_api = AsyncMock()
                    mock_api_class.return_value = mock_api
                    mock_get_logs.return_value = []

                    # Run command
                    result = cli_runner.invoke(scheduler, ["logs"])

                    # Verify
                    assert result.exit_code == 0
                    assert "No logs found matching criteria." in result.output

    def test_retry_command_success(self, cli_runner, mock_google_ads_env):
        """Test successful retry command execution."""
        with patch.dict(os.environ, mock_google_ads_env):
            with patch("paidsearchnav.scheduler.cli.SchedulerAPI") as mock_api_class:
                with patch(
                    "paidsearchnav.scheduler.cli._get_retryable_jobs"
                ) as mock_get_retryable:
                    # Setup mocks
                    mock_api = AsyncMock()
                    mock_api.retry_job.return_value = {"success": True}
                    mock_api_class.return_value = mock_api

                    mock_retryable_jobs = [{"job_id": "job_123", "status": "failed"}]
                    mock_get_retryable.return_value = mock_retryable_jobs

                    # Run command
                    result = cli_runner.invoke(
                        scheduler, ["retry", "--job-id", "job_123"]
                    )

                    # Verify
                    assert result.exit_code == 0
                    assert "✅ Retried job: job_123" in result.output
                    assert "Retried 1 of 1 jobs." in result.output

    def test_retry_command_dry_run(self, cli_runner, mock_google_ads_env):
        """Test retry command in dry-run mode."""
        with patch.dict(os.environ, mock_google_ads_env):
            with patch("paidsearchnav.scheduler.cli.SchedulerAPI") as mock_api_class:
                with patch(
                    "paidsearchnav.scheduler.cli._get_retryable_jobs"
                ) as mock_get_retryable:
                    # Setup mocks
                    mock_api = AsyncMock()
                    mock_api_class.return_value = mock_api

                    mock_retryable_jobs = [{"job_id": "job_123", "status": "failed"}]
                    mock_get_retryable.return_value = mock_retryable_jobs

                    # Run command
                    result = cli_runner.invoke(scheduler, ["retry", "--dry-run"])

                    # Verify
                    assert result.exit_code == 0
                    assert "Jobs that would be retried:" in result.output
                    assert "- job_123 (Status: failed)" in result.output
                    # Ensure retry_job was not called
                    mock_api.retry_job.assert_not_called()

    def test_retry_command_no_retryable_jobs(self, cli_runner, mock_google_ads_env):
        """Test retry command when no retryable jobs found."""
        with patch.dict(os.environ, mock_google_ads_env):
            with patch("paidsearchnav.scheduler.cli.SchedulerAPI") as mock_api_class:
                with patch(
                    "paidsearchnav.scheduler.cli._get_retryable_jobs"
                ) as mock_get_retryable:
                    # Setup mocks
                    mock_api = AsyncMock()
                    mock_api_class.return_value = mock_api
                    mock_get_retryable.return_value = []

                    # Run command
                    result = cli_runner.invoke(scheduler, ["retry"])

                    # Verify
                    assert result.exit_code == 0
                    assert "No retryable jobs found." in result.output

    def test_pause_command_success(self, cli_runner, mock_google_ads_env):
        """Test successful pause command execution."""
        with patch.dict(os.environ, mock_google_ads_env):
            with patch("paidsearchnav.scheduler.cli.SchedulerAPI") as mock_api_class:
                with patch(
                    "paidsearchnav.scheduler.cli._get_schedules_to_modify"
                ) as mock_get_schedules:
                    # Setup mocks
                    mock_api = AsyncMock()
                    mock_api.pause_schedule.return_value = {"success": True}
                    mock_api_class.return_value = mock_api

                    mock_schedules = [
                        {"schedule_id": "schedule_123", "customer_id": "1234567890"}
                    ]
                    mock_get_schedules.return_value = mock_schedules

                    # Run command
                    result = cli_runner.invoke(
                        scheduler, ["pause", "--schedule-id", "schedule_123"]
                    )

                    # Verify
                    assert result.exit_code == 0
                    assert "⏸️  Paused schedule: schedule_123" in result.output
                    assert "Paused 1 of 1 schedules." in result.output

    def test_pause_command_no_schedules(self, cli_runner, mock_google_ads_env):
        """Test pause command when no schedules found."""
        with patch.dict(os.environ, mock_google_ads_env):
            with patch("paidsearchnav.scheduler.cli.SchedulerAPI") as mock_api_class:
                with patch(
                    "paidsearchnav.scheduler.cli._get_schedules_to_modify"
                ) as mock_get_schedules:
                    # Setup mocks
                    mock_api = AsyncMock()
                    mock_api_class.return_value = mock_api
                    mock_get_schedules.return_value = []

                    # Run command
                    result = cli_runner.invoke(
                        scheduler, ["pause", "--customer-id", "1234567890"]
                    )

                    # Verify
                    assert result.exit_code == 0
                    assert "No schedules found to pause." in result.output

    def test_resume_command_success(self, cli_runner, mock_google_ads_env):
        """Test successful resume command execution."""
        with patch.dict(os.environ, mock_google_ads_env):
            with patch("paidsearchnav.scheduler.cli.SchedulerAPI") as mock_api_class:
                with patch(
                    "paidsearchnav.scheduler.cli._get_schedules_to_modify"
                ) as mock_get_schedules:
                    # Setup mocks
                    mock_api = AsyncMock()
                    mock_api.resume_schedule.return_value = {"success": True}
                    mock_api_class.return_value = mock_api

                    mock_schedules = [
                        {"schedule_id": "schedule_123", "customer_id": "1234567890"}
                    ]
                    mock_get_schedules.return_value = mock_schedules

                    # Run command
                    result = cli_runner.invoke(
                        scheduler, ["resume", "--schedule-id", "schedule_123"]
                    )

                    # Verify
                    assert result.exit_code == 0
                    assert "▶️  Resumed schedule: schedule_123" in result.output
                    assert "Resumed 1 of 1 schedules." in result.output

    def test_stats_command_success(self, cli_runner, mock_google_ads_env):
        """Test successful stats command execution."""
        with patch.dict(os.environ, mock_google_ads_env):
            with patch("paidsearchnav.scheduler.cli.SchedulerAPI") as mock_api_class:
                # Setup mocks
                mock_api = AsyncMock()
                mock_stats = {
                    "total_jobs": 100,
                    "successful_jobs": 85,
                    "failed_jobs": 10,
                    "running_jobs": 5,
                    "success_rate": 85.0,
                    "average_duration": 120.5,
                }
                mock_api.get_scheduler_stats.return_value = mock_stats
                mock_api_class.return_value = mock_api

                # Run command
                result = cli_runner.invoke(scheduler, ["stats"])

                # Verify
                assert result.exit_code == 0
                assert "📊 Scheduler Statistics" in result.output
                assert "Total Jobs: 100" in result.output
                assert "Success Rate: 85.0" in result.output

    def test_stats_command_json_format(self, cli_runner, mock_google_ads_env):
        """Test stats command with JSON format."""
        with patch.dict(os.environ, mock_google_ads_env):
            with patch("paidsearchnav.scheduler.cli.SchedulerAPI") as mock_api_class:
                # Setup mocks
                mock_api = AsyncMock()
                mock_stats = {"total_jobs": 100, "success_rate": 85.0}
                mock_api.get_scheduler_stats.return_value = mock_stats
                mock_api_class.return_value = mock_api

                # Run command
                result = cli_runner.invoke(scheduler, ["stats", "--format", "json"])

                # Verify
                assert result.exit_code == 0
                assert '"total_jobs": 100' in result.output
                assert '"success_rate": 85.0' in result.output

    def test_stats_command_with_export(self, cli_runner, mock_google_ads_env, tmp_path):
        """Test stats command with export option."""
        with patch.dict(os.environ, mock_google_ads_env):
            with patch("paidsearchnav.scheduler.cli.SchedulerAPI") as mock_api_class:
                # Setup mocks
                mock_api = AsyncMock()
                mock_stats = {"total_jobs": 100, "success_rate": 85.0}
                mock_api.get_scheduler_stats.return_value = mock_stats
                mock_api_class.return_value = mock_api

                # Create export file path
                export_file = tmp_path / "stats.json"

                # Run command
                result = cli_runner.invoke(
                    scheduler,
                    ["stats", "--format", "json", "--export", str(export_file)],
                )

                # Verify
                assert result.exit_code == 0
                assert f"Statistics exported to {export_file}" in result.output
                assert export_file.exists()

    def test_stats_command_no_data(self, cli_runner, mock_google_ads_env):
        """Test stats command when no data available."""
        with patch.dict(os.environ, mock_google_ads_env):
            with patch("paidsearchnav.scheduler.cli.SchedulerAPI") as mock_api_class:
                # Setup mocks
                mock_api = AsyncMock()
                mock_api.get_scheduler_stats.return_value = {}
                mock_api_class.return_value = mock_api

                # Run command
                result = cli_runner.invoke(scheduler, ["stats"])

                # Verify
                assert result.exit_code == 0
                assert "No statistics data available." in result.output

    def test_resources_command_success(self, cli_runner, mock_google_ads_env):
        """Test successful resources command execution."""
        with patch.dict(os.environ, mock_google_ads_env):
            with patch("paidsearchnav.scheduler.cli.SchedulerAPI") as mock_api_class:
                # Setup mocks
                mock_api = AsyncMock()
                mock_resources = {
                    "cpu": {"usage_percent": 25.5, "cores": 4},
                    "memory": {"total_gb": 16.0, "used_gb": 8.5, "usage_percent": 53.1},
                    "scheduler": {"status": "running"},
                }
                mock_api.get_resource_utilization.return_value = mock_resources
                mock_api_class.return_value = mock_api

                # Run command
                result = cli_runner.invoke(scheduler, ["resources"])

                # Verify
                assert result.exit_code == 0
                assert "📊 Scheduler Resource Utilization" in result.output
                assert "Cpu:" in result.output
                assert "usage_percent: 25.5" in result.output
                assert "Memory:" in result.output
                assert "Scheduler:" in result.output

    def test_resources_command_no_data(self, cli_runner, mock_google_ads_env):
        """Test resources command when no data available."""
        with patch.dict(os.environ, mock_google_ads_env):
            with patch("paidsearchnav.scheduler.cli.SchedulerAPI") as mock_api_class:
                # Setup mocks
                mock_api = AsyncMock()
                mock_api.get_resource_utilization.return_value = {}
                mock_api_class.return_value = mock_api

                # Run command
                result = cli_runner.invoke(scheduler, ["resources"])

                # Verify
                assert result.exit_code == 0
                assert "No resource data available." in result.output

    def test_queue_status_command_success(self, cli_runner, mock_google_ads_env):
        """Test successful queue-status command execution."""
        with patch.dict(os.environ, mock_google_ads_env):
            with patch("paidsearchnav.scheduler.cli.SchedulerAPI") as mock_api_class:
                # Setup mocks
                mock_api = AsyncMock()
                mock_queue_data = {
                    "active_jobs": {"running": 5, "pending": 3},
                    "queues": {
                        "audit_queue": {"size": 3, "processing": 5},
                        "analyzer_queue": {"size": 0, "processing": 0},
                    },
                }
                mock_api.get_queue_status.return_value = mock_queue_data
                mock_api_class.return_value = mock_api

                # Run command
                result = cli_runner.invoke(scheduler, ["queue-status"])

                # Verify
                assert result.exit_code == 0
                assert "📋 Scheduler Queue Status" in result.output
                assert "Active_Jobs" in result.output
                assert "running: 5" in result.output
                assert "Queues Queue:" in result.output

    def test_queue_status_command_no_data(self, cli_runner, mock_google_ads_env):
        """Test queue-status command when no data available."""
        with patch.dict(os.environ, mock_google_ads_env):
            with patch("paidsearchnav.scheduler.cli.SchedulerAPI") as mock_api_class:
                # Setup mocks
                mock_api = AsyncMock()
                mock_api.get_queue_status.return_value = {}
                mock_api_class.return_value = mock_api

                # Run command
                result = cli_runner.invoke(scheduler, ["queue-status"])

                # Verify
                assert result.exit_code == 0
                assert "No queue data available." in result.output

    def test_logs_command_error_handling(self, cli_runner, mock_google_ads_env):
        """Test logs command error handling."""
        with patch.dict(os.environ, mock_google_ads_env):
            with patch("paidsearchnav.scheduler.cli.SchedulerAPI") as mock_api_class:
                with patch("paidsearchnav.scheduler.cli._get_logs") as mock_get_logs:
                    # Setup mocks to raise error
                    mock_api = AsyncMock()
                    mock_api_class.return_value = mock_api
                    mock_get_logs.side_effect = Exception("Logs error")

                    # Run command
                    result = cli_runner.invoke(scheduler, ["logs"])

                    # Verify error handling
                    assert result.exit_code == 1
                    assert "❌ Failed to retrieve logs:" in result.output

    def test_retry_command_error_handling(self, cli_runner, mock_google_ads_env):
        """Test retry command error handling."""
        with patch.dict(os.environ, mock_google_ads_env):
            with patch("paidsearchnav.scheduler.cli.SchedulerAPI") as mock_api_class:
                with patch(
                    "paidsearchnav.scheduler.cli._get_retryable_jobs"
                ) as mock_get_retryable:
                    # Setup mocks to raise error
                    mock_api = AsyncMock()
                    mock_api_class.return_value = mock_api
                    mock_get_retryable.side_effect = Exception("Retry error")

                    # Run command
                    result = cli_runner.invoke(scheduler, ["retry"])

                    # Verify error handling
                    assert result.exit_code == 1
                    assert "❌ Failed to retry jobs:" in result.output

    def test_pause_command_error_handling(self, cli_runner, mock_google_ads_env):
        """Test pause command error handling."""
        with patch.dict(os.environ, mock_google_ads_env):
            with patch("paidsearchnav.scheduler.cli.SchedulerAPI") as mock_api_class:
                with patch(
                    "paidsearchnav.scheduler.cli._get_schedules_to_modify"
                ) as mock_get_schedules:
                    # Setup mocks to raise error
                    mock_api = AsyncMock()
                    mock_api_class.return_value = mock_api
                    mock_get_schedules.side_effect = Exception("Pause error")

                    # Run command
                    result = cli_runner.invoke(scheduler, ["pause"])

                    # Verify error handling
                    assert result.exit_code == 1
                    assert "❌ Failed to pause schedules:" in result.output

    def test_validate_export_path_safe_paths(self):
        """Test export path validation with safe paths."""
        from paidsearchnav.scheduler.cli import validate_export_path

        # Test safe relative path
        safe_path = validate_export_path("logs.txt")
        assert safe_path.name == "logs.txt"

        # Test safe subdirectory path
        safe_subdir = validate_export_path("exports/logs.txt")
        assert safe_subdir.name == "logs.txt"
        assert "exports" in str(safe_subdir)

    def test_validate_export_path_directory_traversal(self):
        """Test export path validation blocks directory traversal."""
        from paidsearchnav.scheduler.cli import validate_export_path

        # Test directory traversal attempt
        with pytest.raises(
            ValueError, match="Export path must be within current directory"
        ):
            validate_export_path("../../../etc/passwd")

        # Test relative path with directory traversal
        with pytest.raises(
            ValueError, match="Export path must be within current directory"
        ):
            validate_export_path("../../etc/passwd")


class TestNewSchedulerCommands:
    """Test new scheduler CLI commands implementation."""

    def test_stop_help(self, cli_runner):
        """Test stop command help."""
        result = cli_runner.invoke(scheduler, ["stop", "--help"])

        assert result.exit_code == 0
        assert "Stop the scheduler service gracefully" in result.output

    def test_service_status_help(self, cli_runner):
        """Test service-status command help."""
        result = cli_runner.invoke(scheduler, ["service-status", "--help"])

        assert result.exit_code == 0
        assert "Show detailed scheduler service status" in result.output

    def test_list_schedules_help(self, cli_runner):
        """Test list-schedules command help."""
        result = cli_runner.invoke(scheduler, ["list-schedules", "--help"])

        assert result.exit_code == 0
        assert "List all active/inactive schedules" in result.output
        assert "--customer-id" in result.output
        assert "--status" in result.output
        assert "--format" in result.output

    def test_update_schedule_help(self, cli_runner):
        """Test update-schedule command help."""
        result = cli_runner.invoke(scheduler, ["update-schedule", "--help"])

        assert result.exit_code == 0
        assert "Modify existing schedule parameters" in result.output
        assert "--schedule" in result.output
        assert "--customer-id" in result.output
        assert "--analyzers" in result.output
        assert "--enabled" in result.output

    def test_delete_schedule_help(self, cli_runner):
        """Test delete-schedule command help."""
        result = cli_runner.invoke(scheduler, ["delete-schedule", "--help"])

        assert result.exit_code == 0
        assert "Remove scheduled jobs" in result.output
        assert "--force" in result.output

    def test_stop_command_success(self, cli_runner):
        """Test successful stop command execution."""
        with patch("paidsearchnav.scheduler.cli.get_settings") as mock_get_settings:
            with patch(
                "paidsearchnav.scheduler.cli.AnalysisRepository"
            ) as mock_repo_class:
                with patch(
                    "paidsearchnav.scheduler.cli.JobHistoryStore"
                ) as mock_job_store_class:
                    with patch(
                        "paidsearchnav.scheduler.cli.AuditScheduler"
                    ) as mock_scheduler_class:
                        # Mock enabled scheduler
                        mock_settings = Mock()
                        mock_settings.scheduler.enabled = True
                        mock_get_settings.return_value = mock_settings

                        # Mock scheduler shutdown
                        mock_scheduler = AsyncMock()
                        mock_scheduler.shutdown = AsyncMock()
                        mock_scheduler_class.return_value = mock_scheduler

                        # Run command
                        result = cli_runner.invoke(scheduler, ["stop"])

                        # Verify
                        assert result.exit_code == 0
                        assert (
                            "✅ Scheduler service stopped gracefully" in result.output
                        )
                        mock_scheduler.shutdown.assert_called_once()

    def test_stop_command_disabled_scheduler(self, cli_runner):
        """Test stop command when scheduler is disabled."""
        with patch("paidsearchnav.scheduler.cli.get_settings") as mock_get_settings:
            # Mock disabled scheduler
            mock_settings = Mock()
            mock_settings.scheduler.enabled = False
            mock_get_settings.return_value = mock_settings

            # Run command
            result = cli_runner.invoke(scheduler, ["stop"])

            # Verify scheduler disabled message
            assert result.exit_code == 0
            assert "❌ Scheduler is not configured as enabled" in result.output

    def test_stop_command_error_handling(self, cli_runner):
        """Test stop command error handling."""
        with patch("paidsearchnav.scheduler.cli.get_settings") as mock_get_settings:
            with patch(
                "paidsearchnav.scheduler.cli.AnalysisRepository"
            ) as mock_repo_class:
                # Mock enabled scheduler
                mock_settings = Mock()
                mock_settings.scheduler.enabled = True
                mock_get_settings.return_value = mock_settings

                # Mock repository initialization failure
                mock_repo_class.side_effect = ConnectionError(
                    "Failed to connect to database"
                )

                # Run command
                result = cli_runner.invoke(scheduler, ["stop"])

                # Verify connection error handling
                assert result.exit_code == 1
                assert "❌ Connection failed:" in result.output
                assert "database connection" in result.output

    def test_service_status_command_success(self, cli_runner, mock_google_ads_env):
        """Test successful service-status command execution."""
        with patch.dict(os.environ, mock_google_ads_env):
            with patch("paidsearchnav.scheduler.cli.SchedulerAPI") as mock_api_class:
                # Setup mocks
                mock_api = AsyncMock()
                mock_api.get_resource_utilization.return_value = {
                    "scheduler": {"status": "running", "uptime": "2 hours"},
                    "cpu": {"usage_percent": 25.5, "cores": 4},
                    "memory": {"total_gb": 16.0, "used_gb": 8.5, "usage_percent": 53.1},
                }
                mock_api.get_queue_status.return_value = {
                    "active_jobs": {"running": 3, "pending": 2},
                    "queues": {
                        "audit_queue": {"size": 2, "processing": 3},
                        "analyzer_queue": {"size": 0, "processing": 0},
                    },
                }
                mock_api.get_scheduler_stats.return_value = {
                    "total_jobs": 150,
                    "success_rate": 92.3,
                    "failed_jobs": 12,
                    "average_duration": 180.5,
                }
                mock_api_class.return_value = mock_api

                # Run command
                result = cli_runner.invoke(scheduler, ["service-status"])

                # Verify
                assert result.exit_code == 0
                assert "🔧 Scheduler Service Status" in result.output
                assert "Service Health:" in result.output
                assert "Status: running" in result.output
                assert "Queue Status:" in result.output
                assert "Running Jobs: 3" in result.output
                assert "Performance Metrics:" in result.output
                assert "Total Jobs Processed: 150" in result.output
                assert "Resource Utilization:" in result.output
                assert "CPU: 25.5%" in result.output

    def test_service_status_command_error_handling(
        self, cli_runner, mock_google_ads_env
    ):
        """Test service-status command error handling."""
        with patch.dict(os.environ, mock_google_ads_env):
            with patch("paidsearchnav.scheduler.cli.SchedulerAPI") as mock_api_class:
                # Setup mock to raise error
                mock_api = AsyncMock()
                mock_api.get_resource_utilization.side_effect = Exception(
                    "Service error"
                )
                mock_api_class.return_value = mock_api

                # Run command
                result = cli_runner.invoke(scheduler, ["service-status"])

                # Verify error handling
                assert result.exit_code == 1
                assert "❌ Failed to get service status:" in result.output

    def test_list_schedules_command_success(self, cli_runner, mock_google_ads_env):
        """Test successful list-schedules command execution."""
        with patch.dict(os.environ, mock_google_ads_env):
            with patch("paidsearchnav.scheduler.cli.SchedulerAPI") as mock_api_class:
                # Setup mocks
                mock_api = Mock()
                mock_scheduler = AsyncMock()

                # Mock scheduled audits
                from datetime import datetime, timezone

                from paidsearchnav.scheduler.interfaces import JobType

                mock_schedule = Mock()
                mock_schedule.job_id = "scheduled_audit_1234567890"
                mock_schedule.job_type = JobType.QUARTERLY_AUDIT
                mock_schedule.trigger = {"expression": "0 0 1 */3 *"}
                mock_schedule.context = {
                    "customer_id": "1234567890",
                    "analyzers": ["keyword_match"],
                }
                mock_schedule.enabled = True
                mock_schedule.created_at = datetime.now(timezone.utc)
                mock_schedule.next_run_time = datetime.now(timezone.utc)

                mock_scheduler.list_scheduled_audits.return_value = [mock_schedule]
                mock_api._ensure_scheduler.return_value = mock_scheduler
                mock_api_class.return_value = mock_api

                # Run command
                result = cli_runner.invoke(scheduler, ["list-schedules"])

                # Verify
                assert result.exit_code == 0
                assert "📅 Scheduled Audits (1 found)" in result.output
                assert "Job ID: scheduled_audit_1234567890" in result.output
                assert "Customer: 1234567890" in result.output
                assert "Status: ✅ Active" in result.output

    def test_list_schedules_command_json_format(self, cli_runner, mock_google_ads_env):
        """Test list-schedules command with JSON format."""
        with patch.dict(os.environ, mock_google_ads_env):
            with patch("paidsearchnav.scheduler.cli.SchedulerAPI") as mock_api_class:
                # Setup mocks
                mock_api = Mock()
                mock_scheduler = AsyncMock()

                from datetime import datetime, timezone

                from paidsearchnav.scheduler.interfaces import JobType

                mock_schedule = Mock()
                mock_schedule.job_id = "scheduled_audit_1234567890"
                mock_schedule.job_type = JobType.QUARTERLY_AUDIT
                mock_schedule.trigger = {"expression": "0 0 1 */3 *"}
                mock_schedule.context = {"customer_id": "1234567890"}
                mock_schedule.enabled = True
                mock_schedule.created_at = datetime.now(timezone.utc)
                mock_schedule.next_run_time = None

                mock_scheduler.list_scheduled_audits.return_value = [mock_schedule]
                mock_api._ensure_scheduler.return_value = mock_scheduler
                mock_api_class.return_value = mock_api

                # Run command
                result = cli_runner.invoke(
                    scheduler, ["list-schedules", "--format", "json"]
                )

                # Verify
                assert result.exit_code == 0
                assert '"job_id": "scheduled_audit_1234567890"' in result.output
                assert '"customer_id": "1234567890"' in result.output

    def test_list_schedules_command_filtered_by_status(
        self, cli_runner, mock_google_ads_env
    ):
        """Test list-schedules command filtered by status."""
        with patch.dict(os.environ, mock_google_ads_env):
            with patch("paidsearchnav.scheduler.cli.SchedulerAPI") as mock_api_class:
                # Setup mocks with mixed statuses
                mock_api = Mock()
                mock_scheduler = AsyncMock()

                from paidsearchnav.scheduler.interfaces import JobType

                mock_active_schedule = Mock()
                mock_active_schedule.job_id = "active_schedule"
                mock_active_schedule.job_type = JobType.QUARTERLY_AUDIT
                mock_active_schedule.trigger = {"expression": "0 0 1 */3 *"}
                mock_active_schedule.context = {"customer_id": "1234567890"}
                mock_active_schedule.enabled = True
                mock_active_schedule.created_at = None
                mock_active_schedule.next_run_time = None

                mock_paused_schedule = Mock()
                mock_paused_schedule.job_id = "paused_schedule"
                mock_paused_schedule.job_type = JobType.QUARTERLY_AUDIT
                mock_paused_schedule.trigger = {"expression": "0 0 1 */3 *"}
                mock_paused_schedule.context = {"customer_id": "9876543210"}
                mock_paused_schedule.enabled = False
                mock_paused_schedule.created_at = None
                mock_paused_schedule.next_run_time = None

                mock_scheduler.list_scheduled_audits.return_value = [
                    mock_active_schedule,
                    mock_paused_schedule,
                ]
                mock_api._ensure_scheduler.return_value = mock_scheduler
                mock_api_class.return_value = mock_api

                # Test filtering by active status
                result = cli_runner.invoke(
                    scheduler, ["list-schedules", "--status", "active"]
                )

                # Verify only active schedule is shown
                assert result.exit_code == 0
                assert "active_schedule" in result.output
                assert "paused_schedule" not in result.output

    def test_list_schedules_command_no_schedules(self, cli_runner, mock_google_ads_env):
        """Test list-schedules command when no schedules found."""
        with patch.dict(os.environ, mock_google_ads_env):
            with patch("paidsearchnav.scheduler.cli.SchedulerAPI") as mock_api_class:
                # Setup mocks with no schedules
                mock_api = Mock()
                mock_scheduler = AsyncMock()
                mock_scheduler.list_scheduled_audits.return_value = []
                mock_api._ensure_scheduler.return_value = mock_scheduler
                mock_api_class.return_value = mock_api

                # Run command
                result = cli_runner.invoke(scheduler, ["list-schedules"])

                # Verify
                assert result.exit_code == 0
                assert "No scheduled audits found." in result.output

    def test_update_schedule_command_success(self, cli_runner, mock_google_ads_env):
        """Test successful update-schedule command execution."""
        with patch.dict(os.environ, mock_google_ads_env):
            with patch("paidsearchnav.scheduler.cli.SchedulerAPI") as mock_api_class:
                # Setup mocks
                mock_api = Mock()
                mock_scheduler = AsyncMock()

                # Mock existing schedule
                from paidsearchnav.scheduler.interfaces import JobType

                mock_schedule = Mock()
                mock_schedule.job_id = "schedule_123"
                mock_schedule.job_type = JobType.QUARTERLY_AUDIT
                mock_schedule.trigger = {"expression": "0 0 1 */3 *"}
                mock_schedule.context = {
                    "customer_id": "1234567890",
                    "analyzers": ["keyword_match"],
                }
                mock_schedule.enabled = True

                mock_scheduler.list_scheduled_audits.return_value = [mock_schedule]
                mock_api._ensure_scheduler.return_value = mock_scheduler

                # Mock update_schedule response (async method)
                mock_api.update_schedule = AsyncMock(
                    return_value={
                        "job_id": "schedule_123",
                        "customer_id": "1234567890",
                        "schedule": "0 0 1 */2 *",
                        "status": "scheduled",
                        "analyzers": ["keyword_match"],
                        "enabled": True,
                        "success": True,
                    }
                )
                mock_api_class.return_value = mock_api

                # Run command
                result = cli_runner.invoke(
                    scheduler,
                    ["update-schedule", "schedule_123", "--schedule", "0 0 1 */2 *"],
                )

                # Verify
                assert result.exit_code == 0
                assert "✅ Successfully updated schedule" in result.output
                assert "Schedule: 0 0 1 */2 *" in result.output

    def test_update_schedule_command_no_parameters(
        self, cli_runner, mock_google_ads_env
    ):
        """Test update-schedule command without any parameters."""
        with patch.dict(os.environ, mock_google_ads_env):
            # Run command without any update parameters
            result = cli_runner.invoke(scheduler, ["update-schedule", "schedule_123"])

            # Verify
            assert result.exit_code == 1
            assert (
                "❌ At least one parameter must be provided for update" in result.output
            )

    def test_update_schedule_command_invalid_cron(
        self, cli_runner, mock_google_ads_env
    ):
        """Test update-schedule command with invalid cron expression."""
        # Run command with invalid cron
        result = cli_runner.invoke(
            scheduler, ["update-schedule", "schedule_123", "--schedule", "invalid-cron"]
        )

        # Verify
        assert result.exit_code == 1
        assert "❌ Invalid cron expression: invalid-cron" in result.output

    def test_update_schedule_command_not_found(self, cli_runner, mock_google_ads_env):
        """Test update-schedule command when schedule not found."""
        with patch.dict(os.environ, mock_google_ads_env):
            with patch("paidsearchnav.scheduler.cli.SchedulerAPI") as mock_api_class:
                # Setup mocks with no existing schedules
                mock_api = Mock()
                mock_scheduler = AsyncMock()
                mock_scheduler.list_scheduled_audits.return_value = []
                mock_api._ensure_scheduler.return_value = mock_scheduler
                # Mock update_schedule to return failure response
                mock_api.update_schedule = AsyncMock(
                    return_value={
                        "job_id": "nonexistent_schedule",
                        "success": False,
                        "error": "Schedule not found",
                    }
                )
                mock_api_class.return_value = mock_api

                # Run command
                result = cli_runner.invoke(
                    scheduler, ["update-schedule", "nonexistent_schedule", "--enabled"]
                )

                # Verify
                assert result.exit_code == 1
                assert (
                    "❌ Failed to update schedule: Schedule not found" in result.output
                )

    def test_delete_schedule_command_success_with_confirmation(
        self, cli_runner, mock_google_ads_env
    ):
        """Test successful delete-schedule command with user confirmation."""
        with patch.dict(os.environ, mock_google_ads_env):
            with patch("paidsearchnav.scheduler.cli.SchedulerAPI") as mock_api_class:
                # Setup mocks
                mock_api = Mock()
                mock_scheduler = AsyncMock()

                # Mock existing schedule
                mock_schedule = Mock()
                mock_schedule.job_id = "schedule_123"
                mock_schedule.context = {"customer_id": "1234567890"}
                mock_schedule.trigger = {"expression": "0 0 1 */3 *"}

                mock_scheduler.list_scheduled_audits.return_value = [mock_schedule]
                mock_api._ensure_scheduler.return_value = mock_scheduler
                # Mock delete_schedule response (async method)
                mock_api.delete_schedule = AsyncMock(return_value={"success": True})
                mock_api_class.return_value = mock_api

                # Run command with confirmation
                result = cli_runner.invoke(
                    scheduler, ["delete-schedule", "schedule_123"], input="y\n"
                )

                # Verify
                assert result.exit_code == 0
                assert "✅ Successfully deleted schedule: schedule_123" in result.output

    def test_delete_schedule_command_force_flag(self, cli_runner, mock_google_ads_env):
        """Test delete-schedule command with --force flag."""
        with patch.dict(os.environ, mock_google_ads_env):
            with patch("paidsearchnav.scheduler.cli.SchedulerAPI") as mock_api_class:
                # Setup mocks
                mock_api = Mock()
                mock_scheduler = AsyncMock()

                # Mock existing schedule
                mock_schedule = Mock()
                mock_schedule.job_id = "schedule_123"
                mock_schedule.context = {"customer_id": "1234567890"}
                mock_schedule.trigger = {"expression": "0 0 1 */3 *"}

                mock_scheduler.list_scheduled_audits.return_value = [mock_schedule]
                mock_api._ensure_scheduler.return_value = mock_scheduler
                # Mock delete_schedule response (async method)
                mock_api.delete_schedule = AsyncMock(return_value={"success": True})
                mock_api_class.return_value = mock_api

                # Run command with --force flag
                result = cli_runner.invoke(
                    scheduler, ["delete-schedule", "schedule_123", "--force"]
                )

                # Verify
                assert result.exit_code == 0
                assert "✅ Successfully deleted schedule: schedule_123" in result.output
                # Should not show confirmation prompt
                assert "Are you sure" not in result.output

    def test_delete_schedule_command_cancelled_by_user(
        self, cli_runner, mock_google_ads_env
    ):
        """Test delete-schedule command cancelled by user."""
        with patch.dict(os.environ, mock_google_ads_env):
            with patch("paidsearchnav.scheduler.cli.SchedulerAPI") as mock_api_class:
                # Setup mocks
                mock_api = Mock()
                mock_scheduler = AsyncMock()

                # Mock existing schedule
                mock_schedule = Mock()
                mock_schedule.job_id = "schedule_123"
                mock_schedule.context = {"customer_id": "1234567890"}
                mock_schedule.trigger = {"expression": "0 0 1 */3 *"}

                mock_scheduler.list_scheduled_audits.return_value = [mock_schedule]
                mock_api._ensure_scheduler.return_value = mock_scheduler
                mock_api_class.return_value = mock_api

                # Run command and cancel
                result = cli_runner.invoke(
                    scheduler, ["delete-schedule", "schedule_123"], input="n\n"
                )

                # Verify
                assert result.exit_code == 0
                assert "Operation cancelled." in result.output
                # Should not call delete
                # Note: No need to assert on delete_schedule since user cancelled

    def test_delete_schedule_command_not_found(self, cli_runner, mock_google_ads_env):
        """Test delete-schedule command when schedule not found."""
        with patch.dict(os.environ, mock_google_ads_env):
            with patch("paidsearchnav.scheduler.cli.SchedulerAPI") as mock_api_class:
                # Setup mocks with no existing schedules
                mock_api = Mock()
                mock_scheduler = AsyncMock()
                mock_scheduler.list_scheduled_audits.return_value = []
                mock_api._ensure_scheduler.return_value = mock_scheduler
                mock_api_class.return_value = mock_api

                # Run command
                result = cli_runner.invoke(
                    scheduler, ["delete-schedule", "nonexistent_schedule", "--force"]
                )

                # Verify
                assert result.exit_code == 1
                assert "❌ Schedule nonexistent_schedule not found" in result.output

    def test_delete_schedule_command_delete_failed(
        self, cli_runner, mock_google_ads_env
    ):
        """Test delete-schedule command when deletion fails."""
        with patch.dict(os.environ, mock_google_ads_env):
            with patch("paidsearchnav.scheduler.cli.SchedulerAPI") as mock_api_class:
                # Setup mocks
                mock_api = Mock()
                mock_scheduler = AsyncMock()

                # Mock existing schedule
                mock_schedule = Mock()
                mock_schedule.job_id = "schedule_123"
                mock_schedule.context = {"customer_id": "1234567890"}
                mock_schedule.trigger = {"expression": "0 0 1 */3 *"}

                mock_scheduler.list_scheduled_audits.return_value = [mock_schedule]
                mock_api._ensure_scheduler.return_value = mock_scheduler
                # Mock delete_schedule response (async method) to fail
                mock_api.delete_schedule = AsyncMock(return_value={"success": False})
                mock_api_class.return_value = mock_api

                # Run command
                result = cli_runner.invoke(
                    scheduler, ["delete-schedule", "schedule_123", "--force"]
                )

                # Verify
                assert result.exit_code == 1
                assert "❌ Failed to delete schedule: Unknown error" in result.output

    def test_new_commands_error_handling(self, cli_runner, mock_google_ads_env):
        """Test error handling for new commands."""
        test_commands = [
            (["list-schedules"], "❌ Failed to list schedules:"),
            (["update-schedule", "test", "--enabled"], "❌ Failed to update schedule:"),
            (["delete-schedule", "test", "--force"], "❌ Failed to delete schedule:"),
        ]

        for command, error_message in test_commands:
            with patch.dict(os.environ, mock_google_ads_env):
                with patch(
                    "paidsearchnav.scheduler.cli.SchedulerAPI"
                ) as mock_api_class:
                    # Setup mock to raise error
                    mock_api = Mock()
                    mock_api._ensure_scheduler.side_effect = Exception("Test error")
                    mock_api_class.return_value = mock_api

                    # Run command
                    result = cli_runner.invoke(scheduler, command)

                    # Verify error handling
                    assert result.exit_code == 1
                    assert error_message in result.output
