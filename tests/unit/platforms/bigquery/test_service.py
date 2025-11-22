"""Tests for BigQuery service functionality."""

from paidsearchnav.core.config import BigQueryConfig, BigQueryTier
from paidsearchnav.platforms.bigquery.service import BigQueryService


class TestBigQueryService:
    """Test BigQuery service methods."""

    def test_service_initialization(self):
        """Test BigQuery service initializes correctly."""
        config = BigQueryConfig(
            enabled=True,
            tier=BigQueryTier.PREMIUM,
            project_id="test-project",
            dataset_id="test_dataset",
        )

        service = BigQueryService(config)

        assert service.config == config
        assert service.is_enabled is True
        assert service.is_premium is True
        assert service.is_enterprise is False

    def test_supports_advanced_analytics_premium(self):
        """Test advanced analytics support for premium tier."""
        config = BigQueryConfig(
            enabled=True,
            tier=BigQueryTier.PREMIUM,
            project_id="test-project",
            dataset_id="test_dataset",
        )

        service = BigQueryService(config)

        assert service.supports_advanced_analytics() is True

    def test_supports_advanced_analytics_enterprise(self):
        """Test advanced analytics support for enterprise tier."""
        config = BigQueryConfig(
            enabled=True,
            tier=BigQueryTier.ENTERPRISE,
            project_id="test-project",
            dataset_id="test_dataset",
        )

        service = BigQueryService(config)

        assert service.supports_advanced_analytics() is True

    def test_supports_advanced_analytics_standard(self):
        """Test advanced analytics support for standard tier."""
        config = BigQueryConfig(
            enabled=True,
            tier=BigQueryTier.STANDARD,
            project_id="test-project",
            dataset_id="test_dataset",
        )

        service = BigQueryService(config)

        assert service.supports_advanced_analytics() is False

    def test_supports_ml_models_enterprise_only(self):
        """Test ML models support only for enterprise tier."""
        # Enterprise tier
        config_enterprise = BigQueryConfig(
            enabled=True,
            tier=BigQueryTier.ENTERPRISE,
            project_id="test-project",
            dataset_id="test_dataset",
        )

        service_enterprise = BigQueryService(config_enterprise)
        assert service_enterprise.supports_ml_models() is True

        # Premium tier
        config_premium = BigQueryConfig(
            enabled=True,
            tier=BigQueryTier.PREMIUM,
            project_id="test-project",
            dataset_id="test_dataset",
        )

        service_premium = BigQueryService(config_premium)
        assert service_premium.supports_ml_models() is False

    def test_disabled_service(self):
        """Test disabled BigQuery service."""
        config = BigQueryConfig(
            enabled=False,
            tier=BigQueryTier.DISABLED,
            project_id="test-project",
            dataset_id="test_dataset",
        )

        service = BigQueryService(config)

        assert service.is_enabled is False
        assert service.supports_advanced_analytics() is False
        assert service.supports_ml_models() is False

    def test_tier_properties(self):
        """Test tier property checks."""
        # Standard tier
        config_standard = BigQueryConfig(
            enabled=True,
            tier=BigQueryTier.STANDARD,
            project_id="test-project",
            dataset_id="test_dataset",
        )

        service_standard = BigQueryService(config_standard)
        assert service_standard.is_premium is False
        assert service_standard.is_enterprise is False

        # Premium tier
        config_premium = BigQueryConfig(
            enabled=True,
            tier=BigQueryTier.PREMIUM,
            project_id="test-project",
            dataset_id="test_dataset",
        )

        service_premium = BigQueryService(config_premium)
        assert service_premium.is_premium is True
        assert service_premium.is_enterprise is False

        # Enterprise tier
        config_enterprise = BigQueryConfig(
            enabled=True,
            tier=BigQueryTier.ENTERPRISE,
            project_id="test-project",
            dataset_id="test_dataset",
        )

        service_enterprise = BigQueryService(config_enterprise)
        assert service_enterprise.is_premium is True
        assert service_enterprise.is_enterprise is True
