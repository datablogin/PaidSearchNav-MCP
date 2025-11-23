"""Security tests for Google Ads client SQL injection prevention."""

from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from paidsearchnav_mcp.platforms.google.client import GoogleAdsAPIClient
from paidsearchnav_mcp.platforms.google.validation import GoogleAdsInputValidator


class TestGoogleAdsClientSecurity:
    """Test SQL injection prevention in Google Ads client methods."""

    def setup_method(self):
        """Set up test client."""
        self.client = GoogleAdsAPIClient(
            developer_token="test_token",
            client_id="test_client_id",
            client_secret="test_client_secret",
            refresh_token="test_refresh_token",
        )

    @patch("paidsearchnav.platforms.google.client.GoogleAdsClient")
    @pytest.mark.asyncio
    async def test_get_campaigns_blocks_malicious_campaign_types(
        self, mock_google_client
    ):
        """Test that malicious campaign types are blocked in get_campaigns."""
        # Mock the client initialization
        mock_client_instance = Mock()
        mock_google_client.load_from_dict.return_value = mock_client_instance

        # Mock the service
        mock_service = Mock()
        mock_client_instance.get_service.return_value = mock_service

        malicious_types = ["SEARCH'; DROP TABLE campaigns--", "DISPLAY' OR '1'='1"]

        with pytest.raises(ValueError) as exc_info:
            await self.client.get_campaigns(
                "1234567890", campaign_types=malicious_types
            )

        assert "Invalid campaign types" in str(exc_info.value)
        # Currency call might happen before validation, but the main query should not
        # Only the currency query should have been called, not the campaigns query
        assert mock_service.search.call_count <= 1
        if mock_service.search.call_count == 1:
            # Verify it was only the currency call
            call_args = mock_service.search.call_args
            query = call_args.kwargs["query"]
            assert "customer.currency_code" in query
            assert "campaign" not in query or "FROM customer" in query

    @patch("paidsearchnav.platforms.google.client.GoogleAdsClient")
    @pytest.mark.asyncio
    async def test_get_campaigns_accepts_valid_campaign_types(self, mock_google_client):
        """Test that valid campaign types are accepted in get_campaigns."""
        # Mock the client initialization
        mock_client_instance = Mock()
        mock_google_client.load_from_dict.return_value = mock_client_instance

        # Mock the service and response
        mock_service = Mock()
        mock_client_instance.get_service.return_value = mock_service

        # Mock currency response
        mock_currency_response = Mock()
        mock_currency_response.__iter__ = Mock(
            return_value=iter([Mock(customer=Mock(currency_code="USD"))])
        )

        # First call returns currency, second returns campaigns
        mock_service.search.side_effect = [mock_currency_response, []]

        valid_types = ["SEARCH", "DISPLAY", "SHOPPING"]

        # Mock the _paginated_search_async method instead of direct service calls
        original_paginated_search = self.client._paginated_search_async
        captured_queries = []

        async def mock_paginated_search(
            customer_id, query, page_size=None, max_results=None
        ):
            captured_queries.append(query)
            if "customer.currency_code" in query:
                return [Mock(customer=Mock(currency_code="USD"))]
            else:
                return []  # Empty campaigns

        self.client._paginated_search_async = mock_paginated_search

        try:
            # Should not raise an exception
            await self.client.get_campaigns("1234567890", campaign_types=valid_types)

            # With the pagination changes, there may be 1 or 2 calls depending on currency handling
            # The important part is that the campaign query includes the filters
            assert len(captured_queries) >= 1

            # Find the campaign query (contains campaign fields)
            campaign_query = None
            for query in captured_queries:
                if "campaign.advertising_channel_type" in query:
                    campaign_query = query
                    break

            assert campaign_query is not None, "Campaign query not found"
            assert "campaign.advertising_channel_type = 'SEARCH'" in campaign_query
            assert "campaign.advertising_channel_type = 'DISPLAY'" in campaign_query
            assert "campaign.advertising_channel_type = 'SHOPPING'" in campaign_query
            assert "DROP" not in campaign_query
            assert "--" not in campaign_query
        finally:
            # Restore original method
            self.client._paginated_search_async = original_paginated_search

    @patch("paidsearchnav.platforms.google.client.GoogleAdsClient")
    @pytest.mark.asyncio
    async def test_get_keywords_blocks_malicious_campaign_ids(self, mock_google_client):
        """Test that malicious campaign IDs are blocked in get_keywords."""
        # Mock the client initialization
        mock_client_instance = Mock()
        mock_google_client.load_from_dict.return_value = mock_client_instance

        # Mock the service
        mock_service = Mock()
        mock_client_instance.get_service.return_value = mock_service

        malicious_ids = ["123'; DROP TABLE campaigns--", "456 OR 1=1"]

        with pytest.raises(ValueError) as exc_info:
            await self.client.get_keywords("1234567890", campaigns=malicious_ids)

        assert "Invalid campaign IDs" in str(exc_info.value)
        # Verify the service was never called with malicious input
        mock_service.search.assert_not_called()

    @patch("paidsearchnav.platforms.google.client.GoogleAdsClient")
    @pytest.mark.asyncio
    async def test_get_keywords_accepts_valid_campaign_ids(self, mock_google_client):
        """Test that valid campaign IDs are accepted in get_keywords."""
        # Mock the client initialization
        mock_client_instance = Mock()
        mock_google_client.load_from_dict.return_value = mock_client_instance

        # Mock the service and response
        mock_service = Mock()
        mock_client_instance.get_service.return_value = mock_service
        mock_service.search.return_value = []  # Empty response

        valid_ids = ["123456789", "987654321"]

        # Mock the _paginated_search_async method instead of direct service calls
        original_paginated_search = self.client._paginated_search_async
        captured_queries = []

        async def mock_paginated_search(
            customer_id, query, page_size=None, max_results=None
        ):
            captured_queries.append(query)
            return []  # Empty response

        self.client._paginated_search_async = mock_paginated_search

        try:
            # Should not raise an exception
            await self.client.get_keywords("1234567890", campaigns=valid_ids)

            # Verify we made the expected calls
            assert len(captured_queries) == 1

            # Verify the query contains safe filters
            query = captured_queries[0]
            assert "campaign.id = 123456789" in query
            assert "campaign.id = 987654321" in query
            assert "DROP" not in query
            assert "--" not in query
            assert "OR 1=1" not in query
        finally:
            # Restore original method
            self.client._paginated_search_async = original_paginated_search

    @patch("paidsearchnav.platforms.google.client.GoogleAdsClient")
    @pytest.mark.asyncio
    async def test_get_keywords_blocks_malicious_ad_group_ids(self, mock_google_client):
        """Test that malicious ad group IDs are blocked in get_keywords."""
        # Mock the client initialization
        mock_client_instance = Mock()
        mock_google_client.load_from_dict.return_value = mock_client_instance

        # Mock the service
        mock_service = Mock()
        mock_client_instance.get_service.return_value = mock_service

        malicious_ids = ["123'; DROP TABLE ad_groups--", "456 OR 1=1"]

        with pytest.raises(ValueError) as exc_info:
            await self.client.get_keywords("1234567890", ad_groups=malicious_ids)

        assert "Invalid ad group IDs" in str(exc_info.value)
        # Verify the service was never called with malicious input
        mock_service.search.assert_not_called()

    @patch("paidsearchnav.platforms.google.client.GoogleAdsClient")
    @pytest.mark.asyncio
    async def test_get_search_terms_blocks_malicious_campaign_ids(
        self, mock_google_client
    ):
        """Test that malicious campaign IDs are blocked in get_search_terms."""
        # Mock the client initialization
        mock_client_instance = Mock()
        mock_google_client.load_from_dict.return_value = mock_client_instance

        # Mock the service
        mock_service = Mock()
        mock_client_instance.get_service.return_value = mock_service

        malicious_ids = [
            "123'; DROP TABLE search_terms--",
            "456' UNION SELECT * FROM users--",
        ]

        with pytest.raises(ValueError) as exc_info:
            await self.client.get_search_terms(
                "1234567890",
                datetime(2024, 1, 1),
                datetime(2024, 1, 31),
                campaigns=malicious_ids,
            )

        assert "Invalid campaign IDs" in str(exc_info.value)
        # Verify the service was never called with malicious input
        mock_service.search.assert_not_called()

    @patch("paidsearchnav.platforms.google.client.GoogleAdsClient")
    @pytest.mark.asyncio
    async def test_get_geographic_performance_blocks_malicious_campaign_ids(
        self, mock_google_client
    ):
        """Test that malicious campaign IDs are blocked in get_geographic_performance."""
        # Mock the client initialization
        mock_client_instance = Mock()
        mock_google_client.load_from_dict.return_value = mock_client_instance

        # Mock the service
        mock_service = Mock()
        mock_client_instance.get_service.return_value = mock_service

        malicious_ids = ["123'; DROP TABLE geographic_view--", "456' OR '1'='1"]

        with pytest.raises(ValueError) as exc_info:
            await self.client.get_geographic_performance(
                "1234567890",
                datetime(2024, 1, 1),
                datetime(2024, 1, 31),
                campaign_ids=malicious_ids,
            )

        assert "Invalid campaign IDs" in str(exc_info.value)
        # Verify the service was never called with malicious input
        mock_service.search.assert_not_called()

    @patch("paidsearchnav.platforms.google.client.GoogleAdsClient")
    @pytest.mark.asyncio
    async def test_get_geographic_performance_blocks_malicious_geographic_level(
        self, mock_google_client
    ):
        """Test that malicious geographic levels are blocked."""
        # Mock the client initialization
        mock_client_instance = Mock()
        mock_google_client.load_from_dict.return_value = mock_client_instance

        # Mock the service
        mock_service = Mock()
        mock_client_instance.get_service.return_value = mock_service

        malicious_level = "CITY'; DROP TABLE geographic_view--"

        with pytest.raises(ValueError) as exc_info:
            await self.client.get_geographic_performance(
                "1234567890",
                datetime(2024, 1, 1),
                datetime(2024, 1, 31),
                geographic_level=malicious_level,
            )

        assert "Invalid geographic level" in str(exc_info.value)
        # Verify the service was never called with malicious input
        mock_service.search.assert_not_called()

    @patch("paidsearchnav.platforms.google.client.GoogleAdsClient")
    @pytest.mark.asyncio
    async def test_get_distance_performance_blocks_malicious_campaign_ids(
        self, mock_google_client
    ):
        """Test that malicious campaign IDs are blocked in get_distance_performance."""
        # Mock the client initialization
        mock_client_instance = Mock()
        mock_google_client.load_from_dict.return_value = mock_client_instance

        # Mock the service
        mock_service = Mock()
        mock_client_instance.get_service.return_value = mock_service

        malicious_ids = ["123'; DELETE FROM distance_view--", "456' EXEC evil()--"]

        with pytest.raises(ValueError) as exc_info:
            await self.client.get_distance_performance(
                "1234567890",
                datetime(2024, 1, 1),
                datetime(2024, 1, 31),
                campaign_ids=malicious_ids,
            )

        assert "Invalid campaign IDs" in str(exc_info.value)
        # Verify the service was never called with malicious input
        mock_service.search.assert_not_called()

    @patch("paidsearchnav.platforms.google.client.GoogleAdsClient")
    @pytest.mark.asyncio
    async def test_comprehensive_security_valid_inputs(self, mock_google_client):
        """Test that all methods work correctly with valid inputs."""
        # Mock the client initialization
        mock_client_instance = Mock()
        mock_google_client.load_from_dict.return_value = mock_client_instance

        # Mock the service and response
        mock_service = Mock()
        mock_client_instance.get_service.return_value = mock_service

        # Mock currency response for get_campaigns
        mock_currency_response = Mock()
        mock_currency_response.__iter__ = Mock(
            return_value=iter([Mock(customer=Mock(currency_code="USD"))])
        )

        # Set up responses: currency for get_campaigns, then empty for all other calls
        mock_service.search.side_effect = [mock_currency_response, [], [], [], [], []]

        customer_id = "1234567890"
        valid_campaign_types = ["SEARCH", "DISPLAY"]
        valid_campaign_ids = ["123456789", "987654321"]
        valid_ad_group_ids = ["555666777", "888999000"]
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 31)

        # Test all methods with valid inputs - should not raise exceptions
        await self.client.get_campaigns(
            customer_id, campaign_types=valid_campaign_types
        )
        await self.client.get_keywords(
            customer_id, campaigns=valid_campaign_ids, ad_groups=valid_ad_group_ids
        )
        await self.client.get_search_terms(
            customer_id,
            start_date,
            end_date,
            campaigns=valid_campaign_ids,
            ad_groups=valid_ad_group_ids,
        )
        await self.client.get_geographic_performance(
            customer_id,
            start_date,
            end_date,
            geographic_level="CITY",
            campaign_ids=valid_campaign_ids,
        )
        await self.client.get_distance_performance(
            customer_id, start_date, end_date, campaign_ids=valid_campaign_ids
        )

        # Verify all methods were called (6 times: 1 currency + 5 regular)
        assert mock_service.search.call_count == 6

        # The main test is that no exceptions were raised
        # and all methods executed successfully with valid inputs

    def test_sql_injection_attack_patterns(self):
        """Test various SQL injection attack patterns are blocked."""
        # Common SQL injection patterns
        attack_patterns = [
            "'; DROP TABLE users--",
            "' OR '1'='1",
            "' OR 1=1--",
            "' UNION SELECT * FROM passwords--",
            "'; DELETE FROM accounts WHERE 1=1--",
            "' OR 'a'='a",
            "1'; INSERT INTO admin VALUES('hacker')--",
            "'; EXEC xp_cmdshell('format c:')--",
            "' AND 1=(SELECT COUNT(*) FROM tablenames)--",
            "'; WAITFOR DELAY '00:00:05'--",
        ]

        # Test each pattern against campaign types validation
        for pattern in attack_patterns:
            with pytest.raises(ValueError):
                GoogleAdsInputValidator.validate_campaign_types([pattern])

        # Test each pattern against campaign IDs validation
        for pattern in attack_patterns:
            with pytest.raises(ValueError):
                GoogleAdsInputValidator.validate_campaign_ids([pattern])

        # Test each pattern against ad group IDs validation
        for pattern in attack_patterns:
            with pytest.raises(ValueError):
                GoogleAdsInputValidator.validate_ad_group_ids([pattern])

        # Test each pattern against customer ID validation
        for pattern in attack_patterns:
            with pytest.raises(ValueError):
                GoogleAdsInputValidator.validate_customer_id(pattern)

        # Test each pattern against geographic level validation
        for pattern in attack_patterns:
            with pytest.raises(ValueError):
                GoogleAdsInputValidator.validate_geographic_level(pattern)
