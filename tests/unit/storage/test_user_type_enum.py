"""Tests for UserType enum functionality."""

import pytest

from paidsearchnav_mcp.storage.models import UserType


class TestUserTypeEnum:
    """Test UserType enum methods and functionality."""

    def test_from_string_valid_individual(self):
        """Test from_string with valid individual value."""
        result = UserType.from_string("individual")
        assert result == UserType.INDIVIDUAL

    def test_from_string_valid_agency(self):
        """Test from_string with valid agency value."""
        result = UserType.from_string("agency")
        assert result == UserType.AGENCY

    def test_from_string_invalid_value(self):
        """Test from_string with invalid value raises ValueError."""
        with pytest.raises(ValueError, match="Invalid user type: invalid_type"):
            UserType.from_string("invalid_type")

    def test_from_string_empty_value(self):
        """Test from_string with empty value raises ValueError."""
        with pytest.raises(ValueError, match="Invalid user type: "):
            UserType.from_string("")

    def test_from_string_none_value(self):
        """Test from_string with None value raises TypeError."""
        with pytest.raises(TypeError, match="Expected string, got NoneType: None"):
            UserType.from_string(None)

    def test_from_string_non_string_types(self):
        """Test from_string with non-string types raises TypeError."""
        with pytest.raises(TypeError, match="Expected string, got int"):
            UserType.from_string(123)

        with pytest.raises(TypeError, match="Expected string, got list"):
            UserType.from_string(["individual"])

        with pytest.raises(TypeError, match="Expected string, got dict"):
            UserType.from_string({"type": "individual"})

    def test_is_individual_true(self):
        """Test is_individual returns True for INDIVIDUAL type."""
        user_type = UserType.INDIVIDUAL
        assert user_type.is_individual() is True
        assert user_type.is_agency() is False

    def test_is_individual_false(self):
        """Test is_individual returns False for AGENCY type."""
        user_type = UserType.AGENCY
        assert user_type.is_individual() is False
        assert user_type.is_agency() is True

    def test_is_agency_true(self):
        """Test is_agency returns True for AGENCY type."""
        user_type = UserType.AGENCY
        assert user_type.is_agency() is True
        assert user_type.is_individual() is False

    def test_is_agency_false(self):
        """Test is_agency returns False for INDIVIDUAL type."""
        user_type = UserType.INDIVIDUAL
        assert user_type.is_agency() is False
        assert user_type.is_individual() is True

    def test_enum_values_unchanged(self):
        """Test that enum values remain as expected strings."""
        assert UserType.INDIVIDUAL.value == "individual"
        assert UserType.AGENCY.value == "agency"

    def test_string_to_enum_roundtrip(self):
        """Test converting string to enum and back preserves value."""
        original_string = "individual"
        enum_instance = UserType.from_string(original_string)
        assert enum_instance.value == original_string

        original_string = "agency"
        enum_instance = UserType.from_string(original_string)
        assert enum_instance.value == original_string

    def test_enum_comparison_with_values(self):
        """Test that enum instances can be compared properly."""
        individual_enum = UserType.from_string("individual")
        agency_enum = UserType.from_string("agency")

        assert individual_enum == UserType.INDIVIDUAL
        assert agency_enum == UserType.AGENCY
        assert individual_enum != UserType.AGENCY
        assert agency_enum != UserType.INDIVIDUAL

    def test_type_safety_enforcement(self):
        """Test that from_string enforces type safety."""
        # This should work
        user_type = UserType.from_string("individual")
        assert isinstance(user_type, UserType)

        # This should fail with clear error message
        with pytest.raises(ValueError) as exc_info:
            UserType.from_string("not_a_valid_type")
        assert "Invalid user type: not_a_valid_type" in str(exc_info.value)
