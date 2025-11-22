"""GA4 API authentication module for PaidSearchNav.

This module handles authentication for the Google Analytics 4 Data API,
supporting both service account and application default credentials.
"""

import logging
from pathlib import Path
from typing import Any, Dict, Optional

try:
    from google.analytics.data_v1beta import BetaAnalyticsDataClient
    from google.auth import default
    from google.auth.exceptions import DefaultCredentialsError
    from google.oauth2 import service_account

    GA4_API_AVAILABLE = True
except ImportError:
    GA4_API_AVAILABLE = False
    BetaAnalyticsDataClient = None
    default = None
    service_account = None
    DefaultCredentialsError = Exception

from paidsearchnav_mcp.core.config import GA4Config

logger = logging.getLogger(__name__)


class GA4AuthenticationError(Exception):
    """Exception raised when GA4 authentication fails."""

    pass


class GA4Authenticator:
    """Handles GA4 API authentication and client creation."""

    def __init__(self, config: GA4Config):
        """Initialize the GA4 authenticator.

        Args:
            config: GA4 configuration containing authentication settings
        """
        if not GA4_API_AVAILABLE:
            raise ImportError(
                "Google Analytics Data API is required for GA4 integration. "
                "Install with: pip install google-analytics-data"
            )

        self.config = config
        self._client: Optional[BetaAnalyticsDataClient] = None

    def get_client(self) -> BetaAnalyticsDataClient:
        """Get authenticated GA4 Data API client.

        Returns:
            Authenticated GA4 Data API client

        Raises:
            GA4AuthenticationError: If authentication fails
        """
        if self._client is None:
            self._client = self._create_client()
        return self._client

    def _create_client(self) -> BetaAnalyticsDataClient:
        """Create authenticated GA4 Data API client.

        Returns:
            Authenticated GA4 Data API client

        Raises:
            GA4AuthenticationError: If authentication fails
        """
        try:
            credentials = self._get_credentials()

            # Create client with optional timeout settings
            client_options = {}
            if hasattr(self.config, "request_timeout_seconds"):
                client_options["timeout"] = self.config.request_timeout_seconds

            return BetaAnalyticsDataClient(
                credentials=credentials, client_options=client_options
            )

        except Exception as e:
            logger.error(f"Failed to create GA4 client: {e}")
            raise GA4AuthenticationError(f"GA4 authentication failed: {e}")

    def _get_credentials(self):
        """Get Google credentials for GA4 API access.

        Returns:
            Google credentials object

        Raises:
            GA4AuthenticationError: If credentials cannot be obtained
        """
        try:
            # Try service account key file first
            if self.config.service_account_key_path:
                key_path = Path(self.config.service_account_key_path)
                if not key_path.exists():
                    raise GA4AuthenticationError(
                        f"Service account key file not found: {key_path}"
                    )

                logger.info(f"Using service account credentials from {key_path}")
                return service_account.Credentials.from_service_account_file(
                    str(key_path),
                    scopes=["https://www.googleapis.com/auth/analytics.readonly"],
                )

            # Fall back to application default credentials
            elif self.config.use_application_default_credentials:
                logger.info("Using application default credentials for GA4")
                credentials, project = default(
                    scopes=["https://www.googleapis.com/auth/analytics.readonly"]
                )
                return credentials

            else:
                raise GA4AuthenticationError(
                    "No authentication method configured for GA4 API"
                )

        except DefaultCredentialsError:
            raise GA4AuthenticationError(
                "Application default credentials not available. "
                "Run 'gcloud auth application-default login' or provide a service account key file."
            )
        except Exception as e:
            logger.error(f"GA4 credential acquisition failed: {e}")
            raise GA4AuthenticationError(f"Failed to obtain GA4 credentials: {e}")

    def test_authentication(self) -> bool:
        """Test GA4 API authentication by making a simple API call.

        Returns:
            True if authentication is successful, False otherwise
        """
        try:
            client = self.get_client()

            # Make a minimal API call to test authentication
            # This will fail gracefully if property_id is not set or invalid
            from google.analytics.data_v1beta.types import (
                DateRange,
                Dimension,
                RunReportRequest,
            )

            request = RunReportRequest(
                property=f"properties/{self.config.property_id}",
                date_ranges=[DateRange(start_date="yesterday", end_date="yesterday")],
                dimensions=[Dimension(name="date")],
                limit=1,
            )

            # This will raise an exception if authentication fails
            response = client.run_report(request)

            logger.info("GA4 authentication test successful")
            return True

        except Exception as e:
            logger.error(f"GA4 authentication test failed: {e}")
            return False

    def validate_property_access(self, property_id: str) -> bool:
        """Validate that the authenticated user has access to the specified GA4 property.

        Args:
            property_id: GA4 property ID to validate

        Returns:
            True if access is valid, False otherwise
        """
        try:
            client = self.get_client()

            from google.analytics.data_v1beta.types import GetMetadataRequest

            request = GetMetadataRequest(name=f"properties/{property_id}/metadata")

            # This will fail if the property doesn't exist or user lacks access
            metadata = client.get_metadata(request)

            logger.info(f"Successfully validated access to GA4 property {property_id}")
            return True

        except Exception as e:
            logger.error(
                f"Failed to validate access to GA4 property {property_id}: {e}"
            )
            return False

    def get_property_metadata(self, property_id: str) -> Optional[Dict[str, Any]]:
        """Get metadata for the specified GA4 property.

        Args:
            property_id: GA4 property ID

        Returns:
            Property metadata dictionary or None if failed
        """
        try:
            client = self.get_client()

            from google.analytics.data_v1beta.types import GetMetadataRequest

            request = GetMetadataRequest(name=f"properties/{property_id}/metadata")

            metadata = client.get_metadata(request)

            # Convert to dictionary for easier handling
            metadata_dict = {
                "dimensions": [
                    {
                        "api_name": dim.api_name,
                        "ui_name": dim.ui_name,
                        "description": dim.description,
                        "type": dim.type_.name
                        if hasattr(dim.type_, "name")
                        else str(dim.type_),
                    }
                    for dim in metadata.dimensions
                ],
                "metrics": [
                    {
                        "api_name": metric.api_name,
                        "ui_name": metric.ui_name,
                        "description": metric.description,
                        "type": metric.type_.name
                        if hasattr(metric.type_, "name")
                        else str(metric.type_),
                    }
                    for metric in metadata.metrics
                ],
            }

            logger.info(f"Retrieved metadata for GA4 property {property_id}")
            return metadata_dict

        except Exception as e:
            logger.error(f"Failed to get metadata for GA4 property {property_id}: {e}")
            return None
