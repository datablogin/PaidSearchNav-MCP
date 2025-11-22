"""Unit tests for CSV parser implementation."""

import csv
import os
import tempfile
from pathlib import Path

import pytest

from paidsearchnav_mcp.parsers.csv_parser import CSVParser
from paidsearchnav_mcp.parsers.field_mappings import get_field_mapping


class TestCSVParser:
    """Test suite for CSVParser class."""

    @pytest.fixture
    def temp_csv_file(self):
        """Create a temporary CSV file for testing."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            writer = csv.writer(f)
            writer.writerow(["Keyword", "Campaign", "Clicks", "Cost"])
            writer.writerow(["buy shoes", "Summer Sale", "100", "50.00"])
            writer.writerow(["cheap sneakers", "Summer Sale", "75", "37.50"])
            temp_path = f.name

        yield Path(temp_path)

        # Cleanup
        os.unlink(temp_path)

    @pytest.fixture
    def parser(self):
        """Create a CSVParser instance."""
        return CSVParser(file_type="keywords")

    def test_parse_valid_csv(self, parser, temp_csv_file):
        """Test parsing a valid CSV file."""
        result = parser.parse(temp_csv_file)

        assert len(result) == 2
        assert result[0]["text"] == "buy shoes"
        assert result[0]["campaign_name"] == "Summer Sale"
        assert result[1]["text"] == "cheap sneakers"

    def test_parse_missing_file(self, parser):
        """Test parsing a non-existent file."""
        with pytest.raises(FileNotFoundError, match="File not found"):
            parser.parse(Path("/nonexistent/file.csv"))

    def test_parse_invalid_format(self, parser, tmp_path):
        """Test parsing a non-CSV file."""
        invalid_file = tmp_path / "test.txt"
        invalid_file.write_text("Not a CSV file")

        with pytest.raises(ValueError, match="Expected .csv file"):
            parser.parse(invalid_file)

    def test_field_mapping_keywords(self, temp_csv_file):
        """Test field mapping for keywords file type."""
        parser = CSVParser(file_type="keywords")
        result = parser.parse(temp_csv_file)

        # Check that fields are mapped correctly
        assert "text" in result[0]
        assert "campaign_name" in result[0]
        assert "Keyword" not in result[0]  # Original field should be mapped
        assert "Campaign" not in result[0]  # Original field should be mapped

    def test_field_mapping_search_terms(self):
        """Test field mapping for search terms file type."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            writer = csv.writer(f)
            writer.writerow(["Search term", "Campaign", "Keyword"])
            writer.writerow(["running shoes", "Sports", "shoes"])
            temp_path = f.name

        try:
            parser = CSVParser(file_type="search_terms")
            result = parser.parse(Path(temp_path))

            assert "search_term" in result[0]
            assert result[0]["search_term"] == "running shoes"
        finally:
            os.unlink(temp_path)

    def test_validate_empty_data(self, parser):
        """Test validation of empty data."""
        assert parser.validate([]) is False

    def test_validate_inconsistent_keys(self, parser):
        """Test validation of data with inconsistent keys."""
        data = [
            {"text": "test1", "campaign_name": "camp1"},
            {"text": "test2", "campaign_name": "camp2", "extra": "value"},
        ]
        assert parser.validate(data) is False

    def test_validate_consistent_data(self, parser):
        """Test validation of consistent data."""
        data = [
            {"text": "test1", "campaign_name": "camp1"},
            {"text": "test2", "campaign_name": "camp2"},
        ]
        assert parser.validate(data) is True

    def test_unmapped_fields_preservation(self):
        """Test that unmapped fields are preserved by default."""
        # Create a CSV with an unmapped field
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            writer = csv.writer(f)
            writer.writerow(["Keyword", "Campaign", "Custom Field"])
            writer.writerow(["buy shoes", "Summer Sale", "custom value"])
            temp_path = f.name

        try:
            parser = CSVParser(file_type="keywords")
            result = parser.parse(Path(temp_path))

            # Keyword and Campaign are mapped
            assert "text" in result[0]
            assert "campaign_name" in result[0]
            # Custom Field is not mapped and should be preserved
            assert "Custom Field" in result[0]
            assert result[0]["Custom Field"] == "custom value"
        finally:
            os.unlink(temp_path)

    def test_unmapped_fields_not_preserved(self):
        """Test that unmapped fields are not preserved when disabled."""
        # Create a CSV with an unmapped field
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            writer = csv.writer(f)
            writer.writerow(["Keyword", "Campaign", "Custom Field"])
            writer.writerow(["buy shoes", "Summer Sale", "custom value"])
            temp_path = f.name

        try:
            parser = CSVParser(file_type="keywords", preserve_unmapped=False)
            result = parser.parse(Path(temp_path))

            # Keyword and Campaign are mapped
            assert "text" in result[0]
            assert "campaign_name" in result[0]
            # Custom Field is not mapped and should NOT be preserved
            assert "Custom Field" not in result[0]
        finally:
            os.unlink(temp_path)

    def test_encoding_support(self, tmp_path):
        """Test support for different encodings."""
        # Create a CSV with non-ASCII characters
        csv_file = tmp_path / "test_encoding.csv"
        with open(csv_file, "w", encoding="utf-16") as f:
            writer = csv.writer(f)
            writer.writerow(["Keyword", "Campaign"])
            writer.writerow(["café", "Campaña"])

        parser = CSVParser(encoding="utf-16")
        result = parser.parse(csv_file)

        assert result[0]["Keyword"] == "café"
        assert result[0]["Campaign"] == "Campaña"

    def test_encoding_error(self, tmp_path):
        """Test handling of encoding errors."""
        # Create a file with UTF-16 encoding
        csv_file = tmp_path / "test_encoding_error.csv"
        with open(csv_file, "w", encoding="utf-16") as f:
            writer = csv.writer(f)
            writer.writerow(["Keyword", "Campaign"])
            writer.writerow(["café", "Campaña"])

        # Try to read with wrong encoding
        parser = CSVParser(encoding="utf-8")
        with pytest.raises(ValueError, match="File encoding error"):
            parser.parse(csv_file)

    def test_file_size_limit(self, tmp_path):
        """Test file size limit validation."""
        large_file = tmp_path / "large.csv"

        # Create a file larger than the limit
        with open(large_file, "w") as f:
            writer = csv.writer(f)
            writer.writerow(["Keyword", "Campaign"])
            for i in range(1000):
                writer.writerow([f"keyword{i}", f"campaign{i}"])

        # Set a small file size limit
        parser = CSVParser(max_file_size=100)  # 100 bytes

        with pytest.raises(ValueError, match="exceeds maximum allowed size"):
            parser.parse(large_file)

    def test_csv_injection_protection(self):
        """Test protection against CSV injection attacks."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            writer = csv.writer(f)
            writer.writerow(["Keyword", "Formula"])
            writer.writerow(["safe keyword", "normal value"])
            writer.writerow(["=1+1", "=SUM(A1:A10)"])
            writer.writerow(["+1234", "-5678"])
            writer.writerow(["@macro", "\ttab_prefixed"])
            temp_path = f.name

        try:
            parser = CSVParser()
            result = parser.parse(Path(temp_path))

            # Check that formula prefixes are sanitized
            assert result[1]["Keyword"] == "'=1+1"
            assert result[1]["Formula"] == "'=SUM(A1:A10)"
            assert result[2]["Keyword"] == "'+1234"
            assert result[2]["Formula"] == "'-5678"
            assert result[3]["Keyword"] == "'@macro"
            assert result[3]["Formula"] == "'\ttab_prefixed"

            # Check that safe values are not modified
            assert result[0]["Keyword"] == "safe keyword"
            assert result[0]["Formula"] == "normal value"
        finally:
            os.unlink(temp_path)

    def test_csv_format_error(self, tmp_path):
        """Test handling of malformed CSV files."""
        bad_csv = tmp_path / "bad.csv"
        # Write binary content that will cause CSV parsing to fail
        bad_csv.write_bytes(b"\xff\xfe\x00\x00This is not a CSV file")

        parser = CSVParser()
        with pytest.raises(ValueError) as exc_info:
            parser.parse(bad_csv)

        # Check that we get an error when parsing - could be encoding or CSV error
        error_msg = str(exc_info.value)
        assert (
            "Error parsing CSV file" in error_msg or "File encoding error" in error_msg
        )

    def test_default_file_type(self, temp_csv_file):
        """Test parser with default file type (no mapping)."""
        parser = CSVParser()  # Default file_type
        result = parser.parse(temp_csv_file)

        # Original field names should be preserved
        assert "Keyword" in result[0]
        assert "Campaign" in result[0]
        assert "text" not in result[0]  # Should not be mapped


class TestFieldMappings:
    """Test suite for field mappings."""

    def test_get_field_mapping_keywords(self):
        """Test getting field mapping for keywords."""
        mapping = get_field_mapping("keywords")
        assert mapping["Keyword"] == "text"
        assert mapping["Campaign"] == "campaign_name"

    def test_get_field_mapping_unknown_type(self):
        """Test getting field mapping for unknown type."""
        mapping = get_field_mapping("unknown_type")
        assert mapping == {}  # Should return default empty mapping

    def test_all_mapping_types(self):
        """Test that all defined mapping types work."""
        types = ["keywords", "search_terms", "campaigns", "ad_groups", "default"]
        for file_type in types:
            mapping = get_field_mapping(file_type)
            assert isinstance(mapping, dict)
