"""Tests for CSV validation API endpoints."""

import io
from unittest.mock import patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from paidsearchnav_mcp.api.main import create_app


@pytest.fixture
def client():
    """Create test client."""
    app = create_app()
    return TestClient(app)


@pytest.fixture
def mock_user():
    """Mock authenticated user."""
    return {"sub": "test_user", "email": "test@example.com"}


@pytest.fixture
def valid_search_terms_csv():
    """Valid search terms CSV content."""
    return """Search term,Keyword,Campaign,Ad group,Impressions,Clicks,Cost
tennis shoes,tennis shoes,Sports Campaign,Tennis Ads,1000,50,25.50
running shoes,running shoes,Sports Campaign,Running Ads,800,40,20.00
basketball shoes,basketball shoes,Sports Campaign,Basketball Ads,600,30,15.00"""


@pytest.fixture
def valid_keywords_csv():
    """Valid keywords CSV content."""
    return """Keyword,Match type,Ad group,Campaign,Status,Max. CPC,Quality Score
tennis shoes,Exact,Tennis Ads,Sports Campaign,Enabled,1.50,8
running shoes,Phrase,Running Ads,Sports Campaign,Enabled,1.25,7
basketball shoes,Broad,Basketball Ads,Sports Campaign,Enabled,1.00,6"""


@pytest.fixture
def invalid_csv():
    """Invalid CSV content with issues."""
    return """Search term,Campaign
"tennis shoes,Sports Campaign
=SUM(A1:A10),Malicious Campaign"""


@pytest.fixture
def empty_csv():
    """Empty CSV content."""
    return ""


class TestCSVValidationEndpoint:
    """Test cases for /api/v1/csv/validate endpoint."""

    @patch("paidsearchnav.api.dependencies.get_current_user")
    def test_validate_csv_success_search_terms(
        self, mock_get_user, client, mock_user, valid_search_terms_csv
    ):
        """Test successful validation of search terms CSV."""
        mock_get_user.return_value = mock_user

        files = {
            "file": (
                "test_search_terms.csv",
                io.StringIO(valid_search_terms_csv),
                "text/csv",
            )
        }
        params = {
            "expected_format": "search_terms",
            "include_preview": True,
            "preview_rows": 2,
        }

        response = client.post("/api/v1/csv/validate", files=files, params=params)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["is_valid"] is True
        assert data["detected_format"] == "search_terms"
        assert data["has_headers"] is True
        assert data["estimated_rows"] == 3
        assert data["detected_encoding"] in ["utf-8", "utf-8-sig"]
        assert data["detected_delimiter"] == ","
        assert len(data["issues"]) == 0
        assert data["preview"] is not None
        assert len(data["preview"]["headers"]) > 0
        assert len(data["preview"]["sample_rows"]) <= 2

    @patch("paidsearchnav.api.dependencies.get_current_user")
    def test_validate_csv_success_keywords(
        self, mock_get_user, client, mock_user, valid_keywords_csv
    ):
        """Test successful validation of keywords CSV."""
        mock_get_user.return_value = mock_user

        files = {
            "file": ("test_keywords.csv", io.StringIO(valid_keywords_csv), "text/csv")
        }
        params = {"expected_format": "keywords", "include_preview": True}

        response = client.post("/api/v1/csv/validate", files=files, params=params)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["is_valid"] is True
        assert data["detected_format"] == "keywords"
        assert data["has_headers"] is True
        assert data["estimated_rows"] == 3

    @patch("paidsearchnav.api.dependencies.get_current_user")
    def test_validate_csv_invalid_format(
        self, mock_get_user, client, mock_user, invalid_csv
    ):
        """Test validation of CSV with format issues."""
        mock_get_user.return_value = mock_user

        files = {"file": ("test_invalid.csv", io.StringIO(invalid_csv), "text/csv")}

        response = client.post("/api/v1/csv/validate", files=files)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["is_valid"] is False
        assert len(data["issues"]) > 0
        assert len(data["suggestions"]) > 0

        # Check for expected issues
        issue_messages = [issue["message"] for issue in data["issues"]]
        assert any("quote" in issue.lower() for issue in issue_messages)
        assert any("formula" in issue.lower() for issue in issue_messages)

    @patch("paidsearchnav.api.dependencies.get_current_user")
    def test_validate_csv_empty_file(self, mock_get_user, client, mock_user, empty_csv):
        """Test validation of empty CSV file."""
        mock_get_user.return_value = mock_user

        files = {"file": ("test_empty.csv", io.StringIO(empty_csv), "text/csv")}

        response = client.post("/api/v1/csv/validate", files=files)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "empty" in response.json()["detail"].lower()

    @patch("paidsearchnav.api.dependencies.get_current_user")
    def test_validate_csv_wrong_extension(
        self, mock_get_user, client, mock_user, valid_search_terms_csv
    ):
        """Test validation with wrong file extension."""
        mock_get_user.return_value = mock_user

        files = {
            "file": ("test.txt", io.StringIO(valid_search_terms_csv), "text/plain")
        }

        response = client.post("/api/v1/csv/validate", files=files)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "csv extension" in response.json()["detail"].lower()

    @patch("paidsearchnav.api.dependencies.get_current_user")
    def test_validate_csv_no_preview(
        self, mock_get_user, client, mock_user, valid_search_terms_csv
    ):
        """Test validation without preview."""
        mock_get_user.return_value = mock_user

        files = {
            "file": (
                "test_search_terms.csv",
                io.StringIO(valid_search_terms_csv),
                "text/csv",
            )
        }
        params = {"include_preview": False}

        response = client.post("/api/v1/csv/validate", files=files, params=params)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["is_valid"] is True
        assert data["preview"] is None

    @patch("paidsearchnav.api.dependencies.get_current_user")
    def test_validate_csv_large_file(self, mock_get_user, client, mock_user):
        """Test validation of file exceeding size limit."""
        mock_get_user.return_value = mock_user

        # Create content larger than 100MB
        large_content = "a,b,c\n" * (100 * 1024 * 1024 // 6 + 1)

        files = {"file": ("large_file.csv", io.StringIO(large_content), "text/csv")}

        response = client.post("/api/v1/csv/validate", files=files)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "exceeds maximum" in response.json()["detail"].lower()

    def test_validate_csv_unauthorized(self, client, valid_search_terms_csv):
        """Test validation without authentication."""
        files = {
            "file": (
                "test_search_terms.csv",
                io.StringIO(valid_search_terms_csv),
                "text/csv",
            )
        }

        response = client.post("/api/v1/csv/validate", files=files)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestCSVHealthCheckEndpoint:
    """Test cases for /api/v1/csv/health-check endpoint."""

    @patch("paidsearchnav.api.dependencies.get_current_user")
    def test_health_check_excellent(
        self, mock_get_user, client, mock_user, valid_search_terms_csv
    ):
        """Test health check for excellent quality CSV."""
        mock_get_user.return_value = mock_user

        files = {
            "file": (
                "test_search_terms.csv",
                io.StringIO(valid_search_terms_csv),
                "text/csv",
            )
        }

        response = client.post("/api/v1/csv/health-check", files=files)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["file_name"] == "test_search_terms.csv"
        assert data["health_score"] >= 0.8  # High score for valid CSV
        assert data["status"] in ["excellent", "good"]
        assert "compatibility" in data
        assert isinstance(data["compatibility"], dict)
        assert len(data["recommendations"]) > 0

    @patch("paidsearchnav.api.dependencies.get_current_user")
    def test_health_check_poor(self, mock_get_user, client, mock_user, invalid_csv):
        """Test health check for poor quality CSV."""
        mock_get_user.return_value = mock_user

        files = {"file": ("test_invalid.csv", io.StringIO(invalid_csv), "text/csv")}

        response = client.post("/api/v1/csv/health-check", files=files)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["health_score"] < 0.7  # Low score for invalid CSV
        assert data["status"] in ["poor", "fair"]
        assert len(data["recommendations"]) > 0

    @patch("paidsearchnav.api.dependencies.get_current_user")
    def test_health_check_target_analyzer(
        self, mock_get_user, client, mock_user, valid_keywords_csv
    ):
        """Test health check with target analyzer specified."""
        mock_get_user.return_value = mock_user

        files = {
            "file": ("test_keywords.csv", io.StringIO(valid_keywords_csv), "text/csv")
        }
        params = {"target_analyzer": "keywords"}

        response = client.post("/api/v1/csv/health-check", files=files, params=params)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "keywords" in data["compatibility"]
        assert data["compatibility"]["keywords"] is True

    @patch("paidsearchnav.api.dependencies.get_current_user")
    def test_health_check_wrong_extension(
        self, mock_get_user, client, mock_user, valid_search_terms_csv
    ):
        """Test health check with wrong file extension."""
        mock_get_user.return_value = mock_user

        files = {
            "file": ("test.txt", io.StringIO(valid_search_terms_csv), "text/plain")
        }

        response = client.post("/api/v1/csv/health-check", files=files)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "csv extension" in response.json()["detail"].lower()

    @patch("paidsearchnav.api.dependencies.get_current_user")
    def test_health_check_empty_file(self, mock_get_user, client, mock_user, empty_csv):
        """Test health check for empty file."""
        mock_get_user.return_value = mock_user

        files = {"file": ("test_empty.csv", io.StringIO(empty_csv), "text/csv")}

        response = client.post("/api/v1/csv/health-check", files=files)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "empty" in response.json()["detail"].lower()

    def test_health_check_unauthorized(self, client, valid_search_terms_csv):
        """Test health check without authentication."""
        files = {
            "file": (
                "test_search_terms.csv",
                io.StringIO(valid_search_terms_csv),
                "text/csv",
            )
        }

        response = client.post("/api/v1/csv/health-check", files=files)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


class TestValidationResponseModels:
    """Test validation response model structure."""

    @patch("paidsearchnav.api.dependencies.get_current_user")
    def test_validation_response_structure(
        self, mock_get_user, client, mock_user, valid_search_terms_csv
    ):
        """Test that validation response has correct structure."""
        mock_get_user.return_value = mock_user

        files = {"file": ("test.csv", io.StringIO(valid_search_terms_csv), "text/csv")}

        response = client.post("/api/v1/csv/validate", files=files)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Check required fields
        required_fields = [
            "validation_id",
            "is_valid",
            "detected_format",
            "detected_encoding",
            "detected_delimiter",
            "has_headers",
            "estimated_rows",
            "file_size_mb",
            "issues",
            "suggestions",
            "processing_time_ms",
        ]

        for field in required_fields:
            assert field in data

        # Check types
        assert isinstance(data["validation_id"], str)
        assert isinstance(data["is_valid"], bool)
        assert isinstance(data["detected_format"], str)
        assert isinstance(data["has_headers"], bool)
        assert isinstance(data["estimated_rows"], int)
        assert isinstance(data["file_size_mb"], (int, float))
        assert isinstance(data["issues"], list)
        assert isinstance(data["suggestions"], list)
        assert isinstance(data["processing_time_ms"], int)

    @patch("paidsearchnav.api.dependencies.get_current_user")
    def test_health_check_response_structure(
        self, mock_get_user, client, mock_user, valid_search_terms_csv
    ):
        """Test that health check response has correct structure."""
        mock_get_user.return_value = mock_user

        files = {"file": ("test.csv", io.StringIO(valid_search_terms_csv), "text/csv")}

        response = client.post("/api/v1/csv/health-check", files=files)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Check required fields
        required_fields = [
            "file_name",
            "health_score",
            "status",
            "summary",
            "compatibility",
            "recommendations",
        ]

        for field in required_fields:
            assert field in data

        # Check types
        assert isinstance(data["file_name"], str)
        assert isinstance(data["health_score"], (int, float))
        assert 0.0 <= data["health_score"] <= 1.0
        assert isinstance(data["status"], str)
        assert data["status"] in ["excellent", "good", "fair", "poor"]
        assert isinstance(data["summary"], str)
        assert isinstance(data["compatibility"], dict)
        assert isinstance(data["recommendations"], list)

    @patch("paidsearchnav.api.dependencies.get_current_user")
    def test_validation_issue_structure(
        self, mock_get_user, client, mock_user, invalid_csv
    ):
        """Test that validation issues have correct structure."""
        mock_get_user.return_value = mock_user

        files = {"file": ("test_invalid.csv", io.StringIO(invalid_csv), "text/csv")}

        response = client.post("/api/v1/csv/validate", files=files)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        if data["issues"]:
            issue = data["issues"][0]

            required_fields = ["type", "message", "severity"]
            for field in required_fields:
                assert field in issue

            assert isinstance(issue["type"], str)
            assert isinstance(issue["message"], str)
            assert isinstance(issue["severity"], str)
            assert issue["severity"] in ["critical", "high", "medium", "low"]

    @patch("paidsearchnav.api.dependencies.get_current_user")
    def test_validation_suggestion_structure(
        self, mock_get_user, client, mock_user, invalid_csv
    ):
        """Test that validation suggestions have correct structure."""
        mock_get_user.return_value = mock_user

        files = {"file": ("test_invalid.csv", io.StringIO(invalid_csv), "text/csv")}

        response = client.post("/api/v1/csv/validate", files=files)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        if data["suggestions"]:
            suggestion = data["suggestions"][0]

            required_fields = ["category", "action", "description", "priority"]
            for field in required_fields:
                assert field in suggestion

            assert isinstance(suggestion["category"], str)
            assert isinstance(suggestion["action"], str)
            assert isinstance(suggestion["description"], str)
            assert isinstance(suggestion["priority"], str)
            assert suggestion["priority"] in ["high", "medium", "low"]

    @patch("paidsearchnav.api.dependencies.get_current_user")
    def test_preview_structure(
        self, mock_get_user, client, mock_user, valid_search_terms_csv
    ):
        """Test that preview data has correct structure."""
        mock_get_user.return_value = mock_user

        files = {"file": ("test.csv", io.StringIO(valid_search_terms_csv), "text/csv")}
        params = {"include_preview": True, "preview_rows": 2}

        response = client.post("/api/v1/csv/validate", files=files, params=params)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        if data["preview"]:
            preview = data["preview"]

            required_fields = [
                "headers",
                "sample_rows",
                "total_columns",
                "estimated_rows",
                "file_size_mb",
            ]
            for field in required_fields:
                assert field in preview

            assert isinstance(preview["headers"], list)
            assert isinstance(preview["sample_rows"], list)
            assert isinstance(preview["total_columns"], int)
            assert isinstance(preview["estimated_rows"], int)
            assert isinstance(preview["file_size_mb"], (int, float))

            # Check that sample rows are limited
            assert len(preview["sample_rows"]) <= 2

            # Check sample row structure
            if preview["sample_rows"]:
                sample_row = preview["sample_rows"][0]
                assert isinstance(sample_row, dict)
                assert len(sample_row) == preview["total_columns"]


class TestCSVValidationEdgeCases:
    """Test edge cases and error scenarios."""

    @patch("paidsearchnav.api.dependencies.get_current_user")
    def test_validate_csv_unicode_error(self, mock_get_user, client, mock_user):
        """Test validation with unicode encoding errors."""
        mock_get_user.return_value = mock_user

        # Create content with problematic bytes
        problematic_content = b"Search term,Campaign\n\xff\xfe\x00Invalid,Test Campaign"

        files = {
            "file": ("test_unicode.csv", io.BytesIO(problematic_content), "text/csv")
        }

        response = client.post("/api/v1/csv/validate", files=files)

        # Should handle unicode errors gracefully
        assert response.status_code in [400, 500]  # Either bad request or server error
        if response.status_code == 400:
            assert "encoding" in response.json()["detail"].lower()

    @patch("paidsearchnav.api.dependencies.get_current_user")
    def test_health_check_unicode_error(self, mock_get_user, client, mock_user):
        """Test health check with unicode encoding errors."""
        mock_get_user.return_value = mock_user

        # Create content with problematic bytes
        problematic_content = b"Search term,Campaign\n\xff\xfe\x00Invalid,Test Campaign"

        files = {
            "file": ("test_unicode.csv", io.BytesIO(problematic_content), "text/csv")
        }

        response = client.post("/api/v1/csv/health-check", files=files)

        # Should handle unicode errors gracefully
        assert response.status_code in [400, 500]
        if response.status_code == 400:
            assert "encoding" in response.json()["detail"].lower()

    @patch("paidsearchnav.api.dependencies.get_current_user")
    def test_validate_csv_file_permission_error(self, mock_get_user, client, mock_user):
        """Test validation when file operations fail."""
        mock_get_user.return_value = mock_user

        # This test simulates OS errors that might occur during file operations
        valid_content = "Search term,Keyword,Campaign\ntest,test,test"

        with patch(
            "tempfile.NamedTemporaryFile", side_effect=OSError("Permission denied")
        ):
            files = {"file": ("test.csv", io.StringIO(valid_content), "text/csv")}
            response = client.post("/api/v1/csv/validate", files=files)

            # Should handle OS errors gracefully
            assert response.status_code == 400
            assert "unable to read" in response.json()["detail"].lower()

    @patch("paidsearchnav.api.dependencies.get_current_user")
    def test_validate_csv_with_cached_content(
        self, mock_get_user, client, mock_user, valid_search_terms_csv
    ):
        """Test that multiple validations use cached content efficiently."""
        mock_get_user.return_value = mock_user

        files = {
            "file": (
                "test_search_terms.csv",
                io.StringIO(valid_search_terms_csv),
                "text/csv",
            )
        }

        # Make multiple requests to test caching
        response1 = client.post("/api/v1/csv/validate", files=files)

        # Reset file pointer and make another request
        files["file"] = (
            "test_search_terms.csv",
            io.StringIO(valid_search_terms_csv),
            "text/csv",
        )
        response2 = client.post("/api/v1/csv/validate", files=files)

        assert response1.status_code == status.HTTP_200_OK
        assert response2.status_code == status.HTTP_200_OK

        # Both should have similar results
        data1 = response1.json()
        data2 = response2.json()
        assert data1["detected_format"] == data2["detected_format"]
        assert data1["is_valid"] == data2["is_valid"]

    @patch("paidsearchnav.api.dependencies.get_current_user")
    def test_health_check_configurable_thresholds(
        self, mock_get_user, client, mock_user, valid_search_terms_csv
    ):
        """Test that health check uses configurable thresholds."""
        mock_get_user.return_value = mock_user

        files = {
            "file": (
                "test_search_terms.csv",
                io.StringIO(valid_search_terms_csv),
                "text/csv",
            )
        }

        response = client.post("/api/v1/csv/health-check", files=files)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verify status corresponds to score and thresholds
        score = data["health_score"]
        status_value = data["status"]

        if score >= 0.9:
            assert status_value == "excellent"
        elif score >= 0.7:
            assert status_value == "good"
        elif score >= 0.5:
            assert status_value == "fair"
        else:
            assert status_value == "poor"

    @patch("paidsearchnav.api.dependencies.get_current_user")
    def test_validate_csv_file_size_with_config(self, mock_get_user, client, mock_user):
        """Test file size validation uses configuration."""
        mock_get_user.return_value = mock_user

        # Test with content at the boundary of the configured limit
        from paidsearchnav.api.v1.csv_validation import VALIDATION_CONFIG

        # Create content that's just under the limit
        safe_size = VALIDATION_CONFIG.max_file_size - 1000
        large_content = "a,b,c\n" * (safe_size // 6)

        files = {"file": ("large_file.csv", io.StringIO(large_content), "text/csv")}

        response = client.post("/api/v1/csv/validate", files=files)

        # Should succeed since it's under the limit
        assert response.status_code == status.HTTP_200_OK
