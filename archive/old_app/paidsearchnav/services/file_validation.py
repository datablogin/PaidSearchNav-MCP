"""File validation utilities for audit operations."""

import csv
import hashlib
import io
import logging
import mimetypes
from pathlib import Path
from typing import List, Optional, Tuple, Union

from paidsearchnav.core.models.file_management import FileValidationResult

logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
MIN_FILE_SIZE = 10  # 10 bytes minimum

REQUIRED_KEYWORDS_COLUMNS = [
    "Keyword ID",
    "Campaign ID",
    "Ad group ID",
    "Status",
    "Keyword",
    "Match type",
]

REQUIRED_SEARCH_TERMS_COLUMNS = [
    "Search term",
    "Campaign ID",
    "Ad group ID",
    "Impressions",
    "Clicks",
    "Cost",
]

REQUIRED_CAMPAIGNS_COLUMNS = [
    "Campaign ID",
    "Campaign name",
    "Status",
    "Budget",
    "Campaign type",
]

REQUIRED_AD_GROUPS_COLUMNS = [
    "Ad group ID",
    "Campaign ID",
    "Ad group name",
    "Status",
]

ALLOWED_CONTENT_TYPES = {
    ".csv": ["text/csv", "application/csv", "text/plain"],
    ".md": ["text/markdown", "text/plain"],
    ".txt": ["text/plain"],
}


class FileValidator:
    """Validates files for audit operations."""

    def __init__(self, max_file_size: int = MAX_FILE_SIZE):
        """Initialize file validator.

        Args:
            max_file_size: Maximum allowed file size in bytes
        """
        self.max_file_size = max_file_size

    def validate_file_size(
        self, content: Union[bytes, str], filename: str
    ) -> Tuple[bool, Optional[str]]:
        """Validate file size.

        Args:
            content: File content
            filename: Name of the file

        Returns:
            Tuple of (is_valid, error_message)
        """
        if isinstance(content, str):
            size = len(content.encode("utf-8"))
        else:
            size = len(content)

        if size < MIN_FILE_SIZE:
            return False, f"File {filename} is too small ({size} bytes)"

        if size > self.max_file_size:
            return (
                False,
                f"File {filename} exceeds maximum size ({size} > {self.max_file_size} bytes)",
            )

        return True, None

    def validate_content_type(
        self, filename: str, content_type: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """Validate content type based on file extension.

        Args:
            filename: Name of the file
            content_type: Provided content type (optional)

        Returns:
            Tuple of (is_valid, error_message)
        """
        ext = Path(filename).suffix.lower()

        if ext not in ALLOWED_CONTENT_TYPES:
            return False, f"File extension {ext} is not allowed"

        if content_type:
            allowed_types = ALLOWED_CONTENT_TYPES[ext]
            if content_type not in allowed_types:
                return (
                    False,
                    f"Content type {content_type} not allowed for {ext} files",
                )

        return True, None

    def validate_csv_structure(
        self, content: Union[bytes, str], filename: str, required_columns: List[str]
    ) -> FileValidationResult:
        """Validate CSV file structure.

        Args:
            content: CSV file content
            filename: Name of the file
            required_columns: Required column names

        Returns:
            FileValidationResult with validation details
        """
        errors = []
        warnings = []
        file_info = {}

        try:
            if isinstance(content, bytes):
                content = content.decode("utf-8")

            csv_reader = csv.DictReader(io.StringIO(content))
            headers = csv_reader.fieldnames or []
            file_info["columns"] = headers
            file_info["column_count"] = len(headers)

            rows = list(csv_reader)
            file_info["row_count"] = len(rows)

            if not headers:
                errors.append("CSV file has no headers")
                return FileValidationResult(
                    is_valid=False,
                    errors=errors,
                    warnings=warnings,
                    file_info=file_info,
                )

            missing_columns = set(required_columns) - set(headers)
            if missing_columns:
                errors.append(f"Missing required columns: {', '.join(missing_columns)}")

            extra_columns = set(headers) - set(required_columns)
            if extra_columns:
                warnings.append(f"Extra columns found: {', '.join(extra_columns)}")

            if len(rows) == 0:
                warnings.append("CSV file has no data rows")

            for idx, row in enumerate(rows[:10]):
                empty_required_fields = [
                    col for col in required_columns if col in row and not row[col]
                ]
                if empty_required_fields:
                    warnings.append(
                        f"Row {idx + 1} has empty required fields: {', '.join(empty_required_fields)}"
                    )

        except UnicodeDecodeError:
            errors.append("File is not valid UTF-8 encoded")
        except csv.Error as e:
            errors.append(f"CSV parsing error: {str(e)}")
        except Exception as e:
            errors.append(f"Unexpected error validating CSV: {str(e)}")

        return FileValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            file_info=file_info,
        )

    def validate_keywords_csv(
        self, content: Union[bytes, str], filename: str = "keywords.csv"
    ) -> FileValidationResult:
        """Validate keywords CSV file.

        Args:
            content: CSV file content
            filename: Name of the file

        Returns:
            FileValidationResult
        """
        result = self.validate_csv_structure(
            content, filename, REQUIRED_KEYWORDS_COLUMNS
        )

        if result.is_valid and "row_count" in result.file_info:
            if result.file_info["row_count"] > 100000:
                result.warnings.append(
                    f"Large file warning: {result.file_info['row_count']} keywords"
                )

        return result

    def validate_search_terms_csv(
        self, content: Union[bytes, str], filename: str = "search_terms.csv"
    ) -> FileValidationResult:
        """Validate search terms CSV file.

        Args:
            content: CSV file content
            filename: Name of the file

        Returns:
            FileValidationResult
        """
        result = self.validate_csv_structure(
            content, filename, REQUIRED_SEARCH_TERMS_COLUMNS
        )

        if result.is_valid:
            try:
                if isinstance(content, bytes):
                    content = content.decode("utf-8")

                csv_reader = csv.DictReader(io.StringIO(content))
                numeric_errors = []

                for idx, row in enumerate(csv_reader):
                    if idx >= 100:
                        break

                    for field in ["Impressions", "Clicks", "Cost"]:
                        if field in row and row[field]:
                            try:
                                value = float(row[field].replace(",", ""))
                                if value < 0:
                                    numeric_errors.append(
                                        f"Row {idx + 1}: {field} cannot be negative"
                                    )
                            except ValueError:
                                numeric_errors.append(
                                    f"Row {idx + 1}: Invalid numeric value for {field}"
                                )

                if numeric_errors:
                    result.errors.extend(numeric_errors[:10])
                    if len(numeric_errors) > 10:
                        result.errors.append(
                            f"... and {len(numeric_errors) - 10} more numeric errors"
                        )
                    result.is_valid = False

            except Exception as e:
                result.errors.append(f"Error validating numeric fields: {str(e)}")
                result.is_valid = False

        return result

    def validate_campaigns_csv(
        self, content: Union[bytes, str], filename: str = "campaigns.csv"
    ) -> FileValidationResult:
        """Validate campaigns CSV file.

        Args:
            content: CSV file content
            filename: Name of the file

        Returns:
            FileValidationResult
        """
        return self.validate_csv_structure(
            content, filename, REQUIRED_CAMPAIGNS_COLUMNS
        )

    def validate_ad_groups_csv(
        self, content: Union[bytes, str], filename: str = "ad_groups.csv"
    ) -> FileValidationResult:
        """Validate ad groups CSV file.

        Args:
            content: CSV file content
            filename: Name of the file

        Returns:
            FileValidationResult
        """
        return self.validate_csv_structure(
            content, filename, REQUIRED_AD_GROUPS_COLUMNS
        )

    def calculate_checksum(
        self, content: Union[bytes, str], algorithm: str = "sha256"
    ) -> str:
        """Calculate checksum for file content.

        Args:
            content: File content
            algorithm: Hash algorithm to use (md5, sha256)

        Returns:
            Hex digest of the checksum
        """
        if isinstance(content, str):
            content = content.encode("utf-8")

        if algorithm == "md5":
            hasher = hashlib.md5()
        elif algorithm == "sha256":
            hasher = hashlib.sha256()
        else:
            raise ValueError(f"Unsupported hash algorithm: {algorithm}")

        hasher.update(content)
        return hasher.hexdigest()

    def validate_input_file(
        self, content: Union[bytes, str], filename: str, file_type: str
    ) -> FileValidationResult:
        """Validate an input file based on its type.

        Args:
            content: File content
            filename: Name of the file
            file_type: Type of the file (keywords, search_terms, campaigns, ad_groups)

        Returns:
            FileValidationResult
        """
        size_valid, size_error = self.validate_file_size(content, filename)
        if not size_valid:
            return FileValidationResult(
                is_valid=False, errors=[size_error], warnings=[], file_info={}
            )

        content_type_valid, content_type_error = self.validate_content_type(filename)
        if not content_type_valid:
            return FileValidationResult(
                is_valid=False, errors=[content_type_error], warnings=[], file_info={}
            )

        if file_type == "keywords":
            return self.validate_keywords_csv(content, filename)
        elif file_type == "search_terms":
            return self.validate_search_terms_csv(content, filename)
        elif file_type == "campaigns":
            return self.validate_campaigns_csv(content, filename)
        elif file_type == "ad_groups":
            return self.validate_ad_groups_csv(content, filename)
        else:
            return FileValidationResult(
                is_valid=False,
                errors=[f"Unknown file type: {file_type}"],
                warnings=[],
                file_info={},
            )

    def detect_content_type(self, filename: str) -> str:
        """Detect content type from filename.

        Args:
            filename: Name of the file

        Returns:
            MIME content type
        """
        content_type, _ = mimetypes.guess_type(filename)
        return content_type or "application/octet-stream"
