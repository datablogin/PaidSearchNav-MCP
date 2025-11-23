"""Tests for CSV formatting utilities."""

import csv
from io import StringIO

import pytest

from paidsearchnav_mcp.platforms.google.scripts.csv_formatter import (
    CSVCompatibilityValidator,
    CSVFormatter,
)


class TestCSVFormatter:
    """Test CSVFormatter functionality."""

    @pytest.fixture
    def formatter(self):
        """Create CSVFormatter instance."""
        return CSVFormatter()

    def test_format_search_terms_csv_basic(self, formatter):
        """Test basic search terms CSV formatting."""
        data = [
            {
                "Campaign": "Test Campaign",
                "Ad Group": "Test Ad Group",
                "Search Term": "test keyword",
                "Match Type": "Exact",
                "Clicks": 10,
                "Impressions": 100,
                "Cost": 25.50,
                "Conversions": 2,
                "Conv. Rate": 0.2,
                "Cost / Conv.": 12.75,
                "CPC": 2.55,
                "CTR": 0.1,
                "Impression Share": 0.85,
            }
        ]

        csv_output = formatter.format_search_terms_csv(data)

        # Parse the CSV to verify structure
        reader = csv.reader(StringIO(csv_output))
        rows = list(reader)

        # Check headers
        headers = rows[0]
        assert "Campaign" in headers
        assert "Search term" in headers
        assert "Clicks" in headers

        # Check data row
        data_row = rows[1]
        assert data_row[0] == "Test Campaign"
        assert data_row[2] == "test keyword"  # Search term column
        assert data_row[4] == "10"  # Clicks
        assert data_row[6] == "$25.50"  # Cost formatted as currency

    def test_format_search_terms_csv_with_geographic_data(self, formatter):
        """Test search terms CSV formatting with geographic data."""
        data = [
            {
                "Campaign": "Test Campaign",
                "Ad Group": "Test Ad Group",
                "Search Term": "gym near me",
                "Match Type": "Phrase",
                "Clicks": 5,
                "Impressions": 50,
                "Cost": 15.25,
                "Conversions": 1,
                "Conv. Rate": 0.2,
                "Cost / Conv.": 15.25,
                "CPC": 3.05,
                "CTR": 0.1,
                "Impression Share": 0.75,
                "Geographic Location": "Dallas, TX",
                "Location Type": "City",
                "Is Local Intent": True,
            }
        ]

        csv_output = formatter.format_search_terms_csv(data)

        # Parse the CSV to verify geographic data inclusion
        reader = csv.reader(StringIO(csv_output))
        rows = list(reader)

        headers = rows[0]
        assert "Geographic Location" in headers
        assert "Location Type" in headers
        assert "Is Local Intent" in headers

        data_row = rows[1]
        geo_location_idx = headers.index("Geographic Location")
        assert data_row[geo_location_idx] == "Dallas, TX"

    def test_format_keywords_csv_with_quality_score(self, formatter):
        """Test keywords CSV formatting with quality score data."""
        data = [
            {
                "Campaign": "Test Campaign",
                "Ad Group": "Test Ad Group",
                "Keyword": "[test keyword]",
                "Match Type": "Exact",
                "Clicks": 15,
                "Impressions": 200,
                "Cost": 45.00,
                "Conversions": 3,
                "Conv. Rate": 0.2,
                "Cost / Conv.": 15.00,
                "CPC": 3.00,
                "CTR": 0.075,
                "Avg. Position": 2.5,
                "Max CPC": 5.00,
                "Status": "Enabled",
                "Quality Score": 8,
                "Landing Page Experience": "Above average",
                "Ad Relevance": "Above average",
                "Expected CTR": "Average",
                "First Page Bid": 2.80,
                "Top of Page Bid": 4.20,
                "Bid Recommendation": "Increase to top of page",
            }
        ]

        csv_output = formatter.format_keywords_csv(data)

        reader = csv.reader(StringIO(csv_output))
        rows = list(reader)

        headers = rows[0]
        assert "Quality Score" in headers
        assert "Bid recommendation" in headers

        data_row = rows[1]
        quality_score_idx = headers.index("Quality Score")
        assert data_row[quality_score_idx] == "8"

    def test_format_bulk_actions_csv(self, formatter):
        """Test bulk actions CSV formatting."""
        data = [
            {
                "Action": "CREATE",
                "Campaign": "Test Campaign",
                "Ad Group": "Test Ad Group",
                "Keyword": "test keyword",
                "Match Type": "Exact",
                "Max CPC": 2.50,
                "Landing Page": "https://example.com",
                "Status": "Enabled",
                "First Page Bid Estimate": 1.80,
                "Top of Page Bid Estimate": 2.20,
            }
        ]

        csv_output = formatter.format_bulk_actions_csv(data)

        reader = csv.reader(StringIO(csv_output))
        rows = list(reader)

        # Verify bulk actions format matches expected structure
        headers = rows[0]
        expected_headers = [
            "Action",
            "Campaign",
            "Ad Group",
            "Keyword",
            "Match Type",
            "Max CPC",
            "Landing Page",
            "Status",
            "First Page Bid Estimate",
            "Top of Page Bid Estimate",
        ]
        assert headers == expected_headers

        data_row = rows[1]
        assert data_row[0] == "CREATE"
        assert (
            data_row[3] == "[test keyword]"
        )  # Should be formatted with brackets for exact match
        assert data_row[5] == "2.50"  # No currency symbol in bulk actions

    def test_format_geographic_csv(self, formatter):
        """Test geographic performance CSV formatting."""
        data = [
            {
                "Campaign": "Test Campaign",
                "Ad Group": "Test Ad Group",
                "Geographic Location": "Dallas, TX",
                "Location Type": "Target City",
                "Clicks": 25,
                "Impressions": 300,
                "Cost": 62.50,
                "Conversions": 5,
                "Conv. Rate": 0.2,
                "Cost / Conv.": 12.50,
                "CPC": 2.50,
                "CTR": 0.083,
                "Distance": "0-5 miles",
                "Local Intent Score": "High",
                "Store Performance Rank": 2,
            }
        ]

        csv_output = formatter.format_geographic_csv(data)

        reader = csv.reader(StringIO(csv_output))
        rows = list(reader)

        headers = rows[0]
        assert "Geographic Location" in headers
        assert "Local Intent Score" in headers
        assert "Store Performance Rank" in headers

    def test_format_campaign_csv_with_all_data(self, formatter):
        """Test campaign CSV formatting with device and demographic data."""
        data = [
            {
                "Campaign": "Test Campaign",
                "Campaign Type": "Search",
                "Status": "Enabled",
                "Budget": 100.00,
                "Clicks": 50,
                "Impressions": 1000,
                "Cost": 125.00,
                "Conversions": 10,
                "Conv. Rate": 0.2,
                "Cost / Conv.": 12.50,
                "CPC": 2.50,
                "CTR": 0.05,
                "Impression Share": 0.8,
                "Budget Utilization": "90%",
                "Performance Score": "High",
                "Mobile Clicks": "60%",
                "Desktop Clicks": "35%",
                "Tablet Clicks": "5%",
                "Mobile Conv Rate": "2.5%",
                "Desktop Conv Rate": "3.2%",
                "Age 18-24 Performance": "Medium",
                "Age 25-34 Performance": "High",
                "Age 35-44 Performance": "High",
                "Age 45-54 Performance": "Medium",
                "Age 55+ Performance": "Low",
            }
        ]

        csv_output = formatter.format_campaign_csv(data)

        reader = csv.reader(StringIO(csv_output))
        rows = list(reader)

        headers = rows[0]
        assert "Mobile clicks %" in headers
        assert "Age 25-34" in headers

    def test_number_formatting(self, formatter):
        """Test number formatting helper method."""
        assert formatter._format_number(10) == "10"
        assert formatter._format_number(10.0) == "10"
        assert formatter._format_number(10.5) == "10.5"
        assert formatter._format_number(10.50) == "10.5"
        assert formatter._format_number("10.25") == "10.25"
        assert formatter._format_number("5%") == "5"
        assert formatter._format_number(None) == "0"
        assert formatter._format_number("") == "0"

    def test_currency_formatting(self, formatter):
        """Test currency formatting helper method."""
        assert formatter._format_currency(10) == "$10.00"
        assert formatter._format_currency(10.5) == "$10.50"
        assert formatter._format_currency("25.75") == "$25.75"
        assert formatter._format_currency("$15.25") == "$15.25"
        assert formatter._format_currency(None) == "$0.00"
        assert formatter._format_currency("") == "$0.00"

    def test_percentage_formatting(self, formatter):
        """Test percentage formatting helper method."""
        assert formatter._format_percentage(0.05) == "5.00%"
        assert formatter._format_percentage(0.1) == "10.00%"
        assert (
            formatter._format_percentage(5.5) == "5.50%"
        )  # Already in percentage form
        assert formatter._format_percentage("3.25%") == "3.25%"
        assert formatter._format_percentage(None) == "0.00%"
        assert formatter._format_percentage("") == "0.00%"

    def test_keyword_formatting_for_bulk_actions(self, formatter):
        """Test keyword formatting for different match types."""
        assert (
            formatter._format_keyword_for_bulk_action("test keyword", "Exact")
            == "[test keyword]"
        )
        assert (
            formatter._format_keyword_for_bulk_action("test keyword", "Phrase")
            == '"test keyword"'
        )
        assert (
            formatter._format_keyword_for_bulk_action("test keyword", "Broad")
            == "test keyword"
        )
        assert formatter._format_keyword_for_bulk_action("", "Exact") == ""

    def test_bid_formatting_for_bulk_actions(self, formatter):
        """Test bid formatting for bulk actions (no currency symbol)."""
        assert formatter._format_bid_for_bulk_action(2.50) == "2.50"
        assert formatter._format_bid_for_bulk_action("$3.75") == "3.75"
        assert formatter._format_bid_for_bulk_action("5.00") == "5.00"
        assert formatter._format_bid_for_bulk_action(None) == "0.00"
        assert formatter._format_bid_for_bulk_action("") == "0.00"


class TestCSVCompatibilityValidator:
    """Test CSVCompatibilityValidator functionality."""

    @pytest.fixture
    def validator(self):
        """Create CSVCompatibilityValidator instance."""
        return CSVCompatibilityValidator()

    def test_validate_search_terms_format_valid(self, validator):
        """Test validation of valid search terms CSV."""
        csv_content = """Campaign,Search term,Clicks,Impressions,Cost
Test Campaign,test keyword,10,100,$25.50"""

        result = validator.validate_search_terms_format(csv_content)

        assert result["valid"] is True
        assert len(result["errors"]) == 0
        assert result["row_count"] == 1
        assert "Campaign" in result["headers"]

    def test_validate_search_terms_format_missing_headers(self, validator):
        """Test validation with missing required headers."""
        csv_content = """Campaign,Search term,Clicks
Test Campaign,test keyword,10"""

        result = validator.validate_search_terms_format(csv_content)

        assert result["valid"] is False
        assert len(result["errors"]) > 0
        assert "Missing required headers" in result["errors"][0]

    def test_validate_keywords_format_valid(self, validator):
        """Test validation of valid keywords CSV."""
        csv_content = """Campaign,Keyword,Match Type,Clicks,Impressions
Test Campaign,[test keyword],Exact,10,100"""

        result = validator.validate_keywords_format(csv_content)

        assert result["valid"] is True
        assert len(result["errors"]) == 0

    def test_validate_bulk_actions_format_valid(self, validator):
        """Test validation of valid bulk actions CSV."""
        csv_content = """Action,Campaign,Ad Group,Keyword,Match Type,Max CPC
CREATE,Test Campaign,Test Ad Group,[test keyword],Exact,2.50"""

        result = validator.validate_bulk_actions_format(csv_content)

        assert result["valid"] is True
        assert len(result["errors"]) == 0

    def test_validate_bulk_actions_content_warnings(self, validator):
        """Test bulk actions content validation with warnings."""
        csv_content = """Action,Campaign,Ad Group,Keyword,Match Type,Max CPC
INVALID_ACTION,Test Campaign,Test Ad Group,test keyword,Exact,2.50"""

        result = validator.validate_bulk_actions_format(csv_content)

        # Should be valid structurally but have content warnings
        assert result["valid"] is True
        assert len(result["warnings"]) > 0

    def test_validate_csv_structure_malformed(self, validator):
        """Test validation of malformed CSV."""
        csv_content = """Campaign,Search term,Clicks
Test Campaign,test keyword"""  # Missing value

        result = validator._validate_csv_structure(
            csv_content,
            required_headers=["Campaign", "Search term", "Clicks"],
            format_type="test",
        )

        assert result["valid"] is True  # Structure is valid even with missing data
        assert result["row_count"] == 1

    def test_validate_csv_structure_empty(self, validator):
        """Test validation of CSV with no data rows."""
        csv_content = """Campaign,Search term,Clicks,Impressions,Cost"""

        result = validator._validate_csv_structure(
            csv_content,
            required_headers=["Campaign", "Search term", "Clicks"],
            format_type="test",
        )

        assert result["valid"] is True
        assert result["row_count"] == 0
        assert len(result["warnings"]) > 0
        assert "No data rows found" in result["warnings"][0]

    def test_validate_csv_structure_parse_error(self, validator):
        """Test validation with CSV parsing error."""
        # Invalid CSV with unescaped quotes
        csv_content = """Campaign,Search term,Clicks
Test Campaign,"broken quote,10"""

        result = validator._validate_csv_structure(
            csv_content,
            required_headers=["Campaign", "Search term", "Clicks"],
            format_type="test",
        )

        # Should handle parsing errors gracefully
        assert "row_count" in result
        assert "headers" in result


class TestCSVFormatterIntegration:
    """Test CSV formatter integration scenarios."""

    @pytest.fixture
    def formatter(self):
        """Create CSVFormatter instance."""
        return CSVFormatter()

    @pytest.fixture
    def validator(self):
        """Create CSVCompatibilityValidator instance."""
        return CSVCompatibilityValidator()

    def test_format_and_validate_search_terms(self, formatter, validator):
        """Test formatting and validating search terms CSV."""
        data = [
            {
                "Campaign": "Test Campaign",
                "Ad Group": "Test Ad Group",
                "Search Term": "fitness near me",
                "Match Type": "Phrase",
                "Clicks": 25,
                "Impressions": 500,
                "Cost": 75.25,
                "Conversions": 5,
                "Conv. Rate": 0.2,
                "Cost / Conv.": 15.05,
                "CPC": 3.01,
                "CTR": 0.05,
                "Impression Share": 0.75,
            }
        ]

        # Format the data
        csv_output = formatter.format_search_terms_csv(data)

        # Validate the output
        result = validator.validate_search_terms_format(csv_output)

        assert result["valid"] is True
        assert result["row_count"] == 1
        assert len(result["errors"]) == 0

    def test_format_and_validate_bulk_actions(self, formatter, validator):
        """Test formatting and validating bulk actions CSV."""
        data = [
            {
                "Action": "CREATE",
                "Campaign": "Test Campaign",
                "Ad Group": "Test Ad Group",
                "Keyword": "gym membership",
                "Match Type": "Exact",
                "Max CPC": 3.50,
                "Landing Page": "https://example.com/membership",
                "Status": "Enabled",
                "First Page Bid Estimate": 2.80,
                "Top of Page Bid Estimate": 4.20,
            }
        ]

        # Format the data
        csv_output = formatter.format_bulk_actions_csv(data)

        # Validate the output
        result = validator.validate_bulk_actions_format(csv_output)

        assert result["valid"] is True
        assert result["row_count"] == 1
        assert len(result["errors"]) == 0

    def test_format_large_dataset(self, formatter):
        """Test formatting performance with larger dataset."""
        # Create a larger dataset
        data = []
        for i in range(1000):
            data.append(
                {
                    "Campaign": f"Campaign {i}",
                    "Ad Group": f"Ad Group {i}",
                    "Search Term": f"keyword {i}",
                    "Match Type": "Exact",
                    "Clicks": i * 2,
                    "Impressions": i * 20,
                    "Cost": i * 2.50,
                    "Conversions": i // 10,
                    "Conv. Rate": 0.05,
                    "Cost / Conv.": 25.00,
                    "CPC": 2.50,
                    "CTR": 0.1,
                    "Impression Share": 0.8,
                }
            )

        # Should format without errors
        csv_output = formatter.format_search_terms_csv(data)

        # Verify output
        lines = csv_output.split("\n")
        assert len(lines) == 1002  # 1000 data rows + 1 header + 1 empty line at end

    def test_edge_cases_handling(self, formatter):
        """Test handling of edge cases in data."""
        data = [
            {
                "Campaign": "",  # Empty string
                "Ad Group": None,  # None value
                "Search Term": "test keyword",
                "Match Type": "Exact",
                "Clicks": 0,  # Zero value
                "Impressions": None,  # None numeric
                "Cost": "",  # Empty string for numeric
                "Conversions": "N/A",  # Non-numeric string
                "Conv. Rate": None,
                "Cost / Conv.": 0,
                "CPC": "",
                "CTR": None,
                "Impression Share": "Unknown",
            }
        ]

        # Should handle edge cases gracefully
        csv_output = formatter.format_search_terms_csv(data)

        # Parse to verify it's valid CSV
        reader = csv.reader(StringIO(csv_output))
        rows = list(reader)

        assert len(rows) == 2  # Header + 1 data row
        data_row = rows[1]

        # Verify empty/None values are handled
        assert data_row[0] == ""  # Empty campaign
        assert data_row[1] == ""  # None ad group
        assert data_row[4] == "0"  # Zero clicks


class TestStreamingCSVWriter:
    """Test StreamingCSVWriter functionality."""

    @pytest.fixture
    def sample_headers(self):
        """Sample CSV headers for testing."""
        return ["Campaign", "Keyword", "Clicks", "Cost", "Conv. Rate"]

    def test_streaming_writer_initialization(self, sample_headers):
        """Test streaming writer initialization."""
        from io import StringIO

        output = StringIO()

        from paidsearchnav.platforms.google.scripts.csv_formatter import (
            StreamingCSVWriter,
        )

        writer = StreamingCSVWriter(output, sample_headers)

        assert writer.rows_written == 0
        assert not writer._headers_written
        assert writer.headers == sample_headers

    def test_write_headers(self, sample_headers):
        """Test header writing."""
        from io import StringIO

        output = StringIO()

        from paidsearchnav.platforms.google.scripts.csv_formatter import (
            StreamingCSVWriter,
        )

        writer = StreamingCSVWriter(output, sample_headers)

        writer.write_headers()

        assert writer._headers_written
        content = output.getvalue()
        assert "Campaign" in content
        assert "Keyword" in content

    def test_write_single_row(self, sample_headers):
        """Test writing a single data row."""
        from io import StringIO

        output = StringIO()

        from paidsearchnav.platforms.google.scripts.csv_formatter import (
            StreamingCSVWriter,
        )

        writer = StreamingCSVWriter(output, sample_headers)

        row_data = {
            "Campaign": "Test Campaign",
            "Keyword": "test keyword",
            "Clicks": 10,
            "Cost": 25.50,
            "Conv. Rate": 0.05,
        }

        writer.write_row(row_data)

        assert writer.rows_written == 1
        content = output.getvalue()
        lines = content.strip().split("\n")
        assert len(lines) == 2  # Header + data row
        assert "Test Campaign" in content
        assert "$25.50" in content
        assert "5.00%" in content

    def test_write_batch(self, sample_headers):
        """Test writing a batch of rows."""
        from io import StringIO

        output = StringIO()

        from paidsearchnav.platforms.google.scripts.csv_formatter import (
            StreamingCSVWriter,
        )

        writer = StreamingCSVWriter(output, sample_headers)

        batch_data = [
            {
                "Campaign": "Campaign 1",
                "Keyword": "keyword 1",
                "Clicks": 10,
                "Cost": 20.00,
                "Conv. Rate": 0.1,
            },
            {
                "Campaign": "Campaign 2",
                "Keyword": "keyword 2",
                "Clicks": 15,
                "Cost": 30.00,
                "Conv. Rate": 0.15,
            },
        ]

        writer.write_batch(batch_data)

        assert writer.rows_written == 2
        content = output.getvalue()
        assert "Campaign 1" in content
        assert "Campaign 2" in content

    def test_write_from_generator(self, sample_headers):
        """Test writing from a generator."""
        from io import StringIO

        output = StringIO()

        from paidsearchnav.platforms.google.scripts.csv_formatter import (
            StreamingCSVWriter,
        )

        writer = StreamingCSVWriter(output, sample_headers)

        def data_generator():
            for i in range(5):
                yield {
                    "Campaign": f"Campaign {i}",
                    "Keyword": f"keyword {i}",
                    "Clicks": i * 10,
                    "Cost": i * 5.00,
                    "Conv. Rate": i * 0.01,
                }

        writer.write_from_generator(data_generator())

        assert writer.rows_written == 5
        content = output.getvalue()
        assert "Campaign 0" in content
        assert "Campaign 4" in content

    def test_formatting_integration(self, sample_headers):
        """Test data formatting integration in streaming writer."""
        from io import StringIO

        output = StringIO()

        from paidsearchnav.platforms.google.scripts.csv_formatter import (
            StreamingCSVWriter,
        )

        writer = StreamingCSVWriter(output, sample_headers)

        row_data = {
            "Campaign": "Test Campaign",
            "Keyword": "test keyword",
            "Clicks": 1000,
            "Cost": 125.75,
            "Conv. Rate": 0.0525,  # 5.25%
        }

        writer.write_row(row_data)

        content = output.getvalue()
        # Verify formatting is applied correctly
        assert "$125.75" in content  # Currency formatting
        assert "5.25%" in content  # Percentage formatting
        assert "1000" in content  # Number formatting

    def test_bulk_action_keyword_formatting(self):
        """Test keyword formatting for bulk actions."""
        from io import StringIO

        output = StringIO()

        headers = ["Action", "Campaign", "Keyword", "Match Type", "Max CPC"]

        from paidsearchnav.platforms.google.scripts.csv_formatter import (
            StreamingCSVWriter,
        )

        writer = StreamingCSVWriter(output, headers)

        row_data = {
            "Action": "CREATE",
            "Campaign": "Test Campaign",
            "Keyword": "test keyword",
            "Match Type": "Exact",
            "Max CPC": 2.50,
        }

        writer.write_row(row_data)

        content = output.getvalue()
        # Keyword should be formatted with brackets for exact match
        assert "[test keyword]" in content
        # Bid should be formatted without currency symbol
        assert "2.50" in content and "$2.50" not in content

    def test_get_stats(self, sample_headers):
        """Test statistics tracking."""
        from io import StringIO

        output = StringIO()

        from paidsearchnav.platforms.google.scripts.csv_formatter import (
            StreamingCSVWriter,
        )

        writer = StreamingCSVWriter(output, sample_headers)

        # Write some test data
        for i in range(3):
            writer.write_row(
                {
                    "Campaign": f"Campaign {i}",
                    "Keyword": f"keyword {i}",
                    "Clicks": i,
                    "Cost": i * 1.0,
                    "Conv. Rate": 0.05,
                }
            )

        stats = writer.get_stats()

        assert stats["rows_written"] == 3
        assert stats["headers_count"] == 5
        assert stats["headers_written"] is True

    def test_error_handling_with_missing_data(self, sample_headers):
        """Test handling of missing data in rows."""
        from io import StringIO

        output = StringIO()

        from paidsearchnav.platforms.google.scripts.csv_formatter import (
            StreamingCSVWriter,
        )

        writer = StreamingCSVWriter(output, sample_headers)

        # Row with missing data
        incomplete_row = {
            "Campaign": "Test Campaign",
            # Missing Keyword, Clicks, Cost, Conv. Rate
        }

        writer.write_row(incomplete_row)

        assert writer.rows_written == 1
        content = output.getvalue()
        # Should handle missing data gracefully
        assert "Test Campaign" in content

    def test_large_dataset_simulation(self, sample_headers):
        """Test performance with simulated large dataset."""
        from io import StringIO

        output = StringIO()

        from paidsearchnav.platforms.google.scripts.csv_formatter import (
            StreamingCSVWriter,
        )

        writer = StreamingCSVWriter(output, sample_headers)

        # Simulate writing 1500 rows (should trigger progress logging)
        def large_data_generator():
            for i in range(1500):
                yield {
                    "Campaign": f"Campaign {i % 10}",  # Cycle through 10 campaigns
                    "Keyword": f"keyword {i}",
                    "Clicks": i % 100,
                    "Cost": (i % 100) * 0.50,
                    "Conv. Rate": (i % 10) * 0.01,
                }

        writer.write_from_generator(large_data_generator())

        assert writer.rows_written == 1500
        stats = writer.get_stats()
        assert stats["rows_written"] == 1500
