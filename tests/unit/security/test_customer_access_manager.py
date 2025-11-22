"""Tests for Customer Access Manager."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from paidsearchnav.security.access_control import (
    AccessLevel,
    AccessToken,
    CustomerAccessManager,
    ResourceType,
)


@pytest.fixture
def access_manager():
    """Create CustomerAccessManager instance."""
    return CustomerAccessManager()


@pytest.fixture
def mock_storage():
    """Create mock storage backend."""
    return MagicMock()


@pytest.fixture
def access_manager_with_storage(mock_storage):
    """Create CustomerAccessManager with storage backend."""
    return CustomerAccessManager(storage_backend=mock_storage)


class TestCustomerAccessManager:
    """Test Customer Access Manager functionality."""

    def test_initialization(self, access_manager):
        """Test manager initialization."""
        assert access_manager.storage is None
        assert isinstance(access_manager._permissions_cache, dict)
        assert isinstance(access_manager._token_cache, dict)
        assert isinstance(access_manager._access_rules, dict)

    def test_initialization_with_storage(self, mock_storage):
        """Test manager initialization with storage backend."""
        manager = CustomerAccessManager(storage_backend=mock_storage)
        assert manager.storage == mock_storage

    def test_grant_permission(self, access_manager):
        """Test granting access permission."""
        customer_id = "cust-123"
        user_id = "user-456"
        resource_type = ResourceType.AUDIT_DATA
        access_levels = [AccessLevel.READ, AccessLevel.WRITE]
        granted_by = "admin-user"

        permission = access_manager.grant_permission(
            customer_id=customer_id,
            user_id=user_id,
            resource_type=resource_type,
            access_levels=access_levels,
            granted_by=granted_by,
        )

        assert permission.customer_id == customer_id
        assert permission.user_id == user_id
        assert permission.resource_type == resource_type
        assert AccessLevel.READ in permission.access_levels
        assert AccessLevel.WRITE in permission.access_levels
        assert permission.granted_by == granted_by
        assert permission.is_active is True
        assert permission.expires_at is None

    def test_grant_permission_with_expiration(self, access_manager):
        """Test granting temporary access permission."""
        customer_id = "cust-123"
        user_id = "user-456"
        resource_type = ResourceType.REPORTS
        access_levels = [AccessLevel.READ]
        granted_by = "admin-user"
        duration_hours = 24

        permission = access_manager.grant_permission(
            customer_id=customer_id,
            user_id=user_id,
            resource_type=resource_type,
            access_levels=access_levels,
            granted_by=granted_by,
            duration_hours=duration_hours,
        )

        assert permission.expires_at is not None
        expected_expiry = datetime.now(timezone.utc) + timedelta(hours=duration_hours)
        assert abs((permission.expires_at - expected_expiry).total_seconds()) < 60

    def test_grant_permission_with_conditions(self, access_manager):
        """Test granting permission with conditions."""
        conditions = {"ip_ranges": ["192.168.1.0/24"], "mfa_required": True}

        permission = access_manager.grant_permission(
            customer_id="cust-123",
            user_id="user-456",
            resource_type=ResourceType.CONFIGURATIONS,
            access_levels=[AccessLevel.READ],
            granted_by="admin",
            conditions=conditions,
        )

        assert permission.conditions == conditions

    def test_revoke_permission(self, access_manager):
        """Test revoking permissions."""
        # First grant permission
        customer_id = "cust-123"
        user_id = "user-456"

        access_manager.grant_permission(
            customer_id=customer_id,
            user_id=user_id,
            resource_type=ResourceType.AUDIT_DATA,
            access_levels=[AccessLevel.READ],
            granted_by="admin",
        )

        # Revoke permission
        result = access_manager.revoke_permission(
            customer_id=customer_id, user_id=user_id
        )

        assert result is True

        # Check permissions are inactive
        permissions = access_manager.get_user_permissions(customer_id, user_id)
        assert len(permissions) == 0

    def test_revoke_specific_permission(self, access_manager):
        """Test revoking specific resource permission."""
        customer_id = "cust-123"
        user_id = "user-456"

        # Grant multiple permissions
        access_manager.grant_permission(
            customer_id=customer_id,
            user_id=user_id,
            resource_type=ResourceType.AUDIT_DATA,
            access_levels=[AccessLevel.READ],
            granted_by="admin",
        )

        access_manager.grant_permission(
            customer_id=customer_id,
            user_id=user_id,
            resource_type=ResourceType.REPORTS,
            access_levels=[AccessLevel.READ],
            granted_by="admin",
        )

        # Revoke only AUDIT_DATA permission
        result = access_manager.revoke_permission(
            customer_id=customer_id,
            user_id=user_id,
            resource_type=ResourceType.AUDIT_DATA,
        )

        assert result is True

        # Check remaining permissions
        permissions = access_manager.get_user_permissions(customer_id, user_id)
        assert len(permissions) == 1
        assert permissions[0].resource_type == ResourceType.REPORTS

    def test_check_access_allowed(self, access_manager):
        """Test access check when allowed."""
        customer_id = "cust-123"
        user_id = "user-456"
        resource_path = "/customers/cust-123/audits/2024-01-01/data.csv"

        # Grant permission
        access_manager.grant_permission(
            customer_id=customer_id,
            user_id=user_id,
            resource_type=ResourceType.AUDIT_DATA,
            access_levels=[AccessLevel.READ, AccessLevel.WRITE],
            granted_by="admin",
        )

        # Check access
        decision = access_manager.check_access(
            customer_id=customer_id,
            user_id=user_id,
            resource_path=resource_path,
            access_level=AccessLevel.READ,
        )

        assert decision.allowed is True
        assert decision.reason == "Permission granted"
        assert decision.permissions is not None

    def test_check_access_denied_no_permission(self, access_manager):
        """Test access check when no permission exists."""
        decision = access_manager.check_access(
            customer_id="cust-123",
            user_id="user-456",
            resource_path="/customers/cust-123/audits/data.csv",
            access_level=AccessLevel.READ,
        )

        assert decision.allowed is False
        assert decision.reason == "No valid permission found"
        assert decision.permissions is None

    def test_check_access_denied_wrong_level(self, access_manager):
        """Test access check when permission level insufficient."""
        customer_id = "cust-123"
        user_id = "user-456"

        # Grant read-only permission
        access_manager.grant_permission(
            customer_id=customer_id,
            user_id=user_id,
            resource_type=ResourceType.AUDIT_DATA,
            access_levels=[AccessLevel.READ],
            granted_by="admin",
        )

        # Try to write
        decision = access_manager.check_access(
            customer_id=customer_id,
            user_id=user_id,
            resource_path="/customers/cust-123/audits/data.csv",
            access_level=AccessLevel.WRITE,
        )

        assert decision.allowed is False

    def test_check_access_expired_permission(self, access_manager):
        """Test access check with expired permission."""
        customer_id = "cust-123"
        user_id = "user-456"

        # Grant permission with past expiration
        permission = access_manager.grant_permission(
            customer_id=customer_id,
            user_id=user_id,
            resource_type=ResourceType.AUDIT_DATA,
            access_levels=[AccessLevel.READ],
            granted_by="admin",
        )

        # Manually set past expiration
        permission.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)

        # Check access
        decision = access_manager.check_access(
            customer_id=customer_id,
            user_id=user_id,
            resource_path="/customers/cust-123/audits/data.csv",
            access_level=AccessLevel.READ,
        )

        assert decision.allowed is False

    def test_check_access_with_conditions(self, access_manager):
        """Test access check with conditions."""
        customer_id = "cust-123"
        user_id = "user-456"

        # Grant permission with IP restriction
        access_manager.grant_permission(
            customer_id=customer_id,
            user_id=user_id,
            resource_type=ResourceType.AUDIT_DATA,
            access_levels=[AccessLevel.READ],
            granted_by="admin",
            conditions={"ip_ranges": ["192.168.1.0/24"]},
        )

        # Check access with matching IP
        context = {"ip_address": "192.168.1.100"}
        decision = access_manager.check_access(
            customer_id=customer_id,
            user_id=user_id,
            resource_path="/customers/cust-123/audits/data.csv",
            access_level=AccessLevel.READ,
            context=context,
        )

        assert decision.allowed is True

        # Check access with non-matching IP
        context = {"ip_address": "10.0.0.1"}
        decision = access_manager.check_access(
            customer_id=customer_id,
            user_id=user_id,
            resource_path="/customers/cust-123/audits/data.csv",
            access_level=AccessLevel.READ,
            context=context,
        )

        assert decision.allowed is False

    def test_generate_access_token(self, access_manager):
        """Test access token generation."""
        customer_id = "cust-123"
        user_id = "user-456"

        # Grant permission first
        access_manager.grant_permission(
            customer_id=customer_id,
            user_id=user_id,
            resource_type=ResourceType.AUDIT_DATA,
            access_levels=[AccessLevel.READ],
            granted_by="admin",
        )

        # Generate token
        token = access_manager.generate_access_token(
            customer_id=customer_id, user_id=user_id, duration_hours=2
        )

        assert isinstance(token, AccessToken)
        assert token.customer_id == customer_id
        assert token.user_id == user_id
        assert len(token.permissions) > 0
        assert token.token is not None
        assert len(token.token) > 0

    def test_generate_access_token_with_restrictions(self, access_manager):
        """Test access token generation with restrictions."""
        customer_id = "cust-123"
        user_id = "user-456"
        ip_address = "192.168.1.100"
        user_agent = "TestAgent/1.0"

        # Grant permission
        access_manager.grant_permission(
            customer_id=customer_id,
            user_id=user_id,
            resource_type=ResourceType.REPORTS,
            access_levels=[AccessLevel.READ],
            granted_by="admin",
        )

        # Generate token with restrictions
        token = access_manager.generate_access_token(
            customer_id=customer_id,
            user_id=user_id,
            duration_hours=1,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        assert token.ip_address == ip_address
        assert token.user_agent == user_agent

    def test_generate_access_token_no_permissions(self, access_manager):
        """Test access token generation without permissions."""
        with pytest.raises(ValueError, match="No permissions found"):
            access_manager.generate_access_token(
                customer_id="cust-123", user_id="user-456"
            )

    def test_validate_token_valid(self, access_manager):
        """Test token validation with valid token."""
        customer_id = "cust-123"
        user_id = "user-456"

        # Grant permission and generate token
        access_manager.grant_permission(
            customer_id=customer_id,
            user_id=user_id,
            resource_type=ResourceType.AUDIT_DATA,
            access_levels=[AccessLevel.READ],
            granted_by="admin",
        )

        token = access_manager.generate_access_token(
            customer_id=customer_id, user_id=user_id
        )

        # Validate token
        validated = access_manager.validate_token(token.token)

        assert validated is not None
        assert validated.customer_id == customer_id
        assert validated.user_id == user_id

    def test_validate_token_expired(self, access_manager):
        """Test token validation with expired token."""
        customer_id = "cust-123"
        user_id = "user-456"

        # Grant permission and generate token
        access_manager.grant_permission(
            customer_id=customer_id,
            user_id=user_id,
            resource_type=ResourceType.AUDIT_DATA,
            access_levels=[AccessLevel.READ],
            granted_by="admin",
        )

        token = access_manager.generate_access_token(
            customer_id=customer_id, user_id=user_id
        )

        # Manually expire token
        token.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)

        # Validate token
        validated = access_manager.validate_token(token.token)

        assert validated is None

    def test_validate_token_ip_mismatch(self, access_manager):
        """Test token validation with IP mismatch."""
        customer_id = "cust-123"
        user_id = "user-456"

        # Grant permission and generate token with IP restriction
        access_manager.grant_permission(
            customer_id=customer_id,
            user_id=user_id,
            resource_type=ResourceType.AUDIT_DATA,
            access_levels=[AccessLevel.READ],
            granted_by="admin",
        )

        token = access_manager.generate_access_token(
            customer_id=customer_id, user_id=user_id, ip_address="192.168.1.100"
        )

        # Validate with different IP
        validated = access_manager.validate_token(token.token, ip_address="10.0.0.1")

        assert validated is None

    def test_validate_token_invalid(self, access_manager):
        """Test token validation with invalid token."""
        validated = access_manager.validate_token("invalid-token")
        assert validated is None

    def test_get_user_permissions(self, access_manager):
        """Test getting user permissions."""
        customer_id = "cust-123"
        user_id = "user-456"

        # Grant multiple permissions
        access_manager.grant_permission(
            customer_id=customer_id,
            user_id=user_id,
            resource_type=ResourceType.AUDIT_DATA,
            access_levels=[AccessLevel.READ],
            granted_by="admin",
        )

        access_manager.grant_permission(
            customer_id=customer_id,
            user_id=user_id,
            resource_type=ResourceType.REPORTS,
            access_levels=[AccessLevel.READ, AccessLevel.WRITE],
            granted_by="admin",
        )

        # Get permissions
        permissions = access_manager.get_user_permissions(customer_id, user_id)

        assert len(permissions) == 2
        resource_types = {p.resource_type for p in permissions}
        assert ResourceType.AUDIT_DATA in resource_types
        assert ResourceType.REPORTS in resource_types

    def test_get_user_permissions_filters_inactive(self, access_manager):
        """Test that inactive permissions are filtered."""
        customer_id = "cust-123"
        user_id = "user-456"

        # Grant permission
        permission = access_manager.grant_permission(
            customer_id=customer_id,
            user_id=user_id,
            resource_type=ResourceType.AUDIT_DATA,
            access_levels=[AccessLevel.READ],
            granted_by="admin",
        )

        # Make it inactive
        permission.is_active = False

        # Get permissions
        permissions = access_manager.get_user_permissions(customer_id, user_id)

        assert len(permissions) == 0

    def test_create_service_account(self, access_manager):
        """Test service account creation."""
        customer_id = "cust-123"
        service_name = "data-processor"
        permissions = [ResourceType.AUDIT_DATA, ResourceType.REPORTS]

        service_account = access_manager.create_service_account(
            customer_id=customer_id, service_name=service_name, permissions=permissions
        )

        assert service_account["customer_id"] == customer_id
        assert service_account["service_name"] == service_name
        assert service_account["service_id"].startswith(
            f"svc_{customer_id}_{service_name}"
        )
        assert service_account["api_key"] is not None
        assert len(service_account["api_key"]) > 0
        assert service_account["permissions"] == ["audit_data", "reports"]

    def test_generate_data_isolation_key(self, access_manager):
        """Test data isolation key generation."""
        customer_id = "cust-123"
        data_type = "audit_data"

        key1 = access_manager.generate_data_isolation_key(customer_id, data_type)
        key2 = access_manager.generate_data_isolation_key(customer_id, data_type)
        key3 = access_manager.generate_data_isolation_key("cust-456", data_type)

        # Same inputs should produce same key
        assert key1 == key2

        # Different customer should produce different key
        assert key1 != key3

        # Key should be 16 characters
        assert len(key1) == 16

    def test_resource_path_matching(self, access_manager):
        """Test resource path pattern matching."""
        # Test exact match
        assert access_manager._matches_resource_path(
            "/customers/123/audits/file.csv", "/customers/123/audits/file.csv"
        )

        # Test wildcard match
        assert access_manager._matches_resource_path(
            "/customers/123/audits/2024/file.csv", "/customers/123/audits/*"
        )

        # Test no match
        assert not access_manager._matches_resource_path(
            "/customers/456/audits/file.csv", "/customers/123/audits/*"
        )

    def test_ip_range_checking(self, access_manager):
        """Test IP range validation."""
        # Test single IP
        assert access_manager._check_ip_range("192.168.1.100", ["192.168.1.100/32"])

        # Test subnet
        assert access_manager._check_ip_range("192.168.1.100", ["192.168.1.0/24"])

        # Test not in range
        assert not access_manager._check_ip_range("10.0.0.1", ["192.168.1.0/24"])

        # Test invalid IP
        assert not access_manager._check_ip_range("invalid", ["192.168.1.0/24"])
