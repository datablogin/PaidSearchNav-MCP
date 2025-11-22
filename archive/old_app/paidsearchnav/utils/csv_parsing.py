"""CSV parsing utilities for analyzers.

This module provides common CSV parsing functionality to reduce code duplication
across different analyzers.
"""

import csv
import itertools
import logging
import re
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import pandas as pd

logger = logging.getLogger(__name__)

# Valid match types for Google Ads
VALID_MATCH_TYPES = {"EXACT", "PHRASE", "BROAD"}

# Valid keyword levels
VALID_LEVELS = {"CAMPAIGN", "AD_GROUP", "SHARED"}

# Field inference configuration
MAX_AD_GROUP_NAME_LENGTH = 30
MAX_CAMPAIGN_NAME_LENGTH = 20


def normalize_match_type(
    text: str, match_type: Optional[str] = None
) -> Tuple[str, str]:
    """Extract and normalize match type from keyword text.

    Args:
        text: The keyword text that may contain match type indicators
        match_type: Optional match type from CSV column

    Returns:
        Tuple of (cleaned_text, normalized_match_type)
    """
    if not text:
        return text, "BROAD"

    text = str(text).strip()

    # Check for match type indicators in text
    if text.startswith("[") and text.endswith("]"):
        # Exact match
        cleaned_text = text[1:-1]
        final_match_type = "EXACT"
    elif text.startswith("'\"") and text.endswith("\"'"):
        # Handle nested quotes from CSV: '"phrase keyword"'
        cleaned_text = text[2:-2]
        final_match_type = "PHRASE"
    elif text.startswith('"') and text.endswith('"'):
        # Phrase match
        cleaned_text = text[1:-1]
        final_match_type = "PHRASE"
    else:
        cleaned_text = text
        # Use provided match type or default to BROAD
        if match_type and not pd.isna(match_type):
            match_type_upper = str(match_type).upper()
            if "EXACT" in match_type_upper:
                final_match_type = "EXACT"
            elif "PHRASE" in match_type_upper:
                final_match_type = "PHRASE"
            elif "BROAD" in match_type_upper:
                final_match_type = "BROAD"
            else:
                final_match_type = "BROAD"
        else:
            final_match_type = "BROAD"

    # Validate match type
    if final_match_type not in VALID_MATCH_TYPES:
        logger.warning(
            f"Invalid match type '{final_match_type}' for keyword '{cleaned_text}', "
            f"defaulting to BROAD"
        )
        final_match_type = "BROAD"

    return cleaned_text, final_match_type


def normalize_level(level: Optional[str], ad_group: Optional[str] = None) -> str:
    """Normalize keyword level.

    Args:
        level: The level string from CSV
        ad_group: Optional ad group value to help determine level

    Returns:
        Normalized level (CAMPAIGN, AD_GROUP, or SHARED)
    """
    if not level or pd.isna(level):
        # Default based on presence of ad group
        return "AD_GROUP" if ad_group and not pd.isna(ad_group) else "CAMPAIGN"

    level_upper = str(level).upper()

    # Explicit mapping for common variations
    level_mapping = {
        "AD GROUP": "AD_GROUP",
        "ADGROUP": "AD_GROUP",
        "AD_GROUP": "AD_GROUP",
        "CAMPAIGN": "CAMPAIGN",
        "SHARED": "SHARED",
        "SHARED LIST": "SHARED",
        "LIST": "SHARED",
    }

    # Check against mapping
    for key, value in level_mapping.items():
        if key in level_upper:
            return value

    # Fallback logic
    if "AD" in level_upper and "GROUP" in level_upper:
        return "AD_GROUP"
    elif "CAMPAIGN" in level_upper:
        return "CAMPAIGN"
    elif "SHARED" in level_upper or "LIST" in level_upper:
        return "SHARED"

    # Default based on ad group presence
    return "AD_GROUP" if ad_group and not pd.isna(ad_group) else "CAMPAIGN"


def validate_keyword_text(text: str) -> bool:
    """Validate keyword text for potential issues.

    Args:
        text: The keyword text to validate

    Returns:
        True if valid, False otherwise
    """
    if not text or not text.strip():
        return False

    # Check for CSV injection patterns
    if text.strip().startswith(("=", "+", "-", "@", "\t", "\r")):
        logger.warning(f"Potential CSV injection detected in keyword: {text}")
        return False

    # Check for excessive length (Google Ads limit is 80 chars for keywords)
    if len(text) > 80:
        logger.warning(f"Keyword exceeds 80 character limit: {text[:50]}...")
        return False

    return True


def validate_google_ads_numeric_ranges(field_name: str, value: float | int) -> bool:
    """Validate numeric values against Google Ads limits.

    Args:
        field_name: Name of the field being validated
        value: Numeric value to validate

    Returns:
        True if value is within valid Google Ads ranges
    """
    if value < 0:
        logger.warning(f"Negative value not allowed for {field_name}: {value}")
        return False

    # Google Ads specific limits
    limits = {
        "cost": 1_000_000_000,  # $1B limit
        "cpc_bid": 1000,  # $1000 max CPC
        "budget": 1_000_000,  # $1M daily budget limit
        "quality_score": 10,  # Quality score 1-10
        "impressions": 2**31 - 1,  # Max int32
        "clicks": 2**31 - 1,  # Max int32
    }

    max_value = limits.get(field_name, 2**31 - 1)  # Default to max int32
    if value > max_value:
        logger.warning(
            f"Value exceeds Google Ads limit for {field_name}: {value} > {max_value}"
        )
        return False

    return True


def detect_csv_headers(file_path: str, max_lines: int = 20) -> int:
    """Detect the header row in a CSV file more robustly.

    Args:
        file_path: Path to the CSV file
        max_lines: Maximum lines to check for headers

    Returns:
        Number of rows to skip before actual data
    """
    skip_rows = 0
    header_patterns = [
        # Look for actual column headers
        r"negative\s*keyword|campaign|ad\s*group|match\s*type|level",
        # Common data row patterns (if we see these, header is probably the line before)
        r"^\[.*\]|^\".*\"|^[a-zA-Z0-9\s]+,(EXACT|PHRASE|BROAD)",
    ]

    metadata_patterns = [
        # Skip metadata rows
        r"^#|report|all\s*time|date\s*range|downloaded|generated|account",
    ]

    try:
        with open(file_path, "r", encoding="utf-8-sig") as f:  # Handle BOM
            for i, line in enumerate(f):
                if i >= max_lines:
                    break

                line_lower = line.lower()

                # Check if this is a metadata line to skip
                if any(re.search(pattern, line_lower) for pattern in metadata_patterns):
                    continue

                # Check if this looks like a header line
                if re.search(header_patterns[0], line_lower) and "," in line:
                    skip_rows = i
                    break

                # Check if this looks like a data line (header would be previous non-metadata line)
                if i > 0 and re.search(header_patterns[1], line, re.IGNORECASE):
                    skip_rows = max(0, i - 1)
                    break

    except Exception as e:
        logger.warning(f"Error detecting headers: {e}, using default")

    return skip_rows


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


def normalize_dataframe_numerics(
    df: pd.DataFrame, numeric_columns: list[str]
) -> pd.DataFrame:
    """Normalize numeric columns in DataFrame using clean_numeric_value.

    Args:
        df: DataFrame to process
        numeric_columns: List of column names that should be numeric

    Returns:
        DataFrame with cleaned numeric columns
    """
    df_cleaned = df.copy()

    for col in numeric_columns:
        if col in df_cleaned.columns:
            logger.debug(f"Cleaning numeric column: {col}")
            df_cleaned[col] = df_cleaned[col].apply(clean_numeric_value)

            # Fill None values with 0 for required numeric fields
            df_cleaned[col] = df_cleaned[col].fillna(0)

    return df_cleaned


def get_common_numeric_columns() -> dict[str, list[str]]:
    """Get commonly used numeric columns for different Google Ads report types.

    Returns:
        Dictionary mapping report type to list of numeric column names
    """
    return {
        "keywords": [
            "impressions",
            "clicks",
            "cost",
            "conversions",
            "conversion_value",
            "cpc_bid",
            "quality_score",
            "avg_position",
            "top_impression_percentage",
            "absolute_top_impression_percentage",
        ],
        "search_terms": [
            "impressions",
            "clicks",
            "cost",
            "conversions",
            "conversion_value",
        ],
        "campaigns": [
            "impressions",
            "clicks",
            "cost",
            "conversions",
            "conversion_value",
            "budget",
            "avg_cpc",
            "ctr",
            "conversion_rate",
        ],
        "ad_groups": [
            "impressions",
            "clicks",
            "cost",
            "conversions",
            "conversion_value",
            "cpc_bid",
            "avg_cpc",
            "ctr",
            "conversion_rate",
        ],
        "demographics": [
            "impressions",
            "clicks",
            "cost",
            "conversions",
            "conversion_value",
            "bid_adjustment",
        ],
        "device": [
            "impressions",
            "clicks",
            "cost",
            "conversions",
            "conversion_value",
            "bid_adjustment",
        ],
        "geo": [
            "impressions",
            "clicks",
            "cost",
            "conversions",
            "conversion_value",
            "bid_adjustment",
        ],
        "store_performance": [
            "local_impressions",
            "store_visits",
            "call_clicks",
            "driving_directions",
            "website_visits",
            "clicks",
            "conversions",
            "cost",
            "latitude",
            "longitude",
        ],
    }


def process_dataframe_efficiently(
    df: pd.DataFrame,
    process_func: Callable[[pd.Series], dict],
    progress_callback: Optional[Callable[[str], None]] = None,
    chunk_size: int = 1000,
) -> list[dict[str, Any]]:
    """Process DataFrame rows efficiently using vectorized operations where possible.

    Args:
        df: DataFrame to process
        process_func: Function to process each row
        progress_callback: Optional callback for progress updates
        chunk_size: Size of chunks for processing large DataFrames

    Returns:
        List of processed records
    """
    results: list[dict[str, Any]] = []
    total_rows = len(df)

    if total_rows == 0:
        return results

    # For small DataFrames, use apply
    if total_rows <= chunk_size:
        if progress_callback:
            progress_callback(f"Processing {total_rows} rows...")

        # Use apply instead of iterrows for better performance
        processed = df.apply(process_func, axis=1)
        results = [item for item in processed if item is not None]
    else:
        # For large DataFrames, process in chunks
        for i in range(0, total_rows, chunk_size):
            chunk = df.iloc[i : i + chunk_size]

            if progress_callback:
                progress_callback(
                    f"Processing rows {i + 1} to {min(i + chunk_size, total_rows)} "
                    f"of {total_rows}..."
                )

            chunk_results = chunk.apply(process_func, axis=1)
            results.extend([item for item in chunk_results if item is not None])

    if progress_callback:
        progress_callback(f"Completed processing {len(results)} valid records")

    return results


def detect_summary_rows(
    df: pd.DataFrame, search_term_column: str = "search_term"
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Detect and separate summary/total rows from regular data.

    Args:
        df: DataFrame to process
        search_term_column: Name of the column containing search terms

    Returns:
        Tuple of (regular_data, summary_data) DataFrames
    """
    if search_term_column not in df.columns:
        logger.warning(
            f"Column '{search_term_column}' not found, returning original data"
        )
        return df, pd.DataFrame()

    # Summary row patterns
    summary_patterns = [
        r"^Total:?\s*$",
        r"^Grand Total:?\s*$",
        r"^All time:?\s*$",
        r"^--+\s*$",
        r"^\s*$",  # Empty rows
        r"^Summary:?\s*$",
        r"^\(not set\)\s*$",
        r"^Other\s*$",
    ]

    # Create combined pattern
    combined_pattern = "|".join(summary_patterns)

    # Mark rows as summary
    is_summary = (
        df[search_term_column]
        .astype(str)
        .str.contains(combined_pattern, na=False, case=False, regex=True)
    )

    # Split data
    regular_data = df[~is_summary].copy()
    summary_data = df[is_summary].copy()

    if len(summary_data) > 0:
        logger.info(
            f"Detected {len(summary_data)} summary/total rows, processing {len(regular_data)} regular rows"
        )

    return regular_data, summary_data


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


def preprocess_search_terms_data(
    df: pd.DataFrame, strict_validation: bool = True
) -> pd.DataFrame:
    """Preprocess search terms data to handle missing fields and summary rows.

    Args:
        df: DataFrame containing search terms data
        strict_validation: Whether to apply strict validation (if False, more lenient)

    Returns:
        Preprocessed DataFrame with inferred fields
    """
    if df.empty:
        return df

    # Detect search term column name (flexible mapping)
    search_term_column = None
    possible_names = ["search_term", "Search term", "Query", "query", "Search Query"]
    for col_name in possible_names:
        if col_name in df.columns:
            search_term_column = col_name
            break

    if not search_term_column:
        logger.warning(
            "Could not find search term column, skipping summary row detection"
        )
        processed_df = df.copy()
    else:
        # Detect and remove summary rows
        processed_df, summary_df = detect_summary_rows(df, search_term_column)

        if len(summary_df) > 0:
            logger.info(f"Removed {len(summary_df)} summary rows from dataset")

    # Apply field inference to each row
    processed_rows = []
    skipped_count = 0

    for idx, row in processed_df.iterrows():
        try:
            row_dict = row.to_dict()

            # Skip rows with no search term data
            if search_term_column and (
                not row_dict.get(search_term_column)
                or pd.isna(row_dict.get(search_term_column))
            ):
                skipped_count += 1
                continue

            # Apply field inference
            inferred_row = infer_missing_fields(row_dict)
            processed_rows.append(inferred_row)

        except Exception as e:
            if strict_validation:
                raise ValueError(f"Error processing row {idx}: {e}") from e
            else:
                logger.warning(f"Skipping row {idx} due to error: {e}")
                skipped_count += 1
                continue

    if skipped_count > 0:
        logger.info(f"Skipped {skipped_count} rows during preprocessing")

    # Convert back to DataFrame
    if processed_rows:
        result_df = pd.DataFrame(processed_rows)
        logger.info(f"Preprocessed {len(result_df)} rows with field inference")
        return result_df
    else:
        logger.warning("No valid rows remaining after preprocessing")
        return pd.DataFrame()


class CSVValidationResult:
    """Result of CSV validation with detailed error information."""

    def __init__(
        self,
        is_valid: bool,
        errors: List[str],
        warnings: List[str],
        suggested_fixes: List[str],
    ):
        self.is_valid = is_valid
        self.errors = errors
        self.warnings = warnings
        self.suggested_fixes = suggested_fixes

    def get_error_summary(self) -> str:
        """Get a human-readable summary of validation issues."""
        if self.is_valid:
            return "CSV file is valid"

        summary_parts = []
        if self.errors:
            summary_parts.append(f"Errors: {'; '.join(self.errors)}")
        if self.warnings:
            summary_parts.append(f"Warnings: {'; '.join(self.warnings)}")
        if self.suggested_fixes:
            summary_parts.append(f"Suggested fixes: {'; '.join(self.suggested_fixes)}")

        return " | ".join(summary_parts)


def validate_csv_structure(
    file_path: Path, max_sample_lines: int = 100
) -> CSVValidationResult:
    """Validate CSV file structure before attempting pandas parsing.

    This function performs pre-parsing validation to detect common CSV issues
    that would cause pandas to fail, providing specific error messages and
    suggested fixes.

    Args:
        file_path: Path to the CSV file
        max_sample_lines: Maximum number of lines to sample for validation

    Returns:
        CSVValidationResult with validation status and detailed error information
    """
    errors = []
    warnings = []
    suggested_fixes = []

    try:
        # Check if file exists and is readable
        if not file_path.exists():
            errors.append(f"File does not exist: {file_path}")
            return CSVValidationResult(False, errors, warnings, suggested_fixes)

        if not file_path.is_file():
            errors.append(f"Path is not a file: {file_path}")
            return CSVValidationResult(False, errors, warnings, suggested_fixes)

        # Check file size
        file_size = file_path.stat().st_size
        if file_size == 0:
            errors.append("File is empty")
            suggested_fixes.append("Ensure the CSV file contains data")
            return CSVValidationResult(False, errors, warnings, suggested_fixes)

        # Read sample lines for validation using efficient slicing
        sample_lines = []
        try:
            with open(file_path, "r", encoding="utf-8-sig") as f:
                # Use itertools.islice for efficient line sampling
                sample_lines = [
                    line.rstrip("\n\r")
                    for line in itertools.islice(f, max_sample_lines)
                ]
        except UnicodeDecodeError:
            # Try alternative encodings
            encodings_to_try = ["utf-16", "cp1252", "iso-8859-1"]
            for encoding in encodings_to_try:
                try:
                    with open(file_path, "r", encoding=encoding) as f:
                        # Use itertools.islice for alternative encodings too
                        sample_lines = [
                            line.rstrip("\n\r")
                            for line in itertools.islice(f, max_sample_lines)
                        ]
                    warnings.append(f"File encoding detected as {encoding}")
                    break
                except UnicodeDecodeError:
                    continue
            else:
                errors.append("Could not determine file encoding")
                suggested_fixes.append("Convert file to UTF-8 encoding")
                return CSVValidationResult(False, errors, warnings, suggested_fixes)

        if not sample_lines:
            errors.append("Could not read any lines from file")
            return CSVValidationResult(False, errors, warnings, suggested_fixes)

        # Validate CSV structure using Python's csv module
        validation_issues = _validate_csv_lines(sample_lines)
        errors.extend(validation_issues["errors"])
        warnings.extend(validation_issues["warnings"])
        suggested_fixes.extend(validation_issues["suggested_fixes"])

        # Additional Google Ads specific validations
        google_ads_issues = _validate_google_ads_format(sample_lines)
        warnings.extend(google_ads_issues["warnings"])
        suggested_fixes.extend(google_ads_issues["suggested_fixes"])

        is_valid = len(errors) == 0
        return CSVValidationResult(is_valid, errors, warnings, suggested_fixes)

    except Exception as e:
        errors.append(f"Unexpected error during validation: {str(e)}")
        return CSVValidationResult(False, errors, warnings, suggested_fixes)


def _validate_csv_lines(lines: List[str]) -> Dict[str, List[str]]:
    """Validate CSV structure using Python's csv module."""
    errors = []
    warnings = []
    suggested_fixes = []

    if not lines:
        errors.append("No lines to validate")
        return {
            "errors": errors,
            "warnings": warnings,
            "suggested_fixes": suggested_fixes,
        }

    # Detect delimiter
    delimiter = ","
    sample_line = next((line for line in lines if line.strip()), "")
    if sample_line:
        # Try to detect delimiter
        sniffer = csv.Sniffer()
        try:
            dialect = sniffer.sniff(sample_line, delimiters=",;\t|")
            delimiter = dialect.delimiter
        except csv.Error:
            # Fallback to comma
            pass

    # Validate each line with csv reader
    field_counts = []
    field_count_lines = []  # Track which lines have which field counts
    problematic_lines = []

    for line_num, line in enumerate(lines):
        if not line.strip():
            continue  # Skip empty lines

        try:
            reader = csv.reader([line], delimiter=delimiter)
            fields = next(reader)
            field_count = len(fields)
            field_counts.append(field_count)
            field_count_lines.append((line_num + 1, field_count))
        except csv.Error as e:
            problematic_lines.append((line_num + 1, str(e)))

    # Check for consistent field counts
    if field_counts:
        most_common_count = max(set(field_counts), key=field_counts.count)
        inconsistent_lines = [
            (line_num, count)
            for line_num, count in field_count_lines
            if count != most_common_count
        ]

        if inconsistent_lines:
            # Show specific line numbers with inconsistent counts
            if len(inconsistent_lines) <= 5:
                line_details = [
                    f"line {line_num}: {count} fields"
                    for line_num, count in inconsistent_lines
                ]
                line_info = f"Lines with inconsistent counts: {', '.join(line_details)}"
            else:
                line_details = [
                    f"line {line_num}: {count} fields"
                    for line_num, count in inconsistent_lines[:5]
                ]
                line_info = f"Lines with inconsistent counts (showing first 5): {', '.join(line_details)}"

            warnings.append(
                f"Inconsistent field counts detected. Most common: {most_common_count} fields. {line_info}"
            )
            suggested_fixes.append(
                "Check for missing commas, extra delimiters, or unescaped quotes in data"
            )

    # Report problematic lines
    if problematic_lines:
        if len(problematic_lines) <= 5:
            error_details = [
                f"Line {line_num}: {error}" for line_num, error in problematic_lines
            ]
            errors.append(f"CSV parsing errors: {'; '.join(error_details)}")
        else:
            errors.append(
                f"CSV parsing errors on {len(problematic_lines)} lines (showing first 5)"
            )
            error_details = [
                f"Line {line_num}: {error}" for line_num, error in problematic_lines[:5]
            ]
            errors.extend(error_details)

        suggested_fixes.append(
            "Check for unescaped quotes, newlines within fields, or delimiter conflicts"
        )

    return {"errors": errors, "warnings": warnings, "suggested_fixes": suggested_fixes}


def _validate_google_ads_format(lines: List[str]) -> Dict[str, List[str]]:
    """Validate Google Ads specific CSV format requirements."""
    warnings = []
    suggested_fixes = []

    # Check for Google Ads export metadata headers
    metadata_patterns = [
        r"report|all\s*time|date\s*range|downloaded|generated|account",
        r"#.*report",
        r"^\s*$",  # Empty lines
    ]

    has_metadata = False
    header_line_found = False

    for line in lines:
        line_lower = line.lower().strip()

        # Check if this looks like metadata
        if any(re.search(pattern, line_lower) for pattern in metadata_patterns):
            has_metadata = True
            continue

        # Check if this looks like a header line
        google_ads_headers = [
            "keyword",
            "search term",
            "campaign",
            "ad group",
            "match type",
            "impressions",
            "clicks",
            "cost",
            "conversions",
            "location",
        ]

        if any(header in line_lower for header in google_ads_headers) and "," in line:
            header_line_found = True
            break

    if has_metadata and not header_line_found:
        warnings.append(
            "File appears to contain Google Ads metadata but no clear header row found"
        )
        suggested_fixes.append(
            "Ensure the CSV contains a proper header row with column names"
        )
    elif has_metadata:
        warnings.append(
            "File contains Google Ads export metadata - will be automatically cleaned"
        )

    return {"warnings": warnings, "suggested_fixes": suggested_fixes}


def parse_csv_with_fallbacks(file_path: Path, **pandas_kwargs) -> pd.DataFrame:
    """Parse CSV with multiple fallback strategies for malformed files.

    This function attempts to parse CSV files using progressively more lenient
    strategies when pandas fails with the default settings.

    Args:
        file_path: Path to the CSV file
        **pandas_kwargs: Additional arguments to pass to pd.read_csv

    Returns:
        Successfully parsed DataFrame

    Raises:
        ValueError: If all parsing strategies fail
    """
    # Strategy 1: Standard pandas parsing
    try:
        logger.debug("Attempting standard pandas parsing")
        return pd.read_csv(file_path, **pandas_kwargs)
    except Exception as e:
        logger.warning(f"Standard pandas parsing failed: {e}")

    # Strategy 2: Python engine (more lenient)
    try:
        logger.debug("Attempting parsing with Python engine")
        kwargs_python = pandas_kwargs.copy()
        kwargs_python["engine"] = "python"
        return pd.read_csv(file_path, **kwargs_python)
    except Exception as e:
        logger.warning(f"Python engine parsing failed: {e}")

    # Strategy 3: Skip bad lines
    try:
        logger.debug("Attempting parsing with error handling")
        kwargs_skip = pandas_kwargs.copy()
        kwargs_skip["engine"] = "python"
        kwargs_skip["on_bad_lines"] = "skip"
        kwargs_skip["warn_bad_lines"] = True
        df = pd.read_csv(file_path, **kwargs_skip)
        if not df.empty:
            logger.warning(
                f"Successfully parsed with bad lines skipped, got {len(df)} rows"
            )
            return df
    except Exception as e:
        logger.warning(f"Skip bad lines parsing failed: {e}")

    # Strategy 4: Line-by-line parsing for severely malformed files
    try:
        logger.debug("Attempting line-by-line parsing")
        return _parse_csv_line_by_line(file_path)
    except Exception as e:
        logger.error(f"Line-by-line parsing failed: {e}")

    # All strategies failed
    raise ValueError(
        "All CSV parsing strategies failed. The file may be severely malformed. "
        "Please check the file format and consider manual correction."
    )


def _parse_csv_line_by_line(file_path: Path) -> pd.DataFrame:
    """Parse CSV file line by line, handling malformed rows gracefully."""
    rows = []
    headers = None
    skipped_lines = 0

    with open(file_path, "r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)

        # Find headers
        for line_num, row in enumerate(reader):
            if row and any(cell.strip() for cell in row):  # Non-empty row
                if not headers:
                    headers = row
                    continue

                # Try to process data row
                try:
                    # Pad or truncate row to match header length
                    if len(row) < len(headers):
                        row.extend([""] * (len(headers) - len(row)))
                    elif len(row) > len(headers):
                        row = row[: len(headers)]

                    rows.append(row)
                except Exception as e:
                    logger.debug(f"Skipping malformed row {line_num + 1}: {e}")
                    skipped_lines += 1

    if not headers:
        raise ValueError("No valid header row found in CSV file")

    if not rows:
        raise ValueError("No valid data rows found in CSV file")

    if skipped_lines > 0:
        logger.warning(f"Skipped {skipped_lines} malformed lines during parsing")

    df = pd.DataFrame(rows, columns=headers)
    logger.info(
        f"Line-by-line parsing successful: {len(df)} rows, {len(df.columns)} columns"
    )

    return df


@contextmanager
def managed_temp_files(temp_files: List[Path]):
    """Context manager for automatic cleanup of temporary files.

    Args:
        temp_files: List of temporary file paths to manage

    Yields:
        The same list of temporary files

    Ensures:
        All temporary files are cleaned up on exit, even if an exception occurs
    """
    try:
        yield temp_files
    finally:
        # Clean up all temp files
        for temp_file in temp_files:
            if temp_file and temp_file.exists():
                try:
                    temp_file.unlink()
                    logger.debug(f"Cleaned up temp file: {temp_file}")
                except OSError as e:
                    logger.warning(f"Failed to clean up temp file {temp_file}: {e}")
