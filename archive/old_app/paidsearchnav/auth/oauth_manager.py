"""OAuth2 Manager for Google Ads API Write Operations.

This module provides OAuth2 authentication management specifically for
API integrations that need write permissions to customer Google Ads accounts.
"""

import asyncio
import logging
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Any

from google.oauth2.credentials import Credentials
from pydantic import BaseModel, Field

from paidsearchnav.core.config import Settings
from paidsearchnav.core.exceptions import AuthenticationError, ConfigurationError
from paidsearchnav.platforms.google.auth import OAuth2TokenManager, TokenData

logger = logging.getLogger(__name__)

# Extended OAuth2 scopes for write operations
GOOGLE_ADS_WRITE_SCOPES = [
    "https://www.googleapis.com/auth/adwords",
    "https://www.googleapis.com/auth/adwords.readonly",
]


class WorkflowTokenData(BaseModel):
    """Extended token data for workflow operations."""

    customer_id: str = Field(..., description="Google Ads customer ID")
    access_token: str = Field(..., description="OAuth2 access token")
    refresh_token: str = Field(..., description="OAuth2 refresh token")
    token_uri: str = Field(
        default="https://oauth2.googleapis.com/token", description="Token endpoint URI"
    )
    client_id: str = Field(..., description="OAuth2 client ID")
    scopes: list[str] = Field(default_factory=lambda: GOOGLE_ADS_WRITE_SCOPES)
    expiry: datetime | None = Field(None, description="Token expiry time")
    granted_at: datetime = Field(
        default_factory=datetime.utcnow, description="Token grant timestamp"
    )
    granted_by_user: str | None = Field(None, description="User who granted access")
    permissions: list[str] = Field(
        default_factory=list, description="Specific permissions granted"
    )
    consent_metadata: dict[str, Any] = Field(
        default_factory=dict, description="Consent metadata for audit trail"
    )

    def to_google_credentials(self, client_secret: str) -> Credentials:
        """Convert to Google Credentials object.

        Args:
            client_secret: OAuth2 client secret from settings
        """
        return Credentials(
            token=self.access_token,
            refresh_token=self.refresh_token,
            token_uri=self.token_uri,
            client_id=self.client_id,
            client_secret=client_secret,
            scopes=self.scopes,
            expiry=self.expiry,
        )

    @classmethod
    def from_token_data(
        cls, token_data: TokenData, customer_id: str
    ) -> "WorkflowTokenData":
        """Create from base TokenData."""
        return cls(
            customer_id=customer_id,
            access_token=token_data.access_token,
            refresh_token=token_data.refresh_token,
            token_uri=token_data.token_uri,
            client_id=token_data.client_id,
            scopes=token_data.scopes,
            expiry=token_data.expiry,
        )


class ConsentFlow(BaseModel):
    """OAuth2 consent flow tracking."""

    flow_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    customer_id: str = Field(..., description="Customer ID requesting consent")
    state: str = Field(default_factory=lambda: secrets.token_urlsafe(32))
    requested_permissions: list[str] = Field(..., description="Requested permissions")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime = Field(
        default_factory=lambda: datetime.utcnow() + timedelta(hours=1)
    )
    authorization_url: str | None = Field(None, description="OAuth2 authorization URL")
    callback_received: bool = Field(False, description="Whether callback was received")
    completed_at: datetime | None = Field(None, description="Completion timestamp")
    user_info: dict[str, Any] = Field(
        default_factory=dict, description="User information from callback"
    )


class OAuth2Manager:
    """Enhanced OAuth2 manager for Google Ads API workflow integrations."""

    def __init__(self, settings: Settings):
        """Initialize OAuth2 manager.

        Args:
            settings: Application settings
        """
        self.settings = settings
        self._base_token_manager = OAuth2TokenManager(settings)
        self._active_flows: dict[str, ConsentFlow] = {}
        self._cleanup_task: asyncio.Task | None = None

        # Validate configuration
        if not settings.google_ads:
            raise ConfigurationError("Google Ads configuration not provided")

        # Background cleanup task will be started on first use

    def _start_cleanup_task(self) -> None:
        """Start the background cleanup task if event loop is running."""
        try:
            if self._cleanup_task is None or self._cleanup_task.done():
                self._cleanup_task = asyncio.create_task(self._background_cleanup())
        except RuntimeError:
            # No event loop running, task will be started later
            logger.debug("No event loop running, cleanup task will start later")

    async def _background_cleanup(self) -> None:
        """Background task to periodically clean up expired flows."""
        try:
            while True:
                await asyncio.sleep(300)  # Run every 5 minutes
                try:
                    await self.cleanup_expired_flows()
                except Exception as e:
                    logger.error(f"Background cleanup failed: {e}")
        except asyncio.CancelledError:
            logger.info("Background cleanup task cancelled")
        except Exception as e:
            logger.error(f"Background cleanup task failed: {e}")

    def __del__(self) -> None:
        """Clean up background task on destruction."""
        if (
            hasattr(self, "_cleanup_task")
            and self._cleanup_task
            and not self._cleanup_task.done()
        ):
            self._cleanup_task.cancel()

    async def initiate_consent_flow(
        self,
        customer_id: str,
        requested_permissions: list[str],
        user_info: dict[str, Any] | None = None,
    ) -> ConsentFlow:
        """Initiate OAuth2 consent flow for API workflows.

        Args:
            customer_id: Google Ads customer ID
            requested_permissions: List of requested permissions
            user_info: Optional user information

        Returns:
            ConsentFlow object with authorization details
        """
        # Create consent flow
        flow = ConsentFlow(
            customer_id=customer_id,
            requested_permissions=requested_permissions,
            user_info=user_info or {},
        )

        # Start cleanup task if not already running
        self._start_cleanup_task()

        # Generate authorization URL
        if not self.settings.google_ads:
            raise ConfigurationError("Google Ads configuration not provided")

        from google_auth_oauthlib.flow import (
            InstalledAppFlow,  # type: ignore[import-untyped]
        )

        oauth_flow = InstalledAppFlow.from_client_config(
            {
                "installed": {
                    "client_id": self.settings.google_ads.client_id,
                    "client_secret": self.settings.google_ads.client_secret.get_secret_value(),
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": self.settings.google_ads.oauth_redirect_uris,
                }
            },
            scopes=GOOGLE_ADS_WRITE_SCOPES,
            state=flow.state,
        )

        authorization_url, _ = oauth_flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
            state=flow.state,
        )

        flow.authorization_url = authorization_url
        self._active_flows[flow.flow_id] = flow

        logger.info(f"Initiated consent flow {flow.flow_id} for customer {customer_id}")
        return flow

    async def handle_oauth_callback(
        self, authorization_code: str, state: str
    ) -> WorkflowTokenData:
        """Handle OAuth2 callback and exchange code for tokens.

        Args:
            authorization_code: Authorization code from callback
            state: State parameter for CSRF protection

        Returns:
            WorkflowTokenData with access credentials
        """
        # Find matching flow
        flow = None
        for consent_flow in self._active_flows.values():
            if consent_flow.state == state and not consent_flow.callback_received:
                flow = consent_flow
                break

        if not flow:
            raise AuthenticationError("Invalid or expired OAuth2 state")

        if flow.expires_at < datetime.utcnow():
            raise AuthenticationError("OAuth2 flow expired")

        try:
            # Exchange authorization code for tokens
            from google_auth_oauthlib.flow import (
                InstalledAppFlow,  # type: ignore[import-untyped]
            )

            if not self.settings.google_ads:
                raise ConfigurationError("Google Ads configuration not provided")

            oauth_flow = InstalledAppFlow.from_client_config(
                {
                    "installed": {
                        "client_id": self.settings.google_ads.client_id,
                        "client_secret": self.settings.google_ads.client_secret.get_secret_value(),
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "redirect_uris": self.settings.google_ads.oauth_redirect_uris,
                    }
                },
                scopes=GOOGLE_ADS_WRITE_SCOPES,
            )

            # Fetch tokens
            oauth_flow.fetch_token(code=authorization_code)
            creds = oauth_flow.credentials

            # Create workflow token data
            workflow_tokens = WorkflowTokenData(
                customer_id=flow.customer_id,
                access_token=creds.token,
                refresh_token=creds.refresh_token,
                token_uri=creds.token_uri,
                client_id=self.settings.google_ads.client_id,
                client_secret=self.settings.google_ads.client_secret.get_secret_value(),
                scopes=list(creds.scopes) if creds.scopes else GOOGLE_ADS_WRITE_SCOPES,
                expiry=creds.expiry,
                permissions=flow.requested_permissions,
                consent_metadata={
                    "flow_id": flow.flow_id,
                    "state": state,
                    "user_agent": flow.user_info.get("user_agent"),
                    "ip_address": flow.user_info.get("ip_address"),
                },
            )

            # Store tokens using base token manager
            base_token_data = TokenData(
                access_token=creds.token,
                refresh_token=creds.refresh_token,
                token_uri=creds.token_uri,
                client_id=self.settings.google_ads.client_id,
                client_secret=self.settings.google_ads.client_secret.get_secret_value(),
                scopes=list(creds.scopes) if creds.scopes else GOOGLE_ADS_WRITE_SCOPES,
                expiry=creds.expiry,
            )

            self._base_token_manager.storage.save_tokens(
                flow.customer_id, base_token_data
            )

            # Mark flow as completed
            flow.callback_received = True
            flow.completed_at = datetime.utcnow()

            logger.info(f"OAuth2 callback processed for customer {flow.customer_id}")
            return workflow_tokens

        except Exception as e:
            logger.error(f"OAuth2 callback handling failed: {e}")
            raise AuthenticationError("OAuth2 callback processing failed") from e

    async def get_workflow_credentials(self, customer_id: str) -> WorkflowTokenData:
        """Get valid workflow credentials for a customer.

        Args:
            customer_id: Google Ads customer ID

        Returns:
            Valid WorkflowTokenData

        Raises:
            AuthenticationError: If no valid credentials available
        """
        try:
            # Use base token manager to get credentials
            creds = self._base_token_manager.get_credentials(customer_id)

            # Convert to workflow token data
            base_token_data = self._base_token_manager.storage.load_tokens(customer_id)
            if not base_token_data:
                raise AuthenticationError(
                    f"No stored tokens for customer {customer_id}"
                )

            return WorkflowTokenData.from_token_data(base_token_data, customer_id)

        except Exception as e:
            logger.error(f"Failed to get workflow credentials for {customer_id}: {e}")
            raise AuthenticationError("Failed to get workflow credentials") from e

    async def refresh_workflow_credentials(
        self, customer_id: str, workflow_tokens: WorkflowTokenData
    ) -> WorkflowTokenData:
        """Refresh expired workflow credentials.

        Args:
            customer_id: Google Ads customer ID
            workflow_tokens: Current workflow tokens

        Returns:
            Refreshed WorkflowTokenData
        """
        try:
            # Convert to base credentials and refresh
            if not self.settings.google_ads:
                raise ConfigurationError("Google Ads configuration not provided")
            creds = workflow_tokens.to_google_credentials(
                self.settings.google_ads.client_secret.get_secret_value()
            )
            refreshed_creds = self._base_token_manager._refresh_token(
                creds, customer_id
            )

            # Update workflow tokens
            workflow_tokens.access_token = refreshed_creds.token
            workflow_tokens.refresh_token = refreshed_creds.refresh_token
            workflow_tokens.expiry = refreshed_creds.expiry

            logger.info(f"Refreshed workflow credentials for customer {customer_id}")
            return workflow_tokens

        except Exception as e:
            logger.error(f"Failed to refresh workflow credentials: {e}")
            raise AuthenticationError("Failed to refresh workflow credentials") from e

    async def validate_permissions(
        self, customer_id: str, required_permissions: list[str]
    ) -> bool:
        """Validate that customer has granted required permissions.

        Args:
            customer_id: Google Ads customer ID
            required_permissions: List of required permissions

        Returns:
            True if all permissions are granted
        """
        try:
            workflow_tokens = await self.get_workflow_credentials(customer_id)

            # Check if all required permissions are granted
            granted_permissions = set(workflow_tokens.permissions)
            required_permissions_set = set(required_permissions)

            return required_permissions_set.issubset(granted_permissions)

        except AuthenticationError:
            return False

    async def revoke_workflow_access(self, customer_id: str) -> None:
        """Revoke workflow access for a customer.

        Args:
            customer_id: Google Ads customer ID
        """
        try:
            # Use base token manager to revoke tokens
            self._base_token_manager.revoke_tokens(customer_id)

            # Clean up any active flows for this customer
            flows_to_remove = [
                flow_id
                for flow_id, flow in self._active_flows.items()
                if flow.customer_id == customer_id
            ]

            for flow_id in flows_to_remove:
                del self._active_flows[flow_id]

            logger.info(f"Revoked workflow access for customer {customer_id}")

        except Exception as e:
            logger.error(f"Failed to revoke workflow access: {e}")
            raise

    async def cleanup_expired_flows(self) -> int:
        """Clean up expired consent flows.

        Returns:
            Number of flows cleaned up
        """
        now = datetime.utcnow()
        expired_flows = [
            flow_id
            for flow_id, flow in self._active_flows.items()
            if flow.expires_at < now
        ]

        for flow_id in expired_flows:
            del self._active_flows[flow_id]

        if expired_flows:
            logger.debug(f"Cleaned up {len(expired_flows)} expired consent flows")

        return len(expired_flows)

    def get_active_flows(self, customer_id: str | None = None) -> list[ConsentFlow]:
        """Get active consent flows.

        Args:
            customer_id: Optional customer ID to filter by

        Returns:
            List of active consent flows
        """
        if customer_id:
            return [
                flow
                for flow in self._active_flows.values()
                if flow.customer_id == customer_id
            ]

        return list(self._active_flows.values())

    async def health_check(self) -> bool:
        """Check OAuth2 manager health.

        Returns:
            True if healthy
        """
        try:
            # Clean up expired flows
            await self.cleanup_expired_flows()

            # Check base token manager health
            return await asyncio.to_thread(
                lambda: hasattr(self._base_token_manager, "storage")
            )

        except Exception as e:
            logger.error(f"OAuth2 manager health check failed: {e}")
            return False
