"""Tests for ad groups parser API functionality."""

from io import BytesIO

import pytest
from fastapi.testclient import TestClient

from paidsearchnav.api.main import create_app


class TestAdGroupsParser:
    """Test class for ad groups parser functionality."""

    @pytest.fixture(scope="session")
    def client(self):
        """Create test client with session scope for better performance."""
        app = create_app()
        return TestClient(app)

    def test_parse_ad_groups_csv(self, client):
        """Test parsing ad groups CSV file."""
        csv_content = """Campaign,Ad group,Ad group state,Default max. CPC,Target CPA,Impr.,Clicks,Cost,Conversions,Conv. rate,Avg. CPC
Test Campaign,General_Gyms_Near Me,Enabled,1.50,,"10,000",500,750.00,25,5.00,1.50
Test Campaign,General_Membership,Enabled,2.00,,"8,000",300,600.00,18,6.00,2.00
Test Campaign,Term Only_Exact,Enabled,3.00,,"5,000",400,1200.00,52,13.00,3.00"""

        files = {
            "file": (
                "ad_groups.csv",
                BytesIO(csv_content.encode("utf-8")),
                "text/csv",
            )
        }
        response = client.post("/api/v1/parse-csv?data_type=ad_groups", files=files)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["total_records"] == 3
        assert data["data_type"] == "ad_groups"
        assert "Campaign" in data["columns"]
        assert "Ad group" in data["columns"]
        assert "Ad group state" in data["columns"]

    def test_analyze_ad_groups_csv(self, client):
        """Test analyzing ad groups CSV file."""
        csv_content = """Campaign,Ad group,Ad group state,Default max. CPC,Target CPA,Impr.,Clicks,Cost,Conversions,Conv. rate,Avg. CPC
Test Campaign 1,General_Gyms_Near Me,Enabled,1.50,,"10,000",500,750.00,25,5.00,1.50
Test Campaign 1,General_Membership,Enabled,2.00,,"8,000",300,600.00,18,6.00,2.00
Test Campaign 1,Term Only_Exact,Enabled,3.00,,"5,000",400,1200.00,52,13.00,3.00
Test Campaign 1,General_Gyms_Location,Paused,1.25,,"2,000",100,125.00,2,2.00,1.25
Test Campaign 2,Brand_Exact_Match,Enabled,1.00,,"15,000",800,800.00,80,10.00,1.00"""

        files = {
            "file": (
                "ad_groups.csv",
                BytesIO(csv_content.encode("utf-8")),
                "text/csv",
            )
        }
        response = client.post("/api/v1/analyze-csv?data_type=ad_groups", files=files)

        assert response.status_code == 200
        data = response.json()
        assert data["total_rows"] == 5
        assert data["analysis_summary"]["data_type"] == "ad_groups"
        assert data["analysis_summary"]["total_ad_groups"] == 5
        assert data["analysis_summary"]["active_ad_groups"] >= 4
        assert data["analysis_summary"]["paused_ad_groups"] >= 1

        # Test ad group theme analysis
        themes = data["analysis_summary"]["ad_group_themes"]
        assert "near_me_groups" in themes
        assert "membership_groups" in themes
        assert "brand_exact_groups" in themes
        assert "location_groups" in themes
        assert "other_groups" in themes

    def test_ad_groups_with_google_ads_headers(self, client):
        """Test parsing ad groups with Google Ads export headers."""
        csv_content = """# Ad group report
# Downloaded from Google Ads on 2025-07-30
# Account: Test Account

Campaign,Ad group,Ad group state,Default max. CPC,Impr.,Clicks,Cost,Conversions
Test Campaign,General_Gyms_Near Me,Enabled,1.50,"10,000",500,750.00,25
Test Campaign,General_Membership,Enabled,2.00,"8,000",300,600.00,18"""

        files = {
            "file": (
                "ad_groups.csv",
                BytesIO(csv_content.encode("utf-8")),
                "text/csv",
            )
        }
        response = client.post("/api/v1/analyze-csv?data_type=ad_groups", files=files)

        assert response.status_code == 200
        data = response.json()
        assert data["total_rows"] == 2
        assert data["analysis_summary"]["total_ad_groups"] == 2

    def test_ad_groups_theme_classification(self, client):
        """Test ad group theme classification functionality."""
        csv_content = """Campaign,Ad group,Ad group state,Default max. CPC,Impr.,Clicks,Cost,Conversions
Test Campaign,General_Gyms_Near Me,Enabled,1.50,"5,000",250,375.00,12
Test Campaign,General_Membership,Enabled,2.00,"4,000",200,400.00,10
Test Campaign,Term Only_Exact,Enabled,3.00,"3,000",300,900.00,39
Test Campaign,General_Gyms_Location,Enabled,1.25,"2,000",100,125.00,2
Test Campaign,Personal Training,Enabled,2.50,"1,000",50,125.00,5"""

        files = {
            "file": (
                "ad_groups.csv",
                BytesIO(csv_content.encode("utf-8")),
                "text/csv",
            )
        }
        response = client.post("/api/v1/analyze-csv?data_type=ad_groups", files=files)

        assert response.status_code == 200
        data = response.json()

        # Check theme classification
        themes = data["analysis_summary"]["ad_group_themes"]
        assert themes["near_me_groups"] >= 1  # General_Gyms_Near Me
        assert themes["membership_groups"] >= 1  # General_Membership
        assert themes["brand_exact_groups"] >= 1  # Term Only_Exact
        assert themes["location_groups"] >= 1  # General_Gyms_Location

        # Check theme performance analysis
        theme_performance = data["analysis_summary"]["theme_performance"]
        assert len(theme_performance) > 0

    def test_ad_groups_bidding_strategy_analysis(self, client):
        """Test bidding strategy analysis for ad groups."""
        csv_content = """Campaign,Ad group,Ad group state,Default max. CPC,Target CPA,Target ROAS,Impr.,Clicks,Cost,Conversions
Test Campaign,Ad Group 1,Enabled,1.50,,,"5,000",250,375.00,12
Test Campaign,Ad Group 2,Enabled,,25.00,,"4,000",200,400.00,10
Test Campaign,Ad Group 3,Enabled,,,3.50,"3,000",300,900.00,39
Test Campaign,Ad Group 4,Enabled,2.00,,,"2,000",100,200.00,5"""

        files = {
            "file": (
                "ad_groups.csv",
                BytesIO(csv_content.encode("utf-8")),
                "text/csv",
            )
        }
        response = client.post("/api/v1/analyze-csv?data_type=ad_groups", files=files)

        assert response.status_code == 200
        data = response.json()

        # Check bidding strategy analysis
        strategies = data["analysis_summary"]["bidding_strategies"]
        assert "target_cpa" in strategies
        assert "target_roas" in strategies
        assert "enhanced_cpc" in strategies
        assert strategies["target_cpa"] >= 1
        assert strategies["target_roas"] >= 1
        assert strategies["enhanced_cpc"] >= 2

    def test_ad_groups_performance_metrics(self, client):
        """Test ad groups performance metrics calculation."""
        csv_content = """Campaign,Ad group,Ad group state,Default max. CPC,Impr.,Clicks,Cost,Conversions,Conv. rate,Avg. CPC
Test Campaign,Test Ad Group 1,Enabled,1.50,"10,000",500,750.00,25,5.00,1.50
Test Campaign,Test Ad Group 2,Enabled,2.00,"8,000",300,600.00,18,6.00,2.00
Test Campaign,Test Ad Group 3,Paused,1.25,"2,000",100,125.00,2,2.00,1.25"""

        files = {
            "file": (
                "ad_groups.csv",
                BytesIO(csv_content.encode("utf-8")),
                "text/csv",
            )
        }
        response = client.post("/api/v1/analyze-csv?data_type=ad_groups", files=files)

        assert response.status_code == 200
        data = response.json()

        # Check basic metrics
        summary = data["analysis_summary"]
        assert summary["total_cost"] == 1475.0
        assert summary["total_clicks"] == 900
        assert summary["total_conversions"] == 45.0
        assert summary["avg_cpc"] > 0
        assert summary["conversion_rate"] > 0
        assert summary["avg_cost_per_conversion"] > 0

    def test_ad_groups_empty_file(self, client):
        """Test error handling for empty ad groups file."""
        csv_content = ""

        files = {
            "file": ("empty.csv", BytesIO(csv_content.encode("utf-8")), "text/csv")
        }
        response = client.post("/api/v1/analyze-csv?data_type=ad_groups", files=files)

        assert response.status_code == 400
        assert "empty" in response.json()["detail"].lower()

    def test_ad_groups_non_csv_file(self, client):
        """Test rejection of non-CSV files."""
        txt_content = "This is a text file"

        files = {
            "file": ("test.txt", BytesIO(txt_content.encode("utf-8")), "text/plain")
        }
        response = client.post("/api/v1/analyze-csv?data_type=ad_groups", files=files)

        assert response.status_code == 400
        assert "CSV" in response.json()["detail"]

    def test_ad_groups_underperformer_identification(self, client):
        """Test identification of underperforming ad groups."""
        csv_content = """Campaign,Ad group,Ad group state,Default max. CPC,Impr.,Clicks,Cost,Conversions
Test Campaign,High Cost No Conv,Enabled,5.00,"1,000",100,500.00,0
Test Campaign,Good Performance,Enabled,1.50,"10,000",500,750.00,25
Test Campaign,Low Cost No Conv,Enabled,0.50,"2,000",20,10.00,0"""

        files = {
            "file": (
                "ad_groups.csv",
                BytesIO(csv_content.encode("utf-8")),
                "text/csv",
            )
        }
        response = client.post("/api/v1/analyze-csv?data_type=ad_groups", files=files)

        assert response.status_code == 200
        data = response.json()

        # Should identify the high cost, no conversion ad group
        summary = data["analysis_summary"]
        assert summary["underperforming_ad_groups"] >= 1
        assert len(summary["sample_underperforming"]) >= 1
        assert "High Cost No Conv" in str(summary["sample_underperforming"])

    def test_ad_groups_local_intent_identification(self, client):
        """Test identification of local intent ad groups."""
        csv_content = """Campaign,Ad group,Ad group state,Default max. CPC,Impr.,Clicks,Cost,Conversions
Test Campaign,Near Me Search,Enabled,1.50,"5,000",250,375.00,12
Test Campaign,Local Gyms,Enabled,1.75,"4,000",200,350.00,10
Test Campaign,Houston Location,Enabled,2.00,"3,000",150,300.00,8
Test Campaign,General Terms,Enabled,1.25,"6,000",300,375.00,15"""

        files = {
            "file": (
                "ad_groups.csv",
                BytesIO(csv_content.encode("utf-8")),
                "text/csv",
            )
        }
        response = client.post("/api/v1/analyze-csv?data_type=ad_groups", files=files)

        assert response.status_code == 200
        data = response.json()

        # Should identify local intent ad groups
        summary = data["analysis_summary"]
        assert summary["local_intent_ad_groups"] >= 3
        assert len(summary["sample_local_intent"]) >= 3
        local_intent_str = str(summary["sample_local_intent"])
        assert (
            "Near Me Search" in local_intent_str
            or "Local Gyms" in local_intent_str
            or "Houston Location" in local_intent_str
        )

    def test_ad_groups_empty_ad_group_names(self, client):
        """Test handling of empty or null ad group names."""
        csv_content = """Campaign,Ad group,Ad group state,Default max. CPC,Impr.,Clicks,Cost,Conversions
Test Campaign,,Enabled,1.50,"5,000",250,375.00,12
Test Campaign,   ,Enabled,2.00,"4,000",200,400.00,10
Test Campaign,Normal Ad Group,Enabled,1.25,"3,000",150,300.00,8"""

        files = {
            "file": (
                "ad_groups.csv",
                BytesIO(csv_content.encode("utf-8")),
                "text/csv",
            )
        }
        response = client.post("/api/v1/analyze-csv?data_type=ad_groups", files=files)

        assert response.status_code == 200
        data = response.json()

        # Should handle empty names gracefully
        summary = data["analysis_summary"]
        assert summary["total_ad_groups"] == 3
        assert (
            summary["ad_group_themes"]["other_groups"] >= 2
        )  # Empty names classified as "other"

    def test_ad_groups_missing_required_fields(self, client):
        """Test handling of missing required fields."""
        csv_content = """Campaign,Ad group,Ad group state,Impr.,Clicks
Test Campaign,Test Ad Group,Enabled,"5,000",250"""  # Missing Cost and Conversions

        files = {
            "file": (
                "ad_groups.csv",
                BytesIO(csv_content.encode("utf-8")),
                "text/csv",
            )
        }
        response = client.post("/api/v1/analyze-csv?data_type=ad_groups", files=files)

        assert response.status_code == 200
        data = response.json()

        # Should handle missing fields gracefully with defaults
        summary = data["analysis_summary"]
        assert summary["total_ad_groups"] == 1
        assert summary["total_cost"] == 0.0  # Default when Cost field missing
        assert (
            summary["total_conversions"] == 0.0
        )  # Default when Conversions field missing

    def test_ad_groups_malformed_numeric_data(self, client):
        """Test handling of malformed numeric data."""
        csv_content = """Campaign,Ad group,Ad group state,Default max. CPC,Impr.,Clicks,Cost,Conversions
Test Campaign,Test Ad Group 1,Enabled,invalid_cpc,"not_a_number",abc,bad_cost,xyz
Test Campaign,Test Ad Group 2,Enabled,1.50,"5,000",250,375.00,12"""

        files = {
            "file": (
                "ad_groups.csv",
                BytesIO(csv_content.encode("utf-8")),
                "text/csv",
            )
        }
        response = client.post("/api/v1/analyze-csv?data_type=ad_groups", files=files)

        assert response.status_code == 200
        data = response.json()

        # Should handle malformed data gracefully with defaults
        summary = data["analysis_summary"]
        assert summary["total_ad_groups"] == 2
        assert summary["total_cost"] == 375.0  # Only valid cost counted
        assert summary["total_conversions"] == 12.0  # Only valid conversions counted

    def test_ad_groups_edge_case_theme_classification(self, client):
        """Test edge cases in theme classification."""
        csv_content = """Campaign,Ad group,Ad group state,Default max. CPC,Impr.,Clicks,Cost,Conversions
Test Campaign,NEAR_ME_ALL_CAPS,Enabled,1.50,"5,000",250,375.00,12
Test Campaign,membership-special,Enabled,2.00,"4,000",200,400.00,10
Test Campaign,Brand_EXACT_Mixed,Enabled,1.75,"3,000",150,300.00,8
Test Campaign,city_location_Test,Enabled,1.25,"2,000",100,200.00,5
Test Campaign,   random   spaces   ,Enabled,1.00,"1,000",50,100.00,2"""

        files = {
            "file": (
                "ad_groups.csv",
                BytesIO(csv_content.encode("utf-8")),
                "text/csv",
            )
        }
        response = client.post("/api/v1/analyze-csv?data_type=ad_groups", files=files)

        assert response.status_code == 200
        data = response.json()

        # Should handle case-insensitive classification correctly
        themes = data["analysis_summary"]["ad_group_themes"]
        assert themes["near_me_groups"] >= 1  # NEAR_ME_ALL_CAPS
        assert themes["membership_groups"] >= 1  # membership-special
        assert themes["brand_exact_groups"] >= 1  # Brand_EXACT_Mixed
        assert themes["location_groups"] >= 1  # city_location_Test

    def test_ad_groups_division_by_zero_protection(self, client):
        """Test protection against division by zero in calculations."""
        csv_content = """Campaign,Ad group,Ad group state,Default max. CPC,Impr.,Clicks,Cost,Conversions
Test Campaign,Zero Clicks Ad Group,Enabled,1.50,"5,000",0,0.00,0
Test Campaign,Normal Ad Group,Enabled,2.00,"4,000",200,400.00,10"""

        files = {
            "file": (
                "ad_groups.csv",
                BytesIO(csv_content.encode("utf-8")),
                "text/csv",
            )
        }
        response = client.post("/api/v1/analyze-csv?data_type=ad_groups", files=files)

        assert response.status_code == 200
        data = response.json()

        # Should handle zero values without crashing
        summary = data["analysis_summary"]
        assert summary["total_ad_groups"] == 2
        assert "avg_cpc" in summary
        assert "conversion_rate" in summary
        assert "avg_cost_per_conversion" in summary

        # Theme performance should handle zero division
        theme_performance = summary["theme_performance"]
        assert isinstance(theme_performance, dict)
