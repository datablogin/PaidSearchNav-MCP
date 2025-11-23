"""Tests for CSV export functionality."""

import csv
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from paidsearchnav_mcp.exports.base import ExportFormat, ExportStatus
from paidsearchnav_mcp.exports.csv import CSVExporter


class TestCSVExporter:
    """Test CSV export functionality."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def exporter(self, temp_dir):
        """Create a CSV exporter with temporary directory."""
        return CSVExporter(output_dir=temp_dir)

    @pytest.fixture
    def sample_data(self):
        """Sample data for testing CSV export."""
        return {
            "search_terms": [
                {
                    "campaign": "Test Campaign",
                    "search_term": "test keyword",
                    "clicks": 10,
                    "cost": 5.50,
                    "has_conversions": True,
                },
                {
                    "campaign": "Another Campaign",
                    "search_term": "another keyword",
                    "clicks": 5,
                    "cost": 2.25,
                    "has_conversions": False,
                },
            ],
            "keywords": [
                {
                    "campaign": "Test Campaign",
                    "keyword": "exact keyword",
                    "match_type": "EXACT",
                    "clicks": 15,
                    "cost": 7.25,
                    "quality_score": 8,
                }
            ],
        }

    def test_initialization_with_default_dir(self):
        """Test CSV exporter initialization with default directory."""
        exporter = CSVExporter()
        assert exporter.output_dir == Path.cwd()

    def test_initialization_with_custom_dir(self, temp_dir):
        """Test CSV exporter initialization with custom directory."""
        exporter = CSVExporter(output_dir=temp_dir)
        assert exporter.output_dir == temp_dir
        assert temp_dir.exists()

    @pytest.mark.asyncio
    async def test_export_batch_success(self, exporter, sample_data, temp_dir):
        """Test successful batch export to CSV files."""
        customer_id = "test_customer_123"

        result = await exporter.export_batch(customer_id, sample_data)

        # Check result
        assert result.status == ExportStatus.COMPLETED
        assert result.destination == ExportFormat.CSV
        assert result.records_exported == 3  # 2 search_terms + 1 keyword
        assert result.metadata["customer_id"] == customer_id
        assert len(result.metadata["files_created"]) == 2

        # Check files were created
        files_created = result.metadata["files_created"]
        assert len(files_created) == 2

        for file_path in files_created:
            assert Path(file_path).exists()
            assert Path(file_path).suffix == ".csv"

    @pytest.mark.asyncio
    async def test_export_batch_empty_data(self, exporter):
        """Test export with empty data."""
        customer_id = "test_customer"
        empty_data = {}

        result = await exporter.export_batch(customer_id, empty_data)

        assert result.status == ExportStatus.COMPLETED
        assert result.records_exported == 0
        assert len(result.metadata["files_created"]) == 0

    @pytest.mark.asyncio
    async def test_export_batch_with_empty_tables(self, exporter):
        """Test export with tables containing no records."""
        customer_id = "test_customer"
        data_with_empty_tables = {"search_terms": [], "keywords": []}

        result = await exporter.export_batch(customer_id, data_with_empty_tables)

        assert result.status == ExportStatus.COMPLETED
        assert result.records_exported == 0
        assert len(result.metadata["files_created"]) == 0

    @pytest.mark.asyncio
    async def test_write_csv_file_content(self, exporter, temp_dir):
        """Test that CSV file content is written correctly."""
        test_records = [
            {"name": "John", "age": 30, "city": "New York"},
            {"name": "Jane", "age": 25, "city": "Los Angeles"},
        ]

        test_file = temp_dir / "test.csv"
        records_written = await exporter._write_csv_file(test_file, test_records)

        assert records_written == 2
        assert test_file.exists()

        # Read and verify content
        with open(test_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 2
        assert rows[0]["name"] == "John"
        assert rows[0]["age"] == "30"
        assert rows[1]["name"] == "Jane"
        assert rows[1]["city"] == "Los Angeles"

    @pytest.mark.asyncio
    async def test_write_csv_file_empty_records(self, exporter, temp_dir):
        """Test writing empty records list."""
        test_file = temp_dir / "empty.csv"
        records_written = await exporter._write_csv_file(test_file, [])

        assert records_written == 0
        assert not test_file.exists()

    def test_clean_record_for_csv_basic_types(self, exporter):
        """Test cleaning basic data types for CSV output."""
        record = {
            "string": "hello",
            "integer": 42,
            "float": 3.14,
            "boolean_true": True,
            "boolean_false": False,
            "none_value": None,
        }

        cleaned = exporter._clean_record_for_csv(record)

        assert cleaned["string"] == "hello"
        assert cleaned["integer"] == "42"
        assert cleaned["float"] == "3.14"
        assert cleaned["boolean_true"] == "true"
        assert cleaned["boolean_false"] == "false"
        assert cleaned["none_value"] == ""

    def test_clean_record_for_csv_complex_types(self, exporter):
        """Test cleaning complex data types for CSV output."""
        record = {
            "dict": {"key": "value"},
            "list": [1, 2, 3],
            "nested": {"users": [{"name": "John"}]},
        }

        cleaned = exporter._clean_record_for_csv(record)

        assert isinstance(cleaned["dict"], str)
        assert isinstance(cleaned["list"], str)
        assert isinstance(cleaned["nested"], str)

    def test_clean_record_for_csv_string_cleaning(self, exporter):
        """Test string cleaning for CSV output."""
        record = {
            "with_newlines": "line1\nline2\rline3",
            "with_whitespace": "  lots   of    spaces  ",
            "normal_string": "normal text",
        }

        cleaned = exporter._clean_record_for_csv(record)

        # Newlines should be replaced with spaces
        assert "\n" not in cleaned["with_newlines"]
        assert "\r" not in cleaned["with_newlines"]
        assert "line1 line2 line3" == cleaned["with_newlines"]

        # Excessive whitespace should be cleaned
        assert cleaned["with_whitespace"] == "lots of spaces"

        # Normal strings should remain unchanged
        assert cleaned["normal_string"] == "normal text"

    def test_export_to_string_with_headers(self, exporter):
        """Test exporting records to CSV string format with headers."""
        records = [{"name": "John", "age": 30}, {"name": "Jane", "age": 25}]

        csv_string = exporter.export_to_string(records, include_headers=True)

        lines = csv_string.strip().split("\n")
        assert len(lines) == 3  # Header + 2 data rows
        assert "name,age" in lines[0]
        assert "John,30" in lines[1]
        assert "Jane,25" in lines[2]

    def test_export_to_string_without_headers(self, exporter):
        """Test exporting records to CSV string format without headers."""
        records = [{"name": "John", "age": 30}, {"name": "Jane", "age": 25}]

        csv_string = exporter.export_to_string(records, include_headers=False)

        lines = csv_string.strip().split("\n")
        assert len(lines) == 2  # Only data rows
        assert "John,30" in lines[0]
        assert "Jane,25" in lines[1]

    def test_export_to_string_empty_records(self, exporter):
        """Test exporting empty records to string."""
        csv_string = exporter.export_to_string([])
        assert csv_string == ""

    def test_get_output_directory(self, exporter, temp_dir):
        """Test getting the configured output directory."""
        assert exporter.get_output_directory() == temp_dir

    def test_set_output_directory(self, exporter, temp_dir):
        """Test setting a new output directory."""
        new_dir = temp_dir / "new_output"
        exporter.set_output_directory(new_dir)

        assert exporter.get_output_directory() == new_dir
        assert new_dir.exists()

    @pytest.mark.asyncio
    async def test_export_batch_filename_format(self, exporter, sample_data, temp_dir):
        """Test that CSV filenames follow the expected format."""
        customer_id = "test_customer_456"

        with patch("paidsearchnav.exports.csv.datetime") as mock_datetime:
            # Mock datetime to get predictable filename
            mock_datetime.now.return_value.strftime.return_value = "2024-01-15_10-30-45"

            result = await exporter.export_batch(customer_id, sample_data)

            files_created = result.metadata["files_created"]
            assert len(files_created) == 2

            for file_path in files_created:
                filename = Path(file_path).name
                assert filename.startswith(customer_id)
                assert "2024-01-15_10-30-45" in filename
                assert filename.endswith(".csv")

    @pytest.mark.asyncio
    async def test_export_batch_file_permissions_error(self, exporter, sample_data):
        """Test handling of file permission errors during export."""
        customer_id = "test_customer"

        # Mock the _write_csv_file method to raise a permission error
        with patch.object(
            exporter,
            "_write_csv_file",
            side_effect=PermissionError("Permission denied"),
        ):
            result = await exporter.export_batch(customer_id, sample_data)

            assert result.status == ExportStatus.FAILED
            assert "Permission denied" in result.error_message

    @pytest.mark.asyncio
    async def test_csv_special_characters_handling(self, exporter, temp_dir):
        """Test handling of special characters in CSV data."""
        test_records = [
            {
                "name": 'John "Johnny" Smith',
                "description": "Line1\nLine2",
                "data": "comma,separated,values",
            }
        ]

        test_file = temp_dir / "special_chars.csv"
        await exporter._write_csv_file(test_file, test_records)

        # Read back and verify proper escaping
        with open(test_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Should contain properly escaped content
        assert '"John ""Johnny"" Smith"' in content or 'John "Johnny" Smith' in content
        # Newlines should be handled in cleaned records
        assert "\n" not in content or content.count("\n") <= 2  # Header + 1 data row
