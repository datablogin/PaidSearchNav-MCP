"""Unit tests for DaypartingAnalyzer."""

import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from paidsearchnav.analyzers.dayparting import (
    DaypartingAnalysisResult,
    DaypartingAnalyzer,
)


class TestDaypartingAnalyzer:
    """Test DaypartingAnalyzer functionality."""

    @pytest.fixture
    def mock_api_client(self):
        """Create mock API client."""
        client = MagicMock()
        client.get_ad_schedule_performance = AsyncMock()
        return client

    @pytest.fixture
    def analyzer(self, mock_api_client):
        """Create DaypartingAnalyzer instance."""
        return DaypartingAnalyzer(
            api_client=mock_api_client,
            min_impressions=100,
            min_conversions=5,
            performance_threshold=0.2,
            significance_threshold=0.05,
        )

    @pytest.fixture
    def sample_schedule_data(self):
        """Create sample ad schedule performance data."""
        return [
            {
                "campaign_id": "123",
                "campaign_name": "Test Campaign",
                "day_time": "Monday, 8:00 AM - 9:00 AM",
                "day_of_week": "Monday",
                "hour": 8,
                "bid_adjustment": 1.1,
                "impressions": 1000,
                "clicks": 100,
                "conversions": 10.0,
                "cost_micros": 50_000_000,
                "conversion_value_micros": 200_000_000,
                "ctr": 0.1,
                "avg_cpc": 500_000,
                "conversion_rate": 0.1,
                "cpa": 5_000_000,
                "cost": 50.0,
            },
            {
                "campaign_id": "123",
                "campaign_name": "Test Campaign",
                "day_time": "Tuesday, All hours",
                "day_of_week": "Tuesday",
                "hour": None,
                "bid_adjustment": None,
                "impressions": 800,
                "clicks": 40,
                "conversions": 2.0,
                "cost_micros": 30_000_000,
                "conversion_value_micros": 60_000_000,
                "ctr": 0.05,
                "avg_cpc": 750_000,
                "conversion_rate": 0.05,
                "cpa": 15_000_000,
                "cost": 30.0,
            },
            {
                "campaign_id": "123",
                "campaign_name": "Test Campaign",
                "day_time": "Thursday, 2:00 PM - 3:00 PM",
                "day_of_week": "Thursday",
                "hour": 14,
                "bid_adjustment": 1.2,
                "impressions": 1200,
                "clicks": 120,
                "conversions": 15.0,
                "cost_micros": 60_000_000,
                "conversion_value_micros": 300_000_000,
                "ctr": 0.1,
                "avg_cpc": 500_000,
                "conversion_rate": 0.125,
                "cpa": 4_000_000,
                "cost": 60.0,
            },
            {
                "campaign_id": "123",
                "campaign_name": "Test Campaign",
                "day_time": "Friday, 6:00 PM - 7:00 PM",
                "day_of_week": "Friday",
                "hour": 18,
                "bid_adjustment": 0.9,
                "impressions": 500,
                "clicks": 25,
                "conversions": 1.0,
                "cost_micros": 20_000_000,
                "conversion_value_micros": 30_000_000,
                "ctr": 0.05,
                "avg_cpc": 800_000,
                "conversion_rate": 0.04,
                "cpa": 20_000_000,
                "cost": 20.0,
            },
        ]

    async def test_analyze_success(
        self, analyzer, mock_api_client, sample_schedule_data
    ):
        """Test successful analysis."""
        # Setup mock
        mock_api_client.get_ad_schedule_performance.return_value = sample_schedule_data

        # Run analysis
        result = await analyzer.analyze(
            customer_id="123456789",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        # Verify result
        assert isinstance(result, DaypartingAnalysisResult)
        assert result.customer_id == "123456789"
        assert result.analyzer_name == "dayparting"
        assert len(result.schedule_data) == 4

        # Verify API call
        mock_api_client.get_ad_schedule_performance.assert_called_once_with(
            customer_id="123456789",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
            campaign_ids=None,
        )

    async def test_day_performance_analysis(
        self, analyzer, mock_api_client, sample_schedule_data
    ):
        """Test day of week performance analysis."""
        mock_api_client.get_ad_schedule_performance.return_value = sample_schedule_data

        result = await analyzer.analyze(
            customer_id="123456789",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        # Check day performance
        assert "Monday" in result.day_performance
        assert "Tuesday" in result.day_performance
        assert "Thursday" in result.day_performance
        assert "Friday" in result.day_performance

        # Verify Thursday has best performance
        thursday_perf = result.day_performance["Thursday"]
        assert thursday_perf["conversion_rate"] == 0.125
        assert thursday_perf["conversions"] == 15.0

        # Verify Friday has worst performance
        friday_perf = result.day_performance["Friday"]
        assert friday_perf["conversion_rate"] == 0.04
        assert friday_perf["conversions"] == 1.0

    async def test_hour_performance_analysis(
        self, analyzer, mock_api_client, sample_schedule_data
    ):
        """Test hour of day performance analysis."""
        mock_api_client.get_ad_schedule_performance.return_value = sample_schedule_data

        result = await analyzer.analyze(
            customer_id="123456789",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        # Check hour performance (excluding "All hours" entries)
        assert "8 AM" in result.hour_performance
        assert "2 PM" in result.hour_performance
        assert "6 PM" in result.hour_performance

        # Verify 2 PM has best performance
        two_pm_perf = result.hour_performance["2 PM"]
        assert two_pm_perf["conversion_rate"] == 0.125

    async def test_recommendations_generation(
        self, analyzer, mock_api_client, sample_schedule_data
    ):
        """Test recommendation generation."""
        mock_api_client.get_ad_schedule_performance.return_value = sample_schedule_data

        result = await analyzer.analyze(
            customer_id="123456789",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        # Check for recommendations
        assert len(result.recommendations) > 0

        # Should have bid adjustment recommendations
        assert len(result.bid_adjustment_recommendations) > 0

        # Thursday should have positive bid adjustment
        thursday_rec = next(
            (
                r
                for r in result.bid_adjustment_recommendations
                if r["day"] == "Thursday"
            ),
            None,
        )
        assert thursday_rec is not None
        assert thursday_rec["recommended_bid_adjustment"] > 0

        # Tuesday should have negative bid adjustment (lowest conversion rate)
        tuesday_rec = next(
            (r for r in result.bid_adjustment_recommendations if r["day"] == "Tuesday"),
            None,
        )
        # Tuesday might not have bid adjustment if it doesn't meet cost threshold
        # or performance threshold criteria
        if tuesday_rec:
            assert tuesday_rec["recommended_bid_adjustment"] < 0

    async def test_best_worst_performers(
        self, analyzer, mock_api_client, sample_schedule_data
    ):
        """Test identification of best and worst performers."""
        mock_api_client.get_ad_schedule_performance.return_value = sample_schedule_data

        result = await analyzer.analyze(
            customer_id="123456789",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        # Check best performers
        assert len(result.best_performing_days) > 0
        best_day = result.best_performing_days[0]
        assert best_day["day"] == "Thursday"
        assert best_day["conversion_rate"] == 0.125

        # Check worst performers
        assert len(result.worst_performing_days) > 0
        worst_day = result.worst_performing_days[0]
        # Tuesday has the worst conversion rate in the test data
        assert worst_day["day"] == "Tuesday"
        assert worst_day["conversion_rate"] == 0.05

    async def test_variance_calculations(
        self, analyzer, mock_api_client, sample_schedule_data
    ):
        """Test variance metric calculations."""
        mock_api_client.get_ad_schedule_performance.return_value = sample_schedule_data

        result = await analyzer.analyze(
            customer_id="123456789",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        # Check variance metrics
        assert result.conversion_rate_variance_by_day > 0
        assert result.cost_efficiency_variance > 0

    async def test_filter_by_campaign_ids(
        self, analyzer, mock_api_client, sample_schedule_data
    ):
        """Test filtering by campaign IDs."""
        mock_api_client.get_ad_schedule_performance.return_value = sample_schedule_data

        result = await analyzer.analyze(
            customer_id="123456789",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
            campaign_ids=["123", "456"],
        )

        # Verify API called with campaign IDs
        mock_api_client.get_ad_schedule_performance.assert_called_once_with(
            customer_id="123456789",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
            campaign_ids=["123", "456"],
        )

    async def test_minimum_threshold_filtering(self, analyzer, mock_api_client):
        """Test filtering by minimum impressions threshold."""
        # Create data with low impressions
        low_impression_data = [
            {
                "campaign_id": "123",
                "campaign_name": "Test Campaign",
                "day_time": "Monday, All hours",
                "day_of_week": "Monday",
                "hour": None,
                "bid_adjustment": None,
                "impressions": 50,  # Below threshold
                "clicks": 5,
                "conversions": 0.0,
                "cost_micros": 5_000_000,
                "conversion_value_micros": 0,
                "ctr": 0.1,
                "avg_cpc": 1_000_000,
                "conversion_rate": 0.0,
                "cpa": 0,
                "cost": 5.0,
            },
            {
                "campaign_id": "123",
                "campaign_name": "Test Campaign",
                "day_time": "Tuesday, All hours",
                "day_of_week": "Tuesday",
                "hour": None,
                "bid_adjustment": None,
                "impressions": 200,  # Above threshold
                "clicks": 20,
                "conversions": 2.0,
                "cost_micros": 10_000_000,
                "conversion_value_micros": 40_000_000,
                "ctr": 0.1,
                "avg_cpc": 500_000,
                "conversion_rate": 0.1,
                "cpa": 5_000_000,
                "cost": 10.0,
            },
        ]

        mock_api_client.get_ad_schedule_performance.return_value = low_impression_data

        result = await analyzer.analyze(
            customer_id="123456789",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        # Should only include Tuesday data
        assert len(result.schedule_data) == 1
        assert result.schedule_data[0].day_of_week == "Tuesday"

    async def test_parse_day_time(self, analyzer):
        """Test day_time parsing."""
        # Test with hour range
        day, hour = analyzer._parse_day_time("Monday, 12:00 AM - 1:00 AM")
        assert day == "Monday"
        assert hour == "12:00 AM - 1:00 AM"

        # Test with all hours
        day, hour = analyzer._parse_day_time("Tuesday, All hours")
        assert day == "Tuesday"
        assert hour is None

        # Test with just day
        day, hour = analyzer._parse_day_time("Wednesday")
        assert day == "Wednesday"
        assert hour is None

        # Test empty string
        day, hour = analyzer._parse_day_time("")
        assert day == ""
        assert hour is None

    async def test_potential_improvements_calculation(
        self, analyzer, mock_api_client, sample_schedule_data
    ):
        """Test calculation of potential improvements."""
        mock_api_client.get_ad_schedule_performance.return_value = sample_schedule_data

        result = await analyzer.analyze(
            customer_id="123456789",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        # Should calculate potential savings and conversion increase
        assert result.potential_savings > 0
        assert result.potential_conversion_increase > 0

    async def test_error_handling(self, analyzer, mock_api_client):
        """Test error handling."""
        mock_api_client.get_ad_schedule_performance.side_effect = Exception("API Error")

        with pytest.raises(Exception) as exc_info:
            await analyzer.analyze(
                customer_id="123456789",
                start_date=datetime(2024, 1, 1),
                end_date=datetime(2024, 1, 31),
            )

        assert "API Error" in str(exc_info.value)

    def test_analyzer_name(self, analyzer):
        """Test analyzer name."""
        assert analyzer.get_name() == "dayparting"

    def test_analyzer_description(self, analyzer):
        """Test analyzer description."""
        description = analyzer.get_description()
        assert "ad schedule" in description.lower()
        assert "optimal times" in description.lower()


class TestDaypartingAnalyzerCSV:
    """Test DaypartingAnalyzer CSV functionality."""

    @pytest.fixture
    def sample_csv_content(self):
        """Sample CSV content for testing."""
        return """# Ad schedule report
# Downloaded from Google Ads on 2025-07-30
# Account: Test Account

Day & time,Campaign,Bid adj.,Currency code,Avg. CPM,Impr.,Interactions,Interaction rate,Avg. cost,Cost,Conv. rate,Conversions,Cost / conv.
"Mondays, 8:00 AM - 6:00 PM",Test Campaign,+10%,USD,14.52,"1,500",150,10.00%,0.87,130.50,8.00%,12,10.88
"Tuesdays, 8:00 AM - 6:00 PM",Test Campaign,+0%,USD,13.98,"2,000",180,9.00%,0.75,135.00,7.78%,14,9.64
"Wednesdays, all day",Test Campaign,--,USD,15.21,"1,800",162,9.00%,0.88,142.56,6.79%,11,12.96
"Thursdays, 12:00 AM - 8:00 AM",Test Campaign,-20%,USD,18.75,"800",40,5.00%,1.50,60.00,5.00%,2,30.00
"Fridays, 6:00 PM - 12:00 AM",Test Campaign,+15%,USD,16.30,"1,200",120,10.00%,0.95,114.00,10.00%,12,9.50
"""

    @pytest.fixture
    def malformed_csv_content(self):
        """Malformed CSV content for testing error handling."""
        return """Some random text
Not a proper CSV format
Missing required columns"""

    @pytest.fixture
    def empty_csv_content(self):
        """Empty CSV content for testing."""
        return """# Ad schedule report
Day & time,Campaign,Bid adj.,Currency code,Avg. CPM,Impr.,Interactions,Interaction rate,Avg. cost,Cost,Conv. rate,Conversions,Cost / conv.
"""

    def test_from_csv_success(self, sample_csv_content):
        """Test successful CSV parsing."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(sample_csv_content)
            temp_path = Path(f.name)

        try:
            analyzer = DaypartingAnalyzer.from_csv(temp_path)

            # Check that data was loaded
            assert analyzer._csv_data is not None
            assert len(analyzer._csv_data) == 5

            # Check first record
            first_record = analyzer._csv_data[0]
            assert first_record.day_of_week == "Monday"
            assert first_record.hour_range == "8:00 AM - 6:00 PM"
            assert first_record.impressions == 1500
            assert first_record.clicks == 150
            assert first_record.conversions == 12.0
            assert first_record.cost == 130.50
            assert first_record.bid_adjustment == 0.10  # +10% -> 0.10

            # Check "all day" record
            all_day_record = analyzer._csv_data[2]
            assert all_day_record.day_of_week == "Wednesday"
            assert all_day_record.hour_range is None
            assert all_day_record.bid_adjustment is None  # "--" -> None

            # Check negative bid adjustment
            negative_bid_record = analyzer._csv_data[3]
            assert negative_bid_record.bid_adjustment == -0.20  # -20% -> -0.20

        finally:
            temp_path.unlink()

    def test_from_csv_file_not_found(self):
        """Test handling of non-existent file."""
        with pytest.raises(FileNotFoundError) as exc_info:
            DaypartingAnalyzer.from_csv("non_existent_file.csv")
        assert "CSV file not found" in str(exc_info.value)

    def test_from_csv_invalid_extension(self):
        """Test handling of non-CSV file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Not a CSV file")
            temp_path = Path(f.name)

        try:
            with pytest.raises(ValueError) as exc_info:
                DaypartingAnalyzer.from_csv(temp_path)
            assert "Expected .csv file" in str(exc_info.value)
        finally:
            temp_path.unlink()

    def test_from_csv_file_too_large(self, sample_csv_content):
        """Test handling of file size limit."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(sample_csv_content)
            temp_path = Path(f.name)

        try:
            with pytest.raises(ValueError) as exc_info:
                # Set very small max size to trigger error
                DaypartingAnalyzer.from_csv(temp_path, max_file_size_mb=0.0001)
            assert "CSV file too large" in str(exc_info.value)
        finally:
            temp_path.unlink()

    def test_from_csv_missing_required_columns(self, malformed_csv_content):
        """Test handling of CSV with missing required columns."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(malformed_csv_content)
            temp_path = Path(f.name)

        try:
            with pytest.raises(ValueError) as exc_info:
                DaypartingAnalyzer.from_csv(temp_path)
            assert "CSV missing required columns" in str(exc_info.value)
        finally:
            temp_path.unlink()

    def test_from_csv_empty_data(self, empty_csv_content):
        """Test handling of CSV with no data rows."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(empty_csv_content)
            temp_path = Path(f.name)

        try:
            with pytest.raises(ValueError) as exc_info:
                DaypartingAnalyzer.from_csv(temp_path)
            assert "No valid ad schedule data found" in str(exc_info.value)
        finally:
            temp_path.unlink()

    def test_from_csv_data_parsing(self, sample_csv_content):
        """Test detailed data parsing from CSV."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(sample_csv_content)
            temp_path = Path(f.name)

        try:
            analyzer = DaypartingAnalyzer.from_csv(temp_path)

            # Test that all records were parsed correctly
            assert len(analyzer._csv_data) == 5

            # Test calculated metrics
            for record in analyzer._csv_data:
                if record.clicks > 0:
                    assert record.ctr == record.clicks / record.impressions
                    assert record.avg_cpc == record.cost / record.clicks
                    if record.conversions > 0:
                        assert (
                            record.conversion_rate == record.conversions / record.clicks
                        )
                        assert record.cpa == record.cost / record.conversions

            # Test campaign name parsing
            for record in analyzer._csv_data:
                assert record.campaign_name == "Test Campaign"

        finally:
            temp_path.unlink()

    async def test_analyze_with_csv_data(self, sample_csv_content):
        """Test analysis using CSV data."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(sample_csv_content)
            temp_path = Path(f.name)

        try:
            analyzer = DaypartingAnalyzer.from_csv(temp_path)

            # Run analysis with CSV data
            result = await analyzer.analyze(
                customer_id="123456789",
                start_date=datetime(2024, 1, 1),
                end_date=datetime(2024, 1, 31),
            )

            # Check that analysis was performed
            assert isinstance(result, DaypartingAnalysisResult)
            assert len(result.schedule_data) > 0
            assert len(result.day_performance) > 0

            # Check day performance aggregation
            assert "Monday" in result.day_performance
            assert "Tuesday" in result.day_performance
            assert "Wednesday" in result.day_performance

            # Check metrics calculation
            for day_metrics in result.day_performance.values():
                assert "impressions" in day_metrics
                assert "clicks" in day_metrics
                assert "conversions" in day_metrics
                assert "cost" in day_metrics

        finally:
            temp_path.unlink()

    def test_from_csv_with_currency_symbols(self):
        """Test CSV parsing with currency symbols."""
        csv_content = """Day & time,Campaign,Bid adj.,Currency code,Impr.,Interactions,Cost,Conversions
"Mondays, 9:00 AM - 5:00 PM",Campaign A,+5%,USD,"1,000",100,$50.00,5
"Tuesdays, all day",Campaign B,--,EUR,"2,000",150,€75.50,8
"Wednesdays, 10:00 AM - 2:00 PM",Campaign C,-10%,GBP,"1,500",120,£45.25,6
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            temp_path = Path(f.name)

        try:
            analyzer = DaypartingAnalyzer.from_csv(temp_path)

            assert len(analyzer._csv_data) == 3

            # Check that currency symbols were handled
            assert analyzer._csv_data[0].cost == 50.00
            assert analyzer._csv_data[1].cost == 75.50
            assert analyzer._csv_data[2].cost == 45.25

        finally:
            temp_path.unlink()

    def test_from_csv_with_24_hour_format(self):
        """Test CSV parsing with 24-hour time format."""
        csv_content = """Day & time,Campaign,Bid adj.,Currency code,Impr.,Interactions,Cost,Conversions
"Mondays, 09:00 - 17:00",Campaign A,+5%,USD,"1,000",100,50.00,5
"Tuesdays, 14:30 - 18:45",Campaign B,+10%,USD,"2,000",150,75.00,8
"Wednesdays, 00:00 - 06:00",Campaign C,-20%,USD,"500",25,12.50,1
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            temp_path = Path(f.name)

        try:
            analyzer = DaypartingAnalyzer.from_csv(temp_path)

            assert len(analyzer._csv_data) == 3

            # Check that 24-hour times were converted to 12-hour format
            assert analyzer._csv_data[0].hour_range == "9:00 AM - 5:00 PM"
            assert analyzer._csv_data[1].hour_range == "2:30 PM - 6:45 PM"
            assert analyzer._csv_data[2].hour_range == "12:00 AM - 6:00 AM"

        finally:
            temp_path.unlink()

    def test_from_csv_with_negative_values(self):
        """Test CSV parsing handles negative values appropriately."""
        csv_content = """Day & time,Campaign,Bid adj.,Currency code,Impr.,Interactions,Cost,Conversions
"Mondays, 9:00 AM - 5:00 PM",Campaign A,+5%,USD,"-100",100,50.00,5
"Tuesdays, all day",Campaign B,--,USD,"2,000",-50,75.00,8
"Wednesdays, 10:00 AM - 2:00 PM",Campaign C,-10%,USD,"1,500",120,-45.25,-2
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            temp_path = Path(f.name)

        try:
            analyzer = DaypartingAnalyzer.from_csv(temp_path)

            # Negative values should be set to 0
            assert analyzer._csv_data[0].impressions == 0  # Was negative
            assert analyzer._csv_data[1].clicks == 0  # Was negative
            assert analyzer._csv_data[2].cost == 0.0  # Currency shouldn't be negative
            assert analyzer._csv_data[2].conversions == 0.0  # Was negative

        finally:
            temp_path.unlink()

    def test_from_csv_with_alternative_column_names(self):
        """Test CSV parsing with alternative column names."""
        csv_content = """Day and time,Campaign name,Bid adjustment,Currency code,Impressions,Clicks,Cost,Conv.,Conv. rate
"Mondays, 9:00 AM - 5:00 PM",Campaign A,+5%,USD,"1,000",100,50.00,5,5.00%
"Tuesdays, all day",Campaign B,--,USD,"2,000",150,75.00,8,5.33%
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            temp_path = Path(f.name)

        try:
            analyzer = DaypartingAnalyzer.from_csv(temp_path)

            assert len(analyzer._csv_data) == 2

            # Check that alternative column names were handled
            first_record = analyzer._csv_data[0]
            assert first_record.day_of_week == "Monday"
            assert first_record.impressions == 1000
            assert first_record.clicks == 100
            assert first_record.conversions == 5.0

        finally:
            temp_path.unlink()
