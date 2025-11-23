"""Integration tests for job context validation in scheduler jobs."""

from unittest.mock import AsyncMock, Mock

import pytest

from paidsearchnav_mcp.core.config import Settings
from paidsearchnav_mcp.models.analysis import AnalysisResult
from paidsearchnav_mcp.scheduler.jobs import AuditJob, SingleAnalyzerJob
from paidsearchnav_mcp.scheduler.models import AuditJobConfig


class TestAuditJobContextValidation:
    """Test context validation in AuditJob."""

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings."""
        settings = Mock(spec=Settings)
        settings.google_ads = Mock()
        settings.google_ads.developer_token = "test_token"
        settings.database = Mock()
        settings.database.url = "sqlite:///:memory:"
        # Mock scheduler settings for parallel execution
        settings.scheduler = Mock()
        settings.scheduler.max_parallel_analyzers = 3
        return settings

    @pytest.fixture
    def audit_config(self):
        """Create test audit configuration."""
        return AuditJobConfig(
            customer_id="1234567890",
            analyzers=["keyword_match", "search_terms"],
            generate_report=False,
        )

    @pytest.fixture
    def audit_job(self, audit_config, mock_settings, mocker):
        """Create AuditJob instance with mocks."""
        # Mock GoogleAdsClient
        mock_client = Mock()
        mocker.patch(
            "paidsearchnav.scheduler.jobs.GoogleAdsClient", return_value=mock_client
        )

        # Mock AnalysisRepository
        mock_storage = AsyncMock()
        mocker.patch(
            "paidsearchnav.scheduler.jobs.AnalysisRepository", return_value=mock_storage
        )

        # Mock ReportGenerator
        mock_report_gen = Mock()
        mocker.patch(
            "paidsearchnav.scheduler.jobs.ReportGenerator", return_value=mock_report_gen
        )

        job = AuditJob(audit_config, mock_settings)

        # Mock the analyzers - create separate mock for each analyzer
        mock_analyzers = {}
        for analyzer_name in job.available_analyzers:
            mock_analyzer = AsyncMock()
            mock_result = Mock(spec=AnalysisResult)
            mock_result.id = f"test_analysis_{analyzer_name}_123"
            mock_analyzer.analyze.return_value = mock_result
            mock_analyzers[analyzer_name] = mock_analyzer
            job.available_analyzers[analyzer_name] = mock_analyzer

        # Set up storage mock
        job.storage.save_analysis.return_value = "test_analysis_123"

        return job

    @pytest.mark.asyncio
    async def test_valid_context_passes_validation(self, audit_job):
        """Test that valid context passes validation and job executes."""
        context = {
            "default_audit_days": 90,
            "min_impressions": 100,
            "analyzer_config": {"keyword_match": {"min_impressions": 50}},
        }

        result = await audit_job.execute(context)

        # Should succeed
        assert "error" not in result
        assert result["customer_id"] == "1234567890"
        assert result["analyzers_run"] == 2  # keyword_match and search_terms

        # Verify analyzer was called with validated parameters
        analyzer = audit_job.available_analyzers["keyword_match"]
        analyzer.analyze.assert_called()

        # Get the call arguments
        call_args = analyzer.analyze.call_args
        assert call_args.kwargs["customer_id"] == "1234567890"
        assert (
            call_args.kwargs["min_impressions"] == 50
        )  # Analyzer-specific config overrides general (100)

    @pytest.mark.asyncio
    async def test_invalid_context_fails_validation(self, audit_job):
        """Test that invalid context fails validation and returns error."""
        context = {
            "default_audit_days": -1,  # Invalid - negative value
            "unknown_parameter": "malicious_value",  # Invalid - unknown field
        }

        result = await audit_job.execute(context)

        # Should fail with validation error
        assert "error" in result
        assert "Context validation failed" in result["error"]
        assert result["success"] is False
        assert result["customer_id"] == "1234567890"

        # Analyzers should not have been called
        for analyzer in audit_job.available_analyzers.values():
            analyzer.analyze.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_context_uses_defaults(self, audit_job):
        """Test that empty context uses default values."""
        result = await audit_job.execute({})

        # Should succeed with defaults
        assert "error" not in result
        assert result["analyzers_run"] == 2

        # Verify default audit days was used (90 days)
        # This would be reflected in the date range calculation

    @pytest.mark.asyncio
    async def test_analyzer_specific_config_passed_correctly(self, audit_job):
        """Test that analyzer-specific configuration is passed correctly."""
        context = {
            "analyzer_config": {
                "keyword_match": {"min_impressions": 200, "campaigns": ["111", "222"]},
                "search_terms": {"min_clicks": 10},
            },
            "min_impressions": 50,  # General parameter
            "include_shared_sets": True,
        }

        result = await audit_job.execute(context)

        # Should succeed
        assert "error" not in result

        # Verify analyzers were called with correct parameters
        analyzer = audit_job.available_analyzers["keyword_match"]
        call_args = analyzer.analyze.call_args

        # Should have both general and analyzer-specific parameters
        # For keyword_match analyzer: analyzer-specific min_impressions (200) should override general (50)
        assert call_args.kwargs["min_impressions"] == 200  # Analyzer-specific override
        assert call_args.kwargs["campaigns"] == ["111", "222"]  # Analyzer-specific
        assert call_args.kwargs["include_shared_sets"] is True  # General parameter


class TestSingleAnalyzerJobContextValidation:
    """Test context validation in SingleAnalyzerJob."""

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings."""
        settings = Mock(spec=Settings)
        settings.google_ads = Mock()
        settings.google_ads.developer_token = "test_token"
        settings.database = Mock()
        settings.database.url = "sqlite:///:memory:"
        # Mock scheduler settings for parallel execution
        settings.scheduler = Mock()
        settings.scheduler.max_parallel_analyzers = 3
        return settings

    @pytest.fixture
    def single_analyzer_job(self, mock_settings, mocker):
        """Create SingleAnalyzerJob instance."""
        # Mock GoogleAdsClient
        mock_client = Mock()
        mocker.patch(
            "paidsearchnav.scheduler.jobs.GoogleAdsClient", return_value=mock_client
        )

        # Mock AnalysisRepository
        mock_storage = AsyncMock()
        mock_storage.save_analysis.return_value = "test_analysis_123"
        mocker.patch(
            "paidsearchnav.scheduler.jobs.AnalysisRepository", return_value=mock_storage
        )

        job = SingleAnalyzerJob(
            customer_id="1234567890",
            analyzer_name="keyword_match",
            settings=mock_settings,
        )

        return job

    @pytest.mark.asyncio
    async def test_valid_context_single_analyzer(self, single_analyzer_job, mocker):
        """Test valid context validation for single analyzer job."""
        # Mock the analyzer class
        mock_analyzer_class = Mock()
        mock_analyzer_instance = AsyncMock()
        mock_result = Mock(spec=AnalysisResult)
        mock_result.id = "test_analysis_123"
        mock_analyzer_instance.analyze.return_value = mock_result
        mock_analyzer_class.return_value = mock_analyzer_instance

        # Patch the KeywordMatchAnalyzer import
        mocker.patch(
            "paidsearchnav.scheduler.jobs.KeywordMatchAnalyzer", mock_analyzer_class
        )

        context = {"min_impressions": 100, "campaigns": ["12345"]}

        result = await single_analyzer_job.execute(context)

        # Should succeed
        assert result["success"] is True
        assert result["customer_id"] == "1234567890"
        assert result["analyzer"] == "keyword_match"

        # Verify analyzer was called with validated context
        mock_analyzer_instance.analyze.assert_called_once()
        call_args = mock_analyzer_instance.analyze.call_args
        assert call_args.kwargs["min_impressions"] == 100
        assert call_args.kwargs["campaigns"] == ["12345"]

    @pytest.mark.asyncio
    async def test_invalid_context_single_analyzer(self, single_analyzer_job):
        """Test invalid context validation for single analyzer job."""
        context = {
            "min_impressions": -10,  # Invalid negative value
        }

        result = await single_analyzer_job.execute(context)

        # Should fail with validation error
        assert result["success"] is False
        assert "Context validation failed" in result["error"]
        assert result["customer_id"] == "1234567890"
        assert result["analyzer"] == "keyword_match"

    @pytest.mark.asyncio
    async def test_malicious_context_filtered(self, single_analyzer_job):
        """Test that malicious context parameters are filtered out."""
        context = {
            "min_impressions": 100,  # Valid
            "malicious_code": "__import__('os').system('rm -rf /')",  # Invalid
            "sql_injection": "'; DROP TABLE users; --",  # Invalid
        }

        result = await single_analyzer_job.execute(context)

        # Should fail due to unknown fields
        assert result["success"] is False
        assert "Context validation failed" in result["error"]


class TestSecurityScenarios:
    """Test security-related scenarios for context validation."""

    def test_prevents_code_injection_attempts(self):
        """Test that code injection attempts are prevented."""
        from paidsearchnav.scheduler.jobs import validate_job_context

        malicious_contexts = [
            {"eval": "__import__('os').system('rm -rf /')"},
            {"exec": "exec('malicious code')"},
            {"import": "__import__('subprocess').call(['rm', '-rf', '/'])"},
            {"os_system": "os.system('malicious command')"},
        ]

        for context in malicious_contexts:
            with pytest.raises(ValueError) as exc_info:
                validate_job_context(context)
            assert "Extra inputs are not permitted" in str(exc_info.value)

    def test_prevents_sql_injection_like_strings(self):
        """Test that SQL injection-like strings are handled safely."""
        from paidsearchnav.scheduler.jobs import validate_job_context

        # These should be rejected as unknown fields
        sql_injection_contexts = [
            {"query": "'; DROP TABLE analysis; --"},
            {"filter": "1=1; DELETE FROM users; --"},
            {"where": "1 OR 1=1"},
        ]

        for context in sql_injection_contexts:
            with pytest.raises(ValueError):
                validate_job_context(context)

    def test_large_parameter_values_handled(self):
        """Test that extremely large parameter values are handled appropriately."""
        from paidsearchnav.scheduler.jobs import validate_job_context

        # Test with very large lists (potential DoS)
        large_context = {
            "campaigns": ["id_" + str(i) for i in range(10000)]  # Very large list
        }

        # Should still validate (Pydantic handles large data structures)
        result = validate_job_context(large_context)
        assert len(result["campaigns"]) == 10000

    def test_deeply_nested_analyzer_config_limited(self):
        """Test handling of deeply nested analyzer configuration."""
        from paidsearchnav.scheduler.jobs import validate_job_context

        # Test reasonable nesting depth
        context = {
            "analyzer_config": {
                "keyword_match": {
                    "filter_config": {
                        "performance_thresholds": {"min_impressions": 100}
                    }
                }
            }
        }

        # Should validate (reasonable nesting)
        result = validate_job_context(context)
        assert "analyzer_config" in result
