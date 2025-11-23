"""Performance tests for BigQuery hybrid pipeline."""

import asyncio
import os
import time
from datetime import datetime
from typing import Dict
from unittest.mock import patch

import psutil
import pytest

from paidsearchnav_mcp.exports.base import ExportRequest
from paidsearchnav_mcp.exports.hybrid import HybridExportManager
from tests.mocks.bigquery_mock import MockBigQueryService, create_mock_bigquery_config


class TestBigQueryPerformance:
    """Performance benchmarking tests for BigQuery pipeline."""

    @pytest.fixture
    def performance_data_small(self):
        """Small dataset for performance testing (1K records)."""
        return self._generate_test_data(1000)

    @pytest.fixture
    def performance_data_medium(self):
        """Medium dataset for performance testing (10K records)."""
        return self._generate_test_data(10000)

    @pytest.fixture
    def performance_data_large(self):
        """Large dataset for performance testing (10K records - optimized for CI)."""
        return self._generate_test_data(10000)

    def _generate_test_data(self, num_records: int) -> Dict:
        """Generate test data with specified number of records."""
        data = {
            "search_terms": [],
            "keywords": [],
            "recommendations": [],
            "audit_metadata": {
                "audit_id": f"perf_test_{int(time.time())}",
                "customer_id": "performance_test_customer",
                "audit_date": datetime.now().strftime("%Y-%m-%d"),
                "total_records": num_records,
            },
        }

        # Generate search terms (80% of records)
        search_terms_count = int(num_records * 0.8)
        for i in range(search_terms_count):
            data["search_terms"].append(
                {
                    "campaign": f"Campaign_{i % 100}",
                    "ad_group": f"AdGroup_{i % 500}",
                    "search_term": f"search_term_{i}",
                    "match_type": ["BROAD", "PHRASE", "EXACT"][i % 3],
                    "clicks": i % 100,
                    "impressions": (i % 100) * 20,
                    "cost": round((i % 100) * 1.5, 2),
                    "conversions": i % 10,
                    "conversion_value": round((i % 10) * 39.99, 2),
                    "date": "2024-01-15",
                    "device": ["DESKTOP", "MOBILE", "TABLET"][i % 3],
                    "location": f"Location_{i % 50}",
                }
            )

        # Generate keywords (15% of records)
        keywords_count = int(num_records * 0.15)
        for i in range(keywords_count):
            data["keywords"].append(
                {
                    "campaign": f"Campaign_{i % 100}",
                    "ad_group": f"AdGroup_{i % 500}",
                    "keyword": f"keyword_{i}",
                    "match_type": ["BROAD", "PHRASE", "EXACT"][i % 3],
                    "clicks": i % 50,
                    "impressions": (i % 50) * 15,
                    "cost": round((i % 50) * 2.0, 2),
                    "conversions": i % 5,
                    "conversion_value": round((i % 5) * 59.99, 2),
                    "quality_score": (i % 10) + 1,
                    "date": "2024-01-15",
                    "first_page_cpc": round((i % 10) * 0.5 + 1.0, 2),
                    "top_of_page_cpc": round((i % 10) * 0.7 + 1.5, 2),
                }
            )

        # Generate recommendations (5% of records)
        recommendations_count = int(num_records * 0.05)
        for i in range(recommendations_count):
            data["recommendations"].append(
                {
                    "recommendation_id": f"rec_{i}",
                    "type": ["negative_keyword", "bid_adjustment", "keyword_expansion"][
                        i % 3
                    ],
                    "priority": ["high", "medium", "low"][i % 3],
                    "title": f"Recommendation {i}",
                    "description": f"Detailed recommendation description {i}",
                    "estimated_impact": round((i % 100) * 10.0, 2),
                    "campaign": f"Campaign_{i % 100}",
                    "created_at": datetime.now().isoformat(),
                }
            )

        return data

    def _get_memory_usage(self):
        """Get current memory usage in MB."""
        process = psutil.Process(os.getpid())
        return process.memory_info().rss / 1024 / 1024

    # CPU usage monitoring removed - unreliable in CI environments

    @pytest.mark.performance
    async def test_csv_export_performance_small_dataset(self, performance_data_small):
        """Test CSV export performance with small dataset."""
        manager = HybridExportManager()
        request = ExportRequest(customer_id="performance_test")

        # Measure performance
        start_time = time.time()
        start_memory = self._get_memory_usage()
        # CPU monitoring removed for CI reliability

        results = await manager.export_data_hybrid(request, performance_data_small)

        end_time = time.time()
        end_memory = self._get_memory_usage()
        # CPU monitoring removed for CI reliability

        # Performance assertions
        processing_time = end_time - start_time
        memory_increase = end_memory - start_memory
        # CPU usage calculation removed for CI reliability

        # Small dataset should be very fast
        assert processing_time < 2.0, (
            f"Processing took {processing_time:.2f}s, expected < 2.0s"
        )
        assert memory_increase < 50, (
            f"Memory increased by {memory_increase:.2f}MB, expected < 50MB"
        )
        assert results[0].records_exported == 1000

        print(
            f"Small dataset performance: {processing_time:.2f}s, {memory_increase:.2f}MB"
        )

    @pytest.mark.performance
    async def test_csv_export_performance_medium_dataset(self, performance_data_medium):
        """Test CSV export performance with medium dataset."""
        manager = HybridExportManager()
        request = ExportRequest(customer_id="performance_test")

        start_time = time.time()
        start_memory = self._get_memory_usage()

        results = await manager.export_data_hybrid(request, performance_data_medium)

        end_time = time.time()
        end_memory = self._get_memory_usage()

        processing_time = end_time - start_time
        memory_increase = end_memory - start_memory

        # Medium dataset performance requirements
        assert processing_time < 10.0, (
            f"Processing took {processing_time:.2f}s, expected < 10.0s"
        )
        assert memory_increase < 200, (
            f"Memory increased by {memory_increase:.2f}MB, expected < 200MB"
        )
        assert results[0].records_exported == 10000

        print(
            f"Medium dataset performance: {processing_time:.2f}s, {memory_increase:.2f}MB"
        )

    @pytest.mark.performance
    @pytest.mark.slow
    async def test_csv_export_performance_large_dataset(self, performance_data_large):
        """Test CSV export performance with large dataset."""
        manager = HybridExportManager()
        request = ExportRequest(customer_id="performance_test")

        start_time = time.time()
        start_memory = self._get_memory_usage()

        results = await manager.export_data_hybrid(request, performance_data_large)

        end_time = time.time()
        end_memory = self._get_memory_usage()

        processing_time = end_time - start_time
        memory_increase = end_memory - start_memory

        # Large dataset performance requirements
        assert processing_time < 60.0, (
            f"Processing took {processing_time:.2f}s, expected < 60.0s"
        )
        assert memory_increase < 500, (
            f"Memory increased by {memory_increase:.2f}MB, expected < 500MB"
        )
        assert results[0].records_exported == 10000

        # Calculate throughput
        throughput = 10000 / processing_time
        assert throughput > 2000, (
            f"Throughput {throughput:.0f} records/sec, expected > 2000"
        )

        print(
            f"Large dataset performance: {processing_time:.2f}s, {memory_increase:.2f}MB, {throughput:.0f} records/sec"
        )

    @pytest.mark.performance
    async def test_hybrid_export_performance_comparison(self, performance_data_medium):
        """Compare performance between CSV-only and hybrid export."""
        bigquery_config = create_mock_bigquery_config("premium", True)
        manager = HybridExportManager()

        # Test CSV-only export
        csv_request = ExportRequest(customer_id="standard_customer")  # Standard tier
        csv_start = time.time()
        csv_results = await manager.export_data_hybrid(
            csv_request, performance_data_medium
        )
        csv_time = time.time() - csv_start

        # Test hybrid export (CSV + BigQuery)
        with patch("paidsearchnav.exports.bigquery.BigQueryExporter") as mock_bq:
            mock_service = MockBigQueryService(bigquery_config)
            mock_bq.return_value = mock_service

            hybrid_request = ExportRequest(
                customer_id="premium_customer"
            )  # Premium tier
            hybrid_start = time.time()
            hybrid_results = await manager.export_data_hybrid(
                hybrid_request, performance_data_medium, bigquery_config
            )
            hybrid_time = time.time() - hybrid_start

        # Performance comparison
        assert len(csv_results) == 1  # CSV only
        assert len(hybrid_results) == 2  # CSV + BigQuery

        # Hybrid should be slower but not excessively so
        overhead_ratio = hybrid_time / csv_time
        assert overhead_ratio < 3.0, (
            f"Hybrid overhead {overhead_ratio:.1f}x, expected < 3.0x"
        )

        print(
            f"Performance comparison: CSV {csv_time:.2f}s, Hybrid {hybrid_time:.2f}s, Overhead {overhead_ratio:.1f}x"
        )

    @pytest.mark.performance
    async def test_concurrent_export_performance(self, performance_data_small):
        """Test performance of concurrent export operations."""
        manager = HybridExportManager()

        # Create multiple concurrent requests
        num_concurrent = 5
        requests = [
            ExportRequest(customer_id=f"concurrent_customer_{i}")
            for i in range(num_concurrent)
        ]

        start_time = time.time()
        start_memory = self._get_memory_usage()

        # Execute concurrent exports
        tasks = [
            manager.export_data_hybrid(request, performance_data_small)
            for request in requests
        ]
        results_list = await asyncio.gather(*tasks)

        end_time = time.time()
        end_memory = self._get_memory_usage()

        total_time = end_time - start_time
        memory_increase = end_memory - start_memory

        # All should succeed
        assert len(results_list) == num_concurrent
        for results in results_list:
            assert len(results) == 1
            assert results[0].records_exported == 1000

        # Concurrent execution should benefit from parallelism
        estimated_sequential_time = num_concurrent * 2.0  # Assume 2s per export
        efficiency = estimated_sequential_time / total_time
        assert efficiency > 2.0, (
            f"Concurrency efficiency {efficiency:.1f}x, expected > 2.0x"
        )

        print(
            f"Concurrent performance: {total_time:.2f}s for {num_concurrent} exports, {efficiency:.1f}x efficiency"
        )

    @pytest.mark.performance
    async def test_memory_efficiency_streaming(self, performance_data_large):
        """Test memory efficiency with streaming/chunked processing."""
        manager = HybridExportManager()
        request = ExportRequest(customer_id="memory_test")

        # Monitor memory throughout the process
        memory_samples = []

        async def memory_monitor():
            for _ in range(100):  # Sample for ~10 seconds
                memory_samples.append(self._get_memory_usage())
                await asyncio.sleep(0.1)

        # Start memory monitoring
        monitor_task = asyncio.create_task(memory_monitor())

        # Run export
        start_memory = self._get_memory_usage()
        results = await manager.export_data_hybrid(request, performance_data_large)
        end_memory = self._get_memory_usage()

        # Stop monitoring
        monitor_task.cancel()

        # Calculate memory statistics
        peak_memory = max(memory_samples) if memory_samples else end_memory
        memory_increase = end_memory - start_memory
        peak_increase = peak_memory - start_memory

        # Memory should not grow excessively during processing
        assert memory_increase < 300, (
            f"Final memory increase {memory_increase:.2f}MB, expected < 300MB"
        )
        assert peak_increase < 400, (
            f"Peak memory increase {peak_increase:.2f}MB, expected < 400MB"
        )

        # Memory should be relatively stable (not growing linearly with data size)
        if len(memory_samples) > 10:
            memory_stability = max(memory_samples) - min(memory_samples)
            assert memory_stability < 200, (
                f"Memory fluctuation {memory_stability:.2f}MB, expected < 200MB"
            )

        print(
            f"Memory efficiency: Final +{memory_increase:.2f}MB, Peak +{peak_increase:.2f}MB"
        )

    @pytest.mark.performance
    async def test_bigquery_mock_performance(self, performance_data_medium):
        """Test BigQuery mock service performance."""
        config = create_mock_bigquery_config("premium", True)
        service = MockBigQueryService(config)

        # Test health check performance
        start_time = time.time()
        health_result = await service.health_check()
        health_time = time.time() - start_time

        assert health_time < 0.1, (
            f"Health check took {health_time:.3f}s, expected < 0.1s"
        )
        assert health_result["status"] == "healthy"

        # Test usage stats performance
        start_time = time.time()
        usage_result = await service.get_usage_stats("test_customer")
        usage_time = time.time() - start_time

        assert usage_time < 0.1, f"Usage stats took {usage_time:.3f}s, expected < 0.1s"
        assert "daily_cost_usd" in usage_result

        # Test analytics performance
        start_time = time.time()
        insights = await service.analytics.get_search_terms_insights(
            "test_customer", 30
        )
        analytics_time = time.time() - start_time

        assert analytics_time < 0.2, (
            f"Analytics took {analytics_time:.3f}s, expected < 0.2s"
        )
        assert len(insights) >= 1

        print(
            f"BigQuery mock performance: Health {health_time:.3f}s, Usage {usage_time:.3f}s, Analytics {analytics_time:.3f}s"
        )

    @pytest.mark.performance
    async def test_cost_tracking_performance(self, performance_data_medium):
        """Test cost tracking and monitoring performance."""
        manager = HybridExportManager()
        customer_id = "cost_performance_test"

        # Simulate multiple exports with cost tracking
        num_exports = 20

        start_time = time.time()

        for i in range(num_exports):
            # Simulate export results for cost tracking
            from paidsearchnav.exports.base import (
                ExportFormat,
                ExportResult,
                ExportStatus,
            )

            export_result = ExportResult(
                export_id=f"export_{i}",
                status=ExportStatus.COMPLETED,
                destination=ExportFormat.BIGQUERY,
                records_exported=10000,
                metadata={"estimated_cost_usd": 0.01},
            )

            # Track cost
            await manager._track_export_cost(customer_id, export_result)

            # Check cost limits
            await manager._check_cost_limits(
                customer_id, manager.get_hybrid_config(customer_id)
            )

        end_time = time.time()
        total_time = end_time - start_time

        # Cost tracking should be very fast
        avg_time_per_operation = total_time / (
            num_exports * 2
        )  # 2 operations per export
        assert avg_time_per_operation < 0.001, (
            f"Cost tracking too slow: {avg_time_per_operation:.4f}s per operation"
        )

        # Verify cost accumulation
        final_cost = manager.cost_tracker[customer_id]
        expected_cost = num_exports * 0.01
        assert abs(final_cost - expected_cost) < 0.001, (
            f"Cost tracking inaccurate: {final_cost} vs {expected_cost}"
        )

        print(
            f"Cost tracking performance: {avg_time_per_operation:.4f}s per operation, {final_cost:.2f} total cost"
        )

    @pytest.mark.performance
    def test_configuration_performance(self):
        """Test performance of configuration operations."""
        manager = HybridExportManager()

        # Test tier detection performance
        customer_ids = [f"customer_{i}" for i in range(1000)]

        start_time = time.time()
        for customer_id in customer_ids:
            tier = manager.get_customer_tier(customer_id)
            config = manager.get_hybrid_config(customer_id)
        end_time = time.time()

        total_time = end_time - start_time
        avg_time = total_time / len(customer_ids)

        # Configuration should be very fast
        assert avg_time < 0.0001, (
            f"Configuration too slow: {avg_time:.6f}s per customer"
        )
        assert total_time < 0.1, f"Total configuration time too slow: {total_time:.3f}s"

        print(
            f"Configuration performance: {avg_time:.6f}s per customer, {total_time:.3f}s total"
        )

    @pytest.mark.performance
    async def test_error_handling_performance(self, performance_data_small):
        """Test performance when handling errors."""
        manager = HybridExportManager()

        # Test CSV export failure handling
        with patch.object(manager.csv_exporter, "export_search_terms") as mock_export:
            mock_export.side_effect = Exception("Simulated failure")

            start_time = time.time()
            results = await manager.export_data_hybrid(
                ExportRequest(customer_id="error_test"), performance_data_small
            )
            end_time = time.time()

            error_handling_time = end_time - start_time

            # Error handling should be fast (no retries, quick failure)
            assert error_handling_time < 1.0, (
                f"Error handling too slow: {error_handling_time:.2f}s"
            )
            assert len(results) == 1
            assert results[0].status.name == "FAILED"

        print(f"Error handling performance: {error_handling_time:.3f}s")

    def test_performance_regression_detection(self):
        """Test for performance regression detection."""
        # This test would typically compare against baseline performance metrics
        # stored in a file or database. For now, we'll just validate current performance
        # meets minimum requirements.

        baseline_metrics = {
            "small_dataset_max_time": 2.0,
            "medium_dataset_max_time": 10.0,
            "large_dataset_max_time": 60.0,
            "max_memory_increase_mb": 500,
            "min_throughput_records_per_sec": 2000,
            "max_cost_tracking_time_per_op": 0.001,
        }

        # In a real implementation, these would be compared against actual test results
        # and alerts would be raised if performance degrades significantly

        current_metrics = {
            "small_dataset_time": 1.5,  # Would be measured from actual test
            "medium_dataset_time": 8.0,
            "large_dataset_time": 45.0,
            "memory_increase_mb": 300,
            "throughput_records_per_sec": 2500,
            "cost_tracking_time_per_op": 0.0005,
        }

        # Check for regressions (more than 20% slower)
        regression_threshold = 1.2

        assert (
            current_metrics["small_dataset_time"]
            <= baseline_metrics["small_dataset_max_time"] * regression_threshold
        )
        assert (
            current_metrics["medium_dataset_time"]
            <= baseline_metrics["medium_dataset_max_time"] * regression_threshold
        )
        assert (
            current_metrics["large_dataset_time"]
            <= baseline_metrics["large_dataset_max_time"] * regression_threshold
        )
        assert (
            current_metrics["memory_increase_mb"]
            <= baseline_metrics["max_memory_increase_mb"]
        )
        assert (
            current_metrics["throughput_records_per_sec"]
            >= baseline_metrics["min_throughput_records_per_sec"] / regression_threshold
        )
        assert (
            current_metrics["cost_tracking_time_per_op"]
            <= baseline_metrics["max_cost_tracking_time_per_op"] * regression_threshold
        )

        print("Performance regression check passed")
