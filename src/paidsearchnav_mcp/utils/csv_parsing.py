"""CSV parsing utilities for analyzers.

This module provides common CSV parsing functionality to reduce code duplication
across different analyzers.
"""

import logging
import re
from typing import Any, Dict, Optional

import pandas as pd

logger = logging.getLogger(__name__)

# Field inference configuration
MAX_AD_GROUP_NAME_LENGTH = 30
MAX_CAMPAIGN_NAME_LENGTH = 20


def clean_numeric_value(value: Any) -> int | float | None:
    """Clean and parse numeric values from CSV data.

    Handles various Google Ads CSV numeric formats including:
    - Comma-separated numbers: "4,894" → 4894
    - Currency symbols: "$1,234.56" → 1234.56
    - Percentage values: "12.5%" → 12.5
    - Empty/null values: "" → None
    - Invalid formats: "N/A" → None

    Args:
        value: Raw value from CSV that should be numeric

    Returns:
        Cleaned numeric value (int/float) or None if invalid
    """
    # Handle None, NaN, or empty values early
    if value is None or pd.isna(value) or value == "":
        return None

    # If already a number, return as-is (fast path)
    if isinstance(value, (int, float)):
        return value

    # Handle string values with cleaning
    if isinstance(value, str):
        cleaned = value.strip()

        # Handle common invalid values
        if cleaned.lower() in ("n/a", "na", "--", "-", "null", "none"):
            return None

        # Remove common formatting characters
        cleaned = re.sub(r"[,$%\s]", "", cleaned)

        # Handle negative values with parentheses (accounting format)
        if cleaned.startswith("(") and cleaned.endswith(")"):
            cleaned = "-" + cleaned[1:-1]

        # Try to parse as number
        try:
            # Check if it's an integer (no decimal point)
            if "." not in cleaned:
                return int(float(cleaned))
            else:
                return float(cleaned)
        except (ValueError, OverflowError):
            logger.debug(f"Unable to parse numeric value: '{value}', returning None")
            return None

    # For other types, try converting to string first then parsing
    try:
        return clean_numeric_value(str(value))
    except Exception:
        logger.debug(
            f"Unable to convert value to numeric: '{value}' (type: {type(value)})"
        )
        return None


def infer_missing_fields(
    row_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Infer missing required fields from available data and context.

    Args:
        row_data: Dictionary containing row data with potentially missing fields
        context: Optional context information for inference

    Returns:
        Dictionary with inferred fields added
    """
    if context is None:
        context = {}

    row_copy = row_data.copy()

    # Infer ad_group_name from available data
    ad_group_val = row_copy.get("ad_group_name")

    def is_missing_value(val):
        """Helper to check if a value is missing, handling pandas NA properly."""
        try:
            # Try the normal checks first
            if val is None:
                return True
            if pd.isna(val):
                return True
            if val == "":
                return True
        except (TypeError, ValueError):
            # Handle pandas NA which can't be used in boolean context
            # Convert to string and check
            val_str = str(val).lower()
            if val_str in ["na", "nan", "<na>"]:
                return True
        return False

    if is_missing_value(ad_group_val):
        ad_group_name = None

        # Priority 1: Use campaign name as basis if available
        campaign_val = row_copy.get("campaign_name")
        if not is_missing_value(campaign_val):
            campaign_str = str(row_copy["campaign_name"]).strip()
            ad_group_name = f"{campaign_str} - Default Ad Group"

        # Priority 2: Use search term as basis
        elif row_copy.get("search_term"):
            search_term = str(row_copy["search_term"]).strip()
            # Truncate long search terms for ad group names
            search_term_truncated = (
                search_term[:MAX_AD_GROUP_NAME_LENGTH]
                if len(search_term) > MAX_AD_GROUP_NAME_LENGTH
                else search_term
            )
            ad_group_name = f"Inferred - {search_term_truncated}"

        # Priority 3: Generic fallback
        else:
            ad_group_name = "Unknown Ad Group"

        row_copy["ad_group_name"] = ad_group_name
        logger.debug(
            f"Inferred ad_group_name: '{ad_group_name}' for search term: '{row_copy.get('search_term', 'N/A')}'"
        )

    # Infer campaign_name if missing
    campaign_val = row_copy.get("campaign_name")
    if is_missing_value(campaign_val):
        campaign_name: str

        # Use search term as basis
        if row_copy.get("search_term"):
            search_term = str(row_copy["search_term"]).strip()
            search_term_truncated = (
                search_term[:MAX_CAMPAIGN_NAME_LENGTH]
                if len(search_term) > MAX_CAMPAIGN_NAME_LENGTH
                else search_term
            )
            campaign_name = f"Inferred Campaign - {search_term_truncated}"
        else:
            campaign_name = "Unknown Campaign"

        row_copy["campaign_name"] = campaign_name
        logger.debug(
            f"Inferred campaign_name: '{campaign_name}' for search term: '{row_copy.get('search_term', 'N/A')}'"
        )

    # Infer other commonly missing fields with smart defaults
    match_type_val = row_copy.get("match_type")
    if is_missing_value(match_type_val):
        row_copy["match_type"] = "BROAD"  # Most common default

    keyword_text_val = row_copy.get("keyword_text")
    if is_missing_value(keyword_text_val):
        # Use search term as fallback for triggering keyword
        if row_copy.get("search_term"):
            row_copy["keyword_text"] = row_copy["search_term"]

    return row_copy
