"""Tests for User model validation with enum functionality."""

import pytest

from paidsearchnav_mcp.storage.models import User, UserType


class TestUserModelValidation:
    """Test User model validation with UserType enum."""

    def test_user_type_validation_valid_individual(self):
        """Test user type validation accepts valid individual string."""
        user = User()
        result = user.validate_user_type("user_type", "individual")
        assert result == "individual"

    def test_user_type_validation_valid_agency(self):
        """Test user type validation accepts valid agency string."""
        user = User()
        result = user.validate_user_type("user_type", "agency")
        assert result == "agency"

    def test_user_type_validation_invalid_type(self):
        """Test user type validation rejects invalid type."""
        user = User()
        with pytest.raises(ValueError, match="Invalid user type: invalid_type"):
            user.validate_user_type("user_type", "invalid_type")

    def test_user_type_validation_empty_string(self):
        """Test user type validation rejects empty string."""
        user = User()
        with pytest.raises(ValueError, match="Invalid user type: "):
            user.validate_user_type("user_type", "")

    def test_user_type_validation_none_value(self):
        """Test user type validation handles None appropriately."""
        user = User()
        with pytest.raises(ValueError):
            user.validate_user_type("user_type", None)

    def test_user_type_validation_uses_enum_validation(self):
        """Test that user type validation uses the enum's from_string method."""
        user = User()

        # Test that it accepts all valid enum values
        for user_type_enum in UserType:
            result = user.validate_user_type("user_type", user_type_enum.value)
            assert result == user_type_enum.value

    def test_user_type_default_value(self):
        """Test that default user type is set correctly."""
        # This tests that the default value still works as expected
        assert (
            User.__table__.columns["user_type"].default.arg == UserType.INDIVIDUAL.value
        )
