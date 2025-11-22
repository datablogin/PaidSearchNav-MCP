"""Tests for Google Ads Write Client."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from google.ads.googleads.errors import GoogleAdsException

from paidsearchnav.auth.oauth_manager import OAuth2Manager, WorkflowTokenData
from paidsearchnav.core.config import GoogleAdsConfig, Settings
from paidsearchnav.core.exceptions import APIError, AuthenticationError
from paidsearchnav.integrations.google_ads_write_client import (
    BudgetOperation,
    CampaignStatusOperation,
    GoogleAdsWriteClient,
    NegativeKeywordOperation,
    WriteOperationResult,
    WriteOperationStatus,
    WriteOperationType,
)


@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    google_ads = GoogleAdsConfig(
        developer_token="test_dev_token",
        client_id="test_client_id",
        client_secret="test_client_secret",
    )
    return Settings(google_ads=google_ads)


@pytest.fixture
def mock_oauth_manager():
    """Create mock OAuth manager."""
    return AsyncMock(spec=OAuth2Manager)


@pytest.fixture
def mock_workflow_tokens():
    """Create mock workflow tokens."""
    return WorkflowTokenData(
        customer_id="1234567890",
        access_token="test_access_token",
        refresh_token="test_refresh_token",
        client_id="test_client_id",
        client_secret="test_client_secret",
    )


@pytest.fixture
def write_client(mock_settings, mock_oauth_manager):
    """Create Google Ads write client for testing."""
    with patch(
        "paidsearchnav.integrations.google_ads_write_client.GoogleAdsRateLimiter"
    ):
        return GoogleAdsWriteClient(
            settings=mock_settings,
            oauth_manager=mock_oauth_manager,
            dry_run=False,
        )


@pytest.fixture
def dry_run_client(mock_settings, mock_oauth_manager):
    """Create dry-run write client for testing."""
    with patch(
        "paidsearchnav.integrations.google_ads_write_client.GoogleAdsRateLimiter"
    ):
        return GoogleAdsWriteClient(
            settings=mock_settings,
            oauth_manager=mock_oauth_manager,
            dry_run=True,
        )


class TestGoogleAdsWriteClient:
    """Test GoogleAdsWriteClient functionality."""

    async def test_get_write_client_success(
        self, write_client, mock_oauth_manager, mock_workflow_tokens
    ):
        """Test successful write client creation."""
        customer_id = "1234567890"
        mock_oauth_manager.get_workflow_credentials.return_value = mock_workflow_tokens

        with patch("google.ads.googleads.client.GoogleAdsClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.load_from_dict.return_value = mock_client

            client = await write_client._get_write_client(customer_id)

            assert client == mock_client
            mock_oauth_manager.get_workflow_credentials.assert_called_once_with(
                customer_id
            )

    async def test_get_write_client_auth_failure(
        self, write_client, mock_oauth_manager
    ):
        """Test write client creation with authentication failure."""
        customer_id = "1234567890"
        mock_oauth_manager.get_workflow_credentials.side_effect = Exception(
            "Auth failed"
        )

        with pytest.raises(
            AuthenticationError, match="Failed to authenticate for write operations"
        ):
            await write_client._get_write_client(customer_id)

    async def test_add_negative_keywords_dry_run(self, dry_run_client):
        """Test adding negative keywords in dry-run mode."""
        customer_id = "1234567890"
        operation = NegativeKeywordOperation(
            campaign_id="111", keywords=["free", "cheap"], match_type="BROAD"
        )

        results = await dry_run_client.add_negative_keywords(customer_id, operation)

        assert len(results) == 2
        for result in results:
            assert isinstance(result, WriteOperationResult)
            assert result.operation_type == WriteOperationType.ADD_NEGATIVE_KEYWORDS
            assert result.status == WriteOperationStatus.COMPLETED
            assert result.success is True

    async def test_add_negative_keywords_success(
        self, write_client, mock_oauth_manager, mock_workflow_tokens
    ):
        """Test successful negative keyword addition."""
        customer_id = "1234567890"
        operation = NegativeKeywordOperation(
            campaign_id="111",
            keywords=["free", "cheap"],
        )

        mock_oauth_manager.get_workflow_credentials.return_value = mock_workflow_tokens

        with patch("google.ads.googleads.client.GoogleAdsClient") as mock_client_class:
            mock_client = MagicMock()
            mock_service = MagicMock()
            mock_client.get_service.return_value = mock_service
            mock_client.get_type.return_value = MagicMock()
            mock_client.enums.KeywordMatchTypeEnum = {"BROAD": "BROAD"}

            # Mock successful response
            mock_result = MagicMock()
            mock_result.resource_name = "customers/1234567890/campaignCriteria/123"
            mock_response = MagicMock()
            mock_response.results = [mock_result, mock_result]
            mock_service.mutate_campaign_criteria.return_value = mock_response

            mock_client_class.load_from_dict.return_value = mock_client

            results = await write_client.add_negative_keywords(customer_id, operation)

            assert len(results) == 2
            for result in results:
                assert result.success is True
                assert result.operation_type == WriteOperationType.ADD_NEGATIVE_KEYWORDS

    async def test_add_negative_keywords_api_error(
        self, write_client, mock_oauth_manager, mock_workflow_tokens
    ):
        """Test negative keyword addition with API error."""
        customer_id = "1234567890"
        operation = NegativeKeywordOperation(
            campaign_id="111",
            keywords=["free"],
        )

        mock_oauth_manager.get_workflow_credentials.return_value = mock_workflow_tokens

        with patch("google.ads.googleads.client.GoogleAdsClient") as mock_client_class:
            mock_client = MagicMock()
            mock_service = MagicMock()
            mock_client.get_service.return_value = mock_service
            mock_service.mutate_campaign_criteria.side_effect = GoogleAdsException(
                "API Error"
            )

            mock_client_class.load_from_dict.return_value = mock_client

            results = await write_client.add_negative_keywords(customer_id, operation)

            assert len(results) == 1
            assert results[0].success is False
            assert results[0].status == WriteOperationStatus.FAILED
            assert "API Error" in results[0].error_message

    async def test_update_campaign_budgets_dry_run(self, dry_run_client):
        """Test budget updates in dry-run mode."""
        customer_id = "1234567890"
        operations = [
            BudgetOperation(campaign_id="111", amount_micros=1000000),
            BudgetOperation(campaign_id="222", amount_micros=2000000),
        ]

        results = await dry_run_client.update_campaign_budgets(customer_id, operations)

        assert len(results) == 2
        for result in results:
            assert result.operation_type == WriteOperationType.UPDATE_BUDGETS
            assert result.success is True

    async def test_update_campaign_budgets_success(
        self, write_client, mock_oauth_manager, mock_workflow_tokens
    ):
        """Test successful budget updates."""
        customer_id = "1234567890"
        operations = [BudgetOperation(campaign_id="111", amount_micros=1000000)]

        mock_oauth_manager.get_workflow_credentials.return_value = mock_workflow_tokens

        with patch("google.ads.googleads.client.GoogleAdsClient") as mock_client_class:
            mock_client = MagicMock()
            mock_service = MagicMock()
            mock_client.get_service.return_value = mock_service

            # Mock successful response
            mock_result = MagicMock()
            mock_result.resource_name = "customers/1234567890/campaignBudgets/111"
            mock_response = MagicMock()
            mock_response.results = [mock_result]
            mock_service.mutate_campaign_budgets.return_value = mock_response

            mock_client_class.load_from_dict.return_value = mock_client

            results = await write_client.update_campaign_budgets(
                customer_id, operations
            )

            assert len(results) == 1
            assert results[0].success is True
            assert results[0].operation_type == WriteOperationType.UPDATE_BUDGETS

    async def test_update_campaign_status_dry_run(self, dry_run_client):
        """Test campaign status updates in dry-run mode."""
        customer_id = "1234567890"
        operations = [
            CampaignStatusOperation(campaign_id="111", status="PAUSED"),
            CampaignStatusOperation(campaign_id="222", status="ENABLED"),
        ]

        results = await dry_run_client.update_campaign_status(customer_id, operations)

        assert len(results) == 2
        assert results[0].operation_type == WriteOperationType.PAUSE_CAMPAIGNS
        assert results[1].operation_type == WriteOperationType.ENABLE_CAMPAIGNS
        for result in results:
            assert result.success is True

    async def test_update_campaign_status_success(
        self, write_client, mock_oauth_manager, mock_workflow_tokens
    ):
        """Test successful campaign status updates."""
        customer_id = "1234567890"
        operations = [CampaignStatusOperation(campaign_id="111", status="PAUSED")]

        mock_oauth_manager.get_workflow_credentials.return_value = mock_workflow_tokens

        with patch("google.ads.googleads.client.GoogleAdsClient") as mock_client_class:
            mock_client = MagicMock()
            mock_service = MagicMock()
            mock_client.get_service.return_value = mock_service
            mock_client.enums.CampaignStatusEnum = {"PAUSED": "PAUSED"}

            # Mock successful response
            mock_result = MagicMock()
            mock_result.resource_name = "customers/1234567890/campaigns/111"
            mock_response = MagicMock()
            mock_response.results = [mock_result]
            mock_service.mutate_campaigns.return_value = mock_response

            mock_client_class.load_from_dict.return_value = mock_client

            results = await write_client.update_campaign_status(customer_id, operations)

            assert len(results) == 1
            assert results[0].success is True
            assert results[0].operation_type == WriteOperationType.PAUSE_CAMPAIGNS

    async def test_execute_batch_operations_dry_run(self, dry_run_client):
        """Test batch operations in dry-run mode."""
        customer_id = "1234567890"
        operations = [MagicMock(), MagicMock()]
        operation_type = WriteOperationType.ADD_NEGATIVE_KEYWORDS

        results = await dry_run_client.execute_batch_operations(
            customer_id, operations, operation_type
        )

        assert len(results) == 2
        for result in results:
            assert result.operation_type == operation_type
            assert result.success is True

    async def test_execute_batch_operations_negative_keywords(self, write_client):
        """Test batch operations for negative keywords."""
        customer_id = "1234567890"
        operations = [
            NegativeKeywordOperation(campaign_id="111", keywords=["free"]),
            NegativeKeywordOperation(campaign_id="222", keywords=["cheap"]),
        ]
        operation_type = WriteOperationType.ADD_NEGATIVE_KEYWORDS

        with patch.object(write_client, "add_negative_keywords") as mock_method:
            mock_method.return_value = [
                WriteOperationResult(
                    operation_type=operation_type,
                    status=WriteOperationStatus.COMPLETED,
                    resource_name="test",
                    success=True,
                )
            ]

            results = await write_client.execute_batch_operations(
                customer_id, operations, operation_type
            )

            assert len(results) == 2  # Two operations, each returns one result
            assert mock_method.call_count == 2

    async def test_execute_batch_operations_unsupported_type(self, write_client):
        """Test batch operations with unsupported operation type."""
        customer_id = "1234567890"
        operations = [MagicMock()]
        operation_type = WriteOperationType.UPDATE_SHARED_SETS  # Not implemented

        with pytest.raises(APIError, match="Unsupported batch operation type"):
            await write_client.execute_batch_operations(
                customer_id, operations, operation_type
            )

    async def test_rollback_operations_no_history(self, write_client):
        """Test rollback with no operation history."""
        customer_id = "1234567890"

        results = await write_client.rollback_operations(customer_id)

        assert len(results) == 0

    async def test_rollback_operations_success(self, write_client):
        """Test successful operation rollback."""
        customer_id = "1234567890"

        # Add some operation history
        operation_result = WriteOperationResult(
            operation_type=WriteOperationType.ADD_NEGATIVE_KEYWORDS,
            status=WriteOperationStatus.COMPLETED,
            resource_name="test_resource",
            success=True,
            resource_id="123",
            mutation_result={"keyword": "free"},
        )
        write_client._operation_history[customer_id] = [operation_result]

        results = await write_client.rollback_operations(customer_id)

        assert len(results) == 1
        assert results[0].status == WriteOperationStatus.ROLLED_BACK

    def test_get_operation_history(self, write_client):
        """Test getting operation history."""
        customer_id = "1234567890"

        # Initially empty
        history = write_client.get_operation_history(customer_id)
        assert len(history) == 0

        # Add some history
        operation_result = WriteOperationResult(
            operation_type=WriteOperationType.ADD_NEGATIVE_KEYWORDS,
            status=WriteOperationStatus.COMPLETED,
            resource_name="test",
            success=True,
        )
        write_client._operation_history[customer_id] = [operation_result]

        history = write_client.get_operation_history(customer_id)
        assert len(history) == 1
        assert history[0] == operation_result

    async def test_validate_write_permissions_success(
        self, write_client, mock_oauth_manager
    ):
        """Test successful write permission validation."""
        customer_id = "1234567890"
        mock_oauth_manager.validate_permissions.return_value = True

        result = await write_client.validate_write_permissions(customer_id)

        assert result is True
        mock_oauth_manager.validate_permissions.assert_called_once()

    async def test_validate_write_permissions_failure(
        self, write_client, mock_oauth_manager
    ):
        """Test write permission validation failure."""
        customer_id = "1234567890"
        mock_oauth_manager.validate_permissions.side_effect = Exception(
            "Permission check failed"
        )

        result = await write_client.validate_write_permissions(customer_id)

        assert result is False

    async def test_health_check_success(self, write_client, mock_oauth_manager):
        """Test successful health check."""
        mock_oauth_manager.health_check.return_value = True

        with patch.object(
            write_client._rate_limiter, "health_check", return_value=True
        ):
            result = await write_client.health_check()

            assert result["healthy"] is True
            assert "oauth_manager" in result
            assert "rate_limiter" in result
            assert "dry_run_mode" in result

    async def test_health_check_failure(self, write_client, mock_oauth_manager):
        """Test health check failure."""
        mock_oauth_manager.health_check.side_effect = Exception("Health check failed")

        result = await write_client.health_check()

        assert result["healthy"] is False
        assert "error" in result


class TestWriteOperationModels:
    """Test write operation data models."""

    def test_negative_keyword_operation(self):
        """Test NegativeKeywordOperation model."""
        operation = NegativeKeywordOperation(
            campaign_id="111", keywords=["free", "cheap"], match_type="EXACT"
        )

        assert operation.campaign_id == "111"
        assert operation.keywords == ["free", "cheap"]
        assert operation.match_type == "EXACT"
        assert operation.ad_group_id is None

    def test_budget_operation(self):
        """Test BudgetOperation model."""
        operation = BudgetOperation(
            campaign_id="111", amount_micros=1000000, delivery_method="STANDARD"
        )

        assert operation.campaign_id == "111"
        assert operation.amount_micros == 1000000
        assert operation.delivery_method == "STANDARD"

    def test_campaign_status_operation(self):
        """Test CampaignStatusOperation model."""
        operation = CampaignStatusOperation(campaign_id="111", status="PAUSED")

        assert operation.campaign_id == "111"
        assert operation.status == "PAUSED"


class TestWriteOperationResult:
    """Test WriteOperationResult data class."""

    def test_write_operation_result_creation(self):
        """Test WriteOperationResult creation."""
        result = WriteOperationResult(
            operation_type=WriteOperationType.ADD_NEGATIVE_KEYWORDS,
            status=WriteOperationStatus.COMPLETED,
            resource_name="customers/123/criteria/456",
            success=True,
            resource_id="456",
            mutation_result={"keyword": "free"},
        )

        assert result.operation_type == WriteOperationType.ADD_NEGATIVE_KEYWORDS
        assert result.status == WriteOperationStatus.COMPLETED
        assert result.resource_name == "customers/123/criteria/456"
        assert result.success is True
        assert result.resource_id == "456"
        assert result.mutation_result == {"keyword": "free"}
