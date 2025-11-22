"""Per Store parser for Google Ads local store performance analysis."""

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from paidsearchnav.core.models.store_performance import (
    StoreLocationData,
    StoreMetrics,
    StorePerformanceData,
    StorePerformanceLevel,
)
from paidsearchnav.parsers.csv_parser import GoogleAdsCSVParser

logger = logging.getLogger(__name__)


class PerStoreConfig:
    """Configuration for per store analysis."""

    def __init__(
        self,
        min_impressions_threshold: int = 100,
        high_engagement_threshold: float = 3.0,
        moderate_engagement_threshold: float = 1.5,
        low_engagement_threshold: float = 0.5,
    ):
        """Initialize per store configuration.

        Args:
            min_impressions_threshold: Minimum impressions to consider for analysis
            high_engagement_threshold: Engagement rate threshold for high performers (%)
            moderate_engagement_threshold: Engagement rate threshold for moderate performers (%)
            low_engagement_threshold: Engagement rate threshold for low performers (%)
        """
        self.min_impressions_threshold = min_impressions_threshold
        self.high_engagement_threshold = high_engagement_threshold
        self.moderate_engagement_threshold = moderate_engagement_threshold
        self.low_engagement_threshold = low_engagement_threshold


class PerStoreParser(GoogleAdsCSVParser):
    """Parser for Google Ads Per Store reports.

    Provides comprehensive store-by-store performance analysis including
    local metrics, geographic insights, and store performance ranking
    for multi-location retail businesses.
    """

    def __init__(self, config: Optional[PerStoreConfig] = None, **kwargs):
        """Initialize PerStoreParser with per_store file type.

        Args:
            config: Configuration for per store analysis
            **kwargs: Additional arguments passed to parent class
        """
        # Enable preprocessing to handle Google Ads headers
        kwargs.setdefault("strict_validation", False)
        super().__init__(file_type="per_store", **kwargs)
        self.config = config or PerStoreConfig()

    def analyze_store_performance(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze store performance data and generate comprehensive insights.

        Optimized for large datasets with efficient parsing and memory usage.

        Args:
            data: List of parsed per store records.

        Returns:
            Comprehensive store performance analysis with KPIs and insights.
        """
        if not data:
            logger.warning("No per store data provided for analysis")
            return {"error": "No per store data provided"}

        logger.info(
            f"Starting store performance analysis for {len(data)} store entries"
        )

        # Performance optimization: batch process stores for large datasets
        batch_size = min(1000, len(data))  # Process in batches for memory efficiency
        stores = []
        skipped_rows = 0

        # Parse store data with batch processing for large datasets
        for i in range(0, len(data), batch_size):
            batch = data[i : i + batch_size]
            logger.debug(
                f"Processing batch {i // batch_size + 1} of {len(batch)} records"
            )

            for j, row in enumerate(batch):
                try:
                    store = self._parse_store_record(row)
                    if store:
                        stores.append(store)
                    else:
                        skipped_rows += 1
                except Exception as e:
                    logger.warning(f"Failed to parse store record {i + j}: {e}")
                    skipped_rows += 1
                    continue

        if skipped_rows > 0:
            logger.warning(f"Skipped {skipped_rows} rows due to parsing issues")

        if not stores:
            logger.warning("No valid store records found")
            return {"error": "No valid store records found"}

        # Pre-calculate metrics once for performance optimization
        total_impressions = sum(store.metrics.local_impressions for store in stores)

        # Filter stores with sufficient data (optimized with generator for large datasets)
        filtered_stores = [
            store
            for store in stores
            if store.metrics.local_impressions >= self.config.min_impressions_threshold
        ]

        logger.info(
            f"Found {len(filtered_stores)} stores with sufficient data for analysis"
        )

        # Performance optimization: categorize stores in-place to avoid re-iteration
        for store in filtered_stores:
            store.performance_level = self._categorize_performance(store)

        # Generate analysis with cached calculations
        analysis = self._generate_store_analysis(filtered_stores)

        return analysis

    def _parse_store_record(
        self, row: Dict[str, Any]
    ) -> Optional[StorePerformanceData]:
        """Parse a single store record into StorePerformanceData.

        Args:
            row: Raw CSV row data

        Returns:
            StorePerformanceData object or None if parsing fails
        """
        try:
            # Validate required fields - handle both raw CSV and mapped field names
            store_name = (
                row.get("Store locations") or row.get("store_name", "")
            ).strip()
            if not store_name:
                return None

            # Parse location data - handle both raw CSV and mapped field names
            location = StoreLocationData(
                store_name=store_name,
                address_line_1=row.get("address_line_1", ""),
                address_line_2=row.get("address_line_2"),
                city=row.get("city", ""),
                state=row.get("province")
                or row.get("state", ""),  # Handle both "province" and "state"
                postal_code=row.get("postal_code", ""),
                country_code=row.get("country_code", "US"),
                phone_number=row.get("phone_number"),
            )

            # Parse metrics - handle both raw CSV and mapped field names
            local_impressions = self._parse_number(
                row.get("Local reach (impressions)") or row.get("local_impressions", 0)
            )
            store_visits = self._parse_number(
                row.get("Store visits") or row.get("store_visits", 0)
            )
            call_clicks = self._parse_number(
                row.get("Call clicks") or row.get("call_clicks", 0)
            )
            driving_directions = self._parse_number(
                row.get("Driving directions") or row.get("driving_directions", 0)
            )
            website_visits = self._parse_number(
                row.get("Website visits") or row.get("website_visits", 0)
            )

            metrics = StoreMetrics(
                local_impressions=local_impressions,
                store_visits=store_visits,
                call_clicks=call_clicks,
                driving_directions=driving_directions,
                website_visits=website_visits,
            )

            return StorePerformanceData(
                location=location,
                metrics=metrics,
                performance_level=StorePerformanceLevel.MODERATE_PERFORMER,  # Will be updated
            )

        except Exception as e:
            logger.warning(f"Failed to parse store record: {e}, row: {row}")
            return None

    @lru_cache(maxsize=512)
    def _parse_number_cached(self, value: str) -> int:
        """Parse a number from string with LRU cache for repeated values.

        This method caches parsed numbers to avoid redundant computation
        for repeated values in large datasets.
        """
        try:
            # Remove commas and convert to int via float to preserve precision
            return int(float(value.replace(",", "")))
        except (ValueError, AttributeError):
            return 0

    def _parse_number(self, value: Any) -> int:
        """Parse a number from CSV, handling commas and string formatting.

        Uses caching for string values to optimize performance on large datasets.
        """
        if isinstance(value, int):
            return value
        if isinstance(value, (str, float)):
            str_value = str(value)
            # Use cached version for string values
            return self._parse_number_cached(str_value)
        return 0

    def _categorize_performance(
        self, store: StorePerformanceData
    ) -> StorePerformanceLevel:
        """Categorize store performance based on engagement rate."""
        engagement_rate = store.metrics.engagement_rate

        if engagement_rate >= self.config.high_engagement_threshold:
            return StorePerformanceLevel.HIGH_PERFORMER
        elif engagement_rate >= self.config.moderate_engagement_threshold:
            return StorePerformanceLevel.MODERATE_PERFORMER
        elif engagement_rate >= self.config.low_engagement_threshold:
            return StorePerformanceLevel.LOW_PERFORMER
        else:
            return StorePerformanceLevel.UNDERPERFORMER

    def _generate_store_analysis(
        self, stores: List[StorePerformanceData]
    ) -> Dict[str, Any]:
        """Generate comprehensive store performance analysis.

        Args:
            stores: List of store performance data.

        Returns:
            Detailed analysis with KPIs, geographic insights, and recommendations.
        """
        if not stores:
            return {"error": "No stores with sufficient data"}

        logger.info(f"Generating comprehensive analysis for {len(stores)} stores")

        # Calculate basic metrics
        basic_metrics = self._calculate_basic_metrics(stores)

        # Categorize stores by performance
        performance_breakdown = self._categorize_stores_by_performance(stores)

        # Generate analysis components
        geographic_analysis = self._analyze_geographic_distribution(stores)
        local_action_metrics = self._calculate_local_action_metrics(
            stores, basic_metrics["total_local_impressions"]
        )
        insights = self._generate_strategic_insights(stores, performance_breakdown)
        recommendations = self._generate_recommendations(stores, geographic_analysis)
        kpis = self._calculate_kpis(stores, basic_metrics["total_local_impressions"])

        # Build top performing stores list
        top_performing_stores = self._build_top_performing_stores_list(
            performance_breakdown
        )

        return {
            "total_stores": basic_metrics["total_stores"],
            "active_stores": len(
                [s for s in stores if s.metrics.local_impressions > 0]
            ),
            "inactive_stores": len(
                [s for s in stores if s.metrics.local_impressions == 0]
            ),
            "state_distribution": geographic_analysis["state_distribution"],
            "top_performing_stores": top_performing_stores,
            "market_performance": geographic_analysis["market_performance"],
            "local_action_metrics": local_action_metrics,
            "performance_breakdown": self._format_performance_breakdown(
                performance_breakdown
            ),
            "optimization_opportunities": self._count_optimization_opportunities(
                performance_breakdown
            ),
            "strategic_insights": insights,
            "recommendations": recommendations,
            "kpis": kpis,
        }

    def _calculate_basic_metrics(
        self, stores: List[StorePerformanceData]
    ) -> Dict[str, int]:
        """Calculate basic aggregate metrics from stores."""
        return {
            "total_stores": len(stores),
            "total_local_impressions": sum(
                store.metrics.local_impressions for store in stores
            ),
            "total_store_visits": sum(store.metrics.store_visits for store in stores),
            "total_call_clicks": sum(store.metrics.call_clicks for store in stores),
            "total_driving_directions": sum(
                store.metrics.driving_directions for store in stores
            ),
            "total_website_visits": sum(
                store.metrics.website_visits for store in stores
            ),
        }

    def _categorize_stores_by_performance(
        self, stores: List[StorePerformanceData]
    ) -> Dict[StorePerformanceLevel, List[StorePerformanceData]]:
        """Categorize stores by their performance level."""
        performance_breakdown = {
            StorePerformanceLevel.HIGH_PERFORMER: [],
            StorePerformanceLevel.MODERATE_PERFORMER: [],
            StorePerformanceLevel.LOW_PERFORMER: [],
            StorePerformanceLevel.UNDERPERFORMER: [],
        }

        for store in stores:
            performance_breakdown[store.performance_level].append(store)

        return performance_breakdown

    def _build_top_performing_stores_list(
        self,
        performance_breakdown: Dict[StorePerformanceLevel, List[StorePerformanceData]],
    ) -> List[Dict[str, Any]]:
        """Build a list of top performing stores with key metrics."""
        top_performers = performance_breakdown[StorePerformanceLevel.HIGH_PERFORMER]
        top_performers.sort(key=lambda x: x.metrics.engagement_rate, reverse=True)

        return [
            {
                "store": store.location.store_name,
                "store_visits": store.metrics.store_visits,
                "local_impressions": store.metrics.local_impressions,
                "visit_rate_per_1000": round(
                    (
                        store.metrics.store_visits
                        / max(store.metrics.local_impressions, 1)
                    )
                    * 1000,
                    1,
                ),
                "engagement_rate": round(store.metrics.engagement_rate, 1),
            }
            for store in top_performers[:5]
        ]

    def _format_performance_breakdown(
        self,
        performance_breakdown: Dict[StorePerformanceLevel, List[StorePerformanceData]],
    ) -> Dict[str, int]:
        """Format performance breakdown into counts by category."""
        return {
            "high_performers": len(
                performance_breakdown[StorePerformanceLevel.HIGH_PERFORMER]
            ),
            "moderate_performers": len(
                performance_breakdown[StorePerformanceLevel.MODERATE_PERFORMER]
            ),
            "low_performers": len(
                performance_breakdown[StorePerformanceLevel.LOW_PERFORMER]
            ),
            "underperformers": len(
                performance_breakdown[StorePerformanceLevel.UNDERPERFORMER]
            ),
        }

    def _count_optimization_opportunities(
        self,
        performance_breakdown: Dict[StorePerformanceLevel, List[StorePerformanceData]],
    ) -> int:
        """Count stores that need optimization."""
        return len(performance_breakdown[StorePerformanceLevel.UNDERPERFORMER]) + len(
            performance_breakdown[StorePerformanceLevel.LOW_PERFORMER]
        )

    def _analyze_geographic_distribution(
        self, stores: List[StorePerformanceData]
    ) -> Dict[str, Any]:
        """Analyze geographic distribution and performance by location.

        Optimized for large datasets with efficient dictionary operations.
        """
        # Use defaultdict for performance optimization on large datasets
        from collections import defaultdict

        state_distribution = defaultdict(int)
        city_performance = defaultdict(
            lambda: {"total_stores": 0, "total_visits": 0, "avg_visits_per_store": 0}
        )
        market_performance = defaultdict(
            lambda: {"total_stores": 0, "total_visits": 0, "total_impressions": 0}
        )

        # Single pass through stores for efficiency
        for store in stores:
            state = store.location.state
            city = store.location.city
            store_visits = store.metrics.store_visits
            local_impressions = store.metrics.local_impressions

            # State distribution and market performance
            if state:
                state_distribution[state] += 1
                market_performance[state]["total_stores"] += 1
                market_performance[state]["total_visits"] += store_visits
                market_performance[state]["total_impressions"] += local_impressions

            # City performance
            if city:
                city_performance[city]["total_stores"] += 1
                city_performance[city]["total_visits"] += store_visits

        # Calculate averages
        for city_data in city_performance.values():
            city_data["avg_visits_per_store"] = city_data["total_visits"] // max(
                city_data["total_stores"], 1
            )

        for market_data in market_performance.values():
            market_data["avg_visits_per_store"] = market_data["total_visits"] // max(
                market_data["total_stores"], 1
            )

        return {
            "state_distribution": dict(
                sorted(state_distribution.items(), key=lambda x: x[1], reverse=True)
            ),
            "city_performance": dict(
                sorted(
                    city_performance.items(),
                    key=lambda x: x[1]["total_visits"],
                    reverse=True,
                )[:10]
            ),
            "market_performance": dict(
                sorted(
                    market_performance.items(),
                    key=lambda x: x[1]["total_visits"],
                    reverse=True,
                )
            ),
        }

    def _calculate_local_action_metrics(
        self, stores: List[StorePerformanceData], total_impressions: int
    ) -> Dict[str, float]:
        """Calculate local action metrics across all stores."""
        total_store_visits = sum(store.metrics.store_visits for store in stores)
        total_call_clicks = sum(store.metrics.call_clicks for store in stores)
        total_driving_directions = sum(
            store.metrics.driving_directions for store in stores
        )
        total_website_visits = sum(store.metrics.website_visits for store in stores)

        return {
            "avg_store_visit_rate": round(
                (total_store_visits / max(total_impressions, 1)) * 1000, 1
            ),
            "avg_call_click_rate": round(
                (total_call_clicks / max(total_impressions, 1)) * 1000, 1
            ),
            "avg_directions_rate": round(
                (total_driving_directions / max(total_impressions, 1)) * 1000, 1
            ),
            "avg_website_visit_rate": round(
                (total_website_visits / max(total_impressions, 1)) * 1000, 1
            ),
        }

    def _generate_strategic_insights(
        self,
        stores: List[StorePerformanceData],
        performance_breakdown: Dict[StorePerformanceLevel, List[StorePerformanceData]],
    ) -> List[str]:
        """Generate strategic insights based on store performance data."""
        insights = []

        high_performers = performance_breakdown[StorePerformanceLevel.HIGH_PERFORMER]
        underperformers = performance_breakdown[StorePerformanceLevel.UNDERPERFORMER]

        if high_performers:
            top_performer = max(
                high_performers, key=lambda x: x.metrics.engagement_rate
            )
            insights.append(
                f"Top performing store: {top_performer.location.store_name} with {top_performer.metrics.engagement_rate:.1f}% engagement rate"
            )

        if underperformers:
            insights.append(
                f"{len(underperformers)} stores need optimization with engagement rates below {self.config.low_engagement_threshold}%"
            )

        # Call tracking issues
        call_issues = [
            store
            for store in stores
            if store.metrics.local_impressions > 500
            and store.metrics.call_clicks == 0
            and store.location.phone_number
        ]
        if call_issues:
            insights.append(
                f"{len(call_issues)} stores may have call tracking issues despite having phone numbers"
            )

        return insights

    def _generate_recommendations(
        self,
        stores: List[StorePerformanceData],
        geographic_analysis: Dict[str, Any],
    ) -> List[str]:
        """Generate actionable recommendations based on analysis."""
        recommendations = []

        # Geographic optimization
        top_market = next(iter(geographic_analysis["market_performance"].keys()), None)
        if top_market:
            recommendations.append(
                f"Focus expansion efforts in {top_market} market based on strong performance"
            )

        # Performance optimization
        low_performers = [
            store
            for store in stores
            if store.performance_level
            in [
                StorePerformanceLevel.LOW_PERFORMER,
                StorePerformanceLevel.UNDERPERFORMER,
            ]
        ]
        if low_performers:
            recommendations.append(
                f"Review location extensions and local listings for {len(low_performers)} underperforming stores"
            )

        # Local action optimization
        avg_engagement = sum(store.metrics.engagement_rate for store in stores) / len(
            stores
        )
        if avg_engagement < 2.0:
            recommendations.append(
                "Improve overall local engagement through better location targeting and ad copy optimization"
            )

        return recommendations[:5]  # Limit to top 5 recommendations

    def _calculate_kpis(
        self, stores: List[StorePerformanceData], total_impressions: int
    ) -> Dict[str, Any]:
        """Calculate key performance indicators."""
        total_engagements = sum(store.metrics.total_engagements for store in stores)

        return {
            "total_active_stores": len(
                [s for s in stores if s.metrics.local_impressions > 0]
            ),
            "avg_store_visit_rate": round(
                (
                    sum(store.metrics.store_visits for store in stores)
                    / max(total_impressions, 1)
                )
                * 1000,
                1,
            ),
            "overall_engagement_rate": round(
                (total_engagements / max(total_impressions, 1)) * 100, 2
            ),
            "stores_needing_optimization": len(
                [
                    store
                    for store in stores
                    if store.performance_level
                    in [
                        StorePerformanceLevel.LOW_PERFORMER,
                        StorePerformanceLevel.UNDERPERFORMER,
                    ]
                ]
            ),
        }

    def parse_and_analyze(self, file_path: Path) -> Dict[str, Any]:
        """Parse per store CSV and return comprehensive analysis.

        Args:
            file_path: Path to the per store CSV file.

        Returns:
            Complete analysis including parsed data and store insights.
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

            # Perform store performance analysis
            analysis = self.analyze_store_performance(data_dicts)

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
            logger.error(f"Error parsing and analyzing per store data: {e}")
            return {
                "parsing_info": {
                    "total_records": 0,
                    "file_type": self.file_type,
                    "parsed_successfully": False,
                    "error": str(e),
                },
                "analysis": {"error": f"Failed to analyze per store data: {str(e)}"},
            }
