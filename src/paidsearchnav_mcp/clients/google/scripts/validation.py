"""Validation utilities for Google Ads Scripts parameters."""

import logging
import re
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)

# Supported Google Ads date ranges
VALID_DATE_RANGES = {
    "TODAY",
    "YESTERDAY",
    "LAST_7_DAYS",
    "LAST_14_DAYS",
    "LAST_30_DAYS",
    "LAST_60_DAYS",  # Added for quarterly analysis
    "LAST_BUSINESS_WEEK",
    "LAST_WEEK_SUN_SAT",
    "LAST_WEEK_MON_SUN",
    "THIS_MONTH",
    "LAST_MONTH",
    "ALL_TIME",
    "CUSTOM_DATE",
    "LAST_90_DAYS",
    "LAST_365_DAYS",
    "THIS_WEEK_SUN_TODAY",
    "THIS_WEEK_MON_TODAY",
    "LAST_WEEK",
    "LAST_2_WEEKS",
}

# Google Ads API error codes that support retries
RETRYABLE_ERROR_CODES = {
    "RATE_LIMIT_EXCEEDED",
    "INTERNAL_ERROR",
    "BACKEND_ERROR",
    "DEADLINE_EXCEEDED",
    "TEMPORARILY_UNAVAILABLE",
    "SERVICE_UNAVAILABLE",
}


class ValidationError(Exception):
    """Exception raised for parameter validation errors."""

    pass


class ParameterValidator:
    """Validates Google Ads Scripts parameters."""

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def validate_date_range(self, date_range: str) -> bool:
        """Validate date_range parameter.

        Args:
            date_range: The date range string to validate

        Returns:
            True if valid

        Raises:
            ValidationError: If date_range is invalid
        """
        if not isinstance(date_range, str):
            raise ValidationError(
                f"date_range must be a string, got {type(date_range)}"
            )

        if date_range not in VALID_DATE_RANGES:
            raise ValidationError(
                f"Invalid date_range '{date_range}'. "
                f"Must be one of: {', '.join(sorted(VALID_DATE_RANGES))}"
            )

        return True

    def validate_customer_id(self, customer_id: Union[str, int]) -> str:
        """Validate and sanitize customer_id parameter.

        Args:
            customer_id: The customer ID to validate

        Returns:
            Sanitized customer ID string

        Raises:
            ValidationError: If customer_id is invalid
        """
        # Convert to string and remove any non-digit characters
        customer_id_str = str(customer_id).replace("-", "").replace(" ", "")

        # Validate format (should be 10 digits)
        if not re.match(r"^\d{10}$", customer_id_str):
            raise ValidationError(
                f"Invalid customer_id '{customer_id}'. "
                "Must be a 10-digit number (with or without dashes)."
            )

        return customer_id_str

    def sanitize_campaign_ids(self, campaign_ids: List[Union[str, int]]) -> List[str]:
        """Sanitize a list of campaign IDs.

        Args:
            campaign_ids: List of campaign IDs to sanitize

        Returns:
            List of sanitized campaign ID strings

        Raises:
            ValidationError: If any campaign ID is invalid
        """
        if not isinstance(campaign_ids, list):
            raise ValidationError(
                f"campaign_ids must be a list, got {type(campaign_ids)}"
            )

        sanitized_ids = []
        for i, campaign_id in enumerate(campaign_ids):
            # Convert to string and ensure it's numeric
            campaign_id_str = str(campaign_id).strip()

            if not re.match(r"^\d+$", campaign_id_str):
                raise ValidationError(
                    f"Invalid campaign_id at index {i}: '{campaign_id}'. "
                    "Campaign IDs must be numeric strings."
                )

            sanitized_ids.append(campaign_id_str)

        return sanitized_ids

    def validate_numeric_threshold(
        self,
        value: Any,
        param_name: str,
        min_value: float = 0.0,
        max_value: Optional[float] = None,
    ) -> float:
        """Validate numeric threshold parameters.

        Args:
            value: The value to validate
            param_name: Name of the parameter for error messages
            min_value: Minimum allowed value
            max_value: Maximum allowed value (optional)

        Returns:
            Validated numeric value

        Raises:
            ValidationError: If value is invalid
        """
        try:
            numeric_value = float(value)
        except (TypeError, ValueError):
            raise ValidationError(
                f"{param_name} must be a numeric value, got {type(value)}"
            )

        if numeric_value < min_value:
            raise ValidationError(
                f"{param_name} must be >= {min_value}, got {numeric_value}"
            )

        if max_value is not None and numeric_value > max_value:
            raise ValidationError(
                f"{param_name} must be <= {max_value}, got {numeric_value}"
            )

        return numeric_value

    def validate_script_parameters(
        self, parameters: Dict[str, Any], script_type: str
    ) -> Dict[str, Any]:
        """Validate all parameters for a specific script type.

        Args:
            parameters: Dictionary of parameters to validate
            script_type: Type of script (for specific validation rules)

        Returns:
            Dictionary of validated and sanitized parameters

        Raises:
            ValidationError: If any parameter is invalid
        """
        validated_params = parameters.copy()

        # Validate common parameters
        if "date_range" in parameters:
            self.validate_date_range(parameters["date_range"])

        if "customer_id" in parameters:
            validated_params["customer_id"] = self.validate_customer_id(
                parameters["customer_id"]
            )

        # Script-specific validations
        if script_type == "performance_max_monitoring":
            self._validate_monitoring_params(validated_params)
        elif script_type == "performance_max_geographic":
            self._validate_geographic_params(validated_params)
        elif script_type == "performance_max_bidding":
            self._validate_bidding_params(validated_params)
        elif script_type == "performance_max_cross_campaign":
            self._validate_cross_campaign_params(validated_params)
        elif script_type == "performance_max_assets":
            self._validate_assets_params(validated_params)

        return validated_params

    def _validate_monitoring_params(self, params: Dict[str, Any]) -> None:
        """Validate Performance Max monitoring script parameters."""
        if "min_spend" in params:
            params["min_spend"] = self.validate_numeric_threshold(
                params["min_spend"], "min_spend", min_value=0.0, max_value=10000.0
            )

        if "target_roas_threshold" in params:
            params["target_roas_threshold"] = self.validate_numeric_threshold(
                params["target_roas_threshold"],
                "target_roas_threshold",
                min_value=0.1,
                max_value=100.0,
            )

        if "locations_of_interest" in params:
            if not isinstance(params["locations_of_interest"], list):
                raise ValidationError("locations_of_interest must be a list")

    def _validate_geographic_params(self, params: Dict[str, Any]) -> None:
        """Validate Performance Max geographic script parameters."""
        if "target_locations" in params:
            if not isinstance(params["target_locations"], list):
                raise ValidationError("target_locations must be a list")

            for i, location in enumerate(params["target_locations"]):
                if not isinstance(location, dict):
                    raise ValidationError(f"target_locations[{i}] must be a dictionary")

                required_fields = ["name", "state", "criterion_id"]
                for field in required_fields:
                    if field not in location:
                        raise ValidationError(
                            f"target_locations[{i}] missing required field: {field}"
                        )

                # Validate criterion_id is numeric
                if not str(location["criterion_id"]).isdigit():
                    raise ValidationError(
                        f"target_locations[{i}].criterion_id must be numeric"
                    )

    def _validate_bidding_params(self, params: Dict[str, Any]) -> None:
        """Validate Performance Max bidding script parameters."""
        if "target_roas_threshold" in params:
            params["target_roas_threshold"] = self.validate_numeric_threshold(
                params["target_roas_threshold"],
                "target_roas_threshold",
                min_value=0.1,
                max_value=50.0,
            )

        if "target_cpa_threshold" in params:
            params["target_cpa_threshold"] = self.validate_numeric_threshold(
                params["target_cpa_threshold"],
                "target_cpa_threshold",
                min_value=0.01,
                max_value=1000.0,
            )

        if "min_conversions_for_analysis" in params:
            params["min_conversions_for_analysis"] = int(
                self.validate_numeric_threshold(
                    params["min_conversions_for_analysis"],
                    "min_conversions_for_analysis",
                    min_value=1,
                    max_value=1000,
                )
            )

    def _validate_cross_campaign_params(self, params: Dict[str, Any]) -> None:
        """Validate Performance Max cross-campaign script parameters."""
        if "overlap_threshold" in params:
            params["overlap_threshold"] = self.validate_numeric_threshold(
                params["overlap_threshold"],
                "overlap_threshold",
                min_value=0.0,
                max_value=1.0,
            )

        if "min_cost_for_analysis" in params:
            params["min_cost_for_analysis"] = self.validate_numeric_threshold(
                params["min_cost_for_analysis"],
                "min_cost_for_analysis",
                min_value=0.0,
                max_value=1000.0,
            )

    def _validate_assets_params(self, params: Dict[str, Any]) -> None:
        """Validate Performance Max assets script parameters."""
        if "min_impressions" in params:
            params["min_impressions"] = int(
                self.validate_numeric_threshold(
                    params["min_impressions"],
                    "min_impressions",
                    min_value=1,
                    max_value=1000000,
                )
            )

        if "zombie_threshold_days" in params:
            params["zombie_threshold_days"] = int(
                self.validate_numeric_threshold(
                    params["zombie_threshold_days"],
                    "zombie_threshold_days",
                    min_value=1,
                    max_value=365,
                )
            )

        if "asset_strength_threshold" in params:
            valid_strengths = {"POOR", "AVERAGE", "GOOD", "EXCELLENT"}
            if params["asset_strength_threshold"] not in valid_strengths:
                raise ValidationError(
                    f"asset_strength_threshold must be one of: {', '.join(valid_strengths)}"
                )


def is_retryable_error(error_code: str) -> bool:
    """Check if a Google Ads API error code is retryable.

    Args:
        error_code: The Google Ads API error code

    Returns:
        True if the error is retryable
    """
    return error_code in RETRYABLE_ERROR_CODES


def calculate_pagination_size(estimated_rows: int, max_memory_mb: int = 100) -> int:
    """Calculate optimal pagination size based on estimated data volume.

    Args:
        estimated_rows: Estimated number of rows to process
        max_memory_mb: Maximum memory to use in MB

    Returns:
        Optimal page size for processing
    """
    # Rough estimate: 1KB per row average
    bytes_per_row = 1024
    max_bytes = max_memory_mb * 1024 * 1024
    max_rows_per_page = max_bytes // bytes_per_row

    # Use conservative limits
    if estimated_rows <= 1000:
        return min(estimated_rows, 500)
    elif estimated_rows <= 10000:
        return min(max_rows_per_page, 2000)
    else:
        return min(max_rows_per_page, 5000)
