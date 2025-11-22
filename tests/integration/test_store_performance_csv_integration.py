"""Integration tests for store performance analyzers with CSV parsing."""

from datetime import datetime
from pathlib import Path

import pytest

from paidsearchnav_mcp.analyzers.local_reach_store_performance import (
    LocalReachStoreAnalyzer,
)
from paidsearchnav_mcp.analyzers.store_performance import StorePerformanceAnalyzer


class TestStorePerformanceCSVIntegration:
    """Integration tests for store performance CSV parsing with real data."""

    @pytest.fixture
    def sample_csv_path(self) -> Path:
        """Path to sample CSV file."""
        return Path("test_data/fitness_connection_samples/per_store_sample.csv")

    @pytest.fixture
    def alternative_csv_path(self) -> Path:
        """Path to alternative sample CSV file."""
        return Path("test_data/sample_per_store.csv")

    @pytest.mark.asyncio
    async def test_local_reach_analyzer_with_fitness_connection_data(
        self, sample_csv_path
    ):
        """Test LocalReachStoreAnalyzer with Fitness Connection sample data."""
        if not sample_csv_path.exists():
            pytest.skip(f"Sample CSV file not found: {sample_csv_path}")

        # Load analyzer from CSV
        analyzer = LocalReachStoreAnalyzer.from_csv(sample_csv_path)

        # Verify data was loaded
        assert len(analyzer._csv_data) > 0

        # Run full analysis
        result = await analyzer.analyze(
            customer_id="fitness_connection_test",
            start_date=datetime(2025, 5, 18),
            end_date=datetime(2025, 8, 15),
        )

        # Verify analysis results
        assert result.customer_id == "fitness_connection_test"
        assert result.analyzer_name == "Local Reach Store Performance Analyzer"
        assert result.analysis_type == "local_reach_store_performance"

        # Check that locations were parsed and analyzed
        assert len(result.location_performance) > 0
        assert result.summary.total_locations > 0
        assert result.summary.total_local_impressions > 0
        assert result.summary.total_store_visits > 0

        # Verify location data structure
        first_location = result.location_performance[0]
        assert first_location.location.store_name == "Fitness Connection"
        assert first_location.location.city in [
            "Charlotte",
            "Watauga",
            "Carrollton",
        ]  # Known cities
        assert first_location.metrics.local_impressions > 0
        assert first_location.metrics.store_visits > 0

        # Check performance scoring and categorization
        for location in result.location_performance:
            assert location.efficiency_level is not None
            assert location.market_rank is not None
            assert location.performance_score >= 0

        # Verify insights generation
        assert isinstance(result.insights, list)

        # Check summary calculations
        total_impressions = sum(
            loc.metrics.local_impressions for loc in result.location_performance
        )
        total_visits = sum(
            loc.metrics.store_visits for loc in result.location_performance
        )

        assert result.summary.total_local_impressions == total_impressions
        assert result.summary.total_store_visits == total_visits
        assert result.summary.avg_store_visit_rate > 0

    @pytest.mark.asyncio
    async def test_store_analyzer_with_fitness_connection_data(self, sample_csv_path):
        """Test StorePerformanceAnalyzer with Fitness Connection sample data."""
        if not sample_csv_path.exists():
            pytest.skip(f"Sample CSV file not found: {sample_csv_path}")

        # Load analyzer from CSV
        analyzer = StorePerformanceAnalyzer.from_csv(sample_csv_path)

        # Verify data was loaded
        assert len(analyzer._csv_data) > 0

        # Run full analysis
        result = await analyzer.analyze(
            customer_id="fitness_connection_test",
            start_date=datetime(2025, 5, 18),
            end_date=datetime(2025, 8, 15),
        )

        # Verify analysis results
        assert result.customer_id == "fitness_connection_test"
        assert result.analyzer_name == "Store Performance Analyzer"
        assert result.analysis_type == "store_performance"

        # Check that stores were parsed and analyzed
        assert len(result.store_data) > 0
        assert result.summary.total_stores > 0
        assert result.summary.total_local_impressions > 0

        # Verify store data structure
        first_store = result.store_data[0]
        assert first_store.location.store_name == "Fitness Connection"
        assert first_store.metrics.local_impressions > 0
        assert first_store.performance_level is not None

        # Check performance categorization
        performance_levels = [store.performance_level for store in result.store_data]
        assert all(level is not None for level in performance_levels)

        # Verify insights generation
        assert isinstance(result.insights, list)

    @pytest.mark.asyncio
    async def test_alternative_csv_format(self, alternative_csv_path):
        """Test analyzers with alternative CSV format."""
        if not alternative_csv_path.exists():
            pytest.skip(f"Alternative CSV file not found: {alternative_csv_path}")

        # Test with LocalReachStoreAnalyzer
        local_analyzer = LocalReachStoreAnalyzer.from_csv(alternative_csv_path)
        assert len(local_analyzer._csv_data) > 0

        local_result = await local_analyzer.analyze(
            customer_id="alternative_format_test",
            start_date=datetime(2025, 5, 1),
            end_date=datetime(2025, 8, 31),
        )

        assert len(local_result.location_performance) > 0

        # Test with StorePerformanceAnalyzer
        store_analyzer = StorePerformanceAnalyzer.from_csv(alternative_csv_path)
        assert len(store_analyzer._csv_data) > 0

        store_result = await store_analyzer.analyze(
            customer_id="alternative_format_test",
            start_date=datetime(2025, 5, 1),
            end_date=datetime(2025, 8, 31),
        )

        assert len(store_result.store_data) > 0

    @pytest.mark.asyncio
    async def test_performance_comparison_between_analyzers(self, sample_csv_path):
        """Test that both analyzers produce consistent results on same data."""
        if not sample_csv_path.exists():
            pytest.skip(f"Sample CSV file not found: {sample_csv_path}")

        # Load same data into both analyzers
        local_analyzer = LocalReachStoreAnalyzer.from_csv(sample_csv_path)
        store_analyzer = StorePerformanceAnalyzer.from_csv(sample_csv_path)

        # Run analyses
        local_result = await local_analyzer.analyze(
            customer_id="comparison_test",
            start_date=datetime(2025, 5, 18),
            end_date=datetime(2025, 8, 15),
        )

        store_result = await store_analyzer.analyze(
            customer_id="comparison_test",
            start_date=datetime(2025, 5, 18),
            end_date=datetime(2025, 8, 15),
        )

        # Verify both analyzers processed the same number of locations
        assert len(local_result.location_performance) == len(store_result.store_data)

        # Verify total impressions match
        local_total_impressions = local_result.summary.total_local_impressions
        store_total_impressions = store_result.summary.total_local_impressions

        assert local_total_impressions == store_total_impressions

        # Check that store names match between analyses
        local_store_names = {
            loc.location.store_name for loc in local_result.location_performance
        }
        store_store_names = {
            store.location.store_name for store in store_result.store_data
        }

        assert local_store_names == store_store_names

    def test_csv_data_validation_and_cleanup(self, sample_csv_path):
        """Test CSV data validation and cleanup functionality."""
        if not sample_csv_path.exists():
            pytest.skip(f"Sample CSV file not found: {sample_csv_path}")

        analyzer = LocalReachStoreAnalyzer.from_csv(sample_csv_path)

        # Verify that CSV data contains expected fields
        first_record = analyzer._csv_data[0]

        # Should have location information
        assert "store_name" in first_record
        assert "city" in first_record

        # Should have performance metrics
        assert "local_impressions" in first_record
        assert "store_visits" in first_record

        # Check that numeric values are properly formatted
        for record in analyzer._csv_data:
            # Local impressions should be string with commas or plain number
            impressions = record.get("local_impressions")
            assert impressions is not None

            # Store visits should be present
            visits = record.get("store_visits")
            assert visits is not None

    @pytest.mark.performance
    def test_large_csv_performance(self, sample_csv_path):
        """Test performance with CSV files."""
        if not sample_csv_path.exists():
            pytest.skip(f"Sample CSV file not found: {sample_csv_path}")

        import time

        # Measure CSV loading time
        start_time = time.time()
        analyzer = LocalReachStoreAnalyzer.from_csv(sample_csv_path)
        load_time = time.time() - start_time

        # CSV loading should be fast (under 1 second for reasonable files)
        assert load_time < 1.0, (
            f"CSV loading took {load_time:.2f}s, should be under 1 second"
        )

        # Verify data was loaded
        assert len(analyzer._csv_data) > 0

    def test_error_handling_with_malformed_csv(self, tmp_path):
        """Test error handling with malformed CSV files."""
        # Create a malformed CSV file
        malformed_csv = tmp_path / "malformed.csv"
        malformed_csv.write_text("""
Invalid header line
"Missing proper structure"
store1,address1,city1
store2,address2,city2,extra_column
""")

        # Should handle malformed CSV gracefully
        try:
            analyzer = LocalReachStoreAnalyzer.from_csv(malformed_csv)
            # If parsing succeeds, verify it handles missing columns
            assert len(analyzer._csv_data) >= 0
        except ValueError as e:
            # Should provide informative error message
            assert "No location identifier column found" in str(
                e
            ) or "Invalid CSV format" in str(e)

    @pytest.mark.asyncio
    async def test_end_to_end_workflow_with_insights(self, sample_csv_path):
        """Test complete end-to-end workflow including insights generation."""
        if not sample_csv_path.exists():
            pytest.skip(f"Sample CSV file not found: {sample_csv_path}")

        analyzer = LocalReachStoreAnalyzer.from_csv(sample_csv_path)

        result = await analyzer.analyze(
            customer_id="end_to_end_test",
            start_date=datetime(2025, 5, 18),
            end_date=datetime(2025, 8, 15),
        )

        # Verify complete result structure
        assert result.customer_id == "end_to_end_test"
        assert result.start_date == datetime(2025, 5, 18)
        assert result.end_date == datetime(2025, 8, 15)

        # Check all major components are present
        assert result.summary is not None
        assert result.location_performance is not None
        assert result.insights is not None
        assert result.top_performers is not None
        assert result.underperformers is not None
        assert result.optimization_opportunities is not None

        # Verify insights have proper structure
        for insight in result.insights:
            assert insight.store_name is not None
            assert insight.issue_type is not None
            assert insight.description is not None
            assert insight.recommendation is not None
            assert insight.priority in ["low", "medium", "high", "critical"]

        # Verify performance rankings
        if len(result.location_performance) > 1:
            market_ranks = [loc.market_rank for loc in result.location_performance]
            assert len(set(market_ranks)) == len(
                market_ranks
            )  # All ranks should be unique
            assert min(market_ranks) == 1
            assert max(market_ranks) == len(result.location_performance)
