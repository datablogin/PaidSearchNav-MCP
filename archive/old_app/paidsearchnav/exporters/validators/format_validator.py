"""Format compliance validation for Google Ads exports."""

import logging
from typing import List, Optional, Tuple

from paidsearchnav.core.models.analysis import Recommendation, RecommendationType
from paidsearchnav.core.models.export_models import (
    BidAdjustment,
    CampaignChange,
    KeywordChange,
    NegativeKeyword,
)
from paidsearchnav.core.models.google_ads_formats import (
    GoogleAdsCSVFormat,
    GoogleAdsValidation,
)

logger = logging.getLogger(__name__)


class FormatValidator:
    """Validates Google Ads import format compliance."""

    def validate_recommendation_data(
        self, recommendation: Recommendation
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate that a recommendation has the required data for export.

        Args:
            recommendation: Recommendation to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check required fields based on recommendation type
        required_fields = self._get_required_fields(recommendation.type)

        if not recommendation.action_data:
            if required_fields:
                return False, f"Missing required fields: {', '.join(required_fields)}"
            return False, "Recommendation missing action_data"

        missing_fields = [
            field
            for field in required_fields
            if field not in recommendation.action_data
        ]

        if missing_fields:
            return False, f"Missing required fields: {', '.join(missing_fields)}"

        return True, None

    def _get_required_fields(self, rec_type: RecommendationType) -> List[str]:
        """Get required fields for a recommendation type."""
        field_map = {
            RecommendationType.ADD_KEYWORD: [
                "keyword",
                "match_type",
                "campaign",
                "ad_group",
            ],
            RecommendationType.ADD_NEGATIVE: ["keyword", "match_type", "campaign"],
            RecommendationType.PAUSE_KEYWORD: ["keyword_id", "campaign", "ad_group"],
            RecommendationType.CHANGE_MATCH_TYPE: [
                "keyword",
                "old_match_type",
                "new_match_type",
                "campaign",
                "ad_group",
            ],
            RecommendationType.ADJUST_BID: [
                "campaign",
                "adjustment_type",
                "adjustment_value",
            ],
            RecommendationType.OPTIMIZE_LOCATION: [
                "campaign",
                "location",
                "bid_adjustment",
            ],
        }
        return field_map.get(rec_type, [])

    def validate_keyword_change(self, change: KeywordChange) -> Tuple[bool, List[str]]:
        """
        Validate a keyword change for Google Ads compliance.

        Args:
            change: KeywordChange to validate

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []

        # Validate customer ID
        if not GoogleAdsCSVFormat.validate_customer_id(change.customer_id):
            errors.append("Invalid customer ID format")

        # Validate campaign name
        valid, error = GoogleAdsValidation.validate_campaign_name(change.campaign)
        if not valid:
            errors.append(error)

        # Validate ad group name
        valid, error = GoogleAdsValidation.validate_ad_group_name(change.ad_group)
        if not valid:
            errors.append(error)

        # Validate keyword
        valid, error = GoogleAdsValidation.validate_keyword(change.keyword)
        if not valid:
            errors.append(error)

        # Validate bid if present
        if change.max_cpc is not None:
            valid, error = GoogleAdsValidation.validate_bid(change.max_cpc)
            if not valid:
                errors.append(error)

        # Validate URL if present
        if change.final_url:
            valid, error = GoogleAdsValidation.validate_url(change.final_url)
            if not valid:
                errors.append(error)

        return len(errors) == 0, errors

    def validate_negative_keyword(
        self, negative: NegativeKeyword
    ) -> Tuple[bool, List[str]]:
        """
        Validate a negative keyword for Google Ads compliance.

        Args:
            negative: NegativeKeyword to validate

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []

        # Validate customer ID
        if not GoogleAdsCSVFormat.validate_customer_id(negative.customer_id):
            errors.append("Invalid customer ID format")

        # Validate campaign name
        valid, error = GoogleAdsValidation.validate_campaign_name(negative.campaign)
        if not valid:
            errors.append(error)

        # Validate ad group name if not campaign-level
        if negative.ad_group and negative.ad_group not in ["[Campaign]", None]:
            valid, error = GoogleAdsValidation.validate_ad_group_name(negative.ad_group)
            if not valid:
                errors.append(error)

        # Validate keyword
        valid, error = GoogleAdsValidation.validate_keyword(negative.keyword)
        if not valid:
            errors.append(error)

        return len(errors) == 0, errors

    def validate_bid_adjustment(
        self, adjustment: BidAdjustment
    ) -> Tuple[bool, List[str]]:
        """
        Validate a bid adjustment for Google Ads compliance.

        Args:
            adjustment: BidAdjustment to validate

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []

        # Validate customer ID
        if not GoogleAdsCSVFormat.validate_customer_id(adjustment.customer_id):
            errors.append("Invalid customer ID format")

        # Validate campaign name
        valid, error = GoogleAdsValidation.validate_campaign_name(adjustment.campaign)
        if not valid:
            errors.append(error)

        # Must have either location or device
        if not adjustment.location and not adjustment.device:
            errors.append("Must specify either location or device for bid adjustment")

        # Validate bid adjustment value
        if adjustment.bid_adjustment:
            # Extract numeric value
            adj_str = adjustment.bid_adjustment.rstrip("%")
            is_negative = adj_str.startswith("-")
            adj_str = adj_str.lstrip("+-")
            try:
                adj_value = float(adj_str)
                if is_negative:
                    adj_value = -adj_value
                if adj_value < -100:
                    errors.append("Bid adjustment cannot be less than -100%")
                elif adj_value > 900:
                    errors.append("Bid adjustment cannot exceed +900%")
            except ValueError:
                errors.append("Invalid bid adjustment value")

        return len(errors) == 0, errors

    def validate_campaign_change(
        self, change: CampaignChange
    ) -> Tuple[bool, List[str]]:
        """
        Validate a campaign change for Google Ads compliance.

        Args:
            change: CampaignChange to validate

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []

        # Validate customer ID
        if not GoogleAdsCSVFormat.validate_customer_id(change.customer_id):
            errors.append("Invalid customer ID format")

        # Validate campaign name
        valid, error = GoogleAdsValidation.validate_campaign_name(change.campaign)
        if not valid:
            errors.append(error)

        # Validate budget if present
        if change.budget is not None:
            if change.budget < 0:
                errors.append("Budget cannot be negative")
            elif change.budget > 10000000:  # $10M daily budget limit
                errors.append("Budget exceeds maximum allowed value")

        # Validate Target CPA if present
        if change.target_cpa is not None:
            if change.target_cpa < 0:
                errors.append("Target CPA cannot be negative")

        # Validate Target ROAS if present
        if change.target_roas is not None:
            if change.target_roas < 0:
                errors.append("Target ROAS cannot be negative")

        return len(errors) == 0, errors

    def check_for_conflicts(
        self,
        keyword_changes: List[KeywordChange],
        negative_keywords: List[NegativeKeyword],
    ) -> List[str]:
        """
        Check for conflicts between keywords and negatives.

        Args:
            keyword_changes: List of keyword changes
            negative_keywords: List of negative keywords

        Returns:
            List of conflict warnings
        """
        warnings = []

        # Build sets of keywords and negatives by campaign
        campaign_keywords = {}
        campaign_negatives = {}

        for kw in keyword_changes:
            if kw.campaign not in campaign_keywords:
                campaign_keywords[kw.campaign] = set()
            campaign_keywords[kw.campaign].add(kw.keyword.lower())

        for neg in negative_keywords:
            if neg.campaign not in campaign_negatives:
                campaign_negatives[neg.campaign] = set()
            campaign_negatives[neg.campaign].add(neg.keyword.lower())

        # Check for conflicts
        for campaign in campaign_keywords:
            if campaign in campaign_negatives:
                conflicts = campaign_keywords[campaign].intersection(
                    campaign_negatives[campaign]
                )
                for conflict in conflicts:
                    warnings.append(
                        f"Keyword '{conflict}' is both positive and negative "
                        f"in campaign '{campaign}'"
                    )

        return warnings
