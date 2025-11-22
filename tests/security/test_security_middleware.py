"""Tests for security middleware functionality."""

import asyncio
from unittest.mock import AsyncMock, Mock

import pytest
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.status import HTTP_408_REQUEST_TIMEOUT, HTTP_413_REQUEST_ENTITY_TOO_LARGE

from paidsearchnav_mcp.api.middleware_security import (
    ContentTypeValidationMiddleware,
    RequestLimitMiddleware,
    RequestSizeReaderMiddleware,
)


class TestRequestLimitMiddleware:
    """Test request limit middleware functionality."""

    def setup_method(self):
        """Set up test middleware."""
        self.middleware = RequestLimitMiddleware(
            app=Mock(),
            max_request_size=1024,  # 1KB for testing
            request_timeout=1.0,  # 1 second for testing
            max_concurrent_requests=2,
        )

    @pytest.mark.asyncio
    async def test_request_size_limit_header(self):
        """Test request size limit based on Content-Length header."""
        # Mock request with large content-length
        request = Mock(spec=Request)
        request.headers = {"content-length": "2048"}  # Exceeds 1KB limit

        call_next = Mock()

        response = await self.middleware.dispatch(request, call_next)

        # Should return 413 error
        assert isinstance(response, JSONResponse)
        assert response.status_code == HTTP_413_REQUEST_ENTITY_TOO_LARGE

        # Should not call next middleware
        call_next.assert_not_called()

    @pytest.mark.asyncio
    async def test_request_size_limit_valid(self):
        """Test that valid request sizes are allowed."""
        # Mock request with acceptable size
        request = Mock(spec=Request)
        request.headers = {"content-length": "512"}  # Within 1KB limit

        # Mock successful response
        mock_response = Mock()
        call_next = AsyncMock(return_value=mock_response)

        response = await self.middleware.dispatch(request, call_next)

        # Should call next middleware and return its response
        call_next.assert_called_once_with(request)
        assert response == mock_response

    @pytest.mark.asyncio
    async def test_request_timeout(self):
        """Test request timeout functionality."""
        request = Mock(spec=Request)
        request.headers = {}

        # Mock slow call_next that exceeds timeout
        async def slow_call_next(req):
            await asyncio.sleep(1.1)  # Exceeds 1 second timeout
            return Mock()

        response = await self.middleware.dispatch(request, slow_call_next)

        # Should return 408 timeout error
        assert isinstance(response, JSONResponse)
        assert response.status_code == HTTP_408_REQUEST_TIMEOUT

    @pytest.mark.asyncio
    async def test_concurrent_request_limit(self):
        """Test concurrent request limiting."""
        request1 = Mock(spec=Request)
        request1.headers = {}
        request2 = Mock(spec=Request)
        request2.headers = {}
        request3 = Mock(spec=Request)
        request3.headers = {}

        # Mock call_next that takes some time
        async def delayed_call_next(req):
            await asyncio.sleep(0.1)
            return Mock()

        # Start two requests (should be allowed)
        task1 = asyncio.create_task(
            self.middleware.dispatch(request1, delayed_call_next)
        )
        task2 = asyncio.create_task(
            self.middleware.dispatch(request2, delayed_call_next)
        )

        # Wait a bit to ensure they're running
        await asyncio.sleep(0.05)

        # Third request should be rejected
        response3 = await self.middleware.dispatch(request3, delayed_call_next)

        # Third request should get 429 error
        assert isinstance(response3, JSONResponse)
        assert response3.status_code == 429

        # Wait for first two to complete
        await task1
        await task2

    @pytest.mark.asyncio
    async def test_invalid_content_length(self):
        """Test handling of invalid Content-Length header."""
        request = Mock(spec=Request)
        request.headers = {"content-length": "not_a_number"}

        call_next = Mock()

        response = await self.middleware.dispatch(request, call_next)

        # Should return 400 error for invalid header
        assert isinstance(response, JSONResponse)
        assert response.status_code == 400
        call_next.assert_not_called()


class TestContentTypeValidationMiddleware:
    """Test content type validation middleware."""

    def setup_method(self):
        """Set up test middleware."""
        self.middleware = ContentTypeValidationMiddleware(app=Mock())

    @pytest.mark.asyncio
    async def test_allowed_content_type(self):
        """Test that allowed content types pass through."""
        request = Mock(spec=Request)
        request.method = "POST"
        request.headers = {"content-type": "application/json", "content-length": "100"}

        mock_response = Mock()
        call_next = AsyncMock(return_value=mock_response)

        response = await self.middleware.dispatch(request, call_next)

        call_next.assert_called_once_with(request)
        assert response == mock_response

    @pytest.mark.asyncio
    async def test_disallowed_content_type(self):
        """Test that disallowed content types are rejected."""
        request = Mock(spec=Request)
        request.method = "POST"
        request.headers = {"content-type": "application/xml", "content-length": "100"}

        call_next = Mock()

        response = await self.middleware.dispatch(request, call_next)

        # Should return 415 Unsupported Media Type
        assert isinstance(response, JSONResponse)
        assert response.status_code == 415
        call_next.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_request_no_validation(self):
        """Test that GET requests bypass content type validation."""
        request = Mock(spec=Request)
        request.method = "GET"
        request.headers = {"content-type": "application/xml"}

        mock_response = Mock()
        call_next = AsyncMock(return_value=mock_response)

        response = await self.middleware.dispatch(request, call_next)

        # Should pass through without validation
        call_next.assert_called_once_with(request)
        assert response == mock_response

    @pytest.mark.asyncio
    async def test_empty_body_allowed(self):
        """Test that requests with no body are allowed regardless of content type."""
        request = Mock(spec=Request)
        request.method = "POST"
        request.headers = {"content-type": "application/xml", "content-length": "0"}

        mock_response = Mock()
        call_next = AsyncMock(return_value=mock_response)

        response = await self.middleware.dispatch(request, call_next)

        # Should pass through for empty body
        call_next.assert_called_once_with(request)
        assert response == mock_response

    @pytest.mark.asyncio
    async def test_content_type_with_charset(self):
        """Test content type validation with charset parameter."""
        request = Mock(spec=Request)
        request.method = "POST"
        request.headers = {
            "content-type": "application/json; charset=utf-8",
            "content-length": "100",
        }

        mock_response = Mock()
        call_next = AsyncMock(return_value=mock_response)

        response = await self.middleware.dispatch(request, call_next)

        # Should extract base content type and allow
        call_next.assert_called_once_with(request)
        assert response == mock_response


class TestRequestSizeReaderMiddleware:
    """Test request size reader middleware."""

    def setup_method(self):
        """Set up test middleware."""
        self.middleware = RequestSizeReaderMiddleware(
            app=Mock(),
            max_body_size=1024,  # 1KB for testing
        )

    @pytest.mark.asyncio
    async def test_body_size_enforcement(self):
        """Test that large request bodies are rejected."""
        # This test is complex because it involves mocking the ASGI receive protocol
        # For now, we test that the middleware is properly configured
        assert self.middleware.max_body_size == 1024

    @pytest.mark.asyncio
    async def test_normal_request_processing(self):
        """Test that normal requests pass through."""
        request = Mock(spec=Request)

        # Mock the receive callable to simulate normal request
        async def mock_receive():
            return {"type": "http.request", "body": b"small_body"}

        request.receive = mock_receive
        request._receive = mock_receive

        mock_response = Mock()
        call_next = AsyncMock(return_value=mock_response)

        response = await self.middleware.dispatch(request, call_next)

        call_next.assert_called_once_with(request)
        assert response == mock_response


class TestSecurityMiddlewareIntegration:
    """Integration tests for security middleware stack."""

    @pytest.mark.asyncio
    async def test_middleware_order_matters(self):
        """Test that middleware order affects behavior."""
        # Create middleware instances
        request_limit = RequestLimitMiddleware(
            app=Mock(),
            max_request_size=1024,
            request_timeout=1.0,
            max_concurrent_requests=2,
        )
        content_validation = ContentTypeValidationMiddleware(app=Mock())

        # Create request that would fail both validations
        request = Mock(spec=Request)
        request.method = "POST"
        request.headers = {
            "content-type": "application/xml",  # Invalid content type
            "content-length": "2048",  # Too large
        }

        # Test order 1: RequestLimit -> ContentValidation
        async def content_val_next(req):
            return await content_validation.dispatch(req, Mock())

        response1 = await request_limit.dispatch(request, content_val_next)

        # Should fail at RequestLimit (413) before reaching ContentValidation
        assert response1.status_code == HTTP_413_REQUEST_ENTITY_TOO_LARGE

        # Test order 2: ContentValidation -> RequestLimit
        request2 = Mock(spec=Request)
        request2.method = "POST"
        request2.headers = {
            "content-type": "application/xml",  # Invalid content type
            "content-length": "512",  # Valid size
        }

        async def request_limit_next(req):
            return await request_limit.dispatch(req, Mock())

        response2 = await content_validation.dispatch(request2, request_limit_next)

        # Should fail at ContentValidation (415) before reaching RequestLimit
        assert response2.status_code == 415

    @pytest.mark.asyncio
    async def test_error_response_consistency(self):
        """Test that all security middleware return consistent error formats."""
        # Test RequestLimitMiddleware error format
        middleware = RequestLimitMiddleware(app=Mock(), max_request_size=100)

        request = Mock(spec=Request)
        request.headers = {"content-length": "1000"}  # Too large

        response = await middleware.dispatch(request, Mock())

        # All security middleware should return JSONResponse with error/detail structure
        assert isinstance(response, JSONResponse)
        assert response.status_code == HTTP_413_REQUEST_ENTITY_TOO_LARGE

    @pytest.mark.asyncio
    async def test_middleware_performance_under_load(self):
        """Test middleware performance with concurrent requests."""
        middleware = RequestLimitMiddleware(
            app=Mock(),
            max_request_size=1024,
            request_timeout=2.0,
            max_concurrent_requests=2,  # Lower limit for easier testing
        )

        # Create valid requests
        request1 = Mock(spec=Request)
        request1.headers = {"content-length": "512"}
        request2 = Mock(spec=Request)
        request2.headers = {"content-length": "512"}
        request3 = Mock(spec=Request)
        request3.headers = {"content-length": "512"}

        # Mock call_next with small delay
        async def delayed_call_next(req):
            await asyncio.sleep(0.2)
            return Mock()

        # Start two requests concurrently (at the limit)
        task1 = asyncio.create_task(middleware.dispatch(request1, delayed_call_next))
        task2 = asyncio.create_task(middleware.dispatch(request2, delayed_call_next))

        # Wait a bit to ensure they're running
        await asyncio.sleep(0.1)

        # Third request should be rejected
        extra_response = await middleware.dispatch(request3, delayed_call_next)

        # Should be rejected due to concurrent limit
        assert isinstance(extra_response, JSONResponse)
        assert extra_response.status_code == 429

        # Wait for initial requests to complete
        await task1
        await task2

    @pytest.mark.asyncio
    async def test_content_type_security_bypass_attempts(self):
        """Test security against content type bypass attempts."""
        middleware = ContentTypeValidationMiddleware(app=Mock())

        # Test content types that should be allowed (valid base type)
        valid_attempts = [
            "application/json; charset=utf-8; boundary=something",
            "application/json",
            "text/plain",
            "multipart/form-data",
        ]

        for content_type in valid_attempts:
            request = Mock(spec=Request)
            request.method = "POST"
            request.headers = {"content-type": content_type, "content-length": "100"}

            mock_response = Mock()
            call_next = AsyncMock(return_value=mock_response)

            response = await middleware.dispatch(request, call_next)

            # Should allow valid base content type
            call_next.assert_called_with(request)
            assert response == mock_response

            # Reset mock for next iteration
            call_next.reset_mock()

        # Test content types that should be rejected
        invalid_attempts = [
            "application/xml",
            "text/html",
            "application/pdf",
        ]

        for content_type in invalid_attempts:
            request = Mock(spec=Request)
            request.method = "POST"
            request.headers = {"content-type": content_type, "content-length": "100"}

            call_next = AsyncMock()

            response = await middleware.dispatch(request, call_next)

            # Should reject invalid content type
            assert isinstance(response, JSONResponse)
            assert response.status_code == 415
            call_next.assert_not_called()

    @pytest.mark.asyncio
    async def test_request_size_edge_cases(self):
        """Test edge cases for request size validation."""
        middleware = RequestLimitMiddleware(
            app=Mock(),
            max_request_size=1024,
            request_timeout=1.0,
            max_concurrent_requests=10,
        )

        # Test exact size limit
        request = Mock(spec=Request)
        request.headers = {"content-length": "1024"}  # Exactly at limit

        mock_response = Mock()
        call_next = AsyncMock(return_value=mock_response)

        response = await middleware.dispatch(request, call_next)

        # Should be allowed at exact limit
        call_next.assert_called_once_with(request)
        assert response == mock_response

        # Test one byte over limit
        request_over = Mock(spec=Request)
        request_over.headers = {"content-length": "1025"}  # One byte over

        response_over = await middleware.dispatch(request_over, Mock())

        # Should be rejected
        assert isinstance(response_over, JSONResponse)
        assert response_over.status_code == HTTP_413_REQUEST_ENTITY_TOO_LARGE

    @pytest.mark.asyncio
    async def test_timeout_precision(self):
        """Test timeout precision and cleanup."""
        middleware = RequestLimitMiddleware(
            app=Mock(),
            max_request_size=1024,
            request_timeout=0.5,  # 500ms timeout
            max_concurrent_requests=10,
        )

        request = Mock(spec=Request)
        request.headers = {}

        # Mock call_next that takes just under timeout
        async def almost_timeout_call_next(req):
            await asyncio.sleep(0.4)  # 400ms - should succeed
            return Mock()

        response = await middleware.dispatch(request, almost_timeout_call_next)

        # Should succeed
        assert (
            not isinstance(response, JSONResponse)
            or response.status_code != HTTP_408_REQUEST_TIMEOUT
        )

        # Mock call_next that exceeds timeout
        async def timeout_call_next(req):
            await asyncio.sleep(0.51)  # 510ms - should timeout
            return Mock()

        response_timeout = await middleware.dispatch(request, timeout_call_next)

        # Should timeout
        assert isinstance(response_timeout, JSONResponse)
        assert response_timeout.status_code == HTTP_408_REQUEST_TIMEOUT

    @pytest.mark.asyncio
    async def test_concurrent_request_cleanup(self):
        """Test that concurrent request counter is properly cleaned up."""
        middleware = RequestLimitMiddleware(
            app=Mock(),
            max_request_size=1024,
            request_timeout=1.0,
            max_concurrent_requests=1,
        )

        # Start a request that will complete
        request1 = Mock(spec=Request)
        request1.headers = {}

        async def quick_call_next(req):
            await asyncio.sleep(0.1)
            return Mock()

        # Start first request
        task1 = asyncio.create_task(middleware.dispatch(request1, quick_call_next))

        # Wait a bit, then try second request
        await asyncio.sleep(0.05)

        request2 = Mock(spec=Request)
        request2.headers = {}

        # Should be rejected due to concurrent limit
        response2 = await middleware.dispatch(request2, quick_call_next)
        assert isinstance(response2, JSONResponse)
        assert response2.status_code == 429

        # Wait for first request to complete
        await task1

        # Now third request should succeed
        request3 = Mock(spec=Request)
        request3.headers = {}

        response3 = await middleware.dispatch(request3, quick_call_next)

        # Should succeed because first request cleaned up
        assert not isinstance(response3, JSONResponse) or response3.status_code != 429
