"""CSV formatting utilities for Google Ads Scripts data extraction.

This module ensures that data extracted by Google Ads Scripts is formatted
to be compatible with existing PaidSearchNav CSV parsers.
"""

import csv
import logging
from io import StringIO
from typing import Any, Dict, Generator, List, TextIO

logger = logging.getLogger(__name__)


class CSVFormatter:
    """Formats Google Ads Scripts output to match expected CSV formats."""

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def format_search_terms_csv(self, data: List[Dict[str, Any]]) -> str:
        """Format search terms data to match expected CSV format.

        Expected format matches what PaidSearchNav CSV parser expects:
        - Campaign, Search term, Clicks, Impressions, Cost, Conversions

        Args:
            data: List of search terms performance data

        Returns:
            CSV formatted string
        """
        headers = [
            "Campaign",
            "Ad Group",
            "Search term",
            "Match Type",
            "Clicks",
            "Impressions",
            "Cost",
            "Conversions",
            "Conv. rate",
            "Cost / conv.",
            "Avg. CPC",
            "CTR",
            "Impr. share",
        ]

        # Add geographic headers if present
        if data and any("Geographic Location" in row for row in data):
            headers.extend(
                [
                    "Geographic Location",
                    "Location Type",
                    "Is Local Intent",
                ]
            )

        output = StringIO()
        writer = csv.writer(output, quoting=csv.QUOTE_ALL)

        # Write headers
        writer.writerow(headers)

        # Write data rows
        for row in data:
            csv_row = [
                row.get("Campaign", ""),
                row.get("Ad Group", ""),
                row.get("Search Term", row.get("Query", "")),
                row.get("Match Type", ""),
                self._format_number(row.get("Clicks", 0)),
                self._format_number(row.get("Impressions", 0)),
                self._format_currency(row.get("Cost", 0)),
                self._format_number(row.get("Conversions", 0)),
                self._format_percentage(row.get("Conv. Rate", 0)),
                self._format_currency(row.get("Cost / Conv.", 0)),
                self._format_currency(row.get("CPC", 0)),
                self._format_percentage(row.get("CTR", 0)),
                self._format_percentage(row.get("Impression Share", 0)),
            ]

            # Add geographic data if present
            if "Geographic Location" in row:
                csv_row.extend(
                    [
                        row.get("Geographic Location", ""),
                        row.get("Location Type", ""),
                        str(row.get("Is Local Intent", False)),
                    ]
                )

            writer.writerow(csv_row)

        return output.getvalue()

    def format_keywords_csv(self, data: List[Dict[str, Any]]) -> str:
        """Format keywords data to match expected CSV format."""
        headers = [
            "Campaign",
            "Ad Group",
            "Keyword",
            "Match Type",
            "Clicks",
            "Impressions",
            "Cost",
            "Conversions",
            "Conv. rate",
            "Cost / conv.",
            "Avg. CPC",
            "CTR",
            "Avg. position",
            "Max. CPC",
            "Status",
        ]

        # Add quality score headers if present
        if data and any("Quality Score" in row for row in data):
            headers.extend(
                [
                    "Quality Score",
                    "Landing page experience",
                    "Ad relevance",
                    "Expected CTR",
                ]
            )

        headers.extend(
            [
                "First page bid",
                "Top of page bid",
                "Bid recommendation",
            ]
        )

        output = StringIO()
        writer = csv.writer(output, quoting=csv.QUOTE_ALL)

        # Write headers
        writer.writerow(headers)

        # Write data rows
        for row in data:
            csv_row = [
                row.get("Campaign", ""),
                row.get("Ad Group", ""),
                row.get("Keyword", row.get("Criteria", "")),
                row.get("Match Type", ""),
                self._format_number(row.get("Clicks", 0)),
                self._format_number(row.get("Impressions", 0)),
                self._format_currency(row.get("Cost", 0)),
                self._format_number(row.get("Conversions", 0)),
                self._format_percentage(row.get("Conv. Rate", 0)),
                self._format_currency(row.get("Cost / Conv.", 0)),
                self._format_currency(row.get("CPC", 0)),
                self._format_percentage(row.get("CTR", 0)),
                self._format_number(row.get("Avg. Position", 0)),
                self._format_currency(row.get("Max CPC", 0)),
                row.get("Status", ""),
            ]

            # Add quality score data if present
            if "Quality Score" in row:
                csv_row.extend(
                    [
                        self._format_number(row.get("Quality Score", 0)),
                        row.get("Landing Page Experience", ""),
                        row.get("Ad Relevance", ""),
                        row.get("Expected CTR", ""),
                    ]
                )

            csv_row.extend(
                [
                    self._format_currency(row.get("First Page Bid", 0)),
                    self._format_currency(row.get("Top of Page Bid", 0)),
                    row.get("Bid Recommendation", ""),
                ]
            )

            writer.writerow(csv_row)

        return output.getvalue()

    def format_bulk_actions_csv(self, data: List[Dict[str, Any]]) -> str:
        """Format data for bulk actions CSV compatible with Google Ads Editor.

        This matches the format seen in bulk_actions_keyword_optimization.csv:
        Action,Campaign,Ad Group,Keyword,Match Type,Max CPC,Landing Page,Status,First Page Bid Estimate,Top of Page Bid Estimate
        """
        headers = [
            "Action",
            "Campaign",
            "Ad Group",
            "Keyword",
            "Match Type",
            "Max CPC",
            "Landing Page",
            "Status",
            "First Page Bid Estimate",
            "Top of Page Bid Estimate",
        ]

        output = StringIO()
        writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)

        # Write headers
        writer.writerow(headers)

        # Write data rows
        for row in data:
            csv_row = [
                row.get("Action", "CREATE"),
                row.get("Campaign", ""),
                row.get("Ad Group", ""),
                self._format_keyword_for_bulk_action(
                    row.get("Keyword", ""), row.get("Match Type", "Exact")
                ),
                row.get("Match Type", "Exact"),
                self._format_bid_for_bulk_action(row.get("Max CPC", 0)),
                row.get("Landing Page", ""),
                row.get("Status", "Enabled"),
                self._format_bid_for_bulk_action(row.get("First Page Bid Estimate", 0)),
                self._format_bid_for_bulk_action(
                    row.get("Top of Page Bid Estimate", 0)
                ),
            ]

            writer.writerow(csv_row)

        return output.getvalue()

    def format_geographic_csv(self, data: List[Dict[str, Any]]) -> str:
        """Format geographic performance data."""
        headers = [
            "Campaign",
            "Ad Group",
            "Geographic Location",
            "Location Type",
            "Clicks",
            "Impressions",
            "Cost",
            "Conversions",
            "Conv. rate",
            "Cost / conv.",
            "Avg. CPC",
            "CTR",
            "Distance",
            "Local Intent Score",
            "Store Performance Rank",
        ]

        output = StringIO()
        writer = csv.writer(output, quoting=csv.QUOTE_ALL)

        # Write headers
        writer.writerow(headers)

        # Write data rows
        for row in data:
            csv_row = [
                row.get("Campaign", ""),
                row.get("Ad Group", ""),
                row.get("Geographic Location", ""),
                row.get("Location Type", ""),
                self._format_number(row.get("Clicks", 0)),
                self._format_number(row.get("Impressions", 0)),
                self._format_currency(row.get("Cost", 0)),
                self._format_number(row.get("Conversions", 0)),
                self._format_percentage(row.get("Conv. Rate", 0)),
                self._format_currency(row.get("Cost / Conv.", 0)),
                self._format_currency(row.get("CPC", 0)),
                self._format_percentage(row.get("CTR", 0)),
                row.get("Distance", ""),
                row.get("Local Intent Score", ""),
                self._format_number(row.get("Store Performance Rank", 0)),
            ]

            writer.writerow(csv_row)

        return output.getvalue()

    def format_campaign_csv(self, data: List[Dict[str, Any]]) -> str:
        """Format campaign performance data."""
        headers = [
            "Campaign",
            "Campaign Type",
            "Status",
            "Budget",
            "Clicks",
            "Impressions",
            "Cost",
            "Conversions",
            "Conv. rate",
            "Cost / conv.",
            "Avg. CPC",
            "CTR",
            "Impr. share",
            "Budget utilization",
            "Performance score",
        ]

        # Add device data headers if present
        if data and any("Mobile Clicks" in row for row in data):
            headers.extend(
                [
                    "Mobile clicks %",
                    "Desktop clicks %",
                    "Tablet clicks %",
                    "Mobile conv. rate",
                    "Desktop conv. rate",
                ]
            )

        # Add demographic headers if present
        if data and any("Age 18-24 Performance" in row for row in data):
            headers.extend(
                [
                    "Age 18-24",
                    "Age 25-34",
                    "Age 35-44",
                    "Age 45-54",
                    "Age 55+",
                ]
            )

        output = StringIO()
        writer = csv.writer(output, quoting=csv.QUOTE_ALL)

        # Write headers
        writer.writerow(headers)

        # Write data rows
        for row in data:
            csv_row = [
                row.get("Campaign", ""),
                row.get("Campaign Type", ""),
                row.get("Status", ""),
                self._format_currency(row.get("Budget", 0)),
                self._format_number(row.get("Clicks", 0)),
                self._format_number(row.get("Impressions", 0)),
                self._format_currency(row.get("Cost", 0)),
                self._format_number(row.get("Conversions", 0)),
                self._format_percentage(row.get("Conv. Rate", 0)),
                self._format_currency(row.get("Cost / Conv.", 0)),
                self._format_currency(row.get("CPC", 0)),
                self._format_percentage(row.get("CTR", 0)),
                self._format_percentage(row.get("Impression Share", 0)),
                row.get("Budget Utilization", ""),
                row.get("Performance Score", ""),
            ]

            # Add device data if present
            if "Mobile Clicks" in row:
                csv_row.extend(
                    [
                        row.get("Mobile Clicks", ""),
                        row.get("Desktop Clicks", ""),
                        row.get("Tablet Clicks", ""),
                        row.get("Mobile Conv Rate", ""),
                        row.get("Desktop Conv Rate", ""),
                    ]
                )

            # Add demographic data if present
            if "Age 18-24 Performance" in row:
                csv_row.extend(
                    [
                        row.get("Age 18-24 Performance", ""),
                        row.get("Age 25-34 Performance", ""),
                        row.get("Age 35-44 Performance", ""),
                        row.get("Age 45-54 Performance", ""),
                        row.get("Age 55+ Performance", ""),
                    ]
                )

            writer.writerow(csv_row)

        return output.getvalue()

    def _format_number(self, value: Any) -> str:
        """Format numeric value for CSV output."""
        if value is None or value == "":
            return "0"

        try:
            # Handle string percentages and remove % sign
            if isinstance(value, str) and value.endswith("%"):
                value = value.rstrip("%")

            # Convert to float and format
            num_value = float(value)

            # Format with appropriate decimal places
            if num_value == int(num_value):
                return str(int(num_value))
            else:
                return f"{num_value:.2f}".rstrip("0").rstrip(".")

        except (ValueError, TypeError):
            return str(value)

    def _format_currency(self, value: Any) -> str:
        """Format currency value for CSV output."""
        if value is None or value == "":
            return "$0.00"

        try:
            # Remove currency symbols and commas
            if isinstance(value, str):
                value = value.replace("$", "").replace(",", "")

            num_value = float(value)
            return f"${num_value:.2f}"

        except (ValueError, TypeError):
            return str(value)

    def _format_percentage(self, value: Any) -> str:
        """Format percentage value for CSV output."""
        if value is None or value == "":
            return "0.00%"

        try:
            # Handle existing percentage strings
            if isinstance(value, str) and value.endswith("%"):
                return value

            num_value = float(value)

            # If value is already in percentage form (e.g., 5.5 for 5.5%)
            if num_value > 1:
                return f"{num_value:.2f}%"
            else:
                # Convert decimal to percentage (e.g., 0.055 to 5.5%)
                return f"{num_value * 100:.2f}%"

        except (ValueError, TypeError):
            return str(value)

    def _format_keyword_for_bulk_action(self, keyword: str, match_type: str) -> str:
        """Format keyword for bulk action CSV based on match type."""
        if not keyword:
            return ""

        match_type = match_type.lower()

        if match_type == "exact":
            return f"[{keyword}]"
        elif match_type == "phrase":
            return f'"{keyword}"'
        else:  # broad match
            return keyword

    def _format_bid_for_bulk_action(self, bid: Any) -> str:
        """Format bid value for bulk actions (no currency symbol)."""
        if bid is None or bid == "":
            return "0.00"

        try:
            # Remove currency symbols
            if isinstance(bid, str):
                bid = bid.replace("$", "").replace(",", "")

            num_value = float(bid)
            return f"{num_value:.2f}"

        except (ValueError, TypeError):
            return "0.00"


class StreamingCSVWriter:
    """Memory-efficient CSV writer for large datasets.

    This class allows writing CSV data row by row to avoid loading
    large datasets into memory all at once.
    """

    def __init__(self, output_file: TextIO, headers: List[str]):
        """Initialize streaming CSV writer.

        Args:
            output_file: File-like object to write CSV data to
            headers: List of column headers
        """
        self.output_file = output_file
        self.writer = csv.writer(output_file, quoting=csv.QUOTE_ALL)
        self.headers = headers
        self._headers_written = False
        self.rows_written = 0
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def write_headers(self) -> None:
        """Write CSV headers if not already written."""
        if not self._headers_written:
            self.writer.writerow(self.headers)
            self._headers_written = True
            self.logger.debug(f"Headers written: {len(self.headers)} columns")

    def write_row(self, row_data: Dict[str, Any]) -> None:
        """Write a single data row.

        Args:
            row_data: Dictionary containing row data with keys matching headers
        """
        if not self._headers_written:
            self.write_headers()

        # Convert row data to list in header order
        row_values = []
        for header in self.headers:
            value = row_data.get(header, "")

            # Apply appropriate formatting based on header name
            if any(
                cost_keyword in header.lower()
                for cost_keyword in ["cost", "cpc", "bid", "budget"]
            ):
                if "estimate" in header.lower() or "bid" in header.lower():
                    # Bid values without currency symbol for bulk actions
                    formatted_value = self._format_bid_for_bulk_action(value)
                else:
                    formatted_value = self._format_currency(value)
            elif (
                "rate" in header.lower()
                or "share" in header.lower()
                or "ctr" in header.lower()
            ):
                formatted_value = self._format_percentage(value)
            elif header.lower() in [
                "clicks",
                "impressions",
                "conversions",
                "quality score",
            ]:
                formatted_value = self._format_number(value)
            elif header.lower() == "keyword" and "match type" in row_data:
                # Apply keyword formatting for bulk actions
                formatted_value = self._format_keyword_for_bulk_action(
                    value, row_data.get("Match Type", "Broad")
                )
            else:
                formatted_value = str(value) if value is not None else ""

            row_values.append(formatted_value)

        self.writer.writerow(row_values)
        self.rows_written += 1

        if self.rows_written % 1000 == 0:
            self.logger.debug(f"Written {self.rows_written} rows")

    def write_batch(self, batch_data: List[Dict[str, Any]]) -> None:
        """Write a batch of rows efficiently.

        Args:
            batch_data: List of dictionaries containing row data
        """
        for row_data in batch_data:
            self.write_row(row_data)

    def write_from_generator(
        self, data_generator: Generator[Dict[str, Any], None, None]
    ) -> None:
        """Write data from a generator for maximum memory efficiency.

        Args:
            data_generator: Generator yielding row data dictionaries
        """
        for row_data in data_generator:
            self.write_row(row_data)

    def flush(self) -> None:
        """Flush the output file."""
        if hasattr(self.output_file, "flush"):
            self.output_file.flush()

    def close(self) -> None:
        """Close the writer and output file."""
        self.flush()
        if hasattr(self.output_file, "close"):
            self.output_file.close()
        self.logger.info(
            f"CSV writing completed. Total rows written: {self.rows_written}"
        )

    def get_stats(self) -> Dict[str, Any]:
        """Get writing statistics."""
        return {
            "rows_written": self.rows_written,
            "headers_count": len(self.headers),
            "headers_written": self._headers_written,
        }

    def _format_number(self, value: Any) -> str:
        """Format numeric value for CSV output."""
        if value is None or value == "":
            return "0"

        try:
            # Handle string percentages and remove % sign
            if isinstance(value, str) and value.endswith("%"):
                value = value.rstrip("%")

            # Convert to float and format
            num_value = float(value)

            # Format with appropriate decimal places
            if num_value == int(num_value):
                return str(int(num_value))
            else:
                return f"{num_value:.2f}".rstrip("0").rstrip(".")

        except (ValueError, TypeError):
            return str(value)

    def _format_currency(self, value: Any) -> str:
        """Format currency value for CSV output."""
        if value is None or value == "":
            return "$0.00"

        try:
            # Remove currency symbols and commas
            if isinstance(value, str):
                value = value.replace("$", "").replace(",", "")

            num_value = float(value)
            return f"${num_value:.2f}"

        except (ValueError, TypeError):
            return str(value)

    def _format_percentage(self, value: Any) -> str:
        """Format percentage value for CSV output."""
        if value is None or value == "":
            return "0.00%"

        try:
            # Handle existing percentage strings
            if isinstance(value, str) and value.endswith("%"):
                return value

            num_value = float(value)

            # If value is already in percentage form (e.g., 5.5 for 5.5%)
            if num_value > 1:
                return f"{num_value:.2f}%"
            else:
                # Convert decimal to percentage (e.g., 0.055 to 5.5%)
                return f"{num_value * 100:.2f}%"

        except (ValueError, TypeError):
            return str(value)

    def _format_keyword_for_bulk_action(self, keyword: str, match_type: str) -> str:
        """Format keyword for bulk action CSV based on match type."""
        if not keyword:
            return ""

        match_type = match_type.lower()

        if match_type == "exact":
            return f"[{keyword}]"
        elif match_type == "phrase":
            return f'"{keyword}"'
        else:  # broad match
            return keyword

    def _format_bid_for_bulk_action(self, bid: Any) -> str:
        """Format bid value for bulk actions (no currency symbol)."""
        if bid is None or bid == "":
            return "0.00"

        try:
            # Remove currency symbols
            if isinstance(bid, str):
                bid = bid.replace("$", "").replace(",", "")

            num_value = float(bid)
            return f"{num_value:.2f}"

        except (ValueError, TypeError):
            return "0.00"


class CSVCompatibilityValidator:
    """Validates CSV output compatibility with existing parsers."""

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def validate_search_terms_format(self, csv_content: str) -> Dict[str, Any]:
        """Validate search terms CSV format."""
        return self._validate_csv_structure(
            csv_content,
            required_headers=[
                "Campaign",
                "Search term",
                "Clicks",
                "Impressions",
                "Cost",
            ],
            format_type="search_terms",
        )

    def validate_keywords_format(self, csv_content: str) -> Dict[str, Any]:
        """Validate keywords CSV format."""
        return self._validate_csv_structure(
            csv_content,
            required_headers=[
                "Campaign",
                "Keyword",
                "Match Type",
                "Clicks",
                "Impressions",
            ],
            format_type="keywords",
        )

    def validate_bulk_actions_format(self, csv_content: str) -> Dict[str, Any]:
        """Validate bulk actions CSV format."""
        return self._validate_csv_structure(
            csv_content,
            required_headers=[
                "Action",
                "Campaign",
                "Ad Group",
                "Keyword",
                "Match Type",
            ],
            format_type="bulk_actions",
        )

    def _validate_csv_structure(
        self, csv_content: str, required_headers: List[str], format_type: str
    ) -> Dict[str, Any]:
        """Validate CSV structure and format."""
        try:
            reader = csv.reader(StringIO(csv_content))
            headers = next(reader, [])

            # Check required headers
            missing_headers = [h for h in required_headers if h not in headers]

            # Count data rows
            row_count = sum(1 for _ in reader)

            # Validate data format (basic checks)
            errors = []
            warnings = []

            if missing_headers:
                errors.append(f"Missing required headers: {missing_headers}")

            if row_count == 0:
                warnings.append("No data rows found")

            # Additional format-specific validations
            if format_type == "bulk_actions":
                self._validate_bulk_actions_content(csv_content, errors, warnings)

            return {
                "valid": len(errors) == 0,
                "errors": errors,
                "warnings": warnings,
                "row_count": row_count,
                "headers": headers,
                "format_type": format_type,
            }

        except Exception as e:
            return {
                "valid": False,
                "errors": [f"CSV parsing error: {str(e)}"],
                "warnings": [],
                "row_count": 0,
                "headers": [],
                "format_type": format_type,
            }

    def _validate_bulk_actions_content(
        self, csv_content: str, errors: List[str], warnings: List[str]
    ) -> None:
        """Validate bulk actions CSV content."""
        try:
            reader = csv.reader(StringIO(csv_content))
            headers = next(reader, [])

            action_col = headers.index("Action") if "Action" in headers else -1
            match_type_col = (
                headers.index("Match Type") if "Match Type" in headers else -1
            )
            keyword_col = headers.index("Keyword") if "Keyword" in headers else -1

            for row_num, row in enumerate(reader, start=2):
                if len(row) <= max(action_col, match_type_col, keyword_col):
                    continue

                # Validate action
                if action_col >= 0 and row[action_col] not in [
                    "CREATE",
                    "UPDATE",
                    "DELETE",
                ]:
                    warnings.append(
                        f"Row {row_num}: Unexpected action '{row[action_col]}'"
                    )

                # Validate keyword format matches match type
                if keyword_col >= 0 and match_type_col >= 0:
                    keyword = row[keyword_col]
                    match_type = row[match_type_col].lower()

                    if match_type == "exact" and not (
                        keyword.startswith("[") and keyword.endswith("]")
                    ):
                        warnings.append(
                            f"Row {row_num}: Exact match keyword should be in brackets"
                        )
                    elif match_type == "phrase" and not (
                        keyword.startswith('"') and keyword.endswith('"')
                    ):
                        warnings.append(
                            f"Row {row_num}: Phrase match keyword should be in quotes"
                        )

        except Exception as e:
            errors.append(f"Content validation error: {str(e)}")
