"""Tests for Geographic Optimization Google Ads Scripts."""

from unittest.mock import Mock, patch

import pytest

from paidsearchnav_mcp.platforms.google.scripts.base import (
    ScriptConfig,
    ScriptStatus,
)
from paidsearchnav_mcp.platforms.google.scripts.geographic_optimization import (
    GeographicActionType,
    GeographicOptimizationEngine,
    GeographicRecommendation,
    OptimizationPriority,
    RadiusPerformanceSegment,
    StoreCompetitiveAnalysis,
    create_geographic_optimization_config,
)
from paidsearchnav_mcp.platforms.google.scripts.local_intent_optimization import (
    GeographicPerformanceMetric,
    StoreLocation,
)


class TestGeographicOptimizationEngine:
    """Test suite for GeographicOptimizationEngine."""

    @pytest.fixture
    def sample_store_locations(self):
        """Sample store locations with enhanced data for testing."""
        return [
            {
                "store_id": "store_001",
                "name": "Fitness Connection Red Bird",
                "city": "Dallas",
                "state": "TX",
                "latitude": 32.7767,
                "longitude": -96.7970,
                "radius_miles": 25,
                "landing_page": "https://fitnessconnection.com/gyms/red-bird-lane",
                "store_type": "fitness_center",
                "market_tier": "primary",
                "competitor_density": "high",
                "seasonality_index": 1.2,
            },
            {
                "store_id": "store_002",
                "name": "Fitness Connection Blanco West",
                "city": "San Antonio",
                "state": "TX",
                "latitude": 29.4241,
                "longitude": -98.4936,
                "radius_miles": 20,
                "landing_page": "https://fitnessconnection.com/gyms/blanco-west",
                "store_type": "fitness_center",
                "market_tier": "secondary",
                "competitor_density": "medium",
                "seasonality_index": 1.0,
            },
        ]

    @pytest.fixture
    def geographic_optimization_config(self, sample_store_locations):
        """Create test configuration for geographic optimization."""
        return create_geographic_optimization_config(
            store_locations=sample_store_locations,
            lookback_days=30,
            min_impressions=100,
        )

    @pytest.fixture
    def mock_client(self):
        """Mock Google Ads client."""
        return Mock()

    @pytest.fixture
    def geo_engine(self, mock_client, geographic_optimization_config):
        """Create GeographicOptimizationEngine instance for testing."""
        engine = GeographicOptimizationEngine(
            mock_client, geographic_optimization_config
        )
        # Set up store locations from config
        engine.store_locations = [
            StoreLocation(**store)
            for store in geographic_optimization_config.parameters["store_locations"]
        ]
        return engine

    def test_geo_engine_initialization(self, geo_engine):
        """Test proper initialization of GeographicOptimizationEngine."""
        assert len(geo_engine.store_locations) == 2
        assert isinstance(geo_engine.excluded_locations, set)
        assert isinstance(geo_engine.competitor_data, dict)

    def test_generate_script_content(self, geo_engine):
        """Test generation of Google Ads Script content."""
        script_content = geo_engine.generate_script()

        # Should contain main function
        assert "function main()" in script_content

        # Should contain store data
        assert "STORE_DATA" in script_content
        assert "Red Bird" in script_content
        assert "Blanco West" in script_content

        # Should contain key analysis functions
        assert "analyzeRadiusPerformance" in script_content
        assert "generateGeographicBidAdjustments" in script_content
        assert "identifyLocationExclusions" in script_content
        assert "analyzeStorePerformance" in script_content

        # Should contain configuration
        assert "CONFIG" in script_content
        assert "LOOKBACK_DAYS" in script_content
        assert "MIN_IMPRESSIONS" in script_content

    def test_analyze_radius_performance(self, geo_engine):
        """Test radius performance analysis."""
        store = geo_engine.store_locations[0]
        radius_segments = [(0, 5), (5, 10), (10, 15), (15, 25), (25, 50)]

        segments = geo_engine.analyze_radius_performance(store, radius_segments)

        assert len(segments) == len(radius_segments)

        for segment in segments:
            assert isinstance(segment, RadiusPerformanceSegment)
            assert segment.impressions > 0
            assert segment.clicks > 0
            assert segment.efficiency_score > 0
            assert -50 <= segment.recommended_bid_adjustment <= 50

    def test_efficiency_score_calculation(self, geo_engine):
        """Test efficiency score calculation for radius segments."""
        # Closer segments should have higher efficiency
        close_efficiency = geo_engine._calculate_efficiency_score(0, 5)
        medium_efficiency = geo_engine._calculate_efficiency_score(10, 15)
        far_efficiency = geo_engine._calculate_efficiency_score(25, 50)

        assert close_efficiency > medium_efficiency
        assert medium_efficiency > far_efficiency
        assert 0.0 <= close_efficiency <= 1.0
        assert 0.0 <= far_efficiency <= 1.0

    def test_radius_bid_adjustment_calculation(self, geo_engine):
        """Test bid adjustment calculation for radius segments."""
        # Closer segments should have higher bid adjustments
        close_adjustment = geo_engine._calculate_radius_bid_adjustment(0, 5)
        medium_adjustment = geo_engine._calculate_radius_bid_adjustment(10, 15)
        far_adjustment = geo_engine._calculate_radius_bid_adjustment(30, 40)

        assert close_adjustment > medium_adjustment
        assert medium_adjustment > far_adjustment
        assert close_adjustment > 0  # Should be positive
        assert far_adjustment < 0  # Should be negative

    def test_geographic_recommendations_generation(self, geo_engine):
        """Test generation of geographic recommendations."""
        recommendations = geo_engine.generate_geographic_recommendations(
            geo_engine.store_locations
        )

        assert isinstance(recommendations, list)

        for recommendation in recommendations:
            assert isinstance(recommendation, GeographicRecommendation)
            assert recommendation.action_type in GeographicActionType
            assert recommendation.priority in OptimizationPriority
            assert recommendation.confidence_score > 0.0
            assert len(recommendation.reasoning) > 0

    def test_process_results_success(self, geo_engine):
        """Test processing of successful geographic optimization results."""
        mock_results = {
            "radiusOptimizations": [
                {
                    "storeId": "store_001",
                    "currentRadius": 25,
                    "recommendedRadius": 20,
                    "expectedImpact": {"costReduction": 15.0},
                },
                {
                    "storeId": "store_002",
                    "currentRadius": 20,
                    "recommendedRadius": 15,
                    "expectedImpact": {"costReduction": 10.0},
                },
            ],
            "bidAdjustments": [
                {
                    "locationId": "dallas_tx",
                    "priority": "high",
                    "recommendedBidAdjustment": 25.0,
                },
                {
                    "locationId": "san_antonio_tx",
                    "priority": "medium",
                    "recommendedBidAdjustment": 15.0,
                },
            ],
            "locationExclusions": [
                {
                    "locationId": "austin_tx",
                    "potentialSavings": 150.0,
                },
            ],
            "storePerformanceAnalysis": [
                {
                    "storeId": "store_001",
                    "overallScore": 0.85,
                },
                {
                    "storeId": "store_002",
                    "overallScore": 0.55,  # Poor performance
                },
            ],
            "competitiveInsights": [
                {"storeId": "store_001"},
            ],
            "seasonalAdjustments": [
                {"locationId": "dallas_tx"},
                {"locationId": "san_antonio_tx"},
            ],
            "crossLocationAnalysis": [
                {
                    "severity": "critical",
                    "cannibalizationRisk": "high",
                },
            ],
        }

        result = geo_engine.process_results(mock_results)

        assert result["status"] == ScriptStatus.COMPLETED.value
        assert result["rows_processed"] == 4  # store_analysis + bid_adjustments
        assert result["changes_made"] == 5  # Total optimizations
        assert len(result["errors"]) == 0

        # Should have warnings for critical issues
        assert len(result["warnings"]) >= 2

        # Check detailed analysis
        details = result["details"]
        assert "geographic_optimization" in details
        assert "bid_optimization" in details
        assert "location_management" in details
        assert "competitive_analysis" in details
        assert "temporal_optimization" in details
        assert "cross_location_analysis" in details

        # Check specific metrics
        assert details["geographic_optimization"]["stores_analyzed"] == 2
        assert details["bid_optimization"]["total_bid_adjustments"] == 2
        assert details["location_management"]["exclusion_candidates"] == 1
        assert details["cross_location_analysis"]["potential_conflicts"] == 1

    def test_process_results_with_warnings(self, geo_engine):
        """Test processing results that generate various warnings."""
        mock_results = {
            "radiusOptimizations": [],
            "bidAdjustments": [],
            "locationExclusions": [
                {"potentialSavings": 600.0},  # High-cost exclusion
                {"potentialSavings": 750.0},  # High-cost exclusion
            ],
            "storePerformanceAnalysis": [
                {"overallScore": 0.4},  # Poor performance
                {"overallScore": 0.3},  # Poor performance
            ],
            "competitiveInsights": [],
            "seasonalAdjustments": [],
            "crossLocationAnalysis": [
                {"severity": "critical", "cannibalizationRisk": "critical"},
                {"severity": "high", "cannibalizationRisk": "high"},
            ],
        }

        result = geo_engine.process_results(mock_results)

        assert result["status"] == ScriptStatus.COMPLETED.value
        assert len(result["warnings"]) == 3  # All three warning types should trigger

        # Check specific warnings
        warnings_text = " ".join(result["warnings"])
        assert "critical cross-location conflicts" in warnings_text
        assert "cost savings potential" in warnings_text
        assert "poor performance metrics" in warnings_text

    def test_required_parameters(self, geo_engine):
        """Test that required parameters are properly defined."""
        required_params = geo_engine.get_required_parameters()

        assert "store_locations" in required_params
        assert "lookback_days" in required_params
        assert "min_impressions" in required_params

    def test_create_geographic_optimization_config(self, sample_store_locations):
        """Test creation of geographic optimization configuration."""
        config = create_geographic_optimization_config(
            store_locations=sample_store_locations,
            lookback_days=45,
            min_impressions=150,
        )

        assert isinstance(config, ScriptConfig)
        assert "Geographic Optimization" in config.name
        assert config.parameters["lookback_days"] == 45
        assert config.parameters["min_impressions"] == 150
        assert config.parameters["store_locations"] == sample_store_locations

        # Check default parameters
        assert config.parameters["min_bid_adjustment"] == 5
        assert config.parameters["max_bid_adjustment"] == 50
        assert config.parameters["efficiency_threshold"] == 0.7

    def test_geographic_action_type_enum(self):
        """Test GeographicActionType enum values."""
        assert GeographicActionType.BID_ADJUSTMENT.value == "bid_adjustment"
        assert GeographicActionType.LOCATION_EXCLUSION.value == "location_exclusion"
        assert GeographicActionType.RADIUS_OPTIMIZATION.value == "radius_optimization"
        assert GeographicActionType.DAYPART_ADJUSTMENT.value == "daypart_adjustment"
        assert (
            GeographicActionType.DEMOGRAPHIC_TARGETING.value == "demographic_targeting"
        )

    def test_optimization_priority_enum(self):
        """Test OptimizationPriority enum values."""
        assert OptimizationPriority.LOW.value == "low"
        assert OptimizationPriority.MEDIUM.value == "medium"
        assert OptimizationPriority.HIGH.value == "high"
        assert OptimizationPriority.CRITICAL.value == "critical"

    def test_error_handling_in_processing(self, geo_engine):
        """Test error handling in results processing."""
        # Test with malformed results
        invalid_results = {"invalid": "data", "structure": None}

        result = geo_engine.process_results(invalid_results)

        # Should handle gracefully
        assert result["status"] == ScriptStatus.COMPLETED.value
        assert result["rows_processed"] == 0
        assert result["changes_made"] == 0

    @patch("paidsearchnav.platforms.google.scripts.geographic_optimization.logger")
    def test_exception_handling(self, mock_logger, geo_engine):
        """Test exception handling in results processing."""
        # Force an exception
        with patch.object(
            geo_engine,
            "_calculate_efficiency_score",
            side_effect=Exception("Test error"),
        ):
            result = geo_engine.process_results(
                {"storePerformanceAnalysis": [{"error": "test"}]}
            )

            # Should log error and return failure
            assert result["status"] == ScriptStatus.FAILED.value
            assert len(result["errors"]) > 0
            mock_logger.error.assert_called()


class TestGeographicDataStructures:
    """Test data structures used in geographic optimization."""

    def test_geographic_recommendation_dataclass(self):
        """Test GeographicRecommendation dataclass."""
        performance_metric = GeographicPerformanceMetric(
            location="Dallas, TX",
            radius_miles=25,
            impressions=1000,
            clicks=50,
            conversions=5,
            cost=125.0,
        )

        recommendation = GeographicRecommendation(
            action_type=GeographicActionType.BID_ADJUSTMENT,
            priority=OptimizationPriority.HIGH,
            location_identifier="dallas_tx",
            current_performance=performance_metric,
            recommended_change={"bid_adjustment": 15.0},
            expected_impact={"cost_reduction": 10.0, "conversion_increase": 20.0},
            confidence_score=0.85,
            reasoning="High-performing location needs bid increase",
        )

        assert recommendation.action_type == GeographicActionType.BID_ADJUSTMENT
        assert recommendation.priority == OptimizationPriority.HIGH
        assert recommendation.confidence_score == 0.85
        assert "bid_adjustment" in recommendation.recommended_change
        assert len(recommendation.reasoning) > 0

    def test_radius_performance_segment_dataclass(self):
        """Test RadiusPerformanceSegment dataclass."""
        segment = RadiusPerformanceSegment(
            radius_start=0,
            radius_end=5,
            impressions=500,
            clicks=25,
            conversions=3,
            cost=75.0,
            store_visits=5,
            efficiency_score=0.9,
            recommended_bid_adjustment=20.0,
        )

        assert segment.radius_start == 0
        assert segment.radius_end == 5
        assert segment.efficiency_score == 0.9
        assert segment.recommended_bid_adjustment == 20.0

    def test_store_competitive_analysis_dataclass(self):
        """Test StoreCompetitiveAnalysis dataclass."""
        analysis = StoreCompetitiveAnalysis(
            store_id="store_001",
            market_share_estimate=0.15,
            competitor_density=5,
            local_search_volume=10000,
            seasonal_trends={"Q1": 0.8, "Q2": 1.2, "Q3": 1.1, "Q4": 0.9},
            opportunity_score=0.75,
            threat_level="medium",
        )

        assert analysis.store_id == "store_001"
        assert analysis.market_share_estimate == 0.15
        assert analysis.opportunity_score == 0.75
        assert "Q1" in analysis.seasonal_trends
        assert analysis.threat_level == "medium"


class TestGeographicOptimizationIntegration:
    """Integration tests for geographic optimization functionality."""

    @pytest.fixture
    def sample_performance_data(self):
        """Sample performance data for integration testing."""
        return {
            "location_performance": {
                "dallas_tx": {
                    "impressions": 5000,
                    "clicks": 250,
                    "conversions": 25,
                    "cost": 625.0,
                    "ctr": 5.0,
                    "cpc": 2.50,
                    "conversion_rate": 10.0,
                },
                "san_antonio_tx": {
                    "impressions": 3000,
                    "clicks": 120,
                    "conversions": 8,
                    "cost": 360.0,
                    "ctr": 4.0,
                    "cpc": 3.00,
                    "conversion_rate": 6.67,
                },
            },
            "radius_performance": {
                "0-5": {"efficiency": 0.9, "cost_per_conversion": 20.0},
                "5-10": {"efficiency": 0.8, "cost_per_conversion": 25.0},
                "10-15": {"efficiency": 0.7, "cost_per_conversion": 30.0},
                "15-25": {"efficiency": 0.6, "cost_per_conversion": 40.0},
                "25+": {"efficiency": 0.4, "cost_per_conversion": 60.0},
            },
        }

    def test_comprehensive_analysis_workflow(self, geo_engine, sample_performance_data):
        """Test comprehensive geographic analysis workflow."""
        # Test radius optimization
        store = geo_engine.store_locations[0]
        radius_segments = [(0, 5), (5, 10), (10, 15), (15, 25)]

        segments = geo_engine.analyze_radius_performance(store, radius_segments)
        assert len(segments) > 0

        # Test recommendations generation
        recommendations = geo_engine.generate_geographic_recommendations([store])
        assert len(recommendations) > 0

        # Test that recommendations are actionable
        for recommendation in recommendations:
            assert recommendation.confidence_score > 0.5
            assert len(recommendation.reasoning) > 10
            assert recommendation.action_type in GeographicActionType

    def test_multi_store_optimization(self, geo_engine):
        """Test optimization across multiple stores."""
        stores = geo_engine.store_locations
        assert len(stores) >= 2

        # Generate recommendations for all stores
        recommendations = geo_engine.generate_geographic_recommendations(stores)

        # Should have recommendations for multiple stores
        store_ids = {rec.location_identifier for rec in recommendations}
        assert len(store_ids) > 0

        # Recommendations should vary by store characteristics
        priority_counts = {}
        for rec in recommendations:
            priority = rec.priority.value
            priority_counts[priority] = priority_counts.get(priority, 0) + 1

        # Should have varied priorities
        assert len(priority_counts) > 1

    def test_performance_threshold_validation(self, geo_engine):
        """Test that performance thresholds are properly applied."""
        # Test efficiency score boundaries
        high_efficiency = geo_engine._calculate_efficiency_score(0, 5)
        low_efficiency = geo_engine._calculate_efficiency_score(40, 50)

        assert high_efficiency >= 0.7  # Should meet high threshold
        assert low_efficiency <= 0.5  # Should be below threshold

        # Test bid adjustment boundaries
        max_positive = geo_engine._calculate_radius_bid_adjustment(0, 5)
        max_negative = geo_engine._calculate_radius_bid_adjustment(40, 50)

        assert max_positive <= 50  # Should not exceed max
        assert max_negative >= -50  # Should not go below min

    def test_cross_location_analysis_prevention(self, geo_engine):
        """Test prevention of cross-location conflicts."""
        # This would test the logic for detecting when stores
        # might compete against each other geographically
        stores = geo_engine.store_locations

        # Test distance calculation between stores
        if len(stores) >= 2:
            store1, store2 = stores[0], stores[1]

            # Calculate distance between stores (simplified)
            lat_diff = abs(store1.latitude - store2.latitude)
            lon_diff = abs(store1.longitude - store2.longitude)
            distance = (lat_diff + lon_diff) * 69  # Rough miles conversion

            # Stores should be far enough apart to avoid conflicts
            assert distance > 10  # At least 10 miles apart

    def test_seasonal_adjustment_integration(self, geo_engine):
        """Test integration with seasonal adjustments."""
        # Test that seasonal factors are considered in recommendations
        store = geo_engine.store_locations[0]
        recommendations = geo_engine.generate_geographic_recommendations([store])

        # Should consider store seasonality index if present
        if hasattr(store, "seasonality_index"):
            seasonal_recs = [
                rec for rec in recommendations if "seasonal" in rec.reasoning.lower()
            ]
            # May or may not have seasonal recommendations, but shouldn't error


if __name__ == "__main__":
    pytest.main([__file__])
