"""Tests for scheduler jobs."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from paidsearchnav.core.config import Settings
from paidsearchnav.scheduler.interfaces import JobType
from paidsearchnav.scheduler.jobs import AuditJob, SingleAnalyzerJob
from paidsearchnav.scheduler.models import AuditJobConfig


@pytest.fixture
def mock_settings():
    """Create mock settings."""
    settings = Mock(spec=Settings)
    settings.environment = "test"
    # Add scheduler config for parallel execution
    settings.scheduler = Mock()
    settings.scheduler.max_parallel_analyzers = 3
    return settings


@pytest.fixture
def mock_google_ads_client():
    """Create mock Google Ads client."""
    with patch("paidsearchnav.scheduler.jobs.GoogleAdsClient") as mock_class:
        # Mock the class itself to avoid instantiation issues
        mock_instance = Mock()
        mock_class.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_storage():
    """Create mock storage."""
    with patch("paidsearchnav.scheduler.jobs.AnalysisRepository") as mock_class:
        storage = mock_class.return_value
        storage.save_analysis = AsyncMock(return_value="analysis_123")
        yield storage


@pytest.fixture
def mock_report_generator():
    """Create mock report generator."""
    with patch("paidsearchnav.scheduler.jobs.ReportGenerator") as mock_class:
        generator = mock_class.return_value
        generator.generate = Mock(return_value=b"<html>Report</html>")
        yield generator


@pytest.fixture
def mock_analyzers():
    """Create mock analyzers."""
    analyzers = {}

    for name in [
        "keyword_match",
        "search_terms",
        "negative_conflicts",
        "geo_performance",
        "pmax",
        "shared_negatives",
    ]:
        analyzer = Mock()
        analyzer.analyze = AsyncMock(
            return_value=Mock(
                id=f"{name}_result_123",
                analyzer_name=name,
                findings=[],
                recommendations=[],
            )
        )
        analyzers[name] = analyzer

    with patch.multiple(
        "paidsearchnav.scheduler.jobs",
        KeywordMatchAnalyzer=Mock(return_value=analyzers["keyword_match"]),
        SearchTermsAnalyzer=Mock(return_value=analyzers["search_terms"]),
        NegativeConflictAnalyzer=Mock(return_value=analyzers["negative_conflicts"]),
        GeoPerformanceAnalyzer=Mock(return_value=analyzers["geo_performance"]),
        PerformanceMaxAnalyzer=Mock(return_value=analyzers["pmax"]),
        SharedNegativeValidatorAnalyzer=Mock(
            return_value=analyzers["shared_negatives"]
        ),
    ):
        yield analyzers


class TestAuditJob:
    """Test AuditJob class."""

    def setup_method(self):
        """Set up test fixtures."""
        # Patch GoogleAdsClient at module level
        self.gads_patcher = patch("paidsearchnav.scheduler.jobs.GoogleAdsClient")
        self.mock_gads_class = self.gads_patcher.start()
        self.mock_gads_class.return_value = MagicMock()

        # Patch ReportGenerator
        self.report_patcher = patch("paidsearchnav.scheduler.jobs.ReportGenerator")
        self.mock_report_class = self.report_patcher.start()
        self.mock_report_class.return_value = MagicMock()

        # Patch AnalysisRepository
        self.repo_patcher = patch("paidsearchnav.scheduler.jobs.AnalysisRepository")
        self.mock_repo_class = self.repo_patcher.start()
        self.mock_repo_class.return_value = MagicMock()

    def teardown_method(self):
        """Clean up patches."""
        self.gads_patcher.stop()
        self.report_patcher.stop()
        self.repo_patcher.stop()

    @patch("paidsearchnav.scheduler.jobs.GoogleAdsClient")
    @patch("paidsearchnav.scheduler.jobs.AnalysisRepository")
    @patch("paidsearchnav.scheduler.jobs.ReportGenerator")
    def test_init(self, mock_report_gen, mock_repo, mock_gads_client, mock_settings):
        """Test job initialization."""
        config = AuditJobConfig(
            customer_id="123456789",
            analyzers=["keyword_match", "search_terms"],
        )

        job = AuditJob(config, mock_settings)

        assert job.config == config
        assert job.settings == mock_settings
        assert job.get_job_id().startswith("audit_123456789_")

    @patch("paidsearchnav.scheduler.jobs.GoogleAdsClient")
    @patch("paidsearchnav.scheduler.jobs.AnalysisRepository")
    @patch("paidsearchnav.scheduler.jobs.ReportGenerator")
    def test_get_job_type_quarterly(
        self, mock_report_gen, mock_repo, mock_gads_client, mock_settings
    ):
        """Test job type for quarterly audit."""
        config = AuditJobConfig(
            customer_id="123456789",
            # No start/end date = quarterly
        )

        job = AuditJob(config, mock_settings)
        assert job.get_job_type() == JobType.QUARTERLY_AUDIT

    @patch("paidsearchnav.scheduler.jobs.GoogleAdsClient")
    @patch("paidsearchnav.scheduler.jobs.AnalysisRepository")
    @patch("paidsearchnav.scheduler.jobs.ReportGenerator")
    def test_get_job_type_on_demand(
        self, mock_report_gen, mock_repo, mock_gads_client, mock_settings
    ):
        """Test job type for on-demand audit."""
        config = AuditJobConfig(
            customer_id="123456789",
            start_date=datetime.utcnow() - timedelta(days=30),
            end_date=datetime.utcnow(),
        )

        job = AuditJob(config, mock_settings)
        assert job.get_job_type() == JobType.ON_DEMAND_AUDIT

    @pytest.mark.asyncio
    async def test_execute_with_specified_analyzers(
        self,
        mock_settings,
        mock_analyzers,
        mock_storage,
        mock_report_generator,
    ):
        """Test executing audit with specific analyzers."""
        config = AuditJobConfig(
            customer_id="123456789",
            analyzers=["keyword_match", "search_terms"],
            generate_report=True,
            report_formats=["html"],
        )

        with patch("paidsearchnav.scheduler.jobs.GoogleAdsClient"):
            job = AuditJob(config, mock_settings)

        # Execute job
        result = await job.execute({})

        # Verify analyzers were run
        assert mock_analyzers["keyword_match"].analyze.called
        assert mock_analyzers["search_terms"].analyze.called
        assert not mock_analyzers["negative_conflicts"].analyze.called

        # Verify results were saved
        assert mock_storage.save_analysis.call_count == 2

        # Verify report was generated
        assert mock_report_generator.generate.called

        # Check result
        assert result["customer_id"] == "123456789"
        assert result["analyzers_run"] == 2
        assert result["analyzers_requested"] == 2
        assert len(result["errors"]) == 0
        assert result["report"] is not None

    @pytest.mark.asyncio
    async def test_execute_with_all_analyzers(
        self,
        mock_settings,
        mock_analyzers,
        mock_storage,
    ):
        """Test executing audit with all analyzers."""
        config = AuditJobConfig(
            customer_id="123456789",
            analyzers=None,  # Run all
            generate_report=False,
        )

        job = AuditJob(config, mock_settings)

        # Execute job
        result = await job.execute({})

        # All available analyzers should be run
        assert result["analyzers_run"] == 6  # All 6 analyzers
        assert result["report"] is None  # No report requested

    @pytest.mark.asyncio
    async def test_execute_with_analyzer_error(
        self,
        mock_settings,
        mock_analyzers,
        mock_storage,
    ):
        """Test handling analyzer errors."""
        # Make one analyzer fail
        mock_analyzers["search_terms"].analyze.side_effect = Exception(
            "Analyzer failed"
        )

        config = AuditJobConfig(
            customer_id="123456789",
            analyzers=["keyword_match", "search_terms"],
        )

        job = AuditJob(config, mock_settings)

        # Execute job
        result = await job.execute({})

        # Should complete with partial results
        assert result["analyzers_run"] == 1  # Only keyword_match succeeded
        assert result["analyzers_requested"] == 2
        assert len(result["errors"]) == 1
        assert result["errors"][0]["analyzer"] == "search_terms"
        assert "Analyzer failed" in result["errors"][0]["error"]

    @pytest.mark.asyncio
    async def test_execute_with_date_range(
        self,
        mock_settings,
        mock_analyzers,
    ):
        """Test executing with custom date range."""
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 3, 31)

        config = AuditJobConfig(
            customer_id="123456789",
            analyzers=["keyword_match"],
            start_date=start_date,
            end_date=end_date,
        )

        job = AuditJob(config, mock_settings)

        # Execute job
        await job.execute({})

        # Verify date range was passed to analyzer
        call_args = mock_analyzers["keyword_match"].analyze.call_args
        assert call_args.kwargs["start_date"] == start_date
        assert call_args.kwargs["end_date"] == end_date


class TestSingleAnalyzerJob:
    """Test SingleAnalyzerJob class."""

    def setup_method(self):
        """Set up test fixtures."""
        # Patch GoogleAdsClient at module level
        self.gads_patcher = patch("paidsearchnav.scheduler.jobs.GoogleAdsClient")
        self.mock_gads_class = self.gads_patcher.start()
        self.mock_gads_class.return_value = MagicMock()

        # Patch ReportGenerator
        self.report_patcher = patch("paidsearchnav.scheduler.jobs.ReportGenerator")
        self.mock_report_class = self.report_patcher.start()
        self.mock_report_class.return_value = MagicMock()

        # Patch AnalysisRepository
        self.repo_patcher = patch("paidsearchnav.scheduler.jobs.AnalysisRepository")
        self.mock_repo_class = self.repo_patcher.start()
        self.mock_repo_class.return_value = MagicMock()

    def teardown_method(self):
        """Clean up patches."""
        self.gads_patcher.stop()
        self.report_patcher.stop()
        self.repo_patcher.stop()

    @patch("paidsearchnav.scheduler.jobs.GoogleAdsClient")
    @patch("paidsearchnav.scheduler.jobs.AnalysisRepository")
    @patch("paidsearchnav.scheduler.jobs.ReportGenerator")
    def test_init(self, mock_report_gen, mock_repo, mock_gads_client, mock_settings):
        """Test job initialization."""
        job = SingleAnalyzerJob(
            customer_id="123456789",
            analyzer_name="keyword_match",
            settings=mock_settings,
        )

        assert job.customer_id == "123456789"
        assert job.analyzer_name == "keyword_match"
        assert job.get_job_type() == JobType.SINGLE_ANALYZER
        assert job.get_job_id().startswith("analyzer_keyword_match_123456789_")

    @pytest.mark.asyncio
    async def test_execute_success(
        self,
        mock_settings,
        mock_analyzers,
        mock_storage,
    ):
        """Test successful single analyzer execution."""
        job = SingleAnalyzerJob(
            customer_id="123456789",
            analyzer_name="keyword_match",
            settings=mock_settings,
        )

        # Execute job
        result = await job.execute({})

        # Verify analyzer was run
        assert mock_analyzers["keyword_match"].analyze.called

        # Verify result was saved
        assert mock_storage.save_analysis.called

        # Check result
        assert result["customer_id"] == "123456789"
        assert result["analyzer"] == "keyword_match"
        assert result["success"] is True
        assert result["analysis_id"] == "analysis_123"

    @pytest.mark.asyncio
    async def test_execute_with_error(
        self,
        mock_settings,
        mock_analyzers,
    ):
        """Test handling analyzer error."""
        # Make analyzer fail
        mock_analyzers["keyword_match"].analyze.side_effect = Exception(
            "Analysis failed"
        )

        job = SingleAnalyzerJob(
            customer_id="123456789",
            analyzer_name="keyword_match",
            settings=mock_settings,
        )

        # Execute job
        result = await job.execute({})

        # Check error result
        assert result["success"] is False
        assert "Analysis failed" in result["error"]

    @pytest.mark.asyncio
    @patch("paidsearchnav.scheduler.jobs.GoogleAdsClient")
    @patch("paidsearchnav.scheduler.jobs.AnalysisRepository")
    @patch("paidsearchnav.scheduler.jobs.ReportGenerator")
    async def test_execute_unknown_analyzer(
        self, mock_report_gen, mock_repo, mock_gads_client, mock_settings
    ):
        """Test executing with unknown analyzer."""
        job = SingleAnalyzerJob(
            customer_id="123456789",
            analyzer_name="unknown_analyzer",
            settings=mock_settings,
        )

        # Should raise ValueError
        with pytest.raises(ValueError, match="Unknown analyzer: unknown_analyzer"):
            await job.execute({})

    @pytest.mark.asyncio
    async def test_execute_with_context(
        self,
        mock_settings,
        mock_analyzers,
    ):
        """Test passing context to analyzer."""
        job = SingleAnalyzerJob(
            customer_id="123456789",
            analyzer_name="keyword_match",
            settings=mock_settings,
        )

        # Execute with context
        context = {
            "min_impressions": 100,
            "include_paused": False,
        }
        await job.execute(context)

        # Verify context was passed
        call_args = mock_analyzers["keyword_match"].analyze.call_args
        assert call_args.kwargs["min_impressions"] == 100
        assert call_args.kwargs["include_paused"] is False
