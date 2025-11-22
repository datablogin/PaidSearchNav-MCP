"""Tests for configurable default CPA in SearchTermsAnalyzer."""

from unittest.mock import AsyncMock

from paidsearchnav_mcp.analyzers.search_terms import SearchTermsAnalyzer
from paidsearchnav_mcp.core.config import AnalyzerThresholds
from paidsearchnav_mcp.models import SearchTerm, SearchTermMetrics


class TestSearchTermsAnalyzerConfigurableCPA:
    """Test that SearchTermsAnalyzer uses configurable default CPA."""

    def test_default_cpa_fallback_used_when_no_conversions(self):
        """Test that configurable default CPA is used when no conversions exist."""
        mock_data_provider = AsyncMock()

        # Custom thresholds with different default CPA
        custom_thresholds = AnalyzerThresholds(default_cpa_fallback=75.0)
        analyzer = SearchTermsAnalyzer(mock_data_provider, custom_thresholds)

        # Create search terms with no conversions
        search_terms = [
            SearchTerm(
                search_term="test query 1",
                campaign_id="12345",
                campaign_name="Test Campaign",
                ad_group_id="67890",
                ad_group_name="Test Ad Group",
                keyword_id="11111",
                keyword_text="test keyword",
                match_type="BROAD",
                date_start=None,
                date_end=None,
                metrics=SearchTermMetrics(
                    impressions=100,
                    clicks=5,
                    cost=10.0,
                    conversions=0.0,  # No conversions
                    conversion_value=0.0,
                ),
            ),
            SearchTerm(
                search_term="test query 2",
                campaign_id="12345",
                campaign_name="Test Campaign",
                ad_group_id="67890",
                ad_group_name="Test Ad Group",
                keyword_id="22222",
                keyword_text="another keyword",
                match_type="PHRASE",
                date_start=None,
                date_end=None,
                metrics=SearchTermMetrics(
                    impressions=200,
                    clicks=8,
                    cost=15.0,
                    conversions=0.0,  # No conversions
                    conversion_value=0.0,
                ),
            ),
        ]

        # Calculate average CPA
        avg_cpa = analyzer._calculate_average_cpa(search_terms)

        # Should use the configured default CPA fallback
        assert avg_cpa == 75.0

    def test_actual_cpa_calculated_when_conversions_exist(self):
        """Test that actual CPA is calculated when conversions exist."""
        mock_data_provider = AsyncMock()

        # Custom thresholds with different default CPA
        custom_thresholds = AnalyzerThresholds(default_cpa_fallback=75.0)
        analyzer = SearchTermsAnalyzer(mock_data_provider, custom_thresholds)

        # Create search terms with conversions
        search_terms = [
            SearchTerm(
                search_term="converting query 1",
                campaign_id="12345",
                campaign_name="Test Campaign",
                ad_group_id="67890",
                ad_group_name="Test Ad Group",
                keyword_id="11111",
                keyword_text="converting keyword",
                match_type="EXACT",
                date_start=None,
                date_end=None,
                metrics=SearchTermMetrics(
                    impressions=100,
                    clicks=10,
                    cost=20.0,
                    conversions=2.0,  # Has conversions
                    conversion_value=50.0,
                ),
            ),
            SearchTerm(
                search_term="converting query 2",
                campaign_id="12345",
                campaign_name="Test Campaign",
                ad_group_id="67890",
                ad_group_name="Test Ad Group",
                keyword_id="22222",
                keyword_text="another converting keyword",
                match_type="PHRASE",
                date_start=None,
                date_end=None,
                metrics=SearchTermMetrics(
                    impressions=150,
                    clicks=15,
                    cost=30.0,
                    conversions=3.0,  # Has conversions
                    conversion_value=90.0,
                ),
            ),
        ]

        # Calculate average CPA
        avg_cpa = analyzer._calculate_average_cpa(search_terms)

        # Should calculate actual CPA: (20.0 + 30.0) / (2.0 + 3.0) = 50.0 / 5.0 = 10.0
        assert avg_cpa == 10.0

    def test_default_thresholds_use_standard_fallback(self):
        """Test that default thresholds use the standard 100.0 fallback."""
        mock_data_provider = AsyncMock()

        # Use default thresholds
        analyzer = SearchTermsAnalyzer(mock_data_provider)

        # Create search terms with no conversions
        search_terms = [
            SearchTerm(
                search_term="no conversion query",
                campaign_id="12345",
                campaign_name="Test Campaign",
                ad_group_id="67890",
                ad_group_name="Test Ad Group",
                keyword_id="11111",
                keyword_text="test keyword",
                match_type="BROAD",
                date_start=None,
                date_end=None,
                metrics=SearchTermMetrics(
                    impressions=50,
                    clicks=3,
                    cost=5.0,
                    conversions=0.0,  # No conversions
                    conversion_value=0.0,
                ),
            ),
        ]

        # Calculate average CPA
        avg_cpa = analyzer._calculate_average_cpa(search_terms)

        # Should use the default fallback of 100.0
        assert avg_cpa == 100.0

    def test_mixed_conversion_scenario(self):
        """Test with mixed scenarios - some conversions, some not."""
        mock_data_provider = AsyncMock()

        custom_thresholds = AnalyzerThresholds(default_cpa_fallback=80.0)
        analyzer = SearchTermsAnalyzer(mock_data_provider, custom_thresholds)

        # Mix of converting and non-converting search terms
        search_terms = [
            SearchTerm(
                search_term="converting query",
                campaign_id="12345",
                campaign_name="Test Campaign",
                ad_group_id="67890",
                ad_group_name="Test Ad Group",
                keyword_id="11111",
                keyword_text="converting keyword",
                match_type="EXACT",
                date_start=None,
                date_end=None,
                metrics=SearchTermMetrics(
                    impressions=100,
                    clicks=10,
                    cost=25.0,
                    conversions=1.0,  # Has conversion
                    conversion_value=30.0,
                ),
            ),
            SearchTerm(
                search_term="non-converting query",
                campaign_id="12345",
                campaign_name="Test Campaign",
                ad_group_id="67890",
                ad_group_name="Test Ad Group",
                keyword_id="22222",
                keyword_text="non-converting keyword",
                match_type="BROAD",
                date_start=None,
                date_end=None,
                metrics=SearchTermMetrics(
                    impressions=200,
                    clicks=15,
                    cost=10.0,
                    conversions=0.0,  # No conversions
                    conversion_value=0.0,
                ),
            ),
        ]

        # Calculate average CPA
        avg_cpa = analyzer._calculate_average_cpa(search_terms)

        # Should calculate based on actual conversions: 35.0 total cost / 1.0 total conversions = 35.0
        assert avg_cpa == 35.0
