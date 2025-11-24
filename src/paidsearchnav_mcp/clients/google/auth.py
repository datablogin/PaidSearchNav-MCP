"""OAuth2 Token Manager for Google Ads API.

This module handles:
- OAuth2 authentication flow (browser and device flow)
- Automatic environment detection for headless systems
- Secure token storage with encryption
- Automatic token refresh
- Token revocation handling

Authentication Methods:
- Browser Flow: Interactive authentication with web browser (default for interactive environments)
- Device Flow: Headless authentication for servers/CI systems (default for headless environments)

Environment Detection:
The system automatically detects headless environments based on:
- CI/CD environment variables (CI, GITHUB_ACTIONS, JENKINS_URL, etc.)
- Docker containers (/.dockerenv file)
- Missing DISPLAY environment variable (Unix/Linux)
- Non-TTY stdin/stdout
- Explicit PSN_HEADLESS environment variable

Manual Override:
You can force a specific authentication method by setting the force_auth_method parameter:
- get_credentials(customer_id, force_auth_method="browser")
- get_credentials(customer_id, force_auth_method="device")
"""

import json
import logging
import os
import re
import secrets
import sys
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests
from cryptography.fernet import Fernet

# Keyring will be imported lazily in KeyringTokenStorage class
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow  # type: ignore[import-untyped]
from pydantic import BaseModel, Field

from paidsearchnav_mcp.core.config import SecretProvider, Settings
from paidsearchnav_mcp.core.exceptions import AuthenticationError, ConfigurationError

logger = logging.getLogger(__name__)

# OAuth2 scopes required for Google Ads API
GOOGLE_ADS_SCOPES = ["https://www.googleapis.com/auth/adwords"]


def _validate_customer_id(customer_id: str) -> str:
    """Validate and sanitize customer ID for secure storage.

    Args:
        customer_id: Google Ads customer ID to validate

    Returns:
        Sanitized customer ID

    Raises:
        ValueError: If customer ID is invalid or potentially malicious
    """
    if not customer_id or not isinstance(customer_id, str):
        raise ValueError("Customer ID must be a non-empty string")

    # Remove any dashes (common in customer ID format)
    cleaned = customer_id.replace("-", "")

    # Validate format: should be 10 digits only
    if not re.match(r"^\d{10}$", cleaned):
        raise ValueError("Customer ID must be exactly 10 digits")

    # Additional security: check for suspicious patterns
    if len(set(cleaned)) == 1:  # All same digit
        logger.warning(f"Suspicious customer ID pattern detected: {customer_id}")

    return cleaned


def _is_headless_environment() -> bool:
    """Detect if running in a headless environment.

    Returns:
        True if in headless environment, False if interactive environment available
    """
    # Check for common CI/server environment variables
    ci_indicators = [
        "CI",
        "CONTINUOUS_INTEGRATION",
        "BUILD_NUMBER",
        "JENKINS_URL",
        "GITHUB_ACTIONS",
        "GITLAB_CI",
        "CIRCLECI",
        "TRAVIS",
        "DRONE",
        "BUILDKITE",
        "DOCKER_CONTAINER",
        "AZURE_HTTP_USER_AGENT",
        "bamboo_buildKey",
        "TEAMCITY_VERSION",
        "BITBUCKET_BUILD_NUMBER",
        "CODEBUILD_BUILD_ID",
        "APPVEYOR",
        "TF_BUILD",
        "WERCKER",
        "CONCOURSE_URL",
        "GO_PIPELINE_NAME",
        "BUDDY",
        "SAIL_CI",
    ]

    if any(os.getenv(var) for var in ci_indicators):
        return True

    # Check if DISPLAY is set (Unix/Linux systems)
    if os.name == "posix" and not os.getenv("DISPLAY"):
        return True

    # Check if running in Docker
    if os.path.exists("/.dockerenv"):
        return True

    # Check if stdin/stdout are not connected to a terminal
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        return True

    # Check for explicit headless flag
    if os.getenv("PSN_HEADLESS", "").lower() in ("true", "1", "yes"):
        return True

    return False


class TokenData(BaseModel):
    """OAuth2 token data model."""

    access_token: str = Field(..., description="OAuth2 access token")
    refresh_token: str = Field(..., description="OAuth2 refresh token")
    token_uri: str = Field(
        default="https://oauth2.googleapis.com/token",
        description="Token endpoint URI",
    )
    client_id: str = Field(..., description="OAuth2 client ID")
    client_secret: str = Field(..., description="OAuth2 client secret")
    scopes: list[str] = Field(default_factory=lambda: GOOGLE_ADS_SCOPES)
    expiry: datetime | None = Field(None, description="Token expiry time")

    def to_google_credentials(self) -> Credentials:
        """Convert to Google Credentials object."""
        return Credentials(
            token=self.access_token,
            refresh_token=self.refresh_token,
            token_uri=self.token_uri,
            client_id=self.client_id,
            client_secret=self.client_secret,
            scopes=self.scopes,
            expiry=self.expiry,
        )

    @classmethod
    def from_google_credentials(
        cls, creds: Credentials, client_id: str, client_secret: str
    ) -> "TokenData":
        """Create from Google Credentials object."""
        return cls(
            access_token=creds.token,
            refresh_token=creds.refresh_token,
            token_uri=creds.token_uri,
            client_id=client_id,
            client_secret=client_secret,
            scopes=list(creds.scopes) if creds.scopes else GOOGLE_ADS_SCOPES,
            expiry=creds.expiry,
        )


class TokenStorage:
    """Secure token storage with encryption."""

    def __init__(self, settings: Settings):
        """Initialize token storage.

        Args:
            settings: Application settings
        """
        self.settings = settings
        self._encryption_key = self._get_or_create_encryption_key()
        self._fernet = Fernet(self._encryption_key)

    def _get_or_create_encryption_key(self) -> bytes:
        """Get or create encryption key for token storage.

        Uses atomic file operations to prevent race conditions when multiple
        processes attempt to create the key file simultaneously.
        """
        key_file = Path.home() / ".paidsearchnav" / ".token_key"
        key_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            # Try to read existing key first
            with open(key_file, "rb") as f:
                return f.read()
        except FileNotFoundError:
            pass

        # Key doesn't exist, create it atomically
        # Generate new key
        key = Fernet.generate_key()

        # Write to temporary file first, then atomically rename
        temp_file = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb", dir=key_file.parent, delete=False, prefix=".token_key_tmp_"
            ) as f:
                f.write(key)
                temp_file = f.name

            # Set restrictive permissions before moving
            os.chmod(temp_file, 0o600)

            # Atomic rename (only works if file doesn't exist)
            try:
                os.link(temp_file, key_file)
                os.unlink(temp_file)
            except FileExistsError:
                # Another process created the key, use that one
                os.unlink(temp_file)
                with open(key_file, "rb") as f:
                    return f.read()

            return key

        except Exception:
            # Clean up temp file if something went wrong
            if temp_file and os.path.exists(temp_file):
                os.unlink(temp_file)
            raise

    def save_tokens(self, customer_id: str, token_data: TokenData) -> None:
        """Save encrypted tokens.

        Args:
            customer_id: Google Ads customer ID
            token_data: Token data to save
        """
        token_file = self._get_token_file_path(customer_id)
        token_file.parent.mkdir(parents=True, exist_ok=True)

        # Encrypt token data
        encrypted_data = self._fernet.encrypt(
            token_data.model_dump_json().encode("utf-8")
        )

        # Save encrypted data
        with open(token_file, "wb") as f:
            f.write(encrypted_data)

        # Set restrictive permissions
        os.chmod(token_file, 0o600)

        logger.info(f"Saved encrypted tokens for customer {customer_id}")

    def load_tokens(self, customer_id: str) -> TokenData | None:
        """Load encrypted tokens.

        Args:
            customer_id: Google Ads customer ID

        Returns:
            Token data if exists, None otherwise
        """
        token_file = self._get_token_file_path(customer_id)

        if not token_file.exists():
            return None

        try:
            # Read encrypted data
            with open(token_file, "rb") as f:
                encrypted_data = f.read()

            # Decrypt data
            decrypted_data = self._fernet.decrypt(encrypted_data)
            token_dict = json.loads(decrypted_data.decode("utf-8"))

            # Parse dates
            if token_dict.get("expiry"):
                token_dict["expiry"] = datetime.fromisoformat(token_dict["expiry"])

            return TokenData(**token_dict)

        except FileNotFoundError:
            logger.debug(f"Token file not found for customer {customer_id}")
            return None
        except PermissionError as e:
            logger.error(
                f"Permission denied reading token file for customer {customer_id}: {e}"
            )
            return None
        except Exception as e:
            from cryptography.fernet import InvalidToken

            if isinstance(e, InvalidToken):
                logger.error(
                    f"Token decryption failed for customer {customer_id}: Invalid encryption key or corrupted token file"
                )
            elif isinstance(e, json.JSONDecodeError):
                logger.error(
                    f"Token parsing failed for customer {customer_id}: Corrupted JSON data after decryption"
                )
            elif isinstance(e, (ValueError, TypeError)) and "expiry" in str(e):
                logger.error(
                    f"Token date parsing failed for customer {customer_id}: Invalid expiry date format"
                )
            else:
                logger.error(
                    f"Unexpected error loading tokens for customer {customer_id}: {type(e).__name__}: {e}"
                )
            return None

    def delete_tokens(self, customer_id: str) -> None:
        """Delete stored tokens.

        Args:
            customer_id: Google Ads customer ID
        """
        token_file = self._get_token_file_path(customer_id)
        if token_file.exists():
            token_file.unlink()
            logger.info(f"Deleted tokens for customer {customer_id}")

    def _get_token_file_path(self, customer_id: str) -> Path:
        """Get token file path for customer."""
        return Path.home() / ".paidsearchnav" / "tokens" / f"{customer_id}.enc"


class OAuth2TokenManager:
    """Manages OAuth2 tokens for Google Ads API."""

    def __init__(self, settings: Settings):
        """Initialize token manager.

        Args:
            settings: Application settings
        """
        self.settings = settings
        self.storage = create_token_storage(settings)

        # Validate configuration
        if not settings.google_ads:
            raise ConfigurationError("Google Ads configuration not provided")

        if (
            not settings.google_ads.client_id
            or not settings.google_ads.client_secret.get_secret_value()
        ):
            raise ConfigurationError(
                "Google Ads client_id and client_secret are required"
            )

    def _safe_print(self, message: str) -> None:
        """Safely print to stdout with fallback to logging.

        Protects against BrokenPipeError when stdout is closed (e.g., in MCP context).

        Args:
            message: Message to print
        """
        try:
            print(message)
            sys.stdout.flush()
        except (BrokenPipeError, IOError) as e:
            # Stdout is closed or broken - fallback to logging
            logger.debug(f"Unable to write to stdout: {e}. Message: {message}")
        except Exception as e:
            # Unexpected error - log it but don't crash
            logger.warning(f"Unexpected error writing to stdout: {e}")

    def get_credentials(
        self, customer_id: str, force_auth_method: str | None = None
    ) -> Credentials:
        """Get valid credentials for a customer.

        Args:
            customer_id: Google Ads customer ID
            force_auth_method: Force specific auth method ('browser', 'device', or None for auto-detect)

        Returns:
            Valid Google credentials

        Raises:
            AuthenticationError: If authentication fails
        """
        # Try to load existing tokens
        token_data = self.storage.load_tokens(customer_id)

        if token_data:
            if not self.settings.google_ads:
                raise ConfigurationError("Google Ads configuration not provided")
            creds = token_data.to_google_credentials(
                self.settings.google_ads.client_secret.get_secret_value()
            )

            # Check if token needs refresh
            if self._needs_refresh(creds):
                logger.info(f"Refreshing token for customer {customer_id}")
                creds = self._refresh_token(creds, customer_id)

            return creds

        # No existing tokens, need to authenticate
        logger.info(f"No tokens found for customer {customer_id}, starting OAuth2 flow")
        return self._authenticate_new(customer_id, force_auth_method)

    def _needs_refresh(self, creds: Credentials) -> bool:
        """Check if credentials need refresh.

        Args:
            creds: Google credentials

        Returns:
            True if refresh needed
        """
        if not creds.expiry:
            return False

        # Refresh if expiring within 5 minutes
        # Use utcnow() to match Google Credentials library expectations (offset-naive)
        return bool(creds.expiry <= datetime.utcnow() + timedelta(minutes=5))

    def _refresh_token(self, creds: Credentials, customer_id: str) -> Credentials:
        """Refresh access token.

        Args:
            creds: Google credentials
            customer_id: Google Ads customer ID

        Returns:
            Refreshed credentials

        Raises:
            AuthenticationError: If refresh fails
        """
        try:
            creds.refresh(Request())

            # Save refreshed tokens
            if not self.settings.google_ads:
                raise ConfigurationError("Google Ads configuration not provided")
            token_data = TokenData.from_google_credentials(
                creds,
                self.settings.google_ads.client_id,
                self.settings.google_ads.client_secret.get_secret_value(),
            )
            self.storage.save_tokens(customer_id, token_data)

            return creds

        except Exception as e:
            logger.error(f"Token refresh failed for customer {customer_id}: {e}")
            raise AuthenticationError(f"Failed to refresh token: {e}") from e

    def _authenticate_new(
        self, customer_id: str, force_auth_method: str | None = None
    ) -> Credentials:
        """Perform new OAuth2 authentication flow.

        Automatically chooses between interactive and device flow based on environment,
        unless a specific method is forced.

        Args:
            customer_id: Google Ads customer ID
            force_auth_method: Force specific auth method ('browser', 'device', or None for auto-detect)

        Returns:
            New credentials

        Raises:
            AuthenticationError: If authentication fails
        """
        if force_auth_method == "device":
            logger.info(f"Forced device flow for customer {customer_id}")
            return self._authenticate_device_flow(customer_id)
        elif force_auth_method == "browser":
            logger.info(f"Forced browser flow for customer {customer_id}")
            return self._authenticate_browser_flow(customer_id)
        elif _is_headless_environment():
            logger.info(
                f"Headless environment detected, using device flow for customer {customer_id}"
            )
            return self._authenticate_device_flow(customer_id)
        else:
            logger.info(
                f"Interactive environment detected, using browser flow for customer {customer_id}"
            )
            return self._authenticate_browser_flow(customer_id)

    def _authenticate_browser_flow(self, customer_id: str) -> Credentials:
        """Perform OAuth2 authentication using browser flow.

        Args:
            customer_id: Google Ads customer ID

        Returns:
            New credentials

        Raises:
            AuthenticationError: If authentication fails
        """
        try:
            # Create OAuth2 flow
            if not self.settings.google_ads:
                raise ConfigurationError("Google Ads configuration not provided")
            flow = InstalledAppFlow.from_client_config(
                {
                    "installed": {
                        "client_id": self.settings.google_ads.client_id,
                        "client_secret": self.settings.google_ads.client_secret.get_secret_value(),
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                    }
                },
                scopes=GOOGLE_ADS_SCOPES,
            )

            # Run local server for authentication
            # This will open a browser for user consent
            creds = flow.run_local_server(
                port=8080,
                prompt="consent",
                success_message="Authentication successful! You can close this window.",
            )

            if not isinstance(creds, Credentials):
                raise AuthenticationError(
                    "Invalid credentials returned from OAuth flow"
                )

            # Save new tokens
            token_data = TokenData.from_google_credentials(
                creds,
                self.settings.google_ads.client_id,
                self.settings.google_ads.client_secret.get_secret_value(),
            )
            self.storage.save_tokens(customer_id, token_data)

            logger.info(
                f"Successfully authenticated customer {customer_id} using browser flow"
            )
            return creds

        except Exception as e:
            logger.error(
                f"Browser authentication failed for customer {customer_id}: {e}"
            )
            raise AuthenticationError(
                f"OAuth2 browser authentication failed: {e}"
            ) from e

    def _authenticate_device_flow(self, customer_id: str) -> Credentials:
        """Perform OAuth2 authentication using device flow for headless environments.

        Args:
            customer_id: Google Ads customer ID

        Returns:
            New credentials

        Raises:
            AuthenticationError: If authentication fails
        """
        try:
            if not self.settings.google_ads:
                raise ConfigurationError("Google Ads configuration not provided")

            # Step 1: Request device and user codes
            device_response = self._request_device_code()

            # Step 2: Display instructions to user
            self._display_device_flow_instructions(device_response)

            # Step 3: Poll for authorization and get credentials
            creds = self._poll_for_device_authorization(device_response, customer_id)

            logger.info(
                f"Successfully authenticated customer {customer_id} using device flow"
            )
            return creds

        except Exception as e:
            logger.error(
                f"Device flow authentication failed for customer {customer_id}: {e}"
            )
            if isinstance(e, AuthenticationError):
                raise
            raise AuthenticationError(
                f"OAuth2 device flow authentication failed: {e}"
            ) from e

    def _request_device_code(self) -> dict:
        """Request device and user codes from Google OAuth2 device endpoint.

        Returns:
            Device response containing device_code, user_code, verification_url, etc.

        Raises:
            AuthenticationError: If device code request fails
        """
        device_code_url = "https://oauth2.googleapis.com/device/code"
        device_code_data = {
            "client_id": self.settings.google_ads.client_id,
            "scope": " ".join(GOOGLE_ADS_SCOPES),
        }

        logger.info("Requesting device authorization codes...")
        response = requests.post(device_code_url, data=device_code_data)
        response.raise_for_status()
        return response.json()

    def _display_device_flow_instructions(self, device_response: dict) -> None:
        """Display user-friendly instructions for device flow authentication.

        Args:
            device_response: Response from device code request
        """
        user_code = device_response["user_code"]
        verification_url = device_response["verification_url"]
        expires_in = device_response["expires_in"]

        # Always log the critical auth info in case stdout fails
        logger.info(f"Device flow authentication: {verification_url} - Code: {user_code}")

        # Use safe print to handle broken pipes in MCP context
        self._safe_print("\n" + "=" * 60)
        self._safe_print("🔐 GOOGLE ADS AUTHENTICATION REQUIRED")
        self._safe_print("=" * 60)
        self._safe_print(f"📱 Go to: {verification_url}")
        self._safe_print(f"🔑 Enter code: {user_code}")
        self._safe_print("=" * 60)
        self._safe_print("📝 Instructions:")
        self._safe_print("1. Open the URL above in any web browser")
        self._safe_print("2. Sign in to your Google account")
        self._safe_print("3. Enter the verification code shown above")
        self._safe_print("4. Grant access to Google Ads API")
        self._safe_print("5. Return here - authentication will complete automatically")
        self._safe_print(f"\n⏰ Code expires in {expires_in // 60} minutes")
        self._safe_print("⏳ Waiting for authorization...")

    def _poll_for_device_authorization(
        self, device_response: dict, customer_id: str
    ) -> Credentials:
        """Poll Google OAuth2 token endpoint until user completes authorization.

        Args:
            device_response: Response from device code request
            customer_id: Google Ads customer ID

        Returns:
            Valid credentials

        Raises:
            AuthenticationError: If authorization fails or times out
        """
        device_code = device_response["device_code"]
        expires_in = device_response["expires_in"]
        interval = device_response.get("interval", 5)

        token_url = "https://oauth2.googleapis.com/token"
        token_data = {
            "client_id": self.settings.google_ads.client_id,
            "client_secret": self.settings.google_ads.client_secret.get_secret_value(),
            "device_code": device_code,
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
        }

        start_time = time.time()
        while time.time() - start_time < expires_in:
            time.sleep(interval)

            token_response = requests.post(token_url, data=token_data)
            token_result = token_response.json()

            if token_response.status_code == 200:
                self._safe_print("✅ Authentication successful!")
                logger.info("Device flow authentication completed successfully")
                return self._create_credentials_from_token_response(
                    token_result, customer_id
                )

            # Handle various error conditions
            error = token_result.get("error")
            if error == "authorization_pending":
                self._safe_print("⏳ Still waiting for authorization...")
                continue
            elif error == "slow_down":
                interval += 1
                continue
            elif error == "expired_token":
                raise AuthenticationError("Device code expired. Please try again.")
            elif error == "access_denied":
                raise AuthenticationError("User denied access.")
            else:
                raise AuthenticationError(
                    f"Device flow error: {error or 'Unknown error'}"
                )

        raise AuthenticationError(
            "Device code expired before user completed authorization."
        )

    def _create_credentials_from_token_response(
        self, token_result: dict, customer_id: str
    ) -> Credentials:
        """Create and save credentials from successful token response.

        Args:
            token_result: Token response from OAuth2 endpoint
            customer_id: Google Ads customer ID

        Returns:
            Valid credentials
        """
        # Create credentials object
        creds = Credentials(
            token=token_result["access_token"],
            refresh_token=token_result.get("refresh_token"),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=self.settings.google_ads.client_id,
            client_secret=self.settings.google_ads.client_secret.get_secret_value(),
            scopes=GOOGLE_ADS_SCOPES,
            expiry=datetime.utcnow()
            + timedelta(seconds=token_result.get("expires_in", 3600)),
        )

        # Save new tokens
        token_data = TokenData.from_google_credentials(
            creds,
            self.settings.google_ads.client_id,
            self.settings.google_ads.client_secret.get_secret_value(),
        )
        self.storage.save_tokens(customer_id, token_data)

        return creds

    def has_valid_tokens(self, customer_id: str) -> bool:
        """Check if valid tokens exist for a customer.

        Args:
            customer_id: Google Ads customer ID

        Returns:
            True if valid tokens exist, False otherwise
        """
        token_data = self.storage.load_tokens(customer_id)
        if not token_data:
            return False

        # Check if tokens are expired (use UTC for consistency)
        if token_data.expiry and token_data.expiry < datetime.utcnow():
            return False

        return True

    def revoke_tokens(self, customer_id: str) -> None:
        """Revoke stored tokens for a customer.

        Args:
            customer_id: Google Ads customer ID
        """
        # Load tokens
        token_data = self.storage.load_tokens(customer_id)
        if not token_data:
            logger.warning(f"No tokens found for customer {customer_id}")
            # Always delete local tokens even if none found
            self.storage.delete_tokens(customer_id)
            return

        try:
            # Revoke tokens with Google
            import requests

            response = requests.post(
                "https://oauth2.googleapis.com/revoke",
                params={"token": token_data.refresh_token},
                headers={"content-type": "application/x-www-form-urlencoded"},
            )

            if response.status_code == 200:
                logger.info(f"Successfully revoked tokens for customer {customer_id}")
            else:
                logger.warning(
                    f"Token revocation returned status {response.status_code}"
                )

        except Exception as e:
            logger.error(f"Failed to revoke tokens with Google: {e}")

        # Always delete local tokens
        self.storage.delete_tokens(customer_id)

    def list_authenticated_customers(self) -> list[str]:
        """List all customers with stored tokens.

        Returns:
            List of customer IDs
        """
        token_dir = Path.home() / ".paidsearchnav" / "tokens"
        if not token_dir.exists():
            return []

        customer_ids = []
        for token_file in token_dir.glob("*.enc"):
            customer_id = token_file.stem
            customer_ids.append(customer_id)

        return sorted(customer_ids)


class SecretManagerTokenStorage(TokenStorage):
    """Token storage using cloud secret managers."""

    def __init__(self, settings: Settings):
        """Initialize secret manager storage."""
        super().__init__(settings)
        self.provider = settings.secret_provider

    def save_tokens(self, customer_id: str, token_data: TokenData) -> None:
        """Save tokens to secret manager."""
        secret_name = f"paidsearchnav-tokens-{customer_id}"

        if self.provider == SecretProvider.AWS_SECRETS_MANAGER:
            self._save_to_aws_secrets_manager(secret_name, token_data)
        elif self.provider == SecretProvider.GCP_SECRET_MANAGER:
            self._save_to_gcp_secret_manager(secret_name, token_data)
        elif self.provider == SecretProvider.HASHICORP_VAULT:
            self._save_to_hashicorp_vault(secret_name, token_data)
        else:
            # Fallback to local storage
            super().save_tokens(customer_id, token_data)

    def load_tokens(self, customer_id: str) -> TokenData | None:
        """Load tokens from secret manager."""
        secret_name = f"paidsearchnav-tokens-{customer_id}"

        if self.provider == SecretProvider.AWS_SECRETS_MANAGER:
            return self._load_from_aws_secrets_manager(secret_name)
        elif self.provider == SecretProvider.GCP_SECRET_MANAGER:
            return self._load_from_gcp_secret_manager(secret_name)
        elif self.provider == SecretProvider.HASHICORP_VAULT:
            return self._load_from_hashicorp_vault(secret_name)
        else:
            # Fallback to local storage
            return super().load_tokens(customer_id)

    def _save_to_aws_secrets_manager(
        self, secret_name: str, token_data: TokenData
    ) -> None:
        """Save to AWS Secrets Manager."""
        try:
            import boto3  # type: ignore[import-not-found]

            client = boto3.client("secretsmanager")
            client.put_secret_value(
                SecretId=secret_name,
                SecretString=token_data.model_dump_json(),
            )
            logger.info(f"Saved tokens to AWS Secrets Manager: {secret_name}")
        except Exception as e:
            logger.error(f"Failed to save to AWS Secrets Manager: {e}")
            raise AuthenticationError(f"Failed to save tokens: {e}") from e

    def _load_from_aws_secrets_manager(self, secret_name: str) -> TokenData | None:
        """Load from AWS Secrets Manager."""
        try:
            import boto3  # type: ignore[import-not-found]

            client = boto3.client("secretsmanager")
            response = client.get_secret_value(SecretId=secret_name)
            secret_string = response["SecretString"]
            token_dict = json.loads(secret_string)

            # Parse dates
            if token_dict.get("expiry"):
                token_dict["expiry"] = datetime.fromisoformat(token_dict["expiry"])

            return TokenData(**token_dict)
        except Exception as e:
            logger.error(f"Failed to load from AWS Secrets Manager: {e}")
            return None

    def _save_to_gcp_secret_manager(
        self, secret_name: str, token_data: TokenData
    ) -> None:
        """Save to GCP Secret Manager."""
        try:
            from google.cloud import secretmanager  # type: ignore[import-untyped]

            client = secretmanager.SecretManagerServiceClient()
            project_id = self.settings.gcp_project_id
            parent = f"projects/{project_id}"

            # Create secret if doesn't exist
            try:
                secret = client.create_secret(
                    request={
                        "parent": parent,
                        "secret_id": secret_name,
                        "secret": {"replication": {"automatic": {}}},
                    }
                )
            except Exception:
                # Secret might already exist
                secret = client.get_secret(
                    request={"name": f"{parent}/secrets/{secret_name}"}
                )

            # Add secret version
            client.add_secret_version(
                request={
                    "parent": secret.name,
                    "payload": {"data": token_data.model_dump_json().encode("UTF-8")},
                }
            )
            logger.info(f"Saved tokens to GCP Secret Manager: {secret_name}")
        except Exception as e:
            logger.error(f"Failed to save to GCP Secret Manager: {e}")
            raise AuthenticationError(f"Failed to save tokens: {e}") from e

    def _load_from_gcp_secret_manager(self, secret_name: str) -> TokenData | None:
        """Load from GCP Secret Manager."""
        try:
            from google.cloud import secretmanager  # type: ignore[import-untyped]

            client = secretmanager.SecretManagerServiceClient()
            project_id = self.settings.gcp_project_id
            name = f"projects/{project_id}/secrets/{secret_name}/versions/latest"

            response = client.access_secret_version(request={"name": name})
            secret_string = response.payload.data.decode("UTF-8")
            token_dict = json.loads(secret_string)

            # Parse dates
            if token_dict.get("expiry"):
                token_dict["expiry"] = datetime.fromisoformat(token_dict["expiry"])

            return TokenData(**token_dict)
        except Exception as e:
            logger.error(f"Failed to load from GCP Secret Manager: {e}")
            return None

    def _save_to_hashicorp_vault(self, secret_name: str, token_data: TokenData) -> None:
        """Save to HashiCorp Vault."""
        try:
            import hvac

            client = hvac.Client(url=self.settings.vault_url)
            client.secrets.kv.v2.create_or_update_secret(
                path=f"paidsearchnav/{secret_name}",
                secret=token_data.model_dump(),
            )
            logger.info(f"Saved tokens to HashiCorp Vault: {secret_name}")
        except Exception as e:
            logger.error(f"Failed to save to HashiCorp Vault: {e}")
            raise AuthenticationError(f"Failed to save tokens: {e}") from e

    def _load_from_hashicorp_vault(self, secret_name: str) -> TokenData | None:
        """Load from HashiCorp Vault."""
        try:
            import hvac

            client = hvac.Client(url=self.settings.vault_url)
            response = client.secrets.kv.v2.read_secret_version(
                path=f"paidsearchnav/{secret_name}"
            )
            token_dict = response["data"]["data"]

            # Parse dates
            if token_dict.get("expiry"):
                token_dict["expiry"] = datetime.fromisoformat(token_dict["expiry"])

            return TokenData(**token_dict)
        except Exception as e:
            logger.error(f"Failed to load from HashiCorp Vault: {e}")
            return None


class KeyringTokenStorage(TokenStorage):
    """Token storage using system keyring with fallback to encrypted file storage.

    Provides enhanced security by using OS-level credential storage:
    - macOS: Keychain
    - Windows: Credential Manager
    - Linux: Secret Service API (GNOME Keyring, KWallet)

    Falls back to encrypted file storage if keyring is unavailable.
    """

    def __init__(self, settings: Settings):
        """Initialize keyring storage with fallback.

        Args:
            settings: Application settings
        """
        super().__init__(settings)
        self._keyring = None  # Lazy loaded
        self._keyring_available = self._test_keyring_availability()
        self._service_name = settings.token_storage_service_name

        if not self._keyring_available:
            logger.warning(
                "System keyring unavailable, falling back to encrypted file storage"
            )

    def _get_keyring(self):
        """Lazy import keyring module to avoid global state.

        Returns:
            Keyring module if available, None otherwise
        """
        if self._keyring is None:
            try:
                import keyring

                self._keyring = keyring
            except ImportError:
                self._keyring = (
                    False  # Use False to distinguish from None (not yet checked)
                )

        return self._keyring if self._keyring is not False else None

    def _handle_keyring_failure(self, operation: str, error: Exception) -> None:
        """Handle keyring operation failure by disabling keyring and logging error.

        Args:
            operation: Description of the operation that failed
            error: The exception that occurred
        """
        self._keyring_available = False
        logger.error(f"Keyring {operation} failed ({type(error).__name__}): {error}")

    def _test_keyring_availability(self) -> bool:
        """Test if keyring is available and functional.

        Returns:
            True if keyring can be used, False otherwise
        """
        try:
            keyring = self._get_keyring()
            if keyring is None:
                logger.debug("Keyring module not available")
                return False

            # Test keyring with a more secure dummy operation
            test_key = f"psn_test_{secrets.token_hex(8)}"
            test_value = f"test_{secrets.token_hex(16)}"

            # Try to set and get a test value
            keyring.set_password(self._service_name, test_key, test_value)
            retrieved = keyring.get_password(self._service_name, test_key)

            if retrieved == test_value:
                # Clean up test data - use try/except for cleanup
                try:
                    keyring.delete_password(self._service_name, test_key)
                except Exception as cleanup_error:
                    logger.debug(f"Failed to cleanup test key: {cleanup_error}")
                return True
            else:
                logger.warning(
                    "Keyring test failed: retrieved value doesn't match expected value"
                )
                # Attempt cleanup even on failure
                try:
                    keyring.delete_password(self._service_name, test_key)
                except Exception:
                    pass  # Ignore cleanup errors
                return False

        except ImportError as e:
            logger.debug(f"Keyring import error: {e}")
            return False
        except PermissionError as e:
            logger.warning(f"Keyring permission denied: {e}")
            return False
        except Exception as e:
            logger.debug(f"Keyring availability test failed: {type(e).__name__}: {e}")
            return False

    def save_tokens(self, customer_id: str, token_data: TokenData) -> None:
        """Save tokens to keyring or fallback to file storage.

        Args:
            customer_id: Google Ads customer ID
            token_data: Token data to save

        Raises:
            ValueError: If customer_id is invalid
        """
        # Validate customer ID first
        try:
            validated_customer_id = _validate_customer_id(customer_id)
        except ValueError as e:
            logger.error(f"Invalid customer ID for token storage: {e}")
            raise

        if self._keyring_available and self._get_keyring() is not None:
            try:
                # Use validated customer_id as the username and store JSON as password
                keyring_key = f"tokens_{validated_customer_id}"
                token_json = token_data.model_dump_json()

                self._get_keyring().set_password(
                    self._service_name, keyring_key, token_json
                )
                logger.info(
                    f"Saved tokens to system keyring for customer {validated_customer_id}"
                )
                return

            except PermissionError as e:
                self._handle_keyring_failure("save (permission denied)", e)
            except Exception as e:
                self._handle_keyring_failure("save", e)

        # Fallback to encrypted file storage
        super().save_tokens(validated_customer_id, token_data)

    def load_tokens(self, customer_id: str) -> TokenData | None:
        """Load tokens from keyring or fallback to file storage.

        Args:
            customer_id: Google Ads customer ID

        Returns:
            Token data if exists, None otherwise

        Raises:
            ValueError: If customer_id is invalid
        """
        # Validate customer ID first
        try:
            validated_customer_id = _validate_customer_id(customer_id)
        except ValueError as e:
            logger.error(f"Invalid customer ID for token loading: {e}")
            raise

        if self._keyring_available and self._get_keyring() is not None:
            try:
                keyring_key = f"tokens_{validated_customer_id}"
                token_json = self._get_keyring().get_password(
                    self._service_name, keyring_key
                )

                if token_json:
                    try:
                        token_dict = json.loads(token_json)
                    except json.JSONDecodeError as e:
                        logger.error(
                            f"Invalid JSON in keyring for customer {validated_customer_id}: {e}"
                        )
                        # Fall back to file storage instead of raising
                        self._handle_keyring_failure("load (invalid JSON)", e)
                        return super().load_tokens(validated_customer_id)

                    # Parse dates
                    if token_dict.get("expiry"):
                        try:
                            token_dict["expiry"] = datetime.fromisoformat(
                                token_dict["expiry"]
                            )
                        except ValueError as e:
                            logger.error(f"Invalid expiry date format in keyring: {e}")
                            return None

                    logger.debug(
                        f"Loaded tokens from system keyring for customer {validated_customer_id}"
                    )
                    return TokenData(**token_dict)

            except PermissionError as e:
                self._handle_keyring_failure("load (permission denied)", e)
            except Exception as e:
                self._handle_keyring_failure("load", e)

        # Fallback to encrypted file storage
        return super().load_tokens(validated_customer_id)

    def delete_tokens(self, customer_id: str) -> None:
        """Delete tokens from keyring or fallback to file storage.

        Args:
            customer_id: Google Ads customer ID

        Raises:
            ValueError: If customer_id is invalid
        """
        # Validate customer ID first
        try:
            validated_customer_id = _validate_customer_id(customer_id)
        except ValueError as e:
            logger.error(f"Invalid customer ID for token deletion: {e}")
            raise

        if self._keyring_available and self._get_keyring() is not None:
            try:
                keyring_key = f"tokens_{validated_customer_id}"
                self._get_keyring().delete_password(self._service_name, keyring_key)
                logger.info(
                    f"Deleted tokens from system keyring for customer {validated_customer_id}"
                )
                return

            except KeyError:
                # Token doesn't exist in keyring - this is OK, might be in file storage
                logger.debug(
                    f"No tokens found in keyring for customer {validated_customer_id}"
                )
            except PermissionError as e:
                self._handle_keyring_failure("delete (permission denied)", e)
            except Exception as e:
                self._handle_keyring_failure("delete", e)

        # Fallback to encrypted file storage
        super().delete_tokens(validated_customer_id)


def create_token_storage(settings: Settings) -> TokenStorage:
    """Create appropriate token storage backend based on configuration.

    Args:
        settings: Application settings

    Returns:
        Token storage instance
    """
    from paidsearchnav_mcp.core.config import TokenStorageBackend

    # Check if using secret manager backend
    if settings.token_storage_backend == TokenStorageBackend.SECRET_MANAGER:
        return SecretManagerTokenStorage(settings)

    # Check if using keyring backend
    elif settings.token_storage_backend == TokenStorageBackend.KEYRING:
        return KeyringTokenStorage(settings)

    # Default to encrypted file storage
    else:
        return TokenStorage(settings)
