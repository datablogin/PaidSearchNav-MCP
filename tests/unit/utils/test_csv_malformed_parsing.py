"""Tests for CSV parsing error handling and malformed file processing."""

import tempfile
from pathlib import Path

import pytest

from paidsearchnav.parsers.csv_parser import GoogleAdsCSVParser
from paidsearchnav.utils.csv_parsing import (
    CSVValidationResult,
    parse_csv_with_fallbacks,
    validate_csv_structure,
)


class TestCSVValidation:
    """Test CSV validation functionality."""

    def test_validate_valid_csv(self, tmp_path):
        """Test validation of a valid CSV file."""
        csv_file = tmp_path / "valid.csv"
        csv_file.write_text(
            "Keyword,Campaign,Impressions,Clicks,Cost\n"
            "test keyword,Test Campaign,100,10,5.50\n"
            "another keyword,Test Campaign,200,20,10.00\n"
        )

        result = validate_csv_structure(csv_file)
        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_validate_empty_csv(self, tmp_path):
        """Test validation of an empty CSV file."""
        csv_file = tmp_path / "empty.csv"
        csv_file.write_text("")

        result = validate_csv_structure(csv_file)
        assert result.is_valid is False
        assert "File is empty" in result.errors[0]
        assert "Ensure the CSV file contains data" in result.suggested_fixes[0]

    def test_validate_inconsistent_field_counts(self, tmp_path):
        """Test validation of CSV with inconsistent field counts."""
        csv_file = tmp_path / "inconsistent.csv"
        csv_file.write_text(
            "Keyword,Campaign,Impressions,Clicks,Cost\n"
            "test keyword,Test Campaign,100,10,5.50\n"
            "another keyword,Test Campaign,200\n"  # Missing fields
            "third keyword,Test Campaign,300,30,15.00,extra_field\n"  # Extra field
        )

        result = validate_csv_structure(csv_file)
        assert result.is_valid is True  # Warnings, not errors
        assert len(result.warnings) > 0
        assert "Inconsistent field counts detected" in result.warnings[0]
        assert "Check for missing commas" in result.suggested_fixes[0]

    def test_validate_malformed_quotes(self, tmp_path):
        """Test validation of CSV with malformed quotes."""
        csv_file = tmp_path / "malformed_quotes.csv"
        csv_file.write_text(
            "Keyword,Campaign,Impressions,Clicks,Cost\n"
            '"test keyword,Test Campaign,100,10,5.50\n'  # Missing closing quote
            'another keyword","Test Campaign,200,20,10.00\n'  # Quote in wrong place
        )

        result = validate_csv_structure(csv_file)
        assert result.is_valid is False
        assert len(result.errors) > 0
        assert "CSV parsing errors" in result.errors[0]
        assert "unescaped quotes" in result.suggested_fixes[0]

    def test_validate_google_ads_metadata(self, tmp_path):
        """Test validation of Google Ads CSV with metadata headers."""
        csv_file = tmp_path / "google_ads_with_metadata.csv"
        csv_file.write_text(
            "# Google Ads Search Keywords Report\n"
            "# Downloaded: 2023-01-01\n"
            "# Account: Test Account\n"
            "\n"
            "Keyword,Campaign,Impressions,Clicks,Cost\n"
            "test keyword,Test Campaign,100,10,5.50\n"
        )

        result = validate_csv_structure(csv_file)
        assert result.is_valid is True
        assert len(result.warnings) > 0
        assert "Google Ads export metadata" in result.warnings[0]


class TestCSVFallbackParsing:
    """Test CSV parsing with fallback strategies."""

    def test_standard_parsing_success(self, tmp_path):
        """Test that standard parsing works for valid CSV."""
        csv_file = tmp_path / "standard.csv"
        csv_file.write_text(
            "Keyword,Campaign,Impressions,Clicks,Cost\n"
            "test keyword,Test Campaign,100,10,5.50\n"
            "another keyword,Test Campaign,200,20,10.00\n"
        )

        df = parse_csv_with_fallbacks(csv_file)
        assert len(df) == 2
        assert list(df.columns) == [
            "Keyword",
            "Campaign",
            "Impressions",
            "Clicks",
            "Cost",
        ]

    def test_python_engine_fallback(self, tmp_path):
        """Test fallback to Python engine for CSV with issues."""
        csv_file = tmp_path / "python_engine.csv"
        # Create a CSV that might cause issues with C engine
        csv_file.write_text(
            "Keyword,Campaign,Impressions,Clicks,Cost\n"
            '"test keyword with, comma",Test Campaign,100,10,5.50\n'
            '"another keyword\nwith newline",Test Campaign,200,20,10.00\n'
        )

        df = parse_csv_with_fallbacks(csv_file)
        assert len(df) >= 1  # At least one row should parse

    def test_skip_bad_lines_fallback(self, tmp_path):
        """Test fallback to skip bad lines strategy."""
        csv_file = tmp_path / "skip_bad.csv"
        csv_file.write_text(
            "Keyword,Campaign,Impressions,Clicks,Cost\n"
            "test keyword,Test Campaign,100,10,5.50\n"
            'malformed line with "unclosed quote and wrong fields\n'
            "another keyword,Test Campaign,200,20,10.00\n"
            "extra,field,count,in,this,line,should,be,skipped\n"
        )

        df = parse_csv_with_fallbacks(csv_file)
        assert len(df) >= 2  # At least the good rows should parse

    def test_line_by_line_fallback(self, tmp_path):
        """Test line-by-line parsing fallback for severely malformed CSV."""
        csv_file = tmp_path / "line_by_line.csv"
        # Create a severely malformed CSV that pandas can't handle
        csv_file.write_text(
            "Keyword,Campaign,Impressions,Clicks,Cost\n"
            "test keyword,Test Campaign,100,10,5.50\n"
            'bad line with unclosed "quote\n'
            "another keyword,Test Campaign,200,20\n"  # Missing field
            "third keyword,Test Campaign,300,30,15.00,extra\n"  # Extra field
        )

        df = parse_csv_with_fallbacks(csv_file)
        assert len(df) >= 2  # Should recover at least some rows
        assert len(df.columns) == 5  # Should maintain header structure

    def test_all_strategies_fail(self, tmp_path):
        """Test behavior when all parsing strategies fail."""
        csv_file = tmp_path / "completely_broken.csv"
        # Create a file that's not even close to CSV
        csv_file.write_text("This is not a CSV file at all!\nJust random text...")

        with pytest.raises(ValueError, match="All CSV parsing strategies failed"):
            parse_csv_with_fallbacks(csv_file)


class TestGoogleAdsCSVParserErrorHandling:
    """Test GoogleAdsCSVParser error handling for malformed files."""

    def test_parser_with_validation_enabled(self, tmp_path):
        """Test parser behavior with validation enabled."""
        csv_file = tmp_path / "malformed.csv"
        csv_file.write_text(
            "Keyword,Campaign,Impressions\n"
            '"unclosed quote field,Test Campaign,100\n'
            "normal field,Test Campaign,200\n"
        )

        # Strict validation should fail
        parser = GoogleAdsCSVParser(file_type="keywords", strict_validation=True)
        with pytest.raises(ValueError, match="CSV validation failed"):
            parser.parse(csv_file)

        # Lenient validation should succeed with warnings
        parser = GoogleAdsCSVParser(file_type="keywords", strict_validation=False)
        records = parser.parse(csv_file)
        assert len(records) >= 1  # Should parse at least some records

    def test_parser_with_encoding_issues(self, tmp_path):
        """Test parser behavior with encoding issues."""
        csv_file = tmp_path / "encoding_issue.csv"
        # Write with specific encoding that might cause issues
        with open(csv_file, "w", encoding="utf-16") as f:
            f.write("Keyword,Campaign,Impressions\ntest keyword,Test Campaign,100\n")

        # Parser should auto-detect encoding and succeed
        parser = GoogleAdsCSVParser(file_type="keywords", strict_validation=False)
        records = parser.parse(csv_file)
        assert len(records) == 1

    def test_parser_detailed_error_messages(self, tmp_path):
        """Test that parser provides detailed error messages."""
        csv_file = tmp_path / "broken.csv"
        csv_file.write_text("Not a CSV file")

        parser = GoogleAdsCSVParser(file_type="keywords", strict_validation=True)
        with pytest.raises(ValueError) as exc_info:
            parser.parse(csv_file)

        error_msg = str(exc_info.value)
        # Should contain validation details
        assert "CSV validation failed" in error_msg or "parsing" in error_msg.lower()

    def test_parser_handles_cotton_patch_scenario(self, tmp_path):
        """Test parser handling of Cotton Patch Cafe-like scenario from issue."""
        # Simulate the type of CSV that was failing in the issue
        csv_file = tmp_path / "landing_page_report.csv"
        csv_file.write_text(
            "# Google Ads Landing Page Report\n"
            "# All time\n"
            "# Downloaded: 2023-01-01\n"
            "\n"
            'Landing page,Campaign,Impressions,Clicks,"Cost (USD)"\n'
            'https://example.com/page1,"Campaign 1",1000,50,"25.00"\n'
            'https://example.com/page2,"Campaign 2",500,25  # Malformed line\n'
            'https://example.com/page3,"Campaign 3",750,35,"17.50"\n'
        )

        # Should handle this gracefully
        parser = GoogleAdsCSVParser(
            file_type="geo_performance", strict_validation=False
        )
        records = parser.parse(csv_file)
        assert len(records) >= 2  # Should recover most records

    def test_chunked_parsing_with_malformed_csv(self, tmp_path):
        """Test chunked parsing with malformed CSV."""
        csv_file = tmp_path / "large_malformed.csv"

        # Create a larger CSV with some malformed lines
        lines = ["Keyword,Campaign,Impressions,Clicks,Cost\n"]
        for i in range(100):
            if i % 20 == 0:  # Every 20th line is malformed
                lines.append(f'"unclosed quote keyword {i},Campaign {i},100\n')
            else:
                lines.append(
                    f"keyword {i},Campaign {i},{100 + i},{10 + i},{(5 + i):.2f}\n"
                )

        csv_file.write_text("".join(lines))

        # Force chunked parsing
        parser = GoogleAdsCSVParser(
            file_type="keywords",
            strict_validation=False,
            chunk_size=10,
            use_chunked_reading=True,
        )
        records = parser.parse_chunked(csv_file)
        assert len(records) >= 80  # Should recover most records


class TestCSVValidationResult:
    """Test CSVValidationResult class."""

    def test_validation_result_valid(self):
        """Test validation result for valid CSV."""
        result = CSVValidationResult(True, [], [], [])
        assert result.is_valid is True
        assert result.get_error_summary() == "CSV file is valid"

    def test_validation_result_with_errors(self):
        """Test validation result with errors."""
        result = CSVValidationResult(
            False, ["Error 1", "Error 2"], ["Warning 1"], ["Fix 1", "Fix 2"]
        )
        assert result.is_valid is False
        summary = result.get_error_summary()
        assert "Error 1" in summary
        assert "Warning 1" in summary
        assert "Fix 1" in summary

    def test_validation_result_warnings_only(self):
        """Test validation result with only warnings."""
        result = CSVValidationResult(
            True, [], ["Warning 1", "Warning 2"], ["Suggestion 1"]
        )
        assert result.is_valid is True
        summary = result.get_error_summary()
        assert summary == "CSV file is valid"  # No errors = valid


@pytest.fixture
def tmp_path():
    """Provide a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)
