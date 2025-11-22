"""Negative keyword conflict analyzer.

This module analyzes negative keywords that might be blocking positive keywords
in Google Ads campaigns.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Optional, Union

import pandas as pd

from paidsearchnav.core.interfaces import Analyzer
from paidsearchnav.core.models.analysis import (
    AnalysisMetrics,
    AnalysisResult,
    Recommendation,
    RecommendationPriority,
    RecommendationType,
)
from paidsearchnav.core.models.keyword import Keyword, KeywordStatus
from paidsearchnav.utils.csv_parsing import (
    detect_csv_headers,
    normalize_level,
    normalize_match_type,
    process_dataframe_efficiently,
    validate_keyword_text,
)

if TYPE_CHECKING:
    from paidsearchnav.data_providers.base import DataProvider

logger = logging.getLogger(__name__)

# Constants for metric keys
TOTAL_NEGATIVE_KEYWORDS_KEY = "total_negative_keywords"
CONFLICTS_BY_LEVEL_KEY = "conflicts_by_level"
ESTIMATED_IMPRESSIONS_LOST_KEY = "estimated_impressions_lost"

# Performance optimization constants
BATCH_SIZE_FOR_LARGE_ACCOUNTS = (
    1000  # Process keywords in batches for accounts with >10k keywords
)
LARGE_ACCOUNT_THRESHOLD = 10000  # Threshold above which batched processing is used

# Word boundary regex pattern for broad match conflict detection
WORD_BOUNDARY_PATTERN = r"\b\w+\b"


class NegativeConflictAnalyzer(Analyzer):
    """Analyzes negative keywords that block positive keywords."""

    def __init__(self, data_provider: DataProvider = None) -> None:
        """Initialize the analyzer.

        Args:
            data_provider: Provider for fetching Google Ads data (optional for CSV mode)
        """
        self.data_provider = data_provider
        self._csv_negative_keywords = None  # Stores negative keywords loaded from CSV
        self._csv_positive_keywords = (
            None  # Stores positive keywords if provided via CSV
        )

    @classmethod
    def from_csv(
        cls,
        file_path: Union[str, Path],
        max_file_size_mb: int = 100,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> "NegativeConflictAnalyzer":
        """Create a NegativeConflictAnalyzer instance from a CSV file.

        Parses Google Ads negative keyword CSV export and prepares data for analysis.

        Supports two CSV formats:
        1. Standard negative keywords export with columns:
           - Campaign, Campaign ID, Ad group, Ad group ID, Negative keyword, Match type, Level
        2. Google Ads report format with columns:
           - Negative keyword, Keyword or list, Campaign, Ad group, Level, Match type

        Args:
            file_path: Path to the negative keywords CSV file
            max_file_size_mb: Maximum allowed file size in MB (default: 100)
            progress_callback: Optional callback for progress updates

        Returns:
            NegativeConflictAnalyzer instance with loaded negative keyword data

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

        logger.info(f"Loading negative keywords from CSV: {file_path}")

        try:
            # Use improved header detection
            skip_rows = detect_csv_headers(str(file_path))

            if progress_callback:
                progress_callback(f"Loading CSV file: {file_path}")

            # Read CSV with UTF-8-sig to handle BOM
            df = pd.read_csv(file_path, skiprows=skip_rows, encoding="utf-8-sig")

            # Handle empty dataframe
            if df.empty:
                raise ValueError(f"CSV file is empty or contains no data: {file_path}")

            # Normalize column names (handle different formats)
            df.columns = df.columns.str.strip()

            # Parse negative keywords based on format
            negative_keywords = cls._parse_csv_negative_keywords(df, progress_callback)

            if not negative_keywords:
                raise ValueError("No valid negative keyword data found in CSV")

            # Create analyzer instance
            analyzer = cls()
            analyzer._csv_negative_keywords = negative_keywords

            logger.info(
                f"Loaded {len(negative_keywords)} negative keywords from CSV: {file_path}"
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
    def _parse_csv_negative_keywords(
        df: pd.DataFrame, progress_callback: Optional[Callable[[str], None]] = None
    ) -> list[dict[str, Any]]:
        """Parse negative keywords from CSV dataframe using efficient processing.

        Args:
            df: Pandas dataframe containing negative keyword data
            progress_callback: Optional callback for progress updates

        Returns:
            List of parsed negative keywords with metadata
        """
        # Detect format based on column names
        columns_lower = [col.lower() for col in df.columns]

        # Format 1: Standard export (Campaign, Ad group, Negative keyword, Match type, Level)
        if "campaign" in columns_lower and "negative keyword" in columns_lower:

            def process_row(row: pd.Series) -> dict[str, Any] | None:
                """Process a single row of negative keyword data."""
                # Get values, handling different column name cases
                negative_text = (
                    row.get("Negative keyword") or row.get("negative keyword") or ""
                )

                # Skip empty rows
                if not negative_text or pd.isna(negative_text):
                    return None

                # Validate keyword text
                negative_text = str(negative_text).strip()
                if not validate_keyword_text(negative_text):
                    return None

                # Get other fields
                match_type = row.get("Match type") or row.get("match type") or None
                level = row.get("Level") or row.get("level") or None
                campaign = row.get("Campaign") or row.get("campaign") or ""
                campaign_id = row.get("Campaign ID") or row.get("campaign id") or ""
                ad_group = row.get("Ad group") or row.get("ad group") or ""
                ad_group_id = row.get("Ad group ID") or row.get("ad group id") or ""

                # Normalize match type and clean text
                cleaned_text, final_match_type = normalize_match_type(
                    negative_text, match_type
                )

                # Normalize level
                final_level = normalize_level(level, ad_group)

                return {
                    "text": cleaned_text,
                    "match_type": final_match_type,
                    "level": final_level,
                    "campaign_id": str(campaign_id)
                    if campaign_id and not pd.isna(campaign_id)
                    else None,
                    "campaign_name": str(campaign)
                    if campaign and not pd.isna(campaign)
                    else None,
                    "ad_group_id": str(ad_group_id)
                    if ad_group_id and not pd.isna(ad_group_id)
                    else None,
                    "ad_group_name": str(ad_group)
                    if ad_group and not pd.isna(ad_group)
                    else None,
                    "shared_set_id": None,
                    "shared_set_name": None,
                }

            # Use efficient processing
            return process_dataframe_efficiently(df, process_row, progress_callback)

        # Format 2: Could be other formats, try to be flexible
        else:
            # Look for any column that might contain negative keywords
            keyword_columns = [
                col
                for col in df.columns
                if any(kw in col.lower() for kw in ["keyword", "negative", "term"])
            ]

            if not keyword_columns:
                return []

            keyword_col = keyword_columns[0]

            # Find match type column if exists
            match_type_col = None
            for col in df.columns:
                if "match" in col.lower() and "type" in col.lower():
                    match_type_col = col
                    break

            def process_flexible_row(row: pd.Series) -> dict[str, Any] | None:
                """Process a row with flexible column detection."""
                negative_text = row.get(keyword_col)
                if not negative_text or pd.isna(negative_text):
                    return None

                negative_text = str(negative_text).strip()
                if not validate_keyword_text(negative_text):
                    return None

                # Get match type if column exists
                match_type = None
                if match_type_col:
                    match_type = row.get(match_type_col)

                # Normalize match type and clean text
                cleaned_text, final_match_type = normalize_match_type(
                    negative_text, match_type
                )

                return {
                    "text": cleaned_text,
                    "match_type": final_match_type,
                    "level": "CAMPAIGN",  # Default level
                    "campaign_id": None,
                    "campaign_name": None,
                    "ad_group_id": None,
                    "ad_group_name": None,
                    "shared_set_id": None,
                    "shared_set_name": None,
                }

            # Use efficient processing
            return process_dataframe_efficiently(
                df, process_flexible_row, progress_callback
            )

    def get_name(self) -> str:
        """Get analyzer name."""
        return "Negative Keyword Conflict Analyzer"

    def get_description(self) -> str:
        """Get analyzer description."""
        return (
            "Detects negative keywords that are blocking positive keywords "
            "in campaigns, leading to reduced reach and missed opportunities."
        )

    async def analyze(
        self,
        customer_id: str,
        start_date: datetime,
        end_date: datetime,
        **kwargs: Any,
    ) -> AnalysisResult:
        """Run negative keyword conflict analysis.

        Args:
            customer_id: Google Ads customer ID
            start_date: Analysis period start
            end_date: Analysis period end
            **kwargs: Additional parameters

        Returns:
            Analysis result with conflicts and recommendations
        """
        # Use CSV data if loaded, otherwise fetch from API
        if self._csv_negative_keywords is not None:
            negative_keywords = self._csv_negative_keywords
            logger.info(
                f"Using {len(negative_keywords)} negative keywords from CSV data"
            )

            # For CSV mode, we need positive keywords to find conflicts
            # They can be provided via kwargs or we fetch from API if available
            if self._csv_positive_keywords is not None:
                positive_keywords = self._csv_positive_keywords
                active_keywords = [
                    kw for kw in positive_keywords if kw.status == KeywordStatus.ENABLED
                ]
            elif self.data_provider:
                positive_keywords = await self.data_provider.get_keywords(customer_id)
                active_keywords = [
                    kw for kw in positive_keywords if kw.status == KeywordStatus.ENABLED
                ]
            else:
                # Without positive keywords, we can't find conflicts
                logger.warning("No positive keywords available for conflict analysis")
                active_keywords = []
        else:
            # Fetch from API
            if not self.data_provider:
                raise ValueError("Data provider is required when not using CSV data")

            # Fetch positive keywords
            positive_keywords = await self.data_provider.get_keywords(customer_id)
            active_keywords = [
                kw for kw in positive_keywords if kw.status == KeywordStatus.ENABLED
            ]

            # Fetch negative keywords including shared sets
            negative_data = await self.data_provider.get_negative_keywords(
                customer_id, include_shared_sets=True
            )

            # Parse negative keywords from the raw data
            negative_keywords = self._parse_negative_keywords(negative_data)

        # Find conflicts
        conflicts = self._find_conflicts(active_keywords, negative_keywords)

        # Generate recommendations
        recommendations = self._generate_recommendations(conflicts)

        # Calculate metrics
        # Calculate estimated monthly revenue loss from conflicts
        estimated_revenue_loss = sum(
            c.get("estimated_impact", {}).get("revenue_loss", 0) for c in conflicts
        )

        metrics = AnalysisMetrics(
            total_keywords_analyzed=len(active_keywords),
            total_campaigns_analyzed=len({kw.campaign_id for kw in active_keywords}),
            issues_found=len(conflicts),
            critical_issues=len([c for c in conflicts if c["severity"] == "CRITICAL"]),
            potential_cost_savings=0.0,  # Conflicts cause lost opportunities, not savings
            custom_metrics={
                TOTAL_NEGATIVE_KEYWORDS_KEY: len(negative_keywords),
                CONFLICTS_BY_LEVEL_KEY: self._count_conflicts_by_level(conflicts),
                ESTIMATED_IMPRESSIONS_LOST_KEY: sum(
                    c.get("estimated_impact", {}).get("impressions_lost", 0)
                    for c in conflicts
                ),
                "revenue_loss": estimated_revenue_loss,  # Monthly revenue loss from conflicts
                "conflicts_by_severity": {
                    "critical": len(
                        [c for c in conflicts if c["severity"] == "CRITICAL"]
                    ),
                    "high": len([c for c in conflicts if c["severity"] == "HIGH"]),
                    "medium": len([c for c in conflicts if c["severity"] == "MEDIUM"]),
                    "low": len([c for c in conflicts if c["severity"] == "LOW"]),
                },
            },
        )

        return AnalysisResult(
            customer_id=customer_id,
            analysis_type="negative_conflicts",
            analyzer_name=self.get_name(),
            start_date=start_date,
            end_date=end_date,
            metrics=metrics,
            recommendations=recommendations,
            raw_data={
                "conflicts": conflicts,
                "summary": {
                    "total_positive_keywords": len(active_keywords),
                    "total_negative_keywords": len(negative_keywords),
                    "total_conflicts": len(conflicts),
                    "critical_conflicts": metrics.critical_issues,
                },
            },
        )

    def _parse_negative_keywords(
        self, negative_data: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Parse negative keywords from API response.

        Args:
            negative_data: Raw negative keyword data from API

        Returns:
            List of parsed negative keywords with metadata
        """
        # Input validation
        if negative_data is None:
            return []

        if not isinstance(negative_data, list):
            return []

        if not negative_data:
            return []

        negative_keywords = []

        for item in negative_data:
            # Skip non-dict items
            if not isinstance(item, dict):
                continue
            # Parse based on the structure returned by the API
            if "campaign_criterion" in item:
                # Campaign-level negative
                criterion = item["campaign_criterion"]
                if criterion.get("negative") and "keyword" in criterion:
                    keyword_info = criterion["keyword"]
                    negative_keywords.append(
                        {
                            "text": keyword_info.get("text", ""),
                            "match_type": keyword_info.get("match_type", "BROAD"),
                            "level": "CAMPAIGN",
                            "campaign_id": item.get("campaign", {}).get("id"),
                            "campaign_name": item.get("campaign", {}).get("name"),
                            "shared_set_id": None,
                            "shared_set_name": None,
                        }
                    )
            elif "ad_group_criterion" in item:
                # Ad group-level negative
                criterion = item["ad_group_criterion"]
                if criterion.get("negative") and "keyword" in criterion:
                    keyword_info = criterion["keyword"]
                    negative_keywords.append(
                        {
                            "text": keyword_info.get("text", ""),
                            "match_type": keyword_info.get("match_type", "BROAD"),
                            "level": "AD_GROUP",
                            "campaign_id": item.get("campaign", {}).get("id"),
                            "campaign_name": item.get("campaign", {}).get("name"),
                            "ad_group_id": item.get("ad_group", {}).get("id"),
                            "ad_group_name": item.get("ad_group", {}).get("name"),
                            "shared_set_id": None,
                            "shared_set_name": None,
                        }
                    )
            elif "shared_criterion" in item:
                # Shared negative list
                criterion = item["shared_criterion"]
                if "keyword" in criterion:
                    keyword_info = criterion["keyword"]
                    negative_keywords.append(
                        {
                            "text": keyword_info.get("text", ""),
                            "match_type": keyword_info.get("match_type", "BROAD"),
                            "level": "SHARED",
                            "campaign_id": None,
                            "campaign_name": None,
                            "shared_set_id": item.get("shared_set", {}).get("id"),
                            "shared_set_name": item.get("shared_set", {}).get("name"),
                        }
                    )

        return negative_keywords

    def _find_conflicts(
        self,
        positive_keywords: list[Keyword],
        negative_keywords: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Find conflicts between positive and negative keywords.

        Args:
            positive_keywords: Active positive keywords
            negative_keywords: All negative keywords

        Returns:
            List of conflicts with details
        """
        # Early returns for performance
        if not positive_keywords or not negative_keywords:
            return []

        conflicts = []

        # For large accounts, consider batch processing
        if len(positive_keywords) > LARGE_ACCOUNT_THRESHOLD:
            return self._find_conflicts_batched(positive_keywords, negative_keywords)

        # Index negative keywords by level for faster lookup
        negative_by_level = self._index_negatives_by_level(negative_keywords)

        for positive_kw in positive_keywords:
            # Check shared negatives first (affect all campaigns)
            for negative_kw in negative_by_level["SHARED"]:
                if self._is_conflict(positive_kw, negative_kw):
                    conflict = self._create_conflict_record(positive_kw, negative_kw)
                    conflicts.append(conflict)

            # Check campaign-level negatives
            for negative_kw in negative_by_level["CAMPAIGN"]:
                if self._is_conflict(positive_kw, negative_kw):
                    conflict = self._create_conflict_record(positive_kw, negative_kw)
                    conflicts.append(conflict)

            # Check ad group-level negatives
            for negative_kw in negative_by_level["AD_GROUP"]:
                if self._is_conflict(positive_kw, negative_kw):
                    conflict = self._create_conflict_record(positive_kw, negative_kw)
                    conflicts.append(conflict)

        return conflicts

    def _is_conflict(self, positive_kw: Keyword, negative_kw: dict[str, Any]) -> bool:
        """Check if a negative keyword blocks a positive keyword.

        Args:
            positive_kw: Positive keyword
            negative_kw: Negative keyword data

        Returns:
            True if there's a conflict
        """
        # Validate required fields - return False if missing or invalid
        if not isinstance(negative_kw, dict):
            return False

        negative_text = negative_kw.get("text")
        negative_match_type = negative_kw.get("match_type")
        negative_level = negative_kw.get("level")

        # Return False if required fields are missing or None
        if not negative_text or not negative_match_type or not negative_level:
            return False

        # Return False if text is not a string
        if not isinstance(negative_text, str):
            return False

        # Skip if same campaign/ad group (negatives at lower levels don't affect same level)
        if negative_level == "AD_GROUP":
            ad_group_id = negative_kw.get("ad_group_id")
            if ad_group_id == positive_kw.ad_group_id:
                return False
        elif negative_level == "CAMPAIGN":
            # Campaign-level negatives affect all ad groups in the campaign
            campaign_id = negative_kw.get("campaign_id")
            if campaign_id != positive_kw.campaign_id:
                return False

        # Check match type rules
        # Note: Matching is case-insensitive following Google Ads behavior
        positive_text = positive_kw.text.lower()
        negative_text_lower = negative_text.lower()

        # Empty negative keywords should not block anything
        if not negative_text_lower.strip():
            return False

        if negative_match_type == "EXACT":
            # Exact match negative only blocks exact match
            return positive_text == negative_text_lower
        elif negative_match_type == "PHRASE":
            # Phrase match negative blocks if negative phrase is in positive
            return negative_text_lower in positive_text
        else:  # BROAD or other match types default to broad behavior
            # Broad match negative blocks if all words are present
            # Use regex for better word extraction to handle punctuation and boundaries
            negative_words = set(re.findall(WORD_BOUNDARY_PATTERN, negative_text_lower))
            positive_words = set(re.findall(WORD_BOUNDARY_PATTERN, positive_text))
            return negative_words.issubset(positive_words) and len(negative_words) > 0

    def _create_conflict_record(
        self, positive_kw: Keyword, negative_kw: dict[str, Any]
    ) -> dict[str, Any]:
        """Create a detailed conflict record.

        Args:
            positive_kw: Blocked positive keyword
            negative_kw: Blocking negative keyword

        Returns:
            Conflict record with all details
        """
        # Determine severity based on keyword performance
        severity = self._calculate_severity(positive_kw)

        # Estimate impact
        estimated_impact = {
            "impressions_lost": positive_kw.impressions,
            "clicks_lost": positive_kw.clicks,
            "conversions_lost": positive_kw.conversions,
            "revenue_lost": positive_kw.conversion_value,
        }

        return {
            "positive_keyword": {
                "id": positive_kw.keyword_id,
                "text": positive_kw.text,
                "match_type": positive_kw.match_type.value
                if isinstance(positive_kw.match_type, Enum)
                else positive_kw.match_type,
                "campaign_id": positive_kw.campaign_id,
                "campaign_name": positive_kw.campaign_name,
                "ad_group_id": positive_kw.ad_group_id,
                "ad_group_name": positive_kw.ad_group_name,
                "quality_score": positive_kw.quality_score,
                "impressions": positive_kw.impressions,
                "conversions": positive_kw.conversions,
                "conversion_value": positive_kw.conversion_value,
            },
            "negative_keyword": negative_kw,
            "severity": severity,
            "estimated_impact": estimated_impact,
            "resolution_options": self._get_resolution_options(
                positive_kw, negative_kw
            ),
        }

    def _calculate_severity(self, keyword: Keyword) -> str:
        """Calculate conflict severity based on keyword performance.

        Args:
            keyword: The blocked keyword

        Returns:
            Severity level (CRITICAL, HIGH, MEDIUM, LOW)
        """
        # Critical if high conversions or high quality score
        if keyword.conversions > 10 or (
            keyword.quality_score and keyword.quality_score >= 8
        ):
            return "CRITICAL"
        # High if moderate conversions or decent performance
        elif keyword.conversions > 5 or keyword.clicks > 100:
            return "HIGH"
        # Medium if some activity
        elif keyword.clicks > 10:
            return "MEDIUM"
        # Low otherwise
        else:
            return "LOW"

    def _get_resolution_options(
        self, positive_kw: Keyword, negative_kw: dict[str, Any]
    ) -> list[str]:
        """Get resolution options for a conflict.

        Args:
            positive_kw: Blocked positive keyword
            negative_kw: Blocking negative keyword

        Returns:
            List of resolution suggestions
        """
        options = []

        # Option 1: Remove the negative keyword
        options.append(f"Remove negative keyword '{negative_kw['text']}'")

        # Option 2: Change negative to more restrictive match type
        if negative_kw["match_type"] == "BROAD":
            options.append(
                f"Change negative keyword '{negative_kw['text']}' to phrase or exact match"
            )
        elif negative_kw["match_type"] == "PHRASE":
            options.append(
                f"Change negative keyword '{negative_kw['text']}' to exact match"
            )

        # Option 3: Add positive as exception at appropriate level
        if negative_kw["level"] == "SHARED":
            options.append(
                f"Add '{positive_kw.text}' as campaign-level positive to override shared negative"
            )

        return options

    def _generate_recommendations(
        self, conflicts: list[dict[str, Any]]
    ) -> list[Recommendation]:
        """Generate recommendations from conflicts.

        Args:
            conflicts: List of conflicts found

        Returns:
            List of recommendations
        """
        recommendations = []

        # Group conflicts by severity
        critical_conflicts = [c for c in conflicts if c["severity"] == "CRITICAL"]
        high_conflicts = [c for c in conflicts if c["severity"] == "HIGH"]

        # Generate recommendations for critical conflicts
        for conflict in critical_conflicts[:10]:  # Top 10 critical
            positive = conflict["positive_keyword"]
            negative = conflict["negative_keyword"]

            recommendations.append(
                Recommendation(
                    type=RecommendationType.FIX_CONFLICT,
                    priority=RecommendationPriority.CRITICAL,
                    title=f"Critical: Negative '{negative['text']}' blocking high-value keyword",
                    description=(
                        f"The negative keyword '{negative['text']}' ({negative['match_type']}) "
                        f"is blocking the positive keyword '{positive['text']}' which has "
                        f"{positive['conversions']:.1f} conversions. "
                        f"Estimated revenue loss: ${positive['conversion_value']:.2f}"
                    ),
                    campaign_id=positive["campaign_id"],
                    ad_group_id=positive["ad_group_id"],
                    keyword_id=positive["id"],
                    estimated_impact=f"{positive['conversions']:.1f} conversions",
                    estimated_cost_savings=-positive[
                        "conversion_value"
                    ],  # Negative = lost revenue
                    estimated_conversion_increase=None,
                    action_data={
                        "negative_keyword": negative,
                        "resolution_options": conflict["resolution_options"],
                    },
                )
            )

        # Add summary recommendation if many conflicts
        if len(conflicts) > 20:
            recommendations.append(
                Recommendation(
                    type=RecommendationType.RESOLVE_CONFLICTS,
                    priority=RecommendationPriority.HIGH,
                    title="Review negative keyword strategy",
                    description=(
                        f"Found {len(conflicts)} negative keyword conflicts across your account. "
                        f"{len(critical_conflicts)} are critical and blocking high-value keywords. "
                        "Consider implementing a more targeted negative keyword strategy."
                    ),
                    campaign_id=None,
                    ad_group_id=None,
                    keyword_id=None,
                    estimated_impact=f"{len(conflicts)} conflicts resolved",
                    estimated_cost_savings=None,
                    estimated_conversion_increase=None,
                    action_data={
                        "total_conflicts": len(conflicts),
                        "by_severity": {
                            "critical": len(critical_conflicts),
                            "high": len(high_conflicts),
                            "medium": len(
                                [c for c in conflicts if c["severity"] == "MEDIUM"]
                            ),
                            "low": len(
                                [c for c in conflicts if c["severity"] == "LOW"]
                            ),
                        },
                    },
                )
            )

        return recommendations

    def _count_conflicts_by_level(
        self, conflicts: list[dict[str, Any]]
    ) -> dict[str, int]:
        """Count conflicts by negative keyword level.

        Args:
            conflicts: List of conflicts

        Returns:
            Count by level (SHARED, CAMPAIGN, AD_GROUP)
        """
        counts = {"SHARED": 0, "CAMPAIGN": 0, "AD_GROUP": 0}

        for conflict in conflicts:
            level = conflict["negative_keyword"]["level"]
            counts[level] = counts.get(level, 0) + 1

        return counts

    def _index_negatives_by_level(
        self, negative_keywords: list[dict[str, Any]]
    ) -> dict[str, list[dict[str, Any]]]:
        """Index negative keywords by level for faster lookup.

        Args:
            negative_keywords: List of negative keywords

        Returns:
            Dictionary indexed by level (SHARED, CAMPAIGN, AD_GROUP)
        """
        index = {"SHARED": [], "CAMPAIGN": [], "AD_GROUP": []}

        for neg in negative_keywords:
            level = neg.get("level", "CAMPAIGN")
            if level in index:
                index[level].append(neg)

        return index

    def _find_conflicts_batched(
        self,
        positive_keywords: list[Keyword],
        negative_keywords: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Find conflicts using batch processing for large accounts.

        Args:
            positive_keywords: Active positive keywords
            negative_keywords: All negative keywords

        Returns:
            List of conflicts with details
        """
        conflicts = []

        # Index negative keywords by level for faster lookup
        negative_by_level = self._index_negatives_by_level(negative_keywords)

        # Process in batches to avoid memory issues
        for i in range(0, len(positive_keywords), BATCH_SIZE_FOR_LARGE_ACCOUNTS):
            batch = positive_keywords[i : i + BATCH_SIZE_FOR_LARGE_ACCOUNTS]

            for positive_kw in batch:
                # Check shared negatives first (affect all campaigns)
                for negative_kw in negative_by_level["SHARED"]:
                    if self._is_conflict(positive_kw, negative_kw):
                        conflict = self._create_conflict_record(
                            positive_kw, negative_kw
                        )
                        conflicts.append(conflict)

                # Check campaign-level negatives
                for negative_kw in negative_by_level["CAMPAIGN"]:
                    if self._is_conflict(positive_kw, negative_kw):
                        conflict = self._create_conflict_record(
                            positive_kw, negative_kw
                        )
                        conflicts.append(conflict)

                # Check ad group-level negatives
                for negative_kw in negative_by_level["AD_GROUP"]:
                    if self._is_conflict(positive_kw, negative_kw):
                        conflict = self._create_conflict_record(
                            positive_kw, negative_kw
                        )
                        conflicts.append(conflict)

        return conflicts
