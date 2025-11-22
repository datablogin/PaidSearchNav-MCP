"""Offline conversion tracking implementations."""

import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from google.ads.googleads.errors import GoogleAdsException

from paidsearchnav.platforms.google.client import GoogleAdsClient

from .base import OfflineConversion, OfflineConversionTracker

logger = logging.getLogger(__name__)


class EnhancedConversionsTracker(OfflineConversionTracker):
    """Implements Google Ads Enhanced Conversions for Leads."""

    def __init__(self, google_ads_client: GoogleAdsClient):
        super().__init__(google_ads_client)
        self.conversion_upload_service = None
        self.conversion_action_service = None
        self._init_services()

    def _init_services(self):
        """Initialize Google Ads services."""
        try:
            client = self.client.client
            self.conversion_upload_service = client.get_service(
                "ConversionUploadService"
            )
            self.conversion_action_service = client.get_service(
                "ConversionActionService"
            )
        except Exception as e:
            logger.error(f"Failed to initialize services: {e}")

    def upload_conversions(
        self, conversions: List[OfflineConversion]
    ) -> Dict[str, Any]:
        """Upload offline conversions with enhanced conversion data.

        Args:
            conversions: List of offline conversions to upload

        Returns:
            Dict with upload results
        """
        if not conversions:
            return {"successful": 0, "failed": 0, "errors": []}

        results = {
            "successful": 0,
            "failed": 0,
            "errors": [],
            "partial_failures": [],
        }

        # Validate conversions first
        valid_conversions = []
        for conversion in conversions:
            validation_errors = self.validate_conversion(conversion)
            if validation_errors:
                results["failed"] += 1
                results["errors"].extend(validation_errors)
            else:
                valid_conversions.append(conversion)

        if not valid_conversions:
            return results

        # Build conversion upload request
        try:
            request = self._build_upload_request(valid_conversions)
            response = self.conversion_upload_service.upload_click_conversions(
                request=request
            )

            # Process response
            if response.partial_failure_error:
                results["partial_failures"].append(
                    self._parse_partial_failure(response.partial_failure_error)
                )

            # Count successes
            results["successful"] = len(valid_conversions) - len(
                results.get("partial_failures", [])
            )
            results["failed"] += len(results.get("partial_failures", []))

            logger.info(
                f"Uploaded {results['successful']} conversions successfully, "
                f"{results['failed']} failed"
            )

        except GoogleAdsException as ex:
            logger.error(f"Google Ads API error: {ex}")
            results["failed"] = len(valid_conversions)
            results["errors"].append(self._format_google_ads_error(ex))

        except Exception as e:
            logger.error(f"Unexpected error during upload: {e}")
            results["failed"] = len(valid_conversions)
            results["errors"].append(str(e))

        return results

    def validate_conversion(self, conversion: OfflineConversion) -> List[str]:
        """Validate an offline conversion.

        Args:
            conversion: The conversion to validate

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # GCLID validation
        if not conversion.gclid:
            errors.append("GCLID is required for offline conversion tracking")
        elif len(conversion.gclid) < 20:
            errors.append("Invalid GCLID format")

        # Conversion name validation
        if not conversion.conversion_name:
            errors.append("Conversion name is required")

        # Time validation
        if not conversion.conversion_time:
            errors.append("Conversion time is required")
        elif conversion.conversion_time > datetime.now(timezone.utc):
            errors.append("Conversion time cannot be in the future")

        # Value validation
        if conversion.conversion_value is None:
            errors.append("Conversion value is required")
        elif conversion.conversion_value < 0:
            errors.append("Conversion value cannot be negative")

        # Currency validation
        if not conversion.currency_code:
            errors.append("Currency code is required")
        elif len(conversion.currency_code) != 3:
            errors.append("Currency code must be 3 characters (e.g., USD)")

        return errors

    def get_conversion_actions(self) -> List[Dict[str, Any]]:
        """Get available conversion actions from Google Ads.

        Returns:
            List of conversion action details
        """
        conversion_actions = []

        try:
            ga_service = self.client.client.get_service("GoogleAdsService")
            query = """
                SELECT
                    conversion_action.id,
                    conversion_action.name,
                    conversion_action.status,
                    conversion_action.type,
                    conversion_action.category,
                    conversion_action.value_settings.default_value,
                    conversion_action.value_settings.default_currency_code
                FROM conversion_action
                WHERE conversion_action.status = 'ENABLED'
            """

            response = ga_service.search_stream(
                customer_id=self.client.customer_id, query=query
            )

            for batch in response:
                for row in batch.results:
                    action = row.conversion_action
                    conversion_actions.append(
                        {
                            "id": action.id,
                            "name": action.name,
                            "type": action.type.name,
                            "category": action.category.name,
                            "default_value": action.value_settings.default_value,
                            "currency": action.value_settings.default_currency_code,
                        }
                    )

        except Exception as e:
            logger.error(f"Failed to get conversion actions: {e}")

        return conversion_actions

    def _build_upload_request(self, conversions: List[OfflineConversion]) -> Dict:
        """Build the conversion upload request.

        Args:
            conversions: List of conversions to upload

        Returns:
            Upload request dictionary
        """
        client = self.client.client
        upload_operations = []

        for conversion in conversions:
            # Create click conversion
            click_conversion = client.get_type("ClickConversion")
            click_conversion.gclid = conversion.gclid
            click_conversion.conversion_action = self._get_conversion_action_resource(
                conversion.conversion_name
            )
            click_conversion.conversion_date_time = conversion.conversion_time.strftime(
                "%Y-%m-%d %H:%M:%S+00:00"
            )
            click_conversion.conversion_value = conversion.conversion_value
            click_conversion.currency_code = conversion.currency_code

            # Add custom variables if provided
            if conversion.custom_variables:
                for key, value in conversion.custom_variables.items():
                    if key.startswith("custom_variable_"):
                        custom_var = client.get_type("CustomVariable")
                        custom_var.key = key
                        custom_var.value = str(value)
                        click_conversion.custom_variables.append(custom_var)

            # Add order ID if provided (for deduplication)
            if conversion.order_id:
                click_conversion.order_id = conversion.order_id

            upload_operations.append(click_conversion)

        return {
            "customer_id": self.client.customer_id,
            "conversions": upload_operations,
            "partial_failure": True,  # Continue on individual errors
        }

    def _get_conversion_action_resource(self, conversion_name: str) -> str:
        """Get the resource name for a conversion action.

        Args:
            conversion_name: The conversion action name

        Returns:
            The resource name
        """
        # Look up conversion action ID from cache or API
        conversion_action_id = self._lookup_conversion_action_id(conversion_name)
        if conversion_action_id:
            return f"customers/{self.client.customer_id}/conversionActions/{conversion_action_id}"
        else:
            # Fallback to name-based resource (may fail if action doesn't exist)
            logger.warning(
                f"Conversion action '{conversion_name}' not found, using name as ID"
            )
            return f"customers/{self.client.customer_id}/conversionActions/{conversion_name}"

    def _lookup_conversion_action_id(self, conversion_name: str) -> Optional[str]:
        """Look up conversion action ID by name.

        Args:
            conversion_name: The conversion action name

        Returns:
            The conversion action ID if found
        """
        # Check cache first
        if not hasattr(self, "_conversion_action_cache"):
            self._conversion_action_cache = {}

        if conversion_name in self._conversion_action_cache:
            return self._conversion_action_cache[conversion_name]

        # Query API for conversion actions
        try:
            ga_service = self.client.client.get_service("GoogleAdsService")
            query = f"""
                SELECT
                    conversion_action.id,
                    conversion_action.name
                FROM conversion_action
                WHERE conversion_action.name = '{conversion_name}'
                AND conversion_action.status = 'ENABLED'
                LIMIT 1
            """

            response = ga_service.search_stream(
                customer_id=self.client.customer_id, query=query
            )

            for batch in response:
                for row in batch.results:
                    conversion_id = str(row.conversion_action.id)
                    # Cache the result
                    self._conversion_action_cache[conversion_name] = conversion_id
                    return conversion_id

        except Exception as e:
            logger.error(f"Failed to lookup conversion action '{conversion_name}': {e}")

        return None

    def _parse_partial_failure(self, error) -> Dict[str, Any]:
        """Parse partial failure error details."""
        return {
            "code": error.code,
            "message": error.message,
            "details": error.details,
        }

    def _format_google_ads_error(self, exception: GoogleAdsException) -> str:
        """Format Google Ads exception for logging."""
        errors = []
        for error in exception.failure.errors:
            errors.append(
                f"Error: {error.error_code}: {error.message} (trigger: {error.trigger})"
            )
        return "; ".join(errors)


class GCLIDTracker:
    """Tracks and manages Google Click IDs for offline conversion attribution."""

    def __init__(self, storage_backend=None):
        self.storage = storage_backend
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def store_gclid(
        self,
        gclid: str,
        timestamp: datetime,
        landing_page: Optional[str] = None,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> bool:
        """Store a GCLID with associated metadata.

        Args:
            gclid: The Google Click ID
            timestamp: When the click occurred
            landing_page: The landing page URL
            user_agent: The user's browser user agent
            ip_address: The user's IP address (for geo targeting)

        Returns:
            True if stored successfully
        """
        try:
            # Hash PII data for privacy
            hashed_ip = None
            if ip_address:
                hashed_ip = hashlib.sha256(ip_address.encode()).hexdigest()

            gclid_data = {
                "gclid": gclid,
                "timestamp": timestamp.isoformat(),
                "landing_page": landing_page,
                "user_agent": user_agent,
                "hashed_ip": hashed_ip,
            }

            if self.storage:
                return self.storage.store_gclid(gclid_data)
            else:
                # Log for now if no storage backend
                self.logger.info(f"GCLID tracked: {gclid}")
                return True

        except Exception as e:
            self.logger.error(f"Failed to store GCLID: {e}")
            return False

    def get_gclid_data(self, gclid: str) -> Optional[Dict[str, Any]]:
        """Retrieve data associated with a GCLID.

        Args:
            gclid: The Google Click ID

        Returns:
            GCLID data if found
        """
        if self.storage:
            return self.storage.get_gclid(gclid)
        return None

    def associate_gclid_with_lead(
        self, gclid: str, lead_id: str, lead_data: Dict[str, Any]
    ) -> bool:
        """Associate a GCLID with a lead record.

        Args:
            gclid: The Google Click ID
            lead_id: The lead ID from CRM
            lead_data: Additional lead data

        Returns:
            True if associated successfully
        """
        try:
            association = {
                "gclid": gclid,
                "lead_id": lead_id,
                "associated_at": datetime.now(timezone.utc).isoformat(),
                "lead_data": lead_data,
            }

            if self.storage:
                return self.storage.associate_lead(association)
            else:
                self.logger.info(f"GCLID {gclid} associated with lead {lead_id}")
                return True

        except Exception as e:
            self.logger.error(f"Failed to associate GCLID with lead: {e}")
            return False

    def cleanup_old_gclids(self, days_to_keep: int = 540) -> int:
        """Clean up old GCLIDs beyond Google's attribution window.

        Args:
            days_to_keep: Number of days to keep GCLIDs (default 540 days)

        Returns:
            Number of GCLIDs cleaned up
        """
        if self.storage:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_to_keep)
            return self.storage.cleanup_gclids(cutoff_date)
        return 0
