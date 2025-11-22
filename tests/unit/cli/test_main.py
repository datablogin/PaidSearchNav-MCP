"""Tests for the main CLI entry point."""

import pytest
from click.testing import CliRunner

from paidsearchnav.cli.main import cli


@pytest.fixture
def cli_runner():
    """Create CLI runner for testing."""
    return CliRunner()


class TestMainCLI:
    """Test the main CLI functionality."""

    def test_cli_without_args_shows_usage(self, cli_runner):
        """Test that running CLI without arguments shows usage."""
        result = cli_runner.invoke(cli)

        # Click shows help when no command is provided
        assert result.exit_code == 2
        assert "Usage: cli [OPTIONS] COMMAND [ARGS]..." in result.output
        assert "Commands:" in result.output
        assert "auth" in result.output
        assert "scheduler" in result.output

    def test_cli_help_option(self, cli_runner):
        """Test that --help option works."""
        result = cli_runner.invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "PaidSearchNav - Google Ads Keyword Audit Tool" in result.output
        assert "Commands:" in result.output
        assert "auth" in result.output
        assert "scheduler" in result.output

    def test_cli_version_option(self, cli_runner):
        """Test that --version option shows version."""
        result = cli_runner.invoke(cli, ["--version"])

        assert result.exit_code == 0
        assert "PaidSearchNav, version" in result.output
        # Version pattern check instead of hardcoded version
        assert result.output.strip().startswith("PaidSearchNav, version")

    def test_invalid_command_shows_error(self, cli_runner):
        """Test that invalid command shows error."""
        result = cli_runner.invoke(cli, ["invalid-command"])

        assert result.exit_code == 2
        assert "Error: No such command 'invalid-command'" in result.output

    def test_auth_command_exists(self, cli_runner):
        """Test that auth command is registered."""
        result = cli_runner.invoke(cli, ["auth", "--help"])

        assert result.exit_code == 0
        assert "Authentication management" in result.output

    def test_scheduler_command_exists(self, cli_runner):
        """Test that scheduler command is registered."""
        result = cli_runner.invoke(cli, ["scheduler", "--help"])

        assert result.exit_code == 0
        assert "Manage audit scheduling" in result.output

    def test_accounts_command_registered(self, cli_runner):
        """Test that accounts command is now registered."""
        result = cli_runner.invoke(cli, ["accounts", "--help"])

        assert result.exit_code == 0
        assert "Manage Google Ads accounts and MCC hierarchy" in result.output

    def test_cli_subcommand_help(self, cli_runner):
        """Test that subcommand help works."""
        # Test auth subcommand help
        result = cli_runner.invoke(cli, ["auth", "--help"])
        assert result.exit_code == 0
        assert "Commands:" in result.output
        assert "login" in result.output

        # Test scheduler subcommand help
        result = cli_runner.invoke(cli, ["scheduler", "--help"])
        assert result.exit_code == 0
        assert "Commands:" in result.output
        assert "run" in result.output

    def test_cli_command_chaining(self, cli_runner):
        """Test that commands can be chained properly."""
        # Test that we can access nested commands
        result = cli_runner.invoke(cli, ["auth", "test-device-flow", "--help"])

        assert result.exit_code == 0
        assert "Test OAuth2 device flow authentication" in result.output

    def test_cli_error_handling(self, cli_runner):
        """Test CLI error handling for various scenarios."""
        # Test missing required options
        result = cli_runner.invoke(cli, ["auth", "login"])
        assert result.exit_code == 2
        assert "Missing option" in result.output

        # Test invalid options
        result = cli_runner.invoke(cli, ["--invalid-option"])
        assert result.exit_code == 2
        assert "No such option" in result.output


class TestCLIEnvironment:
    """Test CLI environment and configuration."""

    def test_cli_runs_without_env_vars(self, cli_runner):
        """Test that CLI can run without environment variables set."""
        # The CLI should still work for help commands even without config
        result = cli_runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "PaidSearchNav" in result.output

    def test_cli_version_independent_of_config(self, cli_runner):
        """Test that version command works regardless of configuration."""
        # Version should work even with no environment setup
        result = cli_runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "version" in result.output


class TestCLICommandGroups:
    """Test CLI command group functionality."""

    def test_command_groups_are_properly_registered(self, cli_runner):
        """Test that all command groups are properly registered."""
        from paidsearchnav.cli.main import cli as main_cli

        # Get registered commands
        commands = main_cli.commands

        # Check expected commands are present
        assert "auth" in commands
        assert "scheduler" in commands
        assert "accounts" in commands  # Now enabled

    def test_command_group_isolation(self, cli_runner):
        """Test that command groups are isolated from each other."""
        # Test that auth commands don't leak into scheduler
        result = cli_runner.invoke(cli, ["scheduler", "login"])
        assert result.exit_code == 2
        assert "No such command 'login'" in result.output

        # Test that scheduler commands don't leak into auth
        result = cli_runner.invoke(cli, ["auth", "run"])
        assert result.exit_code == 2
        assert "No such command 'run'" in result.output
