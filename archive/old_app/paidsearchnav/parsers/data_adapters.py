"""Data adapters for converting CSV data to model formats.

This module provides adapters that handle the conversion between
Google Ads CSV export formats and the expected data model formats
used by analyzers.
"""

import hashlib
import logging
from datetime import datetime
from typing import Any, Dict, Optional, Type

from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Constants for ID generation
ID_HASH_MODULO = 10000000  # Modulo value for hash-based ID generation
HASH_DIGEST_LENGTH = 8  # Number of hex digits to use from hash

# Move imports to top-level to avoid runtime import issues
try:
    from paidsearchnav.core.models.search_term import SearchTermMetrics
except ImportError:
    # Handle case where import fails
    logger.warning(
        "Could not import SearchTermMetrics - SearchTerm adapter may not work"
    )
    SearchTermMetrics = None


class DataAdapter:
    """Base class for data adapters."""

    def __init__(self, target_model: Type[BaseModel]):
        """Initialize adapter with target model class.

        Args:
            target_model: The Pydantic model class to convert data to
        """
        self.target_model = target_model

    def convert(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert raw CSV data to model-compatible format.

        Args:
            data: Raw data dictionary from CSV

        Returns:
            Dictionary compatible with target model
        """
        raise NotImplementedError("Subclasses must implement convert method")


class GeoPerformanceAdapter(DataAdapter):
    """Adapter for geographic performance data."""

    # Mapping from CSV location types to GeographicLevel enum values
    GEOGRAPHIC_LEVEL_MAPPING = {
        "COUNTRY": "COUNTRY",
        "STATE": "STATE",
        "PROVINCE": "STATE",
        "REGION": "STATE",
        "CITY": "CITY",
        "POSTAL CODE": "ZIP_CODE",
        "ZIP CODE": "ZIP_CODE",
        "ZIP": "ZIP_CODE",
        "DMA": "STATE",  # Map DMA to STATE as closest equivalent
        "DMA REGION": "STATE",
        "COUNTY": "STATE",
        "AIRPORT": "CITY",
        "CONGRESSIONAL DISTRICT": "STATE",
        "OTHER": "CITY",  # Default fallback
    }

    # Mapping from GeographicLevel to GeoTargetType for Google Ads models
    GEO_TARGET_TYPE_MAPPING = {
        "COUNTRY": "COUNTRY",
        "STATE": "STATE",
        "CITY": "CITY",
        "ZIP_CODE": "POSTAL_CODE",
        "RADIUS": "OTHER",
    }

    def convert(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert geo performance data to target model format.

        Handles conversion between different geographic data models:
        - GeoPerformanceData (core.models) expects cost_micros, revenue_micros, GeographicLevel
        - GeoPerformance (google.models) expects cost, conversion_value, GeoTargetType

        Args:
            data: Raw CSV data

        Returns:
            Converted data dictionary
        """
        converted = data.copy()

        # Check if target model expects micros format
        model_fields = getattr(self.target_model, "model_fields", {})
        if not model_fields:
            # Fallback for older Pydantic versions
            model_fields = getattr(self.target_model, "__fields__", {})
        expects_micros = "cost_micros" in model_fields
        expects_geographic_level = "geographic_level" in model_fields
        expects_location_type = "location_type" in model_fields

        # Handle geographic level/location type mapping
        if "geographic_level" in converted:
            # Ensure case-insensitive matching by normalizing to uppercase
            level = str(converted["geographic_level"]).strip().upper()

            if expects_geographic_level:
                # Convert to GeographicLevel enum with case-insensitive lookup
                mapped_level = self.GEOGRAPHIC_LEVEL_MAPPING.get(level, "CITY")
                converted["geographic_level"] = mapped_level
                logger.debug(
                    f"Mapped geographic level '{converted.get('geographic_level', 'N/A')}' -> '{mapped_level}'"
                )

            if expects_location_type:
                # Also add location_type for Google Ads models
                geo_level = self.GEOGRAPHIC_LEVEL_MAPPING.get(level)
                if geo_level:
                    location_type = self.GEO_TARGET_TYPE_MAPPING.get(geo_level, "OTHER")
                else:
                    # For truly invalid/unknown location types, default to OTHER
                    location_type = "OTHER"
                converted["location_type"] = location_type
                logger.debug(f"Mapped location type '{level}' -> '{location_type}'")

        elif expects_location_type and "location_type" not in converted:
            # Default location type if missing
            converted["location_type"] = "OTHER"
            logger.debug(
                "No geographic level provided, defaulting location_type to 'OTHER'"
            )

        # Handle cost conversion
        if expects_micros:
            # Convert dollar amounts to micros
            if "cost" in converted and "cost_micros" not in converted:
                try:
                    cost_dollars = self._parse_currency(converted.pop("cost"))
                    converted["cost_micros"] = int(cost_dollars * 1_000_000)
                except (ValueError, TypeError) as e:
                    logger.error(
                        f"Failed to convert cost '{converted.get('cost', 'N/A')}' to micros: {e}"
                    )
                    # Don't silently default to 0 - this could mask data quality issues
                    # Instead, raise a more descriptive error
                    raise ValueError(
                        f"Invalid cost value '{converted.get('cost', 'N/A')}' cannot be converted to micros. Original error: {e}"
                    ) from e

            # Convert revenue to revenue_micros
            revenue_field = None
            if "conversion_value" in converted:
                revenue_field = "conversion_value"
            elif "revenue" in converted:
                revenue_field = "revenue"

            if revenue_field and "revenue_micros" not in converted:
                try:
                    revenue_dollars = self._parse_currency(converted.pop(revenue_field))
                    converted["revenue_micros"] = (
                        int(revenue_dollars * 1_000_000) if revenue_dollars else None
                    )
                except (ValueError, TypeError) as e:
                    logger.warning(
                        f"Could not convert {revenue_field} '{converted.get(revenue_field, 'N/A')}' to revenue_micros: {e}"
                    )
                    # Revenue conversion failure is less critical than cost, so we can default to None
                    # but log the specific value that failed
                    converted["revenue_micros"] = None
        else:
            # Standard model expects dollar amounts - parse currency formats
            if "cost" in converted:
                try:
                    converted["cost"] = self._parse_currency(converted["cost"])
                except (ValueError, TypeError):
                    logger.warning(
                        f"Could not convert cost '{converted.get('cost', 'N/A')}' to float"
                    )
                    converted["cost"] = 0.0

            # Parse conversion_value currency format
            if "conversion_value" in converted:
                try:
                    converted["conversion_value"] = self._parse_currency(
                        converted["conversion_value"]
                    )
                except (ValueError, TypeError):
                    logger.warning(
                        f"Could not convert conversion_value '{converted.get('conversion_value', 'N/A')}' to float"
                    )
                    converted["conversion_value"] = 0.0

            if "revenue" in converted and "conversion_value" not in converted:
                converted["conversion_value"] = self._parse_currency(
                    converted.pop("revenue")
                )
            elif "revenue" in converted and "conversion_value" in converted:
                # Both present, prefer conversion_value
                logger.warning(
                    "Both 'revenue' and 'conversion_value' present, using 'conversion_value'"
                )
                converted.pop("revenue", None)

        # Handle missing required fields with defaults
        if expects_micros:
            if "cost_micros" not in converted:
                converted["cost_micros"] = 0
            if "revenue_micros" not in converted:
                converted["revenue_micros"] = None

            # Add default dates if missing (required by GeoPerformanceData)
            # Use deterministic defaults instead of datetime.now() for consistency
            if "start_date" not in converted:
                # Default to first day of current year for consistent behavior
                current_year = datetime.now().year
                converted["start_date"] = datetime(current_year, 1, 1)
                logger.info(
                    f"Missing start_date field, using default: {current_year}-01-01"
                )
            if "end_date" not in converted:
                # Default to last day of current year for consistent behavior
                current_year = datetime.now().year
                converted["end_date"] = datetime(current_year, 12, 31)
                logger.info(
                    f"Missing end_date field, using default: {current_year}-12-31"
                )

        # Ensure numeric fields are properly typed
        numeric_fields = ["impressions", "clicks", "conversions"]
        for field in numeric_fields:
            if field in converted:
                try:
                    # Remove commas from numeric values like "21,893"
                    value = str(converted[field]).replace(",", "").strip()
                    if value == "" or value.lower() in ["--", "n/a", "null"]:
                        converted[field] = 0 if field != "conversions" else 0.0
                    elif field == "conversions":
                        converted[field] = float(value)
                    else:
                        converted[field] = int(float(value))  # Handle decimal integers
                except (ValueError, TypeError):
                    logger.warning(f"Could not convert {field} to numeric value")
                    converted[field] = 0 if field != "conversions" else 0.0

        # Handle missing required IDs for location reports
        if "customer_id" not in converted or not converted.get("customer_id"):
            converted["customer_id"] = "unknown"
            logger.info("Missing customer_id field, using default: 'unknown'")

        if "campaign_id" not in converted or not converted.get("campaign_id"):
            # Try to generate campaign_id from campaign_name using deterministic hash
            campaign_name = converted.get("campaign_name", "unknown")
            hash_value = int(
                hashlib.md5(campaign_name.encode()).hexdigest()[:HASH_DIGEST_LENGTH], 16
            )
            converted["campaign_id"] = f"campaign_{hash_value % ID_HASH_MODULO}"
            logger.info(
                f"Missing campaign_id field, generated from campaign_name: '{converted['campaign_id']}'"
            )

        if "location_id" not in converted:
            # Generate location_id from location_name using deterministic hash
            location_name = converted.get("location_name", "unknown")
            hash_value = int(
                hashlib.md5(location_name.encode()).hexdigest()[:HASH_DIGEST_LENGTH], 16
            )
            converted["location_id"] = f"loc_{hash_value % ID_HASH_MODULO}"

        # Ensure string fields are properly typed
        string_fields = ["zip_code", "location_id", "customer_id", "campaign_id"]
        for field in string_fields:
            if field in converted and converted[field] is not None:
                converted[field] = str(converted[field])

        return converted

    def _parse_currency(self, value: Any) -> float:
        """Parse currency value from string.

        Args:
            value: Currency value (may include $ symbol, commas)

        Returns:
            Float value in dollars

        Raises:
            ValueError: If value cannot be parsed as currency
        """
        if value is None or value == "":
            return 0.0

        if isinstance(value, (int, float)):
            return float(value)

        # Handle string values
        str_value = str(value).strip()

        # Remove currency symbols and commas
        cleaned = str_value.replace("$", "").replace(",", "").strip()

        if cleaned == "" or cleaned.lower() in ["--", "n/a", "null"]:
            return 0.0

        try:
            return float(cleaned)
        except ValueError:
            raise ValueError(f"Cannot parse currency value: {value}")


class KeywordAdapter(DataAdapter):
    """Adapter for keyword data."""

    MATCH_TYPE_MAPPING = {
        "EXACT": "EXACT",
        "PHRASE": "PHRASE",
        "BROAD": "BROAD",
        "BROAD MATCH": "BROAD",
        "PHRASE MATCH": "PHRASE",
        "EXACT MATCH": "EXACT",
    }

    STATUS_MAPPING = {
        "ENABLED": "ENABLED",
        "PAUSED": "PAUSED",
        "REMOVED": "REMOVED",
        "ACTIVE": "ENABLED",
        "INACTIVE": "PAUSED",
    }

    def convert(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert keyword data to target model format."""
        converted = data.copy()

        # Normalize match type
        if "match_type" in converted and converted["match_type"]:
            match_type = str(converted["match_type"]).upper()
            converted["match_type"] = self.MATCH_TYPE_MAPPING.get(match_type, "BROAD")

        # Normalize status
        if "status" in converted and converted["status"]:
            status = str(converted["status"]).upper()
            converted["status"] = self.STATUS_MAPPING.get(status, "ENABLED")

        # Handle quality score
        if "quality_score" in converted and converted["quality_score"] is not None:
            try:
                converted["quality_score"] = int(float(converted["quality_score"]))
            except (ValueError, TypeError):
                converted["quality_score"] = None

        # Handle quality score components
        quality_fields = ["landing_page_experience", "expected_ctr", "ad_relevance"]
        for field in quality_fields:
            if field in converted and converted[field] is not None:
                value = str(converted[field]).upper().replace(" ", "_")
                valid_values = ["BELOW_AVERAGE", "AVERAGE", "ABOVE_AVERAGE", "UNKNOWN"]
                converted[field] = value if value in valid_values else "UNKNOWN"

        return converted


class CampaignAdapter(DataAdapter):
    """Adapter for campaign data."""

    # Mapping from CSV status values to enum values
    STATUS_MAPPING = {
        "ENABLED": "ENABLED",
        "PAUSED": "PAUSED",
        "REMOVED": "REMOVED",
        "Enabled": "ENABLED",
        "Paused": "PAUSED",
        "Removed": "REMOVED",
    }

    # Mapping from CSV campaign types to enum values
    TYPE_MAPPING = {
        "SEARCH": "SEARCH",
        "DISPLAY": "DISPLAY",
        "SHOPPING": "SHOPPING",
        "VIDEO": "VIDEO",
        "APP": "APP",
        "SMART": "SMART",
        "LOCAL": "LOCAL",
        "HOTEL": "HOTEL",
        "PERFORMANCE_MAX": "PERFORMANCE_MAX",
        "Search": "SEARCH",
        "Display": "DISPLAY",
        "Shopping": "SHOPPING",
        "Video": "VIDEO",
        "YouTube": "VIDEO",
        "App": "APP",
        "Smart": "SMART",
        "Local": "LOCAL",
        "Hotel": "HOTEL",
        "Performance Max": "PERFORMANCE_MAX",
        "Demand Gen": "UNKNOWN",  # New campaign type not in enum yet
    }

    # Mapping from CSV bidding strategy to enum values
    BIDDING_STRATEGY_MAPPING = {
        "MANUAL_CPC": "MANUAL_CPC",
        "MANUAL_CPV": "MANUAL_CPV",
        "MANUAL_CPM": "MANUAL_CPM",
        "TARGET_CPA": "TARGET_CPA",
        "TARGET_ROAS": "TARGET_ROAS",
        "TARGET_SPEND": "TARGET_SPEND",
        "MAXIMIZE_CONVERSIONS": "MAXIMIZE_CONVERSIONS",
        "MAXIMIZE_CONVERSION_VALUE": "MAXIMIZE_CONVERSION_VALUE",
        "TARGET_IMPRESSION_SHARE": "TARGET_IMPRESSION_SHARE",
        "MAXIMIZE_CLICKS": "MAXIMIZE_CLICKS",
        "Manual CPC": "MANUAL_CPC",
        "CPC (enhanced)": "MANUAL_CPC",
        "Enhanced CPC": "MANUAL_CPC",
        "Manual CPV": "MANUAL_CPV",
        "Manual CPM": "MANUAL_CPM",
        "Target CPA": "TARGET_CPA",
        "Target ROAS": "TARGET_ROAS",
        "Maximize Conversion Value (Target ROAS)": "TARGET_ROAS",
        "Target spend": "TARGET_SPEND",
        "Maximize conversions": "MAXIMIZE_CONVERSIONS",
        "Maximize Conversions": "MAXIMIZE_CONVERSIONS",
        "Maximize conversion value": "MAXIMIZE_CONVERSION_VALUE",
        "Maximize Conversion Value": "MAXIMIZE_CONVERSION_VALUE",
        "Target impression share": "TARGET_IMPRESSION_SHARE",
        "Maximize clicks": "MAXIMIZE_CLICKS",
        "Maximize Clicks": "MAXIMIZE_CLICKS",
    }

    def convert(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert campaign data to target model format."""
        converted = data.copy()

        # Handle missing required IDs
        if "customer_id" not in converted or not converted.get("customer_id"):
            converted["customer_id"] = "unknown"

        if "campaign_id" not in converted or not converted.get("campaign_id"):
            # Generate campaign_id from campaign_name using deterministic hash
            campaign_name = converted.get(
                "campaign_name", converted.get("name", "unknown")
            )
            hash_value = int(
                hashlib.md5(campaign_name.encode()).hexdigest()[:HASH_DIGEST_LENGTH], 16
            )
            converted["campaign_id"] = f"campaign_{hash_value % ID_HASH_MODULO}"

        # Handle name field mapping - campaign model expects 'name' field
        if "name" not in converted:
            if "campaign_name" in converted:
                converted["name"] = converted["campaign_name"]
            elif "campaign" in converted:
                converted["name"] = converted["campaign"]
            else:
                converted["name"] = "Unknown Campaign"

        # Handle missing required budget fields
        if "budget_amount" not in converted:
            converted["budget_amount"] = 0.0
        if "budget_currency" not in converted:
            converted["budget_currency"] = "USD"

        # Handle status enum mapping
        if "status" in converted:
            status = str(converted["status"]).strip()
            converted["status"] = self.STATUS_MAPPING.get(status, "UNKNOWN")
        elif "campaign_state" in converted:
            status = str(converted["campaign_state"]).strip()
            converted["status"] = self.STATUS_MAPPING.get(status, "UNKNOWN")

        # Handle campaign type enum mapping
        if "type" in converted:
            campaign_type = str(converted["type"]).strip()
            converted["type"] = self.TYPE_MAPPING.get(campaign_type, "UNKNOWN")

        # Handle bidding strategy enum mapping
        if "bidding_strategy" in converted:
            strategy = str(converted["bidding_strategy"]).strip()
            converted["bidding_strategy"] = self.BIDDING_STRATEGY_MAPPING.get(
                strategy, "UNKNOWN"
            )
        else:
            converted["bidding_strategy"] = "UNKNOWN"

        # Ensure required enum fields have values
        if "status" not in converted:
            converted["status"] = "UNKNOWN"
        if "type" not in converted:
            converted["type"] = "UNKNOWN"

        # Handle numeric fields with commas
        numeric_fields = ["impressions", "clicks", "conversions"]
        for field in numeric_fields:
            if field in converted:
                try:
                    # Remove commas from numeric values like "21,893"
                    value = str(converted[field]).replace(",", "").strip()
                    if value == "" or value.lower() in ["--", "n/a", "null"]:
                        converted[field] = 0 if field != "conversions" else 0.0
                    elif field == "conversions":
                        converted[field] = float(value)
                    else:
                        converted[field] = int(float(value))  # Handle decimal integers
                except (ValueError, TypeError):
                    converted[field] = 0 if field != "conversions" else 0.0

        # Handle currency fields
        currency_fields = ["cost", "conversion_value", "avg_cpc"]
        for field in currency_fields:
            if field in converted:
                try:
                    converted[field] = self._parse_currency(converted[field])
                except (ValueError, TypeError):
                    converted[field] = 0.0

        # Ensure string fields are properly typed
        string_fields = ["campaign_id", "customer_id", "campaign_name"]
        for field in string_fields:
            if field in converted and converted[field] is not None:
                converted[field] = str(converted[field])

        return converted

    def _parse_currency(self, value: Any) -> float:
        """Parse currency value from string."""
        if value is None or value == "":
            return 0.0

        if isinstance(value, (int, float)):
            return float(value)

        # Handle string values
        str_value = str(value).strip()

        # Remove currency symbols and commas
        cleaned = str_value.replace("$", "").replace(",", "").strip()

        if cleaned == "" or cleaned.lower() in ["--", "n/a", "null"]:
            return 0.0

        try:
            return float(cleaned)
        except ValueError:
            return 0.0


class SearchTermAdapter(DataAdapter):
    """Adapter for search term data."""

    def convert(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert search term data to target model format."""
        converted = data.copy()

        # Handle nested metrics structure
        metrics_fields = {
            "impressions",
            "clicks",
            "cost",
            "conversions",
            "conversion_value",
            "ctr",
            "cpc",
            "cpa",
            "conversion_rate",
            "roas",
        }

        # Check if we need to create metrics object
        model_fields = getattr(self.target_model, "model_fields", {})
        if not model_fields:
            # Fallback for older Pydantic versions
            model_fields = getattr(self.target_model, "__fields__", {})
        if "metrics" in model_fields:
            metrics_data = {}

            # Extract metrics fields
            for field in list(converted.keys()):
                if field in metrics_fields:
                    metrics_data[field] = converted.pop(field)
                elif field.startswith("metrics."):
                    # Handle already-prefixed fields
                    clean_field = field.replace("metrics.", "")
                    if clean_field in metrics_fields:
                        metrics_data[clean_field] = converted.pop(field)

            # Add metrics object if we have data
            if metrics_data:
                if SearchTermMetrics is None:
                    logger.error(
                        "SearchTermMetrics not available - cannot create metrics object"
                    )
                    raise ImportError("SearchTermMetrics model is not available")
                converted["metrics"] = SearchTermMetrics(**metrics_data)

        return converted


class SearchTermUIAdapter(DataAdapter):
    """Adapter for search term UI export data (flat structure, no nested metrics)."""

    def convert(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert search term UI export data to target model format."""
        converted = data.copy()

        # For UI exports, metrics are flat in the CSV, but model expects nested structure
        metrics_fields = {
            "impressions",
            "clicks",
            "cost",
            "conversions",
            "conversion_value",
            "ctr",
            "avg_cpc",  # UI exports use "Avg. CPC" vs API's "cpc"
            "cpa",
            "conversion_rate",
            "roas",
        }

        # Check if target model expects nested metrics
        model_fields = getattr(self.target_model, "model_fields", {})
        if not model_fields:
            # Fallback for older Pydantic versions
            model_fields = getattr(self.target_model, "__fields__", {})

        if "metrics" in model_fields:
            metrics_data = {}

            # Extract metrics fields from flat structure
            for field in list(converted.keys()):
                if field in metrics_fields:
                    value = converted.pop(field)
                    # Map avg_cpc to cpc for consistency
                    metric_field = "cpc" if field == "avg_cpc" else field
                    metrics_data[metric_field] = value

            # Add metrics object if we have data
            if metrics_data:
                if SearchTermMetrics is None:
                    logger.error(
                        "SearchTermMetrics not available - cannot create metrics object"
                    )
                    raise ImportError("SearchTermMetrics model is not available")
                converted["metrics"] = SearchTermMetrics(**metrics_data)

        return converted


def get_adapter(file_type: str, target_model: Type[BaseModel]) -> Optional[DataAdapter]:
    """Get appropriate data adapter for file type and target model.

    Args:
        file_type: Type of CSV file (e.g., 'geo_performance', 'keywords', 'search_terms', 'search_terms_ui')
        target_model: Target Pydantic model class

    Returns:
        DataAdapter instance or None if no adapter available

    Examples:
        >>> from paidsearchnav.core.models.geo_performance import GeoPerformanceData
        >>> adapter = get_adapter("geo_performance", GeoPerformanceData)
        >>> if adapter:
        ...     converted_data = adapter.convert(csv_row_data)

        >>> from paidsearchnav.platforms.google.models import GeoPerformance
        >>> adapter = get_adapter("geo_performance", GeoPerformance)
        >>> # Same CSV data, different model format (dollars vs micros)
    """
    adapter_mapping = {
        "geo_performance": GeoPerformanceAdapter,
        "keywords": KeywordAdapter,
        "keywords_ui": KeywordAdapter,  # UI keywords use same adapter
        "search_terms": SearchTermAdapter,
        "search_terms_ui": SearchTermUIAdapter,  # UI search terms need special handling
        "campaigns": CampaignAdapter,
    }

    adapter_class = adapter_mapping.get(file_type)
    if adapter_class:
        return adapter_class(target_model)

    return None
