"""Integration tests for CSV parsing with search terms field inference."""

import csv
import os
import tempfile
from pathlib import Path

import pytest

from paidsearchnav.core.models.search_term import SearchTerm
from paidsearchnav.parsers.csv_parser import GoogleAdsCSVParser


class TestCSVSearchTermsInference:
    """Integration tests for CSV parsing with missing field handling."""

    @pytest.fixture
    def search_terms_csv_with_missing_fields(self):
        """Create a CSV file with missing ad_group_name fields (simulating the Cotton Patch issue)."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            writer = csv.writer(f)
            # Header row - API format with ID fields
            writer.writerow(
                [
                    "Search term",
                    "Campaign ID",
                    "Campaign",
                    "Ad group ID",
                    "Ad group",
                    "Impr.",
                    "Clicks",
                    "Cost",
                    "Conversions",
                    "Conversion value",
                ]
            )

            # Regular data rows
            writer.writerow(
                [
                    "cotton patch cafe",
                    "12345",
                    "Restaurant Campaign",
                    "67890",
                    "Main Ad Group",
                    "1000",
                    "50",
                    "100.00",
                    "5",
                    "250.00",
                ]
            )

            # Row with missing ad_group_name (empty field)
            writer.writerow(
                [
                    "cotton patch cafe near me",
                    "12345",
                    "Restaurant Campaign",
                    "67891",
                    "",
                    "800",
                    "40",
                    "80.00",
                    "3",
                    "150.00",
                ]
            )

            # Row with missing campaign_name and ad_group_name
            writer.writerow(
                [
                    "best restaurant in town",
                    "12346",
                    "",
                    "67892",
                    "",
                    "500",
                    "25",
                    "50.00",
                    "2",
                    "100.00",
                ]
            )

            # Summary row that should be filtered out
            writer.writerow(
                [
                    "Total:",
                    "12345",
                    "Restaurant Campaign",
                    "67890",
                    "Main Ad Group",
                    "2300",
                    "115",
                    "230.00",
                    "10",
                    "500.00",
                ]
            )

            # Another regular row
            writer.writerow(
                [
                    "chicken fried steak",
                    "12345",
                    "Restaurant Campaign",
                    "67893",
                    "Food Items",
                    "600",
                    "30",
                    "60.00",
                    "4",
                    "200.00",
                ]
            )

            temp_path = f.name

        yield Path(temp_path)
        os.unlink(temp_path)

    @pytest.fixture
    def search_terms_csv_all_missing(self):
        """Create a CSV file where all rows are missing required fields."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "Search term",
                    "Campaign ID",
                    "Campaign",
                    "Ad group ID",
                    "Ad group",
                    "Impr.",
                    "Clicks",
                    "Cost",
                ]
            )

            # All rows missing campaign and ad group names
            writer.writerow(
                ["cotton patch cafe", "12345", "", "67890", "", "1000", "50", "100.00"]
            )
            writer.writerow(
                ["restaurant near me", "12346", "", "67891", "", "800", "40", "80.00"]
            )
            writer.writerow(
                ["fast food delivery", "12347", "", "67892", "", "600", "30", "60.00"]
            )

            temp_path = f.name

        yield Path(temp_path)
        os.unlink(temp_path)

    def test_parse_search_terms_with_smart_inference_strict_mode(
        self, search_terms_csv_with_missing_fields
    ):
        """Test parsing search terms CSV with missing fields in strict mode."""
        parser = GoogleAdsCSVParser(
            file_type="search_terms", strict_validation=True, preserve_unmapped=False
        )

        # Should not raise errors due to smart inference
        results = parser.parse(search_terms_csv_with_missing_fields)

        # Should have 4 regular data rows (1 summary row filtered out)
        assert len(results) == 4

        # All results should be SearchTerm instances
        assert all(isinstance(result, SearchTerm) for result in results)

        # Check first row (has all fields)
        row1 = next(r for r in results if r.search_term == "cotton patch cafe")
        assert row1.campaign_name == "Restaurant Campaign"
        assert row1.ad_group_name == "Main Ad Group"
        assert row1.metrics.impressions == 1000

        # Check second row (missing ad_group_name)
        row2 = next(r for r in results if r.search_term == "cotton patch cafe near me")
        assert row2.campaign_name == "Restaurant Campaign"
        assert row2.ad_group_name == "Restaurant Campaign - Default Ad Group"
        assert row2.metrics.impressions == 800

        # Check third row (missing both names)
        row3 = next(r for r in results if r.search_term == "best restaurant in town")
        assert "Inferred Campaign" in row3.campaign_name
        assert "Inferred - best restaurant in town" == row3.ad_group_name
        assert row3.metrics.impressions == 500

    def test_parse_search_terms_with_smart_inference_lenient_mode(
        self, search_terms_csv_with_missing_fields
    ):
        """Test parsing search terms CSV with missing fields in lenient mode."""
        parser = GoogleAdsCSVParser(
            file_type="search_terms", strict_validation=False, preserve_unmapped=False
        )

        results = parser.parse(search_terms_csv_with_missing_fields)

        # Should still get all valid rows
        assert len(results) == 4

        # Check that inference worked for all rows
        for result in results:
            assert isinstance(result, SearchTerm)
            assert result.campaign_name  # Should never be empty
            assert result.ad_group_name  # Should never be empty
            assert result.search_term  # Original search term preserved

    def test_parse_all_missing_fields(self, search_terms_csv_all_missing):
        """Test parsing CSV where all rows have missing required fields."""
        parser = GoogleAdsCSVParser(file_type="search_terms", strict_validation=False)

        results = parser.parse(search_terms_csv_all_missing)

        assert len(results) == 3

        # All should have inferred names
        for result in results:
            assert "Inferred Campaign" in result.campaign_name
            assert "Inferred -" in result.ad_group_name
            assert (
                result.search_term in result.ad_group_name
            )  # Search term used for inference

    def test_summary_row_filtering(self, search_terms_csv_with_missing_fields):
        """Test that summary rows are properly filtered out."""
        parser = GoogleAdsCSVParser(file_type="search_terms")

        results = parser.parse(search_terms_csv_with_missing_fields)

        # Should not contain the "Total:" row
        search_terms = [r.search_term for r in results]
        assert "Total:" not in search_terms

        # Should contain all non-summary rows
        assert "cotton patch cafe" in search_terms
        assert "cotton patch cafe near me" in search_terms
        assert "best restaurant in town" in search_terms
        assert "chicken fried steak" in search_terms

    def test_metrics_parsing_with_inference(self, search_terms_csv_with_missing_fields):
        """Test that metrics are properly parsed even with field inference."""
        parser = GoogleAdsCSVParser(file_type="search_terms")

        results = parser.parse(search_terms_csv_with_missing_fields)

        # Check metrics for the row with missing ad_group_name
        row = next(r for r in results if r.search_term == "cotton patch cafe near me")
        assert row.metrics.impressions == 800
        assert row.metrics.clicks == 40
        assert row.metrics.cost == 80.0
        assert row.metrics.conversions == 3.0
        assert row.metrics.conversion_value == 150.0

        # Check calculated metrics
        assert row.metrics.ctr == (40 / 800 * 100)  # CTR calculation
        assert row.metrics.cpc == (80.0 / 40)  # CPC calculation

    def test_local_intent_detection_with_inference(
        self, search_terms_csv_with_missing_fields
    ):
        """Test that local intent detection works with inferred fields."""
        parser = GoogleAdsCSVParser(file_type="search_terms")

        results = parser.parse(search_terms_csv_with_missing_fields)

        # Find the "near me" search term
        near_me_term = next(r for r in results if "near me" in r.search_term)

        # Should detect local intent
        assert near_me_term.has_near_me
        assert near_me_term.is_local_intent
        assert "near me" in near_me_term.location_terms

    def test_field_inference_preserves_data_integrity(
        self, search_terms_csv_with_missing_fields
    ):
        """Test that field inference doesn't corrupt other data."""
        parser = GoogleAdsCSVParser(file_type="search_terms")

        results = parser.parse(search_terms_csv_with_missing_fields)

        for result in results:
            # Search terms should be unchanged
            assert result.search_term
            assert not result.search_term.startswith("Inferred")

            # Metrics should be present and valid
            assert result.metrics.impressions >= 0
            assert result.metrics.clicks >= 0
            assert result.metrics.cost >= 0.0

            # Inferred fields should be clearly marked
            if "Inferred" in result.campaign_name:
                assert (
                    result.search_term in result.campaign_name
                    or "Inferred Campaign" in result.campaign_name
                )
            if "Inferred" in result.ad_group_name:
                assert result.search_term in result.ad_group_name

    @pytest.fixture
    def search_terms_csv_ui_format(self):
        """Create a CSV file simulating UI export format (no ID fields)."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "Search term",
                    "Campaign",
                    "Ad group",
                    "Match type",
                    "Impr.",
                    "Clicks",
                    "Cost",
                    "Conversions",
                ]
            )

            # Row with missing ad group
            writer.writerow(
                [
                    "cotton patch cafe delivery",
                    "Food Delivery",
                    "",
                    "Broad",
                    "400",
                    "20",
                    "40.00",
                    "1",
                ]
            )

            temp_path = f.name

        yield Path(temp_path)
        os.unlink(temp_path)

    def test_ui_format_detection_with_inference(self, search_terms_csv_ui_format):
        """Test that UI format detection works with field inference."""
        parser = GoogleAdsCSVParser(file_type="search_terms")

        results = parser.parse(search_terms_csv_ui_format)

        assert len(results) == 1
        result = results[0]

        # Should detect as UI format and still apply inference
        assert result.search_term == "cotton patch cafe delivery"
        assert result.campaign_name == "Food Delivery"
        assert (
            result.ad_group_name == "Food Delivery - Default Ad Group"
        )  # Inferred from campaign

        # Should not have ID fields (UI format)
        assert result.campaign_id is None
        assert result.ad_group_id is None
