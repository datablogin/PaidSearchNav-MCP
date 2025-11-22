"""Test campaign models and enums."""

from datetime import datetime, timezone

import pytest

from paidsearchnav.core.models.campaign import (
    BiddingStrategy,
    Campaign,
    CampaignStatus,
    CampaignType,
)


class TestBiddingStrategyEnum:
    """Test BiddingStrategy enum values and completeness."""

    def test_bidding_strategy_enum_values(self):
        """Test that all expected bidding strategy values are present."""
        expected_strategies = {
            "MANUAL_CPC",
            "MANUAL_CPV",
            "MANUAL_CPM",
            "TARGET_CPA",
            "TARGET_ROAS",
            "TARGET_SPEND",  # This is the newly added value
            "MAXIMIZE_CONVERSIONS",
            "MAXIMIZE_CONVERSION_VALUE",
            "TARGET_IMPRESSION_SHARE",
            "MAXIMIZE_CLICKS",
            "UNKNOWN",
        }
        actual_strategies = {strategy.value for strategy in BiddingStrategy}
        assert actual_strategies == expected_strategies

    def test_bidding_strategy_enum_access(self):
        """Test individual bidding strategy enum access."""
        assert BiddingStrategy.MANUAL_CPC.value == "MANUAL_CPC"
        assert BiddingStrategy.TARGET_CPA.value == "TARGET_CPA"
        assert BiddingStrategy.TARGET_SPEND.value == "TARGET_SPEND"
        assert BiddingStrategy.MAXIMIZE_CONVERSIONS.value == "MAXIMIZE_CONVERSIONS"
        assert BiddingStrategy.UNKNOWN.value == "UNKNOWN"

    def test_target_spend_enum_value(self):
        """Test specifically that TARGET_SPEND enum value exists and is correct."""
        assert hasattr(BiddingStrategy, "TARGET_SPEND")
        assert BiddingStrategy.TARGET_SPEND == "TARGET_SPEND"
        assert BiddingStrategy.TARGET_SPEND.value == "TARGET_SPEND"


class TestCampaignStatusEnum:
    """Test CampaignStatus enum values."""

    def test_campaign_status_enum_values(self):
        """Test that all expected campaign status values are present."""
        expected_statuses = {"ENABLED", "PAUSED", "REMOVED", "UNKNOWN"}
        actual_statuses = {status.value for status in CampaignStatus}
        assert actual_statuses == expected_statuses


class TestCampaignTypeEnum:
    """Test CampaignType enum values."""

    def test_campaign_type_enum_values(self):
        """Test that all expected campaign type values are present."""
        expected_types = {
            "SEARCH",
            "DISPLAY",
            "SHOPPING",
            "VIDEO",
            "APP",
            "SMART",
            "LOCAL",
            "HOTEL",
            "PERFORMANCE_MAX",
            "UNKNOWN",
        }
        actual_types = {campaign_type.value for campaign_type in CampaignType}
        assert actual_types == expected_types


class TestCampaignModel:
    """Test Campaign model creation and validation."""

    def test_campaign_creation_with_target_spend(self):
        """Test creating a campaign with TARGET_SPEND bidding strategy."""
        campaign_data = {
            "campaign_id": "123456789",
            "customer_id": "987654321",
            "name": "Test Campaign",
            "status": CampaignStatus.ENABLED,
            "type": CampaignType.SEARCH,
            "budget_amount": 100.0,
            "budget_currency": "USD",
            "bidding_strategy": BiddingStrategy.TARGET_SPEND,
        }

        campaign = Campaign(**campaign_data)

        assert campaign.campaign_id == "123456789"
        assert campaign.customer_id == "987654321"
        assert campaign.name == "Test Campaign"
        assert campaign.status == CampaignStatus.ENABLED
        assert campaign.type == CampaignType.SEARCH
        assert campaign.budget_amount == 100.0
        assert campaign.bidding_strategy == BiddingStrategy.TARGET_SPEND

    def test_campaign_creation_with_all_bidding_strategies(self):
        """Test creating campaigns with all bidding strategy types."""
        base_data = {
            "campaign_id": "123456789",
            "customer_id": "987654321",
            "name": "Test Campaign",
            "status": CampaignStatus.ENABLED,
            "type": CampaignType.SEARCH,
            "budget_amount": 100.0,
            "budget_currency": "USD",
        }

        for strategy in BiddingStrategy:
            campaign_data = {**base_data, "bidding_strategy": strategy}
            campaign = Campaign(**campaign_data)
            assert campaign.bidding_strategy == strategy

    def test_campaign_properties(self):
        """Test campaign calculated properties."""
        campaign = Campaign(
            campaign_id="123456789",
            customer_id="987654321",
            name="Test Campaign",
            status=CampaignStatus.ENABLED,
            type=CampaignType.SEARCH,
            budget_amount=100.0,
            budget_currency="USD",
            bidding_strategy=BiddingStrategy.TARGET_SPEND,
            impressions=1000,
            clicks=50,
            cost=75.0,
            conversions=5.0,
            conversion_value=250.0,
        )

        assert campaign.ctr == 5.0  # (50/1000) * 100
        assert campaign.avg_cpc == 1.5  # 75/50
        assert campaign.conversion_rate == 10.0  # (5/50) * 100
        assert campaign.cpa == 15.0  # 75/5
        assert campaign.roas == pytest.approx(3.33, rel=1e-2)  # 250/75

    def test_campaign_properties_zero_handling(self):
        """Test campaign properties handle zero values gracefully."""
        campaign = Campaign(
            campaign_id="123456789",
            customer_id="987654321",
            name="Test Campaign",
            status=CampaignStatus.ENABLED,
            type=CampaignType.SEARCH,
            budget_amount=100.0,
            budget_currency="USD",
            bidding_strategy=BiddingStrategy.TARGET_SPEND,
            impressions=0,
            clicks=0,
            cost=0.0,
            conversions=0.0,
            conversion_value=0.0,
        )

        assert campaign.ctr == 0.0
        assert campaign.avg_cpc == 0.0
        assert campaign.conversion_rate == 0.0
        assert campaign.cpa == 0.0
        assert campaign.roas == 0.0

    def test_campaign_with_optional_fields(self):
        """Test campaign creation with optional fields."""
        now = datetime.now(timezone.utc)

        campaign = Campaign(
            campaign_id="123456789",
            customer_id="987654321",
            name="Test Campaign",
            status=CampaignStatus.ENABLED,
            type=CampaignType.SEARCH,
            budget_amount=100.0,
            budget_currency="USD",
            bidding_strategy=BiddingStrategy.TARGET_SPEND,
            target_cpa=25.0,
            target_roas=4.0,
            start_date=now,
            end_date=now,
            geo_targets=["US", "CA"],
            language_targets=["en", "es"],
            tracking_url_template="https://example.com/track?id={campaignid}",
        )

        assert campaign.target_cpa == 25.0
        assert campaign.target_roas == 4.0
        assert campaign.start_date == now
        assert campaign.end_date == now
        assert campaign.geo_targets == ["US", "CA"]
        assert campaign.language_targets == ["en", "es"]
        assert (
            campaign.tracking_url_template
            == "https://example.com/track?id={campaignid}"
        )
