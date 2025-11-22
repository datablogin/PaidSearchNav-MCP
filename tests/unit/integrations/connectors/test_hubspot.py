"""Tests for HubSpot CRM connector."""

from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest
import requests

from paidsearchnav.integrations.base import Lead, LeadStage
from paidsearchnav.integrations.connectors.hubspot import HubSpotConnector


class TestHubSpotConnector:
    """Test HubSpotConnector functionality."""

    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return {
            "access_token": "test_token_123",
            "portal_id": "12345",
            "custom_field_mapping": {
                "lead_score": "hs_lead_score",
                "persona": "hs_persona",
            },
        }

    @pytest.fixture
    def connector(self, config):
        """Create HubSpotConnector instance."""
        with patch("requests.Session"):
            connector = HubSpotConnector(config)
            connector.session = Mock()
        return connector

    def test_initialization_with_access_token(self, config):
        """Test initialization with access token."""
        connector = HubSpotConnector(config)
        assert connector.access_token == "test_token_123"
        assert connector.portal_id == "12345"
        assert connector.custom_field_mapping["lead_score"] == "hs_lead_score"

    def test_initialization_with_api_key(self):
        """Test initialization with legacy API key."""
        config = {"api_key": "legacy_key_123"}
        connector = HubSpotConnector(config)
        assert connector.api_key == "legacy_key_123"

    def test_initialization_no_auth(self):
        """Test initialization without authentication."""
        with pytest.raises(ValueError, match="Either access_token or api_key"):
            HubSpotConnector({})

    def test_authenticate_success(self, connector):
        """Test successful authentication."""
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        connector.session.get.return_value = mock_response

        result = connector.authenticate()

        assert result is True
        connector.session.get.assert_called_once()

    def test_authenticate_failure(self, connector):
        """Test failed authentication."""
        connector.session.get.side_effect = requests.RequestException("Auth failed")

        result = connector.authenticate()

        assert result is False

    def test_get_leads_basic(self, connector):
        """Test basic lead retrieval."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "results": [
                {
                    "id": "contact1",
                    "properties": {
                        "email": "test1@example.com",
                        "phone": "+1234567890",
                        "gclid": "gclid_123",
                        "createdate": "1234567890000",
                        "lifecyclestage": "qualified",
                        "total_revenue": "1000",
                        "hs_analytics_source": "PAID_SEARCH",
                        "hs_analytics_source_data_1": "campaign123",
                        "hs_analytics_source_data_2": "keyword test",
                    },
                }
            ],
            "paging": {},
        }
        mock_response.raise_for_status.return_value = None
        connector.session.post.return_value = mock_response

        leads = connector.get_leads()

        assert len(leads) == 1
        assert leads[0].id == "contact1"
        assert leads[0].email == "test1@example.com"
        assert leads[0].stage == LeadStage.QUALIFIED
        assert leads[0].value == 1000.0

    def test_get_leads_with_date_filter(self, connector):
        """Test lead retrieval with date filters."""
        start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2024, 1, 31, tzinfo=timezone.utc)

        mock_response = Mock()
        mock_response.json.return_value = {"results": [], "paging": {}}
        mock_response.raise_for_status.return_value = None
        connector.session.post.return_value = mock_response

        leads = connector.get_leads(start_date=start_date, end_date=end_date)

        # Check that date filters were included in request
        call_args = connector.session.post.call_args
        request_body = call_args[1]["json"]
        assert len(request_body["filterGroups"]) > 0

        # Should have date filters
        date_filters = request_body["filterGroups"][0]["filters"]
        assert any(f["operator"] == "GTE" for f in date_filters)
        assert any(f["operator"] == "LTE" for f in date_filters)

    def test_get_leads_with_stage_filter(self, connector):
        """Test lead retrieval with stage filter."""
        mock_response = Mock()
        mock_response.json.return_value = {"results": [], "paging": {}}
        mock_response.raise_for_status.return_value = None
        connector.session.post.return_value = mock_response

        leads = connector.get_leads(stage=LeadStage.QUALIFIED)

        # Check that stage filter was included
        call_args = connector.session.post.call_args
        request_body = call_args[1]["json"]

        # Find stage filter
        stage_filter_found = False
        for group in request_body["filterGroups"]:
            for filter_item in group["filters"]:
                if filter_item["propertyName"] == "lifecyclestage":
                    stage_filter_found = True
                    assert filter_item["value"] == "qualified"

        assert stage_filter_found

    def test_get_leads_pagination(self, connector):
        """Test lead retrieval with pagination."""
        # First page
        mock_response1 = Mock()
        mock_response1.json.return_value = {
            "results": [{"id": "1", "properties": {"createdate": "1234567890000"}}],
            "paging": {"next": {"after": "token123"}},
        }
        mock_response1.raise_for_status.return_value = None

        # Second page
        mock_response2 = Mock()
        mock_response2.json.return_value = {
            "results": [{"id": "2", "properties": {"createdate": "1234567890000"}}],
            "paging": {},
        }
        mock_response2.raise_for_status.return_value = None

        connector.session.post.side_effect = [mock_response1, mock_response2]

        leads = connector.get_leads()

        assert len(leads) == 2
        assert connector.session.post.call_count == 2

    def test_update_lead_success(self, connector):
        """Test successful lead update."""
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        connector.session.patch.return_value = mock_response

        updates = {"email": "newemail@example.com", "lead_score": 85}
        result = connector.update_lead("contact123", updates)

        assert result is True
        connector.session.patch.assert_called_once()

        # Check that custom field mapping was applied
        call_args = connector.session.patch.call_args
        properties = call_args[1]["json"]["properties"]
        assert "hs_lead_score" in properties
        assert properties["hs_lead_score"] == 85

    def test_update_lead_failure(self, connector):
        """Test failed lead update."""
        connector.session.patch.side_effect = requests.RequestException("Update failed")

        result = connector.update_lead("contact123", {"email": "new@example.com"})

        assert result is False

    def test_sync_lead_stages(self, connector):
        """Test syncing lead stages."""
        leads = [
            Lead(
                id="lead1",
                email="test1@example.com",
                phone=None,
                gclid=None,
                created_at=datetime.now(timezone.utc),
                stage=LeadStage.QUALIFIED,
            ),
            Lead(
                id="lead2",
                email="test2@example.com",
                phone=None,
                gclid=None,
                created_at=datetime.now(timezone.utc),
                stage=LeadStage.CLOSED_WON,
            ),
        ]

        # Mock update_lead to return True
        connector.update_lead = Mock(return_value=True)

        results = connector.sync_lead_stages(leads)

        assert results["lead1"] is True
        assert results["lead2"] is True
        assert connector.update_lead.call_count == 2

    def test_get_custom_fields(self, connector):
        """Test retrieving custom fields."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "results": [
                {
                    "name": "custom_field_1",
                    "label": "Custom Field 1",
                    "type": "custom",
                    "fieldType": "text",
                    "description": "Test custom field",
                },
                {
                    "name": "standard_field",
                    "type": "standard",  # Should be filtered out
                },
                {
                    "name": "custom_field_2",
                    "label": "Custom Field 2",
                    "type": "custom",
                    "fieldType": "select",
                    "options": [{"value": "opt1"}, {"value": "opt2"}],
                },
            ]
        }
        mock_response.raise_for_status.return_value = None
        connector.session.get.return_value = mock_response

        custom_fields = connector.get_custom_fields()

        assert len(custom_fields) == 2
        assert "custom_field_1" in custom_fields
        assert "custom_field_2" in custom_fields
        assert custom_fields["custom_field_1"]["type"] == "text"
        assert len(custom_fields["custom_field_2"]["options"]) == 2

    def test_create_or_update_lead_existing(self, connector):
        """Test create/update for existing lead."""
        # Mock search response - lead exists
        search_response = Mock()
        search_response.json.return_value = {"results": [{"id": "existing123"}]}
        search_response.raise_for_status.return_value = None

        # Mock update response
        update_response = Mock()
        update_response.raise_for_status.return_value = None

        connector.session.post.return_value = search_response
        connector.session.patch.return_value = update_response

        lead_data = {"email": "existing@example.com", "company": "Test Corp"}
        result = connector.create_or_update_lead(lead_data)

        assert result == "existing123"
        connector.session.post.assert_called_once()  # Search
        connector.session.patch.assert_called_once()  # Update

    def test_create_or_update_lead_new(self, connector):
        """Test create/update for new lead."""
        # Mock search response - no results
        search_response = Mock()
        search_response.json.return_value = {"results": []}
        search_response.raise_for_status.return_value = None

        # Mock create response
        create_response = Mock()
        create_response.json.return_value = {"id": "new123"}
        create_response.raise_for_status.return_value = None

        connector.session.post.side_effect = [search_response, create_response]

        lead_data = {"email": "new@example.com", "company": "New Corp"}
        result = connector.create_or_update_lead(lead_data)

        assert result == "new123"
        assert connector.session.post.call_count == 2  # Search + Create

    def test_create_or_update_lead_no_email(self, connector):
        """Test create/update without email."""
        lead_data = {"company": "Test Corp"}  # No email
        result = connector.create_or_update_lead(lead_data)

        assert result is None
        connector.session.post.assert_not_called()

    def test_convert_hubspot_contact(self, connector):
        """Test converting HubSpot contact to Lead."""
        contact = {
            "id": "hs123",
            "properties": {
                "email": "test@example.com",
                "phone": "+1234567890",
                "gclid": "gclid_test",
                "createdate": "1704067200000",  # 2024-01-01 00:00:00 UTC
                "lifecyclestage": "closedwon",
                "total_revenue": "5000",
                "hs_analytics_source": "PAID_SEARCH",
                "hs_analytics_source_data_1": "campaign_abc",
                "hs_analytics_source_data_2": "buy shoes",
                "hs_lead_score": "85",
            },
        }

        lead = connector._convert_hubspot_contact(contact)

        assert lead is not None
        assert lead.id == "hs123"
        assert lead.email == "test@example.com"
        assert lead.stage == LeadStage.CLOSED_WON
        assert lead.value == 5000.0
        assert lead.source == "PAID_SEARCH"
        assert lead.campaign_id == "campaign_abc"
        assert lead.keyword == "buy shoes"
        assert lead.custom_fields["lead_score"] == "85"

    def test_convert_hubspot_contact_error(self, connector):
        """Test converting invalid HubSpot contact."""
        contact = {"id": "invalid"}  # Missing properties

        lead = connector._convert_hubspot_contact(contact)

        assert lead is None

    def test_get_hubspot_stage_mapping(self, connector):
        """Test internal to HubSpot stage mapping."""
        assert connector._get_hubspot_stage(LeadStage.NEW) == "new"
        assert connector._get_hubspot_stage(LeadStage.QUALIFIED) == "qualified"
        assert connector._get_hubspot_stage(LeadStage.CLOSED_WON) == "closedwon"

        # Test unmapped stage
        from unittest.mock import Mock

        unknown_stage = Mock()
        unknown_stage.name = "UNKNOWN"
        assert connector._get_hubspot_stage(unknown_stage) is None
