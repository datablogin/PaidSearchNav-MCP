"""Google Ads account hierarchy mapper."""

import asyncio
import logging
import time
from datetime import datetime

from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException

from paidsearchnav.core.models.account import (
    Account,
    AccountHierarchy,
    AccountStatus,
    AccountType,
    AuditOptInStatus,
    SyncResult,
)

logger = logging.getLogger(__name__)


class AccountMapper:
    """Maps Google Ads account hierarchy from API to domain models."""

    def __init__(
        self,
        developer_token: str,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        login_customer_id: str | None = None,
    ):
        """Initialize AccountMapper with Google Ads credentials.

        Args:
            developer_token: Google Ads API developer token
            client_id: OAuth2 client ID
            client_secret: OAuth2 client secret
            refresh_token: OAuth2 refresh token
            login_customer_id: Login customer ID for MCC accounts
        """
        self.credentials = {
            "developer_token": developer_token,
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
        }
        if login_customer_id:
            self.credentials["login_customer_id"] = login_customer_id

        self._client: GoogleAdsClient | None = None

    def _get_client(self) -> GoogleAdsClient:
        """Get or create Google Ads client."""
        if not self._client:
            self._client = GoogleAdsClient.load_from_dict(self.credentials)
        return self._client

    async def sync_account_hierarchy(self, root_mcc: str | None = None) -> SyncResult:
        """Sync account hierarchy from Google Ads API.

        Args:
            root_mcc: Optional root MCC customer ID to start from

        Returns:
            SyncResult with hierarchy and sync metadata
        """
        start_time = time.time()
        errors = []
        hierarchy = None
        accounts_synced = 0

        try:
            # Run in executor to avoid blocking
            hierarchy = await asyncio.get_event_loop().run_in_executor(
                None, self._fetch_hierarchy, root_mcc
            )
            accounts_synced = hierarchy.total_accounts if hierarchy else 0
            success = True

        except Exception as e:
            logger.error(f"Failed to sync account hierarchy: {e}")
            errors.append(str(e))
            success = False

        sync_duration = time.time() - start_time

        return SyncResult(
            success=success,
            hierarchy=hierarchy,
            accounts_synced=accounts_synced,
            errors=errors,
            sync_duration_seconds=sync_duration,
            timestamp=datetime.utcnow(),
        )

    def _fetch_hierarchy(self, root_mcc: str | None = None) -> AccountHierarchy:
        """Fetch account hierarchy from Google Ads API (synchronous).

        Args:
            root_mcc: Optional root MCC customer ID

        Returns:
            AccountHierarchy with all accessible accounts
        """
        client = self._get_client()
        accounts = {}

        # First get accessible customers
        customer_service = client.get_service("CustomerService")

        try:
            # Get list of accessible customers
            accessible_customers = customer_service.list_accessible_customers()
            logger.info(
                f"Found {len(accessible_customers.resource_names)} accessible customers"
            )

            # Extract customer IDs from resource names (format: customers/1234567890)
            customer_ids = [
                resource_name.split("/")[1]
                for resource_name in accessible_customers.resource_names
            ]

            # If root MCC specified, filter to only that hierarchy
            if root_mcc and root_mcc not in customer_ids:
                logger.warning(f"Root MCC {root_mcc} not in accessible customers")
                customer_ids = []
            elif root_mcc:
                customer_ids = [root_mcc]

            # Fetch details for each customer
            for customer_id in customer_ids:
                try:
                    account = self._fetch_customer_details(client, customer_id)
                    if account:
                        accounts[account.customer_id] = account

                        # If this is an MCC, fetch its child accounts
                        if account.is_mcc:
                            child_accounts = self._fetch_child_accounts(
                                client, customer_id
                            )
                            for child in child_accounts:
                                accounts[child.customer_id] = child

                except Exception as e:
                    logger.error(f"Failed to fetch customer {customer_id}: {e}")

        except GoogleAdsException as e:
            logger.error(f"Google Ads API error: {e}")
            raise

        return AccountHierarchy(
            root_customer_id=root_mcc,
            accounts=accounts,
            last_sync=datetime.utcnow(),
        )

    def _fetch_customer_details(
        self, client: GoogleAdsClient, customer_id: str
    ) -> Account | None:
        """Fetch details for a single customer.

        Args:
            client: Google Ads client
            customer_id: Customer ID to fetch

        Returns:
            Account model or None if fetch fails
        """
        try:
            ga_service = client.get_service("GoogleAdsService")

            # Query to get customer details
            query = """
                SELECT
                    customer.id,
                    customer.descriptive_name,
                    customer.status,
                    customer.currency_code,
                    customer.time_zone,
                    customer.test_account,
                    customer.manager
                FROM customer
                WHERE customer.id = :customer_id
            """

            # Set the customer ID for the query
            request = client.get_type("SearchGoogleAdsRequest")
            request.customer_id = customer_id
            request.query = query
            request.page_size = 1

            # Add parameter value
            param = request.query_parameters.add()
            param.key = "customer_id"
            param.value.int64_value = int(customer_id)

            response = ga_service.search(request=request)

            for row in response:
                customer = row.customer

                # Determine account type and properties
                is_mcc = customer.manager
                account_type = AccountType.MCC if is_mcc else AccountType.STANDARD

                # Map status
                status_mapping = {
                    "ENABLED": AccountStatus.ENABLED,
                    "PAUSED": AccountStatus.PAUSED,
                    "REMOVED": AccountStatus.REMOVED,
                    "SUSPENDED": AccountStatus.SUSPENDED,
                    "CANCELED": AccountStatus.CANCELED,
                }
                status = status_mapping.get(customer.status.name, AccountStatus.ENABLED)

                return Account(
                    customer_id=str(customer.id),
                    name=customer.descriptive_name or f"Account {customer.id}",
                    account_type=account_type,
                    status=status,
                    audit_status=AuditOptInStatus.PENDING,
                    is_mcc=is_mcc,
                    can_manage_clients=is_mcc,
                    accessible=True,
                    currency_code=customer.currency_code,
                    time_zone=customer.time_zone,
                    test_account=customer.test_account,
                    last_sync=datetime.utcnow(),
                )

        except Exception as e:
            logger.error(f"Failed to fetch customer details for {customer_id}: {e}")
            return None

    def _fetch_child_accounts(
        self, client: GoogleAdsClient, mcc_customer_id: str
    ) -> list[Account]:
        """Fetch child accounts for an MCC.

        Args:
            client: Google Ads client
            mcc_customer_id: MCC customer ID

        Returns:
            List of child Account models
        """
        child_accounts = []

        try:
            ga_service = client.get_service("GoogleAdsService")

            # Query to get client links (child accounts)
            query = """
                SELECT
                    customer_client_link.client_customer,
                    customer_client_link.status
                FROM customer_client_link
                WHERE customer_client_link.status = 'ENABLED'
            """

            request = client.get_type("SearchGoogleAdsRequest")
            request.customer_id = mcc_customer_id
            request.query = query
            request.page_size = 1000

            response = ga_service.search(request=request)

            for row in response:
                # Extract customer ID from resource name (customers/1234567890)
                client_customer = row.customer_client_link.client_customer
                if client_customer:
                    child_customer_id = client_customer.split("/")[1]

                    # Fetch details for this child account
                    child_account = self._fetch_customer_details(
                        client, child_customer_id
                    )
                    if child_account:
                        child_account.manager_customer_id = mcc_customer_id
                        child_accounts.append(child_account)

        except Exception as e:
            logger.error(
                f"Failed to fetch child accounts for MCC {mcc_customer_id}: {e}"
            )

        return child_accounts
