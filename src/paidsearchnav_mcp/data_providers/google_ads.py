"""Google Ads data provider implementation."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from paidsearchnav_mcp.data_providers.base import DataProvider
from paidsearchnav_mcp.platforms.google.client import GoogleAdsAPIClient
from paidsearchnav_mcp.security.rate_limiting import validate_multiple_id_lists

if TYPE_CHECKING:
    from paidsearchnav_mcp.models.campaign import Campaign
    from paidsearchnav_mcp.models.keyword import Keyword
    from paidsearchnav_mcp.models.search_term import SearchTerm


class GoogleAdsDataProvider(DataProvider):
    """Data provider implementation for Google Ads API.

    This provider wraps the GoogleAdsAPIClient to implement the DataProvider
    interface, providing a clean abstraction for accessing Google Ads data.
    """

    def __init__(self, api_client: GoogleAdsAPIClient):
        """Initialize the Google Ads data provider.

        Args:
            api_client: Configured GoogleAdsAPIClient instance
        """
        self.api_client = api_client

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
        """Fetch search terms report data from Google Ads."""
        # Validate ID list sizes to prevent DoS
        validated = validate_multiple_id_lists(campaigns=campaigns, ad_groups=ad_groups)

        return await self.api_client.get_search_terms(
            customer_id=customer_id,
            start_date=start_date,
            end_date=end_date,
            campaigns=validated["campaigns"],
            ad_groups=validated["ad_groups"],
            page_size=page_size,
            max_results=max_results,
        )

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
        """Fetch keyword data from Google Ads."""
        # Validate ID list sizes to prevent DoS
        validated = validate_multiple_id_lists(campaigns=campaigns, ad_groups=ad_groups)

        return await self.api_client.get_keywords(
            customer_id=customer_id,
            campaigns=validated["campaigns"],
            ad_groups=validated["ad_groups"],
            campaign_id=campaign_id,
            include_metrics=include_metrics,
            start_date=start_date,
            end_date=end_date,
            page_size=page_size,
            max_results=max_results,
        )

    async def get_negative_keywords(
        self,
        customer_id: str,
        include_shared_sets: bool = True,
        page_size: int | None = None,
        max_results: int | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch negative keyword data from Google Ads."""
        return await self.api_client.get_negative_keywords(
            customer_id=customer_id,
            include_shared_sets=include_shared_sets,
            page_size=page_size,
            max_results=max_results,
        )

    async def get_campaigns(
        self,
        customer_id: str,
        campaign_types: list[str] | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        page_size: int | None = None,
        max_results: int | None = None,
    ) -> list[Campaign]:
        """Fetch campaign data from Google Ads."""
        return await self.api_client.get_campaigns(
            customer_id=customer_id,
            campaign_types=campaign_types,
            start_date=start_date,
            end_date=end_date,
            page_size=page_size,
            max_results=max_results,
        )

    async def get_shared_negative_lists(
        self,
        customer_id: str,
    ) -> list[dict[str, Any]]:
        """Fetch shared negative keyword lists from Google Ads."""
        return await self.api_client.get_shared_negative_lists(
            customer_id=customer_id,
        )

    async def get_campaign_shared_sets(
        self,
        customer_id: str,
        campaign_id: str,
    ) -> list[dict[str, Any]]:
        """Get shared sets applied to a specific campaign from Google Ads."""
        return await self.api_client.get_campaign_shared_sets(
            customer_id=customer_id,
            campaign_id=campaign_id,
        )

    async def get_shared_set_negatives(
        self,
        customer_id: str,
        shared_set_id: str,
    ) -> list[dict[str, Any]]:
        """Get negative keywords from a specific shared set from Google Ads."""
        return await self.api_client.get_shared_set_negatives(
            customer_id=customer_id,
            shared_set_id=shared_set_id,
        )

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
        """Fetch placement performance data from Google Ads."""
        # Validate ID list sizes to prevent DoS
        validated = validate_multiple_id_lists(campaigns=campaigns, ad_groups=ad_groups)

        return await self.api_client.get_placement_data(
            customer_id=customer_id,
            start_date=start_date,
            end_date=end_date,
            campaigns=validated["campaigns"],
            ad_groups=validated["ad_groups"],
            page_size=page_size,
            max_results=max_results,
        )

    # Additional Google Ads specific methods not in the base interface
    async def get_geographic_performance(
        self,
        customer_id: str,
        start_date: datetime,
        end_date: datetime,
        campaigns: list[str] | None = None,
        ad_groups: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch geographic performance data from Google Ads."""
        # Validate ID list sizes to prevent DoS
        validated = validate_multiple_id_lists(campaigns=campaigns, ad_groups=ad_groups)

        return await self.api_client.get_geographic_performance(
            customer_id=customer_id,
            start_date=start_date,
            end_date=end_date,
            campaigns=validated["campaigns"],
            ad_groups=validated["ad_groups"],
        )

    async def get_distance_performance(
        self,
        customer_id: str,
        start_date: datetime,
        end_date: datetime,
        campaigns: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch distance-based performance data from Google Ads."""
        # Validate ID list sizes to prevent DoS
        validated = validate_multiple_id_lists(campaigns=campaigns)

        return await self.api_client.get_distance_performance(
            customer_id=customer_id,
            start_date=start_date,
            end_date=end_date,
            campaigns=validated["campaigns"],
        )

    async def get_performance_max_data(
        self,
        customer_id: str,
        start_date: datetime,
        end_date: datetime,
    ) -> list[dict[str, Any]]:
        """Fetch Performance Max campaign data from Google Ads."""
        return await self.api_client.get_performance_max_data(
            customer_id=customer_id,
            start_date=start_date,
            end_date=end_date,
        )

    async def get_performance_max_search_terms(
        self,
        customer_id: str,
        start_date: datetime,
        end_date: datetime,
        campaign_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch Performance Max search terms from Google Ads."""
        return await self.api_client.get_performance_max_search_terms(
            customer_id=customer_id,
            start_date=start_date,
            end_date=end_date,
            campaign_id=campaign_id,
        )
