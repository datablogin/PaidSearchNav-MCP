"""Shared negative list validator analyzer.

This module validates that campaigns are using shared negative keyword lists
consistently and identifies potential conflicts with campaign goals.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Union

import pandas as pd

from paidsearchnav.core.interfaces import Analyzer
from paidsearchnav.core.models.analysis import (
    AnalysisMetrics,
    AnalysisResult,
    Recommendation,
    RecommendationPriority,
    RecommendationType,
)
from paidsearchnav.core.models.campaign import Campaign, CampaignStatus, CampaignType

if TYPE_CHECKING:
    from paidsearchnav.data_providers.base import DataProvider

logger = logging.getLogger(__name__)


class SharedNegativeValidatorAnalyzer(Analyzer):
    """Validates shared negative keyword list usage across campaigns."""

    def __init__(
        self,
        data_provider: DataProvider = None,
        min_impressions: int = 1000,
        conflict_threshold: float = 0.1,
        max_conflicts_per_campaign: int = 10,
        keywords_page_size: int = 1000,
        wasted_spend_percentage: float = 0.05,
        avg_conversion_value: float = 50.0,
        impressions_risk_percentage: float = 0.1,
        conflict_recovery_estimate: float = 0.1,
        high_priority_cost_threshold: float = 10000.0,
    ) -> None:
        """Initialize the analyzer.

        Args:
            data_provider: Provider for fetching Google Ads data (optional for CSV mode)
            min_impressions: Minimum impressions for campaign relevance
            conflict_threshold: Percentage threshold for conflict detection
            max_conflicts_per_campaign: Maximum number of conflicts to show per campaign
            keywords_page_size: Page size for fetching keywords (for large campaigns)
            wasted_spend_percentage: Estimated percentage of spend at risk without negatives (default: 0.05)
            avg_conversion_value: Estimated average value per conversion in USD (default: 50.0)
            impressions_risk_percentage: Estimated percentage of impressions potentially wasted (default: 0.1)
            conflict_recovery_estimate: Estimated percentage of lost conversions recoverable (default: 0.1)
            high_priority_cost_threshold: Cost threshold for high priority campaigns in USD (default: 10000.0)
        """
        self.data_provider = data_provider
        self._csv_shared_lists = None  # Stores shared negative lists loaded from CSV
        self._csv_campaigns = None  # Stores campaign data if provided via CSV
        self.min_impressions = min_impressions
        self.conflict_threshold = conflict_threshold
        self.max_conflicts_per_campaign = max_conflicts_per_campaign
        self.keywords_page_size = keywords_page_size
        self.wasted_spend_percentage = wasted_spend_percentage
        self.avg_conversion_value = avg_conversion_value
        self.impressions_risk_percentage = impressions_risk_percentage
        self.conflict_recovery_estimate = conflict_recovery_estimate
        self.high_priority_cost_threshold = high_priority_cost_threshold

        # Validate parameters
        self._validate_parameters()

    def _validate_parameters(self) -> None:
        """Validate configuration parameters."""
        # Validate percentage parameters are between 0 and 1
        if not 0 <= self.wasted_spend_percentage <= 1:
            raise ValueError(
                f"wasted_spend_percentage must be between 0 and 1, got {self.wasted_spend_percentage}"
            )
        if not 0 <= self.impressions_risk_percentage <= 1:
            raise ValueError(
                f"impressions_risk_percentage must be between 0 and 1, got {self.impressions_risk_percentage}"
            )
        if not 0 <= self.conflict_recovery_estimate <= 1:
            raise ValueError(
                f"conflict_recovery_estimate must be between 0 and 1, got {self.conflict_recovery_estimate}"
            )
        if not 0 <= self.conflict_threshold <= 1:
            raise ValueError(
                f"conflict_threshold must be between 0 and 1, got {self.conflict_threshold}"
            )

        # Validate positive values
        if self.avg_conversion_value <= 0:
            raise ValueError(
                f"avg_conversion_value must be positive, got {self.avg_conversion_value}"
            )
        if self.high_priority_cost_threshold <= 0:
            raise ValueError(
                f"high_priority_cost_threshold must be positive, got {self.high_priority_cost_threshold}"
            )
        if self.min_impressions < 0:
            raise ValueError(
                f"min_impressions must be non-negative, got {self.min_impressions}"
            )
        if self.max_conflicts_per_campaign <= 0:
            raise ValueError(
                f"max_conflicts_per_campaign must be positive, got {self.max_conflicts_per_campaign}"
            )
        if self.keywords_page_size <= 0:
            raise ValueError(
                f"keywords_page_size must be positive, got {self.keywords_page_size}"
            )

    @classmethod
    def from_csv(
        cls, file_path: Union[str, Path], max_file_size_mb: int = 100
    ) -> "SharedNegativeValidatorAnalyzer":
        """Create a SharedNegativeValidatorAnalyzer instance from a CSV file.

        Parses Google Ads shared negative lists CSV export and prepares data for analysis.

        Supports CSV format with columns:
        - Negative keyword list: Name of the shared negative list
        - Negative keyword: The negative keyword text
        - Match type: EXACT, PHRASE, or BROAD
        - Status: Enabled/Paused

        Args:
            file_path: Path to the shared negative lists CSV file
            max_file_size_mb: Maximum allowed file size in MB (default: 100)

        Returns:
            SharedNegativeValidatorAnalyzer instance with loaded shared lists data

        Raises:
            FileNotFoundError: If the file does not exist
            ValueError: If file is too large, empty, or has invalid format
            PermissionError: If file cannot be read due to permissions
        """
        file_path = Path(file_path)

        # Validate file exists
        if not file_path.exists():
            raise FileNotFoundError(f"CSV file not found: {file_path}")

        # Check file size
        file_size_mb = file_path.stat().st_size / (1024 * 1024)
        if file_size_mb > max_file_size_mb:
            raise ValueError(
                f"File size ({file_size_mb:.1f}MB) exceeds maximum allowed size ({max_file_size_mb}MB)"
            )

        logger.info(f"Loading shared negative lists from CSV: {file_path}")

        try:
            # Determine number of rows to skip by checking for header patterns
            skip_rows = 0
            with open(file_path, "r", encoding="utf-8") as f:
                for i, line in enumerate(f):
                    if i >= 20:  # Limit search to first 20 lines
                        break
                    # Look for header row patterns
                    if "Negative keyword list" in line or "Negative keyword" in line:
                        skip_rows = i
                        break
                    # Skip report header rows
                    if any(
                        pattern in line
                        for pattern in ["report", "All time", "Date range", "#"]
                    ):
                        continue

            # Read CSV
            df = pd.read_csv(file_path, skiprows=skip_rows, encoding="utf-8")

            # Handle empty dataframe
            if df.empty:
                raise ValueError(f"CSV file is empty or contains no data: {file_path}")

            # Normalize column names
            df.columns = df.columns.str.strip()

            # Parse shared lists based on format
            shared_lists = cls._parse_csv_shared_lists(df)

            if not shared_lists:
                raise ValueError("No valid shared negative list data found in CSV")

            # Create analyzer instance
            analyzer = cls()
            analyzer._csv_shared_lists = shared_lists

            logger.info(
                f"Loaded {len(shared_lists)} shared negative lists from CSV: {file_path}"
            )

            return analyzer

        except pd.errors.EmptyDataError as e:
            raise ValueError(f"CSV file is empty: {file_path}") from e
        except pd.errors.ParserError as e:
            raise ValueError(f"CSV parsing error in {file_path}: {str(e)}") from e
        except UnicodeDecodeError as e:
            raise ValueError(
                f"Encoding error reading {file_path}. Expected UTF-8 encoding: {str(e)}"
            ) from e
        except MemoryError as e:
            raise ValueError(f"File too large to process in memory: {file_path}") from e
        except Exception as e:
            if isinstance(e, (ValueError, FileNotFoundError, PermissionError)):
                raise
            raise ValueError(
                f"Unexpected error parsing CSV file {file_path}: {type(e).__name__}: {str(e)}"
            ) from e

    @staticmethod
    def _parse_csv_shared_lists(df: pd.DataFrame) -> list[dict[str, Any]]:
        """Parse shared negative lists from CSV dataframe.

        Args:
            df: Pandas dataframe containing shared negative list data

        Returns:
            List of shared lists with their negative keywords
        """
        shared_lists_dict = {}

        # Look for relevant columns
        list_col = None
        keyword_col = None
        match_type_col = None
        status_col = None

        for col in df.columns:
            col_lower = col.lower()
            if "list" in col_lower and list_col is None:
                list_col = col
            elif "negative keyword" in col_lower and keyword_col is None:
                keyword_col = col
            elif (
                "match" in col_lower and "type" in col_lower and match_type_col is None
            ):
                match_type_col = col
            elif "status" in col_lower and status_col is None:
                status_col = col

        # Validate we have required columns
        if not keyword_col:
            raise ValueError("CSV missing required 'Negative keyword' column")

        # Process rows
        for _, row in df.iterrows():
            keyword = row.get(keyword_col)
            if not keyword or pd.isna(keyword):
                continue

            keyword = str(keyword).strip()

            # Get list name (if not present, use "Default List")
            list_name = "Default List"
            if list_col:
                ln = row.get(list_col)
                if ln and not pd.isna(ln):
                    list_name = str(ln).strip()

            # Get match type
            match_type = "BROAD"  # Default
            if match_type_col:
                mt = row.get(match_type_col)
                if mt and not pd.isna(mt):
                    match_type_upper = str(mt).upper()
                    if "EXACT" in match_type_upper:
                        match_type = "EXACT"
                    elif "PHRASE" in match_type_upper:
                        match_type = "PHRASE"
                    elif "BROAD" in match_type_upper:
                        match_type = "BROAD"

            # Handle match type indicators in keyword text
            if keyword.startswith("[") and keyword.endswith("]"):
                keyword = keyword[1:-1]
                match_type = "EXACT"
            elif keyword.startswith('"') and keyword.endswith('"'):
                keyword = keyword[1:-1]
                match_type = "PHRASE"
            elif keyword.startswith("'\"") and keyword.endswith("\"'"):
                # Handle nested quotes from CSV: '"phrase keyword"'
                keyword = keyword[2:-2]
                match_type = "PHRASE"

            # Get status
            status = "ENABLED"  # Default
            if status_col:
                st = row.get(status_col)
                if st and not pd.isna(st):
                    status_upper = str(st).upper()
                    if "PAUSE" in status_upper or "DISABLED" in status_upper:
                        status = "PAUSED"
                    else:
                        status = "ENABLED"

            # Add to shared lists dictionary
            if list_name not in shared_lists_dict:
                shared_lists_dict[list_name] = {
                    "id": f"list_{len(shared_lists_dict) + 1}",
                    "name": list_name,
                    "negative_keywords": [],
                    "status": status,
                }

            shared_lists_dict[list_name]["negative_keywords"].append(
                {
                    "text": keyword,
                    "match_type": match_type,
                }
            )

        # Convert to list format
        shared_lists = list(shared_lists_dict.values())

        return shared_lists

    def get_name(self) -> str:
        """Get analyzer name."""
        return "Shared Negative List Validator"

    def get_description(self) -> str:
        """Get analyzer description."""
        return (
            "Validates that campaigns are using shared negative keyword lists "
            "consistently and identifies campaigns missing shared lists or with "
            "conflicting negative keywords."
        )

    async def analyze(
        self,
        customer_id: str,
        start_date: datetime,
        end_date: datetime,
        **kwargs: Any,
    ) -> AnalysisResult:
        """Run shared negative list validation analysis.

        Args:
            customer_id: Google Ads customer ID
            start_date: Analysis period start
            end_date: Analysis period end
            **kwargs: Additional parameters including:
                - target_campaigns: Optional list of campaign IDs to analyze
                - check_conflicts: Whether to check for conflicts (default True)
                - auto_apply_suggestions: Generate auto-apply recommendations

        Returns:
            Analysis result with validation findings and recommendations
        """
        logger.info(
            f"Starting shared negative list validation for customer {customer_id}"
        )

        # Extract optional parameters
        target_campaigns = kwargs.get("target_campaigns", [])
        check_conflicts = kwargs.get("check_conflicts", True)
        auto_apply_suggestions = kwargs.get("auto_apply_suggestions", False)

        # Use CSV data if loaded, otherwise fetch from API
        if self._csv_shared_lists is not None:
            shared_lists = self._csv_shared_lists
            logger.info(
                f"Using {len(shared_lists)} shared negative lists from CSV data"
            )

            # For CSV mode, we need campaign data to validate usage
            if self._csv_campaigns is not None:
                campaigns = self._csv_campaigns
            elif self.data_provider:
                campaigns = await self.data_provider.get_campaigns(
                    customer_id,
                    start_date=start_date,
                    end_date=end_date,
                )
            else:
                # Without campaigns, we can only report on the shared lists themselves
                logger.warning("No campaign data available for validation analysis")
                campaigns = []
        else:
            # Fetch from API
            if not self.data_provider:
                raise ValueError("Data provider is required when not using CSV data")

            # Fetch campaigns with performance data
            campaigns = await self.data_provider.get_campaigns(
                customer_id,
                start_date=start_date,
                end_date=end_date,
            )

            # Fetch shared negative lists
            shared_lists = await self.data_provider.get_shared_negative_lists(
                customer_id
            )

        # Filter active campaigns with sufficient impressions
        relevant_campaigns = self._filter_relevant_campaigns(
            campaigns, target_campaigns
        )

        logger.info(f"Analyzing {len(relevant_campaigns)} relevant campaigns")

        # Map campaigns to their applied shared lists
        campaign_shared_lists = await self._get_campaign_shared_lists(
            customer_id, relevant_campaigns
        )

        # Identify campaigns missing shared lists
        missing_shared_lists = self._identify_missing_shared_lists(
            relevant_campaigns, campaign_shared_lists, shared_lists
        )

        # Check for conflicts if requested (only if we have a data provider)
        conflicts = []
        if check_conflicts and shared_lists and self.data_provider:
            conflicts = await self._check_for_conflicts(
                customer_id, relevant_campaigns, shared_lists
            )

        # Analyze shared list coverage
        coverage_stats = self._calculate_coverage_stats(
            relevant_campaigns, campaign_shared_lists, shared_lists
        )

        # Generate recommendations
        recommendations = self._generate_recommendations(
            missing_shared_lists,
            conflicts,
            coverage_stats,
            auto_apply_suggestions,
        )

        # Calculate metrics
        metrics = AnalysisMetrics(
            total_keywords_analyzed=0,  # Not analyzing keywords directly
            total_campaigns_analyzed=len(relevant_campaigns),
            issues_found=len(missing_shared_lists) + len(conflicts),
            critical_issues=len(
                [c for c in missing_shared_lists if c["priority"] == "high"]
            ),
            potential_cost_savings=self._estimate_savings(
                missing_shared_lists, conflicts
            ),
            custom_metrics={
                "total_shared_lists": len(shared_lists),
                "campaigns_missing_lists": len(missing_shared_lists),
                "campaigns_with_conflicts": len(conflicts),
                "shared_list_coverage": coverage_stats.get("coverage_percentage", 0.0),
                "most_used_list": coverage_stats.get("most_used_list", "None"),
                "campaigns_by_type": self._count_campaigns_by_type(relevant_campaigns),
            },
        )

        # Create summary
        summary = {
            "validation_status": self._get_validation_status(
                missing_shared_lists, conflicts
            ),
            "campaigns_analyzed": len(relevant_campaigns),
            "shared_lists_found": len(shared_lists),
            "missing_list_campaigns": missing_shared_lists,
            "conflict_campaigns": conflicts,
            "coverage_stats": coverage_stats,
            "recommendations_count": len(recommendations),
        }

        return AnalysisResult(
            customer_id=customer_id,
            analysis_type="shared_negative_validation",
            analyzer_name=self.get_name(),
            start_date=start_date,
            end_date=end_date,
            metrics=metrics,
            recommendations=recommendations,
            raw_data=summary,
        )

    def _filter_relevant_campaigns(
        self, campaigns: list[Campaign], target_campaigns: list[str]
    ) -> list[Campaign]:
        """Filter campaigns to analyze based on criteria."""
        filtered = []
        for campaign in campaigns:
            # Skip if not in target campaigns (if specified)
            if target_campaigns and campaign.campaign_id not in target_campaigns:
                continue

            # Skip paused/removed campaigns
            if campaign.status not in (CampaignStatus.ENABLED, CampaignStatus.PAUSED):
                continue

            # Skip campaigns with low impressions
            if campaign.impressions < self.min_impressions:
                continue

            # Include all campaign types but prioritize Search, PMax, and Local
            filtered.append(campaign)

        return filtered

    async def _get_campaign_shared_lists(
        self, customer_id: str, campaigns: list[Campaign]
    ) -> dict[str, list[dict[str, Any]]]:
        """Get shared negative lists applied to each campaign."""
        campaign_lists = {}

        for campaign in campaigns:
            lists = await self.data_provider.get_campaign_shared_sets(
                customer_id, campaign.campaign_id
            )
            campaign_lists[campaign.campaign_id] = lists

        return campaign_lists

    def _identify_missing_shared_lists(
        self,
        campaigns: list[Campaign],
        campaign_shared_lists: dict[str, list[dict[str, Any]]],
        shared_lists: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Identify campaigns missing shared negative lists."""
        missing = []

        # Determine which lists should be applied based on campaign type
        for campaign in campaigns:
            applied_lists = campaign_shared_lists.get(campaign.campaign_id, [])
            applied_list_ids = {lst["id"] for lst in applied_lists}

            # Determine expected lists based on campaign type
            expected_lists = self._get_expected_lists(campaign, shared_lists)
            missing_list_ids = expected_lists - applied_list_ids

            if missing_list_ids:
                missing_lists = [
                    lst for lst in shared_lists if lst["id"] in missing_list_ids
                ]

                missing.append(
                    {
                        "campaign_id": campaign.campaign_id,
                        "campaign_name": campaign.name,
                        "campaign_type": campaign.type,
                        "campaign_impressions": campaign.impressions,
                        "campaign_cost": campaign.cost,
                        "missing_lists": missing_lists,
                        "priority": self._get_priority(campaign),
                        "estimated_impact": {
                            "wasted_spend_risk": campaign.cost
                            * self.wasted_spend_percentage,
                            "impressions_at_risk": campaign.impressions
                            * self.impressions_risk_percentage,
                        },
                    }
                )

        return sorted(missing, key=lambda x: x["campaign_cost"], reverse=True)

    def _get_expected_lists(
        self, campaign: Campaign, shared_lists: list[dict[str, Any]]
    ) -> set[str]:
        """Determine which shared lists should be applied to a campaign."""
        expected = set()

        for shared_list in shared_lists:
            list_name_lower = shared_list["name"].lower()

            # All campaigns should have general brand/competitor lists
            if any(
                term in list_name_lower
                for term in ["brand", "competitor", "general", "global"]
            ):
                expected.add(shared_list["id"])

            # Search and Shopping campaigns need product-specific lists
            elif campaign.type in (CampaignType.SEARCH, CampaignType.SHOPPING):
                if any(
                    term in list_name_lower
                    for term in ["product", "search", "shopping"]
                ):
                    expected.add(shared_list["id"])

            # Performance Max needs PMax-specific lists
            elif campaign.type == CampaignType.PERFORMANCE_MAX:
                if "pmax" in list_name_lower or "performance" in list_name_lower:
                    expected.add(shared_list["id"])

            # Local campaigns need location-specific lists
            elif campaign.type == CampaignType.LOCAL:
                if "local" in list_name_lower or "location" in list_name_lower:
                    expected.add(shared_list["id"])

        return expected

    def _get_priority(self, campaign: Campaign) -> str:
        """Determine priority based on campaign performance and type."""
        # High priority for high-spend campaigns
        if campaign.cost > self.high_priority_cost_threshold:
            return "high"

        # High priority for PMax and Local campaigns (newer, more automated)
        if campaign.type in (CampaignType.PERFORMANCE_MAX, CampaignType.LOCAL):
            return "high"

        # Medium priority for Search campaigns
        if campaign.type == CampaignType.SEARCH:
            return "medium"

        return "low"

    async def _check_for_conflicts(
        self,
        customer_id: str,
        campaigns: list[Campaign],
        shared_lists: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Check for conflicts between campaign keywords and shared negatives."""
        # Fetch all shared negatives in parallel
        all_shared_negatives = await self._fetch_all_shared_negatives(
            customer_id, shared_lists
        )

        # Check conflicts for each campaign
        conflicts = []
        for campaign in campaigns:
            if not self._should_check_campaign_conflicts(campaign):
                continue

            campaign_conflicts = await self._check_campaign_conflicts(
                customer_id, campaign, all_shared_negatives
            )

            if campaign_conflicts:
                conflict_summary = self._create_conflict_summary(
                    campaign, campaign_conflicts
                )
                conflicts.append(conflict_summary)

        return sorted(
            conflicts,
            key=lambda x: x["impact"]["conversions_lost"],
            reverse=True,
        )

    async def _fetch_all_shared_negatives(
        self, customer_id: str, shared_lists: list[dict[str, Any]]
    ) -> set[str]:
        """Fetch all negative keywords from shared lists using batch API calls."""
        all_shared_negatives = set()

        # Create tasks for all shared list negative fetches
        negative_tasks = [
            self.data_provider.get_shared_set_negatives(customer_id, shared_list["id"])
            for shared_list in shared_lists
        ]

        # Execute all tasks in parallel
        if negative_tasks:
            all_negatives_results = await asyncio.gather(*negative_tasks)

            # Process results
            for negatives in all_negatives_results:
                all_shared_negatives.update(neg["text"].lower() for neg in negatives)

        return all_shared_negatives

    def _should_check_campaign_conflicts(self, campaign: Campaign) -> bool:
        """Determine if a campaign should be checked for conflicts."""
        return campaign.type in (
            CampaignType.SEARCH,
            CampaignType.SHOPPING,
            CampaignType.PERFORMANCE_MAX,
        )

    async def _check_campaign_conflicts(
        self, customer_id: str, campaign: Campaign, all_shared_negatives: set[str]
    ) -> list[dict[str, Any]]:
        """Check for conflicts in a single campaign."""
        # Get campaign keywords with pagination support for large campaigns
        # TODO: Verify that data provider handles pagination internally
        # If not, implement pagination loop here to fetch all keywords
        keywords = await self.data_provider.get_keywords(
            customer_id,
            campaigns=[campaign.campaign_id],
            page_size=self.keywords_page_size,
        )

        # Find conflicts
        campaign_conflicts = []
        for keyword in keywords:
            keyword_text_lower = keyword.text.lower()
            for negative in all_shared_negatives:
                if self._is_conflict(keyword_text_lower, negative, keyword.match_type):
                    campaign_conflicts.append(
                        {
                            "keyword": keyword.text,
                            "match_type": str(keyword.match_type),
                            "negative": negative,
                            "impressions_blocked": keyword.impressions,
                            "potential_clicks_lost": keyword.clicks,
                            "potential_conversions_lost": keyword.conversions,
                        }
                    )

        return campaign_conflicts

    def _create_conflict_summary(
        self, campaign: Campaign, campaign_conflicts: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Create a summary of conflicts for a campaign."""
        return {
            "campaign_id": campaign.campaign_id,
            "campaign_name": campaign.name,
            "campaign_type": campaign.type,
            "conflicts": campaign_conflicts[: self.max_conflicts_per_campaign],
            "total_conflicts": len(campaign_conflicts),
            "impact": {
                "impressions_blocked": sum(
                    c["impressions_blocked"] for c in campaign_conflicts
                ),
                "clicks_lost": sum(
                    c["potential_clicks_lost"] for c in campaign_conflicts
                ),
                "conversions_lost": sum(
                    c["potential_conversions_lost"] for c in campaign_conflicts
                ),
            },
        }

    def _is_conflict(self, keyword: str, negative: str, match_type: str) -> bool:
        """Check if a negative keyword conflicts with a positive keyword.

        Handles exact, phrase, and broad match negative keywords according
        to Google Ads matching rules.
        """
        # Exact match negative [keyword]
        if negative.startswith("[") and negative.endswith("]"):
            negative_text = negative[1:-1].lower()
            return keyword.lower() == negative_text

        # Phrase match negative "keyword phrase"
        elif negative.startswith('"') and negative.endswith('"'):
            negative_text = negative[1:-1].lower()
            # Check if the phrase appears in the keyword (respecting word order)
            return negative_text in keyword.lower()

        # Broad match negative
        else:
            # Broad match: all words in negative must appear in keyword
            # The key insight from the test cases:
            # 1. Words are primarily separated by spaces
            # 2. "email@example.com" is ONE word (no spaces around special chars)
            # 3. "hotel & spa" is THREE words: "hotel", "&", "spa"
            # 4. "(limited offer)" with negative "offer)" should match

            keyword_lower = keyword.lower()
            negative_words = negative.lower().split()

            # Split keyword by spaces to get words
            keyword_words = keyword_lower.split()

            # Check if all negative words appear
            for neg_word in negative_words:
                # Direct match as a complete word
                if neg_word in keyword_words:
                    continue

                # If not found as exact match, return False
                # This handles cases like "email@example.com" vs "email"
                # where "email" is not a separate word
                return False

            return True

    def _calculate_coverage_stats(
        self,
        campaigns: list[Campaign],
        campaign_shared_lists: dict[str, list[dict[str, Any]]],
        shared_lists: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Calculate shared list coverage statistics."""
        if not campaigns:
            return {
                "coverage_percentage": 0.0,
                "avg_lists_per_campaign": 0.0,
                "most_used_list": "None",
                "least_used_list": "None",
            }

        # Count campaigns with at least one shared list
        campaigns_with_lists = sum(
            1 for c in campaigns if campaign_shared_lists.get(c.campaign_id)
        )

        # Count usage of each shared list
        list_usage = {lst["id"]: 0 for lst in shared_lists}
        for lists in campaign_shared_lists.values():
            for lst in lists:
                if lst["id"] in list_usage:
                    list_usage[lst["id"]] += 1

        # Find most and least used lists
        if list_usage:
            most_used_id = max(list_usage, key=list_usage.get)
            least_used_id = min(list_usage, key=list_usage.get)
            most_used = next(
                (lst["name"] for lst in shared_lists if lst["id"] == most_used_id),
                "Unknown",
            )
            least_used = next(
                (lst["name"] for lst in shared_lists if lst["id"] == least_used_id),
                "Unknown",
            )
        else:
            most_used = least_used = "None"

        # Calculate average lists per campaign
        total_lists = sum(len(lists) for lists in campaign_shared_lists.values())
        avg_lists = total_lists / len(campaigns) if campaigns else 0

        return {
            "coverage_percentage": (campaigns_with_lists / len(campaigns)) * 100,
            "avg_lists_per_campaign": avg_lists,
            "most_used_list": most_used,
            "least_used_list": least_used,
            "list_usage_counts": {
                lst["name"]: list_usage.get(lst["id"], 0) for lst in shared_lists
            },
        }

    def _generate_recommendations(
        self,
        missing_shared_lists: list[dict[str, Any]],
        conflicts: list[dict[str, Any]],
        coverage_stats: dict[str, Any],
        auto_apply_suggestions: bool,
    ) -> list[Recommendation]:
        """Generate recommendations based on analysis."""
        recommendations = []

        # Recommendations for missing shared lists
        for missing in missing_shared_lists[:5]:  # Top 5 campaigns
            priority = (
                RecommendationPriority.HIGH
                if missing["priority"] == "high"
                else RecommendationPriority.MEDIUM
            )

            list_names = [lst["name"] for lst in missing["missing_lists"]]
            recommendation = Recommendation(
                type=RecommendationType.ADD_NEGATIVE,
                priority=priority,
                title=f"Apply shared negative lists to {missing['campaign_name']}",
                description=(
                    f"Campaign '{missing['campaign_name']}' is missing {len(list_names)} "
                    f"shared negative list(s): {', '.join(list_names)}. "
                    f"Applying these lists could prevent up to "
                    f"${missing['estimated_impact']['wasted_spend_risk']:.2f} in wasted spend."
                ),
                campaign_id=missing["campaign_id"],
                estimated_cost_savings=missing["estimated_impact"]["wasted_spend_risk"],
            )

            if auto_apply_suggestions:
                recommendation.action_data = {
                    "auto_apply": True,
                    "shared_list_ids": [lst["id"] for lst in missing["missing_lists"]],
                }

            recommendations.append(recommendation)

        # Recommendations for conflicts
        for conflict in conflicts[:3]:  # Top 3 conflicts
            recommendations.append(
                Recommendation(
                    type=RecommendationType.FIX_CONFLICT,
                    priority=RecommendationPriority.HIGH,
                    title=f"Resolve negative keyword conflicts in {conflict['campaign_name']}",
                    description=(
                        f"Campaign '{conflict['campaign_name']}' has {conflict['total_conflicts']} "
                        f"keywords blocked by shared negative lists, potentially losing "
                        f"{conflict['impact']['conversions_lost']:.1f} conversions. "
                        f"Review and adjust shared negative lists to allow high-value keywords."
                    ),
                    campaign_id=conflict["campaign_id"],
                    estimated_conversion_increase=(
                        (
                            conflict["impact"]["conversions_lost"]
                            / conflict["impact"].get("current_conversions", 1)
                        )
                        * 100
                        if conflict["impact"].get("current_conversions", 0) > 0
                        else 10.0
                    ),
                )
            )

        # General coverage recommendation if coverage is low
        if coverage_stats["coverage_percentage"] < 80:
            recommendations.append(
                Recommendation(
                    type=RecommendationType.OTHER,
                    priority=RecommendationPriority.MEDIUM,
                    title="Improve shared negative list coverage",
                    description=(
                        f"Only {coverage_stats['coverage_percentage']:.1f}% of campaigns "
                        f"have shared negative lists applied. Implement a standard negative "
                        f"list strategy across all campaigns to prevent wasted spend on "
                        f"irrelevant traffic."
                    ),
                )
            )

        return recommendations

    def _estimate_savings(
        self,
        missing_shared_lists: list[dict[str, Any]],
        conflicts: list[dict[str, Any]],
    ) -> float:
        """Estimate potential cost savings from applying recommendations."""
        # Savings from applying missing lists (prevent wasted spend)
        missing_savings = sum(
            item["estimated_impact"]["wasted_spend_risk"]
            for item in missing_shared_lists
        )

        # No direct savings from conflicts (they cause lost opportunities)
        # But we could estimate value of recovered conversions
        conflict_value = sum(
            c["impact"]["conversions_lost"] * self.avg_conversion_value
            for c in conflicts
        )

        return missing_savings + (conflict_value * self.conflict_recovery_estimate)

    def _get_validation_status(
        self,
        missing_shared_lists: list[dict[str, Any]],
        conflicts: list[dict[str, Any]],
    ) -> str:
        """Determine overall validation status."""
        total_issues = len(missing_shared_lists) + len(conflicts)

        if total_issues == 0:
            return "EXCELLENT"
        elif total_issues <= 5:
            return "GOOD"
        elif total_issues <= 10:
            return "NEEDS_ATTENTION"
        else:
            return "CRITICAL"

    def _count_campaigns_by_type(self, campaigns: list[Campaign]) -> dict[str, int]:
        """Count campaigns by type."""
        counts = {}
        for campaign in campaigns:
            type_name = str(campaign.type)
            counts[type_name] = counts.get(type_name, 0) + 1
        return counts
