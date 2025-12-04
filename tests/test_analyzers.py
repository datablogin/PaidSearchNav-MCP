"""Tests for PaidSearchNav analyzers module."""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from paidsearchnav_mcp.analyzers import (
    AnalysisSummary,
    BaseAnalyzer,
    KeywordMatchAnalyzer,
    SearchTermWasteAnalyzer,
    NegativeConflictAnalyzer,
    GeoPerformanceAnalyzer,
    PMaxCannibalizationAnalyzer,
)


class TestBaseAnalyzer:
    """Test BaseAnalyzer class."""

    def test_format_currency(self):
        """Test currency formatting."""
        # Create a concrete implementation to test base methods
        class TestAnalyzer(BaseAnalyzer):
            async def analyze(self, customer_id, start_date, end_date, **kwargs):
                pass

        analyzer = TestAnalyzer()

        assert analyzer._format_currency(1234.56) == "$1,234.56"
        assert analyzer._format_currency(0) == "$0.00"
        assert analyzer._format_currency(1000000.99) == "$1,000,000.99"
        assert analyzer._format_currency(5.5) == "$5.50"

    def test_calculate_savings(self):
        """Test savings calculation."""
        class TestAnalyzer(BaseAnalyzer):
            async def analyze(self, customer_id, start_date, end_date, **kwargs):
                pass

        analyzer = TestAnalyzer()

        # Normal case
        assert analyzer._calculate_savings(100.0, 80.0) == 20.0

        # No savings
        assert analyzer._calculate_savings(100.0, 100.0) == 0.0

        # Negative savings (returns 0)
        assert analyzer._calculate_savings(80.0, 100.0) == 0.0

        # Large savings
        assert analyzer._calculate_savings(10000.0, 5000.0) == 5000.0


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

    def test_analysis_summary_with_complex_recommendations(self):
        """Test AnalysisSummary with complex recommendation data."""
        summary = AnalysisSummary(
            total_records_analyzed=200,
            estimated_monthly_savings=1500.75,
            primary_issue="Excessive broad match spend",
            top_recommendations=[
                {
                    "keyword": "expensive keyword",
                    "current_match_type": "BROAD",
                    "recommended_match_type": "EXACT",
                    "estimated_savings": 500.0,
                    "reasoning": "High cost with low ROAS"
                },
                {
                    "keyword": "another keyword",
                    "current_match_type": "PHRASE",
                    "recommended_match_type": "EXACT",
                    "estimated_savings": 300.0,
                    "reasoning": "60% exact matches"
                }
            ],
            implementation_steps=[
                "Week 1: Optimize top 3 keywords",
                "Week 2: Review and adjust bids",
                "Week 3: Monitor performance"
            ],
            analysis_period="2024-01-01 to 2024-03-31",
            customer_id="9876543210",
        )

        assert len(summary.top_recommendations) == 2
        assert summary.top_recommendations[0]["estimated_savings"] == 500.0
        assert len(summary.implementation_steps) == 3


class TestKeywordMatchAnalyzer:
    """Test KeywordMatchAnalyzer."""

    def test_analyzer_initialization(self):
        """Test analyzer can be initialized with default settings."""
        analyzer = KeywordMatchAnalyzer()
        assert analyzer.min_impressions == 50
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

        # Note: Keyword data has metrics at top level, not nested
        keywords = [
            {
                "match_type": "BROAD",
                "impressions": 1000,
                "clicks": 100,
                "cost": 50.0,
                "conversions": 5.0,
                "conversion_value": 250.0,
            },
            {
                "match_type": "EXACT",
                "impressions": 500,
                "clicks": 75,
                "cost": 30.0,
                "conversions": 10.0,
                "conversion_value": 500.0,
            },
        ]

        stats = analyzer._calculate_match_type_performance(keywords)

        assert "BROAD" in stats
        assert "EXACT" in stats
        assert stats["BROAD"]["count"] == 1
        assert stats["BROAD"]["cost"] == 50.0
        assert stats["EXACT"]["count"] == 1
        assert stats["EXACT"]["cpa"] == 3.0  # 30 / 10

    def test_calculate_match_type_performance_with_empty_keywords(self):
        """Test match type performance calculation with empty list."""
        analyzer = KeywordMatchAnalyzer()
        stats = analyzer._calculate_match_type_performance([])
        assert stats == {}

    def test_calculate_match_type_performance_derived_metrics(self):
        """Test that derived metrics are calculated correctly."""
        analyzer = KeywordMatchAnalyzer()
        keywords = [
            {
                "match_type": "PHRASE",
                "impressions": 2000,
                "clicks": 200,
                "cost": 100.0,
                "conversions": 20.0,
                "conversion_value": 1000.0,
            }
        ]

        stats = analyzer._calculate_match_type_performance(keywords)

        assert stats["PHRASE"]["ctr"] == 10.0  # (200/2000) * 100
        assert stats["PHRASE"]["avg_cpc"] == 0.5  # 100 / 200
        assert stats["PHRASE"]["cpa"] == 5.0  # 100 / 20
        assert stats["PHRASE"]["roas"] == 10.0  # 1000 / 100
        assert stats["PHRASE"]["conversion_rate"] == 10.0  # (20/200) * 100

    @pytest.mark.asyncio
    async def test_analyze_no_keywords(self):
        """Test analyze with no keywords returned."""
        analyzer = KeywordMatchAnalyzer(min_impressions=50)

        # Mock get_keywords to return empty data
        mock_keywords_result = {
            "status": "success",
            "data": [],
            "metadata": {"pagination": {"has_more": False}}
        }

        # Patch at the point where they're imported in the analyze method
        with patch("paidsearchnav_mcp.server.get_keywords") as mock_get_kw, \
             patch("paidsearchnav_mcp.server.get_search_terms") as mock_get_st:

            # Create mock function tools
            mock_get_kw.fn = AsyncMock(return_value=mock_keywords_result)
            mock_get_st.fn = AsyncMock(return_value={
                "status": "success",
                "data": [],
                "metadata": {"pagination": {"has_more": False}}
            })

            result = await analyzer.analyze(
                customer_id="1234567890",
                start_date="2024-01-01",
                end_date="2024-01-31"
            )

            assert result.total_records_analyzed == 0
            assert result.estimated_monthly_savings == 0.0
            assert "No keywords found" in result.primary_issue
            assert len(result.top_recommendations) == 0

    @pytest.mark.asyncio
    async def test_analyze_keywords_below_threshold(self):
        """Test analyze with keywords below impression threshold."""
        analyzer = KeywordMatchAnalyzer(min_impressions=100)

        # Mock keywords with low impressions
        mock_keywords_result = {
            "status": "success",
            "data": [
                {
                    "keyword_text": "low impressions",
                    "match_type": "BROAD",
                    "impressions": 50,
                    "clicks": 5,
                    "cost": 10.0,
                    "conversions": 1.0,
                    "conversion_value": 20.0,
                }
            ],
            "metadata": {"pagination": {"has_more": False}}
        }

        with patch("paidsearchnav_mcp.server.get_keywords") as mock_get_kw, \
             patch("paidsearchnav_mcp.server.get_search_terms") as mock_get_st:

            mock_get_kw.fn = AsyncMock(return_value=mock_keywords_result)
            mock_get_st.fn = AsyncMock(return_value={
                "status": "success",
                "data": [],
                "metadata": {"pagination": {"has_more": False}}
            })

            result = await analyzer.analyze(
                customer_id="1234567890",
                start_date="2024-01-01",
                end_date="2024-01-31"
            )

            # All keywords filtered out due to low impressions
            assert result.total_records_analyzed == 0
            assert "No keywords found with" in result.primary_issue
            assert "Try reducing min_impressions" in result.primary_issue

    @pytest.mark.asyncio
    async def test_analyze_with_exact_match_opportunities(self):
        """Test analyze identifies exact match opportunities."""
        analyzer = KeywordMatchAnalyzer(
            min_impressions=50,
            exact_match_ratio_threshold=0.6
        )

        # Create keywords and search terms where 80% of searches are exact matches
        mock_keywords_result = {
            "status": "success",
            "data": [
                {
                    "keyword_text": "running shoes",
                    "match_type": "BROAD",
                    "campaign_name": "Test Campaign",
                    "ad_group_name": "Test Ad Group",
                    "impressions": 1000,
                    "clicks": 100,
                    "cost": 200.0,
                    "conversions": 10.0,
                    "conversion_value": 500.0,
                }
            ],
            "metadata": {"pagination": {"has_more": False}}
        }

        mock_search_terms_result = {
            "status": "success",
            "data": [
                # 4 exact matches
                {"keyword_text": "running shoes", "search_term": "running shoes", "metrics": {}},
                {"keyword_text": "running shoes", "search_term": "running shoes", "metrics": {}},
                {"keyword_text": "running shoes", "search_term": "running shoes", "metrics": {}},
                {"keyword_text": "running shoes", "search_term": "running shoes", "metrics": {}},
                # 1 broad match
                {"keyword_text": "running shoes", "search_term": "best running shoes", "metrics": {}},
            ],
            "metadata": {"pagination": {"has_more": False}}
        }

        with patch("paidsearchnav_mcp.server.get_keywords") as mock_get_kw, \
             patch("paidsearchnav_mcp.server.get_search_terms") as mock_get_st:

            mock_get_kw.fn = AsyncMock(return_value=mock_keywords_result)
            mock_get_st.fn = AsyncMock(return_value=mock_search_terms_result)

            result = await analyzer.analyze(
                customer_id="1234567890",
                start_date="2024-01-01",
                end_date="2024-01-31"
            )

            # Should find exact match opportunity (80% > 60% threshold)
            assert result.total_records_analyzed == 1
            assert len(result.top_recommendations) > 0
            assert result.top_recommendations[0]["recommended_match_type"] == "EXACT"
            assert "80%" in result.top_recommendations[0]["reasoning"]

    @pytest.mark.asyncio
    async def test_analyze_with_high_cost_broad_keywords(self):
        """Test analyze identifies high-cost broad keywords with low ROAS."""
        analyzer = KeywordMatchAnalyzer(
            min_impressions=50,
            high_cost_threshold=100.0,
            low_roas_threshold=1.5
        )

        mock_keywords_result = {
            "status": "success",
            "data": [
                {
                    "keyword_text": "expensive keyword",
                    "match_type": "BROAD",
                    "campaign_name": "Test Campaign",
                    "ad_group_name": "Test Ad Group",
                    "impressions": 5000,
                    "clicks": 500,
                    "cost": 150.0,  # Above threshold
                    "conversions": 5.0,
                    "conversion_value": 100.0,  # ROAS = 0.67 (below 1.5)
                }
            ],
            "metadata": {"pagination": {"has_more": False}}
        }

        with patch("paidsearchnav_mcp.server.get_keywords") as mock_get_kw, \
             patch("paidsearchnav_mcp.server.get_search_terms") as mock_get_st:

            mock_get_kw.fn = AsyncMock(return_value=mock_keywords_result)
            mock_get_st.fn = AsyncMock(return_value={
                "status": "success",
                "data": [],
                "metadata": {"pagination": {"has_more": False}}
            })

            result = await analyzer.analyze(
                customer_id="1234567890",
                start_date="2024-01-01",
                end_date="2024-01-31"
            )

            # Should identify as high-cost broad keyword
            assert len(result.top_recommendations) > 0
            assert result.top_recommendations[0]["current_match_type"] == "BROAD"
            assert "PHRASE or PAUSE" in result.top_recommendations[0]["recommended_match_type"]
            assert "ROAS" in result.top_recommendations[0]["reasoning"]

    def test_identify_primary_issue_excessive_broad_spend(self):
        """Test primary issue identification for excessive broad match spend."""
        analyzer = KeywordMatchAnalyzer(low_roas_threshold=1.5)

        match_type_stats = {
            "BROAD": {"cost": 600.0, "roas": 0.8},
            "PHRASE": {"cost": 200.0, "roas": 3.0},
            "EXACT": {"cost": 200.0, "roas": 5.0},
        }

        issue = analyzer._identify_primary_issue(match_type_stats, [], [])
        assert "Excessive broad match spend" in issue
        assert "60%" in issue  # 600/1000 = 60%
        assert "0.8" in issue  # ROAS

    def test_generate_implementation_steps_few_recommendations(self):
        """Test implementation steps with 1-2 recommendations."""
        analyzer = KeywordMatchAnalyzer()

        recommendations = [
            {"keyword": "test", "estimated_savings": 50.0}
        ]

        steps = analyzer._generate_implementation_steps(recommendations)
        assert len(steps) == 3
        assert "Week 1: Convert 1 keyword" in steps[0]
        assert "well-optimized" in steps[2]

    def test_generate_implementation_steps_many_recommendations(self):
        """Test implementation steps with many recommendations."""
        analyzer = KeywordMatchAnalyzer()

        recommendations = [
            {"keyword": f"test{i}", "estimated_savings": 10.0, "current_match_type": "BROAD"}
            for i in range(10)
        ]

        steps = analyzer._generate_implementation_steps(recommendations)
        assert len(steps) >= 3
        assert "Week 1: Convert top 3" in steps[0]
        assert "Week 2-3" in steps[1]
        assert "Week 4" in steps[2]


class TestSearchTermWasteAnalyzer:
    """Test SearchTermWasteAnalyzer."""

    def test_analyzer_initialization(self):
        """Test analyzer initialization."""
        analyzer = SearchTermWasteAnalyzer()
        assert analyzer.min_cost == 10.0
        assert analyzer.min_clicks == 5
        assert analyzer.min_impressions == 100

    def test_analyzer_custom_settings(self):
        """Test analyzer with custom settings."""
        analyzer = SearchTermWasteAnalyzer(
            min_cost=20.0,
            min_clicks=10,
            min_impressions=200,
        )
        assert analyzer.min_cost == 20.0
        assert analyzer.min_clicks == 10
        assert analyzer.min_impressions == 200

    @pytest.mark.asyncio
    async def test_analyze_no_search_terms(self):
        """Test analyze with no search terms."""
        analyzer = SearchTermWasteAnalyzer()

        mock_result = {
            "status": "success",
            "data": [],
            "metadata": {"pagination": {"has_more": False}}
        }

        with patch("paidsearchnav_mcp.server.get_search_terms") as mock_get_st:
            mock_get_st.fn = AsyncMock(return_value=mock_result)

            result = await analyzer.analyze(
                customer_id="1234567890",
                start_date="2024-01-01",
                end_date="2024-01-31"
            )

            assert result.total_records_analyzed == 0
            assert result.estimated_monthly_savings == 0.0
            assert len(result.top_recommendations) == 0

    @pytest.mark.asyncio
    async def test_analyze_identifies_wasteful_terms(self):
        """Test analyze identifies wasteful search terms."""
        analyzer = SearchTermWasteAnalyzer(
            min_cost=10.0,
            min_clicks=5,
            min_impressions=100
        )

        # Create wasteful search terms (no conversions, significant spend)
        mock_result = {
            "status": "success",
            "data": [
                {
                    "search_term": "free coffee",
                    "campaign_name": "Test Campaign",
                    "match_type": "BROAD",
                    "metrics": {
                        "impressions": 500,
                        "clicks": 50,
                        "cost": 100.0,
                        "conversions": 0,  # No conversions
                        "conversion_value": 0.0,
                    }
                },
                {
                    "search_term": "coffee jobs",
                    "campaign_name": "Test Campaign",
                    "match_type": "BROAD",
                    "metrics": {
                        "impressions": 300,
                        "clicks": 30,
                        "cost": 50.0,
                        "conversions": 0,  # No conversions
                        "conversion_value": 0.0,
                    }
                },
                {
                    "search_term": "good coffee",  # Below cost threshold
                    "campaign_name": "Test Campaign",
                    "match_type": "BROAD",
                    "metrics": {
                        "impressions": 200,
                        "clicks": 10,
                        "cost": 5.0,  # Below min_cost
                        "conversions": 0,
                        "conversion_value": 0.0,
                    }
                },
                {
                    "search_term": "coffee shop",  # Has conversions
                    "campaign_name": "Test Campaign",
                    "match_type": "BROAD",
                    "metrics": {
                        "impressions": 1000,
                        "clicks": 100,
                        "cost": 200.0,
                        "conversions": 10,  # Has conversions
                        "conversion_value": 500.0,
                    }
                },
            ],
            "metadata": {"pagination": {"has_more": False}}
        }

        with patch("paidsearchnav_mcp.server.get_search_terms") as mock_get_st:
            mock_get_st.fn = AsyncMock(return_value=mock_result)

            result = await analyzer.analyze(
                customer_id="1234567890",
                start_date="2024-01-01",
                end_date="2024-01-31"
            )

            # Should identify 2 wasteful terms ("free coffee" and "coffee jobs")
            assert result.total_records_analyzed == 4
            assert len(result.top_recommendations) == 2
            assert result.estimated_monthly_savings == 150.0  # 100 + 50
            assert result.top_recommendations[0]["search_term"] == "free coffee"  # Sorted by cost

    @pytest.mark.asyncio
    async def test_analyze_pagination(self):
        """Test analyze handles pagination correctly."""
        analyzer = SearchTermWasteAnalyzer()

        # Mock multiple pages
        page1 = {
            "status": "success",
            "data": [
                {
                    "search_term": "term1",
                    "campaign_name": "Campaign",
                    "match_type": "BROAD",
                    "metrics": {"impressions": 200, "clicks": 20, "cost": 30.0, "conversions": 0}
                }
            ],
            "metadata": {"pagination": {"has_more": True}}
        }
        page2 = {
            "status": "success",
            "data": [
                {
                    "search_term": "term2",
                    "campaign_name": "Campaign",
                    "match_type": "BROAD",
                    "metrics": {"impressions": 200, "clicks": 20, "cost": 40.0, "conversions": 0}
                }
            ],
            "metadata": {"pagination": {"has_more": False}}
        }

        with patch("paidsearchnav_mcp.server.get_search_terms") as mock_get_st:
            mock_get_st.fn = AsyncMock(side_effect=[page1, page2])

            result = await analyzer.analyze(
                customer_id="1234567890",
                start_date="2024-01-01",
                end_date="2024-01-31"
            )

            # Should combine both pages
            assert result.total_records_analyzed == 2
            assert mock_get_st.fn.call_count == 2

    def test_generate_implementation_steps_no_recommendations(self):
        """Test implementation steps with no wasteful terms."""
        analyzer = SearchTermWasteAnalyzer()

        steps = analyzer._generate_implementation_steps([])
        assert len(steps) == 1
        assert "well-optimized" in steps[0]

    def test_generate_implementation_steps_with_recommendations(self):
        """Test implementation steps with wasteful terms."""
        analyzer = SearchTermWasteAnalyzer()

        recommendations = [
            {"search_term": f"term{i}", "estimated_savings": 10.0}
            for i in range(10)
        ]

        steps = analyzer._generate_implementation_steps(recommendations)
        assert len(steps) == 4
        assert "Week 1" in steps[0]
        assert "Week 2" in steps[1]
        assert "Week 3" in steps[2]
        assert "Week 4" in steps[3]


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
