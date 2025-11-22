"""Tests for shared validation utilities."""

import pytest

# Import the validation functions directly
from paidsearchnav_mcp.core.request_validation import (
    validate_email_address,
    validate_google_ads_customer_id,
    validate_user_type,
)


class TestEmailValidation:
    """Test email address validation."""

    def test_valid_email_addresses(self):
        """Test valid email addresses."""
        valid_emails = [
            "test@example.com",
            "user.name@domain.org",
            "user+tag@example.co.uk",
            "123@example.com",
            "test@sub.domain.com",
        ]

        for email in valid_emails:
            result = validate_email_address(email)
            assert isinstance(result, str)
            assert "@" in result
            assert "." in result

    def test_email_normalization(self):
        """Test email address normalization."""
        test_cases = [
            ("TEST@EXAMPLE.COM", "test@example.com"),
            ("User@Domain.ORG", "user@domain.org"),
            ("  spaces@example.com  ", "spaces@example.com"),
        ]

        for input_email, expected in test_cases:
            result = validate_email_address(input_email)
            assert result == expected

    def test_invalid_email_addresses(self):
        """Test invalid email addresses."""
        invalid_emails = [
            "not-an-email",
            "@example.com",
            "test@",
            "test..test@example.com",
            "test@.com",
            "",
            "test@example.",
            "test space@example.com",
        ]

        for email in invalid_emails:
            with pytest.raises(ValueError, match="Invalid email address"):
                validate_email_address(email)


class TestGoogleAdsCustomerIdValidation:
    """Test Google Ads Customer ID validation."""

    def test_valid_google_ads_ids(self):
        """Test valid Google Ads Customer IDs."""
        valid_ids = [
            "1234567890",
            "123-456-7890",
            "123 456 7890",
            "0000000001",
            "9999999999",
        ]

        for customer_id in valid_ids:
            result = validate_google_ads_customer_id(customer_id)
            assert result == customer_id.replace("-", "").replace(" ", "")
            assert len(result) == 10
            assert result.isdigit()

    def test_google_ads_id_normalization(self):
        """Test Google Ads Customer ID normalization."""
        test_cases = [
            ("123-456-7890", "1234567890"),
            ("123 456 7890", "1234567890"),
            ("123-456 7890", "1234567890"),
            ("  1234567890  ", "1234567890"),
        ]

        for input_id, expected in test_cases:
            result = validate_google_ads_customer_id(input_id)
            assert result == expected

    def test_invalid_google_ads_ids(self):
        """Test invalid Google Ads Customer IDs."""
        invalid_ids = [
            "123456789",  # Too short
            "12345678901",  # Too long
            "123456789a",  # Contains letter
            "123-456-789",  # Too short even with formatting
            "",  # Empty
            "abcdefghij",  # All letters
            "123-456-789",  # Too short (9 digits)
        ]

        for customer_id in invalid_ids:
            with pytest.raises(ValueError, match="must be 10 digits"):
                validate_google_ads_customer_id(customer_id)


class TestUserTypeValidation:
    """Test user type validation."""

    def test_valid_user_types(self):
        """Test valid user types."""
        valid_types = [
            "individual",
            "agency",
            "INDIVIDUAL",
            "AGENCY",
            "Individual",
            "Agency",
            "  individual  ",
            "  AGENCY  ",
        ]

        for user_type in valid_types:
            result = validate_user_type(user_type)
            assert result in ["individual", "agency"]
            assert result == user_type.lower().strip()

    def test_user_type_normalization(self):
        """Test user type normalization."""
        test_cases = [
            ("INDIVIDUAL", "individual"),
            ("Agency", "agency"),
            ("  individual  ", "individual"),
            ("  AGENCY  ", "agency"),
        ]

        for input_type, expected in test_cases:
            result = validate_user_type(input_type)
            assert result == expected

    def test_invalid_user_types(self):
        """Test invalid user types."""
        invalid_types = [
            "admin",
            "user",
            "customer",
            "business",
            "",
            "invalid",
            "123",
        ]

        for user_type in invalid_types:
            with pytest.raises(ValueError, match="User type must be one of"):
                validate_user_type(user_type)


class TestValidationIntegration:
    """Test integration scenarios with validation utilities."""

    def test_validation_error_messages(self):
        """Test that validation error messages are helpful."""
        # Test email validation error message
        with pytest.raises(ValueError) as exc_info:
            validate_email_address("invalid-email")
        assert "Invalid email address" in str(exc_info.value)

        # Test Google Ads ID validation error message
        with pytest.raises(ValueError) as exc_info:
            validate_google_ads_customer_id("123")
        assert "10 digits" in str(exc_info.value)

        # Test user type validation error message
        with pytest.raises(ValueError) as exc_info:
            validate_user_type("invalid")
        assert "individual" in str(exc_info.value)
        assert "agency" in str(exc_info.value)

    def test_validation_with_none_values(self):
        """Test validation behavior with None values."""
        # These should handle None gracefully in the Pydantic validators
        # but the raw functions should not accept None

        with pytest.raises((TypeError, AttributeError)):
            validate_email_address(None)

        with pytest.raises((TypeError, AttributeError)):
            validate_google_ads_customer_id(None)

        with pytest.raises((TypeError, AttributeError)):
            validate_user_type(None)

    def test_validation_with_empty_strings(self):
        """Test validation behavior with empty strings."""
        with pytest.raises(ValueError):
            validate_email_address("")

        with pytest.raises(ValueError):
            validate_google_ads_customer_id("")

        with pytest.raises(ValueError):
            validate_user_type("")

    def test_validation_edge_cases(self):
        """Test validation edge cases."""
        # Test very long strings
        long_string = "a" * 1000

        with pytest.raises(ValueError):
            validate_email_address(long_string)

        with pytest.raises(ValueError):
            validate_google_ads_customer_id(long_string)

        with pytest.raises(ValueError):
            validate_user_type(long_string)

        # Test strings with special characters
        special_chars = "!@#$%^&*()"

        with pytest.raises(ValueError):
            validate_google_ads_customer_id(special_chars)

        with pytest.raises(ValueError):
            validate_user_type(special_chars)
