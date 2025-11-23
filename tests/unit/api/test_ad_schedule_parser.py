"""Tests for ad schedule parser API functionality."""

from io import BytesIO

import pytest
from fastapi.testclient import TestClient

from paidsearchnav_mcp.api.main import create_app


class TestAdScheduleParser:
    """Test class for ad schedule parser functionality."""

    @pytest.fixture(scope="session")
    def client(self):
        """Create test client with session scope for better performance."""
        app = create_app()
        return TestClient(app)

    def test_parse_ad_schedule_csv(self, client):
        """Test parsing ad schedule CSV file."""
        csv_content = """Day & time,Campaign,Bid adj.,Currency code,Impr.,Interactions,Cost,Conversions,Interaction rate
"Mondays, 8:00 AM - 6:00 PM",Test Campaign BRN,+0%,USD,"3,500",890,774.30,140,25.43%
"Tuesdays, 6:00 PM - 12:00 AM",Test Campaign GEN,-20%,USD,"1,350",100,869.00,9,7.41%
"Saturdays, all day",Test Campaign BRN,--,USD,"2,800",504,831.60,64,18.00%"""

        files = {
            "file": (
                "ad_schedule.csv",
                BytesIO(csv_content.encode("utf-8")),
                "text/csv",
            )
        }
        response = client.post("/api/v1/parse-csv?data_type=ad_schedule", files=files)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["total_records"] == 3
        assert data["data_type"] == "ad_schedule"
        assert "Day & time" in data["columns"]
        assert "Campaign" in data["columns"]
        assert "Bid adj." in data["columns"]

    def test_analyze_ad_schedule_csv(self, client):
        """Test analyzing ad schedule CSV file."""
        csv_content = """Day & time,Campaign,Bid adj.,Currency code,Impr.,Interactions,Cost,Conversions,Interaction rate,Clicks,CTR,Conv. rate
"Mondays, 8:00 AM - 6:00 PM",Test Campaign BRN,+0%,USD,"3,500",890,774.30,140,25.43%,890,25.43%,15.73%
"Tuesdays, 8:00 AM - 6:00 PM",Test Campaign BRN,+0%,USD,"4,200",1068,801.00,159,25.43%,1068,25.43%,14.89%
"Wednesdays, 6:00 PM - 12:00 AM",Test Campaign GEN,-20%,USD,"1,180",87,891.75,7,7.37%,87,7.37%,8.05%
"Saturdays, all day",Test Campaign BRN,--,USD,"2,800",504,831.60,64,18.00%,504,18.00%,12.70%
"Sundays, all day",Test Campaign BRN,--,USD,"2,650",477,820.44,54,18.00%,477,18.00%,11.32%"""

        files = {
            "file": (
                "ad_schedule.csv",
                BytesIO(csv_content.encode("utf-8")),
                "text/csv",
            )
        }
        response = client.post("/api/v1/analyze-csv?data_type=ad_schedule", files=files)

        assert response.status_code == 200
        data = response.json()
        assert data["total_rows"] == 5
        assert data["analysis_summary"]["data_type"] == "ad_schedule"
        assert data["analysis_summary"]["total_schedule_records"] == 5

        # Test time period classification
        time_periods = data["analysis_summary"]["time_periods"]
        assert "business_hours" in time_periods
        assert "evening" in time_periods
        assert "weekend_all_day" in time_periods
        assert time_periods["business_hours"] >= 2  # Monday and Tuesday business hours
        assert time_periods["evening"] >= 1  # Wednesday evening
        assert time_periods["weekend_all_day"] >= 2  # Saturday and Sunday all day

    def test_ad_schedule_with_google_ads_headers(self, client):
        """Test parsing ad schedule with Google Ads export headers."""
        csv_content = """# Ad schedule report
# Downloaded from Google Ads on 2025-07-30
# Account: Test Account

Day & time,Campaign,Bid adj.,Currency code,Impr.,Interactions,Cost,Conversions,Interaction rate
"Mondays, 8:00 AM - 6:00 PM",Test Campaign BRN,+0%,USD,"3,500",890,774.30,140,25.43%
"Saturdays, all day",Test Campaign BRN,--,USD,"2,800",504,831.60,64,18.00%"""

        files = {
            "file": (
                "ad_schedule.csv",
                BytesIO(csv_content.encode("utf-8")),
                "text/csv",
            )
        }
        response = client.post("/api/v1/analyze-csv?data_type=ad_schedule", files=files)

        assert response.status_code == 200
        data = response.json()
        assert data["total_rows"] == 2
        assert data["analysis_summary"]["total_schedule_records"] == 2

    def test_ad_schedule_time_period_classification(self, client):
        """Test time period classification functionality."""
        csv_content = """Day & time,Campaign,Bid adj.,Currency code,Impr.,Interactions,Cost,Conversions,Interaction rate
"Mondays, 8:00 AM - 6:00 PM",Test Campaign,+0%,USD,"3,500",890,774.30,140,25.43%
"Tuesdays, 6:00 PM - 12:00 AM",Test Campaign,-20%,USD,"1,350",100,869.00,9,7.41%
"Wednesdays, 12:00 AM - 8:00 AM",Test Campaign,--,USD,"800",48,600.00,2,6.00%
"Saturdays, all day",Test Campaign,--,USD,"2,800",504,831.60,64,18.00%
"Sundays, all day",Test Campaign,--,USD,"2,650",477,820.44,54,18.00%"""

        files = {
            "file": (
                "ad_schedule.csv",
                BytesIO(csv_content.encode("utf-8")),
                "text/csv",
            )
        }
        response = client.post("/api/v1/analyze-csv?data_type=ad_schedule", files=files)

        assert response.status_code == 200
        data = response.json()

        # Check time period classification
        time_periods = data["analysis_summary"]["time_periods"]
        assert time_periods["business_hours"] >= 1  # Monday business hours
        assert time_periods["evening"] >= 1  # Tuesday evening
        assert time_periods["early_morning"] >= 1  # Wednesday early morning
        assert time_periods["weekend_all_day"] >= 2  # Saturday and Sunday all day

    def test_ad_schedule_bid_adjustment_analysis(self, client):
        """Test bid adjustment analysis for ad schedule."""
        csv_content = """Day & time,Campaign,Bid adj.,Currency code,Impr.,Interactions,Cost,Conversions,Interaction rate
"Mondays, 8:00 AM - 6:00 PM",Test Campaign,+0%,USD,"3,500",890,774.30,140,25.43%
"Tuesdays, 8:00 AM - 6:00 PM",Test Campaign,+15%,USD,"4,200",1068,801.00,159,25.43%
"Wednesdays, 6:00 PM - 12:00 AM",Test Campaign,-20%,USD,"1,180",87,891.75,7,7.37%
"Thursdays, 6:00 PM - 12:00 AM",Test Campaign,--,USD,"1,400",105,957.60,8,7.50%"""

        files = {
            "file": (
                "ad_schedule.csv",
                BytesIO(csv_content.encode("utf-8")),
                "text/csv",
            )
        }
        response = client.post("/api/v1/analyze-csv?data_type=ad_schedule", files=files)

        assert response.status_code == 200
        data = response.json()

        # Check bid adjustment analysis
        bid_adjustments = data["analysis_summary"]["bid_adjustments"]
        assert "neutral" in bid_adjustments
        assert "positive" in bid_adjustments
        assert "negative" in bid_adjustments
        assert "default" in bid_adjustments
        assert bid_adjustments["neutral"] >= 1  # +0%
        assert bid_adjustments["positive"] >= 1  # +15%
        assert bid_adjustments["negative"] >= 1  # -20%
        assert bid_adjustments["default"] >= 1  # --

    def test_ad_schedule_day_distribution(self, client):
        """Test day of week distribution analysis."""
        csv_content = """Day & time,Campaign,Bid adj.,Currency code,Impr.,Interactions,Cost,Conversions,Interaction rate
"Mondays, 8:00 AM - 6:00 PM",Test Campaign,+0%,USD,"3,500",890,774.30,140,25.43%
"Tuesdays, 8:00 AM - 6:00 PM",Test Campaign,+0%,USD,"4,200",1068,801.00,159,25.43%
"Wednesdays, 6:00 PM - 12:00 AM",Test Campaign,-20%,USD,"1,180",87,891.75,7,7.37%
"Thursdays, 6:00 PM - 12:00 AM",Test Campaign,-20%,USD,"1,400",105,957.60,8,7.50%
"Fridays, 8:00 AM - 6:00 PM",Test Campaign,+0%,USD,"3,600",900,855.00,132,25.00%
"Saturdays, all day",Test Campaign,--,USD,"2,800",504,831.60,64,18.00%
"Sundays, all day",Test Campaign,--,USD,"2,650",477,820.44,54,18.00%"""

        files = {
            "file": (
                "ad_schedule.csv",
                BytesIO(csv_content.encode("utf-8")),
                "text/csv",
            )
        }
        response = client.post("/api/v1/analyze-csv?data_type=ad_schedule", files=files)

        assert response.status_code == 200
        data = response.json()

        # Check day distribution
        day_distribution = data["analysis_summary"]["day_distribution"]
        assert day_distribution["Monday"] >= 1
        assert day_distribution["Tuesday"] >= 1
        assert day_distribution["Wednesday"] >= 1
        assert day_distribution["Thursday"] >= 1
        assert day_distribution["Friday"] >= 1
        assert day_distribution["Saturday"] >= 1
        assert day_distribution["Sunday"] >= 1

    def test_ad_schedule_performance_metrics(self, client):
        """Test ad schedule performance metrics calculation."""
        csv_content = """Day & time,Campaign,Bid adj.,Currency code,Impr.,Interactions,Cost,Conversions,Interaction rate,Clicks,CTR,Conv. rate
"Mondays, 8:00 AM - 6:00 PM",Test Campaign,+0%,USD,"3,500",890,774.30,140,25.43%,890,25.43%,15.73%
"Tuesdays, 6:00 PM - 12:00 AM",Test Campaign,-20%,USD,"1,350",100,869.00,9,7.41%,100,7.41%,9.00%
"Saturdays, all day",Test Campaign,--,USD,"2,800",504,831.60,64,18.00%,504,18.00%,12.70%"""

        files = {
            "file": (
                "ad_schedule.csv",
                BytesIO(csv_content.encode("utf-8")),
                "text/csv",
            )
        }
        response = client.post("/api/v1/analyze-csv?data_type=ad_schedule", files=files)

        assert response.status_code == 200
        data = response.json()

        # Check basic metrics
        summary = data["analysis_summary"]
        assert summary["total_cost"] == 2474.9
        assert summary["total_clicks"] == 1494
        assert summary["total_conversions"] == 213.0
        assert summary["avg_cpc"] > 0
        assert summary["conversion_rate"] > 0
        assert summary["avg_interaction_rate"] > 0

    def test_ad_schedule_weekend_vs_weekday(self, client):
        """Test weekend vs weekday performance analysis."""
        csv_content = """Day & time,Campaign,Bid adj.,Currency code,Impr.,Interactions,Cost,Conversions,Interaction rate
"Mondays, 8:00 AM - 6:00 PM",Test Campaign,+0%,USD,"3,500",890,774.30,140,25.43%
"Tuesdays, 8:00 AM - 6:00 PM",Test Campaign,+0%,USD,"4,200",1068,801.00,159,25.43%
"Saturdays, all day",Test Campaign,--,USD,"2,800",504,831.60,64,18.00%
"Sundays, all day",Test Campaign,--,USD,"2,650",477,820.44,54,18.00%"""

        files = {
            "file": (
                "ad_schedule.csv",
                BytesIO(csv_content.encode("utf-8")),
                "text/csv",
            )
        }
        response = client.post("/api/v1/analyze-csv?data_type=ad_schedule", files=files)

        assert response.status_code == 200
        data = response.json()

        # Check weekend vs weekday analysis
        summary = data["analysis_summary"]
        assert "weekend_vs_weekday" in summary
        assert summary["weekend_records"] >= 2  # Saturday and Sunday
        assert summary["weekday_records"] >= 2  # Monday and Tuesday business hours

    def test_ad_schedule_peak_performance_identification(self, client):
        """Test identification of peak performance periods."""
        csv_content = """Day & time,Campaign,Bid adj.,Currency code,Impr.,Interactions,Cost,Conversions,Interaction rate,Clicks,CTR,Conv. rate
"Mondays, 8:00 AM - 6:00 PM",Test Campaign,+0%,USD,"3,500",890,774.30,140,25.43%,890,25.43%,15.73%
"Tuesdays, 6:00 PM - 12:00 AM",Test Campaign,-20%,USD,"1,350",100,869.00,9,7.41%,100,7.41%,9.00%
"Saturdays, all day",Test Campaign,--,USD,"2,800",504,831.60,64,18.00%,504,18.00%,12.70%"""

        files = {
            "file": (
                "ad_schedule.csv",
                BytesIO(csv_content.encode("utf-8")),
                "text/csv",
            )
        }
        response = client.post("/api/v1/analyze-csv?data_type=ad_schedule", files=files)

        assert response.status_code == 200
        data = response.json()

        # Check peak performance identification
        summary = data["analysis_summary"]
        assert "peak_performance_time" in summary
        assert "best_conversion_rate" in summary
        assert "time_period_performance" in summary
        assert isinstance(summary["time_period_performance"], dict)

    def test_ad_schedule_underperformer_identification(self, client):
        """Test identification of underperforming time periods."""
        csv_content = """Day & time,Campaign,Bid adj.,Currency code,Impr.,Interactions,Cost,Conversions,Interaction rate
"Mondays, 8:00 AM - 6:00 PM",Test Campaign,+0%,USD,"3,500",890,774.30,140,25.43%
"Tuesdays, 12:00 AM - 8:00 AM",Test Campaign,--,USD,"800",48,600.00,0,6.00%
"Saturdays, all day",Test Campaign,--,USD,"2,800",504,831.60,64,18.00%"""

        files = {
            "file": (
                "ad_schedule.csv",
                BytesIO(csv_content.encode("utf-8")),
                "text/csv",
            )
        }
        response = client.post("/api/v1/analyze-csv?data_type=ad_schedule", files=files)

        assert response.status_code == 200
        data = response.json()

        # Should identify underperforming time periods (high cost, no conversions)
        summary = data["analysis_summary"]
        assert "underperforming_time_periods" in summary
        assert "sample_underperforming" in summary
        # Tuesday early morning should be flagged as underperforming (high cost, 0 conversions)

    def test_ad_schedule_empty_file(self, client):
        """Test error handling for empty ad schedule file."""
        csv_content = ""

        files = {
            "file": ("empty.csv", BytesIO(csv_content.encode("utf-8")), "text/csv")
        }
        response = client.post("/api/v1/analyze-csv?data_type=ad_schedule", files=files)

        assert response.status_code == 400
        assert "empty" in response.json()["detail"].lower()

    def test_ad_schedule_non_csv_file(self, client):
        """Test rejection of non-CSV files."""
        txt_content = "This is a text file"

        files = {
            "file": ("test.txt", BytesIO(txt_content.encode("utf-8")), "text/plain")
        }
        response = client.post("/api/v1/analyze-csv?data_type=ad_schedule", files=files)

        assert response.status_code == 400
        assert "CSV" in response.json()["detail"]

    def test_ad_schedule_malformed_time_strings(self, client):
        """Test handling of malformed time strings and bid adjustments."""
        csv_content = """Day & time,Campaign,Bid adj.,Currency code,Impr.,Interactions,Cost,Conversions,Interaction rate
"Invalid time format",Test Campaign,+0%,USD,"3,500",890,774.30,140,25.43%
"Tuesdays, invalid time",Test Campaign,-,USD,"1,350",100,869.00,9,7.41%
"Saturdays, all day",Test Campaign,invalid_bid,USD,"2,800",504,831.60,64,18.00%
"",Test Campaign,,USD,"1,000",50,250.00,5,5.00%"""

        files = {
            "file": (
                "ad_schedule.csv",
                BytesIO(csv_content.encode("utf-8")),
                "text/csv",
            )
        }
        response = client.post("/api/v1/analyze-csv?data_type=ad_schedule", files=files)

        assert response.status_code == 200
        data = response.json()
        assert data["total_rows"] == 4

        # Should handle malformed data gracefully
        summary = data["analysis_summary"]
        assert "time_periods" in summary
        assert "bid_adjustments" in summary

        # Invalid time formats should be classified as "unknown"
        time_periods = summary["time_periods"]
        assert "unknown" in time_periods or sum(time_periods.values()) >= 2

        # Invalid bid adjustments should be handled gracefully
        bid_adjustments = summary["bid_adjustments"]
        assert sum(bid_adjustments.values()) == 4  # All rows should be classified

    def test_ad_schedule_edge_case_time_classification(self, client):
        """Test edge cases in time period classification."""
        csv_content = """Day & time,Campaign,Bid adj.,Currency code,Impr.,Interactions,Cost,Conversions,Interaction rate
"Mondays, 12:00 AM - 8:00 AM",Test Campaign,+0%,USD,"1,000",50,100.00,5,5.00%
"Tuesdays, 8:00 AM - 6:00 PM",Test Campaign,+0%,USD,"1,200",60,120.00,6,5.00%
"Wednesdays, 6:00 PM - 12:00 AM",Test Campaign,+0%,USD,"1,100",55,110.00,5,5.00%
"SATURDAYS, ALL DAY",Test Campaign,+0%,USD,"2,000",100,200.00,10,5.00%
"sundays, all day",Test Campaign,+0%,USD,"1,800",90,180.00,9,5.00%"""

        files = {
            "file": (
                "ad_schedule.csv",
                BytesIO(csv_content.encode("utf-8")),
                "text/csv",
            )
        }
        response = client.post("/api/v1/analyze-csv?data_type=ad_schedule", files=files)

        assert response.status_code == 200
        data = response.json()

        # Check edge case classification
        time_periods = data["analysis_summary"]["time_periods"]

        # Boundary times should be classified correctly
        assert time_periods["early_morning"] >= 1  # 12:00 AM - 8:00 AM
        assert time_periods["business_hours"] >= 1  # 8:00 AM - 6:00 PM
        assert time_periods["evening"] >= 1  # 6:00 PM - 12:00 AM

        # Case-insensitive weekend detection
        assert time_periods["weekend_all_day"] >= 2  # Both Saturday and Sunday

    def test_ad_schedule_division_by_zero_protection(self, client):
        """Test protection against division by zero in ad schedule calculations."""
        csv_content = """Day & time,Campaign,Bid adj.,Currency code,Impr.,Interactions,Cost,Conversions,Interaction rate,Clicks,CTR,Conv. rate
"Mondays, 8:00 AM - 6:00 PM",Test Campaign,+0%,USD,"1,000",0,0.00,0,0.00%,0,0.00%,0.00%
"Tuesdays, 6:00 PM - 12:00 AM",Test Campaign,-20%,USD,"2,000",100,200.00,10,5.00%,100,5.00%,10.00%"""

        files = {
            "file": (
                "ad_schedule.csv",
                BytesIO(csv_content.encode("utf-8")),
                "text/csv",
            )
        }
        response = client.post("/api/v1/analyze-csv?data_type=ad_schedule", files=files)

        assert response.status_code == 200
        data = response.json()

        # Should handle zero values without crashing
        summary = data["analysis_summary"]
        assert "avg_cpc" in summary
        assert "conversion_rate" in summary
        assert isinstance(summary["avg_cpc"], (int, float))
        assert isinstance(summary["conversion_rate"], (int, float))

        # Time period performance should handle zero division
        time_performance = summary["time_period_performance"]
        assert isinstance(time_performance, dict)
        for period_data in time_performance.values():
            assert "conversion_rate" in period_data
            assert "cost_per_conversion" in period_data
            assert isinstance(period_data["conversion_rate"], (int, float))
            assert isinstance(period_data["cost_per_conversion"], (int, float))
