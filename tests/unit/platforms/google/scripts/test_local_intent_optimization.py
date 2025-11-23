"""Tests for Local Intent Optimization Google Ads Scripts."""

from unittest.mock import Mock, patch

import pytest

from paidsearchnav_mcp.platforms.google.scripts.base import (
    ScriptConfig,
    ScriptStatus,
)
from paidsearchnav_mcp.platforms.google.scripts.local_intent_optimization import (
    GeographicPerformanceMetric,
    LocalIntentDetectionEngine,
    LocalIntentMatch,
    LocalIntentType,
    StoreLocation,
    create_local_intent_config,
)


class TestLocalIntentDetectionEngine:
    """Test suite for LocalIntentDetectionEngine."""

    @pytest.fixture
    def sample_store_locations(self):
        """Sample store locations for testing."""
        return [
            {
                "store_id": "store_001",
                "name": "Fitness Connection Red Bird",
                "address": "123 Red Bird Lane",
                "city": "Dallas",
                "state": "TX",
                "zip_code": "75232",
                "latitude": 32.7767,
                "longitude": -96.7970,
                "radius_miles": 25,
                "landing_page": "https://fitnessconnection.com/gyms/red-bird-lane",
            },
            {
                "store_id": "store_002",
                "name": "Fitness Connection Blanco West",
                "address": "456 Blanco Rd",
                "city": "San Antonio",
                "state": "TX",
                "zip_code": "78216",
                "latitude": 29.4241,
                "longitude": -98.4936,
                "radius_miles": 20,
                "landing_page": "https://fitnessconnection.com/gyms/blanco-west",
            },
        ]

    @pytest.fixture
    def local_intent_config(self, sample_store_locations):
        """Create test configuration for local intent optimization."""
        return create_local_intent_config(
            store_locations=sample_store_locations,
            lookback_days=30,
            min_impressions=100,
        )

    @pytest.fixture
    def mock_client(self):
        """Mock Google Ads client."""
        return Mock()

    @pytest.fixture
    def local_intent_engine(self, mock_client, local_intent_config):
        """Create LocalIntentDetectionEngine instance for testing."""
        engine = LocalIntentDetectionEngine(mock_client, local_intent_config)
        # Set up store locations from config
        engine.store_locations = [
            StoreLocation(**store)
            for store in local_intent_config.parameters["store_locations"]
        ]
        return engine

    def test_local_intent_engine_initialization(self, local_intent_engine):
        """Test proper initialization of LocalIntentDetectionEngine."""
        assert len(local_intent_engine.store_locations) == 2
        assert len(local_intent_engine.local_intent_patterns) > 0
        assert LocalIntentType.NEAR_ME in local_intent_engine.local_intent_patterns
        assert (
            LocalIntentType.CITY_SPECIFIC in local_intent_engine.local_intent_patterns
        )

    def test_detect_near_me_intent(self, local_intent_engine):
        """Test detection of 'near me' local intent."""
        test_cases = [
            "gym equipment near me",
            "fitness center near me",
            "workout gear nearby",
            "exercise equipment close to me",
        ]

        for search_term in test_cases:
            intent_match = local_intent_engine.detect_local_intent(search_term)
            assert intent_match is not None
            assert intent_match.intent_type == LocalIntentType.NEAR_ME
            assert intent_match.confidence_score > 0.7
            assert intent_match.suggested_bid_adjustment > 0

    def test_detect_city_specific_intent(self, local_intent_engine):
        """Test detection of city-specific local intent."""
        test_cases = [
            "gym dallas",
            "fitness connection san antonio",
            "workout centers in houston",
            "dallas gym equipment",
        ]

        for search_term in test_cases:
            intent_match = local_intent_engine.detect_local_intent(search_term)
            assert intent_match is not None
            assert intent_match.intent_type == LocalIntentType.CITY_SPECIFIC
            assert intent_match.confidence_score > 0.7

            # Should have geographic modifier
            assert len(intent_match.geographic_modifier) > 0

    def test_detect_no_local_intent(self, local_intent_engine):
        """Test that non-local terms are not detected."""
        test_cases = [
            "home gym equipment",
            "online fitness classes",
            "workout supplements",
            "exercise videos",
        ]

        for search_term in test_cases:
            intent_match = local_intent_engine.detect_local_intent(search_term)
            assert intent_match is None

    def test_confidence_score_calculation(self, local_intent_engine):
        """Test confidence score calculation for different intent types."""
        # Near me should have high confidence
        near_me_match = local_intent_engine.detect_local_intent("gym near me")
        assert near_me_match.confidence_score > 0.8

        # City specific should have good confidence
        city_match = local_intent_engine.detect_local_intent("gym dallas")
        assert city_match.confidence_score > 0.7

        # Multiple local indicators should boost confidence
        multi_indicator = local_intent_engine.detect_local_intent(
            "local gym near me dallas"
        )
        assert multi_indicator.confidence_score > near_me_match.confidence_score

    def test_geographic_modifier_extraction(self, local_intent_engine):
        """Test extraction of geographic modifiers from search terms."""
        test_cases = [
            ("gym dallas", "dallas"),
            ("fitness near downtown", "downtown"),
            ("workout center north dallas", "north"),
            ("gym equipment san antonio", "san antonio"),
        ]

        for search_term, expected_modifier in test_cases:
            modifier = local_intent_engine._extract_geographic_modifier(search_term)
            assert expected_modifier.lower() in modifier.lower()

    def test_store_matching(self, local_intent_engine):
        """Test matching search terms to appropriate store locations."""
        # Dallas search should match Dallas store
        dallas_match = local_intent_engine.detect_local_intent("gym dallas")
        dallas_stores = [s for s in dallas_match.matched_stores if s.city == "Dallas"]
        assert len(dallas_stores) > 0

        # San Antonio search should match San Antonio store
        sa_match = local_intent_engine.detect_local_intent("fitness san antonio")
        sa_stores = [s for s in sa_match.matched_stores if s.city == "San Antonio"]
        assert len(sa_stores) > 0

        # Near me should potentially match all stores
        near_me_match = local_intent_engine.detect_local_intent("gym near me")
        assert len(near_me_match.matched_stores) >= 2

    def test_bid_adjustment_suggestions(self, local_intent_engine):
        """Test bid adjustment suggestions for local intent."""
        # Near me terms should get higher bid adjustments
        near_me_match = local_intent_engine.detect_local_intent("gym near me")
        assert near_me_match.suggested_bid_adjustment >= 15.0

        # City specific should get moderate adjustments
        city_match = local_intent_engine.detect_local_intent("gym dallas")
        assert city_match.suggested_bid_adjustment >= 10.0

        # Store specific should get highest adjustments
        store_match = local_intent_engine.detect_local_intent(
            "fitness connection red bird"
        )
        assert store_match.suggested_bid_adjustment >= 20.0

    def test_landing_page_recommendations(self, local_intent_engine):
        """Test landing page recommendations for local intent matches."""
        # Dallas search should recommend Dallas store landing page
        dallas_match = local_intent_engine.detect_local_intent("gym dallas")
        if dallas_match.matched_stores:
            dallas_store = next(
                s for s in dallas_match.matched_stores if s.city == "Dallas"
            )
            assert dallas_match.landing_page_recommendation == dallas_store.landing_page

        # Store-specific search should recommend specific store page
        store_match = local_intent_engine.detect_local_intent(
            "fitness connection blanco"
        )
        if store_match.matched_stores:
            blanco_store = next(
                s for s in store_match.matched_stores if "blanco" in s.name.lower()
            )
            assert store_match.landing_page_recommendation == blanco_store.landing_page

    def test_generate_script_content(self, local_intent_engine):
        """Test generation of Google Ads Script content."""
        script_content = local_intent_engine.generate_script()

        # Should contain main function
        assert "function main()" in script_content

        # Should contain store locations data
        assert "STORE_LOCATIONS" in script_content
        assert "Red Bird" in script_content
        assert "Blanco West" in script_content

        # Should contain detection patterns
        assert "DETECTION_PATTERNS" in script_content
        assert "near_me" in script_content

        # Should contain configuration
        assert "CONFIG" in script_content
        assert "LOOKBACK_DAYS" in script_content

    def test_store_performance_analysis(self, local_intent_engine):
        """Test store performance analysis functionality."""
        store = local_intent_engine.store_locations[0]
        performance = local_intent_engine.analyze_store_performance(store)

        assert isinstance(performance, GeographicPerformanceMetric)
        assert performance.location == f"{store.city}, {store.state}"
        assert performance.radius_miles == store.radius_miles
        assert performance.impressions > 0
        assert performance.clicks > 0

    def test_required_parameters(self, local_intent_engine):
        """Test that required parameters are properly defined."""
        required_params = local_intent_engine.get_required_parameters()

        assert "store_locations" in required_params
        assert "lookback_days" in required_params
        assert "min_impressions" in required_params

    def test_process_results_success(self, local_intent_engine):
        """Test processing of successful script results."""
        mock_results = {
            "nearMeTermsAnalyzed": [
                {
                    "searchTerm": "gym near me",
                    "intentType": "near_me",
                    "confidenceScore": 0.9,
                    "matchedStores": ["store_001"],
                },
                {
                    "searchTerm": "fitness dallas",
                    "intentType": "city_specific",
                    "confidenceScore": 0.8,
                    "matchedStores": ["store_001"],
                },
            ],
            "storeSpecificOptimizations": [
                {
                    "storeId": "store_001",
                    "optimizationPriority": 0.9,
                    "recommendations": ["increase_radius", "adjust_bids"],
                },
            ],
            "geographicAdjustments": [
                {
                    "action": "adjust_bid",
                    "locationId": "dallas",
                    "bidAdjustment": 15.0,
                },
            ],
            "crossLocationConflicts": [],
            "localKeywordExpansions": [
                {
                    "keyword": "gym equipment dallas",
                    "score": 0.85,
                    "searchVolume": 1200,
                },
            ],
            "landingPageMatches": [
                {
                    "searchTerm": "gym dallas",
                    "confidenceScore": 0.95,
                    "recommendedPage": "https://example.com/dallas",
                },
            ],
        }

        result = local_intent_engine.process_results(mock_results)

        assert result["status"] == ScriptStatus.COMPLETED.value
        assert result["rows_processed"] == 3  # near_me_terms + store_optimizations
        assert result["changes_made"] == 4  # Total optimizations found
        assert len(result["errors"]) == 0

        # Check detailed analysis
        details = result["details"]
        assert "local_intent_analysis" in details
        assert details["local_intent_analysis"]["near_me_terms_analyzed"] == 2
        assert (
            details["local_intent_analysis"]["high_confidence_matches"] == 1
        )  # Score > 0.9

    def test_process_results_with_warnings(self, local_intent_engine):
        """Test processing results that generate warnings."""
        mock_results = {
            "nearMeTermsAnalyzed": [],
            "storeSpecificOptimizations": [
                {"optimizationPriority": 0.9},  # High priority store
                {"optimizationPriority": 0.85},  # High priority store
            ],
            "geographicAdjustments": [],
            "crossLocationConflicts": [
                {"type": "cannibalization_risk"},
            ],
            "localKeywordExpansions": [],
            "landingPageMatches": [],
        }

        result = local_intent_engine.process_results(mock_results)

        assert result["status"] == ScriptStatus.COMPLETED.value
        assert len(result["warnings"]) > 0

        # Should warn about conflicts
        conflict_warning = any("conflict" in warning for warning in result["warnings"])
        assert conflict_warning

        # Should warn about high-priority stores
        priority_warning = any(
            "immediate optimization" in warning for warning in result["warnings"]
        )
        assert priority_warning

    def test_process_results_error_handling(self, local_intent_engine):
        """Test error handling in results processing."""
        # Invalid results format
        invalid_results = {"invalid_key": "invalid_value"}

        result = local_intent_engine.process_results(invalid_results)

        assert result["status"] == ScriptStatus.COMPLETED.value
        assert result["rows_processed"] == 0
        assert result["changes_made"] == 0

    def test_create_local_intent_config(self, sample_store_locations):
        """Test creation of local intent configuration."""
        config = create_local_intent_config(
            store_locations=sample_store_locations,
            lookback_days=45,
            min_impressions=150,
            enable_auto_bidding=True,
        )

        assert isinstance(config, ScriptConfig)
        assert "Local Intent Enhancement" in config.name
        assert config.parameters["lookback_days"] == 45
        assert config.parameters["min_impressions"] == 150
        assert config.parameters["enable_auto_bidding"] is True
        assert config.parameters["store_locations"] == sample_store_locations

    def test_intent_pattern_coverage(self, local_intent_engine):
        """Test that intent patterns cover various local search scenarios."""
        patterns = local_intent_engine.local_intent_patterns

        # Should have patterns for all intent types
        assert LocalIntentType.NEAR_ME in patterns
        assert LocalIntentType.CITY_SPECIFIC in patterns
        assert LocalIntentType.NEIGHBORHOOD in patterns
        assert LocalIntentType.DIRECTION_MODIFIER in patterns
        assert LocalIntentType.LANDMARK_REFERENCE in patterns
        assert LocalIntentType.STORE_SPECIFIC in patterns

        # Each type should have multiple patterns
        for intent_type, pattern_list in patterns.items():
            assert len(pattern_list) >= 2, (
                f"{intent_type} should have multiple patterns"
            )

    def test_edge_cases(self, local_intent_engine):
        """Test edge cases and boundary conditions."""
        # Empty search term
        assert local_intent_engine.detect_local_intent("") is None

        # Very short term
        assert local_intent_engine.detect_local_intent("gym") is None

        # Very long search term with local intent
        long_term = "best gym equipment for home workouts near me in dallas texas area"
        intent_match = local_intent_engine.detect_local_intent(long_term)
        assert intent_match is not None
        assert intent_match.intent_type in [
            LocalIntentType.NEAR_ME,
            LocalIntentType.CITY_SPECIFIC,
        ]

        # Case sensitivity
        upper_case = "GYM NEAR ME DALLAS"
        lower_case = "gym near me dallas"

        upper_match = local_intent_engine.detect_local_intent(upper_case)
        lower_match = local_intent_engine.detect_local_intent(lower_case)

        assert upper_match is not None
        assert lower_match is not None
        assert upper_match.intent_type == lower_match.intent_type

    @patch("paidsearchnav.platforms.google.scripts.local_intent_optimization.logger")
    def test_error_logging(self, mock_logger, local_intent_engine):
        """Test that errors are properly logged."""
        # Force an error in results processing
        with patch.object(
            local_intent_engine,
            "_calculate_confidence_score",
            side_effect=Exception("Test error"),
        ):
            result = local_intent_engine.process_results({"nearMeTermsAnalyzed": [{}]})

            # Should handle error gracefully
            assert result["status"] == ScriptStatus.FAILED.value
            assert len(result["errors"]) > 0
            mock_logger.error.assert_called()

    def test_performance_with_large_dataset(self, local_intent_engine):
        """Test performance with larger datasets."""
        # Test with many search terms
        search_terms = [f"gym near me variation {i}" for i in range(100)] + [
            f"fitness {city} variation {i}"
            for city in ["dallas", "houston", "austin", "san antonio"]
            for i in range(25)
        ]

        matches = []
        for term in search_terms:
            match = local_intent_engine.detect_local_intent(term)
            if match:
                matches.append(match)

        # Should handle large dataset efficiently
        assert len(matches) > 150  # Most should match

        # All matches should have valid data
        for match in matches:
            assert match.confidence_score > 0
            assert match.suggested_bid_adjustment >= 0
            assert len(match.matched_stores) > 0


class TestLocalIntentDataStructures:
    """Test data structures used in local intent optimization."""

    def test_store_location_dataclass(self):
        """Test StoreLocation dataclass."""
        store = StoreLocation(
            store_id="test_001",
            name="Test Store",
            address="123 Test St",
            city="Dallas",
            state="TX",
            zip_code="75001",
            latitude=32.7767,
            longitude=-96.7970,
        )

        assert store.store_id == "test_001"
        assert store.radius_miles == 25  # Default value
        assert store.landing_page is None  # Default value

    def test_local_intent_match_dataclass(self):
        """Test LocalIntentMatch dataclass."""
        store = StoreLocation(
            store_id="test_001",
            name="Test Store",
            address="123 Test St",
            city="Dallas",
            state="TX",
            zip_code="75001",
            latitude=32.7767,
            longitude=-96.7970,
        )

        match = LocalIntentMatch(
            search_term="gym near me",
            intent_type=LocalIntentType.NEAR_ME,
            confidence_score=0.9,
            matched_stores=[store],
            geographic_modifier="near me",
            suggested_bid_adjustment=15.0,
        )

        assert match.search_term == "gym near me"
        assert match.intent_type == LocalIntentType.NEAR_ME
        assert match.confidence_score == 0.9
        assert len(match.matched_stores) == 1
        assert match.landing_page_recommendation is None  # Default

    def test_geographic_performance_metric_dataclass(self):
        """Test GeographicPerformanceMetric dataclass."""
        metric = GeographicPerformanceMetric(
            location="Dallas, TX",
            radius_miles=25,
            impressions=1000,
            clicks=50,
            conversions=5,
            cost=125.0,
        )

        assert metric.location == "Dallas, TX"
        assert metric.store_visits == 0  # Default
        assert metric.ctr == 0.0  # Default
        assert metric.cpc == 0.0  # Default
        assert metric.conversion_rate == 0.0  # Default

    def test_local_intent_type_enum(self):
        """Test LocalIntentType enum values."""
        assert LocalIntentType.NEAR_ME.value == "near_me"
        assert LocalIntentType.CITY_SPECIFIC.value == "city_specific"
        assert LocalIntentType.NEIGHBORHOOD.value == "neighborhood"
        assert LocalIntentType.DIRECTION_MODIFIER.value == "direction_modifier"
        assert LocalIntentType.LANDMARK_REFERENCE.value == "landmark_reference"
        assert LocalIntentType.STORE_SPECIFIC.value == "store_specific"

        # Should have all expected types
        assert len(LocalIntentType) == 6


if __name__ == "__main__":
    pytest.main([__file__])
