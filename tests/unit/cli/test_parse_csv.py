"""Tests for the parse-csv CLI command."""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from click.testing import CliRunner

from paidsearchnav_mcp.cli.parse_csv import parse_csv


@pytest.fixture
def cli_runner():
    """Create CLI runner for testing."""
    return CliRunner()


@pytest.fixture
def sample_keyword_csv():
    """Create a sample keyword CSV file."""
    content = """Keyword ID,Campaign ID,Campaign,Ad group ID,Ad group,Keyword,Match type,Status,Max. CPC,Quality Score,Impressions,Clicks,Cost,Avg. CPC,CTR,Conversions,Conv. rate,Avg. position
123456789,987654321,Campaign 1,456789123,Ad Group 1,running shoes,EXACT,ENABLED,2.50,8,1000,50,125.00,2.50,5.00%,10,20.00%,2.1
234567890,987654321,Campaign 1,456789123,Ad Group 1,buy running shoes,PHRASE,ENABLED,3.00,7,800,40,120.00,3.00,5.00%,8,20.00%,2.5
345678901,987654322,Campaign 2,567890124,Ad Group 2,marathon training,BROAD,ENABLED,1.50,9,500,25,37.50,1.50,5.00%,5,20.00%,1.8"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write(content)
        temp_path = Path(f.name)

    yield temp_path

    # Cleanup
    temp_path.unlink(missing_ok=True)


@pytest.fixture
def sample_search_term_csv():
    """Create a sample search term CSV file."""
    content = """Campaign ID,Campaign,Ad group ID,Ad group,Search term,Keyword,Match type,Added/Excluded,Impressions,Clicks,Cost,CTR,Avg. CPC,Conversions,Conv. rate
987654321,Campaign 1,456789123,Ad Group 1,running shoes near me,running shoes,EXACT,Added,1200,60,150.00,5.00%,2.50,12,20.00%
987654321,Campaign 1,456789123,Ad Group 1,best running shoes 2024,running shoes,BROAD,Added,800,32,96.00,4.00%,3.00,6,18.75%"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write(content)
        temp_path = Path(f.name)

    yield temp_path

    # Cleanup
    temp_path.unlink(missing_ok=True)


@pytest.fixture
def invalid_csv():
    """Create an invalid CSV file."""
    content = """This is not a valid CSV
It has no structure
Just random text"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write(content)
        temp_path = Path(f.name)

    yield temp_path

    # Cleanup
    temp_path.unlink(missing_ok=True)


class TestParseCsvCommand:
    """Test the parse-csv command."""

    def test_parse_keyword_csv_success(self, cli_runner, sample_keyword_csv):
        """Test successful parsing of keyword CSV."""
        result = cli_runner.invoke(
            parse_csv, ["--file", str(sample_keyword_csv), "--type", "keyword"]
        )

        assert result.exit_code == 0
        assert "Successfully parsed 3 records" in result.output
        assert "Parsing keyword CSV file" in result.output

    def test_parse_search_term_csv_success(self, cli_runner, sample_search_term_csv):
        """Test successful parsing of search term CSV."""
        result = cli_runner.invoke(
            parse_csv, ["--file", str(sample_search_term_csv), "--type", "search_term"]
        )

        assert result.exit_code == 0
        assert "Successfully parsed 2 records" in result.output
        assert "Parsing search_term CSV file" in result.output

    def test_parse_with_sample_output(self, cli_runner, sample_keyword_csv):
        """Test parsing with sample output display."""
        result = cli_runner.invoke(
            parse_csv,
            ["--file", str(sample_keyword_csv), "--type", "keyword", "--show-sample"],
        )

        assert result.exit_code == 0
        assert "Sample records" in result.output
        assert "Campaign 1" in result.output  # This should be visible in the table

    def test_parse_with_custom_sample_size(self, cli_runner, sample_keyword_csv):
        """Test parsing with custom sample size."""
        result = cli_runner.invoke(
            parse_csv,
            [
                "--file",
                str(sample_keyword_csv),
                "--type",
                "keyword",
                "--show-sample",
                "--sample-size",
                "2",
            ],
        )

        assert result.exit_code == 0
        assert "Sample records (first 2)" in result.output

    def test_parse_without_validation(self, cli_runner, sample_keyword_csv):
        """Test parsing without validation."""
        result = cli_runner.invoke(
            parse_csv,
            ["--file", str(sample_keyword_csv), "--type", "keyword", "--no-validate"],
        )

        assert result.exit_code == 0
        assert "Successfully parsed 3 records" in result.output

    def test_file_not_found_error(self, cli_runner):
        """Test error when file doesn't exist."""
        result = cli_runner.invoke(
            parse_csv, ["--file", "nonexistent.csv", "--type", "keyword"]
        )

        assert result.exit_code == 2  # Click exits with code 2 for validation errors
        assert "Path 'nonexistent.csv' does not exist" in result.output

    def test_invalid_file_type(self, cli_runner, sample_keyword_csv):
        """Test error with invalid file type."""
        result = cli_runner.invoke(
            parse_csv, ["--file", str(sample_keyword_csv), "--type", "invalid_type"]
        )

        assert result.exit_code == 2  # Click validation error
        assert "Invalid value" in result.output

    def test_invalid_sample_size(self, cli_runner, sample_keyword_csv):
        """Test error with invalid sample size."""
        result = cli_runner.invoke(
            parse_csv,
            [
                "--file",
                str(sample_keyword_csv),
                "--type",
                "keyword",
                "--sample-size",
                "0",
            ],
        )

        assert result.exit_code == 2  # Click validation error
        assert "Invalid value" in result.output

    def test_sample_size_too_large(self, cli_runner, sample_keyword_csv):
        """Test error with sample size too large."""
        result = cli_runner.invoke(
            parse_csv,
            [
                "--file",
                str(sample_keyword_csv),
                "--type",
                "keyword",
                "--sample-size",
                "101",
            ],
        )

        assert result.exit_code == 2  # Click validation error
        assert "Invalid value" in result.output

    def test_missing_required_options(self, cli_runner):
        """Test error when required options are missing."""
        result = cli_runner.invoke(parse_csv, [])

        assert result.exit_code == 2
        assert "Missing option" in result.output

    def test_help_text(self, cli_runner):
        """Test that help text is comprehensive."""
        result = cli_runner.invoke(parse_csv, ["--help"])

        assert result.exit_code == 0
        assert "Parse Google Ads CSV files" in result.output
        assert "Examples:" in result.output
        assert "--file" in result.output
        assert "--type" in result.output
        assert "[keyword|search_term|geo]" in result.output
        assert "max: 100" in result.output  # Check that MAX_SAMPLE_SIZE is shown

    @patch("paidsearchnav.cli.parse_csv.GoogleAdsCSVParser")
    def test_parser_initialization(
        self, mock_parser_class, cli_runner, sample_keyword_csv
    ):
        """Test that parser is initialized with correct parameters."""
        mock_parser = Mock()
        mock_parser.parse.return_value = []
        mock_parser_class.return_value = mock_parser

        result = cli_runner.invoke(
            parse_csv,
            [
                "--file",
                str(sample_keyword_csv),
                "--type",
                "keyword",
                "--encoding",
                "utf-16",
            ],
        )

        assert result.exit_code == 0
        mock_parser_class.assert_called_once_with(
            file_type="keywords", encoding="utf-16"
        )

    @patch("paidsearchnav.cli.parse_csv.GoogleAdsCSVParser")
    def test_large_file_progress_bar(self, mock_parser_class, cli_runner):
        """Test that progress bar is shown for large files."""
        # Create a mock file that appears to be > 10MB
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            temp_path = Path(f.name)

        try:
            # Mock the parser
            mock_parser = Mock()
            mock_parser.parse.return_value = []
            mock_parser.LARGE_FILE_THRESHOLD = 50 * 1024 * 1024  # 50MB
            mock_parser_class.return_value = mock_parser

            # Mock file size to be > 10MB
            with patch.object(Path, "stat") as mock_stat:
                mock_stat.return_value = Mock(st_size=15 * 1024 * 1024)  # 15MB

                result = cli_runner.invoke(
                    parse_csv, ["--file", str(temp_path), "--type", "keyword"]
                )

                assert result.exit_code == 0
                assert "File size: 15.00 MB" in result.output
        finally:
            temp_path.unlink(missing_ok=True)

    @patch("paidsearchnav.cli.parse_csv.GoogleAdsCSVParser")
    def test_validation_error_handling(
        self, mock_parser_class, cli_runner, sample_keyword_csv
    ):
        """Test that validation errors are handled gracefully."""
        mock_parser = Mock()
        mock_parser.parse.side_effect = ValueError(
            "Validation error at Row 2: Invalid keyword format"
        )
        mock_parser_class.return_value = mock_parser

        result = cli_runner.invoke(
            parse_csv, ["--file", str(sample_keyword_csv), "--type", "keyword"]
        )

        assert result.exit_code == 1
        assert (
            "Error: Validation error at Row 2: Invalid keyword format" in result.output
        )

    @patch("paidsearchnav.cli.parse_csv.GoogleAdsCSVParser")
    def test_exception_handling(
        self, mock_parser_class, cli_runner, sample_keyword_csv
    ):
        """Test that exceptions are handled gracefully."""
        mock_parser = Mock()
        mock_parser.parse.side_effect = ValueError("Invalid CSV format")
        mock_parser_class.return_value = mock_parser

        result = cli_runner.invoke(
            parse_csv, ["--file", str(sample_keyword_csv), "--type", "keyword"]
        )

        assert result.exit_code == 1
        assert "Error: Invalid CSV format" in result.output
