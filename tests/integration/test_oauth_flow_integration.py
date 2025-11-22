"""Integration tests for OAuth2 authentication flow with minimal dependencies."""

import asyncio
import json
import time
from datetime import datetime, timedelta, timezone

import httpx
import pytest
import respx


@pytest.fixture
def oauth_settings_dict():
    """OAuth settings as a dictionary to avoid import issues."""
    return {
        "google_ads": {
            "client_id": "test_client_id",
            "client_secret": "test_client_secret",
            "developer_token": "test_developer_token",
        }
    }


@pytest.fixture
def mock_oauth_server():
    """Mock OAuth2 server responses for integration testing."""

    class MockOAuthServer:
        def __init__(self):
            self.device_codes = {}
            self.access_tokens = {}
            self.refresh_tokens = {}
            self.user_codes = {}

        def create_device_code_response(self, client_id: str) -> dict:
            """Create device code response."""
            device_code = f"device_code_{int(time.time())}"
            user_code = f"TEST-{int(time.time()) % 10000:04d}"

            self.device_codes[device_code] = {
                "client_id": client_id,
                "user_code": user_code,
                "expires_at": datetime.now(timezone.utc) + timedelta(minutes=15),
                "authorized": False,
                "interval": 5,
            }
            self.user_codes[user_code] = device_code

            return {
                "device_code": device_code,
                "user_code": user_code,
                "verification_url": "https://www.google.com/device",
                "verification_url_complete": f"https://www.google.com/device?user_code={user_code}",
                "expires_in": 900,
                "interval": 5,
            }

        def authorize_device_code(self, user_code: str) -> bool:
            """Simulate user authorizing device code."""
            if user_code in self.user_codes:
                device_code = self.user_codes[user_code]
                if device_code in self.device_codes:
                    self.device_codes[device_code]["authorized"] = True
                    return True
            return False

        def create_token_response(self, grant_type: str, **kwargs) -> dict:
            """Create token response for various grant types."""
            if grant_type == "urn:ietf:params:oauth:grant-type:device_code":
                device_code = kwargs.get("device_code")
                if device_code not in self.device_codes:
                    return {"error": "invalid_grant"}

                device_info = self.device_codes[device_code]
                if datetime.now(timezone.utc) > device_info["expires_at"]:
                    return {"error": "expired_token"}

                if not device_info["authorized"]:
                    return {"error": "authorization_pending"}

                # Generate tokens
                access_token = f"access_token_{int(time.time())}"
                refresh_token = f"refresh_token_{int(time.time())}"

                self.access_tokens[access_token] = {
                    "client_id": device_info["client_id"],
                    "expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
                    "refresh_token": refresh_token,
                }
                self.refresh_tokens[refresh_token] = {
                    "client_id": device_info["client_id"],
                    "access_token": access_token,
                }

                return {
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "token_type": "Bearer",
                    "expires_in": 3600,
                    "scope": "https://www.googleapis.com/auth/adwords",
                }

            elif grant_type == "refresh_token":
                refresh_token = kwargs.get("refresh_token")
                if refresh_token not in self.refresh_tokens:
                    return {"error": "invalid_grant"}

                refresh_info = self.refresh_tokens[refresh_token]
                new_access_token = f"new_access_token_{int(time.time())}"

                self.access_tokens[new_access_token] = {
                    "client_id": refresh_info["client_id"],
                    "expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
                    "refresh_token": refresh_token,
                }

                return {
                    "access_token": new_access_token,
                    "token_type": "Bearer",
                    "expires_in": 3600,
                    "scope": "https://www.googleapis.com/auth/adwords",
                }

            elif grant_type == "authorization_code":
                code = kwargs.get("code")
                if code == "valid_auth_code":
                    access_token = f"browser_access_token_{int(time.time())}"
                    refresh_token = f"browser_refresh_token_{int(time.time())}"

                    self.access_tokens[access_token] = {
                        "client_id": kwargs.get("client_id"),
                        "expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
                        "refresh_token": refresh_token,
                    }
                    self.refresh_tokens[refresh_token] = {
                        "client_id": kwargs.get("client_id"),
                        "access_token": access_token,
                    }

                    return {
                        "access_token": access_token,
                        "refresh_token": refresh_token,
                        "token_type": "Bearer",
                        "expires_in": 3600,
                        "scope": "https://www.googleapis.com/auth/adwords",
                    }
                else:
                    return {"error": "invalid_grant"}

            return {"error": "unsupported_grant_type"}

        def revoke_token(self, token: str) -> bool:
            """Revoke a token."""
            if token in self.access_tokens:
                del self.access_tokens[token]
                return True
            if token in self.refresh_tokens:
                # Also remove the associated access token
                refresh_info = self.refresh_tokens[token]
                associated_access_token = refresh_info.get("access_token")
                if (
                    associated_access_token
                    and associated_access_token in self.access_tokens
                ):
                    del self.access_tokens[associated_access_token]
                del self.refresh_tokens[token]
                return True
            return False

        def is_token_valid(self, token: str) -> bool:
            """Check if access token is valid."""
            if token not in self.access_tokens:
                return False
            token_info = self.access_tokens[token]
            return datetime.now(timezone.utc) < token_info["expires_at"]

    return MockOAuthServer()


class TestOAuth2DeviceFlowIntegration:
    """Integration tests for OAuth2 device flow without heavy imports."""

    @pytest.mark.asyncio
    async def test_device_code_generation_flow(self, mock_oauth_server):
        """Test device code generation and user authorization flow."""

        def mock_device_code_request(request):
            """Mock device code endpoint."""
            data = dict(httpx.QueryParams(request.content.decode()))
            return httpx.Response(
                200,
                json=mock_oauth_server.create_device_code_response(data["client_id"]),
            )

        with respx.mock:
            respx.post("https://oauth2.googleapis.com/device/code").mock(
                side_effect=mock_device_code_request
            )

            # Simulate device code request
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://oauth2.googleapis.com/device/code",
                    data={
                        "client_id": "test_client_id",
                        "scope": "https://www.googleapis.com/auth/adwords",
                    },
                )

                assert response.status_code == 200
                device_data = response.json()

                assert "device_code" in device_data
                assert "user_code" in device_data
                assert "verification_url" in device_data
                assert device_data["expires_in"] == 900
                assert device_data["interval"] == 5

                # Verify device code is stored
                device_code = device_data["device_code"]
                user_code = device_data["user_code"]

                assert device_code in mock_oauth_server.device_codes
                assert user_code in mock_oauth_server.user_codes

                # Simulate user authorization
                auth_success = mock_oauth_server.authorize_device_code(user_code)
                assert auth_success is True

    @pytest.mark.asyncio
    async def test_device_flow_token_polling(self, mock_oauth_server):
        """Test polling for tokens after device authorization."""

        def mock_device_code_request(request):
            """Mock device code endpoint."""
            data = dict(httpx.QueryParams(request.content.decode()))
            return httpx.Response(
                200,
                json=mock_oauth_server.create_device_code_response(data["client_id"]),
            )

        def mock_token_request(request):
            """Mock token endpoint."""
            data = dict(httpx.QueryParams(request.content.decode()))
            response_data = mock_oauth_server.create_token_response(**data)
            status_code = 200 if "error" not in response_data else 400
            return httpx.Response(status_code, json=response_data)

        with respx.mock:
            respx.post("https://oauth2.googleapis.com/device/code").mock(
                side_effect=mock_device_code_request
            )
            respx.post("https://oauth2.googleapis.com/token").mock(
                side_effect=mock_token_request
            )

            async with httpx.AsyncClient() as client:
                # Get device code
                device_response = await client.post(
                    "https://oauth2.googleapis.com/device/code",
                    data={
                        "client_id": "test_client_id",
                        "scope": "https://www.googleapis.com/auth/adwords",
                    },
                )
                device_data = device_response.json()

                # First polling attempt - should be pending
                token_response = await client.post(
                    "https://oauth2.googleapis.com/token",
                    data={
                        "client_id": "test_client_id",
                        "client_secret": "test_client_secret",
                        "device_code": device_data["device_code"],
                        "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                    },
                )

                assert token_response.status_code == 400
                token_data = token_response.json()
                assert token_data["error"] == "authorization_pending"

                # Authorize the device code
                mock_oauth_server.authorize_device_code(device_data["user_code"])

                # Second polling attempt - should succeed
                token_response = await client.post(
                    "https://oauth2.googleapis.com/token",
                    data={
                        "client_id": "test_client_id",
                        "client_secret": "test_client_secret",
                        "device_code": device_data["device_code"],
                        "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                    },
                )

                assert token_response.status_code == 200
                token_data = token_response.json()

                assert "access_token" in token_data
                assert "refresh_token" in token_data
                assert token_data["token_type"] == "Bearer"
                assert token_data["expires_in"] == 3600

    @pytest.mark.asyncio
    async def test_device_flow_timeout_scenario(self, mock_oauth_server):
        """Test device flow timeout scenario."""

        def mock_device_code_request(request):
            """Mock device code endpoint with short timeout."""
            data = dict(httpx.QueryParams(request.content.decode()))
            response = mock_oauth_server.create_device_code_response(data["client_id"])
            # Manually expire the device code
            device_code = response["device_code"]
            mock_oauth_server.device_codes[device_code]["expires_at"] = datetime.now(
                timezone.utc
            ) - timedelta(minutes=1)
            return httpx.Response(200, json=response)

        def mock_token_request(request):
            """Mock token endpoint."""
            data = dict(httpx.QueryParams(request.content.decode()))
            response_data = mock_oauth_server.create_token_response(**data)
            status_code = 200 if "error" not in response_data else 400
            return httpx.Response(status_code, json=response_data)

        with respx.mock:
            respx.post("https://oauth2.googleapis.com/device/code").mock(
                side_effect=mock_device_code_request
            )
            respx.post("https://oauth2.googleapis.com/token").mock(
                side_effect=mock_token_request
            )

            async with httpx.AsyncClient() as client:
                # Get device code
                device_response = await client.post(
                    "https://oauth2.googleapis.com/device/code",
                    data={
                        "client_id": "test_client_id",
                        "scope": "https://www.googleapis.com/auth/adwords",
                    },
                )
                device_data = device_response.json()

                # Try to get token with expired device code
                token_response = await client.post(
                    "https://oauth2.googleapis.com/token",
                    data={
                        "client_id": "test_client_id",
                        "client_secret": "test_client_secret",
                        "device_code": device_data["device_code"],
                        "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                    },
                )

                assert token_response.status_code == 400
                token_data = token_response.json()
                assert token_data["error"] == "expired_token"


class TestOAuth2TokenRefreshIntegration:
    """Integration tests for token refresh functionality."""

    @pytest.mark.asyncio
    async def test_token_refresh_success(self, mock_oauth_server):
        """Test successful token refresh."""

        # Pre-populate refresh token
        refresh_token = "test_refresh_token_123"
        mock_oauth_server.refresh_tokens[refresh_token] = {
            "client_id": "test_client_id",
            "access_token": "old_access_token",
        }

        def mock_token_request(request):
            """Mock token endpoint."""
            data = dict(httpx.QueryParams(request.content.decode()))
            response_data = mock_oauth_server.create_token_response(**data)
            status_code = 200 if "error" not in response_data else 400
            return httpx.Response(status_code, json=response_data)

        with respx.mock:
            respx.post("https://oauth2.googleapis.com/token").mock(
                side_effect=mock_token_request
            )

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://oauth2.googleapis.com/token",
                    data={
                        "client_id": "test_client_id",
                        "client_secret": "test_client_secret",
                        "refresh_token": refresh_token,
                        "grant_type": "refresh_token",
                    },
                )

                assert response.status_code == 200
                token_data = response.json()

                assert "access_token" in token_data
                assert token_data["access_token"].startswith("new_access_token_")
                assert token_data["token_type"] == "Bearer"
                assert token_data["expires_in"] == 3600

    @pytest.mark.asyncio
    async def test_token_refresh_invalid_refresh_token(self, mock_oauth_server):
        """Test token refresh with invalid refresh token."""

        def mock_token_request(request):
            """Mock token endpoint."""
            data = dict(httpx.QueryParams(request.content.decode()))
            response_data = mock_oauth_server.create_token_response(**data)
            status_code = 200 if "error" not in response_data else 400
            return httpx.Response(status_code, json=response_data)

        with respx.mock:
            respx.post("https://oauth2.googleapis.com/token").mock(
                side_effect=mock_token_request
            )

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://oauth2.googleapis.com/token",
                    data={
                        "client_id": "test_client_id",
                        "client_secret": "test_client_secret",
                        "refresh_token": "invalid_refresh_token",
                        "grant_type": "refresh_token",
                    },
                )

                assert response.status_code == 400
                error_data = response.json()
                assert error_data["error"] == "invalid_grant"


class TestOAuth2BrowserFlowIntegration:
    """Integration tests for OAuth2 browser flow."""

    @pytest.mark.asyncio
    async def test_browser_flow_authorization_code_exchange(self, mock_oauth_server):
        """Test browser flow authorization code to token exchange."""

        def mock_token_request(request):
            """Mock token endpoint."""
            data = dict(httpx.QueryParams(request.content.decode()))
            response_data = mock_oauth_server.create_token_response(**data)
            status_code = 200 if "error" not in response_data else 400
            return httpx.Response(status_code, json=response_data)

        with respx.mock:
            respx.post("https://oauth2.googleapis.com/token").mock(
                side_effect=mock_token_request
            )

            async with httpx.AsyncClient() as client:
                # Exchange valid authorization code
                response = await client.post(
                    "https://oauth2.googleapis.com/token",
                    data={
                        "code": "valid_auth_code",
                        "client_id": "test_client_id",
                        "client_secret": "test_client_secret",
                        "redirect_uri": "http://localhost:3000/callback",
                        "grant_type": "authorization_code",
                    },
                )

                assert response.status_code == 200
                token_data = response.json()

                assert "access_token" in token_data
                assert "refresh_token" in token_data
                assert token_data["access_token"].startswith("browser_access_token_")
                assert token_data["refresh_token"].startswith("browser_refresh_token_")

    @pytest.mark.asyncio
    async def test_browser_flow_invalid_authorization_code(self, mock_oauth_server):
        """Test browser flow with invalid authorization code."""

        def mock_token_request(request):
            """Mock token endpoint."""
            data = dict(httpx.QueryParams(request.content.decode()))
            response_data = mock_oauth_server.create_token_response(**data)
            status_code = 200 if "error" not in response_data else 400
            return httpx.Response(status_code, json=response_data)

        with respx.mock:
            respx.post("https://oauth2.googleapis.com/token").mock(
                side_effect=mock_token_request
            )

            async with httpx.AsyncClient() as client:
                # Exchange invalid authorization code
                response = await client.post(
                    "https://oauth2.googleapis.com/token",
                    data={
                        "code": "invalid_auth_code",
                        "client_id": "test_client_id",
                        "client_secret": "test_client_secret",
                        "redirect_uri": "http://localhost:3000/callback",
                        "grant_type": "authorization_code",
                    },
                )

                assert response.status_code == 400
                error_data = response.json()
                assert error_data["error"] == "invalid_grant"


class TestOAuth2TokenRevocationIntegration:
    """Integration tests for token revocation."""

    @pytest.mark.asyncio
    async def test_token_revocation_success(self, mock_oauth_server):
        """Test successful token revocation."""

        # Pre-populate tokens
        refresh_token = "test_refresh_token_revoke"
        access_token = "test_access_token_revoke"

        mock_oauth_server.refresh_tokens[refresh_token] = {
            "client_id": "test_client_id",
            "access_token": access_token,
        }
        mock_oauth_server.access_tokens[access_token] = {
            "client_id": "test_client_id",
            "refresh_token": refresh_token,
            "expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
        }

        def mock_revoke_request(request):
            """Mock revoke endpoint."""
            params = dict(
                httpx.QueryParams(
                    str(request.url).split("?", 1)[1] if "?" in str(request.url) else ""
                )
            )
            token = params.get("token")
            success = mock_oauth_server.revoke_token(token)
            status_code = 200 if success else 400
            return httpx.Response(status_code)

        with respx.mock:
            respx.post("https://oauth2.googleapis.com/revoke").mock(
                side_effect=mock_revoke_request
            )

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://oauth2.googleapis.com/revoke",
                    params={"token": refresh_token},
                )

                assert response.status_code == 200

                # Verify token was removed from server
                assert refresh_token not in mock_oauth_server.refresh_tokens

                # Access token should also be removed
                assert access_token not in mock_oauth_server.access_tokens

    @pytest.mark.asyncio
    async def test_token_revocation_invalid_token(self, mock_oauth_server):
        """Test token revocation with invalid token."""

        def mock_revoke_request(request):
            """Mock revoke endpoint."""
            params = dict(
                httpx.QueryParams(
                    str(request.url).split("?", 1)[1] if "?" in str(request.url) else ""
                )
            )
            token = params.get("token")
            success = mock_oauth_server.revoke_token(token)
            status_code = 200 if success else 400
            return httpx.Response(status_code)

        with respx.mock:
            respx.post("https://oauth2.googleapis.com/revoke").mock(
                side_effect=mock_revoke_request
            )

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://oauth2.googleapis.com/revoke",
                    params={"token": "invalid_token"},
                )

                assert response.status_code == 400


class TestOAuth2ErrorScenarios:
    """Integration tests for various OAuth2 error scenarios."""

    @pytest.mark.asyncio
    async def test_network_timeout_handling(self):
        """Test OAuth2 flow with network timeout."""

        def mock_timeout_request(request):
            """Mock request that times out."""
            raise httpx.TimeoutException("Request timed out")

        with respx.mock:
            respx.post("https://oauth2.googleapis.com/device/code").mock(
                side_effect=mock_timeout_request
            )

            async with httpx.AsyncClient(timeout=1.0) as client:
                with pytest.raises(httpx.TimeoutException):
                    await client.post(
                        "https://oauth2.googleapis.com/device/code",
                        data={
                            "client_id": "test_client_id",
                            "scope": "https://www.googleapis.com/auth/adwords",
                        },
                    )

    @pytest.mark.asyncio
    async def test_invalid_client_credentials(self):
        """Test OAuth2 flow with invalid client credentials."""

        def mock_invalid_client_request(request):
            """Mock endpoint that rejects invalid client."""
            return httpx.Response(
                400,
                json={
                    "error": "invalid_client",
                    "error_description": "Invalid client credentials",
                },
            )

        with respx.mock:
            respx.post("https://oauth2.googleapis.com/device/code").mock(
                side_effect=mock_invalid_client_request
            )

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://oauth2.googleapis.com/device/code",
                    data={
                        "client_id": "invalid_client_id",
                        "scope": "https://www.googleapis.com/auth/adwords",
                    },
                )

                assert response.status_code == 400
                error_data = response.json()
                assert error_data["error"] == "invalid_client"

    @pytest.mark.asyncio
    async def test_malformed_json_response(self):
        """Test handling of malformed JSON responses."""

        def mock_malformed_response(request):
            """Mock response with malformed JSON."""
            return httpx.Response(200, content=b'{"malformed": json}')

        with respx.mock:
            respx.post("https://oauth2.googleapis.com/device/code").mock(
                side_effect=mock_malformed_response
            )

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://oauth2.googleapis.com/device/code",
                    data={
                        "client_id": "test_client_id",
                        "scope": "https://www.googleapis.com/auth/adwords",
                    },
                )

                assert response.status_code == 200
                # JSON parsing should fail when trying to access the response
                with pytest.raises(json.JSONDecodeError):
                    response.json()


class TestOAuth2PerformanceIntegration:
    """Performance integration tests for OAuth2."""

    @pytest.mark.asyncio
    async def test_concurrent_device_code_requests(self, mock_oauth_server):
        """Test multiple concurrent device code requests."""

        request_count = 0

        def mock_device_code_request(request):
            """Mock device code endpoint with tracking."""
            nonlocal request_count
            request_count += 1

            data = dict(httpx.QueryParams(request.content.decode()))
            response = mock_oauth_server.create_device_code_response(data["client_id"])
            # Make each response unique
            response["user_code"] = f"TEST-{request_count:04d}"
            return httpx.Response(200, json=response)

        with respx.mock:
            respx.post("https://oauth2.googleapis.com/device/code").mock(
                side_effect=mock_device_code_request
            )

            async def make_device_code_request():
                async with httpx.AsyncClient() as client:
                    return await client.post(
                        "https://oauth2.googleapis.com/device/code",
                        data={
                            "client_id": "test_client_id",
                            "scope": "https://www.googleapis.com/auth/adwords",
                        },
                    )

            # Execute concurrent requests
            tasks = [make_device_code_request() for _ in range(5)]
            responses = await asyncio.gather(*tasks)

            # All requests should succeed
            assert len(responses) == 5
            user_codes = set()

            for response in responses:
                assert response.status_code == 200
                data = response.json()
                assert "device_code" in data
                assert "user_code" in data
                user_codes.add(data["user_code"])

            # Each request should get a unique user code
            assert len(user_codes) == 5

    @pytest.mark.asyncio
    async def test_oauth_response_time_performance(self, mock_oauth_server):
        """Test OAuth2 response time under normal conditions."""

        def mock_fast_device_code_request(request):
            """Mock fast device code response."""
            data = dict(httpx.QueryParams(request.content.decode()))
            return httpx.Response(
                200,
                json=mock_oauth_server.create_device_code_response(data["client_id"]),
            )

        with respx.mock:
            respx.post("https://oauth2.googleapis.com/device/code").mock(
                side_effect=mock_fast_device_code_request
            )

            start_time = time.time()

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://oauth2.googleapis.com/device/code",
                    data={
                        "client_id": "test_client_id",
                        "scope": "https://www.googleapis.com/auth/adwords",
                    },
                )

            end_time = time.time()
            response_time = end_time - start_time

            assert response.status_code == 200
            # Response should be fast (under 100ms for mocked requests)
            assert response_time < 0.1, (
                f"Device code request took too long: {response_time:.3f}s"
            )

    @pytest.mark.asyncio
    async def test_oauth_rate_limiting_behavior(self, mock_oauth_server):
        """Test OAuth2 behavior under rate limiting."""

        request_count = 0

        def mock_rate_limited_request(request):
            """Mock endpoint that rate limits after certain number of requests."""
            nonlocal request_count
            request_count += 1

            if request_count > 3:
                return httpx.Response(
                    429,
                    json={
                        "error": "rate_limit_exceeded",
                        "error_description": "Too many requests",
                        "retry_after": "60",
                    },
                )

            data = dict(httpx.QueryParams(request.content.decode()))
            return httpx.Response(
                200,
                json=mock_oauth_server.create_device_code_response(data["client_id"]),
            )

        with respx.mock:
            respx.post("https://oauth2.googleapis.com/device/code").mock(
                side_effect=mock_rate_limited_request
            )

            async def make_request():
                async with httpx.AsyncClient() as client:
                    return await client.post(
                        "https://oauth2.googleapis.com/device/code",
                        data={
                            "client_id": "test_client_id",
                            "scope": "https://www.googleapis.com/auth/adwords",
                        },
                    )

            # First few requests should succeed
            for i in range(3):
                response = await make_request()
                assert response.status_code == 200

            # Next request should be rate limited
            response = await make_request()
            assert response.status_code == 429
            error_data = response.json()
            assert error_data["error"] == "rate_limit_exceeded"
