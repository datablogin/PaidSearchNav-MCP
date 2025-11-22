"""Tests for Local Keyword Expansion Google Ads Scripts."""

from unittest.mock import Mock, patch

import pytest

from paidsearchnav.platforms.google.scripts.base import (
    ScriptConfig,
    ScriptStatus,
)
from paidsearchnav.platforms.google.scripts.local_intent_optimization import (
    StoreLocation,
)
from paidsearchnav.platforms.google.scripts.local_keyword_expansion import (
    KeywordExpansionType,
    KeywordOpportunity,
    LandingPageMatchType,
    LandingPageRecommendation,
    LocalKeywordExpansionEngine,
    LocalMarketOpportunity,
    create_local_keyword_expansion_config,
)


class TestLocalKeywordExpansionEngine:
    """Test suite for LocalKeywordExpansionEngine."""

    @pytest.fixture
    def sample_store_locations(self):
        """Sample store locations for testing."""
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
                "neighborhoods": ["Red Bird", "Oak Cliff", "Cedar Crest"],
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
                "neighborhoods": ["Blanco", "Stone Oak", "North San Antonio"],
            },
        ]

    @pytest.fixture
    def keyword_expansion_config(self, sample_store_locations):
        """Create test configuration for keyword expansion."""
        return create_local_keyword_expansion_config(
            store_locations=sample_store_locations,
            lookback_days=30,
            min_impressions=100,
        )

    @pytest.fixture
    def mock_client(self):
        """Mock Google Ads client."""
        return Mock()

    @pytest.fixture
    def keyword_engine(self, mock_client, keyword_expansion_config):
        """Create LocalKeywordExpansionEngine instance for testing."""
        engine = LocalKeywordExpansionEngine(mock_client, keyword_expansion_config)
        # Set up store locations from config
        engine.store_locations = [
            StoreLocation(**store)
            for store in keyword_expansion_config.parameters["store_locations"]
        ]
        return engine

    def test_keyword_engine_initialization(self, keyword_engine):
        """Test proper initialization of LocalKeywordExpansionEngine."""
        assert len(keyword_engine.store_locations) == 2
        assert len(keyword_engine.geographic_modifiers) > 0
        assert len(keyword_engine.competitor_keywords) > 0
        assert len(keyword_engine.seasonal_modifiers) > 0

        # Check geographic modifiers structure
        geo_modifiers = keyword_engine.geographic_modifiers
        assert "cities" in geo_modifiers
        assert "neighborhoods" in geo_modifiers
        assert "proximity" in geo_modifiers
        assert "landmarks" in geo_modifiers

    def test_geographic_modifier_content(self, keyword_engine):
        """Test content of geographic modifiers."""
        geo_modifiers = keyword_engine.geographic_modifiers

        # Should contain Texas cities
        assert "dallas" in geo_modifiers["cities"]
        assert "san antonio" in geo_modifiers["cities"]
        assert "houston" in geo_modifiers["cities"]

        # Should contain proximity terms
        assert "near me" in geo_modifiers["proximity"]
        assert "nearby" in geo_modifiers["proximity"]

        # Should contain directional terms
        assert "north" in geo_modifiers["directions"]
        assert "south" in geo_modifiers["directions"]

    def test_competitor_keyword_structure(self, keyword_engine):
        """Test competitor keyword structure."""
        competitor_keywords = keyword_engine.competitor_keywords

        # Should have different business categories
        assert "fitness" in competitor_keywords
        assert "retail" in competitor_keywords
        assert "restaurants" in competitor_keywords

        # Each category should have competitor comparisons
        for category, keywords in competitor_keywords.items():
            assert len(keywords) > 0
            # Should contain comparison terms
            has_comparison = any(
                "vs" in kw or "better than" in kw or "alternative to" in kw
                for kw in keywords
            )
            assert has_comparison

    def test_seasonal_modifier_structure(self, keyword_engine):
        """Test seasonal modifier structure."""
        seasonal_modifiers = keyword_engine.seasonal_modifiers

        # Should have seasonal categories
        assert "seasonal" in seasonal_modifiers
        assert "temporal" in seasonal_modifiers
        assert "events" in seasonal_modifiers

        # Should contain relevant terms
        assert "summer" in seasonal_modifiers["seasonal"]
        assert "24 hours" in seasonal_modifiers["temporal"]
        assert "back to school" in seasonal_modifiers["events"]

    def test_generate_script_content(self, keyword_engine):
        """Test generation of Google Ads Script content."""
        script_content = keyword_engine.generate_script()

        # Should contain main function
        assert "function main()" in script_content

        # Should contain key functions
        assert "generateLocalKeywordExpansions()" in script_content
        assert "optimizeLandingPageMatches()" in script_content
        assert "identifyMarketOpportunities()" in script_content
        assert "generateCompetitiveKeywords()" in script_content
        assert "generateSeasonalExpansions()" in script_content

        # Should contain modifier data
        assert "GEOGRAPHIC_MODIFIERS" in script_content
        assert "COMPETITOR_KEYWORDS" in script_content
        assert "SEASONAL_MODIFIERS" in script_content

        # Should contain configuration
        assert "CONFIG" in script_content
        assert "MIN_OPPORTUNITY_SCORE" in script_content

    def test_generate_keyword_opportunities(self, keyword_engine):
        """Test generation of keyword expansion opportunities."""
        base_keywords = ["gym equipment", "fitness classes", "personal training"]
        opportunities = keyword_engine.generate_keyword_opportunities(
            base_keywords, keyword_engine.store_locations
        )

        assert len(opportunities) > 0

        for opportunity in opportunities:
            assert isinstance(opportunity, KeywordOpportunity)
            assert opportunity.base_keyword in base_keywords
            assert opportunity.expanded_keyword != opportunity.base_keyword
            assert opportunity.confidence_score > 0
            assert opportunity.suggested_bid > 0
            assert opportunity.expansion_type in KeywordExpansionType

    def test_geographic_variations_generation(self, keyword_engine):
        """Test generation of geographic keyword variations."""
        base_keyword = "gym equipment"
        store = keyword_engine.store_locations[0]  # Dallas store

        variations = keyword_engine._generate_geographic_variations(base_keyword, store)

        assert len(variations) > 0

        # Should create city-specific variations
        city_variations = [
            v for v in variations if store.city.lower() in v.expanded_keyword.lower()
        ]
        assert len(city_variations) > 0

        # Check variation formats
        expected_formats = [
            f"{store.city.lower()} {base_keyword}",
            f"{base_keyword} {store.city.lower()}",
            f"{base_keyword} in {store.city.lower()}",
        ]

        actual_keywords = [v.expanded_keyword.lower() for v in variations]
        for expected in expected_formats:
            assert expected in actual_keywords

    def test_proximity_variations_generation(self, keyword_engine):
        """Test generation of proximity-based keyword variations."""
        base_keyword = "fitness classes"
        variations = keyword_engine._generate_proximity_variations(base_keyword)

        assert len(variations) > 0

        # Should create proximity variations
        proximity_terms = ["near me", "nearby", "close to me", "in my area"]
        for term in proximity_terms:
            expected_keyword = f"{base_keyword} {term}"
            matching_variations = [
                v for v in variations if v.expanded_keyword == expected_keyword
            ]
            assert len(matching_variations) == 1

            variation = matching_variations[0]
            assert variation.expansion_type == KeywordExpansionType.DISTANCE_MODIFIER
            assert (
                variation.confidence_score > 0.8
            )  # High confidence for proximity terms

    def test_search_volume_estimation(self, keyword_engine):
        """Test search volume estimation logic."""
        # Test different keyword types
        near_me_volume = keyword_engine._estimate_search_volume("gym near me")
        city_volume = keyword_engine._estimate_search_volume("gym dallas")
        generic_volume = keyword_engine._estimate_search_volume("gym equipment plano")

        # Near me terms should have adjusted volume
        assert near_me_volume > 0

        # Major city terms should have higher volume
        assert city_volume > near_me_volume

        # All should be reasonable values
        assert 0 < generic_volume < 100000

    def test_bid_calculation(self, keyword_engine):
        """Test bid calculation for expanded keywords."""
        base_keyword = "personal training"

        # Test without location (base bid)
        base_bid = keyword_engine._calculate_suggested_bid(base_keyword)
        assert base_bid > 0
        assert base_bid < 10  # Reasonable upper bound

        # Test with Dallas location (major market)
        dallas_store = next(
            s for s in keyword_engine.store_locations if s.city == "Dallas"
        )
        dallas_bid = keyword_engine._calculate_suggested_bid(base_keyword, dallas_store)
        assert dallas_bid > base_bid  # Should be higher for major market

        # Test with San Antonio location (secondary market)
        sa_store = next(
            s for s in keyword_engine.store_locations if s.city == "San Antonio"
        )
        sa_bid = keyword_engine._calculate_suggested_bid(base_keyword, sa_store)
        assert sa_bid != dallas_bid  # Should be different

    def test_process_results_success(self, keyword_engine):
        """Test processing of successful keyword expansion results."""
        mock_results = {
            "keywordExpansions": [
                {
                    "baseKeyword": "gym equipment",
                    "expandedKeyword": "gym equipment dallas",
                    "expansionType": "geographic_modifier",
                    "opportunityScore": 0.85,
                },
                {
                    "baseKeyword": "fitness classes",
                    "expandedKeyword": "fitness classes near me",
                    "expansionType": "distance_modifier",
                    "opportunityScore": 0.90,
                },
            ],
            "landingPageOptimizations": [
                {
                    "searchTerm": "gym dallas",
                    "confidenceScore": 0.95,
                    "expectedImprovements": {"conversionRateIncrease": 30.0},
                },
                {
                    "searchTerm": "fitness san antonio",
                    "confidenceScore": 0.80,
                    "expectedImprovements": {"conversionRateIncrease": 15.0},
                },
            ],
            "marketOpportunities": [
                {
                    "marketName": "Austin",
                    "searchVolume": 15000,
                    "opportunityScore": 0.75,
                },
            ],
            "competitiveKeywords": [
                {
                    "baseKeyword": "gym membership",
                    "expandedKeyword": "gym membership vs planet fitness",
                    "opportunityScore": 0.80,
                },
            ],
            "seasonalExpansions": [
                {
                    "baseKeyword": "fitness classes",
                    "expandedKeyword": "fitness classes new year",
                    "trendStrength": 0.85,
                },
            ],
            "performancePredictions": [
                {
                    "keyword": "gym equipment dallas",
                    "expectedImpressions": 1200,
                    "expectedClicks": 60,
                    "expectedConversions": 6,
                    "expectedROI": 250.0,
                },
                {
                    "keyword": "fitness classes near me",
                    "expectedImpressions": 800,
                    "expectedClicks": 48,
                    "expectedConversions": 8,
                    "expectedROI": 180.0,
                },
            ],
        }

        result = keyword_engine.process_results(mock_results)

        assert result["status"] == ScriptStatus.COMPLETED.value
        assert result["rows_processed"] == 5  # Total opportunities
        assert result["changes_made"] == 2  # Landing page optimizations
        assert len(result["errors"]) == 0

        # Should have warnings for high-impact opportunities
        assert len(result["warnings"]) >= 2

        # Check detailed analysis
        details = result["details"]
        assert "keyword_expansion" in details
        assert "landing_page_optimization" in details
        assert "market_opportunities" in details
        assert "competitive_analysis" in details
        assert "seasonal_analysis" in details
        assert "performance_predictions" in details

        # Check specific metrics
        assert details["keyword_expansion"]["total_opportunities"] == 2
        assert details["landing_page_optimization"]["total_optimizations"] == 2
        assert details["market_opportunities"]["total_markets"] == 1
        assert details["performance_predictions"]["total_predicted_impressions"] == 2000
        assert details["performance_predictions"]["high_roi_keywords"] == 1  # ROI > 200

    def test_process_results_with_warnings(self, keyword_engine):
        """Test processing results that generate warnings."""
        mock_results = {
            "keywordExpansions": [
                {"opportunityScore": 0.90},  # High opportunity
                {"opportunityScore": 0.87},  # High opportunity
            ],
            "landingPageOptimizations": [
                {
                    "expectedImprovements": {"conversionRateIncrease": 35.0}
                },  # High impact
                {
                    "expectedImprovements": {"conversionRateIncrease": 28.0}
                },  # High impact
            ],
            "marketOpportunities": [
                {"searchVolume": 25000},  # High volume
                {"searchVolume": 15000},  # High volume
            ],
            "competitiveKeywords": [],
            "seasonalExpansions": [],
            "performancePredictions": [],
        }

        result = keyword_engine.process_results(mock_results)

        assert result["status"] == ScriptStatus.COMPLETED.value
        assert len(result["warnings"]) == 3  # Should warn about high-opportunity items

        # Check specific warnings
        warnings_text = " ".join(result["warnings"])
        assert "conversion rate improvement potential" in warnings_text
        assert "very high opportunity scores" in warnings_text
        assert "high search volume potential" in warnings_text

    def test_required_parameters(self, keyword_engine):
        """Test that required parameters are properly defined."""
        required_params = keyword_engine.get_required_parameters()

        assert "store_locations" in required_params
        assert "lookback_days" in required_params
        assert "min_impressions" in required_params

    def test_create_keyword_expansion_config(self, sample_store_locations):
        """Test creation of keyword expansion configuration."""
        config = create_local_keyword_expansion_config(
            store_locations=sample_store_locations,
            lookback_days=45,
            min_impressions=150,
        )

        assert isinstance(config, ScriptConfig)
        assert "Local Keyword Expansion" in config.name
        assert config.parameters["lookback_days"] == 45
        assert config.parameters["min_impressions"] == 150
        assert config.parameters["store_locations"] == sample_store_locations

        # Check default parameters
        assert config.parameters["min_opportunity_score"] == 0.6
        assert config.parameters["max_keyword_suggestions"] == 100
        assert config.parameters["expansion_bid_multiplier"] == 0.8

    def test_keyword_expansion_type_enum(self):
        """Test KeywordExpansionType enum values."""
        assert KeywordExpansionType.GEOGRAPHIC_MODIFIER.value == "geographic_modifier"
        assert KeywordExpansionType.DISTANCE_MODIFIER.value == "distance_modifier"
        assert KeywordExpansionType.LANDMARK_REFERENCE.value == "landmark_reference"
        assert KeywordExpansionType.COMPETITOR_REFERENCE.value == "competitor_reference"
        assert KeywordExpansionType.SEASONAL_MODIFIER.value == "seasonal_modifier"
        assert KeywordExpansionType.SERVICE_LOCATION.value == "service_location"

    def test_landing_page_match_type_enum(self):
        """Test LandingPageMatchType enum values."""
        assert LandingPageMatchType.STORE_SPECIFIC.value == "store_specific"
        assert LandingPageMatchType.CITY_SPECIFIC.value == "city_specific"
        assert LandingPageMatchType.SERVICE_SPECIFIC.value == "service_specific"
        assert LandingPageMatchType.PROMOTIONAL.value == "promotional"
        assert LandingPageMatchType.DEFAULT_FALLBACK.value == "default_fallback"

    def test_error_handling(self, keyword_engine):
        """Test error handling in various scenarios."""
        # Test with empty input
        empty_opportunities = keyword_engine.generate_keyword_opportunities([], [])
        assert len(empty_opportunities) == 0

        # Test with invalid store data
        invalid_store = StoreLocation(
            store_id="invalid",
            name="",
            address="",
            city="",
            state="",
            zip_code="",
            latitude=0,
            longitude=0,
        )

        opportunities = keyword_engine.generate_keyword_opportunities(
            ["test keyword"], [invalid_store]
        )
        # Should handle gracefully
        assert isinstance(opportunities, list)

    @patch("paidsearchnav.platforms.google.scripts.local_keyword_expansion.logger")
    def test_exception_handling(self, mock_logger, keyword_engine):
        """Test exception handling in results processing."""
        # Force an exception
        with patch.object(
            keyword_engine,
            "_estimate_search_volume",
            side_effect=Exception("Test error"),
        ):
            result = keyword_engine.process_results(
                {"keywordExpansions": [{"test": "data"}]}
            )

            # Should log error and return failure
            assert result["status"] == ScriptStatus.FAILED.value
            assert len(result["errors"]) > 0
            mock_logger.error.assert_called()

    def test_performance_with_large_datasets(self, keyword_engine):
        """Test performance with larger datasets."""
        # Test with many base keywords
        base_keywords = [f"keyword_{i}" for i in range(50)]
        stores = keyword_engine.store_locations

        opportunities = keyword_engine.generate_keyword_opportunities(
            base_keywords, stores
        )

        # Should handle large datasets efficiently
        assert len(opportunities) > 50  # Should generate multiple variations

        # All opportunities should be valid
        for opportunity in opportunities:
            assert opportunity.confidence_score > 0
            assert opportunity.suggested_bid > 0
            assert len(opportunity.expanded_keyword) > 0
            assert opportunity.expansion_type in KeywordExpansionType


class TestKeywordExpansionDataStructures:
    """Test data structures used in keyword expansion."""

    def test_keyword_opportunity_dataclass(self):
        """Test KeywordOpportunity dataclass."""
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

        opportunity = KeywordOpportunity(
            base_keyword="gym equipment",
            expanded_keyword="gym equipment dallas",
            expansion_type=KeywordExpansionType.GEOGRAPHIC_MODIFIER,
            matched_stores=[store],
            search_volume_estimate=1500,
            competition_level="medium",
            suggested_bid=3.25,
            confidence_score=0.85,
            landing_page_recommendation="https://example.com/dallas",
            reasoning="Geographic expansion for Dallas market",
        )

        assert opportunity.base_keyword == "gym equipment"
        assert opportunity.expanded_keyword == "gym equipment dallas"
        assert opportunity.expansion_type == KeywordExpansionType.GEOGRAPHIC_MODIFIER
        assert len(opportunity.matched_stores) == 1
        assert opportunity.confidence_score == 0.85
        assert opportunity.landing_page_recommendation is not None

    def test_landing_page_recommendation_dataclass(self):
        """Test LandingPageRecommendation dataclass."""
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

        recommendation = LandingPageRecommendation(
            search_term="gym dallas",
            current_landing_page="https://example.com/generic",
            recommended_landing_page="https://example.com/dallas",
            match_type=LandingPageMatchType.CITY_SPECIFIC,
            matched_store=store,
            confidence_score=0.90,
            expected_improvement={"conversion_rate": 25.0, "quality_score": 15.0},
            reasoning="City-specific landing page will improve relevance",
        )

        assert recommendation.search_term == "gym dallas"
        assert recommendation.match_type == LandingPageMatchType.CITY_SPECIFIC
        assert recommendation.matched_store == store
        assert recommendation.confidence_score == 0.90
        assert "conversion_rate" in recommendation.expected_improvement

    def test_local_market_opportunity_dataclass(self):
        """Test LocalMarketOpportunity dataclass."""
        opportunity = LocalMarketOpportunity(
            market_identifier="austin_tx",
            market_name="Austin, TX",
            opportunity_type="underserved_market",
            search_volume=12000,
            competition_density=0.65,
            nearest_store_distance=85.0,
            market_penetration_score=0.15,
            recommended_keywords=[
                "gym austin",
                "fitness center austin",
                "workout austin",
            ],
            estimated_performance={
                "expected_impressions": 1800,
                "expected_clicks": 90,
                "expected_conversions": 9,
                "roi_projection": 200.0,
            },
        )

        assert opportunity.market_identifier == "austin_tx"
        assert opportunity.market_name == "Austin, TX"
        assert opportunity.search_volume == 12000
        assert len(opportunity.recommended_keywords) == 3
        assert "roi_projection" in opportunity.estimated_performance

    def test_enum_completeness(self):
        """Test that all enum types have expected values."""
        # KeywordExpansionType should have 6 types
        assert len(KeywordExpansionType) == 6

        # LandingPageMatchType should have 5 types
        assert len(LandingPageMatchType) == 5

        # All enum values should be strings
        for expansion_type in KeywordExpansionType:
            assert isinstance(expansion_type.value, str)
            assert len(expansion_type.value) > 0

        for match_type in LandingPageMatchType:
            assert isinstance(match_type.value, str)
            assert len(match_type.value) > 0


class TestKeywordExpansionIntegration:
    """Integration tests for keyword expansion functionality."""

    def test_end_to_end_keyword_expansion(self, keyword_engine):
        """Test end-to-end keyword expansion workflow."""
        base_keywords = ["gym", "fitness", "workout"]
        stores = keyword_engine.store_locations

        # Generate opportunities
        opportunities = keyword_engine.generate_keyword_opportunities(
            base_keywords, stores
        )

        assert len(opportunities) > 0

        # Test that we get different types of expansions
        expansion_types = {opp.expansion_type for opp in opportunities}
        assert KeywordExpansionType.GEOGRAPHIC_MODIFIER in expansion_types
        assert KeywordExpansionType.DISTANCE_MODIFIER in expansion_types

        # Test that opportunities are reasonable
        for opportunity in opportunities:
            # Base keyword should be one of our inputs
            assert opportunity.base_keyword in base_keywords

            # Expanded keyword should be different and longer
            assert opportunity.expanded_keyword != opportunity.base_keyword
            assert len(opportunity.expanded_keyword) > len(opportunity.base_keyword)

            # Should have matched stores
            assert len(opportunity.matched_stores) > 0

            # Metrics should be reasonable
            assert 0 < opportunity.confidence_score <= 1.0
            assert opportunity.suggested_bid > 0
            assert opportunity.search_volume_estimate > 0

    def test_geographic_targeting_consistency(self, keyword_engine):
        """Test that geographic targeting is consistent across features."""
        dallas_store = next(
            s for s in keyword_engine.store_locations if s.city == "Dallas"
        )
        base_keyword = "personal training"

        # Generate geographic variations
        geo_variations = keyword_engine._generate_geographic_variations(
            base_keyword, dallas_store
        )

        # All variations should target Dallas
        for variation in geo_variations:
            assert "dallas" in variation.expanded_keyword.lower()

            # Should recommend Dallas landing page
            if dallas_store.landing_page:
                assert (
                    variation.landing_page_recommendation == dallas_store.landing_page
                )

            # Should include Dallas store in matched stores
            dallas_matches = [s for s in variation.matched_stores if s.city == "Dallas"]
            assert len(dallas_matches) > 0

    def test_competitive_analysis_integration(self, keyword_engine):
        """Test integration with competitive analysis."""
        # Test that competitor keywords are business-appropriate
        competitor_keywords = keyword_engine.competitor_keywords

        # For fitness business, should have fitness competitors
        if "fitness" in competitor_keywords:
            fitness_competitors = competitor_keywords["fitness"]

            # Should include major fitness chains
            competitor_text = " ".join(fitness_competitors).lower()
            assert any(
                chain in competitor_text
                for chain in ["planet fitness", "la fitness", "24 hour fitness"]
            )

    def test_seasonal_relevance(self, keyword_engine):
        """Test seasonal keyword relevance."""
        seasonal_modifiers = keyword_engine.seasonal_modifiers

        # Should have current season relevance
        seasonal_terms = seasonal_modifiers["seasonal"]
        temporal_terms = seasonal_modifiers["temporal"]
        event_terms = seasonal_modifiers["events"]

        # Should cover major seasons/events
        assert "summer" in seasonal_terms
        assert "winter" in seasonal_terms
        assert "new year" in seasonal_terms

        # Should have time-based terms
        assert any("24" in term for term in temporal_terms)
        assert any("hour" in term for term in temporal_terms)

        # Should have event-based terms
        assert any("school" in term for term in event_terms)
        assert any("day" in term for term in event_terms)


if __name__ == "__main__":
    pytest.main([__file__])
