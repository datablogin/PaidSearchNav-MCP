"""Formatter for negative keywords export."""

import csv
import io
import logging
from typing import List

from paidsearchnav.core.models.export_models import (
    NegativeKeyword,
    NegativeKeywordsFile,
)
from paidsearchnav.core.models.google_ads_formats import (
    GoogleAdsCSVFormat,
    GoogleAdsFileRequirements,
    GoogleAdsValidation,
)

logger = logging.getLogger(__name__)


class NegativeKeywordFormatter:
    """Formats negative keywords for Google Ads import."""

    def format_to_csv(self, negatives: List[NegativeKeyword]) -> str:
        """
        Format negative keywords to CSV string.

        Args:
            negatives: List of negative keywords

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
        writer.writerow(GoogleAdsCSVFormat.NEGATIVE_KEYWORDS_HEADERS)

        # Write data rows
        for negative in negatives:
            row = self._format_row(negative)
            writer.writerow(row)

        return output.getvalue()

    def _format_row(self, negative: NegativeKeyword) -> List[str]:
        """Format a single negative keyword to CSV row."""
        # Determine ad group value
        ad_group_value = ""
        if negative.ad_group:
            if negative.ad_group == "[Campaign]":
                ad_group_value = GoogleAdsCSVFormat.CAMPAIGN_LEVEL_NEGATIVE
            else:
                ad_group_value = GoogleAdsValidation.escape_csv_value(negative.ad_group)
        else:
            # Default to campaign level if not specified
            ad_group_value = GoogleAdsCSVFormat.CAMPAIGN_LEVEL_NEGATIVE

        return [
            GoogleAdsCSVFormat.clean_customer_id(negative.customer_id),
            GoogleAdsValidation.escape_csv_value(negative.campaign),
            ad_group_value,
            GoogleAdsValidation.escape_csv_value(negative.keyword),
            negative.match_type,
        ]

    def validate_negatives(
        self, negatives: List[NegativeKeyword]
    ) -> tuple[List[str], List[str]]:
        """
        Validate negative keywords before export.

        Args:
            negatives: List of negative keywords to validate

        Returns:
            Tuple of (errors, warnings)
        """
        errors = []
        warnings = []

        if not negatives:
            warnings.append("No negative keywords to export")
            return errors, warnings

        # Check total row count
        if len(negatives) > GoogleAdsFileRequirements.MAX_ROWS_PER_FILE:
            errors.append(
                f"Too many rows ({len(negatives)}). "
                f"Maximum is {GoogleAdsFileRequirements.MAX_ROWS_PER_FILE}"
            )

        # Track campaign-level negatives for duplicate detection
        campaign_negatives = {}
        ad_group_negatives = {}

        # Validate each negative
        for i, negative in enumerate(negatives):
            row_prefix = f"Row {i + 2}"  # +2 for header and 0-based index

            # Validate customer ID
            if not GoogleAdsCSVFormat.validate_customer_id(negative.customer_id):
                errors.append(f"{row_prefix}: Invalid customer ID format")

            # Validate campaign name
            valid, error = GoogleAdsValidation.validate_campaign_name(negative.campaign)
            if not valid:
                errors.append(f"{row_prefix}: {error}")

            # Validate ad group name if not campaign-level
            if negative.ad_group and negative.ad_group not in ["[Campaign]", None]:
                valid, error = GoogleAdsValidation.validate_ad_group_name(
                    negative.ad_group
                )
                if not valid:
                    errors.append(f"{row_prefix}: {error}")

            # Validate keyword
            valid, error = GoogleAdsValidation.validate_keyword(negative.keyword)
            if not valid:
                errors.append(f"{row_prefix}: {error}")

            # Check for duplicates
            if negative.level == "campaign":
                key = (negative.campaign, negative.keyword.lower(), negative.match_type)
                if key in campaign_negatives:
                    warnings.append(
                        f"{row_prefix}: Duplicate campaign-level negative keyword"
                    )
                campaign_negatives[key] = True
            else:
                key = (
                    negative.campaign,
                    negative.ad_group,
                    negative.keyword.lower(),
                    negative.match_type,
                )
                if key in ad_group_negatives:
                    warnings.append(
                        f"{row_prefix}: Duplicate ad group-level negative keyword"
                    )
                ad_group_negatives[key] = True

        return errors, warnings

    def create_file(
        self, negatives: List[NegativeKeyword], validate: bool = True
    ) -> NegativeKeywordsFile:
        """
        Create a negative keywords file.

        Args:
            negatives: List of negative keywords
            validate: Whether to validate before creating

        Returns:
            NegativeKeywordsFile object
        """
        file = NegativeKeywordsFile(
            file_name="negative_keywords.csv",
            negatives=negatives,
            row_count=len(negatives),
        )

        if validate:
            errors, warnings = self.validate_negatives(negatives)
            file.validation_errors = errors
            file.validation_warnings = warnings

        if not file.validation_errors:
            # Generate CSV content
            csv_content = self.format_to_csv(negatives)
            file.file_size = len(csv_content.encode("utf-8"))

        return file
