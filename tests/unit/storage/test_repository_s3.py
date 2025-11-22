"""Tests for S3 file integration in AnalysisRepository."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from paidsearchnav.core.config import Settings
from paidsearchnav.core.models.analysis import (
    AnalysisMetrics,
    AnalysisResult,
    Recommendation,
    RecommendationPriority,
    RecommendationType,
)
from paidsearchnav.core.models.audit_files import (
    AnalysisWithFiles,
    ArchiveReport,
    AuditFileSet,
    AuditSummary,
    FileCategory,
    S3FileReference,
)
from paidsearchnav.storage.repository import AnalysisRepository


@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    return Settings(
        environment="development",
        debug=True,
        data_dir="/tmp/test_data",
    )


@pytest.fixture
def sample_analysis_result():
    """Create a sample analysis result for testing."""
    return AnalysisResult(
        customer_id="1234567890",
        analysis_type="search_terms",
        analyzer_name="SearchTermAnalyzer",
        start_date=datetime(2024, 1, 1),
        end_date=datetime(2024, 1, 31),
        status="completed",
        metrics=AnalysisMetrics(
            total_keywords_analyzed=100,
            total_search_terms_analyzed=500,
            potential_cost_savings=150.0,
            potential_conversion_increase=10.5,
        ),
        recommendations=[
            Recommendation(
                type=RecommendationType.ADD_NEGATIVE,
                priority=RecommendationPriority.HIGH,
                title="Add negative keyword",
                description="Add 'free' as negative keyword",
                estimated_cost_savings=50.0,
            )
        ],
    )


@pytest.fixture
def sample_input_files():
    """Create sample input files for testing."""
    return [
        S3FileReference(
            file_path="s3://bucket/customer/account/input/search_terms.csv",
            file_name="search_terms.csv",
            file_size=1024,
            content_type="text/csv",
            checksum="abc123",
            upload_timestamp=datetime.utcnow(),
            file_category=FileCategory.INPUT_CSV,
        ),
        S3FileReference(
            file_path="s3://bucket/customer/account/input/keywords.csv",
            file_name="keywords.csv",
            file_size=512,
            content_type="text/csv",
            checksum="def456",
            upload_timestamp=datetime.utcnow(),
            file_category=FileCategory.INPUT_KEYWORDS,
        ),
    ]


@pytest.fixture
def sample_output_files():
    """Create sample output files for testing."""
    return [
        S3FileReference(
            file_path="s3://bucket/customer/account/output/report.pdf",
            file_name="report.pdf",
            file_size=2048,
            content_type="application/pdf",
            checksum="ghi789",
            upload_timestamp=datetime.utcnow(),
            file_category=FileCategory.OUTPUT_REPORT,
        ),
        S3FileReference(
            file_path="s3://bucket/customer/account/output/negative_keywords.js",
            file_name="negative_keywords.js",
            file_size=256,
            content_type="application/javascript",
            checksum="jkl012",
            upload_timestamp=datetime.utcnow(),
            file_category=FileCategory.OUTPUT_SCRIPTS,
        ),
    ]


class TestAnalysisRepositoryS3Integration:
    """Test S3 file integration features of AnalysisRepository."""

    @pytest.fixture
    async def repository(self, mock_settings):
        """Create repository instance for testing."""
        with (
            patch("paidsearchnav.storage.repository.create_engine"),
            patch("paidsearchnav.storage.repository.create_async_engine"),
            patch("paidsearchnav.storage.repository.Base"),
        ):
            repo = AnalysisRepository(mock_settings)
            yield repo

    @pytest.mark.asyncio
    async def test_save_analysis_with_files(
        self,
        repository,
        sample_analysis_result,
        sample_input_files,
        sample_output_files,
    ):
        """Test saving analysis with linked files."""
        # Mock the base save_analysis method
        with (
            patch.object(
                repository, "save_analysis", return_value="test-analysis-id"
            ) as mock_save,
            patch.object(repository, "AsyncSessionLocal") as mock_session_class,
        ):
            # Mock session and file tracker
            mock_session = AsyncMock()
            mock_session_class.return_value.__aenter__.return_value = mock_session

            with patch(
                "paidsearchnav.storage.repository.FileTracker"
            ) as mock_file_tracker_class:
                mock_file_tracker = AsyncMock()
                mock_file_tracker_class.return_value = mock_file_tracker

                # Call the method
                result = await repository.save_analysis_with_files(
                    sample_analysis_result, sample_input_files, sample_output_files
                )

                # Verify analysis was saved first
                mock_save.assert_called_once_with(sample_analysis_result)

                # Verify files were tracked
                assert (
                    mock_file_tracker.track_analysis_file.call_count == 4
                )  # 2 input + 2 output files

                # Verify session commit
                mock_session.commit.assert_called_once()

                # Verify result
                assert result == "test-analysis-id"

    @pytest.mark.asyncio
    async def test_save_analysis_with_files_error_handling(
        self, repository, sample_analysis_result, sample_input_files
    ):
        """Test error handling when file tracking fails."""
        with (
            patch.object(
                repository, "save_analysis", return_value="test-analysis-id"
            ) as mock_save,
            patch.object(repository, "delete_analysis") as mock_delete,
            patch.object(repository, "AsyncSessionLocal") as mock_session_class,
        ):
            # Mock session to raise exception
            mock_session = AsyncMock()
            mock_session_class.return_value.__aenter__.return_value = mock_session

            with patch(
                "paidsearchnav.storage.repository.FileTracker"
            ) as mock_file_tracker_class:
                mock_file_tracker = AsyncMock()
                mock_file_tracker_class.return_value = mock_file_tracker
                mock_file_tracker.track_analysis_file.side_effect = Exception(
                    "File tracking failed"
                )

                # Call should raise exception
                with pytest.raises(Exception, match="File tracking failed"):
                    await repository.save_analysis_with_files(
                        sample_analysis_result, sample_input_files, []
                    )

                # Verify rollback and cleanup
                mock_session.rollback.assert_called_once()
                mock_delete.assert_called_once_with("test-analysis-id")

    @pytest.mark.asyncio
    async def test_get_analysis_with_files(self, repository):
        """Test getting analysis with associated files."""
        # Mock analysis result
        mock_analysis = MagicMock()

        with (
            patch.object(
                repository, "get_analysis", return_value=mock_analysis
            ) as mock_get_analysis,
            patch.object(repository, "AsyncSessionLocal") as mock_session_class,
        ):
            mock_session = AsyncMock()
            mock_session_class.return_value.__aenter__.return_value = mock_session

            with patch(
                "paidsearchnav.storage.repository.FileTracker"
            ) as mock_file_tracker_class:
                mock_file_tracker = AsyncMock()
                mock_file_tracker_class.return_value = mock_file_tracker

                # Mock file references
                mock_input_file = S3FileReference(
                    file_path="s3://bucket/path/input.csv",
                    file_name="input.csv",
                    file_size=1024,
                    content_type="text/csv",
                    checksum="abc123",
                    upload_timestamp=datetime.utcnow(),
                    file_category=FileCategory.INPUT_CSV,
                )

                mock_output_file = S3FileReference(
                    file_path="s3://bucket/path/report.pdf",
                    file_name="report.pdf",
                    file_size=2048,
                    content_type="application/pdf",
                    checksum="def456",
                    upload_timestamp=datetime.utcnow(),
                    file_category=FileCategory.OUTPUT_REPORT,
                )

                # Configure file tracker mock
                def mock_get_files_by_category(analysis_id, category):
                    if category == FileCategory.INPUT_CSV:
                        return [mock_input_file]
                    elif category == FileCategory.OUTPUT_REPORT:
                        return [mock_output_file]
                    else:
                        return []

                mock_file_tracker.get_files_by_category.side_effect = (
                    mock_get_files_by_category
                )

                # Call the method
                result = await repository.get_analysis_with_files("test-analysis-id")

                # Verify result
                assert isinstance(result, AnalysisWithFiles)
                assert result.analysis == mock_analysis
                assert len(result.input_files) == 1
                assert len(result.output_files) == 1
                assert result.s3_folder_path == "s3://bucket/path"

    @pytest.mark.asyncio
    async def test_get_analysis_with_files_not_found(self, repository):
        """Test getting analysis that doesn't exist."""
        with patch.object(repository, "get_analysis", return_value=None):
            result = await repository.get_analysis_with_files("nonexistent-id")
            assert result is None

    @pytest.mark.asyncio
    async def test_list_customer_audits(self, repository):
        """Test listing customer audits."""
        # Mock analysis results
        mock_analysis = MagicMock()
        mock_analysis.analysis_id = "test-analysis-id"
        mock_analysis.created_at = datetime.utcnow()
        mock_analysis.status = "completed"
        mock_analysis.total_recommendations = 5
        mock_analysis.metrics.potential_cost_savings = 100.0
        mock_analysis.analysis_type = "search_terms"

        with (
            patch.object(
                repository, "list_analyses", return_value=[mock_analysis]
            ) as mock_list,
            patch.object(repository, "AsyncSessionLocal") as mock_session_class,
        ):
            mock_session = AsyncMock()
            mock_session_class.return_value.__aenter__.return_value = mock_session

            with patch(
                "paidsearchnav.storage.repository.FileTracker"
            ) as mock_file_tracker_class:
                mock_file_tracker = AsyncMock()
                mock_file_tracker_class.return_value = mock_file_tracker

                # Mock file references for counting
                mock_file = S3FileReference(
                    file_path="s3://bucket/path/file.csv",
                    file_name="file.csv",
                    file_size=1024,
                    content_type="text/csv",
                    checksum="abc123",
                    upload_timestamp=datetime.utcnow(),
                    file_category=FileCategory.INPUT_CSV,
                )

                mock_file_tracker.get_files_by_category.return_value = [mock_file]

                # Call the method
                result = await repository.list_customer_audits("test-customer-id")

                # Verify result
                assert len(result) == 1
                assert isinstance(result[0], AuditSummary)
                assert result[0].analysis_id == "test-analysis-id"
                assert result[0].status == "completed"
                assert result[0].total_recommendations == 5
                assert result[0].cost_savings == 100.0

    @pytest.mark.asyncio
    async def test_get_audit_files(self, repository):
        """Test getting audit files organized by type."""
        with patch.object(repository, "AsyncSessionLocal") as mock_session_class:
            mock_session = AsyncMock()
            mock_session_class.return_value.__aenter__.return_value = mock_session

            with patch(
                "paidsearchnav.storage.repository.FileTracker"
            ) as mock_file_tracker_class:
                mock_file_tracker = AsyncMock()
                mock_file_tracker_class.return_value = mock_file_tracker

                # Mock different file types
                input_file = S3FileReference(
                    file_path="s3://bucket/path/input.csv",
                    file_name="input.csv",
                    file_size=1024,
                    content_type="text/csv",
                    checksum="abc123",
                    upload_timestamp=datetime.utcnow(),
                    file_category=FileCategory.INPUT_CSV,
                )

                report_file = S3FileReference(
                    file_path="s3://bucket/path/report.pdf",
                    file_name="report.pdf",
                    file_size=2048,
                    content_type="application/pdf",
                    checksum="def456",
                    upload_timestamp=datetime.utcnow(),
                    file_category=FileCategory.OUTPUT_REPORT,
                )

                def mock_get_files_by_category(analysis_id, category):
                    if category == FileCategory.INPUT_CSV:
                        return [input_file]
                    elif category == FileCategory.OUTPUT_REPORT:
                        return [report_file]
                    else:
                        return []

                mock_file_tracker.get_files_by_category.side_effect = (
                    mock_get_files_by_category
                )

                # Call the method
                result = await repository.get_audit_files("test-analysis-id")

                # Verify result
                assert isinstance(result, AuditFileSet)
                assert result.analysis_id == "test-analysis-id"
                assert len(result.input_files) == 1
                assert len(result.output_reports) == 1
                assert len(result.output_actionable) == 0
                assert len(result.audit_logs) == 0
                assert result.total_files == 2
                assert result.total_size == 3072  # 1024 + 2048

    @pytest.mark.asyncio
    async def test_archive_old_analyses(self, repository):
        """Test archiving old analyses."""
        # Mock old analysis
        mock_analysis = MagicMock()
        mock_analysis.analysis_id = "old-analysis-id"
        mock_analysis.created_at = datetime.utcnow() - timedelta(days=100)

        # Mock analysis file
        mock_analysis_file = MagicMock()
        mock_analysis_file.file_size = 1024

        with (
            patch.object(
                repository, "list_analyses", return_value=[mock_analysis]
            ) as mock_list,
            patch.object(repository, "delete_analysis") as mock_delete,
            patch.object(repository, "AsyncSessionLocal") as mock_session_class,
        ):
            mock_session = AsyncMock()
            mock_session_class.return_value.__aenter__.return_value = mock_session

            with patch(
                "paidsearchnav.storage.repository.FileTracker"
            ) as mock_file_tracker_class:
                mock_file_tracker = AsyncMock()
                mock_file_tracker_class.return_value = mock_file_tracker

                mock_file_tracker.get_analysis_files.return_value = [mock_analysis_file]
                mock_file_tracker.delete_analysis_files.return_value = 1

                # Call the method
                result = await repository.archive_old_analyses(retention_days=90)

                # Verify result
                assert isinstance(result, ArchiveReport)
                assert result.archived_count == 1
                assert result.files_archived == 1
                assert result.space_freed == 1024
                assert len(result.errors) == 0

                # Verify cleanup calls
                mock_file_tracker.delete_analysis_files.assert_called_once_with(
                    "old-analysis-id"
                )
                mock_delete.assert_called_once_with("old-analysis-id")

    @pytest.mark.asyncio
    async def test_archive_old_analyses_with_errors(self, repository):
        """Test archiving with some failures."""
        # Mock analyses
        mock_analysis1 = MagicMock()
        mock_analysis1.analysis_id = "analysis-1"
        mock_analysis2 = MagicMock()
        mock_analysis2.analysis_id = "analysis-2"

        with (
            patch.object(
                repository,
                "list_analyses",
                return_value=[mock_analysis1, mock_analysis2],
            ),
            patch.object(repository, "delete_analysis") as mock_delete,
            patch.object(repository, "AsyncSessionLocal") as mock_session_class,
        ):
            mock_session = AsyncMock()
            mock_session_class.return_value.__aenter__.return_value = mock_session

            with patch(
                "paidsearchnav.storage.repository.FileTracker"
            ) as mock_file_tracker_class:
                mock_file_tracker = AsyncMock()
                mock_file_tracker_class.return_value = mock_file_tracker

                # Make first analysis succeed, second fail
                def mock_get_analysis_files(analysis_id):
                    if analysis_id == "analysis-1":
                        return []
                    else:
                        raise Exception("Database error")

                mock_file_tracker.get_analysis_files.side_effect = (
                    mock_get_analysis_files
                )
                mock_file_tracker.delete_analysis_files.return_value = 0

                # Call the method
                result = await repository.archive_old_analyses(retention_days=90)

                # Verify partial success
                assert result.archived_count == 1
                assert result.files_archived == 0
                assert len(result.errors) == 1
                assert "analysis-2" in result.errors[0]
