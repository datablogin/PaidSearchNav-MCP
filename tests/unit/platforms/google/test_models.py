"""Tests for Google Ads specific models and data structures."""

import pytest
from pydantic import ValidationError

from paidsearchnav.platforms.google.models import (
    AccountStructure,
    AdGroup,
    GeoPerformance,
    GeoTargetType,
    GoogleAdsConfig,
    NegativeKeyword,
    PerformanceMaxAsset,
    SharedNegativeKeywordSet,
)


@pytest.fixture
def sample_ad_group_data():
    """Fixture for common ad group test data."""
    return {
        "ad_group_id": "123456",
        "campaign_id": "789012",
        "name": "Test Ad Group",
        "status": "ENABLED",
    }


@pytest.fixture
def sample_negative_keyword_data():
    """Fixture for common negative keyword test data."""
    return {
        "id": "neg123",
        "text": "test keyword",
        "match_type": "EXACT",
        "level": "campaign",
    }


class TestGoogleAdsConfig:
    """Test GoogleAdsConfig model."""

    def test_valid_config(self) -> None:
        """Test creating a valid config."""
        config = GoogleAdsConfig(
            developer_token="test-token",
            client_id="test-client-id",
            client_secret="test-client-secret",
            refresh_token="test-refresh-token",
        )

        assert config.developer_token == "test-token"
        assert config.client_id == "test-client-id"
        assert config.client_secret == "test-client-secret"
        assert config.refresh_token == "test-refresh-token"
        assert config.api_version == "v18"  # default
        assert config.use_proto_plus is True  # default
        assert config.login_customer_id is None  # optional

    def test_config_with_mcc(self) -> None:
        """Test config with MCC login customer ID."""
        config = GoogleAdsConfig(
            developer_token="test-token",
            client_id="test-client-id",
            client_secret="test-client-secret",
            refresh_token="test-refresh-token",
            login_customer_id="1234567890",
        )

        assert config.login_customer_id == "1234567890"

    def test_custom_api_version(self) -> None:
        """Test setting custom API version."""
        config = GoogleAdsConfig(
            developer_token="test-token",
            client_id="test-client-id",
            client_secret="test-client-secret",
            refresh_token="test-refresh-token",
            api_version="v17",
        )

        assert config.api_version == "v17"

    def test_missing_required_fields(self) -> None:
        """Test that missing required fields raise validation error."""
        with pytest.raises(ValidationError) as exc_info:
            GoogleAdsConfig(
                developer_token="test-token",
                client_id="test-client-id",
                # Missing client_secret and refresh_token
            )

        errors = exc_info.value.errors()
        assert len(errors) == 2
        assert any(e["loc"] == ("client_secret",) for e in errors)
        assert any(e["loc"] == ("refresh_token",) for e in errors)

    def test_extra_fields_forbidden(self) -> None:
        """Test that extra fields are forbidden."""
        with pytest.raises(ValidationError) as exc_info:
            GoogleAdsConfig(
                developer_token="test-token",
                client_id="test-client-id",
                client_secret="test-client-secret",
                refresh_token="test-refresh-token",
                extra_field="not allowed",
            )

        errors = exc_info.value.errors()
        assert any("extra_field" in str(e) for e in errors)


class TestAdGroup:
    """Test AdGroup model."""

    def test_valid_ad_group(self) -> None:
        """Test creating a valid ad group."""
        ad_group = AdGroup(
            ad_group_id="123456",
            campaign_id="789012",
            name="Test Ad Group",
            status="ENABLED",
        )

        assert ad_group.ad_group_id == "123456"
        assert ad_group.campaign_id == "789012"
        assert ad_group.name == "Test Ad Group"
        assert ad_group.status == "ENABLED"
        assert ad_group.cpc_bid_micros is None
        assert ad_group.impressions == 0
        assert ad_group.clicks == 0
        assert ad_group.cost == 0.0
        assert ad_group.conversions == 0.0
        assert ad_group.conversion_value == 0.0

    def test_ad_group_with_bid(self) -> None:
        """Test ad group with CPC bid."""
        ad_group = AdGroup(
            ad_group_id="123456",
            campaign_id="789012",
            name="Test Ad Group",
            status="ENABLED",
            cpc_bid_micros=2500000,  # $2.50
        )

        assert ad_group.cpc_bid_micros == 2500000

    def test_ad_group_with_performance_metrics(self) -> None:
        """Test ad group with performance metrics."""
        ad_group = AdGroup(
            ad_group_id="123456",
            campaign_id="789012",
            name="Test Ad Group",
            status="ENABLED",
            impressions=1000,
            clicks=50,
            cost=25.50,
            conversions=5.0,
            conversion_value=250.0,
        )

        assert ad_group.impressions == 1000
        assert ad_group.clicks == 50
        assert ad_group.cost == 25.50
        assert ad_group.conversions == 5.0
        assert ad_group.conversion_value == 250.0

    def test_micros_to_currency_conversion(self) -> None:
        """Test that micros are properly handled."""
        # This tests that the model accepts float cost directly
        # In real usage, the API would provide micros which need conversion
        ad_group = AdGroup(
            ad_group_id="123456",
            campaign_id="789012",
            name="Test Ad Group",
            status="ENABLED",
            cost=1234.56,  # Already in currency units
        )

        assert ad_group.cost == 1234.56


class TestNegativeKeyword:
    """Test NegativeKeyword model."""

    def test_campaign_level_negative(self) -> None:
        """Test campaign-level negative keyword."""
        negative = NegativeKeyword(
            id="neg123",
            text="cheap",
            match_type="BROAD",
            level="campaign",
            campaign_id="789012",
            campaign_name="Test Campaign",
        )

        assert negative.id == "neg123"
        assert negative.text == "cheap"
        assert negative.match_type == "BROAD"
        assert negative.level == "campaign"
        assert negative.campaign_id == "789012"
        assert negative.campaign_name == "Test Campaign"
        assert negative.ad_group_id is None
        assert negative.shared_set_id is None

    def test_ad_group_level_negative(self) -> None:
        """Test ad group-level negative keyword."""
        negative = NegativeKeyword(
            id="neg456",
            text="[discount]",
            match_type="EXACT",
            level="ad_group",
            campaign_id="789012",
            campaign_name="Test Campaign",
            ad_group_id="123456",
            ad_group_name="Test Ad Group",
        )

        assert negative.ad_group_id == "123456"
        assert negative.ad_group_name == "Test Ad Group"

    def test_shared_set_negative(self) -> None:
        """Test negative keyword from shared set."""
        negative = NegativeKeyword(
            id="neg789",
            text='"free shipping"',
            match_type="PHRASE",
            level="account",
            shared_set_id="shared123",
            shared_set_name="Brand Protection",
        )

        assert negative.shared_set_id == "shared123"
        assert negative.shared_set_name == "Brand Protection"
        assert negative.campaign_id is None

    def test_match_type_validation(self) -> None:
        """Test that match types are accepted."""
        # All valid match types
        for match_type in ["EXACT", "PHRASE", "BROAD"]:
            negative = NegativeKeyword(
                id="neg123",
                text="test",
                match_type=match_type,
                level="campaign",
            )
            assert negative.match_type == match_type


class TestGeoTargetType:
    """Test GeoTargetType enum."""

    def test_all_geo_types(self) -> None:
        """Test all geographic target types."""
        expected_types = [
            "COUNTRY",
            "STATE",
            "CITY",
            "POSTAL_CODE",
            "DMA_REGION",
            "COUNTY",
            "AIRPORT",
            "CONGRESSIONAL_DISTRICT",
            "OTHER",
        ]

        for geo_type in expected_types:
            assert GeoTargetType(geo_type) == geo_type

    def test_invalid_geo_type(self) -> None:
        """Test invalid geographic type raises error."""
        with pytest.raises(ValueError):
            GeoTargetType("INVALID_TYPE")


class TestGeoPerformance:
    """Test GeoPerformance model."""

    def test_basic_geo_performance(self) -> None:
        """Test creating basic geo performance data."""
        geo = GeoPerformance(
            campaign_id="789012",
            location_id="1014044",  # New York, NY
            location_name="New York, NY",
            location_type=GeoTargetType.CITY,
        )

        assert geo.campaign_id == "789012"
        assert geo.location_id == "1014044"
        assert geo.location_name == "New York, NY"
        assert geo.location_type == GeoTargetType.CITY
        assert geo.impressions == 0
        assert geo.clicks == 0
        assert geo.cost == 0.0
        assert geo.conversions == 0.0
        assert geo.conversion_value == 0.0

    def test_geo_performance_with_hierarchy(self) -> None:
        """Test geo performance with location hierarchy."""
        geo = GeoPerformance(
            campaign_id="789012",
            location_id="1014044",
            location_name="New York, NY",
            location_type=GeoTargetType.CITY,
            country_code="US",
            state="New York",
            city="New York",
            postal_code="10001",
        )

        assert geo.country_code == "US"
        assert geo.state == "New York"
        assert geo.city == "New York"
        assert geo.postal_code == "10001"

    def test_geo_performance_with_metrics(self) -> None:
        """Test geo performance with performance metrics."""
        geo = GeoPerformance(
            campaign_id="789012",
            location_id="1014044",
            location_name="New York, NY",
            location_type=GeoTargetType.CITY,
            impressions=10000,
            clicks=500,
            cost=250.0,
            conversions=25.0,
            conversion_value=2500.0,
        )

        assert geo.impressions == 10000
        assert geo.clicks == 500
        assert geo.cost == 250.0
        assert geo.conversions == 25.0
        assert geo.conversion_value == 2500.0

    def test_geo_performance_with_distance(self) -> None:
        """Test geo performance with distance metrics."""
        geo = GeoPerformance(
            campaign_id="789012",
            location_id="1014044",
            location_name="New York, NY",
            location_type=GeoTargetType.CITY,
            distance_miles=5.2,
            store_visits=15.0,
        )

        assert geo.distance_miles == 5.2
        assert geo.store_visits == 15.0

    def test_different_location_types(self) -> None:
        """Test various location types."""
        # Country level
        country = GeoPerformance(
            campaign_id="789012",
            location_id="2840",
            location_name="United States",
            location_type=GeoTargetType.COUNTRY,
            country_code="US",
        )
        assert country.location_type == GeoTargetType.COUNTRY

        # State level
        state = GeoPerformance(
            campaign_id="789012",
            location_id="21167",
            location_name="California",
            location_type=GeoTargetType.STATE,
            country_code="US",
            state="California",
        )
        assert state.location_type == GeoTargetType.STATE

        # Postal code level
        postal = GeoPerformance(
            campaign_id="789012",
            location_id="9061268",
            location_name="90210",
            location_type=GeoTargetType.POSTAL_CODE,
            postal_code="90210",
        )
        assert postal.location_type == GeoTargetType.POSTAL_CODE


class TestPerformanceMaxAsset:
    """Test PerformanceMaxAsset model."""

    def test_text_asset(self) -> None:
        """Test creating a text asset."""
        asset = PerformanceMaxAsset(
            asset_id="asset123",
            asset_type="TEXT",
            content="Shop our latest collection",
        )

        assert asset.asset_id == "asset123"
        assert asset.asset_type == "TEXT"
        assert asset.content == "Shop our latest collection"
        assert asset.performance_label is None
        assert asset.impressions == 0
        assert asset.clicks == 0
        assert asset.conversions == 0.0

    def test_image_asset(self) -> None:
        """Test creating an image asset."""
        asset = PerformanceMaxAsset(
            asset_id="asset456",
            asset_type="IMAGE",
            content="https://example.com/image.jpg",
            performance_label="GOOD",
            impressions=5000,
            clicks=250,
            conversions=12.5,
        )

        assert asset.asset_type == "IMAGE"
        assert asset.content == "https://example.com/image.jpg"
        assert asset.performance_label == "GOOD"
        assert asset.impressions == 5000
        assert asset.clicks == 250
        assert asset.conversions == 12.5

    def test_video_asset(self) -> None:
        """Test creating a video asset."""
        asset = PerformanceMaxAsset(
            asset_id="asset789",
            asset_type="VIDEO",
            content="https://youtube.com/watch?v=abc123",
            performance_label="BEST",
        )

        assert asset.asset_type == "VIDEO"
        assert asset.performance_label == "BEST"


class TestSharedNegativeKeywordSet:
    """Test SharedNegativeKeywordSet model."""

    def test_empty_shared_set(self) -> None:
        """Test creating an empty shared set."""
        shared_set = SharedNegativeKeywordSet(
            shared_set_id="shared123",
            name="Brand Protection",
            member_count=0,
        )

        assert shared_set.shared_set_id == "shared123"
        assert shared_set.name == "Brand Protection"
        assert shared_set.member_count == 0
        assert shared_set.applied_campaign_ids == []
        assert shared_set.applied_campaign_names == []
        assert shared_set.negative_keywords == []

    def test_shared_set_with_campaigns(self) -> None:
        """Test shared set applied to campaigns."""
        shared_set = SharedNegativeKeywordSet(
            shared_set_id="shared123",
            name="Brand Protection",
            member_count=5,
            applied_campaign_ids=["789012", "789013"],
            applied_campaign_names=["Campaign 1", "Campaign 2"],
        )

        assert len(shared_set.applied_campaign_ids) == 2
        assert "789012" in shared_set.applied_campaign_ids
        assert len(shared_set.applied_campaign_names) == 2
        assert "Campaign 1" in shared_set.applied_campaign_names

    def test_shared_set_with_keywords(self) -> None:
        """Test shared set with negative keywords."""
        keywords = [
            NegativeKeyword(
                id="neg1",
                text="competitor1",
                match_type="EXACT",
                level="account",
                shared_set_id="shared123",
                shared_set_name="Brand Protection",
            ),
            NegativeKeyword(
                id="neg2",
                text="competitor2",
                match_type="PHRASE",
                level="account",
                shared_set_id="shared123",
                shared_set_name="Brand Protection",
            ),
        ]

        shared_set = SharedNegativeKeywordSet(
            shared_set_id="shared123",
            name="Brand Protection",
            member_count=2,
            negative_keywords=keywords,
        )

        assert len(shared_set.negative_keywords) == 2
        assert shared_set.negative_keywords[0].text == "competitor1"
        assert shared_set.negative_keywords[1].text == "competitor2"


class TestAccountStructure:
    """Test AccountStructure model."""

    def test_basic_account_structure(self) -> None:
        """Test creating basic account structure."""
        account = AccountStructure(
            customer_id="1234567890",
            customer_name="Test Account",
            currency_code="USD",
            time_zone="America/New_York",
        )

        assert account.customer_id == "1234567890"
        assert account.customer_name == "Test Account"
        assert account.currency_code == "USD"
        assert account.time_zone == "America/New_York"
        assert account.is_mcc is False
        assert account.is_test_account is False
        assert account.campaign_count == 0
        assert account.active_campaign_count == 0
        assert account.ad_group_count == 0
        assert account.keyword_count == 0
        assert account.total_budget == 0.0
        assert account.total_cost_mtd == 0.0
        assert account.total_conversions_mtd == 0.0

    def test_mcc_account(self) -> None:
        """Test MCC account structure."""
        account = AccountStructure(
            customer_id="9876543210",
            customer_name="Agency MCC",
            currency_code="USD",
            time_zone="America/Los_Angeles",
            is_mcc=True,
        )

        assert account.is_mcc is True

    def test_account_with_counts(self) -> None:
        """Test account with campaign and structure counts."""
        account = AccountStructure(
            customer_id="1234567890",
            customer_name="Test Account",
            currency_code="USD",
            time_zone="America/New_York",
            campaign_count=25,
            active_campaign_count=20,
            ad_group_count=150,
            keyword_count=5000,
            total_budget=10000.0,
        )

        assert account.campaign_count == 25
        assert account.active_campaign_count == 20
        assert account.ad_group_count == 150
        assert account.keyword_count == 5000
        assert account.total_budget == 10000.0

    def test_account_with_performance(self) -> None:
        """Test account with performance metrics."""
        account = AccountStructure(
            customer_id="1234567890",
            customer_name="Test Account",
            currency_code="USD",
            time_zone="America/New_York",
            total_cost_mtd=5000.0,
            total_conversions_mtd=250.0,
        )

        assert account.total_cost_mtd == 5000.0
        assert account.total_conversions_mtd == 250.0

    def test_test_account(self) -> None:
        """Test marking account as test account."""
        account = AccountStructure(
            customer_id="1234567890",
            customer_name="Test Account",
            currency_code="USD",
            time_zone="America/New_York",
            is_test_account=True,
        )

        assert account.is_test_account is True


class TestModelIntegration:
    """Test model integration and relationships."""

    def test_negative_keyword_in_shared_set(self) -> None:
        """Test negative keyword properly links to shared set."""
        negative = NegativeKeyword(
            id="neg123",
            text="competitor",
            match_type="EXACT",
            level="account",
            shared_set_id="shared456",
            shared_set_name="Competitors",
        )

        shared_set = SharedNegativeKeywordSet(
            shared_set_id="shared456",
            name="Competitors",
            member_count=1,
            negative_keywords=[negative],
        )

        assert shared_set.negative_keywords[0].shared_set_id == shared_set.shared_set_id
        assert shared_set.negative_keywords[0].shared_set_name == shared_set.name

    def test_complete_data_flow(self) -> None:
        """Test complete data flow from API response to models."""
        # Simulate data that would come from Google Ads API
        api_response_data = {
            "customer_id": "1234567890",
            "campaign_id": "789012",
            "ad_group_id": "123456",
            "location_id": "1014044",
            "impressions": 1000,
            "clicks": 50,
            "cost_micros": 25000000,  # $25.00
            "conversions": 5.0,
        }

        # Convert micros to currency
        cost = api_response_data["cost_micros"] / 1_000_000

        # Create models
        ad_group = AdGroup(
            ad_group_id=api_response_data["ad_group_id"],
            campaign_id=api_response_data["campaign_id"],
            name="Test Ad Group",
            status="ENABLED",
            impressions=api_response_data["impressions"],
            clicks=api_response_data["clicks"],
            cost=cost,
            conversions=api_response_data["conversions"],
        )

        geo_performance = GeoPerformance(
            campaign_id=api_response_data["campaign_id"],
            location_id=api_response_data["location_id"],
            location_name="New York, NY",
            location_type=GeoTargetType.CITY,
            impressions=api_response_data["impressions"],
            clicks=api_response_data["clicks"],
            cost=cost,
            conversions=api_response_data["conversions"],
        )

        # Verify data integrity
        assert ad_group.cost == geo_performance.cost
        assert ad_group.impressions == geo_performance.impressions
        assert ad_group.conversions == geo_performance.conversions


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_null_optional_fields(self) -> None:
        """Test that optional fields can be None."""
        negative = NegativeKeyword(
            id="neg123",
            text="test",
            match_type="EXACT",
            level="campaign",
            campaign_id=None,
            campaign_name=None,
            ad_group_id=None,
            ad_group_name=None,
            shared_set_id=None,
            shared_set_name=None,
        )

        assert negative.campaign_id is None
        assert negative.campaign_name is None
        assert negative.ad_group_id is None
        assert negative.ad_group_name is None
        assert negative.shared_set_id is None
        assert negative.shared_set_name is None

    def test_empty_strings(self) -> None:
        """Test handling of empty strings."""
        # Empty strings are allowed by Pydantic by default
        # This test documents that behavior
        ad_group = AdGroup(
            ad_group_id="",  # Empty ID is allowed
            campaign_id="789012",
            name="Test",
            status="ENABLED",
        )
        assert ad_group.ad_group_id == ""

    def test_large_numbers(self) -> None:
        """Test handling of large numbers."""
        # Test with a large but reasonable value to avoid overflow issues
        large_micros = 1000000000000  # $1 million in micros

        ad_group = AdGroup(
            ad_group_id="123456",
            campaign_id="789012",
            name="Test Ad Group",
            status="ENABLED",
            cpc_bid_micros=large_micros,
        )

        assert ad_group.cpc_bid_micros == large_micros

    def test_unicode_handling(self) -> None:
        """Test handling of unicode characters."""
        account = AccountStructure(
            customer_id="1234567890",
            customer_name="Test Account 测试账户",
            currency_code="JPY",
            time_zone="Asia/Tokyo",
        )

        assert "测试账户" in account.customer_name

        negative = NegativeKeyword(
            id="neg123",
            text="café",
            match_type="EXACT",
            level="campaign",
        )

        assert negative.text == "café"

    def test_zero_metrics(self) -> None:
        """Test handling of zero metrics."""
        geo = GeoPerformance(
            campaign_id="789012",
            location_id="1014044",
            location_name="New York, NY",
            location_type=GeoTargetType.CITY,
            impressions=0,
            clicks=0,
            cost=0.0,
            conversions=0.0,
            conversion_value=0.0,
        )

        # All metrics should be zero without errors
        assert geo.impressions == 0
        assert geo.clicks == 0
        assert geo.cost == 0.0
        assert geo.conversions == 0.0
        assert geo.conversion_value == 0.0

    def test_negative_values(self) -> None:
        """Test that negative values are handled appropriately."""
        # Some fields should accept negative values (e.g., adjustments)
        # but performance metrics should not
        ad_group = AdGroup(
            ad_group_id="123456",
            campaign_id="789012",
            name="Test Ad Group",
            status="ENABLED",
            impressions=-1,  # This might happen due to data issues
        )

        # Model should accept it, validation is application-level concern
        assert ad_group.impressions == -1
