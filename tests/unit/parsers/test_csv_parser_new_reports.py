"""Integration tests for CSV parser with new report types."""

import csv
import os
import tempfile
from pathlib import Path

import pytest

from paidsearchnav.parsers.csv_parser import CSVParser


class TestCSVParserNewReports:
    """Test suite for CSVParser with new report types."""

    @pytest.fixture
    def device_report_csv(self):
        """Create a temporary device report CSV file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            writer = csv.writer(f)
            # Column headers only (no Google Ads header rows for simple test)
            writer.writerow(
                [
                    "Device",
                    "Level",
                    "Campaign",
                    "Ad group",
                    "Bid adj.",
                    "Clicks",
                    "Impr.",
                    "CTR",
                    "Avg. CPC",
                    "Cost",
                    "Conv. rate",
                    "Conversions",
                    "Cost / conv.",
                ]
            )
            # Data rows
            writer.writerow(
                [
                    "Mobile phones",
                    "Campaign",
                    "Test Campaign",
                    "--",
                    "--",
                    "100",
                    "1,000",
                    "10.00%",
                    "0.50",
                    "50.00",
                    "5.00%",
                    "5.0",
                    "10.00",
                ]
            )
            writer.writerow(
                [
                    "Computers",
                    "Campaign",
                    "Test Campaign",
                    "--",
                    "--",
                    "50",
                    "500",
                    "10.00%",
                    "0.40",
                    "20.00",
                    "4.00%",
                    "2.0",
                    "10.00",
                ]
            )
            temp_path = f.name

        yield Path(temp_path)
        os.unlink(temp_path)

    @pytest.fixture
    def ad_schedule_report_csv(self):
        """Create a temporary ad schedule report CSV file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            writer = csv.writer(f)
            # Column headers only
            writer.writerow(
                [
                    "Day & time",
                    "Bid adj.",
                    "Clicks",
                    "Impr.",
                    "CTR",
                    "Avg. CPC",
                    "Cost",
                    "Conv. rate",
                    "Conversions",
                    "Cost / conv.",
                ]
            )
            # Data rows
            writer.writerow(
                [
                    "Monday, all day",
                    "'--",
                    "100",
                    "1,000",
                    "10.00%",
                    "0.50",
                    "50.00",
                    "5.00%",
                    "5.0",
                    "10.00",
                ]
            )
            writer.writerow(
                [
                    "Tuesday, 9:00 AM - 5:00 PM",
                    "10%",
                    "80",
                    "800",
                    "10.00%",
                    "0.55",
                    "44.00",
                    "6.25%",
                    "5.0",
                    "8.80",
                ]
            )
            temp_path = f.name

        yield Path(temp_path)
        os.unlink(temp_path)

    @pytest.fixture
    def per_store_report_csv(self):
        """Create a temporary per store report CSV file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            writer = csv.writer(f)
            # Column headers only
            writer.writerow(
                [
                    "Store locations",
                    "address_line_1",
                    "address_line_2",
                    "city",
                    "country_code",
                    "phone_number",
                    "postal_code",
                    "province",
                    "Local reach (impressions)",
                    "Call clicks",
                    "Driving directions",
                    "Website visits",
                ]
            )
            # Data rows
            writer.writerow(
                [
                    "Test Store Dallas",
                    "123 Main St",
                    "",
                    "Dallas",
                    "US",
                    "+1 214-555-0100",
                    "75201",
                    "TX",
                    "1,000",
                    "10",
                    "5",
                    "20",
                ]
            )
            writer.writerow(
                [
                    "Test Store Plano",
                    "456 Oak Ave",
                    "Suite 200",
                    "Plano",
                    "US",
                    "+1 972-555-0200",
                    "75093",
                    "TX",
                    "2,000",
                    "20",
                    "10",
                    "30",
                ]
            )
            temp_path = f.name

        yield Path(temp_path)
        os.unlink(temp_path)

    def test_parse_device_report(self, device_report_csv):
        """Test parsing device report CSV."""
        parser = CSVParser(file_type="device")
        data = parser.parse(device_report_csv)

        # Check data was parsed correctly
        assert len(data) == 2
        assert data[0]["device"] == "Mobile phones"
        assert data[0]["campaign_name"] == "Test Campaign"
        assert data[0]["clicks"] == "100"
        assert data[0]["impressions"] == "1,000"

        # Check second row
        assert data[1]["device"] == "Computers"
        assert data[1]["cost"] == "20.00"

    def test_parse_ad_schedule_report(self, ad_schedule_report_csv):
        """Test parsing ad schedule report CSV."""
        parser = CSVParser(file_type="ad_schedule")
        data = parser.parse(ad_schedule_report_csv)

        # Check data was parsed correctly
        assert len(data) == 2
        assert data[0]["day_time"] == "Monday, all day"
        assert data[0]["clicks"] == "100"
        assert data[0]["bid_adjustment"] == "'--"

        # Check second row
        assert data[1]["day_time"] == "Tuesday, 9:00 AM - 5:00 PM"
        assert data[1]["bid_adjustment"] == "10%"
        assert data[1]["conversions"] == "5.0"

    def test_parse_per_store_report(self, per_store_report_csv):
        """Test parsing per store report CSV."""
        parser = CSVParser(file_type="per_store")
        data = parser.parse(per_store_report_csv)

        # Check data was parsed correctly
        assert len(data) == 2
        assert data[0]["store_name"] == "Test Store Dallas"
        assert data[0]["city"] == "Dallas"
        assert data[0]["local_impressions"] == "1,000"
        assert data[0]["call_clicks"] == "10"

        # Check second row
        assert data[1]["store_name"] == "Test Store Plano"
        assert data[1]["state"] == "TX"
        assert data[1]["website_visits"] == "30"

    def test_numeric_conversion(self, device_report_csv):
        """Test that numeric fields can be converted properly."""
        parser = CSVParser(file_type="device")
        data = parser.parse(device_report_csv)

        # Convert string numbers to actual numbers
        row = data[0]

        # Remove commas and convert
        clicks = int(row["clicks"])
        impressions = int(row["impressions"].replace(",", ""))
        cost = float(row["cost"])

        assert clicks == 100
        assert impressions == 1000
        assert cost == 50.0

    def test_missing_optional_fields(self, per_store_report_csv):
        """Test handling of missing optional fields."""
        parser = CSVParser(file_type="per_store")
        data = parser.parse(per_store_report_csv)

        # address_line_2 should be empty for first row
        assert data[0]["address_line_2"] == ""
        # But present for second row
        assert data[1]["address_line_2"] == "Suite 200"

    def test_validate_required_fields_device(self, device_report_csv):
        """Test that required fields are present in device report."""
        parser = CSVParser(file_type="device")
        data = parser.parse(device_report_csv)

        # Check required fields are present in first row
        required_fields = ["device", "campaign_name", "clicks", "cost"]
        for field in required_fields:
            assert field in data[0]

    def test_validate_required_fields_per_store(self, per_store_report_csv):
        """Test that required fields are present in per store report."""
        parser = CSVParser(file_type="per_store")
        data = parser.parse(per_store_report_csv)

        # Check required fields are present in first row
        required_fields = ["store_name", "local_impressions"]
        for field in required_fields:
            assert field in data[0]
