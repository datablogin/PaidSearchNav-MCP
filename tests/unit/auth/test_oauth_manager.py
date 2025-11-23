"""Tests for OAuth2 manager for API integrations."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from google.oauth2.credentials import Credentials

from paidsearchnav_mcp.auth.oauth_manager import (
    ConsentFlow,
    OAuth2Manager,
    WorkflowTokenData,
)
from paidsearchnav_mcp.core.config import GoogleAdsConfig, Settings
from paidsearchnav_mcp.core.exceptions import AuthenticationError, ConfigurationError
from paidsearchnav_mcp.platforms.google.auth import TokenData


@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    google_ads = GoogleAdsConfig(
        developer_token="test_dev_token",
        client_id="test_client_id",
        client_secret="test_client_secret",
    )
    return Settings(google_ads=google_ads)


@pytest.fixture
def mock_token_manager():
    """Create mock token manager."""
    mock = MagicMock()
    mock.storage = MagicMock()
    return mock


@pytest.fixture
def oauth_manager(mock_settings, mock_token_manager):
    """Create OAuth2 manager for testing."""
    with patch(
        "paidsearchnav.auth.oauth_manager.OAuth2TokenManager",
        return_value=mock_token_manager,
    ):
        return OAuth2Manager(mock_settings)


@pytest.fixture
def sample_token_data():
    """Create sample token data."""
    return TokenData(
        access_token="test_access_token",
        refresh_token="test_refresh_token",
        client_id="test_client_id",
        client_secret="test_client_secret",
        expiry=datetime.utcnow() + timedelta(hours=1),
    )


@pytest.fixture
def sample_workflow_tokens():
    """Create sample workflow token data."""
    return WorkflowTokenData(
        customer_id="1234567890",
        access_token="test_access_token",
        refresh_token="test_refresh_token",
        client_id="test_client_id",
        client_secret="test_client_secret",
        expiry=datetime.utcnow() + timedelta(hours=1),
        permissions=["write_campaigns", "write_keywords"],
    )


class TestOAuth2Manager:
    """Test OAuth2Manager functionality."""

    def test_init_without_google_ads_config(self):
        """Test initialization without Google Ads configuration."""
        settings = Settings()
        with pytest.raises(
            ConfigurationError, match="Google Ads configuration not provided"
        ):
            OAuth2Manager(settings)

    async def test_initiate_consent_flow(self, oauth_manager):
        """Test initiating OAuth2 consent flow."""
        customer_id = "1234567890"
        permissions = ["write_campaigns", "write_keywords"]
        user_info = {"ip_address": "127.0.0.1"}

        with patch("google_auth_oauthlib.flow.InstalledAppFlow") as mock_flow_class:
            mock_flow = MagicMock()
            mock_flow.authorization_url.return_value = ("http://auth.url", "state")
            mock_flow_class.from_client_config.return_value = mock_flow

            flow = await oauth_manager.initiate_consent_flow(
                customer_id, permissions, user_info
            )

            assert isinstance(flow, ConsentFlow)
            assert flow.customer_id == customer_id
            assert flow.requested_permissions == permissions
            assert flow.user_info == user_info
            assert flow.authorization_url == "http://auth.url"
            assert flow.flow_id in oauth_manager._active_flows

    async def test_handle_oauth_callback_success(self, oauth_manager, mock_settings):
        """Test successful OAuth callback handling."""
        # Setup active flow
        flow = ConsentFlow(
            customer_id="1234567890",
            requested_permissions=["write_campaigns"],
            state="test_state",
        )
        oauth_manager._active_flows[flow.flow_id] = flow

        mock_creds = MagicMock(spec=Credentials)
        mock_creds.token = "access_token"
        mock_creds.refresh_token = "refresh_token"
        mock_creds.token_uri = "https://oauth2.googleapis.com/token"
        mock_creds.scopes = ["https://www.googleapis.com/auth/adwords"]
        mock_creds.expiry = datetime.utcnow() + timedelta(hours=1)

        with patch("google_auth_oauthlib.flow.InstalledAppFlow") as mock_flow_class:
            mock_flow = MagicMock()
            mock_flow.credentials = mock_creds
            mock_flow_class.from_client_config.return_value = mock_flow

            result = await oauth_manager.handle_oauth_callback(
                "auth_code", "test_state"
            )

            assert isinstance(result, WorkflowTokenData)
            assert result.customer_id == "1234567890"
            assert result.access_token == "access_token"
            assert result.refresh_token == "refresh_token"
            assert flow.callback_received is True
            assert flow.completed_at is not None

    async def test_handle_oauth_callback_invalid_state(self, oauth_manager):
        """Test OAuth callback with invalid state."""
        with pytest.raises(
            AuthenticationError, match="Invalid or expired OAuth2 state"
        ):
            await oauth_manager.handle_oauth_callback("auth_code", "invalid_state")

    async def test_handle_oauth_callback_expired_flow(self, oauth_manager):
        """Test OAuth callback with expired flow."""
        # Setup expired flow
        flow = ConsentFlow(
            customer_id="1234567890",
            requested_permissions=["write_campaigns"],
            state="test_state",
        )
        flow.expires_at = datetime.utcnow() - timedelta(hours=1)  # Expired
        oauth_manager._active_flows[flow.flow_id] = flow

        with pytest.raises(AuthenticationError, match="OAuth2 flow expired"):
            await oauth_manager.handle_oauth_callback("auth_code", "test_state")

    async def test_get_workflow_credentials_success(
        self, oauth_manager, sample_token_data
    ):
        """Test successful workflow credentials retrieval."""
        customer_id = "1234567890"

        mock_creds = MagicMock(spec=Credentials)
        oauth_manager._base_token_manager.get_credentials.return_value = mock_creds
        oauth_manager._base_token_manager.storage.load_tokens.return_value = (
            sample_token_data
        )

        result = await oauth_manager.get_workflow_credentials(customer_id)

        assert isinstance(result, WorkflowTokenData)
        assert result.customer_id == customer_id

    async def test_get_workflow_credentials_no_tokens(self, oauth_manager):
        """Test workflow credentials retrieval with no stored tokens."""
        customer_id = "1234567890"

        oauth_manager._base_token_manager.storage.load_tokens.return_value = None

        with pytest.raises(AuthenticationError, match="No stored tokens"):
            await oauth_manager.get_workflow_credentials(customer_id)

    async def test_refresh_workflow_credentials(
        self, oauth_manager, sample_workflow_tokens
    ):
        """Test refreshing workflow credentials."""
        customer_id = "1234567890"

        mock_refreshed_creds = MagicMock(spec=Credentials)
        mock_refreshed_creds.token = "new_access_token"
        mock_refreshed_creds.refresh_token = "new_refresh_token"
        mock_refreshed_creds.expiry = datetime.utcnow() + timedelta(hours=1)

        oauth_manager._base_token_manager._refresh_token.return_value = (
            mock_refreshed_creds
        )

        result = await oauth_manager.refresh_workflow_credentials(
            customer_id, sample_workflow_tokens
        )

        assert result.access_token == "new_access_token"
        assert result.refresh_token == "new_refresh_token"

    async def test_validate_permissions_success(
        self, oauth_manager, sample_workflow_tokens
    ):
        """Test successful permission validation."""
        customer_id = "1234567890"
        required_permissions = ["write_campaigns"]

        with patch.object(
            oauth_manager,
            "get_workflow_credentials",
            return_value=sample_workflow_tokens,
        ):
            result = await oauth_manager.validate_permissions(
                customer_id, required_permissions
            )
            assert result is True

    async def test_validate_permissions_insufficient(
        self, oauth_manager, sample_workflow_tokens
    ):
        """Test permission validation with insufficient permissions."""
        customer_id = "1234567890"
        required_permissions = ["write_campaigns", "admin_access"]

        with patch.object(
            oauth_manager,
            "get_workflow_credentials",
            return_value=sample_workflow_tokens,
        ):
            result = await oauth_manager.validate_permissions(
                customer_id, required_permissions
            )
            assert result is False

    async def test_validate_permissions_no_credentials(self, oauth_manager):
        """Test permission validation with no credentials."""
        customer_id = "1234567890"
        required_permissions = ["write_campaigns"]

        with patch.object(
            oauth_manager,
            "get_workflow_credentials",
            side_effect=AuthenticationError("No tokens"),
        ):
            result = await oauth_manager.validate_permissions(
                customer_id, required_permissions
            )
            assert result is False

    async def test_revoke_workflow_access(self, oauth_manager):
        """Test revoking workflow access."""
        customer_id = "1234567890"

        # Add active flow for customer
        flow = ConsentFlow(customer_id=customer_id, requested_permissions=[])
        oauth_manager._active_flows[flow.flow_id] = flow

        await oauth_manager.revoke_workflow_access(customer_id)

        # Verify token manager was called
        oauth_manager._base_token_manager.revoke_tokens.assert_called_once_with(
            customer_id
        )

        # Verify active flows were cleaned up
        assert len(oauth_manager._active_flows) == 0

    async def test_cleanup_expired_flows(self, oauth_manager):
        """Test cleanup of expired consent flows."""
        # Add expired flow
        expired_flow = ConsentFlow(
            customer_id="1234567890",
            requested_permissions=["write_campaigns"],
        )
        expired_flow.expires_at = datetime.utcnow() - timedelta(hours=1)
        oauth_manager._active_flows[expired_flow.flow_id] = expired_flow

        # Add active flow
        active_flow = ConsentFlow(
            customer_id="0987654321",
            requested_permissions=["write_keywords"],
        )
        oauth_manager._active_flows[active_flow.flow_id] = active_flow

        cleaned_count = await oauth_manager.cleanup_expired_flows()

        assert cleaned_count == 1
        assert expired_flow.flow_id not in oauth_manager._active_flows
        assert active_flow.flow_id in oauth_manager._active_flows

    async def test_get_active_flows_all(self, oauth_manager):
        """Test getting all active flows."""
        flow1 = ConsentFlow(customer_id="1111111111", requested_permissions=[])
        flow2 = ConsentFlow(customer_id="2222222222", requested_permissions=[])

        oauth_manager._active_flows[flow1.flow_id] = flow1
        oauth_manager._active_flows[flow2.flow_id] = flow2

        flows = oauth_manager.get_active_flows()

        assert len(flows) == 2
        assert flow1 in flows
        assert flow2 in flows

    async def test_get_active_flows_filtered(self, oauth_manager):
        """Test getting active flows filtered by customer."""
        flow1 = ConsentFlow(customer_id="1111111111", requested_permissions=[])
        flow2 = ConsentFlow(customer_id="2222222222", requested_permissions=[])

        oauth_manager._active_flows[flow1.flow_id] = flow1
        oauth_manager._active_flows[flow2.flow_id] = flow2

        flows = oauth_manager.get_active_flows("1111111111")

        assert len(flows) == 1
        assert flow1 in flows
        assert flow2 not in flows

    async def test_health_check_success(self, oauth_manager):
        """Test successful health check."""
        result = await oauth_manager.health_check()
        assert result is True

    async def test_health_check_failure(self, oauth_manager):
        """Test health check failure."""
        with patch.object(
            oauth_manager, "cleanup_expired_flows", side_effect=Exception("Test error")
        ):
            result = await oauth_manager.health_check()
            assert result is False


class TestWorkflowTokenData:
    """Test WorkflowTokenData model."""

    def test_to_google_credentials(self, sample_workflow_tokens):
        """Test conversion to Google Credentials."""
        client_secret = "test_client_secret"
        creds = sample_workflow_tokens.to_google_credentials(client_secret)

        assert isinstance(creds, Credentials)
        assert creds.token == sample_workflow_tokens.access_token
        assert creds.refresh_token == sample_workflow_tokens.refresh_token
        assert creds.client_id == sample_workflow_tokens.client_id
        assert creds.client_secret == client_secret

    def test_from_token_data(self, sample_token_data):
        """Test creation from TokenData."""
        customer_id = "1234567890"
        workflow_tokens = WorkflowTokenData.from_token_data(
            sample_token_data, customer_id
        )

        assert workflow_tokens.customer_id == customer_id
        assert workflow_tokens.access_token == sample_token_data.access_token
        assert workflow_tokens.refresh_token == sample_token_data.refresh_token


class TestConsentFlow:
    """Test ConsentFlow model."""

    def test_consent_flow_creation(self):
        """Test ConsentFlow creation with defaults."""
        flow = ConsentFlow(
            customer_id="1234567890", requested_permissions=["write_campaigns"]
        )

        assert flow.customer_id == "1234567890"
        assert flow.requested_permissions == ["write_campaigns"]
        assert flow.callback_received is False
        assert flow.state is not None
        assert len(flow.state) > 10  # Should be a random string
        assert flow.expires_at > datetime.utcnow()
