"""CSV format validation utilities for Google Ads exports.

This module provides comprehensive CSV format validation and user guidance
to prevent parsing issues and provide clear feedback when CSV files don't
match expected formats.
"""

import csv
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of CSV format validation."""

    is_valid: bool
    issues: List[str]
    suggestions: List[str]
    detected_format: str
    estimated_rows: int
    detected_encoding: Optional[str] = None
    delimiter: Optional[str] = None
    has_headers: bool = True


@dataclass
class CSVPreview:
    """Preview of CSV file structure."""

    headers: List[str]
    sample_rows: List[Dict[str, str]]
    total_columns: int
    estimated_rows: int
    file_size_mb: float


class CSVFormatValidator:
    """Validate CSV files before processing."""

    # Common Google Ads report format signatures
    FORMAT_SIGNATURES = {
        "search_terms": ["Search term", "Keyword", "Impressions", "Clicks"],
        "search_terms_ui": ["Search term", "Added/Excluded", "Campaign", "Ad group"],
        "keywords": ["Keyword", "Match type", "Ad group", "Campaign"],
        "keywords_ui": ["Keyword", "State", "Max. CPC", "Quality Score"],
        "campaigns": ["Campaign", "Impressions", "Clicks", "Cost"],
        "per_store": ["Store locations", "Store visits", "Call clicks"],
        "negative_keywords": ["Negative keyword", "Level", "Campaign"],
        "negative_keywords_ui": ["Negative keyword", "Campaign", "Ad group", "Level"],
        "demographics": ["Age range", "Gender", "Household income"],
        "device": ["Device", "Impressions", "Clicks"],
        "geo": ["Location", "Impressions", "Clicks"],
        "geo_performance": ["Location", "Impressions", "Clicks", "Cost"],
        "ad_groups": ["Ad group", "Campaign", "Impressions", "Clicks"],
        "ads": ["Ad", "Ad group", "Campaign", "Status"],
    }

    # Common metadata patterns to skip
    METADATA_PATTERNS = [
        r"^#",
        r"report\s*name",
        r"all\s*time",
        r"date\s*range",
        r"downloaded",
        r"generated",
        r"account\s*name",
        r"currency\s*code",
        r"time\s*zone",
        r"report\s*type",
    ]

    # Common delimiters in order of likelihood
    COMMON_DELIMITERS = [",", ";", "\t", "|"]

    # Encoding candidates for Google Ads exports
    ENCODING_CANDIDATES = [
        "utf-8-sig",  # UTF-8 with BOM (common in Google exports)
        "utf-8",
        "utf-16le",  # UTF-16 Little Endian
        "utf-16",
        "cp1252",  # Windows-1252
        "iso-8859-1",  # Latin-1
        "ascii",
    ]

    def __init__(self, max_sample_size: int = 10000):
        """Initialize validator.

        Args:
            max_sample_size: Maximum bytes to read for format detection
        """
        self.max_sample_size = max_sample_size
        self._file_cache = {}  # Cache for file content to reduce multiple reads

    def _get_cached_content(self, file_path: Path, encoding: str) -> str:
        """Get cached file content or read and cache it.

        Args:
            file_path: Path to the file
            encoding: File encoding to use

        Returns:
            File content (up to max_sample_size)
        """
        cache_key = (str(file_path), encoding)
        if cache_key not in self._file_cache:
            try:
                with open(file_path, "r", encoding=encoding) as f:
                    content = f.read(self.max_sample_size)
                    self._file_cache[cache_key] = content
            except Exception as e:
                logger.warning(
                    f"Failed to read file {file_path} with encoding {encoding}: {e}"
                )
                return ""
        return self._file_cache[cache_key]

    def validate_format(self, file_path: Path) -> ValidationResult:
        """Comprehensive CSV format validation.

        Args:
            file_path: Path to the CSV file to validate

        Returns:
            ValidationResult with validation details and suggestions
        """
        issues = []
        suggestions = []

        if not file_path.exists():
            return ValidationResult(
                is_valid=False,
                issues=["File does not exist"],
                suggestions=["Check the file path and ensure the file exists"],
                detected_format="unknown",
                estimated_rows=0,
            )

        if not file_path.suffix.lower() == ".csv":
            issues.append(f"File extension is '{file_path.suffix}', expected '.csv'")
            suggestions.append("Rename file to have .csv extension")

        # Check file size
        file_size = file_path.stat().st_size
        if file_size == 0:
            return ValidationResult(
                is_valid=False,
                issues=["File is empty"],
                suggestions=["Ensure the CSV file contains data"],
                detected_format="unknown",
                estimated_rows=0,
            )

        if file_size > 100 * 1024 * 1024:  # 100MB
            suggestions.append(
                "Large file detected - consider splitting into smaller files for better performance"
            )

        # Detect encoding
        encoding_result = self.detect_encoding(file_path)
        detected_encoding = encoding_result["encoding"]

        if not detected_encoding:
            issues.append("Unable to detect file encoding")
            suggestions.append("Save file as UTF-8 encoded CSV")
            detected_encoding = "utf-8"  # Fallback
        elif detected_encoding != "utf-8" and detected_encoding != "utf-8-sig":
            suggestions.append(
                f"File encoding is {detected_encoding}, consider converting to UTF-8"
            )

        # Detect delimiter
        delimiter_result = self.detect_delimiter(file_path, detected_encoding)
        delimiter = delimiter_result["delimiter"]

        if not delimiter:
            issues.append("Unable to detect consistent delimiter")
            suggestions.append(
                "Ensure file uses consistent comma, semicolon, or tab delimiters"
            )
        elif delimiter != ",":
            suggestions.append(
                f"File uses '{delimiter}' delimiter, comma is more standard"
            )

        # Check for headers and estimate rows
        headers_result = self.detect_headers(file_path, detected_encoding, delimiter)
        has_headers = headers_result["has_headers"]
        estimated_rows = headers_result["estimated_rows"]

        if not has_headers:
            issues.append("No header row detected")
            suggestions.append("Ensure first row contains column headers")

        # Detect Google Ads format
        format_type = "unknown"
        if has_headers and delimiter:
            format_type = self.detect_google_ads_format(
                file_path, detected_encoding, delimiter
            )

        # Check required columns for detected format
        if format_type != "unknown" and has_headers:
            missing_cols = self.check_required_columns(
                file_path, format_type, detected_encoding, delimiter
            )
            if missing_cols:
                issues.append(
                    f"Missing required columns for {format_type}: {', '.join(missing_cols)}"
                )
                suggestions.append(
                    f"Ensure CSV includes all required columns for {format_type} reports"
                )

        # Check for common issues
        common_issues = self.check_common_issues(
            file_path, detected_encoding, delimiter
        )
        issues.extend(common_issues["issues"])
        suggestions.extend(common_issues["suggestions"])

        return ValidationResult(
            is_valid=len(issues) == 0,
            issues=issues,
            suggestions=suggestions,
            detected_format=format_type,
            estimated_rows=estimated_rows,
            detected_encoding=detected_encoding,
            delimiter=delimiter,
            has_headers=has_headers,
        )

    def detect_encoding(self, file_path: Path) -> Dict[str, Optional[str]]:
        """Detect file encoding.

        Args:
            file_path: Path to the file

        Returns:
            Dictionary with encoding and confidence
        """
        # Try charset-normalizer first if available
        try:
            import charset_normalizer

            with open(file_path, "rb") as f:
                raw_data = f.read(min(self.max_sample_size, file_path.stat().st_size))
                result = charset_normalizer.detect(raw_data)

            if result and result.get("confidence", 0) > 0.7:
                return {
                    "encoding": result["encoding"],
                    "confidence": result["confidence"],
                }
        except ImportError:
            pass

        # Fallback: try common encodings
        for encoding in self.ENCODING_CANDIDATES:
            try:
                with open(file_path, "r", encoding=encoding) as f:
                    f.read(min(1024, file_path.stat().st_size))
                return {"encoding": encoding, "confidence": 0.8}
            except (UnicodeDecodeError, UnicodeError):
                continue

        return {"encoding": None, "confidence": 0.0}

    def detect_delimiter(
        self, file_path: Path, encoding: str
    ) -> Dict[str, Optional[str]]:
        """Detect CSV delimiter.

        Args:
            file_path: Path to the file
            encoding: File encoding to use

        Returns:
            Dictionary with delimiter and confidence
        """
        try:
            # Use cached content to avoid re-reading file
            sample = self._get_cached_content(file_path, encoding)
            if not sample:
                return {"delimiter": None, "confidence": 0.0}

            # Use Python's CSV sniffer
            try:
                sniffer = csv.Sniffer()
                delimiter = sniffer.sniff(sample, delimiters=",;\t|").delimiter
                return {"delimiter": delimiter, "confidence": 0.9}
            except csv.Error:
                pass

            # Fallback: count delimiter occurrences
            delimiter_counts = {}
            lines = sample.split("\n")[:10]  # Check first 10 lines

            for delimiter in self.COMMON_DELIMITERS:
                counts = [line.count(delimiter) for line in lines if line.strip()]
                if counts and len(set(counts)) == 1 and counts[0] > 0:
                    delimiter_counts[delimiter] = counts[0]

            if delimiter_counts:
                best_delimiter = max(delimiter_counts.items(), key=lambda x: x[1])[0]
                return {"delimiter": best_delimiter, "confidence": 0.8}

        except Exception as e:
            logger.warning(f"Error detecting delimiter: {e}")

        return {"delimiter": None, "confidence": 0.0}

    def detect_headers(
        self, file_path: Path, encoding: str, delimiter: Optional[str]
    ) -> Dict[str, Any]:
        """Detect if file has headers and estimate row count.

        Args:
            file_path: Path to the file
            encoding: File encoding to use
            delimiter: CSV delimiter

        Returns:
            Dictionary with has_headers and estimated_rows
        """
        has_headers = False
        estimated_rows = 0

        if not delimiter:
            return {"has_headers": False, "estimated_rows": 0}

        try:
            with open(file_path, "r", encoding=encoding) as f:
                reader = csv.reader(f, delimiter=delimiter)

                # Skip metadata rows
                rows = []
                for i, row in enumerate(reader):
                    if i > 20:  # Don't read too many rows for detection
                        break
                    if row and not self._is_metadata_row(" ".join(row)):
                        rows.append(row)

                if len(rows) >= 2:
                    # Check if first row looks like headers
                    first_row = rows[0]
                    second_row = rows[1] if len(rows) > 1 else None

                    # Headers typically contain text, data rows contain numbers
                    header_score = 0
                    for i, cell in enumerate(first_row):
                        if cell and isinstance(cell, str):
                            # Check if it looks like a header (contains common header words)
                            header_words = [
                                "campaign",
                                "keyword",
                                "impression",
                                "click",
                                "cost",
                                "conversion",
                                "search",
                                "term",
                                "match",
                                "type",
                                "id",
                                "name",
                                "group",
                                "ad",
                                "negative",
                            ]
                            if any(word in cell.lower() for word in header_words):
                                header_score += 2
                            elif (
                                not cell.replace(".", "")
                                .replace(",", "")
                                .replace("-", "")
                                .isdigit()
                            ):
                                header_score += 1

                            # Check if corresponding cell in second row is different type
                            if second_row and i < len(second_row) and second_row[i]:
                                if (
                                    cell.replace(".", "").replace(",", "").isdigit()
                                    and not second_row[i]
                                    .replace(".", "")
                                    .replace(",", "")
                                    .isdigit()
                                ):
                                    header_score -= 1
                                elif (
                                    not cell.replace(".", "").replace(",", "").isdigit()
                                    and second_row[i]
                                    .replace(".", "")
                                    .replace(",", "")
                                    .isdigit()
                                ):
                                    header_score += 1

                    has_headers = header_score > 0

                # Estimate total rows
                f.seek(0)
                line_count = sum(1 for line in f) - (1 if has_headers else 0)
                estimated_rows = max(0, line_count)

        except Exception as e:
            logger.warning(f"Error detecting headers: {e}")

        return {"has_headers": has_headers, "estimated_rows": estimated_rows}

    def detect_google_ads_format(
        self, file_path: Path, encoding: str, delimiter: str
    ) -> str:
        """Detect specific Google Ads report type.

        Args:
            file_path: Path to the file
            encoding: File encoding
            delimiter: CSV delimiter

        Returns:
            Detected format name or 'unknown'
        """
        try:
            headers = self.get_csv_headers(file_path, encoding, delimiter)
            if not headers:
                return "unknown"

            # Normalize headers for comparison
            headers_lower = [h.lower().strip() for h in headers]

            # Check each format signature
            best_match = "unknown"
            best_score = 0

            for format_name, required_columns in self.FORMAT_SIGNATURES.items():
                score = 0
                required_lower = [req.lower() for req in required_columns]

                for req in required_lower:
                    for header in headers_lower:
                        if req in header or header in req:
                            score += 1
                            break

                # Calculate match percentage
                match_percentage = score / len(required_columns)

                if match_percentage > 0.5 and score > best_score:
                    best_score = score
                    best_match = format_name

            return best_match

        except Exception as e:
            logger.warning(f"Error detecting Google Ads format: {e}")
            return "unknown"

    def check_required_columns(
        self, file_path: Path, format_type: str, encoding: str, delimiter: str
    ) -> List[str]:
        """Check for missing required columns.

        Args:
            file_path: Path to the file
            format_type: Detected format type
            encoding: File encoding
            delimiter: CSV delimiter

        Returns:
            List of missing required columns
        """
        if format_type not in self.FORMAT_SIGNATURES:
            return []

        try:
            headers = self.get_csv_headers(file_path, encoding, delimiter)
            if not headers:
                return list(self.FORMAT_SIGNATURES[format_type])

            headers_lower = [h.lower().strip() for h in headers]
            required_columns = self.FORMAT_SIGNATURES[format_type]
            missing = []

            for required in required_columns:
                required_lower = required.lower()
                found = any(
                    required_lower in header or header in required_lower
                    for header in headers_lower
                )
                if not found:
                    missing.append(required)

            return missing

        except Exception as e:
            logger.warning(f"Error checking required columns: {e}")
            return []

    def check_common_issues(
        self, file_path: Path, encoding: str, delimiter: Optional[str]
    ) -> Dict[str, List[str]]:
        """Check for common CSV issues.

        Args:
            file_path: Path to the file
            encoding: File encoding
            delimiter: CSV delimiter

        Returns:
            Dictionary with lists of issues and suggestions
        """
        issues = []
        suggestions = []

        if not delimiter:
            return {"issues": issues, "suggestions": suggestions}

        try:
            with open(file_path, "r", encoding=encoding) as f:
                # Check first few lines for common issues
                lines_checked = 0
                for line_num, line in enumerate(f, 1):
                    if lines_checked >= 100:  # Limit check to first 100 lines
                        break

                    if not line.strip():
                        continue

                    lines_checked += 1

                    # Check for unmatched quotes
                    quote_count = line.count('"')
                    if quote_count % 2 != 0:
                        issues.append(f"Line {line_num}: Unmatched quotes detected")
                        suggestions.append(
                            "Check for missing closing quotes in text fields"
                        )
                        break  # Don't spam with quote errors

                    # Check for potential encoding issues
                    try:
                        line.encode("utf-8")
                    except UnicodeEncodeError:
                        issues.append(
                            f"Line {line_num}: Character encoding issues detected"
                        )
                        suggestions.append("Save file with UTF-8 encoding")
                        break

                    # Check for formula injection patterns
                    if delimiter in line:
                        cells = line.split(delimiter)
                        for i, cell in enumerate(cells):
                            cell = cell.strip().strip('"')
                            if cell.startswith(("=", "+", "-", "@")):
                                issues.append(
                                    f"Line {line_num}, Column {i + 1}: Potential formula injection detected"
                                )
                                suggestions.append(
                                    "Remove formula characters (=, +, -, @) from beginning of cells"
                                )
                                break

                    # Check for very long lines (potential delimiter issues)
                    if len(line) > 10000:
                        issues.append(f"Line {line_num}: Extremely long line detected")
                        suggestions.append("Check if delimiter is correctly detected")

        except Exception as e:
            logger.warning(f"Error checking common issues: {e}")

        return {"issues": issues, "suggestions": suggestions}

    def get_csv_headers(
        self, file_path: Path, encoding: str, delimiter: str
    ) -> List[str]:
        """Get CSV headers, skipping metadata rows.

        Args:
            file_path: Path to the file
            encoding: File encoding
            delimiter: CSV delimiter

        Returns:
            List of header column names
        """
        try:
            with open(file_path, "r", encoding=encoding) as f:
                reader = csv.reader(f, delimiter=delimiter)

                for row in reader:
                    if row and not self._is_metadata_row(" ".join(row)):
                        return [cell.strip() for cell in row]

        except Exception as e:
            logger.warning(f"Error getting CSV headers: {e}")

        return []

    def get_csv_preview(
        self, file_path: Path, num_rows: int = 5
    ) -> Optional[CSVPreview]:
        """Get a preview of the CSV file structure.

        Args:
            file_path: Path to the file
            num_rows: Number of data rows to include in preview

        Returns:
            CSVPreview object or None if failed
        """
        validation_result = self.validate_format(file_path)

        if not validation_result.detected_encoding or not validation_result.delimiter:
            return None

        try:
            headers = self.get_csv_headers(
                file_path,
                validation_result.detected_encoding,
                validation_result.delimiter,
            )

            sample_rows = []
            with open(
                file_path, "r", encoding=validation_result.detected_encoding
            ) as f:
                reader = csv.DictReader(f, delimiter=validation_result.delimiter)

                # Skip to actual data (past headers and metadata)
                rows_collected = 0
                for row in reader:
                    if rows_collected >= num_rows:
                        break
                    if any(value and str(value).strip() for value in row.values()):
                        sample_rows.append(
                            {k: str(v) if v is not None else "" for k, v in row.items()}
                        )
                        rows_collected += 1

            file_size_mb = file_path.stat().st_size / (1024 * 1024)

            return CSVPreview(
                headers=headers,
                sample_rows=sample_rows,
                total_columns=len(headers),
                estimated_rows=validation_result.estimated_rows,
                file_size_mb=round(file_size_mb, 2),
            )

        except Exception as e:
            logger.warning(f"Error creating CSV preview: {e}")
            return None

    def _is_metadata_row(self, row_text: str) -> bool:
        """Check if a row is metadata that should be skipped.

        Args:
            row_text: Text content of the row

        Returns:
            True if row appears to be metadata
        """
        row_lower = row_text.lower().strip()

        return any(re.search(pattern, row_lower) for pattern in self.METADATA_PATTERNS)


def suggest_csv_fixes(
    file_path: Path, validation_result: ValidationResult
) -> Dict[str, Any]:
    """Suggest specific fixes for common CSV issues.

    Args:
        file_path: Path to the CSV file
        validation_result: Result from validation

    Returns:
        Dictionary with fix suggestions
    """
    fixes = {
        "encoding_fixes": [],
        "delimiter_fixes": [],
        "structure_fixes": [],
        "content_fixes": [],
        "alternative_formats": [],
    }

    # Encoding fixes
    if (
        not validation_result.detected_encoding
        or validation_result.detected_encoding not in ["utf-8", "utf-8-sig"]
    ):
        fixes["encoding_fixes"].append("Save file as UTF-8 encoded CSV")
        fixes["encoding_fixes"].append(
            "In Excel: File > Save As > CSV UTF-8 (Comma delimited)"
        )

    # Delimiter fixes
    if not validation_result.delimiter:
        fixes["delimiter_fixes"].append(
            "Ensure consistent comma delimiters throughout file"
        )
        fixes["delimiter_fixes"].append(
            "Check for mixed delimiters (commas, semicolons, tabs)"
        )
    elif validation_result.delimiter != ",":
        fixes["delimiter_fixes"].append(
            f"File uses '{validation_result.delimiter}' delimiter, consider using commas"
        )

    # Structure fixes
    if not validation_result.has_headers:
        fixes["structure_fixes"].append("Add header row with column names as first row")

    if validation_result.estimated_rows == 0:
        fixes["structure_fixes"].append("File appears to have no data rows")
        fixes["structure_fixes"].append(
            "Check that file contains actual Google Ads export data"
        )

    # Content fixes based on issues
    for issue in validation_result.issues:
        if "quote" in issue.lower():
            fixes["content_fixes"].append("Fix unmatched quotes in text fields")
        elif "formula" in issue.lower():
            fixes["content_fixes"].append(
                "Remove formula characters (=, +, -, @) from cell beginnings"
            )
        elif "encoding" in issue.lower():
            fixes["content_fixes"].append("Fix character encoding issues")

    # Alternative export formats
    fixes["alternative_formats"] = [
        "Google Ads Editor export (.csv)",
        "Google Ads Scripts output (.csv)",
        "Manual copy-paste from Google Ads UI into spreadsheet",
    ]

    return fixes
