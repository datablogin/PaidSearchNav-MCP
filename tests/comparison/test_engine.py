"""Tests for the comparison engine."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from paidsearchnav.comparison.engine import AuditComparator
from paidsearchnav.comparison.models import AuditResult, ComparisonOptions


class TestAuditComparator:
    """Test the audit comparison engine."""

    @pytest.fixture
    def mock_repository(self):
        """Create mock repository."""
        return AsyncMock()

    @pytest.fixture
    def comparator(self, mock_repository):
        """Create comparator instance."""
        return AuditComparator(mock_repository)

    @pytest.fixture
    def sample_audit_baseline(self):
        """Create sample baseline audit result."""
        return AuditResult(
            id="audit-1",
            customer_id="customer-123",
            status="completed",
            created_at=datetime(2024, 1, 1),
            summary={
                "total_issues": 20,
                "metrics": {
                    "total_spend": 10000.0,
                    "wasted_spend": 2000.0,
                    "cost_per_conversion": 50.0,
                    "roas": 4.0,
                    "ctr": 2.5,
                    "conversion_rate": 3.0,
                    "avg_quality_score": 7.5,
                    "impressions": 100000,
                    "clicks": 2500,
                    "conversions": 75,
                    "keywords_analyzed": 500,
                },
            },
        )

    @pytest.fixture
    def sample_audit_comparison(self):
        """Create sample comparison audit result."""
        return AuditResult(
            id="audit-2",
            customer_id="customer-123",
            status="completed",
            created_at=datetime(2024, 2, 1),
            summary={
                "total_issues": 15,
                "metrics": {
                    "total_spend": 11000.0,
                    "wasted_spend": 1500.0,
                    "cost_per_conversion": 45.0,
                    "roas": 4.5,
                    "ctr": 2.8,
                    "conversion_rate": 3.3,
                    "avg_quality_score": 8.0,
                    "impressions": 110000,
                    "clicks": 3080,
                    "conversions": 102,
                    "keywords_analyzed": 550,
                },
            },
        )

    @pytest.mark.asyncio
    async def test_compare_audits_success(
        self,
        comparator,
        mock_repository,
        sample_audit_baseline,
        sample_audit_comparison,
    ):
        """Test successful audit comparison."""
        # Setup mock
        mock_repository.get_audit_result.side_effect = [
            sample_audit_baseline,
            sample_audit_comparison,
        ]
        mock_repository.get_recommendations_by_audit.return_value = []

        # Perform comparison
        result = await comparator.compare_audits("audit-1", "audit-2")

        # Verify results
        assert result.baseline_audit_id == "audit-1"
        assert result.comparison_audit_id == "audit-2"

        # Check metrics calculations
        metrics = result.metrics
        assert metrics.total_spend_change == 1000.0  # 11000 - 10000
        assert metrics.total_spend_change_pct == 10.0  # 10% increase
        assert metrics.wasted_spend_reduction == 500.0  # 2000 - 1500
        assert metrics.wasted_spend_reduction_pct == 25.0  # 25% reduction
        assert metrics.cost_per_conversion_change == -5.0  # 45 - 50
        assert metrics.cost_per_conversion_change_pct == -10.0  # 10% decrease
        assert metrics.roas_change == 0.5  # 4.5 - 4.0
        assert metrics.ctr_improvement == 0.3  # 2.8 - 2.5
        assert metrics.conversion_rate_change == 0.3  # 3.3 - 3.0
        assert metrics.issues_resolved == 5  # 20 - 15
        assert metrics.new_issues_found == 0

        # Check insights
        assert len(result.insights) > 0
        assert any(
            "wasted spend reduced" in insight.lower() for insight in result.insights
        )

    @pytest.mark.asyncio
    async def test_compare_audits_not_found(self, comparator, mock_repository):
        """Test comparison when audit not found."""
        # Setup mock to return None
        mock_repository.get_audit_result.return_value = None

        # Should raise ValueError
        with pytest.raises(ValueError, match="audit results not found"):
            await comparator.compare_audits("audit-1", "audit-2")

    @pytest.mark.asyncio
    async def test_compare_with_statistical_tests(
        self,
        comparator,
        mock_repository,
        sample_audit_baseline,
        sample_audit_comparison,
    ):
        """Test comparison with statistical significance testing."""
        # Setup mock
        mock_repository.get_audit_result.side_effect = [
            sample_audit_baseline,
            sample_audit_comparison,
        ]
        mock_repository.get_recommendations_by_audit.return_value = []

        # Create options with statistical tests
        options = ComparisonOptions(
            include_statistical_tests=True,
            confidence_level=0.95,
            minimum_sample_size=30,
        )

        # Perform comparison
        result = await comparator.compare_audits("audit-1", "audit-2", options)

        # Should have statistical significance results
        assert result.metrics.is_statistically_significant is not None
        assert isinstance(result.metrics.is_statistically_significant, dict)

    def test_calculate_percentage_change(self, comparator):
        """Test percentage change calculation."""
        # Normal case
        assert comparator._calculate_percentage_change(100, 110) == 10.0
        assert comparator._calculate_percentage_change(100, 90) == -10.0

        # Zero baseline
        assert comparator._calculate_percentage_change(0, 100) == 100.0
        assert comparator._calculate_percentage_change(0, 0) == 0.0

        # Inverse calculation (for metrics where decrease is good)
        assert comparator._calculate_percentage_change(100, 80, inverse=True) == 20.0
        assert comparator._calculate_percentage_change(100, 120, inverse=True) == -20.0

    def test_generate_insights(self, comparator):
        """Test insight generation."""
        from paidsearchnav.comparison.models import ComparisonMetrics

        metrics = ComparisonMetrics(
            total_spend_change=1000.0,
            total_spend_change_pct=10.0,
            wasted_spend_reduction=500.0,
            wasted_spend_reduction_pct=15.0,
            cost_per_conversion_change=-5.0,
            cost_per_conversion_change_pct=-10.0,
            roas_change=0.5,
            roas_change_pct=12.0,
            ctr_improvement=0.3,
            ctr_improvement_pct=8.0,
            conversion_rate_change=0.2,
            conversion_rate_change_pct=7.0,
            quality_score_trend=0.6,
            impressions_change=5000,
            impressions_change_pct=5.0,
            clicks_change=200,
            clicks_change_pct=8.0,
            conversions_change=10,
            conversions_change_pct=10.0,
            recommendations_implemented=10,
            recommendations_pending=5,
            issues_resolved=8,
            new_issues_found=2,
            keywords_analyzed_change=50,
            negative_keywords_added=30,
            match_type_optimizations=15,
            is_statistically_significant={"ctr": True, "conversion_rate": True},
        )

        baseline = MagicMock()
        comparison = MagicMock()

        insights = comparator._generate_insights(metrics, baseline, comparison)

        # Should generate insights for significant improvements
        assert len(insights) > 0
        assert any("wasted spend" in insight.lower() for insight in insights)
        assert any("roas" in insight.lower() for insight in insights)
        assert any("ctr" in insight.lower() for insight in insights)
        assert any("quality score" in insight.lower() for insight in insights)
        assert any("statistically significant" in insight for insight in insights)

    def test_generate_warnings(self, comparator):
        """Test warning generation."""
        from paidsearchnav.comparison.models import ComparisonMetrics

        # Create metrics with concerning trends
        metrics = ComparisonMetrics(
            total_spend_change=2000.0,
            total_spend_change_pct=25.0,
            wasted_spend_reduction=-100.0,
            wasted_spend_reduction_pct=-5.0,
            cost_per_conversion_change=10.0,
            cost_per_conversion_change_pct=15.0,
            roas_change=-0.5,
            roas_change_pct=-10.0,
            ctr_improvement=-0.3,
            ctr_improvement_pct=-8.0,
            conversion_rate_change=-0.2,
            conversion_rate_change_pct=-7.0,
            quality_score_trend=-0.8,
            impressions_change=10000,
            impressions_change_pct=10.0,
            clicks_change=500,
            clicks_change_pct=5.0,
            conversions_change=5,
            conversions_change_pct=5.0,
            recommendations_implemented=2,
            recommendations_pending=20,
            issues_resolved=3,
            new_issues_found=10,
            keywords_analyzed_change=50,
            negative_keywords_added=5,
            match_type_optimizations=2,
        )

        warnings = comparator._generate_warnings(metrics)

        # Should generate warnings for negative trends
        assert len(warnings) > 0
        assert any("ctr decreased" in warning.lower() for warning in warnings)
        assert any("conversion rate" in warning.lower() for warning in warnings)
        assert any(
            "cost per conversion increased" in warning.lower() for warning in warnings
        )
        assert any("quality scores declined" in warning.lower() for warning in warnings)
        assert any("more new issues" in warning.lower() for warning in warnings)
