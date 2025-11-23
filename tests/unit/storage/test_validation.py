"""Tests for storage validation functions."""

import pytest

from paidsearchnav_mcp.storage.repository import (
    SecurityConfig,
    _detect_sql_injection,
    _validate_customer_id,
    _validate_string_input,
)


class TestSqlInjectionDetection:
    """Test SQL injection detection."""

    def test_detect_sql_injection_with_dangerous_patterns(self):
        """Test detection of actual SQL injection patterns."""
        dangerous_inputs = [
            "; DROP TABLE users; --",
            "'; DELETE FROM accounts WHERE 1=1; --",
            "UNION SELECT username, password FROM users",
            "admin'--",
            "/* comment */ DROP TABLE test",
            "OR '1'='1'",
            "AND 1=1",
            "; INSERT INTO users VALUES ('hacker', 'password')",
            "; ALTER TABLE users ADD COLUMN admin BOOLEAN DEFAULT TRUE",
            "; CREATE TABLE malicious AS SELECT * FROM sensitive_data",
            "; TRUNCATE TABLE important_data",
        ]

        for dangerous_input in dangerous_inputs:
            assert _detect_sql_injection(dangerous_input), (
                f"Should detect SQL injection in: {dangerous_input}"
            )

    def test_detect_sql_injection_safe_inputs(self):
        """Test that safe inputs are not flagged as SQL injection."""
        safe_inputs = [
            "keyword_match_audit",
            "KeywordMatchAnalyzer",
            "SELECT shoes from catalog",  # Business name with SQL keyword
            "My Business & Company",
            "Test-Customer-123",
            "Analysis for Q1 2024",
            "Normal text with punctuation!",
            "Email: user@example.com",
            "Phone: 123-456-7890",
            "Address: 123 Main St, Unit 5",
            "Special chars: !@#$%^&*()",
        ]

        for safe_input in safe_inputs:
            assert not _detect_sql_injection(safe_input), (
                f"Should NOT detect SQL injection in: {safe_input}"
            )

    def test_detect_sql_injection_case_insensitive(self):
        """Test that detection is case insensitive."""
        patterns = [
            "; drop table users",
            "; DROP TABLE users",
            "; Drop Table Users",
            "union select * from users",
            "UNION SELECT * FROM users",
        ]

        for pattern in patterns:
            assert _detect_sql_injection(pattern), (
                f"Should detect case insensitive pattern: {pattern}"
            )


class TestStringInputValidation:
    """Test string input validation."""

    def test_validate_string_input_valid(self):
        """Test validation of valid string inputs."""
        valid_inputs = [
            ("keyword_match_audit", "analysis_type"),
            ("KeywordMatchAnalyzer", "analyzer_name"),
            ("Test Customer 123", "customer_name"),
            ("", "empty_field"),  # Empty string should be allowed
        ]

        for input_value, field_name in valid_inputs:
            result = _validate_string_input(input_value, field_name)
            assert result == input_value.strip()

    def test_validate_string_input_with_custom_length(self):
        """Test validation with custom max length."""
        # Should pass with custom length
        long_string = "a" * 100
        result = _validate_string_input(long_string, "test_field", max_length=150)
        assert result == long_string

        # Should fail with custom length
        with pytest.raises(ValueError, match="cannot exceed 50 characters"):
            _validate_string_input(long_string, "test_field", max_length=50)

    def test_validate_string_input_default_length(self):
        """Test validation with default max length."""
        # Should pass with default length
        normal_string = "a" * 200
        result = _validate_string_input(normal_string, "test_field")
        assert result == normal_string

        # Should fail with default length
        too_long_string = "a" * (SecurityConfig.MAX_STRING_LENGTH + 1)
        with pytest.raises(
            ValueError,
            match=f"cannot exceed {SecurityConfig.MAX_STRING_LENGTH} characters",
        ):
            _validate_string_input(too_long_string, "test_field")

    def test_validate_string_input_non_string(self):
        """Test validation rejects non-string inputs."""
        invalid_inputs = [123, [], {}, None, True]

        for invalid_input in invalid_inputs:
            with pytest.raises(ValueError, match="must be a string"):
                _validate_string_input(invalid_input, "test_field")

    def test_validate_string_input_sql_injection(self):
        """Test validation detects SQL injection."""
        malicious_inputs = [
            "; DROP TABLE users",
            "'; DELETE FROM accounts; --",
            "UNION SELECT * FROM passwords",
            "admin'--",
        ]

        for malicious_input in malicious_inputs:
            with pytest.raises(ValueError, match="potentially malicious SQL patterns"):
                _validate_string_input(malicious_input, "test_field")

    def test_validate_string_input_strips_whitespace(self):
        """Test that validation strips leading/trailing whitespace."""
        input_with_whitespace = "  keyword_match_audit  "
        result = _validate_string_input(input_with_whitespace, "analysis_type")
        assert result == "keyword_match_audit"


class TestCustomerIdValidation:
    """Test customer ID validation."""

    def test_validate_customer_id_valid_formats(self):
        """Test validation of valid customer ID formats."""
        valid_customer_ids = [
            "1234567890",  # 10 digits
            "123-456-7890",  # 10 digits with hyphens
            "12345678",  # 8 digits
            "123456789012",  # 12 digits
            "123-456-789",  # 9 digits with hyphens
        ]

        for customer_id in valid_customer_ids:
            result = _validate_customer_id(customer_id)
            # Should return digits only, no hyphens
            assert result.isdigit()
            assert "-" not in result
            assert len(result) >= SecurityConfig.MIN_CUSTOMER_ID_LENGTH
            assert len(result) <= SecurityConfig.MAX_CUSTOMER_ID_LENGTH

    def test_validate_customer_id_removes_hyphens(self):
        """Test that validation removes hyphens."""
        customer_id_with_hyphens = "123-456-7890"
        result = _validate_customer_id(customer_id_with_hyphens)
        assert result == "1234567890"

    def test_validate_customer_id_invalid_formats(self):
        """Test validation rejects invalid customer ID formats."""
        invalid_customer_ids = [
            "",  # Empty string
            "   ",  # Whitespace only
            None,  # None value
            "abc123def",  # Contains letters
            "123-abc-456",  # Contains letters with hyphens
            "123.456.789",  # Contains dots
            "123 456 789",  # Contains spaces
            "1234567",  # Too short (7 digits)
            "12345678901234",  # Too long (14 digits)
        ]

        for invalid_customer_id in invalid_customer_ids:
            with pytest.raises(ValueError):
                _validate_customer_id(invalid_customer_id)

    def test_validate_customer_id_length_validation(self):
        """Test customer ID length validation bounds."""
        # Test minimum length boundary
        min_length_id = "1" * SecurityConfig.MIN_CUSTOMER_ID_LENGTH
        result = _validate_customer_id(min_length_id)
        assert result == min_length_id

        # Test maximum length boundary
        max_length_id = "1" * SecurityConfig.MAX_CUSTOMER_ID_LENGTH
        result = _validate_customer_id(max_length_id)
        assert result == max_length_id

        # Test below minimum
        too_short_id = "1" * (SecurityConfig.MIN_CUSTOMER_ID_LENGTH - 1)
        with pytest.raises(
            ValueError, match=f"must be between {SecurityConfig.MIN_CUSTOMER_ID_LENGTH}"
        ):
            _validate_customer_id(too_short_id)

        # Test above maximum
        too_long_id = "1" * (SecurityConfig.MAX_CUSTOMER_ID_LENGTH + 1)
        with pytest.raises(
            ValueError, match=f"and {SecurityConfig.MAX_CUSTOMER_ID_LENGTH} digits"
        ):
            _validate_customer_id(too_long_id)

    def test_validate_customer_id_strips_whitespace(self):
        """Test that validation strips whitespace."""
        customer_id_with_whitespace = "  123-456-7890  "
        result = _validate_customer_id(customer_id_with_whitespace)
        assert result == "1234567890"


class TestSecurityConfig:
    """Test security configuration constants."""

    def test_security_config_constants(self):
        """Test that security config constants are properly defined."""
        assert SecurityConfig.MAX_STRING_LENGTH > 0
        assert SecurityConfig.MAX_ANALYSIS_TYPE_LENGTH > 0
        assert SecurityConfig.MAX_ANALYZER_NAME_LENGTH > 0
        assert SecurityConfig.MIN_CUSTOMER_ID_LENGTH > 0
        assert (
            SecurityConfig.MAX_CUSTOMER_ID_LENGTH
            > SecurityConfig.MIN_CUSTOMER_ID_LENGTH
        )
        assert SecurityConfig.MAX_QUERY_LIMIT > 0
        assert len(SecurityConfig.SQL_INJECTION_PATTERNS) > 0

    def test_sql_injection_patterns_are_valid_regex(self):
        """Test that all SQL injection patterns are valid regex."""
        import re

        for pattern in SecurityConfig.SQL_INJECTION_PATTERNS:
            try:
                re.compile(pattern)
            except re.error:
                pytest.fail(f"Invalid regex pattern: {pattern}")


class TestIntegrationScenarios:
    """Test integration scenarios combining multiple validation functions."""

    def test_realistic_analysis_data(self):
        """Test validation with realistic analysis data."""
        # Valid data that should pass
        valid_data = {
            "customer_id": "123-456-7890",
            "analysis_type": "keyword_match_audit",
            "analyzer_name": "KeywordMatchAnalyzer",
        }

        # All should pass validation
        validated_customer_id = _validate_customer_id(valid_data["customer_id"])
        validated_analysis_type = _validate_string_input(
            valid_data["analysis_type"],
            "analysis_type",
            SecurityConfig.MAX_ANALYSIS_TYPE_LENGTH,
        )
        validated_analyzer_name = _validate_string_input(
            valid_data["analyzer_name"],
            "analyzer_name",
            SecurityConfig.MAX_ANALYZER_NAME_LENGTH,
        )

        assert validated_customer_id == "1234567890"
        assert validated_analysis_type == "keyword_match_audit"
        assert validated_analyzer_name == "KeywordMatchAnalyzer"

    def test_malicious_analysis_data(self):
        """Test validation blocks malicious analysis data."""
        malicious_data = {
            "customer_id": "'; DROP TABLE users; --",
            "analysis_type": "UNION SELECT * FROM passwords",
            "analyzer_name": "; DELETE FROM accounts WHERE 1=1",
        }

        # All should fail validation
        with pytest.raises(ValueError):
            _validate_customer_id(malicious_data["customer_id"])

        with pytest.raises(ValueError):
            _validate_string_input(
                malicious_data["analysis_type"],
                "analysis_type",
                SecurityConfig.MAX_ANALYSIS_TYPE_LENGTH,
            )

        with pytest.raises(ValueError):
            _validate_string_input(
                malicious_data["analyzer_name"],
                "analyzer_name",
                SecurityConfig.MAX_ANALYZER_NAME_LENGTH,
            )
