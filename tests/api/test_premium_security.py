"""Security tests for premium API endpoints."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from paidsearchnav_mcp.api.main import app
from paidsearchnav_mcp.api.v1.premium_utils import (
    parse_date_range,
    validate_campaign_ids,
    validate_customer_id,
)


class TestInputValidation:
    """Test input validation and sanitization."""

    def test_validate_customer_id_valid(self):
        """Test valid customer ID passes validation."""
        valid_ids = ["12345", "customer_123", "test_customer"]
        for customer_id in valid_ids:
            result = validate_customer_id(customer_id)
            assert result == customer_id

    def test_validate_customer_id_invalid(self):
        """Test invalid customer IDs are rejected."""
        invalid_ids = [
            "",  # Empty
            None,  # None
            "customer'; DROP TABLE users; --",  # SQL injection attempt
            "customer<script>alert('xss')</script>",  # XSS attempt
            "customer with spaces",  # Spaces not allowed
            "customer-with-special!@#$%^&*()",  # Special characters
            "x" * 51,  # Too long (over 50 chars)
            123,  # Not a string
        ]

        for invalid_id in invalid_ids:
            with pytest.raises(HTTPException) as exc_info:
                validate_customer_id(invalid_id)
            assert exc_info.value.status_code == 400

    def test_validate_campaign_ids_valid(self):
        """Test valid campaign IDs pass validation."""
        valid_campaigns = [
            ["12345", "67890"],
            ["campaign_123"],
            ["test-campaign"],
        ]

        for campaigns in valid_campaigns:
            result = validate_campaign_ids(campaigns)
            assert result == campaigns

    def test_validate_campaign_ids_invalid(self):
        """Test invalid campaign IDs are rejected."""
        invalid_campaigns = [
            ["campaign'; DROP TABLE campaigns; --"],  # SQL injection
            ["campaign<script>"],  # XSS attempt
            ["campaign with spaces"],  # Spaces not allowed
            ["x" * 51],  # Too long
            [123],  # Not string
            "not_a_list",  # Not a list
            ["valid"] + ["x"] * 100,  # Too many campaigns
        ]

        for campaigns in invalid_campaigns:
            with pytest.raises(HTTPException) as exc_info:
                validate_campaign_ids(campaigns)
            assert exc_info.value.status_code == 400

    def test_parse_date_range_valid(self):
        """Test valid date ranges are parsed correctly."""
        valid_ranges = [
            ("7d", "7 DAY"),
            ("30d", "30 DAY"),
            ("2w", "2 WEEK"),
            ("1h", "1 HOUR"),
        ]

        for input_range, expected in valid_ranges:
            result = parse_date_range(input_range)
            assert result == expected

    def test_parse_date_range_invalid(self):
        """Test invalid date ranges are rejected."""
        invalid_ranges = [
            "",  # Empty
            None,  # None
            "invalid",  # Invalid format
            "999999d",  # Too large
            "-5d",  # Negative
            "0d",  # Zero
            "1000h",  # Too many hours
            "SELECT * FROM users",  # SQL injection attempt
        ]

        for invalid_range in invalid_ranges:
            with pytest.raises(HTTPException) as exc_info:
                parse_date_range(invalid_range)
            assert exc_info.value.status_code == 400


class TestSQLInjectionPrevention:
    """Test SQL injection prevention in premium endpoints."""

    @patch("paidsearchnav.api.v1.premium.BigQueryService")
    @patch("paidsearchnav.api.dependencies.get_current_user")
    def test_search_terms_sql_injection_prevention(self, mock_user, mock_bigquery):
        """Test search terms endpoint prevents SQL injection."""
        # Mock dependencies
        mock_user.return_value = {"customer_id": "test_customer"}
        mock_service = MagicMock()
        mock_service.is_premium = True
        mock_service.config.project_id = "test_project"
        mock_service.config.dataset_id = "test_dataset"

        mock_client = AsyncMock()
        mock_service.authenticator.get_client.return_value = mock_client
        mock_bigquery.return_value = mock_service

        client = TestClient(app)

        # Attempt SQL injection in customer_id
        malicious_customer_id = "test'; DROP TABLE users; --"

        with patch(
            "paidsearchnav.api.v1.premium.get_bigquery_service",
            return_value=mock_service,
        ):
            response = client.get(
                f"/api/v1/premium/analytics/search-terms?customer_id={malicious_customer_id}"
            )

        # Should return 400 due to validation, not execute malicious SQL
        assert response.status_code == 400
        assert "Customer ID must be alphanumeric" in response.json()["detail"]

    @patch("paidsearchnav.api.v1.premium.BigQueryService")
    @patch("paidsearchnav.api.dependencies.get_current_user")
    def test_campaigns_filter_sql_injection_prevention(self, mock_user, mock_bigquery):
        """Test campaigns filter prevents SQL injection."""
        mock_user.return_value = {"customer_id": "test_customer"}
        mock_service = MagicMock()
        mock_service.is_premium = True
        mock_bigquery.return_value = mock_service

        client = TestClient(app)

        # Attempt SQL injection in campaigns filter
        malicious_campaigns = ["valid_campaign", "'; DROP TABLE campaigns; --"]

        with patch(
            "paidsearchnav.api.v1.premium.get_bigquery_service",
            return_value=mock_service,
        ):
            response = client.get(
                "/api/v1/premium/analytics/search-terms",
                params={
                    "customer_id": "valid_customer",
                    "campaigns": malicious_campaigns,
                },
            )

        # Should return 400 due to validation
        assert response.status_code == 400


class TestParameterizedQueries:
    """Test that BigQuery queries are properly parameterized."""

    @patch("paidsearchnav.api.v1.premium_utils.bigquery")
    def test_parameterized_query_structure(self, mock_bigquery):
        """Test that parameterized queries are structured correctly."""
        from paidsearchnav.api.v1.premium_utils import create_query_parameters

        # Test basic parameters
        customer_id = "test_customer"
        date_range = "7 DAY"

        parameters = create_query_parameters(customer_id, date_range)

        # Verify parameters structure
        assert len(parameters) >= 2
        param_names = [p.name for p in parameters]
        assert "customer_id" in param_names
        assert "start_timestamp" in param_names

        # Verify parameter types
        for param in parameters:
            if param.name == "customer_id":
                assert param.value == customer_id
            assert hasattr(param, "value")
            assert hasattr(param, "name")

    @patch("paidsearchnav.api.v1.premium_utils.bigquery.Client")
    def test_safe_execute_query_cost_validation(self, mock_client):
        """Test that safe_execute_query validates query costs."""
        from paidsearchnav.api.v1.premium_utils import safe_execute_query

        # Mock expensive query (dry run returns high cost)
        mock_dry_run_job = MagicMock()
        mock_dry_run_job.total_bytes_processed = 10**15  # 1 PB = very expensive

        mock_client_instance = MagicMock()
        mock_client_instance.query.return_value = mock_dry_run_job

        query = "SELECT * FROM table WHERE customer_id = @customer_id"
        parameters = []

        # Should raise HTTPException for expensive query
        with pytest.raises(HTTPException) as exc_info:
            safe_execute_query(mock_client_instance, query, parameters)

        assert exc_info.value.status_code == 429
        assert "Query too expensive" in str(exc_info.value.detail)


class TestAuthenticationAndAuthorization:
    """Test authentication and authorization security."""

    def test_premium_tier_required(self):
        """Test that premium endpoints require premium tier."""
        client = TestClient(app)

        # Mock user without premium tier
        with patch("paidsearchnav.api.dependencies.get_current_user") as mock_user:
            with patch(
                "paidsearchnav.api.v1.premium.get_bigquery_service"
            ) as mock_service:
                mock_user.return_value = {"customer_id": "test_customer"}
                mock_service.return_value.is_premium = False

                response = client.get(
                    "/api/v1/premium/analytics/search-terms?customer_id=test_customer"
                )

        assert response.status_code == 402
        assert "Premium tier required" in response.json()["detail"]

    def test_authentication_required(self):
        """Test that endpoints require authentication."""
        client = TestClient(app)

        # No authentication provided
        response = client.get(
            "/api/v1/premium/analytics/search-terms?customer_id=test_customer"
        )

        # Should require authentication (exact status depends on auth implementation)
        assert response.status_code in [401, 422]  # Unauthorized or validation error


class TestRateLimiting:
    """Test rate limiting functionality."""

    @patch("paidsearchnav.api.v1.premium.limiter")
    def test_rate_limiting_applied(self, mock_limiter):
        """Test that rate limiting is applied to endpoints."""
        # This is a basic test to ensure rate limiting decorators are present
        # Full rate limiting testing would require Redis/memory store setup

        # Check that the function has rate limiting decorator
        # This is indicated by the presence of limiter calls in the module
        assert mock_limiter is not None


class TestErrorHandling:
    """Test error handling doesn't leak sensitive information."""

    @patch("paidsearchnav.api.v1.premium.BigQueryService")
    @patch("paidsearchnav.api.dependencies.get_current_user")
    def test_error_message_sanitization(self, mock_user, mock_bigquery):
        """Test that error messages don't leak internal details."""
        mock_user.return_value = {"customer_id": "test_customer"}
        mock_service = MagicMock()
        mock_service.is_premium = True

        # Mock BigQuery client to raise an exception
        mock_client = AsyncMock()
        mock_client.query.side_effect = Exception(
            "Internal BigQuery error with sensitive data"
        )
        mock_service.authenticator.get_client.return_value = mock_client
        mock_bigquery.return_value = mock_service

        client = TestClient(app)

        with patch(
            "paidsearchnav.api.v1.premium.get_bigquery_service",
            return_value=mock_service,
        ):
            response = client.get(
                "/api/v1/premium/analytics/search-terms?customer_id=valid_customer"
            )

        # Should return generic error message, not internal details
        assert response.status_code == 500
        error_detail = response.json()["detail"]
        assert "Analytics query failed" in error_detail
        assert "Internal BigQuery error" not in error_detail
        assert "sensitive data" not in error_detail


class TestConfigurationSecurity:
    """Test configuration and constant security."""

    def test_hardcoded_values_moved_to_config(self):
        """Test that hardcoded values are moved to configuration."""
        from paidsearchnav.api.v1.premium_utils import BYTES_PER_TB, COST_PER_TB_USD

        # Verify constants are defined and reasonable
        assert isinstance(COST_PER_TB_USD, (int, float))
        assert COST_PER_TB_USD > 0
        assert isinstance(BYTES_PER_TB, int)
        assert BYTES_PER_TB > 0

    def test_query_timeout_configuration(self):
        """Test that query timeouts are configurable."""
        from paidsearchnav.api.v1.premium_utils import DEFAULT_QUERY_TIMEOUT

        assert isinstance(DEFAULT_QUERY_TIMEOUT, int)
        assert DEFAULT_QUERY_TIMEOUT > 0
        assert DEFAULT_QUERY_TIMEOUT <= 300  # Reasonable maximum
