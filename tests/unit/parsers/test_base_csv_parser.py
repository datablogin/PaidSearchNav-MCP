"""Unit tests for BaseCSVParser abstract class."""

from pathlib import Path
from typing import Dict, List

import pytest

from paidsearchnav_mcp.parsers.base_csv_parser import (
    BaseCSVParser,
    ColumnMapping,
    CSVParsingError,
)


class DummyCSVParser(BaseCSVParser[Dict[str, str]]):
    """Dummy implementation of BaseCSVParser for testing."""

    def parse(self, file_path: Path) -> List[Dict[str, str]]:
        """Parse implementation for testing."""
        return [{"test": "data"}]

    def validate_headers(self, headers: List[str]) -> bool:
        """Validate headers implementation for testing."""
        return "test" in headers


class TestBaseCSVParser:
    """Tests for BaseCSVParser abstract class."""

    def test_cannot_instantiate_abstract_class(self):
        """Test that BaseCSVParser cannot be instantiated directly."""
        with pytest.raises(TypeError) as exc_info:
            BaseCSVParser()  # type: ignore

        assert "Can't instantiate abstract class" in str(exc_info.value)

    def test_must_implement_parse_method(self):
        """Test that subclasses must implement parse method."""

        class IncompleteParser(BaseCSVParser[Dict[str, str]]):
            """Parser missing parse method."""

            def validate_headers(self, headers: List[str]) -> bool:
                return True

        with pytest.raises(TypeError) as exc_info:
            IncompleteParser()

        assert "Can't instantiate abstract class" in str(exc_info.value)
        assert "parse" in str(exc_info.value)

    def test_must_implement_validate_headers_method(self):
        """Test that subclasses must implement validate_headers method."""

        class IncompleteParser(BaseCSVParser[Dict[str, str]]):
            """Parser missing validate_headers method."""

            def parse(self, file_path: Path) -> List[Dict[str, str]]:
                return []

        with pytest.raises(TypeError) as exc_info:
            IncompleteParser()

        assert "Can't instantiate abstract class" in str(exc_info.value)
        assert "validate_headers" in str(exc_info.value)

    def test_dummy_implementation_works(self):
        """Test that a complete implementation can be instantiated and used."""
        parser = DummyCSVParser()

        # Test parse method
        result = parser.parse(Path("dummy.csv"))
        assert result == [{"test": "data"}]

        # Test validate_headers method
        assert parser.validate_headers(["test", "other"]) is True
        assert parser.validate_headers(["other", "fields"]) is False

    def test_generic_typing_preserved(self):
        """Test that generic typing is preserved in implementations."""

        class TypedRow(Dict[str, str]):
            """Custom typed row dictionary."""

            pass

        class TypedCSVParser(BaseCSVParser[TypedRow]):
            """Parser with custom row type."""

            def parse(self, file_path: Path) -> List[TypedRow]:
                return [TypedRow({"field": "value"})]

            def validate_headers(self, headers: List[str]) -> bool:
                return True

        parser = TypedCSVParser()
        result = parser.parse(Path("test.csv"))

        # Verify the result type
        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], dict)
        assert result[0]["field"] == "value"


class TestColumnMapping:
    """Tests for ColumnMapping dataclass."""

    def test_column_mapping_creation_required_fields_only(self):
        """Test ColumnMapping creation with only required fields."""
        mapping = ColumnMapping(campaign="Campaign", ad_group="Ad Group")

        assert mapping.campaign == "Campaign"
        assert mapping.ad_group == "Ad Group"
        assert mapping.keyword is None
        assert mapping.match_type is None
        assert mapping.search_term is None

    def test_column_mapping_creation_with_optional_fields(self):
        """Test ColumnMapping creation with optional fields."""
        mapping = ColumnMapping(
            campaign="Campaign",
            ad_group="Ad Group",
            keyword="Keyword",
            match_type="Match Type",
            impressions="Impressions",
            clicks="Clicks",
            cost="Cost",
            location="Location",
        )

        assert mapping.campaign == "Campaign"
        assert mapping.ad_group == "Ad Group"
        assert mapping.keyword == "Keyword"
        assert mapping.match_type == "Match Type"
        assert mapping.impressions == "Impressions"
        assert mapping.clicks == "Clicks"
        assert mapping.cost == "Cost"
        assert mapping.location == "Location"

    def test_get_mapping_dict_required_only(self):
        """Test get_mapping_dict with only required fields."""
        mapping = ColumnMapping(campaign="Campaign", ad_group="Ad Group")
        result = mapping.get_mapping_dict()

        expected = {"campaign": "Campaign", "ad_group": "Ad Group"}
        assert result == expected

    def test_get_mapping_dict_with_optional_fields(self):
        """Test get_mapping_dict filters out None values."""
        mapping = ColumnMapping(
            campaign="Campaign",
            ad_group="Ad Group",
            keyword="Keyword",
            impressions="Impressions",
            # match_type and others left as None
        )
        result = mapping.get_mapping_dict()

        expected = {
            "campaign": "Campaign",
            "ad_group": "Ad Group",
            "keyword": "Keyword",
            "impressions": "Impressions",
        }
        assert result == expected

    def test_get_mapping_dict_all_fields(self):
        """Test get_mapping_dict with all fields set."""
        mapping = ColumnMapping(
            campaign="Campaign",
            ad_group="Ad Group",
            keyword="Keyword",
            match_type="Match Type",
            search_term="Search Term",
            impressions="Impressions",
            clicks="Clicks",
            cost="Cost",
            conversions="Conversions",
            location="Location",
            location_type="Location Type",
        )
        result = mapping.get_mapping_dict()

        # All fields should be present
        assert len(result) == 11
        assert result["campaign"] == "Campaign"
        assert result["ad_group"] == "Ad Group"
        assert result["keyword"] == "Keyword"
        assert result["match_type"] == "Match Type"
        assert result["search_term"] == "Search Term"
        assert result["impressions"] == "Impressions"
        assert result["clicks"] == "Clicks"
        assert result["cost"] == "Cost"
        assert result["conversions"] == "Conversions"
        assert result["location"] == "Location"
        assert result["location_type"] == "Location Type"


class TestCSVParsingError:
    """Tests for CSVParsingError exception."""

    def test_basic_error_message(self):
        """Test CSVParsingError with basic message only."""
        error = CSVParsingError("Invalid CSV format")
        assert str(error) == "Invalid CSV format"
        assert error.row_number is None
        assert error.column is None
        assert error.value is None

    def test_error_with_row_number(self):
        """Test CSVParsingError with row number context."""
        error = CSVParsingError("Missing required field", row_number=5)
        assert str(error) == "Missing required field (at row 5)"
        assert error.row_number == 5
        assert error.column is None
        assert error.value is None

    def test_error_with_column(self):
        """Test CSVParsingError with column context."""
        error = CSVParsingError("Invalid value", column="impressions")
        assert str(error) == "Invalid value (at column 'impressions')"
        assert error.row_number is None
        assert error.column == "impressions"
        assert error.value is None

    def test_error_with_value(self):
        """Test CSVParsingError with value context."""
        error = CSVParsingError("Cannot parse value", value="abc123")
        assert str(error) == "Cannot parse value (at value 'abc123')"
        assert error.row_number is None
        assert error.column is None
        assert error.value == "abc123"

    def test_error_with_row_and_column(self):
        """Test CSVParsingError with row and column context."""
        error = CSVParsingError("Type conversion failed", row_number=3, column="cost")
        assert str(error) == "Type conversion failed (at row 3, column 'cost')"
        assert error.row_number == 3
        assert error.column == "cost"
        assert error.value is None

    def test_error_with_all_context(self):
        """Test CSVParsingError with full context information."""
        error = CSVParsingError(
            "Invalid numeric value", row_number=10, column="clicks", value="invalid"
        )
        expected = "Invalid numeric value (at row 10, column 'clicks', value 'invalid')"
        assert str(error) == expected
        assert error.row_number == 10
        assert error.column == "clicks"
        assert error.value == "invalid"

    def test_error_inheritance(self):
        """Test that CSVParsingError properly inherits from Exception."""
        error = CSVParsingError("Test error")
        assert isinstance(error, Exception)

        # Test that it can be raised and caught
        with pytest.raises(CSVParsingError) as exc_info:
            raise error

        assert str(exc_info.value) == "Test error"

    def test_error_context_ordering(self):
        """Test that error context is properly ordered."""
        # Test different combinations to ensure consistent ordering
        error1 = CSVParsingError("Test", row_number=1, value="val")
        assert "row 1" in str(error1) and "value 'val'" in str(error1)

        error2 = CSVParsingError("Test", column="col", value="val")
        assert "column 'col'" in str(error2) and "value 'val'" in str(error2)

        error3 = CSVParsingError("Test", row_number=1, column="col")
        assert "row 1" in str(error3) and "column 'col'" in str(error3)
