"""HubSpot CRM connector implementation."""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests
from requests.exceptions import RequestException

from ..base import CRMConnector, Lead, LeadStage

logger = logging.getLogger(__name__)


class HubSpotConnector(CRMConnector):
    """Connector for HubSpot CRM integration."""

    BASE_URL = "https://api.hubapi.com"
    API_VERSION = "v3"

    # HubSpot to internal stage mapping
    STAGE_MAPPING = {
        "new": LeadStage.NEW,
        "open": LeadStage.NEW,
        "in_progress": LeadStage.CONTACTED,
        "qualified": LeadStage.QUALIFIED,
        "proposal": LeadStage.PROPOSAL,
        "negotiation": LeadStage.NEGOTIATION,
        "closedwon": LeadStage.CLOSED_WON,
        "closedlost": LeadStage.CLOSED_LOST,
    }

    def __init__(self, config: Dict[str, Any]):
        """Initialize HubSpot connector.

        Args:
            config: Configuration dict with:
                - api_key: HubSpot API key (for legacy auth)
                - access_token: HubSpot private app access token (preferred)
                - portal_id: HubSpot portal ID
                - custom_field_mapping: Dict mapping HubSpot fields to internal fields
        """
        super().__init__(config)
        self.api_key = config.get("api_key")
        self.access_token = config.get("access_token")
        self.portal_id = config.get("portal_id")
        self.custom_field_mapping = config.get("custom_field_mapping", {})
        self.session = requests.Session()
        self._setup_auth()

    def _setup_auth(self):
        """Set up authentication headers."""
        if self.access_token:
            self.session.headers.update(
                {"Authorization": f"Bearer {self.access_token}"}
            )
        elif self.api_key:
            # Legacy API key auth (deprecated by HubSpot)
            self.session.headers.update({"hapikey": self.api_key})
        else:
            raise ValueError("Either access_token or api_key must be provided")

    def authenticate(self) -> bool:
        """Test authentication with HubSpot API.

        Returns:
            True if authentication successful
        """
        try:
            # Test auth by getting account info
            url = f"{self.BASE_URL}/account-info/{self.API_VERSION}/details"
            self.rate_limiter.wait_if_needed()
            response = self.session.get(url)
            response.raise_for_status()
            return True
        except RequestException as e:
            self.logger.error(f"Authentication failed: {e}")
            return False

    def get_leads(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        stage: Optional[LeadStage] = None,
    ) -> List[Lead]:
        """Retrieve leads (contacts) from HubSpot.

        Args:
            start_date: Filter leads created after this date
            end_date: Filter leads created before this date
            stage: Filter by lead stage

        Returns:
            List of Lead objects
        """
        leads = []

        try:
            # Build filter groups
            filter_groups = []

            if start_date or end_date:
                date_filters = []
                if start_date:
                    date_filters.append(
                        {
                            "propertyName": "createdate",
                            "operator": "GTE",
                            "value": int(start_date.timestamp() * 1000),
                        }
                    )
                if end_date:
                    date_filters.append(
                        {
                            "propertyName": "createdate",
                            "operator": "LTE",
                            "value": int(end_date.timestamp() * 1000),
                        }
                    )
                filter_groups.append({"filters": date_filters})

            if stage:
                # Map internal stage to HubSpot lifecycle stage
                hs_stage = self._get_hubspot_stage(stage)
                if hs_stage:
                    filter_groups.append(
                        {
                            "filters": [
                                {
                                    "propertyName": "lifecyclestage",
                                    "operator": "EQ",
                                    "value": hs_stage,
                                }
                            ]
                        }
                    )

            # Build request body
            body = {
                "filterGroups": filter_groups,
                "properties": [
                    "email",
                    "phone",
                    "gclid",
                    "createdate",
                    "lifecyclestage",
                    "hs_lead_status",
                    "total_revenue",
                    "hs_analytics_source",
                    "hs_analytics_source_data_1",  # Campaign
                    "hs_analytics_source_data_2",  # Keyword
                ]
                + list(self.custom_field_mapping.keys()),
                "limit": 100,
            }

            # Paginate through results with safety limit
            after = None
            page_count = 0
            max_pages = 100  # Safety limit to prevent infinite loops

            while page_count < max_pages:
                if after:
                    body["after"] = after

                url = f"{self.BASE_URL}/crm/{self.API_VERSION}/objects/contacts/search"
                self.rate_limiter.wait_if_needed()
                response = self.session.post(url, json=body)
                response.raise_for_status()
                data = response.json()

                # Process contacts
                for contact in data.get("results", []):
                    lead = self._convert_hubspot_contact(contact)
                    if lead:
                        leads.append(lead)

                # Check for more pages
                paging = data.get("paging", {})
                if paging.get("next"):
                    after = paging["next"]["after"]
                    page_count += 1
                else:
                    break

            if page_count >= max_pages:
                self.logger.warning(f"Reached pagination limit of {max_pages} pages")

        except RequestException as e:
            self.logger.error(f"Failed to get leads: {e}")

        return leads

    def update_lead(self, lead_id: str, updates: Dict[str, Any]) -> bool:
        """Update a lead in HubSpot.

        Args:
            lead_id: HubSpot contact ID
            updates: Dict of properties to update

        Returns:
            True if update successful
        """
        try:
            # Map internal fields to HubSpot properties
            hs_properties = {}
            for key, value in updates.items():
                hs_key = self.custom_field_mapping.get(key, key)
                hs_properties[hs_key] = value

            url = f"{self.BASE_URL}/crm/{self.API_VERSION}/objects/contacts/{lead_id}"
            self.rate_limiter.wait_if_needed()
            response = self.session.patch(url, json={"properties": hs_properties})
            response.raise_for_status()
            return True

        except RequestException as e:
            self.logger.error(f"Failed to update lead {lead_id}: {e}")
            return False

    def sync_lead_stages(self, leads: List[Lead]) -> Dict[str, bool]:
        """Sync lead stages with HubSpot.

        Args:
            leads: List of leads to sync

        Returns:
            Dict mapping lead IDs to success status
        """
        results = {}

        for lead in leads:
            # Map internal stage to HubSpot lifecycle stage
            hs_stage = self._get_hubspot_stage(lead.stage)
            if hs_stage:
                success = self.update_lead(
                    lead.id, {"lifecyclestage": hs_stage, "hs_lead_status": hs_stage}
                )
                results[lead.id] = success
            else:
                results[lead.id] = False

        return results

    def get_custom_fields(self) -> Dict[str, Any]:
        """Get available custom fields from HubSpot.

        Returns:
            Dict of custom field definitions
        """
        custom_fields = {}

        try:
            url = f"{self.BASE_URL}/crm/{self.API_VERSION}/properties/contacts"
            self.rate_limiter.wait_if_needed()
            response = self.session.get(url)
            response.raise_for_status()
            data = response.json()

            for prop in data.get("results", []):
                if prop.get("type") == "custom":
                    custom_fields[prop["name"]] = {
                        "label": prop.get("label"),
                        "type": prop.get("fieldType"),
                        "description": prop.get("description"),
                        "options": prop.get("options", []),
                    }

        except RequestException as e:
            self.logger.error(f"Failed to get custom fields: {e}")

        return custom_fields

    def create_or_update_lead(self, lead_data: Dict[str, Any]) -> Optional[str]:
        """Create or update a lead in HubSpot.

        Args:
            lead_data: Lead data including email (required for deduplication)

        Returns:
            HubSpot contact ID if successful
        """
        try:
            email = lead_data.get("email")
            if not email:
                self.logger.error("Email is required for HubSpot lead creation")
                return None

            # Search for existing contact
            search_body = {
                "filterGroups": [
                    {
                        "filters": [
                            {"propertyName": "email", "operator": "EQ", "value": email}
                        ]
                    }
                ],
                "properties": ["id"],
                "limit": 1,
            }

            url = f"{self.BASE_URL}/crm/{self.API_VERSION}/objects/contacts/search"
            self.rate_limiter.wait_if_needed()
            response = self.session.post(url, json=search_body)
            response.raise_for_status()
            search_results = response.json()

            if search_results.get("results"):
                # Update existing contact
                contact_id = search_results["results"][0]["id"]
                self.update_lead(contact_id, lead_data)
                return contact_id
            else:
                # Create new contact
                url = f"{self.BASE_URL}/crm/{self.API_VERSION}/objects/contacts"
                self.rate_limiter.wait_if_needed()
                response = self.session.post(url, json={"properties": lead_data})
                response.raise_for_status()
                return response.json()["id"]

        except RequestException as e:
            self.logger.error(f"Failed to create/update lead: {e}")
            return None

    def _convert_hubspot_contact(self, contact: Dict[str, Any]) -> Optional[Lead]:
        """Convert HubSpot contact to internal Lead object.

        Args:
            contact: HubSpot contact data

        Returns:
            Lead object or None if conversion fails
        """
        try:
            properties = contact.get("properties", {})

            # Parse created date
            created_timestamp = properties.get("createdate")
            created_at = datetime.fromtimestamp(
                int(created_timestamp) / 1000, tz=timezone.utc
            )

            # Map HubSpot stage to internal stage
            hs_stage = properties.get("lifecyclestage", "new")
            stage = self.STAGE_MAPPING.get(hs_stage.lower(), LeadStage.NEW)

            # Extract custom fields
            custom_fields = {}
            for internal_field, hs_field in self.custom_field_mapping.items():
                if hs_field in properties:
                    custom_fields[internal_field] = properties[hs_field]

            lead = Lead(
                id=contact["id"],
                email=properties.get("email"),
                phone=properties.get("phone"),
                gclid=properties.get("gclid"),
                created_at=created_at,
                stage=stage,
                value=float(properties.get("total_revenue", 0) or 0),
                source=properties.get("hs_analytics_source"),
                campaign_id=properties.get("hs_analytics_source_data_1"),
                keyword=properties.get("hs_analytics_source_data_2"),
                custom_fields=custom_fields,
            )

            return lead

        except Exception as e:
            self.logger.error(f"Failed to convert HubSpot contact: {e}")
            return None

    def _get_hubspot_stage(self, stage: LeadStage) -> Optional[str]:
        """Map internal stage to HubSpot lifecycle stage.

        Args:
            stage: Internal lead stage

        Returns:
            HubSpot lifecycle stage or None
        """
        # Reverse mapping
        for hs_stage, internal_stage in self.STAGE_MAPPING.items():
            if internal_stage == stage:
                return hs_stage
        return None
