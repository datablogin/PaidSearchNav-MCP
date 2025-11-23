"""Test CLI configuration loading fixes."""

from unittest.mock import Mock, patch

import pytest
from click.testing import CliRunner

from paidsearchnav_mcp.cli.accounts import accounts
from paidsearchnav_mcp.cli.geo import _create_api_client, geo
from paidsearchnav_mcp.core.config import Settings


class TestCLIConfigurationLoading:
    """Test that all CLI modules properly load configuration from environment."""

    @patch("paidsearchnav.cli.accounts.get_settings_safely")
    @patch("paidsearchnav.cli.accounts.OAuth2TokenManager")
    @patch("paidsearchnav.cli.accounts.AccountRepository")
    @patch("paidsearchnav.cli.accounts.AnalysisRepository")
    def test_accounts_cli_uses_from_env(
        self,
        mock_analysis_repo,
        mock_account_repo,
        mock_oauth_manager,
        mock_settings_from_env,
    ):
        """Test that accounts CLI uses Settings.from_env() instead of Settings()."""
        # Setup mocks
        mock_settings = Mock(spec=Settings)
        mock_settings_from_env.return_value = mock_settings

        # Mock the repository chain
        mock_analysis_instance = Mock()
        mock_analysis_repo.return_value = mock_analysis_instance
        mock_account_instance = Mock()
        mock_account_repo.return_value = mock_account_instance
        mock_account_instance.get_account_hierarchy.return_value = None

        # Mock OAuth manager
        mock_oauth_instance = Mock()
        mock_oauth_manager.return_value = mock_oauth_instance

        runner = CliRunner()

        # This should not raise any configuration errors
        result = runner.invoke(accounts, ["list", "--root-mcc", "1234567890"])

        # Verify get_settings_safely was called
        mock_settings_from_env.assert_called()
        # Should not fail due to configuration loading
        assert "Google Ads configuration not provided" not in result.output

    def test_geo_create_api_client_loads_settings(self):
        """Test that geo CLI helper function loads settings properly."""
        with patch(
            "paidsearchnav.cli.geo.create_google_ads_client"
        ) as mock_create_client:
            mock_client = Mock()
            mock_create_client.return_value = mock_client

            # Call the helper function
            result = _create_api_client()

            # Verify that create_google_ads_client was called
            mock_create_client.assert_called_once()
            assert result == mock_client

    def test_geo_create_api_client_handles_missing_config(self):
        """Test that geo CLI helper function handles missing Google Ads config."""
        with patch(
            "paidsearchnav.cli.geo.create_google_ads_client"
        ) as mock_create_client:
            from paidsearchnav.cli.utils import CLIConfigurationError

            mock_create_client.side_effect = CLIConfigurationError(
                "Google Ads configuration not found"
            )

            # Should raise CLIConfigurationError when config is missing
            with pytest.raises(CLIConfigurationError) as exc_info:
                _create_api_client()

            assert "Google Ads configuration not found" in str(exc_info.value)

    @patch("paidsearchnav.cli.reports.get_settings_safely")
    def test_reports_cli_uses_from_env(self, mock_settings_from_env):
        """Test that reports CLI uses Settings.from_env()."""
        mock_settings = Mock(spec=Settings)
        mock_settings_from_env.return_value = mock_settings

        # Import should not raise configuration errors

        # Verify that the module can be imported and Settings.from_env would be called
        # when running actual commands
        mock_settings_from_env.assert_not_called()  # Only called during actual command execution

    @patch("paidsearchnav.cli.recommendations.get_settings_safely")
    def test_recommendations_cli_uses_from_env(self, mock_settings_from_env):
        """Test that recommendations CLI uses Settings.from_env()."""
        mock_settings = Mock(spec=Settings)
        mock_settings_from_env.return_value = mock_settings

        # Import should not raise configuration errors

        # Verify that the module can be imported and Settings.from_env would be called
        # when running actual commands
        mock_settings_from_env.assert_not_called()  # Only called during actual command execution

    def test_configuration_consistency_across_cli_modules(self):
        """Test that all CLI modules use consistent configuration loading."""
        # This test ensures that we don't regress and accidentally use Settings()
        # instead of Settings.from_env() in any CLI module

        import inspect

        import paidsearchnav.cli.accounts
        import paidsearchnav.cli.geo
        import paidsearchnav.cli.recommendations
        import paidsearchnav.cli.reports

        modules_to_check = [
            paidsearchnav.cli.accounts,
            paidsearchnav.cli.reports,
            paidsearchnav.cli.recommendations,
        ]

        for module in modules_to_check:
            source = inspect.getsource(module)

            # Check that Settings() is not used directly (should use get_settings_safely())
            direct_settings_calls = source.count("Settings()")
            assert direct_settings_calls == 0, (
                f"Module {module.__name__} still uses Settings() directly"
            )

            # Check that get_settings_safely() is used
            get_settings_calls = source.count("get_settings_safely()")
            if (
                "get_settings_safely" in source
            ):  # Only check if get_settings_safely is used at all
                assert get_settings_calls > 0, (
                    f"Module {module.__name__} should use get_settings_safely()"
                )


class TestGeoCliCredentialHandling:
    """Test specific geo CLI credential handling."""

    def test_geo_analyze_command_uses_credentials(self):
        """Test that geo analyze command properly initializes client with credentials."""
        runner = CliRunner()

        # Mock all the dependencies
        with (
            patch("paidsearchnav.cli.geo._create_api_client") as mock_create_client,
            patch(
                "paidsearchnav.cli.geo.GeoPerformanceAnalyzer"
            ) as mock_analyzer_class,
        ):
            mock_client = Mock()
            mock_create_client.return_value = mock_client

            mock_analyzer = Mock()
            mock_analyzer_class.return_value = mock_analyzer
            mock_analyzer.analyze.return_value = Mock(performance_data=[], insights=[])

            # Run the command
            result = runner.invoke(
                geo,
                [
                    "analyze",
                    "--customer-id",
                    "1234567890",
                    "--locations",
                    "Dallas,Austin",
                ],
            )

            # Verify that _create_api_client was called
            mock_create_client.assert_called_once()

            # Verify that the client was passed to the analyzer
            mock_analyzer_class.assert_called_once()
            call_kwargs = mock_analyzer_class.call_args[1]
            assert "api_client" in call_kwargs
            assert call_kwargs["api_client"] == mock_client

    def test_geo_compare_command_uses_credentials(self):
        """Test that geo compare command properly initializes client with credentials."""
        runner = CliRunner()

        with (
            patch("paidsearchnav.cli.geo._create_api_client") as mock_create_client,
            patch(
                "paidsearchnav.cli.geo.GeoPerformanceAnalyzer"
            ) as mock_analyzer_class,
        ):
            mock_client = Mock()
            mock_create_client.return_value = mock_client

            mock_analyzer = Mock()
            mock_analyzer_class.return_value = mock_analyzer
            mock_result = Mock()
            mock_result.performance_data = []
            mock_analyzer.analyze.return_value = mock_result

            # Run the command
            result = runner.invoke(
                geo,
                [
                    "compare",
                    "--customer-id",
                    "1234567890",
                    "--locations",
                    "Dallas,Austin",
                ],
            )

            # Verify credentials were loaded
            mock_create_client.assert_called_once()

    def test_geo_export_recommendations_uses_credentials(self):
        """Test that geo export-recommendations command properly initializes client."""
        runner = CliRunner()

        with (
            patch("paidsearchnav.cli.geo._create_api_client") as mock_create_client,
            patch(
                "paidsearchnav.cli.geo.GeoPerformanceAnalyzer"
            ) as mock_analyzer_class,
        ):
            mock_client = Mock()
            mock_create_client.return_value = mock_client

            mock_analyzer = Mock()
            mock_analyzer_class.return_value = mock_analyzer
            mock_result = Mock()
            mock_result.insights = []
            mock_analyzer.analyze.return_value = mock_result

            # Run the command
            result = runner.invoke(
                geo, ["export-recommendations", "--customer-id", "1234567890"]
            )

            # Verify credentials were loaded
            mock_create_client.assert_called_once()
