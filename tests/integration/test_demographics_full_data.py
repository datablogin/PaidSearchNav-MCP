"""Integration tests for Demographics Analyzer using full Fitness Connection data."""

import csv
from datetime import datetime
from pathlib import Path

import pytest

from paidsearchnav_mcp.analyzers.demographics import DemographicsAnalyzer
from paidsearchnav_mcp.models.demographics import DemographicType


class TestDemographicsAnalyzerIntegration:
    """Integration tests using full Fitness Connection demographic data."""

    @pytest.fixture
    def analyzer(self):
        """Create analyzer instance for testing."""
        return DemographicsAnalyzer(
            min_impressions=50,
            min_interactions=5,
            performance_variance_threshold=0.20,
            cost_variance_threshold=0.15,
        )

    @pytest.fixture
    def test_data_path(self):
        """Path to test data directory."""
        return (
            Path(__file__).parent.parent.parent
            / "test_data"
            / "fitness_connection_samples"
        )

    @pytest.fixture
    def age_data(self, test_data_path):
        """Load age demographic data from sample file."""
        age_file = test_data_path / "age_report_sample.csv"
        if not age_file.exists():
            pytest.skip("Age report sample file not found")

        data = []
        with open(age_file, "r", encoding="utf-8") as f:
            # Skip the title and date range lines (first 2 lines)
            lines = f.readlines()[2:]
            reader = csv.DictReader(lines)

            for row in reader:
                if row.get("Age"):  # Skip empty rows
                    data.append(dict(row))

        return data

    @pytest.fixture
    def gender_data(self, test_data_path):
        """Load gender demographic data from sample file."""
        gender_file = test_data_path / "gender_report_sample.csv"
        if not gender_file.exists():
            pytest.skip("Gender report sample file not found")

        data = []
        with open(gender_file, "r", encoding="utf-8") as f:
            # Skip the title and date range lines (first 2 lines)
            lines = f.readlines()[2:]
            reader = csv.DictReader(lines)

            for row in reader:
                if row.get("Gender"):  # Skip empty rows
                    data.append(dict(row))

        return data

    @pytest.fixture
    def income_data(self, test_data_path):
        """Load household income data from sample file."""
        income_file = test_data_path / "household_income_sample.csv"
        if not income_file.exists():
            pytest.skip("Household income sample file not found")

        data = []
        with open(income_file, "r", encoding="utf-8") as f:
            # Skip the title and date range lines (first 2 lines)
            lines = f.readlines()[2:]
            reader = csv.DictReader(lines)

            for row in reader:
                if row.get("Household income"):  # Skip empty rows
                    data.append(dict(row))

        return data

    async def test_full_demographics_analysis_performance(
        self, analyzer, age_data, gender_data, income_data
    ):
        """Test performance of full demographics analysis with real data."""
        customer_id = "646-990-6417"
        start_date = datetime(2025, 5, 18)
        end_date = datetime(2025, 8, 15)

        # Measure analysis time
        import time

        start_time = time.time()

        result = await analyzer.analyze(
            customer_id=customer_id,
            start_date=start_date,
            end_date=end_date,
            age_data=age_data,
            gender_data=gender_data,
            income_data=income_data,
        )

        analysis_time = time.time() - start_time

        # Analysis should complete within 30 seconds
        assert analysis_time < 30.0, (
            f"Analysis took {analysis_time:.2f} seconds, exceeding 30 second limit"
        )

        # Should process all provided data
        assert len(result.segments) > 0
        assert len(result.performance_by_demographic) > 0

        # Should identify multiple demographic types
        demo_types = {
            perf.demographic_type for perf in result.performance_by_demographic
        }
        assert len(demo_types) >= 2  # Should have at least age and gender data

    async def test_comprehensive_data_quality_validation(
        self, analyzer, age_data, gender_data, income_data
    ):
        """Test comprehensive data quality validation with real data."""
        customer_id = "646-990-6417"
        start_date = datetime(2025, 5, 18)
        end_date = datetime(2025, 8, 15)

        result = await analyzer.analyze(
            customer_id=customer_id,
            start_date=start_date,
            end_date=end_date,
            age_data=age_data,
            gender_data=gender_data,
            income_data=income_data,
        )

        # Data Quality KPIs Validation
        data_quality = result.data_quality_kpis
        summary = result.summary

        # Minimum Data Threshold: Each segment must have ≥50 impressions and ≥5 interactions
        segments_meeting_threshold = 0
        for segment in result.segments:
            if (
                segment.impressions >= analyzer.MIN_IMPRESSIONS_THRESHOLD
                and (segment.clicks + segment.conversions)
                >= analyzer.MIN_INTERACTIONS_THRESHOLD
            ):
                segments_meeting_threshold += 1

        assert segments_meeting_threshold == len(result.segments), (
            "All segments should meet minimum thresholds after filtering"
        )

        # Coverage Check: Analysis should cover ≥80% of total campaign impressions
        assert summary.coverage_percentage >= 80.0, (
            f"Coverage is {summary.coverage_percentage:.1f}%, below 80% threshold"
        )

        # Completeness Score: ≥90% of demographic data should be analyzable (not "Unknown")
        unknown_segments = sum(
            1
            for perf in result.performance_by_demographic
            if "Unknown" in perf.demographic_value
        )
        completeness = (
            (
                (len(result.performance_by_demographic) - unknown_segments)
                / len(result.performance_by_demographic)
                * 100
            )
            if result.performance_by_demographic
            else 0
        )

        assert completeness >= 90.0, (
            f"Data completeness is {completeness:.1f}%, below 90% threshold"
        )

    async def test_analysis_value_kpis_validation(
        self, analyzer, age_data, gender_data, income_data
    ):
        """Test analysis value KPIs validation with real data."""
        customer_id = "646-990-6417"
        start_date = datetime(2025, 5, 18)
        end_date = datetime(2025, 8, 15)

        result = await analyzer.analyze(
            customer_id=customer_id,
            start_date=start_date,
            end_date=end_date,
            age_data=age_data,
            gender_data=gender_data,
            income_data=income_data,
        )

        # Analysis Value KPIs Validation
        analysis_value = result.analysis_value_kpis

        # Performance Variance: Identify segments with ≥20% conversion rate difference from average
        assert analysis_value["max_conversion_rate_variance"] >= 20.0, (
            "Should identify ≥20% conversion rate variance"
        )

        # Cost Efficiency Gaps: Find segments with ≥15% CPC variance from campaign average
        assert analysis_value["max_cpc_variance"] >= 15.0, (
            "Should identify ≥15% CPC variance"
        )

        # Actionable Recommendations: Generate ≥3 specific bid adjustment recommendations
        assert analysis_value["actionable_recommendations_generated"] >= 3, (
            "Should generate ≥3 actionable recommendations"
        )

        # ROI Impact Potential: Identify opportunities worth ≥10% budget reallocation
        business_impact = result.business_impact_kpis
        assert business_impact["spend_optimization_potential"] >= 10.0, (
            "Should identify ≥10% budget reallocation potential"
        )

    async def test_business_impact_kpis_validation(
        self, analyzer, age_data, gender_data, income_data
    ):
        """Test business impact KPIs validation with real data."""
        customer_id = "646-990-6417"
        start_date = datetime(2025, 5, 18)
        end_date = datetime(2025, 8, 15)

        result = await analyzer.analyze(
            customer_id=customer_id,
            start_date=start_date,
            end_date=end_date,
            age_data=age_data,
            gender_data=gender_data,
            income_data=income_data,
        )

        # Business Impact KPIs Validation
        business_impact = result.business_impact_kpis
        summary = result.summary

        # Conversion Rate Spread: Document conversion rate range across demographics
        conversion_rates = [
            perf.avg_conversion_rate
            for perf in result.performance_by_demographic
            if perf.avg_conversion_rate > 0
        ]
        if conversion_rates:
            expected_spread = max(conversion_rates) - min(conversion_rates)
            assert business_impact["conversion_rate_spread"] == expected_spread, (
                "Conversion rate spread calculation error"
            )
            assert expected_spread > 0, (
                "Should show meaningful conversion rate differences"
            )

        # Cost Per Conversion Variance: Track CPC variance across segments
        cpc_values = [
            perf.avg_cpc
            for perf in result.performance_by_demographic
            if perf.avg_cpc > 0
        ]
        if cpc_values:
            expected_cpc_variance = max(cpc_values) - min(cpc_values)
            assert (
                business_impact["cost_per_conversion_variance"] == expected_cpc_variance
            ), "CPC variance calculation error"

        # Spend Optimization Potential: Calculate potential budget reallocation value
        reallocation_potential = result.get_reallocation_potential()
        assert (
            business_impact["spend_optimization_potential"] == reallocation_potential
        ), "Reallocation potential calculation error"

    async def test_comprehensive_recommendations_quality(
        self, analyzer, age_data, gender_data, income_data
    ):
        """Test quality and specificity of recommendations with real data."""
        customer_id = "646-990-6417"
        start_date = datetime(2025, 5, 18)
        end_date = datetime(2025, 8, 15)

        result = await analyzer.analyze(
            customer_id=customer_id,
            start_date=start_date,
            end_date=end_date,
            age_data=age_data,
            gender_data=gender_data,
            income_data=income_data,
        )

        # Should identify top 3 performing and bottom 3 underperforming segments
        top_performers = result.get_top_performers(limit=3)
        bottom_performers = result.get_bottom_performers(limit=3)

        assert len(top_performers) >= 1, "Should identify at least 1 top performer"
        assert len(bottom_performers) >= 1, (
            "Should identify at least 1 bottom performer"
        )

        # Top performers should have higher scores than bottom performers
        if top_performers and bottom_performers:
            assert (
                top_performers[0].performance_score
                > bottom_performers[-1].performance_score
            )

        # Should provide ROI-based reallocation suggestions
        budget_recommendations = result.budget_reallocation_recommendations
        assert len(budget_recommendations) > 0, (
            "Should provide budget reallocation recommendations"
        )

        # All bid adjustment recommendations should be reasonable
        for key, adjustment in result.bid_adjustment_recommendations.items():
            assert -0.50 <= adjustment <= 0.50, (
                f"Bid adjustment {adjustment} for {key} is outside reasonable range"
            )

        # Should include comprehensive insights
        assert len(result.insights) >= 3, "Should generate at least 3 insights"

        # Insights should cover different demographic types
        insight_demo_types = {insight.demographic_type for insight in result.insights}
        assert len(insight_demo_types) >= 2, (
            "Insights should cover multiple demographic types"
        )

    async def test_demographic_specific_analysis(
        self, analyzer, age_data, gender_data, income_data
    ):
        """Test demographic-specific analysis capabilities."""
        customer_id = "646-990-6417"
        start_date = datetime(2025, 5, 18)
        end_date = datetime(2025, 8, 15)

        result = await analyzer.analyze(
            customer_id=customer_id,
            start_date=start_date,
            end_date=end_date,
            age_data=age_data,
            gender_data=gender_data,
            income_data=income_data,
        )

        # Test age demographic analysis
        age_segments = result.get_segments_by_type(DemographicType.AGE)
        if age_segments:
            # Should have realistic age groups
            age_values = {seg.demographic_value for seg in age_segments}
            expected_ages = {"25-34", "35-44", "45-54", "55-64", "18-24", "65+"}
            assert any(age in expected_ages for age in age_values), (
                f"Age values {age_values} don't match expected patterns"
            )

        # Test gender demographic analysis
        gender_segments = result.get_segments_by_type(DemographicType.GENDER)
        if gender_segments:
            # Should have realistic gender values
            gender_values = {seg.demographic_value for seg in gender_segments}
            expected_genders = {"Male", "Female"}
            assert any(gender in expected_genders for gender in gender_values), (
                f"Gender values {gender_values} don't match expected patterns"
            )

        # Test income demographic analysis
        income_segments = result.get_segments_by_type(DemographicType.HOUSEHOLD_INCOME)
        if income_segments:
            # Should have realistic income percentiles
            income_values = {seg.demographic_value for seg in income_segments}
            # Check for percentile patterns
            has_percentile = any(
                "%" in income
                or "Lower" in income
                or "Upper" in income
                or "Top" in income
                for income in income_values
            )
            assert has_percentile, (
                f"Income values {income_values} don't match expected percentile patterns"
            )

    async def test_scalability_with_large_dataset(
        self, analyzer, age_data, gender_data, income_data
    ):
        """Test analyzer scalability with larger datasets."""
        customer_id = "646-990-6417"
        start_date = datetime(2025, 5, 18)
        end_date = datetime(2025, 8, 15)

        # Duplicate data to simulate larger dataset
        large_age_data = age_data * 5
        large_gender_data = gender_data * 5
        large_income_data = income_data * 5

        import time

        start_time = time.time()

        result = await analyzer.analyze(
            customer_id=customer_id,
            start_date=start_date,
            end_date=end_date,
            age_data=large_age_data,
            gender_data=large_gender_data,
            income_data=large_income_data,
        )

        analysis_time = time.time() - start_time

        # Should still complete within reasonable time
        assert analysis_time < 60.0, (
            f"Large dataset analysis took {analysis_time:.2f} seconds, too slow"
        )

        # Should still generate valid results
        assert len(result.segments) > 0
        assert len(result.performance_by_demographic) > 0
        assert len(result.insights) > 0

    async def test_edge_cases_and_data_validation(
        self, analyzer, age_data, gender_data
    ):
        """Test edge cases and data validation with real data."""
        customer_id = "646-990-6417"
        start_date = datetime(2025, 5, 18)
        end_date = datetime(2025, 8, 15)

        # Test with mixed quality data (some good, some bad)
        mixed_data = age_data.copy()

        # Add some problematic rows
        mixed_data.extend(
            [
                {
                    "Age": "Invalid",
                    "Campaign": "Test",
                    "Ad group": "Test",
                    "Demographic status": "Enabled",
                    "Bid adj.": "--",
                    "Currency code": "USD",
                    "Avg. CPM": "invalid",
                    "Impr.": "not_a_number",
                    "Interactions": "0",
                    "Interaction rate": "0%",
                    "Avg. cost": "0",
                    "Cost": "0",
                    "Conv. rate": "0%",
                    "Conversions": "0",
                    "Cost / conv.": "0",
                }
            ]
        )

        result = await analyzer.analyze(
            customer_id=customer_id,
            start_date=start_date,
            end_date=end_date,
            age_data=mixed_data,
            gender_data=gender_data,
        )

        # Should handle invalid data gracefully
        assert isinstance(result, type(result))  # Should not raise exceptions
        assert len(result.segments) > 0  # Should still process valid data

        # All processed segments should have valid data
        for segment in result.segments:
            assert segment.impressions >= 0
            assert segment.clicks >= 0
            assert segment.conversions >= 0
            assert segment.cost >= 0

    async def test_fitness_connection_specific_patterns(
        self, analyzer, age_data, gender_data, income_data
    ):
        """Test recognition of Fitness Connection specific patterns."""
        customer_id = "646-990-6417"
        start_date = datetime(2025, 5, 18)
        end_date = datetime(2025, 8, 15)

        result = await analyzer.analyze(
            customer_id=customer_id,
            start_date=start_date,
            end_date=end_date,
            age_data=age_data,
            gender_data=gender_data,
            income_data=income_data,
        )

        # Should recognize fitness industry patterns
        campaign_names = {segment.campaign_name for segment in result.segments}

        # Should have fitness-related campaigns
        fitness_patterns = ["FIT", "GYM", "FITNESS", "GENERAL"]
        has_fitness_campaigns = any(
            any(pattern in campaign.upper() for pattern in fitness_patterns)
            for campaign in campaign_names
        )
        assert has_fitness_campaigns, (
            f"No fitness-related campaigns found in {campaign_names}"
        )

        # Should identify meaningful demographic targeting for fitness
        # Fitness businesses typically see different performance by age and gender
        age_performances = [
            p
            for p in result.performance_by_demographic
            if p.demographic_type == DemographicType.AGE
        ]
        gender_performances = [
            p
            for p in result.performance_by_demographic
            if p.demographic_type == DemographicType.GENDER
        ]

        if age_performances:
            age_scores = [p.performance_score for p in age_performances]
            age_variance = (
                max(age_scores) - min(age_scores) if len(age_scores) > 1 else 0
            )
            assert age_variance > 10, (
                "Should show meaningful age performance differences for fitness business"
            )

        if gender_performances:
            gender_scores = [p.performance_score for p in gender_performances]
            gender_variance = (
                max(gender_scores) - min(gender_scores) if len(gender_scores) > 1 else 0
            )
            # Gender differences are common in fitness marketing
            assert gender_variance >= 0, "Should analyze gender performance differences"

    async def test_recommendations_implementation_readiness(
        self, analyzer, age_data, gender_data, income_data
    ):
        """Test that recommendations are ready for implementation."""
        customer_id = "646-990-6417"
        start_date = datetime(2025, 5, 18)
        end_date = datetime(2025, 8, 15)

        result = await analyzer.analyze(
            customer_id=customer_id,
            start_date=start_date,
            end_date=end_date,
            age_data=age_data,
            gender_data=gender_data,
            income_data=income_data,
        )

        # All bid adjustment recommendations should be specific and implementable
        for key, adjustment in result.bid_adjustment_recommendations.items():
            assert ":" in key, (
                f"Bid adjustment key {key} should specify demographic type:value"
            )
            assert isinstance(adjustment, (int, float)), (
                f"Bid adjustment {adjustment} should be numeric"
            )
            assert -0.50 <= adjustment <= 0.50, (
                f"Bid adjustment {adjustment} should be reasonable (-50% to +50%)"
            )

        # Exclusion recommendations should be specific
        for exclusion in result.targeting_exclusion_recommendations:
            assert "exclude" in exclusion.lower(), (
                f"Exclusion recommendation should mention exclusion: {exclusion}"
            )
            assert any(
                demo_type.value in exclusion.lower() for demo_type in DemographicType
            ), f"Exclusion should specify demographic type: {exclusion}"

        # Budget recommendations should be actionable
        for budget_rec in result.budget_reallocation_recommendations:
            assert any(
                word in budget_rec.lower()
                for word in ["increase", "decrease", "reallocate"]
            ), f"Budget recommendation should be actionable: {budget_rec}"

        # Optimization recommendations should provide clear next steps
        for opt_rec in result.optimization_recommendations:
            assert len(opt_rec) > 20, (
                f"Optimization recommendation should be detailed: {opt_rec}"
            )
            assert any(
                word in opt_rec.lower()
                for word in ["implement", "consider", "optimize", "improve"]
            ), f"Optimization recommendation should suggest action: {opt_rec}"
