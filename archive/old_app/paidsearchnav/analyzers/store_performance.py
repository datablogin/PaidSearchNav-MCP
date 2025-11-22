"""Store performance analyzer for local metrics optimization."""

import logging
import statistics
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Union

from paidsearchnav.core.interfaces import Analyzer
from paidsearchnav.core.models import (
    StoreInsight,
    StoreIssueType,
    StoreLocationData,
    StoreMetrics,
    StorePerformanceAnalysisResult,
    StorePerformanceData,
    StorePerformanceLevel,
    StorePerformanceSummary,
)
from paidsearchnav.parsers.store_csv_parser import StoreCSVParser

# Type alias for store CSV data
StoreCSVData = List[Dict[str, Any]]

logger = logging.getLogger(__name__)


class StorePerformanceAnalyzer(Analyzer):
    """Analyzes store-level performance to identify local optimization opportunities."""

    # Business logic thresholds
    MIN_IMPRESSIONS_THRESHOLD = 100  # Minimum impressions to consider for analysis
    HIGH_ENGAGEMENT_THRESHOLD = 3.0  # 3% engagement rate for high performers
    MODERATE_ENGAGEMENT_THRESHOLD = 1.5  # 1.5% engagement rate for moderate performers
    LOW_ENGAGEMENT_THRESHOLD = 0.5  # 0.5% engagement rate threshold
    CALL_TRACKING_ISSUE_THRESHOLD = 0  # Zero call clicks with phone number

    def __init__(
        self,
        min_impressions: int = 100,
        high_engagement_threshold: float = 3.0,
        moderate_engagement_threshold: float = 1.5,
        low_engagement_threshold: float = 0.5,
    ):
        """Initialize the store performance analyzer.

        Args:
            min_impressions: Minimum impressions required for meaningful analysis
            high_engagement_threshold: Engagement rate threshold for high performers (%)
            moderate_engagement_threshold: Engagement rate threshold for moderate performers (%)
            low_engagement_threshold: Engagement rate threshold for low performers (%)
        """
        self.min_impressions = min_impressions
        self.high_engagement_threshold = high_engagement_threshold
        self.moderate_engagement_threshold = moderate_engagement_threshold
        self.low_engagement_threshold = low_engagement_threshold
        self._csv_data: StoreCSVData = []

    def get_name(self) -> str:
        """Get analyzer name."""
        return "Store Performance Analyzer"

    def get_description(self) -> str:
        """Get analyzer description."""
        return "Analyzes store-level performance metrics to identify local optimization opportunities, tracking issues, and performance gaps across physical retail locations."

    @classmethod
    def from_csv(
        cls, file_path: Union[str, Path], max_file_size_mb: int = 100
    ) -> "StorePerformanceAnalyzer":
        """Create a StorePerformanceAnalyzer instance from a CSV file.

        Parses Google Ads per-store CSV report and prepares data for analysis.

        Args:
            file_path: Path to the store performance CSV file
            max_file_size_mb: Maximum allowed file size in MB (default: 100)

        Returns:
            StorePerformanceAnalyzer instance with loaded data

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
    ) -> StorePerformanceAnalysisResult:
        """Analyze store performance data and generate insights.

        Args:
            customer_id: Google Ads customer ID
            start_date: Analysis start date
            end_date: Analysis end date
            **kwargs: Additional arguments, expects 'csv_data' for per_store report

        Returns:
            StorePerformanceAnalysisResult with analysis findings
        """
        # Validate inputs
        if not customer_id or not customer_id.strip():
            raise ValueError("customer_id is required and cannot be empty")

        if start_date >= end_date:
            raise ValueError("start_date must be before end_date")

        logger.info(
            f"Starting store performance analysis for customer {customer_id} "
            f"from {start_date} to {end_date}"
        )

        # Get store performance data from kwargs or use pre-loaded CSV data
        csv_data = kwargs.get("csv_data", self._csv_data)
        if not csv_data:
            raise ValueError("csv_data is required for store performance analysis")

        if not csv_data:  # Empty list
            logger.warning("No CSV data provided for analysis")
            return self._create_empty_result(customer_id, start_date, end_date)

        # Parse the CSV data into store performance data
        store_data = self._parse_store_data(csv_data)

        # Filter stores with sufficient data
        filtered_stores = [
            store
            for store in store_data
            if store.metrics.local_impressions >= self.min_impressions
        ]

        if not filtered_stores:
            logger.warning("No stores found with sufficient data for analysis")
            return self._create_empty_result(customer_id, start_date, end_date)

        # Categorize stores by performance
        for store in filtered_stores:
            store.performance_level = self._categorize_performance(store)

        # Generate insights
        insights = self._generate_insights(filtered_stores)

        # Create summary
        summary = self._create_summary(filtered_stores)

        # Identify top performers and underperformers
        top_performers = [
            store
            for store in filtered_stores
            if store.performance_level == StorePerformanceLevel.HIGH_PERFORMER
        ]
        underperformers = [
            store
            for store in filtered_stores
            if store.performance_level == StorePerformanceLevel.UNDERPERFORMER
        ]

        # Sort by engagement rate
        top_performers.sort(key=lambda x: x.metrics.engagement_rate, reverse=True)
        underperformers.sort(key=lambda x: x.metrics.engagement_rate)

        return StorePerformanceAnalysisResult(
            customer_id=customer_id,
            analysis_type="store_performance",
            analyzer_name=self.get_name(),
            start_date=start_date,
            end_date=end_date,
            summary=summary,
            store_data=filtered_stores,
            insights=insights,
            top_performers=top_performers[:10],  # Top 10 performers
            underperformers=underperformers[:10],  # Bottom 10 performers
        )

    def _parse_store_data(
        self, csv_data: List[Dict[str, Any]]
    ) -> List[StorePerformanceData]:
        """Parse CSV data into StorePerformanceData objects."""
        stores = []
        required_fields = ["store_name", "local_impressions"]

        for row in csv_data:
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
                location = StoreLocationData(
                    store_name=row.get("store_name", "Unknown Store"),
                    address_line_1=row.get("address_line_1", ""),
                    address_line_2=row.get("address_line_2"),
                    city=row.get("city", ""),
                    state=row.get("state", ""),
                    postal_code=StoreCSVParser.safe_str_cast(row.get("postal_code")),
                    country_code=row.get("country_code", "US"),
                    phone_number=row.get("phone_number"),
                )

                # Parse metrics (already validated by shared utility)
                local_impressions = row.get("local_impressions", 0)
                store_visits = row.get("store_visits", 0)
                call_clicks = row.get("call_clicks", 0)
                driving_directions = row.get("driving_directions", 0)
                website_visits = row.get("website_visits", 0)

                metrics = StoreMetrics(
                    local_impressions=local_impressions,
                    store_visits=store_visits,
                    call_clicks=call_clicks,
                    driving_directions=driving_directions,
                    website_visits=website_visits,
                )

                store = StorePerformanceData(
                    location=location,
                    metrics=metrics,
                    performance_level=StorePerformanceLevel.MODERATE_PERFORMER,  # Will be updated
                )

                stores.append(store)

            except Exception as e:
                logger.warning(f"Failed to parse store data: {e}, row: {row}")
                continue

        return stores

    def _parse_number(self, value: Any) -> int:
        """Parse a number from CSV, handling commas and string formatting."""
        if isinstance(value, int):
            return value
        if isinstance(value, (str, float)):
            try:
                # Remove commas and convert to int via float to preserve precision
                return int(float(str(value).replace(",", "")))
            except (ValueError, AttributeError):
                return 0
        return 0

    def _categorize_performance(
        self, store: StorePerformanceData
    ) -> StorePerformanceLevel:
        """Categorize store performance based on engagement rate."""
        engagement_rate = store.metrics.engagement_rate

        if engagement_rate >= self.high_engagement_threshold:
            return StorePerformanceLevel.HIGH_PERFORMER
        elif engagement_rate >= self.moderate_engagement_threshold:
            return StorePerformanceLevel.MODERATE_PERFORMER
        elif engagement_rate >= self.low_engagement_threshold:
            return StorePerformanceLevel.LOW_PERFORMER
        else:
            return StorePerformanceLevel.UNDERPERFORMER

    def _generate_insights(
        self, stores: List[StorePerformanceData]
    ) -> List[StoreInsight]:
        """Generate insights about store performance issues and opportunities."""
        insights = []

        for store in stores:
            # Check for call tracking issues
            if store.has_call_tracking_issue:
                insights.append(
                    StoreInsight(
                        store_name=store.location.store_name,
                        issue_type=StoreIssueType.MISSING_CALL_TRACKING,
                        description=f"Store has {store.metrics.local_impressions:,} local impressions but zero call clicks despite having a phone number",
                        impact="Missing potential phone leads from local searches",
                        recommendation="Verify call tracking setup and call extensions configuration",
                        priority="high",
                    )
                )

            # Check for low engagement
            if store.has_low_engagement:
                insights.append(
                    StoreInsight(
                        store_name=store.location.store_name,
                        issue_type=StoreIssueType.LOW_ENGAGEMENT,
                        description=f"Store has {store.metrics.engagement_rate:.2f}% engagement rate, below optimal levels",
                        impact="Poor conversion of local impressions to actions",
                        recommendation="Review location extensions, store hours, and local listing accuracy",
                        priority="medium",
                    )
                )

            # Check for missing driving directions
            if (
                store.metrics.local_impressions > 500
                and store.metrics.driving_directions == 0
            ):
                insights.append(
                    StoreInsight(
                        store_name=store.location.store_name,
                        issue_type=StoreIssueType.NO_DRIVING_DIRECTIONS,
                        description="Store receives local impressions but no driving direction requests",
                        impact="Potential missed foot traffic and in-store visits",
                        recommendation="Optimize location extensions and ensure accurate address information",
                        priority="medium",
                    )
                )

            # Check for poor local reach
            if (
                store.metrics.local_impressions < 100
                and store.performance_level == StorePerformanceLevel.UNDERPERFORMER
            ):
                insights.append(
                    StoreInsight(
                        store_name=store.location.store_name,
                        issue_type=StoreIssueType.POOR_LOCAL_REACH,
                        description="Store has very low local impression volume",
                        impact="Limited visibility in local searches",
                        recommendation="Expand location targeting radius and review local keyword strategy",
                        priority="high",
                    )
                )

        return insights

    def _create_summary(
        self, stores: List[StorePerformanceData]
    ) -> StorePerformanceSummary:
        """Create summary statistics for all stores."""
        total_stores = len(stores)
        total_local_impressions = sum(
            store.metrics.local_impressions for store in stores
        )
        total_engagements = sum(store.metrics.total_engagements for store in stores)

        engagement_rates = [
            store.metrics.engagement_rate
            for store in stores
            if store.metrics.local_impressions > 0
        ]
        avg_engagement_rate = (
            statistics.mean(engagement_rates) if engagement_rates else 0.0
        )

        stores_with_issues = len(
            [
                store
                for store in stores
                if store.has_call_tracking_issue or store.has_low_engagement
            ]
        )

        high_performers = len(
            [
                store
                for store in stores
                if store.performance_level == StorePerformanceLevel.HIGH_PERFORMER
            ]
        )

        low_performers = len(
            [
                store
                for store in stores
                if store.performance_level
                in [
                    StorePerformanceLevel.LOW_PERFORMER,
                    StorePerformanceLevel.UNDERPERFORMER,
                ]
            ]
        )

        return StorePerformanceSummary(
            total_stores=total_stores,
            total_local_impressions=total_local_impressions,
            total_engagements=total_engagements,
            avg_engagement_rate=avg_engagement_rate,
            stores_with_issues=stores_with_issues,
            high_performers=high_performers,
            low_performers=low_performers,
        )

    def _create_empty_result(
        self, customer_id: str, start_date: datetime, end_date: datetime
    ) -> StorePerformanceAnalysisResult:
        """Create an empty result when no data is available."""
        return StorePerformanceAnalysisResult(
            customer_id=customer_id,
            analysis_type="store_performance",
            analyzer_name=self.get_name(),
            start_date=start_date,
            end_date=end_date,
            summary=StorePerformanceSummary(
                total_stores=0,
                total_local_impressions=0,
                total_engagements=0,
                avg_engagement_rate=0.0,
                stores_with_issues=0,
                high_performers=0,
                low_performers=0,
            ),
            store_data=[],
            insights=[],
            top_performers=[],
            underperformers=[],
        )
