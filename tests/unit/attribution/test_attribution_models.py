"""Tests for attribution data models and validation."""

from datetime import datetime

import pytest
from pydantic import ValidationError

from paidsearchnav_mcp.attribution.models import (
    AttributionInsight,
    AttributionModel,
    AttributionModelType,
    AttributionResult,
    AttributionTouch,
    ConversionType,
    CrossPlatformMetrics,
    CustomerJourney,
    GCLIDMapping,
    MLAttributionModel,
    TouchpointType,
)


class TestAttributionTouch:
    """Test cases for AttributionTouch model."""

    def test_attribution_touch_creation(self):
        """Test creating valid AttributionTouch."""
        touch = AttributionTouch(
            customer_journey_id="journey_123",
            customer_id="customer_123",
            touchpoint_type=TouchpointType.GOOGLE_ADS_CLICK,
            timestamp=datetime(2025, 1, 1, 10, 0, 0),
            gclid="test_gclid",
            campaign_id="campaign_123",
            source="google",
            medium="cpc",
            country="US",
            device_category="mobile",
            attribution_weight=0.5,
            revenue_attributed=75.0,
        )

        assert touch.customer_journey_id == "journey_123"
        assert touch.touchpoint_type == TouchpointType.GOOGLE_ADS_CLICK
        assert touch.attribution_weight == 0.5
        assert touch.revenue_attributed == 75.0
        assert touch.touch_id is not None  # UUID auto-generated
        assert touch.created_at is not None

    def test_attribution_weight_validation(self):
        """Test attribution weight validation (0.0-1.0 range)."""
        # Valid weight
        touch = AttributionTouch(
            customer_journey_id="journey_123",
            customer_id="customer_123",
            touchpoint_type=TouchpointType.GA4_SESSION,
            timestamp=datetime(2025, 1, 1),
            attribution_weight=0.8,
        )
        assert touch.attribution_weight == 0.8

        # Invalid weights should raise validation error
        with pytest.raises(ValidationError):
            AttributionTouch(
                customer_journey_id="journey_123",
                customer_id="customer_123",
                touchpoint_type=TouchpointType.GA4_SESSION,
                timestamp=datetime(2025, 1, 1),
                attribution_weight=1.5,  # > 1.0
            )

        with pytest.raises(ValidationError):
            AttributionTouch(
                customer_journey_id="journey_123",
                customer_id="customer_123",
                touchpoint_type=TouchpointType.GA4_SESSION,
                timestamp=datetime(2025, 1, 1),
                attribution_weight=-0.1,  # < 0.0
            )

    def test_conversion_touch_validation(self):
        """Test conversion touch fields validation."""
        # Valid conversion touch
        touch = AttributionTouch(
            customer_journey_id="journey_123",
            customer_id="customer_123",
            touchpoint_type=TouchpointType.DIRECT_VISIT,
            timestamp=datetime(2025, 1, 1),
            is_conversion_touch=True,
            conversion_type=ConversionType.PURCHASE,
            conversion_value=100.0,
        )

        assert touch.is_conversion_touch is True
        assert touch.conversion_type == ConversionType.PURCHASE
        assert touch.conversion_value == 100.0

        # Invalid conversion value
        with pytest.raises(ValidationError):
            AttributionTouch(
                customer_journey_id="journey_123",
                customer_id="customer_123",
                touchpoint_type=TouchpointType.DIRECT_VISIT,
                timestamp=datetime(2025, 1, 1),
                conversion_value=-10.0,  # Negative value
            )


class TestCustomerJourney:
    """Test cases for CustomerJourney model."""

    def test_customer_journey_creation(self):
        """Test creating valid CustomerJourney."""
        journey = CustomerJourney(
            customer_id="customer_123",
            first_touch=datetime(2025, 1, 1, 10, 0, 0),
            last_touch=datetime(2025, 1, 3, 15, 0, 0),
            conversion_timestamp=datetime(2025, 1, 3, 15, 0, 0),
            total_touches=5,
            converted=True,
            conversion_value=250.0,
            attribution_model=AttributionModelType.LINEAR,
            is_multi_session=True,
            is_multi_device=True,
            first_touch_source="google",
            first_touch_medium="cpc",
            last_touch_source="direct",
            last_touch_medium="(none)",
        )

        assert journey.customer_id == "customer_123"
        assert journey.total_touches == 5
        assert journey.converted is True
        assert journey.journey_id is not None  # UUID auto-generated

        # Journey length should be auto-calculated
        expected_length = (
            datetime(2025, 1, 3, 15, 0, 0) - datetime(2025, 1, 1, 10, 0, 0)
        ).total_seconds() / 86400
        assert abs(journey.journey_length_days - expected_length) < 0.001

    def test_journey_length_calculation(self):
        """Test automatic journey length calculation."""
        journey = CustomerJourney(
            customer_id="customer_123",
            first_touch=datetime(2025, 1, 1, 12, 0, 0),
            last_touch=datetime(2025, 1, 2, 12, 0, 0),  # Exactly 24 hours later
            total_touches=2,
            attribution_model=AttributionModelType.LINEAR,
        )

        assert journey.journey_length_days == 1.0

    def test_journey_validation(self):
        """Test CustomerJourney field validation."""
        # Valid journey
        journey = CustomerJourney(
            customer_id="customer_123",
            first_touch=datetime(2025, 1, 1),
            last_touch=datetime(2025, 1, 2),
            total_touches=3,
            attribution_model=AttributionModelType.TIME_DECAY,
            conversion_value=100.0,
        )
        assert journey.conversion_value == 100.0

        # Invalid conversion value
        with pytest.raises(ValidationError):
            CustomerJourney(
                customer_id="customer_123",
                first_touch=datetime(2025, 1, 1),
                last_touch=datetime(2025, 1, 2),
                total_touches=2,
                attribution_model=AttributionModelType.LINEAR,
                conversion_value=-50.0,  # Negative value
            )


class TestAttributionModel:
    """Test cases for AttributionModel configuration."""

    def test_attribution_model_creation(self):
        """Test creating attribution model configurations."""
        model = AttributionModel(
            model_name="Test Time Decay",
            model_type=AttributionModelType.TIME_DECAY,
            time_decay_half_life_days=14.0,
            max_journey_length_days=60,
            require_conversion=True,
        )

        assert model.model_name == "Test Time Decay"
        assert model.model_type == AttributionModelType.TIME_DECAY
        assert model.time_decay_half_life_days == 14.0
        assert model.max_journey_length_days == 60
        assert model.model_id is not None

    def test_position_based_weight_validation(self):
        """Test position-based model weight validation."""
        # Valid weights that sum to less than 1.0
        model = AttributionModel(
            model_name="Position Based",
            model_type=AttributionModelType.POSITION_BASED,
            position_based_first_weight=0.3,
            position_based_last_weight=0.4,
        )
        assert model.position_based_first_weight == 0.3
        assert model.position_based_last_weight == 0.4

        # Invalid weights that sum to more than 1.0
        with pytest.raises(ValidationError):
            AttributionModel(
                model_name="Invalid Position Based",
                model_type=AttributionModelType.POSITION_BASED,
                position_based_first_weight=0.6,
                position_based_last_weight=0.6,  # 0.6 + 0.6 = 1.2 > 1.0
            )

    def test_custom_weights_model(self):
        """Test custom attribution model with touchpoint weights."""
        custom_weights = {
            TouchpointType.GOOGLE_ADS_CLICK: 0.5,
            TouchpointType.GA4_SESSION: 0.3,
            TouchpointType.DIRECT_VISIT: 0.2,
        }

        model = AttributionModel(
            model_name="Custom Model",
            model_type=AttributionModelType.CUSTOM,
            custom_weights=custom_weights,
        )

        assert model.custom_weights == custom_weights
        assert TouchpointType.GOOGLE_ADS_CLICK in model.custom_weights

    def test_data_driven_model_config(self):
        """Test data-driven model configuration."""
        model = AttributionModel(
            model_name="ML Attribution",
            model_type=AttributionModelType.DATA_DRIVEN,
            ml_model_path="/models/attribution_model.pkl",
            confidence_threshold=0.8,
            feature_importance_weights={
                "touchpoint_position": 0.3,
                "time_decay": 0.25,
                "channel_type": 0.25,
                "engagement_signals": 0.2,
            },
        )

        assert model.ml_model_path == "/models/attribution_model.pkl"
        assert model.confidence_threshold == 0.8
        assert len(model.feature_importance_weights) == 4


class TestGCLIDMapping:
    """Test cases for GCLIDMapping model."""

    def test_gclid_mapping_creation(self):
        """Test creating GCLID mapping between Google Ads and GA4."""
        mapping = GCLIDMapping(
            gclid="test_gclid_123",
            google_ads_click_timestamp=datetime(2025, 1, 1, 10, 0, 0),
            campaign_id="campaign_123",
            campaign_name="Test Campaign",
            ad_group_id="adgroup_123",
            click_cost=2.50,
            ga4_session_id="session_456",
            ga4_user_id="user_789",
            session_start_timestamp=datetime(2025, 1, 1, 10, 1, 30),
            landing_page="https://example.com/landing",
            match_confidence=0.95,
            time_diff_seconds=90,  # 1.5 minutes
            session_converted=True,
            conversion_value=150.0,
            attribution_weight=1.0,
        )

        assert mapping.gclid == "test_gclid_123"
        assert mapping.match_confidence == 0.95
        assert mapping.time_diff_seconds == 90
        assert mapping.session_converted is True
        assert mapping.mapping_id is not None

    def test_match_confidence_validation(self):
        """Test match confidence score validation."""
        # Valid confidence scores
        for confidence in [0.0, 0.5, 0.99, 1.0]:
            mapping = GCLIDMapping(
                gclid="test_gclid",
                google_ads_click_timestamp=datetime(2025, 1, 1),
                campaign_id="campaign_123",
                campaign_name="Campaign",
                ad_group_id="adgroup_123",
                click_cost=1.0,
                match_confidence=confidence,
                session_converted=False,
                conversion_value=0.0,
                attribution_weight=1.0,
            )
            assert mapping.match_confidence == confidence

        # Invalid confidence scores
        with pytest.raises(ValidationError):
            GCLIDMapping(
                gclid="test_gclid",
                google_ads_click_timestamp=datetime(2025, 1, 1),
                campaign_id="campaign_123",
                campaign_name="Campaign",
                ad_group_id="adgroup_123",
                click_cost=1.0,
                match_confidence=1.5,  # > 1.0
                session_converted=False,
                conversion_value=0.0,
                attribution_weight=1.0,
            )


class TestAttributionResult:
    """Test cases for AttributionResult model."""

    def test_attribution_result_creation(self):
        """Test creating attribution analysis result."""
        result = AttributionResult(
            customer_journey_id="journey_123",
            customer_id="customer_123",
            attribution_model_id="model_456",
            total_conversion_value=200.0,
            total_attributed_value=200.0,
            attribution_confidence=0.85,
            touch_attributions=[
                {
                    "touch_id": "touch_1",
                    "weight": 0.4,
                    "attributed_revenue": 80.0,
                    "touchpoint_type": "google_ads_click",
                },
                {
                    "touch_id": "touch_2",
                    "weight": 0.6,
                    "attributed_revenue": 120.0,
                    "touchpoint_type": "direct_visit",
                },
            ],
            channel_attribution={
                "google/cpc": 80.0,
                "direct/(none)": 120.0,
            },
        )

        assert result.total_conversion_value == 200.0
        assert result.attribution_confidence == 0.85
        assert len(result.touch_attributions) == 2
        assert result.channel_attribution["google/cpc"] == 80.0
        assert result.result_id is not None

    def test_confidence_score_validation(self):
        """Test attribution confidence score validation."""
        # Valid confidence scores
        result = AttributionResult(
            customer_journey_id="journey_123",
            customer_id="customer_123",
            attribution_model_id="model_456",
            attribution_confidence=0.75,
        )
        assert result.attribution_confidence == 0.75

        # Invalid confidence scores
        with pytest.raises(ValidationError):
            AttributionResult(
                customer_journey_id="journey_123",
                customer_id="customer_123",
                attribution_model_id="model_456",
                attribution_confidence=1.2,  # > 1.0
            )


class TestMLAttributionModel:
    """Test cases for MLAttributionModel metadata."""

    def test_ml_model_creation(self):
        """Test creating ML attribution model metadata."""
        model = MLAttributionModel(
            customer_id="customer_123",
            model_name="XGBoost Attribution Model",
            model_type="xgboost",
            training_start_date=datetime(2025, 1, 1),
            training_end_date=datetime(2025, 1, 31),
            training_sample_size=1000,
            validation_sample_size=200,
            feature_columns=[
                "journey_length_days",
                "total_touches",
                "first_touch_source",
                "device_count",
            ],
            target_column="conversion_value",
            accuracy_score=0.85,
            precision_score=0.82,
            recall_score=0.88,
            f1_score=0.85,
            status="active",
            model_file_path="/models/attribution_customer_123.pkl",
        )

        assert model.customer_id == "customer_123"
        assert model.model_type == "xgboost"
        assert model.training_sample_size == 1000
        assert model.accuracy_score == 0.85
        assert model.status == "active"
        assert model.model_id is not None

    def test_ml_model_performance_validation(self):
        """Test ML model performance score validation."""
        # Valid performance scores (0.0-1.0)
        model = MLAttributionModel(
            customer_id="customer_123",
            model_name="Test Model",
            training_start_date=datetime(2025, 1, 1),
            training_end_date=datetime(2025, 1, 2),
            accuracy_score=0.92,
            precision_score=0.89,
            recall_score=0.95,
        )

        assert model.accuracy_score == 0.92
        assert model.precision_score == 0.89
        assert model.recall_score == 0.95

        # Invalid performance scores
        with pytest.raises(ValidationError):
            MLAttributionModel(
                customer_id="customer_123",
                model_name="Invalid Model",
                training_start_date=datetime(2025, 1, 1),
                training_end_date=datetime(2025, 1, 2),
                accuracy_score=1.2,  # > 1.0
            )

    def test_retrain_configuration(self):
        """Test model retraining configuration."""
        model = MLAttributionModel(
            customer_id="customer_123",
            model_name="Retraining Model",
            training_start_date=datetime(2025, 1, 1),
            training_end_date=datetime(2025, 1, 2),
            retrain_frequency_days=14,
            auto_retrain_enabled=True,
            performance_threshold=0.8,
        )

        assert model.retrain_frequency_days == 14
        assert model.auto_retrain_enabled is True
        assert model.performance_threshold == 0.8


class TestAttributionInsight:
    """Test cases for AttributionInsight model."""

    def test_attribution_insight_creation(self):
        """Test creating attribution insights."""
        insight = AttributionInsight(
            customer_id="customer_123",
            analysis_period_start=datetime(2025, 1, 1),
            analysis_period_end=datetime(2025, 1, 31),
            insight_type="underperforming_channel",
            priority="high",
            confidence=0.85,
            title="Google Organic Underperforming",
            description="Google organic traffic showing 30% lower LTV than expected",
            impact_description="Optimizing organic could increase LTV by $25 per customer",
            supporting_data={
                "channel": "google/organic",
                "current_ltv": 75.0,
                "expected_ltv": 100.0,
                "sample_size": 150,
            },
            recommended_actions=[
                "Review SEO strategy for key landing pages",
                "Optimize meta descriptions for higher CTR",
                "Improve page load speed for organic traffic",
            ],
            projected_revenue_impact=3750.0,  # 150 customers * $25
            implementation_effort="medium",
        )

        assert insight.insight_type == "underperforming_channel"
        assert insight.priority == "high"
        assert insight.confidence == 0.85
        assert len(insight.recommended_actions) == 3
        assert insight.projected_revenue_impact == 3750.0
        assert insight.insight_id is not None

    def test_insight_confidence_validation(self):
        """Test insight confidence validation."""
        # Valid confidence
        insight = AttributionInsight(
            customer_id="customer_123",
            analysis_period_start=datetime(2025, 1, 1),
            analysis_period_end=datetime(2025, 1, 2),
            insight_type="test_insight",
            title="Test Insight",
            description="Test description",
            confidence=0.7,
        )
        assert insight.confidence == 0.7

        # Invalid confidence
        with pytest.raises(ValidationError):
            AttributionInsight(
                customer_id="customer_123",
                analysis_period_start=datetime(2025, 1, 1),
                analysis_period_end=datetime(2025, 1, 2),
                insight_type="test_insight",
                title="Test Insight",
                description="Test description",
                confidence=1.5,  # > 1.0
            )


class TestCrossPlatformMetrics:
    """Test cases for CrossPlatformMetrics model."""

    def test_cross_platform_metrics_creation(self):
        """Test creating cross-platform performance metrics."""
        metrics = CrossPlatformMetrics(
            customer_id="customer_123",
            date=datetime(2025, 1, 1),
            google_ads_clicks=1500,
            google_ads_impressions=50000,
            google_ads_cost=3750.0,
            google_ads_conversions=45.0,
            google_ads_conversion_value=6750.0,
            ga4_sessions=1800,
            ga4_users=1200,
            ga4_pageviews=5400,
            ga4_bounce_rate=0.35,
            ga4_conversion_rate=0.025,
            ga4_revenue=7200.0,
            attributed_revenue_google_ads=5400.0,
            attributed_revenue_organic=1200.0,
            attributed_revenue_direct=600.0,
            gclid_match_rate=0.82,
            cross_platform_roas=1.8,
            multi_touch_journeys_count=32,
            single_touch_journeys_count=13,
            avg_journey_length_days=2.5,
            avg_touches_per_journey=3.2,
        )

        assert metrics.customer_id == "customer_123"
        assert metrics.google_ads_clicks == 1500
        assert metrics.gclid_match_rate == 0.82
        assert metrics.cross_platform_roas == 1.8
        assert metrics.multi_touch_journeys_count == 32
        assert metrics.metrics_id is not None

    def test_metrics_validation(self):
        """Test cross-platform metrics field validation."""
        # Valid metrics
        metrics = CrossPlatformMetrics(
            customer_id="customer_123",
            date=datetime(2025, 1, 1),
            ga4_bounce_rate=0.45,  # Valid bounce rate
            gclid_match_rate=0.75,  # Valid match rate
        )
        assert metrics.ga4_bounce_rate == 0.45
        assert metrics.gclid_match_rate == 0.75

        # Invalid bounce rate (> 1.0)
        with pytest.raises(ValidationError):
            CrossPlatformMetrics(
                customer_id="customer_123",
                date=datetime(2025, 1, 1),
                ga4_bounce_rate=1.2,  # > 1.0
            )

        # Invalid match rate (< 0.0)
        with pytest.raises(ValidationError):
            CrossPlatformMetrics(
                customer_id="customer_123",
                date=datetime(2025, 1, 1),
                gclid_match_rate=-0.1,  # < 0.0
            )

    def test_negative_value_validation(self):
        """Test validation of fields that must be non-negative."""
        # Valid non-negative values
        metrics = CrossPlatformMetrics(
            customer_id="customer_123",
            date=datetime(2025, 1, 1),
            google_ads_cost=0.0,  # Zero is valid
            attributed_revenue_google_ads=1000.0,
        )
        assert metrics.google_ads_cost == 0.0
        assert metrics.attributed_revenue_google_ads == 1000.0

        # Invalid negative values
        with pytest.raises(ValidationError):
            CrossPlatformMetrics(
                customer_id="customer_123",
                date=datetime(2025, 1, 1),
                google_ads_cost=-100.0,  # Negative cost
            )

        with pytest.raises(ValidationError):
            CrossPlatformMetrics(
                customer_id="customer_123",
                date=datetime(2025, 1, 1),
                attributed_revenue_google_ads=-50.0,  # Negative revenue
            )


class TestModelIntegration:
    """Integration tests for model interactions."""

    def test_journey_with_attribution_result(self):
        """Test creating journey and attribution result together."""
        # Create journey
        journey = CustomerJourney(
            customer_id="integration_customer",
            first_touch=datetime(2025, 1, 1),
            last_touch=datetime(2025, 1, 3),
            total_touches=3,
            converted=True,
            conversion_value=300.0,
            attribution_model=AttributionModelType.TIME_DECAY,
        )

        # Create corresponding attribution result
        result = AttributionResult(
            customer_journey_id=journey.journey_id,
            customer_id=journey.customer_id,
            attribution_model_id="time_decay_model",
            total_conversion_value=journey.conversion_value,
            total_attributed_value=journey.conversion_value,
            attribution_confidence=0.8,
        )

        # Verify consistency
        assert result.customer_journey_id == journey.journey_id
        assert result.customer_id == journey.customer_id
        assert result.total_conversion_value == journey.conversion_value

    def test_ml_model_with_insights(self):
        """Test ML model generating insights."""
        # Create ML model
        ml_model = MLAttributionModel(
            customer_id="insight_customer",
            model_name="Insight Generator",
            training_start_date=datetime(2025, 1, 1),
            training_end_date=datetime(2025, 1, 31),
            feature_columns=["journey_length", "touch_count"],
            accuracy_score=0.88,
            status="active",
        )

        # Create related insight
        insight = AttributionInsight(
            customer_id=ml_model.customer_id,
            analysis_period_start=ml_model.training_start_date,
            analysis_period_end=ml_model.training_end_date,
            insight_type="model_performance",
            title="High-Performing Attribution Model",
            description=f"Model {ml_model.model_name} achieving {ml_model.accuracy_score:.1%} accuracy",
            confidence=ml_model.accuracy_score,
        )

        # Verify relationship
        assert insight.customer_id == ml_model.customer_id
        assert insight.confidence == ml_model.accuracy_score
