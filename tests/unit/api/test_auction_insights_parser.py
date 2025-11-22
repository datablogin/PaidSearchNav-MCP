"""Unit tests for auction insights parser functionality."""

from io import BytesIO

import pytest
from fastapi.testclient import TestClient

from paidsearchnav.api.main import create_app
from paidsearchnav.api.services import CSVAnalysisService


class TestAuctionInsightsParser:
    """Test class for auction insights parser functionality."""

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
    def sample_auction_insights_csv(self):
        """Sample auction insights CSV data."""
        return """Auction insights report
Campaign date range: Dec 1, 2024 - Dec 31, 2024
Display URL domain,Impr. share,Overlap rate,Top of page rate,Abs. Top of page rate,Outranking share,Position above rate
yourdomain.com,32.1%,--,--,--,--,--
competitor1.com,25.5%,18.2%,45.3%,12.1%,38.7%,22.4%
competitor2.com,18.9%,15.6%,32.8%,8.9%,29.3%,18.7%
competitor3.com,12.3%,10.4%,28.1%,7.2%,22.6%,15.3%
competitor4.com,8.7%,8.1%,21.4%,5.5%,18.2%,12.8%
localstore.com,4.8%,4.2%,19.3%,4.1%,11.8%,8.2%"""

    @pytest.fixture
    def sample_auction_insights_data(self):
        """Sample parsed auction insights data."""
        return [
            {
                "Display URL domain": "yourdomain.com",
                "Impr. share": "32.1%",
                "Overlap rate": "--",
                "Top of page rate": "--",
                "Abs. Top of page rate": "--",
                "Outranking share": "--",
                "Position above rate": "--",
            },
            {
                "Display URL domain": "competitor1.com",
                "Impr. share": "25.5%",
                "Overlap rate": "18.2%",
                "Top of page rate": "45.3%",
                "Abs. Top of page rate": "12.1%",
                "Outranking share": "38.7%",
                "Position above rate": "22.4%",
            },
            {
                "Display URL domain": "competitor2.com",
                "Impr. share": "18.9%",
                "Overlap rate": "15.6%",
                "Top of page rate": "32.8%",
                "Abs. Top of page rate": "8.9%",
                "Outranking share": "29.3%",
                "Position above rate": "18.7%",
            },
        ]

    def test_parse_auction_insights_csv(self, csv_service, sample_auction_insights_csv):
        """Test parsing auction insights CSV content."""
        rows, columns = csv_service.parse_google_ads_csv(sample_auction_insights_csv)

        assert len(rows) == 6  # 6 domains in the test data
        assert "Display URL domain" in columns
        assert "Impr. share" in columns
        assert "Overlap rate" in columns

        # Check first row (own domain)
        assert rows[0]["Display URL domain"] == "yourdomain.com"
        assert rows[0]["Impr. share"] == "32.1%"
        assert rows[0]["Overlap rate"] == "--"

        # Check competitor row
        assert rows[1]["Display URL domain"] == "competitor1.com"
        assert rows[1]["Impr. share"] == "25.5%"
        assert rows[1]["Overlap rate"] == "18.2%"

    def test_analyze_auction_insights_data(
        self, csv_service, sample_auction_insights_data
    ):
        """Test analysis of auction insights data."""
        analysis = csv_service.analyze_data_by_type(
            sample_auction_insights_data, "auction_insights"
        )

        assert analysis["data_type"] == "auction_insights"
        assert "total_competitors" in analysis
        assert "market_analysis" in analysis
        assert "position_analysis" in analysis
        assert "competitive_insights" in analysis

        # Should identify competitors (excluding own domain)
        assert analysis["total_competitors"] == 2
        assert analysis["market_analysis"]["top_competitor"] == "competitor1.com"

    def test_parse_csv_endpoint_auction_insights(
        self, client, sample_auction_insights_csv
    ):
        """Test the /api/v1/parse-csv endpoint with auction insights data."""
        # Create file-like object
        file_data = BytesIO(sample_auction_insights_csv.encode("utf-8"))

        response = client.post(
            "/api/v1/parse-csv?data_type=auction_insights&show_sample=true&sample_size=3",
            files={"file": ("auction_insights.csv", file_data, "text/csv")},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "success"
        assert data["data_type"] == "auction_insights"
        assert data["total_records"] == 6
        assert len(data["sample_records"]) == 3

        # Check that the columns are correctly parsed
        expected_columns = [
            "Display URL domain",
            "Impr. share",
            "Overlap rate",
            "Top of page rate",
            "Abs. Top of page rate",
            "Outranking share",
            "Position above rate",
        ]
        for col in expected_columns:
            assert col in data["columns"]

    def test_analyze_csv_endpoint_auction_insights(
        self, client, sample_auction_insights_csv
    ):
        """Test the /api/v1/analyze-csv endpoint with auction insights data."""
        # Create file-like object
        file_data = BytesIO(sample_auction_insights_csv.encode("utf-8"))

        response = client.post(
            "/api/v1/analyze-csv?data_type=auction_insights",
            files={"file": ("auction_insights.csv", file_data, "text/csv")},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["filename"] == "auction_insights.csv"
        assert data["total_rows"] == 6
        assert len(data["sample_data"]) <= 3

        # Check analysis summary contains auction insights specific data
        analysis = data["analysis_summary"]
        assert analysis["data_type"] == "auction_insights"
        assert "total_competitors" in analysis
        assert "market_analysis" in analysis

    def test_auction_insights_row_analysis(self, csv_service):
        """Test individual row analysis for auction insights."""
        row = {
            "Display URL domain": "competitor1.com",
            "Impr. share": "25.5%",
            "Overlap rate": "35.2%",  # High overlap
            "Outranking share": "15.0%",  # Low outranking
        }

        negative_candidates = []
        local_terms = []

        csv_service._analyze_auction_insights_row(row, negative_candidates, local_terms)

        # Should identify as strong competitor
        assert len(negative_candidates) == 1
        assert "competitor1.com" in negative_candidates[0]
        assert "Strong competitor" in negative_candidates[0]

    def test_auction_insights_local_competitor_detection(self, csv_service):
        """Test detection of local competitors."""
        row = {
            "Display URL domain": "localstore.com",
            "Impr. share": "8.5%",
            "Overlap rate": "5.0%",
            "Outranking share": "10.0%",
        }

        negative_candidates = []
        local_terms = []

        csv_service._analyze_auction_insights_row(row, negative_candidates, local_terms)

        # Should not be identified as strong competitor (low thresholds)
        assert len(negative_candidates) == 0
        # Should be identified as local competitor (domain contains "local" keyword)
        assert len(local_terms) == 1

        # Test with explicit local domain
        local_row = {
            "Display URL domain": "cityshop.com",
            "Impr. share": "6.0%",
            "Overlap rate": "3.0%",
            "Outranking share": "8.0%",
        }

        local_terms.clear()
        csv_service._analyze_auction_insights_row(
            local_row, negative_candidates, local_terms
        )

        # Should identify as local competitor
        assert len(local_terms) == 1
        assert "Local competitor: cityshop.com" in local_terms[0]

    def test_percentage_parsing_in_analysis(self, csv_service):
        """Test percentage parsing functionality in analysis service."""
        assert csv_service._parse_percentage("25.5%") == 0.255
        assert csv_service._parse_percentage("100%") == 1.0
        assert csv_service._parse_percentage("--") == 0.0
        assert csv_service._parse_percentage("") == 0.0

    def test_market_position_calculation_in_analysis(self, csv_service):
        """Test market position calculation in analysis service."""
        own_domain = {"domain": "yourdomain.com", "impression_share": 0.25}
        competitors = [
            {"domain": "competitor1.com", "impression_share": 0.30},
            {"domain": "competitor2.com", "impression_share": 0.20},
        ]

        position = csv_service._calculate_market_position(own_domain, competitors)
        assert position == 2  # Should be 2nd place

    def test_empty_auction_insights_file(self, client):
        """Test handling of empty auction insights file."""
        empty_content = "Auction insights report\nCampaign date range\nDisplay URL domain,Impr. share\n"
        file_data = BytesIO(empty_content.encode("utf-8"))

        response = client.post(
            "/api/v1/parse-csv?data_type=auction_insights",
            files={"file": ("empty_auction_insights.csv", file_data, "text/csv")},
        )

        assert response.status_code == 400
        assert "empty" in response.json()["detail"].lower()

    def test_malformed_auction_insights_csv(self, client):
        """Test handling of malformed auction insights CSV."""
        malformed_content = "This is not a proper CSV file\nwith auction insights data"
        file_data = BytesIO(malformed_content.encode("utf-8"))

        response = client.post(
            "/api/v1/analyze-csv?data_type=auction_insights",
            files={"file": ("malformed.csv", file_data, "text/csv")},
        )

        # The API is lenient and tries to parse whatever it can
        # It should return 200 but with analysis showing issues
        assert response.status_code == 200
        data = response.json()

        # Should have limited or no meaningful analysis
        assert data["total_rows"] <= 2  # Only the malformed lines

    def test_auction_insights_analysis_summary_structure(
        self, csv_service, sample_auction_insights_data
    ):
        """Test the structure of auction insights analysis summary."""
        analysis = csv_service._generate_auction_insights_summary(
            sample_auction_insights_data, 0.0, 0, 0.0, [], []
        )

        # Check all required keys are present
        required_keys = [
            "data_type",
            "total_competitors",
            "total_records",
            "market_analysis",
            "position_analysis",
            "competitive_insights",
            "strategic_opportunities",
        ]

        for key in required_keys:
            assert key in analysis

        # Check market analysis structure
        market_keys = [
            "top_competitor",
            "top_competitor_impression_share",
            "total_market_coverage",
            "market_concentration_top3",
        ]

        for key in market_keys:
            assert key in analysis["market_analysis"]

    def test_auction_insights_with_no_own_domain(self, csv_service):
        """Test auction insights analysis when own domain is not identified."""
        competitor_only_data = [
            {
                "Display URL domain": "competitor1.com",
                "Impr. share": "25.5%",
                "Overlap rate": "18.2%",
                "Top of page rate": "45.3%",
                "Abs. Top of page rate": "12.1%",
                "Outranking share": "38.7%",
                "Position above rate": "22.4%",
            },
            {
                "Display URL domain": "competitor2.com",
                "Impr. share": "18.9%",
                "Overlap rate": "15.6%",
                "Top of page rate": "32.8%",
                "Abs. Top of page rate": "8.9%",
                "Outranking share": "29.3%",
                "Position above rate": "18.7%",
            },
        ]

        analysis = csv_service._generate_auction_insights_summary(
            competitor_only_data, 0.0, 0, 0.0, [], []
        )

        assert analysis["total_competitors"] == 2
        assert analysis["own_performance"] is None
