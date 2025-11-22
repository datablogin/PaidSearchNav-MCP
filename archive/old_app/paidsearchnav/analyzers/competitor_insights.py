"""Competitor insights analyzer for auction insights analysis."""

import logging
import statistics
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Union

import pandas as pd

from paidsearchnav.core.interfaces import Analyzer
from paidsearchnav.core.models import (
    AnalysisResult,
    Recommendation,
    RecommendationPriority,
    RecommendationType,
)
from paidsearchnav.platforms.google import AuctionInsights
from paidsearchnav.platforms.google.client import GoogleAdsAPIClient

logger = logging.getLogger(__name__)


class CompetitorInsightsResult(AnalysisResult):
    """Result of competitor insights analysis."""

    # Raw auction data
    auction_data: list[AuctionInsights] = []

    # Competitor rankings
    competitor_rankings: list[dict[str, Any]] = []
    aggressive_competitors: list[dict[str, Any]] = []

    # Competitive metrics by campaign
    campaign_competition: dict[str, dict[str, Any]] = {}

    # Position analysis
    position_metrics: dict[str, Any] = {}
    position_loss_analysis: list[dict[str, Any]] = []

    # Keyword theme analysis
    keyword_theme_pressure: dict[str, dict[str, Any]] = {}

    # Strategic insights
    competitive_gaps: list[dict[str, Any]] = []
    opportunity_areas: list[dict[str, Any]] = []

    # Market share analysis
    overall_impression_share: float = 0.0
    avg_competitor_share: float = 0.0
    market_concentration: float = 0.0

    # Time-based tracking
    competitive_trends: dict[str, list[dict[str, Any]]] = {}
    share_changes: dict[str, float] = {}

    # Strategic recommendations
    bid_strategy_recommendations: list[dict[str, Any]] = []
    budget_reallocation_recommendations: list[dict[str, Any]] = []
    keyword_opportunity_recommendations: list[dict[str, Any]] = []


class CompetitorInsightsAnalyzer(Analyzer):
    """Analyzes auction insights data for competitive intelligence."""

    # Threat assessment thresholds
    HIGH_OVERLAP_THRESHOLD = 0.7
    AGGRESSIVE_POSITION_THRESHOLD = 0.6
    LOW_OUTRANKING_THRESHOLD = 0.3

    # Competition pressure thresholds
    HIGH_COMPETITION_OVERLAP = 0.6
    MEDIUM_COMPETITION_OVERLAP = 0.3

    # Analysis limits
    MAX_COMPETITIVE_GAPS = 10
    MIN_CAMPAIGNS_FOR_AGGRESSION = 3

    # Position analysis thresholds
    POSITION_LOSS_THRESHOLD = 0.5
    LOW_MARKET_SHARE_THRESHOLD = 0.3

    def __init__(self, client: Optional[GoogleAdsAPIClient] = None) -> None:
        """Initialize the competitor insights analyzer."""
        self.client = client
        self.logger = logger
        self._result: Optional[CompetitorInsightsResult] = None
        self._csv_data: Optional[list[AuctionInsights]] = None

    @classmethod
    def from_csv(
        cls, file_path: Union[str, Path], max_file_size_mb: int = 100
    ) -> "CompetitorInsightsAnalyzer":
        """
        Create a CompetitorInsightsAnalyzer instance from a CSV file.

        Parses Google Ads Auction Insights CSV report and prepares data for analysis.

        Args:
            file_path: Path to the auction insights CSV file
            max_file_size_mb: Maximum allowed file size in MB (default: 100)

        Returns:
            CompetitorInsightsAnalyzer instance with loaded data

        Raises:
            FileNotFoundError: If the CSV file doesn't exist
            ValueError: If the CSV format is invalid, missing required columns, or file too large
        """
        file_path = Path(file_path) if isinstance(file_path, str) else file_path

        # Resolve to absolute path for security
        file_path = file_path.resolve()

        if not file_path.exists():
            raise FileNotFoundError(f"CSV file not found: {file_path}")

        if not file_path.suffix.lower() == ".csv":
            raise ValueError(f"Expected .csv file, got: {file_path.suffix}")

        # Check file size before reading
        file_size_mb = file_path.stat().st_size / (1024 * 1024)
        if file_size_mb > max_file_size_mb:
            raise ValueError(
                f"CSV file too large ({file_size_mb:.1f} MB > {max_file_size_mb} MB)"
            )

        # Define parse_percentage function outside the loop for performance
        def parse_percentage(value):
            """Parse percentage string to float."""
            if pd.isna(value) or value == "--":
                return None
            if isinstance(value, str) and value.endswith("%"):
                return float(value.rstrip("%")) / 100
            return float(value) if value else None

        try:
            # Read CSV file, skipping the header rows that contain report metadata
            df = pd.read_csv(file_path, skiprows=2)

            # Required columns in the auction insights CSV
            required_columns = ["Display URL domain"]
            if not all(col in df.columns for col in required_columns):
                raise ValueError(
                    f"CSV missing required columns. Found: {list(df.columns)}"
                )

            # Parse the CSV data into AuctionInsights objects
            auction_data = []

            # Process rows - using itertuples with name parameter for performance
            # Note: We access columns by index position due to spaces in column names
            col_names = list(df.columns)

            for row in df.itertuples(index=False, name=None):
                # Create a dictionary mapping column names to values
                row_dict = dict(zip(col_names, row))

                # Skip the row for our own domain (has no competitive metrics)
                overlap_rate = row_dict.get("Overlap rate")
                if pd.isna(overlap_rate) or overlap_rate == "--":
                    continue

                # Get campaign_id and convert properly
                campaign_id_value = row_dict.get("Campaign ID")
                campaign_id = None
                if pd.notna(campaign_id_value):
                    campaign_id = str(campaign_id_value)

                auction_insight = AuctionInsights(
                    competitor_domain=row_dict["Display URL domain"],
                    impression_share=parse_percentage(row_dict.get("Impr. share")),
                    overlap_rate=parse_percentage(overlap_rate),
                    top_of_page_rate=parse_percentage(row_dict.get("Top of page rate")),
                    abs_top_of_page_rate=parse_percentage(
                        row_dict.get("Abs. Top of page rate")
                    ),
                    outranking_share=parse_percentage(row_dict.get("Outranking share")),
                    position_above_rate=parse_percentage(
                        row_dict.get("Position above rate")
                    ),
                    # Campaign information can be added if available in extended CSV format
                    campaign_name=row_dict.get("Campaign")
                    if pd.notna(row_dict.get("Campaign"))
                    else None,
                    campaign_id=campaign_id,
                    date_range=row_dict.get("Date range")
                    if pd.notna(row_dict.get("Date range"))
                    else None,
                )

                auction_data.append(auction_insight)

            if not auction_data:
                raise ValueError("No valid competitor data found in CSV")

            # Create analyzer instance
            analyzer = cls()

            # Store the parsed data for later use in analyze()
            analyzer._csv_data = auction_data

            logger.info(
                f"Loaded {len(auction_data)} competitor records from CSV: {file_path}"
            )

            return analyzer

        except pd.errors.EmptyDataError:
            raise ValueError(f"CSV file is empty: {file_path}")
        except Exception as e:
            raise ValueError(f"Error parsing CSV file: {e}")

    async def analyze(
        self,
        customer_id: str,
        start_date: datetime,
        end_date: datetime,
        **kwargs: Any,
    ) -> CompetitorInsightsResult:
        """
        Analyze auction insights data for competitive intelligence.

        Args:
            customer_id: Google Ads customer ID
            start_date: Analysis period start
            end_date: Analysis period end
            **kwargs: Additional parameters (expects 'data' with list of AuctionInsights)

        Returns:
            CompetitorInsightsResult with competitive analysis
        """
        # Get data from kwargs or use CSV data if loaded
        data: list[AuctionInsights] = kwargs.get("data", [])

        # If no data provided and CSV data was loaded, use that
        if not data and self._csv_data is not None:
            data = self._csv_data

        # Initialize result with required fields
        self._result = CompetitorInsightsResult(
            analyzer_name="CompetitorInsightsAnalyzer",
            customer_id=customer_id,
            analysis_type="competitor_insights",
            start_date=start_date,
            end_date=end_date,
            recommendations=[],
        )

        if not data:
            self.logger.warning("No auction insights data provided")
            return self._result

        # Validate data structure
        valid_records = []
        for record in data:
            if not isinstance(record, AuctionInsights):
                self.logger.warning(f"Invalid record type: {type(record)}")
                continue
            if not record.competitor_domain:
                self.logger.warning("Record missing competitor_domain, skipping")
                continue
            valid_records.append(record)

        if not valid_records:
            self.logger.warning("No valid auction insights records found")
            return self._result

        self._result.auction_data = valid_records
        self.logger.info(
            f"Analyzing {len(valid_records)} valid auction insights records"
        )

        # Perform analysis steps
        # Single-pass data aggregation for better performance
        aggregated_data = self._aggregate_auction_data()
        self._last_aggregated_data = aggregated_data  # Store for use in other methods

        self._analyze_competitor_rankings_optimized(aggregated_data)
        self._analyze_campaign_competition()
        self._analyze_position_metrics_optimized(aggregated_data)
        self._identify_aggressive_competitors()
        self._analyze_keyword_themes()
        self._identify_competitive_gaps()
        self._analyze_competitive_trends()
        self._generate_recommendations()

        self.logger.info(
            f"Analysis complete: {len(self._result.competitor_rankings)} competitors analyzed, "
            f"{len(self._result.recommendations)} recommendations generated"
        )

        return self._result

    def _aggregate_auction_data(self) -> dict[str, Any]:
        """Aggregate auction data in a single pass for performance optimization."""
        aggregated = {
            "competitor_metrics": defaultdict(
                lambda: {
                    "domains": set(),
                    "total_overlap": 0.0,
                    "avg_overlap_rate": 0.0,
                    "avg_position_above": 0.0,
                    "avg_outranking_share": 0.0,
                    "campaigns_affected": set(),
                    "records": [],
                }
            ),
            "position_rates": {
                "top_rates": [],
                "abs_top_rates": [],
                "position_losses": [],
            },
            "impression_shares": [],
        }

        # Single pass through data
        for record in self._result.auction_data:
            domain = record.competitor_domain
            metrics = aggregated["competitor_metrics"][domain]

            # Competitor metrics
            metrics["domains"].add(domain)
            metrics["records"].append(record)
            if record.campaign_name:
                metrics["campaigns_affected"].add(record.campaign_name)

            # Aggregate metrics
            if record.overlap_rate is not None:
                metrics["total_overlap"] += record.overlap_rate
            if record.position_above_rate is not None:
                metrics["avg_position_above"] += record.position_above_rate
            if record.outranking_share is not None:
                metrics["avg_outranking_share"] += record.outranking_share

            # Position metrics
            if record.top_of_page_rate is not None:
                aggregated["position_rates"]["top_rates"].append(
                    record.top_of_page_rate
                )
            if record.abs_top_of_page_rate is not None:
                aggregated["position_rates"]["abs_top_rates"].append(
                    record.abs_top_of_page_rate
                )
            if (
                record.position_above_rate is not None
                and record.position_above_rate > self.POSITION_LOSS_THRESHOLD
            ):
                aggregated["position_rates"]["position_losses"].append(
                    {
                        "competitor": record.competitor_domain,
                        "position_above_rate": record.position_above_rate,
                        "campaign": record.campaign_name,
                    }
                )

            # Impression shares
            if record.impression_share is not None:
                aggregated["impression_shares"].append(record.impression_share)

        return aggregated

    def _analyze_competitor_rankings_optimized(
        self, aggregated_data: dict[str, Any]
    ) -> None:
        """Analyze competitor rankings using pre-aggregated data."""
        competitor_metrics = aggregated_data["competitor_metrics"]
        rankings = []

        for domain, metrics in competitor_metrics.items():
            record_count = len(metrics["records"])

            # Safety check for division by zero
            if record_count == 0:
                self.logger.warning(f"No records found for competitor {domain}")
                continue

            # Calculate averages
            avg_overlap = metrics["total_overlap"] / record_count
            avg_position_above = metrics["avg_position_above"] / record_count
            avg_outranking = metrics["avg_outranking_share"] / record_count

            # Calculate threat score (weighted combination)
            threat_score = (
                avg_overlap * 0.3  # How often they show with us
                + avg_position_above * 0.4  # How often they're above us
                + (1 - avg_outranking) * 0.3  # How rarely we outrank them
            )

            rankings.append(
                {
                    "domain": domain,
                    "threat_score": threat_score,
                    "avg_overlap_rate": avg_overlap,
                    "avg_position_above_rate": avg_position_above,
                    "avg_outranking_share": avg_outranking,
                    "campaigns_affected": len(metrics["campaigns_affected"]),
                    "campaign_names": list(metrics["campaigns_affected"]),
                }
            )

        # Sort by threat score
        self._result.competitor_rankings = sorted(
            rankings, key=lambda x: x["threat_score"], reverse=True
        )

    def _analyze_competitor_rankings(self) -> None:
        """Rank competitors by various threat metrics."""
        competitor_metrics = defaultdict(
            lambda: {
                "domains": set(),
                "total_overlap": 0.0,
                "avg_overlap_rate": 0.0,
                "avg_position_above": 0.0,
                "avg_outranking_share": 0.0,
                "campaigns_affected": set(),
                "records": [],
            }
        )

        # Aggregate metrics by competitor
        for record in self._result.auction_data:
            domain = record.competitor_domain
            metrics = competitor_metrics[domain]

            metrics["domains"].add(domain)
            metrics["records"].append(record)

            if record.campaign_name:
                metrics["campaigns_affected"].add(record.campaign_name)

            # Sum up metrics for averaging
            if record.overlap_rate is not None:
                metrics["total_overlap"] += record.overlap_rate
            if record.position_above_rate is not None:
                metrics["avg_position_above"] += record.position_above_rate
            if record.outranking_share is not None:
                metrics["avg_outranking_share"] += record.outranking_share

        # Calculate averages and threat scores
        rankings = []
        for domain, metrics in competitor_metrics.items():
            record_count = len(metrics["records"])

            # Safety check for division by zero (should never happen due to loop logic)
            if record_count == 0:
                self.logger.warning(f"No records found for competitor {domain}")
                continue

            # Calculate averages
            avg_overlap = metrics["total_overlap"] / record_count
            avg_position_above = metrics["avg_position_above"] / record_count
            avg_outranking = metrics["avg_outranking_share"] / record_count

            # Calculate threat score (weighted combination)
            threat_score = (
                avg_overlap * 0.3  # How often they show with us
                + avg_position_above * 0.4  # How often they're above us
                + (1 - avg_outranking) * 0.3  # How rarely we outrank them
            )

            rankings.append(
                {
                    "domain": domain,
                    "threat_score": threat_score,
                    "avg_overlap_rate": avg_overlap,
                    "avg_position_above_rate": avg_position_above,
                    "avg_outranking_share": avg_outranking,
                    "campaigns_affected": len(metrics["campaigns_affected"]),
                    "campaign_names": list(metrics["campaigns_affected"]),
                }
            )

        # Sort by threat score
        self._result.competitor_rankings = sorted(
            rankings, key=lambda x: x["threat_score"], reverse=True
        )

    def _analyze_campaign_competition(self) -> None:
        """Analyze competition levels by campaign."""
        campaign_data = defaultdict(
            lambda: {
                "competitors": [],
                "avg_overlap": 0.0,
                "avg_position_loss": 0.0,
                "competitive_pressure": "low",
            }
        )

        # Group by campaign
        for record in self._result.auction_data:
            if not record.campaign_name:
                continue

            campaign = campaign_data[record.campaign_name]
            campaign["competitors"].append(
                {
                    "domain": record.competitor_domain,
                    "overlap_rate": record.overlap_rate or 0.0,
                    "position_above_rate": record.position_above_rate or 0.0,
                    "competitive_pressure": record.competitive_pressure,
                }
            )

        # Calculate campaign-level metrics
        for campaign_name, data in campaign_data.items():
            if data["competitors"]:
                # Filter out None values before calculations
                overlaps = [
                    c["overlap_rate"]
                    for c in data["competitors"]
                    if c["overlap_rate"] is not None
                ]
                positions = [
                    c["position_above_rate"]
                    for c in data["competitors"]
                    if c["position_above_rate"] is not None
                ]

                if overlaps:
                    data["avg_overlap"] = statistics.mean(overlaps)
                if positions:
                    data["avg_position_loss"] = statistics.mean(positions)

                # Determine overall pressure
                if data["avg_overlap"] > self.HIGH_COMPETITION_OVERLAP:
                    data["competitive_pressure"] = "high"
                elif data["avg_overlap"] > self.MEDIUM_COMPETITION_OVERLAP:
                    data["competitive_pressure"] = "medium"
                else:
                    data["competitive_pressure"] = "low"

        self._result.campaign_competition = dict(campaign_data)

    def _analyze_position_metrics_optimized(
        self, aggregated_data: dict[str, Any]
    ) -> None:
        """Analyze position metrics using pre-aggregated data."""
        position_rates = aggregated_data["position_rates"]
        position_data = {
            "avg_top_of_page_rate": 0.0,
            "avg_abs_top_rate": 0.0,
            "position_loss_frequency": 0.0,
            "primary_position_threats": [],
        }

        # Calculate averages from pre-aggregated data
        if position_rates["top_rates"]:
            position_data["avg_top_of_page_rate"] = statistics.mean(
                position_rates["top_rates"]
            )
        if position_rates["abs_top_rates"]:
            position_data["avg_abs_top_rate"] = statistics.mean(
                position_rates["abs_top_rates"]
            )
        if self._result.auction_data:
            position_data["position_loss_frequency"] = len(
                position_rates["position_losses"]
            ) / len(self._result.auction_data)

        # Primary threats are already sorted by position_above_rate
        position_data["primary_position_threats"] = sorted(
            position_rates["position_losses"],
            key=lambda x: x["position_above_rate"],
            reverse=True,
        )[:5]

        self._result.position_metrics = position_data
        self._result.position_loss_analysis = position_rates["position_losses"]

    def _analyze_position_metrics(self) -> None:
        """Analyze position metrics and identify position loss causes."""
        position_data = {
            "avg_top_of_page_rate": 0.0,
            "avg_abs_top_rate": 0.0,
            "position_loss_frequency": 0.0,
            "primary_position_threats": [],
        }

        top_rates = []
        abs_top_rates = []
        position_losses = []

        for record in self._result.auction_data:
            if record.top_of_page_rate is not None:
                top_rates.append(record.top_of_page_rate)
            if record.abs_top_of_page_rate is not None:
                abs_top_rates.append(record.abs_top_of_page_rate)
            if (
                record.position_above_rate is not None
                and record.position_above_rate > self.POSITION_LOSS_THRESHOLD
            ):
                position_losses.append(
                    {
                        "competitor": record.competitor_domain,
                        "position_above_rate": record.position_above_rate,
                        "campaign": record.campaign_name,
                    }
                )

        # Calculate averages
        if top_rates:
            position_data["avg_top_of_page_rate"] = statistics.mean(top_rates)
        if abs_top_rates:
            position_data["avg_abs_top_rate"] = statistics.mean(abs_top_rates)
        if self._result.auction_data:
            position_data["position_loss_frequency"] = len(position_losses) / len(
                self._result.auction_data
            )

        # Identify main threats
        position_data["primary_position_threats"] = sorted(
            position_losses, key=lambda x: x["position_above_rate"], reverse=True
        )[:5]

        self._result.position_metrics = position_data
        self._result.position_loss_analysis = position_losses

    def _identify_aggressive_competitors(self) -> None:
        """Identify competitors showing aggressive bidding behavior."""
        aggressive = []

        for competitor in self._result.competitor_rankings[:10]:  # Top 10 threats
            aggression_assessment = self._assess_competitor_aggression(competitor)
            if aggression_assessment["is_aggressive"]:
                aggressive.append(
                    {
                        "domain": competitor["domain"],
                        "threat_score": competitor["threat_score"],
                        "reasons": aggression_assessment["reasons"],
                        "campaigns_affected": competitor["campaign_names"],
                    }
                )

        self._result.aggressive_competitors = aggressive

    def _assess_competitor_aggression(
        self, competitor: dict[str, Any]
    ) -> dict[str, Any]:
        """Assess if a competitor shows aggressive behavior."""
        is_aggressive = False
        aggression_reasons = []

        # High overlap rate (showing frequently)
        if competitor["avg_overlap_rate"] > self.HIGH_OVERLAP_THRESHOLD:
            is_aggressive = True
            aggression_reasons.append(
                f"High overlap rate (>{self.HIGH_OVERLAP_THRESHOLD * 100:.0f}%)"
            )

        # Frequently above us
        if competitor["avg_position_above_rate"] > self.AGGRESSIVE_POSITION_THRESHOLD:
            is_aggressive = True
            aggression_reasons.append(
                f"Frequently in higher positions (>{self.AGGRESSIVE_POSITION_THRESHOLD * 100:.0f}%)"
            )

        # Low outranking share (hard to beat)
        if competitor["avg_outranking_share"] < self.LOW_OUTRANKING_THRESHOLD:
            is_aggressive = True
            aggression_reasons.append(
                f"Difficult to outrank (<{self.LOW_OUTRANKING_THRESHOLD * 100:.0f}% success)"
            )

        # Affecting multiple campaigns
        if competitor["campaigns_affected"] > self.MIN_CAMPAIGNS_FOR_AGGRESSION:
            is_aggressive = True
            aggression_reasons.append(
                f"Competing across {competitor['campaigns_affected']} campaigns"
            )

        return {"is_aggressive": is_aggressive, "reasons": aggression_reasons}

    def _analyze_keyword_themes(self) -> None:
        """Analyze competitive pressure by keyword themes."""
        # Since we don't have keyword-level data in auction insights,
        # we'll analyze by campaign patterns
        theme_pressure = defaultdict(
            lambda: {
                "competitors": set(),
                "avg_pressure": 0.0,
                "dominant_competitor": None,
            }
        )

        # Group campaigns by common patterns (simplified theme detection)
        for campaign_name, competition in self._result.campaign_competition.items():
            # Extract potential theme from campaign name
            theme = self._extract_theme(campaign_name)

            for competitor in competition["competitors"]:
                theme_pressure[theme]["competitors"].add(competitor["domain"])

            # Calculate average pressure for theme
            if competition["competitors"]:
                pressures = [c["overlap_rate"] for c in competition["competitors"]]
                theme_pressure[theme]["avg_pressure"] = statistics.mean(pressures)

                # Find dominant competitor
                dominant = max(
                    competition["competitors"], key=lambda x: x["overlap_rate"]
                )
                theme_pressure[theme]["dominant_competitor"] = dominant["domain"]

        self._result.keyword_theme_pressure = dict(theme_pressure)

    def _extract_theme(self, campaign_name: str) -> str:
        """Extract theme from campaign name (simplified)."""
        # Common patterns in campaign names
        campaign_lower = campaign_name.lower()

        if "brand" in campaign_lower and "non-brand" not in campaign_lower:
            return "Brand"
        elif "competitor" in campaign_lower or "comp" in campaign_lower:
            return "Competitor"
        elif (
            "location" in campaign_lower
            or "geo" in campaign_lower
            or "local" in campaign_lower
        ):
            return "Local/Geo"
        elif "product" in campaign_lower or "shopping" in campaign_lower:
            return "Product/Shopping"
        elif "generic" in campaign_lower or "non-brand" in campaign_lower:
            return "Generic/Non-Brand"
        else:
            return "Other"

    def _identify_competitive_gaps(self) -> None:
        """Identify gaps and opportunities in competitive landscape."""
        gaps = []

        # Low competition campaigns (opportunities)
        for campaign, data in self._result.campaign_competition.items():
            if (
                data["competitive_pressure"] == "low"
                and data["avg_overlap"] < self.MEDIUM_COMPETITION_OVERLAP
            ):
                gaps.append(
                    {
                        "type": "low_competition_opportunity",
                        "campaign": campaign,
                        "avg_overlap": data["avg_overlap"],
                        "description": f"Low competition in {campaign} - opportunity to dominate",
                    }
                )

        # Position improvement opportunities
        for record in self._result.auction_data:
            if (
                record.position_above_rate is not None
                and record.position_above_rate > self.POSITION_LOSS_THRESHOLD
                and record.outranking_share is not None
                and record.outranking_share < self.POSITION_LOSS_THRESHOLD
            ):
                gaps.append(
                    {
                        "type": "position_improvement",
                        "competitor": record.competitor_domain,
                        "campaign": record.campaign_name,
                        "current_outranking": record.outranking_share,
                        "description": f"Position improvement opportunity against {record.competitor_domain}",
                    }
                )

        # Market share opportunities (use aggregated data if available)
        if self._result.competitor_rankings:
            # Check if we have aggregated impression shares
            aggregated_shares = getattr(self, "_last_aggregated_data", {}).get(
                "impression_shares", []
            )
            if not aggregated_shares:
                # Fall back to manual collection
                aggregated_shares = [
                    record.impression_share
                    for record in self._result.auction_data
                    if record.impression_share is not None
                ]

            if aggregated_shares:
                our_avg_share = statistics.mean(aggregated_shares)
                if our_avg_share < self.LOW_MARKET_SHARE_THRESHOLD:  # Low market share
                    gaps.append(
                        {
                            "type": "market_share",
                            "current_share": our_avg_share,
                            "description": "Low overall impression share - opportunity to expand market presence",
                        }
                    )

        self._result.competitive_gaps = gaps[: self.MAX_COMPETITIVE_GAPS]  # Top gaps

    def _analyze_competitive_trends(self) -> None:
        """Analyze competitive changes over time."""
        # Group data by date ranges if available
        trends = defaultdict(list)

        for record in self._result.auction_data:
            if record.date_range:
                trends[record.competitor_domain].append(
                    {
                        "date_range": record.date_range,
                        "overlap_rate": record.overlap_rate,
                        "position_above_rate": record.position_above_rate,
                        "impression_share": record.impression_share,
                    }
                )

        # Calculate share changes (simplified - would need historical data)
        share_changes = {}
        for domain, trend_data in trends.items():
            if len(trend_data) >= 2:
                # Simple change calculation
                first_share = trend_data[0].get("impression_share", 0) or 0
                last_share = trend_data[-1].get("impression_share", 0) or 0
                share_changes[domain] = last_share - first_share

        self._result.competitive_trends = dict(trends)
        self._result.share_changes = share_changes

    def _generate_recommendations(self) -> None:
        """Generate strategic recommendations based on analysis."""
        recommendations = []

        # Bid strategy recommendations
        for competitor in self._result.aggressive_competitors[:3]:
            recommendations.append(
                Recommendation(
                    type=RecommendationType.ADJUST_BID,
                    priority=RecommendationPriority.HIGH,
                    title=f"Compete with {competitor['domain']}",
                    description=f"Increase bids to compete with aggressive competitor {competitor['domain']}",
                    action_data={
                        "competitor": competitor["domain"],
                        "threat_score": competitor["threat_score"],
                        "campaigns_affected": competitor["campaigns_affected"],
                        "reasons": competitor["reasons"],
                    },
                    estimated_impact="Improved position and impression share",
                )
            )

        # Budget reallocation recommendations
        high_competition_campaigns = [
            (campaign, data)
            for campaign, data in self._result.campaign_competition.items()
            if data["competitive_pressure"] == "high"
        ]

        if high_competition_campaigns:
            recommendations.append(
                Recommendation(
                    type=RecommendationType.BUDGET_OPTIMIZATION,
                    priority=RecommendationPriority.MEDIUM,
                    title="Reallocate budget to competitive campaigns",
                    description="Reallocate budget to high-competition campaigns requiring more investment",
                    action_data={
                        "campaigns": [c[0] for c in high_competition_campaigns[:5]],
                        "reason": "High competitive pressure requiring increased investment",
                    },
                    estimated_impact="Better competitive positioning in key campaigns",
                )
            )

        # Keyword opportunity recommendations
        for gap in self._result.competitive_gaps:
            if gap["type"] == "low_competition_opportunity":
                recommendations.append(
                    Recommendation(
                        type=RecommendationType.ADD_KEYWORD,
                        priority=RecommendationPriority.MEDIUM,
                        title=f"Expand {gap['campaign']}",
                        description=f"Expand keywords in low-competition campaign: {gap['campaign']}",
                        action_data={
                            "campaign": gap["campaign"],
                            "current_overlap": gap["avg_overlap"],
                            "opportunity": "Low competition provides growth opportunity",
                        },
                        estimated_impact="Increased impression share with lower competition",
                    )
                )

        # Position improvement recommendations
        position_threats = self._result.position_loss_analysis[:3]
        for threat in position_threats:
            recommendations.append(
                Recommendation(
                    type=RecommendationType.ADJUST_BID,
                    priority=RecommendationPriority.HIGH,
                    title=f"Improve position vs {threat['competitor']}",
                    description=f"Improve ad position against {threat['competitor']} in {threat['campaign']}",
                    action_data={
                        "competitor": threat["competitor"],
                        "campaign": threat["campaign"],
                        "position_above_rate": threat["position_above_rate"],
                    },
                    estimated_impact="Reduced position losses to competitor",
                )
            )

        # Market share recommendation
        if self._result.competitive_gaps:
            share_gaps = [
                g for g in self._result.competitive_gaps if g["type"] == "market_share"
            ]
            if share_gaps:
                recommendations.append(
                    Recommendation(
                        type=RecommendationType.OTHER,
                        priority=RecommendationPriority.HIGH,
                        title="Expand market share",
                        description="Expand campaign reach to capture more market share",
                        action_data={
                            "current_share": share_gaps[0]["current_share"],
                            "recommendation": "Consider new campaigns or broader targeting",
                        },
                        estimated_impact="Increased overall impression share",
                    )
                )

        self._result.recommendations = recommendations

    def get_name(self) -> str:
        """Return analyzer name."""
        return "competitor_insights"

    def get_description(self) -> str:
        """Return analyzer description."""
        return "Analyzes auction insights data to provide competitive intelligence"
