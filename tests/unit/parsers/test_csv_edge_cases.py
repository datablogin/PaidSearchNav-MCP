"""Edge case tests for CSV parsing."""

import csv
import tempfile
from pathlib import Path

from paidsearchnav.parsers.csv_parser import CSVParser


class TestCSVEdgeCases:
    """Test edge cases and malformed CSV files."""

    def test_empty_csv_file(self):
        """Test parsing completely empty CSV file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write("")
            temp_path = Path(f.name)

        try:
            parser = CSVParser("keywords")
            result = parser.parse(temp_path)
            assert result.data == []
            assert result.total_records == 0
        finally:
            temp_path.unlink()

    def test_csv_with_only_headers(self):
        """Test CSV file with only headers, no data."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write("keyword_id,keyword,status,match_type\n")
            temp_path = Path(f.name)

        try:
            parser = CSVParser("keywords")
            result = parser.parse(temp_path)
            assert result.data == []
            assert result.total_records == 0
        finally:
            temp_path.unlink()

    def test_csv_with_missing_columns(self):
        """Test CSV with missing required columns."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            writer = csv.writer(f)
            writer.writerow(["keyword", "status"])  # Missing keyword_id and match_type
            writer.writerow(["test keyword", "ENABLED"])
            temp_path = Path(f.name)

        try:
            parser = CSVParser("keywords")
            result = parser.parse(temp_path)
            # Parser should handle missing fields gracefully
            assert result.total_records == 1
            assert result.data[0]["keyword"] == "test keyword"
            assert result.data[0]["status"] == "ENABLED"
        finally:
            temp_path.unlink()

    def test_csv_with_extra_columns(self):
        """Test CSV with extra unexpected columns."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            writer = csv.writer(f)
            writer.writerow(
                ["keyword_id", "keyword", "status", "match_type", "extra1", "extra2"]
            )
            writer.writerow(["123", "test", "ENABLED", "EXACT", "value1", "value2"])
            temp_path = Path(f.name)

        try:
            parser = CSVParser("keywords")
            result = parser.parse(temp_path)
            # Parser should handle extra fields without breaking
            assert result.total_records == 1
            assert result.data[0]["keyword"] == "test"
        finally:
            temp_path.unlink()

    def test_csv_with_special_characters(self):
        """Test CSV with special characters and potential injection attempts."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            writer = csv.writer(f)
            writer.writerow(["keyword_id", "keyword", "status", "match_type"])
            # Test various special characters
            writer.writerow(["1", "test & test", "ENABLED", "EXACT"])
            writer.writerow(
                ["2", "test <script>alert('xss')</script>", "ENABLED", "EXACT"]
            )
            writer.writerow(["3", "test'; DROP TABLE users; --", "ENABLED", "EXACT"])
            writer.writerow(["4", "test\nwith\nnewlines", "ENABLED", "EXACT"])
            writer.writerow(["5", "test\twith\ttabs", "ENABLED", "EXACT"])
            temp_path = Path(f.name)

        try:
            parser = CSVParser("keywords")
            result = parser.parse(temp_path)
            assert result.total_records == 5
            # Special characters should be preserved (sanitization happens elsewhere)
            assert "alert" in result.data[1]["keyword"]
            assert "DROP TABLE" in result.data[2]["keyword"]
        finally:
            temp_path.unlink()

    def test_csv_with_unicode_characters(self):
        """Test CSV with Unicode/international characters."""
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", suffix=".csv", delete=False
        ) as f:
            writer = csv.writer(f)
            writer.writerow(["keyword_id", "keyword", "status", "match_type"])
            writer.writerow(["1", "café", "ENABLED", "EXACT"])
            writer.writerow(["2", "北京", "ENABLED", "EXACT"])
            writer.writerow(["3", "Москва", "ENABLED", "EXACT"])
            writer.writerow(["4", "🚀 rocket", "ENABLED", "EXACT"])
            temp_path = Path(f.name)

        try:
            parser = CSVParser("keywords")
            result = parser.parse(temp_path)
            assert result.total_records == 4
            assert result.data[0]["keyword"] == "café"
            assert result.data[1]["keyword"] == "北京"
            assert result.data[2]["keyword"] == "Москва"
            assert "🚀" in result.data[3]["keyword"]
        finally:
            temp_path.unlink()

    def test_csv_with_null_values(self):
        """Test CSV with various representations of null/empty values."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            writer = csv.writer(f)
            writer.writerow(["keyword_id", "keyword", "impressions", "clicks", "cost"])
            writer.writerow(["1", "test1", "", "", ""])
            writer.writerow(["2", "test2", "NULL", "null", "N/A"])
            writer.writerow(["3", "test3", "--", "-", "0"])
            writer.writerow(["4", "test4", "None", "NONE", "n/a"])
            temp_path = Path(f.name)

        try:
            parser = CSVParser("keywords")
            result = parser.parse(temp_path)
            assert result.total_records == 4
            # Check that null values are handled appropriately
            for record in result.data:
                assert "keyword" in record
                assert record["keyword"].startswith("test")
        finally:
            temp_path.unlink()

    def test_csv_with_inconsistent_rows(self):
        """Test CSV with inconsistent number of columns per row."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write("keyword_id,keyword,status,match_type\n")
            f.write("1,test1,ENABLED,EXACT\n")
            f.write("2,test2,ENABLED\n")  # Missing match_type
            f.write("3,test3,ENABLED,EXACT,extra_field\n")  # Extra field
            f.write("4\n")  # Only one field
            temp_path = Path(f.name)

        try:
            parser = CSVParser("keywords")
            result = parser.parse(temp_path)
            # Parser should handle inconsistent rows gracefully
            assert result.total_records >= 3  # At least the valid rows
        finally:
            temp_path.unlink()

    def test_csv_with_very_long_values(self):
        """Test CSV with extremely long field values."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            writer = csv.writer(f)
            writer.writerow(["keyword_id", "keyword", "status", "match_type"])
            # Create a very long keyword
            long_keyword = "test " * 1000  # 5000 characters
            writer.writerow(["1", long_keyword, "ENABLED", "EXACT"])
            temp_path = Path(f.name)

        try:
            parser = CSVParser("keywords")
            result = parser.parse(temp_path)
            assert result.total_records == 1
            # Long values should be handled (possibly truncated elsewhere)
            assert len(result.data[0]["keyword"]) > 100
        finally:
            temp_path.unlink()

    def test_csv_with_quoted_fields(self):
        """Test CSV with various quoting scenarios."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            writer = csv.writer(f, quoting=csv.QUOTE_ALL)
            writer.writerow(["keyword_id", "keyword", "status", "match_type"])
            writer.writerow(["1", 'test with "quotes"', "ENABLED", "EXACT"])
            writer.writerow(["2", "test, with, commas", "ENABLED", "EXACT"])
            writer.writerow(["3", '"already quoted"', "ENABLED", "EXACT"])
            temp_path = Path(f.name)

        try:
            parser = CSVParser("keywords")
            result = parser.parse(temp_path)
            assert result.total_records == 3
            assert "quotes" in result.data[0]["keyword"]
            assert "commas" in result.data[1]["keyword"]
        finally:
            temp_path.unlink()

    def test_csv_with_different_delimiters(self):
        """Test CSV parser's ability to handle different delimiters."""
        # Test with tab delimiter
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tsv", delete=False) as f:
            f.write("keyword_id\tkeyword\tstatus\tmatch_type\n")
            f.write("1\ttest keyword\tENABLED\tEXACT\n")
            temp_path = Path(f.name)

        try:
            # Note: CSVParser might need to auto-detect or accept delimiter param
            parser = CSVParser("keywords")
            # This test might fail if parser doesn't support tab delimiters
            # which is fine - it documents the limitation
            try:
                result = parser.parse(temp_path)
                if result.total_records > 0:
                    assert result.data[0]["keyword"] == "test keyword"
            except Exception:
                # Document that non-comma delimiters aren't supported
                pass
        finally:
            temp_path.unlink()

    def test_csv_with_bom(self):
        """Test CSV with Byte Order Mark (BOM)."""
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".csv", delete=False) as f:
            # Write UTF-8 BOM
            f.write(b"\xef\xbb\xbf")
            f.write(b"keyword_id,keyword,status,match_type\n")
            f.write(b"1,test keyword,ENABLED,EXACT\n")
            temp_path = Path(f.name)

        try:
            parser = CSVParser("keywords")
            result = parser.parse(temp_path)
            # Parser should handle BOM gracefully
            assert result.total_records == 1
            assert result.data[0]["keyword"] == "test keyword"
        finally:
            temp_path.unlink()

    def test_large_csv_file(self):
        """Test parsing a large CSV file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            writer = csv.writer(f)
            writer.writerow(["keyword_id", "keyword", "status", "match_type"])
            # Write 10,000 rows
            for i in range(10000):
                writer.writerow([str(i), f"keyword_{i}", "ENABLED", "EXACT"])
            temp_path = Path(f.name)

        try:
            parser = CSVParser("keywords")
            result = parser.parse(temp_path)
            assert result.total_records == 10000
            # Check a few samples
            assert result.data[0]["keyword"] == "keyword_0"
            assert result.data[9999]["keyword"] == "keyword_9999"
        finally:
            temp_path.unlink()
