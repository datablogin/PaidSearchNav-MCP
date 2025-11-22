"""JWT token management for authentication and authorization."""

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import jwt
from passlib.context import CryptContext
from pydantic import BaseModel, Field, field_validator

from paidsearchnav.core.config import get_settings
from paidsearchnav.core.exceptions import AuthenticationError

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class TokenData(BaseModel):
    """Token payload data structure."""

    sub: str  # Subject (user ID)
    email: str
    role: str = "customer"
    exp: Optional[datetime] = None
    iat: Optional[datetime] = None
    jti: Optional[str] = None  # JWT ID for token revocation
    token_type: str = "access"
    scopes: list[str] = Field(default_factory=list)

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        """Validate role value."""
        valid_roles = {"admin", "customer", "read_only"}
        if v not in valid_roles:
            raise ValueError(f"Invalid role: {v}")
        return v

    @field_validator("token_type")
    @classmethod
    def validate_token_type(cls, v: str) -> str:
        """Validate token type."""
        valid_types = {"access", "refresh", "api_key"}
        if v not in valid_types:
            raise ValueError(f"Invalid token type: {v}")
        return v


class JWTManager:
    """Manages JWT token creation, validation, and refresh."""

    def __init__(
        self,
        secret_key: Optional[str] = None,
        algorithm: str = "HS256",
        access_token_expire_minutes: int = 30,
        refresh_token_expire_days: int = 7,
    ):
        """Initialize JWT Manager.

        Args:
            secret_key: Secret key for token signing
            algorithm: JWT signing algorithm
            access_token_expire_minutes: Access token expiration time in minutes
            refresh_token_expire_days: Refresh token expiration time in days
        """
        if secret_key:
            self.secret_key = secret_key
        else:
            settings = get_settings()
            self.secret_key = (
                settings.jwt_secret_key.get_secret_value()
                if settings.jwt_secret_key
                else None
            )
        if not self.secret_key:
            raise ValueError("SECRET_KEY must be set for JWT authentication")

        self.algorithm = algorithm
        self.access_token_expire = timedelta(minutes=access_token_expire_minutes)
        self.refresh_token_expire = timedelta(days=refresh_token_expire_days)

    def create_access_token(
        self,
        user_id: str,
        email: str,
        role: str = "customer",
        scopes: Optional[list[str]] = None,
        expires_delta: Optional[timedelta] = None,
    ) -> str:
        """Create a new access token.

        Args:
            user_id: User ID to encode in token
            email: User email address
            role: User role
            scopes: List of permission scopes
            expires_delta: Optional custom expiration time

        Returns:
            Encoded JWT access token
        """
        now = datetime.now(timezone.utc)
        expire = now + (expires_delta or self.access_token_expire)

        token_data = TokenData(
            sub=user_id,
            email=email,
            role=role,
            exp=expire,
            iat=now,
            jti=secrets.token_urlsafe(32),
            token_type="access",
            scopes=scopes or [],
        )

        return jwt.encode(
            token_data.model_dump(exclude_none=True),
            self.secret_key,
            algorithm=self.algorithm,
        )

    def create_refresh_token(
        self,
        user_id: str,
        email: str,
        expires_delta: Optional[timedelta] = None,
    ) -> str:
        """Create a new refresh token.

        Args:
            user_id: User ID to encode in token
            email: User email address
            expires_delta: Optional custom expiration time

        Returns:
            Encoded JWT refresh token
        """
        now = datetime.now(timezone.utc)
        expire = now + (expires_delta or self.refresh_token_expire)

        token_data = {
            "sub": user_id,
            "email": email,
            "exp": expire,
            "iat": now,
            "jti": secrets.token_urlsafe(32),
            "token_type": "refresh",
        }

        return jwt.encode(token_data, self.secret_key, algorithm=self.algorithm)

    def create_api_key_token(
        self,
        user_id: str,
        key_id: str,
        scopes: Optional[list[str]] = None,
        expires_at: Optional[datetime] = None,
    ) -> str:
        """Create an API key token.

        Args:
            user_id: User ID who owns the API key
            key_id: API key ID
            scopes: List of permission scopes
            expires_at: Optional expiration time

        Returns:
            Encoded JWT API key token
        """
        now = datetime.now(timezone.utc)

        token_data = {
            "sub": user_id,
            "key_id": key_id,
            "iat": now,
            "token_type": "api_key",
            "scopes": scopes or [],
        }

        if expires_at:
            token_data["exp"] = expires_at

        return jwt.encode(token_data, self.secret_key, algorithm=self.algorithm)

    def decode_token(self, token: str) -> Dict[str, Any]:
        """Decode and validate a JWT token.

        Args:
            token: JWT token to decode

        Returns:
            Decoded token payload

        Raises:
            AuthenticationError: If token is invalid or expired
        """
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
                options={"verify_exp": True},
            )
            return payload
        except jwt.ExpiredSignatureError:
            raise AuthenticationError("Token has expired")
        except jwt.InvalidTokenError as e:
            raise AuthenticationError(f"Invalid token: {str(e)}")

    def verify_token(self, token: str, token_type: str = "access") -> TokenData:
        """Verify a token and return structured data.

        Args:
            token: JWT token to verify
            token_type: Expected token type

        Returns:
            TokenData object with token information

        Raises:
            AuthenticationError: If token is invalid
        """
        payload = self.decode_token(token)

        if payload.get("token_type") != token_type:
            raise AuthenticationError(
                f"Invalid token type. Expected {token_type}, got {payload.get('token_type')}"
            )

        try:
            # Convert exp and iat to datetime if they're timestamps
            if isinstance(payload.get("exp"), (int, float)):
                payload["exp"] = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
            if isinstance(payload.get("iat"), (int, float)):
                payload["iat"] = datetime.fromtimestamp(payload["iat"], tz=timezone.utc)

            return TokenData(**payload)
        except Exception as e:
            raise AuthenticationError(f"Invalid token structure: {str(e)}")

    def refresh_access_token(self, refresh_token: str) -> tuple[str, str]:
        """Generate new access and refresh tokens from a refresh token.

        Args:
            refresh_token: Valid refresh token

        Returns:
            Tuple of (new_access_token, new_refresh_token)

        Raises:
            AuthenticationError: If refresh token is invalid
        """
        payload = self.decode_token(refresh_token)

        if payload.get("token_type") != "refresh":
            raise AuthenticationError("Invalid token type for refresh")

        # Create new tokens
        new_access = self.create_access_token(
            user_id=payload["sub"],
            email=payload["email"],
            role=payload.get("role", "customer"),
            scopes=payload.get("scopes", []),
        )

        new_refresh = self.create_refresh_token(
            user_id=payload["sub"],
            email=payload["email"],
        )

        return new_access, new_refresh

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password for storage.

        Args:
            password: Plain text password

        Returns:
            Hashed password
        """
        return pwd_context.hash(password)

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash.

        Args:
            plain_password: Plain text password to verify
            hashed_password: Hashed password from storage

        Returns:
            True if password matches, False otherwise
        """
        return pwd_context.verify(plain_password, hashed_password)

    @staticmethod
    def generate_api_key() -> str:
        """Generate a secure API key.

        Returns:
            Random API key string
        """
        return f"psn_{secrets.token_urlsafe(32)}"

    @staticmethod
    def hash_api_key(api_key: str) -> str:
        """Hash an API key for storage.

        Args:
            api_key: Plain text API key

        Returns:
            Hashed API key
        """
        # Use a simpler hash for API keys since they're random
        import hashlib

        return hashlib.sha256(api_key.encode()).hexdigest()


# Global JWT manager instance (lazy-loaded)
_jwt_manager: Optional[JWTManager] = None


def get_jwt_manager() -> JWTManager:
    """Get or create the global JWT manager instance."""
    global _jwt_manager
    if _jwt_manager is None:
        _jwt_manager = JWTManager()
    return _jwt_manager


# For backward compatibility
jwt_manager = get_jwt_manager()
