"""Tests for data adapters."""

from datetime import datetime

import pytest

from paidsearchnav_mcp.models.geo_performance import GeoPerformanceData
from paidsearchnav_mcp.models.keyword import Keyword
from paidsearchnav_mcp.models.search_term import SearchTerm
from paidsearchnav_mcp.parsers.data_adapters import (
    GeoPerformanceAdapter,
    KeywordAdapter,
    SearchTermAdapter,
    get_adapter,
)
from paidsearchnav_mcp.platforms.google.models import GeoPerformance


class TestGeoPerformanceAdapter:
    """Test geographic performance data adapter."""

    def test_geo_performance_data_micros_conversion(self):
        """Test conversion to GeoPerformanceData with micros."""
        adapter = GeoPerformanceAdapter(GeoPerformanceData)

        # Sample CSV data with dollar amounts
        csv_data = {
            "customer_id": "123456789",
            "campaign_id": "111",
            "campaign_name": "Test Campaign",
            "geographic_level": "CITY",
            "location_name": "New York, NY",
            "country_code": "US",
            "region_code": "NY",
            "city": "New York",
            "zip_code": "10001",
            "impressions": 1000,
            "clicks": 50,
            "conversions": 5.0,
            "cost": "123.45",  # Dollar amount as string
            "conversion_value": "987.65",  # Revenue as string
            "start_date": datetime(2024, 1, 1),
            "end_date": datetime(2024, 1, 31),
        }

        converted = adapter.convert(csv_data)

        # Check that dollar amounts were converted to micros
        assert converted["cost_micros"] == 123_450_000
        assert converted["revenue_micros"] == 987_650_000
        assert "cost" not in converted  # Should be removed after conversion
        assert "conversion_value" not in converted  # Should be removed after conversion

        # Check geographic level mapping
        assert converted["geographic_level"] == "CITY"

        # Verify we can create the model
        model = GeoPerformanceData(**converted)
        assert model.cost == 123.45  # Property should convert back to dollars
        assert model.revenue == 987.65

    def test_geo_performance_google_model_conversion(self):
        """Test conversion to Google Ads GeoPerformance model."""
        adapter = GeoPerformanceAdapter(GeoPerformance)

        # Sample CSV data
        csv_data = {
            "campaign_id": "111",
            "location_id": "1023191",
            "location_name": "New York, NY",
            "geographic_level": "CITY",
            "country_code": "US",
            "state": "New York",
            "city": "New York",
            "postal_code": "10001",
            "impressions": 1000,
            "clicks": 50,
            "conversions": 5.0,
            "cost": 123.45,  # Already numeric
            "conversion_value": 987.65,
        }

        converted = adapter.convert(csv_data)

        # Should NOT convert to micros for Google model
        assert converted["cost"] == 123.45
        assert converted["conversion_value"] == 987.65
        assert "cost_micros" not in converted
        assert "revenue_micros" not in converted

        # Should add location_type
        assert converted["location_type"] == "CITY"

        # Verify we can create the model
        model = GeoPerformance(**converted)
        assert model.cost == 123.45
        assert model.conversion_value == 987.65

    def test_geographic_level_mappings(self):
        """Test various geographic level mappings."""
        adapter = GeoPerformanceAdapter(GeoPerformanceData)

        test_cases = [
            ("POSTAL CODE", "ZIP_CODE"),
            ("ZIP CODE", "ZIP_CODE"),
            ("ZIP", "ZIP_CODE"),
            ("DMA", "STATE"),
            ("DMA REGION", "STATE"),
            ("COUNTY", "STATE"),
            ("AIRPORT", "CITY"),
            ("UNKNOWN_TYPE", "CITY"),  # Default fallback
        ]

        for input_level, expected_output in test_cases:
            csv_data = {
                "customer_id": "123",
                "campaign_id": "111",
                "campaign_name": "Test",
                "geographic_level": input_level,
                "location_name": "Test Location",
                "impressions": 100,
                "clicks": 10,
                "conversions": 1.0,
                "cost": "10.00",
                "start_date": datetime(2024, 1, 1),
                "end_date": datetime(2024, 1, 31),
            }

            converted = adapter.convert(csv_data)
            assert converted["geographic_level"] == expected_output

    def test_currency_parsing(self):
        """Test currency value parsing."""
        adapter = GeoPerformanceAdapter(GeoPerformanceData)

        # Test various currency formats
        test_cases = [
            ("$1,234.56", 1234.56),
            ("1234.56", 1234.56),
            ("$1,000", 1000.0),
            ("0", 0.0),
            ("", 0.0),
            ("--", 0.0),
            ("N/A", 0.0),
        ]

        for input_value, expected in test_cases:
            result = adapter._parse_currency(input_value)
            assert result == expected

    def test_invalid_currency_parsing(self):
        """Test invalid currency value handling."""
        adapter = GeoPerformanceAdapter(GeoPerformanceData)

        with pytest.raises(ValueError):
            adapter._parse_currency("invalid_value")

    def test_invalid_cost_conversion_error(self):
        """Test that invalid cost values raise descriptive errors instead of defaulting to 0."""
        adapter = GeoPerformanceAdapter(GeoPerformanceData)

        csv_data = {
            "customer_id": "123",
            "campaign_id": "111",
            "campaign_name": "Test",
            "geographic_level": "CITY",
            "location_name": "Test Location",
            "cost": "invalid_cost_value",  # This should cause an error
            "start_date": datetime(2024, 1, 1),
            "end_date": datetime(2024, 1, 31),
        }

        with pytest.raises(ValueError) as exc_info:
            adapter.convert(csv_data)

        # Verify the error message is descriptive
        assert "Invalid cost value" in str(exc_info.value)
        assert "invalid_cost_value" in str(exc_info.value)


class TestKeywordAdapter:
    """Test keyword data adapter."""

    def test_keyword_conversion(self):
        """Test keyword data conversion."""
        adapter = KeywordAdapter(Keyword)

        csv_data = {
            "keyword_id": "123",
            "text": "test keyword",
            "match_type": "EXACT MATCH",
            "status": "ACTIVE",
            "quality_score": "8.0",
            "landing_page_experience": "Above Average",
            "expected_ctr": "average",
            "ad_relevance": "below average",
        }

        converted = adapter.convert(csv_data)

        assert converted["match_type"] == "EXACT"
        assert converted["status"] == "ENABLED"
        assert converted["quality_score"] == 8
        assert converted["landing_page_experience"] == "ABOVE_AVERAGE"
        assert converted["expected_ctr"] == "AVERAGE"
        assert converted["ad_relevance"] == "BELOW_AVERAGE"

    def test_match_type_mappings(self):
        """Test match type mappings."""
        adapter = KeywordAdapter(Keyword)

        test_cases = [
            ("EXACT", "EXACT"),
            ("EXACT MATCH", "EXACT"),
            ("PHRASE", "PHRASE"),
            ("PHRASE MATCH", "PHRASE"),
            ("BROAD", "BROAD"),
            ("BROAD MATCH", "BROAD"),
            ("UNKNOWN", "BROAD"),  # Default
        ]

        for input_type, expected in test_cases:
            csv_data = {"match_type": input_type}
            converted = adapter.convert(csv_data)
            assert converted["match_type"] == expected

    def test_status_mappings(self):
        """Test status mappings."""
        adapter = KeywordAdapter(Keyword)

        test_cases = [
            ("ENABLED", "ENABLED"),
            ("ACTIVE", "ENABLED"),
            ("PAUSED", "PAUSED"),
            ("INACTIVE", "PAUSED"),
            ("REMOVED", "REMOVED"),
            ("UNKNOWN", "ENABLED"),  # Default
        ]

        for input_status, expected in test_cases:
            csv_data = {"status": input_status}
            converted = adapter.convert(csv_data)
            assert converted["status"] == expected


class TestSearchTermAdapter:
    """Test search term data adapter."""

    def test_search_term_conversion(self):
        """Test search term data conversion."""
        adapter = SearchTermAdapter(SearchTerm)

        csv_data = {
            "search_term": "test query",
            "keyword_id": "123",
            "impressions": 100,
            "clicks": 10,
            "cost": 5.50,
            "conversions": 1.0,
            "conversion_value": 25.00,
        }

        converted = adapter.convert(csv_data)

        # Should create metrics object
        assert "metrics" in converted
        metrics = converted["metrics"]
        assert metrics.impressions == 100
        assert metrics.clicks == 10
        assert metrics.cost == 5.50

    def test_metrics_prefixed_fields(self):
        """Test handling of metrics.* prefixed fields."""
        adapter = SearchTermAdapter(SearchTerm)

        csv_data = {
            "search_term": "test query",
            "keyword_id": "123",
            "metrics.impressions": 100,
            "metrics.clicks": 10,
            "metrics.cost": 5.50,
        }

        converted = adapter.convert(csv_data)

        # Should extract metrics from prefixed fields
        assert "metrics" in converted
        metrics = converted["metrics"]
        assert metrics.impressions == 100
        assert metrics.clicks == 10
        assert metrics.cost == 5.50

        # Prefixed fields should be removed
        assert "metrics.impressions" not in converted
        assert "metrics.clicks" not in converted
        assert "metrics.cost" not in converted


class TestGetAdapter:
    """Test adapter factory function."""

    def test_get_adapter_geo_performance(self):
        """Test getting geo performance adapter."""
        adapter = get_adapter("geo_performance", GeoPerformanceData)
        assert isinstance(adapter, GeoPerformanceAdapter)
        assert adapter.target_model == GeoPerformanceData

    def test_get_adapter_keywords(self):
        """Test getting keyword adapter."""
        adapter = get_adapter("keywords", Keyword)
        assert isinstance(adapter, KeywordAdapter)
        assert adapter.target_model == Keyword

    def test_get_adapter_search_terms(self):
        """Test getting search term adapter."""
        adapter = get_adapter("search_terms", SearchTerm)
        assert isinstance(adapter, SearchTermAdapter)
        assert adapter.target_model == SearchTerm

    def test_get_adapter_unknown_type(self):
        """Test getting adapter for unknown file type."""
        adapter = get_adapter("unknown_type", Keyword)
        assert adapter is None
