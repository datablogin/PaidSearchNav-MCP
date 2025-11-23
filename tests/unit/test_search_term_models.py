"""Unit tests for search term models."""

from datetime import date

import pytest

from paidsearchnav_mcp.models import (
    SearchTerm,
    SearchTermAnalysisResult,
    SearchTermClassification,
    SearchTermMetrics,
)


class TestSearchTermMetrics:
    """Test SearchTermMetrics model."""

    def test_metrics_calculation(self):
        """Test calculated metrics properties."""
        metrics = SearchTermMetrics(
            impressions=1000,
            clicks=50,
            cost=100.0,
            conversions=5.0,
            conversion_value=500.0,
        )

        assert metrics.ctr == pytest.approx(5.0)  # 50/1000 * 100
        assert metrics.cpc == pytest.approx(2.0)  # 100/50
        assert metrics.conversion_rate == pytest.approx(10.0)  # 5/50 * 100
        assert metrics.cpa == pytest.approx(20.0)  # 100/5
        assert metrics.roas == pytest.approx(5.0)  # 500/100

    def test_metrics_zero_handling(self):
        """Test metrics with zero values."""
        metrics = SearchTermMetrics(
            impressions=0,
            clicks=0,
            cost=0.0,
            conversions=0.0,
            conversion_value=0.0,
        )

        assert metrics.ctr == 0.0
        assert metrics.cpc == 0.0
        assert metrics.conversion_rate == 0.0
        assert metrics.cpa == 0.0
        assert metrics.roas == 0.0

    def test_metrics_edge_cases(self):
        """Test edge cases in metrics calculations."""
        # No clicks but has impressions
        metrics = SearchTermMetrics(
            impressions=1000,
            clicks=0,
            cost=0.0,
            conversions=0.0,
            conversion_value=0.0,
        )
        assert metrics.ctr == 0.0
        assert metrics.conversion_rate == 0.0

        # Has cost but no conversions
        metrics = SearchTermMetrics(
            impressions=100,
            clicks=10,
            cost=50.0,
            conversions=0.0,
            conversion_value=0.0,
        )
        assert metrics.cpa == 0.0
        assert metrics.roas == 0.0


class TestSearchTerm:
    """Test SearchTerm model."""

    def test_search_term_creation(self):
        """Test creating a search term."""
        metrics = SearchTermMetrics(
            impressions=1000,
            clicks=50,
            cost=100.0,
            conversions=5.0,
            conversion_value=500.0,
        )

        search_term = SearchTerm(
            search_term="widgets near me",
            campaign_id="123",
            campaign_name="Widgets Campaign",
            ad_group_id="456",
            ad_group_name="Widget Ad Group",
            keyword_id="789",
            keyword_text="widgets",
            match_type="BROAD",
            date_start=date(2024, 1, 1),
            date_end=date(2024, 1, 31),
            metrics=metrics,
        )

        assert search_term.search_term == "widgets near me"
        assert search_term.campaign_name == "Widgets Campaign"
        assert search_term.metrics.conversions == 5.0

    def test_local_intent_detection(self):
        """Test local intent detection."""
        metrics = SearchTermMetrics(
            impressions=100,
            clicks=10,
            cost=20.0,
            conversions=1.0,
            conversion_value=100.0,
        )

        # Test "near me" detection
        search_term = SearchTerm(
            search_term="widgets near me",
            campaign_id="123",
            campaign_name="Campaign",
            ad_group_id="456",
            ad_group_name="Ad Group",
            date_start=date(2024, 1, 1),
            date_end=date(2024, 1, 31),
            metrics=metrics,
        )
        search_term.detect_local_intent()
        assert search_term.contains_near_me is True
        assert search_term.is_local_intent is True

        # Test local pattern detection
        search_term2 = SearchTerm(
            search_term="widgets nearby",
            campaign_id="123",
            campaign_name="Campaign",
            ad_group_id="456",
            ad_group_name="Ad Group",
            date_start=date(2024, 1, 1),
            date_end=date(2024, 1, 31),
            metrics=metrics,
        )
        search_term2.detect_local_intent()
        assert search_term2.contains_near_me is False
        assert search_term2.is_local_intent is True

        # Test non-local term
        search_term3 = SearchTerm(
            search_term="buy widgets online",
            campaign_id="123",
            campaign_name="Campaign",
            ad_group_id="456",
            ad_group_name="Ad Group",
            date_start=date(2024, 1, 1),
            date_end=date(2024, 1, 31),
            metrics=metrics,
        )
        search_term3.detect_local_intent()
        assert search_term3.contains_near_me is False
        assert search_term3.is_local_intent is False

    def test_is_wasteful(self):
        """Test wasteful search term detection."""
        # Wasteful: high cost, no conversions
        metrics = SearchTermMetrics(
            impressions=1000,
            clicks=50,
            cost=200.0,
            conversions=0.0,
            conversion_value=0.0,
        )

        search_term = SearchTerm(
            search_term="expensive widgets",
            campaign_id="123",
            campaign_name="Campaign",
            ad_group_id="456",
            ad_group_name="Ad Group",
            date_start=date(2024, 1, 1),
            date_end=date(2024, 1, 31),
            metrics=metrics,
        )

        assert (
            search_term.is_wasteful(min_clicks=10, max_conversions=0.0, min_cost=50.0)
            is True
        )
        assert (
            search_term.is_wasteful(min_clicks=100, max_conversions=0.0, min_cost=50.0)
            is False
        )
        assert (
            search_term.is_wasteful(min_clicks=10, max_conversions=1.0, min_cost=50.0)
            is True
        )

        # Not wasteful: has conversions
        metrics2 = SearchTermMetrics(
            impressions=1000,
            clicks=50,
            cost=200.0,
            conversions=5.0,
            conversion_value=500.0,
        )

        search_term2 = SearchTerm(
            search_term="quality widgets",
            campaign_id="123",
            campaign_name="Campaign",
            ad_group_id="456",
            ad_group_name="Ad Group",
            date_start=date(2024, 1, 1),
            date_end=date(2024, 1, 31),
            metrics=metrics2,
        )

        assert (
            search_term2.is_wasteful(min_clicks=10, max_conversions=0.0, min_cost=50.0)
            is False
        )

    def test_is_high_value(self):
        """Test high value search term detection."""
        # High performing: good CPA and conversion rate
        metrics = SearchTermMetrics(
            impressions=1000,
            clicks=100,
            cost=200.0,
            conversions=20.0,
            conversion_value=2000.0,
        )

        search_term = SearchTerm(
            search_term="premium widgets",
            campaign_id="123",
            campaign_name="Campaign",
            ad_group_id="456",
            ad_group_name="Ad Group",
            date_start=date(2024, 1, 1),
            date_end=date(2024, 1, 31),
            metrics=metrics,
        )

        # CPA is 10.0 (200/20)
        assert (
            search_term.is_high_value(
                min_conversions=10.0,
                max_cpa=20.0,
            )
            is True
        )

        assert (
            search_term.is_high_value(
                min_conversions=30.0,  # Too high
                max_cpa=20.0,
            )
            is False
        )

        assert (
            search_term.is_high_value(
                min_conversions=10.0,
                max_cpa=5.0,  # Too low
            )
            is False
        )

    def test_search_term_with_classification(self):
        """Test search term with classification."""
        metrics = SearchTermMetrics(
            impressions=1000,
            clicks=50,
            cost=100.0,
            conversions=5.0,
            conversion_value=500.0,
        )

        search_term = SearchTerm(
            search_term="widgets near me",
            campaign_id="123",
            campaign_name="Campaign",
            ad_group_id="456",
            ad_group_name="Ad Group",
            date_start=date(2024, 1, 1),
            date_end=date(2024, 1, 31),
            metrics=metrics,
            classification=SearchTermClassification.ADD_CANDIDATE,
            classification_reason="High performing search term",
            recommendation="Add as Exact match keyword",
        )

        assert search_term.classification == SearchTermClassification.ADD_CANDIDATE
        assert search_term.classification_reason == "High performing search term"
        assert search_term.recommendation == "Add as Exact match keyword"


class TestSearchTermAnalysisResult:
    """Test SearchTermAnalysisResult model."""

    def test_analysis_result_creation(self):
        """Test creating analysis result."""
        from datetime import datetime

        result = SearchTermAnalysisResult(
            customer_id="12345",
            analyzer_name="search_terms_analyzer",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
            total_search_terms=100,
            total_impressions=10000,
            total_clicks=500,
            total_cost=1000.0,
            total_conversions=50.0,
            add_candidates=[],
            negative_candidates=[],
            already_covered=[],
            review_needed=[],
            classification_summary={
                SearchTermClassification.ADD_CANDIDATE: 10,
                SearchTermClassification.NEGATIVE_CANDIDATE: 20,
                SearchTermClassification.ALREADY_COVERED: 60,
                SearchTermClassification.REVIEW_NEEDED: 10,
            },
            local_intent_terms=15,
            near_me_terms=5,
            potential_savings=200.0,
            potential_revenue=500.0,
            recommendations=[],
        )

        assert result.customer_id == "12345"
        assert result.total_search_terms == 100
        assert result.overall_ctr == pytest.approx(5.0)  # 500/10000 * 100
        assert result.overall_cpc == pytest.approx(2.0)  # 1000/500
        assert result.overall_cpa == pytest.approx(20.0)  # 1000/50

    def test_analysis_result_to_summary_dict(self):
        """Test converting analysis result to summary dictionary."""
        from datetime import datetime

        result = SearchTermAnalysisResult(
            customer_id="12345",
            analyzer_name="search_terms_analyzer",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
            total_search_terms=100,
            total_impressions=10000,
            total_clicks=500,
            total_cost=1000.0,
            total_conversions=50.0,
            add_candidates=[],
            negative_candidates=[],
            already_covered=[],
            review_needed=[],
            classification_summary={
                SearchTermClassification.ADD_CANDIDATE: 10,
                SearchTermClassification.NEGATIVE_CANDIDATE: 20,
            },
            local_intent_terms=15,
            near_me_terms=5,
            potential_savings=200.0,
            potential_revenue=500.0,
            recommendations=[],
        )

        summary = result.to_summary_dict()

        assert (
            summary["account"] == "12345"
        )  # Uses customer_id since account_name is None
        assert summary["summary"]["total_search_terms"] == 100
        assert summary["summary"]["overall_cpa"] == pytest.approx(20.0)
        assert summary["classifications"]["add_candidates"] == 0  # Empty list
        assert summary["classifications"]["negative_candidates"] == 0  # Empty list
        assert summary["local_intent"]["local_intent_terms"] == 15
        assert summary["local_intent"]["near_me_terms"] == 5
        assert summary["potential_impact"]["savings"] == 200.0
        assert summary["potential_impact"]["revenue"] == 500.0
        assert len(summary["top_recommendations"]) == 0
