"""Base DataProvider interface for all data providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from paidsearchnav.core.models.campaign import Campaign
    from paidsearchnav.core.models.keyword import Keyword
    from paidsearchnav.core.models.search_term import SearchTerm


class DataProvider(ABC):
    """Interface for data providers that fetch campaign data from various sources."""

    @abstractmethod
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
        """Fetch search terms report data."""
        pass

    @abstractmethod
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
        """Fetch keyword data."""
        pass

    @abstractmethod
    async def get_negative_keywords(
        self,
        customer_id: str,
        include_shared_sets: bool = True,
        page_size: int | None = None,
        max_results: int | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch negative keyword data."""
        pass

    @abstractmethod
    async def get_campaigns(
        self,
        customer_id: str,
        campaign_types: list[str] | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        page_size: int | None = None,
        max_results: int | None = None,
    ) -> list[Campaign]:
        """Fetch campaign data."""
        pass

    @abstractmethod
    async def get_shared_negative_lists(
        self,
        customer_id: str,
    ) -> list[dict[str, Any]]:
        """Fetch shared negative keyword lists.

        Returns list of dictionaries with at least: id, name, negative_count
        """
        pass

    @abstractmethod
    async def get_campaign_shared_sets(
        self,
        customer_id: str,
        campaign_id: str,
    ) -> list[dict[str, Any]]:
        """Get shared sets applied to a specific campaign.

        Returns list of dictionaries with at least: id, name
        """
        pass

    @abstractmethod
    async def get_shared_set_negatives(
        self,
        customer_id: str,
        shared_set_id: str,
    ) -> list[dict[str, Any]]:
        """Get negative keywords from a specific shared set.

        Returns list of dictionaries with at least: text (the negative keyword)
        """
        pass

    @abstractmethod
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
        """Fetch placement performance data.

        Returns list of dictionaries with placement data including:
        - placement_id: str - Unique placement identifier
        - placement_name: str - Placement name or URL
        - display_name: str - Display name for the placement
        - impressions: int - Total impressions
        - clicks: int - Total clicks
        - cost: float - Total cost
        - conversions: float - Total conversions
        - conversion_value: float - Total conversion value
        - ctr: float - Click-through rate
        - cpc: float - Cost per click
        - cpa: float - Cost per acquisition
        - roas: float - Return on ad spend
        - campaign_ids: list[str] - Associated campaigns
        - ad_group_ids: list[str] - Associated ad groups
        - is_brand_safe: bool - Brand safety status (optional)
        - is_relevant: bool - Relevance to campaign (optional)
        - country_code: str - Country code (optional)
        - is_excluded: bool - Currently excluded status (optional)
        - exclusion_reason: str - Reason for exclusion (optional)
        """
        pass
