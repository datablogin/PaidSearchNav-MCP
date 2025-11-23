"""Unit tests for OAuth2 token management."""

from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest
from cryptography.fernet import Fernet
from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials

from paidsearchnav_mcp.core.config import (
    GoogleAdsConfig,
    SecretProvider,
    Settings,
    TokenStorageBackend,
)
from paidsearchnav_mcp.core.exceptions import AuthenticationError
from paidsearchnav_mcp.platforms.google.auth import (
    KeyringTokenStorage,
    OAuth2TokenManager,
    SecretManagerTokenStorage,
    TokenData,
    TokenStorage,
    _is_headless_environment,
    _validate_customer_id,
    create_token_storage,
)

# Try to import optional dependencies
try:
    import boto3  # noqa: F401

    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False

try:
    import google.cloud.secretmanager  # noqa: F401

    HAS_GCP = True
except ImportError:
    HAS_GCP = False

try:
    import hvac  # noqa: F401

    HAS_HVAC = True
except ImportError:
    HAS_HVAC = False


class TestTokenData:
    """Test TokenData model."""

    def test_token_data_creation(self):
        """Test creating TokenData instance."""
        token_data = TokenData(
            access_token="access_token",
            refresh_token="refresh_token",
            client_id="client_id",
            client_secret="client_secret",
            expiry=datetime.utcnow() + timedelta(hours=1),
        )

        assert token_data.access_token == "access_token"
        assert token_data.refresh_token == "refresh_token"
        assert token_data.client_id == "client_id"
        assert token_data.client_secret == "client_secret"
        assert token_data.scopes == ["https://www.googleapis.com/auth/adwords"]

    def test_token_data_to_google_credentials(self):
        """Test converting TokenData to Google Credentials."""
        expiry = datetime.utcnow() + timedelta(hours=1)
        token_data = TokenData(
            access_token="access_token",
            refresh_token="refresh_token",
            client_id="client_id",
            client_secret="client_secret",
            expiry=expiry,
        )

        creds = token_data.to_google_credentials("client_secret")

        assert creds.token == "access_token"
        assert creds.refresh_token == "refresh_token"
        assert creds.client_id == "client_id"
        assert creds.client_secret == "client_secret"
        assert creds.expiry == expiry

    def test_token_data_from_google_credentials(self):
        """Test creating TokenData from Google Credentials."""
        expiry = datetime.utcnow() + timedelta(hours=1)
        creds = Credentials(
            token="access_token",
            refresh_token="refresh_token",
            token_uri="https://oauth2.googleapis.com/token",
            expiry=expiry,
        )

        token_data = TokenData.from_google_credentials(
            creds, client_id="client_id", client_secret="client_secret"
        )

        assert token_data.access_token == "access_token"
        assert token_data.refresh_token == "refresh_token"
        assert token_data.client_id == "client_id"
        assert token_data.client_secret == "client_secret"
        assert token_data.expiry == expiry


class TestTokenStorage:
    """Test TokenStorage class."""

    @pytest.fixture
    def settings(self):
        """Create test settings."""
        return Settings(
            google_ads=GoogleAdsConfig(
                client_id="test_client_id",
                client_secret="test_client_secret",
                developer_token="test_developer_token",
                refresh_token="test_refresh_token",
            )
        )

    @pytest.fixture
    def token_storage(self, settings):
        """Create TokenStorage instance."""
        return TokenStorage(settings)

    def test_token_storage_initialization(self, token_storage, settings):
        """Test TokenStorage initialization."""
        assert token_storage.settings == settings
        assert isinstance(token_storage._fernet, Fernet)

    def test_save_and_load_token(self, token_storage):
        """Test saving and loading tokens."""
        token_data = TokenData(
            access_token="access_token",
            refresh_token="refresh_token",
            client_id="client_id",
            client_secret="client_secret",
        )

        # Save token
        token_storage.save_tokens("customer_123", token_data)

        # Load token
        loaded_token = token_storage.load_tokens("customer_123")

        assert loaded_token is not None
        assert loaded_token.access_token == "access_token"
        assert loaded_token.refresh_token == "refresh_token"
        assert loaded_token.client_id == "client_id"
        assert loaded_token.client_secret == "client_secret"

    def test_load_nonexistent_token(self, token_storage):
        """Test loading non-existent token returns None."""
        token = token_storage.load_tokens("nonexistent")
        assert token is None

    def test_delete_token(self, token_storage):
        """Test deleting tokens."""
        token_data = TokenData(
            access_token="access_token",
            refresh_token="refresh_token",
            client_id="client_id",
            client_secret="client_secret",
        )

        # Save and delete token
        token_storage.save_tokens("customer_123", token_data)
        token_storage.delete_tokens("customer_123")

        # Verify token is deleted
        token = token_storage.load_tokens("customer_123")
        assert token is None

    def test_token_file_permissions(self, token_storage):
        """Test that token files have secure permissions."""
        token_data = TokenData(
            access_token="access_token",
            refresh_token="refresh_token",
            client_id="client_id",
            client_secret="client_secret",
        )

        token_storage.save_tokens("customer_123", token_data)

        token_file = token_storage._get_token_file_path("customer_123")
        assert token_file.exists()

        # Check file permissions (should be 0o600)
        stat_info = token_file.stat()
        assert stat_info.st_mode & 0o777 == 0o600


class TestSecretManagerTokenStorage:
    """Test SecretManagerTokenStorage class."""

    @pytest.fixture
    def settings_aws(self):
        """Create test settings for AWS."""
        return Settings(
            secret_provider=SecretProvider.AWS_SECRETS_MANAGER,
            google_ads=GoogleAdsConfig(
                client_id="test_client_id",
                client_secret="test_client_secret",
                developer_token="test_developer_token",
                refresh_token="test_refresh_token",
            ),
        )

    @pytest.mark.skipif(not HAS_BOTO3, reason="boto3 not installed")
    def test_aws_secrets_manager_save(self, settings_aws):
        """Test saving token to AWS Secrets Manager."""
        with patch("boto3.client") as mock_boto:
            mock_client = Mock()
            mock_boto.return_value = mock_client

            storage = SecretManagerTokenStorage(settings_aws)
            token_data = TokenData(
                access_token="access_token",
                refresh_token="refresh_token",
                client_id="client_id",
                client_secret="client_secret",
            )

            storage.save_tokens("customer_123", token_data)

            mock_client.put_secret_value.assert_called_once()
            call_args = mock_client.put_secret_value.call_args
            assert call_args[1]["SecretId"] == "paidsearchnav-tokens-customer_123"
            assert "SecretString" in call_args[1]

    @pytest.mark.skipif(not HAS_BOTO3, reason="boto3 not installed")
    def test_aws_secrets_manager_load(self, settings_aws):
        """Test loading token from AWS Secrets Manager."""
        with patch("boto3.client") as mock_boto:
            mock_client = Mock()
            mock_boto.return_value = mock_client

            # Mock response
            token_data = TokenData(
                access_token="access_token",
                refresh_token="refresh_token",
                client_id="client_id",
                client_secret="client_secret",
            )
            mock_client.get_secret_value.return_value = {
                "SecretString": token_data.model_dump_json()
            }

            storage = SecretManagerTokenStorage(settings_aws)
            loaded_token = storage.load_tokens("customer_123")

            assert loaded_token is not None
            assert loaded_token.access_token == "access_token"
            assert loaded_token.refresh_token == "refresh_token"

    @pytest.fixture
    def settings_gcp(self):
        """Create test settings for GCP."""
        return Settings(
            secret_provider=SecretProvider.GCP_SECRET_MANAGER,
            gcp_project_id="test-project",
            google_ads=GoogleAdsConfig(
                client_id="test_client_id",
                client_secret="test_client_secret",
                developer_token="test_developer_token",
                refresh_token="test_refresh_token",
            ),
        )

    @pytest.mark.skipif(not HAS_GCP, reason="google.cloud.secretmanager not installed")
    def test_gcp_secret_manager_save(self, settings_gcp):
        """Test saving token to GCP Secret Manager."""
        with patch(
            "google.cloud.secretmanager.SecretManagerServiceClient"
        ) as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value = mock_client

            # Mock get_secret to simulate existing secret
            mock_secret = Mock()
            mock_secret.name = (
                "projects/test-project/secrets/paidsearchnav-tokens-customer_123"
            )
            mock_client.get_secret.return_value = mock_secret

            storage = SecretManagerTokenStorage(settings_gcp)
            token_data = TokenData(
                access_token="access_token",
                refresh_token="refresh_token",
                client_id="client_id",
                client_secret="client_secret",
            )

            storage.save_tokens("customer_123", token_data)

            # Verify add_secret_version was called
            mock_client.add_secret_version.assert_called_once()

    @pytest.fixture
    def settings_vault(self):
        """Create test settings for Vault."""
        return Settings(
            secret_provider=SecretProvider.HASHICORP_VAULT,
            vault_url="http://localhost:8200",
            google_ads=GoogleAdsConfig(
                client_id="test_client_id",
                client_secret="test_client_secret",
                developer_token="test_developer_token",
                refresh_token="test_refresh_token",
            ),
        )

    @pytest.mark.skipif(not HAS_HVAC, reason="hvac not installed")
    def test_vault_save_load(self, settings_vault):
        """Test saving and loading token from HashiCorp Vault."""
        with patch("hvac.Client") as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value = mock_client
            mock_client.is_authenticated.return_value = True

            storage = SecretManagerTokenStorage(settings_vault)
            token_data = TokenData(
                access_token="access_token",
                refresh_token="refresh_token",
                client_id="client_id",
                client_secret="client_secret",
            )

            # Test save
            storage.save_tokens("customer_123", token_data)
            mock_client.secrets.kv.v2.create_or_update_secret.assert_called_once()

            # Test load
            mock_client.secrets.kv.v2.read_secret_version.return_value = {
                "data": {"data": token_data.model_dump()}
            }
            loaded_token = storage.load_tokens("customer_123")

            assert loaded_token is not None
            assert loaded_token.access_token == "access_token"

    def test_local_fallback(self):
        """Test fallback to local storage when provider is ENVIRONMENT."""
        settings = Settings(
            secret_provider=SecretProvider.ENVIRONMENT,
            google_ads=GoogleAdsConfig(
                client_id="test_client_id",
                client_secret="test_client_secret",
                developer_token="test_developer_token",
                refresh_token="test_refresh_token",
            ),
        )

        storage = SecretManagerTokenStorage(settings)
        assert storage.provider == SecretProvider.ENVIRONMENT


class TestOAuth2TokenManager:
    """Test OAuth2TokenManager class."""

    @pytest.fixture
    def settings(self):
        """Create test settings."""
        return Settings(
            google_ads=GoogleAdsConfig(
                client_id="test_client_id",
                client_secret="test_client_secret",
                developer_token="test_developer_token",
                refresh_token="test_refresh_token",
            )
        )

    @pytest.fixture
    def mock_storage(self):
        """Create mock token storage."""
        return Mock(spec=TokenStorage)

    @pytest.fixture
    def token_manager(self, settings, mock_storage, monkeypatch):
        """Create OAuth2TokenManager instance."""
        # Patch TokenStorage constructor to return our mock
        monkeypatch.setattr(
            "paidsearchnav.platforms.google.auth.TokenStorage", lambda _: mock_storage
        )
        return OAuth2TokenManager(settings)

    def test_get_credentials_with_valid_token(self, token_manager, mock_storage):
        """Test getting credentials with valid token."""
        # Create valid token
        valid_token = TokenData(
            access_token="valid_access_token",
            refresh_token="valid_refresh_token",
            client_id="test_client_id",
            client_secret="test_client_secret",
            expiry=datetime.utcnow() + timedelta(hours=1),
        )
        mock_storage.load_tokens.return_value = valid_token

        # Get credentials
        creds = token_manager.get_credentials("customer_123")

        assert creds.token == "valid_access_token"
        assert creds.valid
        mock_storage.load_tokens.assert_called_once_with("customer_123")

    def test_get_credentials_with_expired_token(self, token_manager, mock_storage):
        """Test getting credentials with expired token triggers refresh."""
        # Create expired token
        expired_token = TokenData(
            access_token="expired_access_token",
            refresh_token="valid_refresh_token",
            client_id="test_client_id",
            client_secret="test_client_secret",
            expiry=datetime.utcnow() - timedelta(hours=1),
        )
        mock_storage.load_tokens.return_value = expired_token

        # Mock refresh
        with patch.object(token_manager, "_refresh_token") as mock_refresh:
            refreshed_creds = Mock(spec=Credentials)
            refreshed_creds.token = "new_access_token"
            refreshed_creds.valid = True
            refreshed_creds.expiry = datetime.utcnow() + timedelta(hours=1)
            mock_refresh.return_value = refreshed_creds

            # Get credentials
            creds = token_manager.get_credentials("customer_123")

            assert creds.token == "new_access_token"
            mock_refresh.assert_called_once()

    def test_get_credentials_no_token(self, token_manager, mock_storage):
        """Test getting credentials with no stored token triggers auth flow."""
        mock_storage.load_tokens.return_value = None

        # Mock authenticate_new
        with patch.object(token_manager, "_authenticate_new") as mock_auth:
            new_creds = Mock(spec=Credentials)
            new_creds.token = "new_access_token"
            new_creds.valid = True
            mock_auth.return_value = new_creds

            # Get credentials
            creds = token_manager.get_credentials("customer_123")

            assert creds.token == "new_access_token"
            mock_auth.assert_called_once_with("customer_123", None)

    def test_refresh_token_success(self, token_manager, mock_storage):
        """Test successful token refresh."""
        # Create credentials with refresh token
        creds = Credentials(
            token="old_token",
            refresh_token="valid_refresh_token",
            client_id="test_client_id",
            client_secret="test_client_secret",
            token_uri="https://oauth2.googleapis.com/token",
        )

        # Mock the refresh
        with patch.object(creds, "refresh") as mock_refresh:
            creds.token = "new_token"
            creds.expiry = datetime.utcnow() + timedelta(hours=1)

            # Refresh token
            refreshed = token_manager._refresh_token(creds, "customer_123")

            assert refreshed.token == "new_token"
            mock_refresh.assert_called_once()
            mock_storage.save_tokens.assert_called_once()

    def test_refresh_token_failure(self, token_manager, mock_storage):
        """Test token refresh failure."""
        # Create credentials with refresh token
        creds = Credentials(
            token="old_token",
            refresh_token="invalid_refresh_token",
            client_id="test_client_id",
            client_secret="test_client_secret",
            token_uri="https://oauth2.googleapis.com/token",
        )

        # Mock the refresh to fail
        with patch.object(
            creds, "refresh", side_effect=RefreshError("Invalid refresh token")
        ):
            with pytest.raises(AuthenticationError, match="Failed to refresh token"):
                token_manager._refresh_token(creds, "customer_123")

    def test_authenticate_new_browser_flow(self, token_manager, mock_storage):
        """Test new authentication flow using browser method."""
        # Mock the OAuth flow
        mock_flow = Mock()
        mock_creds = Mock(spec=Credentials)
        mock_creds.token = "new_token"
        mock_creds.refresh_token = "new_refresh_token"
        mock_creds.scopes = ["https://www.googleapis.com/auth/adwords"]
        mock_creds.expiry = datetime.utcnow() + timedelta(hours=1)
        mock_creds.client_id = "test_client_id"
        mock_creds.client_secret = "test_client_secret"
        mock_creds.token_uri = "https://oauth2.googleapis.com/token"
        mock_flow.run_local_server.return_value = mock_creds

        with patch(
            "google_auth_oauthlib.flow.InstalledAppFlow.from_client_config"
        ) as mock_flow_class:
            mock_flow_class.return_value = mock_flow

            # Authenticate using browser flow
            creds = token_manager._authenticate_browser_flow("customer_123")

            assert creds == mock_creds
            mock_flow.run_local_server.assert_called_once()
            mock_storage.save_tokens.assert_called_once()

    def test_revoke_tokens(self, token_manager, mock_storage):
        """Test revoking tokens."""
        # Create token
        token_data = TokenData(
            access_token="access_token",
            refresh_token="refresh_token",
            client_id="test_client_id",
            client_secret="test_client_secret",
        )
        mock_storage.load_tokens.return_value = token_data

        # Mock requests.post for revocation
        with patch("requests.post") as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_post.return_value = mock_response

            # Revoke tokens
            token_manager.revoke_tokens("customer_123")

            # Verify revocation request
            mock_post.assert_called_once_with(
                "https://oauth2.googleapis.com/revoke",
                params={"token": "refresh_token"},
                headers={"content-type": "application/x-www-form-urlencoded"},
            )
            mock_storage.delete_tokens.assert_called_once_with("customer_123")

    def test_revoke_tokens_no_token(self, token_manager, mock_storage):
        """Test revoking tokens when no token exists."""
        mock_storage.load_tokens.return_value = None

        # Should not raise error
        token_manager.revoke_tokens("customer_123")

        # Storage delete should still be called
        mock_storage.delete_tokens.assert_called_once_with("customer_123")

    def test_needs_refresh_no_expiry(self, token_manager):
        """Test needs_refresh when credentials have no expiry."""
        creds = Credentials(token="token")
        assert not token_manager._needs_refresh(creds)

    def test_needs_refresh_with_expiry(self, token_manager):
        """Test needs_refresh with various expiry times."""
        # Token expires in 10 minutes - should need refresh
        creds = Credentials(
            token="token", expiry=datetime.utcnow() + timedelta(minutes=3)
        )
        assert token_manager._needs_refresh(creds)

        # Token expires in 1 hour - should not need refresh
        creds = Credentials(
            token="token", expiry=datetime.utcnow() + timedelta(hours=1)
        )
        assert not token_manager._needs_refresh(creds)

        # Token already expired - should need refresh
        creds = Credentials(
            token="token", expiry=datetime.utcnow() - timedelta(minutes=1)
        )
        assert token_manager._needs_refresh(creds)


class TestHeadlessEnvironmentDetection:
    """Test headless environment detection."""

    def test_ci_environment_detection(self):
        """Test detection of CI environments."""
        ci_vars = ["CI", "GITHUB_ACTIONS", "TRAVIS", "JENKINS_URL"]

        for ci_var in ci_vars:
            with patch.dict("os.environ", {ci_var: "true"}, clear=False):
                assert _is_headless_environment()

    def test_docker_environment_detection(self):
        """Test detection of Docker environment."""
        with patch("os.path.exists") as mock_exists:
            mock_exists.return_value = True
            assert _is_headless_environment()

    def test_no_display_environment(self):
        """Test detection when DISPLAY is not set."""
        with patch("os.name", "posix"), patch.dict("os.environ", {}, clear=True):
            # Mock DISPLAY not being set
            assert _is_headless_environment()

    def test_explicit_headless_flag(self):
        """Test explicit headless flag."""
        with patch.dict("os.environ", {"PSN_HEADLESS": "true"}, clear=False):
            assert _is_headless_environment()

    def test_non_tty_detection(self):
        """Test detection when stdin/stdout are not TTY."""
        with (
            patch("sys.stdin.isatty", return_value=False),
            patch("sys.stdout.isatty", return_value=True),
        ):
            assert _is_headless_environment()

    def test_interactive_environment(self):
        """Test detection of interactive environment."""
        with (
            patch.dict("os.environ", {}, clear=True),
            patch("os.path.exists", return_value=False),
            patch("os.name", "nt"),
            patch("sys.stdin.isatty", return_value=True),
            patch("sys.stdout.isatty", return_value=True),
        ):
            assert not _is_headless_environment()


class TestDeviceFlowAuthentication:
    """Test device flow authentication."""

    @pytest.fixture
    def settings(self):
        """Create test settings."""
        return Settings(
            google_ads=GoogleAdsConfig(
                client_id="test_client_id",
                client_secret="test_client_secret",
                developer_token="test_developer_token",
                refresh_token="test_refresh_token",
            )
        )

    @pytest.fixture
    def mock_storage(self):
        """Create mock token storage."""
        return Mock(spec=TokenStorage)

    @pytest.fixture
    def token_manager(self, settings, mock_storage, monkeypatch):
        """Create OAuth2TokenManager instance."""
        monkeypatch.setattr(
            "paidsearchnav.platforms.google.auth.TokenStorage", lambda _: mock_storage
        )
        return OAuth2TokenManager(settings)

    def test_device_flow_success(self, token_manager, mock_storage):
        """Test successful device flow authentication."""
        # Mock device code response
        device_response = {
            "device_code": "test_device_code",
            "user_code": "TEST-CODE",
            "verification_url": "https://www.google.com/device",
            "expires_in": 1800,
            "interval": 5,
        }

        # Mock successful token response
        token_response = {
            "access_token": "new_access_token",
            "refresh_token": "new_refresh_token",
            "expires_in": 3600,
            "token_type": "Bearer",
        }

        with patch("requests.post") as mock_post:
            # First call: device code request
            # Second call: token request (success)
            mock_post.side_effect = [
                Mock(status_code=200, json=lambda: device_response),
                Mock(status_code=200, json=lambda: token_response),
            ]

            with patch("time.sleep"), patch("builtins.print"):
                creds = token_manager._authenticate_device_flow("customer_123")

            assert creds.token == "new_access_token"
            assert creds.refresh_token == "new_refresh_token"
            mock_storage.save_tokens.assert_called_once()

    def test_device_flow_pending_then_success(self, token_manager, mock_storage):
        """Test device flow with pending authorization then success."""
        device_response = {
            "device_code": "test_device_code",
            "user_code": "TEST-CODE",
            "verification_url": "https://www.google.com/device",
            "expires_in": 1800,
            "interval": 5,
        }

        pending_response = {"error": "authorization_pending"}
        token_response = {
            "access_token": "new_access_token",
            "refresh_token": "new_refresh_token",
            "expires_in": 3600,
        }

        with patch("requests.post") as mock_post:
            mock_post.side_effect = [
                Mock(status_code=200, json=lambda: device_response),
                Mock(status_code=400, json=lambda: pending_response),
                Mock(status_code=200, json=lambda: token_response),
            ]

            with patch("time.sleep"), patch("builtins.print"):
                creds = token_manager._authenticate_device_flow("customer_123")

            assert creds.token == "new_access_token"
            assert creds.refresh_token == "new_refresh_token"

    def test_device_flow_slow_down(self, token_manager, mock_storage):
        """Test device flow handling slow_down response."""
        device_response = {
            "device_code": "test_device_code",
            "user_code": "TEST-CODE",
            "verification_url": "https://www.google.com/device",
            "expires_in": 1800,
            "interval": 5,
        }

        slow_down_response = {"error": "slow_down"}
        token_response = {
            "access_token": "new_access_token",
            "refresh_token": "new_refresh_token",
            "expires_in": 3600,
        }

        with patch("requests.post") as mock_post:
            mock_post.side_effect = [
                Mock(status_code=200, json=lambda: device_response),
                Mock(status_code=400, json=lambda: slow_down_response),
                Mock(status_code=200, json=lambda: token_response),
            ]

            with patch("time.sleep"), patch("builtins.print"):
                creds = token_manager._authenticate_device_flow("customer_123")

            assert creds.token == "new_access_token"

    def test_device_flow_expired_token(self, token_manager, mock_storage):
        """Test device flow with expired token."""
        device_response = {
            "device_code": "test_device_code",
            "user_code": "TEST-CODE",
            "verification_url": "https://www.google.com/device",
            "expires_in": 1800,
            "interval": 5,
        }

        expired_response = {"error": "expired_token"}

        with patch("requests.post") as mock_post:
            mock_post.side_effect = [
                Mock(status_code=200, json=lambda: device_response),
                Mock(status_code=400, json=lambda: expired_response),
            ]

            with patch("time.sleep"), patch("builtins.print"):
                with pytest.raises(AuthenticationError, match="Device code expired"):
                    token_manager._authenticate_device_flow("customer_123")

    def test_device_flow_access_denied(self, token_manager, mock_storage):
        """Test device flow with access denied."""
        device_response = {
            "device_code": "test_device_code",
            "user_code": "TEST-CODE",
            "verification_url": "https://www.google.com/device",
            "expires_in": 1800,
            "interval": 5,
        }

        denied_response = {"error": "access_denied"}

        with patch("requests.post") as mock_post:
            mock_post.side_effect = [
                Mock(status_code=200, json=lambda: device_response),
                Mock(status_code=400, json=lambda: denied_response),
            ]

            with patch("time.sleep"), patch("builtins.print"):
                with pytest.raises(AuthenticationError, match="User denied access"):
                    token_manager._authenticate_device_flow("customer_123")

    def test_device_flow_timeout(self, token_manager, mock_storage):
        """Test device flow timeout."""
        device_response = {
            "device_code": "test_device_code",
            "user_code": "TEST-CODE",
            "verification_url": "https://www.google.com/device",
            "expires_in": 1,  # Very short timeout
            "interval": 1,  # Short interval too
        }

        pending_response = {"error": "authorization_pending"}

        def mock_post_side_effect(*args, **kwargs):
            # First call: device code request
            if "device/code" in args[0]:
                return Mock(status_code=200, json=lambda: device_response)
            # Subsequent calls: always pending
            return Mock(status_code=400, json=lambda: pending_response)

        with patch("requests.post", side_effect=mock_post_side_effect):
            with patch("time.sleep"), patch("builtins.print"):
                with pytest.raises(
                    AuthenticationError, match="expired before user completed"
                ):
                    token_manager._authenticate_device_flow("customer_123")

    def test_forced_auth_method_device(self, token_manager, mock_storage):
        """Test forcing device authentication method."""
        mock_storage.load_tokens.return_value = None

        with patch.object(token_manager, "_authenticate_device_flow") as mock_device:
            mock_creds = Mock(spec=Credentials)
            mock_device.return_value = mock_creds

            creds = token_manager.get_credentials(
                "customer_123", force_auth_method="device"
            )

            assert creds == mock_creds
            mock_device.assert_called_once_with("customer_123")

    def test_forced_auth_method_browser(self, token_manager, mock_storage):
        """Test forcing browser authentication method."""
        mock_storage.load_tokens.return_value = None

        with patch.object(token_manager, "_authenticate_browser_flow") as mock_browser:
            mock_creds = Mock(spec=Credentials)
            mock_browser.return_value = mock_creds

            creds = token_manager.get_credentials(
                "customer_123", force_auth_method="browser"
            )

            assert creds == mock_creds
            mock_browser.assert_called_once_with("customer_123")

    def test_auto_detection_headless(self, token_manager, mock_storage):
        """Test automatic detection chooses device flow in headless environment."""
        mock_storage.load_tokens.return_value = None

        with (
            patch(
                "paidsearchnav.platforms.google.auth._is_headless_environment",
                return_value=True,
            ),
            patch.object(token_manager, "_authenticate_device_flow") as mock_device,
        ):
            mock_creds = Mock(spec=Credentials)
            mock_device.return_value = mock_creds

            creds = token_manager.get_credentials("customer_123")

            assert creds == mock_creds
            mock_device.assert_called_once_with("customer_123")

    def test_auto_detection_interactive(self, token_manager, mock_storage):
        """Test automatic detection chooses browser flow in interactive environment."""
        mock_storage.load_tokens.return_value = None

        with (
            patch(
                "paidsearchnav.platforms.google.auth._is_headless_environment",
                return_value=False,
            ),
            patch.object(token_manager, "_authenticate_browser_flow") as mock_browser,
        ):
            mock_creds = Mock(spec=Credentials)
            mock_browser.return_value = mock_creds

            creds = token_manager.get_credentials("customer_123")

            assert creds == mock_creds
            mock_browser.assert_called_once_with("customer_123")


class TestKeyringTokenStorage:
    """Test KeyringTokenStorage with system keyring integration."""

    @pytest.fixture
    def settings(self):
        """Create test settings."""
        return Settings(
            token_storage_backend=TokenStorageBackend.KEYRING,
            google_ads=GoogleAdsConfig(
                developer_token="test_token",
                client_id="test_client_id",
                client_secret="test_secret",
            ),
        )

    @pytest.fixture
    def token_data(self):
        """Create test token data."""
        return TokenData(
            access_token="access123",
            refresh_token="refresh456",
            token_uri="https://oauth2.googleapis.com/token",
            client_id="test_client_id",
            client_secret="test_secret",
            scopes=["https://www.googleapis.com/auth/adwords"],
            expiry=datetime.utcnow() + timedelta(hours=1),
        )

    def test_keyring_available_save_and_load(self, settings, token_data):
        """Test keyring storage when keyring is available."""
        # Use direct method mocking instead of module mocking
        with patch.object(
            KeyringTokenStorage, "_test_keyring_availability", return_value=True
        ):
            storage = KeyringTokenStorage(settings)

            # Test that keyring is detected as available
            assert storage._keyring_available is True

            # Create a mock keyring object
            mock_keyring = Mock()
            mock_keyring.set_password = Mock()
            mock_keyring.get_password = Mock(return_value=token_data.model_dump_json())
            mock_keyring.delete_password = Mock()

            # Patch the _get_keyring method
            with patch.object(storage, "_get_keyring", return_value=mock_keyring):
                # Test save tokens
                storage.save_tokens("1234567890", token_data)
                mock_keyring.set_password.assert_called_with(
                    "paidsearchnav", "tokens_1234567890", token_data.model_dump_json()
                )

                # Test load tokens
                loaded_token = storage.load_tokens("1234567890")
                assert loaded_token is not None
                assert loaded_token.access_token == "access123"
                assert loaded_token.refresh_token == "refresh456"

                # Test delete tokens
                storage.delete_tokens("1234567890")
                mock_keyring.delete_password.assert_called_with(
                    "paidsearchnav", "tokens_1234567890"
                )

    def test_keyring_unavailable_fallback(self, settings, token_data):
        """Test fallback to file storage when keyring is unavailable."""
        with (
            patch("keyring.set_password") as mock_set,
            patch("keyring.get_password") as mock_get,
        ):
            # Mock keyring test failure
            mock_get.return_value = None  # Test fails

            with (
                patch.object(TokenStorage, "save_tokens") as mock_file_save,
                patch.object(TokenStorage, "load_tokens") as mock_file_load,
            ):
                storage = KeyringTokenStorage(settings)

                # Test that keyring is detected as unavailable
                assert storage._keyring_available is False

                # Test save falls back to file storage
                storage.save_tokens("1234567890", token_data)
                mock_file_save.assert_called_once_with("1234567890", token_data)

                # Test load falls back to file storage
                mock_file_load.return_value = token_data
                loaded_token = storage.load_tokens("1234567890")
                mock_file_load.assert_called_once_with("1234567890")
                assert loaded_token == token_data

    def test_keyring_runtime_error_fallback(self, settings, token_data):
        """Test fallback when keyring operations fail at runtime."""
        with patch.object(
            KeyringTokenStorage, "_test_keyring_availability", return_value=True
        ):
            storage = KeyringTokenStorage(settings)
            assert storage._keyring_available is True

            # Create a mock keyring object
            mock_keyring = Mock()
            mock_keyring.set_password.side_effect = Exception("Keyring save error")

            with (
                patch.object(storage, "_get_keyring", return_value=mock_keyring),
                patch.object(TokenStorage, "save_tokens") as mock_file_save,
            ):
                storage.save_tokens("1234567890", token_data)

                # Should fall back to file storage and mark keyring as unavailable
                mock_file_save.assert_called_once_with("1234567890", token_data)
                assert storage._keyring_available is False

    def test_keyring_load_error_fallback(self, settings, token_data):
        """Test fallback when keyring load fails at runtime."""
        with patch.object(
            KeyringTokenStorage, "_test_keyring_availability", return_value=True
        ):
            storage = KeyringTokenStorage(settings)
            assert storage._keyring_available is True

            # Create a mock keyring object
            mock_keyring = Mock()
            mock_keyring.get_password.side_effect = Exception("Keyring load error")

            with (
                patch.object(storage, "_get_keyring", return_value=mock_keyring),
                patch.object(TokenStorage, "load_tokens") as mock_file_load,
            ):
                mock_file_load.return_value = token_data

                loaded_token = storage.load_tokens("1234567890")

                # Should fall back to file storage and mark keyring as unavailable
                mock_file_load.assert_called_once_with("1234567890")
                assert loaded_token == token_data
                assert storage._keyring_available is False

    def test_keyring_test_with_wrong_value(self, settings):
        """Test keyring availability detection with incorrect retrieved value."""
        with patch("keyring.set_password"), patch("keyring.get_password") as mock_get:
            # Mock wrong value returned
            mock_get.return_value = "wrong_value"

            storage = KeyringTokenStorage(settings)

            # Should detect keyring as unavailable
            assert storage._keyring_available is False

    def test_keyring_import_error(self, settings):
        """Test behavior when keyring module cannot be imported."""
        with patch("builtins.__import__") as mock_import:
            mock_import.side_effect = ImportError("No module named 'keyring'")

            storage = KeyringTokenStorage(settings)

            # Should detect keyring as unavailable
            assert storage._keyring_available is False


class TestTokenStorageFactory:
    """Test the token storage factory function."""

    def test_create_keyring_storage(self):
        """Test creating KeyringTokenStorage."""
        settings = Settings(
            token_storage_backend=TokenStorageBackend.KEYRING,
            google_ads=GoogleAdsConfig(
                developer_token="test_token",
                client_id="test_client_id",
                client_secret="test_secret",
            ),
        )

        storage = create_token_storage(settings)
        assert isinstance(storage, KeyringTokenStorage)

    def test_create_secret_manager_storage(self):
        """Test creating SecretManagerTokenStorage."""
        settings = Settings(
            token_storage_backend=TokenStorageBackend.SECRET_MANAGER,
            google_ads=GoogleAdsConfig(
                developer_token="test_token",
                client_id="test_client_id",
                client_secret="test_secret",
            ),
        )

        storage = create_token_storage(settings)
        assert isinstance(storage, SecretManagerTokenStorage)

    def test_create_file_encrypted_storage(self):
        """Test creating default TokenStorage (file encrypted)."""
        settings = Settings(
            token_storage_backend=TokenStorageBackend.FILE_ENCRYPTED,
            google_ads=GoogleAdsConfig(
                developer_token="test_token",
                client_id="test_client_id",
                client_secret="test_secret",
            ),
        )

        storage = create_token_storage(settings)
        assert isinstance(storage, TokenStorage)
        assert not isinstance(storage, KeyringTokenStorage)
        assert not isinstance(storage, SecretManagerTokenStorage)

    def test_create_default_storage(self):
        """Test creating storage with default configuration."""
        settings = Settings(
            google_ads=GoogleAdsConfig(
                developer_token="test_token",
                client_id="test_client_id",
                client_secret="test_secret",
            ),
        )

        # Default should be FILE_ENCRYPTED
        storage = create_token_storage(settings)
        assert isinstance(storage, TokenStorage)
        assert not isinstance(storage, KeyringTokenStorage)

    def test_oauth2_token_manager_uses_factory(self):
        """Test that OAuth2TokenManager uses the factory function."""
        settings = Settings(
            token_storage_backend=TokenStorageBackend.KEYRING,
            google_ads=GoogleAdsConfig(
                developer_token="test_token",
                client_id="test_client_id",
                client_secret="test_secret",
            ),
        )

        with patch(
            "paidsearchnav.platforms.google.auth.create_token_storage"
        ) as mock_factory:
            mock_storage = Mock()
            mock_factory.return_value = mock_storage

            manager = OAuth2TokenManager(settings)

            mock_factory.assert_called_once_with(settings)
            assert manager.storage == mock_storage


class TestCustomerIdValidation:
    """Test customer ID validation functionality."""

    def test_valid_customer_id(self):
        """Test validation with valid customer IDs."""
        # Test standard format
        assert _validate_customer_id("1234567890") == "1234567890"

        # Test with dashes (common format)
        assert _validate_customer_id("123-456-7890") == "1234567890"

    def test_invalid_customer_id_types(self):
        """Test validation with invalid input types."""
        with pytest.raises(ValueError, match="Customer ID must be a non-empty string"):
            _validate_customer_id("")

        with pytest.raises(ValueError, match="Customer ID must be a non-empty string"):
            _validate_customer_id(None)

        with pytest.raises(ValueError, match="Customer ID must be a non-empty string"):
            _validate_customer_id(123)

    def test_invalid_customer_id_formats(self):
        """Test validation with invalid customer ID formats."""
        # Too short
        with pytest.raises(ValueError, match="Customer ID must be exactly 10 digits"):
            _validate_customer_id("123456789")

        # Too long
        with pytest.raises(ValueError, match="Customer ID must be exactly 10 digits"):
            _validate_customer_id("12345678901")

        # Contains letters
        with pytest.raises(ValueError, match="Customer ID must be exactly 10 digits"):
            _validate_customer_id("123456789a")

        # Contains special characters
        with pytest.raises(ValueError, match="Customer ID must be exactly 10 digits"):
            _validate_customer_id("1234567@90")

    def test_suspicious_customer_id_patterns(self):
        """Test detection of suspicious customer ID patterns."""
        # All same digits should log a warning but still validate
        with patch("paidsearchnav.platforms.google.auth.logger") as mock_logger:
            result = _validate_customer_id("1111111111")
            assert result == "1111111111"
            mock_logger.warning.assert_called_once()


class TestKeyringTokenStorageValidation:
    """Test KeyringTokenStorage with enhanced validation."""

    @pytest.fixture
    def settings(self):
        """Create test settings."""
        return Settings(
            token_storage_backend=TokenStorageBackend.KEYRING,
            google_ads=GoogleAdsConfig(
                developer_token="test_token",
                client_id="test_client_id",
                client_secret="test_secret",
            ),
        )

    @pytest.fixture
    def token_data(self):
        """Create test token data."""
        return TokenData(
            access_token="access123",
            refresh_token="refresh456",
            token_uri="https://oauth2.googleapis.com/token",
            client_id="test_client_id",
            client_secret="test_secret",
            scopes=["https://www.googleapis.com/auth/adwords"],
            expiry=datetime.utcnow() + timedelta(hours=1),
        )

    def test_save_tokens_invalid_customer_id(self, settings):
        """Test save_tokens with invalid customer ID."""
        with patch.object(
            KeyringTokenStorage, "_test_keyring_availability", return_value=True
        ):
            storage = KeyringTokenStorage(settings)

            token_data = TokenData(
                access_token="access123",
                refresh_token="refresh456",
                token_uri="https://oauth2.googleapis.com/token",
                client_id="test_client_id",
                client_secret="test_secret",
                scopes=["https://www.googleapis.com/auth/adwords"],
            )

            with pytest.raises(
                ValueError, match="Customer ID must be exactly 10 digits"
            ):
                storage.save_tokens("invalid", token_data)

    def test_load_tokens_invalid_customer_id(self, settings):
        """Test load_tokens with invalid customer ID."""
        with patch.object(
            KeyringTokenStorage, "_test_keyring_availability", return_value=True
        ):
            storage = KeyringTokenStorage(settings)

            with pytest.raises(
                ValueError, match="Customer ID must be exactly 10 digits"
            ):
                storage.load_tokens("invalid")

    def test_delete_tokens_invalid_customer_id(self, settings):
        """Test delete_tokens with invalid customer ID."""
        with patch.object(
            KeyringTokenStorage, "_test_keyring_availability", return_value=True
        ):
            storage = KeyringTokenStorage(settings)

            with pytest.raises(
                ValueError, match="Customer ID must be exactly 10 digits"
            ):
                storage.delete_tokens("invalid")

    def test_json_decode_error_handling(self, settings, token_data):
        """Test handling of JSON decode errors from keyring."""
        with patch.object(
            KeyringTokenStorage, "_test_keyring_availability", return_value=True
        ):
            storage = KeyringTokenStorage(settings)

            # Create a mock keyring object
            mock_keyring = Mock()
            mock_keyring.get_password = Mock(return_value="invalid json")

            with patch.object(storage, "_get_keyring", return_value=mock_keyring):
                # Should fall back to file storage
                with patch.object(TokenStorage, "load_tokens") as mock_file_load:
                    mock_file_load.return_value = token_data
                    result = storage.load_tokens("1234567890")
                    assert result == token_data
                    mock_file_load.assert_called_once_with("1234567890")

    def test_permission_error_handling(self, settings, token_data):
        """Test handling of permission errors."""
        with patch.object(
            KeyringTokenStorage, "_test_keyring_availability", return_value=True
        ):
            storage = KeyringTokenStorage(settings)

            # Create a mock keyring object
            mock_keyring = Mock()
            mock_keyring.set_password.side_effect = PermissionError("Access denied")

            with patch.object(storage, "_get_keyring", return_value=mock_keyring):
                # Should fall back to file storage and mark keyring unavailable
                with patch.object(TokenStorage, "save_tokens") as mock_file_save:
                    storage.save_tokens("1234567890", token_data)
                    mock_file_save.assert_called_once_with("1234567890", token_data)
                    assert storage._keyring_available is False

    def test_keyring_delete_keyerror_handling(self, settings):
        """Test handling of KeyError when deleting non-existent tokens."""
        with patch.object(
            KeyringTokenStorage, "_test_keyring_availability", return_value=True
        ):
            storage = KeyringTokenStorage(settings)

            # Create a mock keyring object
            mock_keyring = Mock()
            mock_keyring.delete_password.side_effect = KeyError("Token not found")

            with patch.object(storage, "_get_keyring", return_value=mock_keyring):
                # Should continue to file storage fallback without marking keyring unavailable
                with patch.object(TokenStorage, "delete_tokens") as mock_file_delete:
                    storage.delete_tokens("1234567890")
                    mock_file_delete.assert_called_once_with("1234567890")
                    assert (
                        storage._keyring_available is True
                    )  # Should still be available
