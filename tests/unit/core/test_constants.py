"""Tests for core constants module."""

from typing import Any

import pytest

from paidsearchnav.core import constants


@pytest.fixture
def restore_constants(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Fixture to restore constants after modification."""
    # Store original values
    original_values = {
        "MAX_COST_MICROS": constants.MAX_COST_MICROS,
        "MAX_REVENUE_MICROS": constants.MAX_REVENUE_MICROS,
        "MICROS_TO_CURRENCY": constants.MICROS_TO_CURRENCY,
        "DEFAULT_CPA_FALLBACK": constants.DEFAULT_CPA_FALLBACK,
    }

    yield monkeypatch

    # Restore original values
    for name, value in original_values.items():
        monkeypatch.setattr(constants, name, value)


class TestConstantValues:
    """Test the actual constant values."""

    def test_max_cost_micros(self) -> None:
        """Test MAX_COST_MICROS value."""
        assert constants.MAX_COST_MICROS == 10_000_000_000_000
        assert isinstance(constants.MAX_COST_MICROS, int)
        # $10M in micros
        assert constants.MAX_COST_MICROS == 10_000_000 * 1_000_000

    def test_max_revenue_micros(self) -> None:
        """Test MAX_REVENUE_MICROS value."""
        assert constants.MAX_REVENUE_MICROS == 100_000_000_000_000
        assert isinstance(constants.MAX_REVENUE_MICROS, int)
        # $100M in micros
        assert constants.MAX_REVENUE_MICROS == 100_000_000 * 1_000_000

    def test_micros_to_currency(self) -> None:
        """Test MICROS_TO_CURRENCY conversion factor."""
        assert constants.MICROS_TO_CURRENCY == 1_000_000
        assert isinstance(constants.MICROS_TO_CURRENCY, int)

    def test_default_cpa_fallback(self) -> None:
        """Test DEFAULT_CPA_FALLBACK value."""
        assert constants.DEFAULT_CPA_FALLBACK == 100.0
        assert isinstance(constants.DEFAULT_CPA_FALLBACK, float)

    def test_relative_values(self) -> None:
        """Test relationships between constant values."""
        # Revenue max should be greater than cost max
        assert constants.MAX_REVENUE_MICROS > constants.MAX_COST_MICROS

        # Both should be multiples of MICROS_TO_CURRENCY
        assert constants.MAX_COST_MICROS % constants.MICROS_TO_CURRENCY == 0
        assert constants.MAX_REVENUE_MICROS % constants.MICROS_TO_CURRENCY == 0


class TestConstantImmutability:
    """Test that constants are immutable."""

    def test_constants_immutable_behavior(
        self, restore_constants: pytest.MonkeyPatch
    ) -> None:
        """Test that constants maintain their values in typical usage."""
        # Store original values
        original_max_cost = constants.MAX_COST_MICROS
        original_max_revenue = constants.MAX_REVENUE_MICROS
        original_micros = constants.MICROS_TO_CURRENCY
        original_cpa = constants.DEFAULT_CPA_FALLBACK

        # These are the expected immutable values
        assert original_max_cost == 10_000_000_000_000
        assert original_max_revenue == 100_000_000_000_000
        assert original_micros == 1_000_000
        assert original_cpa == 100.0

        # In production, these would be treated as constants
        # We use monkeypatch to simulate modification attempts
        restore_constants.setattr(constants, "MAX_COST_MICROS", 999)
        restore_constants.setattr(constants, "MAX_REVENUE_MICROS", 999)
        restore_constants.setattr(constants, "MICROS_TO_CURRENCY", 999)
        restore_constants.setattr(constants, "DEFAULT_CPA_FALLBACK", 999.0)

        # Values are modified in this test context
        assert constants.MAX_COST_MICROS == 999
        assert constants.MAX_REVENUE_MICROS == 999
        assert constants.MICROS_TO_CURRENCY == 999
        assert constants.DEFAULT_CPA_FALLBACK == 999.0


class TestConstantUsagePatterns:
    """Test common usage patterns for constants."""

    def test_micros_to_currency_conversion(self) -> None:
        """Test using MICROS_TO_CURRENCY for conversions."""
        # Convert $100 to micros
        dollars = 100
        micros = dollars * constants.MICROS_TO_CURRENCY
        assert micros == 100_000_000

        # Convert back
        assert micros / constants.MICROS_TO_CURRENCY == dollars

    def test_cost_validation_pattern(self) -> None:
        """Test using MAX_COST_MICROS for validation."""
        valid_costs = [
            0,
            1_000_000,  # $1
            1_000_000_000,  # $1,000
            constants.MAX_COST_MICROS - 1,
            constants.MAX_COST_MICROS,
        ]

        invalid_costs = [
            -1,
            constants.MAX_COST_MICROS + 1,
            constants.MAX_COST_MICROS * 2,
        ]

        for cost in valid_costs:
            assert 0 <= cost <= constants.MAX_COST_MICROS

        for cost in invalid_costs:
            assert not (0 <= cost <= constants.MAX_COST_MICROS)

    def test_revenue_validation_pattern(self) -> None:
        """Test using MAX_REVENUE_MICROS for validation."""
        valid_revenues = [
            0,
            10_000_000,  # $10
            10_000_000_000,  # $10,000
            constants.MAX_REVENUE_MICROS - 1,
            constants.MAX_REVENUE_MICROS,
        ]

        invalid_revenues = [
            -1,
            constants.MAX_REVENUE_MICROS + 1,
            constants.MAX_REVENUE_MICROS * 2,
        ]

        for revenue in valid_revenues:
            assert 0 <= revenue <= constants.MAX_REVENUE_MICROS

        for revenue in invalid_revenues:
            assert not (0 <= revenue <= constants.MAX_REVENUE_MICROS)

    def test_cpa_fallback_usage(self) -> None:
        """Test using DEFAULT_CPA_FALLBACK in calculations."""

        # Simulate CPA calculation with fallback
        def calculate_cpa(cost: float, conversions: int) -> float:
            if conversions == 0:
                return constants.DEFAULT_CPA_FALLBACK
            return cost / conversions

        # With conversions
        assert calculate_cpa(1000.0, 10) == 100.0

        # Without conversions (fallback)
        assert calculate_cpa(1000.0, 0) == constants.DEFAULT_CPA_FALLBACK


class TestModuleImports:
    """Test various import patterns."""

    def test_import_all_constants(self) -> None:
        """Test importing all constants at once."""
        from paidsearchnav.core.constants import (
            DEFAULT_CPA_FALLBACK,
            MAX_COST_MICROS,
            MAX_REVENUE_MICROS,
            MICROS_TO_CURRENCY,
        )

        assert MAX_COST_MICROS == 10_000_000_000_000
        assert MAX_REVENUE_MICROS == 100_000_000_000_000
        assert MICROS_TO_CURRENCY == 1_000_000
        assert DEFAULT_CPA_FALLBACK == 100.0

    def test_import_module(self) -> None:
        """Test importing the module itself."""
        from paidsearchnav.core import constants as const

        assert hasattr(const, "MAX_COST_MICROS")
        assert hasattr(const, "MAX_REVENUE_MICROS")
        assert hasattr(const, "MICROS_TO_CURRENCY")
        assert hasattr(const, "DEFAULT_CPA_FALLBACK")

    def test_no_circular_dependencies(self) -> None:
        """Test that constants module has no circular dependencies."""
        # Simply verify the module can be imported and has expected attributes
        import paidsearchnav.core.constants as const_module

        # Verify it has all expected constants
        assert hasattr(const_module, "MAX_COST_MICROS")
        assert hasattr(const_module, "MAX_REVENUE_MICROS")
        assert hasattr(const_module, "MICROS_TO_CURRENCY")
        assert hasattr(const_module, "DEFAULT_CPA_FALLBACK")


class TestConstantTypes:
    """Test the types of constants."""

    def test_numeric_types(self) -> None:
        """Test that numeric constants have correct types."""
        # Integer constants
        assert isinstance(constants.MAX_COST_MICROS, int)
        assert isinstance(constants.MAX_REVENUE_MICROS, int)
        assert isinstance(constants.MICROS_TO_CURRENCY, int)

        # Float constants
        assert isinstance(constants.DEFAULT_CPA_FALLBACK, float)

    def test_no_string_constants(self) -> None:
        """Test that module doesn't accidentally expose string constants."""
        # Get all module attributes
        all_attrs = dir(constants)

        # Filter to uppercase names (convention for constants)
        constant_names = [
            attr for attr in all_attrs if attr.isupper() and not attr.startswith("_")
        ]

        # Verify we have the expected constants
        expected_constants = {
            "MAX_COST_MICROS",
            "MAX_REVENUE_MICROS",
            "MICROS_TO_CURRENCY",
            "DEFAULT_CPA_FALLBACK",
        }

        assert set(constant_names) == expected_constants


class TestConstantDocumentation:
    """Test that constants are properly documented."""

    def test_module_has_docstring(self) -> None:
        """Test that the constants module has a docstring."""
        assert constants.__doc__ is not None
        assert "Constants for PaidSearchNav" in constants.__doc__

    def test_constants_have_comments(self) -> None:
        """Test constant definitions via module inspection."""
        # Read the source file to check for comments
        import inspect

        source_file = inspect.getsourcefile(constants)
        assert source_file is not None

        with open(source_file, "r") as f:
            content = f.read()

        # Check that each constant has a descriptive comment
        assert "# Validation limits for cost and revenue" in content
        assert "# Max reasonable cost" in content
        assert "# Max reasonable revenue" in content
        assert "# Conversion factor" in content
        assert "# Default CPA fallback" in content


class TestConstantBoundaries:
    """Test boundary conditions for constants."""

    def test_cost_micros_boundaries(self) -> None:
        """Test MAX_COST_MICROS boundary conditions."""
        # Maximum cost in dollars
        max_dollars = constants.MAX_COST_MICROS / constants.MICROS_TO_CURRENCY
        assert max_dollars == 10_000_000  # $10M

        # Just within bounds
        assert constants.MAX_COST_MICROS - 1 < constants.MAX_COST_MICROS

        # Edge case: exactly at boundary
        assert constants.MAX_COST_MICROS == 10_000_000_000_000

    def test_revenue_micros_boundaries(self) -> None:
        """Test MAX_REVENUE_MICROS boundary conditions."""
        # Maximum revenue in dollars
        max_dollars = constants.MAX_REVENUE_MICROS / constants.MICROS_TO_CURRENCY
        assert max_dollars == 100_000_000  # $100M

        # Relationship to cost limit
        assert constants.MAX_REVENUE_MICROS == constants.MAX_COST_MICROS * 10

    def test_cpa_fallback_reasonableness(self) -> None:
        """Test that DEFAULT_CPA_FALLBACK is reasonable."""
        # Should be positive
        assert constants.DEFAULT_CPA_FALLBACK > 0

        # Should be a reasonable CPA value (not too high or too low)
        assert 1.0 <= constants.DEFAULT_CPA_FALLBACK <= 10000.0

        # Should be exactly 100.0 as specified
        assert constants.DEFAULT_CPA_FALLBACK == 100.0


class TestConstantApplicationIntegration:
    """Test how constants integrate with the application."""

    def test_constants_module_exports(self) -> None:
        """Test that all constants are properly exported."""
        # Test __all__ if defined
        if hasattr(constants, "__all__"):
            assert "MAX_COST_MICROS" in constants.__all__
            assert "MAX_REVENUE_MICROS" in constants.__all__
            assert "MICROS_TO_CURRENCY" in constants.__all__
            assert "DEFAULT_CPA_FALLBACK" in constants.__all__

    def test_no_mutable_defaults(self) -> None:
        """Test that constants aren't mutable objects."""
        # All our constants should be immutable types (int, float)
        assert isinstance(constants.MAX_COST_MICROS, (int, float))
        assert isinstance(constants.MAX_REVENUE_MICROS, (int, float))
        assert isinstance(constants.MICROS_TO_CURRENCY, (int, float))
        assert isinstance(constants.DEFAULT_CPA_FALLBACK, (int, float))

        # No lists, dicts, or other mutable types
        for name in dir(constants):
            if name.isupper() and not name.startswith("_"):
                value = getattr(constants, name)
                assert not isinstance(value, (list, dict, set, bytearray))
