"""Tests for metrics validation functions."""

import pytest

from paidsearchnav.core.constants import MAX_COST_MICROS, MAX_REVENUE_MICROS
from paidsearchnav.core.validation.metrics import (
    MetricsValidationError,
    validate_cost_micros,
    validate_integer,
    validate_metrics_data,
    validate_percentage,
    validate_positive_number,
    validate_revenue_micros,
)


class TestMetricsValidationError:
    """Test MetricsValidationError exception."""

    def test_basic_error(self):
        """Test basic error creation."""
        error = MetricsValidationError("Test message")
        assert str(error) == "Test message"
        assert error.field is None
        assert error.value is None

    def test_error_with_field_and_value(self):
        """Test error with field and value context."""
        error = MetricsValidationError("Test message", field="cost", value=100.0)
        assert str(error) == "Test message"
        assert error.field == "cost"
        assert error.value == 100.0


class TestValidateCostMicros:
    """Test validate_cost_micros function."""

    def test_valid_cost_micros(self):
        """Test valid cost micros conversion."""
        assert validate_cost_micros(1_000_000) == 1.0
        assert validate_cost_micros(2_500_000) == 2.5
        assert validate_cost_micros(0) == 0.0

    def test_none_input(self):
        """Test None input returns 0.0."""
        assert validate_cost_micros(None) == 0.0

    def test_string_numeric_input(self):
        """Test string numeric input is converted."""
        assert validate_cost_micros("1000000") == 1.0
        assert validate_cost_micros("2500000") == 2.5

    def test_negative_cost_raises_error(self):
        """Test negative cost raises error."""
        with pytest.raises(MetricsValidationError) as exc_info:
            validate_cost_micros(-1000000)

        error = exc_info.value
        assert "cannot be negative" in str(error)
        assert error.field == "cost_micros"
        assert error.value == -1000000.0

    def test_excessive_cost_raises_error(self):
        """Test excessive cost raises error."""
        excessive_cost = MAX_COST_MICROS + 1

        with pytest.raises(MetricsValidationError) as exc_info:
            validate_cost_micros(excessive_cost)

        error = exc_info.value
        assert "exceeds maximum reasonable value" in str(error)
        assert error.field == "cost_micros"

    def test_invalid_type_raises_error(self):
        """Test invalid type raises error."""
        with pytest.raises(MetricsValidationError) as exc_info:
            validate_cost_micros("invalid")

        error = exc_info.value
        assert "must be numeric" in str(error)
        assert error.field == "cost_micros"

    def test_boundary_values(self):
        """Test boundary values."""
        # Test maximum allowed value
        assert validate_cost_micros(MAX_COST_MICROS) == MAX_COST_MICROS / 1_000_000

        # Test just above zero
        assert validate_cost_micros(1) == 1 / 1_000_000


class TestValidateRevenueMicros:
    """Test validate_revenue_micros function."""

    def test_valid_revenue_micros(self):
        """Test valid revenue micros conversion."""
        assert validate_revenue_micros(1_000_000) == 1.0
        assert validate_revenue_micros(5_000_000) == 5.0
        assert validate_revenue_micros(0) == 0.0

    def test_none_input(self):
        """Test None input returns 0.0."""
        assert validate_revenue_micros(None) == 0.0

    def test_negative_revenue_raises_error(self):
        """Test negative revenue raises error."""
        with pytest.raises(MetricsValidationError) as exc_info:
            validate_revenue_micros(-1000000)

        error = exc_info.value
        assert "cannot be negative" in str(error)
        assert error.field == "revenue_micros"

    def test_excessive_revenue_raises_error(self):
        """Test excessive revenue raises error."""
        excessive_revenue = MAX_REVENUE_MICROS + 1

        with pytest.raises(MetricsValidationError) as exc_info:
            validate_revenue_micros(excessive_revenue)

        error = exc_info.value
        assert "exceeds maximum reasonable value" in str(error)
        assert error.field == "revenue_micros"


class TestValidatePercentage:
    """Test validate_percentage function."""

    def test_valid_percentages(self):
        """Test valid percentage values."""
        assert validate_percentage(50.0, "test_field") == 50.0
        assert validate_percentage(0, "test_field") == 0.0
        assert validate_percentage(100, "test_field") == 100.0

    def test_none_input(self):
        """Test None input returns 0.0."""
        assert validate_percentage(None, "test_field") == 0.0

    def test_custom_range(self):
        """Test custom min/max range."""
        assert validate_percentage(150, "test_field", min_val=0, max_val=200) == 150.0

    def test_out_of_range_raises_error(self):
        """Test out of range values raise error."""
        with pytest.raises(MetricsValidationError) as exc_info:
            validate_percentage(150, "test_field")

        error = exc_info.value
        assert "must be between 0.0 and 100.0" in str(error)
        assert error.field == "test_field"

    def test_invalid_type_raises_error(self):
        """Test invalid type raises error."""
        with pytest.raises(MetricsValidationError) as exc_info:
            validate_percentage("invalid", "test_field")

        error = exc_info.value
        assert "must be numeric" in str(error)
        assert error.field == "test_field"


class TestValidatePositiveNumber:
    """Test validate_positive_number function."""

    def test_valid_positive_numbers(self):
        """Test valid positive numbers."""
        assert validate_positive_number(5.0, "test_field") == 5.0
        assert (
            validate_positive_number(0.0, "test_field") == 0.0
        )  # Zero allowed by default

    def test_none_input(self):
        """Test None input returns 0.0."""
        assert validate_positive_number(None, "test_field") == 0.0

    def test_negative_with_zero_allowed(self):
        """Test negative number with zero allowed raises error."""
        with pytest.raises(MetricsValidationError) as exc_info:
            validate_positive_number(-5.0, "test_field", allow_zero=True)

        error = exc_info.value
        assert "cannot be negative" in str(error)
        assert error.field == "test_field"

    def test_zero_not_allowed(self):
        """Test zero when not allowed raises error."""
        with pytest.raises(MetricsValidationError) as exc_info:
            validate_positive_number(0.0, "test_field", allow_zero=False)

        error = exc_info.value
        assert "must be positive" in str(error)
        assert error.field == "test_field"

    def test_negative_not_allowed(self):
        """Test negative when zero not allowed raises error."""
        with pytest.raises(MetricsValidationError) as exc_info:
            validate_positive_number(-1.0, "test_field", allow_zero=False)

        error = exc_info.value
        assert "must be positive" in str(error)
        assert error.field == "test_field"


class TestValidateInteger:
    """Test validate_integer function."""

    def test_valid_integers(self):
        """Test valid integer values."""
        assert validate_integer(5, "test_field") == 5
        assert validate_integer(0, "test_field") == 0
        assert validate_integer("10", "test_field") == 10  # String conversion

    def test_none_input(self):
        """Test None input returns 0."""
        assert validate_integer(None, "test_field") == 0

    def test_float_conversion(self):
        """Test float is converted to integer."""
        assert validate_integer(5.7, "test_field") == 5

    def test_below_minimum_raises_error(self):
        """Test value below minimum raises error."""
        with pytest.raises(MetricsValidationError) as exc_info:
            validate_integer(-5, "test_field", min_val=0)

        error = exc_info.value
        assert "must be >= 0" in str(error)
        assert error.field == "test_field"

    def test_custom_minimum(self):
        """Test custom minimum value."""
        assert validate_integer(10, "test_field", min_val=5) == 10

    def test_invalid_type_raises_error(self):
        """Test invalid type raises error."""
        with pytest.raises(MetricsValidationError) as exc_info:
            validate_integer("invalid", "test_field")

        error = exc_info.value
        assert "must be an integer" in str(error)
        assert error.field == "test_field"


class TestValidateMetricsData:
    """Test validate_metrics_data function."""

    def test_complete_metrics_validation(self):
        """Test complete metrics data validation."""
        data = {
            "cost_micros": 2_000_000,
            "revenue_micros": 5_000_000,
            "impressions": 1000,
            "clicks": 50,
            "conversions": 5,
            "conversions_value": 250.0,
        }

        result = validate_metrics_data(data)

        assert result["cost"] == 2.0
        assert result["revenue"] == 5.0
        assert result["impressions"] == 1000
        assert result["clicks"] == 50
        assert result["conversions"] == 5
        assert result["conversions_value"] == 250.0

        # Check derived metrics
        assert result["ctr"] == 5.0  # (50/1000) * 100
        assert result["cpa"] == 0.4  # 2.0/5
        assert result["roas"] == 2.5  # 5.0/2.0

    def test_partial_metrics_validation(self):
        """Test validation with partial data."""
        data = {
            "cost_micros": 1_000_000,
            "impressions": 500,
        }

        result = validate_metrics_data(data)

        assert result["cost"] == 1.0
        assert result["impressions"] == 500
        assert "revenue" not in result
        assert "ctr" not in result  # No clicks data
        assert "cpa" not in result  # No conversions data

    def test_derived_metrics_calculations(self):
        """Test derived metrics are calculated correctly."""
        data = {
            "impressions": 2000,
            "clicks": 100,
            "conversions": 10,
            "cost_micros": 5_000_000,
            "revenue_micros": 15_000_000,
        }

        result = validate_metrics_data(data)

        # CTR = (clicks / impressions) * 100 = (100/2000) * 100 = 5%
        assert result["ctr"] == 5.0

        # CPA = cost / conversions = 5.0 / 10 = 0.5
        assert result["cpa"] == 0.5

        # ROAS = revenue / cost = 15.0 / 5.0 = 3.0
        assert result["roas"] == 3.0

    def test_invalid_metrics_raises_error(self):
        """Test invalid metrics raise appropriate errors."""
        data = {
            "cost_micros": -1000000,  # Negative cost
            "impressions": 100,
        }

        with pytest.raises(MetricsValidationError):
            validate_metrics_data(data)

    def test_empty_data(self):
        """Test empty data returns empty result."""
        result = validate_metrics_data({})
        assert result == {}

    def test_zero_division_safety(self):
        """Test zero division is handled safely."""
        data = {
            "impressions": 0,
            "clicks": 0,
            "conversions": 0,
            "cost_micros": 0,
        }

        result = validate_metrics_data(data)

        assert result["impressions"] == 0
        assert result["clicks"] == 0
        assert result["conversions"] == 0
        assert result["cost"] == 0.0

        # No derived metrics should be calculated with zero values
        assert "ctr" not in result
        assert "cpa" not in result
        assert "roas" not in result
