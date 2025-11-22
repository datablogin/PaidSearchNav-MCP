"""Local reach store performance analyzer for enhanced location-based metrics."""

import logging
import statistics
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Union

from paidsearchnav.core.interfaces import Analyzer
from paidsearchnav.core.models import (
    LocalReachAnalysisResult,
    LocalReachEfficiencyLevel,
    LocalReachInsight,
    LocalReachIssueType,
    LocalReachMetrics,
    LocalReachSummary,
    LocationPerformance,
    StoreLocation,
    StoreVisitData,
)
from paidsearchnav.parsers.store_csv_parser import StoreCSVParser

# Type alias for store CSV data
StoreCSVData = List[Dict[str, Any]]

logger = logging.getLogger(__name__)


class LocalReachStoreAnalyzer(Analyzer):
    """Analyzes local reach and store visit performance across multiple locations."""

    # Business logic thresholds
    MIN_IMPRESSIONS_THRESHOLD = 100
    HIGH_VISIT_RATE_THRESHOLD = 2.0  # 2% store visit rate
    MODERATE_VISIT_RATE_THRESHOLD = 1.0  # 1% store visit rate
    LOW_VISIT_RATE_THRESHOLD = 0.5  # 0.5% store visit rate
    HIGH_COST_PER_VISIT_THRESHOLD = 25.0  # $25 per store visit
    MODERATE_COST_PER_VISIT_THRESHOLD = 15.0  # $15 per store visit
    EXCELLENT_ENGAGEMENT_THRESHOLD = 4.0  # 4% local engagement rate
    GOOD_ENGAGEMENT_THRESHOLD = 2.5  # 2.5% local engagement rate
    POOR_ENGAGEMENT_THRESHOLD = 1.0  # 1% local engagement rate

    def __init__(
        self,
        min_impressions: int = 100,
        high_visit_rate_threshold: float = 2.0,
        moderate_visit_rate_threshold: float = 1.0,
        low_visit_rate_threshold: float = 0.5,
        high_cost_per_visit_threshold: float = 25.0,
    ):
        """Initialize the local reach store analyzer.

        Args:
            min_impressions: Minimum impressions required for meaningful analysis
            high_visit_rate_threshold: Store visit rate threshold for high performers (%)
            moderate_visit_rate_threshold: Store visit rate threshold for moderate performers (%)
            low_visit_rate_threshold: Store visit rate threshold for low performers (%)
            high_cost_per_visit_threshold: Cost per visit threshold for identifying inefficiency ($)
        """
        self.min_impressions = min_impressions
        self.high_visit_rate_threshold = high_visit_rate_threshold
        self.moderate_visit_rate_threshold = moderate_visit_rate_threshold
        self.low_visit_rate_threshold = low_visit_rate_threshold
        self.high_cost_per_visit_threshold = high_cost_per_visit_threshold
        self._csv_data: StoreCSVData = []

    def get_name(self) -> str:
        """Get analyzer name."""
        return "Local Reach Store Performance Analyzer"

    def get_description(self) -> str:
        """Get analyzer description."""
        return (
            "Analyzes local reach efficiency, store visit patterns, and geographic "
            "performance across multiple retail locations to optimize local campaign "
            "targeting and budget allocation."
        )

    @classmethod
    def from_csv(
        cls, file_path: Union[str, Path], max_file_size_mb: int = 100
    ) -> "LocalReachStoreAnalyzer":
        """Create a LocalReachStoreAnalyzer instance from a CSV file.

        Parses Google Ads per-store CSV report and prepares data for analysis.

        Args:
            file_path: Path to the store performance CSV file
            max_file_size_mb: Maximum allowed file size in MB (default: 100)

        Returns:
            LocalReachStoreAnalyzer instance with loaded data

        Raises:
            FileNotFoundError: If the CSV file doesn't exist
            ValueError: If the CSV format is invalid or file too large
            PermissionError: If the file path attempts directory traversal
        """
        file_path = Path(file_path) if isinstance(file_path, str) else file_path

        # Resolve to absolute path for security
        file_path = file_path.resolve()

        # Path traversal protection
        cwd = Path.cwd()
        temp_dir = Path("/tmp")
        var_folders = Path("/var/folders")
        if not (
            file_path.is_relative_to(cwd)
            or file_path.is_relative_to(temp_dir)
            or file_path.is_relative_to(var_folders)
        ):
            raise PermissionError(f"Access denied: {file_path}")

        # Check file exists
        if not file_path.exists():
            raise FileNotFoundError(f"CSV file not found: {file_path}")

        # Check file size
        file_size_mb = file_path.stat().st_size / (1024 * 1024)
        if file_size_mb > max_file_size_mb:
            raise ValueError(
                f"File size ({file_size_mb:.2f}MB) exceeds maximum allowed size ({max_file_size_mb}MB)"
            )

        # Create analyzer instance
        analyzer = cls()

        # Parse CSV using shared utility
        analyzer._csv_data = StoreCSVParser.parse_csv(file_path)

        return analyzer

    async def analyze(
        self,
        customer_id: str,
        start_date: datetime,
        end_date: datetime,
        **kwargs: Any,
    ) -> LocalReachAnalysisResult:
        """Analyze local reach and store performance data.

        Args:
            customer_id: Google Ads customer ID
            start_date: Analysis start date
            end_date: Analysis end date
            **kwargs: Additional arguments including:
                - store_data: Per store performance CSV data
                - location_data: Optional location-specific data
                - cost_data: Optional cost data for ROI analysis

        Returns:
            LocalReachAnalysisResult with comprehensive location analysis
        """
        # Validate inputs
        if not customer_id or not customer_id.strip():
            raise ValueError("customer_id is required and cannot be empty")

        if start_date >= end_date:
            raise ValueError("start_date must be before end_date")

        # Start performance tracking
        analysis_start_time = datetime.now()
        logger.info(
            f"Starting local reach store performance analysis for customer {customer_id} "
            f"from {start_date} to {end_date}"
        )

        # Get store performance data from kwargs or use pre-loaded CSV data
        store_data = kwargs.get("store_data", kwargs.get("csv_data", self._csv_data))
        if not store_data:
            raise ValueError("store_data is required for local reach analysis")

        if not store_data:
            logger.warning("No store data provided for analysis")
            return self._create_empty_result(customer_id, start_date, end_date)

        # Parse store data into location performance objects
        parsing_start_time = datetime.now()
        location_performances = self._parse_location_data(store_data)
        parsing_time = (datetime.now() - parsing_start_time).total_seconds() * 1000

        logger.info(
            f"Parsed {len(location_performances)} locations in {parsing_time:.1f}ms "
            f"(avg {parsing_time / len(location_performances) if location_performances else 0:.1f}ms per location)"
        )

        # Filter locations with sufficient data
        filtered_locations = [
            location
            for location in location_performances
            if location.metrics.local_impressions >= self.min_impressions
        ]

        excluded_count = len(location_performances) - len(filtered_locations)
        if excluded_count > 0:
            logger.info(
                f"Excluded {excluded_count} locations with insufficient data (<{self.min_impressions} impressions)"
            )

        if not filtered_locations:
            logger.warning("No locations found with sufficient data for analysis")
            return self._create_empty_result(customer_id, start_date, end_date)

        # Categorize locations by efficiency
        for location in filtered_locations:
            location.efficiency_level = self._categorize_efficiency(location)

        # Calculate market rankings
        self._calculate_market_rankings(filtered_locations)

        # Generate insights
        insights_start_time = datetime.now()
        insights = self._generate_insights(filtered_locations)
        insights_time = (datetime.now() - insights_start_time).total_seconds() * 1000

        logger.info(f"Generated {len(insights)} insights in {insights_time:.1f}ms")

        # Create summary
        summary = self._create_summary(filtered_locations)

        # Log data volume and performance metrics
        total_impressions = sum(
            loc.metrics.local_impressions for loc in filtered_locations
        )
        total_visits = sum(loc.metrics.store_visits for loc in filtered_locations)
        total_cost = sum(loc.metrics.cost for loc in filtered_locations)

        logger.info(
            f"Analysis data volume: {len(filtered_locations)} locations, "
            f"{total_impressions:,} total impressions, {total_visits:,} store visits, "
            f"${total_cost:.2f} total cost"
        )

        # Identify performance categories
        top_performers = [loc for loc in filtered_locations if loc.is_high_performer]
        underperformers = [loc for loc in filtered_locations if loc.is_underperformer]
        optimization_opportunities = [
            loc for loc in filtered_locations if loc.needs_optimization
        ]

        # Sort results
        top_performers.sort(key=lambda x: x.performance_score, reverse=True)
        underperformers.sort(key=lambda x: x.performance_score)
        optimization_opportunities.sort(
            key=lambda x: x.metrics.cost_per_store_visit, reverse=True
        )

        # Log final analysis performance metrics
        total_analysis_time = (
            datetime.now() - analysis_start_time
        ).total_seconds() * 1000

        logger.info(
            f"Completed local reach analysis in {total_analysis_time:.1f}ms: "
            f"{len(top_performers)} top performers, {len(underperformers)} underperformers, "
            f"{len(optimization_opportunities)} optimization opportunities identified"
        )

        return LocalReachAnalysisResult(
            customer_id=customer_id,
            analysis_type="local_reach_store_performance",
            analyzer_name=self.get_name(),
            start_date=start_date,
            end_date=end_date,
            summary=summary,
            location_performance=filtered_locations,
            insights=insights,
            top_performers=top_performers[:10],
            underperformers=underperformers[:10],
            optimization_opportunities=optimization_opportunities[:15],
        )

    def _parse_location_data(
        self, store_data: List[Dict[str, Any]]
    ) -> List[LocationPerformance]:
        """Parse store data into LocationPerformance objects."""
        locations = []
        required_fields = ["store_name", "local_impressions"]

        for row in store_data:
            try:
                # Validate and clean numeric fields using shared utility
                row = StoreCSVParser.validate_numeric_fields(row)

                # Validate required fields
                missing_fields = [
                    field for field in required_fields if not row.get(field)
                ]
                if missing_fields:
                    logger.warning(
                        f"Skipping row with missing required fields: {missing_fields}"
                    )
                    continue

                # Parse location data with safe string casting
                location = StoreLocation(
                    store_name=row.get("store_name", "Unknown Store"),
                    address_line_1=row.get("address_line_1", ""),
                    address_line_2=row.get("address_line_2"),
                    city=row.get("city", ""),
                    state=row.get("state", row.get("province", "")),
                    postal_code=StoreCSVParser.safe_str_cast(row.get("postal_code")),
                    country_code=row.get("country_code", "US"),
                    phone_number=row.get("phone_number"),
                    latitude=self._parse_float(row.get("latitude")),
                    longitude=self._parse_float(row.get("longitude")),
                    market_area=row.get("market_area"),
                )

                # Parse metrics (already validated by shared utility)
                local_impressions = row.get("local_impressions", 0)
                store_visits = row.get("store_visits", 0)
                call_clicks = row.get("call_clicks", 0)
                driving_directions = row.get("driving_directions", 0)
                website_visits = row.get("website_visits", 0)
                cost = self._parse_float(row.get("cost", 0.0)) or 0.0
                clicks = row.get("clicks", 0)
                conversions = row.get("conversions", 0)

                metrics = LocalReachMetrics(
                    local_impressions=local_impressions,
                    store_visits=store_visits,
                    call_clicks=call_clicks,
                    driving_directions=driving_directions,
                    website_visits=website_visits,
                    cost=cost,
                    clicks=clicks,
                    conversions=conversions,
                )

                # Parse visit data if available
                visit_data = None
                if any(
                    key in row
                    for key in [
                        "attributed_revenue",
                        "visit_duration_avg",
                        "repeat_visit_rate",
                        "conversion_rate",
                    ]
                ):
                    visit_data = StoreVisitData(
                        store_visits=store_visits,
                        attributed_revenue=self._parse_float(
                            row.get("attributed_revenue")
                        ),
                        visit_duration_avg=self._parse_float(
                            row.get("visit_duration_avg")
                        ),
                        repeat_visit_rate=self._parse_float(
                            row.get("repeat_visit_rate")
                        ),
                        conversion_rate=self._parse_float(row.get("conversion_rate")),
                    )

                location_performance = LocationPerformance(
                    location=location,
                    metrics=metrics,
                    visit_data=visit_data,
                    competitive_index=self._parse_float(row.get("competitive_index")),
                )

                locations.append(location_performance)

            except Exception as e:
                logger.warning(f"Failed to parse location data: {e}, row: {row}")
                continue

        return locations

    def _parse_number(self, value: Any) -> int:
        """Parse a number from CSV, handling commas and string formatting.

        Includes validation to prevent overflow from extremely large numbers.
        """
        if isinstance(value, int):
            if value < 0:
                logger.warning(f"Parsed negative number {value}, returning 0")
                return 0
            return min(value, 2**31 - 1)  # Prevent int overflow
        if isinstance(value, (str, float)):
            try:
                # Remove commas and convert to int via float to preserve precision
                cleaned = str(value).replace(",", "").replace('"', "").strip()
                if not cleaned:  # Handle empty strings after cleaning
                    return 0

                parsed_float = float(cleaned)

                # Validate reasonable business ranges to prevent overflow
                if parsed_float > 2**31 - 1:  # Max 32-bit signed int
                    logger.warning(
                        f"Parsed number {parsed_float} exceeds maximum allowed value, capping at max int"
                    )
                    return 2**31 - 1
                if parsed_float < 0:  # Negative values don't make sense for metrics
                    logger.warning(
                        f"Parsed negative number {parsed_float}, returning 0"
                    )
                    return 0

                return int(parsed_float)
            except (ValueError, AttributeError, OverflowError):
                return 0
        return 0

    def _parse_float(self, value: Any) -> float | None:
        """Parse a float from CSV, handling commas and string formatting."""
        if value is None or value == "":
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                cleaned = value.replace(",", "").replace('"', "").strip()
                if not cleaned:  # Handle empty strings after cleaning
                    return None
                return float(cleaned)
            except (ValueError, AttributeError):
                return None
        return None

    def _categorize_efficiency(
        self, location: LocationPerformance
    ) -> LocalReachEfficiencyLevel:
        """Categorize location efficiency based on multiple metrics."""
        visit_rate = location.metrics.store_visit_rate
        engagement_rate = location.metrics.local_engagement_rate
        cost_per_visit = location.metrics.cost_per_store_visit

        # Determine efficiency level based on multiple factors
        score = 0

        # Store visit rate scoring
        if visit_rate >= self.high_visit_rate_threshold:
            score += 3
        elif visit_rate >= self.moderate_visit_rate_threshold:
            score += 2
        elif visit_rate >= self.low_visit_rate_threshold:
            score += 1

        # Engagement rate scoring
        if engagement_rate >= self.EXCELLENT_ENGAGEMENT_THRESHOLD:
            score += 3
        elif engagement_rate >= self.GOOD_ENGAGEMENT_THRESHOLD:
            score += 2
        elif engagement_rate >= self.POOR_ENGAGEMENT_THRESHOLD:
            score += 1

        # Cost efficiency scoring (inverted - lower cost is better)
        if cost_per_visit > 0:
            if cost_per_visit <= self.MODERATE_COST_PER_VISIT_THRESHOLD:
                score += 2
            elif cost_per_visit <= self.high_cost_per_visit_threshold:
                score += 1

        # Categorize based on total score
        if score >= 6:
            return LocalReachEfficiencyLevel.EXCELLENT
        elif score >= 4:
            return LocalReachEfficiencyLevel.GOOD
        elif score >= 2:
            return LocalReachEfficiencyLevel.AVERAGE
        else:
            return LocalReachEfficiencyLevel.POOR

    def _calculate_market_rankings(self, locations: List[LocationPerformance]) -> None:
        """Calculate market rankings for each location."""
        # Sort by performance score for ranking
        sorted_locations = sorted(
            locations, key=lambda x: x.performance_score, reverse=True
        )

        for rank, location in enumerate(sorted_locations, 1):
            location.market_rank = rank

    def _generate_insights(
        self, locations: List[LocationPerformance]
    ) -> List[LocalReachInsight]:
        """Generate insights about local reach performance issues and opportunities.

        Pre-calculates all benchmarks to optimize performance and avoid O(n²) complexity.
        """
        insights = []

        # Pre-calculate all benchmarks once for efficiency
        visit_rates = [loc.metrics.store_visit_rate for loc in locations]
        costs_per_visit = [
            loc.metrics.cost_per_store_visit
            for loc in locations
            if loc.metrics.cost_per_store_visit > 0
        ]
        costs_per_action = [
            loc.metrics.cost_per_local_action
            for loc in locations
            if loc.metrics.cost_per_local_action > 0
        ]

        # Calculate benchmark values once
        avg_visit_rate = statistics.mean(visit_rates) if visit_rates else 0
        avg_cost_per_visit = statistics.mean(costs_per_visit) if costs_per_visit else 0
        avg_cost_per_action = (
            statistics.mean(costs_per_action) if costs_per_action else 0
        )

        # Pre-calculate threshold values for efficiency
        high_traffic_threshold = 10000
        low_impression_threshold = 500
        underutilized_visit_rate_threshold = avg_visit_rate * 0.7
        inefficient_spend_threshold = avg_cost_per_action * 1.5

        for location in locations:
            store_name = location.location.store_name

            # Low store visit rate
            if location.metrics.store_visit_rate < self.low_visit_rate_threshold:
                insights.append(
                    LocalReachInsight(
                        store_name=store_name,
                        issue_type=LocalReachIssueType.LOW_STORE_VISIT_RATE,
                        description=f"Store visit rate of {location.metrics.store_visit_rate:.2f}% is below optimal threshold",
                        impact="Missing potential foot traffic and in-store conversions",
                        recommendation="Optimize location extensions, review local keyword targeting, and improve ad relevance",
                        priority="high",
                        potential_improvement=f"Could increase visits by targeting {self.moderate_visit_rate_threshold:.1f}% rate",
                        estimated_impact=f"Potential {int(location.metrics.local_impressions * (self.moderate_visit_rate_threshold - location.metrics.store_visit_rate) / 100)} additional visits",
                    )
                )

            # High cost per visit
            if (
                location.metrics.cost_per_store_visit
                > self.high_cost_per_visit_threshold
            ):
                insights.append(
                    LocalReachInsight(
                        store_name=store_name,
                        issue_type=LocalReachIssueType.HIGH_COST_PER_VISIT,
                        description=f"Cost per store visit of ${location.metrics.cost_per_store_visit:.2f} exceeds efficiency threshold",
                        impact="Inefficient budget allocation reducing overall ROI",
                        recommendation="Review bidding strategy, negative keywords, and location targeting radius",
                        priority="critical"
                        if location.metrics.cost_per_store_visit > 35
                        else "high",
                        potential_improvement=f"Target cost below ${self.MODERATE_COST_PER_VISIT_THRESHOLD}",
                        estimated_impact=f"Could save ${(location.metrics.cost_per_store_visit - self.MODERATE_COST_PER_VISIT_THRESHOLD) * location.metrics.store_visits:.0f} monthly",
                    )
                )

            # Poor local reach (low impressions)
            if location.metrics.local_impressions < low_impression_threshold:
                insights.append(
                    LocalReachInsight(
                        store_name=store_name,
                        issue_type=LocalReachIssueType.POOR_LOCAL_REACH,
                        description=f"Low local impression volume of {location.metrics.local_impressions:,}",
                        impact="Limited visibility in local searches reduces potential customer reach",
                        recommendation="Expand geographic targeting radius and enhance local keyword coverage",
                        priority="medium",
                        potential_improvement="Increase targeting radius or keyword coverage",
                        estimated_impact="Could double local impression volume",
                    )
                )

            # Underutilized high-traffic location
            if (
                location.metrics.local_impressions > high_traffic_threshold
                and location.metrics.store_visit_rate
                < underutilized_visit_rate_threshold
            ):
                insights.append(
                    LocalReachInsight(
                        store_name=store_name,
                        issue_type=LocalReachIssueType.UNDERUTILIZED_LOCATION,
                        description=f"High traffic location with suboptimal {location.metrics.store_visit_rate:.2f}% visit rate",
                        impact="Missing significant store visit opportunities from high impression volume",
                        recommendation="Optimize ad copy for local intent, improve store information accuracy, and enhance local offerings messaging",
                        priority="high",
                        potential_improvement=f"Could achieve {avg_visit_rate:.1f}% visit rate benchmark",
                        estimated_impact=f"Potential {int(location.metrics.local_impressions * (avg_visit_rate - location.metrics.store_visit_rate) / 100)} additional visits",
                    )
                )

            # Inefficient spend detection
            if (
                location.metrics.cost_per_local_action > 0
                and location.metrics.cost_per_local_action > inefficient_spend_threshold
            ):
                insights.append(
                    LocalReachInsight(
                        store_name=store_name,
                        issue_type=LocalReachIssueType.INEFFICIENT_SPEND,
                        description=f"Cost per local action of ${location.metrics.cost_per_local_action:.2f} significantly above network average",
                        impact="Budget inefficiency reducing overall campaign performance",
                        recommendation="Review quality score, ad relevance, and competitor analysis for this location",
                        priority="medium",
                        potential_improvement="Optimize to network average efficiency",
                        estimated_impact="Improve cost efficiency by 20-30%",
                    )
                )

        return insights

    def _create_summary(
        self, locations: List[LocationPerformance]
    ) -> LocalReachSummary:
        """Create summary statistics for all locations."""
        total_locations = len(locations)
        total_local_impressions = sum(
            loc.metrics.local_impressions for loc in locations
        )
        total_store_visits = sum(loc.metrics.store_visits for loc in locations)
        total_cost = sum(loc.metrics.cost for loc in locations)

        # Calculate averages
        visit_rates = [
            loc.metrics.store_visit_rate
            for loc in locations
            if loc.metrics.local_impressions > 0
        ]
        avg_store_visit_rate = statistics.mean(visit_rates) if visit_rates else 0.0

        costs_per_visit = [
            loc.metrics.cost_per_store_visit
            for loc in locations
            if loc.metrics.cost_per_store_visit > 0
        ]
        avg_cost_per_visit = (
            statistics.mean(costs_per_visit) if costs_per_visit else 0.0
        )

        # Count performance categories
        high_performers = len([loc for loc in locations if loc.is_high_performer])
        underperformers = len([loc for loc in locations if loc.is_underperformer])
        locations_needing_optimization = len(
            [loc for loc in locations if loc.needs_optimization]
        )

        return LocalReachSummary(
            total_locations=total_locations,
            total_local_impressions=total_local_impressions,
            total_store_visits=total_store_visits,
            total_cost=total_cost,
            avg_store_visit_rate=avg_store_visit_rate,
            avg_cost_per_visit=avg_cost_per_visit,
            high_performers=high_performers,
            underperformers=underperformers,
            locations_needing_optimization=locations_needing_optimization,
        )

    def _create_empty_result(
        self, customer_id: str, start_date: datetime, end_date: datetime
    ) -> LocalReachAnalysisResult:
        """Create an empty result when no data is available."""
        return LocalReachAnalysisResult(
            customer_id=customer_id,
            analysis_type="local_reach_store_performance",
            analyzer_name=self.get_name(),
            start_date=start_date,
            end_date=end_date,
            summary=LocalReachSummary(),
            location_performance=[],
            insights=[],
            top_performers=[],
            underperformers=[],
            optimization_opportunities=[],
        )
