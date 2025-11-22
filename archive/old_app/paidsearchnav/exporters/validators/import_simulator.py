"""Import simulation testing for Google Ads exports."""

import logging
from typing import Dict, List, Optional, Tuple

from paidsearchnav.core.models.export_models import (
    BidAdjustment,
    CampaignChange,
    KeywordChange,
    NegativeKeyword,
)

logger = logging.getLogger(__name__)


class ImportSimulator:
    """Simulates Google Ads import to detect potential issues."""

    def __init__(self):
        """Initialize the import simulator."""
        self.simulation_results = []

    def simulate_keyword_import(
        self, changes: List[KeywordChange], existing_keywords: Optional[Dict] = None
    ) -> Tuple[bool, List[str]]:
        """
        Simulate importing keyword changes.

        Args:
            changes: List of keyword changes to simulate
            existing_keywords: Optional dict of existing keywords by campaign/ad group

        Returns:
            Tuple of (success, list_of_issues)
        """
        issues = []
        existing = existing_keywords or {}

        # Check for duplicates within the import
        seen_keywords = set()
        for change in changes:
            key = (
                change.campaign,
                change.ad_group,
                change.keyword.lower(),
                change.match_type,
            )
            if key in seen_keywords:
                issues.append(
                    f"Duplicate keyword: '{change.keyword}' ({change.match_type}) "
                    f"in {change.campaign}/{change.ad_group}"
                )
            seen_keywords.add(key)

            # Check against existing keywords
            campaign_keywords = existing.get(change.campaign, {})
            ad_group_keywords = campaign_keywords.get(change.ad_group, set())
            if (change.keyword.lower(), change.match_type) in ad_group_keywords:
                issues.append(
                    f"Keyword already exists: '{change.keyword}' ({change.match_type}) "
                    f"in {change.campaign}/{change.ad_group}"
                )

        return len(issues) == 0, issues

    def simulate_negative_import(
        self,
        negatives: List[NegativeKeyword],
        existing_positives: Optional[Dict] = None,
    ) -> Tuple[bool, List[str]]:
        """
        Simulate importing negative keywords.

        Args:
            negatives: List of negative keywords to simulate
            existing_positives: Optional dict of existing positive keywords

        Returns:
            Tuple of (success, list_of_issues)
        """
        issues = []
        existing = existing_positives or {}

        # Group negatives by campaign
        campaign_negatives = {}
        for neg in negatives:
            if neg.campaign not in campaign_negatives:
                campaign_negatives[neg.campaign] = []
            campaign_negatives[neg.campaign].append(neg)

        # Check for conflicts with existing keywords
        for campaign, negs in campaign_negatives.items():
            if campaign not in existing:
                continue

            for neg in negs:
                # Check if negative would block existing keywords
                blocked_count = self._count_blocked_keywords(
                    neg.keyword, neg.match_type, existing[campaign]
                )
                if blocked_count > 0:
                    issues.append(
                        f"Negative keyword '{neg.keyword}' ({neg.match_type}) "
                        f"would block {blocked_count} existing keywords in {campaign}"
                    )

        return len(issues) == 0, issues

    def simulate_bid_adjustment_import(
        self, adjustments: List[BidAdjustment]
    ) -> Tuple[bool, List[str]]:
        """
        Simulate importing bid adjustments.

        Args:
            adjustments: List of bid adjustments to simulate

        Returns:
            Tuple of (success, list_of_issues)
        """
        issues = []

        # Check for conflicting adjustments
        seen_adjustments = {}
        for adj in adjustments:
            key = (adj.campaign, adj.location or "", adj.device or "")
            if key in seen_adjustments:
                existing = seen_adjustments[key]
                issues.append(
                    f"Conflicting bid adjustments for {adj.campaign}: "
                    f"{existing} vs {adj.bid_adjustment}"
                )
            else:
                seen_adjustments[key] = adj.bid_adjustment

        # Check for extreme adjustments
        for adj in adjustments:
            # Extract numeric value
            adj_str = adj.bid_adjustment.rstrip("%")
            is_negative = adj_str.startswith("-")
            adj_str = adj_str.lstrip("+-")
            try:
                adj_value = float(adj_str)
                if is_negative:
                    adj_value = -adj_value
                if adj_value <= -90:
                    issues.append(
                        f"Bid adjustment {adj.bid_adjustment} for {adj.campaign} "
                        "may pause traffic (≤ -90%)"
                    )
            except ValueError:
                pass  # Already validated elsewhere

        return len(issues) == 0, issues

    def simulate_campaign_import(
        self, changes: List[CampaignChange]
    ) -> Tuple[bool, List[str]]:
        """
        Simulate importing campaign changes.

        Args:
            changes: List of campaign changes to simulate

        Returns:
            Tuple of (success, list_of_issues)
        """
        issues = []

        # Check for duplicate campaign changes
        seen_campaigns = set()
        for change in changes:
            if change.campaign in seen_campaigns:
                issues.append(f"Multiple changes for campaign: {change.campaign}")
            seen_campaigns.add(change.campaign)

            # Check for low budgets
            if change.budget is not None and change.budget < 1:
                issues.append(
                    f"Campaign '{change.campaign}' budget ${change.budget:.2f} "
                    "is below minimum ($1.00)"
                )

            # Check for missing required fields for bid strategies
            if change.bid_strategy == "Target CPA" and not change.target_cpa:
                issues.append(
                    f"Campaign '{change.campaign}' using Target CPA strategy "
                    "but no target CPA specified"
                )
            elif change.bid_strategy == "Target ROAS" and not change.target_roas:
                issues.append(
                    f"Campaign '{change.campaign}' using Target ROAS strategy "
                    "but no target ROAS specified"
                )

        return len(issues) == 0, issues

    def _count_blocked_keywords(
        self, negative: str, match_type: str, keywords: Dict
    ) -> int:
        """
        Count how many keywords would be blocked by a negative.

        Args:
            negative: Negative keyword text
            match_type: Match type of negative
            keywords: Dict of keywords by ad group

        Returns:
            Count of blocked keywords
        """
        blocked = 0
        negative_lower = negative.lower()

        for ad_group, kw_set in keywords.items():
            for kw, kw_match in kw_set:
                kw_lower = kw.lower()

                # Check blocking based on match type
                if match_type == "Exact":
                    if kw_lower == negative_lower:
                        blocked += 1
                elif match_type == "Phrase":
                    if negative_lower in kw_lower:
                        blocked += 1
                elif match_type == "Broad":
                    # Simplified broad match check
                    negative_words = set(negative_lower.split())
                    kw_words = set(kw_lower.split())
                    if negative_words.issubset(kw_words):
                        blocked += 1

        return blocked

    def run_full_simulation(
        self,
        keyword_changes: Optional[List[KeywordChange]] = None,
        negative_keywords: Optional[List[NegativeKeyword]] = None,
        bid_adjustments: Optional[List[BidAdjustment]] = None,
        campaign_changes: Optional[List[CampaignChange]] = None,
    ) -> Tuple[bool, Dict[str, List[str]]]:
        """
        Run full import simulation for all file types.

        Args:
            keyword_changes: Optional list of keyword changes
            negative_keywords: Optional list of negative keywords
            bid_adjustments: Optional list of bid adjustments
            campaign_changes: Optional list of campaign changes

        Returns:
            Tuple of (all_success, dict_of_issues_by_type)
        """
        all_issues = {}
        all_success = True

        if keyword_changes:
            success, issues = self.simulate_keyword_import(keyword_changes)
            if not success:
                all_success = False
                all_issues["keyword_changes"] = issues

        if negative_keywords:
            # Pass existing keywords for conflict checking
            existing = (
                self._build_keyword_dict(keyword_changes) if keyword_changes else None
            )
            success, issues = self.simulate_negative_import(negative_keywords, existing)
            if not success:
                all_success = False
                all_issues["negative_keywords"] = issues

        if bid_adjustments:
            success, issues = self.simulate_bid_adjustment_import(bid_adjustments)
            if not success:
                all_success = False
                all_issues["bid_adjustments"] = issues

        if campaign_changes:
            success, issues = self.simulate_campaign_import(campaign_changes)
            if not success:
                all_success = False
                all_issues["campaign_changes"] = issues

        return all_success, all_issues

    def _build_keyword_dict(
        self, keyword_changes: List[KeywordChange]
    ) -> Dict[str, Dict[str, set]]:
        """Build a dict of keywords by campaign and ad group."""
        keywords = {}
        for change in keyword_changes:
            if change.campaign not in keywords:
                keywords[change.campaign] = {}
            if change.ad_group not in keywords[change.campaign]:
                keywords[change.campaign][change.ad_group] = set()
            keywords[change.campaign][change.ad_group].add(
                (change.keyword.lower(), change.match_type)
            )
        return keywords
