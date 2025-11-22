"""Mock data provider for testing."""

from __future__ import annotations

import random
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from paidsearchnav.core.models.campaign import (
    BiddingStrategy,
    Campaign,
    CampaignStatus,
    CampaignType,
)
from paidsearchnav.core.models.keyword import Keyword, KeywordMatchType, KeywordStatus
from paidsearchnav.core.models.search_term import SearchTerm, SearchTermMetrics
from paidsearchnav.data_providers.base import DataProvider
from paidsearchnav.security.rate_limiting import validate_multiple_id_lists

if TYPE_CHECKING:
    pass


class MockDataProvider(DataProvider):
    """Mock data provider for testing purposes.

    This provider returns predefined sample data for testing analyzers
    and other components without requiring actual Google Ads data.
    """

    def __init__(self, seed: int = 42):
        """Initialize the mock data provider.

        Args:
            seed: Random seed for consistent test data generation
        """
        self.seed = seed
        self._random = random.Random(seed)

    def _add_variance(self, base_value: float, variance_pct: float = 0.2) -> float:
        """Add seeded random variance to a base value.

        Args:
            base_value: The base value to vary
            variance_pct: Percentage variance (0.2 = ±20%)

        Returns:
            Value with random variance applied
        """
        variance = base_value * variance_pct
        return max(0, base_value + self._random.uniform(-variance, variance))

    async def get_search_terms(
        self,
        customer_id: str,
        start_date: datetime,
        end_date: datetime,
        campaigns: list[str] | None = None,
        ad_groups: list[str] | None = None,
        page_size: int | None = None,
        max_results: int | None = None,
    ) -> list[SearchTerm]:
        """Return sample search terms data."""
        # Validate ID list sizes to prevent DoS
        validated = validate_multiple_id_lists(campaigns=campaigns, ad_groups=ad_groups)
        campaigns = validated["campaigns"]
        ad_groups = validated["ad_groups"]
        # Generate sample search terms with various patterns
        search_terms = []

        # High-performing branded terms
        search_terms.extend(
            [
                SearchTerm(
                    campaign_id="camp_001",
                    campaign_name="Brand - Core",
                    ad_group_id="ag_001",
                    ad_group_name="Brand - Shoes",
                    search_term="brand shoes",
                    keyword_id="kw_001",
                    keyword_text="brand shoes",
                    match_type="EXACT",
                    date_start=(start_date + timedelta(days=1)).date(),
                    date_end=end_date.date(),
                    metrics=SearchTermMetrics(
                        impressions=int(self._add_variance(5000, 0.1)),
                        clicks=int(self._add_variance(500, 0.1)),
                        cost=round(self._add_variance(250.0, 0.1), 2),
                        conversions=round(self._add_variance(50.0, 0.1), 1),
                        conversion_value=round(self._add_variance(2500.0, 0.1), 2),
                    ),
                    classification=None,
                    classification_reason=None,
                    recommendation=None,
                    priority_score=None,
                    detected_location=None,
                ),
                SearchTerm(
                    campaign_id="camp_001",
                    campaign_name="Brand - Core",
                    ad_group_id="ag_001",
                    ad_group_name="Brand - Shoes",
                    search_term="brand shoes near me",
                    keyword_id="kw_002",
                    keyword_text="brand shoes",
                    match_type="PHRASE",
                    date_start=(start_date + timedelta(days=1)).date(),
                    date_end=end_date.date(),
                    metrics=SearchTermMetrics(
                        impressions=3000,
                        clicks=450,
                        cost=225.0,
                        conversions=45.0,
                        conversion_value=2250.0,
                    ),
                    classification=None,
                    classification_reason=None,
                    recommendation=None,
                    priority_score=None,
                    detected_location="near me location",
                    has_near_me=True,
                ),
            ]
        )

        # Low-performing generic terms
        search_terms.extend(
            [
                SearchTerm(
                    campaign_id="camp_002",
                    campaign_name="Generic - Shoes",
                    ad_group_id="ag_002",
                    ad_group_name="Generic - Budget",
                    search_term="cheap shoes",
                    keyword_id="kw_003",
                    keyword_text="cheap shoes",
                    match_type="BROAD",
                    date_start=(start_date + timedelta(days=2)).date(),
                    date_end=end_date.date(),
                    metrics=SearchTermMetrics(
                        impressions=10000,
                        clicks=100,
                        cost=150.0,
                        conversions=2.0,
                        conversion_value=80.0,
                    ),
                    classification=None,
                    classification_reason=None,
                    recommendation=None,
                    priority_score=None,
                    detected_location=None,
                ),
                SearchTerm(
                    campaign_id="camp_002",
                    campaign_name="Generic - Shoes",
                    ad_group_id="ag_002",
                    ad_group_name="Generic - Budget",
                    search_term="free shoes",
                    keyword_id="kw_003",
                    keyword_text="cheap shoes",
                    match_type="BROAD",
                    date_start=(start_date + timedelta(days=2)).date(),
                    date_end=end_date.date(),
                    metrics=SearchTermMetrics(
                        impressions=8000,
                        clicks=400,
                        cost=200.0,
                        conversions=0.0,
                        conversion_value=0.0,
                    ),
                    classification=None,
                    classification_reason=None,
                    recommendation=None,
                    priority_score=None,
                    detected_location=None,
                ),
            ]
        )

        # Location-based terms
        search_terms.extend(
            [
                SearchTerm(
                    campaign_id="camp_003",
                    campaign_name="Local - Stores",
                    ad_group_id="ag_003",
                    ad_group_name="Local - Near Me",
                    search_term="shoe store near me",
                    keyword_id="kw_004",
                    keyword_text="shoe store near me",
                    match_type="EXACT",
                    date_start=(start_date + timedelta(days=3)).date(),
                    date_end=end_date.date(),
                    metrics=SearchTermMetrics(
                        impressions=2000,
                        clicks=300,
                        cost=180.0,
                        conversions=30.0,
                        conversion_value=1200.0,
                    ),
                    classification=None,
                    classification_reason=None,
                    recommendation=None,
                    priority_score=None,
                    detected_location="near me",
                    has_near_me=True,
                    has_location=True,
                    location_terms=["near me"],
                ),
                SearchTerm(
                    campaign_id="camp_003",
                    campaign_name="Local - Stores",
                    ad_group_id="ag_004",
                    ad_group_name="Local - Cities",
                    search_term="shoe store chicago",
                    keyword_id="kw_005",
                    keyword_text="shoe store",
                    match_type="EXACT",
                    date_start=(start_date + timedelta(days=3)).date(),
                    date_end=end_date.date(),
                    metrics=SearchTermMetrics(
                        impressions=1500,
                        clicks=200,
                        cost=120.0,
                        conversions=20.0,
                        conversion_value=800.0,
                    ),
                    classification=None,
                    classification_reason=None,
                    recommendation=None,
                    priority_score=None,
                    detected_location="chicago",
                    has_location=True,
                    location_terms=["chicago"],
                ),
            ]
        )

        # Filter by campaigns if specified
        if campaigns:
            search_terms = [st for st in search_terms if st.campaign_name in campaigns]

        # Filter by ad groups if specified
        if ad_groups:
            search_terms = [st for st in search_terms if st.ad_group_name in ad_groups]

        return search_terms

    async def get_keywords(
        self,
        customer_id: str,
        campaigns: list[str] | None = None,
        ad_groups: list[str] | None = None,
        campaign_id: str | None = None,
        include_metrics: bool = True,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        page_size: int | None = None,
        max_results: int | None = None,
    ) -> list[Keyword]:
        """Return sample keyword data."""
        # Validate ID list sizes to prevent DoS
        validated = validate_multiple_id_lists(campaigns=campaigns, ad_groups=ad_groups)
        campaigns = validated["campaigns"]
        ad_groups = validated["ad_groups"]
        keywords = [
            # Brand keywords
            Keyword(
                keyword_id="kw_001",
                text="brand shoes",
                match_type=KeywordMatchType.EXACT,
                status=KeywordStatus.ENABLED,
                campaign_id="camp_001",
                campaign_name="Brand - Core",
                ad_group_id="ag_001",
                ad_group_name="Brand - Shoes",
                cpc_bid=5.0,
                quality_score=9,
                impressions=5000,
                clicks=500,
                cost=250.0,
                conversions=50.0,
                conversion_value=2500.0,
            ),
            Keyword(
                keyword_id="kw_002",
                text="brand shoes",
                match_type=KeywordMatchType.PHRASE,
                status=KeywordStatus.ENABLED,
                campaign_id="camp_001",
                campaign_name="Brand - Core",
                ad_group_id="ag_001",
                ad_group_name="Brand - Shoes",
                cpc_bid=4.0,
                quality_score=8,
                impressions=3000,
                clicks=300,
                cost=150.0,
                conversions=30.0,
                conversion_value=1500.0,
            ),
            # Generic keywords
            Keyword(
                keyword_id="kw_003",
                text="cheap shoes",
                match_type=KeywordMatchType.BROAD,
                status=KeywordStatus.ENABLED,
                campaign_id="camp_002",
                campaign_name="Generic - Shoes",
                ad_group_id="ag_002",
                ad_group_name="Generic - Budget",
                cpc_bid=1.5,
                quality_score=5,
                impressions=10000,
                clicks=100,
                cost=150.0,
                conversions=2.0,
                conversion_value=80.0,
            ),
            # Local keywords
            Keyword(
                keyword_id="kw_004",
                text="shoe store near me",
                match_type=KeywordMatchType.EXACT,
                status=KeywordStatus.ENABLED,
                campaign_id="camp_003",
                campaign_name="Local - Stores",
                ad_group_id="ag_003",
                ad_group_name="Local - Near Me",
                cpc_bid=3.0,
                quality_score=7,
                impressions=2000,
                clicks=300,
                cost=180.0,
                conversions=30.0,
                conversion_value=1200.0,
            ),
            # Paused keyword
            Keyword(
                keyword_id="kw_005",
                text="discount shoes",
                match_type=KeywordMatchType.BROAD,
                status=KeywordStatus.PAUSED,
                campaign_id="camp_002",
                campaign_name="Generic - Shoes",
                ad_group_id="ag_002",
                ad_group_name="Generic - Budget",
                cpc_bid=1.0,
                quality_score=4,
                impressions=0,
                clicks=0,
                cost=0.0,
                conversions=0.0,
                conversion_value=0.0,
            ),
        ]

        # Filter by campaigns if specified
        if campaigns:
            keywords = [kw for kw in keywords if kw.campaign_name in campaigns]

        # Filter by ad groups if specified
        if ad_groups:
            keywords = [kw for kw in keywords if kw.ad_group_name in ad_groups]

        # Filter by campaign_id if specified
        if campaign_id:
            keywords = [kw for kw in keywords if kw.campaign_id == campaign_id]

        return keywords

    async def get_negative_keywords(
        self,
        customer_id: str,
        include_shared_sets: bool = True,
        page_size: int | None = None,
        max_results: int | None = None,
    ) -> list[dict[str, Any]]:
        """Return sample negative keyword data."""
        negatives = [
            # Campaign-level negatives
            {
                "text": "free",
                "match_type": "BROAD",
                "level": "CAMPAIGN",
                "campaign_name": "Brand - Core",
                "campaign_id": "camp_001",
                "ad_group_name": "",
                "shared_set_name": "",
            },
            {
                "text": "cheap",
                "match_type": "PHRASE",
                "level": "CAMPAIGN",
                "campaign_name": "Brand - Core",
                "campaign_id": "camp_001",
                "ad_group_name": "",
                "shared_set_name": "",
            },
            # Ad group-level negatives
            {
                "text": "used shoes",
                "match_type": "EXACT",
                "level": "AD_GROUP",
                "campaign_name": "Generic - Shoes",
                "campaign_id": "camp_002",
                "ad_group_name": "Generic - New",
                "shared_set_name": "",
            },
        ]

        # Shared set negatives
        if include_shared_sets:
            negatives.extend(
                [
                    {
                        "text": "jobs",
                        "match_type": "BROAD",
                        "level": "SHARED_SET",
                        "campaign_name": "",
                        "campaign_id": "",
                        "ad_group_name": "",
                        "shared_set_name": "Universal Negatives",
                    },
                    {
                        "text": "careers",
                        "match_type": "BROAD",
                        "level": "SHARED_SET",
                        "campaign_name": "",
                        "campaign_id": "",
                        "ad_group_name": "",
                        "shared_set_name": "Universal Negatives",
                    },
                ]
            )

        return negatives

    async def get_campaigns(
        self,
        customer_id: str,
        campaign_types: list[str] | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        page_size: int | None = None,
        max_results: int | None = None,
    ) -> list[Campaign]:
        """Return sample campaign data."""
        campaigns = [
            Campaign(
                campaign_id="camp_001",
                customer_id="customer_123",
                name="Brand - Core",
                status=CampaignStatus.ENABLED,
                type=CampaignType.SEARCH,
                budget_amount=1000.0,
                budget_currency="USD",
                bidding_strategy=BiddingStrategy.TARGET_CPA,
                target_cpa=50.0,
                impressions=10000,
                clicks=1000,
                cost=500.0,
                conversions=100.0,
                conversion_value=5000.0,
            ),
            Campaign(
                campaign_id="camp_002",
                customer_id="customer_123",
                name="Generic - Shoes",
                status=CampaignStatus.ENABLED,
                type=CampaignType.SEARCH,
                budget_amount=500.0,
                budget_currency="USD",
                bidding_strategy=BiddingStrategy.MAXIMIZE_CLICKS,
                impressions=20000,
                clicks=500,
                cost=400.0,
                conversions=5.0,
                conversion_value=200.0,
            ),
            Campaign(
                campaign_id="camp_003",
                customer_id="customer_123",
                name="Local - Stores",
                status=CampaignStatus.ENABLED,
                type=CampaignType.SEARCH,
                budget_amount=750.0,
                budget_currency="USD",
                bidding_strategy=BiddingStrategy.TARGET_ROAS,
                target_roas=400.0,
                impressions=5000,
                clicks=750,
                cost=450.0,
                conversions=75.0,
                conversion_value=3000.0,
            ),
            Campaign(
                campaign_id="camp_004",
                customer_id="customer_123",
                name="Performance Max - All Products",
                status=CampaignStatus.ENABLED,
                type=CampaignType.PERFORMANCE_MAX,
                budget_amount=2000.0,
                budget_currency="USD",
                bidding_strategy=BiddingStrategy.MAXIMIZE_CONVERSION_VALUE,
                impressions=50000,
                clicks=2000,
                cost=1500.0,
                conversions=150.0,
                conversion_value=7500.0,
            ),
        ]

        # Filter by campaign types if specified
        if campaign_types:
            type_map = {
                "SEARCH": CampaignType.SEARCH,
                "PERFORMANCE_MAX": CampaignType.PERFORMANCE_MAX,
            }
            allowed_types = {type_map.get(ct, ct) for ct in campaign_types}
            campaigns = [c for c in campaigns if c.type in allowed_types]

        return campaigns

    async def get_shared_negative_lists(
        self,
        customer_id: str,
    ) -> list[dict[str, Any]]:
        """Return sample shared negative keyword lists."""
        return [
            {
                "id": "snl_001",
                "name": "Universal Negatives",
                "negative_count": 25,
            },
            {
                "id": "snl_002",
                "name": "Competitor Brands",
                "negative_count": 50,
            },
            {
                "id": "snl_003",
                "name": "Adult Content",
                "negative_count": 100,
            },
        ]

    async def get_campaign_shared_sets(
        self,
        customer_id: str,
        campaign_id: str,
    ) -> list[dict[str, Any]]:
        """Get shared sets applied to a specific campaign."""
        # Map campaigns to their shared sets
        campaign_sets = {
            "camp_001": [
                {"id": "snl_001", "name": "Universal Negatives"},
                {"id": "snl_003", "name": "Adult Content"},
            ],
            "camp_002": [
                {"id": "snl_001", "name": "Universal Negatives"},
                {"id": "snl_002", "name": "Competitor Brands"},
            ],
            "camp_003": [
                {"id": "snl_001", "name": "Universal Negatives"},
            ],
        }

        return campaign_sets.get(campaign_id, [])

    async def get_shared_set_negatives(
        self,
        customer_id: str,
        shared_set_id: str,
    ) -> list[dict[str, Any]]:
        """Get negative keywords from a specific shared set."""
        # Map shared sets to their negatives
        shared_set_negatives = {
            "snl_001": [
                {"text": "jobs"},
                {"text": "careers"},
                {"text": "employment"},
                {"text": "hiring"},
                {"text": "resume"},
            ],
            "snl_002": [
                {"text": "competitor1"},
                {"text": "competitor2"},
                {"text": "rival brand"},
            ],
            "snl_003": [
                {"text": "adult"},
                {"text": "xxx"},
                {"text": "porn"},
            ],
        }

        negatives = shared_set_negatives.get(shared_set_id, [])
        return [{"text": neg["text"]} for neg in negatives]

    async def get_placement_data(
        self,
        customer_id: str,
        start_date: datetime,
        end_date: datetime,
        campaigns: list[str] | None = None,
        ad_groups: list[str] | None = None,
        page_size: int | None = None,
        max_results: int | None = None,
    ) -> list[dict[str, Any]]:
        """Return sample placement data."""
        placements = [
            {
                "placement_id": "pl_001",
                "placement_name": "example.com",
                "display_name": "Example Website",
                "impressions": 10000,
                "clicks": 100,
                "cost": 50.0,
                "conversions": 5.0,
                "conversion_value": 250.0,
                "ctr": 1.0,
                "cpc": 0.5,
                "cpa": 10.0,
                "roas": 500.0,
                "campaign_ids": ["camp_004"],
                "ad_group_ids": ["ag_004"],
                "is_brand_safe": True,
                "is_relevant": True,
            },
            {
                "placement_id": "pl_002",
                "placement_name": "spam-site.net",
                "display_name": "Spam Website",
                "impressions": 50000,
                "clicks": 2000,
                "cost": 200.0,
                "conversions": 0.0,
                "conversion_value": 0.0,
                "ctr": 4.0,
                "cpc": 0.1,
                "cpa": 0.0,
                "roas": 0.0,
                "campaign_ids": ["camp_004"],
                "ad_group_ids": ["ag_004"],
                "is_brand_safe": False,
                "is_relevant": False,
                "exclusion_reason": "Low quality, no conversions",
            },
            {
                "placement_id": "pl_003",
                "placement_name": "news-site.com",
                "display_name": "News Website",
                "impressions": 20000,
                "clicks": 400,
                "cost": 300.0,
                "conversions": 20.0,
                "conversion_value": 1000.0,
                "ctr": 2.0,
                "cpc": 0.75,
                "cpa": 15.0,
                "roas": 333.33,
                "campaign_ids": ["camp_004"],
                "ad_group_ids": ["ag_004"],
                "is_brand_safe": True,
                "is_relevant": True,
            },
        ]

        # Filter by campaigns if specified
        if campaigns:
            placements = [
                p
                for p in placements
                if any(cid in campaigns for cid in p["campaign_ids"])
            ]

        # Filter by ad groups if specified
        if ad_groups:
            placements = [
                p
                for p in placements
                if any(aid in ad_groups for aid in p["ad_group_ids"])
            ]

        return placements

    def get_sample_search_terms(self) -> list[SearchTerm]:
        """Get sample search terms for testing.

        This is a convenience method for getting test data without
        specifying date ranges and filters.
        """
        import asyncio

        return asyncio.run(
            self.get_search_terms(
                customer_id="test",
                start_date=datetime.now() - timedelta(days=30),
                end_date=datetime.now(),
            )
        )
