"""Formatter for campaign changes export."""

import csv
import io
import logging
from typing import List

from paidsearchnav.core.models.export_models import CampaignChange, CampaignChangesFile
from paidsearchnav.core.models.google_ads_formats import (
    GoogleAdsBidStrategy,
    GoogleAdsCSVFormat,
    GoogleAdsFileRequirements,
    GoogleAdsValidation,
)

logger = logging.getLogger(__name__)


class CampaignFormatter:
    """Formats campaign changes for Google Ads import."""

    def format_to_csv(self, changes: List[CampaignChange]) -> str:
        """
        Format campaign changes to CSV string.

        Args:
            changes: List of campaign changes

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
        writer.writerow(GoogleAdsCSVFormat.CAMPAIGN_CHANGES_HEADERS)

        # Write data rows
        for change in changes:
            row = self._format_row(change)
            writer.writerow(row)

        return output.getvalue()

    def _format_row(self, change: CampaignChange) -> List[str]:
        """Format a single campaign change to CSV row."""
        return [
            GoogleAdsCSVFormat.clean_customer_id(change.customer_id),
            GoogleAdsValidation.escape_csv_value(change.campaign),
            change.status or "",
            GoogleAdsCSVFormat.format_currency(change.budget) if change.budget else "",
            change.bid_strategy or "",
            GoogleAdsCSVFormat.format_currency(change.target_cpa)
            if change.target_cpa
            else "",
            (
                GoogleAdsCSVFormat.format_currency(change.target_roas)
                if change.target_roas
                else ""
            ),
        ]

    def validate_changes(
        self, changes: List[CampaignChange]
    ) -> tuple[List[str], List[str]]:
        """
        Validate campaign changes before export.

        Args:
            changes: List of campaign changes to validate

        Returns:
            Tuple of (errors, warnings)
        """
        errors = []
        warnings = []

        if not changes:
            warnings.append("No campaign changes to export")
            return errors, warnings

        # Check total row count
        if len(changes) > GoogleAdsFileRequirements.MAX_ROWS_PER_FILE:
            errors.append(
                f"Too many rows ({len(changes)}). "
                f"Maximum is {GoogleAdsFileRequirements.MAX_ROWS_PER_FILE}"
            )

        # Track campaigns for duplicate detection
        seen_campaigns = set()

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

            # Check for duplicate campaigns
            if change.campaign in seen_campaigns:
                warnings.append(f"{row_prefix}: Duplicate campaign change")
            seen_campaigns.add(change.campaign)

            # Validate budget
            if change.budget is not None:
                if change.budget < 0:
                    errors.append(f"{row_prefix}: Budget cannot be negative")
                elif change.budget < 1:
                    warnings.append(
                        f"{row_prefix}: Budget ${change.budget:.2f} is below "
                        "recommended minimum of $1.00"
                    )
                elif change.budget > 1000000:
                    warnings.append(
                        f"{row_prefix}: Budget ${change.budget:.2f} is very high"
                    )

            # Validate bid strategy
            if change.bid_strategy:
                valid_strategies = [s.value for s in GoogleAdsBidStrategy]
                if change.bid_strategy not in valid_strategies:
                    errors.append(
                        f"{row_prefix}: Invalid bid strategy '{change.bid_strategy}'. "
                        f"Must be one of {valid_strategies}"
                    )

                # Validate strategy-specific fields
                if change.bid_strategy == GoogleAdsBidStrategy.TARGET_CPA.value:
                    if not change.target_cpa:
                        errors.append(
                            f"{row_prefix}: Target CPA is required for "
                            "Target CPA bid strategy"
                        )
                    elif change.target_cpa < 0:
                        errors.append(f"{row_prefix}: Target CPA cannot be negative")

                elif change.bid_strategy == GoogleAdsBidStrategy.TARGET_ROAS.value:
                    if not change.target_roas:
                        errors.append(
                            f"{row_prefix}: Target ROAS is required for "
                            "Target ROAS bid strategy"
                        )
                    elif change.target_roas < 0:
                        errors.append(f"{row_prefix}: Target ROAS cannot be negative")

            # Warn if conflicting strategy fields are set
            if change.target_cpa and change.target_roas:
                warnings.append(
                    f"{row_prefix}: Both Target CPA and Target ROAS are set. "
                    "Only one will be used based on bid strategy"
                )

        return errors, warnings

    def create_file(
        self, changes: List[CampaignChange], validate: bool = True
    ) -> CampaignChangesFile:
        """
        Create a campaign changes file.

        Args:
            changes: List of campaign changes
            validate: Whether to validate before creating

        Returns:
            CampaignChangesFile object
        """
        file = CampaignChangesFile(
            file_name="campaign_changes.csv",
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
