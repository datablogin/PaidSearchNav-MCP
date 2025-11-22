"""Salesforce CRM connector implementation."""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    from simple_salesforce import Salesforce, SalesforceAuthenticationFailed
    from simple_salesforce.exceptions import SalesforceError

    SALESFORCE_AVAILABLE = True
except ImportError:
    SALESFORCE_AVAILABLE = False
    Salesforce = None
    SalesforceAuthenticationFailed = Exception
    SalesforceError = Exception

from ..base import CRMConnector, Lead, LeadQuality, LeadStage

logger = logging.getLogger(__name__)


class SalesforceConnector(CRMConnector):
    """Connector for Salesforce CRM integration."""

    # Salesforce to internal stage mapping
    STAGE_MAPPING = {
        "New": LeadStage.NEW,
        "Working": LeadStage.CONTACTED,
        "Qualified": LeadStage.QUALIFIED,
        "Proposal": LeadStage.PROPOSAL,
        "Negotiation": LeadStage.NEGOTIATION,
        "Closed Won": LeadStage.CLOSED_WON,
        "Closed Lost": LeadStage.CLOSED_LOST,
    }

    # Lead quality mapping
    QUALITY_MAPPING = {
        "Hot": LeadQuality.HIGH,
        "Warm": LeadQuality.MEDIUM,
        "Cold": LeadQuality.LOW,
        "Unqualified": LeadQuality.UNQUALIFIED,
    }

    def __init__(self, config: Dict[str, Any]):
        """Initialize Salesforce connector.

        Args:
            config: Configuration dict with:
                - username: Salesforce username
                - password: Salesforce password
                - security_token: Salesforce security token
                - domain: Salesforce domain (login/test)
                - client_id: Connected app client ID (optional)
                - client_secret: Connected app client secret (optional)
                - custom_field_mapping: Dict mapping Salesforce fields to internal
        """
        super().__init__(config)
        self.username = config.get("username")
        self.password = config.get("password")
        self.security_token = config.get("security_token")
        self.domain = config.get("domain", "login")
        self.client_id = config.get("client_id")
        self.client_secret = config.get("client_secret")
        self.custom_field_mapping = config.get("custom_field_mapping", {})
        self.sf = None

    def authenticate(self) -> bool:
        """Authenticate with Salesforce API.

        Returns:
            True if authentication successful
        """
        if not SALESFORCE_AVAILABLE:
            self.logger.error("simple-salesforce library not available")
            return False

        try:
            # Simple-salesforce handles auth
            self.sf = Salesforce(
                username=self.username,
                password=self.password,
                security_token=self.security_token,
                domain=self.domain,
                client_id=self.client_id,
            )
            return True
        except SalesforceAuthenticationFailed as e:
            self.logger.error(f"Authentication failed: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error during authentication: {e}")
            return False

    def get_leads(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        stage: Optional[LeadStage] = None,
    ) -> List[Lead]:
        """Retrieve leads from Salesforce.

        Args:
            start_date: Filter leads created after this date
            end_date: Filter leads created before this date
            stage: Filter by lead stage

        Returns:
            List of Lead objects
        """
        if not self.sf:
            self.logger.error("Not authenticated with Salesforce")
            return []

        leads = []

        try:
            # Build SOQL query
            query = """
                SELECT Id, Email, Phone, Status, Rating, CreatedDate,
                       FirstName, LastName, Company, LeadSource,
                       Campaign__c, Keyword__c, GCLID__c,
                       ConvertedOpportunityId, ConvertedAccountId
                FROM Lead
                WHERE IsDeleted = false
            """

            # Add date filters
            conditions = []
            if start_date:
                conditions.append(f"CreatedDate >= {start_date.isoformat()}Z")
            if end_date:
                conditions.append(f"CreatedDate <= {end_date.isoformat()}Z")
            if stage:
                sf_status = self._get_salesforce_status(stage)
                if sf_status:
                    conditions.append(f"Status = '{sf_status}'")

            if conditions:
                query += " AND " + " AND ".join(conditions)

            query += " ORDER BY CreatedDate DESC LIMIT 1000"

            # Execute query
            self.rate_limiter.wait_if_needed()
            result = self.sf.query(query)

            # Process records
            for record in result.get("records", []):
                lead = self._convert_salesforce_lead(record)
                if lead:
                    leads.append(lead)

            # Handle pagination if needed
            while not result["done"] and result.get("nextRecordsUrl"):
                self.rate_limiter.wait_if_needed()
                result = self.sf.query_more(
                    result["nextRecordsUrl"], identifier_is_url=True
                )
                for record in result.get("records", []):
                    lead = self._convert_salesforce_lead(record)
                    if lead:
                        leads.append(lead)

        except SalesforceError as e:
            self.logger.error(f"Failed to get leads: {e}")

        return leads

    def update_lead(self, lead_id: str, updates: Dict[str, Any]) -> bool:
        """Update a lead in Salesforce.

        Args:
            lead_id: Salesforce Lead ID
            updates: Dict of fields to update

        Returns:
            True if update successful
        """
        if not self.sf:
            self.logger.error("Not authenticated with Salesforce")
            return False

        try:
            # Map internal fields to Salesforce fields
            sf_updates = {}
            for key, value in updates.items():
                sf_key = self.custom_field_mapping.get(key, key)
                # Handle special cases
                if key == "stage":
                    sf_updates["Status"] = self._get_salesforce_status(value)
                elif key == "quality":
                    sf_updates["Rating"] = self._get_salesforce_rating(value)
                else:
                    sf_updates[sf_key] = value

            # Update lead
            self.rate_limiter.wait_if_needed()
            self.sf.Lead.update(lead_id, sf_updates)
            return True

        except SalesforceError as e:
            self.logger.error(f"Failed to update lead {lead_id}: {e}")
            return False

    def sync_lead_stages(self, leads: List[Lead]) -> Dict[str, bool]:
        """Sync lead stages with Salesforce.

        Args:
            leads: List of leads to sync

        Returns:
            Dict mapping lead IDs to success status
        """
        results = {}

        for lead in leads:
            sf_status = self._get_salesforce_status(lead.stage)
            if sf_status:
                success = self.update_lead(lead.id, {"Status": sf_status})
                results[lead.id] = success
            else:
                results[lead.id] = False

        return results

    def get_custom_fields(self) -> Dict[str, Any]:
        """Get available custom fields from Salesforce.

        Returns:
            Dict of custom field definitions
        """
        if not self.sf:
            self.logger.error("Not authenticated with Salesforce")
            return {}

        custom_fields = {}

        try:
            # Describe Lead object
            self.rate_limiter.wait_if_needed()
            lead_metadata = self.sf.Lead.describe()

            for field in lead_metadata.get("fields", []):
                if field.get("custom"):
                    custom_fields[field["name"]] = {
                        "label": field.get("label"),
                        "type": field.get("type"),
                        "length": field.get("length"),
                        "picklistValues": field.get("picklistValues", []),
                        "updateable": field.get("updateable"),
                    }

        except SalesforceError as e:
            self.logger.error(f"Failed to get custom fields: {e}")

        return custom_fields

    def create_or_update_lead(self, lead_data: Dict[str, Any]) -> Optional[str]:
        """Create or update a lead in Salesforce.

        Args:
            lead_data: Lead data including email for deduplication

        Returns:
            Salesforce Lead ID if successful
        """
        if not self.sf:
            self.logger.error("Not authenticated with Salesforce")
            return None

        try:
            email = lead_data.get("email")
            if email:
                # Search for existing lead - escape single quotes to prevent SOQL injection
                escaped_email = email.replace("'", "\\'")
                query = f"SELECT Id FROM Lead WHERE Email = '{escaped_email}' LIMIT 1"
                self.rate_limiter.wait_if_needed()
                result = self.sf.query(query)

                if result["records"]:
                    # Update existing lead
                    lead_id = result["records"][0]["Id"]
                    self.update_lead(lead_id, lead_data)
                    return lead_id

            # Create new lead
            # Ensure required fields
            if "LastName" not in lead_data:
                lead_data["LastName"] = lead_data.get("email", "Unknown").split("@")[0]
            if "Company" not in lead_data:
                lead_data["Company"] = "Unknown"

            self.rate_limiter.wait_if_needed()
            result = self.sf.Lead.create(lead_data)
            return result["id"] if result["success"] else None

        except SalesforceError as e:
            self.logger.error(f"Failed to create/update lead: {e}")
            return None

    def get_opportunities_from_leads(
        self, lead_ids: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        """Get opportunities created from converted leads.

        Args:
            lead_ids: List of Salesforce Lead IDs

        Returns:
            Dict mapping lead IDs to opportunity data
        """
        if not self.sf:
            return {}

        opportunities = {}

        try:
            # Build query for converted leads
            lead_ids_str = "', '".join(lead_ids)
            query = f"""
                SELECT Id, ConvertedOpportunityId, ConvertedAccountId
                FROM Lead
                WHERE Id IN ('{lead_ids_str}')
                AND IsConverted = true
                AND ConvertedOpportunityId != null
            """

            self.rate_limiter.wait_if_needed()
            result = self.sf.query(query)

            # Get opportunity details
            opp_ids = [
                r["ConvertedOpportunityId"]
                for r in result["records"]
                if r.get("ConvertedOpportunityId")
            ]

            if opp_ids:
                opp_ids_str = "', '".join(opp_ids)
                opp_query = f"""
                    SELECT Id, Name, Amount, StageName, CloseDate,
                           Probability, IsClosed, IsWon
                    FROM Opportunity
                    WHERE Id IN ('{opp_ids_str}')
                """

                self.rate_limiter.wait_if_needed()
                opp_result = self.sf.query(opp_query)

                # Map opportunities back to leads
                opp_by_id = {r["Id"]: r for r in opp_result["records"]}

                for lead_record in result["records"]:
                    opp_id = lead_record.get("ConvertedOpportunityId")
                    if opp_id and opp_id in opp_by_id:
                        opportunities[lead_record["Id"]] = opp_by_id[opp_id]

        except SalesforceError as e:
            self.logger.error(f"Failed to get opportunities: {e}")

        return opportunities

    def _convert_salesforce_lead(self, record: Dict[str, Any]) -> Optional[Lead]:
        """Convert Salesforce Lead to internal Lead object.

        Args:
            record: Salesforce Lead record

        Returns:
            Lead object or None if conversion fails
        """
        try:
            # Parse created date
            created_date_str = record.get("CreatedDate")
            created_at = datetime.fromisoformat(created_date_str.replace("Z", "+00:00"))

            # Map Salesforce status to internal stage
            sf_status = record.get("Status", "New")
            stage = self.STAGE_MAPPING.get(sf_status, LeadStage.NEW)

            # Map rating to quality
            sf_rating = record.get("Rating")
            quality = self.QUALITY_MAPPING.get(sf_rating) if sf_rating else None

            # Extract custom fields
            custom_fields = {}
            for sf_field, internal_field in self.custom_field_mapping.items():
                if sf_field in record:
                    custom_fields[internal_field] = record[sf_field]

            lead = Lead(
                id=record["Id"],
                email=record.get("Email"),
                phone=record.get("Phone"),
                gclid=record.get("GCLID__c"),
                created_at=created_at,
                stage=stage,
                quality=quality,
                source=record.get("LeadSource"),
                campaign_id=record.get("Campaign__c"),
                keyword=record.get("Keyword__c"),
                custom_fields=custom_fields,
            )

            return lead

        except Exception as e:
            self.logger.error(f"Failed to convert Salesforce lead: {e}")
            return None

    def _get_salesforce_status(self, stage: LeadStage) -> Optional[str]:
        """Map internal stage to Salesforce Status.

        Args:
            stage: Internal lead stage

        Returns:
            Salesforce Status value or None
        """
        for sf_status, internal_stage in self.STAGE_MAPPING.items():
            if internal_stage == stage:
                return sf_status
        return None

    def _get_salesforce_rating(self, quality: LeadQuality) -> Optional[str]:
        """Map internal quality to Salesforce Rating.

        Args:
            quality: Internal lead quality

        Returns:
            Salesforce Rating value or None
        """
        for sf_rating, internal_quality in self.QUALITY_MAPPING.items():
            if internal_quality == quality:
                return sf_rating
        return None
