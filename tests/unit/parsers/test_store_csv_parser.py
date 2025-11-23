"""Unit tests for StoreCSVParser."""

import tempfile
from pathlib import Path

import pytest

from paidsearchnav_mcp.parsers.store_csv_parser import StoreCSVParser


class TestStoreCSVParser:
    """Test cases for StoreCSVParser."""

    def test_validate_numeric_fields(self):
        """Test numeric field validation and cleaning."""
        data = {
            "local_impressions": "1,234",
            "store_visits": "567",
            "call_clicks": 89,
            "driving_directions": "not_a_number",  # Invalid value for numeric field
            "website_visits": "",  # Empty string for numeric field
            "other_field": "unchanged",  # Non-numeric field - should remain unchanged
        }

        cleaned_data = StoreCSVParser.validate_numeric_fields(data)

        assert cleaned_data["local_impressions"] == 1234
        assert cleaned_data["store_visits"] == 567
        assert cleaned_data["call_clicks"] == 89
        assert cleaned_data["driving_directions"] == 0  # Should be set to 0
        assert cleaned_data["website_visits"] == 0  # Should be set to 0
        assert (
            cleaned_data["other_field"] == "unchanged"
        )  # Non-numeric fields left unchanged

    def test_safe_str_cast(self):
        """Test safe string casting."""
        assert StoreCSVParser.safe_str_cast("hello") == "hello"
        assert StoreCSVParser.safe_str_cast(123) == "123"
        assert StoreCSVParser.safe_str_cast(None) == ""
        assert StoreCSVParser.safe_str_cast(None, "default") == "default"

    def test_detect_header_rows_with_report_title(self):
        """Test header detection with report title."""
        csv_content = """Per store report
"May 18, 2025 - August 15, 2025"
Store locations,address_line_1,city
Store 1,123 Main St,City
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            temp_path = Path(f.name)

        try:
            skip_rows = StoreCSVParser._detect_header_rows(temp_path)
            assert skip_rows == 2
        finally:
            temp_path.unlink()

    def test_detect_header_rows_without_title(self):
        """Test header detection without report title."""
        csv_content = """Store locations,address_line_1,city
Store 1,123 Main St,City
Store 2,456 Oak Ave,Town
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            temp_path = Path(f.name)

        try:
            skip_rows = StoreCSVParser._detect_header_rows(temp_path)
            assert skip_rows == 0
        finally:
            temp_path.unlink()

    def test_parse_csv_valid_file(self):
        """Test CSV parsing with valid file."""
        csv_content = """Per store report
"May 18, 2025 - August 15, 2025"
Store locations,address_line_1,city,Local reach (impressions),Store visits
Fitness Connection,6320 Albemarle Road,Charlotte,"27,145",870
Fitness Connection,8428 Denton Highway,Watauga,"56,710","2,212"
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            temp_path = Path(f.name)

        try:
            data = StoreCSVParser.parse_csv(temp_path)
            assert len(data) == 2
            assert data[0]["store_name"] == "Fitness Connection"
            assert data[0]["city"] == "Charlotte"
            assert "local_impressions" in data[0]
        finally:
            temp_path.unlink()

    def test_parse_csv_missing_location_column(self):
        """Test CSV parsing with missing location column."""
        csv_content = """Per store report
"May 18, 2025 - August 15, 2025"
address_line_1,city,Local reach (impressions)
6320 Albemarle Road,Charlotte,"27,145"
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            temp_path = Path(f.name)

        try:
            with pytest.raises(ValueError, match="No location identifier column found"):
                StoreCSVParser.parse_csv(temp_path)
        finally:
            temp_path.unlink()
