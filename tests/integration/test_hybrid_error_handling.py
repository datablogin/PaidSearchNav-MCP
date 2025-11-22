"""Error handling and edge case tests for hybrid BigQuery pipeline."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from paidsearchnav.core.config import BigQueryConfig, BigQueryTier
from paidsearchnav.exports.base import ExportFormat, ExportRequest, ExportStatus
from paidsearchnav.exports.hybrid import HybridExportManager
from tests.mocks.bigquery_mock import create_mock_bigquery_config


class TestHybridErrorHandling:
    """Test error handling and edge cases in hybrid pipeline."""

    @pytest.fixture
    def sample_data(self):
        """Standard test data."""
        return {
            "search_terms": [
                {
                    "campaign": "Test Campaign",
                    "search_term": "test keyword",
                    "clicks": 10,
                    "cost": 5.50,
                    "date": "2024-01-15",
                }
            ],
            "keywords": [
                {
                    "campaign": "Test Campaign",
                    "keyword": "test keyword",
                    "clicks": 15,
                    "cost": 7.25,
                    "date": "2024-01-15",
                }
            ],
        }

    @pytest.fixture
    def corrupted_data(self):
        """Data with various corruption scenarios."""
        return {
            "search_terms": [
                # Missing required fields
                {
                    "campaign": "Test Campaign",
                    # missing search_term
                    "clicks": 10,
                    "cost": 5.50,
                },
                # Invalid data types
                {
                    "campaign": 123,  # Should be string
                    "search_term": "test",
                    "clicks": "invalid",  # Should be int
                    "cost": None,  # Should be float
                },
                # Extremely long strings
                {
                    "campaign": "A" * 10000,  # Very long string
                    "search_term": "B" * 5000,
                    "clicks": 1,
                    "cost": 1.0,
                },
            ],
            "keywords": [
                # Malformed dates
                {
                    "campaign": "Test",
                    "keyword": "test",
                    "date": "invalid-date",
                    "clicks": 1,
                    "cost": 1.0,
                },
                # Negative values
                {
                    "campaign": "Test",
                    "keyword": "test",
                    "clicks": -5,  # Negative clicks
                    "cost": -10.0,  # Negative cost
                    "date": "2024-01-15",
                },
            ],
        }

    @pytest.fixture
    def empty_data(self):
        """Empty data scenarios."""
        return {"search_terms": [], "keywords": [], "recommendations": []}

    @pytest.mark.asyncio
    async def test_bigquery_connection_failure(self, sample_data):
        """Test handling of BigQuery connection failures."""
        manager = HybridExportManager()
        request = ExportRequest(customer_id="1234567890")  # Premium tier
        bigquery_config = create_mock_bigquery_config("premium", True)

        with patch(
            "paidsearchnav.exports.bigquery.BigQueryExporter"
        ) as mock_bq_exporter:
            # Mock connection failure
            mock_exporter = AsyncMock()
            mock_exporter.validate_connection.side_effect = Exception(
                "Connection timeout"
            )
            mock_bq_exporter.return_value = mock_exporter

            results = await manager.export_data_hybrid(
                request, sample_data, bigquery_config
            )

            # Should have CSV (success) and BigQuery (failed) results
            assert len(results) == 2

            csv_results = [r for r in results if r.destination == ExportFormat.CSV]
            bq_results = [r for r in results if r.destination == ExportFormat.BIGQUERY]

            assert len(csv_results) == 1
            assert len(bq_results) == 1

            # CSV should succeed as fallback
            assert csv_results[0].status == ExportStatus.COMPLETED

            # BigQuery should fail gracefully
            assert bq_results[0].status == ExportStatus.FAILED
            assert "connection" in bq_results[0].error_message.lower()

    @pytest.mark.asyncio
    async def test_bigquery_permission_denied(self, sample_data):
        """Test handling of BigQuery permission errors."""
        manager = HybridExportManager()
        request = ExportRequest(customer_id="1234567890")  # Premium tier
        bigquery_config = create_mock_bigquery_config("premium", True)

        with patch(
            "paidsearchnav.exports.bigquery.BigQueryExporter"
        ) as mock_bq_exporter:
            # Mock permission denied
            from google.cloud.exceptions import Forbidden

            mock_exporter = AsyncMock()
            mock_exporter.export_audit_results.side_effect = Forbidden("Access denied")
            mock_bq_exporter.return_value = mock_exporter

            results = await manager.export_data_hybrid(
                request, sample_data, bigquery_config
            )

            bq_results = [r for r in results if r.destination == ExportFormat.BIGQUERY]
            assert len(bq_results) == 1
            assert bq_results[0].status == ExportStatus.FAILED
            assert "access denied" in bq_results[0].error_message.lower()

    @pytest.mark.asyncio
    async def test_bigquery_quota_exceeded(self, sample_data):
        """Test handling of BigQuery quota exceeded errors."""
        manager = HybridExportManager()
        request = ExportRequest(customer_id="1234567890")  # Premium tier
        bigquery_config = create_mock_bigquery_config("premium", True)

        with patch(
            "paidsearchnav.exports.bigquery.BigQueryExporter"
        ) as mock_bq_exporter:
            # Mock quota exceeded
            from google.cloud.exceptions import TooManyRequests

            mock_exporter = AsyncMock()
            mock_exporter.export_audit_results.side_effect = TooManyRequests(
                "Quota exceeded"
            )
            mock_bq_exporter.return_value = mock_exporter

            results = await manager.export_data_hybrid(
                request, sample_data, bigquery_config
            )

            bq_results = [r for r in results if r.destination == ExportFormat.BIGQUERY]
            assert len(bq_results) == 1
            assert bq_results[0].status == ExportStatus.FAILED
            assert "quota" in bq_results[0].error_message.lower()

    @pytest.mark.asyncio
    async def test_csv_export_disk_full(self, sample_data):
        """Test handling of disk space issues during CSV export."""
        manager = HybridExportManager()
        request = ExportRequest(customer_id="9999999999")  # Standard tier

        with patch.object(manager.csv_exporter, "export_search_terms") as mock_export:
            # Mock disk full error
            mock_export.side_effect = OSError("No space left on device")

            results = await manager.export_data_hybrid(request, sample_data)

            assert len(results) == 1
            assert results[0].status == ExportStatus.FAILED
            assert "space" in results[0].error_message.lower()

    @pytest.mark.asyncio
    async def test_csv_export_permission_denied(self, sample_data):
        """Test handling of file permission issues during CSV export."""
        manager = HybridExportManager()
        request = ExportRequest(customer_id="9999999999")  # Standard tier

        with patch.object(manager.csv_exporter, "export_search_terms") as mock_export:
            # Mock permission denied
            mock_export.side_effect = PermissionError("Permission denied")

            results = await manager.export_data_hybrid(request, sample_data)

            assert len(results) == 1
            assert results[0].status == ExportStatus.FAILED
            assert "permission" in results[0].error_message.lower()

    @pytest.mark.asyncio
    async def test_corrupted_data_handling(self, corrupted_data):
        """Test handling of corrupted or malformed data."""
        manager = HybridExportManager()
        request = ExportRequest(customer_id="9999999999")  # Standard tier

        # Should handle corrupted data gracefully
        results = await manager.export_data_hybrid(request, corrupted_data)

        assert len(results) == 1
        result = results[0]

        # Depending on implementation, this might succeed with cleaned data
        # or fail with validation errors. Both are acceptable as long as
        # the system doesn't crash.
        assert result.status in [ExportStatus.COMPLETED, ExportStatus.FAILED]

        if result.status == ExportStatus.FAILED:
            assert result.error_message is not None
            assert len(result.error_message) > 0

    @pytest.mark.asyncio
    async def test_empty_data_handling(self, empty_data):
        """Test handling of empty datasets."""
        manager = HybridExportManager()
        request = ExportRequest(customer_id="9999999999")  # Standard tier

        results = await manager.export_data_hybrid(request, empty_data)

        assert len(results) == 1
        result = results[0]

        # Empty data should be handled gracefully
        assert result.status == ExportStatus.COMPLETED
        assert result.records_exported == 0

    @pytest.mark.asyncio
    async def test_very_large_single_record(self, sample_data):
        """Test handling of extremely large individual records."""
        # Create a record with very large fields
        large_data = {
            "search_terms": [
                {
                    "campaign": "A" * 100000,  # 100KB string
                    "search_term": "B" * 50000,  # 50KB string
                    "clicks": 1,
                    "cost": 1.0,
                    "metadata": "C" * 200000,  # 200KB metadata
                }
            ]
        }

        manager = HybridExportManager()
        request = ExportRequest(customer_id="9999999999")  # Standard tier

        results = await manager.export_data_hybrid(request, large_data)

        # Should handle large records (might truncate or fail gracefully)
        assert len(results) == 1
        result = results[0]
        assert result.status in [ExportStatus.COMPLETED, ExportStatus.FAILED]

    @pytest.mark.asyncio
    async def test_concurrent_failures(self, sample_data):
        """Test handling of concurrent operation failures."""
        manager = HybridExportManager()

        # Create requests that will fail
        failing_requests = [
            ExportRequest(customer_id=f"failing_customer_{i}") for i in range(3)
        ]

        with patch.object(manager.csv_exporter, "export_search_terms") as mock_export:
            # Mock random failures
            mock_export.side_effect = [
                Exception("Failure 1"),
                Exception("Failure 2"),
                Exception("Failure 3"),
            ]

            tasks = [
                manager.export_data_hybrid(request, sample_data)
                for request in failing_requests
            ]

            results_list = await asyncio.gather(*tasks, return_exceptions=True)

            # All should fail but not crash
            assert len(results_list) == 3
            for results in results_list:
                assert not isinstance(results, Exception)
                assert len(results) == 1
                assert results[0].status == ExportStatus.FAILED

    @pytest.mark.asyncio
    async def test_partial_bigquery_failure(self, sample_data):
        """Test handling when only some BigQuery operations fail."""
        manager = HybridExportManager()
        request = ExportRequest(customer_id="1234567890")  # Premium tier
        bigquery_config = create_mock_bigquery_config("premium", True)

        with patch(
            "paidsearchnav.exports.bigquery.BigQueryExporter"
        ) as mock_bq_exporter:
            mock_exporter = AsyncMock()

            # Mock partial failure - audit results succeed, recommendations fail
            mock_exporter.export_audit_results.return_value = MagicMock(
                status=ExportStatus.COMPLETED,
                destination=ExportFormat.BIGQUERY,
                records_exported=2,
            )
            mock_exporter.export_recommendations.side_effect = Exception(
                "Recommendations export failed"
            )

            mock_bq_exporter.return_value = mock_exporter

            results = await manager.export_data_hybrid(
                request, sample_data, bigquery_config
            )

            # Should have CSV and BigQuery results
            csv_results = [r for r in results if r.destination == ExportFormat.CSV]
            bq_results = [r for r in results if r.destination == ExportFormat.BIGQUERY]

            assert len(csv_results) == 1
            assert len(bq_results) == 1

            # CSV should succeed
            assert csv_results[0].status == ExportStatus.COMPLETED

            # BigQuery should show partial failure or complete failure
            # depending on implementation strategy
            assert bq_results[0].status in [ExportStatus.FAILED, ExportStatus.COMPLETED]

    @pytest.mark.asyncio
    async def test_cost_limit_edge_cases(self, sample_data):
        """Test cost limit edge cases."""
        manager = HybridExportManager()
        request = ExportRequest(customer_id="1234567890")  # Premium tier
        bigquery_config = create_mock_bigquery_config("premium", True)

        # Test exactly at limit
        manager.cost_tracker["1234567890"] = 10.0  # Exactly at limit

        results = await manager.export_data_hybrid(
            request, sample_data, bigquery_config
        )

        # Should be blocked
        bq_results = [r for r in results if r.destination == ExportFormat.BIGQUERY]
        assert bq_results[0].status == ExportStatus.FAILED
        assert "cost limit" in bq_results[0].error_message

        # Test just under limit
        manager.cost_tracker["1234567890"] = 9.99

        with patch(
            "paidsearchnav.exports.bigquery.BigQueryExporter"
        ) as mock_bq_exporter:
            mock_exporter = AsyncMock()
            mock_exporter.export_audit_results.return_value = MagicMock(
                status=ExportStatus.COMPLETED,
                destination=ExportFormat.BIGQUERY,
                records_exported=2,
            )
            mock_bq_exporter.return_value = mock_exporter

            results = await manager.export_data_hybrid(
                request, sample_data, bigquery_config
            )

            bq_results = [r for r in results if r.destination == ExportFormat.BIGQUERY]
            assert bq_results[0].status == ExportStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_invalid_customer_tier(self, sample_data):
        """Test handling of invalid or unknown customer tiers."""
        manager = HybridExportManager()

        # Mock invalid tier detection
        with patch.object(manager, "get_customer_tier") as mock_tier:
            mock_tier.return_value = "invalid_tier"

            request = ExportRequest(customer_id="unknown_customer")

            # Should fallback to standard behavior
            results = await manager.export_data_hybrid(request, sample_data)

            assert len(results) == 1
            assert results[0].destination == ExportFormat.CSV
            assert results[0].status == ExportStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_bigquery_config_validation_failure(self, sample_data):
        """Test handling of invalid BigQuery configuration."""
        manager = HybridExportManager()
        request = ExportRequest(customer_id="1234567890")  # Premium tier

        # Invalid BigQuery config
        invalid_config = BigQueryConfig(
            enabled=True,
            tier=BigQueryTier.PREMIUM,
            project_id="",  # Empty project ID
            dataset_id="",  # Empty dataset ID
        )

        results = await manager.export_data_hybrid(request, sample_data, invalid_config)

        # Should fallback to CSV only
        csv_results = [r for r in results if r.destination == ExportFormat.CSV]
        bq_results = [r for r in results if r.destination == ExportFormat.BIGQUERY]

        assert len(csv_results) == 1
        assert csv_results[0].status == ExportStatus.COMPLETED

        # BigQuery should fail due to invalid config
        if bq_results:
            assert bq_results[0].status == ExportStatus.FAILED

    @pytest.mark.asyncio
    async def test_timeout_handling(self, sample_data):
        """Test handling of operation timeouts."""
        manager = HybridExportManager()
        request = ExportRequest(customer_id="1234567890")  # Premium tier
        bigquery_config = create_mock_bigquery_config("premium", True)

        with patch(
            "paidsearchnav.exports.bigquery.BigQueryExporter"
        ) as mock_bq_exporter:
            mock_exporter = AsyncMock()

            # Mock timeout
            async def slow_export(*args, **kwargs):
                await asyncio.sleep(10)  # Simulate very slow operation
                return MagicMock(status=ExportStatus.COMPLETED)

            mock_exporter.export_audit_results.side_effect = slow_export
            mock_bq_exporter.return_value = mock_exporter

            # Set a short timeout for testing
            with patch("asyncio.wait_for") as mock_wait_for:
                mock_wait_for.side_effect = asyncio.TimeoutError("Operation timed out")

                results = await manager.export_data_hybrid(
                    request, sample_data, bigquery_config
                )

                # Should handle timeout gracefully
                bq_results = [
                    r for r in results if r.destination == ExportFormat.BIGQUERY
                ]
                if bq_results:
                    assert bq_results[0].status == ExportStatus.FAILED
                    assert "timeout" in bq_results[0].error_message.lower()

    @pytest.mark.asyncio
    async def test_memory_pressure_handling(self, sample_data):
        """Test handling under memory pressure conditions."""
        manager = HybridExportManager()
        request = ExportRequest(customer_id="9999999999")  # Standard tier

        with patch.object(manager.csv_exporter, "export_search_terms") as mock_export:
            # Mock memory error
            mock_export.side_effect = MemoryError("Not enough memory")

            results = await manager.export_data_hybrid(request, sample_data)

            assert len(results) == 1
            assert results[0].status == ExportStatus.FAILED
            assert "memory" in results[0].error_message.lower()

    def test_cost_tracking_overflow(self):
        """Test cost tracking with very large numbers."""
        manager = HybridExportManager()
        customer_id = "overflow_test"

        # Test with very large cost values
        manager.cost_tracker[customer_id] = 999999999.99

        usage = manager.get_customer_cost_usage(customer_id)

        # Should handle large numbers gracefully
        assert usage["current_cost_usd"] == 999999999.99
        assert usage["cost_percentage"] > 100  # Way over limit

        # Test resetting large values
        manager.reset_customer_costs(customer_id)
        assert manager.cost_tracker[customer_id] == 0.0

    @pytest.mark.asyncio
    async def test_malformed_json_in_data(self, sample_data):
        """Test handling of malformed JSON in metadata fields."""
        # Add malformed JSON to data
        malformed_data = sample_data.copy()
        malformed_data["search_terms"][0]["metadata"] = '{"invalid": json malformed}'
        malformed_data["keywords"][0]["extra_data"] = "Not JSON: {invalid"

        manager = HybridExportManager()
        request = ExportRequest(customer_id="9999999999")  # Standard tier

        # Should handle malformed JSON gracefully
        results = await manager.export_data_hybrid(request, malformed_data)

        assert len(results) == 1
        # Should either succeed by sanitizing data or fail gracefully
        assert results[0].status in [ExportStatus.COMPLETED, ExportStatus.FAILED]

    @pytest.mark.asyncio
    async def test_unicode_and_special_characters(self, sample_data):
        """Test handling of Unicode and special characters."""
        unicode_data = {
            "search_terms": [
                {
                    "campaign": "测试活动",  # Chinese characters
                    "search_term": "поиск 👟",  # Russian + emoji
                    "clicks": 10,
                    "cost": 5.50,
                    "date": "2024-01-15",
                    "special_chars": "!@#$%^&*()[]{}|\\:;\"'<>?,./",
                }
            ]
        }

        manager = HybridExportManager()
        request = ExportRequest(customer_id="9999999999")  # Standard tier

        results = await manager.export_data_hybrid(request, unicode_data)

        assert len(results) == 1
        assert results[0].status == ExportStatus.COMPLETED
        assert results[0].records_exported == 1

    @pytest.mark.asyncio
    async def test_null_and_undefined_values(self, sample_data):
        """Test handling of null and undefined values."""
        null_data = {
            "search_terms": [
                {
                    "campaign": None,
                    "search_term": "test",
                    "clicks": None,
                    "cost": 5.50,
                    "date": None,
                }
            ],
            "keywords": None,  # Null array
            "recommendations": [],
        }

        manager = HybridExportManager()
        request = ExportRequest(customer_id="9999999999")  # Standard tier

        # Should handle null values gracefully
        results = await manager.export_data_hybrid(request, null_data)

        assert len(results) == 1
        # Should either succeed with cleaned data or fail with validation error
        assert results[0].status in [ExportStatus.COMPLETED, ExportStatus.FAILED]

    @pytest.mark.asyncio
    async def test_network_timeout_handling(self, sample_data):
        """Test handling of network timeouts during BigQuery operations."""
        import asyncio
        from unittest.mock import patch

        manager = HybridExportManager()
        request = ExportRequest(customer_id="8888888888")  # Premium tier

        # Mock a network timeout
        async def mock_timeout_operation(*args, **kwargs):
            await asyncio.sleep(0.1)  # Simulate network delay
            raise asyncio.TimeoutError("Network operation timed out")

        with patch(
            "paidsearchnav.platforms.bigquery.service.BigQueryService.health_check",
            side_effect=mock_timeout_operation,
        ):
            # Should fallback to CSV when BigQuery times out
            results = await manager.export_data_hybrid(request, sample_data)

            assert len(results) == 1
            # Should fallback to CSV export on timeout
            assert results[0].destination.name == "CSV"
            assert results[0].status == ExportStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_concurrent_export_requests(self, sample_data):
        """Test handling multiple concurrent export requests."""
        import asyncio

        manager = HybridExportManager()

        # Create multiple concurrent requests
        requests = [
            ExportRequest(customer_id="9999999999"),  # Standard tier (CSV only)
            ExportRequest(customer_id="8888888888"),  # Premium tier
            ExportRequest(customer_id="7777777777"),  # Enterprise tier
        ]

        # Run all exports concurrently
        tasks = [manager.export_data_hybrid(req, sample_data) for req in requests]

        all_results = await asyncio.gather(*tasks, return_exceptions=True)

        # All should complete without exceptions
        assert len(all_results) == 3
        for result_list in all_results:
            assert not isinstance(result_list, Exception)
            assert len(result_list) == 1
            assert result_list[0].status == ExportStatus.COMPLETED
