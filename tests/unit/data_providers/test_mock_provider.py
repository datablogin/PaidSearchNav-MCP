"""Tests for the MockDataProvider."""

from datetime import datetime, timedelta

import pytest

from paidsearchnav_mcp.models.campaign import CampaignStatus, CampaignType
from paidsearchnav_mcp.models.keyword import KeywordMatchType, KeywordStatus
from paidsearchnav_mcp.data_providers.mock_provider import MockDataProvider


class TestMockDataProvider:
    """Test the mock data provider implementation."""

    @pytest.fixture
    def provider(self):
        """Create a mock data provider instance."""
        return MockDataProvider(seed=42)

    @pytest.fixture
    def date_range(self):
        """Create a standard date range for testing."""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        return start_date, end_date

    @pytest.mark.asyncio
    async def test_get_search_terms(self, provider, date_range):
        """Test getting search terms from mock provider."""
        start_date, end_date = date_range

        terms = await provider.get_search_terms(
            customer_id="test_customer",
            start_date=start_date,
            end_date=end_date,
        )

        assert len(terms) > 0

        # Check that we have different types of terms
        brand_terms = [t for t in terms if "brand" in t.search_term.lower()]
        assert len(brand_terms) > 0

        local_terms = [t for t in terms if "near me" in t.search_term.lower()]
        assert len(local_terms) > 0

        # Check data structure
        for term in terms:
            assert term.search_term
            assert term.campaign_id
            assert term.campaign_name
            assert term.metrics.impressions >= 0
            assert term.metrics.clicks >= 0
            assert term.metrics.cost >= 0

    @pytest.mark.asyncio
    async def test_get_search_terms_with_filters(self, provider, date_range):
        """Test filtering search terms by campaign and ad group."""
        start_date, end_date = date_range

        # Get all terms first
        all_terms = await provider.get_search_terms(
            customer_id="test_customer",
            start_date=start_date,
            end_date=end_date,
        )

        # Filter by campaign
        filtered_terms = await provider.get_search_terms(
            customer_id="test_customer",
            start_date=start_date,
            end_date=end_date,
            campaigns=["Brand - Core"],
        )

        assert len(filtered_terms) < len(all_terms)
        assert all(t.campaign_name == "Brand - Core" for t in filtered_terms)

    @pytest.mark.asyncio
    async def test_get_keywords(self, provider):
        """Test getting keywords from mock provider."""
        keywords = await provider.get_keywords(customer_id="test_customer")

        assert len(keywords) > 0

        # Check different match types
        exact_keywords = [k for k in keywords if k.match_type == KeywordMatchType.EXACT]
        phrase_keywords = [
            k for k in keywords if k.match_type == KeywordMatchType.PHRASE
        ]
        broad_keywords = [k for k in keywords if k.match_type == KeywordMatchType.BROAD]

        assert len(exact_keywords) > 0
        assert len(phrase_keywords) > 0
        assert len(broad_keywords) > 0

        # Check for enabled and paused keywords
        enabled_keywords = [k for k in keywords if k.status == KeywordStatus.ENABLED]
        paused_keywords = [k for k in keywords if k.status == KeywordStatus.PAUSED]

        assert len(enabled_keywords) > 0
        assert len(paused_keywords) > 0

    @pytest.mark.asyncio
    async def test_get_negative_keywords(self, provider):
        """Test getting negative keywords from mock provider."""
        negatives = await provider.get_negative_keywords(
            customer_id="test_customer",
            include_shared_sets=True,
        )

        assert len(negatives) > 0

        # Check different levels
        campaign_negatives = [n for n in negatives if n["level"] == "CAMPAIGN"]
        ad_group_negatives = [n for n in negatives if n["level"] == "AD_GROUP"]
        shared_set_negatives = [n for n in negatives if n["level"] == "SHARED_SET"]

        assert len(campaign_negatives) > 0
        assert len(ad_group_negatives) > 0
        assert len(shared_set_negatives) > 0

        # Test without shared sets
        negatives_no_shared = await provider.get_negative_keywords(
            customer_id="test_customer",
            include_shared_sets=False,
        )

        assert len(negatives_no_shared) < len(negatives)
        assert all(n["level"] != "SHARED_SET" for n in negatives_no_shared)

    @pytest.mark.asyncio
    async def test_get_campaigns(self, provider):
        """Test getting campaigns from mock provider."""
        campaigns = await provider.get_campaigns(customer_id="test_customer")

        assert len(campaigns) > 0

        # Check different campaign types
        search_campaigns = [c for c in campaigns if c.type == CampaignType.SEARCH]
        pmax_campaigns = [
            c for c in campaigns if c.type == CampaignType.PERFORMANCE_MAX
        ]

        assert len(search_campaigns) > 0
        assert len(pmax_campaigns) > 0

        # Check campaign data
        for campaign in campaigns:
            assert campaign.campaign_id
            assert campaign.name
            assert campaign.status == CampaignStatus.ENABLED
            assert campaign.budget_amount > 0
            assert campaign.bidding_strategy

    @pytest.mark.asyncio
    async def test_get_campaigns_filtered_by_type(self, provider):
        """Test filtering campaigns by type."""
        search_only = await provider.get_campaigns(
            customer_id="test_customer",
            campaign_types=["SEARCH"],
        )

        assert all(c.type == CampaignType.SEARCH for c in search_only)

        pmax_only = await provider.get_campaigns(
            customer_id="test_customer",
            campaign_types=["PERFORMANCE_MAX"],
        )

        assert all(c.type == CampaignType.PERFORMANCE_MAX for c in pmax_only)

    @pytest.mark.asyncio
    async def test_get_shared_negative_lists(self, provider):
        """Test getting shared negative lists from mock provider."""
        lists = await provider.get_shared_negative_lists(customer_id="test_customer")

        assert len(lists) > 0

        for lst in lists:
            assert lst["id"]
            assert lst["name"]
            assert lst["negative_count"] > 0

    @pytest.mark.asyncio
    async def test_get_campaign_shared_sets(self, provider):
        """Test getting shared sets for a campaign."""
        # Test with a campaign that has shared sets
        sets = await provider.get_campaign_shared_sets(
            customer_id="test_customer",
            campaign_id="camp_001",
        )

        assert len(sets) > 0

        for set_info in sets:
            assert set_info["id"]
            assert set_info["name"]

        # Test with a campaign that has no shared sets
        no_sets = await provider.get_campaign_shared_sets(
            customer_id="test_customer",
            campaign_id="camp_999",
        )

        assert len(no_sets) == 0

    @pytest.mark.asyncio
    async def test_get_shared_set_negatives(self, provider):
        """Test getting negatives from a shared set."""
        negatives = await provider.get_shared_set_negatives(
            customer_id="test_customer",
            shared_set_id="snl_001",
        )

        assert len(negatives) > 0

        for negative in negatives:
            assert negative["text"]

    @pytest.mark.asyncio
    async def test_get_placement_data(self, provider, date_range):
        """Test getting placement data from mock provider."""
        start_date, end_date = date_range

        placements = await provider.get_placement_data(
            customer_id="test_customer",
            start_date=start_date,
            end_date=end_date,
        )

        assert len(placements) > 0

        # Check placement data structure
        for placement in placements:
            assert placement["placement_id"]
            assert placement["placement_name"]
            assert placement["impressions"] >= 0
            assert placement["clicks"] >= 0
            assert placement["cost"] >= 0
            assert "is_brand_safe" in placement
            assert "is_relevant" in placement

        # Check for different types of placements
        good_placements = [p for p in placements if p.get("is_brand_safe", False)]
        bad_placements = [p for p in placements if not p.get("is_brand_safe", True)]

        assert len(good_placements) > 0
        assert len(bad_placements) > 0

    def test_get_sample_search_terms(self, provider):
        """Test the convenience method for getting sample search terms."""
        terms = provider.get_sample_search_terms()

        assert len(terms) > 0
        assert all(hasattr(t, "search_term") for t in terms)

    def test_consistent_data_with_seed(self):
        """Test that the same seed produces consistent data."""
        provider1 = MockDataProvider(seed=123)
        provider2 = MockDataProvider(seed=123)

        terms1 = provider1.get_sample_search_terms()
        terms2 = provider2.get_sample_search_terms()

        assert len(terms1) == len(terms2)
        assert all(t1.search_term == t2.search_term for t1, t2 in zip(terms1, terms2))
