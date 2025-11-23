"""Unit tests for campaigns parser functionality."""

from io import BytesIO

import pytest
from fastapi.testclient import TestClient

from paidsearchnav_mcp.api.main import create_app
from paidsearchnav_mcp.api.services import CSVAnalysisService


class TestCampaignsParser:
    """Test class for campaigns parser functionality."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        app = create_app()
        return TestClient(app)

    @pytest.fixture
    def csv_service(self):
        """Create CSV analysis service."""
        return CSVAnalysisService()

    @pytest.fixture
    def sample_campaigns_csv(self):
        """Sample campaigns CSV data."""
        return """Campaign report
All time
Campaign status,Campaign,Budget,Budget name,Budget type,Currency code,Status,Status reasons,Optimization score,Campaign type,Avg. CPM,Impr.,Interactions,Interaction rate,Avg. cost,Cost,Conv. (Platform Comparable),Cost / Conv. (Platform Comparable),Conv. value / Cost (Platform Comparable),Bid strategy type,Viewable CTR,Avg. viewable CPM,Viewable impr.,Clicks,Conv. rate,Conv. value,Conv. value / cost,Conversions,Avg. CPC,Cost / conv.
Enabled,Test Campaign 1,1000.00, --,Daily,USD,Eligible,eligible,75.0,Search,100.00,10000,5000,50.0%,2.00,10000.00,0.00,0,0.00,CPC (enhanced), --,0,0,5000,10.0%,50000.00,5.0,500.0,2.00,20.00
Enabled,Test Campaign 2,500.00, --,Daily,USD,Eligible,eligible,80.0,Search,150.00,5000,2000,40.0%,3.00,6000.00,0.00,0,0.00,Target ROAS, --,0,0,2000,5.0%,20000.00,3.33,100.0,3.00,60.00
Paused,Test Campaign 3,200.00, --,Daily,USD,Paused,paused,60.0,Display,200.00,1000,100,10.0%,10.00,1000.00,0.00,0,0.00,CPC (enhanced), --,0,0,100,0.0%,0.00,0.0,0.0,10.00,0.00"""

    @pytest.fixture
    def sample_campaigns_data(self):
        """Sample parsed campaigns data."""
        return [
            {
                "Campaign status": "Enabled",
                "Campaign": "Test Campaign 1",
                "Budget": "1000.00",
                "Campaign type": "Search",
                "Cost": "10000.00",
                "Clicks": "5000",
                "Conversions": "500.0",
            },
            {
                "Campaign status": "Enabled",
                "Campaign": "Test Campaign 2",
                "Budget": "500.00",
                "Campaign type": "Search",
                "Cost": "6000.00",
                "Clicks": "2000",
                "Conversions": "100.0",
            },
            {
                "Campaign status": "Paused",
                "Campaign": "Test Campaign 3",
                "Budget": "200.00",
                "Campaign type": "Display",
                "Cost": "1000.00",
                "Clicks": "100",
                "Conversions": "0.0",
            },
        ]

    def test_parse_google_ads_csv_campaigns(self, csv_service, sample_campaigns_csv):
        """Test parsing of Google Ads campaigns CSV."""
        rows, columns = csv_service.parse_google_ads_csv(sample_campaigns_csv)

        assert len(rows) == 3
        assert "Campaign status" in columns
        assert "Campaign" in columns
        assert "Budget" in columns
        assert "Campaign type" in columns

        # Check first campaign
        assert rows[0]["Campaign"] == "Test Campaign 1"
        assert rows[0]["Campaign status"] == "Enabled"
        assert rows[0]["Budget"] == "1000.00"

    def test_analyze_campaigns_data(self, csv_service, sample_campaigns_data):
        """Test campaigns data analysis."""
        result = csv_service.analyze_data_by_type(sample_campaigns_data, "campaigns")

        assert result["data_type"] == "campaigns"
        assert result["total_campaigns"] == 3
        assert result["enabled_campaigns"] == 2
        assert result["paused_campaigns"] == 1
        assert result["search_campaigns"] == 2
        assert result["other_campaigns"] == 1
        assert result["total_budget"] == 1700.0  # 1000 + 500 + 200
        assert result["total_spend"] == 17000.0  # 10000 + 6000 + 1000
        assert result["avg_cost_per_conversion"] == 28.33  # 17000 / 600

    def test_extract_metrics(self, csv_service):
        """Test metric extraction from campaign row."""
        row = {"Cost": "10,000.50", "Clicks": "5,000", "Conversions": "100.5"}

        cost, clicks, conversions = csv_service._extract_metrics(row)

        assert cost == 10000.50
        assert clicks == 5000
        assert conversions == 100.5

    def test_extract_metrics_empty_values(self, csv_service):
        """Test metric extraction with empty/invalid values."""
        row = {"Cost": "", "Clicks": "--", "Conversions": "invalid"}

        cost, clicks, conversions = csv_service._extract_metrics(row)

        assert cost == 0.0
        assert clicks == 0
        assert conversions == 0.0

    def test_analyze_campaign_row(self, csv_service):
        """Test individual campaign row analysis."""
        negative_candidates = []
        local_intent_terms = []

        # High cost, no conversions campaign
        row = {"Campaign": "Expensive Campaign", "Campaign type": "Search"}
        csv_service._analyze_campaign_row(
            row, 1000.0, 0.0, negative_candidates, local_intent_terms
        )

        assert len(negative_candidates) == 1
        assert "Expensive Campaign (High cost, no conversions)" in negative_candidates
        assert len(local_intent_terms) == 0

        # Non-search campaign
        row = {"Campaign": "Display Campaign", "Campaign type": "Display"}
        csv_service._analyze_campaign_row(
            row, 100.0, 10.0, negative_candidates, local_intent_terms
        )

        assert len(local_intent_terms) == 1
        assert "Display Campaign (Display)" in local_intent_terms

    def test_campaigns_summary_generation(self, csv_service, sample_campaigns_data):
        """Test campaigns-specific summary generation."""
        result = csv_service._generate_campaigns_summary(
            sample_campaigns_data, 17000.0, 600.0, [], []
        )

        assert result["data_type"] == "campaigns"
        assert result["total_campaigns"] == 3
        assert result["enabled_campaigns"] == 2
        assert result["paused_campaigns"] == 1
        assert result["search_campaigns"] == 2
        assert result["other_campaigns"] == 1
        assert result["total_budget"] == 1700.0
        assert result["total_spend"] == 17000.0
        assert result["avg_cost_per_conversion"] == 28.33

    def test_clean_sample_data(self, csv_service, sample_campaigns_data):
        """Test sample data cleaning."""
        cleaned = csv_service.clean_sample_data(sample_campaigns_data, 2)

        assert len(cleaned) == 2
        assert all(isinstance(row, dict) for row in cleaned)
        assert all(
            isinstance(key, str) and isinstance(value, str)
            for row in cleaned
            for key, value in row.items()
        )

    def test_api_parse_campaigns_csv(self, client, sample_campaigns_csv):
        """Test campaigns CSV parsing API endpoint."""
        csv_bytes = sample_campaigns_csv.encode("utf-8")
        files = {"file": ("campaigns.csv", BytesIO(csv_bytes), "text/csv")}

        response = client.post("/api/v1/parse-csv?data_type=campaigns", files=files)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["total_records"] == 3
        assert data["data_type"] == "campaigns"
        assert "Campaign status" in data["columns"]

    def test_api_analyze_campaigns_csv(self, client, sample_campaigns_csv):
        """Test campaigns CSV analysis API endpoint."""
        csv_bytes = sample_campaigns_csv.encode("utf-8")
        files = {"file": ("campaigns.csv", BytesIO(csv_bytes), "text/csv")}

        response = client.post("/api/v1/analyze-csv?data_type=campaigns", files=files)

        assert response.status_code == 200
        data = response.json()
        assert data["total_rows"] == 3
        assert data["analysis_summary"]["data_type"] == "campaigns"
        assert data["analysis_summary"]["total_campaigns"] == 3
        assert data["analysis_summary"]["enabled_campaigns"] == 2
        assert data["analysis_summary"]["search_campaigns"] == 2

    def test_file_validation_invalid_extension(self, client):
        """Test file validation with invalid extension."""
        files = {"file": ("test.txt", BytesIO(b"test"), "text/plain")}

        response = client.post("/api/v1/parse-csv", files=files)

        assert response.status_code == 400
        assert "CSV with .csv extension" in response.json()["detail"]

    def test_file_validation_large_file(self, client):
        """Test file validation with large file."""
        # Create a large CSV content (over 100MB)
        large_content = "Campaign,Cost\n" + "Test,100\n" * 12000000  # ~120MB
        csv_bytes = large_content.encode("utf-8")
        files = {"file": ("large.csv", BytesIO(csv_bytes), "text/csv")}

        response = client.post("/api/v1/parse-csv", files=files)

        assert response.status_code == 413
        assert "File too large" in response.json()["detail"]

    def test_error_handling_invalid_csv(self, client):
        """Test error handling with completely empty CSV file."""
        # Create an empty CSV file
        invalid_csv = ""
        csv_bytes = invalid_csv.encode("utf-8")
        files = {"file": ("empty.csv", BytesIO(csv_bytes), "text/csv")}

        response = client.post("/api/v1/analyze-csv", files=files)

        assert response.status_code == 400
        assert "CSV file is empty" in response.json()["detail"]

    def test_cors_security(self, client):
        """Test CORS configuration is secure."""
        response = client.options("/api/v1/parse-csv")

        # Should not allow all origins
        cors_header = response.headers.get("access-control-allow-origin")
        assert cors_header != "*"

    def test_campaigns_field_mapping_coverage(self, csv_service):
        """Test that campaigns field mapping covers all expected fields."""
        from paidsearchnav.parsers.field_mappings import get_field_mapping

        mapping = get_field_mapping("campaigns")

        # Check key fields are mapped
        assert "Campaign" in mapping
        assert "Campaign status" in mapping or "Campaign state" in mapping
        assert "Budget" in mapping
        assert "Campaign type" in mapping
        assert "Cost" in mapping
        assert "Clicks" in mapping
        assert "Conversions" in mapping
