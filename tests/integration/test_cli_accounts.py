"""Integration tests for account management CLI commands."""

import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner

from paidsearchnav.cli.accounts import accounts
from paidsearchnav.core.models.account import (
    Account,
    AccountHierarchy,
    AccountStatus,
    AccountType,
    AuditOptInStatus,
    SyncResult,
)


@pytest.fixture
def runner():
    """Create a CLI runner."""
    return CliRunner()


@pytest.fixture
def mock_settings():
    """Create mock settings."""
    settings = MagicMock()
    settings.data_directory = "/tmp/test_data"
    settings.google_ads = MagicMock()
    settings.google_ads.developer_token = MagicMock()
    settings.google_ads.developer_token.get_secret_value.return_value = "dev-token"
    settings.google_ads.client_id = "client-id"
    settings.google_ads.client_secret = MagicMock()
    settings.google_ads.client_secret.get_secret_value.return_value = "client-secret"
    return settings


@pytest.fixture
def sample_account_hierarchy():
    """Create sample account hierarchy."""
    accounts = {
        "1234567890": Account(
            customer_id="1234567890",
            name="Test MCC Account",
            account_type=AccountType.MCC,
            status=AccountStatus.ENABLED,
            audit_status=AuditOptInStatus.PENDING,
            is_mcc=True,
            can_manage_clients=True,
            accessible=True,
        ),
        "2345678901": Account(
            customer_id="2345678901",
            name="Test Standard Account 1",
            account_type=AccountType.STANDARD,
            status=AccountStatus.ENABLED,
            audit_status=AuditOptInStatus.OPT_IN,
            manager_customer_id="1234567890",
            accessible=True,
            audit_settings={
                "include_search": True,
                "include_pmax": True,
                "include_shopping": False,
                "include_display": False,
                "include_video": False,
            },
        ),
        "3456789012": Account(
            customer_id="3456789012",
            name="Test Standard Account 2",
            account_type=AccountType.STANDARD,
            status=AccountStatus.PAUSED,
            audit_status=AuditOptInStatus.OPT_OUT,
            manager_customer_id="1234567890",
            accessible=True,
        ),
    }

    return AccountHierarchy(
        root_customer_id="1234567890",
        accounts=accounts,
        last_sync=datetime.utcnow(),
    )


class TestAccountsListCommand:
    """Test accounts list command."""

    @patch("paidsearchnav.cli.accounts.Settings")
    @patch("paidsearchnav.cli.accounts.AnalysisRepository")
    @patch("paidsearchnav.cli.accounts.AccountRepository")
    def test_list_accounts_no_stored_hierarchy(
        self,
        mock_account_repo_class,
        mock_analysis_repo_class,
        mock_settings_class,
        runner,
    ):
        """Test listing accounts when no hierarchy is stored."""
        # Setup mocks
        mock_settings_class.return_value = MagicMock()
        mock_account_repo = AsyncMock()
        mock_account_repo.get_account_hierarchy.return_value = None
        mock_account_repo_class.return_value = mock_account_repo

        # Run command
        result = runner.invoke(accounts, ["list"])

        # Verify
        assert result.exit_code == 0
        assert "No root MCC specified" in result.output

    @patch("paidsearchnav.cli.accounts.Settings")
    @patch("paidsearchnav.cli.accounts.AnalysisRepository")
    @patch("paidsearchnav.cli.accounts.AccountRepository")
    def test_list_accounts_with_stored_hierarchy(
        self,
        mock_account_repo_class,
        mock_analysis_repo_class,
        mock_settings_class,
        runner,
        sample_account_hierarchy,
    ):
        """Test listing accounts with stored hierarchy."""
        # Setup mocks
        mock_settings_class.return_value = MagicMock()
        mock_account_repo = AsyncMock()
        mock_account_repo.get_account_hierarchy.return_value = sample_account_hierarchy
        mock_account_repo_class.return_value = mock_account_repo

        # Run command
        result = runner.invoke(accounts, ["list"])

        # Verify
        assert result.exit_code == 0
        assert "1234567890" in result.output
        assert "Test MCC Account" in result.output
        assert "Test Standard Account 1" in result.output
        assert "Total accounts: 3" in result.output
        assert "MCC accounts: 1" in result.output
        assert "Opted in for audit: 1" in result.output

    @patch("paidsearchnav.cli.accounts.Settings")
    @patch("paidsearchnav.cli.accounts.AnalysisRepository")
    @patch("paidsearchnav.cli.accounts.AccountRepository")
    @patch("paidsearchnav.cli.accounts.OAuth2TokenManager")
    @patch("paidsearchnav.cli.accounts.AccountMapper")
    def test_list_accounts_refresh_from_api(
        self,
        mock_mapper_class,
        mock_oauth_class,
        mock_account_repo_class,
        mock_analysis_repo_class,
        mock_settings_class,
        runner,
        mock_settings,
        sample_account_hierarchy,
    ):
        """Test refreshing account list from API."""
        # Setup mocks
        mock_settings_class.return_value = mock_settings

        mock_oauth = MagicMock()
        mock_oauth.has_valid_tokens.return_value = True
        mock_oauth.get_credentials.return_value = MagicMock(
            refresh_token="refresh-token"
        )
        mock_oauth_class.return_value = mock_oauth

        mock_mapper = AsyncMock()
        sync_result = SyncResult(
            success=True,
            hierarchy=sample_account_hierarchy,
            accounts_synced=3,
            errors=[],
            sync_duration_seconds=1.5,
            timestamp=datetime.utcnow(),
        )
        mock_mapper.sync_account_hierarchy.return_value = sync_result
        mock_mapper_class.return_value = mock_mapper

        mock_account_repo = AsyncMock()
        mock_account_repo.save_account_hierarchy.return_value = True
        mock_account_repo.save_sync_history.return_value = True
        mock_account_repo_class.return_value = mock_account_repo

        # Run command
        result = runner.invoke(
            accounts, ["list", "--root-mcc", "1234567890", "--refresh"]
        )

        # Verify
        assert result.exit_code == 0
        assert "Fetching accounts from Google Ads API" in result.output
        assert "✓ Synced 3 accounts" in result.output
        assert "1234567890" in result.output


class TestAccountsSetAuditStatusCommand:
    """Test accounts set-audit-status command."""

    @patch("paidsearchnav.cli.accounts.Settings")
    @patch("paidsearchnav.cli.accounts.AnalysisRepository")
    @patch("paidsearchnav.cli.accounts.AccountRepository")
    def test_set_audit_status_opt_in(
        self,
        mock_account_repo_class,
        mock_analysis_repo_class,
        mock_settings_class,
        runner,
    ):
        """Test setting audit status to opt-in."""
        # Setup mocks
        mock_settings_class.return_value = MagicMock()
        mock_account_repo = AsyncMock()
        mock_account_repo.update_audit_status.return_value = True
        mock_account_repo_class.return_value = mock_account_repo

        # Run command
        result = runner.invoke(
            accounts, ["set-audit-status", "1234567890", "--status", "opt-in"]
        )

        # Verify
        assert result.exit_code == 0
        assert "✓ Updated audit status for 1234567890 to opt-in" in result.output

        # Check call arguments
        mock_account_repo.update_audit_status.assert_called_once()
        call_args = mock_account_repo.update_audit_status.call_args
        assert call_args[0][0] == "1234567890"
        assert call_args[0][1].value == "opt-in"

    @patch("paidsearchnav.cli.accounts.Settings")
    @patch("paidsearchnav.cli.accounts.AnalysisRepository")
    @patch("paidsearchnav.cli.accounts.AccountRepository")
    def test_set_audit_status_with_campaign_types(
        self,
        mock_account_repo_class,
        mock_analysis_repo_class,
        mock_settings_class,
        runner,
    ):
        """Test setting audit status with specific campaign types."""
        # Setup mocks
        mock_settings_class.return_value = MagicMock()
        mock_account_repo = AsyncMock()
        mock_account_repo.update_audit_status.return_value = True
        mock_account_repo_class.return_value = mock_account_repo

        # Run command
        result = runner.invoke(
            accounts,
            [
                "set-audit-status",
                "1234567890",
                "--status",
                "opt-in",
                "--search",
                "--pmax",
                "--no-shopping",
                "--no-display",
                "--no-video",
            ],
        )

        # Verify
        assert result.exit_code == 0
        assert "✓ Updated audit status for 1234567890 to opt-in" in result.output

        # Check audit settings
        call_args = mock_account_repo.update_audit_status.call_args
        audit_settings = call_args[0][2]
        assert audit_settings["include_search"] is True
        assert audit_settings["include_pmax"] is True
        assert audit_settings["include_shopping"] is False


class TestAccountsShowOptedInCommand:
    """Test accounts show-opted-in command."""

    @patch("paidsearchnav.cli.accounts.Settings")
    @patch("paidsearchnav.cli.accounts.AnalysisRepository")
    @patch("paidsearchnav.cli.accounts.AccountRepository")
    def test_show_opted_in_table_format(
        self,
        mock_account_repo_class,
        mock_analysis_repo_class,
        mock_settings_class,
        runner,
        sample_account_hierarchy,
    ):
        """Test showing opted-in accounts in table format."""
        # Setup mocks
        mock_settings_class.return_value = MagicMock()
        mock_account_repo = AsyncMock()
        opted_in = [
            acc
            for acc in sample_account_hierarchy.accounts.values()
            if acc.audit_status == AuditOptInStatus.OPT_IN
        ]
        mock_account_repo.get_opted_in_accounts.return_value = opted_in
        mock_account_repo_class.return_value = mock_account_repo

        # Run command
        result = runner.invoke(accounts, ["show-opted-in", "--format", "table"])

        # Verify
        assert result.exit_code == 0
        assert "2345678901" in result.output
        assert "Test Standard Account 1" in result.output
        assert "search, pmax" in result.output
        assert "Total opted-in accounts: 1" in result.output

    @patch("paidsearchnav.cli.accounts.Settings")
    @patch("paidsearchnav.cli.accounts.AnalysisRepository")
    @patch("paidsearchnav.cli.accounts.AccountRepository")
    def test_show_opted_in_json_format(
        self,
        mock_account_repo_class,
        mock_analysis_repo_class,
        mock_settings_class,
        runner,
        sample_account_hierarchy,
    ):
        """Test showing opted-in accounts in JSON format."""
        # Setup mocks
        mock_settings_class.return_value = MagicMock()
        mock_account_repo = AsyncMock()
        opted_in = [
            acc
            for acc in sample_account_hierarchy.accounts.values()
            if acc.audit_status == AuditOptInStatus.OPT_IN
        ]
        mock_account_repo.get_opted_in_accounts.return_value = opted_in
        mock_account_repo_class.return_value = mock_account_repo

        # Run command
        result = runner.invoke(accounts, ["show-opted-in", "--format", "json"])

        # Verify
        assert result.exit_code == 0
        # Parse JSON output
        output_data = json.loads(result.output)
        assert len(output_data) == 1
        assert output_data[0]["customer_id"] == "2345678901"
        assert output_data[0]["audit_settings"]["include_search"] is True


class TestAccountsShowDetailsCommand:
    """Test accounts show-details command."""

    @patch("paidsearchnav.cli.accounts.Settings")
    @patch("paidsearchnav.cli.accounts.AnalysisRepository")
    @patch("paidsearchnav.cli.accounts.AccountRepository")
    def test_show_details_existing_account(
        self,
        mock_account_repo_class,
        mock_analysis_repo_class,
        mock_settings_class,
        runner,
        sample_account_hierarchy,
    ):
        """Test showing details for existing account."""
        # Setup mocks
        mock_settings_class.return_value = MagicMock()
        mock_account_repo = AsyncMock()
        account = sample_account_hierarchy.accounts["2345678901"]
        mock_account_repo.get_account.return_value = account
        mock_account_repo_class.return_value = mock_account_repo

        # Run command
        result = runner.invoke(accounts, ["show-details", "2345678901"])

        # Verify
        assert result.exit_code == 0
        assert "Account Details: Test Standard Account 1" in result.output
        assert "Customer ID:        2345678901" in result.output
        assert "Account Type:       STANDARD" in result.output
        assert "Audit Status:       opt-in" in result.output
        assert "Manager Account:    1234567890" in result.output
        assert "Search          ✓" in result.output
        assert "Pmax            ✓" in result.output
        assert "Shopping        ✗" in result.output

    @patch("paidsearchnav.cli.accounts.Settings")
    @patch("paidsearchnav.cli.accounts.AnalysisRepository")
    @patch("paidsearchnav.cli.accounts.AccountRepository")
    def test_show_details_nonexistent_account(
        self,
        mock_account_repo_class,
        mock_analysis_repo_class,
        mock_settings_class,
        runner,
    ):
        """Test showing details for nonexistent account."""
        # Setup mocks
        mock_settings_class.return_value = MagicMock()
        mock_account_repo = AsyncMock()
        mock_account_repo.get_account.return_value = None
        mock_account_repo_class.return_value = mock_account_repo

        # Run command
        result = runner.invoke(accounts, ["show-details", "9999999999"])

        # Verify
        assert result.exit_code == 0
        assert "Account 9999999999 not found" in result.output
        assert "Run 'accounts list' to sync accounts" in result.output
