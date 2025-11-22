"""Tests for API versioning functionality."""

from datetime import datetime, timezone
from unittest.mock import Mock

import pytest
from fastapi import HTTPException, Request
from fastapi.testclient import TestClient

from paidsearchnav.api.main import create_app
from paidsearchnav.api.version_config import initialize_api_versions
from paidsearchnav.api.version_transformers import (
    DeprecatedFieldTransformer,
    FieldRenameTransformer,
    ResponseFilterTransformer,
    V1_1ToV2Transformer,
    V1ToV1_1Transformer,
    initialize_transformers,
)
from paidsearchnav.api.versioning import (
    ApiVersion,
    VersionedResponse,
    VersionedRoute,
    VersionFormat,
    VersionMiddleware,
    VersionNegotiator,
    VersionRegistry,
    VersionStatus,
    transformer_registry,
    version_registry,
)


@pytest.fixture
def test_registry():
    """Create a test version registry."""
    registry = VersionRegistry()

    # Register test versions
    v1_0 = ApiVersion(
        major=1,
        minor=0,
        status=VersionStatus.STABLE,
        released_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    registry.register(v1_0)

    v1_1 = ApiVersion(
        major=1,
        minor=1,
        status=VersionStatus.BETA,
        released_date=datetime(2024, 6, 1, tzinfo=timezone.utc),
    )
    registry.register(v1_1)

    v2_0 = ApiVersion(
        major=2,
        minor=0,
        status=VersionStatus.DEPRECATED,
        released_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
        deprecated_date=datetime(2024, 12, 1, tzinfo=timezone.utc),
        sunset_date=datetime(2026, 6, 1, tzinfo=timezone.utc),  # Future date
        deprecation_message="Please migrate to v3.0",
    )
    registry.register(v2_0)

    registry.set_current("1.0")
    registry.set_minimum("1.0")

    return registry


@pytest.fixture
def test_negotiator(test_registry):
    """Create a test version negotiator."""
    return VersionNegotiator(test_registry)


@pytest.fixture
def mock_request():
    """Create a mock request object."""
    request = Mock(spec=Request)
    request.url = Mock()
    request.url.path = "/api/v1/test"
    request.headers = {}
    request.query_params = {}
    request.state = Mock()
    return request


class TestApiVersion:
    """Test ApiVersion class."""

    def test_version_string(self):
        """Test version string generation."""
        version = ApiVersion(
            major=1,
            minor=2,
            status=VersionStatus.STABLE,
            released_date=datetime.now(timezone.utc),
        )
        assert version.version_string == "1.2"

    def test_url_path(self):
        """Test URL path generation."""
        version = ApiVersion(
            major=2,
            minor=0,
            status=VersionStatus.STABLE,
            released_date=datetime.now(timezone.utc),
        )
        assert version.url_path == "v2"

    def test_header_value(self):
        """Test header value generation."""
        version = ApiVersion(
            major=1,
            minor=0,
            status=VersionStatus.STABLE,
            released_date=datetime.now(timezone.utc),
        )
        assert version.header_value == "application/vnd.psn.v1+json"

    def test_is_deprecated(self):
        """Test deprecation check."""
        version = ApiVersion(
            major=1,
            minor=0,
            status=VersionStatus.DEPRECATED,
            released_date=datetime.now(timezone.utc),
        )
        assert version.is_deprecated() is True

        version.status = VersionStatus.STABLE
        assert version.is_deprecated() is False

    def test_is_sunset(self):
        """Test sunset check."""
        # Test with sunset status
        version = ApiVersion(
            major=1,
            minor=0,
            status=VersionStatus.SUNSET,
            released_date=datetime.now(timezone.utc),
        )
        assert version.is_sunset() is True

        # Test with future sunset date
        version = ApiVersion(
            major=1,
            minor=0,
            status=VersionStatus.DEPRECATED,
            released_date=datetime.now(timezone.utc),
            sunset_date=datetime(2099, 1, 1, tzinfo=timezone.utc),
        )
        assert version.is_sunset() is False

        # Test with past sunset date
        version.sunset_date = datetime(2020, 1, 1, tzinfo=timezone.utc)
        assert version.is_sunset() is True


class TestVersionRegistry:
    """Test VersionRegistry class."""

    def test_register_version(self, test_registry):
        """Test version registration."""
        assert "1.0" in test_registry._versions
        assert "1.1" in test_registry._versions
        assert "2.0" in test_registry._versions

    def test_get_version(self, test_registry):
        """Test getting a specific version."""
        version = test_registry.get_version("1.0")
        assert version is not None
        assert version.version_string == "1.0"

        # Test non-existent version
        assert test_registry.get_version("3.0") is None

    def test_get_current(self, test_registry):
        """Test getting current version."""
        current = test_registry.get_current()
        assert current is not None
        assert current.version_string == "1.0"

    def test_is_version_supported(self, test_registry):
        """Test version support check."""
        v1_0 = test_registry.get_version("1.0")
        assert test_registry.is_version_supported(v1_0) is True

        # Test sunset version
        v2_0 = test_registry.get_version("2.0")
        v2_0.status = VersionStatus.SUNSET
        assert test_registry.is_version_supported(v2_0) is False


class TestVersionNegotiator:
    """Test VersionNegotiator class."""

    def test_url_version_extraction(self, test_negotiator, mock_request):
        """Test version extraction from URL."""
        mock_request.url.path = "/api/v2/test"
        version, format_used = test_negotiator.negotiate_version(mock_request)
        assert version.version_string == "2.0"
        assert format_used == VersionFormat.URL

    def test_header_version_extraction(self, test_negotiator, mock_request):
        """Test version extraction from Accept header."""
        mock_request.url.path = "/api/test"
        mock_request.headers = {"accept": "application/vnd.psn.v1.1+json"}
        version, format_used = test_negotiator.negotiate_version(mock_request)
        assert version.version_string == "1.1"
        assert format_used == VersionFormat.HEADER

    def test_custom_header_extraction(self, test_negotiator, mock_request):
        """Test version extraction from X-API-Version header."""
        mock_request.url.path = "/api/test"
        mock_request.headers = {"x-api-version": "2.0"}
        version, format_used = test_negotiator.negotiate_version(mock_request)
        assert version.version_string == "2.0"
        assert format_used == VersionFormat.CUSTOM_HEADER

    def test_query_param_extraction(self, test_negotiator, mock_request):
        """Test version extraction from query parameter."""
        mock_request.url.path = "/api/test"
        mock_request.query_params = {"version": "1.1"}
        version, format_used = test_negotiator.negotiate_version(mock_request)
        assert version.version_string == "1.1"
        assert format_used == VersionFormat.QUERY

    def test_default_version(self, test_negotiator, mock_request):
        """Test default version when none specified."""
        mock_request.url.path = "/api/test"
        version, format_used = test_negotiator.negotiate_version(mock_request)
        assert version.version_string == "1.0"  # Current version
        assert format_used == VersionFormat.URL  # Default format


class TestVersionMiddleware:
    """Test VersionMiddleware class."""

    @pytest.mark.asyncio
    async def test_version_negotiation(self, test_registry):
        """Test middleware version negotiation."""
        # Create a mock app that checks version was set
        version_info = {}

        async def mock_app(scope, receive, send):
            # Capture version info from scope
            if "state" in scope:
                version_info["api_version"] = scope["state"]["api_version"]
                version_info["version_format"] = scope["state"]["version_format"]

            await send(
                {
                    "type": "http.response.start",
                    "status": 200,
                    "headers": [],
                }
            )
            await send(
                {
                    "type": "http.response.body",
                    "body": b"test",
                }
            )

        middleware = VersionMiddleware(mock_app, test_registry)

        # Create mock scope
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/test",
            "headers": [],
            "query_string": b"",
        }

        # Capture sent messages
        sent_messages = []

        async def mock_send(message):
            sent_messages.append(message)

        # Mock receive
        async def mock_receive():
            return {"type": "http.request"}

        # Call middleware
        await middleware(scope, mock_receive, mock_send)

        # Check that version was set
        assert "api_version" in version_info
        assert version_info["api_version"].version_string == "1.0"
        assert "version_format" in version_info

        # Check response headers
        start_message = sent_messages[0]
        headers = dict(start_message["headers"])
        assert headers[b"x-api-version"] == b"1.0"
        assert headers[b"x-api-version-status"] == b"stable"

    @pytest.mark.asyncio
    async def test_deprecated_version_headers(self, test_registry):
        """Test headers for deprecated version."""

        # Create a mock app
        async def mock_app(scope, receive, send):
            await send(
                {
                    "type": "http.response.start",
                    "status": 200,
                    "headers": [],
                }
            )
            await send(
                {
                    "type": "http.response.body",
                    "body": b"test",
                }
            )

        middleware = VersionMiddleware(mock_app, test_registry)

        # Create mock scope for deprecated version
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/api/v2/test",
            "headers": [],
            "query_string": b"",
        }

        # Capture sent messages
        sent_messages = []

        async def mock_send(message):
            sent_messages.append(message)

        # Mock receive
        async def mock_receive():
            return {"type": "http.request"}

        # Call middleware
        await middleware(scope, mock_receive, mock_send)

        # Check that response was sent with deprecation headers
        start_message = sent_messages[0]
        assert start_message["type"] == "http.response.start"

        headers = dict(start_message["headers"])
        assert b"x-api-version" in headers
        assert headers[b"x-api-version"] == b"2.0"
        assert b"sunset" in headers
        assert b"deprecation" in headers
        assert b"link" in headers


class TestVersionTransformers:
    """Test version transformers."""

    def test_v1_to_v1_1_transformer(self):
        """Test v1.0 to v1.1 transformer."""
        transformer = V1ToV1_1Transformer()

        # Test request transformation (single to bulk)
        data = {"id": "123", "name": "test"}
        transformed = transformer.transform_request(data, "1.0", "1.1")
        assert "items" in transformed
        assert transformed["items"] == [data]

        # Test response transformation (bulk to single)
        bulk_data = {
            "items": [{"id": "123", "name": "test"}],
            "bulk_operation_id": "op123",
            "processing_time": 1.5,
        }
        transformed = transformer.transform_response(bulk_data, "1.1", "1.0")
        assert "items" not in transformed
        assert transformed["id"] == "123"
        assert "bulk_operation_id" not in transformed

    def test_v1_1_to_v2_transformer(self):
        """Test v1.1 to v2.0 transformer."""
        transformer = V1_1ToV2Transformer()

        # Test request transformation (snake_case to camelCase)
        data = {
            "customer_id": "123",
            "analysis_type": "keyword",
            "start_date": "2024-01-01",
        }
        transformed = transformer.transform_request(data, "1.1", "2.0")
        assert transformed["customerId"] == "123"
        assert transformed["analysisType"] == "keyword"
        assert transformed["startDate"] == "2024-01-01"

        # Test response transformation (camelCase to snake_case)
        data = {
            "customerId": "123",
            "analysisType": "keyword",
            "createdAt": "2024-01-01",
        }
        transformed = transformer.transform_response(data, "2.0", "1.1")
        assert transformed["customer_id"] == "123"
        assert transformed["analysis_type"] == "keyword"
        assert transformed["created_at"] == "2024-01-01"

    def test_field_rename_transformer(self):
        """Test generic field rename transformer."""
        mappings = {
            "old_field": "new_field",
            "legacy_name": "modern_name",
        }
        transformer = FieldRenameTransformer(mappings)

        # Test request transformation
        data = {"old_field": "value", "legacy_name": "test", "unchanged": "same"}
        transformed = transformer.transform_request(data, "1.0", "2.0")
        assert transformed["new_field"] == "value"
        assert transformed["modern_name"] == "test"
        assert transformed["unchanged"] == "same"

        # Test response transformation (reverse)
        data = {"new_field": "value", "modern_name": "test"}
        transformed = transformer.transform_response(data, "2.0", "1.0")
        assert transformed["old_field"] == "value"
        assert transformed["legacy_name"] == "test"

    def test_response_filter_transformer(self):
        """Test response field filter transformer."""
        allowed_fields = ["id", "name", "status"]
        transformer = ResponseFilterTransformer(allowed_fields)

        # Test filtering
        data = {
            "id": "123",
            "name": "test",
            "status": "active",
            "internal_field": "secret",
            "debug_info": "hidden",
        }
        transformed = transformer.transform_response(data, "2.0", "1.0")
        assert "id" in transformed
        assert "name" in transformed
        assert "status" in transformed
        assert "internal_field" not in transformed
        assert "debug_info" not in transformed

    def test_deprecated_field_transformer(self):
        """Test deprecated field transformer."""
        deprecated_fields = {
            "legacy_field": "default_value",
            "old_status": "unknown",
        }
        transformer = DeprecatedFieldTransformer(deprecated_fields)

        # Test adding deprecated fields
        data = {"id": "123", "name": "test"}
        transformed = transformer.transform_response(data, "2.0", "1.0")
        assert transformed["legacy_field"] == "default_value"
        assert transformed["old_status"] == "unknown"
        assert transformed["id"] == "123"


class TestVersionedRoute:
    """Test versioned route decorator."""

    @pytest.mark.asyncio
    async def test_version_requirement(self):
        """Test route version requirements."""
        # Create a versioned route
        route = VersionedRoute(min_version="1.1", max_version="2.0")

        # Mock function
        async def test_endpoint(request):
            return {"message": "success"}

        wrapped = route(test_endpoint)

        # Test with valid version
        request = Mock()
        request.state = Mock()
        request.state.api_version = ApiVersion(
            major=1,
            minor=1,
            status=VersionStatus.STABLE,
            released_date=datetime.now(timezone.utc),
        )

        result = await wrapped(request)
        assert result["message"] == "success"

        # Test with too old version
        request.state.api_version = ApiVersion(
            major=1,
            minor=0,
            status=VersionStatus.STABLE,
            released_date=datetime.now(timezone.utc),
        )

        with pytest.raises(HTTPException) as exc_info:
            await wrapped(request)
        assert exc_info.value.status_code == 400
        assert "requires API version 1.1" in exc_info.value.detail


class TestVersionedResponse:
    """Test VersionedResponse class for Pydantic v2 migration."""

    def test_versioned_response_ignores_extra_fields(self):
        """Test that VersionedResponse properly ignores extra fields."""

        # Create a concrete subclass for testing
        class TestResponse(VersionedResponse):
            message: str
            status: str

        # Test that extra fields are ignored (not raising validation errors)
        data = {
            "message": "Hello World",
            "status": "success",
            "extra_field": "should be ignored",
            "unknown_data": {"nested": "data"},
        }

        # This should not raise a validation error
        response = TestResponse(**data)

        # Verify the expected fields are present
        assert response.message == "Hello World"
        assert response.status == "success"

        # Verify extra fields are not accessible via attribute access
        assert not hasattr(response, "extra_field")
        assert not hasattr(response, "unknown_data")

    def test_versioned_response_for_version_method(self):
        """Test the for_version class method."""

        class TestResponse(VersionedResponse):
            data: str

        # Test that for_version returns the same class by default
        versioned_class = TestResponse.for_version("1.0")
        assert versioned_class == TestResponse

        versioned_class = TestResponse.for_version("2.0")
        assert versioned_class == TestResponse

    def test_versioned_response_serialization(self):
        """Test that serialization works correctly with extra fields ignored."""

        class TestResponse(VersionedResponse):
            id: int
            name: str

        # Create instance with extra data
        response = TestResponse(id=123, name="test", extra_ignored="value")

        # Test serialization - should only include defined fields
        response_dict = response.model_dump()
        assert response_dict == {"id": 123, "name": "test"}
        assert "extra_ignored" not in response_dict

        # Test JSON serialization
        json_str = response.model_dump_json()
        import json

        parsed = json.loads(json_str)
        assert parsed == {"id": 123, "name": "test"}
        assert "extra_ignored" not in parsed


class TestIntegration:
    """Integration tests for versioning system."""

    @pytest.fixture
    def client(self):
        """Create test client with versioning enabled."""
        # Reset registries for clean test
        version_registry._versions.clear()
        version_registry._current_version = None
        version_registry._minimum_version = None
        transformer_registry._transformers.clear()

        # Initialize versioning
        initialize_api_versions()
        initialize_transformers()

        # Create app
        app = create_app()
        return TestClient(app)

    def test_url_based_versioning(self, client):
        """Test URL-based version access."""
        # Test v1 endpoint
        response = client.get("/api/v1/version")
        assert response.status_code == 200
        data = response.json()
        assert data["version"] == "1.0"

        # Check version headers
        assert response.headers["X-API-Version"] == "1.0"
        assert response.headers["X-API-Version-Status"] == "stable"

    def test_header_based_versioning(self, client):
        """Test header-based version negotiation."""
        # Test Accept header
        response = client.get(
            "/api/version", headers={"Accept": "application/vnd.psn.v1+json"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["version"] == "1.0"

        # Test X-API-Version header
        response = client.get("/api/version", headers={"X-API-Version": "1.1"})
        assert response.status_code == 200
        data = response.json()
        assert data["version"] == "1.1"

    def test_version_list_endpoint(self, client):
        """Test version listing endpoint."""
        response = client.get("/api/v1/versions")
        assert response.status_code == 200
        data = response.json()

        assert "current" in data
        assert "versions" in data
        assert "deprecation_policy" in data

        # Check version list
        versions = {v["version"] for v in data["versions"]}
        assert "1.0" in versions
        assert "1.1" in versions
        assert "2.0" in versions

    def test_version_negotiation_endpoint(self, client):
        """Test version negotiation verification endpoint."""
        # Test with different version methods
        response = client.get(
            "/api/v1/version/negotiation", headers={"X-API-Version": "1.1"}
        )
        assert response.status_code == 200
        data = response.json()

        assert data["negotiated_version"] == "1.0"  # URL takes precedence
        assert data["version_format"] == "url"
        assert data["headers"]["x-api-version"] == "1.1"
