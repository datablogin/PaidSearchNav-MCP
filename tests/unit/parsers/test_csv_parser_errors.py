"""Unit tests for CSV parser error handling."""

import csv

import pytest

from paidsearchnav.parsers.csv_parser import GoogleAdsCSVParser


class TestCSVParserErrorHandling:
    """Test suite for CSV parser error handling scenarios."""

    @pytest.fixture
    def parser(self):
        """Create a GoogleAdsCSVParser instance with strict validation."""
        return GoogleAdsCSVParser(file_type="keywords", strict_validation=True)

    @pytest.fixture
    def parser_lenient(self):
        """Create a GoogleAdsCSVParser instance with lenient validation."""
        return GoogleAdsCSVParser(file_type="keywords", strict_validation=False)

    def test_empty_csv_file(self, parser, tmp_path):
        """Test handling of completely empty CSV file."""
        empty_file = tmp_path / "empty.csv"
        empty_file.write_text("")

        with pytest.raises(ValueError, match="CSV file is empty"):
            parser.parse(empty_file)

    def test_csv_with_only_headers(self, parser, tmp_path):
        """Test handling of CSV file with only headers and no data."""
        headers_only = tmp_path / "headers_only.csv"
        headers_only.write_text("Keyword ID,Campaign,Keyword\n")

        with pytest.raises(ValueError, match="CSV file contains no data rows"):
            parser.parse(headers_only)

    def test_csv_with_only_empty_rows(self, parser, tmp_path):
        """Test handling of CSV file with headers and only empty rows."""
        empty_rows = tmp_path / "empty_rows.csv"
        with open(empty_rows, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Keyword ID", "Campaign", "Keyword"])
            writer.writerow(["", "", ""])
            writer.writerow(["", "", ""])

        with pytest.raises(ValueError, match="CSV file contains only empty rows"):
            parser.parse(empty_rows)

    def test_missing_required_headers(self, parser, tmp_path):
        """Test handling of CSV file missing required headers."""
        missing_headers = tmp_path / "missing_headers.csv"
        with open(missing_headers, "w", newline="") as f:
            writer = csv.writer(f)
            # Missing required fields: Keyword ID, Campaign ID, Ad group ID, etc.
            writer.writerow(["Keyword", "Clicks", "Cost"])
            writer.writerow(["buy shoes", "100", "50.00"])

        with pytest.raises(ValueError, match="Missing required fields"):
            parser.parse(missing_headers)

    def test_invalid_numeric_values_strict(self, parser, tmp_path):
        """Test handling of invalid numeric values with strict validation."""
        invalid_data = tmp_path / "invalid_numeric.csv"
        with open(invalid_data, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "Keyword ID",
                    "Campaign ID",
                    "Campaign",
                    "Ad group ID",
                    "Ad group",
                    "Keyword",
                    "Match type",
                    "Status",
                    "Impr.",
                    "Cost",
                ]
            )
            writer.writerow(
                [
                    "123",
                    "456",
                    "Campaign 1",
                    "789",
                    "Ad Group 1",
                    "test keyword",
                    "EXACT",
                    "ENABLED",
                    "not_a_number",
                    "also_not_a_number",
                ]
            )

        with pytest.raises(ValueError, match="Invalid (integer|numeric) value"):
            parser.parse(invalid_data)

    def test_invalid_numeric_values_lenient(self, parser_lenient, tmp_path):
        """Test handling of invalid numeric values with lenient validation."""
        invalid_data = tmp_path / "invalid_numeric_lenient.csv"
        with open(invalid_data, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "Keyword ID",
                    "Campaign ID",
                    "Campaign",
                    "Ad group ID",
                    "Ad group",
                    "Keyword",
                    "Match type",
                    "Status",
                    "Impr.",
                    "Cost",
                ]
            )
            # Add one valid row
            writer.writerow(
                [
                    "123",
                    "456",
                    "Campaign 1",
                    "789",
                    "Ad Group 1",
                    "valid keyword",
                    "EXACT",
                    "ENABLED",
                    "1000",
                    "50.00",
                ]
            )
            # Add row with invalid numeric values - fields should get default values in lenient mode
            writer.writerow(
                [
                    "124",
                    "456",
                    "Campaign 1",
                    "789",
                    "Ad Group 1",
                    "test keyword",
                    "EXACT",
                    "ENABLED",
                    "not_a_number",
                    "also_not_a_number",
                ]
            )

        # Should not raise error in lenient mode
        # Rows with invalid required fields are skipped entirely
        result = parser_lenient.parse(invalid_data)
        assert len(result) == 1  # Only the valid row is returned

        # First row should have valid values
        assert result[0].text == "valid keyword"
        assert result[0].impressions == 1000
        assert result[0].cost == 50.0

        # The second row with invalid numeric values is skipped entirely
        # because impressions is a required field and cannot be parsed

    def test_currency_and_percentage_values(self, parser, tmp_path):
        """Test handling of currency symbols and percentage values."""
        formatted_data = tmp_path / "formatted_values.csv"
        with open(formatted_data, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "Keyword ID",
                    "Campaign ID",
                    "Campaign",
                    "Ad group ID",
                    "Ad group",
                    "Keyword",
                    "Match type",
                    "Status",
                    "Cost",
                    "CTR",
                ]
            )
            writer.writerow(
                [
                    "123",
                    "456",
                    "Campaign 1",
                    "789",
                    "Ad Group 1",
                    "test keyword",
                    "EXACT",
                    "ENABLED",
                    "$1,234.56",
                    "5.5%",
                ]
            )

        result = parser.parse(formatted_data)
        assert len(result) == 1
        assert result[0].cost == 1234.56
        # CTR would be in the mapped field, check if it's properly converted
        # Note: CTR might not be in the model directly, depends on field mapping

    def test_malformed_csv_structure(self, parser, tmp_path):
        """Test handling of malformed CSV structure."""
        malformed = tmp_path / "malformed.csv"
        with open(malformed, "w") as f:
            # Write inconsistent number of columns
            f.write("col1,col2,col3\n")
            f.write("val1,val2\n")  # Missing column
            f.write("val1,val2,val3,val4\n")  # Extra column

        with pytest.raises(ValueError, match="CSV format error|Error parsing CSV"):
            parser.parse(malformed)

    def test_encoding_error_detection(self, parser, tmp_path):
        """Test automatic encoding detection on error."""
        # Create a file with UTF-16 encoding
        utf16_file = tmp_path / "utf16.csv"
        with open(utf16_file, "w", encoding="utf-16") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "Keyword ID",
                    "Campaign ID",
                    "Campaign",
                    "Ad group ID",
                    "Ad group",
                    "Keyword",
                    "Match type",
                    "Status",
                ]
            )
            writer.writerow(
                [
                    "123",
                    "456",
                    "Campaña",
                    "789",
                    "Grupo de anuncios",
                    "palabra clave",
                    "EXACT",
                    "ENABLED",
                ]
            )

        # Parser is initialized with utf-8, should auto-detect UTF-16 and succeed
        parser_utf8 = GoogleAdsCSVParser(file_type="keywords", encoding="utf-8")

        # With charset-normalizer available, should auto-detect UTF-16 and parse successfully
        results = parser_utf8.parse(utf16_file)
        assert len(results) == 1
        assert results[0].text == "palabra clave"

    def test_file_size_limit(self, parser, tmp_path):
        """Test file size limit validation."""
        large_file = tmp_path / "large.csv"

        # Create a parser with very small size limit
        small_parser = GoogleAdsCSVParser(
            file_type="keywords",
            max_file_size=100,  # 100 bytes
        )

        # Create a file larger than the limit
        with open(large_file, "w") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "Keyword ID",
                    "Campaign ID",
                    "Campaign",
                    "Ad group ID",
                    "Ad group",
                    "Keyword",
                    "Match type",
                    "Status",
                ]
            )
            # Write enough rows to exceed 100 bytes
            for i in range(10):
                writer.writerow(
                    [
                        f"id{i}",
                        f"camp{i}",
                        f"Campaign {i}",
                        f"adg{i}",
                        f"Ad Group {i}",
                        f"keyword {i}",
                        "EXACT",
                        "ENABLED",
                    ]
                )

        with pytest.raises(ValueError, match="exceeds maximum allowed size"):
            small_parser.parse(large_file)

    def test_search_term_with_missing_metrics(self, tmp_path):
        """Test search term parsing with missing metric fields."""
        parser_st = GoogleAdsCSVParser(file_type="search_terms", strict_validation=True)

        missing_metrics = tmp_path / "search_terms_missing.csv"
        with open(missing_metrics, "w", newline="") as f:
            writer = csv.writer(f)
            # Missing several metric fields
            writer.writerow(
                [
                    "Campaign ID",
                    "Campaign",
                    "Ad group ID",
                    "Ad group",
                    "Search term",
                    "Impr.",
                ]
            )
            writer.writerow(
                ["123", "Campaign 1", "456", "Ad Group 1", "test search term", "1000"]
            )

        result = parser_st.parse(missing_metrics)
        assert len(result) == 1
        assert result[0].search_term == "test search term"
        assert result[0].metrics.impressions == 1000
        # Other metrics should have default values or be None

    def test_special_characters_in_data(self, parser, tmp_path):
        """Test handling of special characters in CSV data."""
        special_chars = tmp_path / "special_chars.csv"
        with open(special_chars, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "Keyword ID",
                    "Campaign ID",
                    "Campaign",
                    "Ad group ID",
                    "Ad group",
                    "Keyword",
                    "Match type",
                    "Status",
                ]
            )
            # Include quotes, commas, newlines in data
            writer.writerow(
                [
                    "123",
                    "456",
                    'Campaign "Special"',
                    "789",
                    "Ad Group, Inc.",
                    "keyword with\nnewline",
                    "EXACT",
                    "ENABLED",
                ]
            )

        result = parser.parse(special_chars)
        assert len(result) == 1
        assert result[0].campaign_name == 'Campaign "Special"'
        assert result[0].ad_group_name == "Ad Group, Inc."
        assert "keyword with\nnewline" in result[0].text

    def test_duplicate_headers(self, parser, tmp_path):
        """Test handling of duplicate column headers."""
        duplicate_headers = tmp_path / "duplicate_headers.csv"
        with open(duplicate_headers, "w", newline="") as f:
            # Manually write headers with Campaign ID included
            f.write(
                "Keyword ID,Campaign ID,Campaign,Campaign,Ad group ID,Ad group,Keyword,Match type,Status\n"
            )
            f.write(
                "123,456,Campaign 1,Campaign 2,789,Ad Group 1,test keyword,EXACT,ENABLED\n"
            )

        # Pandas typically handles this by renaming duplicate columns
        result = parser.parse(duplicate_headers)
        assert len(result) == 1

    def test_geo_performance_invalid_location_type(self, tmp_path):
        """Test geo performance parsing with invalid location type."""
        parser_geo = GoogleAdsCSVParser(file_type="geo_performance")

        invalid_geo = tmp_path / "invalid_geo.csv"
        with open(invalid_geo, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "Customer ID",
                    "Campaign ID",
                    "Campaign",
                    "Location type",
                    "Location",
                    "Location ID",
                    "Impr.",
                    "Clicks",
                ]
            )
            writer.writerow(
                [
                    "123",
                    "456",
                    "Campaign 1",
                    "INVALID_TYPE",
                    "New York",
                    "1014044",
                    "1000",
                    "50",
                ]
            )

        result = parser_geo.parse(invalid_geo)
        assert len(result) == 1
        # Should default to "OTHER" for invalid location types
        assert result[0].location_type == "OTHER"

    def test_comprehensive_csv_injection_protection(self, parser, tmp_path):
        """Test comprehensive CSV injection protection."""
        injection_file = tmp_path / "injection_test.csv"
        with open(injection_file, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "Keyword ID",
                    "Campaign ID",
                    "Campaign",
                    "Ad group ID",
                    "Ad group",
                    "Keyword",
                    "Match type",
                    "Status",
                ]
            )
            # Various injection attempts
            writer.writerow(
                [
                    "123",
                    "456",
                    "=1+1",
                    "789",
                    "@SUM(A1:A10)",
                    "+441234567890",
                    "EXACT",
                    "-command",
                ]
            )
            writer.writerow(
                [
                    "124",
                    "457",
                    "\r\n=cmd",
                    "790",
                    "\t=SYSTEM()",
                    '=HYPERLINK("http://evil.com")',
                    "PHRASE",
                    "ENABLED",
                ]
            )

        result = parser.parse(injection_file)
        assert len(result) == 2

        # Check that all formula-like values are sanitized
        assert result[0].campaign_name == "'=1+1"
        assert result[0].ad_group_name == "'@SUM(A1:A10)"
        assert result[0].text == "'+441234567890"
        assert (
            result[0].status == "ENABLED"
        )  # Status values should be validated, not just sanitized

        assert result[1].campaign_name.startswith("'")
        assert result[1].ad_group_name.startswith("'")
        assert result[1].text == '\'=HYPERLINK("http://evil.com")'
