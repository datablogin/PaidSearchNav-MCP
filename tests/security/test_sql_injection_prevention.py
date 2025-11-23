"""Tests for SQL injection prevention in Google Ads client."""

import pytest

from paidsearchnav_mcp.platforms.google.validation import GoogleAdsInputValidator


class TestGoogleAdsInputValidator:
    """Test input validation utilities for SQL injection prevention."""

    def test_validate_campaign_types_valid(self):
        """Test that valid campaign types are accepted."""
        valid_types = ["SEARCH", "DISPLAY", "SHOPPING"]
        result = GoogleAdsInputValidator.validate_campaign_types(valid_types)
        assert result == ["SEARCH", "DISPLAY", "SHOPPING"]

    def test_validate_campaign_types_case_insensitive(self):
        """Test that campaign type validation is case insensitive."""
        mixed_case_types = ["search", "Display", "SHOPPING"]
        result = GoogleAdsInputValidator.validate_campaign_types(mixed_case_types)
        assert result == ["SEARCH", "DISPLAY", "SHOPPING"]

    def test_validate_campaign_types_with_whitespace(self):
        """Test that campaign type validation handles whitespace."""
        types_with_whitespace = [" SEARCH ", "DISPLAY\t", "\nSHOPPING"]
        result = GoogleAdsInputValidator.validate_campaign_types(types_with_whitespace)
        assert result == ["SEARCH", "DISPLAY", "SHOPPING"]

    def test_validate_campaign_types_invalid(self):
        """Test that invalid campaign types are rejected."""
        invalid_types = ["SEARCH", "INVALID_TYPE", "MALICIOUS'; DROP TABLE--"]

        with pytest.raises(ValueError) as exc_info:
            GoogleAdsInputValidator.validate_campaign_types(invalid_types)

        assert "Invalid campaign types" in str(exc_info.value)
        assert "INVALID_TYPE" in str(exc_info.value)
        assert "MALICIOUS'; DROP TABLE--" in str(exc_info.value)

    def test_validate_campaign_types_empty_list(self):
        """Test that empty list is handled correctly."""
        result = GoogleAdsInputValidator.validate_campaign_types([])
        assert result == []

    def test_validate_campaign_types_non_string(self):
        """Test that non-string types are rejected."""
        invalid_types = ["SEARCH", 123, None]

        with pytest.raises(ValueError) as exc_info:
            GoogleAdsInputValidator.validate_campaign_types(invalid_types)

        assert "Invalid campaign types" in str(exc_info.value)

    def test_validate_campaign_ids_valid(self):
        """Test that valid campaign IDs are accepted."""
        valid_ids = ["123456789", "987654321", "555666777"]
        result = GoogleAdsInputValidator.validate_campaign_ids(valid_ids)
        assert result == ["123456789", "987654321", "555666777"]

    def test_validate_campaign_ids_with_whitespace(self):
        """Test that campaign ID validation handles whitespace."""
        ids_with_whitespace = [" 123456789 ", "987654321\t", "\n555666777"]
        result = GoogleAdsInputValidator.validate_campaign_ids(ids_with_whitespace)
        assert result == ["123456789", "987654321", "555666777"]

    def test_validate_campaign_ids_invalid_format(self):
        """Test that invalid campaign ID formats are rejected."""
        invalid_ids = ["123456789", "abc123", "'; DROP TABLE campaigns--"]

        with pytest.raises(ValueError) as exc_info:
            GoogleAdsInputValidator.validate_campaign_ids(invalid_ids)

        assert "Invalid campaign IDs" in str(exc_info.value)
        assert "abc123" in str(exc_info.value)
        assert "'; DROP TABLE campaigns--" in str(exc_info.value)

    def test_validate_campaign_ids_empty_list(self):
        """Test that empty list is handled correctly."""
        result = GoogleAdsInputValidator.validate_campaign_ids([])
        assert result == []

    def test_validate_campaign_ids_non_string(self):
        """Test that non-string campaign IDs are converted."""
        mixed_types = [123456789, "987654321"]
        result = GoogleAdsInputValidator.validate_campaign_ids(mixed_types)
        assert result == ["123456789", "987654321"]

    def test_validate_ad_group_ids_valid(self):
        """Test that valid ad group IDs are accepted."""
        valid_ids = ["123456789", "987654321", "555666777"]
        result = GoogleAdsInputValidator.validate_ad_group_ids(valid_ids)
        assert result == ["123456789", "987654321", "555666777"]

    def test_validate_ad_group_ids_invalid_format(self):
        """Test that invalid ad group ID formats are rejected."""
        invalid_ids = ["123456789", "abc123", "'; DROP TABLE ad_groups--"]

        with pytest.raises(ValueError) as exc_info:
            GoogleAdsInputValidator.validate_ad_group_ids(invalid_ids)

        assert "Invalid ad group IDs" in str(exc_info.value)
        assert "abc123" in str(exc_info.value)

    def test_validate_customer_id_valid(self):
        """Test that valid customer IDs are accepted."""
        valid_ids = ["1234567", "12345678", "123456789", "1234567890"]
        for valid_id in valid_ids:
            result = GoogleAdsInputValidator.validate_customer_id(valid_id)
            assert result == valid_id

    def test_validate_customer_id_with_hyphens(self):
        """Test that customer IDs with hyphens are accepted."""
        id_with_hyphens = "123-456-7890"
        result = GoogleAdsInputValidator.validate_customer_id(id_with_hyphens)
        assert result == "1234567890"

    def test_validate_customer_id_invalid_format(self):
        """Test that invalid customer ID formats are rejected."""
        invalid_ids = [
            "123456",  # Too short (less than 7 digits)
            "12345678901",  # Too long (more than 10 digits)
            "abcd567890",  # Contains letters
            "'; DROP TABLE--",  # SQL injection attempt
        ]

        for invalid_id in invalid_ids:
            with pytest.raises(ValueError) as exc_info:
                GoogleAdsInputValidator.validate_customer_id(invalid_id)
            assert "Invalid customer ID format" in str(exc_info.value)

    def test_validate_geographic_level_valid(self):
        """Test that valid geographic levels are accepted."""
        valid_levels = ["COUNTRY", "STATE", "CITY", "ZIP_CODE"]

        for level in valid_levels:
            result = GoogleAdsInputValidator.validate_geographic_level(level)
            assert result == level

    def test_validate_geographic_level_case_insensitive(self):
        """Test that geographic level validation is case insensitive."""
        result = GoogleAdsInputValidator.validate_geographic_level("city")
        assert result == "CITY"

    def test_validate_geographic_level_invalid(self):
        """Test that invalid geographic levels are rejected."""
        invalid_levels = ["INVALID", "'; DROP TABLE--", "REGION"]

        for invalid_level in invalid_levels:
            with pytest.raises(ValueError) as exc_info:
                GoogleAdsInputValidator.validate_geographic_level(invalid_level)
            assert "Invalid geographic level" in str(exc_info.value)

    def test_build_safe_campaign_type_filter(self):
        """Test building safe campaign type filters."""
        campaign_types = ["SEARCH", "DISPLAY"]
        result = GoogleAdsInputValidator.build_safe_campaign_type_filter(campaign_types)

        expected = (
            "campaign.advertising_channel_type = 'SEARCH' OR "
            "campaign.advertising_channel_type = 'DISPLAY'"
        )
        assert result == expected

    def test_build_safe_campaign_type_filter_empty(self):
        """Test building campaign type filter with empty list."""
        result = GoogleAdsInputValidator.build_safe_campaign_type_filter([])
        assert result == ""

    def test_build_safe_campaign_id_filter(self):
        """Test building safe campaign ID filters."""
        campaign_ids = ["123456789", "987654321"]
        result = GoogleAdsInputValidator.build_safe_campaign_id_filter(campaign_ids)

        expected = "campaign.id = 123456789 OR campaign.id = 987654321"
        assert result == expected

    def test_build_safe_campaign_id_filter_empty(self):
        """Test building campaign ID filter with empty list."""
        result = GoogleAdsInputValidator.build_safe_campaign_id_filter([])
        assert result == ""

    def test_build_safe_ad_group_id_filter(self):
        """Test building safe ad group ID filters."""
        ad_group_ids = ["123456789", "987654321"]
        result = GoogleAdsInputValidator.build_safe_ad_group_id_filter(ad_group_ids)

        expected = "ad_group.id = 123456789 OR ad_group.id = 987654321"
        assert result == expected

    def test_build_safe_ad_group_id_filter_empty(self):
        """Test building ad group ID filter with empty list."""
        result = GoogleAdsInputValidator.build_safe_ad_group_id_filter([])
        assert result == ""


class TestSQLInjectionPrevention:
    """Test SQL injection prevention in practice."""

    def test_malicious_campaign_types_blocked(self):
        """Test that malicious campaign types are blocked."""
        malicious_types = [
            "SEARCH'; DROP TABLE campaigns--",
            "DISPLAY' OR '1'='1",
            "SHOPPING'; INSERT INTO campaigns VALUES ('evil')--",
            "VIDEO' UNION SELECT * FROM sensitive_data--",
        ]

        with pytest.raises(ValueError) as exc_info:
            GoogleAdsInputValidator.validate_campaign_types(malicious_types)

        error_message = str(exc_info.value)
        assert "Invalid campaign types" in error_message
        # Verify all malicious types are mentioned in error
        for malicious_type in malicious_types:
            assert malicious_type in error_message

    def test_malicious_campaign_ids_blocked(self):
        """Test that malicious campaign IDs are blocked."""
        malicious_ids = [
            "123'; DROP TABLE campaigns--",
            "456 OR 1=1",
            "789; INSERT INTO campaigns VALUES ('evil')--",
            "abc' UNION SELECT * FROM sensitive_data--",
            "'; DELETE FROM campaigns WHERE 1=1--",
        ]

        with pytest.raises(ValueError) as exc_info:
            GoogleAdsInputValidator.validate_campaign_ids(malicious_ids)

        error_message = str(exc_info.value)
        assert "Invalid campaign IDs" in error_message

    def test_malicious_ad_group_ids_blocked(self):
        """Test that malicious ad group IDs are blocked."""
        malicious_ids = [
            "123'; DROP TABLE ad_groups--",
            "456 OR 1=1",
            "789; UPDATE ad_groups SET status='REMOVED'--",
            "'; EXEC xp_cmdshell('rm -rf /')--",
        ]

        with pytest.raises(ValueError) as exc_info:
            GoogleAdsInputValidator.validate_ad_group_ids(malicious_ids)

        error_message = str(exc_info.value)
        assert "Invalid ad group IDs" in error_message

    def test_malicious_customer_ids_blocked(self):
        """Test that malicious customer IDs are blocked."""
        malicious_ids = [
            "123'; DROP--",
            "1234567890' OR '1'='1",
            "'; DELETE FROM customers--",
            "abc1234567",
            "1234567890'; EXEC evil()--",
        ]

        for malicious_id in malicious_ids:
            with pytest.raises(ValueError) as exc_info:
                GoogleAdsInputValidator.validate_customer_id(malicious_id)
            assert "Invalid customer ID format" in str(exc_info.value)

    def test_malicious_geographic_levels_blocked(self):
        """Test that malicious geographic levels are blocked."""
        malicious_levels = [
            "CITY'; DROP TABLE geographic_view--",
            "STATE' OR '1'='1",
            "'; DELETE FROM geographic_view--",
            "COUNTRY' UNION SELECT * FROM sensitive_data--",
        ]

        for malicious_level in malicious_levels:
            with pytest.raises(ValueError) as exc_info:
                GoogleAdsInputValidator.validate_geographic_level(malicious_level)
            assert "Invalid geographic level" in str(exc_info.value)

    def test_filter_generation_safety(self):
        """Test that filter generation is safe even with edge cases."""
        # Test with valid inputs to ensure filters are properly constructed
        campaign_types = ["SEARCH", "DISPLAY"]
        type_filter = GoogleAdsInputValidator.build_safe_campaign_type_filter(
            campaign_types
        )

        # Verify no quotes in the enum values (they're safely validated)
        assert "campaign.advertising_channel_type = 'SEARCH'" in type_filter
        assert "campaign.advertising_channel_type = 'DISPLAY'" in type_filter
        assert "--" not in type_filter  # No SQL comments
        assert "DROP" not in type_filter  # No dangerous commands

        # Test with numeric IDs
        campaign_ids = ["123456789", "987654321"]
        id_filter = GoogleAdsInputValidator.build_safe_campaign_id_filter(campaign_ids)

        # Verify numeric IDs don't have quotes (safe)
        assert "campaign.id = 123456789" in id_filter
        assert "campaign.id = 987654321" in id_filter
        assert "'" not in id_filter  # No quotes around numbers
        assert "--" not in id_filter  # No SQL comments

    def test_comprehensive_validation_integration(self):
        """Test that comprehensive validation works in integrated scenarios."""
        # Test scenario with all valid inputs
        valid_campaign_types = ["SEARCH", "DISPLAY"]
        valid_campaign_ids = ["123456789", "987654321"]
        valid_ad_group_ids = ["555666777", "888999000"]
        valid_customer_id = "1234567890"
        valid_geographic_level = "CITY"

        # All validations should pass
        validated_types = GoogleAdsInputValidator.validate_campaign_types(
            valid_campaign_types
        )
        validated_campaign_ids = GoogleAdsInputValidator.validate_campaign_ids(
            valid_campaign_ids
        )
        validated_ad_group_ids = GoogleAdsInputValidator.validate_ad_group_ids(
            valid_ad_group_ids
        )
        validated_customer_id = GoogleAdsInputValidator.validate_customer_id(
            valid_customer_id
        )
        validated_geographic_level = GoogleAdsInputValidator.validate_geographic_level(
            valid_geographic_level
        )

        assert validated_types == ["SEARCH", "DISPLAY"]
        assert validated_campaign_ids == ["123456789", "987654321"]
        assert validated_ad_group_ids == ["555666777", "888999000"]
        assert validated_customer_id == "1234567890"
        assert validated_geographic_level == "CITY"

        # Build safe filters
        type_filter = GoogleAdsInputValidator.build_safe_campaign_type_filter(
            validated_types
        )
        campaign_filter = GoogleAdsInputValidator.build_safe_campaign_id_filter(
            validated_campaign_ids
        )
        ad_group_filter = GoogleAdsInputValidator.build_safe_ad_group_id_filter(
            validated_ad_group_ids
        )

        # All filters should be generated safely
        assert type_filter
        assert campaign_filter
        assert ad_group_filter

        # Verify filters don't contain dangerous patterns
        all_filters = [type_filter, campaign_filter, ad_group_filter]
        for filter_str in all_filters:
            assert "--" not in filter_str
            assert "DROP" not in filter_str.upper()
            assert "DELETE" not in filter_str.upper()
            assert "INSERT" not in filter_str.upper()
            assert "UPDATE" not in filter_str.upper()
            assert "UNION" not in filter_str.upper()
            assert "EXEC" not in filter_str.upper()
