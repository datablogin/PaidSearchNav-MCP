"""Tests for premium API timeout integration."""

from unittest.mock import Mock, patch

import pytest
from google.cloud import bigquery

from paidsearchnav.api.v1.premium_utils import (
    get_customer_tier_from_service_tier,
    safe_execute_query,
)
from paidsearchnav.platforms.bigquery.timeout_config import CustomerTier


class TestPremiumTimeoutIntegration:
    """Test integration between premium utilities and timeout system."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock BigQuery client."""
        return Mock(spec=bigquery.Client)

    @pytest.fixture
    def sample_parameters(self):
        """Create sample query parameters."""
        return [
            bigquery.ScalarQueryParameter("customer_id", "STRING", "test_customer"),
            bigquery.ArrayQueryParameter(
                "campaign_ids", "STRING", ["campaign1", "campaign2"]
            ),
        ]

    def test_get_customer_tier_from_service_tier_mapping(self):
        """Test service tier to customer tier mapping."""
        assert get_customer_tier_from_service_tier("standard") == CustomerTier.STANDARD
        assert get_customer_tier_from_service_tier("premium") == CustomerTier.PREMIUM
        assert (
            get_customer_tier_from_service_tier("enterprise") == CustomerTier.ENTERPRISE
        )

        # Test case insensitivity
        assert get_customer_tier_from_service_tier("PREMIUM") == CustomerTier.PREMIUM
        assert (
            get_customer_tier_from_service_tier("Enterprise") == CustomerTier.ENTERPRISE
        )

        # Test default for unknown tiers
        assert get_customer_tier_from_service_tier("unknown") == CustomerTier.STANDARD

    def test_safe_execute_query_with_customer_tier(
        self, mock_client, sample_parameters
    ):
        """Test safe_execute_query with customer tier-based timeouts."""
        # Setup mock query job
        mock_job = Mock()
        mock_job.total_bytes_processed = 1024 * 1024  # 1 MB
        mock_client.query.return_value = mock_job

        # Execute query with premium tier
        result = safe_execute_query(
            mock_client,
            "SELECT * FROM test_table",
            sample_parameters,
            customer_tier=CustomerTier.PREMIUM,
        )

        # Verify result
        assert result == mock_job

        # Verify query was called twice (dry run + actual)
        assert mock_client.query.call_count == 2

        # Check that job config used premium timeout (5 minutes = 300000ms)
        actual_call_args = mock_client.query.call_args_list[
            1
        ]  # Second call is actual query
        job_config = actual_call_args[1]["job_config"]
        assert job_config.job_timeout_ms == 300000

    def test_safe_execute_query_with_enterprise_tier(
        self, mock_client, sample_parameters
    ):
        """Test safe_execute_query with enterprise tier for higher cost limit."""
        # Setup mock query job with higher cost
        mock_job = Mock()
        mock_job.total_bytes_processed = 1024**4 * 8  # 8 TB (would cost ~$40)
        mock_client.query.return_value = mock_job

        # Execute query with enterprise tier (should allow higher cost)
        result = safe_execute_query(
            mock_client,
            "SELECT * FROM large_table",
            sample_parameters,
            customer_tier=CustomerTier.ENTERPRISE,
        )

        # Should succeed because enterprise has $50 limit
        assert result == mock_job

    def test_safe_execute_query_cost_limit_exceeded_standard(
        self, mock_client, sample_parameters
    ):
        """Test cost limit exceeded for standard tier."""
        # Setup mock query job with high cost
        mock_job = Mock()
        mock_job.total_bytes_processed = 1024**4 * 3  # 3 TB (would cost ~$15)
        mock_client.query.return_value = mock_job

        # Execute query with standard tier (should fail due to $10 limit)
        with pytest.raises(Exception) as exc_info:
            safe_execute_query(
                mock_client,
                "SELECT * FROM expensive_table",
                sample_parameters,
                customer_tier=CustomerTier.STANDARD,
            )

        # Should mention cost limit in error
        assert "too expensive" in str(exc_info.value)

    def test_safe_execute_query_fallback_to_timeout_seconds(
        self, mock_client, sample_parameters
    ):
        """Test fallback to timeout_seconds when customer_tier not provided."""
        # Setup mock query job
        mock_job = Mock()
        mock_job.total_bytes_processed = 1024 * 1024  # 1 MB
        mock_client.query.return_value = mock_job

        # Execute query without customer tier (should use timeout_seconds)
        result = safe_execute_query(
            mock_client,
            "SELECT * FROM test_table",
            sample_parameters,
            timeout_seconds=120,  # 2 minutes
        )

        # Verify result
        assert result == mock_job

        # Check that job config used custom timeout (2 minutes = 120000ms)
        actual_call_args = mock_client.query.call_args_list[
            1
        ]  # Second call is actual query
        job_config = actual_call_args[1]["job_config"]
        assert job_config.job_timeout_ms == 120000

    def test_safe_execute_query_tier_precedence_over_timeout(
        self, mock_client, sample_parameters
    ):
        """Test that customer_tier takes precedence over timeout_seconds."""
        # Setup mock query job
        mock_job = Mock()
        mock_job.total_bytes_processed = 1024 * 1024  # 1 MB
        mock_client.query.return_value = mock_job

        # Execute query with both customer_tier and timeout_seconds
        result = safe_execute_query(
            mock_client,
            "SELECT * FROM test_table",
            sample_parameters,
            timeout_seconds=120,  # Should be ignored
            customer_tier=CustomerTier.ENTERPRISE,  # Should be used
        )

        # Verify result
        assert result == mock_job

        # Check that job config used enterprise timeout (10 minutes = 600000ms), not 120s
        actual_call_args = mock_client.query.call_args_list[
            1
        ]  # Second call is actual query
        job_config = actual_call_args[1]["job_config"]
        assert job_config.job_timeout_ms == 600000

    @patch("paidsearchnav.api.v1.premium_utils.get_timeout_config")
    def test_safe_execute_query_timeout_config_integration(
        self, mock_get_timeout_config, mock_client, sample_parameters
    ):
        """Test integration with timeout configuration system."""
        # Setup mock timeout config
        mock_config = Mock()
        mock_config.query_timeout = 900  # 15 minutes
        mock_get_timeout_config.return_value = mock_config

        # Setup mock query job
        mock_job = Mock()
        mock_job.total_bytes_processed = 1024 * 1024  # 1 MB
        mock_client.query.return_value = mock_job

        # Execute query
        result = safe_execute_query(
            mock_client,
            "SELECT * FROM test_table",
            sample_parameters,
            customer_tier=CustomerTier.PREMIUM,
        )

        # Verify timeout config was called with correct tier
        mock_get_timeout_config.assert_called_with(CustomerTier.PREMIUM)

        # Verify job config used the custom timeout
        actual_call_args = mock_client.query.call_args_list[1]
        job_config = actual_call_args[1]["job_config"]
        assert job_config.job_timeout_ms == 900000  # 15 minutes in ms


class TestRealWorldScenarios:
    """Test real-world usage scenarios."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock BigQuery client."""
        return Mock(spec=bigquery.Client)

    def test_premium_analytics_endpoint_simulation(self, mock_client):
        """Simulate a premium analytics endpoint using timeout system."""
        # Setup query parameters for premium analytics
        parameters = [
            bigquery.ScalarQueryParameter(
                "customer_id", "STRING", "premium_customer_123"
            ),
            bigquery.ScalarQueryParameter("start_timestamp", "TIMESTAMP", "2025-01-01"),
        ]

        # Setup mock response
        mock_job = Mock()
        mock_job.total_bytes_processed = 1024 * 1024 * 100  # 100 MB
        mock_client.query.return_value = mock_job

        # Execute analytics query with premium tier
        query = """
        SELECT
            keyword,
            impressions,
            clicks,
            cost_micros / 1000000 as cost_usd
        FROM `project.dataset.search_terms_performance`
        WHERE customer_id = @customer_id
        AND date >= @start_timestamp
        """

        result = safe_execute_query(
            mock_client,
            query,
            parameters,
            customer_tier=CustomerTier.PREMIUM,
        )

        # Verify premium tier timeout was used
        actual_call_args = mock_client.query.call_args_list[1]
        job_config = actual_call_args[1]["job_config"]
        assert job_config.job_timeout_ms == 300000  # 5 minutes for premium

    def test_enterprise_large_export_simulation(self, mock_client):
        """Simulate an enterprise large export using timeout system."""
        # Setup query parameters for large export
        parameters = [
            bigquery.ScalarQueryParameter(
                "customer_id", "STRING", "enterprise_customer_456"
            ),
        ]

        # Setup mock response for large dataset
        mock_job = Mock()
        mock_job.total_bytes_processed = 1024**4 * 2  # 2 TB
        mock_client.query.return_value = mock_job

        # Execute large export query with enterprise tier
        query = """
        SELECT *
        FROM `project.dataset.historical_performance`
        WHERE customer_id = @customer_id
        ORDER BY date DESC
        """

        result = safe_execute_query(
            mock_client,
            query,
            parameters,
            customer_tier=CustomerTier.ENTERPRISE,
        )

        # Should succeed due to enterprise cost limit ($50 vs $10 for standard)
        assert result == mock_job

    def test_standard_tier_resource_limits(self, mock_client):
        """Test standard tier resource limits and timeouts."""
        # Setup query parameters
        parameters = [
            bigquery.ScalarQueryParameter(
                "customer_id", "STRING", "standard_customer_789"
            ),
        ]

        # Setup mock response that would exceed standard tier limits
        mock_job = Mock()
        mock_job.total_bytes_processed = 1024**4 * 2.5  # 2.5 TB (~$12.50)
        mock_client.query.return_value = mock_job

        # Execute query with standard tier
        query = "SELECT * FROM large_table WHERE customer_id = @customer_id"

        # Should fail due to cost limit
        with pytest.raises(Exception) as exc_info:
            safe_execute_query(
                mock_client,
                query,
                parameters,
                customer_tier=CustomerTier.STANDARD,
            )

        assert "too expensive" in str(exc_info.value)
        assert "$10.00" in str(exc_info.value)  # Standard tier limit

    def test_environment_based_timeout_adjustment(self, mock_client):
        """Test that environment affects timeout calculations."""
        with patch.dict("os.environ", {"PSN_ENVIRONMENT": "development"}):
            # Re-import to pick up environment change
            from paidsearchnav.api.v1.premium_utils import safe_execute_query

            parameters = [
                bigquery.ScalarQueryParameter("customer_id", "STRING", "dev_customer"),
            ]

            mock_job = Mock()
            mock_job.total_bytes_processed = 1024 * 1024  # 1 MB
            mock_client.query.return_value = mock_job

            result = safe_execute_query(
                mock_client,
                "SELECT 1",
                parameters,
                customer_tier=CustomerTier.STANDARD,
            )

            # In development environment, timeouts should be reduced by 0.5 multiplier
            # Standard tier base: 180s -> Development: 90s -> 90000ms
            actual_call_args = mock_client.query.call_args_list[1]
            job_config = actual_call_args[1]["job_config"]
            assert job_config.job_timeout_ms == 90000
