"""Tests for the SearchTermsProvider."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock

import pytest

from paidsearchnav.core.models.search_term import SearchTerm
from paidsearchnav.data_providers.search_terms_provider import SearchTermsProvider


class TestSearchTermsProvider:
    """Test the search terms provider implementation."""

    @pytest.fixture
    def mock_data_provider(self):
        """Create a mock data provider."""
        provider = Mock()
        provider.get_search_terms = AsyncMock()
        return provider

    @pytest.fixture
    def search_terms_provider(self, mock_data_provider):
        """Create a SearchTermsProvider with mock data provider."""
        return SearchTermsProvider(data_provider=mock_data_provider)

    @pytest.fixture
    def date_range(self):
        """Create a standard date range for testing."""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        return start_date, end_date

    @pytest.fixture
    def sample_search_terms(self):
        """Create sample search terms for testing."""
        from paidsearchnav.core.models.search_term import SearchTermMetrics

        return [
            SearchTerm(
                campaign_id="camp_1",
                campaign_name="Local Campaign",
                ad_group_id="ag_1",
                ad_group_name="Near Me Terms",
                search_term="shoes near me",
                match_type="EXACT",
                metrics=SearchTermMetrics(
                    impressions=1000,
                    clicks=100,
                    cost=50.0,
                    conversions=10.0,
                    conversion_value=500.0,
                ),
                has_near_me=True,
            ),
            SearchTerm(
                campaign_id="camp_1",
                campaign_name="Local Campaign",
                ad_group_id="ag_2",
                ad_group_name="City Terms",
                search_term="red shoes chicago",
                match_type="PHRASE",
                metrics=SearchTermMetrics(
                    impressions=500,
                    clicks=50,
                    cost=25.0,
                    conversions=5.0,
                    conversion_value=250.0,
                ),
                has_location=True,
                detected_location="chicago",
            ),
            SearchTerm(
                campaign_id="camp_2",
                campaign_name="Generic Campaign",
                ad_group_id="ag_3",
                ad_group_name="Budget Terms",
                search_term="cheap shoes",
                match_type="BROAD",
                metrics=SearchTermMetrics(
                    impressions=5000,
                    clicks=200,
                    cost=150.0,
                    conversions=2.0,
                    conversion_value=80.0,
                ),
            ),
            SearchTerm(
                campaign_id="camp_2",
                campaign_name="Generic Campaign",
                ad_group_id="ag_3",
                ad_group_name="Budget Terms",
                search_term="free shipping shoes",
                match_type="BROAD",
                metrics=SearchTermMetrics(
                    impressions=3000,
                    clicks=300,
                    cost=200.0,
                    conversions=0.0,
                    conversion_value=0.0,
                ),
            ),
            SearchTerm(
                campaign_id="camp_3",
                campaign_name="Brand Campaign",
                ad_group_id="ag_4",
                ad_group_name="Brand Terms",
                search_term="brand shoes",
                match_type="EXACT",
                metrics=SearchTermMetrics(
                    impressions=2000,
                    clicks=400,
                    cost=100.0,
                    conversions=40.0,
                    conversion_value=2000.0,
                ),
            ),
            SearchTerm(
                campaign_id="camp_1",
                campaign_name="Local Campaign",
                ad_group_id="ag_2",
                ad_group_name="City Terms",
                search_term="shoes in 60601",
                match_type="EXACT",
                metrics=SearchTermMetrics(
                    impressions=300,
                    clicks=30,
                    cost=15.0,
                    conversions=3.0,
                    conversion_value=150.0,
                ),
                has_location=True,
                detected_location="60601",
            ),
            SearchTerm(
                campaign_id="camp_2",
                campaign_name="Generic Campaign",
                ad_group_id="ag_5",
                ad_group_name="Question Terms",
                search_term="what are the best running shoes",
                match_type="BROAD",
                metrics=SearchTermMetrics(
                    impressions=800,
                    clicks=40,
                    cost=20.0,
                    conversions=1.0,
                    conversion_value=50.0,
                ),
            ),
        ]

    @pytest.mark.asyncio
    async def test_get_search_terms_with_local_intent(
        self, search_terms_provider, mock_data_provider, sample_search_terms, date_range
    ):
        """Test getting search terms with local intent."""
        start_date, end_date = date_range
        mock_data_provider.get_search_terms.return_value = sample_search_terms

        local_terms = await search_terms_provider.get_search_terms_with_local_intent(
            customer_id="test",
            start_date=start_date,
            end_date=end_date,
        )

        # Should find "near me", city name, and ZIP code terms
        assert len(local_terms) == 2
        assert any("near me" in t.search_term for t in local_terms)
        assert any("60601" in t.search_term for t in local_terms)

    @pytest.mark.asyncio
    async def test_get_high_cost_low_conversion_terms(
        self, search_terms_provider, mock_data_provider, sample_search_terms, date_range
    ):
        """Test getting high cost, low conversion terms."""
        start_date, end_date = date_range
        mock_data_provider.get_search_terms.return_value = sample_search_terms

        wasteful_terms = await search_terms_provider.get_high_cost_low_conversion_terms(
            customer_id="test",
            start_date=start_date,
            end_date=end_date,
            min_cost=100.0,
            max_conversion_rate=0.01,
        )

        # Should find "free shipping shoes" (200 cost, 0 conversions) and "cheap shoes" (150 cost, low conv rate)
        assert len(wasteful_terms) == 2
        assert wasteful_terms[0].search_term == "free shipping shoes"  # Highest cost
        assert wasteful_terms[1].search_term == "cheap shoes"

        # Verify they meet criteria
        for term in wasteful_terms:
            assert term.cost >= 100.0
            conv_rate = term.conversions / term.clicks if term.clicks > 0 else 0
            assert conv_rate <= 0.01

    @pytest.mark.asyncio
    async def test_get_brand_vs_non_brand_terms(
        self, search_terms_provider, mock_data_provider, sample_search_terms, date_range
    ):
        """Test segmenting brand vs non-brand terms."""
        start_date, end_date = date_range
        mock_data_provider.get_search_terms.return_value = sample_search_terms

        (
            brand_terms,
            non_brand_terms,
        ) = await search_terms_provider.get_brand_vs_non_brand_terms(
            customer_id="test",
            start_date=start_date,
            end_date=end_date,
            brand_keywords=["brand"],
        )

        assert len(brand_terms) == 1
        assert brand_terms[0].search_term == "brand shoes"

        assert len(non_brand_terms) == len(sample_search_terms) - 1

    @pytest.mark.asyncio
    async def test_get_search_terms_by_performance_tier(
        self, search_terms_provider, mock_data_provider, sample_search_terms, date_range
    ):
        """Test categorizing search terms by performance tiers."""
        start_date, end_date = date_range
        mock_data_provider.get_search_terms.return_value = sample_search_terms

        tiers = await search_terms_provider.get_search_terms_by_performance_tier(
            customer_id="test",
            start_date=start_date,
            end_date=end_date,
        )

        # Check tier assignments
        assert len(tiers["top_performers"]) > 0  # "brand shoes" with 2000% ROAS
        assert len(tiers["good_performers"]) > 0  # Terms with 100-300% ROAS
        assert (
            len(tiers["no_conversions"]) > 0
        )  # "free shipping shoes" with 0 conversions

        # Verify ROAS calculations
        for term in tiers["top_performers"]:
            roas = (
                (term.metrics.conversion_value / term.metrics.cost * 100)
                if term.metrics.cost > 0
                else 0
            )
            assert roas >= 300

        for term in tiers["no_conversions"]:
            assert term.metrics.conversions == 0
            assert term.metrics.cost >= 50

    @pytest.mark.asyncio
    async def test_get_question_search_terms(
        self, search_terms_provider, mock_data_provider, sample_search_terms, date_range
    ):
        """Test getting question search terms."""
        start_date, end_date = date_range
        mock_data_provider.get_search_terms.return_value = sample_search_terms

        question_terms = await search_terms_provider.get_question_search_terms(
            customer_id="test",
            start_date=start_date,
            end_date=end_date,
        )

        assert len(question_terms) == 1
        assert question_terms[0].search_term == "what are the best running shoes"

    @pytest.mark.asyncio
    async def test_get_competitor_related_terms(
        self, search_terms_provider, mock_data_provider, date_range
    ):
        """Test getting competitor-related terms."""
        from paidsearchnav.core.models.search_term import SearchTermMetrics

        start_date, end_date = date_range

        # Add competitor terms to sample data
        terms_with_competitors = [
            SearchTerm(
                campaign_id="camp_comp",
                campaign_name="Competitor Campaign",
                ad_group_id="ag_comp",
                ad_group_name="Competitor Terms",
                search_term="nike running shoes",
                match_type="EXACT",
                metrics=SearchTermMetrics(
                    impressions=1000,
                    clicks=50,
                    cost=75.0,
                    conversions=5.0,
                    conversion_value=250.0,
                ),
            ),
            SearchTerm(
                campaign_id="camp_comp",
                campaign_name="Competitor Campaign",
                ad_group_id="ag_comp",
                ad_group_name="Competitor Terms",
                search_term="adidas vs our brand",
                match_type="PHRASE",
                metrics=SearchTermMetrics(
                    impressions=500,
                    clicks=25,
                    cost=37.5,
                    conversions=2.5,
                    conversion_value=125.0,
                ),
            ),
            SearchTerm(
                campaign_id="camp_gen",
                campaign_name="Generic Campaign",
                ad_group_id="ag_gen",
                ad_group_name="Generic Terms",
                search_term="running shoes",
                match_type="BROAD",
                metrics=SearchTermMetrics(
                    impressions=2000,
                    clicks=100,
                    cost=150.0,
                    conversions=10.0,
                    conversion_value=500.0,
                ),
            ),
        ]

        mock_data_provider.get_search_terms.return_value = terms_with_competitors

        competitor_terms = await search_terms_provider.get_competitor_related_terms(
            customer_id="test",
            start_date=start_date,
            end_date=end_date,
            competitor_names=["Nike", "Adidas"],
        )

        assert len(competitor_terms) == 2
        assert all(
            any(comp.lower() in t.search_term.lower() for comp in ["nike", "adidas"])
            for t in competitor_terms
        )

    @pytest.mark.asyncio
    async def test_get_search_term_summary_stats(
        self, search_terms_provider, mock_data_provider, sample_search_terms, date_range
    ):
        """Test getting summary statistics for search terms."""
        start_date, end_date = date_range
        mock_data_provider.get_search_terms.return_value = sample_search_terms

        stats = await search_terms_provider.get_search_term_summary_stats(
            customer_id="test",
            start_date=start_date,
            end_date=end_date,
        )

        # Verify totals
        assert stats["total_terms"] == len(sample_search_terms)
        assert stats["total_impressions"] == sum(
            t.impressions for t in sample_search_terms
        )
        assert stats["total_clicks"] == sum(t.clicks for t in sample_search_terms)
        assert stats["total_cost"] == round(sum(t.cost for t in sample_search_terms), 2)

        # Verify averages
        assert stats["avg_ctr"] > 0
        assert stats["avg_cpc"] > 0
        assert stats["avg_conversion_rate"] >= 0
        assert stats["avg_roas"] > 0

        # Verify top lists
        assert len(stats["top_terms_by_conversions"]) > 0
        assert len(stats["top_terms_by_cost"]) > 0
        assert len(stats["worst_terms_by_waste"]) > 0

        # Verify top term by conversions is "brand shoes"
        assert stats["top_terms_by_conversions"][0]["term"] == "brand shoes"
        assert stats["top_terms_by_conversions"][0]["conversions"] == 40.0

    @pytest.mark.asyncio
    async def test_get_search_term_summary_stats_empty(
        self, search_terms_provider, mock_data_provider, date_range
    ):
        """Test getting summary statistics with no search terms."""
        start_date, end_date = date_range
        mock_data_provider.get_search_terms.return_value = []

        stats = await search_terms_provider.get_search_term_summary_stats(
            customer_id="test",
            start_date=start_date,
            end_date=end_date,
        )

        # Verify all values are zero or empty
        assert stats["total_terms"] == 0
        assert stats["total_impressions"] == 0
        assert stats["total_clicks"] == 0
        assert stats["total_cost"] == 0.0
        assert stats["avg_ctr"] == 0.0
        assert stats["avg_cpc"] == 0.0
        assert stats["top_terms_by_conversions"] == []
        assert stats["top_terms_by_cost"] == []
        assert stats["worst_terms_by_waste"] == []

    def test_initialization(self, mock_data_provider):
        """Test SearchTermsProvider initialization."""
        provider = SearchTermsProvider(data_provider=mock_data_provider)
        assert provider.data_provider is mock_data_provider
