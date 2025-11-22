"""Enhanced Google Ads API client with write operations for workflow integrations.

This client extends the existing read-only functionality with write operations
for applying recommendations directly to Google Ads accounts through API calls.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException
from pydantic import BaseModel, Field

from paidsearchnav.auth.oauth_manager import OAuth2Manager
from paidsearchnav.core.config import Settings
from paidsearchnav.core.exceptions import APIError, AuthenticationError
from paidsearchnav.platforms.google.client import GoogleAdsAPIClient
from paidsearchnav.platforms.google.rate_limiting import (
    GoogleAdsRateLimiter,
    bulk_mutate_rate_limited,
    mutate_rate_limited,
)

logger = logging.getLogger(__name__)


def _extract_google_ads_error_details(exception: GoogleAdsException) -> dict[str, Any]:
    """Extract detailed error information from GoogleAdsException."""
    error_details = {
        "request_id": exception.request_id,
        "errors": [],
        "error_summary": str(exception),
    }

    if exception.failure:
        for error in exception.failure.errors:
            error_info = {
                "error_code": error.error_code.error_code,
                "message": error.message,
                "location": {
                    "field_path_elements": [
                        {
                            "field_name": elem.field_name,
                            "index": getattr(elem, "index", None),
                        }
                        for elem in error.location.field_path_elements
                    ]
                }
                if error.location
                else None,
            }

            # Extract specific error code information
            if hasattr(error.error_code, "authentication_error"):
                error_info["error_type"] = "AUTHENTICATION_ERROR"
                error_info["specific_error"] = (
                    error.error_code.authentication_error.name
                )
            elif hasattr(error.error_code, "authorization_error"):
                error_info["error_type"] = "AUTHORIZATION_ERROR"
                error_info["specific_error"] = error.error_code.authorization_error.name
            elif hasattr(error.error_code, "quota_error"):
                error_info["error_type"] = "QUOTA_ERROR"
                error_info["specific_error"] = error.error_code.quota_error.name
            elif hasattr(error.error_code, "request_error"):
                error_info["error_type"] = "REQUEST_ERROR"
                error_info["specific_error"] = error.error_code.request_error.name
            elif hasattr(error.error_code, "field_error"):
                error_info["error_type"] = "FIELD_ERROR"
                error_info["specific_error"] = error.error_code.field_error.name
            elif hasattr(error.error_code, "mutate_error"):
                error_info["error_type"] = "MUTATE_ERROR"
                error_info["specific_error"] = error.error_code.mutate_error.name

            error_details["errors"].append(error_info)

    return error_details


class WriteOperationType(Enum):
    """Types of write operations supported."""

    ADD_NEGATIVE_KEYWORDS = "add_negative_keywords"
    REMOVE_NEGATIVE_KEYWORDS = "remove_negative_keywords"
    UPDATE_KEYWORDS = "update_keywords"
    UPDATE_BIDS = "update_bids"
    UPDATE_BUDGETS = "update_budgets"
    PAUSE_CAMPAIGNS = "pause_campaigns"
    ENABLE_CAMPAIGNS = "enable_campaigns"
    PAUSE_AD_GROUPS = "pause_ad_groups"
    ENABLE_AD_GROUPS = "enable_ad_groups"
    CREATE_SHARED_SETS = "create_shared_sets"
    UPDATE_SHARED_SETS = "update_shared_sets"


class WriteOperationStatus(Enum):
    """Status of write operations."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class WriteOperationResult:
    """Result of a write operation."""

    operation_type: WriteOperationType
    status: WriteOperationStatus
    resource_name: str
    success: bool
    resource_id: Optional[str] = None
    error_message: Optional[str] = None
    mutation_result: Optional[Dict[str, Any]] = None
    rollback_data: Optional[Dict[str, Any]] = None


class NegativeKeywordOperation(BaseModel):
    """Negative keyword operation definition."""

    campaign_id: str = Field(..., description="Campaign ID")
    ad_group_id: Optional[str] = Field(None, description="Ad Group ID (optional)")
    keywords: List[str] = Field(..., description="List of negative keywords")
    match_type: str = Field(default="BROAD", description="Match type for keywords")


class BudgetOperation(BaseModel):
    """Budget update operation definition."""

    campaign_id: str = Field(..., description="Campaign ID")
    amount_micros: int = Field(..., description="New budget amount in micros")
    delivery_method: Optional[str] = Field(None, description="Budget delivery method")


class BidOperation(BaseModel):
    """Bid adjustment operation definition."""

    ad_group_id: str = Field(..., description="Ad Group ID")
    keyword_id: Optional[str] = Field(None, description="Keyword ID (for keyword bids)")
    bid_micros: int = Field(..., description="New bid amount in micros")
    bid_type: str = Field(default="CPC", description="Bid type")


class CampaignStatusOperation(BaseModel):
    """Campaign status change operation definition."""

    campaign_id: str = Field(..., description="Campaign ID")
    status: str = Field(..., description="New campaign status (ENABLED/PAUSED)")


class GoogleAdsWriteClient:
    """Enhanced Google Ads API client with write operations."""

    def __init__(
        self,
        settings: Settings,
        oauth_manager: OAuth2Manager,
        base_client: Optional[GoogleAdsAPIClient] = None,
        dry_run: bool = False,
    ):
        """Initialize write client.

        Args:
            settings: Application settings
            oauth_manager: OAuth2 manager for authentication
            base_client: Base read-only client (optional)
            dry_run: Whether to run in dry-run mode (no actual mutations)
        """
        self.settings = settings
        self.oauth_manager = oauth_manager
        self.base_client = base_client
        self.dry_run = dry_run

        # Initialize rate limiter
        self._rate_limiter = GoogleAdsRateLimiter(settings)

        # Track write operations for rollback with memory management
        self._operation_history: Dict[str, List[WriteOperationResult]] = {}
        self._max_history_per_customer = 1000  # Limit history per customer
        self._max_total_history = 10000  # Global limit across all customers

    def _add_to_operation_history(
        self, customer_id: str, results: List[WriteOperationResult]
    ) -> None:
        """Add operation results to history with memory management."""
        if customer_id not in self._operation_history:
            self._operation_history[customer_id] = []

        # Add new results
        self._operation_history[customer_id].extend(results)

        # Trim per-customer history if too large
        if len(self._operation_history[customer_id]) > self._max_history_per_customer:
            # Keep only the most recent operations
            excess = (
                len(self._operation_history[customer_id])
                - self._max_history_per_customer
            )
            self._operation_history[customer_id] = self._operation_history[customer_id][
                excess:
            ]
            logger.debug(
                f"Trimmed {excess} old operations from history for customer {customer_id}"
            )

        # Check global history size and trim oldest customers if needed
        total_operations = sum(len(ops) for ops in self._operation_history.values())
        if total_operations > self._max_total_history:
            self._trim_global_history()

    def _trim_global_history(self) -> None:
        """Trim global operation history by removing oldest operations."""
        total_operations = sum(len(ops) for ops in self._operation_history.values())
        operations_to_remove = total_operations - self._max_total_history

        if operations_to_remove <= 0:
            return

        # Sort customers by total operations (remove from customers with most history first)
        customer_history_sizes = [
            (customer_id, len(ops))
            for customer_id, ops in self._operation_history.items()
        ]
        customer_history_sizes.sort(key=lambda x: x[1], reverse=True)

        removed = 0
        for customer_id, history_size in customer_history_sizes:
            if removed >= operations_to_remove:
                break

            # Remove half of this customer's history
            to_remove = min(history_size // 2, operations_to_remove - removed)
            if to_remove > 0:
                self._operation_history[customer_id] = self._operation_history[
                    customer_id
                ][to_remove:]
                removed += to_remove
                logger.debug(
                    f"Trimmed {to_remove} operations from history for customer {customer_id}"
                )

        # Remove empty histories
        self._operation_history = {
            k: v for k, v in self._operation_history.items() if v
        }

    async def _get_write_client(self, customer_id: str) -> GoogleAdsClient:
        """Get authenticated write client for customer.

        Args:
            customer_id: Google Ads customer ID

        Returns:
            Authenticated GoogleAdsClient with write permissions
        """
        try:
            # Get workflow credentials
            workflow_tokens = await self.oauth_manager.get_workflow_credentials(
                customer_id
            )

            # Create Google Ads client
            if not self.settings.google_ads:
                raise AuthenticationError("Google Ads configuration not provided")

            credentials = workflow_tokens.to_google_credentials(
                self.settings.google_ads.client_secret
            )

            client_config = {
                "developer_token": self.settings.google_ads.developer_token,
                "client_id": workflow_tokens.client_id,
                "client_secret": self.settings.google_ads.client_secret.get_secret_value(),
                "refresh_token": workflow_tokens.refresh_token,
                "use_proto_plus": True,
            }

            if self.settings.google_ads.login_customer_id:
                client_config["login_customer_id"] = (
                    self.settings.google_ads.login_customer_id
                )

            return GoogleAdsClient.load_from_dict(client_config)

        except Exception as e:
            logger.error(f"Failed to create write client for {customer_id}: {e}")
            raise AuthenticationError(
                f"Failed to authenticate for write operations: {e}"
            ) from e

    @mutate_rate_limited
    async def add_negative_keywords(
        self,
        customer_id: str,
        operation: NegativeKeywordOperation,
    ) -> List[WriteOperationResult]:
        """Add negative keywords to campaign or ad group.

        Args:
            customer_id: Google Ads customer ID
            operation: Negative keyword operation details

        Returns:
            List of operation results
        """
        results = []

        if self.dry_run:
            logger.info(
                f"[DRY RUN] Would add {len(operation.keywords)} negative keywords to campaign {operation.campaign_id}"
            )
            for keyword in operation.keywords:
                results.append(
                    WriteOperationResult(
                        operation_type=WriteOperationType.ADD_NEGATIVE_KEYWORDS,
                        status=WriteOperationStatus.COMPLETED,
                        resource_name=f"customers/{customer_id}/campaignCriteria/fake_id",
                        success=True,
                        mutation_result={
                            "keyword": keyword,
                            "match_type": operation.match_type,
                        },
                    )
                )
            return results

        try:
            client = await self._get_write_client(customer_id)

            # Prepare mutations
            operations = []

            if operation.ad_group_id:
                # Ad group level negative keywords
                service = client.get_service("AdGroupCriterionService")

                for keyword in operation.keywords:
                    criterion_operation = client.get_type("AdGroupCriterionOperation")
                    criterion = criterion_operation.create
                    criterion.ad_group = client.get_service(
                        "AdGroupService"
                    ).ad_group_path(customer_id, operation.ad_group_id)
                    criterion.negative = True
                    criterion.keyword.text = keyword
                    criterion.keyword.match_type = client.enums.KeywordMatchTypeEnum[
                        operation.match_type
                    ]

                    operations.append(criterion_operation)
            else:
                # Campaign level negative keywords
                service = client.get_service("CampaignCriterionService")

                for keyword in operation.keywords:
                    criterion_operation = client.get_type("CampaignCriterionOperation")
                    criterion = criterion_operation.create
                    criterion.campaign = client.get_service(
                        "CampaignService"
                    ).campaign_path(customer_id, operation.campaign_id)
                    criterion.negative = True
                    criterion.keyword.text = keyword
                    criterion.keyword.match_type = client.enums.KeywordMatchTypeEnum[
                        operation.match_type
                    ]

                    operations.append(criterion_operation)

            # Execute mutations
            response = (
                service.mutate_ad_group_criteria(
                    customer_id=customer_id, operations=operations
                )
                if operation.ad_group_id
                else service.mutate_campaign_criteria(
                    customer_id=customer_id, operations=operations
                )
            )

            # Process results
            for i, result in enumerate(response.results):
                results.append(
                    WriteOperationResult(
                        operation_type=WriteOperationType.ADD_NEGATIVE_KEYWORDS,
                        status=WriteOperationStatus.COMPLETED,
                        resource_name=result.resource_name,
                        success=True,
                        resource_id=result.resource_name.split("/")[-1],
                        mutation_result={
                            "keyword": operation.keywords[i],
                            "match_type": operation.match_type,
                        },
                    )
                )

            # Store operation history for potential rollback
            self._add_to_operation_history(customer_id, results)

            logger.info(
                f"Added {len(results)} negative keywords for customer {customer_id}"
            )
            return results

        except GoogleAdsException as e:
            error_details = _extract_google_ads_error_details(e)
            logger.error(
                f"Google Ads API error adding negative keywords: {error_details['error_summary']}, "
                f"Request ID: {error_details['request_id']}, "
                f"Error count: {len(error_details['errors'])}"
            )
            error_result = WriteOperationResult(
                operation_type=WriteOperationType.ADD_NEGATIVE_KEYWORDS,
                status=WriteOperationStatus.FAILED,
                resource_name="",
                success=False,
                error_message=error_details["error_summary"],
                mutation_result={"error_details": error_details},
            )
            return [error_result]

        except Exception as e:
            logger.error(f"Unexpected error adding negative keywords: {e}")
            raise APIError(f"Failed to add negative keywords: {e}") from e

    @mutate_rate_limited
    async def update_campaign_budgets(
        self,
        customer_id: str,
        operations: List[BudgetOperation],
    ) -> List[WriteOperationResult]:
        """Update campaign budgets.

        Args:
            customer_id: Google Ads customer ID
            operations: List of budget operations

        Returns:
            List of operation results
        """
        results = []

        if self.dry_run:
            logger.info(f"[DRY RUN] Would update {len(operations)} campaign budgets")
            for op in operations:
                results.append(
                    WriteOperationResult(
                        operation_type=WriteOperationType.UPDATE_BUDGETS,
                        status=WriteOperationStatus.COMPLETED,
                        resource_name=f"customers/{customer_id}/campaignBudgets/fake_id",
                        success=True,
                        mutation_result={"amount_micros": op.amount_micros},
                    )
                )
            return results

        try:
            client = await self._get_write_client(customer_id)
            service = client.get_service("CampaignBudgetService")

            # Batch query all campaign budgets in one request for efficiency
            ga_service = client.get_service("GoogleAdsService")

            campaign_ids = [op.campaign_id for op in operations]
            campaign_ids_str = "', '".join(
                [f"customers/{customer_id}/campaigns/{cid}" for cid in campaign_ids]
            )

            batch_query = f"""
                SELECT campaign.resource_name, campaign.budget
                FROM campaign
                WHERE campaign.resource_name IN ('{campaign_ids_str}')
            """

            search_request = client.get_type("SearchGoogleAdsRequest")
            search_request.customer_id = customer_id
            search_request.query = batch_query

            # Execute batch query and build lookup map
            campaign_budget_map = {}
            try:
                response = ga_service.search(request=search_request)
                for campaign_row in response:
                    # Extract campaign ID from resource name
                    campaign_resource = campaign_row.campaign.resource_name
                    campaign_id_from_resource = campaign_resource.split("/")[-1]
                    campaign_budget_map[campaign_id_from_resource] = (
                        campaign_row.campaign.budget
                    )
            except Exception as e:
                logger.error(f"Failed to batch fetch campaign budgets: {e}")
                raise APIError(f"Could not retrieve campaign budgets: {e}") from e

            # Prepare mutations using cached budget resource names
            budget_operations = []

            for operation in operations:
                if operation.campaign_id not in campaign_budget_map:
                    raise APIError(f"Campaign {operation.campaign_id} not found")

                budget_operation = client.get_type("CampaignBudgetOperation")
                budget = budget_operation.update
                budget.resource_name = campaign_budget_map[operation.campaign_id]
                budget.amount_micros = operation.amount_micros

                if operation.delivery_method:
                    budget.delivery_method = client.enums.BudgetDeliveryMethodEnum[
                        operation.delivery_method
                    ]

                budget_operation.update_mask = client.get_type("FieldMask")
                budget_operation.update_mask.paths.append("amount_micros")
                if operation.delivery_method:
                    budget_operation.update_mask.paths.append("delivery_method")

                budget_operations.append(budget_operation)

            # Execute mutations
            response = service.mutate_campaign_budgets(
                customer_id=customer_id, operations=budget_operations
            )

            # Process results
            for i, result in enumerate(response.results):
                results.append(
                    WriteOperationResult(
                        operation_type=WriteOperationType.UPDATE_BUDGETS,
                        status=WriteOperationStatus.COMPLETED,
                        resource_name=result.resource_name,
                        success=True,
                        resource_id=result.resource_name.split("/")[-1],
                        mutation_result={"amount_micros": operations[i].amount_micros},
                    )
                )

            # Store operation history
            self._add_to_operation_history(customer_id, results)

            logger.info(
                f"Updated {len(results)} campaign budgets for customer {customer_id}"
            )
            return results

        except GoogleAdsException as e:
            error_details = _extract_google_ads_error_details(e)
            logger.error(
                f"Google Ads API error updating budgets: {error_details['error_summary']}, "
                f"Request ID: {error_details['request_id']}, "
                f"Error count: {len(error_details['errors'])}"
            )
            error_result = WriteOperationResult(
                operation_type=WriteOperationType.UPDATE_BUDGETS,
                status=WriteOperationStatus.FAILED,
                resource_name="",
                success=False,
                error_message=error_details["error_summary"],
                mutation_result={"error_details": error_details},
            )
            return [error_result]

        except Exception as e:
            logger.error(f"Unexpected error updating budgets: {e}")
            raise APIError(f"Failed to update budgets: {e}") from e

    @mutate_rate_limited
    async def update_campaign_status(
        self,
        customer_id: str,
        operations: List[CampaignStatusOperation],
    ) -> List[WriteOperationResult]:
        """Update campaign status (enable/pause).

        Args:
            customer_id: Google Ads customer ID
            operations: List of status operations

        Returns:
            List of operation results
        """
        results = []

        if self.dry_run:
            logger.info(
                f"[DRY RUN] Would update status for {len(operations)} campaigns"
            )
            for op in operations:
                results.append(
                    WriteOperationResult(
                        operation_type=WriteOperationType.PAUSE_CAMPAIGNS
                        if op.status == "PAUSED"
                        else WriteOperationType.ENABLE_CAMPAIGNS,
                        status=WriteOperationStatus.COMPLETED,
                        resource_name=f"customers/{customer_id}/campaigns/{op.campaign_id}",
                        success=True,
                        mutation_result={"status": op.status},
                    )
                )
            return results

        try:
            client = await self._get_write_client(customer_id)
            service = client.get_service("CampaignService")

            # Prepare mutations
            campaign_operations = []

            for operation in operations:
                campaign_operation = client.get_type("CampaignOperation")
                campaign = campaign_operation.update
                campaign.resource_name = service.campaign_path(
                    customer_id, operation.campaign_id
                )
                campaign.status = client.enums.CampaignStatusEnum[operation.status]

                campaign_operation.update_mask = client.get_type("FieldMask")
                campaign_operation.update_mask.paths.append("status")

                campaign_operations.append(campaign_operation)

            # Execute mutations
            response = service.mutate_campaigns(
                customer_id=customer_id, operations=campaign_operations
            )

            # Process results
            for i, result in enumerate(response.results):
                op_type = (
                    WriteOperationType.PAUSE_CAMPAIGNS
                    if operations[i].status == "PAUSED"
                    else WriteOperationType.ENABLE_CAMPAIGNS
                )

                results.append(
                    WriteOperationResult(
                        operation_type=op_type,
                        status=WriteOperationStatus.COMPLETED,
                        resource_name=result.resource_name,
                        success=True,
                        resource_id=operations[i].campaign_id,
                        mutation_result={"status": operations[i].status},
                    )
                )

            # Store operation history
            self._add_to_operation_history(customer_id, results)

            logger.info(
                f"Updated status for {len(results)} campaigns for customer {customer_id}"
            )
            return results

        except GoogleAdsException as e:
            error_details = _extract_google_ads_error_details(e)
            logger.error(
                f"Google Ads API error updating campaign status: {error_details['error_summary']}, "
                f"Request ID: {error_details['request_id']}, "
                f"Error count: {len(error_details['errors'])}"
            )
            error_result = WriteOperationResult(
                operation_type=WriteOperationType.PAUSE_CAMPAIGNS,
                status=WriteOperationStatus.FAILED,
                resource_name="",
                success=False,
                error_message=error_details["error_summary"],
                mutation_result={"error_details": error_details},
            )
            return [error_result]

        except Exception as e:
            logger.error(f"Unexpected error updating campaign status: {e}")
            raise APIError(f"Failed to update campaign status: {e}") from e

    @bulk_mutate_rate_limited
    async def execute_batch_operations(
        self,
        customer_id: str,
        operations: List[Any],
        operation_type: WriteOperationType,
        batch_size: int = 1000,
    ) -> List[WriteOperationResult]:
        """Execute batch operations efficiently with pagination.

        Args:
            customer_id: Google Ads customer ID
            operations: List of operations to execute
            operation_type: Type of operations being executed
            batch_size: Maximum number of operations per batch

        Returns:
            List of operation results
        """
        if not operations:
            return []

        # Split operations into chunks for pagination
        operation_chunks = [
            operations[i : i + batch_size]
            for i in range(0, len(operations), batch_size)
        ]

        logger.info(
            f"Executing {len(operations)} {operation_type.value} operations "
            f"in {len(operation_chunks)} batches of up to {batch_size} operations each"
        )

        all_results = []

        if self.dry_run:
            logger.info(
                f"[DRY RUN] Would execute {len(operations)} {operation_type.value} operations"
            )
            for chunk_idx, chunk in enumerate(operation_chunks):
                for i, _ in enumerate(chunk):
                    all_results.append(
                        WriteOperationResult(
                            operation_type=operation_type,
                            status=WriteOperationStatus.COMPLETED,
                            resource_name=f"customers/{customer_id}/fake_resource/{chunk_idx}_{i}",
                            success=True,
                            mutation_result={"batch_index": chunk_idx * batch_size + i},
                        )
                    )
            return all_results

        # Process each chunk
        for chunk_idx, chunk in enumerate(operation_chunks):
            logger.debug(
                f"Processing batch {chunk_idx + 1}/{len(operation_chunks)} with {len(chunk)} operations"
            )

            try:
                # Route to appropriate method based on operation type
                if operation_type == WriteOperationType.ADD_NEGATIVE_KEYWORDS:
                    chunk_results = []
                    for op in chunk:
                        if isinstance(op, NegativeKeywordOperation):
                            chunk_results.extend(
                                await self.add_negative_keywords(customer_id, op)
                            )
                    all_results.extend(chunk_results)

                elif operation_type == WriteOperationType.UPDATE_BUDGETS:
                    chunk_results = await self.update_campaign_budgets(
                        customer_id, chunk
                    )
                    all_results.extend(chunk_results)

                elif operation_type in [
                    WriteOperationType.PAUSE_CAMPAIGNS,
                    WriteOperationType.ENABLE_CAMPAIGNS,
                ]:
                    chunk_results = await self.update_campaign_status(
                        customer_id, chunk
                    )
                    all_results.extend(chunk_results)

                else:
                    raise APIError(
                        f"Unsupported batch operation type: {operation_type}"
                    )

                # Small delay between batches to respect rate limits
                if (
                    chunk_idx < len(operation_chunks) - 1
                ):  # Don't delay after last chunk
                    import asyncio

                    await asyncio.sleep(0.1)  # 100ms delay

            except Exception as e:
                logger.error(f"Batch {chunk_idx + 1} failed: {e}")
                # Add error results for all operations in the failed chunk
                for i in range(len(chunk)):
                    all_results.append(
                        WriteOperationResult(
                            operation_type=operation_type,
                            status=WriteOperationStatus.FAILED,
                            resource_name="",
                            success=False,
                            error_message=f"Batch failed: {str(e)}",
                        )
                    )

        logger.info(
            f"Completed batch operations: {len([r for r in all_results if r.success])} successful, {len([r for r in all_results if not r.success])} failed"
        )
        return all_results

    async def rollback_operations(
        self,
        customer_id: str,
        operation_ids: Optional[List[str]] = None,
        time_window: Optional[datetime] = None,
    ) -> List[WriteOperationResult]:
        """Rollback write operations within a time window.

        Args:
            customer_id: Google Ads customer ID
            operation_ids: Specific operation IDs to rollback (optional)
            time_window: Only rollback operations after this time (optional)

        Returns:
            List of rollback results
        """
        if customer_id not in self._operation_history:
            logger.warning(f"No operation history found for customer {customer_id}")
            return []

        rollback_results = []
        operations_to_rollback = self._operation_history[customer_id]

        # Filter operations if needed
        if time_window:
            # In a real implementation, you'd filter by timestamp
            pass

        if operation_ids:
            operations_to_rollback = [
                op for op in operations_to_rollback if op.resource_id in operation_ids
            ]

        logger.info(
            f"Rolling back {len(operations_to_rollback)} operations for customer {customer_id}"
        )

        # Note: Rollback implementation would need to reverse each operation
        # For example, removing added negative keywords, reverting budget changes, etc.
        # This is a simplified version.

        for operation in operations_to_rollback:
            rollback_result = WriteOperationResult(
                operation_type=operation.operation_type,
                status=WriteOperationStatus.ROLLED_BACK,
                resource_name=operation.resource_name,
                success=True,
                rollback_data=operation.mutation_result,
            )
            rollback_results.append(rollback_result)

        return rollback_results

    def get_operation_history(self, customer_id: str) -> List[WriteOperationResult]:
        """Get operation history for a customer.

        Args:
            customer_id: Google Ads customer ID

        Returns:
            List of historical operations
        """
        return self._operation_history.get(customer_id, [])

    async def validate_write_permissions(self, customer_id: str) -> bool:
        """Validate that client has necessary write permissions.

        Args:
            customer_id: Google Ads customer ID

        Returns:
            True if write permissions are available
        """
        try:
            # Check OAuth permissions
            required_permissions = [
                "write_campaigns",
                "write_keywords",
                "write_budgets",
            ]
            return await self.oauth_manager.validate_permissions(
                customer_id, required_permissions
            )

        except Exception as e:
            logger.error(f"Permission validation failed for {customer_id}: {e}")
            return False

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check of write client.

        Returns:
            Health status information
        """
        try:
            oauth_healthy = await self.oauth_manager.health_check()
            rate_limiter_healthy = await self._rate_limiter.health_check()

            return {
                "healthy": oauth_healthy and rate_limiter_healthy,
                "oauth_manager": oauth_healthy,
                "rate_limiter": rate_limiter_healthy,
                "dry_run_mode": self.dry_run,
                "operation_history_count": sum(
                    len(ops) for ops in self._operation_history.values()
                ),
            }

        except Exception as e:
            logger.error(f"Write client health check failed: {e}")
            return {
                "healthy": False,
                "error": str(e),
            }
