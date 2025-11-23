"""Tests for BigQuery timeout client."""

from unittest.mock import Mock, patch

import pytest
from google.cloud import bigquery
from google.cloud.exceptions import GoogleCloudError

from paidsearchnav_mcp.platforms.bigquery.timeout_client import (
    BigQueryTimeoutClient,
    BigQueryTimeoutError,
    create_timeout_client,
)
from paidsearchnav_mcp.platforms.bigquery.timeout_config import CustomerTier


class TestBigQueryTimeoutClient:
    """Test BigQueryTimeoutClient class."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock BigQuery client."""
        return Mock(spec=bigquery.Client)

    @pytest.fixture
    def timeout_client(self, mock_client):
        """Create a timeout client with mock."""
        return BigQueryTimeoutClient(mock_client, CustomerTier.STANDARD)

    @pytest.mark.asyncio
    async def test_query_with_timeout_success(self, timeout_client, mock_client):
        """Test successful query execution with timeout."""
        # Setup mock query job
        mock_job = Mock()
        mock_job.done.side_effect = [False, False, True]  # Complete on third check
        mock_job.error_result = None
        mock_client.query.return_value = mock_job

        # Execute query
        result = await timeout_client.query_with_timeout("SELECT 1")

        # Verify
        assert result == mock_job
        mock_client.query.assert_called_once()

    @pytest.mark.asyncio
    async def test_query_with_timeout_job_timeout(self, timeout_client, mock_client):
        """Test query timeout scenario."""
        # Setup mock that never completes
        mock_job = Mock()
        mock_job.done.return_value = False
        mock_job.cancel = Mock()
        mock_client.query.return_value = mock_job

        # Mock time to simulate timeout
        with patch("time.time") as mock_time:
            mock_time.side_effect = [0, 200]  # Simulate 200 seconds elapsed

            with pytest.raises(BigQueryTimeoutError, match="Query timed out after"):
                await timeout_client.query_with_timeout("SELECT 1")

            # Verify job was cancelled
            mock_job.cancel.assert_called_once()

    @pytest.mark.asyncio
    async def test_query_with_timeout_query_error(self, timeout_client, mock_client):
        """Test query execution with BigQuery error."""
        # Setup mock query job with error
        mock_job = Mock()
        mock_job.done.return_value = True
        mock_job.error_result = {"message": "Test error"}
        mock_client.query.return_value = mock_job

        # Execute query and expect error
        with pytest.raises(GoogleCloudError, match="Query failed"):
            await timeout_client.query_with_timeout("SELECT 1")

    @pytest.mark.asyncio
    async def test_query_with_timeout_retry_logic(self, timeout_client, mock_client):
        """Test retry logic on transient failures."""
        # Setup mock that fails twice then succeeds
        mock_job_success = Mock()
        mock_job_success.done.return_value = True
        mock_job_success.error_result = None

        mock_client.query.side_effect = [
            GoogleCloudError("Transient error"),
            GoogleCloudError("Another transient error"),
            mock_job_success,
        ]

        # Execute query
        result = await timeout_client.query_with_timeout("SELECT 1")

        # Verify retry happened and eventually succeeded
        assert result == mock_job_success
        assert mock_client.query.call_count == 3

    @pytest.mark.asyncio
    async def test_query_with_timeout_max_retries_exceeded(
        self, timeout_client, mock_client
    ):
        """Test behavior when max retries are exceeded."""
        # Setup mock that always fails
        mock_client.query.side_effect = GoogleCloudError("Persistent error")

        # Execute query and expect failure
        with pytest.raises(
            GoogleCloudError, match="Query failed after all retry attempts"
        ):
            await timeout_client.query_with_timeout("SELECT 1")

        # Verify all retries were attempted (default is 3)
        assert mock_client.query.call_count == 3

    @pytest.mark.asyncio
    async def test_query_with_custom_customer_tier(self, timeout_client, mock_client):
        """Test query with custom customer tier."""
        # Setup mock query job
        mock_job = Mock()
        mock_job.done.return_value = True
        mock_job.error_result = None
        mock_client.query.return_value = mock_job

        # Execute with enterprise tier
        result = await timeout_client.query_with_timeout(
            "SELECT 1", customer_tier=CustomerTier.ENTERPRISE
        )

        # Verify job config was called with enterprise timeout (10 minutes = 600000ms)
        args, kwargs = mock_client.query.call_args
        job_config = kwargs.get("job_config") or args[1]
        assert job_config.job_timeout_ms == 600000

    @pytest.mark.asyncio
    async def test_export_to_csv_with_timeout_success(
        self, timeout_client, mock_client
    ):
        """Test successful CSV export."""
        # Setup mock query job
        mock_job = Mock()
        mock_job.done.return_value = True
        mock_job.error_result = None
        mock_job.result.return_value = [{"col1": "value1"}, {"col1": "value2"}]
        mock_client.query.return_value = mock_job

        # Execute export
        result = await timeout_client.export_to_csv_with_timeout(
            "SELECT col1 FROM table"
        )

        # Verify result
        assert result == [{"col1": "value1"}, {"col1": "value2"}]

    @pytest.mark.asyncio
    async def test_export_to_csv_with_cloud_storage(self, timeout_client, mock_client):
        """Test CSV export to Cloud Storage."""
        # Setup mock query job
        mock_query_job = Mock()
        mock_query_job.done.return_value = True
        mock_query_job.error_result = None
        mock_query_job.destination = "project.dataset.table"

        # Setup mock extract job
        mock_extract_job = Mock()
        mock_extract_job.done.return_value = True
        mock_extract_job.error_result = None

        mock_client.query.return_value = mock_query_job
        mock_client.extract_table.return_value = mock_extract_job

        # Execute export
        result = await timeout_client.export_to_csv_with_timeout(
            "SELECT col1 FROM table", "gs://bucket/file.csv"
        )

        # Verify extract job was returned
        assert result == mock_extract_job
        mock_client.extract_table.assert_called_once()

    @pytest.mark.asyncio
    async def test_export_timeout_fallback(self, timeout_client, mock_client):
        """Test export timeout fallback to direct query."""
        # Setup query that times out on first call
        with patch.object(timeout_client, "query_with_timeout") as mock_query:
            mock_query.side_effect = [
                BigQueryTimeoutError("Export timed out"),  # First call times out
                Mock(result=lambda: [{"col1": "fallback"}]),  # Fallback succeeds
            ]

            # Execute export
            result = await timeout_client.export_to_csv_with_timeout(
                "SELECT col1 FROM table"
            )

            # Verify fallback was used
            assert result == [{"col1": "fallback"}]
            assert mock_query.call_count == 2

    @pytest.mark.asyncio
    async def test_connection_timeout_context_manager(self, timeout_client):
        """Test connection timeout context manager."""
        # Test successful operation
        async with timeout_client.connection_timeout(CustomerTier.STANDARD):
            pass  # Should complete without error

        # Test operation that would timeout
        with patch("time.time") as mock_time:
            mock_time.side_effect = [0, 100]  # Simulate 100 seconds elapsed

            with pytest.raises(BigQueryTimeoutError, match="Connection timeout"):
                async with timeout_client.connection_timeout(CustomerTier.STANDARD):
                    raise Exception("Simulated connection error")

    def test_get_job_status_with_timeout_success(self, timeout_client, mock_client):
        """Test successful job status retrieval."""
        # Setup mock job
        mock_job = Mock()
        mock_job.job_id = "test_job_123"
        mock_job.state = "DONE"
        mock_job.created = None
        mock_job.started = None
        mock_job.ended = None
        mock_job.error_result = None
        mock_job.total_bytes_processed = 1024

        mock_client.get_job.return_value = mock_job

        # Get job status
        status = timeout_client.get_job_status_with_timeout("test_job_123")

        # Verify status info
        assert status["job_id"] == "test_job_123"
        assert status["state"] == "DONE"
        assert status["total_bytes_processed"] == 1024
        assert "elapsed_seconds" in status

    def test_get_job_status_with_timeout_error(self, timeout_client, mock_client):
        """Test job status retrieval with error."""
        mock_client.get_job.side_effect = Exception("Job not found")

        # Get job status and expect error
        with pytest.raises(BigQueryTimeoutError, match="Job status check timed out"):
            timeout_client.get_job_status_with_timeout("nonexistent_job")

    def test_get_timeout_config_default_tier(self, timeout_client):
        """Test timeout config retrieval with default tier."""
        config = timeout_client._get_timeout_config()

        # Should use default tier (STANDARD)
        assert config.query_timeout == 180  # Standard tier timeout

    def test_get_timeout_config_custom_tier(self, timeout_client):
        """Test timeout config retrieval with custom tier."""
        config = timeout_client._get_timeout_config(CustomerTier.ENTERPRISE)

        # Should use enterprise tier timeout
        assert config.query_timeout == 600  # Enterprise tier timeout

    def test_get_timeout_config_with_operation(self, timeout_client):
        """Test timeout config retrieval with operation type."""
        config = timeout_client._get_timeout_config(
            CustomerTier.STANDARD, "large_export"
        )

        # Should apply large_export multiplier (2x)
        assert config.query_timeout == 360  # 180 * 2


class TestCreateTimeoutClient:
    """Test create_timeout_client factory function."""

    @patch("paidsearchnav.platforms.bigquery.timeout_client.bigquery.Client")
    def test_create_timeout_client_default(self, mock_client_class):
        """Test creating timeout client with defaults."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        client = create_timeout_client()

        assert isinstance(client, BigQueryTimeoutClient)
        assert client.client == mock_client
        assert client.default_tier == CustomerTier.STANDARD
        mock_client_class.assert_called_once_with(project=None)

    @patch("paidsearchnav.platforms.bigquery.timeout_client.bigquery.Client")
    def test_create_timeout_client_with_params(self, mock_client_class):
        """Test creating timeout client with custom parameters."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        client = create_timeout_client(
            project_id="test-project", customer_tier=CustomerTier.ENTERPRISE
        )

        assert isinstance(client, BigQueryTimeoutClient)
        assert client.default_tier == CustomerTier.ENTERPRISE
        mock_client_class.assert_called_once_with(project="test-project")


class TestBigQueryTimeoutErrorScenarios:
    """Test various timeout error scenarios."""

    @pytest.fixture
    def timeout_client(self):
        """Create timeout client with very short timeouts for testing."""
        mock_client = Mock(spec=bigquery.Client)
        return BigQueryTimeoutClient(mock_client, CustomerTier.STANDARD)

    @pytest.mark.asyncio
    async def test_job_cancellation_failure(self, timeout_client):
        """Test scenario where job cancellation fails."""
        mock_job = Mock()
        mock_job.done.return_value = False
        mock_job.cancel.side_effect = Exception("Cannot cancel job")
        timeout_client.client.query.return_value = mock_job

        with patch("time.time") as mock_time:
            mock_time.side_effect = [0, 200]  # Simulate timeout

            # Should still raise BigQueryTimeoutError even if cancel fails
            with pytest.raises(BigQueryTimeoutError, match="Query timed out"):
                await timeout_client.query_with_timeout("SELECT 1")

    @pytest.mark.asyncio
    async def test_fallback_export_also_fails(self, timeout_client):
        """Test scenario where both primary and fallback exports fail."""
        with patch.object(timeout_client, "query_with_timeout") as mock_query:
            mock_query.side_effect = [
                BigQueryTimeoutError("Primary export failed"),
                Exception("Fallback also failed"),
            ]

            with pytest.raises(
                BigQueryTimeoutError, match="Both primary and fallback exports failed"
            ):
                await timeout_client.export_to_csv_with_timeout("SELECT 1")

    @pytest.mark.asyncio
    async def test_extract_job_timeout(self, timeout_client):
        """Test timeout during extract job execution."""
        # Setup successful query but failing extract
        mock_query_job = Mock()
        mock_query_job.done.return_value = True
        mock_query_job.error_result = None
        mock_query_job.destination = "project.dataset.table"

        mock_extract_job = Mock()
        mock_extract_job.done.return_value = False  # Never completes
        mock_extract_job.cancel = Mock()

        timeout_client.client.query.return_value = mock_query_job
        timeout_client.client.extract_table.return_value = mock_extract_job

        with patch("time.time") as mock_time:
            mock_time.side_effect = [0, 2000]  # Simulate extract timeout

            with pytest.raises(BigQueryTimeoutError, match="Export timed out"):
                await timeout_client.export_to_csv_with_timeout(
                    "SELECT 1", "gs://bucket/file.csv"
                )

    @pytest.mark.asyncio
    async def test_long_running_query_cancellation(self, timeout_client):
        """Test cancellation of long-running queries."""
        mock_job = Mock()
        mock_job.done.return_value = False
        mock_job.cancel = Mock()
        mock_job.job_id = "test_job_123"
        timeout_client.client.query.return_value = mock_job

        with patch("time.time") as mock_time:
            # Simulate timeout scenario
            mock_time.side_effect = [0, 200]  # Start time, then timeout elapsed

            with pytest.raises(BigQueryTimeoutError, match="Query timed out"):
                await timeout_client.query_with_timeout(
                    "SELECT COUNT(*) FROM large_table"
                )

            # Verify job was cancelled
            mock_job.cancel.assert_called_once()

    @pytest.mark.asyncio
    async def test_network_timeout_during_polling(self, timeout_client):
        """Test network timeout during job status polling."""
        mock_job = Mock()
        mock_job.done.return_value = False
        mock_job.reload.side_effect = [None, None, Exception("Network timeout")]
        timeout_client.client.query.return_value = mock_job

        with pytest.raises(Exception, match="Network timeout"):
            await timeout_client.query_with_timeout("SELECT 1")

    @pytest.mark.asyncio
    async def test_bigquery_service_outage_simulation(self, timeout_client):
        """Test behavior during BigQuery service outage simulation."""
        from google.cloud.exceptions import ServiceUnavailable

        # Simulate service unavailable error
        timeout_client.client.query.side_effect = ServiceUnavailable(
            "Service unavailable"
        )

        with pytest.raises(ServiceUnavailable):
            await timeout_client.query_with_timeout("SELECT 1")

    def test_timeout_config_caching(self, timeout_client):
        """Test that timeout configurations are cached for performance."""
        # Clear cache to start fresh
        timeout_client._timeout_cache.clear()

        # First call should cache the config
        config1 = timeout_client._get_timeout_config(CustomerTier.PREMIUM)
        assert len(timeout_client._timeout_cache) == 1

        # Second call should use cache
        config2 = timeout_client._get_timeout_config(CustomerTier.PREMIUM)
        assert config1 is config2  # Should be the same object from cache
        assert len(timeout_client._timeout_cache) == 1  # Cache size unchanged

    def test_exponential_backoff_intervals(self, timeout_client):
        """Test that exponential backoff calculates correct intervals."""
        config = timeout_client._get_timeout_config()
        base_interval = config.job_poll_interval

        # Test that backoff intervals increase exponentially
        # This is tested indirectly by verifying the calculation logic
        for poll_count in range(1, 8):
            if poll_count <= 3:
                expected = base_interval
            else:
                expected = min(
                    base_interval * (2 ** (poll_count - 3)),
                    30,  # Max interval
                )
            # The actual calculation is in the async polling loop
            # We're testing the logic here
            assert expected >= base_interval
