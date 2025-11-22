"""Integration tests for Google Ads API client with mocked responses."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

# Skip entire module if imports are not available
pytest.importorskip("paidsearchnav.platforms.google.client")

from google.ads.googleads.errors import GoogleAdsException

from paidsearchnav.core.exceptions import APIError
from paidsearchnav.core.models.campaign import Campaign
from paidsearchnav.core.models.keyword import Keyword, MatchType
from paidsearchnav.core.models.search_term import SearchTerm
from paidsearchnav.platforms.google.client import GoogleAdsAPIClient


class MockGoogleAdsResponse:
    """Mock Google Ads API response for testing."""

    def __init__(self, rows):
        self.rows = rows

    def __iter__(self):
        return iter(self.rows)


def create_mock_campaign_row(
    campaign_id=123456,
    name="Test Campaign",
    status="ENABLED",
    channel_type="SEARCH",
    budget_micros=50000000,
    impressions=1000,
    clicks=100,
    cost_micros=25000000,
    conversions=10,
    conversion_value=500.0,
):
    """Create a mock campaign row."""
    row = MagicMock()
    row.campaign.id = campaign_id
    row.campaign.name = name
    row.campaign.status.name = status
    row.campaign.advertising_channel_type.name = channel_type
    row.campaign.bidding_strategy_type.name = "TARGET_CPA"
    row.campaign.target_cpa.target_cpa_micros = 5000000
    row.campaign.target_roas = None
    row.campaign_budget.amount_micros = budget_micros
    row.metrics.impressions = impressions
    row.metrics.clicks = clicks
    row.metrics.cost_micros = cost_micros
    row.metrics.conversions = conversions
    row.metrics.conversions_value = conversion_value
    return row


def create_mock_keyword_row(
    keyword_id=987654,
    text="test keyword",
    match_type="EXACT",
    campaign_id=123456,
    campaign_name="Test Campaign",
    ad_group_id=456789,
    ad_group_name="Test Ad Group",
    cpc_bid_micros=2000000,
    quality_score=8,
    impressions=500,
    clicks=50,
    cost_micros=10000000,
    conversions=5,
):
    """Create a mock keyword row."""
    row = MagicMock()
    row.ad_group_criterion.criterion_id = keyword_id
    row.ad_group_criterion.keyword.text = text
    row.ad_group_criterion.keyword.match_type.name = match_type
    row.ad_group_criterion.status.name = "ENABLED"
    row.ad_group_criterion.cpc_bid_micros = cpc_bid_micros
    row.ad_group_criterion.quality_info.quality_score = quality_score
    row.campaign.id = campaign_id
    row.campaign.name = campaign_name
    row.ad_group.id = ad_group_id
    row.ad_group.name = ad_group_name
    row.metrics.impressions = impressions
    row.metrics.clicks = clicks
    row.metrics.cost_micros = cost_micros
    row.metrics.conversions = conversions
    row.metrics.conversions_value = conversions * 50.0
    return row


@pytest.fixture
def mock_google_ads_service():
    """Create a mock Google Ads service."""
    with patch("paidsearchnav.platforms.google.client.GoogleAdsClient") as mock_client:
        mock_instance = MagicMock()
        mock_client.load_from_dict.return_value = mock_instance

        mock_service = MagicMock()
        mock_instance.get_service.return_value = mock_service

        yield mock_service


@pytest.fixture
def client():
    """Create a Google Ads API client instance."""
    return GoogleAdsAPIClient(
        developer_token="test-token",
        client_id="test-client-id",
        client_secret="test-client-secret",
        refresh_token="test-refresh-token",
        login_customer_id="1234567890",
    )


class TestGoogleAdsAPIIntegration:
    """Integration tests for Google Ads API client."""

    @pytest.mark.asyncio
    async def test_fetch_all_campaign_data(self, client, mock_google_ads_service):
        """Test fetching complete campaign data including keywords and search terms."""
        # Mock campaign response
        campaign_rows = [
            create_mock_campaign_row(campaign_id=1, name="Campaign 1"),
            create_mock_campaign_row(
                campaign_id=2, name="Campaign 2", channel_type="PERFORMANCE_MAX"
            ),
            create_mock_campaign_row(campaign_id=3, name="Campaign 3", status="PAUSED"),
        ]

        # Mock keyword response
        keyword_rows = [
            create_mock_keyword_row(
                keyword_id=101, text="shoes", match_type="BROAD", campaign_id=1
            ),
            create_mock_keyword_row(
                keyword_id=102, text="running shoes", match_type="PHRASE", campaign_id=1
            ),
            create_mock_keyword_row(
                keyword_id=103, text="[nike shoes]", match_type="EXACT", campaign_id=1
            ),
        ]

        # Mock customer currency response
        customer_row = MagicMock()
        customer_row.customer.currency_code = "USD"

        # Set up mock responses
        # get_campaigns now makes customer currency call first, then campaigns
        # get_keywords now makes 2 API calls in v20: one for keywords, one for metrics
        mock_google_ads_service.search.side_effect = [
            MockGoogleAdsResponse(
                [customer_row]
            ),  # For get_campaigns - customer currency
            MockGoogleAdsResponse(campaign_rows),  # For get_campaigns - campaigns
            MockGoogleAdsResponse(keyword_rows),  # For get_keywords - keywords query
            MockGoogleAdsResponse(
                []
            ),  # For get_keywords - metrics query (empty for this test)
        ]

        # Fetch campaigns
        campaigns = await client.get_campaigns("1234567890")
        assert len(campaigns) == 3
        assert all(isinstance(c, Campaign) for c in campaigns)

        # Fetch keywords for first campaign
        keywords = await client.get_keywords("1234567890", campaigns=["1"])
        assert len(keywords) == 3
        assert all(isinstance(k, Keyword) for k in keywords)

        # Verify data
        assert campaigns[0].name == "Campaign 1"
        assert campaigns[1].type == "PERFORMANCE_MAX"
        assert campaigns[2].status == "PAUSED"

        assert keywords[0].text == "shoes"
        assert keywords[0].match_type == MatchType.BROAD
        assert keywords[1].text == "running shoes"
        assert keywords[1].match_type == MatchType.PHRASE
        assert keywords[2].text == "[nike shoes]"
        assert keywords[2].match_type == MatchType.EXACT

    @pytest.mark.asyncio
    async def test_search_term_analysis_workflow(self, client, mock_google_ads_service):
        """Test complete search term analysis workflow."""
        # Create search term data
        search_term_rows = []

        # High-performing search terms (candidates for keywords)
        for i in range(5):
            row = MagicMock()
            row.search_term_view.search_term = f"buy premium shoes size {i + 7}"
            row.search_term_view.status.name = "NONE"
            row.campaign.id = 1
            row.campaign.name = "Campaign 1"
            row.ad_group.id = 10
            row.ad_group.name = "Ad Group 1"
            row.ad_group_criterion.criterion_id = 101
            row.ad_group_criterion.keyword.text = "shoes"
            row.ad_group_criterion.keyword.match_type.name = "BROAD"
            row.metrics.impressions = 1000 - i * 100
            row.metrics.clicks = 100 - i * 10
            row.metrics.cost_micros = 50000000 - i * 5000000
            row.metrics.conversions = 10 - i
            row.metrics.conversions_value = 500 - i * 50
            search_term_rows.append(row)

        # Poor-performing search terms (candidates for negatives)
        for i in range(3):
            row = MagicMock()
            row.search_term_view.search_term = f"free shoes giveaway {i + 1}"
            row.search_term_view.status.name = "NONE"
            row.campaign.id = 1
            row.campaign.name = "Campaign 1"
            row.ad_group.id = 10
            row.ad_group.name = "Ad Group 1"
            row.ad_group_criterion.criterion_id = 101
            row.ad_group_criterion.keyword.text = "shoes"
            row.ad_group_criterion.keyword.match_type.name = "BROAD"
            row.metrics.impressions = 2000
            row.metrics.clicks = 200
            row.metrics.cost_micros = 100000000  # High cost
            row.metrics.conversions = 0  # No conversions
            row.metrics.conversions_value = 0
            search_term_rows.append(row)

        mock_google_ads_service.search.return_value = MockGoogleAdsResponse(
            search_term_rows
        )

        # Fetch search terms
        start_date = datetime.now() - timedelta(days=30)
        end_date = datetime.now()
        search_terms = await client.get_search_terms("1234567890", start_date, end_date)

        # Verify results
        assert len(search_terms) == 8
        assert all(isinstance(st, SearchTerm) for st in search_terms)

        # Analyze high-performing terms
        high_performers = [st for st in search_terms if st.conversions > 0]
        assert len(high_performers) == 5

        # Verify CPA calculation
        for st in high_performers:
            if st.conversions > 0:
                assert st.cpa == st.cost / st.conversions

        # Analyze poor performers
        poor_performers = [
            st for st in search_terms if st.conversions == 0 and st.clicks > 0
        ]
        assert len(poor_performers) == 3
        assert all("free" in st.search_term for st in poor_performers)

    @pytest.mark.asyncio
    async def test_negative_keyword_conflict_detection(
        self, client, mock_google_ads_service
    ):
        """Test detecting conflicts between negative and positive keywords."""
        # Mock negative keywords at different levels
        ad_group_negative_rows = [
            self._create_negative_keyword_row("cheap", "BROAD", "ad_group", 1, 10),
            self._create_negative_keyword_row("discount", "PHRASE", "ad_group", 1, 10),
        ]

        campaign_negative_rows = [
            self._create_negative_keyword_row("free", "EXACT", "campaign", 1),
            self._create_negative_keyword_row("used", "BROAD", "campaign", 1),
        ]

        # Set up responses for different queries
        # get_negative_keywords makes 3 API calls:
        # 1. Ad group level negatives
        # 2. Campaign level negatives
        # 3. Shared set negatives
        mock_google_ads_service.search.side_effect = [
            MockGoogleAdsResponse(ad_group_negative_rows),  # Ad group level negatives
            MockGoogleAdsResponse(campaign_negative_rows),  # Campaign level negatives
            MockGoogleAdsResponse([]),  # Shared set negatives
        ]

        # Fetch negatives
        negatives = await client.get_negative_keywords("1234567890")

        # Verify results
        assert len(negatives) == 4

        # Check levels
        ad_group_negatives = [n for n in negatives if n["level"] == "ad_group"]
        campaign_negatives = [n for n in negatives if n["level"] == "campaign"]

        assert len(ad_group_negatives) == 2
        assert len(campaign_negatives) == 2

        # Verify negative keyword data
        assert any(
            n["text"] == "cheap" and n["match_type"] == "BROAD"
            for n in ad_group_negatives
        )
        assert any(
            n["text"] == "free" and n["match_type"] == "EXACT"
            for n in campaign_negatives
        )

    @pytest.mark.asyncio
    async def test_performance_max_campaign_handling(
        self, client, mock_google_ads_service
    ):
        """Test handling of Performance Max campaigns."""
        # Create mixed campaign types
        campaign_rows = [
            create_mock_campaign_row(
                campaign_id=1, name="Search Campaign", channel_type="SEARCH"
            ),
            create_mock_campaign_row(
                campaign_id=2, name="PMax Campaign", channel_type="PERFORMANCE_MAX"
            ),
            create_mock_campaign_row(
                campaign_id=3, name="Shopping Campaign", channel_type="SHOPPING"
            ),
        ]

        # Mock customer currency response
        customer_row = MagicMock()
        customer_row.customer.currency_code = "USD"

        # Mock the _paginated_search_async method instead of direct service calls
        original_paginated_search = client._paginated_search_async
        captured_queries = []

        async def mock_paginated_search(
            customer_id, query, page_size=None, max_results=None
        ):
            captured_queries.append(query)
            if "customer.currency_code" in query:
                return [customer_row]
            else:
                return campaign_rows  # Return campaigns

        client._paginated_search_async = mock_paginated_search

        try:
            # Fetch only PMax campaigns
            await client.get_campaigns("1234567890", campaign_types=["PERFORMANCE_MAX"])

            # Find the campaign query (contains campaign fields)
            campaign_query = None
            for query in captured_queries:
                if "campaign.advertising_channel_type" in query:
                    campaign_query = query
                    break

            assert campaign_query is not None, "Campaign query not found"
            assert (
                "campaign.advertising_channel_type = 'PERFORMANCE_MAX'"
                in campaign_query
            )
        finally:
            # Restore original method
            client._paginated_search_async = original_paginated_search

    @pytest.mark.asyncio
    async def test_error_handling_and_retry(self, client, mock_google_ads_service):
        """Test error handling and retry logic."""
        # Create a real Google Ads exception instance
        exception = GoogleAdsException(None, None, None, None)
        # Mock the failure attribute
        exception.failure = MagicMock()
        error = MagicMock()
        error.error_code = MagicMock()
        error.error_code.name = "INTERNAL_ERROR"
        error.message = "Temporary failure"
        exception.failure.errors = [error]

        # Mock customer currency response
        customer_row = MagicMock()
        customer_row.customer.currency_code = "USD"

        # First campaign call fails, second succeeds (currency calls use fallback)
        mock_google_ads_service.search.side_effect = [
            exception,  # First currency call fails (fallback to USD)
            exception,  # First campaign call fails
            MockGoogleAdsResponse([customer_row]),  # Second currency call succeeds
            MockGoogleAdsResponse(
                [create_mock_campaign_row()]
            ),  # Second campaign call succeeds
        ]

        # First attempt should raise (converted to APIError)
        with pytest.raises(APIError):
            await client.get_campaigns("1234567890")

        # Second attempt should succeed
        campaigns = await client.get_campaigns("1234567890")
        assert len(campaigns) == 1

    def _create_negative_keyword_row(
        self, text, match_type, level, campaign_id, ad_group_id=None
    ):
        """Helper to create negative keyword rows."""
        row = MagicMock()

        if level == "ad_group":
            row.ad_group_criterion.criterion_id = hash(text)
            row.ad_group_criterion.keyword.text = text
            row.ad_group_criterion.keyword.match_type.name = match_type
            row.campaign.id = campaign_id
            row.campaign.name = f"Campaign {campaign_id}"
            row.ad_group.id = ad_group_id
            row.ad_group.name = f"Ad Group {ad_group_id}"
        else:  # campaign level
            row.campaign_criterion.criterion_id = hash(text)
            row.campaign_criterion.keyword.text = text
            row.campaign_criterion.keyword.match_type.name = match_type
            row.campaign.id = campaign_id
            row.campaign.name = f"Campaign {campaign_id}"

        return row
