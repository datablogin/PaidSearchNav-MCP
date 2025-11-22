"""Test CLI configuration loading improvements."""

from unittest.mock import Mock, patch

import pytest
from click.testing import CliRunner

from paidsearchnav_mcp.cli.utils import (
    CLIConfigurationError,
    get_settings_safely,
    validate_customer_id,
)


class TestCLIImprovementsIntegration:
    """Test the CLI improvements integration."""

    def setup_method(self):
        """Set up test environment."""
        self.runner = CliRunner()

    def test_cli_modules_use_get_settings_safely(self):
        """Test that CLI modules use get_settings_safely instead of Settings.from_env()."""
        import inspect

        import paidsearchnav.cli.accounts
        import paidsearchnav.cli.recommendations
        import paidsearchnav.cli.reports

        modules_to_check = [
            paidsearchnav.cli.accounts,
            paidsearchnav.cli.reports,
            paidsearchnav.cli.recommendations,
        ]

        for module in modules_to_check:
            source = inspect.getsource(module)

            # Should import get_settings_safely
            assert "get_settings_safely" in source, (
                f"Module {module.__name__} should import get_settings_safely"
            )

            # Should use get_settings_safely()
            get_settings_calls = source.count("get_settings_safely()")
            assert get_settings_calls > 0, (
                f"Module {module.__name__} should use get_settings_safely()"
            )

    def test_geo_module_uses_create_google_ads_client(self):
        """Test that geo module uses create_google_ads_client."""
        import inspect

        import paidsearchnav.cli.geo

        source = inspect.getsource(paidsearchnav.cli.geo)

        # Should import create_google_ads_client
        assert "create_google_ads_client" in source, (
            "geo module should import create_google_ads_client"
        )

    def test_cli_modules_import_validation_functions(self):
        """Test that CLI modules import validation functions."""
        import inspect

        import paidsearchnav.cli.accounts
        import paidsearchnav.cli.geo

        # Accounts should import validate_customer_id
        accounts_source = inspect.getsource(paidsearchnav.cli.accounts)
        assert "validate_customer_id" in accounts_source, (
            "accounts module should import validate_customer_id"
        )

        # Geo should import validate_customer_id
        geo_source = inspect.getsource(paidsearchnav.cli.geo)
        assert "validate_customer_id" in geo_source, (
            "geo module should import validate_customer_id"
        )

    def test_cli_modules_import_error_handling(self):
        """Test that CLI modules import error handling decorators."""
        import inspect

        import paidsearchnav.cli.accounts
        import paidsearchnav.cli.geo

        # Should import handle_common_cli_errors
        accounts_source = inspect.getsource(paidsearchnav.cli.accounts)
        assert "handle_common_cli_errors" in accounts_source, (
            "accounts module should import handle_common_cli_errors"
        )

        geo_source = inspect.getsource(paidsearchnav.cli.geo)
        assert "handle_common_cli_errors" in geo_source, (
            "geo module should import handle_common_cli_errors"
        )

    def test_utilities_are_available(self):
        """Test that all utility functions are available."""
        # Test that we can import all utilities
        from paidsearchnav.cli.utils import (
            create_google_ads_client,
            format_cli_error,
            format_cli_success,
            format_cli_warning,
            get_settings_safely,
            handle_common_cli_errors,
            validate_customer_id,
        )

        # Test that they're callable
        assert callable(get_settings_safely)
        assert callable(create_google_ads_client)
        assert callable(validate_customer_id)
        assert callable(handle_common_cli_errors)
        assert callable(format_cli_success)
        assert callable(format_cli_warning)
        assert callable(format_cli_error)

    @pytest.mark.parametrize(
        "customer_id,expected",
        [
            ("1234567890", "1234567890"),
            ("123-456-7890", "1234567890"),
            (" 123 456 7890 ", "1234567890"),
        ],
    )
    def test_customer_id_validation_integration(self, customer_id, expected):
        """Test customer ID validation integration."""
        result = validate_customer_id(customer_id)
        assert result == expected

    def test_cli_configuration_error_integration(self):
        """Test CLIConfigurationError integration."""
        error = CLIConfigurationError("Test error", "Test suggestion")
        assert "Test error" in str(error)
        assert "💡 Test suggestion" in str(error)

    @patch("paidsearchnav.cli.utils.Settings.from_env")
    def test_get_settings_safely_integration(self, mock_from_env):
        """Test get_settings_safely integration."""
        from paidsearchnav.core.config import Settings

        mock_settings = Mock(spec=Settings)
        mock_settings.validate_required_settings = Mock()
        mock_from_env.return_value = mock_settings

        result = get_settings_safely()

        assert result == mock_settings
        mock_from_env.assert_called_once()
        mock_settings.validate_required_settings.assert_called_once()

    @patch("paidsearchnav.cli.utils.get_settings_safely")
    def test_create_google_ads_client_integration(self, mock_get_settings):
        """Test create_google_ads_client integration."""
        from paidsearchnav.core.config import Settings

        mock_settings = Mock(spec=Settings)
        mock_settings.google_ads = None
        mock_get_settings.return_value = mock_settings

        with pytest.raises(CLIConfigurationError) as exc_info:
            from paidsearchnav.cli.utils import create_google_ads_client

            create_google_ads_client()

        assert "Google Ads configuration not found" in str(exc_info.value)

    def test_all_cli_modules_avoid_direct_settings_usage(self):
        """Test that all CLI modules avoid using Settings() directly."""
        import inspect

        import paidsearchnav.cli.accounts
        import paidsearchnav.cli.geo
        import paidsearchnav.cli.recommendations
        import paidsearchnav.cli.reports

        modules_to_check = [
            paidsearchnav.cli.accounts,
            paidsearchnav.cli.geo,
            paidsearchnav.cli.reports,
            paidsearchnav.cli.recommendations,
        ]

        for module in modules_to_check:
            source = inspect.getsource(module)

            # Should not use Settings() directly
            direct_settings_calls = source.count("Settings()")
            assert direct_settings_calls == 0, (
                f"Module {module.__name__} should not use Settings() directly. "
                f"Found {direct_settings_calls} occurrences."
            )
