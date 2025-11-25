"""Google Ads API client implementation."""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

from google.ads.googleads.client import GoogleAdsClient  # type: ignore[import-untyped]
from google.ads.googleads.errors import (
    GoogleAdsException,  # type: ignore[import-untyped]
)

from paidsearchnav_mcp.clients.google.metrics import (
    APIEfficiencyMetrics,
)
from paidsearchnav_mcp.clients.google.rate_limiting import (
    GoogleAdsRateLimiter,
    OperationType,
    account_info_rate_limited,
    report_rate_limited,
    search_rate_limited,
)
from paidsearchnav_mcp.clients.google.validation import GoogleAdsInputValidator
from paidsearchnav_mcp.core.circuit_breaker import GoogleAdsCircuitBreaker
from paidsearchnav_mcp.core.config import CircuitBreakerConfig, Settings
from paidsearchnav_mcp.core.exceptions import (
    APIError,
    AuthenticationError,
    RateLimitError,
)
from paidsearchnav_mcp.models.campaign import Campaign
from paidsearchnav_mcp.models.keyword import Keyword, MatchType
from paidsearchnav_mcp.models.search_term import SearchTerm, SearchTermMetrics

logger = logging.getLogger(__name__)

# Constants for Google Ads API
MICROS_PER_CURRENCY_UNIT = (
    1_000_000  # Google Ads uses micros (1 million = 1 currency unit)
)

# Google Ads supported currencies (major ones - can be extended as needed)
VALID_CURRENCY_CODES = {
    "USD",
    "EUR",
    "GBP",
    "CAD",
    "AUD",
    "JPY",
    "CHF",
    "SEK",
    "NOK",
    "DKK",
    "PLN",
    "CZK",
    "HUF",
    "RON",
    "BGN",
    "HRK",
    "RUB",
    "TRY",
    "ILS",
    "ZAR",
    "BRL",
    "MXN",
    "ARS",
    "CLP",
    "COP",
    "PEN",
    "UYU",
    "INR",
    "KRW",
    "TWD",
    "HKD",
    "SGD",
    "THB",
    "MYR",
    "PHP",
    "IDR",
    "VND",
    "CNY",
    "NZD",
}


class GoogleAdsAPIClient:
    """Google Ads API client for fetching campaign data."""

    def __init__(
        self,
        developer_token: str,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        login_customer_id: str | None = None,
        use_proto_plus: bool = True,
        circuit_breaker_config: CircuitBreakerConfig | None = None,
        default_page_size: int = 1000,
        max_page_size: int = 10000,
        settings: Settings | None = None,
    ):
        """Initialize Google Ads API client.

        Args:
            developer_token: Google Ads API developer token
            client_id: OAuth2 client ID
            client_secret: OAuth2 client secret
            refresh_token: OAuth2 refresh token
            login_customer_id: MCC account ID (if applicable)
            use_proto_plus: Whether to use proto-plus messages
            circuit_breaker_config: Circuit breaker configuration
            default_page_size: Default page size for paginated requests (1-10000)
            max_page_size: Maximum page size for paginated requests (Google Ads limit is 10000)
            settings: Application settings for rate limiting configuration
        """
        self.developer_token = developer_token
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self.login_customer_id = login_customer_id
        self._client = None
        self._initialized = False

        # Store settings for rate limiter
        self.settings = settings

        # Validate pagination settings
        if not 1 <= default_page_size <= 10000:
            raise ValueError("default_page_size must be between 1 and 10000")
        if not 1 <= max_page_size <= 10000:
            raise ValueError("max_page_size must be between 1 and 10000")
        if default_page_size > max_page_size:
            raise ValueError("default_page_size cannot exceed max_page_size")

        self.default_page_size = default_page_size
        self.max_page_size = max_page_size

        # Initialize circuit breaker
        if circuit_breaker_config is None:
            circuit_breaker_config = CircuitBreakerConfig()
        self._circuit_breaker = GoogleAdsCircuitBreaker(circuit_breaker_config)

        # Initialize rate limiter
        self._rate_limiter = GoogleAdsRateLimiter(settings)

        # Initialize API efficiency metrics
        self._metrics = APIEfficiencyMetrics()

    def _get_client(self) -> GoogleAdsClient:
        """Get or create Google Ads client instance."""
        if not self._initialized:
            credentials = {
                "developer_token": self.developer_token,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": self.refresh_token,
                "use_proto_plus": True,
            }

            if self.login_customer_id:
                credentials["login_customer_id"] = self.login_customer_id

            try:
                self._client = GoogleAdsClient.load_from_dict(credentials)
                self._initialized = True
            except Exception as ex:
                logger.error(f"Failed to initialize Google Ads client: {ex}")
                raise AuthenticationError(
                    f"Failed to authenticate with Google Ads API: {str(ex)}"
                ) from ex

        return self._client

    @property
    def circuit_breaker_metrics(self) -> dict[str, Any]:
        """Get circuit breaker metrics for monitoring."""
        return self._circuit_breaker.metrics

    @property
    def rate_limiter(self) -> GoogleAdsRateLimiter:
        """Get rate limiter for monitoring and status checks."""
        return self._rate_limiter

    @property
    def api_metrics(self) -> APIEfficiencyMetrics:
        """Get API efficiency metrics for monitoring and reporting."""
        return self._metrics

    async def get_rate_limit_status(
        self, customer_id: str, operation_type: OperationType | None = None
    ) -> dict[str, Any]:
        """Get current rate limit status for a customer.

        Args:
            customer_id: Google Ads customer ID
            operation_type: Specific operation type to check (optional)

        Returns:
            Dictionary with current usage and remaining capacity
        """
        if operation_type:
            return await self._rate_limiter.get_rate_limit_status(
                customer_id, operation_type
            )

        # Return status for all operation types
        status = {}
        for op_type in OperationType:
            status[op_type.value] = await self._rate_limiter.get_rate_limit_status(
                customer_id, op_type
            )

        return status

    def _paginated_search(
        self,
        customer_id: str,
        query: str,
        page_size: int | None = None,
        max_results: int | None = None,
    ) -> list[Any]:
        """Execute a paginated Google Ads search query.

        Loads all results into memory at once. For large datasets (>10k records),
        consider using search_stream() for memory-efficient processing.

        Google Ads API V17+ Compatibility:
        - Uses fixed page size of 10,000 rows (page_size parameter ignored)
        - Automatically handles pagination with next_page_token
        - No PAGE_SIZE_NOT_SUPPORTED errors

        Performance guidance:
        - Small datasets (<10k records): Use this method
        - Large datasets (>10k records): Use search_stream() for memory efficiency

        Args:
            customer_id: Google Ads customer ID
            query: GAQL query string
            page_size: Page size for pagination (IGNORED - kept for compatibility)
            max_results: Maximum number of results to return (no limit if None)

        Returns:
            List of all results from all pages

        Raises:
            ValueError: If page_size exceeds max_page_size
            APIError: If circuit breaker is open or operation fails
        """
        if page_size is None:
            page_size = self.default_page_size
        elif page_size > self.max_page_size:
            raise ValueError(
                f"page_size ({page_size}) cannot exceed max_page_size ({self.max_page_size})"
            )

        # Start metrics tracking
        call_id = self._metrics.start_call(
            operation_type="paginated_search", customer_id=customer_id, query=query
        )

        client = self._get_client()
        ga_service = client.get_service("GoogleAdsService")

        all_results = []
        page_token = None
        total_fetched = 0
        page_count = 0

        try:
            while True:
                page_count += 1

                # Create search request
                search_request = client.get_type("SearchGoogleAdsRequest")
                search_request.customer_id = customer_id
                search_request.query = query
                # Note: page_size removed for Google Ads API V17+ compatibility
                # API now uses fixed page size of 10,000 rows

                if page_token:
                    search_request.page_token = page_token

                # Execute request with circuit breaker
                response = self._execute_with_circuit_breaker(
                    "paginated_search",
                    lambda: ga_service.search(request=search_request),
                )

                # Collect results from this page
                page_results = list(response)
                all_results.extend(page_results)
                total_fetched += len(page_results)

                logger.debug(
                    f"Fetched page with {len(page_results)} results (total: {total_fetched})"
                )

                # Check if we should stop
                if max_results and total_fetched >= max_results:
                    # Trim results to max_results
                    all_results = all_results[:max_results]
                    break

                # Check if there are more pages
                if (
                    not hasattr(response, "next_page_token")
                    or not response.next_page_token
                ):
                    logger.debug(
                        f"Pagination complete: no more pages available for {customer_id}"
                    )
                    break

                page_token = response.next_page_token

            # End metrics tracking with success
            self._metrics.end_call(
                call_id=call_id,
                record_count=len(all_results),
                page_count=page_count,
                success=True,
            )

            # Memory efficiency warning for large datasets
            if len(all_results) > 50000:
                logger.warning(
                    f"Large dataset retrieved: {len(all_results)} records. "
                    "Consider using search_stream() for memory efficiency."
                )

            logger.info(
                f"Paginated search completed: {len(all_results)} total results from {customer_id}"
            )
            return all_results

        except Exception as ex:
            # End metrics tracking with error
            error_type = type(ex).__name__
            self._metrics.end_call(
                call_id=call_id,
                record_count=len(all_results),
                page_count=page_count,
                success=False,
                error_type=error_type,
                error_message=str(ex),
            )

            # Re-raise the exception
            raise

    async def _paginated_search_async(
        self,
        customer_id: str,
        query: str,
        page_size: int | None = None,
        max_results: int | None = None,
    ) -> list[Any]:
        """Execute a paginated Google Ads search query asynchronously.

        Args:
            customer_id: Google Ads customer ID
            query: GAQL query string
            page_size: Page size for pagination (IGNORED - kept for compatibility)
            max_results: Maximum number of results to return (no limit if None)

        Returns:
            List of all results from all pages
        """
        return await asyncio.get_event_loop().run_in_executor(
            None,
            self._paginated_search,
            customer_id,
            query,
            page_size,
            max_results,
        )

    def search_stream(
        self,
        customer_id: str,
        query: str,
        page_size: int | None = None,
    ):
        """Stream Google Ads search results using a generator.

        Memory-efficient streaming for large datasets. Recommended for enterprise
        accounts with >10k records to avoid memory issues.

        Performance guidance:
        - Enterprise accounts: Use page_size=5000-10000 for optimal throughput
        - Network-limited environments: Use smaller page_size=1000-2000
        - Processing-heavy operations: Use page_size=500-1000 to reduce latency

        Args:
            customer_id: Google Ads customer ID
            query: GAQL query string
            page_size: Page size for pagination (IGNORED - kept for compatibility)

        Yields:
            Individual result rows from the Google Ads API

        Example:
            >>> client = GoogleAdsAPIClient(...)
            >>> for row in client.search_stream("1234567890", "SELECT campaign.id FROM campaign"):
            ...     print(row.campaign.id)
        """
        if page_size is None:
            page_size = self.default_page_size
        elif page_size > self.max_page_size:
            raise ValueError(
                f"page_size ({page_size}) cannot exceed max_page_size ({self.max_page_size})"
            )

        client = self._get_client()
        ga_service = client.get_service("GoogleAdsService")

        page_token = None
        total_yielded = 0

        while True:
            # Create search request
            search_request = client.get_type("SearchGoogleAdsRequest")
            search_request.customer_id = customer_id
            search_request.query = query
            # Note: page_size removed for Google Ads API V17+ compatibility
            # API now uses fixed page size of 10,000 rows

            if page_token:
                search_request.page_token = page_token

            # Execute request with circuit breaker
            response = self._execute_with_circuit_breaker(
                "search_stream",
                lambda: ga_service.search(request=search_request),
            )

            # Yield results from this page
            page_count = 0
            for row in response:
                yield row
                page_count += 1
                total_yielded += 1

            logger.debug(
                f"Streamed page with {page_count} results (total: {total_yielded})"
            )

            # Check if there are more pages
            if not hasattr(response, "next_page_token") or not response.next_page_token:
                logger.debug(
                    f"Stream pagination complete: no more pages available for {customer_id}"
                )
                break

            page_token = response.next_page_token

        logger.info(
            f"Search stream completed: {total_yielded} total results from {customer_id}"
        )

    async def search_stream_async(
        self,
        customer_id: str,
        query: str,
        page_size: int | None = None,
    ):
        """Async generator for streaming Google Ads search results.

        This method yields individual rows as they are fetched, providing
        memory-efficient processing for large datasets in async contexts.

        Args:
            customer_id: Google Ads customer ID
            query: GAQL query string
            page_size: Page size for pagination (IGNORED - kept for compatibility)

        Yields:
            Individual result rows from the Google Ads API

        Example:
            >>> client = GoogleAdsAPIClient(...)
            >>> async for row in client.search_stream_async("1234567890", "SELECT campaign.id FROM campaign"):
            ...     print(row.campaign.id)
        """
        if page_size is None:
            page_size = self.default_page_size
        elif page_size > self.max_page_size:
            raise ValueError(
                f"page_size ({page_size}) cannot exceed max_page_size ({self.max_page_size})"
            )

        client = self._get_client()
        ga_service = client.get_service("GoogleAdsService")

        page_token = None
        total_yielded = 0

        while True:
            # Create search request
            search_request = client.get_type("SearchGoogleAdsRequest")
            search_request.customer_id = customer_id
            search_request.query = query
            # Note: page_size removed for Google Ads API V17+ compatibility
            # API now uses fixed page size of 10,000 rows

            if page_token:
                search_request.page_token = page_token

            # Execute request with circuit breaker in executor
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._execute_with_circuit_breaker(
                    "search_stream_async",
                    lambda: ga_service.search(request=search_request),
                ),
            )

            # Yield results from this page
            page_count = 0
            for row in response:
                yield row
                page_count += 1
                total_yielded += 1

            logger.debug(
                f"Async streamed page with {page_count} results (total: {total_yielded})"
            )

            # Check if there are more pages
            if not hasattr(response, "next_page_token") or not response.next_page_token:
                logger.debug(
                    f"Async stream pagination complete: no more pages available for {customer_id}"
                )
                break

            page_token = response.next_page_token

        logger.info(
            f"Async search stream completed: {total_yielded} total results from {customer_id}"
        )

    def _execute_with_circuit_breaker(
        self, operation_name: str, operation_func: Any
    ) -> Any:
        """Execute Google Ads API operation with circuit breaker protection.

        Args:
            operation_name: Name of the operation for logging
            operation_func: Function to execute

        Returns:
            Result of the operation

        Raises:
            APIError: If circuit breaker is open or operation fails
        """

        @self._circuit_breaker
        def protected_operation():
            try:
                return operation_func()
            except GoogleAdsException as ex:
                # Convert Google Ads exceptions to our internal exceptions
                # This will trigger the circuit breaker appropriately
                self._handle_google_ads_exception(ex)
            except Exception as ex:
                logger.error(f"Unexpected error in {operation_name}: {ex}")
                raise APIError(
                    f"Unexpected error in {operation_name}: {str(ex)}"
                ) from ex

        try:
            return protected_operation()
        except Exception as ex:
            # If circuit breaker is open, provide helpful error message
            if self._circuit_breaker.state == "open":
                logger.warning(
                    f"Google Ads API circuit breaker is OPEN - rejecting {operation_name} call"
                )
                raise APIError(
                    f"Google Ads API is temporarily unavailable. "
                    f"Circuit breaker is OPEN due to repeated failures. "
                    f"Operation: {operation_name}"
                ) from ex
            raise

    async def _get_customer_currency(self, customer_id: str, ga_service: Any) -> str:
        """Get customer currency code from Google Ads.

        Args:
            customer_id: Google Ads customer ID
            ga_service: Google Ads service instance

        Returns:
            Currency code (e.g., "USD", "EUR", "GBP")
        """
        try:
            query = """
                SELECT
                    customer.currency_code
                FROM customer
                LIMIT 1
            """.strip()

            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._execute_with_circuit_breaker(
                    "get_customer_currency",
                    lambda: ga_service.search(customer_id=customer_id, query=query),
                ),
            )

            for row in response:
                currency_code = row.customer.currency_code
                if currency_code:
                    # Validate currency code
                    if currency_code in VALID_CURRENCY_CODES:
                        logger.debug(
                            f"Customer {customer_id} currency: {currency_code}"
                        )
                        return currency_code
                    else:
                        logger.warning(
                            f"Unsupported currency '{currency_code}' for customer {customer_id}, "
                            f"defaulting to USD"
                        )
                        return "USD"

            # Fallback to USD if no currency found
            logger.warning(
                f"No currency found for customer {customer_id}, defaulting to USD"
            )
            return "USD"

        except GoogleAdsException as ex:
            logger.error(
                f"Google Ads API error fetching currency for {customer_id}: {ex}"
            )
            # Fallback to USD on error
            return "USD"
        except Exception as ex:
            logger.error(f"Unexpected error fetching currency for {customer_id}: {ex}")
            # Fallback to USD on error
            return "USD"

    @search_rate_limited
    async def get_campaigns(
        self,
        customer_id: str,
        campaign_types: list[str] | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        page_size: int | None = None,
        max_results: int | None = None,
    ) -> list[Campaign]:
        """Fetch campaign data from Google Ads.

        Args:
            customer_id: Google Ads customer ID
            campaign_types: Optional list of campaign types to filter
            start_date: Start date for metrics (not used in campaign query)
            end_date: End date for metrics (not used in campaign query)
            page_size: Number of results per page (uses default if None)
            max_results: Maximum number of results to return (no limit if None)

        Returns:
            List of Campaign objects with correct account currency

        Example:
            >>> client = GoogleAdsAPIClient(...)
            >>> campaigns = await client.get_campaigns("1234567890")
            >>> for campaign in campaigns:
            ...     print(f"{campaign.name}: {campaign.budget_amount} {campaign.budget_currency}")
            "EU Campaign: 100.0 EUR"
            "US Campaign: 150.0 USD"

        Note:
            Currency is automatically detected from the Google Ads account settings.
            Falls back to USD if currency detection fails.
        """
        # Validate customer ID format
        customer_id = GoogleAdsInputValidator.validate_customer_id(customer_id)

        # Validate campaign types early to prevent any API calls with malicious input
        if campaign_types:
            GoogleAdsInputValidator.validate_campaign_types(campaign_types)

        client = self._get_client()
        ga_service = client.get_service("GoogleAdsService")

        # First, get the customer currency code
        customer_currency = await self._get_customer_currency(customer_id, ga_service)

        # Build query
        query = """
            SELECT
                campaign.id,
                campaign.name,
                campaign.status,
                campaign.advertising_channel_type,
                campaign.bidding_strategy_type,
                campaign.target_cpa.target_cpa_micros,
                campaign.target_roas.target_roas,
                campaign_budget.amount_micros,
                metrics.impressions,
                metrics.clicks,
                metrics.cost_micros,
                metrics.conversions,
                metrics.conversions_value
            FROM campaign
            WHERE campaign.status != 'REMOVED'
        """.strip()

        if campaign_types:
            # Validate campaign types against enum to prevent injection
            campaign_type_filter = (
                GoogleAdsInputValidator.build_safe_campaign_type_filter(campaign_types)
            )
            if campaign_type_filter:
                query += f" AND ({campaign_type_filter})"

        query += " ORDER BY campaign.name"

        try:
            # Use paginated search for memory efficiency
            response_rows = await self._paginated_search_async(
                customer_id=customer_id,
                query=query,
                page_size=page_size,
                max_results=max_results,
            )

            campaigns = []
            for row in response_rows:
                campaign = row.campaign
                metrics = row.metrics
                budget = row.campaign_budget

                # Convert micros to currency
                budget_amount = (
                    budget.amount_micros / MICROS_PER_CURRENCY_UNIT if budget else 0
                )
                cost = metrics.cost_micros / MICROS_PER_CURRENCY_UNIT

                campaigns.append(
                    Campaign(
                        campaign_id=str(campaign.id),
                        customer_id=customer_id,
                        name=campaign.name,
                        status=campaign.status.name,
                        type=campaign.advertising_channel_type.name,
                        budget_amount=budget_amount,
                        budget_currency=customer_currency,
                        bidding_strategy=campaign.bidding_strategy_type.name
                        if campaign.bidding_strategy_type
                        else "UNKNOWN",
                        target_cpa=campaign.target_cpa.target_cpa_micros
                        / MICROS_PER_CURRENCY_UNIT
                        if campaign.target_cpa
                        else None,
                        target_roas=campaign.target_roas.target_roas
                        if campaign.target_roas
                        else None,
                        impressions=metrics.impressions,
                        clicks=metrics.clicks,
                        cost=cost,
                        conversions=metrics.conversions,
                        conversion_value=metrics.conversions_value,
                    )
                )

            logger.info(
                f"Fetched {len(campaigns)} campaigns for customer {customer_id}"
            )
            return campaigns

        except GoogleAdsException as e:
            self._handle_google_ads_exception(e)

    @search_rate_limited
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
        """Fetch keyword data from Google Ads.

        Args:
            customer_id: Google Ads customer ID
            campaigns: Optional list of campaign IDs to filter
            ad_groups: Optional list of ad group IDs to filter
            campaign_id: Single campaign ID to filter (will be added to campaigns list)
            include_metrics: Whether to fetch performance metrics (requires date range)
            start_date: Start date for metrics (defaults to last 30 days)
            end_date: End date for metrics (defaults to yesterday)
            page_size: Number of results per page (uses default if None)
            max_results: Maximum number of results to return (no limit if None)

        Returns:
            List of Keyword objects
        """
        # Validate customer ID format
        customer_id = GoogleAdsInputValidator.validate_customer_id(customer_id)

        # Validate campaign IDs early to prevent any API calls with malicious input
        if campaigns:
            GoogleAdsInputValidator.validate_campaign_ids(campaigns)

        # Handle single campaign_id parameter by adding to campaigns list
        if campaign_id:
            GoogleAdsInputValidator.validate_campaign_ids([campaign_id])
            if campaigns:
                campaigns.append(campaign_id)
            else:
                campaigns = [campaign_id]

        # Validate ad group IDs early to prevent any API calls with malicious input
        if ad_groups:
            GoogleAdsInputValidator.validate_ad_group_ids(ad_groups)

        client = self._get_client()
        ga_service = client.get_service("GoogleAdsService")

        # Build query
        # Note: In API v20, metrics are not directly available on ad_group_criterion
        # We need to use keyword_view for metrics data
        query = """
            SELECT
                ad_group_criterion.criterion_id,
                ad_group_criterion.keyword.text,
                ad_group_criterion.keyword.match_type,
                ad_group_criterion.status,
                ad_group_criterion.cpc_bid_micros,
                ad_group_criterion.quality_info.quality_score,
                campaign.id,
                campaign.name,
                ad_group.id,
                ad_group.name
            FROM ad_group_criterion
            WHERE ad_group_criterion.type = 'KEYWORD'
                AND ad_group_criterion.negative = FALSE
                AND ad_group_criterion.status != 'REMOVED'
        """.strip()

        if campaigns:
            # Validate campaign IDs to prevent injection
            campaign_filter, needs_parens = (
                GoogleAdsInputValidator.build_safe_campaign_id_filter(campaigns)
            )
            if campaign_filter:
                query += (
                    f" AND ({campaign_filter})"
                    if needs_parens
                    else f" AND {campaign_filter}"
                )

        if ad_groups:
            # Validate ad group IDs to prevent injection
            ad_group_filter, needs_parens = (
                GoogleAdsInputValidator.build_safe_ad_group_id_filter(ad_groups)
            )
            if ad_group_filter:
                query += (
                    f" AND ({ad_group_filter})"
                    if needs_parens
                    else f" AND {ad_group_filter}"
                )

        query += " ORDER BY ad_group_criterion.keyword.text"

        try:
            # Use paginated search for memory efficiency
            response_rows = await self._paginated_search_async(
                customer_id=customer_id,
                query=query,
                page_size=page_size,
                max_results=max_results,
            )

            keywords = []
            for row in response_rows:
                criterion = row.ad_group_criterion

                # Convert match type
                match_type_map = {
                    "EXACT": MatchType.EXACT,
                    "PHRASE": MatchType.PHRASE,
                    "BROAD": MatchType.BROAD,
                }

                # Convert micros to currency
                cpc_bid = (
                    criterion.cpc_bid_micros / MICROS_PER_CURRENCY_UNIT
                    if criterion.cpc_bid_micros
                    else None
                )

                keywords.append(
                    Keyword(
                        keyword_id=str(criterion.criterion_id),
                        ad_group_id=str(row.ad_group.id),
                        ad_group_name=row.ad_group.name,
                        campaign_id=str(row.campaign.id),
                        campaign_name=row.campaign.name,
                        text=criterion.keyword.text,
                        match_type=match_type_map.get(
                            criterion.keyword.match_type.name, MatchType.BROAD
                        ),
                        status=criterion.status.name,
                        cpc_bid=cpc_bid,
                        quality_score=criterion.quality_info.quality_score
                        if criterion.quality_info
                        else None,
                        # Metrics will be populated if include_metrics=True
                        impressions=0,
                        clicks=0,
                        cost=0.0,
                        conversions=0.0,
                        conversion_value=0.0,
                    )
                )

            logger.info(f"Fetched {len(keywords)} keywords for customer {customer_id}")

            # Fetch metrics if requested
            if include_metrics and keywords:
                # Set default date range if not provided
                if not end_date:
                    end_date = datetime.now() - timedelta(days=1)
                if not start_date:
                    start_date = end_date - timedelta(days=30)

                # Fetch metrics from keyword_view
                metrics_map = await self._get_keyword_metrics(
                    customer_id, start_date, end_date, campaigns, ad_groups
                )

                # Update keywords with metrics
                for keyword in keywords:
                    metric_key = f"{keyword.ad_group_id}_{keyword.keyword_id}"
                    if metric_key in metrics_map:
                        metrics = metrics_map[metric_key]
                        keyword.impressions = metrics["impressions"]
                        keyword.clicks = metrics["clicks"]
                        keyword.cost = metrics["cost"]
                        keyword.conversions = metrics["conversions"]
                        keyword.conversion_value = metrics["conversion_value"]

            return keywords

        except GoogleAdsException as e:
            self._handle_google_ads_exception(e)

    @report_rate_limited
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
        """Fetch search terms report data from Google Ads.

        Args:
            customer_id: Google Ads customer ID
            start_date: Start date for the report
            end_date: End date for the report
            campaigns: Optional list of campaign IDs to filter
            ad_groups: Optional list of ad group IDs to filter
            page_size: Number of results per page (uses default if None)
            max_results: Maximum number of results to return (no limit if None)

        Returns:
            List of SearchTerm objects
        """
        # Validate customer ID format
        customer_id = GoogleAdsInputValidator.validate_customer_id(customer_id)

        # Validate campaign IDs early to prevent any API calls with malicious input
        if campaigns:
            GoogleAdsInputValidator.validate_campaign_ids(campaigns)

        # Validate ad group IDs early to prevent any API calls with malicious input
        if ad_groups:
            GoogleAdsInputValidator.validate_ad_group_ids(ad_groups)

        # Validate date range
        self._validate_date_range(start_date, end_date)

        client = self._get_client()
        ga_service = client.get_service("GoogleAdsService")

        # Format dates for query
        start_date_str = start_date.strftime("%Y-%m-%d")
        end_date_str = end_date.strftime("%Y-%m-%d")

        # Build query (without ad_group_criterion fields which are incompatible with search_term_view)
        # Issue #126: Confirmed compatibility with Google Ads API v20
        query = f"""
            SELECT
                search_term_view.search_term,
                search_term_view.status,
                campaign.id,
                campaign.name,
                ad_group.id,
                ad_group.name,
                metrics.impressions,
                metrics.clicks,
                metrics.cost_micros,
                metrics.conversions,
                metrics.conversions_value
            FROM search_term_view
            WHERE segments.date BETWEEN '{start_date_str}' AND '{end_date_str}'
        """.strip()

        if campaigns:
            # Validate campaign IDs to prevent injection
            campaign_filter, needs_parens = (
                GoogleAdsInputValidator.build_safe_campaign_id_filter(campaigns)
            )
            if campaign_filter:
                query += (
                    f" AND ({campaign_filter})"
                    if needs_parens
                    else f" AND {campaign_filter}"
                )

        if ad_groups:
            # Validate ad group IDs to prevent injection
            ad_group_filter, needs_parens = (
                GoogleAdsInputValidator.build_safe_ad_group_id_filter(ad_groups)
            )
            if ad_group_filter:
                query += (
                    f" AND ({ad_group_filter})"
                    if needs_parens
                    else f" AND {ad_group_filter}"
                )

        query += " ORDER BY metrics.impressions DESC"

        try:
            # Use paginated search for memory efficiency
            response_rows = await self._paginated_search_async(
                customer_id=customer_id,
                query=query,
                page_size=page_size,
                max_results=max_results,
            )

            search_terms = []
            for row in response_rows:
                search_term = row.search_term_view
                metrics = row.metrics

                # Convert micros to currency
                cost = metrics.cost_micros / MICROS_PER_CURRENCY_UNIT

                search_terms.append(
                    SearchTerm(
                        search_term=search_term.search_term,
                        campaign_id=str(row.campaign.id),
                        campaign_name=row.campaign.name,
                        ad_group_id=str(row.ad_group.id),
                        ad_group_name=row.ad_group.name,
                        keyword_id=None,  # Not available from search_term_view
                        keyword_text=None,  # Not available from search_term_view
                        match_type=None,  # Not available from search_term_view
                        date_start=start_date.date() if start_date else None,
                        date_end=end_date.date() if end_date else None,
                        metrics=SearchTermMetrics(
                            impressions=metrics.impressions,
                            clicks=metrics.clicks,
                            cost=cost,
                            conversions=metrics.conversions,
                            conversion_value=metrics.conversions_value,
                        ),
                    )
                )

            logger.info(
                f"Fetched {len(search_terms)} search terms for customer {customer_id} "
                f"between {start_date_str} and {end_date_str}"
            )
            return search_terms

        except GoogleAdsException as e:
            self._handle_google_ads_exception(e)

    async def _fetch_ad_group_negative_keywords(
        self,
        customer_id: str,
        ga_service: Any,
        page_size: int | None = None,
        max_results: int | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch ad group level negative keywords.

        Args:
            customer_id: Google Ads customer ID
            ga_service: Google Ads service instance

        Returns:
            List of ad group negative keyword dictionaries
        """
        query = """
            SELECT
                campaign.id,
                campaign.name,
                ad_group.id,
                ad_group.name,
                ad_group_criterion.criterion_id,
                ad_group_criterion.keyword.text,
                ad_group_criterion.keyword.match_type,
                ad_group_criterion.negative
            FROM ad_group_criterion
            WHERE ad_group_criterion.type = 'KEYWORD'
                AND ad_group_criterion.negative = TRUE
                AND ad_group_criterion.status != 'REMOVED'
        """.strip()

        negative_keywords = []
        try:
            # Use paginated search for memory efficiency
            response_rows = await self._paginated_search_async(
                customer_id=customer_id,
                query=query,
                page_size=page_size,
                max_results=max_results,
            )

            for row in response_rows:
                criterion = row.ad_group_criterion
                negative_keywords.append(
                    {
                        "id": str(criterion.criterion_id),
                        "text": criterion.keyword.text,
                        "match_type": criterion.keyword.match_type.name,
                        "level": "ad_group",
                        "campaign_id": str(row.campaign.id),
                        "campaign_name": row.campaign.name,
                        "ad_group_id": str(row.ad_group.id),
                        "ad_group_name": row.ad_group.name,
                    }
                )
        except GoogleAdsException as e:
            self._handle_google_ads_exception(e)

        return negative_keywords

    async def _fetch_campaign_negative_keywords(
        self,
        customer_id: str,
        ga_service: Any,
        page_size: int | None = None,
        max_results: int | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch campaign level negative keywords.

        Args:
            customer_id: Google Ads customer ID
            ga_service: Google Ads service instance

        Returns:
            List of campaign negative keyword dictionaries
        """
        query = """
            SELECT
                campaign.id,
                campaign.name,
                campaign_criterion.criterion_id,
                campaign_criterion.keyword.text,
                campaign_criterion.keyword.match_type,
                campaign_criterion.negative
            FROM campaign_criterion
            WHERE campaign_criterion.type = 'KEYWORD'
                AND campaign_criterion.negative = TRUE
                AND campaign_criterion.status != 'REMOVED'
        """.strip()

        negative_keywords = []
        try:
            # Use paginated search for memory efficiency
            response_rows = await self._paginated_search_async(
                customer_id=customer_id,
                query=query,
                page_size=page_size,
                max_results=max_results,
            )

            for row in response_rows:
                criterion = row.campaign_criterion
                negative_keywords.append(
                    {
                        "id": str(criterion.criterion_id),
                        "text": criterion.keyword.text,
                        "match_type": criterion.keyword.match_type.name,
                        "level": "campaign",
                        "campaign_id": str(row.campaign.id),
                        "campaign_name": row.campaign.name,
                    }
                )
        except GoogleAdsException as e:
            self._handle_google_ads_exception(e)

        return negative_keywords

    async def _fetch_shared_negative_keywords(
        self,
        customer_id: str,
        ga_service: Any,
        page_size: int | None = None,
        max_results: int | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch shared negative keyword sets and their campaign associations.

        Args:
            customer_id: Google Ads customer ID
            ga_service: Google Ads service instance

        Returns:
            List of shared negative keyword dictionaries with campaign associations
        """
        negative_keywords = []
        shared_sets = {}

        # First, fetch shared criterion data
        shared_set_query = """
            SELECT
                shared_set.id,
                shared_set.name,
                shared_set.type,
                shared_set.status,
                shared_criterion.keyword.text,
                shared_criterion.keyword.match_type,
                shared_criterion.criterion_id
            FROM shared_criterion
            WHERE shared_set.type = 'NEGATIVE_KEYWORDS'
                AND shared_set.status = 'ENABLED'
                AND shared_criterion.type = 'KEYWORD'
        """.strip()

        try:
            # Use paginated search for memory efficiency
            response_rows = await self._paginated_search_async(
                customer_id=customer_id,
                query=shared_set_query,
                page_size=page_size,
                max_results=max_results,
            )

            for row in response_rows:
                shared_set = row.shared_set
                criterion = row.shared_criterion

                shared_set_id: str = str(shared_set.id)
                if shared_set_id not in shared_sets:
                    shared_sets[shared_set_id] = {
                        "id": shared_set_id,
                        "name": shared_set.name,
                        "keywords": [],
                    }

                shared_sets[shared_set_id]["keywords"].append(
                    {
                        "id": str(criterion.criterion_id),
                        "text": criterion.keyword.text,
                        "match_type": criterion.keyword.match_type.name,
                    }
                )
        except GoogleAdsException as ex:
            logger.warning(f"Failed to fetch shared negative keyword sets: {ex}")
            return negative_keywords  # Return empty list on failure

        # If we have shared sets, get their campaign associations
        if shared_sets:
            campaign_shared_set_query = """
                SELECT
                    campaign_shared_set.campaign,
                    campaign_shared_set.shared_set,
                    campaign.id,
                    campaign.name,
                    shared_set.id
                FROM campaign_shared_set
                WHERE campaign_shared_set.status = 'ENABLED'
                    AND shared_set.type = 'NEGATIVE_KEYWORDS'
            """.strip()

            try:
                # Use paginated search for campaign associations
                response_rows = await self._paginated_search_async(
                    customer_id=customer_id,
                    query=campaign_shared_set_query,
                    page_size=page_size,
                    max_results=max_results,
                )

                # Map shared sets to campaigns
                for row in response_rows:
                    shared_set_id = str(row.shared_set.id)
                    if shared_set_id in shared_sets:
                        for keyword in shared_sets[shared_set_id]["keywords"]:
                            negative_keywords.append(
                                {
                                    "id": keyword["id"],
                                    "text": keyword["text"],
                                    "match_type": keyword["match_type"],
                                    "level": "shared_set",
                                    "shared_set_id": shared_set_id,
                                    "shared_set_name": shared_sets[shared_set_id][
                                        "name"
                                    ],
                                    "campaign_id": str(row.campaign.id),
                                    "campaign_name": row.campaign.name,
                                }
                            )
            except GoogleAdsException as ex:
                logger.warning(
                    f"Failed to fetch campaign associations for shared sets: {ex}"
                )
                # Return empty list to avoid partial data
                return []

        return negative_keywords

    @search_rate_limited
    async def get_negative_keywords(
        self,
        customer_id: str,
        include_shared_sets: bool = True,
        page_size: int | None = None,
        max_results: int | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch negative keyword data from Google Ads.

        Args:
            customer_id: Google Ads customer ID
            include_shared_sets: Whether to include shared negative keyword sets
            page_size: Number of results per page (uses default if None)
            max_results: Maximum number of results to return (no limit if None)

        Returns:
            List of negative keyword dictionaries
        """
        # Validate customer ID format
        customer_id = GoogleAdsInputValidator.validate_customer_id(customer_id)

        client = self._get_client()
        ga_service = client.get_service("GoogleAdsService")

        negative_keywords = []

        try:
            # Calculate max_results per method if specified
            # Ensure each method gets at least 1 result if max_results is specified
            if max_results and max_results < 3:
                method_max_results = 1
            else:
                method_max_results = max_results // 3 if max_results else None

            # Fetch ad group level negative keywords
            ad_group_negatives = await self._fetch_ad_group_negative_keywords(
                customer_id, ga_service, page_size, method_max_results
            )
            negative_keywords.extend(ad_group_negatives)

            # Fetch campaign level negative keywords
            campaign_negatives = await self._fetch_campaign_negative_keywords(
                customer_id, ga_service, page_size, method_max_results
            )
            negative_keywords.extend(campaign_negatives)

            # Fetch shared negative keyword sets if requested
            if include_shared_sets:
                shared_negatives = await self._fetch_shared_negative_keywords(
                    customer_id, ga_service, page_size, method_max_results
                )
                negative_keywords.extend(shared_negatives)

            # Apply overall max_results limit if specified
            if max_results and len(negative_keywords) > max_results:
                negative_keywords = negative_keywords[:max_results]

        except StopIteration as e:
            logger.error(
                "Unexpected StopIteration during negative keyword fetch. "
                "This may indicate an API change or issue.",
                exc_info=True,
            )
            raise APIError("Failed to fetch complete negative keyword list") from e

        logger.info(
            f"Fetched {len(negative_keywords)} negative keywords for customer {customer_id}"
        )
        return negative_keywords

    def _handle_google_ads_exception(self, exception: GoogleAdsException) -> None:
        """Handle Google Ads API exceptions.

        Args:
            exception: The GoogleAdsException to handle

        Raises:
            AuthenticationError: For authentication failures
            RateLimitError: For rate limit errors
            APIError: For other API errors
        """
        error_messages = []

        for error in exception.failure.errors:
            error_messages.append(f"{error.error_code}: {error.message}")

            # Check for specific error types
            if "AUTHENTICATION" in str(error.error_code):
                raise AuthenticationError(f"Authentication failed: {error.message}")
            elif "RATE_EXCEEDED" in str(error.error_code):
                raise RateLimitError(f"Rate limit exceeded: {error.message}")

        full_message = "; ".join(error_messages)
        logger.error(f"Google Ads API error: {full_message}")
        raise APIError(f"Google Ads API error: {full_message}")

    async def get_geographic_performance(
        self,
        customer_id: str,
        start_date: datetime,
        end_date: datetime,
        geographic_level: str = "CITY",
        campaign_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch geographic performance data from Google Ads.

        Args:
            customer_id: Google Ads customer ID
            start_date: Start date for the report
            end_date: End date for the report
            geographic_level: Geographic level (COUNTRY, STATE, CITY, ZIP_CODE)
            campaign_ids: Optional list of campaign IDs to filter

        Returns:
            List of geographic performance data dictionaries

        Raises:
            AuthenticationError: For authentication failures
            RateLimitError: For rate limit errors
            APIError: For other API errors
        """
        # Validate customer ID format
        customer_id = GoogleAdsInputValidator.validate_customer_id(customer_id)

        # Validate campaign IDs early to prevent any API calls with malicious input
        if campaign_ids:
            GoogleAdsInputValidator.validate_campaign_ids(campaign_ids)

        # Validate geographic level to prevent injection
        validated_geographic_level = GoogleAdsInputValidator.validate_geographic_level(
            geographic_level
        )

        # Validate date range
        self._validate_date_range(start_date, end_date)

        client = self._get_client()
        ga_service = client.get_service("GoogleAdsService")

        # Map geographic levels to Google Ads API field names
        # In API v20, geographic_view uses location_view fields
        geographic_field_map = {
            "COUNTRY": "geographic_view.location_type",
            "STATE": "geographic_view.location_type",
            "CITY": "geographic_view.location_type",
            "ZIP_CODE": "geographic_view.location_type",
        }

        geographic_field = geographic_field_map.get(
            validated_geographic_level, "geographic_view.location_type"
        )

        # Build query
        # Note: In API v20, geographic_view has limited fields
        # We need to use location_view for detailed location information
        query = f"""
            SELECT
                campaign.id,
                campaign.name,
                geographic_view.resource_name,
                geographic_view.location_type,
                geographic_view.country_criterion_id,
                metrics.impressions,
                metrics.clicks,
                metrics.conversions,
                metrics.cost_micros,
                metrics.conversions_value
            FROM geographic_view
            WHERE segments.date BETWEEN '{start_date.strftime("%Y-%m-%d")}'
                AND '{end_date.strftime("%Y-%m-%d")}'
        """.strip()

        # Add campaign filter if specified
        if campaign_ids:
            # Use consistent safe campaign ID filter method
            campaign_filter, needs_parens = (
                GoogleAdsInputValidator.build_safe_campaign_id_filter(campaign_ids)
            )
            if campaign_filter:
                query += (
                    f" AND ({campaign_filter})"
                    if needs_parens
                    else f" AND {campaign_filter}"
                )

        # Add non-zero impressions filter
        query += " AND metrics.impressions > 0"

        try:
            logger.info(
                f"Fetching geographic performance data for customer {customer_id}"
            )
            search_request = client.get_type("SearchGoogleAdsRequest")
            search_request.customer_id = customer_id
            search_request.query = query

            response = self._execute_with_circuit_breaker(
                "get_geographic_performance",
                lambda: ga_service.search(request=search_request),
            )

            geo_data = []
            criterion_ids = set()

            # First pass: collect data and criterion IDs
            for row in response:
                # Extract location information from resource_name
                resource_name = row.geographic_view.resource_name
                criterion_id, parsed_location_type = (
                    self._parse_geographic_resource_name(resource_name)
                )

                if criterion_id:
                    criterion_ids.add(criterion_id)

                    # Handle null values explicitly
                    country_criterion_id = getattr(
                        row.geographic_view, "country_criterion_id", 0
                    )
                    if country_criterion_id is None:
                        country_criterion_id = 0

                    conversions_value = getattr(row.metrics, "conversions_value", 0)
                    if conversions_value is None:
                        conversions_value = 0

                    geo_data.append(
                        {
                            "campaign_id": str(row.campaign.id),
                            "campaign_name": row.campaign.name,
                            "country_criterion_id": country_criterion_id,
                            "location_type": row.geographic_view.location_type.name
                            if hasattr(row.geographic_view, "location_type")
                            and row.geographic_view.location_type
                            else "",
                            "resource_name": resource_name,
                            "criterion_id": criterion_id,
                            # Metrics
                            "impressions": getattr(row.metrics, "impressions", 0) or 0,
                            "clicks": getattr(row.metrics, "clicks", 0) or 0,
                            "conversions": float(
                                getattr(row.metrics, "conversions", 0) or 0
                            ),
                            "cost_micros": getattr(row.metrics, "cost_micros", 0) or 0,
                            "conversion_value_micros": conversions_value,
                            # Location names to be populated
                            "country_name": "",
                            "region_name": "",
                            "city_name": "",
                            "metro_name": "",
                            "postal_code": "",
                        }
                    )

            # Fetch location names if we have criterion IDs
            if criterion_ids:
                location_map = await self._get_location_names(
                    customer_id, list(criterion_ids)
                )

                # Update geo_data with location names
                for data in geo_data:
                    criterion_id = data.get("criterion_id", "")
                    if criterion_id in location_map:
                        location_info = location_map[criterion_id]
                        data["canonical_name"] = location_info.get("canonical_name", "")

                        # Parse canonical name for detailed location info
                        # Format: "City, State, Country" or "State, Country" etc.
                        canonical_parts = location_info.get("canonical_name", "").split(
                            ", "
                        )
                        target_type = location_info.get("target_type", "")

                        if target_type == "Country":
                            data["country_name"] = location_info.get("name", "")
                        elif target_type == "State" and len(canonical_parts) >= 2:
                            data["region_name"] = location_info.get("name", "")
                            data["country_name"] = canonical_parts[-1]
                        elif target_type == "City" and len(canonical_parts) >= 2:
                            data["city_name"] = location_info.get("name", "")
                            if len(canonical_parts) >= 3:
                                data["region_name"] = canonical_parts[-2]
                                data["country_name"] = canonical_parts[-1]
                            else:
                                data["country_name"] = canonical_parts[-1]
                        elif target_type == "PostalCode":
                            data["postal_code"] = location_info.get("name", "")
                            if len(canonical_parts) >= 2:
                                data["country_name"] = canonical_parts[-1]
                        elif target_type == "Metro":
                            data["metro_name"] = location_info.get("name", "")
                            if len(canonical_parts) >= 2:
                                data["country_name"] = canonical_parts[-1]

                    # Remove temporary criterion_id field
                    data.pop("criterion_id", None)

            logger.info(f"Retrieved {len(geo_data)} geographic performance records")
            return geo_data

        except GoogleAdsException as ex:
            logger.error(f"Failed to fetch geographic performance: {ex}")
            self._handle_google_ads_exception(ex)
        except Exception as ex:
            logger.error(f"Unexpected error fetching geographic performance: {ex}")
            raise APIError(f"Failed to fetch geographic performance: {ex}") from ex

    async def get_distance_performance(
        self,
        customer_id: str,
        start_date: datetime,
        end_date: datetime,
        campaign_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch distance-based performance data from Google Ads.

        Args:
            customer_id: Google Ads customer ID
            start_date: Start date for the report
            end_date: End date for the report
            campaign_ids: Optional list of campaign IDs to filter

        Returns:
            List of distance performance data dictionaries

        Raises:
            AuthenticationError: For authentication failures
            RateLimitError: For rate limit errors
            APIError: For other API errors
        """
        # Validate customer ID format
        customer_id = GoogleAdsInputValidator.validate_customer_id(customer_id)

        # Validate campaign IDs early to prevent any API calls with malicious input
        if campaign_ids:
            GoogleAdsInputValidator.validate_campaign_ids(campaign_ids)

        # Validate date range
        self._validate_date_range(start_date, end_date)

        client = self._get_client()
        ga_service = client.get_service("GoogleAdsService")

        # Build query for distance view
        query = f"""
            SELECT
                campaign.id,
                campaign.name,
                distance_view.distance_bucket,
                metrics.impressions,
                metrics.clicks,
                metrics.conversions,
                metrics.cost_micros,
                metrics.conversions_value
            FROM distance_view
            WHERE segments.date BETWEEN '{start_date.strftime("%Y-%m-%d")}'
                AND '{end_date.strftime("%Y-%m-%d")}'
        """.strip()

        # Add campaign filter if specified
        if campaign_ids:
            # Use consistent safe campaign ID filter method
            campaign_filter, needs_parens = (
                GoogleAdsInputValidator.build_safe_campaign_id_filter(campaign_ids)
            )
            if campaign_filter:
                query += (
                    f" AND ({campaign_filter})"
                    if needs_parens
                    else f" AND {campaign_filter}"
                )

        # Add non-zero impressions filter
        query += " AND metrics.impressions > 0"

        try:
            logger.info(
                f"Fetching distance performance data for customer {customer_id}"
            )
            search_request = client.get_type("SearchGoogleAdsRequest")
            search_request.customer_id = customer_id
            search_request.query = query

            response = self._execute_with_circuit_breaker(
                "get_geographic_performance",
                lambda: ga_service.search(request=search_request),
            )

            distance_data = []
            for row in response:
                distance_data.append(
                    {
                        "campaign_id": str(row.campaign.id),
                        "campaign_name": row.campaign.name,
                        "distance_bucket": str(
                            getattr(row.distance_view, "distance_bucket", "UNKNOWN")
                        ),
                        "impressions": getattr(row.metrics, "impressions", 0),
                        "clicks": getattr(row.metrics, "clicks", 0),
                        "conversions": float(getattr(row.metrics, "conversions", 0)),
                        "cost_micros": getattr(row.metrics, "cost_micros", 0),
                        "conversion_value_micros": getattr(
                            row.metrics, "conversions_value", 0
                        ),
                    }
                )

            logger.info(f"Retrieved {len(distance_data)} distance performance records")
            return distance_data

        except GoogleAdsException as ex:
            logger.error(f"Failed to fetch distance performance: {ex}")
            self._handle_google_ads_exception(ex)
        except Exception as ex:
            logger.error(f"Unexpected error fetching distance performance: {ex}")
            raise APIError(f"Failed to fetch distance performance: {ex}") from ex

    async def get_ad_schedule_performance(
        self,
        customer_id: str,
        start_date: datetime,
        end_date: datetime,
        campaign_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch ad schedule/dayparting performance data from Google Ads.

        Args:
            customer_id: Google Ads customer ID
            start_date: Start date for the report
            end_date: End date for the report
            campaign_ids: Optional list of campaign IDs to filter

        Returns:
            List of ad schedule performance data dictionaries

        Raises:
            AuthenticationError: For authentication failures
            RateLimitError: For rate limit errors
            APIError: For other API errors
        """
        # Validate customer ID format
        customer_id = GoogleAdsInputValidator.validate_customer_id(customer_id)

        # Validate campaign IDs early to prevent any API calls with malicious input
        if campaign_ids:
            GoogleAdsInputValidator.validate_campaign_ids(campaign_ids)

        # Validate date range
        self._validate_date_range(start_date, end_date)

        client = self._get_client()

        # Fetch performance data and bid modifiers in parallel for efficiency
        performance_data, bid_modifiers = await asyncio.gather(
            self._fetch_dayparting_performance(
                client, customer_id, start_date, end_date, campaign_ids
            ),
            self._fetch_ad_schedule_bid_modifiers(client, customer_id, campaign_ids),
            return_exceptions=True,
        )

        # Handle exceptions from parallel execution
        if isinstance(performance_data, Exception):
            raise performance_data
        if isinstance(bid_modifiers, Exception):
            logger.warning(
                f"Failed to fetch bid modifiers: {bid_modifiers}, continuing without them"
            )
            bid_modifiers = {}

        # Combine performance data with bid modifiers
        combined_data = self._combine_dayparting_data(performance_data, bid_modifiers)

        logger.info(f"Retrieved {len(combined_data)} ad schedule performance records")
        return combined_data

    async def _fetch_dayparting_performance(
        self,
        client: GoogleAdsClient,
        customer_id: str,
        start_date: datetime,
        end_date: datetime,
        campaign_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch performance metrics aggregated by day and hour."""
        ga_service = client.get_service("GoogleAdsService")

        # Use segments.day_of_week and segments.hour for improved performance
        # This avoids the date range explosion while maintaining compatibility
        query = f"""
            SELECT
                campaign.id,
                campaign.name,
                segments.day_of_week,
                segments.hour,
                metrics.impressions,
                metrics.clicks,
                metrics.conversions,
                metrics.cost_micros,
                metrics.conversions_value,
                metrics.ctr,
                metrics.average_cpc,
                metrics.conversions_from_interactions_rate,
                metrics.cost_per_conversion
            FROM campaign
            WHERE segments.date BETWEEN '{start_date.strftime("%Y-%m-%d")}'
                AND '{end_date.strftime("%Y-%m-%d")}'
        """.strip()

        # Add campaign filter if specified
        if campaign_ids:
            campaign_filter, needs_parens = (
                GoogleAdsInputValidator.build_safe_campaign_id_filter(campaign_ids)
            )
            if campaign_filter:
                query += (
                    f" AND ({campaign_filter})"
                    if needs_parens
                    else f" AND {campaign_filter}"
                )

        # Add non-zero impressions filter
        query += " AND metrics.impressions > 0"

        logger.info(
            f"Fetching aggregated ad schedule performance data for customer {customer_id}"
        )

        search_request = client.get_type("SearchGoogleAdsRequest")
        search_request.customer_id = customer_id
        search_request.query = query

        response = self._execute_with_circuit_breaker(
            "get_ad_schedule_performance",
            lambda: ga_service.search(request=search_request),
        )

        # Parse aggregated results
        performance_data = []
        day_mapping = {
            2: "Monday",  # Google's MONDAY enum value
            3: "Tuesday",
            4: "Wednesday",
            5: "Thursday",
            6: "Friday",
            7: "Saturday",
            1: "Sunday",  # Google's SUNDAY enum value
        }

        for row in response:
            day_of_week_enum = row.segments.day_of_week
            hour = row.segments.hour if hasattr(row.segments, "hour") else None

            # Convert enum to readable day name
            day_of_week = day_mapping.get(day_of_week_enum, "Unknown")

            # Format day_time string
            if hour is not None and hour >= 0:
                hour_str = f"{hour % 12 if hour % 12 else 12}:00 {('AM' if hour < 12 else 'PM')}"
                next_hour = (hour + 1) % 24
                next_hour_str = f"{next_hour % 12 if next_hour % 12 else 12}:00 {('AM' if next_hour < 12 else 'PM')}"
                day_time = f"{day_of_week}, {hour_str} - {next_hour_str}"
            else:
                day_time = f"{day_of_week}, All hours"

            # Use direct metrics (no aggregation needed since we're using day_of_week/hour segments)
            impressions = row.metrics.impressions
            clicks = row.metrics.clicks
            conversions = row.metrics.conversions
            cost_micros = row.metrics.cost_micros
            conversions_value = getattr(row.metrics, "conversions_value", 0)

            performance_data.append(
                {
                    "campaign_id": str(row.campaign.id),
                    "campaign_name": row.campaign.name,
                    "day_time": day_time,
                    "day_of_week": day_of_week,
                    "day_of_week_enum": day_of_week_enum,
                    "hour": hour,
                    "impressions": impressions,
                    "clicks": clicks,
                    "conversions": float(conversions),
                    "cost_micros": cost_micros,
                    "conversion_value_micros": conversions_value,
                    "ctr": float(row.metrics.ctr) if row.metrics.ctr else None,
                    "avg_cpc": row.metrics.cost_micros / row.metrics.clicks
                    if row.metrics.clicks > 0
                    else None,
                    "conversion_rate": float(
                        row.metrics.conversions_from_interactions_rate
                    )
                    if hasattr(row.metrics, "conversions_from_interactions_rate")
                    else None,
                    "cpa": row.metrics.cost_micros / row.metrics.conversions
                    if row.metrics.conversions > 0
                    else None,
                    "cost": cost_micros / 1_000_000,  # Convert to currency units
                }
            )

        return performance_data

    async def _fetch_ad_schedule_bid_modifiers(
        self,
        client: GoogleAdsClient,
        customer_id: str,
        campaign_ids: list[str] | None = None,
    ) -> dict[str, dict[str, float]]:
        """Fetch ad schedule bid modifiers from campaign_criterion resource."""
        ga_service = client.get_service("GoogleAdsService")

        query = """
            SELECT
                campaign.id,
                campaign_criterion.criterion_id,
                campaign_criterion.ad_schedule.day_of_week,
                campaign_criterion.ad_schedule.start_hour,
                campaign_criterion.ad_schedule.end_hour,
                campaign_criterion.bid_modifier
            FROM campaign_criterion
            WHERE campaign_criterion.type = 'AD_SCHEDULE'
                AND campaign_criterion.status != 'REMOVED'
        """.strip()

        # Add campaign filter if specified
        if campaign_ids:
            campaign_filter, needs_parens = (
                GoogleAdsInputValidator.build_safe_campaign_id_filter(campaign_ids)
            )
            if campaign_filter:
                query += (
                    f" AND ({campaign_filter})"
                    if needs_parens
                    else f" AND {campaign_filter}"
                )

        logger.info(f"Fetching ad schedule bid modifiers for customer {customer_id}")

        search_request = client.get_type("SearchGoogleAdsRequest")
        search_request.customer_id = customer_id
        search_request.query = query

        try:
            response = self._execute_with_circuit_breaker(
                "get_ad_schedule_bid_modifiers",
                lambda: ga_service.search(request=search_request),
            )

            # Parse bid modifier results
            bid_modifiers = {}
            for row in response:
                campaign_id = str(row.campaign.id)
                ad_schedule = row.campaign_criterion.ad_schedule
                bid_modifier = row.campaign_criterion.bid_modifier

                day_of_week_enum = ad_schedule.day_of_week
                start_hour = ad_schedule.start_hour
                end_hour = ad_schedule.end_hour

                # Create key for matching with performance data
                for hour in range(start_hour, end_hour):
                    key = f"{campaign_id}_{day_of_week_enum}_{hour}"
                    bid_modifiers[key] = bid_modifier

            return bid_modifiers

        except GoogleAdsException as ex:
            logger.warning(f"Could not fetch ad schedule bid modifiers: {ex}")
            return {}

    def _combine_dayparting_data(
        self, performance_data: list[dict[str, Any]], bid_modifiers: dict[str, float]
    ) -> list[dict[str, Any]]:
        """Combine performance data with bid modifiers."""
        combined_data = []

        for record in performance_data:
            # Create lookup key for bid modifier
            key = (
                f"{record['campaign_id']}_{record['day_of_week_enum']}_{record['hour']}"
            )
            bid_adjustment = bid_modifiers.get(key)

            # Add bid adjustment to record
            record["bid_adjustment"] = bid_adjustment

            # Remove internal enum field
            record.pop("day_of_week_enum", None)

            combined_data.append(record)

        return combined_data

    async def _get_keyword_metrics(
        self,
        customer_id: str,
        start_date: datetime,
        end_date: datetime,
        campaign_ids: list[str] | None = None,
        ad_group_ids: list[str] | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Fetch keyword metrics from keyword_view.

        Args:
            customer_id: Google Ads customer ID
            start_date: Start date for metrics
            end_date: End date for metrics
            campaign_ids: Optional list of campaign IDs to filter
            ad_group_ids: Optional list of ad group IDs to filter

        Returns:
            Dictionary mapping "{ad_group_id}_{criterion_id}" to metrics
        """
        # Validate date range
        self._validate_date_range(start_date, end_date)

        client = self._get_client()
        ga_service = client.get_service("GoogleAdsService")

        # Format dates for query
        start_date_str = start_date.strftime("%Y-%m-%d")
        end_date_str = end_date.strftime("%Y-%m-%d")

        # Build query for keyword_view with metrics
        query = f"""
            SELECT
                ad_group.id,
                ad_group_criterion.criterion_id,
                metrics.impressions,
                metrics.clicks,
                metrics.cost_micros,
                metrics.conversions,
                metrics.conversions_value
            FROM keyword_view
            WHERE segments.date BETWEEN '{start_date_str}' AND '{end_date_str}'
                AND ad_group_criterion.status != 'REMOVED'
        """.strip()

        if campaign_ids:
            campaign_filter = GoogleAdsInputValidator.build_safe_campaign_id_filter(
                campaign_ids
            )
            if campaign_filter:
                # Don't wrap in parentheses if it's a single condition
                if " OR " in campaign_filter:
                    query += f" AND ({campaign_filter})"
                else:
                    query += f" AND {campaign_filter}"

        if ad_group_ids:
            ad_group_filter = GoogleAdsInputValidator.build_safe_ad_group_id_filter(
                ad_group_ids
            )
            if ad_group_filter:
                # Don't wrap in parentheses if it's a single condition
                if " OR " in ad_group_filter:
                    query += f" AND ({ad_group_filter})"
                else:
                    query += f" AND {ad_group_filter}"

        try:
            # Use paginated search for consistency with other methods
            response = await self._paginated_search_async(
                customer_id=customer_id,
                query=query,
            )

            # Aggregate metrics by keyword
            metrics_map = {}
            for row in response:
                key = f"{row.ad_group.id}_{row.ad_group_criterion.criterion_id}"

                if key not in metrics_map:
                    metrics_map[key] = {
                        "impressions": 0,
                        "clicks": 0,
                        "cost": 0.0,
                        "conversions": 0.0,
                        "conversion_value": 0.0,
                    }

                # Aggregate metrics with null safety
                metrics_map[key]["impressions"] += getattr(
                    row.metrics, "impressions", 0
                )
                metrics_map[key]["clicks"] += getattr(row.metrics, "clicks", 0)
                metrics_map[key]["cost"] += (
                    getattr(row.metrics, "cost_micros", 0) / MICROS_PER_CURRENCY_UNIT
                )
                metrics_map[key]["conversions"] += float(
                    getattr(row.metrics, "conversions", 0)
                )
                metrics_map[key]["conversion_value"] += float(
                    getattr(row.metrics, "conversions_value", 0)
                )

            logger.info(
                f"Fetched metrics for {len(metrics_map)} keywords from {start_date_str} to {end_date_str}"
            )
            return metrics_map

        except GoogleAdsException as ex:
            logger.error(f"Failed to fetch keyword metrics: {ex}")
            # Return empty metrics map on failure to allow graceful degradation
            return {}

    def _validate_date_range(self, start_date: datetime, end_date: datetime) -> None:
        """Validate that start_date is before end_date.

        Args:
            start_date: Start date for the range
            end_date: End date for the range

        Raises:
            ValueError: If start_date is not before end_date
        """
        if start_date >= end_date:
            raise ValueError(
                f"start_date ({start_date}) must be before end_date ({end_date})"
            )

    @staticmethod
    def _parse_geographic_resource_name(
        resource_name: str,
    ) -> tuple[str | None, str | None]:
        """Parse geographic view resource name to extract criterion ID and location type.

        Args:
            resource_name: Resource name in format:
                customers/[customer_id]/geographicViews/[criterion_id]~[location_type]

        Returns:
            Tuple of (criterion_id, location_type) or (None, None) if parsing fails
        """
        try:
            if not resource_name or "geographicViews/" not in resource_name:
                return None, None

            # Extract the part after geographicViews/
            geo_part = resource_name.split("geographicViews/", 1)[1]

            # Split by ~ to get criterion_id and location_type
            if "~" in geo_part:
                criterion_id, location_type = geo_part.split("~", 1)
                return criterion_id, location_type
            else:
                # No location type specified
                return geo_part, None
        except (IndexError, ValueError):
            logger.warning(f"Failed to parse geographic resource name: {resource_name}")
            return None, None

    @staticmethod
    def _calculate_rate(
        numerator: float, denominator: float, default: float = 0.0
    ) -> float:
        """Calculate a rate safely, handling division by zero.

        Args:
            numerator: The top number in the division
            denominator: The bottom number in the division
            default: Default value to return if denominator is 0

        Returns:
            The calculated rate or default if division by zero
        """
        return numerator / denominator if denominator > 0 else default

    async def _get_location_names(
        self, customer_id: str, criterion_ids: list[str]
    ) -> dict[str, dict[str, str]]:
        """Fetch location names for given criterion IDs.

        Args:
            customer_id: Google Ads customer ID
            criterion_ids: List of location criterion IDs

        Returns:
            Dictionary mapping criterion_id to location details
        """
        if not criterion_ids:
            return {}

        client = self._get_client()
        ga_service = client.get_service("GoogleAdsService")

        # Build query for geo_target_constant
        # Note: geo_target_constant uses resource names like "geoTargetConstants/1023191"
        criterion_filter = " OR ".join(
            [f"geo_target_constant.id = {cid}" for cid in criterion_ids]
        )

        query = f"""
            SELECT
                geo_target_constant.id,
                geo_target_constant.name,
                geo_target_constant.country_code,
                geo_target_constant.target_type,
                geo_target_constant.canonical_name
            FROM geo_target_constant
            WHERE {criterion_filter}
        """.strip()

        try:
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._execute_with_circuit_breaker(
                    "google_ads_api_search",
                    lambda: ga_service.search(customer_id=customer_id, query=query),
                ),
            )

            location_map = {}
            for row in response:
                geo_target = row.geo_target_constant
                location_map[str(geo_target.id)] = {
                    "name": geo_target.name,
                    "country_code": geo_target.country_code,
                    "target_type": geo_target.target_type.name
                    if geo_target.target_type
                    else "",
                    "canonical_name": geo_target.canonical_name,
                }

            return location_map

        except GoogleAdsException as ex:
            logger.error(f"Failed to fetch location names: {ex}")
            return {}

    async def get_performance_max_data(
        self,
        customer_id: str,
        start_date: datetime,
        end_date: datetime,
    ) -> list[dict[str, Any]]:
        """Fetch Performance Max campaign data from Google Ads.

        Args:
            customer_id: Google Ads customer ID
            start_date: Start date for the report
            end_date: End date for the report

        Returns:
            List of Performance Max data dictionaries

        Raises:
            AuthenticationError: For authentication failures
            RateLimitError: For rate limit errors
            APIError: For other API errors

        Example:
            >>> client = GoogleAdsAPIClient(...)
            >>> pmax_data = await client.get_performance_max_data(
            ...     customer_id="123-456-7890",
            ...     start_date=datetime(2024, 1, 1),
            ...     end_date=datetime(2024, 1, 31)
            ... )
            >>> for campaign in pmax_data:
            ...     print(f"{campaign['campaign_name']}: {campaign['conversions']} conversions")
        """
        # Validate customer ID format
        customer_id = GoogleAdsInputValidator.validate_customer_id(customer_id)

        # Validate date range
        self._validate_date_range(start_date, end_date)

        client = self._get_client()
        ga_service = client.get_service("GoogleAdsService")

        # Format dates for query
        start_date_str = start_date.strftime("%Y-%m-%d")
        end_date_str = end_date.strftime("%Y-%m-%d")

        # Build query for Performance Max campaigns
        query = f"""
            SELECT
                campaign.id,
                campaign.name,
                campaign.status,
                campaign.performance_max_upgrade.performance_max_campaign,
                campaign.performance_max_upgrade.status,
                campaign_budget.amount_micros,
                metrics.impressions,
                metrics.clicks,
                metrics.cost_micros,
                metrics.conversions,
                metrics.conversions_value,
                metrics.video_views,
                metrics.interactions,
                segments.asset_group_asset_field_type,
                segments.conversion_action
            FROM campaign
            WHERE campaign.advertising_channel_type = 'PERFORMANCE_MAX'
                AND segments.date BETWEEN '{start_date_str}' AND '{end_date_str}'
        """.strip()

        query += " ORDER BY campaign.name"

        try:
            logger.info(
                f"Fetching Performance Max data for customer {customer_id} "
                f"between {start_date_str} and {end_date_str}"
            )

            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._execute_with_circuit_breaker(
                    "google_ads_api_search",
                    lambda: ga_service.search(customer_id=customer_id, query=query),
                ),
            )

            pmax_data = []
            for row in response:
                campaign = row.campaign
                metrics = row.metrics
                budget = row.campaign_budget
                segments = row.segments

                # Convert micros to currency
                budget_amount = (
                    budget.amount_micros / MICROS_PER_CURRENCY_UNIT if budget else 0
                )
                cost = metrics.cost_micros / MICROS_PER_CURRENCY_UNIT

                pmax_data.append(
                    {
                        "campaign_id": str(campaign.id),
                        "campaign_name": campaign.name,
                        "status": campaign.status.name,
                        "budget_amount": budget_amount,
                        "performance_max_upgrade_status": (
                            getattr(
                                getattr(
                                    campaign.performance_max_upgrade, "status", None
                                ),
                                "name",
                                None,
                            )
                            if campaign.performance_max_upgrade
                            else None
                        ),
                        "performance_max_campaign_resource": (
                            getattr(
                                campaign.performance_max_upgrade,
                                "performance_max_campaign",
                                None,
                            )
                            if campaign.performance_max_upgrade
                            else None
                        ),
                        # Metrics
                        "impressions": metrics.impressions,
                        "clicks": metrics.clicks,
                        "cost": cost,
                        "conversions": metrics.conversions,
                        "conversion_value": metrics.conversions_value,
                        "video_views": getattr(metrics, "video_views", 0),
                        "interactions": getattr(metrics, "interactions", 0),
                        # Segments
                        "asset_group_asset_field_type": (
                            getattr(
                                getattr(segments, "asset_group_asset_field_type", None),
                                "name",
                                None,
                            )
                        ),
                        "conversion_action": getattr(
                            segments, "conversion_action", None
                        ),
                    }
                )

            logger.info(
                f"Fetched {len(pmax_data)} Performance Max records for customer {customer_id}"
            )
            return pmax_data

        except GoogleAdsException as e:
            self._handle_google_ads_exception(e)

    async def get_performance_max_search_terms(
        self,
        customer_id: str,
        start_date: datetime,
        end_date: datetime,
        campaign_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch Performance Max search terms data from Google Ads.

        Args:
            customer_id: Google Ads customer ID
            start_date: Start date for the report
            end_date: End date for the report
            campaign_ids: Optional list of Performance Max campaign IDs to filter

        Returns:
            List of Performance Max search term dictionaries with metrics

        Raises:
            AuthenticationError: For authentication failures
            RateLimitError: For rate limit errors
            APIError: For other API errors

        Example:
            >>> client = GoogleAdsAPIClient(...)
            >>> search_terms = await client.get_performance_max_search_terms(
            ...     customer_id="123-456-7890",
            ...     start_date=datetime(2024, 1, 1),
            ...     end_date=datetime(2024, 1, 31),
            ...     campaign_ids=["456", "789"]
            ... )
            >>> for term in search_terms:
            ...     if term['category_label'] == 'Local':
            ...         print(f"Local search: {term['search_term']} - CPA: ${term['cpa']:.2f}")
        """
        # Validate customer ID format
        customer_id = GoogleAdsInputValidator.validate_customer_id(customer_id)

        # Validate date range
        self._validate_date_range(start_date, end_date)

        client = self._get_client()
        ga_service = client.get_service("GoogleAdsService")

        # Format dates for query
        start_date_str = start_date.strftime("%Y-%m-%d")
        end_date_str = end_date.strftime("%Y-%m-%d")

        # Build query for Performance Max search terms
        # Note: In v20, Performance Max search terms are available via campaign_search_term_insight
        query = f"""
            SELECT
                campaign.id,
                campaign.name,
                campaign_search_term_insight.search_term,
                campaign_search_term_insight.category_label,
                metrics.impressions,
                metrics.clicks,
                metrics.cost_micros,
                metrics.conversions,
                metrics.conversions_value
            FROM campaign_search_term_insight
            WHERE segments.date BETWEEN '{start_date_str}' AND '{end_date_str}'
                AND campaign.advertising_channel_type = 'PERFORMANCE_MAX'
        """.strip()

        if campaign_ids:
            # Validate campaign IDs to prevent injection
            campaign_filter, needs_parens = (
                GoogleAdsInputValidator.build_safe_campaign_id_filter(campaign_ids)
            )
            if campaign_filter:
                query += (
                    f" AND ({campaign_filter})"
                    if needs_parens
                    else f" AND {campaign_filter}"
                )

        query += " ORDER BY metrics.impressions DESC"

        try:
            logger.info(
                f"Fetching Performance Max search terms for customer {customer_id} "
                f"between {start_date_str} and {end_date_str}"
            )

            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._execute_with_circuit_breaker(
                    "google_ads_api_search",
                    lambda: ga_service.search(customer_id=customer_id, query=query),
                ),
            )

            search_terms = []
            for row in response:
                campaign = row.campaign
                insight = row.campaign_search_term_insight
                metrics = row.metrics

                # Convert micros to currency
                cost = metrics.cost_micros / MICROS_PER_CURRENCY_UNIT

                search_terms.append(
                    {
                        "campaign_id": str(campaign.id),
                        "campaign_name": campaign.name,
                        "search_term": insight.search_term,
                        "category_label": getattr(insight, "category_label", None),
                        "impressions": metrics.impressions,
                        "clicks": metrics.clicks,
                        "cost": cost,
                        "conversions": metrics.conversions,
                        "conversion_value": metrics.conversions_value,
                        "ctr": self._calculate_rate(
                            metrics.clicks, metrics.impressions
                        ),
                        "cpc": self._calculate_rate(cost, metrics.clicks),
                        "conversion_rate": self._calculate_rate(
                            metrics.conversions, metrics.clicks
                        ),
                        "cpa": self._calculate_rate(cost, metrics.conversions, None),
                    }
                )

            logger.info(
                f"Fetched {len(search_terms)} Performance Max search terms for customer {customer_id}"
            )
            return search_terms

        except GoogleAdsException as e:
            self._handle_google_ads_exception(e)

    @account_info_rate_limited
    async def get_shared_negative_lists(
        self,
        customer_id: str,
    ) -> list[dict[str, Any]]:
        """Fetch shared negative keyword lists for a customer.

        Args:
            customer_id: Google Ads customer ID (7-10 digits, with or without hyphens)

        Returns:
            List of dictionaries with at least: id, name, negative_count

        Example:
            >>> client = GoogleAdsAPIClient(...)
            >>> lists = await client.get_shared_negative_lists("123-456-7890")
            >>> for neg_list in lists:
            ...     print(f"{neg_list['name']}: {neg_list['negative_count']} keywords")
            "Brand Negatives: 15 keywords"
            "Competitor Terms: 8 keywords"
        """
        # Validate customer ID format
        customer_id = GoogleAdsInputValidator.validate_customer_id(customer_id)

        client = self._get_client()
        ga_service = client.get_service("GoogleAdsService")

        # Query to fetch shared negative lists with counts
        query = """
            SELECT
                shared_set.id,
                shared_set.name,
                shared_set.status,
                shared_set.member_count
            FROM shared_set
            WHERE shared_set.type = 'NEGATIVE_KEYWORDS'
                AND shared_set.status = 'ENABLED'
        """.strip()

        try:
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._execute_with_circuit_breaker(
                    "google_ads_api_search",
                    lambda: ga_service.search(customer_id=customer_id, query=query),
                ),
            )

            negative_lists = []
            for row in response:
                shared_set = row.shared_set
                negative_lists.append(
                    {
                        "id": str(shared_set.id),
                        "name": shared_set.name,
                        "negative_count": getattr(shared_set, "member_count", 0),
                        "status": shared_set.status.name,
                    }
                )

            logger.info(
                f"Fetched {len(negative_lists)} shared negative lists for customer {customer_id}"
            )
            return negative_lists

        except GoogleAdsException as e:
            self._handle_google_ads_exception(e)

    async def get_campaign_shared_sets(
        self,
        customer_id: str,
        campaign_id: str,
    ) -> list[dict[str, Any]]:
        """Get shared sets applied to a specific campaign.

        Args:
            customer_id: Google Ads customer ID (7-10 digits, with or without hyphens)
            campaign_id: Campaign ID (numeric string)

        Returns:
            List of dictionaries with at least: id, name

        Example:
            >>> client = GoogleAdsAPIClient(...)
            >>> shared_sets = await client.get_campaign_shared_sets("123-456-7890", "456789")
            >>> for shared_set in shared_sets:
            ...     print(f"Campaign uses shared set: {shared_set['name']} (ID: {shared_set['id']})")
            "Campaign uses shared set: Brand Negatives (ID: 12345)"
        """
        # Validate customer ID format
        customer_id = GoogleAdsInputValidator.validate_customer_id(customer_id)

        # Validate campaign ID
        GoogleAdsInputValidator.validate_campaign_ids([campaign_id])

        client = self._get_client()
        ga_service = client.get_service("GoogleAdsService")

        # Query to fetch shared sets for a specific campaign
        campaign_filter = f"campaign.id = {campaign_id}"
        query = f"""
            SELECT
                campaign_shared_set.shared_set,
                shared_set.id,
                shared_set.name,
                shared_set.type,
                shared_set.status
            FROM campaign_shared_set
            WHERE campaign_shared_set.status = 'ENABLED'
                AND shared_set.type = 'NEGATIVE_KEYWORDS'
                AND shared_set.status = 'ENABLED'
                AND {campaign_filter}
        """.strip()

        try:
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._execute_with_circuit_breaker(
                    "google_ads_api_search",
                    lambda: ga_service.search(customer_id=customer_id, query=query),
                ),
            )

            shared_sets = []
            for row in response:
                shared_set = row.shared_set
                shared_sets.append(
                    {
                        "id": str(shared_set.id),
                        "name": shared_set.name,
                        "type": shared_set.type.name,
                        "status": shared_set.status.name,
                    }
                )

            logger.info(
                f"Fetched {len(shared_sets)} shared sets for campaign {campaign_id} in customer {customer_id}"
            )
            return shared_sets

        except GoogleAdsException as e:
            self._handle_google_ads_exception(e)

    async def get_shared_set_negatives(
        self,
        customer_id: str,
        shared_set_id: str,
    ) -> list[dict[str, Any]]:
        """Get negative keywords from a specific shared set.

        Args:
            customer_id: Google Ads customer ID (7-10 digits, with or without hyphens)
            shared_set_id: Shared set ID to fetch negatives from (positive integer)

        Returns:
            List of dictionaries with at least: text (the negative keyword)

        Example:
            >>> client = GoogleAdsAPIClient(...)
            >>> negatives = await client.get_shared_set_negatives("123-456-7890", "12345")
            >>> for negative in negatives:
            ...     print(f"Negative keyword: {negative['text']} ({negative['match_type']})")
            "Negative keyword: competitor brand (BROAD)"
            "Negative keyword: free (EXACT)"
        """
        # Validate customer ID format
        customer_id = GoogleAdsInputValidator.validate_customer_id(customer_id)

        # Validate shared set ID using consistent validation pattern
        shared_set_id = GoogleAdsInputValidator.validate_shared_set_id(shared_set_id)

        client = self._get_client()
        ga_service = client.get_service("GoogleAdsService")

        # Query to fetch negative keywords from a specific shared set
        shared_set_filter = f"shared_set.id = {shared_set_id}"
        query = f"""
            SELECT
                shared_criterion.criterion_id,
                shared_criterion.keyword.text,
                shared_criterion.keyword.match_type,
                shared_set.id,
                shared_set.name
            FROM shared_criterion
            WHERE shared_set.type = 'NEGATIVE_KEYWORDS'
                AND shared_set.status = 'ENABLED'
                AND shared_criterion.type = 'KEYWORD'
                AND {shared_set_filter}
        """.strip()

        try:
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._execute_with_circuit_breaker(
                    "google_ads_api_search",
                    lambda: ga_service.search(customer_id=customer_id, query=query),
                ),
            )

            negatives = []
            for row in response:
                criterion = row.shared_criterion
                negatives.append(
                    {
                        "id": str(criterion.criterion_id),
                        "text": criterion.keyword.text,
                        "match_type": criterion.keyword.match_type.name,
                        "shared_set_id": str(row.shared_set.id),
                        "shared_set_name": row.shared_set.name,
                    }
                )

            logger.info(
                f"Fetched {len(negatives)} negative keywords from shared set {shared_set_id} in customer {customer_id}"
            )
            return negatives

        except GoogleAdsException as e:
            self._handle_google_ads_exception(e)

    @report_rate_limited
    async def get_placement_data(
        self,
        customer_id: str,
        start_date: datetime,
        end_date: datetime,
        campaigns: list[str] | None = None,
        ad_groups: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch placement data from Google Ads.

        Args:
            customer_id: Google Ads customer ID
            start_date: Start date for the report
            end_date: End date for the report
            campaigns: Optional list of campaign IDs to filter
            ad_groups: Optional list of ad group IDs to filter

        Returns:
            List of placement data dictionaries

        Raises:
            AuthenticationError: For authentication failures
            RateLimitError: For rate limit errors
            APIError: For other API errors
        """
        # Validate customer ID format
        customer_id = GoogleAdsInputValidator.validate_customer_id(customer_id)

        # Validate campaign IDs early to prevent any API calls with malicious input
        if campaigns:
            GoogleAdsInputValidator.validate_campaign_ids(campaigns)

        # Validate ad group IDs early to prevent any API calls with malicious input
        if ad_groups:
            GoogleAdsInputValidator.validate_ad_group_ids(ad_groups)

        # Validate date range
        self._validate_date_range(start_date, end_date)

        client = self._get_client()
        ga_service = client.get_service("GoogleAdsService")

        # Format dates for query
        start_date_str = start_date.strftime("%Y-%m-%d")
        end_date_str = end_date.strftime("%Y-%m-%d")

        # Build query for placement view
        # Note: In Google Ads API v20, placement data is available via detail_placement_view
        query = f"""
            SELECT
                detail_placement_view.resource_name,
                detail_placement_view.placement,
                detail_placement_view.placement_type,
                detail_placement_view.display_name,
                campaign.id,
                campaign.name,
                ad_group.id,
                ad_group.name,
                metrics.impressions,
                metrics.clicks,
                metrics.cost_micros,
                metrics.conversions,
                metrics.conversions_value
            FROM detail_placement_view
            WHERE segments.date BETWEEN '{start_date_str}' AND '{end_date_str}'
                AND metrics.impressions > 0
        """.strip()

        if campaigns:
            # Validate campaign IDs to prevent injection
            campaign_filter = GoogleAdsInputValidator.build_safe_campaign_id_filter(
                campaigns
            )
            if campaign_filter:
                query += f" AND ({campaign_filter})"

        if ad_groups:
            # Validate ad group IDs to prevent injection
            ad_group_filter = GoogleAdsInputValidator.build_safe_ad_group_id_filter(
                ad_groups
            )
            if ad_group_filter:
                query += f" AND ({ad_group_filter})"

        query += " ORDER BY metrics.impressions DESC"

        try:
            logger.info(
                f"Fetching placement data for customer {customer_id} "
                f"between {start_date_str} and {end_date_str}"
            )

            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._execute_with_circuit_breaker(
                    "google_ads_api_search",
                    lambda: ga_service.search(customer_id=customer_id, query=query),
                ),
            )

            placements = []
            for row in response:
                placement_view = row.detail_placement_view
                metrics = row.metrics

                # Convert micros to currency
                cost = metrics.cost_micros / MICROS_PER_CURRENCY_UNIT

                # Calculate derived metrics
                ctr = self._calculate_rate(metrics.clicks, metrics.impressions) * 100
                cpc = self._calculate_rate(cost, metrics.clicks)
                cpa = self._calculate_rate(cost, metrics.conversions, 0.0)
                roas = self._calculate_rate(metrics.conversions_value, cost)

                placements.append(
                    {
                        "placement_id": placement_view.placement,
                        "placement_name": placement_view.placement,
                        "display_name": placement_view.display_name,
                        "placement_type": placement_view.placement_type.name
                        if placement_view.placement_type
                        else "UNSPECIFIED",
                        "campaign_ids": [str(row.campaign.id)],
                        "ad_group_ids": [str(row.ad_group.id)],
                        "campaign_name": row.campaign.name,
                        "ad_group_name": row.ad_group.name,
                        # Performance metrics
                        "impressions": metrics.impressions,
                        "clicks": metrics.clicks,
                        "cost": cost,
                        "conversions": float(metrics.conversions),
                        "conversion_value": float(metrics.conversions_value),
                        "ctr": ctr,
                        "cpc": cpc,
                        "cpa": cpa,
                        "roas": roas,
                        # Default brand safety - would need additional logic to determine
                        "is_brand_safe": True,
                    }
                )

            logger.info(
                f"Fetched {len(placements)} placement records for customer {customer_id}"
            )
            return placements

        except GoogleAdsException as e:
            self._handle_google_ads_exception(e)
