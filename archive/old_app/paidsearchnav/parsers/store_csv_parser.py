"""Shared CSV parsing utilities for store performance data."""

import logging
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

logger = logging.getLogger(__name__)

# Constants for header detection
REPORT_TITLE_INDICATORS = ["report", "Per store"]
DEFAULT_SKIP_ROWS = 2


class StoreCSVParser:
    """Shared utility class for parsing store performance CSV files."""

    @staticmethod
    def parse_csv(file_path: Path) -> List[Dict[str, Any]]:
        """Parse store performance CSV file with intelligent format detection.

        Args:
            file_path: Path to CSV file

        Returns:
            List of dictionaries with parsed store data

        Raises:
            ValueError: If CSV format is invalid
        """
        try:
            # Detect if file has header rows
            skip_rows = StoreCSVParser._detect_header_rows(file_path)

            df = pd.read_csv(
                file_path,
                skiprows=skip_rows,
                thousands=",",
                on_bad_lines="skip",
                engine="python",
            )

            # Apply column mappings
            df = StoreCSVParser._apply_column_mappings(df)

            # Clean numeric fields
            df = StoreCSVParser._clean_numeric_fields(df)

            # Validate required columns
            StoreCSVParser._validate_required_columns(df)

            # Convert to list of dictionaries
            store_data = df.to_dict("records")

            logger.info(f"Successfully parsed {len(store_data)} store records from CSV")

            return store_data

        except Exception as e:
            logger.error(f"Failed to parse store CSV: {e}")
            raise ValueError(f"Invalid CSV format: {e}")

    @staticmethod
    def _detect_header_rows(file_path: Path) -> int:
        """Detect if the CSV has header rows that should be skipped.

        Args:
            file_path: Path to CSV file

        Returns:
            Number of rows to skip
        """
        try:
            with open(file_path, "r") as f:
                first_lines = [f.readline().strip() for _ in range(3)]

            # Check if first line looks like a report title
            if first_lines and any(
                indicator in first_lines[0] or indicator in first_lines[0].lower()
                for indicator in REPORT_TITLE_INDICATORS
            ):
                return DEFAULT_SKIP_ROWS

            # Check if first line doesn't contain commas (likely a title)
            if first_lines and not any("," in line for line in first_lines[:1]):
                return DEFAULT_SKIP_ROWS

            return 0

        except Exception:
            # If we can't detect, assume no header rows
            return 0

    @staticmethod
    def _apply_column_mappings(df: pd.DataFrame) -> pd.DataFrame:
        """Apply standard column mappings for store performance data.

        Args:
            df: Raw DataFrame from CSV

        Returns:
            DataFrame with standardized column names
        """
        # Standard column mappings for store performance report
        column_mappings = {
            "Store locations": "store_name",
            "Store name": "store_name",
            "address_line_1": "address_line_1",
            "address_line_2": "address_line_2",
            "city": "city",
            "province": "state",
            "state": "state",
            "postal_code": "postal_code",
            "country_code": "country_code",
            "phone_number": "phone_number",
            "Local reach (impressions)": "local_impressions",
            "Store visits": "store_visits",
            "Call clicks": "call_clicks",
            "Driving directions": "driving_directions",
            "Website visits": "website_visits",
            "Cost": "cost",
            "Clicks": "clicks",
            "Conversions": "conversions",
            # Additional fields that may be present
            "latitude": "latitude",
            "longitude": "longitude",
            "market_area": "market_area",
            "competitive_index": "competitive_index",
            "attributed_revenue": "attributed_revenue",
            "visit_duration_avg": "visit_duration_avg",
            "repeat_visit_rate": "repeat_visit_rate",
            "conversion_rate": "conversion_rate",
        }

        # Rename columns based on mapping
        for old_col, new_col in column_mappings.items():
            if old_col in df.columns:
                df.rename(columns={old_col: new_col}, inplace=True)

        return df

    @staticmethod
    def _clean_numeric_fields(df: pd.DataFrame) -> pd.DataFrame:
        """Clean numeric fields in store performance DataFrame.

        Args:
            df: DataFrame to clean

        Returns:
            DataFrame with cleaned numeric columns
        """
        from paidsearchnav.utils.csv_parsing import (
            get_common_numeric_columns,
            normalize_dataframe_numerics,
        )

        # Get store performance numeric columns
        numeric_columns = get_common_numeric_columns().get("store_performance", [])

        # Clean the numeric columns
        return normalize_dataframe_numerics(df, numeric_columns)

    @staticmethod
    def _validate_required_columns(df: pd.DataFrame) -> None:
        """Validate that required columns are present.

        Args:
            df: DataFrame to validate

        Raises:
            ValueError: If required columns are missing
        """
        # Check for at least one location identifier column
        location_columns = ["Store locations", "Store name", "store_name"]
        if not any(col in df.columns for col in location_columns):
            raise ValueError(
                f"No location identifier column found. Expected one of: {location_columns}"
            )

    @staticmethod
    def validate_numeric_fields(data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and clean numeric fields in store data.

        Args:
            data: Dictionary containing store data

        Returns:
            Dictionary with validated numeric fields
        """
        numeric_fields = [
            "local_impressions",
            "store_visits",
            "call_clicks",
            "driving_directions",
            "website_visits",
            "clicks",
            "conversions",
        ]

        for field in numeric_fields:
            if field in data and data[field] is not None:
                try:
                    # Try to parse as number, set to 0 if invalid
                    if isinstance(data[field], str):
                        cleaned = data[field].replace(",", "").replace('"', "").strip()
                        data[field] = int(float(cleaned)) if cleaned else 0
                    elif isinstance(data[field], (int, float)):
                        data[field] = int(data[field])
                except (ValueError, AttributeError):
                    logger.warning(f"Invalid numeric value for {field}: {data[field]}")
                    data[field] = 0

        return data

    @staticmethod
    def safe_str_cast(value: Any, default: str = "") -> str:
        """Safely cast a value to string with default.

        Args:
            value: Value to cast
            default: Default value if casting fails

        Returns:
            String representation of value or default
        """
        if value is None:
            return default
        try:
            return str(value)
        except Exception:
            return default
