"""Comprehensive tests for API middleware components."""

from unittest.mock import AsyncMock, Mock

import pytest
from starlette.requests import Request
from starlette.responses import Response

from paidsearchnav.api.middleware import SecurityHeadersMiddleware, TimingMiddleware
from paidsearchnav.api.middleware_token import (
    TokenExtractionMiddleware,
    get_current_jwt_token,
)
from tests.utils import create_test_jwt_token


class TestSecurityHeadersMiddleware:
    """Test security headers middleware."""

    def setup_method(self):
        """Set up test middleware."""
        self.middleware = SecurityHeadersMiddleware(app=Mock())

    @pytest.mark.asyncio
    async def test_security_headers_added(self):
        """Test that security headers are added to responses."""
        request = Mock(spec=Request)

        # Mock response from next middleware
        mock_response = Mock(spec=Response)
        mock_response.headers = {}
        call_next = AsyncMock(return_value=mock_response)

        response = await self.middleware.dispatch(request, call_next)

        # Should call next middleware
        call_next.assert_called_once_with(request)

        # Should add security headers
        expected_headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Referrer-Policy": "strict-origin-when-cross-origin",
        }

        for header, value in expected_headers.items():
            assert response.headers[header] == value

    @pytest.mark.asyncio
    async def test_headers_always_set(self):
        """Test that security headers are always set (may override existing)."""
        request = Mock(spec=Request)

        # Mock response with existing security header
        mock_response = Mock(spec=Response)
        mock_response.headers = {"X-Frame-Options": "SAMEORIGIN"}
        call_next = AsyncMock(return_value=mock_response)

        response = await self.middleware.dispatch(request, call_next)

        # Middleware always sets its own security headers
        assert response.headers["X-Frame-Options"] == "DENY"

        # Should still add other headers
        assert response.headers["X-Content-Type-Options"] == "nosniff"


class TestTimingMiddleware:
    """Test timing middleware functionality."""

    def setup_method(self):
        """Set up test middleware."""
        self.middleware = TimingMiddleware(app=Mock())

    @pytest.mark.asyncio
    async def test_timing_header_added(self):
        """Test that timing header is added to responses."""
        request = Mock(spec=Request)

        # Mock response from next middleware
        mock_response = Mock(spec=Response)
        mock_response.headers = {}
        call_next = AsyncMock(return_value=mock_response)

        response = await self.middleware.dispatch(request, call_next)

        # Should call next middleware
        call_next.assert_called_once_with(request)

        # Should add timing header
        assert "X-Process-Time" in response.headers

        # Header value should be a valid float
        timing_value = response.headers["X-Process-Time"]
        assert isinstance(timing_value, str)
        parsed_time = float(timing_value)
        # Should be a reasonable time (not negative, not too large)
        assert 0 <= parsed_time <= 10.0  # Max 10 seconds is reasonable for a test


class TestTokenExtractionMiddleware:
    """Test JWT token extraction middleware."""

    def setup_method(self):
        """Set up test middleware."""
        self.middleware = TokenExtractionMiddleware(app=Mock())

    @pytest.mark.asyncio
    async def test_token_extraction_bearer(self):
        """Test token extraction from Bearer authorization header."""

        # Create a proper mock that allows attribute assignment
        class MockState:
            pass

        request = Mock(spec=Request)
        request.headers = {
            "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
        }
        request.state = MockState()

        mock_response = Mock(spec=Response)
        call_next = AsyncMock(return_value=mock_response)

        response = await self.middleware.dispatch(request, call_next)

        # Should call next middleware
        call_next.assert_called_once_with(request)

        # Should extract and store token in request state
        assert hasattr(request.state, "jwt_token")
        assert request.state.jwt_token == "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"

    @pytest.mark.asyncio
    async def test_no_authorization_header(self):
        """Test behavior when no authorization header is present."""

        class MockState:
            pass

        request = Mock(spec=Request)
        request.headers = {}
        request.state = MockState()

        mock_response = Mock(spec=Response)
        call_next = AsyncMock(return_value=mock_response)

        response = await self.middleware.dispatch(request, call_next)

        # Should call next middleware
        call_next.assert_called_once_with(request)

        # Should set token to None
        assert request.state.jwt_token is None

    @pytest.mark.asyncio
    async def test_invalid_authorization_format(self):
        """Test behavior with invalid authorization header format."""

        class MockState:
            pass

        request = Mock(spec=Request)
        request.headers = {"Authorization": "Basic dXNlcjpwYXNz"}
        request.state = MockState()

        mock_response = Mock(spec=Response)
        call_next = AsyncMock(return_value=mock_response)

        response = await self.middleware.dispatch(request, call_next)

        # Should set token to None for non-Bearer auth
        assert request.state.jwt_token is None


class TestGetCurrentJwtToken:
    """Test the get_current_jwt_token utility function."""

    def test_get_token_from_request(self):
        """Test getting token from request state."""
        request = Mock(spec=Request)
        request.state = Mock()
        request.state.jwt_token = "test_token_123"

        token = get_current_jwt_token(request)

        assert token == "test_token_123"

    def test_get_token_no_state(self):
        """Test getting token when request has no state."""
        request = Mock(spec=Request)
        request.state = None

        token = get_current_jwt_token(request)

        assert token is None

    def test_get_token_none_value(self):
        """Test getting token when jwt_token is None."""
        request = Mock(spec=Request)
        request.state = Mock()
        request.state.jwt_token = None

        token = get_current_jwt_token(request)

        assert token is None


class TestMiddlewareIntegration:
    """Integration tests for middleware stack."""

    @pytest.mark.asyncio
    async def test_middleware_chain_order(self):
        """Test that middleware can be chained together."""

        # Create a proper mock state
        class MockState:
            pass

        # Create middleware instances
        security_middleware = SecurityHeadersMiddleware(app=Mock())
        timing_middleware = TimingMiddleware(app=Mock())
        token_middleware = TokenExtractionMiddleware(app=Mock())

        request = Mock(spec=Request)
        request.headers = {"Authorization": f"Bearer {create_test_jwt_token()}"}
        request.state = MockState()
        mock_response = Mock(spec=Response)
        mock_response.headers = {}

        # Chain them together: security -> timing -> token -> app
        async def app_call_next(req):
            return mock_response

        # Apply token middleware first
        async def token_call_next(req):
            return await token_middleware.dispatch(req, app_call_next)

        # Apply timing middleware second
        async def timing_call_next(req):
            return await timing_middleware.dispatch(req, token_call_next)

        # Apply security middleware third
        response = await security_middleware.dispatch(request, timing_call_next)

        # Should have security headers, timing header, and extracted token
        assert "X-Content-Type-Options" in response.headers
        assert "X-Process-Time" in response.headers
        assert request.state.jwt_token == "test_token"

    @pytest.mark.asyncio
    async def test_middleware_error_handling(self):
        """Test that middleware properly handles errors from downstream."""
        middleware = SecurityHeadersMiddleware(app=Mock())

        request = Mock(spec=Request)

        # Mock call_next that raises an exception
        async def error_call_next(req):
            raise ValueError("Downstream error")

        # Middleware should let the exception bubble up
        with pytest.raises(ValueError, match="Downstream error"):
            await middleware.dispatch(request, error_call_next)

    @pytest.mark.asyncio
    async def test_token_extraction_with_malformed_header(self):
        """Test token extraction with various malformed headers."""
        middleware = TokenExtractionMiddleware(app=Mock())

        # Generate token once for consistency
        test_token = create_test_jwt_token()
        test_cases = [
            ("Bearer", ""),  # No token - FastAPI returns empty string
            ("Bearer ", ""),  # Empty token - FastAPI returns empty string
            ("bearer token", "token"),  # lowercase bearer
            ("Token abc123", None),  # Wrong scheme
            ("", None),  # Empty header
            (f"Bearer {test_token}", test_token),  # Valid token
        ]

        for auth_header, expected_token in test_cases:

            class MockState:
                pass

            request = Mock(spec=Request)
            request.headers = {"Authorization": auth_header} if auth_header else {}
            request.state = MockState()

            mock_response = Mock(spec=Response)
            call_next = AsyncMock(return_value=mock_response)

            response = await middleware.dispatch(request, call_next)

            # Should still call next middleware
            call_next.assert_called_once()

            # Check extracted token
            assert request.state.jwt_token == expected_token

            # Reset for next iteration
            call_next.reset_mock()
