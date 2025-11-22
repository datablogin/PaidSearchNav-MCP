"""Tests for Google Ads input validation utilities."""

import pytest

from paidsearchnav.core.models.campaign import CampaignType
from paidsearchnav.platforms.google.validation import GoogleAdsInputValidator


class TestCampaignTypeValidation:
    """Test campaign type validation."""

    def test_valid_campaign_types(self) -> None:
        """Test validation of valid campaign types."""
        valid_types = ["SEARCH", "DISPLAY", "SHOPPING", "VIDEO", "PERFORMANCE_MAX"]
        result = GoogleAdsInputValidator.validate_campaign_types(valid_types)

        assert len(result) == 5
        assert all(t in result for t in valid_types)

    def test_case_normalization(self) -> None:
        """Test that campaign types are normalized to uppercase."""
        mixed_case_types = ["search", "Display", "SHOPPING", "video", "Performance_Max"]
        result = GoogleAdsInputValidator.validate_campaign_types(mixed_case_types)

        expected = ["SEARCH", "DISPLAY", "SHOPPING", "VIDEO", "PERFORMANCE_MAX"]
        assert result == expected

    def test_whitespace_handling(self) -> None:
        """Test that whitespace is stripped from campaign types."""
        types_with_spaces = ["  SEARCH  ", "DISPLAY\n", "\tSHOPPING"]
        result = GoogleAdsInputValidator.validate_campaign_types(types_with_spaces)

        assert result == ["SEARCH", "DISPLAY", "SHOPPING"]

    def test_empty_list(self) -> None:
        """Test that empty list returns empty list."""
        result = GoogleAdsInputValidator.validate_campaign_types([])
        assert result == []

    def test_invalid_campaign_types(self) -> None:
        """Test that invalid campaign types raise ValueError."""
        invalid_types = ["SEARCH", "INVALID_TYPE", "FAKE_CAMPAIGN"]

        with pytest.raises(ValueError) as exc_info:
            GoogleAdsInputValidator.validate_campaign_types(invalid_types)

        # Test error structure and content
        error = exc_info.value
        assert hasattr(error, "args")
        assert len(error.args) > 0
        error_msg = str(error)
        # Verify key information is present
        assert "INVALID_TYPE" in error_msg
        assert "FAKE_CAMPAIGN" in error_msg

    def test_non_string_types(self) -> None:
        """Test handling of non-string campaign types."""
        mixed_types = ["SEARCH", 123, None, "DISPLAY"]

        with pytest.raises(ValueError) as exc_info:
            GoogleAdsInputValidator.validate_campaign_types(mixed_types)

        error_msg = str(exc_info.value)
        assert "123" in error_msg
        assert "None" in error_msg

    def test_all_enum_values_valid(self) -> None:
        """Test that all CampaignType enum values are accepted."""
        all_campaign_types = list(CampaignType.__members__.keys())
        result = GoogleAdsInputValidator.validate_campaign_types(all_campaign_types)

        assert len(result) == len(all_campaign_types)
        assert set(result) == set(all_campaign_types)


class TestCampaignIdValidation:
    """Test campaign ID validation."""

    def test_valid_campaign_ids(self) -> None:
        """Test validation of valid campaign IDs."""
        valid_ids = ["123456", "789012", "345678901234567890"]
        result = GoogleAdsInputValidator.validate_campaign_ids(valid_ids)

        assert result == valid_ids

    def test_numeric_conversion(self) -> None:
        """Test that numeric values are converted to strings."""
        numeric_ids = [123456, 789012, "345678"]
        result = GoogleAdsInputValidator.validate_campaign_ids(numeric_ids)

        assert result == ["123456", "789012", "345678"]

    def test_whitespace_stripping(self) -> None:
        """Test that whitespace is stripped from IDs."""
        ids_with_spaces = ["  123456  ", "789012\n", "\t345678"]
        result = GoogleAdsInputValidator.validate_campaign_ids(ids_with_spaces)

        assert result == ["123456", "789012", "345678"]

    def test_empty_list(self) -> None:
        """Test that empty list returns empty list."""
        result = GoogleAdsInputValidator.validate_campaign_ids([])
        assert result == []

    def test_invalid_campaign_ids(self) -> None:
        """Test that invalid campaign IDs raise ValueError."""
        invalid_ids = ["123456", "abc123", "123-456", "12.34"]

        with pytest.raises(ValueError) as exc_info:
            GoogleAdsInputValidator.validate_campaign_ids(invalid_ids)

        error_msg = str(exc_info.value)
        assert "Invalid campaign IDs" in error_msg
        assert "must be numeric" in error_msg
        assert "abc123" in error_msg
        assert "123-456" in error_msg
        assert "12.34" in error_msg

    def test_zero_id(self) -> None:
        """Test that zero is a valid campaign ID."""
        result = GoogleAdsInputValidator.validate_campaign_ids(["0", "123456"])
        assert result == ["0", "123456"]

    def test_very_long_id(self) -> None:
        """Test handling of very long numeric IDs."""
        long_id = "9" * 50  # 50 digit number
        result = GoogleAdsInputValidator.validate_campaign_ids([long_id])
        assert result == [long_id]


class TestAdGroupIdValidation:
    """Test ad group ID validation."""

    def test_valid_ad_group_ids(self) -> None:
        """Test validation of valid ad group IDs."""
        valid_ids = ["456789", "012345", "987654321098765432"]
        result = GoogleAdsInputValidator.validate_ad_group_ids(valid_ids)

        assert result == valid_ids

    def test_numeric_conversion(self) -> None:
        """Test that numeric values are converted to strings."""
        numeric_ids = [456789, 12345, "678901"]
        result = GoogleAdsInputValidator.validate_ad_group_ids(numeric_ids)

        assert result == ["456789", "12345", "678901"]

    def test_whitespace_stripping(self) -> None:
        """Test that whitespace is stripped from IDs."""
        ids_with_spaces = ["  456789  ", "012345\n", "\t678901"]
        result = GoogleAdsInputValidator.validate_ad_group_ids(ids_with_spaces)

        assert result == ["456789", "012345", "678901"]

    def test_empty_list(self) -> None:
        """Test that empty list returns empty list."""
        result = GoogleAdsInputValidator.validate_ad_group_ids([])
        assert result == []

    def test_invalid_ad_group_ids(self) -> None:
        """Test that invalid ad group IDs raise ValueError."""
        invalid_ids = ["456789", "xyz789", "456_789", "45.67"]

        with pytest.raises(ValueError) as exc_info:
            GoogleAdsInputValidator.validate_ad_group_ids(invalid_ids)

        error_msg = str(exc_info.value)
        assert "Invalid ad group IDs" in error_msg
        assert "must be numeric" in error_msg
        assert "xyz789" in error_msg
        assert "456_789" in error_msg
        assert "45.67" in error_msg


class TestSharedSetIdValidation:
    """Test shared set ID validation."""

    def test_valid_shared_set_id(self) -> None:
        """Test validation of valid shared set ID."""
        result = GoogleAdsInputValidator.validate_shared_set_id("123456789")
        assert result == "123456789"

    def test_numeric_conversion(self) -> None:
        """Test that numeric value is converted to string."""
        result = GoogleAdsInputValidator.validate_shared_set_id(987654321)
        assert result == "987654321"

    def test_whitespace_stripping(self) -> None:
        """Test that whitespace is stripped from ID."""
        result = GoogleAdsInputValidator.validate_shared_set_id("  123456  ")
        assert result == "123456"

    def test_zero_id_invalid(self) -> None:
        """Test that zero ID is invalid."""
        with pytest.raises(ValueError) as exc_info:
            GoogleAdsInputValidator.validate_shared_set_id("0")

        error_msg = str(exc_info.value)
        assert "Must be a positive integer greater than 0" in error_msg

    def test_negative_id_invalid(self) -> None:
        """Test that negative ID is invalid."""
        with pytest.raises(ValueError) as exc_info:
            GoogleAdsInputValidator.validate_shared_set_id("-123456")

        error_msg = str(exc_info.value)
        assert "Invalid shared set ID format" in error_msg

    def test_non_numeric_id_invalid(self) -> None:
        """Test that non-numeric ID is invalid."""
        with pytest.raises(ValueError) as exc_info:
            GoogleAdsInputValidator.validate_shared_set_id("abc123")

        error_msg = str(exc_info.value)
        assert "Invalid shared set ID format" in error_msg
        assert "Must be a numeric string" in error_msg

    def test_decimal_id_invalid(self) -> None:
        """Test that decimal ID is invalid."""
        with pytest.raises(ValueError) as exc_info:
            GoogleAdsInputValidator.validate_shared_set_id("123.456")

        error_msg = str(exc_info.value)
        assert "Invalid shared set ID format" in error_msg


class TestCustomerIdValidation:
    """Test customer ID validation."""

    def test_valid_customer_ids(self) -> None:
        """Test validation of valid customer IDs."""
        # 7-10 digits are valid
        valid_ids = ["1234567", "12345678", "123456789", "1234567890"]

        for customer_id in valid_ids:
            result = GoogleAdsInputValidator.validate_customer_id(customer_id)
            assert result == customer_id

    def test_customer_id_with_hyphens(self) -> None:
        """Test that hyphens are removed from customer IDs."""
        result = GoogleAdsInputValidator.validate_customer_id("123-456-7890")
        assert result == "1234567890"

        result = GoogleAdsInputValidator.validate_customer_id("12-34-56-78-90")
        assert result == "1234567890"

    def test_numeric_conversion(self) -> None:
        """Test that numeric value is converted to string."""
        result = GoogleAdsInputValidator.validate_customer_id(1234567890)
        assert result == "1234567890"

    def test_whitespace_stripping(self) -> None:
        """Test that whitespace is stripped from ID."""
        result = GoogleAdsInputValidator.validate_customer_id("  1234567890  ")
        assert result == "1234567890"

    def test_too_short_id(self) -> None:
        """Test that IDs shorter than 7 digits are invalid."""
        with pytest.raises(ValueError) as exc_info:
            GoogleAdsInputValidator.validate_customer_id("123456")  # 6 digits

        error_msg = str(exc_info.value)
        assert "Invalid customer ID format" in error_msg
        assert "Must be 7-10 digits" in error_msg

    def test_too_long_id(self) -> None:
        """Test that IDs longer than 10 digits are invalid."""
        with pytest.raises(ValueError) as exc_info:
            GoogleAdsInputValidator.validate_customer_id("12345678901")  # 11 digits

        error_msg = str(exc_info.value)
        assert "Invalid customer ID format" in error_msg
        assert "Must be 7-10 digits" in error_msg

    def test_non_numeric_id(self) -> None:
        """Test that non-numeric IDs are invalid."""
        with pytest.raises(ValueError) as exc_info:
            GoogleAdsInputValidator.validate_customer_id("abc1234567")

        error_msg = str(exc_info.value)
        assert "Invalid customer ID format" in error_msg

    def test_mixed_format_with_spaces_and_hyphens(self) -> None:
        """Test complex formatting is handled."""
        # This format results in 11 digits, which is invalid
        with pytest.raises(ValueError) as exc_info:
            GoogleAdsInputValidator.validate_customer_id("  12-34-567  890  ")

        # Test error structure rather than exact message
        error = exc_info.value
        assert hasattr(error, "args")
        assert len(error.args) > 0
        # Still check key content is present
        assert "7-10 digits" in str(error)


class TestGeographicLevelValidation:
    """Test geographic level validation."""

    def test_valid_geographic_levels(self) -> None:
        """Test validation of valid geographic levels."""
        valid_levels = ["COUNTRY", "STATE", "CITY", "ZIP_CODE"]

        for level in valid_levels:
            result = GoogleAdsInputValidator.validate_geographic_level(level)
            assert result == level

    def test_case_normalization(self) -> None:
        """Test that geographic levels are normalized to uppercase."""
        result = GoogleAdsInputValidator.validate_geographic_level("country")
        assert result == "COUNTRY"

        result = GoogleAdsInputValidator.validate_geographic_level("City")
        assert result == "CITY"

        result = GoogleAdsInputValidator.validate_geographic_level("zip_code")
        assert result == "ZIP_CODE"

    def test_whitespace_stripping(self) -> None:
        """Test that whitespace is stripped."""
        result = GoogleAdsInputValidator.validate_geographic_level("  STATE  ")
        assert result == "STATE"

    def test_invalid_geographic_level(self) -> None:
        """Test that invalid geographic levels raise ValueError."""
        with pytest.raises(ValueError) as exc_info:
            GoogleAdsInputValidator.validate_geographic_level("INVALID_LEVEL")

        error_msg = str(exc_info.value)
        assert "Invalid geographic level" in error_msg
        assert "INVALID_LEVEL" in error_msg
        assert "Valid levels are:" in error_msg
        assert "COUNTRY" in error_msg
        assert "STATE" in error_msg
        assert "CITY" in error_msg
        assert "ZIP_CODE" in error_msg

    def test_non_string_conversion(self) -> None:
        """Test that non-string values are converted."""
        # This will fail validation as "123" is not a valid level
        with pytest.raises(ValueError) as exc_info:
            GoogleAdsInputValidator.validate_geographic_level(123)

        error_msg = str(exc_info.value)
        assert "Invalid geographic level: '123'" in error_msg


class TestGAQLFilterBuilders:
    """Test GAQL filter builder methods."""

    def test_build_campaign_type_filter(self) -> None:
        """Test building campaign type filter for GAQL."""
        campaign_types = ["SEARCH", "DISPLAY", "SHOPPING"]
        filter_str = GoogleAdsInputValidator.build_safe_campaign_type_filter(
            campaign_types
        )

        expected = (
            "campaign.advertising_channel_type = 'SEARCH' OR "
            "campaign.advertising_channel_type = 'DISPLAY' OR "
            "campaign.advertising_channel_type = 'SHOPPING'"
        )
        assert filter_str == expected

    def test_build_campaign_type_filter_single(self) -> None:
        """Test building campaign type filter with single type."""
        filter_str = GoogleAdsInputValidator.build_safe_campaign_type_filter(["SEARCH"])
        assert filter_str == "campaign.advertising_channel_type = 'SEARCH'"

    def test_build_campaign_type_filter_empty(self) -> None:
        """Test building campaign type filter with empty list."""
        filter_str = GoogleAdsInputValidator.build_safe_campaign_type_filter([])
        assert filter_str == ""

    def test_build_campaign_type_filter_validation(self) -> None:
        """Test that invalid types are rejected in filter building."""
        with pytest.raises(ValueError):
            GoogleAdsInputValidator.build_safe_campaign_type_filter(
                ["SEARCH", "INVALID_TYPE"]
            )

    def test_build_campaign_id_filter(self) -> None:
        """Test building campaign ID filter for GAQL."""
        campaign_ids = ["123456", "789012", "345678"]
        filter_str = GoogleAdsInputValidator.build_safe_campaign_id_filter(campaign_ids)

        expected = (
            "campaign.id = 123456 OR campaign.id = 789012 OR campaign.id = 345678"
        )
        assert filter_str == expected

    def test_build_campaign_id_filter_single(self) -> None:
        """Test building campaign ID filter with single ID."""
        filter_str = GoogleAdsInputValidator.build_safe_campaign_id_filter(["123456"])
        assert filter_str == "campaign.id = 123456"

    def test_build_campaign_id_filter_empty(self) -> None:
        """Test building campaign ID filter with empty list."""
        filter_str = GoogleAdsInputValidator.build_safe_campaign_id_filter([])
        assert filter_str == ""

    def test_build_campaign_id_filter_validation(self) -> None:
        """Test that invalid IDs are rejected in filter building."""
        with pytest.raises(ValueError):
            GoogleAdsInputValidator.build_safe_campaign_id_filter(["123456", "abc123"])

    def test_build_ad_group_id_filter(self) -> None:
        """Test building ad group ID filter for GAQL."""
        ad_group_ids = ["456789", "012345", "678901"]
        filter_str = GoogleAdsInputValidator.build_safe_ad_group_id_filter(ad_group_ids)

        expected = (
            "ad_group.id = 456789 OR ad_group.id = 012345 OR ad_group.id = 678901"
        )
        assert filter_str == expected

    def test_build_ad_group_id_filter_single(self) -> None:
        """Test building ad group ID filter with single ID."""
        filter_str = GoogleAdsInputValidator.build_safe_ad_group_id_filter(["456789"])
        assert filter_str == "ad_group.id = 456789"

    def test_build_ad_group_id_filter_empty(self) -> None:
        """Test building ad group ID filter with empty list."""
        filter_str = GoogleAdsInputValidator.build_safe_ad_group_id_filter([])
        assert filter_str == ""

    def test_build_ad_group_id_filter_validation(self) -> None:
        """Test that invalid IDs are rejected in filter building."""
        with pytest.raises(ValueError):
            GoogleAdsInputValidator.build_safe_ad_group_id_filter(["456789", "xyz789"])


class TestSecurityFeatures:
    """Test security features of the validator."""

    def test_sql_injection_prevention(self) -> None:
        """Test that SQL injection attempts are blocked."""
        # Attempt SQL injection in campaign ID
        malicious_ids = ["123456'; DROP TABLE campaigns; --", "123456 OR 1=1"]

        with pytest.raises(ValueError) as exc_info:
            GoogleAdsInputValidator.validate_campaign_ids(malicious_ids)

        error_msg = str(exc_info.value)
        assert "Invalid campaign IDs" in error_msg
        assert "DROP TABLE" in error_msg

    def test_gaql_injection_prevention(self) -> None:
        """Test that GAQL injection attempts are blocked."""
        # Attempt GAQL injection in campaign type
        malicious_types = ["SEARCH' OR campaign.status = 'ENABLED"]

        with pytest.raises(ValueError) as exc_info:
            GoogleAdsInputValidator.validate_campaign_types(malicious_types)

        error_msg = str(exc_info.value)
        assert "Invalid campaign types" in error_msg

    def test_special_characters_blocked(self) -> None:
        """Test that special characters are blocked in IDs."""
        # IDs with trailing whitespace are stripped and become valid
        whitespace_ids = [
            "123456\n",
            "123456\r",
            "123456\t",
            "123456 ",
        ]

        for id_with_whitespace in whitespace_ids:
            # These should be valid after stripping
            result = GoogleAdsInputValidator.validate_campaign_ids([id_with_whitespace])
            assert result == ["123456"]

        # IDs with embedded special characters should fail
        special_char_ids = [
            "123456<script>",
            "123456&quot;",
            "123456%20",
            "123 456",  # Embedded space
            "123\n456",  # Embedded newline
        ]

        for bad_id in special_char_ids:
            with pytest.raises(ValueError) as exc_info:
                GoogleAdsInputValidator.validate_campaign_ids([bad_id])
            error_msg = str(exc_info.value)
            assert "Invalid campaign IDs" in error_msg

    def test_unicode_injection_prevention(self) -> None:
        """Test that unicode injection attempts are blocked."""
        # Unicode characters that might bypass filters
        unicode_ids = [
            "123456‮⁦",  # Right-to-left override
            "123456\u200b",  # Zero-width space
            "123456\ufeff",  # Zero-width no-break space
        ]

        for bad_id in unicode_ids:
            with pytest.raises(ValueError):
                GoogleAdsInputValidator.validate_campaign_ids([bad_id])


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_string_validation(self) -> None:
        """Test that empty strings are rejected."""
        with pytest.raises(ValueError):
            GoogleAdsInputValidator.validate_campaign_ids([""])

        with pytest.raises(ValueError):
            GoogleAdsInputValidator.validate_shared_set_id("")

        with pytest.raises(ValueError):
            GoogleAdsInputValidator.validate_customer_id("")

        with pytest.raises(ValueError):
            GoogleAdsInputValidator.validate_geographic_level("")

    def test_none_handling(self) -> None:
        """Test handling of None values."""
        # None in list should be converted to string and fail
        with pytest.raises(ValueError):
            GoogleAdsInputValidator.validate_campaign_ids([None])

    def test_maximum_length_ids(self) -> None:
        """Test handling of maximum length IDs."""
        # Test with very long numeric string (should pass)
        long_id = "9" * 100
        result = GoogleAdsInputValidator.validate_campaign_ids([long_id])
        assert result == [long_id]

    def test_mixed_valid_invalid(self) -> None:
        """Test mixed valid and invalid inputs."""
        # Should fail on first invalid, not process valid ones
        with pytest.raises(ValueError) as exc_info:
            GoogleAdsInputValidator.validate_campaign_ids(
                ["123456", "789012", "abc123", "345678"]
            )

        error_msg = str(exc_info.value)
        assert "abc123" in error_msg

    def test_duplicate_handling(self) -> None:
        """Test handling of duplicate values."""
        # Duplicates should be preserved (deduplication is application concern)
        campaign_ids = ["123456", "789012", "123456", "789012"]
        result = GoogleAdsInputValidator.validate_campaign_ids(campaign_ids)
        assert result == campaign_ids

        campaign_types = ["SEARCH", "DISPLAY", "SEARCH", "DISPLAY"]
        result = GoogleAdsInputValidator.validate_campaign_types(campaign_types)
        assert result == campaign_types
