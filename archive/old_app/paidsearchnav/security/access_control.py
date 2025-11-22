"""Customer access control and data isolation management."""

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Constants for access control configuration
DEFAULT_ACCESS_DURATION_HOURS = 24
DEFAULT_TOKEN_DURATION_HOURS = 1
TOKEN_STRING_LENGTH = 32
SERVICE_ID_TOKEN_LENGTH = 4
API_KEY_LENGTH = 48
DATA_ISOLATION_KEY_LENGTH = 16


class AccessLevel(Enum):
    """Access level enumeration."""

    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    ADMIN = "admin"


class ResourceType(Enum):
    """Resource type enumeration."""

    AUDIT_DATA = "audit_data"
    REPORTS = "reports"
    ACTIONABLE_FILES = "actionable_files"
    CONFIGURATIONS = "configurations"


class CustomerAccessPermission(BaseModel):
    """Customer access permission model."""

    customer_id: str = Field(..., description="Customer ID")
    user_id: str = Field(..., description="User ID")
    resource_type: ResourceType = Field(..., description="Type of resource")
    resource_path: str = Field(..., description="Resource path pattern")
    access_levels: Set[AccessLevel] = Field(..., description="Granted access levels")
    granted_by: str = Field(..., description="User who granted permission")
    granted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = Field(None, description="Permission expiration")
    conditions: Dict[str, Any] = Field(
        default_factory=dict, description="Access conditions"
    )
    is_active: bool = Field(True, description="Whether permission is active")


class AccessToken(BaseModel):
    """Temporary access token for API operations."""

    token: str = Field(..., description="Access token string")
    customer_id: str = Field(..., description="Customer ID")
    user_id: str = Field(..., description="User ID")
    permissions: List[CustomerAccessPermission] = Field(
        ..., description="Associated permissions"
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = Field(..., description="Token expiration")
    ip_address: Optional[str] = Field(None, description="IP address restriction")
    user_agent: Optional[str] = Field(None, description="User agent restriction")


class AccessRequest(BaseModel):
    """Access request model."""

    customer_id: str = Field(..., description="Customer ID")
    user_id: str = Field(..., description="User ID")
    resource_type: ResourceType = Field(..., description="Resource type")
    resource_path: str = Field(..., description="Resource path")
    access_level: AccessLevel = Field(..., description="Requested access level")
    reason: Optional[str] = Field(None, description="Reason for access")
    duration_hours: int = Field(
        DEFAULT_ACCESS_DURATION_HOURS, description="Access duration in hours"
    )


class AccessDecision(BaseModel):
    """Access control decision."""

    allowed: bool = Field(..., description="Whether access is allowed")
    reason: str = Field(..., description="Reason for decision")
    permissions: Optional[CustomerAccessPermission] = Field(
        None, description="Granted permissions"
    )
    restrictions: Dict[str, Any] = Field(
        default_factory=dict, description="Access restrictions"
    )


class CustomerAccessManager:
    """
    Manages customer-specific access permissions and data isolation.

    This class provides:
    - Customer data isolation through path-based access control
    - Role-based access management
    - Temporary access token generation
    - Access request validation and auditing
    - Multi-tenant data separation
    """

    def __init__(self, storage_backend: Optional[Any] = None):
        """
        Initialize Customer Access Manager.

        Args:
            storage_backend: Optional storage backend for persistence
        """
        self.storage = storage_backend
        self._permissions_cache: Dict[str, List[CustomerAccessPermission]] = {}
        self._token_cache: Dict[str, AccessToken] = {}
        self._access_rules: Dict[str, Dict] = self._initialize_access_rules()

    def _initialize_access_rules(self) -> Dict[str, Dict]:
        """Initialize default access control rules."""
        return {
            "customer_owner": {
                "audit_data": [AccessLevel.READ, AccessLevel.WRITE, AccessLevel.DELETE],
                "reports": [AccessLevel.READ],
                "actionable_files": [AccessLevel.READ, AccessLevel.WRITE],
                "configurations": [AccessLevel.READ, AccessLevel.WRITE],
            },
            "customer_viewer": {
                "audit_data": [AccessLevel.READ],
                "reports": [AccessLevel.READ],
                "actionable_files": [AccessLevel.READ],
                "configurations": [AccessLevel.READ],
            },
            "admin": {
                "audit_data": [
                    AccessLevel.READ,
                    AccessLevel.WRITE,
                    AccessLevel.DELETE,
                    AccessLevel.ADMIN,
                ],
                "reports": [
                    AccessLevel.READ,
                    AccessLevel.WRITE,
                    AccessLevel.DELETE,
                    AccessLevel.ADMIN,
                ],
                "actionable_files": [
                    AccessLevel.READ,
                    AccessLevel.WRITE,
                    AccessLevel.DELETE,
                    AccessLevel.ADMIN,
                ],
                "configurations": [
                    AccessLevel.READ,
                    AccessLevel.WRITE,
                    AccessLevel.DELETE,
                    AccessLevel.ADMIN,
                ],
            },
            "service_account": {
                "audit_data": [AccessLevel.READ, AccessLevel.WRITE],
                "reports": [AccessLevel.WRITE],
                "actionable_files": [AccessLevel.WRITE],
                "configurations": [AccessLevel.READ],
            },
        }

    def grant_permission(
        self,
        customer_id: str,
        user_id: str,
        resource_type: ResourceType,
        access_levels: List[AccessLevel],
        granted_by: str,
        duration_hours: Optional[int] = None,
        conditions: Optional[Dict[str, Any]] = None,
    ) -> CustomerAccessPermission:
        """
        Grant access permission to a user for customer resources.

        Args:
            customer_id: Customer ID
            user_id: User ID to grant permission to
            resource_type: Type of resource
            access_levels: List of access levels to grant
            granted_by: User granting the permission
            duration_hours: Permission duration in hours (None for permanent)
            conditions: Additional access conditions

        Returns:
            Created permission object
        """
        # Build resource path based on customer ID and resource type
        resource_path = self._build_resource_path(customer_id, resource_type)

        # Calculate expiration if duration specified
        expires_at = None
        if duration_hours:
            expires_at = datetime.now(timezone.utc) + timedelta(hours=duration_hours)

        permission = CustomerAccessPermission(
            customer_id=customer_id,
            user_id=user_id,
            resource_type=resource_type,
            resource_path=resource_path,
            access_levels=set(access_levels),
            granted_by=granted_by,
            expires_at=expires_at,
            conditions=conditions or {},
        )

        # Store permission
        self._store_permission(permission)

        logger.info(
            f"Permission granted: user={user_id}, customer={customer_id}, "
            f"resource={resource_type.value}, levels={[level.value for level in access_levels]}"
        )

        return permission

    def revoke_permission(
        self,
        customer_id: str,
        user_id: str,
        resource_type: Optional[ResourceType] = None,
    ) -> bool:
        """
        Revoke user permissions for customer resources.

        Args:
            customer_id: Customer ID
            user_id: User ID
            resource_type: Specific resource type to revoke (None for all)

        Returns:
            True if revocation successful
        """
        try:
            # Get existing permissions
            permissions = self.get_user_permissions(customer_id, user_id)

            # Filter permissions to revoke
            if resource_type:
                permissions = [
                    p for p in permissions if p.resource_type == resource_type
                ]

            # Mark permissions as inactive
            for permission in permissions:
                permission.is_active = False
                self._store_permission(permission)

            # Invalidate any active tokens
            self._invalidate_user_tokens(customer_id, user_id)

            logger.info(
                f"Permissions revoked: user={user_id}, customer={customer_id}, "
                f"resource={resource_type.value if resource_type else 'all'}"
            )

            return True

        except (ValueError, KeyError, AttributeError) as e:
            logger.error(f"Failed to revoke permissions: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error revoking permissions: {e}")
            raise

    def check_access(
        self,
        customer_id: str,
        user_id: str,
        resource_path: str,
        access_level: AccessLevel,
        context: Optional[Dict[str, Any]] = None,
    ) -> AccessDecision:
        """
        Check if user has access to a resource.

        Args:
            customer_id: Customer ID
            user_id: User ID
            resource_path: Resource path to access
            access_level: Required access level
            context: Additional context for access decision

        Returns:
            Access decision with details
        """
        # Get user permissions
        permissions = self.get_user_permissions(customer_id, user_id)

        # Check for matching permission
        for permission in permissions:
            if not permission.is_active:
                continue

            # Check expiration
            if permission.expires_at and permission.expires_at < datetime.now(
                timezone.utc
            ):
                continue

            # Check resource path match
            if not self._matches_resource_path(resource_path, permission.resource_path):
                continue

            # Check access level
            if access_level not in permission.access_levels:
                continue

            # Check conditions
            if not self._check_conditions(permission.conditions, context):
                continue

            # Access allowed
            return AccessDecision(
                allowed=True,
                reason="Permission granted",
                permissions=permission,
                restrictions=permission.conditions,
            )

        # No matching permission found
        return AccessDecision(
            allowed=False,
            reason="No valid permission found",
            permissions=None,
            restrictions={},
        )

    def generate_access_token(
        self,
        customer_id: str,
        user_id: str,
        duration_hours: int = DEFAULT_TOKEN_DURATION_HOURS,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> AccessToken:
        """
        Generate temporary access token for API operations.

        Args:
            customer_id: Customer ID
            user_id: User ID
            duration_hours: Token validity in hours
            ip_address: IP address restriction
            user_agent: User agent restriction

        Returns:
            Generated access token
        """
        # Get user permissions
        permissions = self.get_user_permissions(customer_id, user_id)

        if not permissions:
            raise ValueError(f"No permissions found for user {user_id}")

        # Generate secure token
        token_string = secrets.token_urlsafe(TOKEN_STRING_LENGTH)

        # Create token object
        token = AccessToken(
            token=token_string,
            customer_id=customer_id,
            user_id=user_id,
            permissions=permissions,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=duration_hours),
            ip_address=ip_address,
            user_agent=user_agent,
        )

        # Cache token
        self._token_cache[token_string] = token

        logger.info(
            f"Access token generated: user={user_id}, customer={customer_id}, "
            f"expires={token.expires_at.isoformat()}"
        )

        return token

    def validate_token(
        self,
        token_string: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Optional[AccessToken]:
        """
        Validate access token.

        Args:
            token_string: Token to validate
            ip_address: Request IP address
            user_agent: Request user agent

        Returns:
            Token object if valid, None otherwise
        """
        # Check cache
        token = self._token_cache.get(token_string)

        if not token:
            # Try to load from storage if available
            if self.storage:
                token = self._load_token(token_string)

            if not token:
                return None

        # Check expiration
        if token.expires_at < datetime.now(timezone.utc):
            del self._token_cache[token_string]
            return None

        # Check IP restriction
        if token.ip_address and ip_address != token.ip_address:
            logger.warning(
                f"Token validation failed: IP mismatch for token {token_string[:8]}..."
            )
            return None

        # Check user agent restriction
        if token.user_agent and user_agent != token.user_agent:
            logger.warning(
                f"Token validation failed: User agent mismatch for token {token_string[:8]}..."
            )
            return None

        return token

    def get_user_permissions(
        self, customer_id: str, user_id: str
    ) -> List[CustomerAccessPermission]:
        """
        Get all active permissions for a user.

        Args:
            customer_id: Customer ID
            user_id: User ID

        Returns:
            List of active permissions
        """
        cache_key = f"{customer_id}:{user_id}"

        # Check cache first
        if cache_key in self._permissions_cache:
            # Filter cached permissions for active and non-expired
            now = datetime.now(timezone.utc)
            active_permissions = []

            for permission in self._permissions_cache[cache_key]:
                if not permission.is_active:
                    continue
                if permission.expires_at and permission.expires_at < now:
                    continue
                active_permissions.append(permission)

            return active_permissions

        # If not in cache, try to load from storage
        if self.storage:
            permissions = self._load_permissions(customer_id, user_id)

            # Filter active and non-expired permissions
            active_permissions = []
            now = datetime.now(timezone.utc)

            for permission in permissions:
                if not permission.is_active:
                    continue
                if permission.expires_at and permission.expires_at < now:
                    continue
                active_permissions.append(permission)

            # Cache results
            self._permissions_cache[cache_key] = active_permissions
            return active_permissions

        # No storage and not in cache - return empty
        return []

    def get_customer_users(self, customer_id: str) -> List[Dict[str, Any]]:
        """
        Get all users with access to customer data.

        Args:
            customer_id: Customer ID

        Returns:
            List of users with their permissions
        """
        if not self.storage:
            return []

        # This would query the database for all users with permissions
        # for the given customer
        users = []

        # Placeholder for actual implementation
        logger.info(f"Retrieved users for customer: {customer_id}")

        return users

    def create_service_account(
        self, customer_id: str, service_name: str, permissions: List[ResourceType]
    ) -> Dict[str, Any]:
        """
        Create service account for automated operations.

        Args:
            customer_id: Customer ID
            service_name: Service account name
            permissions: List of resource types to grant access to

        Returns:
            Service account details including credentials
        """
        # Generate service account ID
        service_id = f"svc_{customer_id}_{service_name}_{secrets.token_hex(SERVICE_ID_TOKEN_LENGTH)}"

        # Generate API key
        api_key = secrets.token_urlsafe(API_KEY_LENGTH)

        # Grant permissions for each resource type
        for resource_type in permissions:
            access_levels = self._access_rules.get("service_account", {}).get(
                resource_type.value, []
            )

            self.grant_permission(
                customer_id=customer_id,
                user_id=service_id,
                resource_type=resource_type,
                access_levels=access_levels,
                granted_by="system",
            )

        service_account = {
            "service_id": service_id,
            "service_name": service_name,
            "customer_id": customer_id,
            "api_key": api_key,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "permissions": [r.value for r in permissions],
        }

        logger.info(f"Service account created: {service_id}")

        return service_account

    def _build_resource_path(
        self, customer_id: str, resource_type: ResourceType
    ) -> str:
        """Build resource path pattern for customer and resource type."""
        base_path = f"/customers/{customer_id}"

        resource_paths = {
            ResourceType.AUDIT_DATA: f"{base_path}/audits/*",
            ResourceType.REPORTS: f"{base_path}/reports/*",
            ResourceType.ACTIONABLE_FILES: f"{base_path}/actionable/*",
            ResourceType.CONFIGURATIONS: f"{base_path}/config/*",
        }

        return resource_paths.get(resource_type, f"{base_path}/*")

    def _matches_resource_path(self, requested_path: str, permission_path: str) -> bool:
        """Check if requested path matches permission path pattern."""
        # Convert wildcard pattern to regex
        import re

        # Escape special characters except *
        pattern = re.escape(permission_path).replace(r"\*", ".*")
        pattern = f"^{pattern}$"

        return bool(re.match(pattern, requested_path))

    def _check_conditions(
        self, conditions: Dict[str, Any], context: Optional[Dict[str, Any]]
    ) -> bool:
        """Check if access conditions are met."""
        if not conditions:
            return True

        if not context:
            return False

        # Check each condition
        for key, value in conditions.items():
            if key == "ip_ranges":
                # Check if request IP is in allowed ranges
                request_ip = context.get("ip_address")
                if not request_ip or not self._check_ip_range(request_ip, value):
                    return False

            elif key == "time_window":
                # Check if current time is within allowed window
                now = datetime.now(timezone.utc)
                start_time = datetime.fromisoformat(value.get("start"))
                end_time = datetime.fromisoformat(value.get("end"))
                if not (start_time <= now <= end_time):
                    return False

            elif key == "mfa_required":
                # Check if MFA was provided
                if value and not context.get("mfa_verified"):
                    return False

        return True

    def _check_ip_range(self, ip_address: str, allowed_ranges: List[str]) -> bool:
        """Check if IP address is in allowed ranges."""
        import ipaddress

        try:
            ip = ipaddress.ip_address(ip_address)

            for range_str in allowed_ranges:
                network = ipaddress.ip_network(range_str, strict=False)
                if ip in network:
                    return True

            return False

        except ValueError:
            logger.error(f"Invalid IP address: {ip_address}")
            return False

    def _store_permission(self, permission: CustomerAccessPermission) -> None:
        """Store permission in backend."""
        if self.storage:
            # Store in database
            pass

        # Update cache
        cache_key = f"{permission.customer_id}:{permission.user_id}"
        if cache_key not in self._permissions_cache:
            self._permissions_cache[cache_key] = []

        # Update or add permission
        existing = [
            p
            for p in self._permissions_cache[cache_key]
            if p.resource_type != permission.resource_type
        ]
        existing.append(permission)
        self._permissions_cache[cache_key] = existing

    def _load_permissions(
        self, customer_id: str, user_id: str
    ) -> List[CustomerAccessPermission]:
        """Load permissions from storage."""
        # Placeholder for database query
        return []

    def _load_token(self, token_string: str) -> Optional[AccessToken]:
        """Load token from storage."""
        # Placeholder for database query
        return None

    def _invalidate_user_tokens(self, customer_id: str, user_id: str) -> None:
        """Invalidate all tokens for a user."""
        tokens_to_remove = []

        for token_string, token in self._token_cache.items():
            if token.customer_id == customer_id and token.user_id == user_id:
                tokens_to_remove.append(token_string)

        for token_string in tokens_to_remove:
            del self._token_cache[token_string]

        logger.info(f"Invalidated {len(tokens_to_remove)} tokens for user {user_id}")

    def generate_data_isolation_key(
        self, customer_id: str, data_type: str, secret_key: str = "default-secret-key"
    ) -> str:
        """
        Generate unique key for customer data isolation.

        Args:
            customer_id: Customer ID
            data_type: Type of data
            secret_key: Secret key for hashing (optional)

        Returns:
            Unique isolation key
        """
        # Create deterministic key for data isolation
        key_data = f"{customer_id}:{data_type}:{secret_key}"
        return hashlib.sha256(key_data.encode()).hexdigest()[:DATA_ISOLATION_KEY_LENGTH]
