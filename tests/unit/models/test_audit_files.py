"""Tests for audit file models."""

from datetime import datetime

import pytest
from pydantic import ValidationError

from paidsearchnav.core.models.analysis import (
    AnalysisMetrics,
    AnalysisResult,
)
from paidsearchnav.core.models.audit_files import (
    AnalysisWithFiles,
    ArchiveReport,
    AuditFileSet,
    AuditSummary,
    FileCategory,
    S3FileReference,
)


class TestFileCategory:
    """Test FileCategory enum."""

    def test_file_category_values(self):
        """Test FileCategory enum values."""
        assert FileCategory.INPUT_CSV == "input_csv"
        assert FileCategory.INPUT_KEYWORDS == "input_keywords"
        assert FileCategory.OUTPUT_REPORT == "output_report"
        assert FileCategory.OUTPUT_ACTIONABLE == "output_actionable"
        assert FileCategory.AUDIT_LOG == "audit_log"
        assert FileCategory.OTHER == "other"


class TestS3FileReference:
    """Test S3FileReference model."""

    def test_create_valid_s3_file_reference(self):
        """Test creating a valid S3FileReference."""
        file_ref = S3FileReference(
            file_path="s3://bucket/customer/input/test.csv",
            file_name="test.csv",
            file_size=1024,
            content_type="text/csv",
            checksum="abc123def456",
            upload_timestamp=datetime(2024, 1, 1, 12, 0, 0),
            file_category=FileCategory.INPUT_CSV,
            metadata={"source": "google_ads", "version": "1.0"},
        )

        assert file_ref.file_path == "s3://bucket/customer/input/test.csv"
        assert file_ref.file_name == "test.csv"
        assert file_ref.file_size == 1024
        assert file_ref.content_type == "text/csv"
        assert file_ref.checksum == "abc123def456"
        assert file_ref.file_category == FileCategory.INPUT_CSV
        assert file_ref.metadata["source"] == "google_ads"
        assert file_ref.metadata["version"] == "1.0"

    def test_s3_file_reference_minimal(self):
        """Test creating S3FileReference with minimal required fields."""
        file_ref = S3FileReference(
            file_path="s3://bucket/test.csv",
            file_name="test.csv",
            file_size=512,
            content_type="text/csv",
            checksum="checksum123",
            upload_timestamp=datetime.utcnow(),
            file_category=FileCategory.INPUT_CSV,
        )

        assert file_ref.metadata == {}  # Default empty dict
        assert file_ref.file_size == 512

    def test_s3_file_reference_missing_required_fields(self):
        """Test validation errors for missing required fields."""
        with pytest.raises(ValidationError) as exc_info:
            S3FileReference()

        errors = exc_info.value.errors()
        required_fields = {
            "file_path",
            "file_name",
            "file_size",
            "content_type",
            "checksum",
            "upload_timestamp",
            "file_category",
        }

        error_fields = {error["loc"][0] for error in errors}
        assert required_fields.issubset(error_fields)


class TestAnalysisWithFiles:
    """Test AnalysisWithFiles model."""

    @pytest.fixture
    def sample_analysis_result(self):
        """Create sample analysis result."""
        return AnalysisResult(
            customer_id="1234567890",
            analysis_type="search_terms",
            analyzer_name="TestAnalyzer",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
            metrics=AnalysisMetrics(potential_cost_savings=100.0),
        )

    @pytest.fixture
    def sample_input_files(self):
        """Create sample input files."""
        return [
            S3FileReference(
                file_path="s3://bucket/input1.csv",
                file_name="input1.csv",
                file_size=1024,
                content_type="text/csv",
                checksum="abc123",
                upload_timestamp=datetime.utcnow(),
                file_category=FileCategory.INPUT_CSV,
            ),
            S3FileReference(
                file_path="s3://bucket/input2.csv",
                file_name="input2.csv",
                file_size=2048,
                content_type="text/csv",
                checksum="def456",
                upload_timestamp=datetime.utcnow(),
                file_category=FileCategory.INPUT_KEYWORDS,
            ),
        ]

    @pytest.fixture
    def sample_output_files(self):
        """Create sample output files."""
        return [
            S3FileReference(
                file_path="s3://bucket/report.pdf",
                file_name="report.pdf",
                file_size=4096,
                content_type="application/pdf",
                checksum="ghi789",
                upload_timestamp=datetime.utcnow(),
                file_category=FileCategory.OUTPUT_REPORT,
            )
        ]

    def test_create_analysis_with_files(
        self, sample_analysis_result, sample_input_files, sample_output_files
    ):
        """Test creating AnalysisWithFiles."""
        analysis_with_files = AnalysisWithFiles(
            analysis=sample_analysis_result,
            input_files=sample_input_files,
            output_files=sample_output_files,
            s3_folder_path="s3://bucket/customer/2024-01-01",
        )

        assert analysis_with_files.analysis == sample_analysis_result
        assert len(analysis_with_files.input_files) == 2
        assert len(analysis_with_files.output_files) == 1
        assert analysis_with_files.s3_folder_path == "s3://bucket/customer/2024-01-01"

    def test_total_input_size(self, sample_analysis_result, sample_input_files):
        """Test calculating total input file size."""
        analysis_with_files = AnalysisWithFiles(
            analysis=sample_analysis_result,
            input_files=sample_input_files,
            output_files=[],
            s3_folder_path="s3://bucket/customer",
        )

        assert analysis_with_files.total_input_size == 3072  # 1024 + 2048

    def test_total_output_size(self, sample_analysis_result, sample_output_files):
        """Test calculating total output file size."""
        analysis_with_files = AnalysisWithFiles(
            analysis=sample_analysis_result,
            input_files=[],
            output_files=sample_output_files,
            s3_folder_path="s3://bucket/customer",
        )

        assert analysis_with_files.total_output_size == 4096

    def test_get_files_by_category(
        self, sample_analysis_result, sample_input_files, sample_output_files
    ):
        """Test filtering files by category."""
        analysis_with_files = AnalysisWithFiles(
            analysis=sample_analysis_result,
            input_files=sample_input_files,
            output_files=sample_output_files,
            s3_folder_path="s3://bucket/customer",
        )

        csv_files = analysis_with_files.get_files_by_category(FileCategory.INPUT_CSV)
        assert len(csv_files) == 1
        assert csv_files[0].file_name == "input1.csv"

        keyword_files = analysis_with_files.get_files_by_category(
            FileCategory.INPUT_KEYWORDS
        )
        assert len(keyword_files) == 1
        assert keyword_files[0].file_name == "input2.csv"

        report_files = analysis_with_files.get_files_by_category(
            FileCategory.OUTPUT_REPORT
        )
        assert len(report_files) == 1
        assert report_files[0].file_name == "report.pdf"

        # Test category not present
        log_files = analysis_with_files.get_files_by_category(FileCategory.AUDIT_LOG)
        assert len(log_files) == 0


class TestAuditSummary:
    """Test AuditSummary model."""

    def test_create_audit_summary(self):
        """Test creating AuditSummary."""
        audit_date = datetime(2024, 1, 15, 10, 30, 0)

        summary = AuditSummary(
            analysis_id="analysis-123",
            customer_name="Test Customer",
            google_ads_account_id="1234567890",
            audit_date=audit_date,
            status="completed",
            total_recommendations=15,
            cost_savings=250.75,
            input_file_count=3,
            output_file_count=5,
            s3_folder_path="s3://bucket/customer/2024-01-15",
            analysis_type="search_terms",
            processing_time=45.5,
            total_file_size=8192,
        )

        assert summary.analysis_id == "analysis-123"
        assert summary.customer_name == "Test Customer"
        assert summary.google_ads_account_id == "1234567890"
        assert summary.audit_date == audit_date
        assert summary.status == "completed"
        assert summary.total_recommendations == 15
        assert summary.cost_savings == 250.75
        assert summary.input_file_count == 3
        assert summary.output_file_count == 5
        assert summary.analysis_type == "search_terms"
        assert summary.processing_time == 45.5
        assert summary.total_file_size == 8192

    def test_audit_summary_defaults(self):
        """Test AuditSummary with default values."""
        summary = AuditSummary(
            analysis_id="analysis-123",
            customer_name="Test Customer",
            google_ads_account_id="1234567890",
            audit_date=datetime.utcnow(),
            status="pending",
            s3_folder_path="s3://bucket/customer",
            analysis_type="search_terms",
        )

        assert summary.total_recommendations == 0
        assert summary.cost_savings == 0.0
        assert summary.input_file_count == 0
        assert summary.output_file_count == 0
        assert summary.processing_time is None
        assert summary.total_file_size == 0


class TestAuditFileSet:
    """Test AuditFileSet model."""

    @pytest.fixture
    def sample_files(self):
        """Create sample files for different categories."""
        return {
            "input": S3FileReference(
                file_path="s3://bucket/input.csv",
                file_name="input.csv",
                file_size=1024,
                content_type="text/csv",
                checksum="input123",
                upload_timestamp=datetime.utcnow(),
                file_category=FileCategory.INPUT_CSV,
            ),
            "report": S3FileReference(
                file_path="s3://bucket/report.pdf",
                file_name="report.pdf",
                file_size=2048,
                content_type="application/pdf",
                checksum="report456",
                upload_timestamp=datetime.utcnow(),
                file_category=FileCategory.OUTPUT_REPORT,
            ),
            "actionable": S3FileReference(
                file_path="s3://bucket/script.js",
                file_name="script.js",
                file_size=512,
                content_type="application/javascript",
                checksum="script789",
                upload_timestamp=datetime.utcnow(),
                file_category=FileCategory.OUTPUT_ACTIONABLE,
            ),
            "log": S3FileReference(
                file_path="s3://bucket/audit.log",
                file_name="audit.log",
                file_size=256,
                content_type="text/plain",
                checksum="log012",
                upload_timestamp=datetime.utcnow(),
                file_category=FileCategory.AUDIT_LOG,
            ),
        }

    def test_create_audit_file_set(self, sample_files):
        """Test creating AuditFileSet."""
        file_set = AuditFileSet(
            analysis_id="analysis-123",
            input_files=[sample_files["input"]],
            output_reports=[sample_files["report"]],
            output_actionable=[sample_files["actionable"]],
            audit_logs=[sample_files["log"]],
            s3_folder_path="s3://bucket/customer",
        )

        assert file_set.analysis_id == "analysis-123"
        assert len(file_set.input_files) == 1
        assert len(file_set.output_reports) == 1
        assert len(file_set.output_actionable) == 1
        assert len(file_set.audit_logs) == 1
        assert file_set.s3_folder_path == "s3://bucket/customer"

    def test_all_files_property(self, sample_files):
        """Test all_files property."""
        file_set = AuditFileSet(
            analysis_id="analysis-123",
            input_files=[sample_files["input"]],
            output_reports=[sample_files["report"]],
            output_actionable=[sample_files["actionable"]],
            audit_logs=[sample_files["log"]],
            s3_folder_path="s3://bucket/customer",
        )

        all_files = file_set.all_files
        assert len(all_files) == 4

        # Check each file is present
        file_names = {f.file_name for f in all_files}
        expected_names = {"input.csv", "report.pdf", "script.js", "audit.log"}
        assert file_names == expected_names

    def test_total_files_property(self, sample_files):
        """Test total_files property."""
        file_set = AuditFileSet(
            analysis_id="analysis-123",
            input_files=[sample_files["input"]],
            output_reports=[sample_files["report"]],
            output_actionable=[sample_files["actionable"]],
            audit_logs=[sample_files["log"]],
            s3_folder_path="s3://bucket/customer",
        )

        assert file_set.total_files == 4

    def test_total_size_property(self, sample_files):
        """Test total_size property."""
        file_set = AuditFileSet(
            analysis_id="analysis-123",
            input_files=[sample_files["input"]],
            output_reports=[sample_files["report"]],
            output_actionable=[sample_files["actionable"]],
            audit_logs=[sample_files["log"]],
            s3_folder_path="s3://bucket/customer",
        )

        # 1024 + 2048 + 512 + 256 = 3840
        assert file_set.total_size == 3840

    def test_empty_audit_file_set(self):
        """Test AuditFileSet with no files."""
        file_set = AuditFileSet(
            analysis_id="analysis-123",
            s3_folder_path="s3://bucket/customer",
        )

        assert file_set.total_files == 0
        assert file_set.total_size == 0
        assert len(file_set.all_files) == 0


class TestArchiveReport:
    """Test ArchiveReport model."""

    def test_create_archive_report(self):
        """Test creating ArchiveReport."""
        archive_date = datetime(2024, 2, 1, 10, 0, 0)

        report = ArchiveReport(
            archived_count=25,
            files_archived=150,
            space_freed=1048576,  # 1MB
            archive_location="s3://archive-bucket/2024-02-01",
            archive_date=archive_date,
            errors=["Failed to archive analysis-456", "Permission error on file.csv"],
        )

        assert report.archived_count == 25
        assert report.files_archived == 150
        assert report.space_freed == 1048576
        assert report.archive_location == "s3://archive-bucket/2024-02-01"
        assert report.archive_date == archive_date
        assert len(report.errors) == 2

    def test_archive_report_defaults(self):
        """Test ArchiveReport with default values."""
        report = ArchiveReport()

        assert report.archived_count == 0
        assert report.files_archived == 0
        assert report.space_freed == 0
        assert report.archive_location is None
        assert isinstance(report.archive_date, datetime)
        assert len(report.errors) == 0

    def test_space_freed_mb_property(self):
        """Test space_freed_mb property."""
        report = ArchiveReport(space_freed=2097152)  # 2MB in bytes
        assert report.space_freed_mb == 2.0

    def test_space_freed_gb_property(self):
        """Test space_freed_gb property."""
        report = ArchiveReport(space_freed=1073741824)  # 1GB in bytes
        assert report.space_freed_gb == 1.0

    def test_space_freed_conversions_with_fractions(self):
        """Test space conversions with fractional results."""
        report = ArchiveReport(space_freed=1536)  # 1.5KB

        assert report.space_freed_mb == pytest.approx(0.00146484375, rel=1e-5)
        assert report.space_freed_gb == pytest.approx(0.000001430511474609375, rel=1e-8)
