"""Unit tests for new field mappings (device, ad_schedule, per_store, auction_insights)."""

from paidsearchnav.parsers.field_mappings import (
    get_field_mapping,
    validate_csv_headers,
)


class TestNewFieldMappings:
    """Test suite for new field mappings added for additional report types."""

    def test_device_field_mapping(self):
        """Test device report field mapping."""
        mapping = get_field_mapping("device")

        # Check key fields are mapped correctly
        assert mapping["Device"] == "device"
        assert mapping["Level"] == "level"
        assert mapping["Campaign"] == "campaign_name"
        assert mapping["Ad group"] == "ad_group_name"
        assert mapping["Bid adj."] == "bid_adjustment"
        assert mapping["Clicks"] == "clicks"
        assert mapping["Impr."] == "impressions"
        assert mapping["CTR"] == "ctr"
        assert mapping["Avg. CPC"] == "avg_cpc"
        assert mapping["Cost"] == "cost"
        assert mapping["Conv. rate"] == "conversion_rate"
        assert mapping["Conversions"] == "conversions"
        assert mapping["Cost / conv."] == "cpa"

    def test_ad_schedule_field_mapping(self):
        """Test ad schedule report field mapping."""
        mapping = get_field_mapping("ad_schedule")

        # Check key fields are mapped correctly
        assert mapping["Day & time"] == "day_time"
        assert mapping["Bid adj."] == "bid_adjustment"
        assert mapping["Clicks"] == "clicks"
        assert mapping["Impr."] == "impressions"
        assert mapping["CTR"] == "ctr"
        assert mapping["Avg. CPC"] == "avg_cpc"
        assert mapping["Cost"] == "cost"
        assert mapping["Conv. rate"] == "conversion_rate"
        assert mapping["Conversions"] == "conversions"
        assert mapping["Cost / conv."] == "cpa"

    def test_per_store_field_mapping(self):
        """Test per store report field mapping."""
        mapping = get_field_mapping("per_store")

        # Check key fields are mapped correctly
        assert mapping["Store locations"] == "store_name"
        assert mapping["address_line_1"] == "address_line_1"
        assert mapping["address_line_2"] == "address_line_2"
        assert mapping["city"] == "city"
        assert mapping["country_code"] == "country_code"
        assert mapping["phone_number"] == "phone_number"
        assert mapping["postal_code"] == "postal_code"
        assert mapping["province"] == "state"
        assert mapping["Local reach (impressions)"] == "local_impressions"
        assert mapping["Call clicks"] == "call_clicks"
        assert mapping["Driving directions"] == "driving_directions"
        assert mapping["Website visits"] == "website_visits"

    def test_auction_insights_field_mapping(self):
        """Test auction insights report field mapping."""
        mapping = get_field_mapping("auction_insights")

        # Check key fields are mapped correctly
        assert mapping["Display URL domain"] == "competitor_domain"
        assert mapping["Impr. share"] == "impression_share"
        assert mapping["Overlap rate"] == "overlap_rate"
        assert mapping["Top of page rate"] == "top_of_page_rate"
        assert mapping["Abs. Top of page rate"] == "abs_top_of_page_rate"
        assert mapping["Outranking share"] == "outranking_share"
        assert mapping["Position above rate"] == "position_above_rate"

    def test_validate_csv_headers_device(self):
        """Test validation for device report headers."""
        # Valid headers
        headers = ["Device", "Campaign", "Clicks", "Cost"]
        missing = validate_csv_headers("device", headers)
        assert missing == []

        # Missing required fields
        headers = ["Device", "Campaign"]
        missing = validate_csv_headers("device", headers)
        assert "Clicks" in missing
        assert "Cost" in missing

    def test_validate_csv_headers_ad_schedule(self):
        """Test validation for ad schedule report headers."""
        # Valid headers
        headers = ["Day & time", "Clicks", "Cost"]
        missing = validate_csv_headers("ad_schedule", headers)
        assert missing == []

        # Missing required fields
        headers = ["Day & time"]
        missing = validate_csv_headers("ad_schedule", headers)
        assert "Clicks" in missing
        assert "Cost" in missing

    def test_validate_csv_headers_per_store(self):
        """Test validation for per store report headers."""
        # Valid headers
        headers = ["Store locations", "Local reach (impressions)"]
        missing = validate_csv_headers("per_store", headers)
        assert missing == []

        # Missing required fields
        headers = ["Store locations"]
        missing = validate_csv_headers("per_store", headers)
        assert "Local reach (impressions)" in missing

    def test_validate_csv_headers_auction_insights(self):
        """Test validation for auction insights report headers."""
        # Valid headers
        headers = ["Display URL domain", "Impr. share"]
        missing = validate_csv_headers("auction_insights", headers)
        assert missing == []

        # Missing required fields
        headers = ["Display URL domain"]
        missing = validate_csv_headers("auction_insights", headers)
        assert "Impr. share" in missing

    def test_field_mapping_consistency(self):
        """Test that all new mappings use consistent field names."""
        # Check that impression fields are consistently mapped
        device_mapping = get_field_mapping("device")
        ad_schedule_mapping = get_field_mapping("ad_schedule")

        # Both should use "Impr." not "Impressions"
        assert "Impr." in device_mapping
        assert "Impr." in ad_schedule_mapping
        assert "Impressions" not in device_mapping
        assert "Impressions" not in ad_schedule_mapping

        # Check consistent mapping targets
        assert device_mapping["Impr."] == "impressions"
        assert ad_schedule_mapping["Impr."] == "impressions"

    def test_currency_code_mapping(self):
        """Test that currency code is mapped for reports that have it."""
        device_mapping = get_field_mapping("device")
        ad_schedule_mapping = get_field_mapping("ad_schedule")

        assert device_mapping.get("Currency code") == "currency_code"
        assert ad_schedule_mapping.get("Currency code") == "currency_code"
