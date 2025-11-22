"""Unit tests for GoogleAdsCSVParser implementation."""

import csv
import os
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from paidsearchnav_mcp.models.keyword import Keyword, KeywordMatchType, KeywordStatus
from paidsearchnav_mcp.models.search_term import SearchTerm, SearchTermMetrics
from paidsearchnav_mcp.parsers.csv_parser import GoogleAdsCSVParser


class TestGoogleAdsCSVParser:
    """Test suite for GoogleAdsCSVParser class."""

    @pytest.fixture
    def keywords_csv(self):
        """Create a temporary keywords CSV file for testing."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            writer = csv.writer(f)
            # Write header with all required fields
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
                    "Max. CPC",
                    "Quality Score",
                    "Landing page experience",
                    "Expected CTR",
                    "Ad relevance",
                    "Impr.",
                    "Clicks",
                    "Cost",
                    "Conversions",
                    "Conversion value",
                ]
            )
            # Write data rows
            writer.writerow(
                [
                    "123456",
                    "111",
                    "Summer Sale",
                    "222",
                    "Shoes",
                    "buy shoes online",
                    "EXACT",
                    "ENABLED",
                    "2.50",
                    "8",
                    "ABOVE_AVERAGE",
                    "AVERAGE",
                    "ABOVE_AVERAGE",
                    "1000",
                    "50",
                    "125.00",
                    "5",
                    "500.00",
                ]
            )
            writer.writerow(
                [
                    "123457",
                    "111",
                    "Summer Sale",
                    "222",
                    "Shoes",
                    "cheap sneakers",
                    "BROAD",
                    "PAUSED",
                    "1.50",
                    "6",
                    "AVERAGE",
                    "BELOW_AVERAGE",
                    "AVERAGE",
                    "2000",
                    "80",
                    "120.00",
                    "3",
                    "300.00",
                ]
            )
            # Row with missing/null values
            writer.writerow(
                [
                    "123458",
                    "111",
                    "Summer Sale",
                    "223",
                    "Boots",
                    "winter boots",
                    "PHRASE",
                    "ENABLED",
                    "--",
                    "",
                    "n/a",
                    "N/A",
                    "null",
                    "500",
                    "10",
                    "15.00",
                    "0",
                    "0.00",
                ]
            )
            temp_path = f.name

        yield Path(temp_path)
        os.unlink(temp_path)

    @pytest.fixture
    def search_terms_csv(self):
        """Create a temporary search terms CSV file for testing."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            writer = csv.writer(f)
            # Write header
            writer.writerow(
                [
                    "Campaign ID",
                    "Campaign",
                    "Ad group ID",
                    "Ad group",
                    "Search term",
                    "Keyword ID",
                    "Keyword",
                    "Match type",
                    "Impr.",
                    "Clicks",
                    "Cost",
                    "Conversions",
                    "Conversion value",
                ]
            )
            # Write data rows
            writer.writerow(
                [
                    "111",
                    "Summer Sale",
                    "222",
                    "Shoes",
                    "buy shoes near me",
                    "123456",
                    "buy shoes",
                    "BROAD",
                    "100",
                    "10",
                    "25.00",
                    "1",
                    "100.00",
                ]
            )
            writer.writerow(
                [
                    "111",
                    "Summer Sale",
                    "222",
                    "Shoes",
                    "shoe store nearby",
                    "123456",
                    "buy shoes",
                    "BROAD",
                    "50",
                    "5",
                    "12.50",
                    "0",
                    "0.00",
                ]
            )
            writer.writerow(
                [
                    "111",
                    "Summer Sale",
                    "222",
                    "Shoes",
                    "best running shoes",
                    "123457",
                    "running shoes",
                    "PHRASE",
                    "200",
                    "20",
                    "40.00",
                    "2",
                    "200.00",
                ]
            )
            temp_path = f.name

        yield Path(temp_path)
        os.unlink(temp_path)

    @pytest.fixture
    def geo_performance_csv(self):
        """Create a temporary geo performance CSV file for testing."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            writer = csv.writer(f)
            # Write header
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
                    "Impr.",
                    "Clicks",
                    "Cost",
                    "Conversions",
                    "Revenue",
                ]
            )
            # Write data rows
            writer.writerow(
                [
                    "123",
                    "111",
                    "Summer Sale",
                    "City",
                    "New York, NY",
                    "1023191",
                    "US",
                    "New York",
                    "New York",
                    "5000",
                    "250",
                    "625.00",
                    "25",
                    "2500.00",
                ]
            )
            writer.writerow(
                [
                    "123",
                    "111",
                    "Summer Sale",
                    "Postal code",
                    "10001",
                    "9001234",
                    "US",
                    "New York",
                    "New York",
                    "1000",
                    "50",
                    "125.00",
                    "5",
                    "500.00",
                ]
            )
            temp_path = f.name

        yield Path(temp_path)
        os.unlink(temp_path)

    def test_parse_keywords_to_models(self, keywords_csv):
        """Test parsing keywords CSV to Keyword models."""
        parser = GoogleAdsCSVParser(file_type="keywords")
        results = parser.parse(keywords_csv)

        assert len(results) == 3
        assert all(isinstance(r, Keyword) for r in results)

        # Check first keyword
        kw1 = results[0]
        assert kw1.keyword_id == "123456"
        assert kw1.campaign_id == "111"
        assert kw1.campaign_name == "Summer Sale"
        assert kw1.ad_group_id == "222"
        assert kw1.ad_group_name == "Shoes"
        assert kw1.text == "buy shoes online"
        assert kw1.match_type == KeywordMatchType.EXACT
        assert kw1.status == KeywordStatus.ENABLED
        assert kw1.cpc_bid == 2.50
        assert kw1.quality_score == 8
        assert kw1.impressions == 1000
        assert kw1.clicks == 50
        assert kw1.cost == 125.00
        assert kw1.conversions == 5
        assert kw1.conversion_value == 500.00

        # Check second keyword
        kw2 = results[1]
        assert kw2.text == "cheap sneakers"
        assert kw2.match_type == KeywordMatchType.BROAD
        assert kw2.status == KeywordStatus.PAUSED

        # Check third keyword with null values
        kw3 = results[2]
        assert kw3.text == "winter boots"
        assert kw3.quality_score is None  # empty string should become None
        assert kw3.cpc_bid is None  # "--" should become None

    def test_parse_search_terms_to_models(self, search_terms_csv):
        """Test parsing search terms CSV to SearchTerm models."""
        parser = GoogleAdsCSVParser(file_type="search_terms")
        results = parser.parse(search_terms_csv)

        assert len(results) == 3
        assert all(isinstance(r, SearchTerm) for r in results)

        # Check first search term with local intent
        st1 = results[0]
        assert st1.search_term == "buy shoes near me"
        assert st1.campaign_id == "111"
        assert st1.campaign_name == "Summer Sale"
        assert st1.keyword_text == "buy shoes"
        assert isinstance(st1.metrics, SearchTermMetrics)
        assert st1.metrics.impressions == 100
        assert st1.metrics.clicks == 10
        assert st1.metrics.cost == 25.00
        assert st1.metrics.conversions == 1
        assert st1.has_near_me is True  # Local intent detected
        assert st1.is_local_intent is True

        # Check second search term with local intent
        st2 = results[1]
        assert st2.search_term == "shoe store nearby"
        assert st2.has_location is True  # "nearby" detected
        assert st2.is_local_intent is True

        # Check third search term without local intent
        st3 = results[2]
        assert st3.search_term == "best running shoes"
        assert st3.has_near_me is False
        assert st3.is_local_intent is False

    def test_parse_geo_performance_to_models(self, geo_performance_csv):
        """Test parsing geo performance CSV to GeoPerformance models."""
        from paidsearchnav.platforms.google.models import GeoPerformance, GeoTargetType

        parser = GoogleAdsCSVParser(file_type="geo_performance")
        results = parser.parse(geo_performance_csv)

        assert len(results) == 2
        assert all(isinstance(r, GeoPerformance) for r in results)

        # Check first location (city)
        geo1 = results[0]
        assert geo1.campaign_id == "111"
        assert geo1.location_id == "1023191"
        assert geo1.location_name == "New York, NY"
        assert geo1.location_type == GeoTargetType.CITY
        assert geo1.impressions == 5000
        assert geo1.clicks == 250
        assert geo1.cost == 625.00

        # Check second location (postal code)
        geo2 = results[1]
        assert geo2.location_name == "10001"
        assert geo2.location_type == GeoTargetType.POSTAL_CODE

    def test_data_cleaning(self, keywords_csv):
        """Test data cleaning functionality."""
        parser = GoogleAdsCSVParser(file_type="keywords")
        results = parser.parse(keywords_csv)

        # Check that null/empty values are cleaned
        kw3 = results[2]
        assert kw3.cpc_bid is None  # "--" cleaned to None
        assert kw3.quality_score is None  # empty string cleaned to None
        assert kw3.landing_page_experience is None  # "n/a" cleaned to None
        assert kw3.expected_ctr is None  # "N/A" cleaned to None
        assert kw3.ad_relevance is None  # "null" cleaned to None

    def test_type_conversion(self, keywords_csv):
        """Test automatic type conversion."""
        parser = GoogleAdsCSVParser(file_type="keywords")
        results = parser.parse(keywords_csv)

        kw1 = results[0]
        # Check numeric conversions
        assert isinstance(kw1.impressions, int)
        assert isinstance(kw1.clicks, int)
        assert isinstance(kw1.cost, float)
        assert isinstance(kw1.conversions, float)
        assert isinstance(kw1.quality_score, int)

    def test_strict_validation_mode(self):
        """Test strict validation mode with invalid data."""
        # Create CSV with missing required fields
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            writer = csv.writer(f)
            writer.writerow(["Keyword", "Campaign"])  # Missing required fields
            writer.writerow(["test keyword", "test campaign"])
            temp_path = f.name

        try:
            parser = GoogleAdsCSVParser(file_type="keywords", strict_validation=True)
            with pytest.raises(ValueError, match="Missing required fields"):
                parser.parse(Path(temp_path))
        finally:
            os.unlink(temp_path)

    def test_non_strict_validation_mode(self):
        """Test non-strict validation mode with invalid data."""
        # Create CSV with some invalid data
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
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
            # Valid row
            writer.writerow(
                [
                    "123",
                    "111",
                    "Campaign1",
                    "222",
                    "AdGroup1",
                    "keyword1",
                    "EXACT",
                    "ENABLED",
                ]
            )
            # Invalid row (missing required field)
            writer.writerow(
                [
                    "",
                    "111",
                    "Campaign1",
                    "222",
                    "AdGroup1",
                    "keyword2",
                    "EXACT",
                    "ENABLED",
                ]
            )
            temp_path = f.name

        try:
            parser = GoogleAdsCSVParser(file_type="keywords", strict_validation=False)
            results = parser.parse(Path(temp_path))
            # Should only return valid rows
            assert len(results) == 1
            assert results[0].keyword_id == "123"
        finally:
            os.unlink(temp_path)

    def test_parse_to_dataframe(self, keywords_csv):
        """Test parsing to pandas DataFrame."""
        parser = GoogleAdsCSVParser(file_type="keywords")
        df = parser.parse_to_dataframe(keywords_csv)

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 3
        # Check that columns are mapped
        assert "text" in df.columns  # "Keyword" mapped to "text"
        assert "campaign_name" in df.columns  # "Campaign" mapped to "campaign_name"
        assert "Keyword" not in df.columns  # Original column name not present

    def test_utf8_encoding_support(self):
        """Test UTF-8 encoding support."""
        # Create CSV with UTF-8 characters
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8"
        ) as f:
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
                    "111",
                    "Campaña España",
                    "222",
                    "Grupo",
                    "café con leche",
                    "EXACT",
                    "ENABLED",
                ]
            )
            temp_path = f.name

        try:
            parser = GoogleAdsCSVParser(file_type="keywords", encoding="utf-8")
            results = parser.parse(Path(temp_path))
            assert len(results) == 1
            assert results[0].text == "café con leche"
            assert results[0].campaign_name == "Campaña España"
        finally:
            os.unlink(temp_path)

    def test_match_type_normalization(self, keywords_csv):
        """Test match type normalization."""
        # Create CSV with various match type formats
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
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
                    "1",
                    "111",
                    "Campaign",
                    "222",
                    "AdGroup",
                    "keyword1",
                    "exact",
                    "ENABLED",  # lowercase
                ]
            )
            writer.writerow(
                [
                    "2",
                    "111",
                    "Campaign",
                    "222",
                    "AdGroup",
                    "keyword2",
                    "Phrase",
                    "ENABLED",  # mixed case
                ]
            )
            writer.writerow(
                [
                    "3",
                    "111",
                    "Campaign",
                    "222",
                    "AdGroup",
                    "keyword3",
                    "invalid",
                    "ENABLED",  # invalid match type
                ]
            )
            temp_path = f.name

        try:
            parser = GoogleAdsCSVParser(file_type="keywords")
            results = parser.parse(Path(temp_path))
            assert results[0].match_type == KeywordMatchType.EXACT
            assert results[1].match_type == KeywordMatchType.PHRASE
            assert (
                results[2].match_type == KeywordMatchType.BROAD
            )  # Default for invalid
        finally:
            os.unlink(temp_path)

    def test_quality_score_level_normalization(self, keywords_csv):
        """Test quality score level normalization."""
        # Create CSV with various quality score level formats
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
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
                    "Landing page experience",
                ]
            )
            writer.writerow(
                [
                    "1",
                    "111",
                    "Campaign",
                    "222",
                    "AdGroup",
                    "keyword1",
                    "EXACT",
                    "ENABLED",
                    "above_average",  # lowercase
                ]
            )
            writer.writerow(
                [
                    "2",
                    "111",
                    "Campaign",
                    "222",
                    "AdGroup",
                    "keyword2",
                    "EXACT",
                    "ENABLED",
                    "Below Average",  # mixed case
                ]
            )
            writer.writerow(
                [
                    "3",
                    "111",
                    "Campaign",
                    "222",
                    "AdGroup",
                    "keyword3",
                    "EXACT",
                    "ENABLED",
                    "invalid",  # invalid
                ]
            )
            temp_path = f.name

        try:
            parser = GoogleAdsCSVParser(file_type="keywords")
            results = parser.parse(Path(temp_path))
            assert results[0].landing_page_experience == "ABOVE_AVERAGE"
            assert results[1].landing_page_experience == "BELOW_AVERAGE"
            assert (
                results[2].landing_page_experience == "UNKNOWN"
            )  # Default for invalid
        finally:
            os.unlink(temp_path)

    def test_csv_injection_protection(self):
        """Test that CSV injection protection still works."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
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
                    "111",
                    "=SUM(A1:A10)",
                    "222",
                    "AdGroup",
                    "=1+1",
                    "EXACT",
                    "ENABLED",
                ]
            )
            temp_path = f.name

        try:
            parser = GoogleAdsCSVParser(file_type="keywords")
            results = parser.parse(Path(temp_path))
            # Formula prefixes should be sanitized
            assert results[0].campaign_name == "'=SUM(A1:A10)"
            assert results[0].text == "'=1+1"
        finally:
            os.unlink(temp_path)

    def test_file_not_found_error(self):
        """Test handling of non-existent files."""
        parser = GoogleAdsCSVParser(file_type="keywords")
        with pytest.raises(FileNotFoundError, match="File not found"):
            parser.parse(Path("/nonexistent/file.csv"))

    def test_invalid_file_extension(self):
        """Test handling of non-CSV files."""
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"Not a CSV file")
            temp_path = f.name

        try:
            parser = GoogleAdsCSVParser(file_type="keywords")
            with pytest.raises(ValueError, match="Expected .csv file"):
                parser.parse(Path(temp_path))
        finally:
            os.unlink(temp_path)

    def test_file_size_limit(self):
        """Test file size limit enforcement."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            writer = csv.writer(f)
            writer.writerow(["Keyword", "Campaign"])
            for i in range(100):
                writer.writerow([f"keyword{i}", f"campaign{i}"])
            temp_path = f.name

        try:
            # Set very small size limit
            parser = GoogleAdsCSVParser(file_type="keywords", max_file_size=100)
            with pytest.raises(ValueError, match="exceeds maximum allowed size"):
                parser.parse(Path(temp_path))
        finally:
            os.unlink(temp_path)

    def test_preserve_unmapped_fields(self):
        """Test preserve unmapped fields functionality."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
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
                    "Custom Field",
                ]
            )
            writer.writerow(
                [
                    "123",
                    "111",
                    "Campaign",
                    "222",
                    "AdGroup",
                    "keyword",
                    "EXACT",
                    "ENABLED",
                    "custom value",
                ]
            )
            temp_path = f.name

        try:
            # Test with preserve_unmapped=True (should include custom field)
            parser = GoogleAdsCSVParser(file_type="keywords", preserve_unmapped=True)
            results = parser.parse(Path(temp_path))
            # Since we return models, unmapped fields are not included in the model
            assert hasattr(results[0], "text")  # Mapped field
            assert not hasattr(
                results[0], "Custom Field"
            )  # Unmapped field not in model

            # For dict output, use base CSVParser
            base_parser = GoogleAdsCSVParser(
                file_type="default", preserve_unmapped=True
            )
            dict_results = base_parser.parse(Path(temp_path))
            assert "Custom Field" in dict_results[0]
        finally:
            os.unlink(temp_path)
