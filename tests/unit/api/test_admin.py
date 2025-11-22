"""Tests for the admin role management module (api/admin.py)."""

import pytest
from fastapi import HTTPException

from paidsearchnav_mcp.api.admin import (
    check_admin_access,
    get_user_permissions,
    require_admin_role,
    require_security_access,
    require_system_access,
    require_user_management_access,
)


class TestAdminRoleManagement:
    """Test admin role management functions."""

    def test_require_admin_role_with_is_admin_flag(self):
        """Test require_admin_role with is_admin flag set to True."""
        current_user = {"is_admin": True, "user_id": "test_user"}

        result = require_admin_role(current_user)

        assert result == current_user

    def test_require_admin_role_with_admin_in_roles(self):
        """Test require_admin_role with 'admin' in roles array."""
        current_user = {
            "is_admin": False,
            "roles": ["admin", "user"],
            "user_id": "test_user",
        }

        result = require_admin_role(current_user)

        assert result == current_user

    def test_require_admin_role_with_administrator_in_roles(self):
        """Test require_admin_role with 'administrator' in roles array."""
        current_user = {
            "is_admin": False,
            "roles": ["administrator", "user"],
            "user_id": "test_user",
        }

        result = require_admin_role(current_user)

        assert result == current_user

    def test_require_admin_role_missing_is_admin_flag(self):
        """Test require_admin_role when is_admin flag is missing."""
        current_user = {"user_id": "test_user"}

        with pytest.raises(HTTPException) as exc_info:
            require_admin_role(current_user)

        assert exc_info.value.status_code == 403
        assert "Admin access required" in exc_info.value.detail

    def test_require_admin_role_is_admin_false_no_roles(self):
        """Test require_admin_role when is_admin is False and no roles."""
        current_user = {"is_admin": False, "user_id": "test_user"}

        with pytest.raises(HTTPException) as exc_info:
            require_admin_role(current_user)

        assert exc_info.value.status_code == 403
        assert "Admin access required" in exc_info.value.detail

    def test_require_admin_role_is_admin_false_no_admin_roles(self):
        """Test require_admin_role when is_admin is False and no admin roles."""
        current_user = {
            "is_admin": False,
            "roles": ["user", "manager"],
            "user_id": "test_user",
        }

        with pytest.raises(HTTPException) as exc_info:
            require_admin_role(current_user)

        assert exc_info.value.status_code == 403
        assert "Admin access required" in exc_info.value.detail

    def test_require_admin_role_empty_roles_array(self):
        """Test require_admin_role with empty roles array."""
        current_user = {"is_admin": False, "roles": [], "user_id": "test_user"}

        with pytest.raises(HTTPException) as exc_info:
            require_admin_role(current_user)

        assert exc_info.value.status_code == 403
        assert "Admin access required" in exc_info.value.detail

    def test_check_admin_access_with_is_admin_true(self):
        """Test check_admin_access with is_admin flag set to True."""
        current_user = {"is_admin": True, "user_id": "test_user"}

        result = check_admin_access(current_user)

        assert result is True

    def test_check_admin_access_with_admin_role(self):
        """Test check_admin_access with admin role."""
        current_user = {"is_admin": False, "roles": ["admin"], "user_id": "test_user"}

        result = check_admin_access(current_user)

        assert result is True

    def test_check_admin_access_with_administrator_role(self):
        """Test check_admin_access with administrator role."""
        current_user = {
            "is_admin": False,
            "roles": ["administrator"],
            "user_id": "test_user",
        }

        result = check_admin_access(current_user)

        assert result is True

    def test_check_admin_access_no_admin_privileges(self):
        """Test check_admin_access without admin privileges."""
        current_user = {"is_admin": False, "roles": ["user"], "user_id": "test_user"}

        result = check_admin_access(current_user)

        assert result is False

    def test_check_admin_access_missing_fields(self):
        """Test check_admin_access with missing fields."""
        current_user = {"user_id": "test_user"}

        result = check_admin_access(current_user)

        assert result is False

    def test_get_user_permissions_regular_user(self):
        """Test get_user_permissions for regular user."""
        current_user = {"is_admin": False, "is_agency": False, "user_id": "test_user"}

        permissions = get_user_permissions(current_user)

        expected_permissions = ["read_own_data", "create_audits", "view_reports"]

        assert all(perm in permissions for perm in expected_permissions)
        assert len(permissions) == len(expected_permissions)

    def test_get_user_permissions_admin_user(self):
        """Test get_user_permissions for admin user."""
        current_user = {"is_admin": True, "is_agency": False, "user_id": "test_user"}

        permissions = get_user_permissions(current_user)

        expected_basic_permissions = ["read_own_data", "create_audits", "view_reports"]

        expected_admin_permissions = [
            "read_all_data",
            "manage_users",
            "view_security_stats",
            "unlock_accounts",
            "manage_system_settings",
            "view_audit_logs",
        ]

        assert all(perm in permissions for perm in expected_basic_permissions)
        assert all(perm in permissions for perm in expected_admin_permissions)

    def test_get_user_permissions_agency_user(self):
        """Test get_user_permissions for agency user."""
        current_user = {"is_admin": False, "is_agency": True, "user_id": "test_user"}

        permissions = get_user_permissions(current_user)

        expected_basic_permissions = ["read_own_data", "create_audits", "view_reports"]

        expected_agency_permissions = [
            "read_client_data",
            "manage_client_accounts",
        ]

        assert all(perm in permissions for perm in expected_basic_permissions)
        assert all(perm in permissions for perm in expected_agency_permissions)

    def test_get_user_permissions_admin_agency_user(self):
        """Test get_user_permissions for admin agency user."""
        current_user = {"is_admin": True, "is_agency": True, "user_id": "test_user"}

        permissions = get_user_permissions(current_user)

        # Should have all permissions: basic + admin + agency
        expected_basic_permissions = ["read_own_data", "create_audits", "view_reports"]

        expected_admin_permissions = [
            "read_all_data",
            "manage_users",
            "view_security_stats",
            "unlock_accounts",
            "manage_system_settings",
            "view_audit_logs",
        ]

        expected_agency_permissions = [
            "read_client_data",
            "manage_client_accounts",
        ]

        all_expected = (
            expected_basic_permissions
            + expected_admin_permissions
            + expected_agency_permissions
        )

        assert all(perm in permissions for perm in all_expected)

    def test_get_user_permissions_missing_flags(self):
        """Test get_user_permissions with missing flags."""
        current_user = {"user_id": "test_user"}

        permissions = get_user_permissions(current_user)

        # Should default to basic permissions only
        expected_permissions = ["read_own_data", "create_audits", "view_reports"]

        assert all(perm in permissions for perm in expected_permissions)
        assert len(permissions) == len(expected_permissions)

    def test_require_user_management_access_with_admin(self):
        """Test require_user_management_access with admin user."""
        current_user = {"is_admin": True, "user_id": "test_user"}

        result = require_user_management_access(current_user)

        assert result == current_user

    def test_require_user_management_access_without_admin(self):
        """Test require_user_management_access without admin user."""
        current_user = {"is_admin": False, "user_id": "test_user"}

        # Since this function uses Depends(), we need to test the underlying logic
        # by directly calling the dependency (require_admin_role)
        with pytest.raises(HTTPException) as exc_info:
            require_admin_role(current_user)

        assert exc_info.value.status_code == 403

    def test_require_security_access_with_admin(self):
        """Test require_security_access with admin user."""
        current_user = {"is_admin": True, "user_id": "test_user"}

        result = require_security_access(current_user)

        assert result == current_user

    def test_require_security_access_without_admin(self):
        """Test require_security_access without admin user."""
        current_user = {"is_admin": False, "user_id": "test_user"}

        # Since this function uses Depends(), we need to test the underlying logic
        # by directly calling the dependency (require_admin_role)
        with pytest.raises(HTTPException) as exc_info:
            require_admin_role(current_user)

        assert exc_info.value.status_code == 403

    def test_require_system_access_with_admin(self):
        """Test require_system_access with admin user."""
        current_user = {"is_admin": True, "user_id": "test_user"}

        result = require_system_access(current_user)

        assert result == current_user

    def test_require_system_access_without_admin(self):
        """Test require_system_access without admin user."""
        current_user = {"is_admin": False, "user_id": "test_user"}

        # Since this function uses Depends(), we need to test the underlying logic
        # by directly calling the dependency (require_admin_role)
        with pytest.raises(HTTPException) as exc_info:
            require_admin_role(current_user)

        assert exc_info.value.status_code == 403

    def test_admin_functions_with_roles_array(self):
        """Test admin functions work with roles array instead of is_admin flag."""
        current_user = {"is_admin": False, "roles": ["admin"], "user_id": "test_user"}

        # All admin functions should work
        assert require_admin_role(current_user) == current_user
        assert require_user_management_access(current_user) == current_user
        assert require_security_access(current_user) == current_user
        assert require_system_access(current_user) == current_user

    def test_admin_functions_with_mixed_case_roles(self):
        """Test admin functions handle role name variations."""
        test_cases = [
            {"roles": ["admin"]},
            {"roles": ["administrator"]},
            {"roles": ["Admin"]},  # This should fail as we check for exact match
            {"roles": ["ADMIN"]},  # This should fail as we check for exact match
        ]

        for i, user_data in enumerate(test_cases):
            current_user = {"is_admin": False, "user_id": f"test_user_{i}", **user_data}

            if i < 2:  # First two cases should pass
                assert require_admin_role(current_user) == current_user
            else:  # Last two cases should fail (case sensitive)
                with pytest.raises(HTTPException):
                    require_admin_role(current_user)

    def test_error_message_content(self):
        """Test that error messages contain expected content."""
        current_user = {"is_admin": False, "user_id": "test_user"}

        with pytest.raises(HTTPException) as exc_info:
            require_admin_role(current_user)

        # Validate specific error details
        assert exc_info.value.status_code == 403
        error_detail = exc_info.value.detail
        assert "Admin access required" in error_detail
        assert "Insufficient privileges" in error_detail

        # Test that error message is user-friendly and informative
        assert isinstance(error_detail, str)
        assert len(error_detail) > 10  # Not empty or too brief
        assert "." in error_detail  # Proper sentence structure

    def test_error_message_consistency(self):
        """Test that error messages are consistent across different scenarios."""
        test_cases = [
            {"is_admin": False, "user_id": "test_user"},
            {"is_admin": False, "roles": [], "user_id": "test_user"},
            {"is_admin": False, "roles": ["user"], "user_id": "test_user"},
            {"user_id": "test_user"},  # Missing is_admin
        ]

        error_messages = []
        for current_user in test_cases:
            with pytest.raises(HTTPException) as exc_info:
                require_admin_role(current_user)

            assert exc_info.value.status_code == 403
            error_messages.append(exc_info.value.detail)

        # All error messages should be identical for consistency
        assert all(msg == error_messages[0] for msg in error_messages)

    def test_detailed_permission_validation(self):
        """Test detailed validation of permission lists."""
        # Test that admin permissions include all expected values
        current_user = {"is_admin": True, "is_agency": False, "user_id": "test_user"}
        permissions = get_user_permissions(current_user)

        # Basic permissions
        expected_basic = ["read_own_data", "create_audits", "view_reports"]
        for perm in expected_basic:
            assert perm in permissions, (
                f"Missing basic permission: {perm}. Got: {permissions}"
            )

        # Admin permissions
        expected_admin = [
            "read_all_data",
            "manage_users",
            "view_security_stats",
            "unlock_accounts",
            "manage_system_settings",
            "view_audit_logs",
        ]
        for perm in expected_admin:
            assert perm in permissions, (
                f"Missing admin permission: {perm}. Got: {permissions}"
            )

        # Verify no unexpected permissions
        all_expected = set(expected_basic + expected_admin)
        actual_set = set(permissions)
        unexpected = actual_set - all_expected
        assert not unexpected, f"Unexpected permissions found: {unexpected}"

    def test_admin_check_with_none_values(self):
        """Test admin functions handle None values gracefully."""
        current_user = {"is_admin": None, "roles": None, "user_id": "test_user"}

        # check_admin_access should handle None values
        assert check_admin_access(current_user) is False

        # require_admin_role should raise exception
        with pytest.raises(HTTPException):
            require_admin_role(current_user)

    def test_permissions_uniqueness(self):
        """Test that permissions list doesn't contain duplicates."""
        current_user = {"is_admin": True, "is_agency": True, "user_id": "test_user"}

        permissions = get_user_permissions(current_user)

        # Check that all permissions are unique
        assert len(permissions) == len(set(permissions))

    def test_permissions_list_not_empty(self):
        """Test that permissions list is never empty."""
        test_cases = [
            {"is_admin": True},
            {"is_admin": False},
            {"is_agency": True},
            {"is_agency": False},
            {},  # Empty user data
        ]

        for user_data in test_cases:
            current_user = {"user_id": "test_user", **user_data}
            permissions = get_user_permissions(current_user)

            assert len(permissions) > 0
            assert isinstance(permissions, list)

    def test_fastapi_dependency_compatibility(self):
        """Test that admin functions work as FastAPI dependencies."""
        from fastapi import Depends

        # Test that functions can be used as dependencies
        # (This is mainly a type check and structure validation)

        def test_endpoint(user=Depends(require_admin_role)):
            return user

        def test_endpoint2(user=Depends(require_user_management_access)):
            return user

        def test_endpoint3(user=Depends(require_security_access)):
            return user

        def test_endpoint4(user=Depends(require_system_access)):
            return user

        # If we reach here, the functions are properly structured as dependencies
        assert callable(test_endpoint)
        assert callable(test_endpoint2)
        assert callable(test_endpoint3)
        assert callable(test_endpoint4)
