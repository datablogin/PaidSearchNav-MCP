"""Validation utilities for metrics data."""

import logging
from typing import Any, Optional

from paidsearchnav.core.constants import (
    MAX_COST_MICROS,
    MAX_REVENUE_MICROS,
    MICROS_TO_CURRENCY,
)

logger = logging.getLogger(__name__)


class MetricsValidationError(ValueError):
    """Raised when metrics validation fails."""

    def __init__(self, message: str, field: Optional[str] = None, value: Any = None):
        super().__init__(message)
        self.field = field
        self.value = value


def validate_cost_micros(cost_micros: Any) -> float:
    """Validate and convert cost from micros to currency units.

    Args:
        cost_micros: Cost value in micros (1/1,000,000 of currency unit)

    Returns:
        Validated cost in currency units

    Raises:
        MetricsValidationError: If cost_micros is invalid
    """
    if cost_micros is None:
        return 0.0

    try:
        cost_micros_float = float(cost_micros)
    except (ValueError, TypeError) as e:
        raise MetricsValidationError(
            f"Cost micros must be numeric, got {type(cost_micros).__name__}: {cost_micros}",
            field="cost_micros",
            value=cost_micros,
        ) from e

    # Validate non-negative
    if cost_micros_float < 0:
        raise MetricsValidationError(
            f"Cost micros cannot be negative: {cost_micros_float}",
            field="cost_micros",
            value=cost_micros_float,
        )

    # Validate reasonable range (protect against overflow)
    if cost_micros_float > MAX_COST_MICROS:
        raise MetricsValidationError(
            f"Cost micros exceeds maximum reasonable value: {cost_micros_float} > {MAX_COST_MICROS}",
            field="cost_micros",
            value=cost_micros_float,
        )

    # Convert to currency units
    return cost_micros_float / MICROS_TO_CURRENCY


def validate_revenue_micros(revenue_micros: Any) -> float:
    """Validate and convert revenue from micros to currency units.

    Args:
        revenue_micros: Revenue value in micros (1/1,000,000 of currency unit)

    Returns:
        Validated revenue in currency units

    Raises:
        MetricsValidationError: If revenue_micros is invalid
    """
    if revenue_micros is None:
        return 0.0

    try:
        revenue_micros_float = float(revenue_micros)
    except (ValueError, TypeError) as e:
        raise MetricsValidationError(
            f"Revenue micros must be numeric, got {type(revenue_micros).__name__}: {revenue_micros}",
            field="revenue_micros",
            value=revenue_micros,
        ) from e

    # Validate non-negative
    if revenue_micros_float < 0:
        raise MetricsValidationError(
            f"Revenue micros cannot be negative: {revenue_micros_float}",
            field="revenue_micros",
            value=revenue_micros_float,
        )

    # Validate reasonable range
    if revenue_micros_float > MAX_REVENUE_MICROS:
        raise MetricsValidationError(
            f"Revenue micros exceeds maximum reasonable value: {revenue_micros_float} > {MAX_REVENUE_MICROS}",
            field="revenue_micros",
            value=revenue_micros_float,
        )

    # Convert to currency units
    return revenue_micros_float / MICROS_TO_CURRENCY


def validate_percentage(
    value: Any, field_name: str, min_val: float = 0.0, max_val: float = 100.0
) -> float:
    """Validate a percentage value.

    Args:
        value: Value to validate
        field_name: Name of the field for error reporting
        min_val: Minimum allowed value (default 0.0)
        max_val: Maximum allowed value (default 100.0)

    Returns:
        Validated percentage value

    Raises:
        MetricsValidationError: If value is invalid
    """
    if value is None:
        return 0.0

    try:
        float_val = float(value)
    except (ValueError, TypeError) as e:
        raise MetricsValidationError(
            f"{field_name} must be numeric, got {type(value).__name__}: {value}",
            field=field_name,
            value=value,
        ) from e

    if float_val < min_val or float_val > max_val:
        raise MetricsValidationError(
            f"{field_name} must be between {min_val} and {max_val}, got: {float_val}",
            field=field_name,
            value=float_val,
        )

    return float_val


def validate_positive_number(
    value: Any, field_name: str, allow_zero: bool = True
) -> float:
    """Validate a positive number.

    Args:
        value: Value to validate
        field_name: Name of the field for error reporting
        allow_zero: Whether zero is allowed (default True)

    Returns:
        Validated positive number

    Raises:
        MetricsValidationError: If value is invalid
    """
    if value is None:
        return 0.0

    try:
        float_val = float(value)
    except (ValueError, TypeError) as e:
        raise MetricsValidationError(
            f"{field_name} must be numeric, got {type(value).__name__}: {value}",
            field=field_name,
            value=value,
        ) from e

    if not allow_zero and float_val <= 0:
        raise MetricsValidationError(
            f"{field_name} must be positive, got: {float_val}",
            field=field_name,
            value=float_val,
        )
    elif allow_zero and float_val < 0:
        raise MetricsValidationError(
            f"{field_name} cannot be negative, got: {float_val}",
            field=field_name,
            value=float_val,
        )

    return float_val


def validate_integer(value: Any, field_name: str, min_val: int = 0) -> int:
    """Validate an integer value.

    Args:
        value: Value to validate
        field_name: Name of the field for error reporting
        min_val: Minimum allowed value (default 0)

    Returns:
        Validated integer value

    Raises:
        MetricsValidationError: If value is invalid
    """
    if value is None:
        return 0

    try:
        int_val = int(value)
    except (ValueError, TypeError) as e:
        raise MetricsValidationError(
            f"{field_name} must be an integer, got {type(value).__name__}: {value}",
            field=field_name,
            value=value,
        ) from e

    if int_val < min_val:
        raise MetricsValidationError(
            f"{field_name} must be >= {min_val}, got: {int_val}",
            field=field_name,
            value=int_val,
        )

    return int_val


def validate_metrics_data(data: dict[str, Any]) -> dict[str, Any]:
    """Validate a complete metrics data dictionary.

    Args:
        data: Dictionary containing metrics data

    Returns:
        Validated metrics data with proper types

    Raises:
        MetricsValidationError: If any metric is invalid
    """
    validated = {}

    # Validate cost and revenue
    if "cost_micros" in data:
        validated["cost"] = validate_cost_micros(data["cost_micros"])
    if "revenue_micros" in data:
        validated["revenue"] = validate_revenue_micros(data["revenue_micros"])

    # Validate integer metrics
    for field in ["impressions", "clicks", "conversions"]:
        if field in data:
            validated[field] = validate_integer(data[field], field)

    # Validate conversion value
    if "conversions_value" in data:
        validated["conversions_value"] = validate_positive_number(
            data["conversions_value"], "conversions_value"
        )

    # Calculate derived metrics with validation
    if validated.get("impressions", 0) > 0 and "clicks" in validated:
        ctr = (validated["clicks"] / validated["impressions"]) * 100
        validated["ctr"] = validate_percentage(ctr, "CTR")

    if validated.get("conversions", 0) > 0 and "cost" in validated:
        cpa = validated["cost"] / validated["conversions"]
        validated["cpa"] = validate_positive_number(cpa, "CPA")

    if validated.get("cost", 0) > 0 and validated.get("revenue", 0) > 0:
        roas = validated["revenue"] / validated["cost"]
        validated["roas"] = validate_positive_number(roas, "ROAS")

    return validated
