"""Pre-processor for Google Ads CSV files to handle various export formats."""

import csv
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class GoogleAdsCSVPreprocessor:
    """Pre-processes Google Ads CSV files to handle various export formats.

    Google Ads exports often include:
    - Multiple header rows (report name, date range, etc.)
    - Special characters and formatting in values
    - Inconsistent field names
    - Missing values represented as "--", " --", etc.
    """

    # Common header patterns to skip
    HEADER_PATTERNS = [
        "report",  # Common in report titles
        "all time",
        "last",
        "date range",  # Date range indicators
        "account",
        "customer id",  # Account info headers
    ]

    # Value replacements for cleaning
    VALUE_REPLACEMENTS = {
        " --": "",  # Empty instead of 0 to avoid data skewing
        "--": "",
        "N/A": "",
        "n/a": "",
    }

    # Special handling for comparison values
    COMPARISON_REPLACEMENTS = {
        "< 10%": None,  # Will be handled specially
        "> 90%": None,
    }

    def __init__(self):
        self.header_rows_to_skip = 0
        self.detected_headers = []

    def detect_header_rows(self, file_path: Path) -> int:
        """Detect how many header rows to skip before actual data.

        Returns:
            Number of rows to skip
        """
        with open(file_path, "r", encoding="utf-8-sig") as f:
            rows = []
            for i, line in enumerate(f):
                if i >= 10:  # Check first 10 rows max
                    break
                rows.append(line.strip().lower())

        # Find the row with column headers (contains multiple commas)
        for i, row in enumerate(rows):
            # Check if row contains header patterns
            if any(pattern in row for pattern in self.HEADER_PATTERNS):
                continue

            # Check if this looks like a data header row
            # Look for common column headers
            common_headers = [
                "keyword",
                "campaign",
                "ad group",
                "clicks",
                "impressions",
                "cost",
                "ctr",
            ]
            if row.count(",") >= 3 and any(header in row for header in common_headers):
                # Check if next row has similar structure (likely data)
                if i + 1 < len(rows):
                    next_row = rows[i + 1]
                    # If next row doesn't contain header patterns and has commas, it's likely data
                    if (
                        not any(pattern in next_row for pattern in self.HEADER_PATTERNS)
                        and next_row.count(",") >= row.count(",") - 1
                    ):
                        self.header_rows_to_skip = i
                        return i

        return 0

    def clean_value(self, value: str) -> str:
        """Clean individual cell values."""
        if not value:
            return value

        # Strip whitespace
        value = value.strip()

        # Apply replacements
        for old, new in self.VALUE_REPLACEMENTS.items():
            if value == old:
                return new

        # Remove quotes if they wrap the entire value
        if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
            value = value[1:-1]

        return value

    def process_file(
        self, input_path: Path, output_path: Optional[Path] = None
    ) -> Path:
        """Process a Google Ads CSV file and return cleaned version.

        Args:
            input_path: Path to input CSV file
            output_path: Optional path for output. If not provided, creates temp file.

        Returns:
            Path to processed file

        Raises:
            ValueError: If input path is invalid or file doesn't exist
        """
        # Validate input path
        if not isinstance(input_path, Path):
            input_path = Path(input_path)

        if not input_path.exists():
            raise ValueError(f"Input file does not exist: {input_path}")

        if not input_path.is_file():
            raise ValueError(f"Input path is not a file: {input_path}")

        # Resolve to absolute path to prevent directory traversal
        input_path = input_path.resolve()
        # Detect header rows
        skip_rows = self.detect_header_rows(input_path)
        logger.info(f"Detected {skip_rows} header rows to skip")

        # Read and process the file
        processed_rows = []

        with open(input_path, "r", encoding="utf-8-sig") as f:
            # Skip header rows
            for _ in range(skip_rows):
                next(f)

            reader = csv.DictReader(f)
            headers = reader.fieldnames

            if not headers:
                raise ValueError("No headers found in CSV file")

            # Clean headers
            cleaned_headers = [h.strip() for h in headers]
            processed_rows.append(cleaned_headers)

            # Process data rows
            row_count = 0
            for row in reader:
                cleaned_row = []
                for header in headers:
                    value = row.get(header, "")
                    cleaned_value = self.clean_value(value)
                    cleaned_row.append(cleaned_value)

                processed_rows.append(cleaned_row)
                row_count += 1

        logger.info(f"Processed {row_count} data rows")

        # Write output
        if output_path is None:
            output_path = input_path.parent / f"{input_path.stem}_preprocessed.csv"

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerows(processed_rows)

        return output_path

    def validate_required_fields(
        self, file_path: Path, required_fields: List[str]
    ) -> Tuple[bool, List[str]]:
        """Check if CSV has required fields.

        Returns:
            Tuple of (all_required_present, missing_fields)
        """
        with open(file_path, "r", encoding="utf-8-sig") as f:
            # Skip detected header rows
            for _ in range(self.header_rows_to_skip):
                next(f)

            reader = csv.DictReader(f)
            headers = (
                [h.strip() for h in reader.fieldnames] if reader.fieldnames else []
            )

        missing = [field for field in required_fields if field not in headers]
        return len(missing) == 0, missing

    def get_flexible_field_mapping(
        self, file_path: Path, known_mappings: Dict[str, str]
    ) -> Dict[str, str]:
        """Create field mapping that handles missing fields gracefully.

        Args:
            file_path: Path to CSV file
            known_mappings: Known field mappings from field_mappings.py

        Returns:
            Flexible mapping that includes only available fields
        """
        with open(file_path, "r", encoding="utf-8-sig") as f:
            # Skip detected header rows
            for _ in range(self.header_rows_to_skip):
                next(f)

            reader = csv.DictReader(f)
            available_headers = (
                [h.strip() for h in reader.fieldnames] if reader.fieldnames else []
            )

        # Create mapping for available fields only
        flexible_mapping = {}
        for csv_field, model_field in known_mappings.items():
            if csv_field in available_headers:
                flexible_mapping[csv_field] = model_field
            else:
                logger.debug(f"Field '{csv_field}' not found in CSV, skipping")

        return flexible_mapping
