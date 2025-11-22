"""Integration tests for Local Intent Optimization Google Ads Scripts system."""

from unittest.mock import Mock

import pytest

from paidsearchnav.platforms.google.client import GoogleAdsClient
from paidsearchnav.platforms.google.scripts.base import (
    RateLimiter,
    ScriptExecutor,
    ScriptStatus,
)
from paidsearchnav.platforms.google.scripts.geographic_optimization import (
    GeographicOptimizationEngine,
    create_geographic_optimization_config,
)
from paidsearchnav.platforms.google.scripts.local_intent_optimization import (
    LocalIntentDetectionEngine,
    create_local_intent_config,
)
from paidsearchnav.platforms.google.scripts.local_keyword_expansion import (
    LocalKeywordExpansionEngine,
    create_local_keyword_expansion_config,
)


class TestLocalIntentOptimizationIntegration:
    """Integration tests for the complete local intent optimization system."""

    @pytest.fixture
    def fitness_connection_store_data(self):
        """Real-world store data based on Fitness Connection example."""
        return [
            {
                "store_id": "FC_RED_BIRD",
                "name": "Fitness Connection Red Bird Lane",
                "address": "3662 W Camp Wisdom Rd, Dallas, TX 75237",
                "city": "Dallas",
                "state": "TX",
                "zip_code": "75237",
                "latitude": 32.7033,
                "longitude": -96.8618,
                "radius_miles": 25,
                "landing_page": "https://fitnessconnection.com/gyms/red-bird-lane",
                "store_type": "fitness_center",
                "market_tier": "primary",
                "competitor_density": "high",
                "seasonality_index": 1.2,
                "neighborhoods": [
                    "Red Bird",
                    "Oak Cliff",
                    "Cedar Crest",
                    "Duncanville",
                ],
            },
            {
                "store_id": "FC_BLANCO_WEST",
                "name": "Fitness Connection Blanco West",
                "address": "11255 Huebner Rd, San Antonio, TX 78230",
                "city": "San Antonio",
                "state": "TX",
                "zip_code": "78230",
                "latitude": 29.5516,
                "longitude": -98.5758,
                "radius_miles": 20,
                "landing_page": "https://fitnessconnection.com/gyms/blanco-west",
                "store_type": "fitness_center",
                "market_tier": "secondary",
                "competitor_density": "medium",
                "seasonality_index": 1.0,
                "neighborhoods": [
                    "Blanco",
                    "Stone Oak",
                    "North San Antonio",
                    "Medical Center",
                ],
            },
            {
                "store_id": "FC_PLANO",
                "name": "Fitness Connection Plano",
                "address": "2000 W Spring Creek Pkwy, Plano, TX 75023",
                "city": "Plano",
                "state": "TX",
                "zip_code": "75023",
                "latitude": 33.0198,
                "longitude": -96.7081,
                "radius_miles": 15,
                "landing_page": "https://fitnessconnection.com/gyms/plano",
                "store_type": "fitness_center",
                "market_tier": "secondary",
                "competitor_density": "very_high",
                "seasonality_index": 1.1,
                "neighborhoods": ["Legacy", "West Plano", "Willow Bend"],
            },
        ]

    @pytest.fixture
    def mock_google_ads_client(self):
        """Mock Google Ads client with realistic response data."""
        client = Mock(spec=GoogleAdsClient)
        client.customer_id = "7126330917"  # Example customer ID from issue
        client.is_authenticated.return_value = True
        return client

    @pytest.fixture
    def sample_search_terms_data(self):
        """Sample search terms data matching Fitness Connection patterns."""
        return [
            {
                "search_term": "gym equipment near me",
                "impressions": 1245,
                "clicks": 62,
                "conversions": 8,
                "cost": 155.0,
                "campaign": "PP_FIT_SRCH_Google_CON_BRN_TermOnly_Generic",
                "ad_group": "Gym Equipment",
            },
            {
                "search_term": "fitness connection dallas",
                "impressions": 890,
                "clicks": 73,
                "conversions": 12,
                "cost": 182.5,
                "campaign": "PP_FIT_SRCH_Google_CON_BRN_TermOnly_Dallas",
                "ad_group": "Brand Terms Dallas",
            },
            {
                "search_term": "gym near me dallas",
                "impressions": 2156,
                "clicks": 108,
                "conversions": 15,
                "cost": 270.0,
                "campaign": "PP_FIT_SRCH_Google_CON_BRN_TermOnly_Dallas",
                "ad_group": "Local Gym Terms",
            },
            {
                "search_term": "san antonio gym",
                "impressions": 756,
                "clicks": 45,
                "conversions": 6,
                "cost": 135.0,
                "campaign": "PP_FIT_SRCH_Google_CON_BRN_TermOnly_SanAntonioBlanco",
                "ad_group": "City Specific",
            },
            {
                "search_term": "24 hour gym plano",
                "impressions": 432,
                "clicks": 28,
                "conversions": 4,
                "cost": 84.0,
                "campaign": "PP_FIT_SRCH_Google_CON_BRN_TermOnly_Plano",
                "ad_group": "Plano Local Terms",
            },
        ]

    @pytest.fixture
    def sample_performance_data(self):
        """Sample geographic performance data."""
        return {
            "dallas_tx": {
                "impressions": 15420,
                "clicks": 771,
                "conversions": 94,
                "cost": 1927.5,
                "store_visits": 156,
                "ctr": 5.0,
                "cpc": 2.50,
                "conversion_rate": 12.2,
            },
            "san_antonio_tx": {
                "impressions": 8940,
                "clicks": 447,
                "conversions": 48,
                "cost": 1292.55,
                "store_visits": 78,
                "ctr": 5.0,
                "cpc": 2.89,
                "conversion_rate": 10.7,
            },
            "plano_tx": {
                "impressions": 5680,
                "clicks": 284,
                "conversions": 31,
                "cost": 909.2,
                "store_visits": 52,
                "ctr": 5.0,
                "cpc": 3.20,
                "conversion_rate": 10.9,
            },
        }

    def test_complete_local_intent_workflow(
        self,
        mock_google_ads_client,
        fitness_connection_store_data,
        sample_search_terms_data,
        sample_performance_data,
    ):
        """Test complete local intent optimization workflow."""
        # Step 1: Initialize all engines
        local_intent_config = create_local_intent_config(
            store_locations=fitness_connection_store_data,
            lookback_days=30,
            min_impressions=100,
        )

        geo_config = create_geographic_optimization_config(
            store_locations=fitness_connection_store_data,
            lookback_days=30,
            min_impressions=100,
        )

        keyword_config = create_local_keyword_expansion_config(
            store_locations=fitness_connection_store_data,
            lookback_days=30,
            min_impressions=100,
        )

        # Create engines
        local_intent_engine = LocalIntentDetectionEngine(
            mock_google_ads_client, local_intent_config
        )
        geo_engine = GeographicOptimizationEngine(mock_google_ads_client, geo_config)
        keyword_engine = LocalKeywordExpansionEngine(
            mock_google_ads_client, keyword_config
        )

        # Step 2: Process search terms through local intent detection
        local_intent_results = []
        for search_data in sample_search_terms_data:
            intent_match = local_intent_engine.detect_local_intent(
                search_data["search_term"]
            )
            if intent_match:
                local_intent_results.append(
                    {
                        "search_term": search_data["search_term"],
                        "intent_type": intent_match.intent_type.value,
                        "confidence_score": intent_match.confidence_score,
                        "matched_stores": [
                            s.store_id for s in intent_match.matched_stores
                        ],
                        "suggested_bid_adjustment": intent_match.suggested_bid_adjustment,
                        "geographic_modifier": intent_match.geographic_modifier,
                        "performance_data": search_data,
                    }
                )

        # Should detect local intent in most terms
        assert len(local_intent_results) >= 4

        # Step 3: Test specific local intent detection accuracy
        near_me_results = [
            r for r in local_intent_results if "near me" in r["search_term"]
        ]
        assert len(near_me_results) >= 1

        city_specific_results = [
            r
            for r in local_intent_results
            if any(
                city in r["search_term"] for city in ["dallas", "san antonio", "plano"]
            )
        ]
        assert len(city_specific_results) >= 3

        # Step 4: Generate geographic optimizations
        mock_geo_results = {
            "radiusOptimizations": [
                {
                    "storeId": "FC_RED_BIRD",
                    "currentRadius": 25,
                    "recommendedRadius": 20,
                    "expectedImpact": {"costReduction": 12.0},
                },
                {
                    "storeId": "FC_PLANO",
                    "currentRadius": 15,
                    "recommendedRadius": 12,
                    "expectedImpact": {"costReduction": 8.0},
                },
            ],
            "bidAdjustments": [
                {
                    "locationId": "dallas_tx",
                    "recommendedBidAdjustment": 15.0,
                    "priority": "high",
                },
                {
                    "locationId": "plano_tx",
                    "recommendedBidAdjustment": -5.0,
                    "priority": "medium",
                },
            ],
            "storePerformanceAnalysis": [
                {"storeId": store["store_id"], "overallScore": 0.8}
                for store in fitness_connection_store_data
            ],
            "crossLocationAnalysis": [],
            "locationExclusions": [],
            "competitiveInsights": [],
            "seasonalAdjustments": [],
        }

        geo_result = geo_engine.process_results(mock_geo_results)
        assert geo_result["status"] == ScriptStatus.COMPLETED.value
        assert geo_result["changes_made"] > 0

        # Step 5: Generate keyword expansion opportunities
        base_keywords = [
            "gym",
            "fitness center",
            "workout",
            "exercise",
            "personal training",
            "group fitness",
            "cardio",
            "strength training",
            "yoga classes",
        ]

        keyword_opportunities = keyword_engine.generate_keyword_opportunities(
            base_keywords, keyword_engine.store_locations
        )

        # Should generate many opportunities
        assert len(keyword_opportunities) >= 20

        # Should have different types of expansions
        expansion_types = {opp.expansion_type.value for opp in keyword_opportunities}
        assert "geographic_modifier" in expansion_types
        assert "distance_modifier" in expansion_types

        # Step 6: Test cross-engine consistency
        # Locations detected by intent engine should match geographic engine targets
        detected_cities = set()
        for result in local_intent_results:
            if result["geographic_modifier"]:
                detected_cities.add(result["geographic_modifier"].lower())

        store_cities = {
            store["city"].lower() for store in fitness_connection_store_data
        }

        # Should have significant overlap
        city_overlap = detected_cities.intersection(store_cities)
        assert len(city_overlap) >= 2

        # Step 7: Test landing page recommendations consistency
        dallas_results = [
            r for r in local_intent_results if "dallas" in r["search_term"]
        ]
        if dallas_results:
            dallas_stores = [
                s for s in fitness_connection_store_data if s["city"] == "Dallas"
            ]
            if dallas_stores:
                expected_landing_page = dallas_stores[0]["landing_page"]
                # Local intent detection should recommend Dallas landing page
                dallas_intent = local_intent_engine.detect_local_intent("gym dallas")
                if dallas_intent and dallas_intent.landing_page_recommendation:
                    assert (
                        expected_landing_page
                        in dallas_intent.landing_page_recommendation
                    )

    def test_script_executor_integration(
        self, mock_google_ads_client, fitness_connection_store_data
    ):
        """Test integration with ScriptExecutor for coordinated execution."""
        # Create script executor with rate limiting
        rate_limiter = RateLimiter(
            calls_per_second=0.5, calls_per_minute=20
        )  # Conservative for testing
        executor = ScriptExecutor(mock_google_ads_client, rate_limiter)

        # Create and register all scripts
        local_intent_config = create_local_intent_config(
            store_locations=fitness_connection_store_data,
            lookback_days=7,  # Shorter for testing
            min_impressions=50,
        )
        local_intent_script = LocalIntentDetectionEngine(
            mock_google_ads_client, local_intent_config
        )

        geo_config = create_geographic_optimization_config(
            store_locations=fitness_connection_store_data,
            lookback_days=7,
            min_impressions=50,
        )
        geo_script = GeographicOptimizationEngine(mock_google_ads_client, geo_config)

        keyword_config = create_local_keyword_expansion_config(
            store_locations=fitness_connection_store_data,
            lookback_days=7,
            min_impressions=50,
        )
        keyword_script = LocalKeywordExpansionEngine(
            mock_google_ads_client, keyword_config
        )

        # Register scripts
        local_intent_id = executor.register_script(local_intent_script)
        geo_id = executor.register_script(geo_script)
        keyword_id = executor.register_script(keyword_script)

        # Execute scripts in sequence
        results = {}

        # Execute local intent detection first
        results["local_intent"] = executor.execute_script(local_intent_id)
        assert results["local_intent"]["status"] == ScriptStatus.COMPLETED.value

        # Execute geographic optimization
        results["geographic"] = executor.execute_script(geo_id)
        assert results["geographic"]["status"] == ScriptStatus.COMPLETED.value

        # Execute keyword expansion
        results["keyword_expansion"] = executor.execute_script(keyword_id)
        assert results["keyword_expansion"]["status"] == ScriptStatus.COMPLETED.value

        # Verify all executions completed successfully
        for script_name, result in results.items():
            assert result["status"] == ScriptStatus.COMPLETED.value
            assert result["execution_time"] > 0
            assert len(result["errors"]) == 0

    def test_real_world_search_term_analysis(
        self, mock_google_ads_client, fitness_connection_store_data
    ):
        """Test with realistic search terms from Fitness Connection data."""
        local_intent_engine = LocalIntentDetectionEngine(
            mock_google_ads_client,
            create_local_intent_config(store_locations=fitness_connection_store_data),
        )

        # Real-world search terms that should be detected
        high_intent_terms = [
            "fitness connection near me",
            "gym dallas red bird",
            "fitness center san antonio blanco",
            "24 hour gym plano legacy",
            "workout classes near me dallas",
            "personal training san antonio",
            "gym membership plano texas",
        ]

        detected_intents = []
        for term in high_intent_terms:
            intent_match = local_intent_engine.detect_local_intent(term)
            if intent_match:
                detected_intents.append(
                    {
                        "term": term,
                        "intent_type": intent_match.intent_type.value,
                        "confidence": intent_match.confidence_score,
                        "stores_matched": len(intent_match.matched_stores),
                        "bid_adjustment": intent_match.suggested_bid_adjustment,
                    }
                )

        # Should detect intent in most terms
        assert len(detected_intents) >= 6

        # Check specific patterns
        near_me_detections = [
            d for d in detected_intents if d["intent_type"] == "near_me"
        ]
        assert len(near_me_detections) >= 2

        city_detections = [
            d for d in detected_intents if d["intent_type"] == "city_specific"
        ]
        assert len(city_detections) >= 3

        # All detections should have reasonable confidence
        for detection in detected_intents:
            assert detection["confidence"] >= 0.7
            assert detection["bid_adjustment"] > 0
            assert detection["stores_matched"] > 0

    def test_performance_optimization_recommendations(
        self,
        mock_google_ads_client,
        fitness_connection_store_data,
        sample_performance_data,
    ):
        """Test performance-based optimization recommendations."""
        geo_engine = GeographicOptimizationEngine(
            mock_google_ads_client,
            create_geographic_optimization_config(
                store_locations=fitness_connection_store_data
            ),
        )

        # Mock results based on performance data
        mock_results = {
            "radiusOptimizations": [],
            "bidAdjustments": [],
            "locationExclusions": [],
            "storePerformanceAnalysis": [],
            "competitiveInsights": [],
            "seasonalAdjustments": [],
            "crossLocationAnalysis": [],
        }

        # Generate bid adjustments based on performance
        for location, perf in sample_performance_data.items():
            if perf["cpc"] > 3.0:  # High CPC locations
                mock_results["bidAdjustments"].append(
                    {
                        "locationId": location,
                        "recommendedBidAdjustment": -10.0,  # Reduce bids
                        "priority": "high",
                        "reason": f"High CPC (${perf['cpc']:.2f})",
                    }
                )
            elif perf["conversion_rate"] > 12.0:  # High performing locations
                mock_results["bidAdjustments"].append(
                    {
                        "locationId": location,
                        "recommendedBidAdjustment": 15.0,  # Increase bids
                        "priority": "medium",
                        "reason": f"High conversion rate ({perf['conversion_rate']:.1f}%)",
                    }
                )

        # Process results
        result = geo_engine.process_results(mock_results)

        assert result["status"] == ScriptStatus.COMPLETED.value
        assert result["details"]["bid_optimization"]["total_bid_adjustments"] >= 2

        # Should identify Dallas as high-performing (high conversion rate)
        # Should identify Plano as high-cost (high CPC)
        bid_details = result["details"]["bid_optimization"]
        assert bid_details["total_bid_adjustments"] >= 2

    def test_keyword_expansion_market_coverage(
        self, mock_google_ads_client, fitness_connection_store_data
    ):
        """Test keyword expansion covers all market areas."""
        keyword_engine = LocalKeywordExpansionEngine(
            mock_google_ads_client,
            create_local_keyword_expansion_config(
                store_locations=fitness_connection_store_data
            ),
        )

        base_keywords = ["gym", "fitness", "workout"]
        opportunities = keyword_engine.generate_keyword_opportunities(
            base_keywords, keyword_engine.store_locations
        )

        # Should generate opportunities for all store cities
        store_cities = {
            store["city"].lower() for store in fitness_connection_store_data
        }

        # Extract cities mentioned in expanded keywords
        mentioned_cities = set()
        for opp in opportunities:
            keyword_lower = opp.expanded_keyword.lower()
            for city in store_cities:
                if city in keyword_lower:
                    mentioned_cities.add(city)

        # Should cover most store cities
        coverage = len(mentioned_cities) / len(store_cities)
        assert coverage >= 0.6  # At least 60% city coverage

        # Should have proximity-based expansions for all stores
        near_me_opportunities = [
            opp for opp in opportunities if "near me" in opp.expanded_keyword
        ]
        assert len(near_me_opportunities) >= len(
            base_keywords
        )  # At least one per base keyword

    def test_cross_engine_data_consistency(
        self, mock_google_ads_client, fitness_connection_store_data
    ):
        """Test data consistency across all engines."""
        # Create all engines with same store data
        configs = {
            "local_intent": create_local_intent_config(
                store_locations=fitness_connection_store_data
            ),
            "geographic": create_geographic_optimization_config(
                store_locations=fitness_connection_store_data
            ),
            "keyword_expansion": create_local_keyword_expansion_config(
                store_locations=fitness_connection_store_data
            ),
        }

        engines = {
            "local_intent": LocalIntentDetectionEngine(
                mock_google_ads_client, configs["local_intent"]
            ),
            "geographic": GeographicOptimizationEngine(
                mock_google_ads_client, configs["geographic"]
            ),
            "keyword_expansion": LocalKeywordExpansionEngine(
                mock_google_ads_client, configs["keyword_expansion"]
            ),
        }

        # Check store data consistency
        for engine_name, engine in engines.items():
            assert len(engine.store_locations) == len(fitness_connection_store_data)

            # Check store IDs match
            engine_store_ids = {store.store_id for store in engine.store_locations}
            expected_store_ids = {
                store["store_id"] for store in fitness_connection_store_data
            }
            assert engine_store_ids == expected_store_ids

            # Check cities match
            engine_cities = {store.city for store in engine.store_locations}
            expected_cities = {store["city"] for store in fitness_connection_store_data}
            assert engine_cities == expected_cities

    def test_script_generation_integration(
        self, mock_google_ads_client, fitness_connection_store_data
    ):
        """Test that generated scripts contain consistent data."""
        engines = {
            "local_intent": LocalIntentDetectionEngine(
                mock_google_ads_client,
                create_local_intent_config(
                    store_locations=fitness_connection_store_data
                ),
            ),
            "geographic": GeographicOptimizationEngine(
                mock_google_ads_client,
                create_geographic_optimization_config(
                    store_locations=fitness_connection_store_data
                ),
            ),
            "keyword_expansion": LocalKeywordExpansionEngine(
                mock_google_ads_client,
                create_local_keyword_expansion_config(
                    store_locations=fitness_connection_store_data
                ),
            ),
        }

        scripts = {}
        for name, engine in engines.items():
            scripts[name] = engine.generate_script()

        # All scripts should contain store data
        for script_name, script_content in scripts.items():
            # Should contain main function
            assert "function main()" in script_content

            # Should contain store information
            for store in fitness_connection_store_data:
                store_name_parts = store["name"].split()
                # Should contain at least part of store name
                assert any(part in script_content for part in store_name_parts)

        # Scripts should contain different optimization logic
        assert "analyzeLocalIntentTerms" in scripts["local_intent"]
        assert "analyzeRadiusPerformance" in scripts["geographic"]
        assert "generateLocalKeywordExpansions" in scripts["keyword_expansion"]


if __name__ == "__main__":
    pytest.main([__file__])
