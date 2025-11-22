"""Unit tests for basic audit functionality."""

from unittest.mock import Mock, patch

from basic_legent_audit import run_basic_audit, validate_api_config
from pydantic import SecretStr


class TestValidateApiConfig:
    """Test configuration validation."""

    def test_validate_api_config_missing_google_ads(self):
        """Test validation when google_ads config is missing."""
        settings = Mock()
        settings.google_ads = None

        errors = validate_api_config(settings)

        assert len(errors) == 1
        assert "Google Ads configuration section missing" in errors[0]

    def test_validate_api_config_missing_required_fields(self):
        """Test validation when required fields are missing."""
        settings = Mock()
        settings.google_ads = Mock()
        settings.google_ads.developer_token = None
        settings.google_ads.client_id = None
        settings.google_ads.client_secret = None
        settings.google_ads.refresh_token = None
        settings.google_ads.login_customer_id = None

        errors = validate_api_config(settings)

        assert (
            len(errors) >= 3
        )  # At least missing developer_token, client_id, client_secret
        assert any("developer_token" in error for error in errors)
        assert any("client_id" in error for error in errors)
        assert any("client_secret" in error for error in errors)

    def test_validate_api_config_invalid_developer_token(self):
        """Test validation of developer token format."""
        settings = Mock()
        settings.google_ads = Mock()
        settings.google_ads.developer_token = SecretStr("short")
        settings.google_ads.client_id = "test.apps.googleusercontent.com"
        settings.google_ads.client_secret = SecretStr("secret")
        settings.google_ads.refresh_token = SecretStr("token")
        settings.google_ads.login_customer_id = "1234567890"

        errors = validate_api_config(settings)

        assert any("Developer token appears invalid" in error for error in errors)

    def test_validate_api_config_invalid_client_id(self):
        """Test validation of client ID format."""
        settings = Mock()
        settings.google_ads = Mock()
        settings.google_ads.developer_token = SecretStr(
            "valid_developer_token_1234567890"
        )
        settings.google_ads.client_id = "invalid_client_id"
        settings.google_ads.client_secret = SecretStr("secret")
        settings.google_ads.refresh_token = SecretStr("token")
        settings.google_ads.login_customer_id = "1234567890"

        errors = validate_api_config(settings)

        assert any("Client ID format appears invalid" in error for error in errors)

    def test_validate_api_config_valid_configuration(self):
        """Test validation with valid configuration."""
        settings = Mock()
        settings.google_ads = Mock()
        settings.google_ads.developer_token = SecretStr(
            "valid_developer_token_that_is_long_enough_12345678901234567890"
        )
        settings.google_ads.client_id = "test.apps.googleusercontent.com"
        settings.google_ads.client_secret = SecretStr("secret")
        settings.google_ads.refresh_token = SecretStr("token")
        settings.google_ads.login_customer_id = "1234567890"

        errors = validate_api_config(settings)

        assert len(errors) == 0


class TestRunBasicAudit:
    """Test basic audit functionality."""

    @patch("basic_legent_audit.Settings")
    @patch("basic_legent_audit.validate_api_config")
    def test_run_basic_audit_config_validation_failure(
        self, mock_validate, mock_settings
    ):
        """Test audit fails when configuration validation fails."""
        mock_validate.return_value = ["Configuration error"]

        result = run_basic_audit()

        assert result is None
        mock_validate.assert_called_once()

    @patch("basic_legent_audit.Settings")
    @patch("basic_legent_audit.validate_api_config")
    @patch("os.getenv")
    def test_run_basic_audit_no_customer_id(
        self, mock_getenv, mock_validate, mock_settings
    ):
        """Test audit fails when no customer ID is provided."""
        mock_validate.return_value = []
        mock_getenv.return_value = None

        mock_settings_instance = Mock()
        mock_settings_instance.google_ads = Mock()
        mock_settings_instance.google_ads.login_customer_id = None
        mock_settings.from_env.return_value = mock_settings_instance

        result = run_basic_audit()

        assert result is None

    @patch("basic_legent_audit.Settings")
    @patch("basic_legent_audit.validate_api_config")
    @patch("basic_legent_audit.GoogleAdsClient")
    @patch("os.getenv")
    @patch("time.sleep")  # Mock sleep to speed up tests
    def test_run_basic_audit_success(
        self, mock_sleep, mock_getenv, mock_client_class, mock_validate, mock_settings
    ):
        """Test successful audit execution."""
        # Setup mocks
        mock_validate.return_value = []
        mock_getenv.side_effect = lambda key, default=None: {
            "PSN_AUDIT_CUSTOMER_ID": "1234567890",
            "PSN_AUDIT_CUSTOMER_NAME": "Test Customer",
        }.get(key, default)

        mock_settings_instance = Mock()
        mock_settings_instance.google_ads = Mock()
        mock_settings_instance.google_ads.developer_token.get_secret_value.return_value = "valid_developer_token_that_is_long_enough_12345678901234567890"
        mock_settings_instance.google_ads.client_id = "client_id"
        mock_settings_instance.google_ads.client_secret.get_secret_value.return_value = "client_secret"
        mock_settings_instance.google_ads.refresh_token.get_secret_value.return_value = "refresh_token"
        mock_settings_instance.google_ads.login_customer_id = "1884837039"
        mock_settings_instance.google_ads.api_version = "v20"
        mock_settings.from_env.return_value = mock_settings_instance

        # Mock Google Ads client
        mock_client = Mock()
        mock_client_class.load_from_dict.return_value = mock_client

        mock_ga_service = Mock()
        mock_client.get_service.return_value = mock_ga_service

        # Mock customer query response
        mock_customer_row = Mock()
        mock_customer_row.customer = Mock()
        mock_customer_row.customer.id = "1234567890"
        mock_customer_row.customer.descriptive_name = "Test Customer"
        mock_customer_row.customer.currency_code = "USD"
        mock_customer_row.customer.time_zone = "America/New_York"

        # Mock campaigns query response
        mock_campaign_row = Mock()
        mock_campaign_row.campaign = Mock()
        mock_campaign_row.campaign.id = "123"
        mock_campaign_row.campaign.name = "Test Campaign"
        mock_campaign_row.campaign.status.name = "ENABLED"
        mock_campaign_row.campaign.advertising_channel_type.name = "SEARCH"
        mock_campaign_row.metrics = Mock()
        mock_campaign_row.metrics.impressions = 1000
        mock_campaign_row.metrics.clicks = 50
        mock_campaign_row.metrics.cost_micros = 100000000  # $100
        mock_campaign_row.metrics.conversions = 5

        # Mock keywords query response
        mock_keyword_row = Mock()
        mock_keyword_row.campaign = Mock()
        mock_keyword_row.campaign.id = "123"
        mock_keyword_row.campaign.name = "Test Campaign"
        mock_keyword_row.ad_group = Mock()
        mock_keyword_row.ad_group.id = "456"
        mock_keyword_row.ad_group.name = "Test Ad Group"
        mock_keyword_row.ad_group_criterion = Mock()
        mock_keyword_row.ad_group_criterion.criterion_id = "789"
        mock_keyword_row.ad_group_criterion.keyword = Mock()
        mock_keyword_row.ad_group_criterion.keyword.text = "test keyword"
        mock_keyword_row.ad_group_criterion.keyword.match_type.name = "EXACT"
        mock_keyword_row.ad_group_criterion.status.name = "ENABLED"
        mock_keyword_row.metrics = Mock()
        mock_keyword_row.metrics.impressions = 100
        mock_keyword_row.metrics.clicks = 5
        mock_keyword_row.metrics.cost_micros = 10000000  # $10

        # Configure search responses
        mock_ga_service.search.side_effect = [
            [mock_customer_row],  # Customer query
            [mock_campaign_row],  # Campaigns query
            [mock_keyword_row],  # Keywords query
            [],  # Search terms query (empty)
        ]

        result = run_basic_audit("1234567890", "Test Customer")

        assert result is not None
        assert result["customer_id"] == "1234567890"
        assert result["customer_name"] == "Test Customer"
        assert len(result["campaigns"]) == 1
        assert len(result["keywords"]) == 1
        assert result["campaigns"][0]["name"] == "Test Campaign"
        assert result["keywords"][0]["keyword_text"] == "test keyword"

        # Verify API calls were made
        mock_client_class.load_from_dict.assert_called_once()
        mock_client.get_service.assert_called_once_with("GoogleAdsService")
        assert mock_ga_service.search.call_count >= 3

    @patch("basic_legent_audit.Settings")
    @patch("basic_legent_audit.validate_api_config")
    @patch("basic_legent_audit.GoogleAdsClient")
    @patch("os.getenv")
    def test_run_basic_audit_api_exception(
        self, mock_getenv, mock_client_class, mock_validate, mock_settings
    ):
        """Test audit handles API exceptions gracefully."""
        # Setup basic mocks
        mock_validate.return_value = []
        mock_getenv.side_effect = lambda key, default=None: {
            "PSN_AUDIT_CUSTOMER_ID": "1234567890",
            "PSN_AUDIT_CUSTOMER_NAME": "Test Customer",
        }.get(key, default)

        mock_settings_instance = Mock()
        mock_settings_instance.google_ads = Mock()
        mock_settings_instance.google_ads.developer_token.get_secret_value.return_value = "valid_developer_token_that_is_long_enough_12345678901234567890"
        mock_settings_instance.google_ads.client_id = "client_id"
        mock_settings_instance.google_ads.client_secret.get_secret_value.return_value = "client_secret"
        mock_settings_instance.google_ads.refresh_token.get_secret_value.return_value = "refresh_token"
        mock_settings_instance.google_ads.login_customer_id = "1884837039"
        mock_settings_instance.google_ads.api_version = "v20"
        mock_settings.from_env.return_value = mock_settings_instance

        # Mock client to raise exception
        mock_client = Mock()
        mock_client_class.load_from_dict.return_value = mock_client
        mock_client.get_service.side_effect = Exception("API Error")

        result = run_basic_audit("1234567890", "Test Customer")

        assert result is None
