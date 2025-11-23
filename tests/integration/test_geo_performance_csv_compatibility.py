"""Integration tests for geographic performance CSV compatibility fixes.

This test file specifically addresses issue #303 - data model compatibility
issues with Google Ads CSV exports.
"""

import csv
import tempfile
from pathlib import Path

import pytest

from paidsearchnav_mcp.models.geo_performance import GeoPerformanceData
from paidsearchnav_mcp.parsers.csv_parser import GoogleAdsCSVParser
from paidsearchnav_mcp.platforms.google.models import GeoPerformance


class TestGeoPerformanceCSVCompatibility:
    """Test CSV compatibility for geographic performance data."""

    @pytest.fixture
    def sample_geo_csv_dollars(self):
        """Create a sample geo performance CSV with dollar amounts (typical Google Ads export)."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            writer = csv.writer(f)

            # Headers matching typical Google Ads geo performance export
            writer.writerow(
                [
                    "Customer ID",
                    "Campaign ID",
                    "Campaign",
                    "Location type",
                    "Location",
                    "Location ID",
                    "Country",
                    "Region",
                    "City",
                    "Postal code",
                    "Impr.",
                    "Clicks",
                    "Conversions",
                    "Cost",
                    "Conversion value",
                ]
            )

            # Sample data with dollar amounts and string location types
            writer.writerow(
                [
                    "1234567890",
                    "111",
                    "Test Campaign",
                    "City",  # String, not enum
                    "New York, NY",
                    "1023191",
                    "United States",
                    "New York",
                    "New York",
                    "10001",
                    "1000",
                    "50",
                    "5.0",
                    "$123.45",  # Dollar amount with symbol
                    "$987.65",  # Revenue as dollar amount
                ]
            )

            writer.writerow(
                [
                    "1234567890",
                    "111",
                    "Test Campaign",
                    "Postal Code",  # Different location type
                    "Los Angeles, CA 90210",
                    "1023192",
                    "United States",
                    "California",
                    "Los Angeles",
                    "90210",
                    "2000",
                    "100",
                    "10.0",
                    "456.78",  # No dollar symbol
                    "1,234.56",  # Comma-separated revenue
                ]
            )

        return Path(f.name)

    @pytest.fixture
    def sample_geo_csv_encoding_issue(self):
        """Create a CSV with cp1252 encoding to test encoding detection."""
        # Use cp1252 (Windows-1252) encoding instead of UTF-16LE as it's more
        # universally supported and still tests the encoding detection functionality
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="cp1252"
        ) as f:
            writer = csv.writer(f)

            writer.writerow(
                [
                    "Customer ID",
                    "Campaign ID",
                    "Campaign",
                    "Location type",
                    "Location",
                    "Location ID",
                    "Cost",
                    "Conversion value",
                ]
            )

            writer.writerow(
                [
                    "1234567890",
                    "111",
                    "Test Campaign",
                    "State",
                    "Texas",
                    "1023195",
                    "$50.00",
                    "$200.00",
                ]
            )

        return Path(f.name)

    def test_geo_performance_data_compatibility(self, sample_geo_csv_dollars):
        """Test that GeoPerformanceData model works with real CSV exports."""
        # Parse using GeoPerformanceData (expects cost_micros, revenue_micros)
        parser = GoogleAdsCSVParser(file_type="geo_performance", strict_validation=True)
        parser.model_class = GeoPerformanceData

        try:
            results = parser.parse(sample_geo_csv_dollars)

            # Should successfully parse without errors
            assert len(results) == 2

            # Verify first row
            row1 = results[0]
            assert isinstance(row1, GeoPerformanceData)
            assert row1.customer_id == "1234567890"
            assert row1.campaign_id == "111"
            assert row1.geographic_level == "CITY"
            assert row1.location_name == "New York, NY"
            assert row1.cost_micros == 123_450_000  # $123.45 converted to micros
            assert row1.revenue_micros == 987_650_000  # $987.65 converted to micros
            assert row1.cost == 123.45  # Property converts back to dollars
            assert row1.revenue == 987.65

            # Verify second row
            row2 = results[1]
            assert isinstance(row2, GeoPerformanceData)
            assert (
                row2.geographic_level == "ZIP_CODE"
            )  # "Postal Code" mapped to ZIP_CODE
            assert row2.cost_micros == 456_780_000  # $456.78 converted
            assert row2.revenue_micros == 1_234_560_000  # $1,234.56 converted

        finally:
            sample_geo_csv_dollars.unlink()

    def test_google_geo_performance_compatibility(self, sample_geo_csv_dollars):
        """Test that Google GeoPerformance model works with real CSV exports."""
        # Parse using Google GeoPerformance model (expects cost, conversion_value in dollars)
        parser = GoogleAdsCSVParser(file_type="geo_performance", strict_validation=True)
        parser.model_class = GeoPerformance

        try:
            results = parser.parse(sample_geo_csv_dollars)

            # Should successfully parse without errors
            assert len(results) == 2

            # Verify first row
            row1 = results[0]
            assert isinstance(row1, GeoPerformance)
            assert row1.campaign_id == "111"
            assert row1.location_type == "CITY"  # String mapped to enum
            assert row1.location_name == "New York, NY"
            assert row1.cost == 123.45  # Dollar amount preserved
            assert row1.conversion_value == 987.65

            # Verify second row
            row2 = results[1]
            assert isinstance(row2, GeoPerformance)
            assert row2.location_type == "POSTAL_CODE"  # "Postal Code" mapped correctly
            assert row2.cost == 456.78
            assert row2.conversion_value == 1234.56  # Comma removed

        finally:
            sample_geo_csv_dollars.unlink()

    def test_utf16_encoding_detection(self, sample_geo_csv_encoding_issue):
        """Test automatic detection of alternative encoding (cp1252)."""
        # Try to parse cp1252 file with default UTF-8 encoding
        # Should automatically detect and use correct encoding
        parser = GoogleAdsCSVParser(
            file_type="geo_performance",
            encoding="utf-8",  # Wrong encoding, should auto-detect
            strict_validation=True,
        )
        parser.model_class = GeoPerformance

        try:
            results = parser.parse(sample_geo_csv_encoding_issue)

            # Should successfully parse despite encoding mismatch
            assert len(results) == 1

            row = results[0]
            assert isinstance(row, GeoPerformance)
            assert row.campaign_id == "111"
            assert row.location_name == "Texas"
            assert row.cost == 50.0
            assert row.conversion_value == 200.0

        finally:
            sample_geo_csv_encoding_issue.unlink()

    def test_lenient_mode_with_bad_data(self, tmp_path):
        """Test lenient mode handling of partially bad data."""
        csv_file = tmp_path / "bad_geo_data.csv"

        with open(csv_file, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "Customer ID",
                    "Campaign ID",
                    "Campaign",
                    "Location type",
                    "Location",
                    "Location ID",
                    "Cost",
                    "Conversion value",
                ]
            )

            # Good row
            writer.writerow(
                [
                    "1234567890",
                    "111",
                    "Test Campaign",
                    "City",
                    "New York",
                    "1023191",
                    "100.00",
                    "500.00",
                ]
            )

            # Bad row - invalid cost
            writer.writerow(
                [
                    "1234567890",
                    "111",
                    "Test Campaign",
                    "City",
                    "Boston",
                    "1023192",
                    "invalid_cost",  # This will cause conversion error
                    "300.00",
                ]
            )

            # Another good row
            writer.writerow(
                [
                    "1234567890",
                    "111",
                    "Test Campaign",
                    "State",
                    "California",
                    "1023193",
                    "200.00",
                    "800.00",
                ]
            )

        # Parse in lenient mode
        parser = GoogleAdsCSVParser(
            file_type="geo_performance",
            strict_validation=False,  # Lenient mode
        )
        parser.model_class = GeoPerformance

        results = parser.parse(csv_file)

        # Should get 3 rows: 2 good rows + 1 row with invalid cost defaulted to 0.0 in lenient mode
        assert len(results) == 3
        assert results[0].location_name == "New York"
        assert results[0].cost == 100.0
        assert (
            results[1].location_name == "Boston"
        )  # Invalid cost row, but kept in lenient mode
        assert results[1].cost == 0.0  # Default value for invalid cost in lenient mode
        assert results[2].location_name == "California"
        assert results[2].cost == 200.0

    def test_missing_fields_handling(self, tmp_path):
        """Test handling of missing or optional fields."""
        csv_file = tmp_path / "minimal_geo_data.csv"

        with open(csv_file, "w", newline="") as f:
            writer = csv.writer(f)

            # Minimal headers - some fields missing
            writer.writerow(
                [
                    "Campaign ID",
                    "Location ID",
                    "Location",
                    "Location type",
                    "Cost",
                    # Missing: Customer ID, Campaign name, Conversion value, etc.
                ]
            )

            writer.writerow(["111", "1023191", "Chicago, IL", "City", "$75.50"])

        parser = GoogleAdsCSVParser(
            file_type="geo_performance", strict_validation=False
        )
        parser.model_class = GeoPerformance

        results = parser.parse(csv_file)

        assert len(results) == 1
        row = results[0]
        assert row.campaign_id == "111"
        assert row.location_name == "Chicago, IL"
        assert row.cost == 75.50
        assert row.conversion_value == 0.0  # Default value for missing field
