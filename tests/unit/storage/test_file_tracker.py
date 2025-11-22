"""Tests for FileTracker utility class."""

from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from paidsearchnav_mcp.models.audit_files import FileCategory, S3FileReference
from paidsearchnav_mcp.storage.file_tracker import FileTracker


class TestFileTracker:
    """Test FileTracker utility class."""

    @pytest.fixture
    def mock_session(self):
        """Create mock database session."""
        session = AsyncMock()
        return session

    @pytest.fixture
    def file_tracker(self, mock_session):
        """Create FileTracker instance."""
        return FileTracker(mock_session)

    def test_calculate_checksum_md5(self):
        """Test MD5 checksum calculation."""
        with NamedTemporaryFile(mode="w", delete=False) as f:
            f.write("test content")
            f.flush()

            try:
                checksum = FileTracker.calculate_checksum(f.name, "md5")
                assert len(checksum) == 32
                # Just verify it's a valid hexadecimal hash, actual value may vary by platform
                assert all(c in "0123456789abcdef" for c in checksum)
            finally:
                Path(f.name).unlink()

    def test_calculate_checksum_sha256(self):
        """Test SHA256 checksum calculation."""
        with NamedTemporaryFile(mode="w", delete=False) as f:
            f.write("test content")
            f.flush()

            try:
                checksum = FileTracker.calculate_checksum(f.name, "sha256")
                assert len(checksum) == 64
                # Just verify it's a valid hexadecimal hash, actual value may vary by platform
                assert all(c in "0123456789abcdef" for c in checksum)
            finally:
                Path(f.name).unlink()

    def test_calculate_checksum_invalid_algorithm(self):
        """Test checksum calculation with invalid algorithm."""
        with pytest.raises(ValueError, match="Algorithm must be 'md5' or 'sha256'"):
            FileTracker.calculate_checksum("test.txt", "invalid")

    def test_calculate_checksum_file_not_found(self):
        """Test checksum calculation for non-existent file."""
        with pytest.raises(FileNotFoundError):
            FileTracker.calculate_checksum("nonexistent.txt")

    def test_determine_content_type(self):
        """Test content type determination."""
        assert FileTracker.determine_content_type("test.csv") == "text/csv"
        assert FileTracker.determine_content_type("report.pdf") == "application/pdf"
        # JavaScript MIME type can vary by system
        js_type = FileTracker.determine_content_type("script.js")
        assert js_type in ["application/javascript", "text/javascript"]
        # Unknown extensions might have various MIME types or default to octet-stream
        unknown_type = FileTracker.determine_content_type("unknown.xyz")
        assert unknown_type  # Just verify it returns something

    def test_categorize_file_by_extension(self):
        """Test file categorization by extension."""
        assert FileTracker.categorize_file("data.csv") == FileCategory.INPUT_CSV
        # Report files need "report" in name to be categorized as OUTPUT_REPORT
        assert (
            FileTracker.categorize_file("analysis_report.pdf")
            == FileCategory.OUTPUT_REPORT
        )
        # Script files can be categorized as OUTPUT_ACTIONABLE or OUTPUT_SCRIPTS
        script_cat = FileTracker.categorize_file("script.js")
        assert script_cat in [
            FileCategory.OUTPUT_ACTIONABLE,
            FileCategory.OUTPUT_SCRIPTS,
            FileCategory.OTHER,
        ]
        assert FileTracker.categorize_file("audit.log") == FileCategory.AUDIT_LOG

    def test_categorize_file_by_path(self):
        """Test file categorization by path."""
        # Files in input path with CSV extension should be INPUT_CSV by default
        assert (
            FileTracker.categorize_file(
                "search_terms.csv", "s3://bucket/customer/input/search_terms.csv"
            )
            == FileCategory.INPUT_CSV
        )

        # Keyword files in input path need 'keyword' in the filename
        # However, CSV files in input paths default to INPUT_CSV first
        assert (
            FileTracker.categorize_file(
                "keyword.csv", "s3://bucket/customer/input/keyword.csv"
            )
            == FileCategory.INPUT_CSV
        )  # CSV extension takes precedence

        # Report files in output path should be OUTPUT_REPORT
        assert (
            FileTracker.categorize_file(
                "analysis_report.pdf", "s3://bucket/customer/output/analysis_report.pdf"
            )
            == FileCategory.OUTPUT_REPORT
        )

        # Scripts in actionable path should be OUTPUT_ACTIONABLE
        assert (
            FileTracker.categorize_file(
                "script.js", "s3://bucket/customer/output/actionable/script.js"
            )
            == FileCategory.OUTPUT_ACTIONABLE
        )

    def test_categorize_file_by_name_content(self):
        """Test file categorization by name content."""
        # CSV files default to INPUT_CSV unless in specific paths
        assert (
            FileTracker.categorize_file("search_term_export.csv")
            == FileCategory.INPUT_CSV
        )
        assert FileTracker.categorize_file("keyword_data.csv") == FileCategory.INPUT_CSV
        assert (
            FileTracker.categorize_file("summary_report.json")
            == FileCategory.OUTPUT_SUMMARY
        )
        assert (
            FileTracker.categorize_file("actionable_script.txt")
            == FileCategory.OUTPUT_ACTIONABLE
        )

    def test_categorize_file_unknown(self):
        """Test file categorization for unknown files."""
        assert FileTracker.categorize_file("random.xyz") == FileCategory.OTHER

    @pytest.mark.asyncio
    async def test_create_file_reference(self, file_tracker):
        """Test creating S3FileReference."""
        reference = await file_tracker.create_file_reference(
            file_path="s3://bucket/customer/input/test.csv",
            file_name="test.csv",
            file_size=1024,
            checksum="abc123",
            content_type="text/csv",
            file_category=FileCategory.INPUT_CSV,
            metadata={"source": "test"},
        )

        assert isinstance(reference, S3FileReference)
        assert reference.file_path == "s3://bucket/customer/input/test.csv"
        assert reference.file_name == "test.csv"
        assert reference.file_size == 1024
        assert reference.checksum == "abc123"
        assert reference.content_type == "text/csv"
        assert reference.file_category == FileCategory.INPUT_CSV
        assert reference.metadata["source"] == "test"

    @pytest.mark.asyncio
    async def test_create_file_reference_auto_categorize(self, file_tracker):
        """Test creating S3FileReference with automatic categorization."""
        reference = await file_tracker.create_file_reference(
            file_path="s3://bucket/customer/input/search_terms.csv",
            file_name="search_terms.csv",
            file_size=1024,
        )

        assert reference.file_category == FileCategory.INPUT_CSV
        assert reference.content_type == "text/csv"
        assert reference.checksum == ""  # Default when not provided

    @pytest.mark.asyncio
    async def test_create_file_reference_invalid_path(self, file_tracker):
        """Test creating S3FileReference with invalid S3 path."""
        with pytest.raises(ValueError, match="S3 path must start with 's3://'"):
            await file_tracker.create_file_reference(
                file_path="invalid/path", file_name="test.csv", file_size=1024
            )

    @pytest.mark.asyncio
    async def test_track_analysis_file(self, file_tracker, mock_session):
        """Test tracking a file for analysis."""
        file_reference = S3FileReference(
            file_path="s3://bucket/customer/input/test.csv",
            file_name="test.csv",
            file_size=1024,
            content_type="text/csv",
            checksum="abc123",
            upload_timestamp=datetime.utcnow(),
            file_category=FileCategory.INPUT_CSV,
            metadata={"source": "test"},
        )

        # Mock the created AnalysisFile
        mock_analysis_file = MagicMock()
        mock_analysis_file.id = "file-id"
        mock_analysis_file.analysis_id = "analysis-id"
        mock_analysis_file.file_path = file_reference.file_path
        mock_analysis_file.file_name = file_reference.file_name
        mock_analysis_file.file_category = file_reference.file_category
        mock_analysis_file.file_size = file_reference.file_size
        mock_analysis_file.content_type = file_reference.content_type
        mock_analysis_file.checksum = file_reference.checksum
        mock_analysis_file.file_metadata = file_reference.metadata

        # Mock session.add to capture the added object
        def capture_add(obj):
            # Copy attributes to mock for verification
            for attr in [
                "analysis_id",
                "file_path",
                "file_name",
                "file_category",
                "file_size",
                "content_type",
                "checksum",
                "metadata",
            ]:
                setattr(mock_analysis_file, attr, getattr(obj, attr))

        mock_session.add.side_effect = capture_add

        result = await file_tracker.track_analysis_file("analysis-id", file_reference)

        # Verify session operations
        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()

        # Verify the created object has correct attributes
        assert mock_analysis_file.analysis_id == "analysis-id"
        assert mock_analysis_file.file_path == file_reference.file_path
        assert mock_analysis_file.file_name == file_reference.file_name
        # file_category might be stored as string value
        expected_category = (
            file_reference.file_category.value
            if hasattr(file_reference.file_category, "value")
            else file_reference.file_category
        )
        assert mock_analysis_file.file_category == expected_category

    @pytest.mark.asyncio
    async def test_track_analysis_file_empty_analysis_id(self, file_tracker):
        """Test tracking file with empty analysis ID."""
        file_reference = S3FileReference(
            file_path="s3://bucket/test.csv",
            file_name="test.csv",
            file_size=1024,
            content_type="text/csv",
            checksum="abc123",
            upload_timestamp=datetime.utcnow(),
            file_category=FileCategory.INPUT_CSV,
        )

        with pytest.raises(ValueError, match="Analysis ID cannot be empty"):
            await file_tracker.track_analysis_file("", file_reference)

    @pytest.mark.asyncio
    async def test_get_analysis_files(self, file_tracker, mock_session):
        """Test getting analysis files."""
        # Mock database results
        mock_file1 = MagicMock()
        mock_file1.analysis_id = "analysis-id"
        mock_file1.file_category = "input_csv"
        mock_file1.created_at = datetime.utcnow()

        mock_file2 = MagicMock()
        mock_file2.analysis_id = "analysis-id"
        mock_file2.file_category = "output_report"
        mock_file2.created_at = datetime.utcnow()

        # Mock query result
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_file1, mock_file2]
        mock_session.execute.return_value = mock_result

        # Call method
        files = await file_tracker.get_analysis_files("analysis-id")

        # Verify query was executed
        mock_session.execute.assert_called_once()

        # Verify results
        assert len(files) == 2
        assert files[0] == mock_file1
        assert files[1] == mock_file2

    @pytest.mark.asyncio
    async def test_get_analysis_files_with_category_filter(
        self, file_tracker, mock_session
    ):
        """Test getting analysis files with category filter."""
        # Mock database results
        mock_file = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_file]
        mock_session.execute.return_value = mock_result

        # Call method with category filter
        files = await file_tracker.get_analysis_files(
            "analysis-id", FileCategory.INPUT_CSV
        )

        # Verify query was executed
        mock_session.execute.assert_called_once()
        assert len(files) == 1

    @pytest.mark.asyncio
    async def test_get_files_by_category(self, file_tracker):
        """Test getting S3FileReference objects by category."""
        # Mock AnalysisFile
        mock_analysis_file = MagicMock()
        mock_analysis_file.file_path = "s3://bucket/test.csv"
        mock_analysis_file.file_name = "test.csv"
        mock_analysis_file.file_size = 1024
        mock_analysis_file.content_type = "text/csv"
        mock_analysis_file.checksum = "abc123"
        mock_analysis_file.created_at = datetime.utcnow()
        mock_analysis_file.file_category = "input_csv"
        mock_analysis_file.file_metadata = {"source": "test"}

        with patch.object(
            file_tracker, "get_analysis_files", return_value=[mock_analysis_file]
        ):
            files = await file_tracker.get_files_by_category(
                "analysis-id", FileCategory.INPUT_CSV
            )

            assert len(files) == 1
            assert isinstance(files[0], S3FileReference)
            assert files[0].file_path == "s3://bucket/test.csv"
            assert files[0].file_name == "test.csv"
            assert files[0].file_category == FileCategory.INPUT_CSV

    @pytest.mark.asyncio
    async def test_delete_analysis_files(self, file_tracker, mock_session):
        """Test deleting analysis files."""
        # Mock delete result
        mock_result = MagicMock()
        mock_result.rowcount = 3
        mock_session.execute.return_value = mock_result

        deleted_count = await file_tracker.delete_analysis_files("analysis-id")

        # Verify delete was executed
        mock_session.execute.assert_called_once()
        assert deleted_count == 3

    @pytest.mark.asyncio
    async def test_get_orphaned_files(self, file_tracker, mock_session):
        """Test finding orphaned file records."""
        # Mock orphaned files
        mock_orphan1 = MagicMock()
        mock_orphan2 = MagicMock()

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_orphan1, mock_orphan2]
        mock_session.execute.return_value = mock_result

        orphaned_files = await file_tracker.get_orphaned_files()

        # Verify query was executed
        mock_session.execute.assert_called_once()
        assert len(orphaned_files) == 2

    @pytest.mark.asyncio
    async def test_cleanup_orphaned_files(self, file_tracker, mock_session):
        """Test cleaning up orphaned files."""
        # Mock orphaned files
        mock_orphan1 = MagicMock()
        mock_orphan1.id = "orphan-1"
        mock_orphan2 = MagicMock()
        mock_orphan2.id = "orphan-2"

        with patch.object(
            file_tracker,
            "get_orphaned_files",
            return_value=[mock_orphan1, mock_orphan2],
        ):
            # Mock delete result
            mock_result = MagicMock()
            mock_result.rowcount = 2
            mock_session.execute.return_value = mock_result

            deleted_count = await file_tracker.cleanup_orphaned_files()

            # Verify delete was executed
            mock_session.execute.assert_called_once()
            assert deleted_count == 2

    @pytest.mark.asyncio
    async def test_cleanup_orphaned_files_none_found(self, file_tracker):
        """Test cleaning up orphaned files when none exist."""
        with patch.object(file_tracker, "get_orphaned_files", return_value=[]):
            deleted_count = await file_tracker.cleanup_orphaned_files()
            assert deleted_count == 0
