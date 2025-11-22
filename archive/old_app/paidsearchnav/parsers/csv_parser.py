"""CSV parser implementation for Google Ads data."""

import csv
import logging
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar, Union

import pandas as pd
import psutil
from pydantic import BaseModel, ValidationError

from paidsearchnav.core.exceptions import (
    CSVEncodingError,
    CSVFormatError,
    CSVParsingError,
)
from paidsearchnav.core.models.keyword import Keyword
from paidsearchnav.core.models.search_term import SearchTerm
from paidsearchnav.parsers.base import BaseParser
from paidsearchnav.parsers.csv_preprocessor import GoogleAdsCSVPreprocessor
from paidsearchnav.parsers.data_adapters import get_adapter
from paidsearchnav.parsers.field_mappings import get_field_mapping, validate_csv_headers
from paidsearchnav.utils.csv_parsing import (
    clean_numeric_value,
    get_common_numeric_columns,
    infer_missing_fields,
    parse_csv_with_fallbacks,
    preprocess_search_terms_data,
    validate_csv_structure,
)
from paidsearchnav.utils.csv_validation import CSVFormatValidator

logger = logging.getLogger(__name__)


class CSVParser(BaseParser):
    """Parser for CSV files from Google Ads.

    Handles various CSV formats from Google Ads exports including
    keywords, search terms, and campaign data.
    """

    # File size constants
    MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024  # 100MB
    ENCODING_DETECTION_SAMPLE_SIZE = 10000  # 10KB for encoding detection
    CHUNK_SIZE = 10000  # Default chunk size for large file processing
    LARGE_FILE_THRESHOLD = 50 * 1024 * 1024  # 50MB threshold for chunked reading

    def __init__(
        self,
        file_type: str = "default",
        encoding: str = "utf-8",
        max_file_size: Optional[int] = None,
        preserve_unmapped: bool = True,
    ):
        """Initialize CSVParser with specified file type.

        Args:
            file_type: Type of CSV file (e.g., 'keywords', 'search_terms').
                      Defaults to 'default'.
            encoding: File encoding to use. Defaults to 'utf-8'.
            max_file_size: Maximum file size in bytes. Defaults to 100MB.
            preserve_unmapped: Whether to preserve unmapped fields. Defaults to True.
        """
        self.file_type = file_type
        self.field_mapping = get_field_mapping(
            file_type
        )  # Will be updated after header detection
        self.encoding = encoding
        self.max_file_size = max_file_size or self.MAX_FILE_SIZE_BYTES
        self.preserve_unmapped = preserve_unmapped

    def parse(self, file_path: Path) -> List[Dict[str, Any]]:
        """Parse a CSV file and return structured data.

        Args:
            file_path: Path to the CSV file to parse.

        Returns:
            List of dictionaries containing the parsed data.

        Raises:
            FileNotFoundError: If the file doesn't exist.
            ValueError: If the CSV format is invalid.
        """
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        if not file_path.suffix.lower() == ".csv":
            raise ValueError(f"Expected .csv file, got: {file_path.suffix}")

        # Check file size for security
        file_size = os.path.getsize(file_path)
        if file_size > self.max_file_size:
            raise ValueError(
                f"File size ({file_size} bytes) exceeds maximum allowed size ({self.max_file_size} bytes)"
            )

        parsed_data = []

        try:
            with open(file_path, "r", encoding=self.encoding) as csvfile:
                reader = csv.DictReader(csvfile)

                for row in reader:
                    parsed_row = self._map_fields(row)
                    # Clean numeric fields first
                    parsed_row = self._clean_numeric_fields(parsed_row)
                    # Sanitize values to prevent CSV injection
                    parsed_row = self._sanitize_row(parsed_row)
                    parsed_data.append(parsed_row)

        except UnicodeDecodeError as e:
            raise ValueError(f"File encoding error: {e}. Try a different encoding.")
        except csv.Error as e:
            raise ValueError(f"CSV format error: {e}")
        except Exception as e:
            raise ValueError(f"Error parsing CSV file: {e}")

        return parsed_data

    def validate(self, data: List[Dict[str, Any]]) -> bool:
        """Validate the parsed CSV data.

        Args:
            data: List of dictionaries containing parsed data.

        Returns:
            True if data is valid, False otherwise.
        """
        if not data:
            return False

        # Check that all rows have the same keys
        expected_keys = set(data[0].keys())
        for row in data[1:]:
            if set(row.keys()) != expected_keys:
                return False

        return True

    def _map_fields(self, row: Dict[str, str]) -> Dict[str, Any]:
        """Map CSV fields to standardized field names.

        Args:
            row: Dictionary containing a single CSV row.

        Returns:
            Dictionary with mapped field names.
        """
        if not self.field_mapping:
            return row

        mapped_row = {}
        for csv_field, standard_field in self.field_mapping.items():
            if csv_field in row:
                mapped_row[standard_field] = row[csv_field]

        # Include any unmapped fields as-is if preserve_unmapped is True
        if self.preserve_unmapped:
            for key, value in row.items():
                if key not in self.field_mapping:
                    mapped_row[key] = value

        return mapped_row

    def _sanitize_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize CSV values to prevent formula injection.

        Args:
            row: Dictionary containing a single CSV row.

        Returns:
            Dictionary with sanitized values.
        """
        sanitized_row = {}
        formula_prefixes = ("=", "+", "-", "@", "\t", "\r")

        for key, value in row.items():
            if isinstance(value, str) and value.startswith(formula_prefixes):
                # Prefix with single quote to prevent formula execution
                logger.warning(
                    f"CSV injection protection: Field '{key}' value '{value}' starts with formula character, "
                    f"prefixing with quote to neutralize potential injection"
                )
                sanitized_row[key] = "'" + value
            else:
                sanitized_row[key] = value

        return sanitized_row

    def _clean_numeric_fields(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Clean numeric fields in a CSV row using the enhanced parsing utilities.

        Args:
            row: Dictionary containing a single CSV row.

        Returns:
            Dictionary with cleaned numeric values.
        """

        cleaned_row = row.copy()

        # Get numeric columns for this file type
        numeric_columns_map = get_common_numeric_columns()
        numeric_columns = numeric_columns_map.get(self.file_type, [])

        # If no specific mapping, try to identify numeric columns by common names
        if not numeric_columns:
            common_numeric_fields = [
                "impressions",
                "clicks",
                "cost",
                "conversions",
                "conversion_value",
                "cpc_bid",
                "budget",
                "avg_cpc",
                "ctr",
                "conversion_rate",
                "quality_score",
                "avg_position",
                "store_visits",
                "call_clicks",
                "driving_directions",
                "website_visits",
                "local_impressions",
            ]
            numeric_columns = [col for col in common_numeric_fields if col in row]

        # Clean all fields that look numeric, regardless of mapping
        for key, value in list(cleaned_row.items()):
            # Check if this field should be cleaned as numeric
            should_clean = False

            # First check if it's in our explicit numeric columns list
            if key in numeric_columns:
                should_clean = True
            else:
                # Also check if the key name suggests it's numeric
                key_lower = key.lower()
                numeric_indicators = [
                    "impression",
                    "click",
                    "cost",
                    "conversion",
                    "cpc",
                    "budget",
                    "ctr",
                    "rate",
                    "quality_score",
                    "position",
                    "visit",
                    "call",
                    "revenue",
                    "value",
                    "latitude",
                    "longitude",
                ]
                should_clean = any(
                    indicator in key_lower for indicator in numeric_indicators
                )

            if should_clean and value is not None:
                original_value = value
                cleaned_value = clean_numeric_value(original_value)
                if cleaned_value != original_value:
                    logger.debug(
                        f"Cleaned numeric field '{key}': '{original_value}' → {cleaned_value}"
                    )
                cleaned_row[key] = cleaned_value

        return cleaned_row


T = TypeVar("T", bound=BaseModel)


class GoogleAdsCSVParser(CSVParser):
    """Enhanced CSV parser specifically for Google Ads data with Pydantic model conversion.

    This parser provides advanced error handling:
    - Automatic encoding detection when UTF-8 fails (requires charset-normalizer)
    - Validation of required fields based on file type
    - Type conversion with error handling for numeric fields
    - CSV injection protection by prefixing formula-like values
    - Support for currency symbols ($) and percentages (%) in numeric fields
    - Lenient mode that skips invalid rows instead of failing
    """

    # Model mapping for different file types
    MODEL_MAPPING = {
        "keywords": Keyword,
        "search_terms": SearchTerm,
        "geo_performance": None,  # Will be imported lazily
        "campaigns": None,  # Will be imported lazily
    }

    # Constants for data cleaning
    NULL_VALUES = ["", "--", "n/a", "N/A", "null", "NULL"]

    # ID field patterns for more specific matching
    ID_FIELD_SUFFIXES = ["_id", "_ID", " ID", " Id"]

    # Numeric field names that should be converted
    INTEGER_FIELDS = ["impressions", "clicks", "Impressions", "Clicks", "Quality Score"]
    FLOAT_FIELDS = [
        "cost",
        "Cost",
        "conversions",
        "Conversions",
        "cpc_bid",
        "Max. CPC",
        "Conversion value",
        "Revenue",
    ]

    # Performance settings for large files
    CHUNK_SIZE = 10000  # Default chunk size for large file processing
    LARGE_FILE_THRESHOLD = 50 * 1024 * 1024  # 50MB threshold for chunked reading

    # Memory monitoring constants
    MEMORY_WARNING_THRESHOLD_RATIO = 0.1  # 10% of system memory
    MEMORY_CHECK_INTERVAL = 10  # Check memory every N chunks

    # Encoding detection constants
    ENCODING_DETECTION_CONFIDENCE_THRESHOLD = (
        0.7  # Minimum confidence for auto-detected encoding
    )

    # Common Google Ads export encodings in order of preference
    COMMON_GOOGLE_ADS_ENCODINGS = [
        "utf-16le",
        "utf-16",
        "utf-8-sig",
        "cp1252",
        "iso-8859-1",
    ]

    def __init__(
        self,
        file_type: str = "default",
        encoding: str = "utf-8",
        max_file_size: Optional[int] = None,
        preserve_unmapped: bool = False,
        strict_validation: bool = True,
        chunk_size: Optional[int] = None,
        use_chunked_reading: Optional[bool] = None,
        memory_warning_threshold: Optional[float] = None,
        validate_format: bool = True,
        encoding_confidence_threshold: Optional[float] = None,
    ):
        """Initialize GoogleAdsCSVParser.

        Args:
            file_type: Type of CSV file (e.g., 'keywords', 'search_terms', 'geo_performance').
            encoding: File encoding to use. Defaults to 'utf-8'. If encoding fails,
                automatic detection will be attempted if charset-normalizer is installed.
            max_file_size: Maximum file size in bytes. Defaults to 100MB.
            preserve_unmapped: Whether to preserve unmapped fields. Defaults to False.
            strict_validation: Whether to raise errors on validation failures. Defaults to True.
                When False, invalid rows are logged and skipped.
            chunk_size: Number of rows to process per chunk for large files. Defaults to 10000.
            use_chunked_reading: Whether to use chunked reading. If None, automatically
                enabled for files larger than LARGE_FILE_THRESHOLD (50MB).
            memory_warning_threshold: Memory usage threshold (MB) for warnings. If None,
                defaults to 10% of system memory.
            validate_format: Whether to perform format validation before parsing.
            encoding_confidence_threshold: Minimum confidence for auto-detected encoding.
                If None, defaults to 0.7.
        """
        super().__init__(file_type, encoding, max_file_size, preserve_unmapped)
        self.strict_validation = strict_validation
        self.validate_format = validate_format
        self.model_class = self._get_model_class(file_type)
        self.chunk_size = chunk_size or self.CHUNK_SIZE
        self.use_chunked_reading = use_chunked_reading
        self.preprocessor = GoogleAdsCSVPreprocessor()
        self.format_validator = CSVFormatValidator() if validate_format else None

        # Set memory warning threshold
        if memory_warning_threshold is None:
            # Default to configured percentage of system memory
            system_memory = psutil.virtual_memory()
            self.memory_warning_threshold = (
                system_memory.total
                * self.MEMORY_WARNING_THRESHOLD_RATIO
                / (1024 * 1024)
            )  # MB
        else:
            self.memory_warning_threshold = memory_warning_threshold

        # Set encoding confidence threshold
        self.encoding_confidence_threshold = (
            encoding_confidence_threshold
            if encoding_confidence_threshold is not None
            else self.ENCODING_DETECTION_CONFIDENCE_THRESHOLD
        )

    def _get_model_class(self, file_type: str) -> Optional[Type[BaseModel]]:
        """Get the model class for the file type, importing lazily if needed."""
        if file_type == "geo_performance":
            # Lazy import to avoid circular dependencies
            from paidsearchnav.platforms.google.models import GeoPerformance

            return GeoPerformance
        elif file_type == "campaigns":
            # Lazy import to avoid circular dependencies
            from paidsearchnav.core.models.campaign import Campaign

            return Campaign
        return self.MODEL_MAPPING.get(file_type)

    def parse(
        self,
        file_path: Path,
        progress_callback: Optional[Callable] = None,
        preprocess: bool = False,
    ) -> List[Union[Dict[str, Any], BaseModel]]:
        """Parse a CSV file and return structured data as Pydantic models or dicts.

        Args:
            file_path: Path to the CSV file to parse.
            progress_callback: Optional callback function that receives (processed_rows, total_rows).
                Only used when chunked reading is enabled.
            preprocess: Whether to preprocess the CSV file to handle Google Ads format variations.

        Returns:
            List of Pydantic models (if model class exists) or dictionaries.
            In lenient mode (strict_validation=False), invalid rows are skipped.

        Raises:
            FileNotFoundError: If the file doesn't exist.
            ValueError: If the CSV format is invalid or data validation fails.
                Specific error cases:
                - Empty CSV file
                - File contains no data rows or only empty rows
                - Missing required fields (in strict mode)
                - Invalid numeric values (in strict mode)
                - File encoding errors
                - File size exceeds limit
                - Malformed CSV structure
        """
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        if not file_path.suffix.lower() == ".csv":
            raise ValueError(f"Expected .csv file, got: {file_path.suffix}")

        # Validate filename for security (prevent directory traversal)
        try:
            # Resolve to absolute path and check it's within expected bounds
            resolved_path = file_path.resolve()
            # Just ensure the file exists at the resolved location
            if not resolved_path.exists():
                raise ValueError(
                    f"File does not exist at resolved path: {resolved_path}"
                )
        except (RuntimeError, OSError) as e:
            raise ValueError(f"Invalid file path: {e}")

        # Check file size for security
        file_size = os.path.getsize(file_path)
        if file_size > self.max_file_size:
            raise ValueError(
                f"File size ({file_size} bytes) exceeds maximum allowed size ({self.max_file_size} bytes)"
            )

        # Check if file is empty
        if file_size == 0:
            raise CSVFormatError(
                file_path=str(file_path),
                detected_format="empty",
                expected_formats=[self.file_type],
            )

        # Perform format validation if enabled
        if self.format_validator:
            logger.info("Performing CSV format validation")
            validation_result = self.format_validator.validate_format(file_path)

            if not validation_result.is_valid and self.strict_validation:
                # Create detailed error with suggestions
                raise CSVFormatError(
                    file_path=str(file_path),
                    detected_format=validation_result.detected_format,
                    expected_formats=[self.file_type],
                    missing_columns=[],  # Will be populated from validation_result.issues if needed
                )
            elif not validation_result.is_valid:
                logger.warning(
                    f"CSV validation found issues but continuing in lenient mode: {validation_result.issues}"
                )

            # Update encoding and other detected parameters
            if (
                validation_result.detected_encoding
                and validation_result.detected_encoding != self.encoding
            ):
                logger.info(
                    f"Using detected encoding: {validation_result.detected_encoding}"
                )
                self.encoding = validation_result.detected_encoding

        # Preprocess file if requested
        if preprocess:
            logger.info("Preprocessing CSV file to handle Google Ads format")
            processed_path = self.preprocessor.process_file(file_path)
            file_path = processed_path  # Use preprocessed file

            # Get flexible field mapping
            from paidsearchnav.parsers.field_mappings import FIELD_MAPPINGS

            if self.file_type in FIELD_MAPPINGS:
                self.field_mapping = self.preprocessor.get_flexible_field_mapping(
                    file_path, FIELD_MAPPINGS[self.file_type]
                )

        # Determine if we should use chunked reading
        should_use_chunked = self.use_chunked_reading
        if should_use_chunked is None:
            should_use_chunked = file_size > self.LARGE_FILE_THRESHOLD

        if should_use_chunked:
            logger.info(
                f"Using chunked reading for large file ({file_size / (1024 * 1024):.2f} MB)"
            )
            return self.parse_chunked(file_path, progress_callback)

        # Validate CSV structure before parsing

        logger.debug("Validating CSV structure before parsing")
        validation_result = validate_csv_structure(file_path)

        if not validation_result.is_valid:
            error_summary = validation_result.get_error_summary()
            if self.strict_validation:
                raise ValueError(f"CSV validation failed: {error_summary}")
            else:
                logger.warning(f"CSV validation issues detected: {error_summary}")
                logger.info(
                    "Attempting to parse with fallback strategies due to validation issues"
                )

        # Use enhanced CSV parsing with fallbacks
        try:
            # Read CSV with ID columns as strings to preserve formatting
            dtype_spec = {}
            # Pre-compile ID column patterns for better performance
            id_patterns = {
                "Keyword ID",
                "Campaign ID",
                "Ad group ID",
                "Customer ID",
                "Location ID",
                "keyword_id",
                "campaign_id",
                "ad_group_id",
                "customer_id",
                "location_id",
            }

            # First read just the header to check which columns exist
            with open(file_path, "r", encoding=self.encoding) as f:
                # Use csv.reader to properly handle quoted headers
                reader = csv.reader(f)
                header = next(reader)
                # Use set intersection for O(1) lookup instead of O(n*m) nested loop
                header_set = set(header)
                id_columns_found = header_set.intersection(id_patterns)
                for col in id_columns_found:
                    dtype_spec[col] = str
                # Also check for partial matches (e.g., columns containing "ID")
                for col in header:
                    if col not in id_columns_found and any(
                        pattern in col for pattern in ["ID", "Id", "_id"]
                    ):
                        dtype_spec[col] = str

            # Try standard parsing first, then fallbacks if needed
            try:
                df = pd.read_csv(file_path, encoding=self.encoding, dtype=dtype_spec)
            except (pd.errors.ParserError, pd.errors.EmptyDataError) as e:
                logger.warning(
                    f"Standard pandas parsing failed: {e}, attempting fallback strategies"
                )
                df = parse_csv_with_fallbacks(
                    file_path, encoding=self.encoding, dtype=dtype_spec
                )
        except (UnicodeDecodeError, UnicodeError) as e:
            # Try encoding detection for Unicode errors
            try:
                df = self._try_alternative_encodings_with_fallbacks(
                    file_path, dtype_spec, e
                )
            except ValueError as encoding_error:
                # Convert to our custom exception with helpful guidance
                raise CSVEncodingError(
                    file_path=str(file_path),
                    detected_encoding=None,
                    tried_encodings=self.COMMON_GOOGLE_ADS_ENCODINGS,
                ) from encoding_error
        except pd.errors.EmptyDataError:
            raise CSVFormatError(
                file_path=str(file_path),
                detected_format="empty",
                expected_formats=[self.file_type],
            )
        except pd.errors.ParserError as e:
            raise CSVParsingError(
                file_path=str(file_path),
                error=f"CSV format error: {e}",
                suggestions=[
                    "Check for consistent delimiters (commas, semicolons, tabs)",
                    "Ensure quotes are properly matched",
                    "Remove any special characters or control characters",
                    "Verify the file is a valid CSV format",
                ],
            )
        except Exception as e:
            # Check if this might be an encoding issue (e.g., NUL characters from wrong encoding)
            if "line contains NUL" in str(e) or "codec can't decode" in str(e):
                # This is likely an encoding issue, try alternative encodings
                logger.warning(f"Potential encoding issue detected: {e}")
                try:
                    df = self._try_alternative_encodings_with_fallbacks(
                        file_path, dtype_spec, e
                    )
                except ValueError as encoding_error:
                    raise CSVEncodingError(
                        file_path=str(file_path),
                        detected_encoding=None,
                        tried_encodings=self.COMMON_GOOGLE_ADS_ENCODINGS,
                    ) from encoding_error
            else:
                # Enhanced error message with suggestions
                error_msg = f"Error parsing CSV file: {e}"
                if (
                    hasattr(validation_result, "suggested_fixes")
                    and validation_result.suggested_fixes
                ):
                    error_msg += f" Suggested fixes: {'; '.join(validation_result.suggested_fixes)}"
                raise CSVParsingError(
                    file_path=str(file_path),
                    error=error_msg,
                    suggestions=[
                        "Check file format and encoding",
                        "Ensure file is not corrupted",
                        "Try re-exporting from Google Ads",
                        "Contact support if the issue persists",
                    ],
                )

        # Check if dataframe is empty
        if df.empty:
            raise CSVFormatError(
                file_path=str(file_path),
                detected_format="empty",
                expected_formats=[self.file_type],
            )

        # Remove completely empty rows (all NaN)
        initial_row_count = len(df)
        df = df.dropna(how="all")

        # Log if rows were dropped for debugging
        if len(df) != initial_row_count:
            logger.debug(
                f"Dropped {initial_row_count - len(df)} empty rows out of {initial_row_count} total rows"
            )

        # Check again after removing empty rows
        if df.empty:
            logger.error(
                f"CSV file contains only empty rows. Original row count: {initial_row_count}, columns: {list(df.columns) if hasattr(df, 'columns') else 'N/A'}"
            )
            raise ValueError("CSV file contains only empty rows")

        # Validate required headers with auto-detection
        headers = df.columns.tolist()
        missing_fields = validate_csv_headers(self.file_type, headers)
        if missing_fields and self.strict_validation and not preprocess:
            raise CSVFormatError(
                file_path=str(file_path),
                detected_format=self.file_type,
                expected_formats=[self.file_type],
                missing_columns=missing_fields,
            )

        # Update field mapping based on detected format
        self.field_mapping = get_field_mapping(self.file_type, headers)
        # Update the effective file type for adapter selection
        from paidsearchnav.parsers.field_mappings import detect_export_format

        self.effective_file_type = detect_export_format(headers, self.file_type)

        # Apply smart preprocessing for search terms to handle missing fields
        if self.file_type in ["search_terms", "search_terms_ui"]:
            logger.info("Applying smart field inference for search terms data")
            df = preprocess_search_terms_data(
                df, strict_validation=self.strict_validation
            )

            if df.empty:
                raise CSVFormatError(
                    file_path=str(file_path),
                    detected_format="search_terms",
                    expected_formats=["search_terms"],
                )

        # Convert to list of dictionaries
        data_dicts = df.to_dict("records")

        # Process each row
        parsed_data: List[Union[Dict[str, Any], BaseModel]] = []
        errors = []

        for idx, row in enumerate(data_dicts):
            try:
                # Clean null/empty values
                cleaned_row = self._clean_data(row)

                # Map fields
                mapped_row = self._map_fields(cleaned_row)

                # Clean numeric fields
                numeric_cleaned_row = self._clean_numeric_fields(mapped_row)

                # Sanitize values
                sanitized_row = self._sanitize_row(numeric_cleaned_row)

                # Convert to Pydantic model if available
                if self.model_class:
                    model_data = self._prepare_model_data(sanitized_row)
                    model_instance = self.model_class(**model_data)

                    # Special processing for SearchTerm
                    if isinstance(model_instance, SearchTerm):
                        model_instance.detect_local_intent()

                    parsed_data.append(model_instance)
                else:
                    parsed_data.append(sanitized_row)

            except ValidationError as e:
                error_msg = f"Row {idx + 2}: {e}"  # +2 for header and 0-indexing
                errors.append(error_msg)
                if self.strict_validation:
                    raise CSVParsingError(
                        file_path=str(file_path),
                        error=f"Data validation error at row {idx + 2}: {e}",
                        line_number=idx + 2,
                        suggestions=[
                            "Check data format and types in the specified row",
                            "Ensure all required fields have valid values",
                            "Remove or fix any invalid characters",
                            "Verify data matches expected Google Ads format",
                        ],
                    )
                else:
                    logger.warning(
                        f"Skipping row {idx + 2} due to validation error: {e}"
                    )
                    continue  # Skip this row in lenient mode
            except Exception as e:
                error_msg = f"Row {idx + 2}: {e}"
                errors.append(error_msg)
                if self.strict_validation:
                    raise CSVParsingError(
                        file_path=str(file_path),
                        error=f"Error processing row {idx + 2}: {e}",
                        line_number=idx + 2,
                        suggestions=[
                            "Check data format in the specified row",
                            "Ensure all cells contain valid data",
                            "Remove any special characters or formulas",
                            "Verify row structure matches CSV headers",
                        ],
                    )
                else:
                    logger.warning(f"Skipping row {idx + 2} due to error: {e}")
                    continue  # Skip this row in lenient mode

        if errors and not self.strict_validation:
            logger.warning(f"{len(errors)} rows had errors during parsing")

        return parsed_data

    def _try_alternative_encodings_with_fallbacks(
        self, file_path: Path, dtype_spec: Dict[str, Any], original_error: Exception
    ) -> pd.DataFrame:
        """Try alternative encodings with fallback parsing strategies when the default encoding fails.

        Args:
            file_path: Path to the CSV file
            dtype_spec: Column data type specifications
            original_error: The original error that triggered this retry

        Returns:
            Successfully parsed DataFrame

        Raises:
            ValueError: If no encoding works
        """

        # Try to detect encoding automatically or use common Google Ads encodings
        encoding_candidates = []

        # First try automatic detection if charset-normalizer is available
        try:
            import charset_normalizer

            with open(file_path, "rb") as f:
                raw_data = f.read(CSVParser.ENCODING_DETECTION_SAMPLE_SIZE)
                result = charset_normalizer.detect(raw_data)
                detected_encoding = result["encoding"]
                confidence = result.get("confidence", 0)

            logger.warning(
                f"Encoding error with {self.encoding}, detected encoding: {detected_encoding} (confidence: {confidence:.2f})"
            )

            if detected_encoding and confidence > self.encoding_confidence_threshold:
                encoding_candidates.append(detected_encoding)

        except ImportError:
            logger.warning(
                "charset-normalizer not available for automatic encoding detection"
            )

        # Add common Google Ads export encodings
        for enc in self.COMMON_GOOGLE_ADS_ENCODINGS:
            if enc not in encoding_candidates and enc != self.encoding:
                encoding_candidates.append(enc)

        # Try each encoding candidate with fallback strategies
        for encoding in encoding_candidates:
            try:
                logger.info(f"Trying encoding: {encoding}")
                # First try standard pandas parsing
                try:
                    df = pd.read_csv(file_path, encoding=encoding, dtype=dtype_spec)
                    logger.info(f"Successfully read file with encoding: {encoding}")
                    return df
                except (pd.errors.ParserError, pd.errors.EmptyDataError) as parse_error:
                    logger.warning(
                        f"Standard parsing failed with {encoding}: {parse_error}, trying fallback strategies"
                    )
                    # Try fallback parsing strategies with this encoding
                    df = parse_csv_with_fallbacks(
                        file_path, encoding=encoding, dtype=dtype_spec
                    )
                    logger.info(
                        f"Successfully read file with encoding {encoding} using fallback strategies"
                    )
                    return df
            except (UnicodeDecodeError, UnicodeError):
                continue
            except Exception as parse_error:
                logger.warning(
                    f"Encoding {encoding} failed with all parsing strategies: {parse_error}"
                )
                continue

        # If all encodings failed
        tried_encodings = [self.encoding] + encoding_candidates
        raise ValueError(
            f"File encoding and parsing error. Could not read file with any of these encodings: {', '.join(tried_encodings)}. "
            f"Original error: {original_error}. The file may be corrupted, have an unsupported encoding, or be severely malformed. "
            f"Please check the file format and consider manual correction."
        )

    def _try_alternative_encodings(
        self, file_path: Path, dtype_spec: Dict[str, Any], original_error: Exception
    ) -> pd.DataFrame:
        """Legacy method - redirects to enhanced version with fallbacks."""
        return self._try_alternative_encodings_with_fallbacks(
            file_path, dtype_spec, original_error
        )

    def _clean_data(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Clean null and empty values from row data.

        Args:
            row: Dictionary containing a single CSV row.

        Returns:
            Dictionary with cleaned values.

        Raises:
            ValueError: If numeric fields contain invalid data.
        """
        cleaned_row = {}
        for key, value in row.items():
            # Handle pandas NaN values
            if pd.isna(value):
                continue

            # Convert numeric strings
            if isinstance(value, str):
                value = value.strip()
                if value in self.NULL_VALUES:
                    continue

                # Try to convert to appropriate type
                if key in self.INTEGER_FIELDS and key != "Quality Score":
                    try:
                        # Remove currency symbols and commas for numeric fields
                        cleaned_value = value.replace("$", "").replace(",", "").strip()
                        value = int(float(cleaned_value))
                    except (ValueError, TypeError):
                        if self.strict_validation:
                            raise ValueError(
                                f"Invalid integer value '{value}' in field '{key}'. "
                                f"Expected a whole number (e.g., 1000, 2500)"
                            )
                        # Log warning and skip the field
                        logger.warning(
                            f"Invalid integer value '{value}' in field '{key}', skipping"
                        )
                        continue
                elif key in self.FLOAT_FIELDS or key == "Quality Score":
                    try:
                        # Remove currency symbols and commas for numeric fields
                        cleaned_value = value.replace("$", "").replace(",", "").strip()
                        # Handle percentage values
                        if cleaned_value.endswith("%"):
                            cleaned_value = cleaned_value.rstrip("%")
                            value = float(cleaned_value) / 100
                        else:
                            value = float(cleaned_value)
                    except (ValueError, TypeError):
                        if self.strict_validation:
                            raise ValueError(
                                f"Invalid numeric value '{value}' in field '{key}'. "
                                f"Expected a number (e.g., 123.45, $1,234.56, 5.5%)"
                            )
                        # Log warning and skip the field
                        logger.warning(
                            f"Invalid numeric value '{value}' in field '{key}', skipping"
                        )
                        continue
            elif isinstance(value, (int, float)):
                # Convert numeric IDs back to strings - use more specific matching
                if any(key.endswith(suffix) for suffix in self.ID_FIELD_SUFFIXES):
                    value = str(int(value))  # Convert to int first to remove decimals
                # Ensure integers for impression/click counts
                elif key in self.INTEGER_FIELDS and key != "Quality Score":
                    value = int(value)
                # Ensure quality score is int if present
                elif key == "Quality Score":
                    value = int(value) if not pd.isna(value) else None

            cleaned_row[key] = value

        return cleaned_row

    def _prepare_model_data(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare data for Pydantic model instantiation using data adapters.

        Args:
            row: Dictionary containing mapped and cleaned row data.

        Returns:
            Dictionary ready for model instantiation.
        """
        # Use effective file type (with UI detection) for adapter selection
        effective_type = getattr(self, "effective_file_type", self.file_type)

        # Try to get a specialized adapter for this file type and model
        adapter = (
            get_adapter(effective_type, self.model_class) if self.model_class else None
        )

        if adapter:
            # Use the adapter to convert the data
            try:
                return adapter.convert(row)
            except Exception as e:
                logger.warning(
                    f"Adapter conversion failed: {e}, falling back to basic conversion"
                )

        # Fallback to basic conversion for unknown file types or adapter failures
        return row.copy()

    def parse_to_dataframe(self, file_path: Path) -> pd.DataFrame:
        """Parse CSV file and return as pandas DataFrame with mapped columns.

        Args:
            file_path: Path to the CSV file to parse.

        Returns:
            DataFrame with mapped column names.

        Raises:
            FileNotFoundError: If the file doesn't exist.
            ValueError: If the CSV format is invalid.
        """
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Read CSV
        df = pd.read_csv(file_path, encoding=self.encoding)

        # Apply field mapping to column names
        if self.field_mapping:
            df.rename(columns=self.field_mapping, inplace=True)

        # Clean data
        df = df.replace(["--", "n/a", "N/A", "null", "NULL", ""], pd.NA)

        return df

    def parse_chunked(
        self,
        file_path: Path,
        progress_callback: Optional[Callable] = None,
        _retry_count: int = 0,
    ) -> List[Union[Dict[str, Any], BaseModel]]:
        """Parse a large CSV file using chunked reading for memory efficiency.

        Args:
            file_path: Path to the CSV file to parse.
            progress_callback: Optional callback function that receives (processed_rows, total_rows).
            _retry_count: Internal parameter for retry limit (do not use directly).

        Returns:
            List of Pydantic models (if model class exists) or dictionaries.

        Raises:
            FileNotFoundError: If the file doesn't exist.
            ValueError: If the CSV format is invalid or data validation fails.
        """
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        if not file_path.suffix.lower() == ".csv":
            raise ValueError(f"Expected .csv file, got: {file_path.suffix}")

        # Security checks
        try:
            resolved_path = file_path.resolve()
            if not resolved_path.exists():
                raise ValueError(
                    f"File does not exist at resolved path: {resolved_path}"
                )
        except (RuntimeError, OSError) as e:
            raise ValueError(f"Invalid file path: {e}")

        # Check file size
        file_size = os.path.getsize(file_path)
        if file_size > self.max_file_size:
            raise ValueError(
                f"File size ({file_size} bytes) exceeds maximum allowed size ({self.max_file_size} bytes)"
            )

        if file_size == 0:
            raise ValueError("CSV file is empty")

        # Prepare dtype specifications for ID columns
        dtype_spec = self._prepare_dtype_spec(file_path)

        # Get total row count for progress reporting (use estimation for large files)
        total_rows = None
        if progress_callback:
            # For very large files, use estimation instead of counting
            if file_size > 10 * 1024 * 1024:  # > 10MB
                total_rows = self._estimate_total_rows(file_path)
            else:
                # For smaller files, count accurately
                try:
                    with open(file_path, "r", encoding=self.encoding) as f:
                        total_rows = sum(1 for line in f) - 1  # Subtract header
                except Exception as e:
                    logger.warning(f"Failed to count rows: {e}")
                    total_rows = self._estimate_total_rows(file_path)

        parsed_data: List[Union[Dict[str, Any], BaseModel]] = []
        errors = []
        processed_rows = 0
        validated_headers = False

        # Validate CSV structure before parsing

        logger.debug("Validating CSV structure before chunked parsing")
        validation_result = validate_csv_structure(file_path)

        if not validation_result.is_valid:
            error_summary = validation_result.get_error_summary()
            if self.strict_validation:
                raise ValueError(f"CSV validation failed: {error_summary}")
            else:
                logger.warning(f"CSV validation issues detected: {error_summary}")
                logger.info("Proceeding with chunked parsing despite validation issues")

        # Log initial memory usage
        initial_memory = self.get_memory_usage()
        logger.info(f"Initial memory usage: {initial_memory['rss']:.2f} MB")

        try:
            # Use chunked reading with fallback strategies
            try:
                chunk_iterator = pd.read_csv(
                    file_path,
                    encoding=self.encoding,
                    dtype=dtype_spec,
                    chunksize=self.chunk_size,
                    na_values=self.NULL_VALUES,
                )
            except (pd.errors.ParserError, pd.errors.EmptyDataError) as e:
                logger.warning(
                    f"Standard chunked parsing failed: {e}, using fallback with error handling"
                )
                chunk_iterator = pd.read_csv(
                    file_path,
                    encoding=self.encoding,
                    dtype=dtype_spec,
                    chunksize=self.chunk_size,
                    na_values=self.NULL_VALUES,
                    engine="python",
                    on_bad_lines="skip",
                    warn_bad_lines=True,
                )

            for chunk_num, chunk in enumerate(chunk_iterator):
                # Validate headers on first chunk
                if not validated_headers:
                    headers = chunk.columns.tolist()
                    missing_fields = validate_csv_headers(self.file_type, headers)
                    if missing_fields and self.strict_validation:
                        raise ValueError(
                            f"Missing required fields: {', '.join(missing_fields)}. "
                            f"Please ensure your CSV file includes all required columns for '{self.file_type}' data."
                        )
                    # Update field mapping based on detected format
                    self.field_mapping = get_field_mapping(self.file_type, headers)
                    # Update the effective file type for adapter selection
                    from paidsearchnav.parsers.field_mappings import (
                        detect_export_format,
                    )

                    self.effective_file_type = detect_export_format(
                        headers, self.file_type
                    )
                    validated_headers = True

                # Remove completely empty rows
                chunk = chunk.dropna(how="all")

                if chunk.empty:
                    continue

                # Apply smart preprocessing for search terms in chunked mode
                if (
                    self.file_type in ["search_terms", "search_terms_ui"]
                    and chunk_num == 0
                ):
                    logger.info(
                        "Applying smart field inference for search terms data (chunked mode)"
                    )
                    # Note: In chunked mode, we only preprocess the first chunk to avoid duplication
                    # The field inference will be applied to each chunk individually

                # Apply field inference to the chunk
                if self.file_type in ["search_terms", "search_terms_ui"]:
                    # Use apply() method for better performance than iterrows()
                    def apply_inference(row):
                        return infer_missing_fields(row.to_dict())

                    # Apply inference to all rows at once using pandas vectorized operation
                    chunk_series = chunk.apply(apply_inference, axis=1)
                    chunk_dicts = chunk_series.tolist()
                else:
                    # Process each row in the chunk
                    chunk_dicts = chunk.to_dict("records")

                for idx, row in enumerate(chunk_dicts):
                    global_idx = processed_rows + idx
                    try:
                        # Clean null/empty values
                        cleaned_row = self._clean_data(row)

                        # Map fields
                        mapped_row = self._map_fields(cleaned_row)

                        # Clean numeric fields
                        numeric_cleaned_row = self._clean_numeric_fields(mapped_row)

                        # Sanitize values
                        sanitized_row = self._sanitize_row(numeric_cleaned_row)

                        # Convert to Pydantic model if available
                        if self.model_class:
                            model_data = self._prepare_model_data(sanitized_row)
                            model_instance = self.model_class(**model_data)

                            # Special processing for SearchTerm
                            if isinstance(model_instance, SearchTerm):
                                model_instance.detect_local_intent()

                            parsed_data.append(model_instance)
                        else:
                            parsed_data.append(sanitized_row)

                    except ValidationError as e:
                        error_msg = (
                            f"Row {global_idx + 2}: {e}"  # +2 for header and 0-indexing
                        )
                        errors.append(error_msg)
                        if self.strict_validation:
                            raise ValueError(f"Validation error at {error_msg}")
                        else:
                            logger.warning(
                                f"Skipping row {global_idx + 2} due to validation error: {e}"
                            )
                            continue
                    except Exception as e:
                        error_msg = f"Row {global_idx + 2}: {e}"
                        errors.append(error_msg)
                        if self.strict_validation:
                            raise ValueError(f"Error processing {error_msg}")
                        else:
                            logger.warning(
                                f"Skipping row {global_idx + 2} due to error: {e}"
                            )
                            continue

                processed_rows += len(chunk_dicts)

                # Report progress
                if progress_callback and total_rows:
                    progress_callback(processed_rows, total_rows)

                # Check memory usage periodically
                if chunk_num % 10 == 0:  # Check every 10 chunks
                    current_memory = self.get_memory_usage()
                    memory_increase = current_memory["rss"] - initial_memory["rss"]
                    if current_memory["rss"] > self.memory_warning_threshold:
                        logger.warning(
                            f"High memory usage: {current_memory['rss']:.2f} MB "
                            f"(+{memory_increase:.2f} MB from start)"
                        )

        except UnicodeDecodeError as e:
            if _retry_count >= 1:  # Limit retries
                raise ValueError(f"File encoding error after retry: {e}")

            # Try encoding detection
            detected_encoding = self._detect_encoding(file_path)
            if detected_encoding and detected_encoding != self.encoding:
                logger.warning(
                    f"Encoding error with {self.encoding}, trying detected encoding: {detected_encoding}"
                )
                # Retry with detected encoding
                original_encoding = self.encoding
                self.encoding = detected_encoding
                try:
                    return self.parse_chunked(
                        file_path, progress_callback, _retry_count + 1
                    )
                except Exception:
                    self.encoding = original_encoding  # Restore original
                    raise
            else:
                raise ValueError(f"File encoding error: {e}. Try a different encoding.")
        except pd.errors.EmptyDataError:
            raise ValueError("CSV file contains no data")
        except pd.errors.ParserError as e:
            raise ValueError(f"CSV format error: {e}")

        if not parsed_data:
            raise ValueError("CSV file contains no valid data rows")

        if errors and not self.strict_validation:
            logger.warning(f"{len(errors)} rows had errors during parsing")

        # Log final memory usage
        final_memory = self.get_memory_usage()
        memory_increase = final_memory["rss"] - initial_memory["rss"]
        logger.info(
            f"Final memory usage: {final_memory['rss']:.2f} MB "
            f"(+{memory_increase:.2f} MB increase)"
        )

        return parsed_data

    def _prepare_dtype_spec(self, file_path: Path) -> Dict[str, type]:
        """Prepare dtype specifications for pandas to optimize memory usage.

        Args:
            file_path: Path to the CSV file.

        Returns:
            Dictionary mapping column names to data types.
        """
        dtype_spec = {}

        # Common ID columns that should be kept as strings
        id_columns = [
            "Keyword ID",
            "Campaign ID",
            "Ad group ID",
            "Customer ID",
            "Location ID",
            "keyword_id",
            "campaign_id",
            "ad_group_id",
            "customer_id",
            "location_id",
        ]

        # Read just the header to check which columns exist
        with open(file_path, "r", encoding=self.encoding) as f:
            reader = csv.reader(f)
            try:
                header = next(reader)
            except StopIteration:
                return dtype_spec

            for col in header:
                # ID columns as strings
                if any(id_col in col for id_col in id_columns):
                    dtype_spec[col] = str
                # Integer columns
                elif col in self.INTEGER_FIELDS and col != "Quality Score":
                    dtype_spec[col] = "Int64"  # Nullable integer
                # Float columns
                elif col in self.FLOAT_FIELDS or col == "Quality Score":
                    dtype_spec[col] = "float64"
                # Match type and status as categorical for memory efficiency
                elif col.lower() in ["match_type", "status", "match type"]:
                    dtype_spec[col] = "category"

        return dtype_spec

    def _detect_encoding(self, file_path: Path) -> Optional[str]:
        """Detect file encoding using charset-normalizer.

        Args:
            file_path: Path to the file.

        Returns:
            Detected encoding or None if detection fails.
        """
        try:
            import charset_normalizer

            with open(file_path, "rb") as f:
                raw_data = f.read(self.ENCODING_DETECTION_SAMPLE_SIZE)
                result = charset_normalizer.detect(raw_data)
                return result.get("encoding")
        except ImportError:
            logger.warning("charset-normalizer not available for encoding detection")
            return None
        except (OSError, PermissionError) as e:
            logger.warning(f"Failed to read file for encoding detection: {e}")
            return None
        except Exception as e:
            logger.warning(f"Unexpected error during encoding detection: {e}")
            return None

    def _estimate_total_rows(
        self, file_path: Path, sample_size: int = 1000
    ) -> Optional[int]:
        """Estimate total rows based on file size and sample.

        Args:
            file_path: Path to the CSV file.
            sample_size: Number of lines to sample for estimation.

        Returns:
            Estimated number of rows or None if estimation fails.
        """
        try:
            with open(file_path, "r", encoding=self.encoding) as f:
                lines = []
                for i, line in enumerate(f):
                    if i >= sample_size:
                        break
                    lines.append(line)

            if not lines:
                return None

            avg_line_length = sum(len(line.encode("utf-8")) for line in lines) / len(
                lines
            )
            file_size = file_path.stat().st_size
            estimated_rows = int(file_size / avg_line_length)
            return max(0, estimated_rows - 1)  # Subtract header
        except Exception as e:
            logger.warning(f"Failed to estimate row count: {e}")
            return None

    @staticmethod
    def get_memory_usage() -> Dict[str, float]:
        """Get current memory usage statistics.

        Returns:
            Dictionary with memory usage in MB for:
            - rss: Resident Set Size (physical memory)
            - vms: Virtual Memory Size
            - percent: Percentage of system memory used
            - available: Available system memory
        """
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        system_memory = psutil.virtual_memory()

        return {
            "rss": memory_info.rss / (1024 * 1024),  # MB
            "vms": memory_info.vms / (1024 * 1024),  # MB
            "percent": process.memory_percent(),
            "available": system_memory.available / (1024 * 1024),  # MB
        }
