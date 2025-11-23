"""Custom exceptions for PaidSearchNav."""


class PaidSearchNavError(Exception):
    """Base exception for all PaidSearchNav errors."""

    pass


class APIError(PaidSearchNavError):
    """Raised when API calls fail."""

    pass


class AuthenticationError(APIError):
    """Raised when authentication fails."""

    pass


class RateLimitError(APIError):
    """Raised when API rate limits are exceeded."""

    pass


class AnalysisError(PaidSearchNavError):
    """Raised when analysis fails."""

    pass


class ValidationError(PaidSearchNavError):
    """Raised when data validation fails."""

    pass


class ConfigurationError(PaidSearchNavError):
    """Raised when configuration is invalid."""

    pass


class StorageError(PaidSearchNavError):
    """Raised when storage operations fail."""

    pass


class DataError(PaidSearchNavError):
    """Raised when data operations fail."""

    pass


class DatabaseConnectionError(StorageError):
    """Raised when database connection fails."""

    pass


class AuthorizationError(PaidSearchNavError):
    """Raised when user lacks required permissions."""

    pass


class ResourceNotFoundError(PaidSearchNavError):
    """Raised when requested resource is not found."""

    pass


class WorkflowError(PaidSearchNavError):
    """Raised when workflow operations fail."""

    pass


class RecommendationError(PaidSearchNavError):
    """Raised when recommendation operations fail."""

    pass


class CSVValidationError(PaidSearchNavError):
    """Raised when CSV validation fails."""

    def __init__(self, message: str, issues: list = None, suggestions: list = None):
        """Initialize CSV validation error.

        Args:
            message: Error message
            issues: List of validation issues found
            suggestions: List of suggested fixes
        """
        super().__init__(message)
        self.issues = issues or []
        self.suggestions = suggestions or []


class CSVParsingError(PaidSearchNavError):
    """Enhanced CSV parsing error with guidance."""

    def __init__(
        self,
        file_path: str,
        error: str,
        suggestions: list = None,
        line_number: int = None,
        column_name: str = None,
        detected_format: str = None,
    ):
        """Initialize CSV parsing error.

        Args:
            file_path: Path to the CSV file that failed to parse
            error: Original error message
            suggestions: List of suggested fixes
            line_number: Line number where error occurred (if known)
            column_name: Column name where error occurred (if known)
            detected_format: Detected CSV format type (if known)
        """
        self.file_path = file_path
        self.original_error = error
        self.suggestions = suggestions or []
        self.line_number = line_number
        self.column_name = column_name
        self.detected_format = detected_format

        # Build comprehensive error message
        message = f"CSV parsing failed for {file_path}:\n"

        if line_number:
            message += f"Error at line {line_number}"
            if column_name:
                message += f", column '{column_name}'"
            message += ":\n"

        message += f"Error: {error}\n"

        if detected_format and detected_format != "unknown":
            message += f"Detected format: {detected_format}\n"

        if self.suggestions:
            message += "\nSuggestions to fix this issue:\n"
            for i, suggestion in enumerate(self.suggestions, 1):
                message += f"  {i}. {suggestion}\n"

        super().__init__(message)


class CSVFormatError(CSVParsingError):
    """Raised when CSV format is invalid or unsupported."""

    def __init__(
        self,
        file_path: str,
        detected_format: str = "unknown",
        expected_formats: list = None,
        missing_columns: list = None,
    ):
        """Initialize CSV format error.

        Args:
            file_path: Path to the CSV file
            detected_format: Detected format type
            expected_formats: List of expected/supported formats
            missing_columns: List of missing required columns
        """
        if detected_format == "unknown":
            error = "Unable to determine CSV format"
            suggestions = [
                "Ensure the file is a valid Google Ads export",
                "Check that column headers match Google Ads report format",
                "Verify the file contains data rows (not just headers)",
            ]
        else:
            error = f"CSV format '{detected_format}' has validation issues"
            suggestions = []

        if missing_columns:
            error += f". Missing required columns: {', '.join(missing_columns)}"
            suggestions.extend(
                [
                    f"Add missing columns: {', '.join(missing_columns)}",
                    "Re-export data from Google Ads with all required columns",
                ]
            )

        if expected_formats:
            suggestions.append(f"Supported formats: {', '.join(expected_formats)}")

        super().__init__(
            file_path=file_path,
            error=error,
            suggestions=suggestions,
            detected_format=detected_format,
        )


class CSVEncodingError(CSVParsingError):
    """Raised when CSV file has encoding issues."""

    def __init__(
        self,
        file_path: str,
        detected_encoding: str = None,
        tried_encodings: list = None,
    ):
        """Initialize CSV encoding error.

        Args:
            file_path: Path to the CSV file
            detected_encoding: Detected encoding (if any)
            tried_encodings: List of encodings that were tried
        """
        if detected_encoding:
            error = f"File encoding '{detected_encoding}' is not supported or corrupted"
        else:
            error = "Unable to detect file encoding"

        suggestions = [
            "Save the file as UTF-8 encoded CSV",
            "In Excel: File > Save As > CSV UTF-8 (Comma delimited)",
            "In Google Sheets: File > Download > Comma-separated values (.csv)",
            "Check for corrupted or binary content in the file",
        ]

        if tried_encodings:
            suggestions.append(f"Tried encodings: {', '.join(tried_encodings)}")

        super().__init__(
            file_path=file_path,
            error=error,
            suggestions=suggestions,
            detected_format="encoding_error",
        )


class ConflictDetectionError(PaidSearchNavError):
    """Raised when Google Ads conflict detection operations fail."""

    pass


class DataProcessingError(PaidSearchNavError):
    """Raised when data processing operations fail."""

    pass
