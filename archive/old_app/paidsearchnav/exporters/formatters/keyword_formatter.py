"""Formatter for keyword changes export."""

import csv
import io
import logging
from typing import List

from paidsearchnav.core.models.export_models import KeywordChange, KeywordChangesFile
from paidsearchnav.core.models.google_ads_formats import (
    GoogleAdsCSVFormat,
    GoogleAdsFileRequirements,
    GoogleAdsValidation,
)

logger = logging.getLogger(__name__)


class KeywordFormatter:
    """Formats keyword changes for Google Ads import."""

    def format_to_csv(self, changes: List[KeywordChange]) -> str:
        """
        Format keyword changes to CSV string.

        Args:
            changes: List of keyword changes

        Returns:
            CSV formatted string with BOM for Excel compatibility
        """
        output = io.StringIO()

        # Write BOM for Excel compatibility
        if GoogleAdsFileRequirements.INCLUDE_BOM:
            output.write("\ufeff")

        writer = csv.writer(
            output,
            delimiter=GoogleAdsFileRequirements.DELIMITER,
            quotechar=GoogleAdsFileRequirements.QUOTE_CHAR,
            quoting=csv.QUOTE_MINIMAL,
            lineterminator=GoogleAdsFileRequirements.LINE_TERMINATOR,
        )

        # Write headers
        writer.writerow(GoogleAdsCSVFormat.KEYWORD_CHANGES_HEADERS)

        # Write data rows
        for change in changes:
            row = self._format_row(change)
            writer.writerow(row)

        return output.getvalue()

    def _format_row(self, change: KeywordChange) -> List[str]:
        """Format a single keyword change to CSV row."""
        return [
            GoogleAdsCSVFormat.clean_customer_id(change.customer_id),
            GoogleAdsValidation.escape_csv_value(change.campaign),
            GoogleAdsValidation.escape_csv_value(change.ad_group),
            GoogleAdsValidation.escape_csv_value(change.keyword),
            change.match_type,
            change.status,
            GoogleAdsCSVFormat.format_currency(change.max_cpc)
            if change.max_cpc
            else "",
            change.final_url or "",
        ]

    def validate_changes(
        self, changes: List[KeywordChange]
    ) -> tuple[List[str], List[str]]:
        """
        Validate keyword changes before export.

        Args:
            changes: List of keyword changes to validate

        Returns:
            Tuple of (errors, warnings)
        """
        errors = []
        warnings = []

        if not changes:
            warnings.append("No keyword changes to export")
            return errors, warnings

        # Check total row count
        if len(changes) > GoogleAdsFileRequirements.MAX_ROWS_PER_FILE:
            errors.append(
                f"Too many rows ({len(changes)}). "
                f"Maximum is {GoogleAdsFileRequirements.MAX_ROWS_PER_FILE}"
            )

        # Validate each change
        for i, change in enumerate(changes):
            row_prefix = f"Row {i + 2}"  # +2 for header and 0-based index

            # Validate customer ID
            if not GoogleAdsCSVFormat.validate_customer_id(change.customer_id):
                errors.append(f"{row_prefix}: Invalid customer ID format")

            # Validate campaign name
            valid, error = GoogleAdsValidation.validate_campaign_name(change.campaign)
            if not valid:
                errors.append(f"{row_prefix}: {error}")

            # Validate ad group name
            valid, error = GoogleAdsValidation.validate_ad_group_name(change.ad_group)
            if not valid:
                errors.append(f"{row_prefix}: {error}")

            # Validate keyword
            valid, error = GoogleAdsValidation.validate_keyword(change.keyword)
            if not valid:
                errors.append(f"{row_prefix}: {error}")

            # Validate bid
            if change.max_cpc is not None:
                valid, error = GoogleAdsValidation.validate_bid(change.max_cpc)
                if not valid:
                    errors.append(f"{row_prefix}: {error}")

            # Validate URL
            if change.final_url:
                valid, error = GoogleAdsValidation.validate_url(change.final_url)
                if not valid:
                    errors.append(f"{row_prefix}: {error}")

        return errors, warnings

    def create_file(
        self, changes: List[KeywordChange], validate: bool = True
    ) -> KeywordChangesFile:
        """
        Create a keyword changes file.

        Args:
            changes: List of keyword changes
            validate: Whether to validate before creating

        Returns:
            KeywordChangesFile object
        """
        file = KeywordChangesFile(
            file_name="keyword_changes.csv",
            changes=changes,
            row_count=len(changes),
        )

        if validate:
            errors, warnings = self.validate_changes(changes)
            file.validation_errors = errors
            file.validation_warnings = warnings

        if not file.validation_errors:
            # Generate CSV content
            csv_content = self.format_to_csv(changes)
            file.file_size = len(csv_content.encode("utf-8"))

        return file
