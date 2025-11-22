"""Tests for negative keywords parser API functionality."""

from io import BytesIO

import pytest
from fastapi.testclient import TestClient

from paidsearchnav.api.main import create_app

# Test constants
LARGE_FILE_TEST_MULTIPLIER = 100000  # Sufficient to exceed 100MB limit
LARGE_ROW_CONTENT_SIZE = 1000  # Size of padding content in test rows


class TestNegativeKeywordsParser:
    """Test class for negative keywords parser functionality."""

    @pytest.fixture(scope="session")
    def client(self):
        """Create test client with session scope for better performance."""
        app = create_app()
        return TestClient(app)

    def test_parse_negative_keywords_csv(self, client):
        """Test parsing negative keywords CSV file."""
        csv_content = """Campaign,Ad group,Negative keyword,Match type,Level
Test Campaign,Test Ad Group,free,Exact,Campaign
Test Campaign,Test Ad Group,cheap,Phrase,Ad group
Test Campaign 2,Test Ad Group 2,discount,Broad,Campaign"""

        files = {
            "file": (
                "negative_keywords.csv",
                BytesIO(csv_content.encode("utf-8")),
                "text/csv",
            )
        }
        response = client.post(
            "/api/v1/parse-csv?data_type=negative_keywords", files=files
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["total_records"] == 3
        assert data["data_type"] == "negative_keywords"
        assert "Campaign" in data["columns"]
        assert "Negative keyword" in data["columns"]
        assert "Match type" in data["columns"]

    def test_analyze_negative_keywords_csv(self, client):
        """Test analyzing negative keywords CSV file."""
        csv_content = """Campaign,Ad group,Negative keyword,Match type,Level
Test Campaign,Test Ad Group,free,Exact,Campaign
Test Campaign,Test Ad Group,cheap,Phrase,Ad group
Test Campaign 2,Test Ad Group 2,discount,Broad,Campaign
Test Campaign 3,Test Ad Group 3,sale,Exact,Campaign
Test Campaign 3,Test Ad Group 3,promo,Phrase,Ad group"""

        files = {
            "file": (
                "negative_keywords.csv",
                BytesIO(csv_content.encode("utf-8")),
                "text/csv",
            )
        }
        response = client.post(
            "/api/v1/analyze-csv?data_type=negative_keywords", files=files
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_rows"] == 5
        assert data["analysis_summary"]["data_type"] == "negative_keywords"
        assert data["analysis_summary"]["total_negative_keywords"] == 5
        assert data["analysis_summary"]["campaign_level_negatives"] == 3
        assert data["analysis_summary"]["ad_group_level_negatives"] == 2
        assert data["analysis_summary"]["exact_match_negatives"] == 2
        assert data["analysis_summary"]["phrase_match_negatives"] == 2
        assert data["analysis_summary"]["broad_match_negatives"] == 1

    def test_negative_keywords_with_google_ads_headers(self, client):
        """Test parsing negative keywords with Google Ads export headers."""
        csv_content = """# Negative keyword report
# Downloaded from Google Ads on 2025-07-29
# Account: Test Account

Campaign,Ad group,Negative keyword,Match type,Level
Test Campaign,Test Ad Group,free,Exact,Campaign
Test Campaign,Test Ad Group,cheap,Phrase,Ad group"""

        files = {
            "file": (
                "negative_keywords.csv",
                BytesIO(csv_content.encode("utf-8")),
                "text/csv",
            )
        }
        response = client.post(
            "/api/v1/analyze-csv?data_type=negative_keywords", files=files
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_rows"] == 2
        assert data["analysis_summary"]["total_negative_keywords"] == 2

    def test_negative_keywords_with_fitness_connection_format(self, client):
        """Test parsing negative keywords with fitness connection specific fields."""
        csv_content = """Campaign,Ad group,Negative keyword,Keyword or list,Match type,Level
Test Campaign,Test Ad Group,free,Individual,Exact,Campaign
Test Campaign,Test Ad Group,cheap,List Name,Phrase,Ad group"""

        files = {
            "file": (
                "negative_keywords.csv",
                BytesIO(csv_content.encode("utf-8")),
                "text/csv",
            )
        }
        response = client.post(
            "/api/v1/analyze-csv?data_type=negative_keywords", files=files
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_rows"] == 2
        assert "Keyword or list" in data["columns"]

    def test_negative_keywords_empty_file(self, client):
        """Test error handling for empty negative keywords file."""
        csv_content = ""

        files = {
            "file": ("empty.csv", BytesIO(csv_content.encode("utf-8")), "text/csv")
        }
        response = client.post(
            "/api/v1/analyze-csv?data_type=negative_keywords", files=files
        )

        assert response.status_code == 400
        assert "empty" in response.json()["detail"].lower()

    def test_negative_keywords_invalid_format(self, client):
        """Test error handling for invalid CSV format."""
        csv_content = "This is not a valid CSV file"

        files = {
            "file": ("invalid.csv", BytesIO(csv_content.encode("utf-8")), "text/csv")
        }
        response = client.post(
            "/api/v1/analyze-csv?data_type=negative_keywords", files=files
        )

        assert response.status_code == 400

    def test_negative_keywords_large_file_validation(self, client):
        """Test file size validation for negative keywords."""
        # Create a CSV that's definitely over 100MB
        large_row = (
            "Test Campaign with a very long name that takes up lots of space,"
            + "x" * LARGE_ROW_CONTENT_SIZE
            + ",Exact,Campaign\n"
        )
        large_content = (
            "Campaign,Negative keyword,Match type,Level\n"
            + large_row * LARGE_FILE_TEST_MULTIPLIER
        )

        files = {
            "file": ("large.csv", BytesIO(large_content.encode("utf-8")), "text/csv")
        }
        response = client.post(
            "/api/v1/analyze-csv?data_type=negative_keywords", files=files
        )

        assert response.status_code == 413
        assert "too large" in response.json()["detail"].lower()

    def test_negative_keywords_non_csv_file(self, client):
        """Test rejection of non-CSV files."""
        txt_content = "This is a text file"

        files = {
            "file": ("test.txt", BytesIO(txt_content.encode("utf-8")), "text/plain")
        }
        response = client.post(
            "/api/v1/analyze-csv?data_type=negative_keywords", files=files
        )

        assert response.status_code == 400
        assert "CSV" in response.json()["detail"]

    def test_negative_keywords_sample_data_cleaning(self, client):
        """Test that sample data is properly cleaned and sanitized."""
        csv_content = """Campaign,Ad group,Negative keyword,Match type,Level
Test Campaign,Test Ad Group,=free,Exact,Campaign
Test Campaign,Test Ad Group,+cheap,Phrase,Ad group"""

        files = {
            "file": (
                "negative_keywords.csv",
                BytesIO(csv_content.encode("utf-8")),
                "text/csv",
            )
        }
        response = client.post(
            "/api/v1/analyze-csv?data_type=negative_keywords", files=files
        )

        assert response.status_code == 200
        data = response.json()

        # Check that dangerous formulas are sanitized in sample data
        for sample in data["sample_data"]:
            for value in sample.values():
                # Should not start with dangerous characters after sanitization
                assert not value.startswith("=")
                assert not value.startswith("+")

    def test_negative_keywords_metrics_with_zero_values(self, client):
        """Test that metrics are properly calculated when there are zero values."""
        csv_content = """Campaign,Ad group,Negative keyword,Match type,Level
Test Campaign,Test Ad Group,free,Exact,Campaign"""

        files = {
            "file": (
                "negative_keywords.csv",
                BytesIO(csv_content.encode("utf-8")),
                "text/csv",
            )
        }
        response = client.post(
            "/api/v1/analyze-csv?data_type=negative_keywords", files=files
        )

        assert response.status_code == 200
        data = response.json()

        # Verify analysis doesn't crash with minimal data
        assert data["analysis_summary"]["total_negative_keywords"] == 1
        assert data["analysis_summary"]["exact_match_negatives"] >= 0
        assert data["analysis_summary"]["phrase_match_negatives"] >= 0
        assert data["analysis_summary"]["broad_match_negatives"] >= 0

    def test_negative_keywords_additional_security_vectors(self, client):
        """Test additional security injection vectors like @SUM, -cmd, etc."""
        csv_content = """Campaign,Ad group,Negative keyword,Match type,Level
Test Campaign,Test Ad Group,@SUM(A1:A10),Exact,Campaign
Test Campaign,Test Ad Group,-cmd,Phrase,Ad group
Test Campaign,Test Ad Group,@HYPERLINK,Broad,Campaign
Test Campaign,Test Ad Group,+cmd,Exact,Ad group"""

        files = {
            "file": (
                "negative_keywords.csv",
                BytesIO(csv_content.encode("utf-8")),
                "text/csv",
            )
        }
        response = client.post(
            "/api/v1/analyze-csv?data_type=negative_keywords", files=files
        )

        assert response.status_code == 200
        data = response.json()

        # Check that additional dangerous patterns are sanitized in sample data
        for sample in data["sample_data"]:
            for value in sample.values():
                # Dangerous values should be prefixed with single quote for safety
                if "SUM" in value or "HYPERLINK" in value or "cmd" in value:
                    assert value.startswith("'")
                # Original dangerous characters should not appear at start (without quote)
                if not value.startswith("'"):
                    assert not value.startswith("@")
                    assert not value.startswith("-")
                    assert not value.startswith("+")
                    assert not value.startswith("=")
