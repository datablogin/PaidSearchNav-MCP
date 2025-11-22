"""Tests for request ID middleware."""

import uuid
from unittest.mock import patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from starlette.testclient import TestClient

from paidsearchnav.api.exceptions import (
    APIException,
    api_exception_handler,
    general_exception_handler,
    http_exception_handler,
)
from paidsearchnav.api.middleware_request_id import (
    RequestIDMiddleware,
    get_request_id,
)


@pytest.fixture
def test_app():
    """Create a test FastAPI app with request ID middleware."""
    app = FastAPI()

    # Add middleware
    app.add_middleware(RequestIDMiddleware)

    # Add exception handlers
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(APIException, api_exception_handler)
    app.add_exception_handler(ValueError, general_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)

    # Add test endpoints
    @app.get("/test")
    async def test_endpoint():
        return {"request_id": get_request_id()}

    @app.get("/error/http")
    async def http_error():
        raise HTTPException(status_code=400, detail="Bad request")

    @app.get("/error/api")
    async def api_error():
        raise APIException(status_code=403, detail="Forbidden")

    @app.get("/error/general")
    async def general_error():
        raise ValueError("Something went wrong")

    @app.get("/headers")
    async def custom_headers():
        return Response(content="OK", headers={"X-Custom-Header": "value"})

    return app


@pytest.fixture
def client(test_app):
    """Create a test client."""
    return TestClient(test_app)


class TestRequestIDMiddleware:
    """Test request ID middleware functionality."""

    def test_request_id_generation(self, client):
        """Test that middleware generates unique request IDs."""
        response = client.get("/test")
        assert response.status_code == 200

        # Check response header
        assert "X-Request-ID" in response.headers
        request_id = response.headers["X-Request-ID"]

        # Validate UUID format
        uuid.UUID(request_id)  # This will raise if invalid

        # Check response body
        assert response.json()["request_id"] == request_id

    def test_unique_request_ids(self, client):
        """Test that each request gets a unique ID."""
        request_ids = set()

        for _ in range(10):
            response = client.get("/test")
            request_id = response.headers["X-Request-ID"]
            request_ids.add(request_id)

        # All request IDs should be unique
        assert len(request_ids) == 10

    def test_request_id_in_context(self, client):
        """Test that request ID is available in context during request."""

        # Add a test endpoint that captures the ID during request
        @client.app.get("/capture")
        async def capture_endpoint():
            captured_id = get_request_id()
            return {"captured_id": captured_id}

        response = client.get("/capture")

        # The captured ID in response should match the response header
        assert response.json()["captured_id"] == response.headers["X-Request-ID"]

    def test_request_id_cleared_after_request(self, client):
        """Test that request ID context is cleared after request."""
        # Before any request
        assert get_request_id() is None

        # Make a request
        response = client.get("/test")
        request_id = response.headers["X-Request-ID"]

        # After request completes, context should be cleared
        assert get_request_id() is None

    def test_request_id_with_existing_headers(self, client):
        """Test that request ID is added alongside existing headers."""
        response = client.get("/headers")

        # Should have both headers
        assert "X-Request-ID" in response.headers
        assert "X-Custom-Header" in response.headers
        assert response.headers["X-Custom-Header"] == "value"

    def test_http_exception_includes_request_id(self, client):
        """Test that HTTP exceptions include request ID."""
        response = client.get("/error/http")

        assert response.status_code == 400
        assert "X-Request-ID" in response.headers

        json_body = response.json()
        assert "request_id" in json_body
        assert json_body["request_id"] == response.headers["X-Request-ID"]
        assert json_body["detail"] == "Bad request"

    def test_api_exception_includes_request_id(self, client):
        """Test that API exceptions include request ID."""
        response = client.get("/error/api")

        assert response.status_code == 403
        assert "X-Request-ID" in response.headers

        json_body = response.json()
        assert "request_id" in json_body
        assert json_body["request_id"] == response.headers["X-Request-ID"]
        assert json_body["detail"] == "Forbidden"

    def test_general_exception_includes_request_id(self, client):
        """Test that general exceptions include request ID."""
        response = client.get("/error/general")

        assert response.status_code == 500
        assert "X-Request-ID" in response.headers

        json_body = response.json()
        assert "request_id" in json_body
        assert json_body["request_id"] == response.headers["X-Request-ID"]
        assert json_body["detail"] == "Internal server error"

    def test_concurrent_requests(self, client):
        """Test that concurrent requests maintain separate request IDs."""
        import concurrent.futures

        def make_request():
            response = client.get("/test")
            request_id = response.headers["X-Request-ID"]
            body_id = response.json()["request_id"]
            return request_id, body_id

        # Make multiple concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(make_request) for _ in range(20)]
            results = [future.result() for future in futures]

        # Each request should have matching header and body IDs
        for header_id, body_id in results:
            assert header_id == body_id

        # All request IDs should be unique
        all_ids = [header_id for header_id, _ in results]
        assert len(set(all_ids)) == len(all_ids)

    @patch("paidsearchnav.api.middleware_request_id.uuid.uuid4")
    def test_request_id_generation_format(self, mock_uuid, client):
        """Test that request IDs use the expected format."""
        # Mock UUID to return a known value
        mock_uuid.return_value = uuid.UUID("12345678-1234-5678-1234-567812345678")

        response = client.get("/test")

        assert (
            response.headers["X-Request-ID"] == "12345678-1234-5678-1234-567812345678"
        )
        assert response.json()["request_id"] == "12345678-1234-5678-1234-567812345678"
