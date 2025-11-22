"""Tests for customer journey builder with GCLID matching."""

from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pandas as pd
import pytest

from paidsearchnav.attribution.journey_builder import CustomerJourneyBuilder
from paidsearchnav.attribution.models import (
    AttributionTouch,
    ConversionType,
    CustomerJourney,
    TouchpointType,
)


@pytest.fixture
def mock_bigquery_client():
    """Mock BigQuery client for testing."""
    client = Mock()
    client.query_to_dataframe = AsyncMock()
    client.dataset_id = "test_dataset"
    return client


@pytest.fixture
def mock_ga4_client():
    """Mock GA4 client for testing."""
    client = Mock()
    client.get_historical_metrics = AsyncMock()
    return client


@pytest.fixture
def journey_builder(mock_bigquery_client, mock_ga4_client):
    """Create journey builder instance with mocked clients."""
    return CustomerJourneyBuilder(
        bigquery_client=mock_bigquery_client,
        ga4_client=mock_ga4_client,
        session_timeout_minutes=30,
        max_journey_length_days=90,
    )


@pytest.fixture
def sample_google_ads_data():
    """Create sample Google Ads click data."""
    return pd.DataFrame(
        [
            {
                "click_timestamp": datetime(2025, 1, 1, 10, 0, 0),
                "gclid": "test_gclid_1",
                "campaign_id": "campaign_123",
                "campaign_name": "Test Campaign",
                "ad_group_id": "adgroup_123",
                "keyword_id": "keyword_123",
                "search_term": "test product",
                "click_cost": 2.50,
                "device": "mobile",
                "geo_target": "US",
                "landing_page_url": "https://example.com/landing",
                "conversions": 0,
                "conversion_value": 0.0,
                "customer_id": "test_customer_123",
            },
            {
                "click_timestamp": datetime(2025, 1, 2, 14, 0, 0),
                "gclid": "test_gclid_2",
                "campaign_id": "campaign_456",
                "campaign_name": "Another Campaign",
                "ad_group_id": "adgroup_456",
                "keyword_id": "keyword_456",
                "search_term": "buy now",
                "click_cost": 3.75,
                "device": "desktop",
                "geo_target": "US",
                "landing_page_url": "https://example.com/product",
                "conversions": 1,
                "conversion_value": 150.0,
                "customer_id": "test_customer_123",
            },
        ]
    )


@pytest.fixture
def sample_ga4_data():
    """Create sample GA4 session data."""
    return pd.DataFrame(
        [
            {
                "date": "2025-01-01",
                "source": "google",
                "medium": "cpc",
                "campaign": "test-campaign",
                "gclid": "test_gclid_1",
                "sessionId": "session_123",
                "userId": "user_123",
                "country": "United States",
                "deviceCategory": "mobile",
                "landingPage": "https://example.com/landing",
                "sessionStart": datetime(2025, 1, 1, 10, 1, 0),  # 1 min after click
                "sessions": 1,
                "conversions": 0,
                "totalRevenue": 0.0,
                "bounceRate": 0.3,
                "engagementRate": 0.7,
                "averageSessionDuration": 120.5,
            },
            {
                "date": "2025-01-01",
                "source": "google",
                "medium": "organic",
                "campaign": "(not set)",
                "gclid": "",
                "sessionId": "session_456",
                "userId": "user_123",
                "country": "United States",
                "deviceCategory": "desktop",
                "landingPage": "https://example.com/product",
                "sessionStart": datetime(2025, 1, 1, 16, 0, 0),
                "sessions": 1,
                "conversions": 0,
                "totalRevenue": 0.0,
                "bounceRate": 0.2,
                "engagementRate": 0.8,
                "averageSessionDuration": 300.0,
            },
            {
                "date": "2025-01-02",
                "source": "direct",
                "medium": "(none)",
                "campaign": "(not set)",
                "gclid": "",
                "sessionId": "session_789",
                "userId": "user_123",
                "country": "United States",
                "deviceCategory": "mobile",
                "landingPage": "https://example.com/checkout",
                "sessionStart": datetime(2025, 1, 2, 15, 0, 0),
                "sessions": 1,
                "conversions": 1,
                "totalRevenue": 150.0,
                "bounceRate": 0.0,
                "engagementRate": 1.0,
                "averageSessionDuration": 600.0,
                "eventName": "purchase",
            },
        ]
    )


class TestCustomerJourneyBuilder:
    """Test cases for CustomerJourneyBuilder class."""

    @pytest.mark.asyncio
    async def test_build_customer_journeys(
        self,
        journey_builder,
        sample_google_ads_data,
        sample_ga4_data,
    ):
        """Test building customer journeys from Google Ads and GA4 data."""
        # Setup mock responses
        journey_builder.bigquery_client.query_to_dataframe.return_value = (
            sample_google_ads_data
        )
        journey_builder.ga4_client.get_historical_metrics.return_value = {
            "rows": sample_ga4_data.to_dict("records")
        }

        # Build journeys
        journeys, journey_touches = await journey_builder.build_customer_journeys(
            customer_id="test_customer_123",
            start_date=datetime(2025, 1, 1),
            end_date=datetime(2025, 1, 2),
            include_non_converting=True,
        )

        assert len(journeys) >= 1
        assert len(journey_touches) >= 1

        # Check first journey
        journey = journeys[0]
        assert journey.customer_id == "test_customer_123"
        assert journey.total_touches >= 3  # At least 3 touchpoints

        # Check touchpoints
        touches = journey_touches[journey.journey_id]
        assert len(touches) >= 3

    def test_create_gclid_mappings(
        self, journey_builder, sample_google_ads_data, sample_ga4_data
    ):
        """Test GCLID mapping creation between Google Ads and GA4."""
        mappings = journey_builder._create_gclid_mappings(
            sample_google_ads_data, sample_ga4_data
        )

        # Should create at least one mapping for gclid_1
        assert len(mappings) >= 1

        # Check first mapping
        mapping = mappings[0]
        assert mapping.gclid == "test_gclid_1"
        assert mapping.campaign_id == "campaign_123"
        assert mapping.ga4_session_id == "session_123"
        assert mapping.match_confidence > 0.9  # High confidence due to close timing

    def test_build_unified_touchpoints(
        self, journey_builder, sample_google_ads_data, sample_ga4_data
    ):
        """Test building unified touchpoint list."""
        # Create GCLID mappings
        mappings = journey_builder._create_gclid_mappings(
            sample_google_ads_data, sample_ga4_data
        )

        # Build touchpoints
        touches = journey_builder._build_unified_touchpoints(
            sample_google_ads_data, sample_ga4_data, mappings
        )

        # Should have touches for Google Ads clicks and GA4 sessions
        assert len(touches) >= 4  # 2 clicks + 2 non-gclid GA4 sessions

        # Check touchpoint types
        touchpoint_types = [touch.touchpoint_type for touch in touches]
        assert TouchpointType.GOOGLE_ADS_CLICK in touchpoint_types
        assert TouchpointType.GA4_SESSION in touchpoint_types

    def test_group_into_journeys(self, journey_builder):
        """Test grouping touchpoints into customer journeys."""
        # Create test touchpoints with different customers and timing
        touches = [
            # Customer 1 - Single journey
            AttributionTouch(
                customer_id="customer_1",
                touchpoint_type=TouchpointType.GOOGLE_ADS_CLICK,
                timestamp=datetime(2025, 1, 1, 10, 0, 0),
                source="google",
                medium="cpc",
            ),
            AttributionTouch(
                customer_id="customer_1",
                touchpoint_type=TouchpointType.DIRECT_VISIT,
                timestamp=datetime(2025, 1, 1, 10, 15, 0),  # 15 minutes later
                source="direct",
                medium="(none)",
                is_conversion_touch=True,
                conversion_value=100.0,
            ),
            # Customer 1 - Second journey (after timeout)
            AttributionTouch(
                customer_id="customer_1",
                touchpoint_type=TouchpointType.GA4_SESSION,
                timestamp=datetime(2025, 1, 2, 10, 0, 0),  # Next day
                source="google",
                medium="organic",
            ),
            # Customer 2 - Separate journey
            AttributionTouch(
                customer_id="customer_2",
                touchpoint_type=TouchpointType.GOOGLE_ADS_CLICK,
                timestamp=datetime(2025, 1, 1, 11, 0, 0),
                source="google",
                medium="cpc",
            ),
        ]

        journeys, journey_touches = journey_builder._group_into_journeys(
            touches, include_non_converting=True
        )

        # Should create separate journeys
        assert len(journeys) >= 2  # At least 2 journeys

        # Check customer separation
        customer_1_journeys = [j for j in journeys if j.customer_id == "customer_1"]
        customer_2_journeys = [j for j in journeys if j.customer_id == "customer_2"]

        assert len(customer_1_journeys) >= 1
        assert len(customer_2_journeys) >= 1

    def test_split_customer_journeys(self, journey_builder):
        """Test splitting customer touches into separate journeys."""
        # Create touches with different timing gaps
        touches = [
            AttributionTouch(
                customer_id="customer_1",
                touchpoint_type=TouchpointType.GOOGLE_ADS_CLICK,
                timestamp=datetime(2025, 1, 1, 10, 0, 0),
                source="google",
                medium="cpc",
            ),
            AttributionTouch(
                customer_id="customer_1",
                touchpoint_type=TouchpointType.DIRECT_VISIT,
                timestamp=datetime(2025, 1, 1, 10, 15, 0),  # 15 min later
                source="direct",
                medium="(none)",
                is_conversion_touch=True,
            ),
            # Long gap - should start new journey
            AttributionTouch(
                customer_id="customer_1",
                touchpoint_type=TouchpointType.GA4_SESSION,
                timestamp=datetime(2025, 1, 2, 10, 0, 0),  # 24 hours later
                source="google",
                medium="organic",
            ),
        ]

        journey_groups = journey_builder._split_customer_journeys(touches)

        # Should split into 2 separate journeys due to time gap
        assert len(journey_groups) == 2
        assert len(journey_groups[0]) == 2  # First journey: click + conversion
        assert len(journey_groups[1]) == 1  # Second journey: organic session

    def test_identify_cross_device_journeys(self, journey_builder):
        """Test identification of cross-device customer journeys."""
        # Create journeys with different device patterns
        journeys = [
            CustomerJourney(
                journey_id="journey_single_device",
                customer_id="customer_1",
                first_touch=datetime(2025, 1, 1),
                last_touch=datetime(2025, 1, 1),
                total_touches=2,
                is_multi_device=False,
            ),
            CustomerJourney(
                journey_id="journey_multi_device",
                customer_id="customer_1",
                first_touch=datetime(2025, 1, 1),
                last_touch=datetime(2025, 1, 2),
                total_touches=3,
                is_multi_device=False,  # Will be updated by method
            ),
        ]

        journey_touches = {
            "journey_single_device": [
                AttributionTouch(
                    customer_journey_id="journey_single_device",
                    customer_id="customer_1",
                    touchpoint_type=TouchpointType.GOOGLE_ADS_CLICK,
                    timestamp=datetime(2025, 1, 1),
                    device_category="mobile",
                ),
                AttributionTouch(
                    customer_journey_id="journey_single_device",
                    customer_id="customer_1",
                    touchpoint_type=TouchpointType.DIRECT_VISIT,
                    timestamp=datetime(2025, 1, 1, 0, 30, 0),
                    device_category="mobile",
                ),
            ],
            "journey_multi_device": [
                AttributionTouch(
                    customer_journey_id="journey_multi_device",
                    customer_id="customer_1",
                    touchpoint_type=TouchpointType.GOOGLE_ADS_CLICK,
                    timestamp=datetime(2025, 1, 1),
                    device_category="mobile",
                ),
                AttributionTouch(
                    customer_journey_id="journey_multi_device",
                    customer_id="customer_1",
                    touchpoint_type=TouchpointType.GA4_SESSION,
                    timestamp=datetime(2025, 1, 1, 12, 0, 0),
                    device_category="desktop",
                ),
                AttributionTouch(
                    customer_journey_id="journey_multi_device",
                    customer_id="customer_1",
                    touchpoint_type=TouchpointType.DIRECT_VISIT,
                    timestamp=datetime(2025, 1, 2),
                    device_category="tablet",
                ),
            ],
        }

        cross_device_journeys = journey_builder.identify_cross_device_journeys(
            journeys, journey_touches
        )

        # Should identify the multi-device journey
        assert len(cross_device_journeys) == 1
        assert "journey_multi_device" in cross_device_journeys

        # Journey should be updated
        multi_device_journey = next(
            j for j in journeys if j.journey_id == "journey_multi_device"
        )
        assert multi_device_journey.is_multi_device is True
        assert len(multi_device_journey.devices_used) == 3  # mobile, desktop, tablet

    def test_identify_assisted_conversions(self, journey_builder):
        """Test identification of assisted conversions."""
        journeys = [
            CustomerJourney(
                journey_id="assisted_journey",
                customer_id="customer_1",
                first_touch=datetime(2025, 1, 1, 10, 0, 0),
                last_touch=datetime(2025, 1, 1, 15, 0, 0),
                converted=True,
                conversion_value=100.0,
            )
        ]

        journey_touches = {
            "assisted_journey": [
                # Assisting touch: Google Ads click
                AttributionTouch(
                    customer_journey_id="assisted_journey",
                    customer_id="customer_1",
                    touchpoint_type=TouchpointType.GOOGLE_ADS_CLICK,
                    timestamp=datetime(2025, 1, 1, 10, 0, 0),
                    source="google",
                    medium="cpc",
                    is_conversion_touch=False,
                ),
                # Converting touch: Direct visit
                AttributionTouch(
                    customer_journey_id="assisted_journey",
                    customer_id="customer_1",
                    touchpoint_type=TouchpointType.DIRECT_VISIT,
                    timestamp=datetime(2025, 1, 1, 15, 0, 0),  # 5 hours later
                    source="direct",
                    medium="(none)",
                    is_conversion_touch=True,
                    conversion_value=100.0,
                ),
            ]
        }

        assisted_conversions = journey_builder.identify_assisted_conversions(
            journeys, journey_touches, assist_window_hours=24
        )

        # Should identify Google Ads assisting Direct conversion
        assert len(assisted_conversions) >= 1
        assist_key = "google/cpc → direct/(none)"
        assert assist_key in assisted_conversions
        assert "assisted_journey" in assisted_conversions[assist_key]

    def test_calculate_path_analysis(self, journey_builder):
        """Test customer journey path analysis."""
        journeys = [
            CustomerJourney(
                journey_id="path_journey_1",
                customer_id="customer_1",
                first_touch=datetime(2025, 1, 1),
                last_touch=datetime(2025, 1, 1),
                converted=True,
                conversion_value=100.0,
                journey_length_days=0.5,
            ),
            CustomerJourney(
                journey_id="path_journey_2",
                customer_id="customer_2",
                first_touch=datetime(2025, 1, 1),
                last_touch=datetime(2025, 1, 2),
                converted=True,
                conversion_value=200.0,
                journey_length_days=1.0,
            ),
            CustomerJourney(
                journey_id="path_journey_3",
                customer_id="customer_3",
                first_touch=datetime(2025, 1, 1),
                last_touch=datetime(2025, 1, 1),
                converted=False,
                conversion_value=0.0,
                journey_length_days=0.2,
            ),
        ]

        journey_touches = {
            "path_journey_1": [
                AttributionTouch(
                    customer_journey_id="path_journey_1",
                    customer_id="customer_1",
                    touchpoint_type=TouchpointType.GOOGLE_ADS_CLICK,
                    timestamp=datetime(2025, 1, 1, 10, 0, 0),
                    source="google",
                    medium="cpc",
                ),
                AttributionTouch(
                    customer_journey_id="path_journey_1",
                    customer_id="customer_1",
                    touchpoint_type=TouchpointType.DIRECT_VISIT,
                    timestamp=datetime(2025, 1, 1, 22, 0, 0),
                    source="direct",
                    medium="(none)",
                    is_conversion_touch=True,
                ),
            ],
            "path_journey_2": [
                AttributionTouch(
                    customer_journey_id="path_journey_2",
                    customer_id="customer_2",
                    touchpoint_type=TouchpointType.GOOGLE_ADS_CLICK,
                    timestamp=datetime(2025, 1, 1, 10, 0, 0),
                    source="google",
                    medium="cpc",
                ),
                AttributionTouch(
                    customer_journey_id="path_journey_2",
                    customer_id="customer_2",
                    touchpoint_type=TouchpointType.DIRECT_VISIT,
                    timestamp=datetime(2025, 1, 2, 10, 0, 0),
                    source="direct",
                    medium="(none)",
                    is_conversion_touch=True,
                ),
            ],
            "path_journey_3": [
                AttributionTouch(
                    customer_journey_id="path_journey_3",
                    customer_id="customer_3",
                    touchpoint_type=TouchpointType.GOOGLE_ADS_CLICK,
                    timestamp=datetime(2025, 1, 1, 10, 0, 0),
                    source="google",
                    medium="cpc",
                ),
            ],
        }

        path_analysis = journey_builder.calculate_path_analysis(
            journeys, journey_touches
        )

        # Should identify the common path "google/cpc → direct/(none)"
        common_path = "google/cpc → direct/(none)"
        assert common_path in path_analysis

        path_perf = path_analysis[common_path]
        assert path_perf["total_journeys"] == 2
        assert path_perf["converting_journeys"] == 2
        assert path_perf["conversion_rate"] == 1.0
        assert path_perf["total_revenue"] == 300.0  # 100 + 200

    def test_detect_anomalies_in_journeys(self, journey_builder):
        """Test anomaly detection in customer journeys."""
        # Create journeys with some anomalies
        journeys = [
            # Normal journey
            CustomerJourney(
                journey_id="normal_journey",
                customer_id="customer_1",
                first_touch=datetime(2025, 1, 1),
                last_touch=datetime(2025, 1, 1),
                journey_length_days=0.5,
                total_touches=3,
                converted=True,
                conversion_value=100.0,
            ),
            # Unusually long journey
            CustomerJourney(
                journey_id="long_journey",
                customer_id="customer_2",
                first_touch=datetime(2025, 1, 1),
                last_touch=datetime(2025, 2, 1),  # 31 days
                journey_length_days=31.0,
                total_touches=2,
                converted=True,
                conversion_value=50.0,
            ),
            # High-value conversion
            CustomerJourney(
                journey_id="high_value_journey",
                customer_id="customer_3",
                first_touch=datetime(2025, 1, 1),
                last_touch=datetime(2025, 1, 1),
                journey_length_days=0.1,
                total_touches=1,
                converted=True,
                conversion_value=5000.0,  # Very high value
            ),
        ]

        journey_touches = {
            "normal_journey": [
                AttributionTouch(
                    customer_journey_id="normal_journey",
                    customer_id="customer_1",
                    touchpoint_type=TouchpointType.GOOGLE_ADS_CLICK,
                    timestamp=datetime(2025, 1, 1),
                    source="google",
                    medium="cpc",
                )
            ],
            "long_journey": [
                AttributionTouch(
                    customer_journey_id="long_journey",
                    customer_id="customer_2",
                    touchpoint_type=TouchpointType.GOOGLE_ADS_CLICK,
                    timestamp=datetime(2025, 1, 1),
                    source="google",
                    medium="cpc",
                )
            ],
            "high_value_journey": [
                AttributionTouch(
                    customer_journey_id="high_value_journey",
                    customer_id="customer_3",
                    touchpoint_type=TouchpointType.DIRECT_VISIT,
                    timestamp=datetime(2025, 1, 1),
                    source="direct",
                    medium="(none)",
                )
            ],
        }

        anomalies = journey_builder.detect_anomalies_in_journeys(
            journeys, journey_touches
        )

        # Should detect anomalies
        assert len(anomalies) >= 2

        # Check for expected anomaly types
        anomaly_types = [anomaly["type"] for anomaly in anomalies]
        assert "unusually_long_journey" in anomaly_types
        assert "high_value_conversion" in anomaly_types

    @pytest.mark.asyncio
    async def test_validate_journey_data_quality(self, journey_builder):
        """Test journey data quality validation."""
        journeys = [
            CustomerJourney(
                journey_id="quality_journey_1",
                customer_id="customer_1",
                first_touch=datetime(2025, 1, 1),
                last_touch=datetime(2025, 1, 2),
                journey_length_days=1.0,
                total_touches=3,
                converted=True,
                is_multi_device=True,
            ),
            CustomerJourney(
                journey_id="quality_journey_2",
                customer_id="customer_2",
                first_touch=datetime(2025, 1, 1),
                last_touch=datetime(2025, 1, 1),
                journey_length_days=0.5,
                total_touches=2,
                converted=False,
                is_multi_device=False,
            ),
        ]

        journey_touches = {
            "quality_journey_1": [
                AttributionTouch(
                    customer_journey_id="quality_journey_1",
                    customer_id="customer_1",
                    touchpoint_type=TouchpointType.GOOGLE_ADS_CLICK,
                    timestamp=datetime(2025, 1, 1),
                    gclid="gclid_1",
                    device_category="mobile",
                ),
                AttributionTouch(
                    customer_journey_id="quality_journey_1",
                    customer_id="customer_1",
                    touchpoint_type=TouchpointType.GA4_SESSION,
                    timestamp=datetime(2025, 1, 1, 12, 0, 0),
                    gclid="gclid_2",
                    device_category="desktop",  # Different device
                ),
                AttributionTouch(
                    customer_journey_id="quality_journey_1",
                    customer_id="customer_1",
                    touchpoint_type=TouchpointType.DIRECT_VISIT,
                    timestamp=datetime(2025, 1, 2),
                    device_category="mobile",
                    is_conversion_touch=True,
                ),
            ],
            "quality_journey_2": [
                AttributionTouch(
                    customer_journey_id="quality_journey_2",
                    customer_id="customer_2",
                    touchpoint_type=TouchpointType.GA4_SESSION,
                    timestamp=datetime(2025, 1, 1),
                    # No GCLID
                    device_category="desktop",
                ),
                AttributionTouch(
                    customer_journey_id="quality_journey_2",
                    customer_id="customer_2",
                    touchpoint_type=TouchpointType.GA4_SESSION,
                    timestamp=datetime(2025, 1, 1, 0, 30, 0),
                    device_category="desktop",
                ),
            ],
        }

        quality_metrics = await journey_builder.validate_journey_data_quality(
            journeys, journey_touches
        )

        # Verify quality metrics
        assert quality_metrics["total_journeys"] == 2
        assert quality_metrics["converting_journeys"] == 1
        assert (
            quality_metrics["gclid_match_rate"] == 0.4
        )  # 2 out of 5 touches have GCLID
        assert (
            quality_metrics["multi_touch_rate"] == 1.0
        )  # All journeys have multiple touches
        assert (
            quality_metrics["cross_device_rate"] == 0.5
        )  # 1 out of 2 journeys cross-device
        assert 0.0 <= quality_metrics["data_quality_score"] <= 1.0

    def test_get_journey_insights(self, journey_builder):
        """Test generation of customer journey insights."""
        journeys = [
            CustomerJourney(
                journey_id="insight_journey_1",
                customer_id="customer_1",
                first_touch=datetime(2025, 1, 1),
                last_touch=datetime(2025, 1, 1),
                journey_length_days=0.25,  # Same day
                total_touches=2,
                converted=True,
                conversion_value=100.0,
                first_touch_source="google",
                first_touch_medium="cpc",
                last_touch_source="direct",
                last_touch_medium="(none)",
            ),
            CustomerJourney(
                journey_id="insight_journey_2",
                customer_id="customer_2",
                first_touch=datetime(2025, 1, 1),
                last_touch=datetime(2025, 1, 8),  # 7 days
                journey_length_days=7.0,
                total_touches=5,
                converted=True,
                conversion_value=250.0,
                first_touch_source="facebook",
                first_touch_medium="social",
                last_touch_source="google",
                last_touch_medium="organic",
            ),
        ]

        journey_touches = {
            "insight_journey_1": [
                AttributionTouch(
                    customer_journey_id="insight_journey_1",
                    customer_id="customer_1",
                    touchpoint_type=TouchpointType.GOOGLE_ADS_CLICK,
                    timestamp=datetime(2025, 1, 1),
                ),
                AttributionTouch(
                    customer_journey_id="insight_journey_1",
                    customer_id="customer_1",
                    touchpoint_type=TouchpointType.DIRECT_VISIT,
                    timestamp=datetime(2025, 1, 1, 6, 0, 0),
                ),
            ],
            "insight_journey_2": [
                AttributionTouch(
                    customer_journey_id="insight_journey_2",
                    customer_id="customer_2",
                    touchpoint_type=TouchpointType.GA4_SESSION,
                    timestamp=datetime(2025, 1, 1),
                ),
                AttributionTouch(
                    customer_journey_id="insight_journey_2",
                    customer_id="customer_2",
                    touchpoint_type=TouchpointType.GA4_SESSION,
                    timestamp=datetime(2025, 1, 2),
                ),
                AttributionTouch(
                    customer_journey_id="insight_journey_2",
                    customer_id="customer_2",
                    touchpoint_type=TouchpointType.GA4_SESSION,
                    timestamp=datetime(2025, 1, 3),
                ),
                AttributionTouch(
                    customer_journey_id="insight_journey_2",
                    customer_id="customer_2",
                    touchpoint_type=TouchpointType.GA4_SESSION,
                    timestamp=datetime(2025, 1, 7),
                ),
                AttributionTouch(
                    customer_journey_id="insight_journey_2",
                    customer_id="customer_2",
                    touchpoint_type=TouchpointType.DIRECT_VISIT,
                    timestamp=datetime(2025, 1, 8),
                ),
            ],
        }

        insights = journey_builder.get_journey_insights(journeys, journey_touches)

        # Verify journey length distribution
        length_dist = insights["journey_length_distribution"]
        assert length_dist["same_day"] == 1  # One same-day journey
        assert length_dist["7_30_days"] == 1  # One 7-day journey

        # Verify touch count distribution
        touch_dist = insights["touch_count_distribution"]
        assert touch_dist["2_5_touches"] == 2  # Both journeys have 2-5 touches

        # Verify conversion insights
        conversion_insights = insights["conversion_insights"]
        assert conversion_insights["conversion_rate"] == 1.0  # Both journeys converted
        assert conversion_insights["avg_conversion_value"] == 175.0  # (100 + 250) / 2

    def test_create_journey_from_touches(self, journey_builder):
        """Test creation of customer journey from touchpoints."""
        touches = [
            AttributionTouch(
                customer_id="customer_1",
                touchpoint_type=TouchpointType.GOOGLE_ADS_CLICK,
                timestamp=datetime(2025, 1, 1, 10, 0, 0),
                source="google",
                medium="cpc",
                device_category="mobile",
                country="US",
                ga4_session_id="session_1",
                page_views=1,
                engagement_time_msec=30000,
            ),
            AttributionTouch(
                customer_id="customer_1",
                touchpoint_type=TouchpointType.GA4_SESSION,
                timestamp=datetime(2025, 1, 1, 14, 0, 0),
                source="google",
                medium="organic",
                device_category="desktop",
                country="US",
                ga4_session_id="session_2",
                page_views=3,
                engagement_time_msec=120000,
            ),
            AttributionTouch(
                customer_id="customer_1",
                touchpoint_type=TouchpointType.DIRECT_VISIT,
                timestamp=datetime(2025, 1, 2, 9, 0, 0),
                source="direct",
                medium="(none)",
                device_category="mobile",
                country="CA",  # Different country
                is_conversion_touch=True,
                conversion_value=150.0,
                conversion_type=ConversionType.PURCHASE,
                page_views=2,
                engagement_time_msec=60000,
            ),
        ]

        journey = journey_builder._create_journey_from_touches(touches)

        assert journey is not None
        assert journey.customer_id == "customer_1"
        assert journey.total_touches == 3
        assert journey.total_sessions == 2  # 2 unique GA4 sessions
        assert journey.total_pageviews == 6  # 1 + 3 + 2
        assert journey.total_engagement_time_msec == 210000  # 30k + 120k + 60k
        assert journey.converted is True
        assert journey.conversion_value == 150.0
        assert journey.conversion_type == ConversionType.PURCHASE
        assert journey.is_multi_device is True  # mobile and desktop
        assert journey.is_multi_channel is True  # google/cpc, google/organic, direct
        assert journey.first_touch_source == "google"
        assert journey.last_touch_source == "direct"
        assert len(journey.countries_visited) == 2  # US and CA
        assert len(journey.devices_used) == 2  # mobile and desktop

    def test_gclid_mapping_quality_scoring(self, journey_builder):
        """Test GCLID mapping quality scoring."""
        google_ads_data = pd.DataFrame(
            [
                {
                    "click_timestamp": datetime(2025, 1, 1, 10, 0, 0),
                    "gclid": "perfect_match",
                    "campaign_id": "camp_1",
                    "campaign_name": "Campaign 1",
                    "ad_group_id": "ag_1",
                    "click_cost": 2.0,
                    "customer_id": "customer_1",
                },
                {
                    "click_timestamp": datetime(2025, 1, 1, 14, 0, 0),
                    "gclid": "delayed_match",
                    "campaign_id": "camp_2",
                    "campaign_name": "Campaign 2",
                    "ad_group_id": "ag_2",
                    "click_cost": 3.0,
                    "customer_id": "customer_1",
                },
            ]
        )

        ga4_data = pd.DataFrame(
            [
                {
                    "gclid": "perfect_match",
                    "sessionId": "session_1",
                    "userId": "user_1",
                    "session_start": datetime(
                        2025, 1, 1, 10, 1, 0
                    ),  # 1 minute after click
                    "landingPage": "https://example.com",
                    "conversions": 1,
                    "totalRevenue": 100.0,
                },
                {
                    "gclid": "delayed_match",
                    "sessionId": "session_2",
                    "userId": "user_1",
                    "session_start": datetime(
                        2025, 1, 1, 16, 0, 0
                    ),  # 2 hours after click
                    "landingPage": "https://example.com/product",
                    "conversions": 0,
                    "totalRevenue": 0.0,
                },
            ]
        )

        mappings = journey_builder._create_gclid_mappings(google_ads_data, ga4_data)

        assert len(mappings) == 2

        # Perfect match should have high confidence
        perfect_mapping = next(m for m in mappings if m.gclid == "perfect_match")
        assert perfect_mapping.match_confidence == 1.0  # Within 5 minutes
        assert perfect_mapping.time_diff_seconds == 60

        # Delayed match should have lower confidence
        delayed_mapping = next(m for m in mappings if m.gclid == "delayed_match")
        assert delayed_mapping.match_confidence == 0.8  # Within 2 hours
        assert delayed_mapping.time_diff_seconds == 7200

    @pytest.mark.asyncio
    async def test_store_visit_enrichment(self, journey_builder):
        """Test enrichment of journeys with store visit data."""
        journeys = [
            CustomerJourney(
                journey_id="store_journey",
                customer_id="customer_1",
                first_touch=datetime(2025, 1, 1),
                last_touch=datetime(2025, 1, 1),
                total_touches=1,
            )
        ]

        journey_touches = {
            "store_journey": [
                AttributionTouch(
                    customer_journey_id="store_journey",
                    customer_id="customer_1",
                    touchpoint_type=TouchpointType.GOOGLE_ADS_CLICK,
                    timestamp=datetime(2025, 1, 1),
                )
            ]
        }

        # Mock store visit data
        with patch.object(
            journey_builder, "_get_store_visits_for_customer"
        ) as mock_store_visits:
            mock_store_visits.return_value = [
                {
                    "visit_timestamp": datetime(2025, 1, 2),
                    "store_id": "store_123",
                    "country": "US",
                    "purchase_made": True,
                    "purchase_amount": 75.0,
                }
            ]

            (
                enriched_journeys,
                enriched_touches,
            ) = await journey_builder.enrich_with_store_visits(
                journeys, journey_touches
            )

            # Journey should be enriched with store visit
            journey = enriched_journeys[0]
            assert len(journey.stores_visited) == 1
            assert journey.stores_visited[0] == "store_123"
            assert journey.total_touches == 2  # Original + store visit

            # Store visit touch should be added
            touches = enriched_touches["store_journey"]
            assert len(touches) == 2
            store_touch = next(
                t for t in touches if t.touchpoint_type == TouchpointType.STORE_VISIT
            )
            assert store_touch.store_location_id == "store_123"
            assert store_touch.is_conversion_touch is True
            assert store_touch.conversion_value == 75.0
