"""Auction Insights parser for Google Ads competitive analysis."""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from paidsearchnav.parsers.csv_parser import GoogleAdsCSVParser

logger = logging.getLogger(__name__)


class AuctionInsightsConfig:
    """Configuration for auction insights analysis."""

    def __init__(
        self,
        high_threat_threshold: float = 0.3,
        medium_threat_threshold: float = 0.15,
        high_overlap_threshold: float = 0.3,
        low_outranking_threshold: float = 0.3,
        low_positioning_threshold: float = 0.4,
        own_domain_detection_strict: bool = True,
    ):
        """Initialize auction insights configuration.

        Args:
            high_threat_threshold: Threat score threshold for high threat classification
            medium_threat_threshold: Threat score threshold for medium threat classification
            high_overlap_threshold: Overlap rate threshold for high overlap detection
            low_outranking_threshold: Outranking share threshold for weak competitors
            low_positioning_threshold: Top-of-page rate threshold for low positioning
            own_domain_detection_strict: Whether to use strict own domain detection
        """
        self.high_threat_threshold = high_threat_threshold
        self.medium_threat_threshold = medium_threat_threshold
        self.high_overlap_threshold = high_overlap_threshold
        self.low_outranking_threshold = low_outranking_threshold
        self.low_positioning_threshold = low_positioning_threshold
        self.own_domain_detection_strict = own_domain_detection_strict


class AuctionInsightsParser(GoogleAdsCSVParser):
    """Parser for Google Ads Auction Insights reports.

    Provides comprehensive competitive analysis including market share,
    positioning metrics, and strategic insights for competitive intelligence.
    """

    def __init__(self, config: Optional[AuctionInsightsConfig] = None, **kwargs):
        """Initialize AuctionInsightsParser with auction insights file type.

        Args:
            config: Configuration for auction insights analysis
            **kwargs: Additional arguments passed to parent class
        """
        # Enable preprocessing to handle Google Ads headers
        kwargs.setdefault("strict_validation", False)
        super().__init__(file_type="auction_insights", **kwargs)
        self.config = config or AuctionInsightsConfig()

    def analyze_competitive_landscape(
        self, data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze competitive landscape from auction insights data.

        Args:
            data: List of parsed auction insights records.

        Returns:
            Comprehensive competitive analysis with strategic insights.
        """
        if not data:
            logger.warning("No auction insights data provided for analysis")
            return {"error": "No auction insights data provided"}

        logger.info(f"Starting competitive analysis for {len(data)} domain entries")

        # Extract competitor data with validation
        competitors = []
        own_domain = None
        skipped_rows = 0

        for i, row in enumerate(data):
            # Validate required fields exist
            if "competitor_domain" not in row:
                logger.warning(f"Row {i}: Missing competitor_domain field, skipping")
                skipped_rows += 1
                continue

            domain = row.get("competitor_domain", "").strip()
            if not domain:
                logger.warning(f"Row {i}: Empty competitor_domain, skipping")
                skipped_rows += 1
                continue

            impression_share = self._parse_percentage(row.get("impression_share", "0%"))
            overlap_rate = self._parse_percentage(row.get("overlap_rate", "0%"))
            top_of_page_rate = self._parse_percentage(row.get("top_of_page_rate", "0%"))
            abs_top_of_page_rate = self._parse_percentage(
                row.get("abs_top_of_page_rate", "0%")
            )
            outranking_share = self._parse_percentage(row.get("outranking_share", "0%"))
            position_above_rate = self._parse_percentage(
                row.get("position_above_rate", "0%")
            )

            competitor_data = {
                "domain": domain,
                "impression_share": impression_share,
                "overlap_rate": overlap_rate,
                "top_of_page_rate": top_of_page_rate,
                "abs_top_of_page_rate": abs_top_of_page_rate,
                "outranking_share": outranking_share,
                "position_above_rate": position_above_rate,
            }

            # Enhanced own domain detection with configuration
            is_own_domain = self._is_own_domain(competitor_data)
            if is_own_domain:
                own_domain = competitor_data
                logger.info(f"Identified own domain: {domain}")
            else:
                competitors.append(competitor_data)

        if skipped_rows > 0:
            logger.warning(f"Skipped {skipped_rows} rows due to validation issues")

        # Sort competitors by impression share
        competitors.sort(key=lambda x: x["impression_share"], reverse=True)

        logger.info(
            f"Found {len(competitors)} competitors and {'1' if own_domain else '0'} own domain entries"
        )

        # Generate analysis
        analysis = self._generate_competitive_analysis(competitors, own_domain)

        return analysis

    def _is_own_domain(self, competitor_data: Dict[str, Any]) -> bool:
        """Determine if this entry represents the own domain.

        Args:
            competitor_data: Competitor data dictionary

        Returns:
            True if this represents the own domain
        """
        overlap_rate = competitor_data["overlap_rate"]
        outranking_share = competitor_data["outranking_share"]
        position_above_rate = competitor_data["position_above_rate"]

        if self.config.own_domain_detection_strict:
            # Strict detection: all competitive metrics must be zero
            return (
                overlap_rate == 0 and outranking_share == 0 and position_above_rate == 0
            )
        else:
            # Lenient detection: at least two competitive metrics must be zero
            zero_count = sum(
                [overlap_rate == 0, outranking_share == 0, position_above_rate == 0]
            )
            return zero_count >= 2

    def _parse_percentage(self, value: str) -> float:
        """Parse percentage string to float.

        Args:
            value: Percentage string (e.g., "25.5%", "--")

        Returns:
            Float value (e.g., 0.255 for "25.5%", 0.0 for "--")
        """
        if not value or value == "--" or value == "":
            return 0.0

        try:
            # Remove % sign and convert to decimal
            cleaned = str(value).replace("%", "").strip()
            return float(cleaned) / 100.0
        except (ValueError, AttributeError):
            return 0.0

    def _generate_competitive_analysis(
        self, competitors: List[Dict[str, Any]], own_domain: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Generate comprehensive competitive analysis.

        Args:
            competitors: List of competitor data dictionaries.
            own_domain: Own domain data (if identified).

        Returns:
            Detailed competitive analysis with KPIs and insights.
        """
        if not competitors:
            return {"error": "No competitor data found"}

        logger.info(
            "Performing optimized competitive analysis with single-pass calculations"
        )

        total_competitors = len(competitors)
        top_competitor = competitors[0] if competitors else None

        # Single-pass analysis to optimize performance
        total_market_coverage = 0.0
        total_top_of_page = 0.0
        total_abs_top = 0.0
        strongest_competitor = None
        easiest_to_outrank = None
        overlap_leader = None

        max_impression_share = 0.0
        min_outranking_share = 1.0
        max_overlap_rate = 0.0

        for i, competitor in enumerate(competitors):
            # Market coverage calculation
            impression_share = competitor["impression_share"]
            total_market_coverage += impression_share

            # Position performance accumulation
            total_top_of_page += competitor["top_of_page_rate"]
            total_abs_top += competitor["abs_top_of_page_rate"]

            # Find strongest competitor (highest impression share)
            if impression_share > max_impression_share:
                max_impression_share = impression_share
                strongest_competitor = competitor

            # Find easiest to outrank (lowest outranking share)
            outranking_share = competitor["outranking_share"]
            if outranking_share < min_outranking_share:
                min_outranking_share = outranking_share
                easiest_to_outrank = competitor

            # Find overlap leader (highest overlap rate)
            overlap_rate = competitor["overlap_rate"]
            if overlap_rate > max_overlap_rate:
                max_overlap_rate = overlap_rate
                overlap_leader = competitor

        # Calculate averages
        avg_top_of_page = (
            total_top_of_page / total_competitors if total_competitors > 0 else 0.0
        )
        avg_abs_top = (
            total_abs_top / total_competitors if total_competitors > 0 else 0.0
        )

        # Market concentration (top 3)
        top_3_share = sum(c["impression_share"] for c in competitors[:3])

        # Add own domain to market coverage
        if own_domain:
            total_market_coverage += own_domain["impression_share"]

        # Strategic recommendations
        recommendations = self._generate_recommendations(competitors, own_domain)

        # Opportunity analysis
        opportunities = self._identify_opportunities(competitors, own_domain)

        analysis = {
            "total_competitors": total_competitors,
            "market_analysis": {
                "top_competitor": top_competitor["domain"] if top_competitor else None,
                "top_competitor_impression_share": f"{top_competitor['impression_share']:.1%}"
                if top_competitor
                else "0.0%",
                "market_leader_gap": f"{(top_competitor['impression_share'] - (own_domain['impression_share'] if own_domain else 0)):.1%}"
                if top_competitor and own_domain
                else "N/A",
                "total_market_coverage": f"{total_market_coverage:.1%}",
                "market_concentration_top3": f"{top_3_share:.1%}",
            },
            "position_analysis": {
                "avg_top_of_page_rate": f"{avg_top_of_page:.1%}",
                "avg_abs_top_rate": f"{avg_abs_top:.1%}",
                "position_opportunities": len(
                    [c for c in competitors if c["top_of_page_rate"] < 0.5]
                ),
            },
            "competitive_insights": {
                "strongest_competitor": strongest_competitor["domain"]
                if strongest_competitor
                else "None",
                "strongest_competitor_share": f"{strongest_competitor['impression_share']:.1%}"
                if strongest_competitor
                else "0.0%",
                "easiest_to_outrank": easiest_to_outrank["domain"]
                if easiest_to_outrank
                else "None",
                "overlap_leader": overlap_leader["domain"]
                if overlap_leader
                else "None",
                "overlap_leader_rate": f"{overlap_leader['overlap_rate']:.1%}"
                if overlap_leader
                else "0.0%",
                "improvement_opportunities": opportunities,
            },
            "strategic_recommendations": recommendations,
            "kpis": self._calculate_kpis(competitors, own_domain),
            "detailed_competitors": [
                {
                    "domain": c["domain"],
                    "impression_share": f"{c['impression_share']:.1%}",
                    "overlap_rate": f"{c['overlap_rate']:.1%}",
                    "top_of_page_rate": f"{c['top_of_page_rate']:.1%}",
                    "abs_top_of_page_rate": f"{c['abs_top_of_page_rate']:.1%}",
                    "outranking_share": f"{c['outranking_share']:.1%}",
                    "position_above_rate": f"{c['position_above_rate']:.1%}",
                    "competitive_threat": self._assess_competitive_threat(c),
                }
                for c in competitors
            ],
        }

        if own_domain:
            analysis["own_performance"] = {
                "domain": own_domain["domain"],
                "impression_share": f"{own_domain['impression_share']:.1%}",
                "market_position": self._calculate_market_position(
                    own_domain, competitors
                ),
                "competitive_advantage_score": self._calculate_advantage_score(
                    own_domain, competitors
                ),
            }

        return analysis

    def _generate_recommendations(
        self, competitors: List[Dict[str, Any]], own_domain: Optional[Dict[str, Any]]
    ) -> List[str]:
        """Generate strategic recommendations based on competitive data."""
        recommendations = []

        if not competitors:
            return ["No competitive data available for recommendations"]

        logger.debug(
            "Generating strategic recommendations based on competitive analysis"
        )

        # High overlap competitors (using configurable threshold)
        high_overlap = [
            c
            for c in competitors
            if c["overlap_rate"] > self.config.high_overlap_threshold
        ]
        if high_overlap:
            recommendations.append(
                "Focus budget on high-overlap keywords to compete directly with top competitors"
            )

        # Top positioning opportunities (using configurable threshold)
        low_top_performers = [
            c
            for c in competitors
            if c["top_of_page_rate"] < self.config.low_positioning_threshold
        ]
        if low_top_performers and own_domain and own_domain["impression_share"] > 0.15:
            recommendations.append(
                "Increase bids for top positioning to outperform competitors with low top-of-page rates"
            )

        # Outranking opportunities (using configurable threshold)
        weak_outranking = [
            c
            for c in competitors
            if c["outranking_share"] < self.config.low_outranking_threshold
        ]
        if weak_outranking:
            top_target = min(weak_outranking, key=lambda x: x["outranking_share"])
            recommendations.append(
                f"Target {top_target['domain']} for outranking opportunities with strategic bid increases"
            )

        # Market share growth
        if own_domain and own_domain["impression_share"] < 0.2:
            recommendations.append(
                "Increase budget allocation to grow market share and impression share"
            )

        # Position dominance strategy
        top_performer = max(competitors, key=lambda x: x["top_of_page_rate"])
        if top_performer["top_of_page_rate"] > 0.6:
            recommendations.append(
                f"Study {top_performer['domain']}'s positioning strategy to improve top-of-page performance"
            )

        return recommendations[:5]  # Limit to top 5 recommendations

    def _identify_opportunities(
        self, competitors: List[Dict[str, Any]], own_domain: Optional[Dict[str, Any]]
    ) -> List[str]:
        """Identify specific improvement opportunities with optimized processing."""
        opportunities: List[str] = []

        if not competitors:
            return opportunities

        logger.debug("Identifying competitive opportunities with batched processing")

        # Batch process all metrics in single pass for large datasets
        total_abs_top = 0.0
        weak_outranking_competitors = []
        market_leader = competitors[0]  # Already sorted by impression share
        max_impression_share = 0.0

        for competitor in competitors:
            # Accumulate metrics
            total_abs_top += competitor["abs_top_of_page_rate"]

            # Batch identify weak outranking competitors
            if competitor["outranking_share"] < 0.25:
                weak_outranking_competitors.append(competitor["domain"])

            # Find market leader
            if competitor["impression_share"] > max_impression_share:
                max_impression_share = competitor["impression_share"]
                market_leader = competitor

        # Calculate average absolute top positioning
        avg_abs_top = total_abs_top / len(competitors)
        if avg_abs_top < 0.15:
            opportunities.append("Increase absolute top positioning across campaigns")

        # Add outranking opportunities (limit to avoid overwhelming output)
        if weak_outranking_competitors:
            if len(weak_outranking_competitors) <= 3:
                for domain in weak_outranking_competitors:
                    opportunities.append(f"Improve outranking share vs {domain}")
            else:
                opportunities.append(
                    f"Improve outranking share vs {len(weak_outranking_competitors)} competitors"
                )

        # Market share expansion
        if (
            own_domain
            and market_leader["impression_share"] - own_domain["impression_share"] > 0.1
        ):
            opportunities.append("Close impression share gap with market leader")

        return opportunities[:4]  # Limit to top 4 opportunities

    def _assess_competitive_threat(self, competitor: Dict[str, Any]) -> str:
        """Assess the competitive threat level of a competitor using configurable thresholds."""
        impression_share = competitor["impression_share"]
        top_of_page = competitor["top_of_page_rate"]
        overlap_rate = competitor["overlap_rate"]

        # Calculate threat score
        threat_score = impression_share * 0.4 + top_of_page * 0.3 + overlap_rate * 0.3

        if threat_score > self.config.high_threat_threshold:
            return "High"
        elif threat_score > self.config.medium_threat_threshold:
            return "Medium"
        else:
            return "Low"

    def _calculate_market_position(
        self, own_domain: Dict[str, Any], competitors: List[Dict[str, Any]]
    ) -> int:
        """Calculate market position ranking."""
        all_domains = competitors + [own_domain]
        sorted_domains = sorted(
            all_domains, key=lambda x: x["impression_share"], reverse=True
        )

        for i, domain in enumerate(sorted_domains):
            if domain["domain"] == own_domain["domain"]:
                return i + 1

        return len(all_domains)

    def _calculate_advantage_score(
        self, own_domain: Dict[str, Any], competitors: List[Dict[str, Any]]
    ) -> float:
        """Calculate competitive advantage score (0-100)."""
        if not competitors:
            return 100.0

        # Compare against average competitor performance
        avg_impression_share = sum(c["impression_share"] for c in competitors) / len(
            competitors
        )
        avg_top_of_page = sum(c["top_of_page_rate"] for c in competitors) / len(
            competitors
        )

        impression_advantage = (
            own_domain["impression_share"] - avg_impression_share
        ) * 100
        positioning_advantage = (
            own_domain.get("top_of_page_rate", 0) - avg_top_of_page
        ) * 100

        # Weighted score
        advantage_score = impression_advantage * 0.6 + positioning_advantage * 0.4

        # Normalize to 0-100 scale
        return max(0, min(100, 50 + advantage_score))

    def _calculate_kpis(
        self, competitors: List[Dict[str, Any]], own_domain: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Calculate key performance indicators for auction insights."""
        if not competitors:
            return {}

        # Competitive market metrics
        avg_impression_share = sum(c["impression_share"] for c in competitors) / len(
            competitors
        )
        market_concentration = sum(c["impression_share"] for c in competitors[:3])
        avg_overlap_rate = sum(c["overlap_rate"] for c in competitors) / len(
            competitors
        )

        # Strategic performance indicators
        avg_outranking_share = sum(c["outranking_share"] for c in competitors) / len(
            competitors
        )
        position_improvement_potential = len(
            [c for c in competitors if c["top_of_page_rate"] < 0.5]
        )

        competitive_advantage_score = 50.0  # Default neutral score
        if own_domain:
            competitive_advantage_score = self._calculate_advantage_score(
                own_domain, competitors
            )

        return {
            "competitive_market_metrics": {
                "total_competitors": len(competitors),
                "market_concentration_top3": f"{market_concentration:.1%}",
                "average_impression_share": f"{avg_impression_share:.1%}",
                "average_overlap_rate": f"{avg_overlap_rate:.1%}",
            },
            "strategic_performance_indicators": {
                "average_outranking_share": f"{avg_outranking_share:.1%}",
                "position_improvement_potential": position_improvement_potential,
                "competitive_advantage_score": f"{competitive_advantage_score:.1f}/100",
            },
        }

    def parse_and_analyze(self, file_path: Path) -> Dict[str, Any]:
        """Parse auction insights CSV and return comprehensive analysis.

        Args:
            file_path: Path to the auction insights CSV file.

        Returns:
            Complete analysis including parsed data and competitive insights.
        """
        try:
            # Parse the CSV file with preprocessing enabled
            parsed_data = self.parse(file_path, preprocess=True)

            # Convert to dictionaries if they are Pydantic models
            data_dicts = []
            for item in parsed_data:
                if hasattr(item, "dict"):
                    data_dicts.append(item.dict())
                else:
                    data_dicts.append(item)

            # Perform competitive analysis
            analysis = self.analyze_competitive_landscape(data_dicts)

            # Add parsing metadata
            result = {
                "parsing_info": {
                    "total_records": len(parsed_data),
                    "file_type": self.file_type,
                    "parsed_successfully": True,
                },
                "raw_data": data_dicts,
                "analysis": analysis,
            }

            return result

        except Exception as e:
            logger.error(f"Error parsing and analyzing auction insights: {e}")
            return {
                "parsing_info": {
                    "total_records": 0,
                    "file_type": self.file_type,
                    "parsed_successfully": False,
                    "error": str(e),
                },
                "analysis": {"error": f"Failed to analyze auction insights: {str(e)}"},
            }
