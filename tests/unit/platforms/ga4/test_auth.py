"""Unit tests for GA4 authentication module."""

from unittest.mock import Mock, patch

import pytest

from paidsearchnav_mcp.core.config import GA4Config
from paidsearchnav_mcp.platforms.ga4.auth import GA4AuthenticationError, GA4Authenticator


class TestGA4Authenticator:
    """Test GA4 authentication functionality."""

    @pytest.fixture
    def ga4_config(self):
        """Create test GA4 configuration."""
        return GA4Config(
            enabled=True,
            property_id="123456789",
            service_account_key_path="/path/to/key.json",
            use_application_default_credentials=True,
            requests_per_minute=10,
            requests_per_hour=600,
            requests_per_day=14400,
        )

    @pytest.fixture
    def ga4_config_minimal(self):
        """Create minimal GA4 configuration."""
        return GA4Config(
            enabled=True,
            property_id="123456789",
            use_application_default_credentials=True,
            requests_per_minute=10,
            requests_per_hour=600,
            requests_per_day=14400,
        )

    def test_init_without_ga4_api_raises_import_error(self):
        """Test that missing GA4 API library raises ImportError."""
        config = GA4Config(
            enabled=True,
            property_id="123456789",
            use_application_default_credentials=True,
            requests_per_minute=10,
            requests_per_hour=600,
            requests_per_day=14400,
        )

        with patch("paidsearchnav.platforms.ga4.auth.GA4_API_AVAILABLE", False):
            with pytest.raises(
                ImportError, match="Google Analytics Data API is required"
            ):
                GA4Authenticator(config)

    @patch("paidsearchnav.platforms.ga4.auth.GA4_API_AVAILABLE", True)
    def test_init_with_valid_config(self, ga4_config):
        """Test successful initialization with valid config."""
        authenticator = GA4Authenticator(ga4_config)
        assert authenticator.config == ga4_config
        assert authenticator._client is None

    @patch("paidsearchnav.platforms.ga4.auth.GA4_API_AVAILABLE", True)
    @patch("paidsearchnav.platforms.ga4.auth.BetaAnalyticsDataClient")
    @patch("paidsearchnav.platforms.ga4.auth.service_account")
    def test_get_client_with_service_account(
        self, mock_service_account, mock_client, ga4_config
    ):
        """Test client creation with service account credentials."""
        # Mock service account credentials
        mock_credentials = Mock()
        mock_service_account.Credentials.from_service_account_file.return_value = (
            mock_credentials
        )

        # Mock path exists
        with patch("pathlib.Path.exists", return_value=True):
            authenticator = GA4Authenticator(ga4_config)
            client = authenticator.get_client()

            # Verify service account was used
            mock_service_account.Credentials.from_service_account_file.assert_called_once_with(
                str(ga4_config.service_account_key_path),
                scopes=["https://www.googleapis.com/auth/analytics.readonly"],
            )

            # Verify client was created
            mock_client.assert_called_once()
            assert client is not None

    @patch("paidsearchnav.platforms.ga4.auth.GA4_API_AVAILABLE", True)
    @patch("paidsearchnav.platforms.ga4.auth.BetaAnalyticsDataClient")
    @patch("paidsearchnav.platforms.ga4.auth.default")
    def test_get_client_with_default_credentials(
        self, mock_default, mock_client, ga4_config_minimal
    ):
        """Test client creation with application default credentials."""
        # Mock default credentials
        mock_credentials = Mock()
        mock_default.return_value = (mock_credentials, "test-project")

        authenticator = GA4Authenticator(ga4_config_minimal)
        client = authenticator.get_client()

        # Verify default credentials were used
        mock_default.assert_called_once_with(
            scopes=["https://www.googleapis.com/auth/analytics.readonly"]
        )

        # Verify client was created
        mock_client.assert_called_once()
        assert client is not None

    @patch("paidsearchnav.platforms.ga4.auth.GA4_API_AVAILABLE", True)
    def test_get_client_with_missing_key_file_raises_error(self, ga4_config):
        """Test that missing service account key file raises error."""
        with patch("pathlib.Path.exists", return_value=False):
            authenticator = GA4Authenticator(ga4_config)

            with pytest.raises(
                GA4AuthenticationError, match="Service account key file not found"
            ):
                authenticator.get_client()

    @patch("paidsearchnav.platforms.ga4.auth.GA4_API_AVAILABLE", True)
    @patch("paidsearchnav.platforms.ga4.auth.default")
    def test_get_client_with_default_credentials_failure(
        self, mock_default, ga4_config_minimal
    ):
        """Test default credentials failure handling."""
        from paidsearchnav.platforms.ga4.auth import DefaultCredentialsError

        mock_default.side_effect = DefaultCredentialsError("No credentials found")

        authenticator = GA4Authenticator(ga4_config_minimal)

        with pytest.raises(
            GA4AuthenticationError,
            match="Application default credentials not available",
        ):
            authenticator.get_client()

    @patch("paidsearchnav.platforms.ga4.auth.GA4_API_AVAILABLE", True)
    @patch("paidsearchnav.platforms.ga4.auth.BetaAnalyticsDataClient")
    @patch("paidsearchnav.platforms.ga4.auth.service_account")
    def test_test_authentication_success(
        self, mock_service_account, mock_client, ga4_config
    ):
        """Test successful authentication test."""
        # Mock successful authentication and API call
        mock_credentials = Mock()
        mock_service_account.Credentials.from_service_account_file.return_value = (
            mock_credentials
        )

        mock_client_instance = Mock()
        mock_client.return_value = mock_client_instance
        mock_client_instance.run_report.return_value = Mock()

        with patch("pathlib.Path.exists", return_value=True):
            authenticator = GA4Authenticator(ga4_config)
            result = authenticator.test_authentication()

            assert result is True

    @patch("paidsearchnav.platforms.ga4.auth.GA4_API_AVAILABLE", True)
    @patch("paidsearchnav.platforms.ga4.auth.BetaAnalyticsDataClient")
    @patch("paidsearchnav.platforms.ga4.auth.service_account")
    def test_test_authentication_failure(
        self, mock_service_account, mock_client, ga4_config
    ):
        """Test authentication test failure handling."""
        # Mock authentication success but API call failure
        mock_credentials = Mock()
        mock_service_account.Credentials.from_service_account_file.return_value = (
            mock_credentials
        )

        mock_client_instance = Mock()
        mock_client.return_value = mock_client_instance
        mock_client_instance.run_report.side_effect = Exception("API call failed")

        with patch("pathlib.Path.exists", return_value=True):
            authenticator = GA4Authenticator(ga4_config)
            result = authenticator.test_authentication()

            assert result is False

    @patch("paidsearchnav.platforms.ga4.auth.GA4_API_AVAILABLE", True)
    @patch("paidsearchnav.platforms.ga4.auth.BetaAnalyticsDataClient")
    @patch("paidsearchnav.platforms.ga4.auth.service_account")
    def test_validate_property_access_success(
        self, mock_service_account, mock_client, ga4_config
    ):
        """Test successful property access validation."""
        # Mock successful authentication and metadata call
        mock_credentials = Mock()
        mock_service_account.Credentials.from_service_account_file.return_value = (
            mock_credentials
        )

        mock_client_instance = Mock()
        mock_client.return_value = mock_client_instance
        mock_client_instance.get_metadata.return_value = Mock()

        with patch("pathlib.Path.exists", return_value=True):
            authenticator = GA4Authenticator(ga4_config)
            result = authenticator.validate_property_access("123456789")

            assert result is True

    @patch("paidsearchnav.platforms.ga4.auth.GA4_API_AVAILABLE", True)
    @patch("paidsearchnav.platforms.ga4.auth.BetaAnalyticsDataClient")
    @patch("paidsearchnav.platforms.ga4.auth.service_account")
    def test_get_property_metadata_success(
        self, mock_service_account, mock_client, ga4_config
    ):
        """Test successful property metadata retrieval."""
        # Mock successful authentication and metadata call
        mock_credentials = Mock()
        mock_service_account.Credentials.from_service_account_file.return_value = (
            mock_credentials
        )

        mock_client_instance = Mock()
        mock_client.return_value = mock_client_instance

        # Mock metadata response
        mock_metadata = Mock()
        mock_metadata.dimensions = [
            Mock(
                api_name="country",
                ui_name="Country",
                description="User country",
                type_=Mock(name="DIMENSION_TYPE_STRING"),
            )
        ]
        mock_metadata.metrics = [
            Mock(
                api_name="sessions",
                ui_name="Sessions",
                description="Session count",
                type_=Mock(name="METRIC_TYPE_INTEGER"),
            )
        ]
        mock_client_instance.get_metadata.return_value = mock_metadata

        with patch("pathlib.Path.exists", return_value=True):
            authenticator = GA4Authenticator(ga4_config)
            metadata = authenticator.get_property_metadata("123456789")

            assert metadata is not None
            assert "dimensions" in metadata
            assert "metrics" in metadata
            assert len(metadata["dimensions"]) == 1
            assert len(metadata["metrics"]) == 1
            assert metadata["dimensions"][0]["api_name"] == "country"
            assert metadata["metrics"][0]["api_name"] == "sessions"


class TestGA4ConfigIntegration:
    """Test GA4Config integration with authentication."""

    def test_ga4_config_validation_invalid_property_id(self):
        """Test GA4Config validation with invalid property ID."""
        with pytest.raises(ValueError, match="GA4 property ID must be numeric"):
            GA4Config(
                enabled=True,
                property_id="invalid-id",
            )

    def test_ga4_config_validation_enabled_without_property_id(self):
        """Test GA4Config validation when enabled without property ID."""
        with pytest.raises(
            ValueError, match="property_id is required when GA4 is enabled"
        ):
            GA4Config(enabled=True, property_id="")

    def test_ga4_config_validation_no_auth_methods(self):
        """Test GA4Config validation with no authentication methods."""
        with pytest.raises(
            ValueError, match="At least one authentication method must be configured"
        ):
            GA4Config(
                enabled=True,
                property_id="123456789",
                service_account_key_path=None,
                use_application_default_credentials=False,
            )

    def test_ga4_config_validation_cost_controls(self):
        """Test GA4Config cost control validation."""
        with pytest.raises(
            ValueError,
            match="daily_cost_limit_usd must be greater than cost_alert_threshold_usd",
        ):
            GA4Config(
                enabled=True,
                property_id="123456789",
                daily_cost_limit_usd=10.0,
                cost_alert_threshold_usd=20.0,
            )

    def test_ga4_config_validation_rate_limits(self):
        """Test GA4Config rate limit validation."""
        with pytest.raises(ValueError, match="Rate limit inconsistency"):
            GA4Config(
                enabled=True,
                property_id="123456789",
                requests_per_minute=1000,
                requests_per_hour=500,  # Invalid: minute * 60 > hour
            )

    def test_ga4_config_valid_configuration(self):
        """Test valid GA4Config passes validation."""
        config = GA4Config(
            enabled=True,
            property_id="123456789",
            service_account_key_path="/path/to/key.json",
            daily_cost_limit_usd=100.0,
            cost_alert_threshold_usd=80.0,
            requests_per_minute=10,
            requests_per_hour=600,
            requests_per_day=14400,  # 600 * 24 = 14400
        )

        # Should not raise any validation errors
        assert config.enabled is True
        assert config.property_id == "123456789"
