"""Unit tests for Per Store parser."""

from pathlib import Path
from unittest.mock import patch

import pytest

from paidsearchnav.core.models.store_performance import (
    StoreLocationData,
    StoreMetrics,
    StorePerformanceData,
    StorePerformanceLevel,
)
from paidsearchnav.parsers.per_store import PerStoreConfig, PerStoreParser


class TestPerStoreConfig:
    """Test PerStoreConfig class."""

    def test_default_config(self):
        """Test default configuration values."""
        config = PerStoreConfig()
        assert config.min_impressions_threshold == 100
        assert config.high_engagement_threshold == 3.0
        assert config.moderate_engagement_threshold == 1.5
        assert config.low_engagement_threshold == 0.5

    def test_custom_config(self):
        """Test custom configuration values."""
        config = PerStoreConfig(
            min_impressions_threshold=200,
            high_engagement_threshold=4.0,
            moderate_engagement_threshold=2.0,
            low_engagement_threshold=1.0,
        )
        assert config.min_impressions_threshold == 200
        assert config.high_engagement_threshold == 4.0
        assert config.moderate_engagement_threshold == 2.0
        assert config.low_engagement_threshold == 1.0


class TestPerStoreParser:
    """Test PerStoreParser class."""

    @pytest.fixture
    def parser(self):
        """Create PerStoreParser instance."""
        return PerStoreParser()

    @pytest.fixture
    def sample_store_data(self):
        """Sample store performance data."""
        return [
            {
                "store_name": "Test Store 1",
                "address_line_1": "123 Main St",
                "city": "Dallas",
                "state": "TX",
                "postal_code": "75201",
                "country_code": "US",
                "phone_number": "+1-214-555-0100",
                "local_impressions": 1000,
                "store_visits": 50,
                "call_clicks": 5,
                "driving_directions": 15,
                "website_visits": 10,
            },
            {
                "store_name": "Test Store 2",
                "address_line_1": "456 Oak Ave",
                "city": "Houston",
                "state": "TX",
                "postal_code": "77001",
                "country_code": "US",
                "phone_number": "+1-713-555-0200",
                "local_impressions": 2000,
                "store_visits": 200,
                "call_clicks": 20,
                "driving_directions": 30,
                "website_visits": 25,
            },
        ]

    def test_parser_initialization(self):
        """Test parser initialization."""
        parser = PerStoreParser()
        assert parser.file_type == "per_store"
        assert parser.config is not None
        assert isinstance(parser.config, PerStoreConfig)

    def test_parser_with_custom_config(self):
        """Test parser initialization with custom config."""
        config = PerStoreConfig(min_impressions_threshold=500)
        parser = PerStoreParser(config=config)
        assert parser.config.min_impressions_threshold == 500

    def test_parse_number(self, parser):
        """Test _parse_number method."""
        # Test integer
        assert parser._parse_number(123) == 123

        # Test string with comma
        assert parser._parse_number("1,234") == 1234

        # Test float
        assert parser._parse_number(123.45) == 123

        # Test invalid values
        assert parser._parse_number("invalid") == 0
        assert parser._parse_number(None) == 0
        assert parser._parse_number("") == 0

    def test_parse_store_record_success(self, parser):
        """Test successful store record parsing."""
        row = {
            "store_name": "Test Store",
            "address_line_1": "123 Main St",
            "city": "Dallas",
            "state": "TX",
            "postal_code": "75201",
            "country_code": "US",
            "phone_number": "+1-214-555-0100",
            "local_impressions": "1,000",
            "store_visits": "50",
            "call_clicks": "5",
            "driving_directions": "15",
            "website_visits": "10",
        }

        result = parser._parse_store_record(row)

        assert result is not None
        assert isinstance(result, StorePerformanceData)
        assert result.location.store_name == "Test Store"
        assert result.location.city == "Dallas"
        assert result.location.state == "TX"
        assert result.metrics.local_impressions == 1000
        assert result.metrics.store_visits == 50
        assert result.metrics.call_clicks == 5
        assert result.metrics.driving_directions == 15
        assert result.metrics.website_visits == 10

    def test_parse_store_record_missing_store_name(self, parser):
        """Test store record parsing with missing store name."""
        row = {
            "store_name": "",
            "local_impressions": "1000",
        }

        result = parser._parse_store_record(row)
        assert result is None

    def test_parse_store_record_minimal_data(self, parser):
        """Test store record parsing with minimal data."""
        row = {
            "store_name": "Minimal Store",
            "local_impressions": "500",
        }

        result = parser._parse_store_record(row)

        assert result is not None
        assert result.location.store_name == "Minimal Store"
        assert result.metrics.local_impressions == 500
        assert result.metrics.store_visits == 0
        assert result.metrics.call_clicks == 0

    def test_categorize_performance(self, parser):
        """Test performance categorization."""
        # High performer
        store_data = StorePerformanceData(
            location=StoreLocationData(
                store_name="High Performer",
                address_line_1="123 Main St",
                city="Dallas",
                state="TX",
                postal_code="75201",
                country_code="US",
            ),
            metrics=StoreMetrics(
                local_impressions=1000,
                store_visits=50,  # 5% engagement rate
                call_clicks=0,
                driving_directions=0,
                website_visits=0,
            ),
            performance_level=StorePerformanceLevel.MODERATE_PERFORMER,
        )

        level = parser._categorize_performance(store_data)
        assert level == StorePerformanceLevel.HIGH_PERFORMER

        # Low performer
        store_data.metrics.store_visits = 3  # 0.3% engagement rate
        level = parser._categorize_performance(store_data)
        assert level == StorePerformanceLevel.UNDERPERFORMER

    def test_analyze_store_performance_empty_data(self, parser):
        """Test analysis with empty data."""
        result = parser.analyze_store_performance([])
        assert "error" in result
        assert result["error"] == "No per store data provided"

    def test_analyze_store_performance_success(self, parser, sample_store_data):
        """Test successful store performance analysis."""
        result = parser.analyze_store_performance(sample_store_data)

        assert "error" not in result
        assert "total_stores" in result
        assert "active_stores" in result
        assert "state_distribution" in result
        assert "top_performing_stores" in result
        assert "market_performance" in result
        assert "local_action_metrics" in result
        assert "performance_breakdown" in result
        assert "strategic_insights" in result
        assert "recommendations" in result
        assert "kpis" in result

        assert result["total_stores"] == 2
        assert result["active_stores"] == 2
        assert "TX" in result["state_distribution"]

    def test_analyze_geographic_distribution(self, parser, sample_store_data):
        """Test geographic distribution analysis."""
        stores = []
        for data in sample_store_data:
            store = parser._parse_store_record(data)
            if store:
                stores.append(store)

        result = parser._analyze_geographic_distribution(stores)

        assert "state_distribution" in result
        assert "city_performance" in result
        assert "market_performance" in result

        assert result["state_distribution"]["TX"] == 2
        assert "Dallas" in result["city_performance"]
        assert "Houston" in result["city_performance"]
        assert "TX" in result["market_performance"]

    def test_calculate_local_action_metrics(self, parser, sample_store_data):
        """Test local action metrics calculation."""
        stores = []
        total_impressions = 0
        for data in sample_store_data:
            store = parser._parse_store_record(data)
            if store:
                stores.append(store)
                total_impressions += store.metrics.local_impressions

        result = parser._calculate_local_action_metrics(stores, total_impressions)

        assert "avg_store_visit_rate" in result
        assert "avg_call_click_rate" in result
        assert "avg_directions_rate" in result
        assert "avg_website_visit_rate" in result

        assert isinstance(result["avg_store_visit_rate"], float)
        assert result["avg_store_visit_rate"] > 0

    def test_generate_strategic_insights(self, parser, sample_store_data):
        """Test strategic insights generation."""
        stores = []
        for data in sample_store_data:
            store = parser._parse_store_record(data)
            if store:
                store.performance_level = parser._categorize_performance(store)
                stores.append(store)

        performance_breakdown = {
            StorePerformanceLevel.HIGH_PERFORMER: [
                s
                for s in stores
                if s.performance_level == StorePerformanceLevel.HIGH_PERFORMER
            ],
            StorePerformanceLevel.MODERATE_PERFORMER: [
                s
                for s in stores
                if s.performance_level == StorePerformanceLevel.MODERATE_PERFORMER
            ],
            StorePerformanceLevel.LOW_PERFORMER: [
                s
                for s in stores
                if s.performance_level == StorePerformanceLevel.LOW_PERFORMER
            ],
            StorePerformanceLevel.UNDERPERFORMER: [
                s
                for s in stores
                if s.performance_level == StorePerformanceLevel.UNDERPERFORMER
            ],
        }

        result = parser._generate_strategic_insights(stores, performance_breakdown)

        assert isinstance(result, list)
        assert len(result) > 0

    def test_generate_recommendations(self, parser, sample_store_data):
        """Test recommendations generation."""
        stores = []
        for data in sample_store_data:
            store = parser._parse_store_record(data)
            if store:
                stores.append(store)

        geographic_analysis = parser._analyze_geographic_distribution(stores)
        result = parser._generate_recommendations(stores, geographic_analysis)

        assert isinstance(result, list)
        assert len(result) <= 5

    def test_calculate_kpis(self, parser, sample_store_data):
        """Test KPI calculation."""
        stores = []
        total_impressions = 0
        for data in sample_store_data:
            store = parser._parse_store_record(data)
            if store:
                store.performance_level = parser._categorize_performance(store)
                stores.append(store)
                total_impressions += store.metrics.local_impressions

        result = parser._calculate_kpis(stores, total_impressions)

        assert "total_active_stores" in result
        assert "avg_store_visit_rate" in result
        assert "overall_engagement_rate" in result
        assert "stores_needing_optimization" in result

        assert result["total_active_stores"] == 2
        assert isinstance(result["avg_store_visit_rate"], float)
        assert isinstance(result["overall_engagement_rate"], float)

    @patch("paidsearchnav.parsers.per_store.logger")
    def test_parse_and_analyze_success(self, mock_logger, parser):
        """Test successful parse_and_analyze."""
        # Mock the parse method
        sample_data = [{"store_name": "Test", "local_impressions": 1000}]
        with patch.object(parser, "parse", return_value=sample_data):
            result = parser.parse_and_analyze(Path("test.csv"))

        assert "parsing_info" in result
        assert "raw_data" in result
        assert "analysis" in result
        assert result["parsing_info"]["parsed_successfully"] is True

    @patch("paidsearchnav.parsers.per_store.logger")
    def test_parse_and_analyze_error(self, mock_logger, parser):
        """Test parse_and_analyze with error."""
        with patch.object(parser, "parse", side_effect=Exception("Parse error")):
            result = parser.parse_and_analyze(Path("test.csv"))

        assert "parsing_info" in result
        assert "analysis" in result
        assert result["parsing_info"]["parsed_successfully"] is False
        assert "error" in result["parsing_info"]
        mock_logger.error.assert_called_once()

    def test_analyze_store_performance_with_filtering(self, parser):
        """Test store performance analysis with filtering by min impressions."""
        # Create data with one store below threshold
        data = [
            {
                "store_name": "High Traffic Store",
                "local_impressions": "1000",  # Above threshold
                "store_visits": "50",
            },
            {
                "store_name": "Low Traffic Store",
                "local_impressions": "50",  # Below threshold (100)
                "store_visits": "5",
            },
        ]

        result = parser.analyze_store_performance(data)

        # Should only analyze the store above threshold
        assert result["total_stores"] == 1
        assert result["active_stores"] == 1

    def test_analyze_store_performance_call_tracking_insights(self, parser):
        """Test insights for stores with call tracking issues."""
        data = [
            {
                "store_name": "Store with Call Issues",
                "local_impressions": "1000",
                "store_visits": "50",
                "call_clicks": "0",  # No call clicks
                "phone_number": "+1-214-555-0100",  # But has phone number
            }
        ]

        result = parser.analyze_store_performance(data)

        # Should identify call tracking issue
        insights = result["strategic_insights"]
        assert any("call tracking" in insight.lower() for insight in insights)
