"""Tests for API version transformers."""

import pytest

from paidsearchnav_mcp.api.version_transformers import (
    DeprecatedFieldTransformer,
    FieldRenameTransformer,
    ResponseFilterTransformer,
    V1_1ToV2Transformer,
    V1ToV1_1Transformer,
    initialize_transformers,
)
from paidsearchnav_mcp.api.versioning import TransformerRegistry, transformer_registry


class TestTransformerRegistry:
    """Test the transformer registry functionality."""

    @pytest.fixture
    def registry(self):
        """Create a clean transformer registry."""
        return TransformerRegistry()

    def test_register_transformer(self, registry):
        """Test registering a transformer."""
        transformer = V1ToV1_1Transformer()
        registry.register("1.0", "1.1", transformer)

        assert registry.get_transformer("1.0", "1.1") == transformer
        assert registry.get_transformer("1.1", "1.0") is None

    def test_transform_request_with_registered_transformer(self, registry):
        """Test transforming request with registered transformer."""
        transformer = V1ToV1_1Transformer()
        registry.register("1.0", "1.1", transformer)

        data = {"id": "123", "name": "test"}
        result = registry.transform_request(data, "1.0", "1.1")

        assert "items" in result
        assert result["items"] == [data]

    def test_transform_request_without_transformer(self, registry):
        """Test transforming request without registered transformer."""
        data = {"id": "123", "name": "test"}
        result = registry.transform_request(data, "1.0", "2.0")

        # Should return original data when no transformer found
        assert result == data

    def test_transform_response_same_version(self, registry):
        """Test that same version returns unchanged data."""
        data = {"id": "123", "name": "test"}
        result = registry.transform_response(data, "1.0", "1.0")

        assert result == data


class TestV1ToV1_1Transformer:
    """Test v1.0 to v1.1 transformer."""

    @pytest.fixture
    def transformer(self):
        """Create transformer instance."""
        return V1ToV1_1Transformer()

    def test_transform_request_single_to_bulk(self, transformer):
        """Test transforming single item to bulk format."""
        data = {"id": "123", "customer_id": "456", "name": "test"}
        result = transformer.transform_request(data, "1.0", "1.1")

        assert "items" in result
        assert len(result["items"]) == 1
        assert result["items"][0] == data

    def test_transform_request_already_bulk(self, transformer):
        """Test that bulk format is preserved."""
        data = {"items": [{"id": "123"}, {"id": "456"}]}
        result = transformer.transform_request(data, "1.0", "1.1")

        assert result == data

    def test_transform_response_bulk_to_single(self, transformer):
        """Test transforming bulk response to single item."""
        data = {
            "items": [{"id": "123", "name": "test"}],
            "bulk_operation_id": "op123",
            "processing_time": 1.5,
            "batch_errors": [],
        }
        result = transformer.transform_response(data, "1.1", "1.0")

        assert "items" not in result
        assert result["id"] == "123"
        assert result["name"] == "test"
        assert "bulk_operation_id" not in result
        assert "processing_time" not in result
        assert "batch_errors" not in result

    def test_transform_response_multiple_items(self, transformer):
        """Test handling multiple items in bulk response."""
        data = {
            "items": [{"id": "123"}, {"id": "456"}],
            "bulk_operation_id": "op123",
        }
        result = transformer.transform_response(data, "1.1", "1.0")

        # Should keep items when multiple
        assert "items" in result
        assert len(result["items"]) == 2
        assert "bulk_operation_id" not in result

    def test_transform_response_empty_items(self, transformer):
        """Test handling empty items list."""
        data = {"items": [], "bulk_operation_id": "op123"}
        result = transformer.transform_response(data, "1.1", "1.0")

        assert "items" in result
        assert result["items"] == []
        assert "bulk_operation_id" not in result


class TestV1_1ToV2Transformer:
    """Test v1.1 to v2.0 transformer."""

    @pytest.fixture
    def transformer(self):
        """Create transformer instance."""
        return V1_1ToV2Transformer()

    def test_transform_request_snake_to_camel(self, transformer):
        """Test transforming snake_case to camelCase."""
        data = {
            "customer_id": "123-456-7890",
            "analysis_type": "keyword",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "other_field": "unchanged",
        }
        result = transformer.transform_request(data, "1.1", "2.0")

        assert result["customerId"] == "123-456-7890"
        assert result["analysisType"] == "keyword"
        assert result["startDate"] == "2024-01-01"
        assert result["endDate"] == "2024-12-31"
        assert result["other_field"] == "unchanged"

    def test_transform_request_nested_fields(self, transformer):
        """Test transforming nested fields."""
        data = {
            "audit": {
                "customer_id": "123",
                "analysis_type": "negative",
            },
            "metadata": {
                "created_by": "user@example.com",
            },
        }
        result = transformer.transform_request(data, "1.1", "2.0")

        assert result["audit"]["customerId"] == "123"
        assert result["audit"]["analysisType"] == "negative"
        assert result["metadata"]["created_by"] == "user@example.com"

    def test_transform_response_camel_to_snake(self, transformer):
        """Test transforming camelCase to snake_case."""
        data = {
            "customerId": "123-456-7890",
            "analysisType": "keyword",
            "startDate": "2024-01-01",
            "endDate": "2024-12-31",
            "createdAt": "2024-01-01T00:00:00Z",
            "updatedAt": "2024-01-02T00:00:00Z",
        }
        result = transformer.transform_response(data, "2.0", "1.1")

        assert result["customer_id"] == "123-456-7890"
        assert result["analysis_type"] == "keyword"
        assert result["start_date"] == "2024-01-01"
        assert result["end_date"] == "2024-12-31"
        assert result["created_at"] == "2024-01-01T00:00:00Z"
        assert result["updated_at"] == "2024-01-02T00:00:00Z"

    def test_transform_response_nested_transformation(self, transformer):
        """Test recursive transformation of nested structures."""
        data = {
            "audit": {
                "customerId": "123",
                "analysisType": "negative",
                "results": [
                    {"keywordId": "k1", "matchType": "exact"},
                    {"keywordId": "k2", "matchType": "phrase"},
                ],
            }
        }
        result = transformer.transform_response(data, "2.0", "1.1")

        assert result["audit"]["customer_id"] == "123"
        assert result["audit"]["analysis_type"] == "negative"
        assert result["audit"]["results"][0]["keywordId"] == "k1"
        assert result["audit"]["results"][1]["keywordId"] == "k2"


class TestFieldRenameTransformer:
    """Test generic field rename transformer."""

    def test_basic_field_rename(self):
        """Test basic field renaming."""
        mappings = {
            "old_name": "new_name",
            "legacy_field": "modern_field",
        }
        transformer = FieldRenameTransformer(mappings)

        data = {
            "old_name": "value1",
            "legacy_field": "value2",
            "unchanged": "value3",
        }
        result = transformer.transform_request(data, "1.0", "2.0")

        assert result["new_name"] == "value1"
        assert result["modern_field"] == "value2"
        assert result["unchanged"] == "value3"
        assert "old_name" not in result
        assert "legacy_field" not in result

    def test_reverse_transformation(self):
        """Test reverse transformation in responses."""
        mappings = {"request_field": "response_field"}
        transformer = FieldRenameTransformer(mappings)

        # Request transformation
        request_data = {"request_field": "value"}
        request_result = transformer.transform_request(request_data, "1.0", "2.0")
        assert request_result["response_field"] == "value"

        # Response transformation (reverse)
        response_data = {"response_field": "value"}
        response_result = transformer.transform_response(response_data, "2.0", "1.0")
        assert response_result["request_field"] == "value"

    def test_nested_field_rename(self):
        """Test renaming fields in nested structures."""
        mappings = {"old_field": "new_field"}
        transformer = FieldRenameTransformer(mappings)

        data = {
            "top_level": {
                "old_field": "nested_value",
                "nested": {
                    "old_field": "deep_value",
                },
            },
            "old_field": "root_value",
        }
        result = transformer.transform_request(data, "1.0", "2.0")

        assert result["new_field"] == "root_value"
        assert result["top_level"]["new_field"] == "nested_value"
        assert result["top_level"]["nested"]["new_field"] == "deep_value"


class TestResponseFilterTransformer:
    """Test response field filter transformer."""

    def test_basic_filtering(self):
        """Test basic field filtering."""
        allowed_fields = ["id", "name", "status"]
        transformer = ResponseFilterTransformer(allowed_fields)

        data = {
            "id": "123",
            "name": "test",
            "status": "active",
            "secret": "hidden",
            "internal": "private",
        }
        result = transformer.transform_response(data, "2.0", "1.0")

        assert result == {"id": "123", "name": "test", "status": "active"}

    def test_nested_filtering(self):
        """Test filtering nested structures."""
        allowed_fields = ["id", "data", "status"]
        transformer = ResponseFilterTransformer(allowed_fields)

        data = {
            "id": "123",
            "data": {
                "id": "nested-id",
                "secret": "hidden",
                "status": "ok",
            },
            "status": "active",
            "private": "removed",
        }
        result = transformer.transform_response(data, "2.0", "1.0")

        assert "id" in result
        assert "data" in result
        assert "status" in result
        assert "private" not in result

        # Nested object should also be filtered
        assert result["data"]["id"] == "nested-id"
        assert result["data"]["status"] == "ok"
        assert "secret" not in result["data"]

    def test_list_filtering(self):
        """Test filtering lists of objects."""
        allowed_fields = ["id", "name"]
        transformer = ResponseFilterTransformer(allowed_fields)

        data = {
            "results": [
                {"id": "1", "name": "first", "secret": "hidden"},
                {"id": "2", "name": "second", "secret": "hidden"},
            ]
        }
        result = transformer.transform_response(data, "2.0", "1.0")

        # Top level doesn't have allowed fields
        assert result == {}

        # Test with results in allowed fields
        transformer = ResponseFilterTransformer(["results", "id", "name"])
        result = transformer.transform_response(data, "2.0", "1.0")

        assert "results" in result
        assert len(result["results"]) == 2
        assert result["results"][0] == {"id": "1", "name": "first"}
        assert result["results"][1] == {"id": "2", "name": "second"}


class TestDeprecatedFieldTransformer:
    """Test deprecated field transformer."""

    def test_add_deprecated_fields(self):
        """Test adding deprecated fields with defaults."""
        deprecated_fields = {
            "legacy_status": "unknown",
            "old_format": None,
            "deprecated_flag": False,
        }
        transformer = DeprecatedFieldTransformer(deprecated_fields)

        data = {"id": "123", "name": "test"}
        result = transformer.transform_response(data, "2.0", "1.0")

        assert result["id"] == "123"
        assert result["name"] == "test"
        assert result["legacy_status"] == "unknown"
        assert result["old_format"] is None
        assert result["deprecated_flag"] is False

    def test_dont_override_existing_fields(self):
        """Test that existing fields are not overridden."""
        deprecated_fields = {
            "status": "default",
            "type": "unknown",
        }
        transformer = DeprecatedFieldTransformer(deprecated_fields)

        data = {"id": "123", "status": "active", "name": "test"}
        result = transformer.transform_response(data, "2.0", "1.0")

        assert result["status"] == "active"  # Not overridden
        assert result["type"] == "unknown"  # Added

    def test_complex_default_values(self):
        """Test adding complex default values."""
        deprecated_fields = {
            "metadata": {"version": "1.0", "deprecated": True},
            "tags": ["legacy", "v1"],
            "settings": {"feature_flags": {"old_ui": True}},
        }
        transformer = DeprecatedFieldTransformer(deprecated_fields)

        data = {"id": "123"}
        result = transformer.transform_response(data, "2.0", "1.0")

        assert result["metadata"] == {"version": "1.0", "deprecated": True}
        assert result["tags"] == ["legacy", "v1"]
        assert result["settings"]["feature_flags"]["old_ui"] is True


class TestTransformerInitialization:
    """Test transformer initialization and registration."""

    def test_initialize_transformers(self):
        """Test that transformers are properly initialized."""
        # Clear registry first
        transformer_registry._transformers.clear()

        # Initialize transformers
        initialize_transformers()

        # Check that transformers are registered
        assert transformer_registry.get_transformer("1.0", "1.1") is not None
        assert transformer_registry.get_transformer("1.1", "2.0") is not None

        # Check transformer types
        v1_to_v1_1 = transformer_registry.get_transformer("1.0", "1.1")
        assert isinstance(v1_to_v1_1, V1ToV1_1Transformer)

        v1_1_to_v2 = transformer_registry.get_transformer("1.1", "2.0")
        assert isinstance(v1_1_to_v2, V1_1ToV2Transformer)

    def test_transformer_chaining(self):
        """Test that transformers can be chained for multi-version hops."""
        # This would be a future enhancement - transforming through multiple versions
        # For now, verify that direct transformers exist
        initialize_transformers()

        # Direct transformers
        assert transformer_registry.get_transformer("1.0", "1.1") is not None
        assert transformer_registry.get_transformer("1.1", "2.0") is not None

        # No direct transformer from 1.0 to 2.0 (except the field rename example)
        # In a real system, you might chain 1.0->1.1->2.0
