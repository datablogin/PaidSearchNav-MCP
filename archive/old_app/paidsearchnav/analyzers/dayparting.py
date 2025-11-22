"""Dayparting analyzer for ad schedule optimization."""

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
from paidsearchnav.platforms.google import AdSchedulePerformance
from paidsearchnav.platforms.google.client import GoogleAdsAPIClient

logger = logging.getLogger(__name__)


class DaypartingAnalysisResult(AnalysisResult):
    """Result of dayparting/ad schedule analysis."""

    # Analysis data
    schedule_data: list[AdSchedulePerformance] = []
    day_performance: dict[str, dict[str, float]] = {}
    hour_performance: dict[str, dict[str, float]] = {}

    # Summary metrics
    best_performing_days: list[dict[str, Any]] = []
    worst_performing_days: list[dict[str, Any]] = []
    best_performing_hours: list[dict[str, Any]] = []
    worst_performing_hours: list[dict[str, Any]] = []

    # Variance metrics
    conversion_rate_variance_by_day: float = 0.0
    conversion_rate_variance_by_hour: float = 0.0
    cost_efficiency_variance: float = 0.0

    # Recommendations
    bid_adjustment_recommendations: list[dict[str, Any]] = []
    schedule_expansion_recommendations: list[str] = []
    schedule_reduction_recommendations: list[str] = []

    # Potential improvements
    potential_savings: float = 0.0
    potential_conversion_increase: float = 0.0


class DaypartingAnalyzer(Analyzer):
    """Analyzes ad schedule data to identify optimal times for ad delivery."""

    # Configuration thresholds
    WORST_PERFORMER_THRESHOLD = 0.7  # 70% of best performer
    PAUSE_THRESHOLD = -0.5  # 50% below average
    MAX_BID_ADJUSTMENT = 30  # Maximum positive bid adjustment %
    MIN_BID_ADJUSTMENT = -50  # Maximum negative bid adjustment %
    HIGH_VARIANCE_THRESHOLD = 0.02  # 2% variance threshold
    POTENTIAL_SAVINGS_FACTOR = 0.5  # Assume 50% reduction in low performer cost
    POTENTIAL_CONVERSION_INCREASE_FACTOR = 0.2  # Assume 20% increase in conversions

    def __init__(
        self,
        api_client: Optional[GoogleAdsAPIClient] = None,
        min_impressions: int = 100,
        min_conversions: int = 5,
        performance_threshold: float = 0.2,  # 20% deviation from average
        significance_threshold: float = 0.05,  # 5% of total metrics
    ):
        """Initialize the dayparting analyzer.

        Args:
            api_client: Google Ads API client (optional for CSV-based analysis)
            min_impressions: Minimum impressions for analysis
            min_conversions: Minimum conversions for significance
            performance_threshold: Threshold for high/low performers
            significance_threshold: Minimum share for consideration
        """
        self.api_client = api_client
        self.min_impressions = min_impressions
        self.min_conversions = min_conversions
        self.performance_threshold = performance_threshold
        self.significance_threshold = significance_threshold
        self._csv_data: Optional[list[AdSchedulePerformance]] = None

    @classmethod
    def from_csv(
        cls, file_path: Union[str, Path], max_file_size_mb: int = 100
    ) -> "DaypartingAnalyzer":
        """Create a DaypartingAnalyzer instance from a CSV file.

        Parses Google Ads Ad Schedule CSV report and prepares data for analysis.

        Note: This method creates a new analyzer instance with CSV data stored internally.
        Instances should not be shared across threads as the internal CSV data storage
        is not thread-safe.

        Args:
            file_path: Path to the ad schedule CSV file
            max_file_size_mb: Maximum allowed file size in MB (default: 100)

        Returns:
            DaypartingAnalyzer instance with loaded data

        Raises:
            FileNotFoundError: If the CSV file doesn't exist
            ValueError: If the CSV format is invalid, missing required columns, or file too large
            PermissionError: If the file path attempts directory traversal
        """
        file_path = Path(file_path) if isinstance(file_path, str) else file_path

        # Resolve to absolute path for security
        file_path = file_path.resolve()

        # Path traversal protection - ensure file is not outside current directory tree
        # Allow files in the project directory or temp directories
        cwd = Path.cwd()
        temp_dir = Path("/tmp")
        if not (file_path.is_relative_to(cwd) or file_path.is_relative_to(temp_dir)):
            # Also allow common test temp directories
            import tempfile

            temp_root = Path(tempfile.gettempdir())
            if not file_path.is_relative_to(temp_root):
                raise PermissionError(
                    f"File path outside allowed directories: {file_path}"
                )

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

        def parse_percentage(value: Any) -> Optional[float]:
            """Parse percentage string to float."""
            if pd.isna(value) or value == "--" or value == "":
                return None
            if isinstance(value, str):
                # Remove percentage sign and convert
                value_str = value.strip().rstrip("%")
                # Handle bid adjustments with + or - signs
                if value_str.startswith("+"):
                    value_str = value_str[1:]
                try:
                    return float(value_str) / 100
                except (ValueError, TypeError):
                    return None
            try:
                return float(value) if value else None
            except (ValueError, TypeError):
                return None

        def parse_number(value: Any, is_currency: bool = False) -> float:
            """Parse number string to float, handling commas and currency."""
            if pd.isna(value) or value == "--" or value == "":
                return 0.0
            if isinstance(value, str):
                # Remove commas and quotes
                value_str = value.strip().replace(",", "").replace('"', "")

                # Remove currency symbols if is_currency is True
                if is_currency:
                    # Common currency symbols to remove
                    currency_symbols = ["$", "€", "£", "¥", "₹", "₽", "¢"]
                    for symbol in currency_symbols:
                        value_str = value_str.replace(symbol, "")
                    value_str = value_str.strip()

                try:
                    result = float(value_str)
                    # Validate non-negative for metrics that shouldn't be negative
                    if result < 0 and is_currency:
                        logger.warning(
                            f"Negative currency value found: {result}, using 0"
                        )
                        return 0.0
                    return result
                except (ValueError, TypeError):
                    return 0.0
            try:
                result = float(value) if value else 0.0
                if result < 0 and is_currency:
                    logger.warning(f"Negative currency value found: {result}, using 0")
                    return 0.0
                return result
            except (ValueError, TypeError):
                return 0.0

        def parse_time_string(
            day_time: str,
        ) -> tuple[str, Optional[str], Optional[str]]:
            """Parse day and time string to extract day, start time, and end time."""
            if not day_time:
                return "", None, None

            # Remove quotes if present
            day_time = day_time.strip().strip('"')

            # Check for "all day" patterns
            if "all day" in day_time.lower():
                day_part = (
                    day_time.replace(", all day", "").replace("all day", "").strip()
                )
                # Remove 's' from days (e.g., "Saturdays" -> "Saturday")
                if day_part.endswith("s"):
                    day_part = day_part[:-1]
                return day_part, None, None

            # Split by comma to separate day from time
            parts = day_time.split(",", 1)
            if len(parts) == 1:
                # No time specified, just day
                day = parts[0].strip()
                if day.endswith("s"):
                    day = day[:-1]
                return day, None, None

            day = parts[0].strip()
            # Remove 's' from days (e.g., "Mondays" -> "Monday")
            if day.endswith("s"):
                day = day[:-1]

            time_part = parts[1].strip()

            # Parse time range (e.g., "8:00 AM - 6:00 PM" or "08:00 - 18:00")
            if " - " in time_part or "-" in time_part:
                # Handle both " - " and "-" as separators
                if " - " in time_part:
                    time_parts = time_part.split(" - ")
                else:
                    time_parts = time_part.split("-")

                if len(time_parts) == 2:
                    start_time = time_parts[0].strip()
                    end_time = time_parts[1].strip()

                    # Normalize 24-hour format to 12-hour format for consistency
                    start_time = normalize_time_format(start_time)
                    end_time = normalize_time_format(end_time)

                    return day, start_time, end_time

            return day, None, None

        def normalize_time_format(time_str: str) -> str:
            """Convert 24-hour format to 12-hour format if needed."""
            if not time_str:
                return time_str

            # Check if it's already in 12-hour format (contains AM/PM)
            if "AM" in time_str.upper() or "PM" in time_str.upper():
                return time_str

            # Try to parse as 24-hour format
            try:
                # Handle formats like "14:00" or "14:30"
                if ":" in time_str:
                    hour_str, minute_str = time_str.split(":", 1)
                    hour = int(hour_str)

                    if hour == 0:
                        return f"12:{minute_str} AM"
                    elif hour < 12:
                        return f"{hour}:{minute_str} AM"
                    elif hour == 12:
                        return f"12:{minute_str} PM"
                    else:
                        return f"{hour - 12}:{minute_str} PM"
            except (ValueError, TypeError):
                pass

            # Return original if we can't parse it
            return time_str

        try:
            # Efficiently determine number of rows to skip by reading only first few lines
            skip_rows = 0
            with open(file_path, "r", encoding="utf-8") as f:
                # Read only first 20 lines to find header
                for i, line in enumerate(f):
                    if i >= 20:  # Limit search to first 20 lines
                        break
                    # Look for the header row with actual column names
                    if "Day & time" in line or "Day and time" in line:
                        skip_rows = i
                        break
                    # Also check for common report header patterns
                    if (
                        line.startswith("#")
                        or "Downloaded from" in line
                        or "Account:" in line
                    ):
                        continue
                    # If we see actual data columns, we've gone too far
                    if any(
                        col in line for col in ["Campaign", "Bid adj", "Impr", "Cost"]
                    ):
                        skip_rows = max(0, i - 1)
                        break

            # Read CSV with determined skip rows - pandas handles the file efficiently
            df = pd.read_csv(file_path, skiprows=skip_rows, encoding="utf-8")

            # Handle different possible column name formats
            column_mappings = {
                "Day & time": ["Day & time", "Day and time", "Day/time"],
                "Campaign": ["Campaign", "Campaign name"],
                "Bid adj.": ["Bid adj.", "Bid adjustment", "Bid adj"],
                "Impressions": ["Impr.", "Impressions", "Impr"],
                "Clicks": ["Interactions", "Clicks"],
                "Cost": ["Cost"],
                "Conversions": ["Conversions", "Conv."],
                "Conv. rate": ["Conv. rate", "Conversion rate"],
                "Cost / conv.": ["Cost / conv.", "Cost/conv.", "CPA"],
            }

            # Normalize column names
            normalized_columns = {}
            for standard_name, variations in column_mappings.items():
                for col in df.columns:
                    if any(var in col for var in variations):
                        normalized_columns[col] = standard_name
                        break

            # Rename columns to standard names
            df.rename(columns=normalized_columns, inplace=True)

            # Check for required columns
            required_columns = ["Day & time"]
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                raise ValueError(
                    f"CSV missing required columns: {missing_columns}. Found columns: {list(df.columns)}"
                )

            # Parse the CSV data into AdSchedulePerformance objects
            schedule_data = []

            for _, row in df.iterrows():
                # Parse day and time
                day_time_str = str(row.get("Day & time", ""))
                day_of_week, start_time, end_time = parse_time_string(day_time_str)

                # Skip empty rows
                if not day_of_week:
                    continue

                # Create hour range string if we have times
                hour_range = None
                if start_time and end_time:
                    hour_range = f"{start_time} - {end_time}"

                # Parse metrics with validation
                impressions = int(parse_number(row.get("Impressions", 0)))
                clicks = int(parse_number(row.get("Clicks", 0)))
                cost = parse_number(row.get("Cost", 0), is_currency=True)
                conversions = parse_number(row.get("Conversions", 0))

                # Validate non-negative values
                if impressions < 0:
                    logger.warning(
                        f"Negative impressions ({impressions}) for {day_time_str}, setting to 0"
                    )
                    impressions = 0
                if clicks < 0:
                    logger.warning(
                        f"Negative clicks ({clicks}) for {day_time_str}, setting to 0"
                    )
                    clicks = 0
                if conversions < 0:
                    logger.warning(
                        f"Negative conversions ({conversions}) for {day_time_str}, setting to 0"
                    )
                    conversions = 0.0

                # Calculate derived metrics
                ctr = clicks / impressions if impressions > 0 else 0.0
                avg_cpc = cost / clicks if clicks > 0 else 0.0
                conversion_rate = conversions / clicks if clicks > 0 else 0.0
                cpa = cost / conversions if conversions > 0 else 0.0

                # Parse bid adjustment
                bid_adj_value = row.get("Bid adj.", "--")
                bid_adjustment = parse_percentage(bid_adj_value)

                schedule_perf = AdSchedulePerformance(
                    day_time=day_time_str,
                    day_of_week=day_of_week,
                    hour_range=hour_range,
                    bid_adjustment=bid_adjustment,
                    clicks=clicks,
                    impressions=impressions,
                    ctr=ctr,
                    avg_cpc=avg_cpc,
                    cost=cost,
                    conversions=conversions,
                    conversion_rate=conversion_rate,
                    cpa=cpa,
                    currency_code=row.get("Currency code", "USD"),
                    campaign_name=row.get("Campaign"),
                    campaign_id=None,  # Not typically in CSV exports
                )

                schedule_data.append(schedule_perf)

            if not schedule_data:
                raise ValueError("No valid ad schedule data found in CSV")

            # Create analyzer instance
            analyzer = cls()

            # Store the parsed data for later use in analyze()
            analyzer._csv_data = schedule_data

            logger.info(
                f"Loaded {len(schedule_data)} ad schedule records from CSV: {file_path}"
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
            # Preserve original exception type and context
            if isinstance(e, (ValueError, FileNotFoundError, PermissionError)):
                raise
            raise ValueError(
                f"Unexpected error parsing CSV file {file_path}: {type(e).__name__}: {str(e)}"
            ) from e

    async def analyze(
        self,
        customer_id: str,
        start_date: datetime,
        end_date: datetime,
        **kwargs: Any,
    ) -> DaypartingAnalysisResult:
        """Analyze ad schedule performance for optimization opportunities.

        Args:
            customer_id: Google Ads customer ID
            start_date: Start date for analysis
            end_date: End date for analysis
            **kwargs: Additional parameters (campaign_ids, timezone)

        Returns:
            Dayparting analysis result
        """
        logger.info(f"Starting dayparting analysis for customer {customer_id}")

        campaign_ids = kwargs.get("campaign_ids")
        timezone = kwargs.get("timezone", "UTC")

        try:
            # Use CSV data if loaded, otherwise fetch from API
            if self._csv_data is not None:
                schedule_data = self._csv_data
                logger.info(f"Using {len(schedule_data)} records from CSV data")
            elif self.api_client:
                # Fetch ad schedule performance data
                schedule_data_raw = await self.api_client.get_ad_schedule_performance(
                    customer_id=customer_id,
                    start_date=start_date,
                    end_date=end_date,
                    campaign_ids=campaign_ids,
                )

                # Convert to structured data
                schedule_data = self._convert_to_schedule_data(schedule_data_raw)
            else:
                logger.warning("No data source available (neither CSV nor API client)")
                schedule_data = []

            # Filter by minimum thresholds
            filtered_data = self._filter_schedule_data(schedule_data)

            # Analyze by day of week
            day_performance = self._analyze_day_performance(filtered_data)

            # Analyze by hour (if available)
            hour_performance = self._analyze_hour_performance(filtered_data)

            # Calculate variance metrics
            variance_metrics = self._calculate_variance_metrics(
                day_performance, hour_performance
            )

            # Identify best and worst performers
            performers = self._identify_performers(day_performance, hour_performance)

            # Generate recommendations
            recommendations = self._generate_recommendations(
                day_performance, hour_performance, variance_metrics
            )

            # Calculate potential improvements
            improvements = self._calculate_potential_improvements(
                filtered_data, day_performance, hour_performance
            )

            # Create result
            result = self._create_analysis_result(
                customer_id=customer_id,
                start_date=start_date,
                end_date=end_date,
                filtered_data=filtered_data,
                day_performance=day_performance,
                hour_performance=hour_performance,
                performers=performers,
                variance_metrics=variance_metrics,
                recommendations=recommendations,
                improvements=improvements,
            )

            logger.info(
                f"Dayparting analysis completed with {len(result.recommendations)} recommendations"
            )
            return result

        except Exception as ex:
            logger.error(f"Dayparting analysis failed: {ex}")
            raise

    def _convert_to_schedule_data(
        self, raw_data: list[dict[str, Any]]
    ) -> list[AdSchedulePerformance]:
        """Convert raw API data to structured schedule performance data."""
        schedule_data = []

        for row in raw_data:
            # Parse day_time field to extract day and hour
            day_time = row.get("day_time", "")
            day_of_week, hour_range = self._parse_day_time(day_time)

            schedule_perf = AdSchedulePerformance(
                day_time=day_time,
                day_of_week=day_of_week,
                hour_range=hour_range,
                bid_adjustment=row.get("bid_adjustment"),
                clicks=row.get("clicks", 0),
                impressions=row.get("impressions", 0),
                ctr=row.get("ctr"),
                avg_cpc=row.get("avg_cpc"),
                cost=row.get("cost", 0.0),
                conversions=row.get("conversions", 0.0),
                conversion_rate=row.get("conversion_rate"),
                cpa=row.get("cpa"),
                currency_code=row.get("currency_code", "USD"),
                campaign_name=row.get("campaign_name"),
                campaign_id=row.get("campaign_id"),
            )

            schedule_data.append(schedule_perf)

        return schedule_data

    def _parse_day_time(self, day_time: str) -> tuple[str, str | None]:
        """Parse day_time string to extract day and hour range."""
        # Example formats:
        # "Monday, 12:00 AM - 1:00 AM"
        # "Tuesday"
        # "Wednesday, All hours"

        if not day_time:
            return "", None

        parts = day_time.split(",", 1)
        day_of_week = parts[0].strip()

        if len(parts) > 1:
            time_part = parts[1].strip()
            if time_part.lower() == "all hours" or time_part.lower() == "all day":
                hour_range = None
            else:
                hour_range = time_part
        else:
            hour_range = None

        return day_of_week, hour_range

    def _filter_schedule_data(
        self, data: list[AdSchedulePerformance]
    ) -> list[AdSchedulePerformance]:
        """Filter schedule data by minimum thresholds."""
        return [d for d in data if d.impressions >= self.min_impressions]

    def _analyze_day_performance(
        self, data: list[AdSchedulePerformance]
    ) -> dict[str, dict[str, float]]:
        """Analyze performance by day of week."""
        day_metrics: dict[str, dict[str, Any]] = defaultdict(
            lambda: {
                "impressions": 0,
                "clicks": 0,
                "conversions": 0.0,
                "cost": 0.0,
                "campaigns": set(),
            }
        )

        for d in data:
            if d.day_of_week:
                metrics = day_metrics[d.day_of_week]
                metrics["impressions"] += d.impressions
                metrics["clicks"] += d.clicks
                metrics["conversions"] += d.conversions
                metrics["cost"] += d.cost
                if d.campaign_id:
                    metrics["campaigns"].add(d.campaign_id)

        # Calculate derived metrics
        day_performance = {}
        for day, metrics in day_metrics.items():
            if metrics["clicks"] > 0:
                day_performance[day] = {
                    "impressions": metrics["impressions"],
                    "clicks": metrics["clicks"],
                    "conversions": metrics["conversions"],
                    "cost": metrics["cost"],
                    "ctr": metrics["clicks"] / metrics["impressions"]
                    if metrics["impressions"] > 0
                    else 0,
                    "conversion_rate": metrics["conversions"] / metrics["clicks"],
                    "cpa": metrics["cost"] / metrics["conversions"]
                    if metrics["conversions"] > 0
                    else 0,
                    "avg_cpc": metrics["cost"] / metrics["clicks"],
                    "campaign_count": len(metrics["campaigns"]),
                }

        return day_performance

    def _analyze_hour_performance(
        self, data: list[AdSchedulePerformance]
    ) -> dict[str, dict[str, float]]:
        """Analyze performance by hour of day."""
        hour_metrics: dict[str, dict[str, Any]] = defaultdict(
            lambda: {
                "impressions": 0,
                "clicks": 0,
                "conversions": 0.0,
                "cost": 0.0,
                "days": set(),
            }
        )

        for d in data:
            if d.hour_range:
                # Extract start hour from range (e.g., "12:00 AM - 1:00 AM" -> "12 AM")
                start_hour = self._extract_start_hour(d.hour_range)
                if start_hour:
                    metrics = hour_metrics[start_hour]
                    metrics["impressions"] += d.impressions
                    metrics["clicks"] += d.clicks
                    metrics["conversions"] += d.conversions
                    metrics["cost"] += d.cost
                    if d.day_of_week:
                        metrics["days"].add(d.day_of_week)

        # Calculate derived metrics
        hour_performance = {}
        for hour, metrics in hour_metrics.items():
            if metrics["clicks"] > 0:
                hour_performance[hour] = {
                    "impressions": metrics["impressions"],
                    "clicks": metrics["clicks"],
                    "conversions": metrics["conversions"],
                    "cost": metrics["cost"],
                    "ctr": metrics["clicks"] / metrics["impressions"]
                    if metrics["impressions"] > 0
                    else 0,
                    "conversion_rate": metrics["conversions"] / metrics["clicks"],
                    "cpa": metrics["cost"] / metrics["conversions"]
                    if metrics["conversions"] > 0
                    else 0,
                    "avg_cpc": metrics["cost"] / metrics["clicks"],
                    "active_days": len(metrics["days"]),
                }

        return hour_performance

    def _extract_start_hour(self, hour_range: str) -> str | None:
        """Extract start hour from hour range string."""
        # Example: "12:00 AM - 1:00 AM" -> "12 AM"
        try:
            start_time = hour_range.split("-")[0].strip()
            # Extract hour and AM/PM
            parts = start_time.split(":")
            if len(parts) >= 2:
                hour = parts[0]
                am_pm = "AM" if "AM" in start_time else "PM"
                return f"{hour} {am_pm}"
        except (IndexError, ValueError, AttributeError) as e:
            logger.warning(f"Failed to extract hour from range '{hour_range}': {e}")
        return None

    def _calculate_variance_metrics(
        self, day_performance: dict, hour_performance: dict
    ) -> dict[str, float]:
        """Calculate variance metrics for performance."""
        # Day variance
        day_conv_rates = [p["conversion_rate"] for p in day_performance.values()]
        day_variance = (
            statistics.stdev(day_conv_rates) if len(day_conv_rates) > 1 else 0.0
        )

        # Hour variance
        hour_conv_rates = [p["conversion_rate"] for p in hour_performance.values()]
        hour_variance = (
            statistics.stdev(hour_conv_rates) if len(hour_conv_rates) > 1 else 0.0
        )

        # Cost efficiency variance (CPA)
        day_cpas = [p["cpa"] for p in day_performance.values() if p["cpa"] > 0]
        cost_variance = statistics.stdev(day_cpas) if len(day_cpas) > 1 else 0.0

        return {
            "day_variance": day_variance,
            "hour_variance": hour_variance,
            "cost_variance": cost_variance,
        }

    def _identify_performers(
        self, day_performance: dict, hour_performance: dict
    ) -> dict[str, list]:
        """Identify best and worst performing time periods."""
        # Sort days by conversion rate
        sorted_days = sorted(
            day_performance.items(), key=lambda x: x[1]["conversion_rate"], reverse=True
        )

        # Sort hours by conversion rate
        sorted_hours = sorted(
            hour_performance.items(),
            key=lambda x: x[1]["conversion_rate"],
            reverse=True,
        )

        # Get top and bottom performers
        best_days = [
            {
                "day": day,
                "conversion_rate": metrics["conversion_rate"],
                "conversions": metrics["conversions"],
                "cost": metrics["cost"],
                "cpa": metrics["cpa"],
            }
            for day, metrics in sorted_days[:3]
        ]

        worst_days = [
            {
                "day": day,
                "conversion_rate": metrics["conversion_rate"],
                "conversions": metrics["conversions"],
                "cost": metrics["cost"],
                "cpa": metrics["cpa"],
            }
            for day, metrics in sorted_days[-3:]
            if metrics["conversion_rate"]
            < sorted_days[0][1]["conversion_rate"] * self.WORST_PERFORMER_THRESHOLD
        ]

        best_hours = (
            [
                {
                    "hour": hour,
                    "conversion_rate": metrics["conversion_rate"],
                    "conversions": metrics["conversions"],
                    "cost": metrics["cost"],
                    "cpa": metrics["cpa"],
                }
                for hour, metrics in sorted_hours[:3]
            ]
            if sorted_hours
            else []
        )

        worst_hours = (
            [
                {
                    "hour": hour,
                    "conversion_rate": metrics["conversion_rate"],
                    "conversions": metrics["conversions"],
                    "cost": metrics["cost"],
                    "cpa": metrics["cpa"],
                }
                for hour, metrics in sorted_hours[-3:]
                if metrics["conversion_rate"]
                < sorted_hours[0][1]["conversion_rate"] * self.WORST_PERFORMER_THRESHOLD
            ]
            if sorted_hours
            else []
        )

        return {
            "best_days": best_days,
            "worst_days": worst_days,
            "best_hours": best_hours,
            "worst_hours": worst_hours,
        }

    def _generate_recommendations(
        self, day_performance: dict, hour_performance: dict, variance_metrics: dict
    ) -> dict[str, Any]:
        """Generate recommendations based on analysis."""
        recommendations = []
        bid_adjustments = []
        expansions = []
        reductions = []

        # Generate day-based recommendations
        if day_performance:
            day_results = self._generate_day_recommendations(day_performance)
            recommendations.extend(day_results["recommendations"])
            bid_adjustments.extend(day_results["bid_adjustments"])
            reductions.extend(day_results["reductions"])

        # Generate hour-based recommendations
        if hour_performance and len(hour_performance) > 3:
            hour_results = self._generate_hour_recommendations(hour_performance)
            expansions.extend(hour_results["expansions"])

        # Variance-based recommendations
        if (
            variance_metrics["day_variance"] > self.HIGH_VARIANCE_THRESHOLD
        ):  # More than 2% variance
            recommendations.append(
                Recommendation(
                    type=RecommendationType.OPTIMIZE_BIDDING,
                    priority=RecommendationPriority.MEDIUM,
                    title="High day-of-week performance variance detected",
                    description=f"Conversion rates vary by {variance_metrics['day_variance'] * 100:.1f}% across days",
                    estimated_impact="Optimize budget allocation by day for better efficiency",
                    estimated_cost_savings=sum(
                        p["cost"] for p in day_performance.values()
                    )
                    * 0.1,
                )
            )

        return {
            "general": recommendations,
            "bid_adjustments": bid_adjustments,
            "expansions": expansions,
            "reductions": reductions,
        }

    def _generate_day_recommendations(self, day_performance: dict) -> dict[str, Any]:
        """Generate recommendations for day performance."""
        recommendations = []
        bid_adjustments = []
        reductions = []

        # Calculate average performance
        conv_rates = [p["conversion_rate"] for p in day_performance.values()]
        avg_day_conv_rate = statistics.mean(conv_rates) if conv_rates else 0.0

        day_cpas = [p["cpa"] for p in day_performance.values() if p["cpa"] > 0]
        avg_day_cpa = statistics.mean(day_cpas) if day_cpas else 0.0

        # Day-based recommendations
        for day, metrics in day_performance.items():
            conv_rate_diff = (
                metrics["conversion_rate"] - avg_day_conv_rate
            ) / avg_day_conv_rate

            if conv_rate_diff > self.performance_threshold:
                # High performer
                bid_adj = min(self.MAX_BID_ADJUSTMENT, int(conv_rate_diff * 100))
                bid_adjustments.append(
                    {
                        "day": day,
                        "current_bid_adjustment": 0,
                        "recommended_bid_adjustment": bid_adj,
                        "reason": f"Conversion rate {conv_rate_diff * 100:.1f}% above average",
                    }
                )

                recommendations.append(
                    Recommendation(
                        type=RecommendationType.ADJUST_BID,
                        priority=RecommendationPriority.HIGH,
                        title=f"Increase {day} bid adjustment",
                        description=f"{day} shows {metrics['conversion_rate']:.1%} conversion rate vs {avg_day_conv_rate:.1%} average",
                        estimated_impact=f"Potential {metrics['conversions'] * 0.2:.0f} additional conversions",
                        estimated_conversion_increase=20.0,
                        action_data={
                            "day": day,
                            "current_bid_adjustment": 0,
                            "recommended_bid_adjustment": bid_adj,
                        },
                    )
                )

            elif conv_rate_diff < -self.performance_threshold and metrics["cost"] > 100:
                # Low performer with significant spend
                bid_adj = max(self.MIN_BID_ADJUSTMENT, int(conv_rate_diff * 100))
                bid_adjustments.append(
                    {
                        "day": day,
                        "current_bid_adjustment": 0,
                        "recommended_bid_adjustment": bid_adj,
                        "reason": f"Conversion rate {abs(conv_rate_diff) * 100:.1f}% below average",
                    }
                )

                if conv_rate_diff < self.PAUSE_THRESHOLD:  # More than 50% below average
                    reductions.append(
                        f"Consider pausing ads on {day} (conversion rate {abs(conv_rate_diff) * 100:.1f}% below average)"
                    )

                    recommendations.append(
                        Recommendation(
                            type=RecommendationType.PAUSE_KEYWORD,
                            priority=RecommendationPriority.HIGH,
                            title=f"Consider pausing {day} advertising",
                            description=f"{day} conversion rate is {abs(conv_rate_diff) * 100:.1f}% below average with ${metrics['cost']:.2f} spend",
                            estimated_impact=f"Save ${metrics['cost']:.2f} in wasted spend",
                            estimated_cost_savings=metrics["cost"] * 0.8,
                            action_data={
                                "day": day,
                                "reason": f"Conversion rate {abs(conv_rate_diff) * 100:.1f}% below average",
                            },
                        )
                    )

        return {
            "recommendations": recommendations,
            "bid_adjustments": bid_adjustments,
            "reductions": reductions,
        }

    def _generate_hour_recommendations(self, hour_performance: dict) -> dict[str, Any]:
        """Generate recommendations for hour performance."""
        expansions = []

        hour_conv_rates = [p["conversion_rate"] for p in hour_performance.values()]
        avg_hour_conv_rate = (
            statistics.mean(hour_conv_rates) if hour_conv_rates else 0.0
        )

        # Find opportunities for expansion
        high_performing_hours = [
            hour
            for hour, metrics in hour_performance.items()
            if metrics["conversion_rate"] > avg_hour_conv_rate * 1.2
        ]

        if high_performing_hours:
            expansions.append(
                f"Expand coverage during high-performing hours: {', '.join(high_performing_hours[:5])}"
            )

        return {
            "expansions": expansions,
        }

    def _calculate_potential_improvements(
        self,
        data: list[AdSchedulePerformance],
        day_performance: dict,
        hour_performance: dict,
    ) -> dict[str, float]:
        """Calculate potential improvements from optimization."""
        if not day_performance:
            return {"savings": 0.0, "conversions": 0.0}

        # Calculate potential savings from reducing low performers
        total_cost = sum(p["cost"] for p in day_performance.values())
        low_performer_cost = sum(
            p["cost"]
            for p in day_performance.values()
            if p["conversion_rate"]
            < statistics.mean([p["conversion_rate"] for p in day_performance.values()])
            * self.WORST_PERFORMER_THRESHOLD
        )
        potential_savings = (
            low_performer_cost * self.POTENTIAL_SAVINGS_FACTOR
        )  # Assume 50% reduction

        # Calculate potential conversion increase from boosting high performers
        high_performer_conversions = sum(
            p["conversions"]
            for p in day_performance.values()
            if p["conversion_rate"]
            > statistics.mean([p["conversion_rate"] for p in day_performance.values()])
            * (1 + self.POTENTIAL_CONVERSION_INCREASE_FACTOR)
        )
        potential_conversion_increase = (
            high_performer_conversions * self.POTENTIAL_CONVERSION_INCREASE_FACTOR
        )  # Assume 20% increase

        return {
            "savings": potential_savings,
            "conversions": potential_conversion_increase,
        }

    def _create_analysis_result(
        self,
        customer_id: str,
        start_date: datetime,
        end_date: datetime,
        filtered_data: list[AdSchedulePerformance],
        day_performance: dict,
        hour_performance: dict,
        performers: dict,
        variance_metrics: dict,
        recommendations: dict,
        improvements: dict,
    ) -> DaypartingAnalysisResult:
        """Create the analysis result object."""
        return DaypartingAnalysisResult(
            customer_id=customer_id,
            analyzer_name="dayparting",
            analysis_type="ad_schedule_optimization",
            start_date=start_date,
            end_date=end_date,
            schedule_data=filtered_data,
            day_performance=day_performance,
            hour_performance=hour_performance,
            best_performing_days=performers["best_days"],
            worst_performing_days=performers["worst_days"],
            best_performing_hours=performers["best_hours"],
            worst_performing_hours=performers["worst_hours"],
            conversion_rate_variance_by_day=variance_metrics["day_variance"],
            conversion_rate_variance_by_hour=variance_metrics["hour_variance"],
            cost_efficiency_variance=variance_metrics["cost_variance"],
            bid_adjustment_recommendations=recommendations["bid_adjustments"],
            schedule_expansion_recommendations=recommendations["expansions"],
            schedule_reduction_recommendations=recommendations["reductions"],
            potential_savings=improvements["savings"],
            potential_conversion_increase=improvements["conversions"],
            recommendations=recommendations["general"],
        )

    def get_name(self) -> str:
        """Return analyzer name."""
        return "dayparting"

    def get_description(self) -> str:
        """Return analyzer description."""
        return "Analyzes ad schedule data to identify optimal times for ad delivery"
