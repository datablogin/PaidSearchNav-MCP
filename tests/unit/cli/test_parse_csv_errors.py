"""Tests for parse-csv CLI command error handling."""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from click.testing import CliRunner

from paidsearchnav.cli.parse_csv import parse_csv


@pytest.fixture
def cli_runner():
    """Create CLI runner for testing."""
    return CliRunner()


class TestParseCsvErrorHandling:
    """Test error handling in parse-csv CLI command."""

    def test_empty_csv_file(self, cli_runner):
        """Test CLI handling of empty CSV file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            # Create empty file
            temp_path = Path(f.name)

        try:
            with patch(
                "paidsearchnav.cli.parse_csv.GoogleAdsCSVParser"
            ) as mock_parser_class:
                mock_parser = Mock()
                mock_parser.parse.side_effect = ValueError("CSV file is empty")
                mock_parser_class.return_value = mock_parser

                result = cli_runner.invoke(
                    parse_csv, ["--file", str(temp_path), "--type", "keyword"]
                )

                assert result.exit_code == 1
                assert "Error: CSV file is empty" in result.output
        finally:
            temp_path.unlink(missing_ok=True)

    def test_missing_required_fields(self, cli_runner):
        """Test CLI handling of missing required fields."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write("Campaign,Impressions\nCampaign 1,1000")
            temp_path = Path(f.name)

        try:
            with patch(
                "paidsearchnav.cli.parse_csv.GoogleAdsCSVParser"
            ) as mock_parser_class:
                mock_parser = Mock()
                mock_parser.parse.side_effect = ValueError(
                    "Missing required fields: Keyword ID, Campaign ID"
                )
                mock_parser_class.return_value = mock_parser

                result = cli_runner.invoke(
                    parse_csv, ["--file", str(temp_path), "--type", "keyword"]
                )

                assert result.exit_code == 1
                assert "Error: Missing required fields" in result.output
                assert "Keyword ID" in result.output
        finally:
            temp_path.unlink(missing_ok=True)

    def test_invalid_numeric_values(self, cli_runner):
        """Test CLI handling of invalid numeric values."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write("Keyword,Cost\nkeyword1,not_a_number")
            temp_path = Path(f.name)

        try:
            with patch(
                "paidsearchnav.cli.parse_csv.GoogleAdsCSVParser"
            ) as mock_parser_class:
                mock_parser = Mock()
                mock_parser.parse.side_effect = ValueError(
                    "Invalid numeric value 'not_a_number' in field 'Cost'"
                )
                mock_parser_class.return_value = mock_parser

                result = cli_runner.invoke(
                    parse_csv, ["--file", str(temp_path), "--type", "keyword"]
                )

                assert result.exit_code == 1
                assert "Error: Invalid numeric value" in result.output
                assert "Cost" in result.output
        finally:
            temp_path.unlink(missing_ok=True)

    def test_encoding_error(self, cli_runner):
        """Test CLI handling of encoding errors."""
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".csv", delete=False) as f:
            # Write invalid UTF-8 bytes
            f.write(b"\xff\xfe Invalid UTF-8")
            temp_path = Path(f.name)

        try:
            with patch(
                "paidsearchnav.cli.parse_csv.GoogleAdsCSVParser"
            ) as mock_parser_class:
                mock_parser = Mock()
                mock_parser.parse.side_effect = ValueError(
                    "File encoding error: 'utf-8' codec can't decode. Try a different encoding."
                )
                mock_parser_class.return_value = mock_parser

                result = cli_runner.invoke(
                    parse_csv, ["--file", str(temp_path), "--type", "keyword"]
                )

                assert result.exit_code == 1
                assert "Error: File encoding error" in result.output
        finally:
            temp_path.unlink(missing_ok=True)

    def test_csv_format_error(self, cli_runner):
        """Test CLI handling of malformed CSV."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write("col1,col2,col3\nval1,val2\nval1,val2,val3,val4")
            temp_path = Path(f.name)

        try:
            with patch(
                "paidsearchnav.cli.parse_csv.GoogleAdsCSVParser"
            ) as mock_parser_class:
                mock_parser = Mock()
                mock_parser.parse.side_effect = ValueError(
                    "CSV format error: Inconsistent columns"
                )
                mock_parser_class.return_value = mock_parser

                result = cli_runner.invoke(
                    parse_csv, ["--file", str(temp_path), "--type", "keyword"]
                )

                assert result.exit_code == 1
                assert "Error: CSV format error" in result.output
        finally:
            temp_path.unlink(missing_ok=True)

    def test_file_size_exceeded(self, cli_runner):
        """Test CLI handling of file size limit exceeded."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write("header\ndata")
            temp_path = Path(f.name)

        try:
            with patch(
                "paidsearchnav.cli.parse_csv.GoogleAdsCSVParser"
            ) as mock_parser_class:
                mock_parser = Mock()
                mock_parser.parse.side_effect = ValueError(
                    "File size (101000000 bytes) exceeds maximum allowed size (100000000 bytes)"
                )
                mock_parser_class.return_value = mock_parser

                result = cli_runner.invoke(
                    parse_csv, ["--file", str(temp_path), "--type", "keyword"]
                )

                assert result.exit_code == 1
                assert "Error: File size" in result.output
                assert "exceeds maximum allowed size" in result.output
        finally:
            temp_path.unlink(missing_ok=True)

    def test_csv_with_only_empty_rows(self, cli_runner):
        """Test CLI handling of CSV with only empty rows."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write("Keyword,Campaign\n,,\n,,")
            temp_path = Path(f.name)

        try:
            with patch(
                "paidsearchnav.cli.parse_csv.GoogleAdsCSVParser"
            ) as mock_parser_class:
                mock_parser = Mock()
                mock_parser.parse.side_effect = ValueError(
                    "CSV file contains only empty rows"
                )
                mock_parser_class.return_value = mock_parser

                result = cli_runner.invoke(
                    parse_csv, ["--file", str(temp_path), "--type", "keyword"]
                )

                assert result.exit_code == 1
                assert "Error: CSV file contains only empty rows" in result.output
        finally:
            temp_path.unlink(missing_ok=True)

    def test_validation_error_at_specific_row(self, cli_runner):
        """Test CLI handling of validation error at specific row."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write("Keyword,Campaign\nkeyword1,camp1")
            temp_path = Path(f.name)

        try:
            with patch(
                "paidsearchnav.cli.parse_csv.GoogleAdsCSVParser"
            ) as mock_parser_class:
                mock_parser = Mock()
                mock_parser.parse.side_effect = ValueError(
                    "Validation error at Row 5: Invalid keyword format"
                )
                mock_parser_class.return_value = mock_parser

                result = cli_runner.invoke(
                    parse_csv, ["--file", str(temp_path), "--type", "keyword"]
                )

                assert result.exit_code == 1
                assert "Error: Validation error at Row 5" in result.output
                assert "Invalid keyword format" in result.output
        finally:
            temp_path.unlink(missing_ok=True)

    def test_file_not_found_during_parsing(self, cli_runner):
        """Test CLI handling when file is deleted during parsing."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write("test")
            temp_path = Path(f.name)

        try:
            with patch(
                "paidsearchnav.cli.parse_csv.GoogleAdsCSVParser"
            ) as mock_parser_class:
                mock_parser = Mock()
                mock_parser.parse.side_effect = FileNotFoundError(
                    "File not found: test.csv"
                )
                mock_parser_class.return_value = mock_parser

                result = cli_runner.invoke(
                    parse_csv, ["--file", str(temp_path), "--type", "keyword"]
                )

                assert result.exit_code == 1
                assert "Error: File not found" in result.output
        finally:
            temp_path.unlink(missing_ok=True)

    def test_unexpected_error_handling(self, cli_runner):
        """Test CLI handling of unexpected errors."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write("test")
            temp_path = Path(f.name)

        try:
            with patch(
                "paidsearchnav.cli.parse_csv.GoogleAdsCSVParser"
            ) as mock_parser_class:
                mock_parser = Mock()
                # Simulate an unexpected error that's not a ValueError
                mock_parser.parse.side_effect = RuntimeError(
                    "Unexpected internal error"
                )
                mock_parser_class.return_value = mock_parser

                result = cli_runner.invoke(
                    parse_csv, ["--file", str(temp_path), "--type", "keyword"]
                )

                assert result.exit_code == 1
                assert "Unexpected error" in result.output
        finally:
            temp_path.unlink(missing_ok=True)

    def test_validation_disabled_shows_no_errors(self, cli_runner):
        """Test that validation errors are suppressed when --no-validate is used."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write("Keyword,Campaign\nkeyword1,camp1")
            temp_path = Path(f.name)

        try:
            with patch(
                "paidsearchnav.cli.parse_csv.GoogleAdsCSVParser"
            ) as mock_parser_class:
                mock_parser = Mock()
                # Parser should not raise errors when strict_validation is False
                mock_parser.parse.return_value = []
                mock_parser_class.return_value = mock_parser

                result = cli_runner.invoke(
                    parse_csv,
                    ["--file", str(temp_path), "--type", "keyword", "--no-validate"],
                )

                assert result.exit_code == 0
                assert "Successfully parsed 0 records" in result.output
                # Verify that strict_validation was set to False
                assert mock_parser.strict_validation is False
        finally:
            temp_path.unlink(missing_ok=True)
