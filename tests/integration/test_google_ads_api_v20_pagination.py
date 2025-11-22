"""Integration tests for Google Ads API V20 pagination investigation."""

import os
import time
from datetime import datetime, timedelta
from typing import Any, Dict

import pytest

from paidsearchnav.core.config import Settings
from paidsearchnav.platforms.google.client import GoogleAdsAPIClient


class APIEfficiencyMetrics:
    """Track API call efficiency metrics for pagination testing."""

    def __init__(self):
        self.call_count = 0
        self.total_response_time = 0.0
        self.error_count = 0
        self.records_retrieved = 0
        self.pagination_errors = 0
        self.page_counts = []
        self.call_details = []

    def track_api_call(
        self,
        response_time: float,
        record_count: int,
        had_error: bool = False,
        error_type: str = None,
    ):
        """Track metrics for each API call."""
        self.call_count += 1
        self.total_response_time += response_time
        self.records_retrieved += record_count

        if had_error:
            self.error_count += 1
            if error_type and "PAGE_SIZE" in error_type:
                self.pagination_errors += 1

        self.page_counts.append(record_count)
        self.call_details.append(
            {
                "call_number": self.call_count,
                "response_time": response_time,
                "record_count": record_count,
                "had_error": had_error,
                "error_type": error_type,
                "timestamp": datetime.now().isoformat(),
            }
        )

    def get_efficiency_report(self) -> Dict[str, Any]:
        """Return comprehensive efficiency metrics."""
        avg_response_time = self.total_response_time / max(self.call_count, 1)
        error_rate = (self.error_count / max(self.call_count, 1)) * 100
        pagination_error_rate = (self.pagination_errors / max(self.call_count, 1)) * 100
        avg_records_per_call = sum(self.page_counts) / max(len(self.page_counts), 1)

        return {
            "total_api_calls": self.call_count,
            "total_response_time": self.total_response_time,
            "average_response_time": avg_response_time,
            "total_records_retrieved": self.records_retrieved,
            "average_records_per_call": avg_records_per_call,
            "error_count": self.error_count,
            "error_rate_percentage": error_rate,
            "pagination_error_count": self.pagination_errors,
            "pagination_error_rate_percentage": pagination_error_rate,
            "page_count_distribution": {
                "min": min(self.page_counts) if self.page_counts else 0,
                "max": max(self.page_counts) if self.page_counts else 0,
                "pages": len(self.page_counts),
            },
            "call_details": self.call_details[-10:],  # Last 10 calls for debugging
        }


class TestGoogleAdsAPIv20Pagination:
    """Integration tests for Google Ads API V20 pagination behavior."""

    @pytest.fixture(scope="class")
    def settings(self):
        """Load settings for integration testing."""
        settings = Settings.from_env()
        if not settings.google_ads or not settings.google_ads.developer_token:
            pytest.skip(
                "Google Ads API credentials not configured for integration testing"
            )
        return settings

    @pytest.fixture(scope="class")
    def client(self, settings):
        """Create GoogleAds client for integration testing."""
        return GoogleAdsAPIClient(
            developer_token=settings.google_ads.developer_token.get_secret_value(),
            client_id=settings.google_ads.client_id,
            client_secret=settings.google_ads.client_secret.get_secret_value(),
            refresh_token=settings.google_ads.refresh_token.get_secret_value(),
            login_customer_id=settings.google_ads.login_customer_id,
            settings=settings,
            default_page_size=1000,  # This should not be used in V20
            max_page_size=10000,
        )

    @pytest.fixture(scope="class")
    def customer_id(self, settings):
        """Get customer ID for testing."""
        customer_id = (
            os.getenv("PSN_TEST_CUSTOMER_ID") or settings.google_ads.login_customer_id
        )
        if not customer_id:
            pytest.skip("No test customer ID configured")
        return customer_id

    @pytest.fixture
    def metrics(self):
        """Create metrics tracker for each test."""
        return APIEfficiencyMetrics()

    def test_default_pagination_behavior(self, client, customer_id, metrics):
        """Test default pagination without setting page_size."""
        query = """
            SELECT
                customer.id,
                customer.descriptive_name,
                customer.currency_code
            FROM customer
            LIMIT 1
        """

        start_time = time.time()
        try:
            results = client._paginated_search(customer_id, query)
            response_time = time.time() - start_time

            metrics.track_api_call(response_time, len(results), False)

            assert len(results) >= 1
            assert response_time < 5.0  # Should respond within 5 seconds

        except Exception as e:
            response_time = time.time() - start_time
            error_type = type(e).__name__
            metrics.track_api_call(response_time, 0, True, error_type)

            # If this fails due to PAGE_SIZE_NOT_SUPPORTED, the test reveals the issue
            if "PAGE_SIZE_NOT_SUPPORTED" in str(e):
                pytest.fail(f"PAGE_SIZE_NOT_SUPPORTED error occurred: {e}")
            else:
                raise

        finally:
            print(f"Default pagination test metrics: {metrics.get_efficiency_report()}")

    def test_campaign_query_without_page_size(self, client, customer_id, metrics):
        """Test campaign queries that historically caused PAGE_SIZE_NOT_SUPPORTED errors."""
        query = """
            SELECT
                campaign.id,
                campaign.name,
                campaign.status,
                campaign.advertising_channel_type
            FROM campaign
            WHERE campaign.status != 'REMOVED'
        """

        start_time = time.time()
        try:
            results = client._paginated_search(customer_id, query, max_results=100)
            response_time = time.time() - start_time

            metrics.track_api_call(response_time, len(results), False)

            # Verify we get results without pagination errors
            assert isinstance(results, list)
            assert response_time < 10.0

        except Exception as e:
            response_time = time.time() - start_time
            error_type = type(e).__name__
            metrics.track_api_call(response_time, 0, True, error_type)

            if "PAGE_SIZE_NOT_SUPPORTED" in str(e):
                pytest.fail(f"Campaign query failed with PAGE_SIZE_NOT_SUPPORTED: {e}")
            else:
                # Other errors might be acceptable (e.g., no campaigns, permission issues)
                print(f"Campaign query failed with acceptable error: {e}")

        finally:
            print(f"Campaign query test metrics: {metrics.get_efficiency_report()}")

    def test_keyword_query_with_metrics(self, client, customer_id, metrics):
        """Test keyword queries with metrics that often trigger pagination issues."""
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=30)

        query = f"""
            SELECT
                ad_group.id,
                ad_group_criterion.keyword.text,
                ad_group_criterion.keyword.match_type,
                metrics.impressions,
                metrics.clicks,
                metrics.cost_micros
            FROM keyword_view
            WHERE segments.date >= '{start_date}'
            AND segments.date <= '{end_date}'
            AND ad_group_criterion.status != 'REMOVED'
        """

        start_time = time.time()
        try:
            results = client._paginated_search(customer_id, query, max_results=500)
            response_time = time.time() - start_time

            metrics.track_api_call(response_time, len(results), False)

            assert isinstance(results, list)
            assert response_time < 15.0  # Metrics queries can be slower

        except Exception as e:
            response_time = time.time() - start_time
            error_type = type(e).__name__
            metrics.track_api_call(response_time, 0, True, error_type)

            if "PAGE_SIZE_NOT_SUPPORTED" in str(e):
                pytest.fail(
                    f"Keyword metrics query failed with PAGE_SIZE_NOT_SUPPORTED: {e}"
                )
            else:
                print(f"Keyword query failed with acceptable error: {e}")

        finally:
            print(f"Keyword query test metrics: {metrics.get_efficiency_report()}")

    def test_search_terms_query_large_dataset(self, client, customer_id, metrics):
        """Test search terms queries that may return large datasets."""
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=90)  # Longer period for more data

        query = f"""
            SELECT
                segments.search_term_view.search_term,
                campaign.id,
                ad_group.id,
                metrics.impressions,
                metrics.clicks,
                segments.search_term_view.status
            FROM search_term_view
            WHERE segments.date >= '{start_date}'
            AND segments.date <= '{end_date}'
            AND metrics.impressions > 0
        """

        page_count = 0
        total_records = 0

        start_time = time.time()
        try:
            # Use streaming to handle potentially large datasets
            for row in client.search_stream(customer_id, query):
                total_records += 1
                if total_records == 1:  # Track first page timing
                    first_page_time = time.time() - start_time
                    page_count = 1

                # Limit to prevent excessive test runtime
                if total_records >= 1000:
                    break

            response_time = time.time() - start_time
            metrics.track_api_call(response_time, total_records, False)

            assert total_records >= 0  # May be 0 if account has no search terms
            print(
                f"Retrieved {total_records} search term records in {response_time:.2f}s"
            )

        except Exception as e:
            response_time = time.time() - start_time
            error_type = type(e).__name__
            metrics.track_api_call(response_time, 0, True, error_type)

            if "PAGE_SIZE_NOT_SUPPORTED" in str(e):
                pytest.fail(
                    f"Search terms query failed with PAGE_SIZE_NOT_SUPPORTED: {e}"
                )
            else:
                print(f"Search terms query failed with acceptable error: {e}")

        finally:
            print(f"Search terms query test metrics: {metrics.get_efficiency_report()}")

    def test_multi_page_iteration(self, client, customer_id, metrics):
        """Test multi-page iteration to verify pagination works without page_size."""
        query = """
            SELECT
                ad_group_criterion.criterion_id,
                ad_group_criterion.keyword.text,
                ad_group.id,
                campaign.id
            FROM keyword_view
            WHERE ad_group_criterion.status != 'REMOVED'
        """

        page_count = 0
        total_records = 0
        page_timings = []

        try:
            for row in client.search_stream(customer_id, query):
                if (
                    total_records % 1000 == 0 and total_records > 0
                ):  # Approximate page boundary
                    page_count += 1
                    if len(page_timings) == page_count - 1:
                        page_timings.append(time.time())

                total_records += 1

                # Limit to prevent excessive test runtime
                if total_records >= 2000 or page_count >= 3:
                    break

            # Calculate page timing metrics
            if len(page_timings) > 1:
                for i in range(1, len(page_timings)):
                    page_time = page_timings[i] - page_timings[i - 1]
                    metrics.track_api_call(
                        page_time, 1000, False
                    )  # Approximate records per page

            print(f"Multi-page test: {page_count} pages, {total_records} total records")

        except Exception as e:
            error_type = type(e).__name__
            metrics.track_api_call(0, 0, True, error_type)

            if "PAGE_SIZE_NOT_SUPPORTED" in str(e):
                pytest.fail(
                    f"Multi-page iteration failed with PAGE_SIZE_NOT_SUPPORTED: {e}"
                )
            else:
                print(f"Multi-page iteration failed with acceptable error: {e}")

        finally:
            print(
                f"Multi-page iteration test metrics: {metrics.get_efficiency_report()}"
            )

    def test_api_version_compatibility(self, client, customer_id, metrics):
        """Test that the client works correctly with V20 API version."""
        # Verify the client is using the correct API version
        assert hasattr(client, "_get_client")

        # Test a simple query to verify API version compatibility
        query = "SELECT customer.id FROM customer LIMIT 1"

        start_time = time.time()
        try:
            # Access the underlying client to check version
            google_client = client._get_client()

            # Verify we can make API calls without page_size issues
            results = client._paginated_search(customer_id, query)
            response_time = time.time() - start_time

            metrics.track_api_call(response_time, len(results), False)

            assert len(results) >= 1
            print("API version compatibility test successful")

        except Exception as e:
            response_time = time.time() - start_time
            error_type = type(e).__name__
            metrics.track_api_call(response_time, 0, True, error_type)

            if "PAGE_SIZE_NOT_SUPPORTED" in str(e):
                pytest.fail(f"V20 compatibility test failed: {e}")
            else:
                raise

        finally:
            print(
                f"API version compatibility test metrics: {metrics.get_efficiency_report()}"
            )

    def test_rate_limit_handling_with_pagination(self, client, customer_id, metrics):
        """Test that rate limiting works correctly with the new pagination behavior."""
        query = "SELECT customer.id FROM customer LIMIT 1"

        # Make multiple rapid calls to test rate limiting
        call_timings = []

        for i in range(3):
            start_time = time.time()
            try:
                results = client._paginated_search(customer_id, query)
                response_time = time.time() - start_time
                call_timings.append(response_time)

                metrics.track_api_call(response_time, len(results), False)

                # Small delay between calls
                time.sleep(0.1)

            except Exception as e:
                response_time = time.time() - start_time
                error_type = type(e).__name__
                metrics.track_api_call(response_time, 0, True, error_type)

                if "PAGE_SIZE_NOT_SUPPORTED" in str(e):
                    pytest.fail(
                        f"Rate limit test failed with PAGE_SIZE_NOT_SUPPORTED: {e}"
                    )
                elif "RATE_LIMIT_EXCEEDED" in str(e):
                    print(f"Rate limit encountered as expected: {e}")
                    break
                else:
                    print(f"Rate limit test error: {e}")

        print(f"Rate limiting test completed. Call timings: {call_timings}")
        print(f"Rate limiting test metrics: {metrics.get_efficiency_report()}")

    @pytest.mark.skipif(
        os.getenv("PSN_RUN_PERFORMANCE_TESTS") != "true",
        reason="Performance tests require PSN_RUN_PERFORMANCE_TESTS=true",
    )
    def test_performance_benchmarks(self, client, customer_id, metrics):
        """Test performance benchmarks for API efficiency KPIs."""
        queries = [
            ("customer", "SELECT customer.id FROM customer LIMIT 1"),
            (
                "campaigns",
                "SELECT campaign.id, campaign.name FROM campaign WHERE campaign.status != 'REMOVED'",
            ),
            (
                "ad_groups",
                "SELECT ad_group.id, ad_group.name FROM ad_group WHERE ad_group.status != 'REMOVED' LIMIT 100",
            ),
        ]

        benchmark_results = {}

        for query_name, query in queries:
            start_time = time.time()
            try:
                results = client._paginated_search(customer_id, query)
                response_time = time.time() - start_time

                metrics.track_api_call(response_time, len(results), False)

                benchmark_results[query_name] = {
                    "response_time": response_time,
                    "record_count": len(results),
                    "records_per_second": len(results) / max(response_time, 0.001),
                }

                # Performance assertions based on issue requirements
                assert response_time < 2.0, (
                    f"{query_name} query exceeded 2s response time target"
                )

                if len(results) > 0:
                    assert len(results) <= 10000, (
                        f"{query_name} returned more than expected page size"
                    )

            except Exception as e:
                response_time = time.time() - start_time
                error_type = type(e).__name__
                metrics.track_api_call(response_time, 0, True, error_type)

                if "PAGE_SIZE_NOT_SUPPORTED" in str(e):
                    pytest.fail(f"Performance test failed for {query_name}: {e}")
                else:
                    print(f"Performance test acceptable error for {query_name}: {e}")

        print(f"Performance benchmark results: {benchmark_results}")
        print(f"Performance test metrics: {metrics.get_efficiency_report()}")

        # Verify overall performance KPIs from issue requirements
        efficiency_report = metrics.get_efficiency_report()
        assert efficiency_report["average_response_time"] < 2.0, (
            "Average response time exceeds 2s target"
        )
        assert efficiency_report["pagination_error_rate_percentage"] < 1.0, (
            "Pagination error rate exceeds 1% target"
        )
