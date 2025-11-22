"""Tests for quarterly data extraction scripts."""

from unittest.mock import Mock

import pytest

from paidsearchnav.platforms.google.client import GoogleAdsClient
from paidsearchnav.platforms.google.scripts.base import ScriptConfig, ScriptType
from paidsearchnav.platforms.google.scripts.quarterly_data_extraction import (
    CampaignPerformanceScript,
    GeographicPerformanceScript,
    KeywordPerformanceScript,
    SearchTermsPerformanceScript,
)


class TestSearchTermsPerformanceScript:
    """Test SearchTermsPerformanceScript functionality."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock Google Ads client."""
        return Mock(spec=GoogleAdsClient)

    @pytest.fixture
    def script_config(self):
        """Create script configuration for testing."""
        return ScriptConfig(
            name="test_search_terms_script",
            type=ScriptType.NEGATIVE_KEYWORD,
            description="Test search terms performance extraction",
            parameters={
                "date_range": "LAST_30_DAYS",
                "customer_id": "1234567890",  # Valid 10-digit customer ID
                "include_geographic_data": True,
                "min_clicks": 1,
                "min_cost": 0.01,
            },
        )

    @pytest.fixture
    def search_terms_script(self, mock_client, script_config):
        """Create SearchTermsPerformanceScript instance."""
        return SearchTermsPerformanceScript(mock_client, script_config)

    def test_script_initialization(self, search_terms_script):
        """Test script initialization."""
        assert search_terms_script.config.name == "test_search_terms_script"
        assert search_terms_script.config.type == ScriptType.NEGATIVE_KEYWORD

    def test_required_parameters(self, search_terms_script):
        """Test required parameters validation."""
        required_params = search_terms_script.get_required_parameters()
        assert "date_range" in required_params
        assert "customer_id" in required_params

    def test_parameter_validation_success(self, search_terms_script):
        """Test successful parameter validation."""
        assert search_terms_script.validate_parameters() is True

    def test_parameter_validation_failure(self, mock_client):
        """Test parameter validation failure."""
        config = ScriptConfig(
            name="test_script",
            type=ScriptType.NEGATIVE_KEYWORD,
            description="Test script",
            parameters={},  # Missing required parameters
        )
        script = SearchTermsPerformanceScript(mock_client, config)
        assert script.validate_parameters() is False

    def test_generate_script(self, search_terms_script):
        """Test script generation."""
        script_code = search_terms_script.generate_script()

        # Verify script contains expected elements
        assert "function main()" in script_code
        assert "SEARCH_QUERY_PERFORMANCE_REPORT" in script_code
        assert "LAST_30_DAYS" in script_code
        assert "detectLocalIntent" in script_code
        assert "classifyLocationType" in script_code

    def test_generate_script_without_geo_data(self, mock_client):
        """Test script generation without geographic data."""
        config = ScriptConfig(
            name="test_script",
            type=ScriptType.NEGATIVE_KEYWORD,
            description="Test script",
            parameters={
                "date_range": "YESTERDAY",
                "customer_id": "1234567890",
                "include_geographic_data": False,
            },
        )
        script = SearchTermsPerformanceScript(mock_client, config)
        script_code = script.generate_script()

        assert "includeGeo = false" in script_code

    def test_process_results(self, search_terms_script):
        """Test results processing."""
        results = {
            "execution_time": 45.5,
            "rows_processed": 1500,
            "file_name": "search_terms_performance_2024-01-01_12-00.csv",
            "date_range": "LAST_30_DAYS",
            "warnings": ["Some items required manual review"],
        }

        processed = search_terms_script.process_results(results)

        assert processed["status"] == "completed"
        assert processed["execution_time"] == 45.5
        assert processed["rows_processed"] == 1500
        assert processed["changes_made"] == 0  # Data extraction, no changes
        assert len(processed["warnings"]) == 1
        assert processed["details"]["script_type"] == "search_terms_performance"


class TestKeywordPerformanceScript:
    """Test KeywordPerformanceScript functionality."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock Google Ads client."""
        return Mock(spec=GoogleAdsClient)

    @pytest.fixture
    def script_config(self):
        """Create script configuration for testing."""
        return ScriptConfig(
            name="test_keywords_script",
            type=ScriptType.NEGATIVE_KEYWORD,
            description="Test keyword performance extraction",
            parameters={
                "date_range": "LAST_30_DAYS",
                "customer_id": "1234567890",
                "include_quality_score": True,
                "min_impressions": 10,
            },
        )

    @pytest.fixture
    def keywords_script(self, mock_client, script_config):
        """Create KeywordPerformanceScript instance."""
        return KeywordPerformanceScript(mock_client, script_config)

    def test_generate_script(self, keywords_script):
        """Test keyword script generation."""
        script_code = keywords_script.generate_script()

        # Verify script contains expected elements
        assert "function main()" in script_code
        assert "KEYWORDS_PERFORMANCE_REPORT" in script_code
        assert "generateBidRecommendation" in script_code
        assert "includeQualityScore = true" in script_code

    def test_generate_script_without_quality_score(self, mock_client):
        """Test script generation without quality score."""
        config = ScriptConfig(
            name="test_script",
            type=ScriptType.NEGATIVE_KEYWORD,
            description="Test script",
            parameters={
                "date_range": "LAST_7_DAYS",
                "customer_id": "1234567890",
                "include_quality_score": False,
            },
        )
        script = KeywordPerformanceScript(mock_client, config)
        script_code = script.generate_script()

        assert "includeQualityScore = false" in script_code

    def test_process_results_with_bid_recommendations(self, keywords_script):
        """Test results processing with bid recommendations."""
        results = {
            "execution_time": 30.2,
            "rows_processed": 800,
            "changes_made": 25,  # Bid recommendations
            "file_name": "keyword_performance_2024-01-01_12-00.csv",
            "date_range": "LAST_30_DAYS",
        }

        processed = keywords_script.process_results(results)

        assert processed["status"] == "completed"
        assert processed["changes_made"] == 25
        assert processed["details"]["bid_recommendations"] == 25


class TestGeographicPerformanceScript:
    """Test GeographicPerformanceScript functionality."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock Google Ads client."""
        return Mock(spec=GoogleAdsClient)

    @pytest.fixture
    def script_config(self):
        """Create script configuration for testing."""
        return ScriptConfig(
            name="test_geo_script",
            type=ScriptType.NEGATIVE_KEYWORD,
            description="Test geographic performance extraction",
            parameters={
                "date_range": "LAST_30_DAYS",
                "customer_id": "1234567890",
                "target_locations": ["Dallas", "San Antonio", "Atlanta"],
                "min_clicks": 1,
            },
        )

    @pytest.fixture
    def geo_script(self, mock_client, script_config):
        """Create GeographicPerformanceScript instance."""
        return GeographicPerformanceScript(mock_client, script_config)

    def test_generate_script(self, geo_script):
        """Test geographic script generation."""
        script_code = geo_script.generate_script()

        # Verify script contains expected elements
        assert "function main()" in script_code
        assert "GEO_PERFORMANCE_REPORT" in script_code
        assert "Dallas" in script_code
        assert "San Antonio" in script_code
        assert "calculateDistance" in script_code
        assert "rankLocationsByPerformance" in script_code

    def test_process_results(self, geo_script):
        """Test geographic results processing."""
        results = {
            "execution_time": 25.8,
            "rows_processed": 200,
            "unique_locations": 15,
            "file_name": "geographic_performance_2024-01-01_12-00.csv",
            "date_range": "LAST_30_DAYS",
        }

        processed = geo_script.process_results(results)

        assert processed["status"] == "completed"
        assert processed["details"]["unique_locations"] == 15
        assert processed["details"]["target_locations"] == [
            "Dallas",
            "San Antonio",
            "Atlanta",
        ]


class TestCampaignPerformanceScript:
    """Test CampaignPerformanceScript functionality."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock Google Ads client."""
        return Mock(spec=GoogleAdsClient)

    @pytest.fixture
    def script_config(self):
        """Create script configuration for testing."""
        return ScriptConfig(
            name="test_campaign_script",
            type=ScriptType.NEGATIVE_KEYWORD,
            description="Test campaign performance extraction",
            parameters={
                "date_range": "LAST_30_DAYS",
                "customer_id": "1234567890",
                "include_device_data": True,
                "include_demographics": True,
            },
        )

    @pytest.fixture
    def campaign_script(self, mock_client, script_config):
        """Create CampaignPerformanceScript instance."""
        return CampaignPerformanceScript(mock_client, script_config)

    def test_generate_script_with_all_data(self, campaign_script):
        """Test campaign script generation with all data types."""
        script_code = campaign_script.generate_script()

        # Verify script contains expected elements
        assert "function main()" in script_code
        assert "CAMPAIGN_PERFORMANCE_REPORT" in script_code
        assert "includeDeviceData = true" in script_code
        assert "includeDemographics = true" in script_code
        assert "getDevicePerformance" in script_code
        assert "getDemographicPerformance" in script_code

    def test_generate_script_minimal_data(self, mock_client):
        """Test campaign script generation with minimal data."""
        config = ScriptConfig(
            name="test_script",
            type=ScriptType.NEGATIVE_KEYWORD,
            description="Test script",
            parameters={
                "date_range": "YESTERDAY",
                "customer_id": "1234567890",
                "include_device_data": False,
                "include_demographics": False,
            },
        )
        script = CampaignPerformanceScript(mock_client, config)
        script_code = script.generate_script()

        assert "includeDeviceData = false" in script_code
        assert "includeDemographics = false" in script_code

    def test_process_results_with_recommendations(self, campaign_script):
        """Test campaign results processing with budget recommendations."""
        results = {
            "execution_time": 35.7,
            "rows_processed": 15,
            "changes_made": 5,  # Budget recommendations
            "file_name": "campaign_performance_2024-01-01_12-00.csv",
            "date_range": "LAST_30_DAYS",
        }

        processed = campaign_script.process_results(results)

        assert processed["status"] == "completed"
        assert processed["changes_made"] == 5
        assert processed["details"]["budget_recommendations"] == 5
        assert processed["details"]["device_data_included"] is True
        assert processed["details"]["demographics_included"] is True


class TestScriptIntegration:
    """Test script integration scenarios."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock Google Ads client."""
        return Mock(spec=GoogleAdsClient)

    def test_all_scripts_have_consistent_interface(self, mock_client):
        """Test that all scripts have consistent interface."""
        script_classes = [
            SearchTermsPerformanceScript,
            KeywordPerformanceScript,
            GeographicPerformanceScript,
            CampaignPerformanceScript,
        ]

        for script_class in script_classes:
            config = ScriptConfig(
                name=f"test_{script_class.__name__.lower()}",
                type=ScriptType.NEGATIVE_KEYWORD,
                description="Test script",
                parameters={
                    "date_range": "LAST_30_DAYS",
                    "customer_id": "1234567890",
                },
            )

            script = script_class(mock_client, config)

            # Test interface consistency
            assert hasattr(script, "get_required_parameters")
            assert hasattr(script, "validate_parameters")
            assert hasattr(script, "generate_script")
            assert hasattr(script, "process_results")

            # Test that required methods return expected types
            required_params = script.get_required_parameters()
            assert isinstance(required_params, list)
            assert "customer_id" in required_params
            assert "date_range" in required_params

    def test_script_metadata_generation(self, mock_client):
        """Test script metadata generation."""
        config = ScriptConfig(
            name="test_metadata_script",
            type=ScriptType.NEGATIVE_KEYWORD,
            description="Test metadata generation",
            parameters={
                "date_range": "LAST_30_DAYS",
                "customer_id": "1234567890",
            },
        )

        script = SearchTermsPerformanceScript(mock_client, config)
        metadata = script.get_script_metadata()

        assert metadata["name"] == "test_metadata_script"
        assert metadata["type"] == "negative_keyword"
        assert metadata["description"] == "Test metadata generation"
        assert "created_at" in metadata
        assert metadata["parameters"]["customer_id"] == "1234567890"

    def test_scripts_with_custom_parameters(self, mock_client):
        """Test scripts with various custom parameters."""

        # Test search terms with custom parameters
        search_config = ScriptConfig(
            name="custom_search_terms",
            type=ScriptType.NEGATIVE_KEYWORD,
            description="Custom search terms script",
            parameters={
                "date_range": "LAST_7_DAYS",
                "customer_id": "1234567890",
                "include_geographic_data": False,
                "min_clicks": 5,
                "min_cost": 1.00,
            },
        )

        search_script = SearchTermsPerformanceScript(mock_client, search_config)
        search_code = search_script.generate_script()

        assert "LAST_7_DAYS" in search_code
        assert "minClicks = 5" in search_code
        assert "minCost = 1" in search_code
        assert "includeGeo = false" in search_code

        # Test keywords with custom parameters
        keyword_config = ScriptConfig(
            name="custom_keywords",
            type=ScriptType.NEGATIVE_KEYWORD,
            description="Custom keywords script",
            parameters={
                "date_range": "YESTERDAY",
                "customer_id": "1234567890",
                "include_quality_score": False,
                "min_impressions": 50,
            },
        )

        keyword_script = KeywordPerformanceScript(mock_client, keyword_config)
        keyword_code = keyword_script.generate_script()

        assert "YESTERDAY" in keyword_code
        assert "minImpressions = 50" in keyword_code
        assert "includeQualityScore = false" in keyword_code

    def test_error_handling_in_results_processing(self, mock_client):
        """Test error handling in results processing."""
        config = ScriptConfig(
            name="test_error_handling",
            type=ScriptType.NEGATIVE_KEYWORD,
            description="Test error handling",
            parameters={
                "date_range": "LAST_30_DAYS",
                "customer_id": "1234567890",
            },
        )

        script = SearchTermsPerformanceScript(mock_client, config)

        # Test with incomplete results
        incomplete_results = {
            "execution_time": 10.5,
            # Missing other fields
        }

        processed = script.process_results(incomplete_results)

        assert processed["status"] == "completed"
        assert processed["execution_time"] == 10.5
        assert processed["rows_processed"] == 0  # Default value
        assert processed["changes_made"] == 0
        assert processed["details"]["file_name"] == ""  # Default value

    def test_quota_exceeded_error_handling(self, mock_client):
        """Test quota exceeded error handling."""
        config = ScriptConfig(
            name="test_quota_error",
            type=ScriptType.NEGATIVE_KEYWORD,
            description="Test quota error handling",
            parameters={
                "date_range": "LAST_30_DAYS",
                "customer_id": "1234567890",
            },
        )

        script = SearchTermsPerformanceScript(mock_client, config)

        # Test quota exceeded error
        quota_error_results = {
            "success": False,
            "rows_processed": 150,
            "changes_made": 0,
            "error": "Google Ads API quota exceeded after 3 retries",
            "error_type": "QUOTA_EXCEEDED",
            "date_range": "LAST_30_DAYS",
        }

        processed = script.process_results(quota_error_results)

        assert processed["status"] == "failed"
        assert processed["rows_processed"] == 150
        assert len(processed["errors"]) == 1
        assert "quota exceeded" in processed["errors"][0].lower()
        assert len(processed["warnings"]) == 1
        assert "reducing date range" in processed["warnings"][0].lower()
        assert processed["details"]["error_type"] == "QUOTA_EXCEEDED"

    def test_authentication_error_handling(self, mock_client):
        """Test authentication error handling."""
        config = ScriptConfig(
            name="test_auth_error",
            type=ScriptType.NEGATIVE_KEYWORD,
            description="Test auth error handling",
            parameters={
                "date_range": "LAST_30_DAYS",
                "customer_id": "1234567890",
            },
        )

        script = SearchTermsPerformanceScript(mock_client, config)

        # Test authentication error
        auth_error_results = {
            "success": False,
            "rows_processed": 0,
            "changes_made": 0,
            "error": "Authentication failed: Invalid credentials",
            "error_type": "AUTH_ERROR",
            "date_range": "LAST_30_DAYS",
        }

        processed = script.process_results(auth_error_results)

        assert processed["status"] == "failed"
        assert processed["rows_processed"] == 0
        assert len(processed["errors"]) == 1
        assert "authentication error" in processed["errors"][0].lower()
        assert len(processed["warnings"]) == 1
        assert "credentials" in processed["warnings"][0].lower()
        assert processed["details"]["error_type"] == "AUTH_ERROR"

    def test_general_error_handling(self, mock_client):
        """Test general error handling."""
        config = ScriptConfig(
            name="test_general_error",
            type=ScriptType.NEGATIVE_KEYWORD,
            description="Test general error handling",
            parameters={
                "date_range": "LAST_30_DAYS",
                "customer_id": "1234567890",
            },
        )

        script = SearchTermsPerformanceScript(mock_client, config)

        # Test general error
        general_error_results = {
            "success": False,
            "rows_processed": 25,
            "changes_made": 0,
            "error": "Unexpected API response format",
            "error_type": "GENERAL_ERROR",
            "date_range": "LAST_30_DAYS",
        }

        processed = script.process_results(general_error_results)

        assert processed["status"] == "failed"
        assert processed["rows_processed"] == 25
        assert len(processed["errors"]) == 1
        assert processed["errors"][0] == "Unexpected API response format"
        assert len(processed["warnings"]) == 0  # No warnings for general errors
        assert processed["details"]["error_type"] == "GENERAL_ERROR"

    def test_script_generation_with_configurable_location_indicators(self, mock_client):
        """Test script generation with configurable location indicators."""
        config = ScriptConfig(
            name="test_configurable_locations",
            type=ScriptType.NEGATIVE_KEYWORD,
            description="Test configurable location indicators",
            parameters={
                "date_range": "LAST_30_DAYS",
                "customer_id": "1234567890",
                "location_indicators": [
                    "orlando",
                    "tampa",
                    "miami",
                    "florida",
                    "fl",
                    "gym near",
                ],
            },
        )

        script = SearchTermsPerformanceScript(mock_client, config)
        script_code = script.generate_script()

        # Verify custom location indicators are included
        assert "orlando" in script_code
        assert "tampa" in script_code
        assert "miami" in script_code
        assert "florida" in script_code

    def test_script_generation_with_pagination_and_retry(self, mock_client):
        """Test script generation includes pagination and retry logic."""
        config = ScriptConfig(
            name="test_pagination_retry",
            type=ScriptType.NEGATIVE_KEYWORD,
            description="Test pagination and retry logic",
            parameters={
                "date_range": "LAST_30_DAYS",
                "customer_id": "1234567890",
            },
        )

        script = SearchTermsPerformanceScript(mock_client, config)
        script_code = script.generate_script()

        # Verify pagination elements
        assert "pageToken" in script_code
        assert "pageSize: 10000" in script_code
        assert "do {" in script_code and "} while (pageToken)" in script_code

        # Verify retry logic
        assert "retryCount" in script_code
        assert "maxRetries" in script_code
        assert "Utilities.sleep" in script_code
        assert "exponential backoff" in script_code.lower() or "Math.pow" in script_code

        # Verify quota error handling
        assert "QUOTA_EXCEEDED" in script_code
        assert "RATE_LIMIT_EXCEEDED" in script_code
        assert "quotaDelay" in script_code

    def test_script_generation_with_v20_gaql_syntax(self, mock_client):
        """Test script generation uses v20 GAQL syntax."""
        config = ScriptConfig(
            name="test_v20_gaql",
            type=ScriptType.NEGATIVE_KEYWORD,
            description="Test v20 GAQL syntax",
            parameters={
                "date_range": "LAST_30_DAYS",
                "customer_id": "1234567890",
            },
        )

        script = SearchTermsPerformanceScript(mock_client, config)
        script_code = script.generate_script()

        # Verify v20 GAQL syntax is used
        assert "AdsApp.search(" in script_code
        assert "gaqlQuery" in script_code
        assert "search_term_view" in script_code
        assert "campaign.name" in script_code
        assert "metrics.clicks" in script_code

        # Verify deprecated syntax is NOT used
        assert "AdsApp.report(" not in script_code
        assert "SEARCH_QUERY_PERFORMANCE_REPORT" not in script_code

    def test_streaming_csv_writer_integration(self, mock_client):
        """Test streaming CSV writer integration for large datasets."""
        config = ScriptConfig(
            name="test_streaming_csv",
            type=ScriptType.NEGATIVE_KEYWORD,
            description="Test streaming CSV writer",
            parameters={
                "date_range": "LAST_30_DAYS",
                "customer_id": "1234567890",
            },
        )

        script = SearchTermsPerformanceScript(mock_client, config)
        script_code = script.generate_script()

        # Verify streaming CSV logic
        assert "streamingCSVWriter" in script_code
        assert "processedRows > 5000" in script_code
        assert "Large dataset detected" in script_code
        assert "chunkSize" in script_code
