"""Integration tests for enhanced AnalysisRepository S3 functionality."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

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
    FileCategory,
    S3FileReference,
)
from paidsearchnav.storage.repository import AnalysisRepository


@pytest.fixture
def test_settings():
    """Create test settings."""
    return Settings(
        environment="development",
        debug=True,
        data_dir="/tmp/test_data",
    )


@pytest.fixture
def sample_analysis_result():
    """Create a sample analysis result."""
    return AnalysisResult(
        customer_id="1234567890",
        analysis_type="search_terms",
        analyzer_name="IntegrationTestAnalyzer",
        start_date=datetime(2024, 1, 1),
        end_date=datetime(2024, 1, 31),
        status="completed",
        metrics=AnalysisMetrics(
            total_keywords_analyzed=250,
            total_search_terms_analyzed=1000,
            potential_cost_savings=500.0,
            potential_conversion_increase=15.0,
        ),
        recommendations=[
            Recommendation(
                type=RecommendationType.ADD_NEGATIVE,
                priority=RecommendationPriority.HIGH,
                title="Add high-priority negative keywords",
                description="Add 'free', 'cheap', 'discount' as negative keywords",
                estimated_cost_savings=200.0,
            ),
            Recommendation(
                type=RecommendationType.OPTIMIZE_KEYWORDS,
                priority=RecommendationPriority.MEDIUM,
                title="Optimize keyword match types",
                description="Change broad match keywords to phrase match",
                estimated_cost_savings=150.0,
            ),
        ],
    )


@pytest.fixture
def sample_s3_files():
    """Create sample S3 files for testing."""
    now = datetime.utcnow()

    input_files = [
        S3FileReference(
            file_path="s3://test-bucket/customer-123/1234567890/input/20240101/search_terms_export.csv",
            file_name="search_terms_export.csv",
            file_size=2048,
            content_type="text/csv",
            checksum="input_checksum_123",
            upload_timestamp=now,
            file_category=FileCategory.INPUT_CSV,
            metadata={"source": "google_ads_api", "account": "1234567890"},
        ),
        S3FileReference(
            file_path="s3://test-bucket/customer-123/1234567890/input/20240101/keyword_list.csv",
            file_name="keyword_list.csv",
            file_size=1024,
            content_type="text/csv",
            checksum="input_checksum_456",
            upload_timestamp=now,
            file_category=FileCategory.INPUT_KEYWORDS,
            metadata={"source": "campaign_export", "total_keywords": "250"},
        ),
    ]

    output_files = [
        S3FileReference(
            file_path="s3://test-bucket/customer-123/1234567890/output/20240101/search_terms/analysis_report.pdf",
            file_name="analysis_report.pdf",
            file_size=4096,
            content_type="application/pdf",
            checksum="output_checksum_789",
            upload_timestamp=now,
            file_category=FileCategory.OUTPUT_REPORT,
            metadata={"format": "executive_summary", "pages": "12"},
        ),
        S3FileReference(
            file_path="s3://test-bucket/customer-123/1234567890/output/20240101/search_terms/negative_keywords_script.js",
            file_name="negative_keywords_script.js",
            file_size=512,
            content_type="application/javascript",
            checksum="output_checksum_012",
            upload_timestamp=now,
            file_category=FileCategory.OUTPUT_SCRIPTS,
            metadata={
                "script_type": "google_ads_script",
                "negative_keywords_count": "47",
            },
        ),
        S3FileReference(
            file_path="s3://test-bucket/customer-123/1234567890/output/20240101/search_terms/summary.json",
            file_name="summary.json",
            file_size=256,
            content_type="application/json",
            checksum="output_checksum_345",
            upload_timestamp=now,
            file_category=FileCategory.OUTPUT_SUMMARY,
            metadata={"format": "json", "compression": "none"},
        ),
    ]

    return input_files, output_files


class TestAnalysisRepositoryIntegration:
    """Integration tests for AnalysisRepository S3 functionality."""

    @pytest.fixture
    async def repository(self, test_settings):
        """Create repository with mocked database."""
        with (
            patch("paidsearchnav.storage.repository.create_engine") as mock_sync_engine,
            patch(
                "paidsearchnav.storage.repository.create_async_engine"
            ) as mock_async_engine,
            patch("paidsearchnav.storage.repository.Base") as mock_base,
        ):
            # Mock engines
            mock_sync_engine.return_value = MagicMock()
            mock_async_engine.return_value = MagicMock()
            mock_base.metadata.create_all = MagicMock()

            repo = AnalysisRepository(test_settings)
            yield repo

    @pytest.mark.asyncio
    async def test_full_analysis_lifecycle_with_files(
        self, repository, sample_analysis_result, sample_s3_files
    ):
        """Test complete analysis lifecycle with S3 files."""
        input_files, output_files = sample_s3_files

        # Mock the database operations
        with (
            patch.object(
                repository, "save_analysis", return_value="integration-test-analysis-id"
            ) as mock_save_base,
            patch.object(repository, "AsyncSessionLocal") as mock_session_class,
        ):
            # Mock session and transaction
            mock_session = MagicMock()
            mock_session.__aenter__ = MagicMock(return_value=mock_session)
            mock_session.__aexit__ = MagicMock(return_value=None)
            mock_session_class.return_value = mock_session

            # Mock file tracker
            with patch(
                "paidsearchnav.storage.repository.FileTracker"
            ) as mock_file_tracker_class:
                mock_file_tracker = MagicMock()
                mock_file_tracker_class.return_value = mock_file_tracker

                # Track all expected file tracking calls
                file_tracking_calls = []

                async def track_file(analysis_id, file_ref):
                    file_tracking_calls.append((analysis_id, file_ref))
                    return MagicMock()

                mock_file_tracker.track_analysis_file = track_file

                # 1. Save analysis with files
                analysis_id = await repository.save_analysis_with_files(
                    sample_analysis_result, input_files, output_files
                )

                # Verify analysis was saved
                assert analysis_id == "integration-test-analysis-id"
                mock_save_base.assert_called_once_with(sample_analysis_result)

                # Verify all files were tracked
                assert len(file_tracking_calls) == 5  # 2 input + 3 output files

                # Verify file tracking details
                tracked_analysis_ids = {call[0] for call in file_tracking_calls}
                assert tracked_analysis_ids == {"integration-test-analysis-id"}

                tracked_file_names = {call[1].file_name for call in file_tracking_calls}
                expected_file_names = {
                    "search_terms_export.csv",
                    "keyword_list.csv",
                    "analysis_report.pdf",
                    "negative_keywords_script.js",
                    "summary.json",
                }
                assert tracked_file_names == expected_file_names

                # Verify session commit was called
                mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_analysis_with_files_integration(self, repository):
        """Test retrieving analysis with files."""
        # Mock base analysis
        mock_analysis = MagicMock()
        mock_analysis.analysis_id = "test-analysis-with-files"
        mock_analysis.customer_id = "1234567890"
        mock_analysis.analysis_type = "search_terms"

        with (
            patch.object(
                repository, "get_analysis", return_value=mock_analysis
            ) as mock_get_analysis,
            patch.object(repository, "AsyncSessionLocal") as mock_session_class,
        ):
            mock_session = MagicMock()
            mock_session.__aenter__ = MagicMock(return_value=mock_session)
            mock_session.__aexit__ = MagicMock(return_value=None)
            mock_session_class.return_value = mock_session

            with patch(
                "paidsearchnav.storage.repository.FileTracker"
            ) as mock_file_tracker_class:
                mock_file_tracker = MagicMock()
                mock_file_tracker_class.return_value = mock_file_tracker

                # Mock file references by category
                def mock_get_files_by_category(analysis_id, category):
                    if category == FileCategory.INPUT_CSV:
                        return [
                            S3FileReference(
                                file_path="s3://bucket/input.csv",
                                file_name="input.csv",
                                file_size=1024,
                                content_type="text/csv",
                                checksum="test123",
                                upload_timestamp=datetime.utcnow(),
                                file_category=FileCategory.INPUT_CSV,
                            )
                        ]
                    elif category == FileCategory.OUTPUT_REPORT:
                        return [
                            S3FileReference(
                                file_path="s3://bucket/report.pdf",
                                file_name="report.pdf",
                                file_size=2048,
                                content_type="application/pdf",
                                checksum="test456",
                                upload_timestamp=datetime.utcnow(),
                                file_category=FileCategory.OUTPUT_REPORT,
                            )
                        ]
                    else:
                        return []

                mock_file_tracker.get_files_by_category = mock_get_files_by_category

                # Get analysis with files
                result = await repository.get_analysis_with_files(
                    "test-analysis-with-files"
                )

                # Verify result structure
                assert isinstance(result, AnalysisWithFiles)
                assert result.analysis == mock_analysis
                assert len(result.input_files) == 1
                assert len(result.output_files) == 1
                assert result.s3_folder_path == "s3://bucket"

                # Verify file details
                assert result.input_files[0].file_name == "input.csv"
                assert result.output_files[0].file_name == "report.pdf"

                # Verify size calculations
                assert result.total_input_size == 1024
                assert result.total_output_size == 2048

    @pytest.mark.asyncio
    async def test_list_customer_audits_integration(self, repository):
        """Test listing customer audits with file information."""
        # Mock analysis results
        mock_analysis = MagicMock()
        mock_analysis.analysis_id = "customer-audit-test"
        mock_analysis.customer_id = "1234567890"
        mock_analysis.created_at = datetime(2024, 1, 15, 10, 30, 0)
        mock_analysis.status = "completed"
        mock_analysis.total_recommendations = 8
        mock_analysis.metrics.potential_cost_savings = 300.0
        mock_analysis.analysis_type = "search_terms"

        with (
            patch.object(
                repository, "list_analyses", return_value=[mock_analysis]
            ) as mock_list_analyses,
            patch.object(repository, "AsyncSessionLocal") as mock_session_class,
        ):
            mock_session = MagicMock()
            mock_session.__aenter__ = MagicMock(return_value=mock_session)
            mock_session.__aexit__ = MagicMock(return_value=None)
            mock_session_class.return_value = mock_session

            with patch(
                "paidsearchnav.storage.repository.FileTracker"
            ) as mock_file_tracker_class:
                mock_file_tracker = MagicMock()
                mock_file_tracker_class.return_value = mock_file_tracker

                # Mock file references for counting
                def mock_get_files_by_category(analysis_id, category):
                    if category == FileCategory.INPUT_CSV:
                        return [
                            MagicMock(file_size=1024),
                            MagicMock(file_size=512),
                        ]  # 2 input files
                    elif category == FileCategory.OUTPUT_REPORT:
                        return [MagicMock(file_size=2048)]  # 1 output file
                    else:
                        return []

                mock_file_tracker.get_files_by_category = mock_get_files_by_category

                # List customer audits
                audits = await repository.list_customer_audits("1234567890")

                # Verify results
                assert len(audits) == 1
                audit = audits[0]

                assert audit.analysis_id == "customer-audit-test"
                assert audit.customer_name == "1234567890"
                assert audit.audit_date == datetime(2024, 1, 15, 10, 30, 0)
                assert audit.status == "completed"
                assert audit.total_recommendations == 8
                assert audit.cost_savings == 300.0
                assert audit.analysis_type == "search_terms"
                assert audit.input_file_count == 2
                assert audit.output_file_count == 1
                assert audit.total_file_size == 3584  # 1024 + 512 + 2048

    @pytest.mark.asyncio
    async def test_archive_old_analyses_integration(self, repository):
        """Test archiving old analyses integration."""
        # Create mock old analyses
        old_analysis_1 = MagicMock()
        old_analysis_1.analysis_id = "old-analysis-1"
        old_analysis_1.created_at = datetime.utcnow() - timedelta(days=120)

        old_analysis_2 = MagicMock()
        old_analysis_2.analysis_id = "old-analysis-2"
        old_analysis_2.created_at = datetime.utcnow() - timedelta(days=150)

        with (
            patch.object(
                repository,
                "list_analyses",
                return_value=[old_analysis_1, old_analysis_2],
            ) as mock_list,
            patch.object(repository, "delete_analysis") as mock_delete_analysis,
            patch.object(repository, "AsyncSessionLocal") as mock_session_class,
        ):
            mock_session = MagicMock()
            mock_session.__aenter__ = MagicMock(return_value=mock_session)
            mock_session.__aexit__ = MagicMock(return_value=None)
            mock_session_class.return_value = mock_session

            with patch(
                "paidsearchnav.storage.repository.FileTracker"
            ) as mock_file_tracker_class:
                mock_file_tracker = MagicMock()
                mock_file_tracker_class.return_value = mock_file_tracker

                # Mock file operations for each analysis
                def mock_get_analysis_files(analysis_id):
                    if analysis_id == "old-analysis-1":
                        return [
                            MagicMock(file_size=1024),
                            MagicMock(file_size=2048),
                        ]  # 2 files, 3072 bytes
                    elif analysis_id == "old-analysis-2":
                        return [MagicMock(file_size=512)]  # 1 file, 512 bytes
                    return []

                def mock_delete_analysis_files(analysis_id):
                    if analysis_id == "old-analysis-1":
                        return 2
                    elif analysis_id == "old-analysis-2":
                        return 1
                    return 0

                mock_file_tracker.get_analysis_files = mock_get_analysis_files
                mock_file_tracker.delete_analysis_files = mock_delete_analysis_files

                # Archive old analyses
                archive_report = await repository.archive_old_analyses(
                    retention_days=100
                )

                # Verify archiving results
                assert archive_report.archived_count == 2
                assert archive_report.files_archived == 3  # 2 + 1
                assert archive_report.space_freed == 3584  # 3072 + 512
                assert len(archive_report.errors) == 0

                # Verify cleanup operations
                assert mock_file_tracker.delete_analysis_files.call_count == 2
                assert mock_delete_analysis.call_count == 2

                # Verify specific analyses were deleted
                deleted_analysis_ids = {
                    call.args[0] for call in mock_delete_analysis.call_args_list
                }
                assert deleted_analysis_ids == {"old-analysis-1", "old-analysis-2"}

    @pytest.mark.asyncio
    async def test_error_handling_integration(self, repository, sample_analysis_result):
        """Test error handling in file operations."""
        input_files = [
            S3FileReference(
                file_path="s3://bucket/test.csv",
                file_name="test.csv",
                file_size=1024,
                content_type="text/csv",
                checksum="test123",
                upload_timestamp=datetime.utcnow(),
                file_category=FileCategory.INPUT_CSV,
            )
        ]

        with (
            patch.object(
                repository, "save_analysis", return_value="error-test-id"
            ) as mock_save_base,
            patch.object(repository, "delete_analysis") as mock_delete_analysis,
            patch.object(repository, "AsyncSessionLocal") as mock_session_class,
        ):
            mock_session = MagicMock()
            mock_session.__aenter__ = MagicMock(return_value=mock_session)
            mock_session.__aexit__ = MagicMock(return_value=None)
            mock_session_class.return_value = mock_session

            with patch(
                "paidsearchnav.storage.repository.FileTracker"
            ) as mock_file_tracker_class:
                mock_file_tracker = MagicMock()
                mock_file_tracker_class.return_value = mock_file_tracker

                # Make file tracking fail
                async def failing_track_file(analysis_id, file_ref):
                    raise Exception("Database connection failed")

                mock_file_tracker.track_analysis_file = failing_track_file

                # Attempt to save analysis with files - should fail
                with pytest.raises(Exception, match="Database connection failed"):
                    await repository.save_analysis_with_files(
                        sample_analysis_result, input_files, []
                    )

                # Verify cleanup was attempted
                mock_session.rollback.assert_called_once()
                mock_delete_analysis.assert_called_once_with("error-test-id")

    @pytest.mark.asyncio
    async def test_complex_file_categorization_integration(self, repository):
        """Test complex file categorization scenarios."""
        # Create files with various naming patterns
        complex_files = [
            S3FileReference(
                file_path="s3://bucket/customer/input/search-terms-detailed-export.csv",
                file_name="search-terms-detailed-export.csv",
                file_size=2048,
                content_type="text/csv",
                checksum="complex1",
                upload_timestamp=datetime.utcnow(),
                file_category=FileCategory.INPUT_SEARCH_TERMS,
            ),
            S3FileReference(
                file_path="s3://bucket/customer/output/actionable/negative_keywords_automation.js",
                file_name="negative_keywords_automation.js",
                file_size=1024,
                content_type="application/javascript",
                checksum="complex2",
                upload_timestamp=datetime.utcnow(),
                file_category=FileCategory.OUTPUT_SCRIPTS,
            ),
            S3FileReference(
                file_path="s3://bucket/customer/output/executive-summary-report.pdf",
                file_name="executive-summary-report.pdf",
                file_size=4096,
                content_type="application/pdf",
                checksum="complex3",
                upload_timestamp=datetime.utcnow(),
                file_category=FileCategory.OUTPUT_REPORT,
            ),
        ]

        # Mock analysis
        mock_analysis = MagicMock()
        mock_analysis.analysis_id = "complex-categorization-test"

        with (
            patch.object(repository, "get_analysis", return_value=mock_analysis),
            patch.object(repository, "AsyncSessionLocal") as mock_session_class,
        ):
            mock_session = MagicMock()
            mock_session.__aenter__ = MagicMock(return_value=mock_session)
            mock_session.__aexit__ = MagicMock(return_value=None)
            mock_session_class.return_value = mock_session

            with patch(
                "paidsearchnav.storage.repository.FileTracker"
            ) as mock_file_tracker_class:
                mock_file_tracker = MagicMock()
                mock_file_tracker_class.return_value = mock_file_tracker

                # Mock file retrieval by category
                def mock_get_files_by_category(analysis_id, category):
                    return [f for f in complex_files if f.file_category == category]

                mock_file_tracker.get_files_by_category = mock_get_files_by_category

                # Get analysis with files
                result = await repository.get_analysis_with_files(
                    "complex-categorization-test"
                )

                # Verify categorization
                assert len(result.input_files) == 1
                assert (
                    result.input_files[0].file_category
                    == FileCategory.INPUT_SEARCH_TERMS
                )
                assert "search-terms" in result.input_files[0].file_name

                assert len(result.output_files) == 2

                # Find script file
                script_files = [
                    f
                    for f in result.output_files
                    if f.file_category == FileCategory.OUTPUT_SCRIPTS
                ]
                assert len(script_files) == 1
                assert script_files[0].file_name == "negative_keywords_automation.js"

                # Find report file
                report_files = [
                    f
                    for f in result.output_files
                    if f.file_category == FileCategory.OUTPUT_REPORT
                ]
                assert len(report_files) == 1
                assert report_files[0].file_name == "executive-summary-report.pdf"
