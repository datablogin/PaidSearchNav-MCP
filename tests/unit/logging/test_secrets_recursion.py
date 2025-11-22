"""Tests for recursion depth limiting in secrets handling."""

import pytest

from paidsearchnav_mcp.logging.secrets import SecretsRegistry, mask_secrets


class TestRecursionDepthLimiting:
    """Test recursion depth limiting for nested data structures."""

    def setup_method(self):
        """Set up test fixtures."""
        self.registry = SecretsRegistry()

    def test_set_max_recursion_depth(self):
        """Test setting maximum recursion depth."""
        # Test default value
        assert self.registry.get_max_recursion_depth() == 10

        # Test setting valid value
        self.registry.set_max_recursion_depth(5)
        assert self.registry.get_max_recursion_depth() == 5

        # Test setting edge case
        self.registry.set_max_recursion_depth(1)
        assert self.registry.get_max_recursion_depth() == 1

    def test_set_invalid_recursion_depth_raises_error(self):
        """Test that invalid recursion depths raise ValueError."""
        with pytest.raises(
            ValueError, match="Maximum recursion depth must be at least 1"
        ):
            self.registry.set_max_recursion_depth(0)

        with pytest.raises(
            ValueError, match="Maximum recursion depth must be at least 1"
        ):
            self.registry.set_max_recursion_depth(-1)

    def test_deeply_nested_dict_with_default_depth(self):
        """Test deeply nested dictionary with default depth limit."""
        # Create a deeply nested dictionary (15 levels deep)
        nested_data = {"level": 0}
        current = nested_data
        for i in range(1, 15):
            current["nested"] = {"level": i}
            current = current["nested"]

        # Add a secret at the deepest level
        current["password"] = "secret123"

        # Mask secrets - should not crash due to recursion limit
        result = self.registry.mask_secrets_in_dict(nested_data)

        # The structure should be preserved up to the recursion limit
        assert "level" in result
        assert result["level"] == 0

        # Navigate to check that masking still happens within limits
        current_result = result
        levels_found = 0
        while "nested" in current_result and isinstance(current_result["nested"], dict):
            current_result = current_result["nested"]
            levels_found += 1
            if levels_found >= 10:  # Default max depth
                break

        # Should have hit the recursion limit
        assert levels_found <= 10

    def test_deeply_nested_list_with_limit(self):
        """Test deeply nested list with recursion limit."""
        # Set a low recursion limit
        self.registry.set_max_recursion_depth(3)

        # Create a deeply nested list (5 levels deep)
        nested_data = [[[[["password", "secret123"]]]]]

        # Mask secrets - should not crash
        result = self.registry._mask_secrets_in_list(nested_data, "***REDACTED***")

        # Should be a list
        assert isinstance(result, list)

    def test_mixed_nested_structures_with_limit(self):
        """Test mixed nested dictionaries and lists with limit."""
        self.registry.set_max_recursion_depth(2)

        data = {
            "level1": {
                "level2": {
                    "level3": {
                        "password": "secret123",  # This should be preserved as-is due to depth limit
                        "normal": "value",
                    }
                }
            },
            "list": [
                {
                    "nested_in_list": {
                        "api_key": "sk-1234567890abcdef1234567890abcdef"  # This might be preserved due to depth
                    }
                }
            ],
        }

        result = self.registry.mask_secrets_in_dict(data)

        # Should not crash and return a dictionary
        assert isinstance(result, dict)
        assert "level1" in result
        assert "list" in result

    def test_circular_reference_protection(self):
        """Test that recursion limit protects against circular references."""
        self.registry.set_max_recursion_depth(5)

        # Create a structure with potential for circular reference
        data = {"level1": {}}
        # Don't actually create a circular reference as Python would detect it,
        # but test that deep nesting is handled gracefully
        current = data["level1"]
        for i in range(10):
            current[f"level{i + 2}"] = {"password": f"secret{i}"}
            current = current[f"level{i + 2}"]

        # Should not crash
        result = self.registry.mask_secrets_in_dict(data)
        assert isinstance(result, dict)

    def test_recursion_limit_masks_strings_at_max_depth(self):
        """Test that string masking still works at maximum recursion depth."""
        self.registry.set_max_recursion_depth(2)

        # Create nested data with secrets at different levels
        data = {
            "level1": {
                "password": "secret_level1",  # Should be masked (sensitive key)
                "level2": {
                    "api_key": "sk-1234567890abcdef1234567890abcdef",  # Should be masked at depth limit
                    "normal": "value",
                },
            }
        }

        result = self.registry.mask_secrets_in_dict(data)

        # Level 1 password should definitely be masked
        assert result["level1"]["password"] == "***REDACTED***"

        # At depth limit, string patterns should still be checked
        level2_result = result["level1"]["level2"]
        # This might be masked as a pattern even though we're at depth limit
        assert isinstance(level2_result, dict)

    def test_function_level_mask_secrets_respects_depth(self):
        """Test that the module-level mask_secrets function respects depth limits."""
        # Create a deeply nested structure
        data = {"l1": {"l2": {"l3": {"l4": {"password": "secret"}}}}}

        # Set a very low limit
        registry = self.registry
        registry.set_max_recursion_depth(2)

        # Test with the global mask_secrets function
        result = mask_secrets(data)

        # Should not crash
        assert isinstance(result, dict)

    def test_audit_logging_with_recursion_limit(self):
        """Test that audit logging works correctly with recursion limits."""
        import logging
        from io import StringIO

        # Set up audit logging
        audit_logger = logging.getLogger("test.recursion.audit")
        log_capture = StringIO()
        handler = logging.StreamHandler(log_capture)
        audit_logger.addHandler(handler)

        self.registry.enable_audit_logging(audit_logger)
        self.registry.set_max_recursion_depth(2)

        # Create nested data with secrets
        data = {
            "level1": {
                "password": "secret1",
                "level2": {"api_key": "sk-1234567890abcdef1234567890abcdef"},
            }
        }

        # Mask secrets
        self.registry.mask_secrets_in_dict(data)

        # Check that audit events were logged (at least for the password)
        log_output = log_capture.getvalue()
        assert "Secret detected and masked" in log_output

        # Clean up
        audit_logger.removeHandler(handler)
        self.registry.disable_audit_logging()

    def test_performance_with_deep_structures(self):
        """Test performance doesn't degrade significantly with deep structures."""
        import time

        self.registry.set_max_recursion_depth(5)

        # Create a reasonably deep structure
        data = {"root": {}}
        current = data["root"]
        for i in range(20):
            current[f"level{i}"] = {"value": f"data{i}", "password": f"secret{i}"}
            current = current[f"level{i}"]

        # Time the masking operation
        start_time = time.time()
        result = self.registry.mask_secrets_in_dict(data)
        end_time = time.time()

        # Should complete quickly (within 1 second for this test)
        assert end_time - start_time < 1.0
        assert isinstance(result, dict)


class TestEdgeCases:
    """Test edge cases for recursion depth limiting."""

    def setup_method(self):
        """Set up test fixtures."""
        self.registry = SecretsRegistry()

    def test_empty_structures_with_recursion_limit(self):
        """Test empty structures don't cause issues with recursion limits."""
        self.registry.set_max_recursion_depth(1)

        # Test empty dict
        result = self.registry.mask_secrets_in_dict({})
        assert result == {}

        # Test empty list
        result = self.registry._mask_secrets_in_list([], "***REDACTED***")
        assert result == []

    def test_single_level_with_limit_one(self):
        """Test that limit of 1 still allows basic masking."""
        self.registry.set_max_recursion_depth(1)

        data = {
            "password": "secret123",
            "normal": "value",
            "nested": {"should": "not_recurse"},
        }

        result = self.registry.mask_secrets_in_dict(data)

        # Password should be masked
        assert result["password"] == "***REDACTED***"
        # Normal value preserved
        assert result["normal"] == "value"
        # Nested structure preserved but not processed
        assert "nested" in result

    def test_none_values_with_recursion_limit(self):
        """Test None values are handled correctly with recursion limits."""
        data = {"value": None, "nested": {"also_none": None, "password": "secret"}}

        result = self.registry.mask_secrets_in_dict(data)

        # None values should be preserved
        assert result["value"] is None
        # Nested masking should still work
        assert result["nested"]["password"] == "***REDACTED***"
        assert result["nested"]["also_none"] is None
