"""Tests for device parser API functionality."""

from io import BytesIO

import pytest
from fastapi.testclient import TestClient

from paidsearchnav_mcp.api.main import create_app


class TestDeviceParser:
    """Test class for device parser functionality."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        app = create_app()
        return TestClient(app)

    def test_parse_device_csv(self, client):
        """Test parsing device CSV file."""
        csv_content = """Device,Level,Campaign,Ad group,Bid adj.,Ad group bid adj.,Currency code,Avg. CPM,Impr.,Interactions,Interaction rate,Avg. cost,Cost,Conv. rate,Conversions,Cost / conv.
Computers,Campaign,PP_FIT_SRCH_Google_CON_GEN_General_NCRaleigh, --, --,None,USD,158.47,"165,256","8,579",5.19%,3.05,26188.81,3.52%,301.85,86.76
Tablets,Campaign,PP_FIT_SRCH_Google_CON_GEN_General_NCRaleigh, --, --,None,USD,129.47,"5,501",329,5.98%,2.16,712.21,3.04%,10.00,71.22
Mobile phones,Campaign,PP_FIT_SRCH_Google_CON_GEN_General_NCRaleigh, --, --,None,USD,187.90,"642,566","45,470",7.08%,2.66,120739.65,2.53%,"1,149.81",105.01"""

        files = {
            "file": (
                "device_report.csv",
                BytesIO(csv_content.encode("utf-8")),
                "text/csv",
            )
        }
        response = client.post("/api/v1/parse-csv?data_type=device", files=files)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["total_records"] == 3
        assert data["data_type"] == "device"
        assert "Device" in data["columns"]
        assert "Campaign" in data["columns"]
        assert "Conversions" in data["columns"]

    def test_analyze_device_csv(self, client):
        """Test analyzing device CSV file."""
        csv_content = """Device,Level,Campaign,Ad group,Bid adj.,Ad group bid adj.,Currency code,Avg. CPM,Impr.,Interactions,Interaction rate,Avg. cost,Cost,Conv. rate,Conversions,Cost / conv.
Computers,Campaign,PP_FIT_SRCH_Google_CON_GEN_General_NCRaleigh, --, --,None,USD,158.47,"165,256","8,579",5.19%,3.05,26188.81,3.52%,301.85,86.76
Tablets,Campaign,PP_FIT_SRCH_Google_CON_GEN_General_NCRaleigh, --, --,None,USD,129.47,"5,501",329,5.98%,2.16,712.21,3.04%,10.00,71.22
Mobile phones,Campaign,PP_FIT_SRCH_Google_CON_GEN_General_NCRaleigh, --, --,None,USD,187.90,"642,566","45,470",7.08%,2.66,120739.65,2.53%,"1,149.81",105.01
Computers,Campaign,PP_FIT_SRCH_Google_CON_BRN_TermOnly_AtlantaMorrow, --, --,None,USD,162.40,"2,509",647,25.79%,0.63,407.46,17.80%,115.17,3.54
Mobile phones,Campaign,PP_FIT_SRCH_Google_CON_BRN_TermOnly_AtlantaMorrow, --, --,None,USD,109.48,"39,336","8,535",21.70%,0.50,4306.44,13.65%,"1,165.05",3.70"""

        files = {
            "file": (
                "device_report.csv",
                BytesIO(csv_content.encode("utf-8")),
                "text/csv",
            )
        }
        response = client.post("/api/v1/analyze-csv?data_type=device", files=files)

        assert response.status_code == 200
        data = response.json()
        assert data["total_rows"] == 5
        assert data["analysis_summary"]["data_type"] == "device"
        assert data["analysis_summary"]["total_device_records"] == 5
        assert data["analysis_summary"]["mobile_records"] == 2
        assert data["analysis_summary"]["desktop_records"] == 2
        assert data["analysis_summary"]["tablet_records"] == 1
        assert "mobile_performance" in data["analysis_summary"]
        assert "desktop_performance" in data["analysis_summary"]
        assert "tablet_performance" in data["analysis_summary"]

    def test_device_performance_metrics(self, client):
        """Test device performance metrics calculation."""
        csv_content = """Device,Level,Campaign,Ad group,Bid adj.,Ad group bid adj.,Currency code,Avg. CPM,Impr.,Interactions,Interaction rate,Avg. cost,Cost,Conv. rate,Conversions,Cost / conv.
Computers,Campaign,Test Campaign, --, --,None,USD,100.00,"10,000","1,000",10.00%,2.00,2000.00,5.00%,50.00,40.00
Mobile phones,Campaign,Test Campaign, --, --,None,USD,150.00,"20,000","1,500",7.50%,3.00,4500.00,3.33%,50.00,90.00"""

        files = {
            "file": (
                "device_report.csv",
                BytesIO(csv_content.encode("utf-8")),
                "text/csv",
            )
        }
        response = client.post("/api/v1/analyze-csv?data_type=device", files=files)

        assert response.status_code == 200
        data = response.json()
        summary = data["analysis_summary"]

        # Check total metrics
        assert summary["total_cost"] == 6500.00
        assert summary["total_conversions"] == 100.00
        assert summary["avg_cpc"] > 0
        assert summary["conversion_rate"] > 0

        # Check desktop performance
        desktop_perf = summary["desktop_performance"]
        assert desktop_perf["total_cost"] == 2000.00
        assert desktop_perf["total_conversions"] == 50.00
        assert desktop_perf["conversion_rate"] == 5.00

        # Check mobile performance
        mobile_perf = summary["mobile_performance"]
        assert mobile_perf["total_cost"] == 4500.00
        assert mobile_perf["total_conversions"] == 50.00
        assert mobile_perf["conversion_rate"] == 3.33

    def test_device_with_google_ads_headers(self, client):
        """Test parsing device CSV with Google Ads export headers."""
        csv_content = """# Device report
# Downloaded from Google Ads on 2025-07-29
# Account: Test Account

Device,Level,Campaign,Ad group,Bid adj.,Ad group bid adj.,Currency code,Avg. CPM,Impr.,Interactions,Interaction rate,Avg. cost,Cost,Conv. rate,Conversions,Cost / conv.
Computers,Campaign,Test Campaign, --, --,None,USD,100.00,"10,000","1,000",10.00%,2.00,2000.00,5.00%,50.00,40.00
Mobile phones,Campaign,Test Campaign, --, --,None,USD,150.00,"20,000","1,500",7.50%,3.00,4500.00,3.33%,50.00,90.00"""

        files = {
            "file": (
                "device_report.csv",
                BytesIO(csv_content.encode("utf-8")),
                "text/csv",
            )
        }
        response = client.post("/api/v1/analyze-csv?data_type=device", files=files)

        assert response.status_code == 200
        data = response.json()
        assert data["total_rows"] == 2
        assert data["analysis_summary"]["total_device_records"] == 2

    def test_device_empty_file(self, client):
        """Test error handling for empty device file."""
        csv_content = ""

        files = {
            "file": ("empty.csv", BytesIO(csv_content.encode("utf-8")), "text/csv")
        }
        response = client.post("/api/v1/analyze-csv?data_type=device", files=files)

        assert response.status_code == 400
        assert "empty" in response.json()["detail"].lower()

    def test_device_invalid_format(self, client):
        """Test error handling for invalid CSV format."""
        csv_content = "This is not a valid CSV file"

        files = {
            "file": ("invalid.csv", BytesIO(csv_content.encode("utf-8")), "text/csv")
        }
        response = client.post("/api/v1/analyze-csv?data_type=device", files=files)

        assert response.status_code == 400

    def test_device_large_file_validation(self, client):
        """Test file size validation for device data."""
        # Create a CSV that's definitely over 100MB
        large_row = (
            "Computers,Campaign,Test Campaign with a very long name that takes up lots of space,"
            + "x" * 1000
            + ",--,None,USD,100.00,10000,1000,10.00%,2.00,2000.00,5.00%,50.00,40.00\\n"
        )
        large_content = (
            "Device,Level,Campaign,Ad group,Bid adj.,Ad group bid adj.,Currency code,Avg. CPM,Impr.,Interactions,Interaction rate,Avg. cost,Cost,Conv. rate,Conversions,Cost / conv.\\n"
            + large_row * 100000
        )

        files = {
            "file": ("large.csv", BytesIO(large_content.encode("utf-8")), "text/csv")
        }
        response = client.post("/api/v1/analyze-csv?data_type=device", files=files)

        assert response.status_code == 413
        assert "too large" in response.json()["detail"].lower()

    def test_device_non_csv_file(self, client):
        """Test rejection of non-CSV files."""
        txt_content = "This is a text file"

        files = {
            "file": ("test.txt", BytesIO(txt_content.encode("utf-8")), "text/plain")
        }
        response = client.post("/api/v1/analyze-csv?data_type=device", files=files)

        assert response.status_code == 400
        assert "CSV" in response.json()["detail"]

    def test_device_sample_data_cleaning(self, client):
        """Test that sample data is properly cleaned and sanitized."""
        csv_content = """Device,Level,Campaign,Ad group,Bid adj.,Ad group bid adj.,Currency code,Avg. CPM,Impr.,Interactions,Interaction rate,Avg. cost,Cost,Conv. rate,Conversions,Cost / conv.
=Computers,Campaign,Test Campaign, --, --,None,USD,100.00,"10,000","1,000",10.00%,2.00,2000.00,5.00%,50.00,40.00
+Mobile phones,Campaign,Test Campaign, --, --,None,USD,150.00,"20,000","1,500",7.50%,3.00,4500.00,3.33%,50.00,90.00"""

        files = {
            "file": (
                "device_report.csv",
                BytesIO(csv_content.encode("utf-8")),
                "text/csv",
            )
        }
        response = client.post("/api/v1/analyze-csv?data_type=device", files=files)

        assert response.status_code == 200
        data = response.json()

        # Check that dangerous formulas are sanitized in sample data
        for sample in data["sample_data"]:
            for value in sample.values():
                # Should not start with dangerous characters after sanitization
                assert not value.startswith("=")
                assert not value.startswith("+")

    def test_device_best_performer_identification(self, client):
        """Test identification of best performing device type."""
        csv_content = """Device,Level,Campaign,Ad group,Bid adj.,Ad group bid adj.,Currency code,Avg. CPM,Impr.,Interactions,Interaction rate,Avg. cost,Cost,Conv. rate,Conversions,Cost / conv.
Computers,Campaign,Test Campaign, --, --,None,USD,100.00,"10,000","1,000",10.00%,2.00,2000.00,8.00%,80.00,25.00
Mobile phones,Campaign,Test Campaign, --, --,None,USD,150.00,"20,000","1,500",7.50%,3.00,4500.00,3.33%,50.00,90.00
Tablets,Campaign,Test Campaign, --, --,None,USD,120.00,"5,000","300",6.00%,4.00,1200.00,2.50%,7.50,160.00"""

        files = {
            "file": (
                "device_report.csv",
                BytesIO(csv_content.encode("utf-8")),
                "text/csv",
            )
        }
        response = client.post("/api/v1/analyze-csv?data_type=device", files=files)

        assert response.status_code == 200
        data = response.json()
        summary = data["analysis_summary"]

        # Desktop should be the best performer with 8% conversion rate
        assert summary["best_performing_device"] == "Desktop"
        assert summary["best_conversion_rate"] == 8.0

    def test_device_metrics_with_zero_values(self, client):
        """Test that metrics are properly calculated when there are zero values."""
        csv_content = """Device,Level,Campaign,Ad group,Bid adj.,Ad group bid adj.,Currency code,Avg. CPM,Impr.,Interactions,Interaction rate,Avg. cost,Cost,Conv. rate,Conversions,Cost / conv.
Computers,Campaign,Test Campaign, --, --,None,USD,100.00,"10,000","1,000",10.00%,2.00,2000.00,0.00%,0.00,0.00"""

        files = {
            "file": (
                "device_report.csv",
                BytesIO(csv_content.encode("utf-8")),
                "text/csv",
            )
        }
        response = client.post("/api/v1/analyze-csv?data_type=device", files=files)

        assert response.status_code == 200
        data = response.json()

        # Verify analysis doesn't crash with zero conversions
        summary = data["analysis_summary"]
        assert summary["total_device_records"] == 1
        assert summary["desktop_performance"]["conversion_rate"] == 0.0
        assert summary["conversion_rate"] == 0.0

    def test_device_underperforming_campaigns(self, client):
        """Test identification of underperforming device/campaign combinations."""
        csv_content = """Device,Level,Campaign,Ad group,Bid adj.,Ad group bid adj.,Currency code,Avg. CPM,Impr.,Interactions,Interaction rate,Avg. cost,Cost,Conv. rate,Conversions,Cost / conv.
Computers,Campaign,High Cost Campaign, --, --,None,USD,100.00,"10,000","1,000",10.00%,5.00,5000.00,0.00%,0.00,0.00
Mobile phones,Campaign,Good Campaign, --, --,None,USD,150.00,"20,000","1,500",7.50%,3.00,4500.00,3.33%,50.00,90.00"""

        files = {
            "file": (
                "device_report.csv",
                BytesIO(csv_content.encode("utf-8")),
                "text/csv",
            )
        }
        response = client.post("/api/v1/analyze-csv?data_type=device", files=files)

        assert response.status_code == 200
        data = response.json()
        summary = data["analysis_summary"]

        # Should identify the high cost, zero conversion campaign
        assert summary["underperforming_device_campaigns"] >= 1
        assert len(summary["sample_underperforming"]) >= 1
        assert "High Cost Campaign" in summary["sample_underperforming"][0]
