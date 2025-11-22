"""Unit tests for extended Google Ads models."""

import pytest
from pydantic import ValidationError

from paidsearchnav_mcp.platforms.google.models_extended import (
    AdSchedulePerformance,
    AuctionInsights,
    DevicePerformance,
    DeviceType,
    StorePerformance,
)


class TestDevicePerformance:
    """Test DevicePerformance model."""

    def test_valid_device_performance(self):
        """Test creating a valid DevicePerformance instance."""
        data = {
            "device": DeviceType.MOBILE,
            "level": "Campaign",
            "campaign_name": "Test Campaign",
            "clicks": 100,
            "impressions": 1000,
            "cost": 50.0,
            "conversions": 10.0,
        }

        device_perf = DevicePerformance(**data)
        assert device_perf.device == DeviceType.MOBILE
        assert device_perf.clicks == 100
        assert device_perf.cost == 50.0

    def test_device_type_enum(self):
        """Test DeviceType enum values."""
        assert DeviceType.MOBILE == "Mobile phones"
        assert DeviceType.DESKTOP == "Computers"
        assert DeviceType.TABLET == "Tablets"

    def test_optional_fields(self):
        """Test that optional fields work correctly."""
        data = {
            "device": DeviceType.DESKTOP,
            "level": "Ad group",
            "campaign_name": "Test Campaign",
        }

        device_perf = DevicePerformance(**data)
        assert device_perf.bid_adjustment is None
        assert device_perf.ctr is None
        assert device_perf.clicks == 0  # Default value

    def test_invalid_device_type(self):
        """Test that invalid device type raises error."""
        data = {
            "device": "Invalid Device",
            "level": "Campaign",
            "campaign_name": "Test Campaign",
        }

        with pytest.raises(ValidationError):
            DevicePerformance(**data)


class TestAdSchedulePerformance:
    """Test AdSchedulePerformance model."""

    def test_valid_ad_schedule(self):
        """Test creating a valid AdSchedulePerformance instance."""
        data = {
            "day_time": "Monday, 9:00 AM - 5:00 PM",
            "clicks": 50,
            "impressions": 500,
            "cost": 25.0,
            "conversions": 5.0,
        }

        schedule_perf = AdSchedulePerformance(**data)
        assert schedule_perf.day_time == "Monday, 9:00 AM - 5:00 PM"
        assert schedule_perf.clicks == 50

    def test_all_day_schedule(self):
        """Test schedule with 'all day' format."""
        data = {
            "day_time": "Tuesday, all day",
            "bid_adjustment": -0.1,
            "cost": 100.0,
        }

        schedule_perf = AdSchedulePerformance(**data)
        assert schedule_perf.day_time == "Tuesday, all day"
        assert schedule_perf.bid_adjustment == -0.1


class TestStorePerformance:
    """Test StorePerformance model."""

    def test_valid_store_performance(self):
        """Test creating a valid StorePerformance instance."""
        data = {
            "store_name": "Test Store Dallas",
            "address_line_1": "123 Main St",
            "city": "Dallas",
            "state": "TX",
            "postal_code": "75201",
            "local_impressions": 1000,
            "call_clicks": 10,
            "driving_directions": 5,
            "website_visits": 20,
        }

        store_perf = StorePerformance(**data)
        assert store_perf.store_name == "Test Store Dallas"
        assert store_perf.total_engagements == 35  # 10 + 5 + 20

    def test_engagement_rate_calculation(self):
        """Test engagement rate calculation."""
        data = {
            "store_name": "Test Store",
            "address_line_1": "123 Main St",
            "city": "Dallas",
            "state": "TX",
            "postal_code": "75201",
            "local_impressions": 1000,
            "call_clicks": 10,
            "driving_directions": 5,
            "website_visits": 15,
        }

        store_perf = StorePerformance(**data)
        assert store_perf.engagement_rate == 0.03  # 30/1000

    def test_zero_impressions_engagement_rate(self):
        """Test engagement rate with zero impressions."""
        data = {
            "store_name": "Test Store",
            "address_line_1": "123 Main St",
            "city": "Dallas",
            "state": "TX",
            "postal_code": "75201",
            "local_impressions": 0,
            "call_clicks": 0,
        }

        store_perf = StorePerformance(**data)
        assert store_perf.engagement_rate is None


class TestAuctionInsights:
    """Test AuctionInsights model."""

    def test_valid_auction_insights(self):
        """Test creating a valid AuctionInsights instance."""
        data = {
            "competitor_domain": "competitor.com",
            "impression_share": 0.25,
            "overlap_rate": 0.60,
            "top_of_page_rate": 0.80,
            "outranking_share": 0.45,
        }

        insights = AuctionInsights(**data)
        assert insights.competitor_domain == "competitor.com"
        assert insights.overlap_rate == 0.60

    def test_competitive_pressure_high(self):
        """Test competitive pressure categorization - high."""
        data = {
            "competitor_domain": "competitor.com",
            "overlap_rate": 0.75,
        }

        insights = AuctionInsights(**data)
        assert insights.competitive_pressure == "high"

    def test_competitive_pressure_medium(self):
        """Test competitive pressure categorization - medium."""
        data = {
            "competitor_domain": "competitor.com",
            "overlap_rate": 0.50,
        }

        insights = AuctionInsights(**data)
        assert insights.competitive_pressure == "medium"

    def test_competitive_pressure_low(self):
        """Test competitive pressure categorization - low."""
        data = {
            "competitor_domain": "competitor.com",
            "overlap_rate": 0.20,
        }

        insights = AuctionInsights(**data)
        assert insights.competitive_pressure == "low"

    def test_competitive_pressure_unknown(self):
        """Test competitive pressure when overlap rate is None."""
        data = {
            "competitor_domain": "competitor.com",
        }

        insights = AuctionInsights(**data)
        assert insights.competitive_pressure == "unknown"
