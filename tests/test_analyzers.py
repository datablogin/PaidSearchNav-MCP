"""Tests for PaidSearchNav analyzers module."""

import pytest
from datetime import datetime

from paidsearchnav_mcp.analyzers import (
    AnalysisSummary,
    KeywordMatchAnalyzer,
    SearchTermWasteAnalyzer,
    NegativeConflictAnalyzer,
    GeoPerformanceAnalyzer,
    PMaxCannibalizationAnalyzer,
)


class TestAnalysisSummary:
    """Test AnalysisSummary model."""

    def test_analysis_summary_creation(self):
        """Test creating an AnalysisSummary."""
        summary = AnalysisSummary(
            total_records_analyzed=100,
            estimated_monthly_savings=500.50,
            primary_issue="Test issue",
            top_recommendations=[
                {"keyword": "test", "savings": 100.00}
            ],
            implementation_steps=["Step 1", "Step 2"],
            analysis_period="2024-01-01 to 2024-01-31",
            customer_id="1234567890",
        )

        assert summary.total_records_analyzed == 100
        assert summary.estimated_monthly_savings == 500.50
        assert summary.primary_issue == "Test issue"
        assert len(summary.top_recommendations) == 1
        assert len(summary.implementation_steps) == 2
        assert summary.customer_id == "1234567890"

    def test_analysis_summary_dict_conversion(self):
        """Test converting AnalysisSummary to dict."""
        summary = AnalysisSummary(
            total_records_analyzed=50,
            estimated_monthly_savings=250.00,
            primary_issue="Test",
            top_recommendations=[],
            implementation_steps=[],
            analysis_period="2024-01-01 to 2024-01-31",
            customer_id="1234567890",
        )

        data = summary.model_dump()
        assert isinstance(data, dict)
        assert data["total_records_analyzed"] == 50
        assert data["customer_id"] == "1234567890"


class TestKeywordMatchAnalyzer:
    """Test KeywordMatchAnalyzer."""

    def test_analyzer_initialization(self):
        """Test analyzer can be initialized with default settings."""
        analyzer = KeywordMatchAnalyzer()
        assert analyzer.min_impressions == 100
        assert analyzer.high_cost_threshold == 100.0

    def test_analyzer_custom_settings(self):
        """Test analyzer with custom settings."""
        analyzer = KeywordMatchAnalyzer(
            min_impressions=200,
            high_cost_threshold=200.0,
        )
        assert analyzer.min_impressions == 200
        assert analyzer.high_cost_threshold == 200.0

    def test_calculate_match_type_performance(self):
        """Test match type performance calculation."""
        analyzer = KeywordMatchAnalyzer()

        keywords = [
            {
                "match_type": "BROAD",
                "metrics": {
                    "impressions": 1000,
                    "clicks": 100,
                    "cost": 50.0,
                    "conversions": 5.0,
                    "conversion_value": 250.0,
                }
            },
            {
                "match_type": "EXACT",
                "metrics": {
                    "impressions": 500,
                    "clicks": 75,
                    "cost": 30.0,
                    "conversions": 10.0,
                    "conversion_value": 500.0,
                }
            },
        ]

        stats = analyzer._calculate_match_type_performance(keywords)

        assert "BROAD" in stats
        assert "EXACT" in stats
        assert stats["BROAD"]["count"] == 1
        assert stats["BROAD"]["cost"] == 50.0
        assert stats["EXACT"]["count"] == 1
        assert stats["EXACT"]["cpa"] == 3.0  # 30 / 10


class TestSearchTermWasteAnalyzer:
    """Test SearchTermWasteAnalyzer."""

    def test_analyzer_initialization(self):
        """Test analyzer initialization."""
        analyzer = SearchTermWasteAnalyzer()
        assert analyzer.min_cost == 10.0
        assert analyzer.min_clicks == 5

    def test_analyzer_custom_settings(self):
        """Test analyzer with custom settings."""
        analyzer = SearchTermWasteAnalyzer(
            min_cost=20.0,
            min_clicks=10,
        )
        assert analyzer.min_cost == 20.0
        assert analyzer.min_clicks == 10


class TestNegativeConflictAnalyzer:
    """Test NegativeConflictAnalyzer."""

    def test_analyzer_initialization(self):
        """Test analyzer initialization."""
        analyzer = NegativeConflictAnalyzer()
        assert analyzer is not None

    def test_is_conflict_exact_match(self):
        """Test exact match conflict detection."""
        analyzer = NegativeConflictAnalyzer()

        # Exact match - should conflict
        assert analyzer._is_conflict("golf shoes", "golf shoes", "EXACT")

        # Different text - should not conflict
        assert not analyzer._is_conflict("golf shoes", "tennis shoes", "EXACT")

    def test_is_conflict_phrase_match(self):
        """Test phrase match conflict detection."""
        analyzer = NegativeConflictAnalyzer()

        # Phrase is contained - should conflict
        assert analyzer._is_conflict("red golf shoes", "golf shoes", "PHRASE")

        # Phrase not contained - should not conflict
        assert not analyzer._is_conflict("golf clubs", "golf shoes", "PHRASE")

    def test_is_conflict_broad_match(self):
        """Test broad match conflict detection."""
        analyzer = NegativeConflictAnalyzer()

        # All words present - should conflict
        assert analyzer._is_conflict("red golf shoes", "golf red", "BROAD")

        # Not all words present - should not conflict
        assert not analyzer._is_conflict("golf shoes", "tennis shoes", "BROAD")


class TestGeoPerformanceAnalyzer:
    """Test GeoPerformanceAnalyzer."""

    def test_analyzer_initialization(self):
        """Test analyzer initialization."""
        analyzer = GeoPerformanceAnalyzer()
        assert analyzer.min_impressions == 100
        assert analyzer.performance_threshold == 0.2

    def test_analyzer_custom_settings(self):
        """Test analyzer with custom settings."""
        analyzer = GeoPerformanceAnalyzer(
            min_impressions=200,
            performance_threshold=0.3,
        )
        assert analyzer.min_impressions == 200
        assert analyzer.performance_threshold == 0.3


class TestPMaxCannibalizationAnalyzer:
    """Test PMaxCannibalizationAnalyzer."""

    def test_analyzer_initialization(self):
        """Test analyzer initialization."""
        analyzer = PMaxCannibalizationAnalyzer()
        assert analyzer.min_overlap_cost == 20.0
        assert analyzer.overlap_threshold == 0.2

    def test_analyzer_custom_settings(self):
        """Test analyzer with custom settings."""
        analyzer = PMaxCannibalizationAnalyzer(
            min_overlap_cost=50.0,
            overlap_threshold=0.3,
        )
        assert analyzer.min_overlap_cost == 50.0
        assert analyzer.overlap_threshold == 0.3


# Integration tests would require mocking the MCP server tools
# These would be added in a separate test file with proper fixtures
