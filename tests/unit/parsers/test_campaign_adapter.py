"""Unit tests for CampaignAdapter."""

from paidsearchnav.core.models.campaign import Campaign
from paidsearchnav.parsers.data_adapters import CampaignAdapter


class TestCampaignAdapter:
    """Test CampaignAdapter functionality."""

    def test_basic_conversion(self):
        """Test basic campaign data conversion."""
        adapter = CampaignAdapter(Campaign)

        data = {
            "customer_id": "12345",
            "campaign_id": "67890",
            "campaign_name": "Test Campaign",
            "status": "ENABLED",
            "type": "SEARCH",
            "bidding_strategy": "MANUAL_CPC",
            "budget_amount": 100.0,
            "impressions": "1,234",
            "clicks": "56",
            "conversions": "7.5",
            "cost": "$89.50",
        }

        result = adapter.convert(data)

        assert result["customer_id"] == "12345"
        assert result["campaign_id"] == "67890"
        assert result["name"] == "Test Campaign"
        assert result["status"] == "ENABLED"
        assert result["type"] == "SEARCH"
        assert result["bidding_strategy"] == "MANUAL_CPC"
        assert result["budget_amount"] == 100.0
        assert result["impressions"] == 1234
        assert result["clicks"] == 56
        assert result["conversions"] == 7.5
        assert result["cost"] == 89.50

    def test_missing_ids_generation(self):
        """Test generation of missing IDs."""
        adapter = CampaignAdapter(Campaign)

        data = {"campaign_name": "My Campaign"}

        result = adapter.convert(data)

        assert result["customer_id"] == "unknown"
        assert result["campaign_id"].startswith("campaign_")
        # ID should be deterministic for same campaign name
        result2 = adapter.convert(data)
        assert result["campaign_id"] == result2["campaign_id"]

    def test_status_mapping(self):
        """Test various status value mappings."""
        adapter = CampaignAdapter(Campaign)

        test_cases = [
            ("ENABLED", "ENABLED"),
            ("Enabled", "ENABLED"),
            ("PAUSED", "PAUSED"),
            ("Paused", "PAUSED"),
            ("REMOVED", "REMOVED"),
            ("Removed", "REMOVED"),
            ("Invalid", "UNKNOWN"),
        ]

        for input_status, expected in test_cases:
            result = adapter.convert({"status": input_status})
            assert result["status"] == expected, f"Failed for status: {input_status}"

    def test_campaign_type_mapping(self):
        """Test campaign type mappings."""
        adapter = CampaignAdapter(Campaign)

        test_cases = [
            ("SEARCH", "SEARCH"),
            ("Search", "SEARCH"),
            ("DISPLAY", "DISPLAY"),
            ("Display", "DISPLAY"),
            ("Performance Max", "PERFORMANCE_MAX"),
            ("PERFORMANCE_MAX", "PERFORMANCE_MAX"),
            ("YouTube", "VIDEO"),
            ("Demand Gen", "UNKNOWN"),  # New type not in enum
            ("Invalid", "UNKNOWN"),
        ]

        for input_type, expected in test_cases:
            result = adapter.convert({"type": input_type})
            assert result["type"] == expected, f"Failed for type: {input_type}"

    def test_bidding_strategy_mapping(self):
        """Test bidding strategy mappings."""
        adapter = CampaignAdapter(Campaign)

        test_cases = [
            ("MANUAL_CPC", "MANUAL_CPC"),
            ("Manual CPC", "MANUAL_CPC"),
            ("Enhanced CPC", "MANUAL_CPC"),
            ("Target CPA", "TARGET_CPA"),
            ("TARGET_ROAS", "TARGET_ROAS"),
            ("Maximize Conversions", "MAXIMIZE_CONVERSIONS"),
            ("Maximize Conversion Value", "MAXIMIZE_CONVERSION_VALUE"),
            ("Invalid", "UNKNOWN"),
        ]

        for input_strategy, expected in test_cases:
            result = adapter.convert({"bidding_strategy": input_strategy})
            assert result["bidding_strategy"] == expected, (
                f"Failed for strategy: {input_strategy}"
            )

    def test_currency_parsing(self):
        """Test currency field parsing."""
        adapter = CampaignAdapter(Campaign)

        test_cases = [
            ("$100.50", 100.50),
            ("100.50", 100.50),
            ("$1,234.56", 1234.56),
            ("1,234.56", 1234.56),
            ("--", 0.0),
            ("N/A", 0.0),
            ("", 0.0),
            (None, 0.0),
            (100, 100.0),
            (100.5, 100.5),
        ]

        for input_value, expected in test_cases:
            result = adapter.convert({"cost": input_value})
            assert result["cost"] == expected, f"Failed for cost: {input_value}"

    def test_numeric_field_parsing(self):
        """Test numeric field parsing with commas."""
        adapter = CampaignAdapter(Campaign)

        data = {"impressions": "21,893", "clicks": "1,234", "conversions": "45.67"}

        result = adapter.convert(data)

        assert result["impressions"] == 21893
        assert result["clicks"] == 1234
        assert result["conversions"] == 45.67

    def test_name_field_mapping(self):
        """Test various name field mappings."""
        adapter = CampaignAdapter(Campaign)

        # Test with 'campaign_name'
        result = adapter.convert({"campaign_name": "Name from campaign_name"})
        assert result["name"] == "Name from campaign_name"

        # Test with 'campaign'
        result = adapter.convert({"campaign": "Name from campaign"})
        assert result["name"] == "Name from campaign"

        # Test with 'name' directly
        result = adapter.convert({"name": "Direct name"})
        assert result["name"] == "Direct name"

        # Test with no name field
        result = adapter.convert({})
        assert result["name"] == "Unknown Campaign"

    def test_default_values(self):
        """Test default values for missing fields."""
        adapter = CampaignAdapter(Campaign)

        result = adapter.convert({})

        assert result["customer_id"] == "unknown"
        assert result["campaign_id"].startswith("campaign_")
        assert result["name"] == "Unknown Campaign"
        assert result["budget_amount"] == 0.0
        assert result["budget_currency"] == "USD"
        assert result["status"] == "UNKNOWN"
        assert result["type"] == "UNKNOWN"
        assert result["bidding_strategy"] == "UNKNOWN"

    def test_campaign_state_field(self):
        """Test campaign_state field as alternative to status."""
        adapter = CampaignAdapter(Campaign)

        result = adapter.convert({"campaign_state": "ENABLED"})
        assert result["status"] == "ENABLED"

        # status should take precedence over campaign_state
        result = adapter.convert({"status": "PAUSED", "campaign_state": "ENABLED"})
        assert result["status"] == "PAUSED"

    def test_edge_cases(self):
        """Test edge cases and malformed data."""
        adapter = CampaignAdapter(Campaign)

        # Empty data
        result = adapter.convert({})
        assert isinstance(result, dict)

        # Invalid numeric values
        result = adapter.convert(
            {
                "impressions": "invalid",
                "clicks": None,
                "conversions": "",
                "cost": "not a number",
            }
        )
        assert result["impressions"] == 0
        assert result["clicks"] == 0
        assert result["conversions"] == 0.0
        assert result["cost"] == 0.0

        # Very large numbers
        result = adapter.convert({"impressions": "999,999,999", "cost": "$999,999.99"})
        assert result["impressions"] == 999999999
        assert result["cost"] == 999999.99
