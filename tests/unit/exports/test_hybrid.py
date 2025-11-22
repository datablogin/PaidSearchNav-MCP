"""Tests for hybrid export manager."""

from unittest.mock import patch

import pytest

from paidsearchnav.core.config import BigQueryConfig, BigQueryTier
from paidsearchnav.exports.base import (
    ExportFormat,
    ExportRequest,
    ExportResult,
    ExportStatus,
)
from paidsearchnav.exports.hybrid import (
    CustomerTier,
    HybridExportConfig,
    HybridExportManager,
)


class TestCustomerTier:
    """Test customer tier constants."""

    def test_tier_constants(self):
        """Test that tier constants are properly defined."""
        assert CustomerTier.STANDARD == "standard"
        assert CustomerTier.PREMIUM == "premium"
        assert CustomerTier.ENTERPRISE == "enterprise"


class TestHybridExportConfig:
    """Test hybrid export configuration."""

    def test_default_config(self):
        """Test default configuration values."""
        config = HybridExportConfig()

        assert config.customer_tier == CustomerTier.STANDARD
        assert config.output_mode == "auto"
        assert config.bigquery_enabled is False
        assert config.fallback_to_csv is True
        assert config.cost_tracking_enabled is True
        assert config.max_cost_per_export_usd == 10.0

    def test_should_export_to_csv_modes(self):
        """Test CSV export determination for different modes."""
        # CSV mode
        config = HybridExportConfig(output_mode="csv")
        assert config.should_export_to_csv() is True

        # BigQuery mode
        config = HybridExportConfig(output_mode="bigquery")
        assert config.should_export_to_csv() is False

        # Both mode
        config = HybridExportConfig(output_mode="both")
        assert config.should_export_to_csv() is True

        # Auto mode (default)
        config = HybridExportConfig(output_mode="auto")
        assert config.should_export_to_csv() is True

    def test_should_export_to_bigquery_modes(self):
        """Test BigQuery export determination for different modes and tiers."""
        # BigQuery disabled
        config = HybridExportConfig(bigquery_enabled=False)
        assert config.should_export_to_bigquery() is False

        # Standard tier with BigQuery enabled
        config = HybridExportConfig(
            customer_tier=CustomerTier.STANDARD, bigquery_enabled=True
        )
        assert config.should_export_to_bigquery() is False

        # Premium tier with CSV mode
        config = HybridExportConfig(
            customer_tier=CustomerTier.PREMIUM, bigquery_enabled=True, output_mode="csv"
        )
        assert config.should_export_to_bigquery() is False

        # Premium tier with BigQuery mode
        config = HybridExportConfig(
            customer_tier=CustomerTier.PREMIUM,
            bigquery_enabled=True,
            output_mode="bigquery",
        )
        assert config.should_export_to_bigquery() is True

        # Enterprise tier with auto mode
        config = HybridExportConfig(
            customer_tier=CustomerTier.ENTERPRISE,
            bigquery_enabled=True,
            output_mode="auto",
        )
        assert config.should_export_to_bigquery() is True


class TestHybridExportManager:
    """Test hybrid export manager functionality."""

    @pytest.fixture
    def manager(self):
        """Create a hybrid export manager for testing."""
        return HybridExportManager()

    @pytest.fixture
    def sample_data(self):
        """Sample data for testing exports."""
        return {
            "search_terms": [
                {
                    "campaign": "Test Campaign",
                    "search_term": "test keyword",
                    "clicks": 10,
                    "cost": 5.50,
                }
            ],
            "keywords": [
                {
                    "campaign": "Test Campaign",
                    "keyword": "test keyword",
                    "clicks": 15,
                    "cost": 7.25,
                }
            ],
        }

    @pytest.fixture
    def bigquery_config(self):
        """Create a test BigQuery configuration."""
        return BigQueryConfig(
            enabled=True,
            tier=BigQueryTier.PREMIUM,
            project_id="test-project",
            dataset_id="test_dataset",
        )

    def test_get_customer_tier_defaults(self, manager):
        """Test customer tier detection with defaults."""
        # Unknown customer should default to standard
        tier = manager.get_customer_tier("9999999999")
        assert tier == CustomerTier.STANDARD

        # Known premium customer
        tier = manager.get_customer_tier("1234567890")
        assert tier == CustomerTier.PREMIUM

        # Known enterprise customer
        tier = manager.get_customer_tier("0987654321")
        assert tier == CustomerTier.ENTERPRISE

    def test_get_hybrid_config_standard_tier(self, manager):
        """Test hybrid configuration for standard tier customer."""
        config = manager.get_hybrid_config("9999999999")

        assert config.customer_tier == CustomerTier.STANDARD
        assert config.output_mode == "csv"
        assert config.bigquery_enabled is False

    def test_get_hybrid_config_premium_tier_with_bigquery(
        self, manager, bigquery_config
    ):
        """Test hybrid configuration for premium tier with BigQuery enabled."""
        config = manager.get_hybrid_config("1234567890", bigquery_config)

        assert config.customer_tier == CustomerTier.PREMIUM
        assert config.output_mode == "both"
        assert config.bigquery_enabled is True

    def test_get_hybrid_config_premium_tier_without_bigquery(self, manager):
        """Test hybrid configuration for premium tier without BigQuery."""
        bigquery_config = BigQueryConfig(enabled=False)
        config = manager.get_hybrid_config("1234567890", bigquery_config)

        assert config.customer_tier == CustomerTier.PREMIUM
        assert config.bigquery_enabled is False

    @pytest.mark.asyncio
    async def test_check_cost_limits_within_limit(self, manager):
        """Test cost limit checking when within limits."""
        customer_id = "test_customer"
        hybrid_config = HybridExportConfig(max_cost_per_export_usd=10.0)

        # No prior costs
        result = await manager._check_cost_limits(customer_id, hybrid_config)
        assert result is True

        # Set some cost below limit
        manager.cost_tracker[customer_id] = 5.0
        result = await manager._check_cost_limits(customer_id, hybrid_config)
        assert result is True

    @pytest.mark.asyncio
    async def test_check_cost_limits_exceeds_limit(self, manager):
        """Test cost limit checking when exceeding limits."""
        customer_id = "test_customer"
        hybrid_config = HybridExportConfig(max_cost_per_export_usd=10.0)

        # Set cost above limit
        manager.cost_tracker[customer_id] = 15.0
        result = await manager._check_cost_limits(customer_id, hybrid_config)
        assert result is False

    @pytest.mark.asyncio
    async def test_track_export_cost(self, manager):
        """Test export cost tracking."""
        customer_id = "test_customer"
        export_result = ExportResult(
            export_id="test-export",
            status=ExportStatus.COMPLETED,
            destination=ExportFormat.BIGQUERY,
            records_exported=1000,
        )

        # Track cost
        await manager._track_export_cost(customer_id, export_result)

        # Cost should be calculated based on records (1000 * 0.001 = 1.0)
        assert manager.cost_tracker[customer_id] == 1.0

        # Track another cost
        await manager._track_export_cost(customer_id, export_result)
        assert manager.cost_tracker[customer_id] == 2.0

    def test_get_customer_cost_usage(self, manager):
        """Test getting customer cost usage information."""
        customer_id = "test_customer"
        manager.cost_tracker[customer_id] = 5.0

        usage = manager.get_customer_cost_usage(customer_id)

        assert usage["customer_id"] == customer_id
        assert usage["current_cost_usd"] == 5.0
        # Standard tier gets 10.0, but enterprise tier gets 25.0
        # Let's check the actual limit from the config
        hybrid_config = manager.get_hybrid_config(customer_id)
        expected_limit = hybrid_config.max_cost_per_export_usd
        assert usage["cost_limit_usd"] == expected_limit
        assert usage["cost_percentage"] == (5.0 / expected_limit) * 100
        assert usage["tier"] == CustomerTier.STANDARD

    def test_reset_customer_costs(self, manager):
        """Test resetting customer costs."""
        customer_id = "test_customer"
        manager.cost_tracker[customer_id] = 15.0

        manager.reset_customer_costs(customer_id)

        assert manager.cost_tracker[customer_id] == 0.0

    @pytest.mark.asyncio
    async def test_export_to_csv_success(self, manager, sample_data):
        """Test successful CSV export."""
        request = ExportRequest(customer_id="test_customer")

        result = await manager._export_to_csv(request, sample_data)

        assert result.status == ExportStatus.COMPLETED
        assert result.destination == ExportFormat.CSV
        assert result.records_exported == 2  # 1 search term + 1 keyword
        assert "files_created" in result.metadata
        assert len(result.metadata["files_created"]) == 2

    @pytest.mark.asyncio
    async def test_export_data_hybrid_standard_tier_csv_only(
        self, manager, sample_data
    ):
        """Test hybrid export for standard tier customer (CSV only)."""
        request = ExportRequest(customer_id="9999999999")  # Standard tier

        with patch.object(manager, "_export_to_csv") as mock_csv:
            mock_csv.return_value = ExportResult(
                export_id=request.export_id,
                status=ExportStatus.COMPLETED,
                destination=ExportFormat.CSV,
                records_exported=2,
            )

            results = await manager.export_data_hybrid(request, sample_data)

            assert len(results) == 1
            assert results[0].destination == ExportFormat.CSV
            assert results[0].status == ExportStatus.COMPLETED
            mock_csv.assert_called_once()

    @pytest.mark.asyncio
    async def test_export_data_hybrid_premium_tier_both_outputs(
        self, manager, sample_data, bigquery_config
    ):
        """Test hybrid export for premium tier customer (both CSV and BigQuery)."""
        request = ExportRequest(customer_id="1234567890")  # Premium tier

        with (
            patch.object(manager, "_export_to_csv") as mock_csv,
            patch.object(manager, "_export_to_bigquery") as mock_bq,
            patch.object(manager, "_check_cost_limits", return_value=True),
        ):
            mock_csv.return_value = ExportResult(
                export_id=request.export_id,
                status=ExportStatus.COMPLETED,
                destination=ExportFormat.CSV,
                records_exported=2,
            )

            mock_bq.return_value = ExportResult(
                export_id=request.export_id,
                status=ExportStatus.COMPLETED,
                destination=ExportFormat.BIGQUERY,
                records_exported=2,
            )

            results = await manager.export_data_hybrid(
                request, sample_data, bigquery_config
            )

            assert len(results) == 2
            destinations = [r.destination for r in results]
            assert ExportFormat.CSV in destinations
            assert ExportFormat.BIGQUERY in destinations

            mock_csv.assert_called_once()
            mock_bq.assert_called_once()

    @pytest.mark.asyncio
    async def test_export_data_hybrid_bigquery_failure_with_fallback(
        self, manager, sample_data, bigquery_config
    ):
        """Test BigQuery failure with CSV fallback."""
        request = ExportRequest(customer_id="1234567890")  # Premium tier

        with (
            patch.object(manager, "_export_to_csv") as mock_csv,
            patch.object(manager, "_export_to_bigquery") as mock_bq,
            patch.object(manager, "_check_cost_limits", return_value=True),
        ):
            # First CSV call succeeds
            mock_csv.return_value = ExportResult(
                export_id=request.export_id,
                status=ExportStatus.COMPLETED,
                destination=ExportFormat.CSV,
                records_exported=2,
            )

            # BigQuery fails
            mock_bq.return_value = ExportResult(
                export_id=request.export_id,
                status=ExportStatus.FAILED,
                destination=ExportFormat.BIGQUERY,
                error_message="BigQuery connection failed",
            )

            results = await manager.export_data_hybrid(
                request, sample_data, bigquery_config
            )

            # Should have CSV (success) and BigQuery (failed) results
            assert len(results) == 2
            csv_results = [r for r in results if r.destination == ExportFormat.CSV]
            bq_results = [r for r in results if r.destination == ExportFormat.BIGQUERY]

            assert len(csv_results) == 1
            assert len(bq_results) == 1
            assert csv_results[0].status == ExportStatus.COMPLETED
            assert bq_results[0].status == ExportStatus.FAILED

    @pytest.mark.asyncio
    async def test_export_data_hybrid_cost_limit_exceeded(
        self, manager, sample_data, bigquery_config
    ):
        """Test BigQuery export skipped due to cost limits."""
        request = ExportRequest(customer_id="1234567890")  # Premium tier

        with (
            patch.object(manager, "_export_to_csv") as mock_csv,
            patch.object(manager, "_check_cost_limits", return_value=False),
        ):
            mock_csv.return_value = ExportResult(
                export_id=request.export_id,
                status=ExportStatus.COMPLETED,
                destination=ExportFormat.CSV,
                records_exported=2,
            )

            results = await manager.export_data_hybrid(
                request, sample_data, bigquery_config
            )

            # Should have CSV and failed BigQuery (due to cost limit)
            assert len(results) == 2
            bq_results = [r for r in results if r.destination == ExportFormat.BIGQUERY]
            assert len(bq_results) == 1
            assert bq_results[0].status == ExportStatus.FAILED
            assert "cost limit exceeded" in bq_results[0].error_message
