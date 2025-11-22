"""Formatter for bid adjustments export."""

import csv
import io
import logging
from typing import List

from paidsearchnav.core.models.export_models import BidAdjustment, BidAdjustmentsFile
from paidsearchnav.core.models.google_ads_formats import (
    GoogleAdsCSVFormat,
    GoogleAdsDevice,
    GoogleAdsFileRequirements,
    GoogleAdsValidation,
)

logger = logging.getLogger(__name__)


class BidAdjustmentFormatter:
    """Formats bid adjustments for Google Ads import."""

    def format_to_csv(self, adjustments: List[BidAdjustment]) -> str:
        """
        Format bid adjustments to CSV string.

        Args:
            adjustments: List of bid adjustments

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
        writer.writerow(GoogleAdsCSVFormat.BID_ADJUSTMENTS_HEADERS)

        # Write data rows
        for adjustment in adjustments:
            row = self._format_row(adjustment)
            writer.writerow(row)

        return output.getvalue()

    def _format_row(self, adjustment: BidAdjustment) -> List[str]:
        """Format a single bid adjustment to CSV row."""
        return [
            GoogleAdsCSVFormat.clean_customer_id(adjustment.customer_id),
            GoogleAdsValidation.escape_csv_value(adjustment.campaign),
            adjustment.location or "",
            adjustment.device or "",
            adjustment.bid_adjustment,
        ]

    def validate_adjustments(
        self, adjustments: List[BidAdjustment]
    ) -> tuple[List[str], List[str]]:
        """
        Validate bid adjustments before export.

        Args:
            adjustments: List of bid adjustments to validate

        Returns:
            Tuple of (errors, warnings)
        """
        errors = []
        warnings = []

        if not adjustments:
            warnings.append("No bid adjustments to export")
            return errors, warnings

        # Check total row count
        if len(adjustments) > GoogleAdsFileRequirements.MAX_ROWS_PER_FILE:
            errors.append(
                f"Too many rows ({len(adjustments)}). "
                f"Maximum is {GoogleAdsFileRequirements.MAX_ROWS_PER_FILE}"
            )

        # Track adjustments for duplicate detection
        seen_adjustments = set()

        # Validate each adjustment
        for i, adjustment in enumerate(adjustments):
            row_prefix = f"Row {i + 2}"  # +2 for header and 0-based index

            # Validate customer ID
            if not GoogleAdsCSVFormat.validate_customer_id(adjustment.customer_id):
                errors.append(f"{row_prefix}: Invalid customer ID format")

            # Validate campaign name
            valid, error = GoogleAdsValidation.validate_campaign_name(
                adjustment.campaign
            )
            if not valid:
                errors.append(f"{row_prefix}: {error}")

            # Validate bid adjustment format (already validated in model)
            # but check for reasonable values
            if adjustment.bid_adjustment:
                # Extract numeric value
                adj_str = adjustment.bid_adjustment.rstrip("%").lstrip("+-")
                is_negative = adjustment.bid_adjustment.startswith("-")
                try:
                    adj_value = float(adj_str)
                    if is_negative:
                        adj_value = -adj_value
                    if adj_value <= -90:
                        warnings.append(
                            f"{row_prefix}: Bid adjustment {adjustment.bid_adjustment} "
                            "is very low (≤ -90%)"
                        )
                    elif adj_value > 900:
                        warnings.append(
                            f"{row_prefix}: Bid adjustment {adjustment.bid_adjustment} "
                            "is very high (> +900%)"
                        )
                except ValueError:
                    errors.append(f"{row_prefix}: Invalid bid adjustment value")

            # Validate device if specified
            if adjustment.device:
                valid_devices = [d.value for d in GoogleAdsDevice]
                if adjustment.device not in valid_devices:
                    errors.append(
                        f"{row_prefix}: Invalid device '{adjustment.device}'. "
                        f"Must be one of {valid_devices}"
                    )

            # Check for conflicting adjustments
            if not adjustment.location and not adjustment.device:
                errors.append(
                    f"{row_prefix}: Must specify either location or device for bid adjustment"
                )

            # Check for duplicates
            key = (
                adjustment.campaign,
                adjustment.location or "",
                adjustment.device or "",
            )
            if key in seen_adjustments:
                warnings.append(
                    f"{row_prefix}: Duplicate bid adjustment for same campaign/"
                    f"location/device combination"
                )
            seen_adjustments.add(key)

        return errors, warnings

    def create_file(
        self, adjustments: List[BidAdjustment], validate: bool = True
    ) -> BidAdjustmentsFile:
        """
        Create a bid adjustments file.

        Args:
            adjustments: List of bid adjustments
            validate: Whether to validate before creating

        Returns:
            BidAdjustmentsFile object
        """
        file = BidAdjustmentsFile(
            file_name="bid_adjustments.csv",
            adjustments=adjustments,
            row_count=len(adjustments),
        )

        if validate:
            errors, warnings = self.validate_adjustments(adjustments)
            file.validation_errors = errors
            file.validation_warnings = warnings

        if not file.validation_errors:
            # Generate CSV content
            csv_content = self.format_to_csv(adjustments)
            file.file_size = len(csv_content.encode("utf-8"))

        return file
