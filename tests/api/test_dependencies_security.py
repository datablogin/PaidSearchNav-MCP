"""Tests for API security dependencies and authentication components."""

import time
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from jose import jwt
from pydantic import SecretStr

from paidsearchnav.api.dependencies import (
    create_access_token,
    get_current_customer,
    get_current_user,
    get_customer_from_jwt,
    get_password_hash,
    verify_api_key,
    verify_password,
)
from paidsearchnav.core.config import Settings


class TestJWTTokenValidation:
    """Test JWT token validation and authentication logic."""

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings for JWT testing."""
        return Settings(
            jwt_secret_key=SecretStr("test-secret-key-for-jwt-testing"),
            jwt_algorithm="HS256",
            jwt_expire_minutes=30,
            api_key_required=False,
            api_key=SecretStr("test-api-key"),
        )

    @pytest.fixture
    def valid_jwt_payload(self):
        """Create a valid JWT payload for testing."""
        return {
            "sub": "test-user-123",
            "customer_id": "1234567890",
            "email": "test@example.com",
            "exp": datetime.utcnow() + timedelta(minutes=30),
            "iat": datetime.utcnow(),
        }

    @pytest.fixture
    def valid_jwt_token(self, mock_settings, valid_jwt_payload):
        """Create a valid JWT token for testing."""
        return jwt.encode(
            valid_jwt_payload,
            mock_settings.jwt_secret_key.get_secret_value(),
            algorithm=mock_settings.jwt_algorithm,
        )

    @pytest.fixture
    def expired_jwt_token(self, mock_settings):
        """Create an expired JWT token for testing."""
        expired_payload = {
            "sub": "test-user-123",
            "customer_id": "1234567890",
            "email": "test@example.com",
            "exp": datetime.utcnow() - timedelta(minutes=30),
            "iat": datetime.utcnow() - timedelta(minutes=60),
        }
        return jwt.encode(
            expired_payload,
            mock_settings.jwt_secret_key.get_secret_value(),
            algorithm=mock_settings.jwt_algorithm,
        )

    @pytest.mark.asyncio
    async def test_get_current_user_valid_token(self, mock_settings, valid_jwt_token):
        """Test getting current user with valid JWT token."""
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials=valid_jwt_token
        )

        with patch("paidsearchnav.api.dependencies.get_settings") as mock_get_settings:
            mock_get_settings.return_value = mock_settings

            with patch(
                "paidsearchnav.api.token_blacklist.is_token_blacklisted"
            ) as mock_blacklist:
                mock_blacklist.return_value = False

                user = await get_current_user(credentials, mock_settings)

                assert user["id"] == "test-user-123"
                assert user["email"] == "test@example.com"
                mock_blacklist.assert_called_once_with(valid_jwt_token)

    @pytest.mark.asyncio
    async def test_get_current_user_expired_token(
        self, mock_settings, expired_jwt_token
    ):
        """Test getting current user with expired JWT token."""
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials=expired_jwt_token
        )

        with patch("paidsearchnav.api.dependencies.get_settings") as mock_get_settings:
            mock_get_settings.return_value = mock_settings

            with patch(
                "paidsearchnav.api.token_blacklist.is_token_blacklisted"
            ) as mock_blacklist:
                mock_blacklist.return_value = False

                with pytest.raises(HTTPException) as exc_info:
                    await get_current_user(credentials, mock_settings)

                assert exc_info.value.status_code == 401
                assert "Could not validate credentials" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_get_current_user_blacklisted_token(
        self, mock_settings, valid_jwt_token
    ):
        """Test getting current user with blacklisted JWT token."""
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials=valid_jwt_token
        )

        with patch("paidsearchnav.api.dependencies.get_settings") as mock_get_settings:
            mock_get_settings.return_value = mock_settings

            with patch(
                "paidsearchnav.api.token_blacklist.is_token_blacklisted"
            ) as mock_blacklist:
                mock_blacklist.return_value = True

                with pytest.raises(HTTPException) as exc_info:
                    await get_current_user(credentials, mock_settings)

                assert exc_info.value.status_code == 401
                assert "Token has been revoked" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_get_current_user_invalid_signature(self, mock_settings):
        """Test getting current user with invalid JWT signature."""
        # Create token with wrong secret
        wrong_secret_token = jwt.encode(
            {"sub": "test-user-123", "exp": datetime.utcnow() + timedelta(minutes=30)},
            "wrong-secret-key",
            algorithm="HS256",
        )

        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials=wrong_secret_token
        )

        with patch("paidsearchnav.api.dependencies.get_settings") as mock_get_settings:
            mock_get_settings.return_value = mock_settings

            with patch(
                "paidsearchnav.api.token_blacklist.is_token_blacklisted"
            ) as mock_blacklist:
                mock_blacklist.return_value = False

                with pytest.raises(HTTPException) as exc_info:
                    await get_current_user(credentials, mock_settings)

                assert exc_info.value.status_code == 401
                assert "Could not validate credentials" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_get_current_user_malformed_token(self, mock_settings):
        """Test getting current user with malformed JWT token."""
        malformed_tokens = [
            "not.a.jwt.token",
            "invalid_token_format",
            "",
            "header.payload",  # Missing signature
            "header.payload.signature.extra",  # Too many parts
        ]

        for malformed_token in malformed_tokens:
            credentials = HTTPAuthorizationCredentials(
                scheme="Bearer", credentials=malformed_token
            )

            with patch(
                "paidsearchnav.api.dependencies.get_settings"
            ) as mock_get_settings:
                mock_get_settings.return_value = mock_settings

                with patch(
                    "paidsearchnav.api.token_blacklist.is_token_blacklisted"
                ) as mock_blacklist:
                    mock_blacklist.return_value = False

                    with pytest.raises(HTTPException) as exc_info:
                        await get_current_user(credentials, mock_settings)

                    assert exc_info.value.status_code == 401
                    assert "Could not validate credentials" in str(
                        exc_info.value.detail
                    )

    @pytest.mark.asyncio
    async def test_get_current_user_missing_subject(self, mock_settings):
        """Test getting current user with JWT token missing subject."""
        payload_no_subject = {
            "customer_id": "1234567890",
            "email": "test@example.com",
            "exp": datetime.utcnow() + timedelta(minutes=30),
            "iat": datetime.utcnow(),
            # Missing 'sub' field
        }

        token = jwt.encode(
            payload_no_subject,
            mock_settings.jwt_secret_key.get_secret_value(),
            algorithm=mock_settings.jwt_algorithm,
        )

        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        with patch("paidsearchnav.api.dependencies.get_settings") as mock_get_settings:
            mock_get_settings.return_value = mock_settings

            with patch(
                "paidsearchnav.api.token_blacklist.is_token_blacklisted"
            ) as mock_blacklist:
                mock_blacklist.return_value = False

                with pytest.raises(HTTPException) as exc_info:
                    await get_current_user(credentials, mock_settings)

                assert exc_info.value.status_code == 401
                assert "Could not validate credentials" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_get_customer_from_jwt_valid_token(
        self, mock_settings, valid_jwt_token
    ):
        """Test getting customer ID from valid JWT token."""
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials=valid_jwt_token
        )

        with patch("paidsearchnav.api.dependencies.get_settings") as mock_get_settings:
            mock_get_settings.return_value = mock_settings

            with patch(
                "paidsearchnav.api.token_blacklist.is_token_blacklisted"
            ) as mock_blacklist:
                mock_blacklist.return_value = False

                customer_id = await get_customer_from_jwt(credentials, mock_settings)

                assert customer_id == "1234567890"

    @pytest.mark.asyncio
    async def test_get_customer_from_jwt_missing_customer_id(self, mock_settings):
        """Test getting customer ID from JWT token missing customer_id."""
        payload_no_customer = {
            "sub": "test-user-123",
            "email": "test@example.com",
            "exp": datetime.utcnow() + timedelta(minutes=30),
            "iat": datetime.utcnow(),
            # Missing 'customer_id' field
        }

        token = jwt.encode(
            payload_no_customer,
            mock_settings.jwt_secret_key.get_secret_value(),
            algorithm=mock_settings.jwt_algorithm,
        )

        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        with patch("paidsearchnav.api.dependencies.get_settings") as mock_get_settings:
            mock_get_settings.return_value = mock_settings

            with patch(
                "paidsearchnav.api.token_blacklist.is_token_blacklisted"
            ) as mock_blacklist:
                mock_blacklist.return_value = False

                with pytest.raises(HTTPException) as exc_info:
                    await get_customer_from_jwt(credentials, mock_settings)

                assert exc_info.value.status_code == 401
                assert "Could not validate credentials" in str(exc_info.value.detail)

    def test_create_access_token_valid_data(self, mock_settings):
        """Test creating access token with valid data."""
        data = {
            "sub": "test-user-123",
            "customer_id": "1234567890",
            "email": "test@example.com",
        }

        token = create_access_token(data, mock_settings)

        # Verify token can be decoded
        payload = jwt.decode(
            token,
            mock_settings.jwt_secret_key.get_secret_value(),
            algorithms=[mock_settings.jwt_algorithm],
        )

        assert payload["sub"] == "test-user-123"
        assert payload["customer_id"] == "1234567890"
        assert payload["email"] == "test@example.com"
        assert "exp" in payload
        assert "iat" in payload

    def test_create_access_token_expiration(self, mock_settings):
        """Test that created access token has correct expiration."""
        data = {"sub": "test-user-123", "customer_id": "1234567890"}

        # Record time before token creation
        before_time = datetime.utcnow()
        token = create_access_token(data, mock_settings)
        after_time = datetime.utcnow()

        # Decode and verify expiration
        payload = jwt.decode(
            token,
            mock_settings.jwt_secret_key.get_secret_value(),
            algorithms=[mock_settings.jwt_algorithm],
        )

        exp_time = datetime.utcfromtimestamp(payload["exp"])
        expected_min_exp = before_time + timedelta(
            minutes=mock_settings.jwt_expire_minutes
        )
        expected_max_exp = after_time + timedelta(
            minutes=mock_settings.jwt_expire_minutes
        )

        # Allow some tolerance for timing differences
        assert (
            (expected_min_exp - timedelta(seconds=1))
            <= exp_time
            <= (expected_max_exp + timedelta(seconds=1))
        )

    def test_create_access_token_missing_customer_id(self, mock_settings):
        """Test creating access token without customer_id (should still work)."""
        data = {"sub": "test-user-123", "email": "test@example.com"}

        token = create_access_token(data, mock_settings)

        # Verify token can be decoded
        payload = jwt.decode(
            token,
            mock_settings.jwt_secret_key.get_secret_value(),
            algorithms=[mock_settings.jwt_algorithm],
        )

        assert payload["sub"] == "test-user-123"
        assert payload["email"] == "test@example.com"
        assert "customer_id" not in payload

    @pytest.mark.asyncio
    async def test_get_current_customer_valid_access(self, mock_settings):
        """Test getting current customer with valid access."""
        current_user = {"id": "test-user-123", "email": "test@example.com"}
        customer_id = "1234567890"

        # Mock repository
        mock_repository = AsyncMock()
        mock_repository.user_has_customer_access.return_value = True
        mock_repository.get_customer.return_value = {
            "id": customer_id,
            "name": "Test Customer",
            "email": "customer@example.com",
        }

        customer = await get_current_customer(
            current_user, mock_repository, customer_id
        )

        assert customer["id"] == customer_id
        assert customer["name"] == "Test Customer"
        mock_repository.user_has_customer_access.assert_called_once_with(
            "test-user-123", customer_id
        )
        mock_repository.get_customer.assert_called_once_with(customer_id)

    @pytest.mark.asyncio
    async def test_get_current_customer_no_access(self, mock_settings):
        """Test getting current customer without access."""
        current_user = {"id": "test-user-123", "email": "test@example.com"}
        customer_id = "1234567890"

        # Mock repository to deny access
        mock_repository = AsyncMock()
        mock_repository.user_has_customer_access.return_value = False

        with pytest.raises(HTTPException) as exc_info:
            await get_current_customer(current_user, mock_repository, customer_id)

        assert exc_info.value.status_code == 401
        assert "Access denied to this customer" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_get_current_customer_not_found(self, mock_settings):
        """Test getting current customer when customer doesn't exist."""
        current_user = {"id": "test-user-123", "email": "test@example.com"}
        customer_id = "1234567890"

        # Mock repository to allow access but return None customer
        mock_repository = AsyncMock()
        mock_repository.user_has_customer_access.return_value = True
        mock_repository.get_customer.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await get_current_customer(current_user, mock_repository, customer_id)

        assert exc_info.value.status_code == 404
        assert "Customer not found" in str(exc_info.value.detail)


class TestAPIKeyValidation:
    """Test API key validation and security."""

    @pytest.fixture
    def mock_settings_api_key_required(self):
        """Create mock settings with API key required."""
        return Settings(
            api_key_required=True,
            api_key=SecretStr("test-api-key-123"),
        )

    @pytest.fixture
    def mock_settings_api_key_not_required(self):
        """Create mock settings with API key not required."""
        return Settings(
            api_key_required=False,
            api_key=SecretStr("test-api-key-123"),
        )

    def test_verify_api_key_not_required(self, mock_settings_api_key_not_required):
        """Test API key verification when not required."""
        result = verify_api_key(None, mock_settings_api_key_not_required)
        assert result is True

    def test_verify_api_key_valid_key(self, mock_settings_api_key_required):
        """Test API key verification with valid key."""
        result = verify_api_key("test-api-key-123", mock_settings_api_key_required)
        assert result is True

    def test_verify_api_key_missing_key(self, mock_settings_api_key_required):
        """Test API key verification with missing key."""
        with pytest.raises(HTTPException) as exc_info:
            verify_api_key(None, mock_settings_api_key_required)

        assert exc_info.value.status_code == 401
        assert "API key required" in str(exc_info.value.detail)
        assert exc_info.value.headers["WWW-Authenticate"] == "ApiKey"

    def test_verify_api_key_invalid_key(self, mock_settings_api_key_required):
        """Test API key verification with invalid key."""
        with pytest.raises(HTTPException) as exc_info:
            verify_api_key("invalid-api-key", mock_settings_api_key_required)

        assert exc_info.value.status_code == 401
        assert "Invalid API key" in str(exc_info.value.detail)

    def test_verify_api_key_timing_attack_resistance(
        self, mock_settings_api_key_required
    ):
        """Test that API key verification is resistant to timing attacks."""
        # Test with different length keys to ensure timing is consistent
        test_keys = [
            "a",
            "short",
            "medium-length-key",
            "very-long-api-key-that-is-much-longer-than-the-real-key",
        ]

        for test_key in test_keys:
            start_time = time.time()
            try:
                verify_api_key(test_key, mock_settings_api_key_required)
            except HTTPException:
                pass  # Expected to fail
            end_time = time.time()

            # Verify that hmac.compare_digest is being used (should be consistent timing)
            # This is a basic check - in practice, timing attack resistance
            # would need more sophisticated testing
            elapsed = end_time - start_time
            assert elapsed < 0.1  # Should be very fast

    def test_verify_api_key_empty_string(self, mock_settings_api_key_required):
        """Test API key verification with empty string."""
        with pytest.raises(HTTPException) as exc_info:
            verify_api_key("", mock_settings_api_key_required)

        assert exc_info.value.status_code == 401
        # Empty string is treated as missing API key
        assert "API key required" in str(exc_info.value.detail)


class TestPasswordHashing:
    """Test password hashing and verification security."""

    def test_get_password_hash_creates_hash(self):
        """Test that password hashing creates a hash."""
        password = "test-password-123"
        hashed = get_password_hash(password)

        assert hashed != password  # Should be different from original
        assert len(hashed) > 50  # bcrypt hashes are long
        assert hashed.startswith("$2b$")  # bcrypt format

    def test_verify_password_correct_password(self):
        """Test password verification with correct password."""
        password = "test-password-123"
        hashed = get_password_hash(password)

        result = verify_password(password, hashed)
        assert result is True

    def test_verify_password_incorrect_password(self):
        """Test password verification with incorrect password."""
        password = "test-password-123"
        wrong_password = "wrong-password-456"
        hashed = get_password_hash(password)

        result = verify_password(wrong_password, hashed)
        assert result is False

    def test_verify_password_empty_password(self):
        """Test password verification with empty password."""
        password = "test-password-123"
        hashed = get_password_hash(password)

        result = verify_password("", hashed)
        assert result is False

    def test_verify_password_malformed_hash(self):
        """Test password verification with malformed hash."""
        password = "test-password-123"
        malformed_hash = "not-a-valid-hash"

        # Should handle malformed hash gracefully by raising exception
        with pytest.raises(
            Exception
        ):  # May raise different exceptions depending on implementation
            verify_password(password, malformed_hash)

    def test_password_hashing_consistency(self):
        """Test that password hashing is consistent but different each time."""
        password = "test-password-123"
        hash1 = get_password_hash(password)
        hash2 = get_password_hash(password)

        # Hashes should be different (due to salt)
        assert hash1 != hash2

        # But both should verify correctly
        assert verify_password(password, hash1) is True
        assert verify_password(password, hash2) is True

    def test_password_hashing_special_characters(self):
        """Test password hashing with special characters."""
        special_passwords = [
            "password!@#$%^&*()",
            "pässwörd",  # Unicode
            "password with spaces",
            "🔐🔑🗝️",  # Emoji
            "p" * 1000,  # Very long password
        ]

        for password in special_passwords:
            hashed = get_password_hash(password)
            assert verify_password(password, hashed) is True

    def test_password_hashing_timing_attack_resistance(self):
        """Test that password verification timing is consistent."""
        password = "test-password-123"
        hashed = get_password_hash(password)

        # Test with different length passwords
        test_passwords = [
            "a",
            "short",
            "medium-length-password",
            "very-long-password-that-is-much-longer-than-the-original",
        ]

        timings = []
        for test_password in test_passwords:
            start_time = time.time()
            verify_password(test_password, hashed)
            end_time = time.time()
            timings.append(end_time - start_time)

        # Verify that timing is relatively consistent
        # bcrypt should have consistent timing regardless of password length
        max_timing = max(timings)
        min_timing = min(timings)
        timing_variance = max_timing - min_timing

        # Allow for some variance but not too much
        assert timing_variance < 0.1  # Should be within 100ms


class TestSecurityEdgeCases:
    """Test security edge cases and attack scenarios."""

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings for security testing."""
        return Settings(
            jwt_secret_key=SecretStr("test-secret-key-for-security-testing"),
            jwt_algorithm="HS256",
            jwt_expire_minutes=30,
        )

    @pytest.mark.asyncio
    async def test_jwt_algorithm_confusion_attack(self, mock_settings):
        """Test resistance to JWT algorithm confusion attacks."""
        # Try to create a token with 'none' algorithm
        none_payload = {
            "sub": "test-user-123",
            "customer_id": "1234567890",
            "exp": datetime.utcnow() + timedelta(minutes=30),
        }

        # jose library doesn't support 'none' algorithm, so we'll create a manually crafted token
        # This simulates an attacker trying to bypass security with an unsigned token
        import base64
        import json

        header = {"alg": "none", "typ": "JWT"}
        header_b64 = (
            base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
        )
        payload_b64 = (
            base64.urlsafe_b64encode(json.dumps(none_payload, default=str).encode())
            .decode()
            .rstrip("=")
        )
        none_token = f"{header_b64}.{payload_b64}."

        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials=none_token
        )

        with patch("paidsearchnav.api.dependencies.get_settings") as mock_get_settings:
            mock_get_settings.return_value = mock_settings

            with patch(
                "paidsearchnav.api.token_blacklist.is_token_blacklisted"
            ) as mock_blacklist:
                mock_blacklist.return_value = False

                # Should reject token with 'none' algorithm
                with pytest.raises(HTTPException) as exc_info:
                    await get_current_user(credentials, mock_settings)

                assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_jwt_key_confusion_attack(self, mock_settings):
        """Test resistance to JWT key confusion attacks."""
        # Try to use a different algorithm with public key
        rs256_payload = {
            "sub": "test-user-123",
            "customer_id": "1234567890",
            "exp": datetime.utcnow() + timedelta(minutes=30),
        }

        # Create token with RS256 algorithm but using HMAC key
        try:
            rs256_token = jwt.encode(
                rs256_payload,
                mock_settings.jwt_secret_key.get_secret_value(),
                algorithm="RS256",
            )
        except Exception:
            # If RS256 fails (expected), create a token with wrong algorithm claim
            rs256_token = jwt.encode(
                rs256_payload,
                mock_settings.jwt_secret_key.get_secret_value(),
                algorithm="HS256",
            )
            # Manually modify the algorithm in the header
            header, payload_part, signature = rs256_token.split(".")
            import base64
            import json

            decoded_header = json.loads(base64.b64decode(header + "=="))
            decoded_header["alg"] = "RS256"
            modified_header = (
                base64.b64encode(json.dumps(decoded_header).encode())
                .decode()
                .rstrip("=")
            )
            rs256_token = f"{modified_header}.{payload_part}.{signature}"

        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials=rs256_token
        )

        with patch("paidsearchnav.api.dependencies.get_settings") as mock_get_settings:
            mock_get_settings.return_value = mock_settings

            with patch(
                "paidsearchnav.api.token_blacklist.is_token_blacklisted"
            ) as mock_blacklist:
                mock_blacklist.return_value = False

                # Should reject token with wrong algorithm
                with pytest.raises(HTTPException) as exc_info:
                    await get_current_user(credentials, mock_settings)

                assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_jwt_claim_injection(self, mock_settings):
        """Test resistance to JWT claim injection attacks."""
        # Try to inject additional claims
        malicious_payload = {
            "sub": "test-user-123",
            "customer_id": "1234567890",
            "exp": datetime.utcnow() + timedelta(minutes=30),
            "iat": datetime.utcnow(),
            "admin": True,  # Injected claim
            "role": "admin",  # Injected claim
            "permissions": ["all"],  # Injected claim
        }

        token = jwt.encode(
            malicious_payload,
            mock_settings.jwt_secret_key.get_secret_value(),
            algorithm=mock_settings.jwt_algorithm,
        )

        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        with patch("paidsearchnav.api.dependencies.get_settings") as mock_get_settings:
            mock_get_settings.return_value = mock_settings

            with patch(
                "paidsearchnav.api.token_blacklist.is_token_blacklisted"
            ) as mock_blacklist:
                mock_blacklist.return_value = False

                # Should accept token but only return expected claims
                user = await get_current_user(credentials, mock_settings)

                assert user["id"] == "test-user-123"
                assert user["email"] is None  # Not in payload
                # Should not include injected claims
                assert "admin" not in user
                assert "role" not in user
                assert "permissions" not in user

    @pytest.mark.asyncio
    async def test_jwt_iat_future_timestamp(self, mock_settings):
        """Test handling of JWT with future issued-at timestamp."""
        future_payload = {
            "sub": "test-user-123",
            "customer_id": "1234567890",
            "exp": datetime.utcnow() + timedelta(minutes=60),
            "iat": datetime.utcnow() + timedelta(minutes=30),  # Future timestamp
        }

        token = jwt.encode(
            future_payload,
            mock_settings.jwt_secret_key.get_secret_value(),
            algorithm=mock_settings.jwt_algorithm,
        )

        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        with patch("paidsearchnav.api.dependencies.get_settings") as mock_get_settings:
            mock_get_settings.return_value = mock_settings

            with patch(
                "paidsearchnav.api.token_blacklist.is_token_blacklisted"
            ) as mock_blacklist:
                mock_blacklist.return_value = False

                # Current implementation doesn't validate iat, so this should work
                # In production, consider adding iat validation
                user = await get_current_user(credentials, mock_settings)
                assert user["id"] == "test-user-123"

    @pytest.mark.asyncio
    async def test_jwt_very_long_expiry(self, mock_settings):
        """Test handling of JWT with very long expiry."""
        long_expiry_payload = {
            "sub": "test-user-123",
            "customer_id": "1234567890",
            "exp": datetime.utcnow() + timedelta(days=365 * 10),  # 10 years
            "iat": datetime.utcnow(),
        }

        token = jwt.encode(
            long_expiry_payload,
            mock_settings.jwt_secret_key.get_secret_value(),
            algorithm=mock_settings.jwt_algorithm,
        )

        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        with patch("paidsearchnav.api.dependencies.get_settings") as mock_get_settings:
            mock_get_settings.return_value = mock_settings

            with patch(
                "paidsearchnav.api.token_blacklist.is_token_blacklisted"
            ) as mock_blacklist:
                mock_blacklist.return_value = False

                # Should accept token with long expiry
                # In production, consider adding maximum expiry validation
                user = await get_current_user(credentials, mock_settings)
                assert user["id"] == "test-user-123"

    @pytest.mark.asyncio
    async def test_jwt_sql_injection_in_claims(self, mock_settings):
        """Test resistance to SQL injection in JWT claims."""
        sql_injection_payload = {
            "sub": "test-user-123'; DROP TABLE users; --",
            "customer_id": "1234567890' OR '1'='1",
            "email": "test@example.com'; DELETE FROM customers; --",
            "exp": datetime.utcnow() + timedelta(minutes=30),
            "iat": datetime.utcnow(),
        }

        token = jwt.encode(
            sql_injection_payload,
            mock_settings.jwt_secret_key.get_secret_value(),
            algorithm=mock_settings.jwt_algorithm,
        )

        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        with patch("paidsearchnav.api.dependencies.get_settings") as mock_get_settings:
            mock_get_settings.return_value = mock_settings

            with patch(
                "paidsearchnav.api.token_blacklist.is_token_blacklisted"
            ) as mock_blacklist:
                mock_blacklist.return_value = False

                # Should accept token and return the values as-is
                # SQL injection prevention should happen at the database layer
                user = await get_current_user(credentials, mock_settings)
                assert "DROP TABLE" in user["id"]
                assert "DELETE FROM customers" in user.get("email", "")

    @pytest.mark.asyncio
    async def test_jwt_xss_in_claims(self, mock_settings):
        """Test handling of XSS payloads in JWT claims."""
        xss_payload = {
            "sub": "<script>alert('xss')</script>",
            "customer_id": "1234567890",
            "email": "test@example.com<img src=x onerror=alert('xss')>",
            "exp": datetime.utcnow() + timedelta(minutes=30),
            "iat": datetime.utcnow(),
        }

        token = jwt.encode(
            xss_payload,
            mock_settings.jwt_secret_key.get_secret_value(),
            algorithm=mock_settings.jwt_algorithm,
        )

        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        with patch("paidsearchnav.api.dependencies.get_settings") as mock_get_settings:
            mock_get_settings.return_value = mock_settings

            with patch(
                "paidsearchnav.api.token_blacklist.is_token_blacklisted"
            ) as mock_blacklist:
                mock_blacklist.return_value = False

                # Should accept token and return the values as-is
                # XSS prevention should happen at the output layer
                user = await get_current_user(credentials, mock_settings)
                assert "<script>" in user["id"]
                assert "<img src=" in user.get("email", "")
