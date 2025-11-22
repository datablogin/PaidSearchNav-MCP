"""Tests for attribution engine with multi-touch models."""

from datetime import datetime
from unittest.mock import AsyncMock, Mock

import pytest

from paidsearchnav.attribution.engine import AttributionEngine
from paidsearchnav.attribution.models import (
    AttributionModel,
    AttributionModelType,
    AttributionTouch,
    ConversionType,
    CustomerJourney,
    TouchpointType,
)


@pytest.fixture
def sample_customer_journey():
    """Create a sample customer journey for testing."""
    return CustomerJourney(
        customer_id="test_customer_123",
        first_touch=datetime(2025, 1, 1, 10, 0, 0),
        last_touch=datetime(2025, 1, 3, 15, 30, 0),
        conversion_timestamp=datetime(2025, 1, 3, 15, 30, 0),
        total_touches=3,
        converted=True,
        conversion_value=150.0,
        attribution_model=AttributionModelType.LINEAR,
        journey_length_days=2.25,
        first_touch_source="google",
        first_touch_medium="cpc",
        last_touch_source="direct",
        last_touch_medium="(none)",
    )


@pytest.fixture
def sample_attribution_touches():
    """Create sample attribution touches for testing."""
    return [
        AttributionTouch(
            customer_journey_id="journey_123",
            customer_id="test_customer_123",
            touchpoint_type=TouchpointType.GOOGLE_ADS_CLICK,
            timestamp=datetime(2025, 1, 1, 10, 0, 0),
            gclid="test_gclid_123",
            campaign_id="campaign_123",
            campaign_name="Test Campaign",
            source="google",
            medium="cpc",
            country="US",
            device_category="mobile",
            landing_page="https://example.com/landing",
        ),
        AttributionTouch(
            customer_journey_id="journey_123",
            customer_id="test_customer_123",
            touchpoint_type=TouchpointType.GA4_SESSION,
            timestamp=datetime(2025, 1, 2, 14, 30, 0),
            ga4_session_id="session_456",
            source="google",
            medium="organic",
            country="US",
            device_category="desktop",
            landing_page="https://example.com/product",
        ),
        AttributionTouch(
            customer_journey_id="journey_123",
            customer_id="test_customer_123",
            touchpoint_type=TouchpointType.DIRECT_VISIT,
            timestamp=datetime(2025, 1, 3, 15, 30, 0),
            source="direct",
            medium="(none)",
            country="US",
            device_category="mobile",
            landing_page="https://example.com/checkout",
            is_conversion_touch=True,
            conversion_value=150.0,
            conversion_type=ConversionType.PURCHASE,
        ),
    ]


@pytest.fixture
def linear_attribution_model():
    """Create a linear attribution model for testing."""
    return AttributionModel(
        model_name="Test Linear Model",
        model_type=AttributionModelType.LINEAR,
    )


@pytest.fixture
def time_decay_attribution_model():
    """Create a time decay attribution model for testing."""
    return AttributionModel(
        model_name="Test Time Decay Model",
        model_type=AttributionModelType.TIME_DECAY,
        time_decay_half_life_days=7.0,
    )


@pytest.fixture
def position_based_attribution_model():
    """Create a position-based attribution model for testing."""
    return AttributionModel(
        model_name="Test Position Based Model",
        model_type=AttributionModelType.POSITION_BASED,
        position_based_first_weight=0.4,
        position_based_last_weight=0.4,
    )


class TestAttributionEngine:
    """Test cases for the AttributionEngine class."""

    @pytest.fixture
    def engine(self):
        """Create attribution engine instance."""
        return AttributionEngine()

    async def test_first_touch_attribution(
        self, engine, sample_customer_journey, sample_attribution_touches
    ):
        """Test first-touch attribution model."""
        model = AttributionModel(
            model_name="First Touch",
            model_type=AttributionModelType.FIRST_TOUCH,
        )

        result = await engine.calculate_attribution(
            sample_customer_journey, sample_attribution_touches, model
        )

        assert result.total_conversion_value == 150.0
        assert result.total_attributed_value == 150.0
        assert len(result.touch_attributions) == 3

        # First touch should get 100% attribution
        first_touch_attribution = result.touch_attributions[0]
        assert first_touch_attribution["weight"] == 1.0
        assert first_touch_attribution["attributed_revenue"] == 150.0

        # Other touches should get 0% attribution
        assert result.touch_attributions[1]["weight"] == 0.0
        assert result.touch_attributions[2]["weight"] == 0.0

    async def test_last_touch_attribution(
        self, engine, sample_customer_journey, sample_attribution_touches
    ):
        """Test last-touch attribution model."""
        model = AttributionModel(
            model_name="Last Touch",
            model_type=AttributionModelType.LAST_TOUCH,
        )

        result = await engine.calculate_attribution(
            sample_customer_journey, sample_attribution_touches, model
        )

        # Last touch should get 100% attribution
        last_touch_attribution = result.touch_attributions[-1]
        assert last_touch_attribution["weight"] == 1.0
        assert last_touch_attribution["attributed_revenue"] == 150.0

        # Other touches should get 0% attribution
        assert result.touch_attributions[0]["weight"] == 0.0
        assert result.touch_attributions[1]["weight"] == 0.0

    async def test_linear_attribution(
        self,
        engine,
        sample_customer_journey,
        sample_attribution_touches,
        linear_attribution_model,
    ):
        """Test linear attribution model."""
        result = await engine.calculate_attribution(
            sample_customer_journey,
            sample_attribution_touches,
            linear_attribution_model,
        )

        # Each touch should get equal attribution (1/3 = 0.333...)
        expected_weight = 1.0 / 3
        expected_revenue = 150.0 / 3

        for touch_attr in result.touch_attributions:
            assert abs(touch_attr["weight"] - expected_weight) < 0.001
            assert abs(touch_attr["attributed_revenue"] - expected_revenue) < 0.001

    async def test_time_decay_attribution(
        self,
        engine,
        sample_customer_journey,
        sample_attribution_touches,
        time_decay_attribution_model,
    ):
        """Test time decay attribution model."""
        result = await engine.calculate_attribution(
            sample_customer_journey,
            sample_attribution_touches,
            time_decay_attribution_model,
        )

        # Later touches should have higher weights
        weights = [attr["weight"] for attr in result.touch_attributions]

        # Verify weights sum to 1.0
        assert abs(sum(weights) - 1.0) < 0.001

        # Later touches should have higher attribution
        assert (
            weights[2] > weights[1] > weights[0]
        )  # Conversion > Organic > First click

    async def test_position_based_attribution(
        self,
        engine,
        sample_customer_journey,
        sample_attribution_touches,
        position_based_attribution_model,
    ):
        """Test position-based (40/20/40) attribution model."""
        result = await engine.calculate_attribution(
            sample_customer_journey,
            sample_attribution_touches,
            position_based_attribution_model,
        )

        weights = [attr["weight"] for attr in result.touch_attributions]

        # First and last touches should get 40% each
        assert abs(weights[0] - 0.4) < 0.001
        assert abs(weights[2] - 0.4) < 0.001

        # Middle touch should get 20%
        assert abs(weights[1] - 0.2) < 0.001

        # Weights should sum to 1.0
        assert abs(sum(weights) - 1.0) < 0.001

    async def test_single_touch_attribution(self, engine, linear_attribution_model):
        """Test attribution with single touchpoint."""
        # Create journey with single touch
        journey = CustomerJourney(
            customer_id="test_customer",
            first_touch=datetime(2025, 1, 1),
            last_touch=datetime(2025, 1, 1),
            total_touches=1,
            converted=True,
            conversion_value=100.0,
            attribution_model=AttributionModelType.LINEAR,
        )

        touches = [
            AttributionTouch(
                customer_journey_id="journey_single",
                customer_id="test_customer",
                touchpoint_type=TouchpointType.DIRECT_VISIT,
                timestamp=datetime(2025, 1, 1),
                source="direct",
                medium="(none)",
                is_conversion_touch=True,
                conversion_value=100.0,
            )
        ]

        result = await engine.calculate_attribution(
            journey, touches, linear_attribution_model
        )

        # Single touch should get 100% attribution
        assert len(result.touch_attributions) == 1
        assert result.touch_attributions[0]["weight"] == 1.0
        assert result.touch_attributions[0]["attributed_revenue"] == 100.0

    async def test_empty_touches_attribution(
        self, engine, sample_customer_journey, linear_attribution_model
    ):
        """Test attribution with no touchpoints."""
        with pytest.raises(ValueError, match="No touchpoints provided"):
            await engine.calculate_attribution(
                sample_customer_journey, [], linear_attribution_model
            )

    async def test_non_converting_journey(self, engine, linear_attribution_model):
        """Test attribution for non-converting journey with require_conversion=True."""
        journey = CustomerJourney(
            customer_id="test_customer",
            first_touch=datetime(2025, 1, 1),
            last_touch=datetime(2025, 1, 2),
            total_touches=2,
            converted=False,
            conversion_value=0.0,
            attribution_model=AttributionModelType.LINEAR,
        )

        touches = [
            AttributionTouch(
                customer_journey_id="journey_non_convert",
                customer_id="test_customer",
                touchpoint_type=TouchpointType.GOOGLE_ADS_CLICK,
                timestamp=datetime(2025, 1, 1),
                source="google",
                medium="cpc",
            )
        ]

        model = linear_attribution_model
        model.require_conversion = True

        result = await engine.calculate_attribution(journey, touches, model)

        # Should return empty result for non-converting journey
        assert result.total_conversion_value == 0.0
        assert result.total_attributed_value == 0.0
        assert result.attribution_confidence == 0.0

    async def test_channel_attribution_aggregation(
        self,
        engine,
        sample_customer_journey,
        sample_attribution_touches,
        linear_attribution_model,
    ):
        """Test channel attribution aggregation."""
        result = await engine.calculate_attribution(
            sample_customer_journey,
            sample_attribution_touches,
            linear_attribution_model,
        )

        expected_revenue_per_touch = 150.0 / 3  # Linear attribution

        # Verify channel attribution
        assert result.channel_attribution["google/cpc"] == expected_revenue_per_touch
        assert (
            result.channel_attribution["google/organic"] == expected_revenue_per_touch
        )
        assert result.channel_attribution["direct/(none)"] == expected_revenue_per_touch

    async def test_confidence_calculation(self, engine, linear_attribution_model):
        """Test attribution confidence calculation."""
        # Journey with good GCLID coverage
        touches_with_gclid = [
            AttributionTouch(
                customer_journey_id="journey_conf",
                customer_id="test_customer",
                touchpoint_type=TouchpointType.GOOGLE_ADS_CLICK,
                timestamp=datetime(2025, 1, 1),
                gclid="test_gclid_1",
                source="google",
                medium="cpc",
            ),
            AttributionTouch(
                customer_journey_id="journey_conf",
                customer_id="test_customer",
                touchpoint_type=TouchpointType.GA4_SESSION,
                timestamp=datetime(2025, 1, 1, 0, 10, 0),  # 10 minutes later
                gclid="test_gclid_2",
                source="google",
                medium="cpc",
            ),
        ]

        confidence = engine._calculate_confidence(
            touches_with_gclid, linear_attribution_model
        )

        # Should have high confidence due to multiple touches and GCLID matches
        assert confidence > 0.7

    async def test_incremental_value_calculation(self, engine):
        """Test incremental value calculation for channels."""
        from paidsearchnav.attribution.models import AttributionResult

        # Create mock attribution results
        current_results = [
            AttributionResult(
                customer_journey_id="journey_1",
                customer_id="customer_1",
                attribution_model_id="model_1",
                channel_attribution={"google/cpc": 100.0, "google/organic": 50.0},
            ),
            AttributionResult(
                customer_journey_id="journey_2",
                customer_id="customer_1",
                attribution_model_id="model_1",
                channel_attribution={"google/cpc": 80.0, "direct/(none)": 30.0},
            ),
        ]

        baseline_results = [
            AttributionResult(
                customer_journey_id="journey_3",
                customer_id="customer_1",
                attribution_model_id="model_1",
                channel_attribution={"google/cpc": 120.0, "google/organic": 40.0},
            ),
        ]

        incremental = engine.calculate_incremental_value(
            current_results, baseline_results, "google/cpc"
        )

        assert incremental["channel"] == "google/cpc"
        assert incremental["current_attributed_revenue"] == 180.0  # 100 + 80
        assert incremental["baseline_attributed_revenue"] == 120.0
        assert incremental["incremental_revenue"] == 60.0  # 180 - 120
        assert incremental["lift_percentage"] == 50.0  # (60/120) * 100

    async def test_compare_attribution_models(
        self,
        engine,
        sample_customer_journey,
        sample_attribution_touches,
        linear_attribution_model,
    ):
        """Test attribution model comparison."""
        models = [
            AttributionModel(
                model_name="First Touch",
                model_type=AttributionModelType.FIRST_TOUCH,
            ),
            AttributionModel(
                model_name="Last Touch",
                model_type=AttributionModelType.LAST_TOUCH,
            ),
            linear_attribution_model,
        ]

        results = await engine.compare_attribution_models(
            sample_customer_journey, sample_attribution_touches, models
        )

        assert len(results) == 3
        assert "First Touch" in results
        assert "Last Touch" in results
        assert "Test Linear Model" in results

        # Verify each model produced different attribution
        first_touch_result = results["First Touch"]
        last_touch_result = results["Last Touch"]

        assert first_touch_result.touch_attributions[0]["weight"] == 1.0
        assert last_touch_result.touch_attributions[-1]["weight"] == 1.0

    async def test_top_converting_sequences(self, engine):
        """Test identification of top converting sequences."""
        from paidsearchnav.attribution.models import AttributionResult

        # Create mock results with different sequences
        results = []

        for i in range(10):
            result = AttributionResult(
                customer_journey_id=f"journey_{i}",
                customer_id="customer_1",
                attribution_model_id="model_1",
                total_conversion_value=100.0,
                touch_attributions=[
                    {
                        "touchpoint_type": "google_ads_click",
                        "timestamp": "2025-01-01T10:00:00",
                        "weight": 0.5,
                    },
                    {
                        "touchpoint_type": "direct_visit",
                        "timestamp": "2025-01-01T15:00:00",
                        "weight": 0.5,
                    },
                ],
            )
            results.append(result)

        # Add some results with different sequence
        for i in range(3):
            result = AttributionResult(
                customer_journey_id=f"journey_alt_{i}",
                customer_id="customer_1",
                attribution_model_id="model_1",
                total_conversion_value=120.0,
                touch_attributions=[
                    {
                        "touchpoint_type": "ga4_session",
                        "timestamp": "2025-01-01T10:00:00",
                        "weight": 1.0,
                    },
                ],
            )
            results.append(result)

        sequences = engine.identify_top_converting_sequences(results, min_occurrences=5)

        # Should identify the common sequence that occurred 10 times
        assert len(sequences) >= 1
        top_sequence = sequences[0]
        assert top_sequence["occurrences"] >= 10
        assert "google_ads_click → direct_visit" == top_sequence["sequence"]
        assert top_sequence["total_revenue"] == 1000.0  # 10 * 100

    async def test_attribution_summary(self, engine):
        """Test attribution summary generation."""
        from paidsearchnav.attribution.models import AttributionResult

        results = [
            AttributionResult(
                customer_journey_id="journey_1",
                customer_id="customer_1",
                attribution_model_id="model_1",
                total_conversion_value=100.0,
                attribution_confidence=0.8,
                channel_attribution={"google/cpc": 60.0, "direct/(none)": 40.0},
            ),
            AttributionResult(
                customer_journey_id="journey_2",
                customer_id="customer_1",
                attribution_model_id="model_1",
                total_conversion_value=200.0,
                attribution_confidence=0.9,
                channel_attribution={"google/cpc": 150.0, "google/organic": 50.0},
            ),
        ]

        summary = engine.get_attribution_summary(results)

        assert summary["period_summary"]["total_conversions"] == 2
        assert summary["period_summary"]["total_attributed_revenue"] == 300.0
        assert (
            abs(summary["period_summary"]["average_attribution_confidence"] - 0.85)
            < 0.001
        )

        # Channel performance
        google_cpc_perf = summary["channel_performance"]["google/cpc"]
        assert google_cpc_perf["attributed_revenue"] == 210.0  # 60 + 150
        assert google_cpc_perf["conversions"] == 2

        # Top channels should be sorted by revenue
        top_channels = summary["top_channels_by_revenue"]
        assert top_channels[0][0] == "google/cpc"  # Highest revenue channel

    async def test_custom_attribution_model(
        self, engine, sample_customer_journey, sample_attribution_touches
    ):
        """Test custom attribution model with custom weights."""
        custom_model = AttributionModel(
            model_name="Custom Model",
            model_type=AttributionModelType.CUSTOM,
            custom_weights={
                TouchpointType.GOOGLE_ADS_CLICK: 0.6,
                TouchpointType.GA4_SESSION: 0.3,
                TouchpointType.DIRECT_VISIT: 0.1,
            },
        )

        result = await engine.calculate_attribution(
            sample_customer_journey, sample_attribution_touches, custom_model
        )

        # Verify custom weights are applied correctly
        assert (
            abs(result.touch_attributions[0]["weight"] - 0.6) < 0.001
        )  # Google Ads click
        assert abs(result.touch_attributions[1]["weight"] - 0.3) < 0.001  # GA4 session
        assert abs(result.touch_attributions[2]["weight"] - 0.1) < 0.001  # Direct visit

    async def test_attribution_with_missing_data(
        self, engine, linear_attribution_model
    ):
        """Test attribution handling with missing data in touches."""
        # Create touches with some missing data
        touches = [
            AttributionTouch(
                customer_journey_id="journey_missing",
                customer_id="test_customer",
                touchpoint_type=TouchpointType.GOOGLE_ADS_CLICK,
                timestamp=datetime(2025, 1, 1),
                # Missing source/medium
                device_category="mobile",
            ),
            AttributionTouch(
                customer_journey_id="journey_missing",
                customer_id="test_customer",
                touchpoint_type=TouchpointType.GA4_SESSION,
                timestamp=datetime(2025, 1, 2),
                source="google",
                medium="organic",
                # Missing country
            ),
        ]

        journey = CustomerJourney(
            customer_id="test_customer",
            first_touch=datetime(2025, 1, 1),
            last_touch=datetime(2025, 1, 2),
            total_touches=2,
            converted=True,
            conversion_value=50.0,
            attribution_model=AttributionModelType.LINEAR,
        )

        # Should not raise an exception
        result = await engine.calculate_attribution(
            journey, touches, linear_attribution_model
        )

        assert result is not None  # Should complete successfully
        assert len(result.touch_attributions) == 2

        # Should handle missing data gracefully in channel attribution
        assert (
            "unknown" in result.channel_attribution
            or len(result.channel_attribution) >= 1
        )


@pytest.mark.asyncio
class TestAttributionEngineAsync:
    """Async test cases for attribution engine."""

    @pytest.fixture
    def engine_with_ml(self):
        """Create attribution engine with mock ML service."""
        mock_ml_service = Mock()
        mock_ml_service.predict_attribution_weights = AsyncMock(return_value=[0.3, 0.7])
        return AttributionEngine(ml_service=mock_ml_service)

    async def test_data_driven_attribution(
        self, engine_with_ml, sample_customer_journey
    ):
        """Test data-driven attribution using ML service."""
        touches = [
            AttributionTouch(
                customer_journey_id="journey_ml",
                customer_id="test_customer",
                touchpoint_type=TouchpointType.GOOGLE_ADS_CLICK,
                timestamp=datetime(2025, 1, 1),
                source="google",
                medium="cpc",
            ),
            AttributionTouch(
                customer_journey_id="journey_ml",
                customer_id="test_customer",
                touchpoint_type=TouchpointType.DIRECT_VISIT,
                timestamp=datetime(2025, 1, 2),
                source="direct",
                medium="(none)",
                is_conversion_touch=True,
                conversion_value=100.0,
            ),
        ]

        model = AttributionModel(
            model_name="Data Driven",
            model_type=AttributionModelType.DATA_DRIVEN,
            ml_model_path="/path/to/model.pkl",
        )

        # Update journey to match touches
        sample_customer_journey.total_touches = 2
        sample_customer_journey.conversion_value = 100.0

        result = await engine_with_ml.calculate_attribution(
            sample_customer_journey, touches, model
        )

        # Verify ML service was called
        engine_with_ml.ml_service.predict_attribution_weights.assert_called_once()

        # Verify ML weights were applied
        weights = [attr["weight"] for attr in result.touch_attributions]
        assert abs(weights[0] - 0.3) < 0.001  # First touch
        assert abs(weights[1] - 0.7) < 0.001  # Second touch

    async def test_data_driven_fallback(
        self, sample_customer_journey, sample_attribution_touches
    ):
        """Test data-driven attribution fallback when ML service fails."""
        # Engine without ML service
        engine = AttributionEngine()

        model = AttributionModel(
            model_name="Data Driven",
            model_type=AttributionModelType.DATA_DRIVEN,
        )

        result = await engine.calculate_attribution(
            sample_customer_journey, sample_attribution_touches, model
        )

        # Should fallback to time decay model
        assert result.total_attributed_value == 150.0
        weights = [attr["weight"] for attr in result.touch_attributions]
        assert abs(sum(weights) - 1.0) < 0.001  # Weights should sum to 1.0
