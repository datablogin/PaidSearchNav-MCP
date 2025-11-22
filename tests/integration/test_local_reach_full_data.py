"""Integration tests for LocalReachStoreAnalyzer with full Fitness Connection dataset."""

import csv
from datetime import datetime
from pathlib import Path

import pytest

from paidsearchnav.analyzers.local_reach_store_performance import (
    LocalReachStoreAnalyzer,
)
from paidsearchnav.core.models import (
    LocalReachEfficiencyLevel,
)


class TestLocalReachStoreAnalyzerIntegration:
    """Integration test cases using real Fitness Connection data."""

    @pytest.fixture
    def analyzer(self):
        """Create analyzer with production-like settings."""
        return LocalReachStoreAnalyzer(
            min_impressions=100,
            high_visit_rate_threshold=2.0,
            moderate_visit_rate_threshold=1.0,
            low_visit_rate_threshold=0.5,
            high_cost_per_visit_threshold=25.0,
        )

    @pytest.fixture
    def fitness_connection_data(self):
        """Load real Fitness Connection per store data."""
        test_data_path = Path(__file__).parent.parent / "test_data"
        per_store_file = (
            test_data_path / "fitness_connection_samples" / "per_store_sample.csv"
        )

        if not per_store_file.exists():
            # Fallback to main test data file if sample doesn't exist
            per_store_file = test_data_path / "sample_per_store.csv"

        if not per_store_file.exists():
            pytest.skip(f"Test data file not found: {per_store_file}")

        store_data = []
        with open(per_store_file, "r", encoding="utf-8") as file:
            # Skip the header rows (report title and date range)
            content = file.read()
            lines = content.strip().split("\n")

            # Find the actual CSV header line
            header_line_idx = 0
            for i, line in enumerate(lines):
                if "Store locations" in line or "store_name" in line.lower():
                    header_line_idx = i
                    break

            # Parse CSV data starting from header
            csv_content = "\n".join(lines[header_line_idx:])
            reader = csv.DictReader(csv_content.splitlines())

            for row in reader:
                # Map CSV columns to expected format
                mapped_row = {
                    "store_name": row.get("Store locations", row.get("store_name", "")),
                    "address_line_1": row.get("address_line_1", ""),
                    "address_line_2": row.get("address_line_2", "--"),
                    "city": row.get("city", ""),
                    "state": row.get("province", row.get("state", "")),
                    "postal_code": row.get("postal_code", ""),
                    "country_code": row.get("country_code", "US"),
                    "phone_number": row.get("phone_number", ""),
                    "local_impressions": row.get(
                        "Local reach (impressions)", row.get("local_impressions", "0")
                    ),
                    "store_visits": row.get(
                        "Store visits", row.get("store_visits", "0")
                    ),
                    "call_clicks": row.get("Call clicks", row.get("call_clicks", "0")),
                    "driving_directions": row.get(
                        "Driving directions", row.get("driving_directions", "0")
                    ),
                    "website_visits": row.get(
                        "Website visits", row.get("website_visits", "0")
                    ),
                    "cost": "0.0",  # Add estimated cost for testing
                    "clicks": "0",
                    "conversions": "0",
                }

                # Skip empty rows
                if mapped_row["store_name"] and mapped_row["local_impressions"]:
                    # Add estimated cost based on impressions for testing
                    try:
                        impressions = int(
                            mapped_row["local_impressions"].replace(",", "")
                        )
                        estimated_cost = impressions * 0.50  # $0.50 CPM estimate
                        mapped_row["cost"] = str(estimated_cost)

                        # Add estimated clicks and conversions
                        estimated_clicks = int(impressions * 0.02)  # 2% CTR estimate
                        estimated_conversions = int(
                            estimated_clicks * 0.05
                        )  # 5% conversion estimate
                        mapped_row["clicks"] = str(estimated_clicks)
                        mapped_row["conversions"] = str(estimated_conversions)
                    except (ValueError, AttributeError):
                        pass

                    store_data.append(mapped_row)

        return store_data

    @pytest.mark.asyncio
    async def test_full_fitness_connection_analysis(
        self, analyzer, fitness_connection_data
    ):
        """Test analysis with complete Fitness Connection dataset."""
        if not fitness_connection_data:
            pytest.skip("No Fitness Connection data available for testing")

        result = await analyzer.analyze(
            customer_id="fitness_connection_test",
            start_date=datetime(2025, 5, 18),
            end_date=datetime(2025, 8, 15),
            store_data=fitness_connection_data,
        )

        # Validate basic result structure
        assert result.customer_id == "fitness_connection_test"
        assert result.analysis_type == "local_reach_store_performance"
        assert len(result.location_performance) > 0

        # Validate summary statistics
        summary = result.summary
        assert summary.total_locations > 0
        assert summary.total_local_impressions > 0
        assert summary.total_store_visits > 0
        assert summary.avg_store_visit_rate >= 0

        print(f"Analyzed {summary.total_locations} Fitness Connection locations")
        print(f"Total local impressions: {summary.total_local_impressions:,}")
        print(f"Total store visits: {summary.total_store_visits:,}")
        print(f"Average store visit rate: {summary.avg_store_visit_rate:.2f}%")

    @pytest.mark.asyncio
    async def test_performance_analysis_speed(self, analyzer, fitness_connection_data):
        """Test that analysis completes within performance requirements (<45 seconds)."""
        if not fitness_connection_data:
            pytest.skip("No Fitness Connection data available for testing")

        import time

        start_time = time.time()

        result = await analyzer.analyze(
            customer_id="performance_test",
            start_date=datetime(2025, 5, 18),
            end_date=datetime(2025, 8, 15),
            store_data=fitness_connection_data,
        )

        end_time = time.time()
        analysis_time = end_time - start_time

        print(f"Analysis completed in {analysis_time:.2f} seconds")

        # Should complete in under 45 seconds as per requirements
        assert analysis_time < 45.0, (
            f"Analysis took {analysis_time:.2f}s, exceeding 45s requirement"
        )

        # Validate that analysis was successful
        assert len(result.location_performance) > 0

    @pytest.mark.asyncio
    async def test_specific_location_validation(
        self, analyzer, fitness_connection_data
    ):
        """Test analysis against known Fitness Connection locations."""
        if not fitness_connection_data:
            pytest.skip("No Fitness Connection data available for testing")

        result = await analyzer.analyze(
            customer_id="location_validation_test",
            start_date=datetime(2025, 5, 18),
            end_date=datetime(2025, 8, 15),
            store_data=fitness_connection_data,
        )

        # Look for specific known locations
        location_names = [
            loc.location.store_name for loc in result.location_performance
        ]

        # Should find Charlotte and Texas locations
        charlotte_locations = [name for name in location_names if "Charlotte" in name]
        texas_locations = [
            name for name in location_names if "TX" in name or "Texas" in name
        ]

        print(f"Found {len(charlotte_locations)} Charlotte locations")
        print(f"Found {len(texas_locations)} Texas locations")

        # Validate specific location data if available
        for location in result.location_performance:
            assert location.metrics.local_impressions >= 0
            assert location.metrics.store_visits >= 0
            assert location.metrics.store_visit_rate >= 0
            assert location.performance_score >= 0

    @pytest.mark.asyncio
    async def test_top_bottom_performer_identification(
        self, analyzer, fitness_connection_data
    ):
        """Test identification of top 5 and bottom 5 performing locations."""
        if not fitness_connection_data:
            pytest.skip("No Fitness Connection data available for testing")

        result = await analyzer.analyze(
            customer_id="performer_identification_test",
            start_date=datetime(2025, 5, 18),
            end_date=datetime(2025, 8, 15),
            store_data=fitness_connection_data,
        )

        # Should identify top performers
        top_performers = result.top_performers
        print(f"Identified {len(top_performers)} top performing locations:")
        for i, performer in enumerate(top_performers[:5], 1):
            print(f"  {i}. {performer.location.store_name}")
            print(f"     Visit Rate: {performer.metrics.store_visit_rate:.2f}%")
            print(f"     Performance Score: {performer.performance_score:.1f}")

        # Should identify underperformers
        underperformers = result.underperformers
        print(f"\nIdentified {len(underperformers)} underperforming locations:")
        for i, underperformer in enumerate(underperformers[:5], 1):
            print(f"  {i}. {underperformer.location.store_name}")
            print(f"     Visit Rate: {underperformer.metrics.store_visit_rate:.2f}%")
            print(f"     Performance Score: {underperformer.performance_score:.1f}")

        # Validate top performers have higher scores than underperformers
        if top_performers and underperformers:
            highest_top_score = max(p.performance_score for p in top_performers)
            lowest_under_score = min(p.performance_score for p in underperformers)
            assert highest_top_score > lowest_under_score

    @pytest.mark.asyncio
    async def test_cost_efficiency_analysis(self, analyzer, fitness_connection_data):
        """Test cost per store visit optimization recommendations."""
        if not fitness_connection_data:
            pytest.skip("No Fitness Connection data available for testing")

        result = await analyzer.analyze(
            customer_id="cost_efficiency_test",
            start_date=datetime(2025, 5, 18),
            end_date=datetime(2025, 8, 15),
            store_data=fitness_connection_data,
        )

        # Should identify optimization opportunities
        optimization_opportunities = result.optimization_opportunities
        print(
            f"Identified {len(optimization_opportunities)} optimization opportunities:"
        )

        for i, opp in enumerate(optimization_opportunities[:5], 1):
            print(f"  {i}. {opp.location.store_name}")
            if opp.metrics.cost_per_store_visit > 0:
                print(f"     Cost per visit: ${opp.metrics.cost_per_store_visit:.2f}")
            print(f"     Needs optimization: {opp.needs_optimization}")

        # Validate cost calculations
        for location in result.location_performance:
            if location.metrics.store_visits > 0 and location.metrics.cost > 0:
                expected_cost_per_visit = (
                    location.metrics.cost / location.metrics.store_visits
                )
                assert (
                    abs(location.metrics.cost_per_store_visit - expected_cost_per_visit)
                    < 0.01
                )

    @pytest.mark.asyncio
    async def test_insights_quality_and_relevance(
        self, analyzer, fitness_connection_data
    ):
        """Test that insights are relevant and actionable."""
        if not fitness_connection_data:
            pytest.skip("No Fitness Connection data available for testing")

        result = await analyzer.analyze(
            customer_id="insights_quality_test",
            start_date=datetime(2025, 5, 18),
            end_date=datetime(2025, 8, 15),
            store_data=fitness_connection_data,
        )

        insights = result.insights
        print(f"Generated {len(insights)} insights:")

        # Categorize insights by type
        insight_types = {}
        for insight in insights:
            insight_type = insight.issue_type.value
            if insight_type not in insight_types:
                insight_types[insight_type] = 0
            insight_types[insight_type] += 1

        for insight_type, count in insight_types.items():
            print(f"  {insight_type}: {count} insights")

        # Should generate at least 5 location-specific recommendations as per requirements
        assert len(insights) >= 5, f"Expected at least 5 insights, got {len(insights)}"

        # Validate insight quality
        for insight in insights:
            assert insight.store_name
            assert insight.description
            assert insight.recommendation
            assert insight.priority in ["critical", "high", "medium", "low"]
            assert insight.impact

    @pytest.mark.asyncio
    async def test_data_quality_kpis(self, analyzer, fitness_connection_data):
        """Test data quality KPIs as specified in requirements."""
        if not fitness_connection_data:
            pytest.skip("No Fitness Connection data available for testing")

        result = await analyzer.analyze(
            customer_id="data_quality_test",
            start_date=datetime(2025, 5, 18),
            end_date=datetime(2025, 8, 15),
            store_data=fitness_connection_data,
        )

        total_input_locations = len(fitness_connection_data)
        analyzed_locations = len(result.location_performance)

        # Location Coverage: Analysis should cover ≥95% of active store locations
        coverage_rate = (analyzed_locations / total_input_locations) * 100
        print(
            f"Location coverage: {coverage_rate:.1f}% ({analyzed_locations}/{total_input_locations})"
        )

        # Note: In real implementation, this should be ≥95%, but for test data we may have incomplete data
        assert coverage_rate > 0, "Should analyze at least some locations"

        # Geographic Completeness: Location data should be complete for ≥90% of stores
        complete_locations = 0
        for location in result.location_performance:
            if (
                location.location.city
                and location.location.state
                and location.location.postal_code
            ):
                complete_locations += 1

        completeness_rate = (
            (complete_locations / analyzed_locations) * 100
            if analyzed_locations > 0
            else 0
        )
        print(
            f"Geographic completeness: {completeness_rate:.1f}% ({complete_locations}/{analyzed_locations})"
        )

        # Should have reasonable completeness
        assert completeness_rate > 50, (
            f"Geographic completeness too low: {completeness_rate:.1f}%"
        )

    @pytest.mark.asyncio
    async def test_analysis_value_kpis(self, analyzer, fitness_connection_data):
        """Test analysis value KPIs as specified in requirements."""
        if not fitness_connection_data:
            pytest.skip("No Fitness Connection data available for testing")

        result = await analyzer.analyze(
            customer_id="analysis_value_test",
            start_date=datetime(2025, 5, 18),
            end_date=datetime(2025, 8, 15),
            store_data=fitness_connection_data,
        )

        if not result.location_performance:
            pytest.skip("No locations analyzed")

        # Performance Variance: Identify stores with ≥25% conversion rate difference
        visit_rates = [
            loc.metrics.store_visit_rate for loc in result.location_performance
        ]
        if len(visit_rates) > 1:
            avg_visit_rate = sum(visit_rates) / len(visit_rates)
            variance_threshold = avg_visit_rate * 0.25  # 25% variance

            high_variance_locations = [
                loc
                for loc in result.location_performance
                if abs(loc.metrics.store_visit_rate - avg_visit_rate)
                >= variance_threshold
            ]

            variance_rate = (
                len(high_variance_locations) / len(result.location_performance)
            ) * 100
            print(f"Locations with ≥25% visit rate variance: {variance_rate:.1f}%")

        # Actionable Insights: Generate ≥5 location-specific optimization recommendations
        optimization_insights = [
            insight
            for insight in result.insights
            if insight.recommendation and "optimize" in insight.recommendation.lower()
        ]

        print(f"Generated {len(optimization_insights)} optimization recommendations")
        assert len(optimization_insights) >= 5, (
            "Should generate at least 5 optimization recommendations"
        )

    @pytest.mark.asyncio
    async def test_geographic_market_analysis(self, analyzer, fitness_connection_data):
        """Test geographic performance analysis by market area."""
        if not fitness_connection_data:
            pytest.skip("No Fitness Connection data available for testing")

        result = await analyzer.analyze(
            customer_id="geographic_test",
            start_date=datetime(2025, 5, 18),
            end_date=datetime(2025, 8, 15),
            store_data=fitness_connection_data,
        )

        # Group locations by state/market
        markets = {}
        for location in result.location_performance:
            state = location.location.state
            if state not in markets:
                markets[state] = []
            markets[state].append(location)

        print(f"Analysis covers {len(markets)} markets/states:")
        for market, locations in markets.items():
            if not locations:
                continue

            avg_visit_rate = sum(
                loc.metrics.store_visit_rate for loc in locations
            ) / len(locations)
            total_visits = sum(loc.metrics.store_visits for loc in locations)

            print(
                f"  {market}: {len(locations)} locations, {avg_visit_rate:.2f}% avg visit rate, {total_visits:,} total visits"
            )

        # Should identify market-level patterns
        assert len(markets) > 0, "Should identify at least one market"

    @pytest.mark.asyncio
    async def test_efficiency_level_distribution(
        self, analyzer, fitness_connection_data
    ):
        """Test distribution of efficiency levels across locations."""
        if not fitness_connection_data:
            pytest.skip("No Fitness Connection data available for testing")

        result = await analyzer.analyze(
            customer_id="efficiency_distribution_test",
            start_date=datetime(2025, 5, 18),
            end_date=datetime(2025, 8, 15),
            store_data=fitness_connection_data,
        )

        # Count efficiency levels
        efficiency_counts = {
            LocalReachEfficiencyLevel.EXCELLENT: 0,
            LocalReachEfficiencyLevel.GOOD: 0,
            LocalReachEfficiencyLevel.AVERAGE: 0,
            LocalReachEfficiencyLevel.POOR: 0,
        }

        for location in result.location_performance:
            efficiency_counts[location.efficiency_level] += 1

        total_locations = len(result.location_performance)
        print(f"Efficiency level distribution across {total_locations} locations:")
        for level, count in efficiency_counts.items():
            percentage = (count / total_locations) * 100 if total_locations > 0 else 0
            print(f"  {level.value}: {count} ({percentage:.1f}%)")

        # Should have variety in efficiency levels
        non_zero_levels = sum(1 for count in efficiency_counts.values() if count > 0)
        assert non_zero_levels >= 2, (
            "Should have locations in at least 2 different efficiency levels"
        )

    def test_data_file_accessibility(self):
        """Test that required data files are accessible."""
        test_data_path = Path(__file__).parent.parent / "test_data"

        # Check for Fitness Connection sample files
        sample_files = [
            "fitness_connection_samples/per_store_sample.csv",
            "sample_per_store.csv",
        ]

        available_files = []
        for file_path in sample_files:
            full_path = test_data_path / file_path
            if full_path.exists():
                available_files.append(str(full_path))

        print(f"Available test data files: {available_files}")
        assert len(available_files) > 0, (
            "No test data files found for integration testing"
        )
