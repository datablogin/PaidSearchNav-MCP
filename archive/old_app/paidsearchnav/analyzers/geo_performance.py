"""Geographic performance analyzer for identifying location-based optimization opportunities."""

import logging
import statistics
from datetime import datetime
from typing import Any, Dict, List, Optional

from paidsearchnav.core.interfaces import Analyzer
from paidsearchnav.core.models import (
    DistancePerformanceData,
    GeographicLevel,
    GeoPerformanceAnalysisResult,
    GeoPerformanceData,
    GeoPerformanceSummary,
    LocationInsight,
)
from paidsearchnav.platforms.ga4.bigquery_client import GA4BigQueryClient
from paidsearchnav.platforms.google.client import GoogleAdsAPIClient

logger = logging.getLogger(__name__)


class GeoPerformanceAnalyzer(Analyzer):
    """Analyzes geographic performance to identify optimization opportunities."""

    def __init__(
        self,
        api_client: GoogleAdsAPIClient,
        min_impressions: int = 100,
        min_clicks: int = 10,
        performance_threshold: float = 0.2,  # 20% deviation from average
        ga4_client: Optional[GA4BigQueryClient] = None,
        top_locations_count: int = 10,
    ):
        """Initialize the geographic performance analyzer.

        Args:
            api_client: Google Ads API client
            min_impressions: Minimum impressions required for analysis
            min_clicks: Minimum clicks required for analysis
            performance_threshold: Threshold for identifying high/low performers
            top_locations_count: Number of top performers to include
        """
        self.api_client = api_client
        self.min_impressions = min_impressions
        self.min_clicks = min_clicks
        self.performance_threshold = performance_threshold
        self.ga4_client = ga4_client
        self.top_locations_count = top_locations_count

    async def analyze(
        self,
        customer_id: str,
        start_date: datetime,
        end_date: datetime,
        **kwargs: Any,
    ) -> GeoPerformanceAnalysisResult:
        """Analyze geographic performance for a customer.

        Args:
            customer_id: Google Ads customer ID
            start_date: Start date for analysis
            end_date: End date for analysis
            **kwargs: Additional parameters (geographic_level, campaign_ids)

        Returns:
            Geographic performance analysis result
        """
        logger.info(
            f"Starting geographic performance analysis for customer {customer_id}"
        )

        # Extract parameters
        geographic_level = kwargs.get("geographic_level", "CITY")
        campaign_ids = kwargs.get("campaign_ids")

        try:
            # Fetch geographic performance data
            geo_data_raw = await self.api_client.get_geographic_performance(
                customer_id=customer_id,
                start_date=start_date,
                end_date=end_date,
                geographic_level=geographic_level,
                campaign_ids=campaign_ids,
            )

            # Convert raw data to structured models
            performance_data = self._convert_to_performance_data(
                geo_data_raw, geographic_level, start_date, end_date
            )

            # Filter data by minimum thresholds
            filtered_data = self._filter_performance_data(performance_data)

            # Enhance with GA4 store visit data if available
            if self.ga4_client:
                filtered_data = await self._enhance_with_store_visit_data(
                    filtered_data, start_date, end_date
                )

            # Analyze performance
            summary = self._analyze_performance_summary(
                customer_id, filtered_data, start_date, end_date
            )

            # Generate insights
            insights = self._generate_location_insights(filtered_data, summary)

            # Get distance performance if available
            distance_analysis = await self._analyze_distance_performance(
                customer_id, start_date, end_date, campaign_ids
            )

            # Generate recommendations
            recommendations = self._generate_recommendations(insights, summary)

            # Create dashboard metrics
            dashboard_metrics = self._create_dashboard_metrics(summary, insights)

            result = GeoPerformanceAnalysisResult(
                customer_id=customer_id,
                analyzer_name="geo_performance",
                start_date=start_date,
                end_date=end_date,
                performance_data=filtered_data,
                summary=summary,
                distance_analysis=distance_analysis,
                insights=insights,
                geo_recommendations=recommendations,
                dashboard_metrics=dashboard_metrics,
            )

            logger.info(f"Geographic analysis completed with {len(insights)} insights")
            return result

        except Exception as ex:
            logger.error(f"Geographic performance analysis failed: {ex}")
            raise

    def _convert_to_performance_data(
        self,
        raw_data: list[dict[str, Any]],
        geographic_level: str,
        start_date: datetime,
        end_date: datetime,
    ) -> list[GeoPerformanceData]:
        """Convert raw API data to structured performance data."""
        performance_data = []

        for row in raw_data:
            # Determine location name based on geographic level
            location_name = self._get_location_name(row, geographic_level)

            if not location_name:
                continue

            geo_data = GeoPerformanceData(
                customer_id=row.get(
                    "customer_id", "unknown"
                ),  # Use customer_id if available
                campaign_id=row["campaign_id"],
                campaign_name=row["campaign_name"],
                geographic_level=GeographicLevel(geographic_level),
                location_name=location_name,
                country_code=row.get("country_name", ""),
                region_code=row.get("region_name", ""),
                city=row.get("city_name", ""),
                zip_code=row.get("postal_code", ""),
                impressions=row["impressions"],
                clicks=row["clicks"],
                conversions=row["conversions"],
                cost_micros=row["cost_micros"],
                revenue_micros=row.get("conversion_value_micros", 0),
                start_date=start_date,
                end_date=end_date,
            )

            performance_data.append(geo_data)

        return performance_data

    def _get_location_name(self, row: dict[str, Any], geographic_level: str) -> str:
        """Extract location name based on geographic level."""
        level_mapping = {
            "COUNTRY": "country_name",
            "STATE": "region_name",
            "CITY": "city_name",
            "ZIP_CODE": "postal_code",
        }

        field_name = level_mapping.get(geographic_level, "city_name")
        return row.get(field_name, "")

    def _filter_performance_data(
        self, data: list[GeoPerformanceData]
    ) -> list[GeoPerformanceData]:
        """Filter performance data by minimum thresholds."""
        return [
            d
            for d in data
            if d.impressions >= self.min_impressions and d.clicks >= self.min_clicks
        ]

    def _analyze_performance_summary(
        self,
        customer_id: str,
        data: list[GeoPerformanceData],
        start_date: datetime,
        end_date: datetime,
    ) -> GeoPerformanceSummary:
        """Analyze overall performance summary."""
        if not data:
            return GeoPerformanceSummary(
                customer_id=customer_id,
                analysis_date=datetime.utcnow(),
                date_range_start=start_date,
                date_range_end=end_date,
                total_locations=0,
                total_cost=0.0,
                total_conversions=0.0,
                average_cpa=0.0,
                average_roas=0.0,
            )

        total_cost = sum(d.cost for d in data)
        total_conversions = sum(d.conversions for d in data)

        # Calculate averages
        cpa_values = [d.cpa for d in data if d.cpa > 0]
        roas_values = [d.roas for d in data if d.roas > 0]

        average_cpa = statistics.mean(cpa_values) if cpa_values else 0.0
        average_roas = statistics.mean(roas_values) if roas_values else 0.0

        # Calculate distribution
        location_distribution: dict[str, int] = {}
        for d in data:
            level = (
                d.geographic_level.value
                if hasattr(d.geographic_level, "value")
                else d.geographic_level
            )
            location_distribution[level] = location_distribution.get(level, 0) + 1

        return GeoPerformanceSummary(
            customer_id=customer_id,
            analysis_date=datetime.utcnow(),
            date_range_start=start_date,
            date_range_end=end_date,
            total_locations=len(data),
            total_cost=total_cost,
            total_conversions=total_conversions,
            average_cpa=average_cpa,
            average_roas=average_roas,
            location_distribution=location_distribution,
            budget_reallocation_potential=self._calculate_reallocation_potential(data),
            expansion_opportunities=self._identify_expansion_opportunities(data),
        )

    def _generate_location_insights(
        self, data: list[GeoPerformanceData], summary: GeoPerformanceSummary
    ) -> list[LocationInsight]:
        """Generate insights for each location."""
        insights = []

        for d in data:
            # Calculate performance vs average
            cpa_vs_avg = d.cpa / summary.average_cpa if summary.average_cpa > 0 else 1.0
            roas_vs_avg = (
                d.roas / summary.average_roas if summary.average_roas > 0 else 1.0
            )
            conv_rate_vs_avg = (
                d.conversion_rate
                / (summary.total_conversions / sum(data2.clicks for data2 in data))
                if summary.total_conversions > 0
                else 1.0
            )

            # Calculate shares
            impression_share = d.impressions / sum(data2.impressions for data2 in data)
            cost_share = d.cost / summary.total_cost if summary.total_cost > 0 else 0.0
            conversion_share = (
                d.conversions / summary.total_conversions
                if summary.total_conversions > 0
                else 0.0
            )

            # Calculate performance score (0-100)
            performance_score = self._calculate_performance_score(
                cpa_vs_avg, roas_vs_avg, conv_rate_vs_avg
            )

            # Generate recommendations
            recommended_action = self._get_recommended_action(
                performance_score, cpa_vs_avg, roas_vs_avg
            )
            budget_rec = self._get_budget_recommendation(performance_score, cost_share)
            targeting_rec = self._get_targeting_recommendation(performance_score, d)

            insight = LocationInsight(
                location_name=d.location_name,
                geographic_level=d.geographic_level,
                performance_score=performance_score,
                cpa_vs_average=cpa_vs_avg,
                roas_vs_average=roas_vs_avg,
                conversion_rate_vs_average=conv_rate_vs_avg,
                impression_share=impression_share,
                cost_share=cost_share,
                conversion_share=conversion_share,
                recommended_action=recommended_action,
                budget_recommendation=budget_rec,
                targeting_recommendation=targeting_rec,
            )

            insights.append(insight)

        # Sort by performance score
        insights.sort(key=lambda x: x.performance_score, reverse=True)
        return insights

    def _calculate_performance_score(
        self, cpa_vs_avg: float, roas_vs_avg: float, conv_rate_vs_avg: float
    ) -> float:
        """Calculate overall performance score (0-100)."""
        # Lower CPA is better, higher ROAS and conversion rate are better
        # For CPA: 1.0 (average) = 50 points, 0.5 (50% better) = 75 points, 2.0 (100% worse) = 25 points
        cpa_score = max(0, min(100, 100 - (cpa_vs_avg - 1) * 50))

        # For ROAS: 1.0 (average) = 50 points, 2.0 (100% better) = 75 points, 0.5 (50% worse) = 25 points
        roas_score = (
            max(0, min(100, (roas_vs_avg - 1) * 25 + 50)) if roas_vs_avg > 0 else 0
        )

        # For conversion rate: similar to ROAS
        conv_score = max(0, min(100, (conv_rate_vs_avg - 1) * 25 + 50))

        # Weighted average
        return cpa_score * 0.4 + roas_score * 0.4 + conv_score * 0.2

    def _get_recommended_action(
        self, score: float, cpa_vs_avg: float, roas_vs_avg: float
    ) -> str:
        """Get recommended action based on performance."""
        if score >= 80:
            return "INCREASE_BUDGET"
        elif score >= 60:
            return "MAINTAIN_CURRENT"
        elif score >= 40:
            return "OPTIMIZE_TARGETING"
        else:
            return "DECREASE_BUDGET"

    def _get_budget_recommendation(self, score: float, cost_share: float) -> str:
        """Get budget adjustment recommendation."""
        if score >= 80 and cost_share < 0.2:
            return "Increase budget by 20-50%"
        elif score <= 40 and cost_share > 0.1:
            return "Decrease budget by 30-50%"
        elif score >= 60:
            return "Maintain current budget"
        else:
            return "Consider redistributing budget to higher-performing locations"

    def _get_targeting_recommendation(
        self, score: float, data: GeoPerformanceData
    ) -> str:
        """Get targeting optimization recommendation."""
        if score <= 40:
            return f"Consider excluding {data.location_name} or adjusting bid modifiers"
        elif score >= 80:
            return f"Consider increasing bid modifiers for {data.location_name}"
        else:
            return "Monitor performance and adjust targeting as needed"

    def _calculate_reallocation_potential(
        self, data: list[GeoPerformanceData]
    ) -> float:
        """Calculate potential improvement from budget reallocation."""
        if len(data) < 2:
            return 0.0

        # Calculate CPA spread
        cpa_values = [d.cpa for d in data if d.cpa > 0]
        if not cpa_values:
            return 0.0

        min_cpa = min(cpa_values)
        max_cpa = max(cpa_values)

        # Potential improvement is based on CPA spread
        return min(50.0, (max_cpa - min_cpa) / min_cpa * 100) if min_cpa > 0 else 0.0

    def _identify_expansion_opportunities(
        self, data: list[GeoPerformanceData]
    ) -> list[str]:
        """Identify geographic areas for potential expansion."""
        # Top performing locations with good ROAS
        high_performers = [
            d.location_name
            for d in data
            if d.roas > 3.0
            and d.conversions >= 5  # ROAS > 3x and meaningful conversions
        ]

        return high_performers[:5]  # Top 5 expansion opportunities

    async def _analyze_distance_performance(
        self,
        customer_id: str,
        start_date: datetime,
        end_date: datetime,
        campaign_ids: list[str] | None,
    ) -> list[DistancePerformanceData] | None:
        """Analyze performance by distance from business locations."""
        try:
            distance_data_raw = await self.api_client.get_distance_performance(
                customer_id=customer_id,
                start_date=start_date,
                end_date=end_date,
                campaign_ids=campaign_ids,
            )

            if not distance_data_raw:
                return None

            # For now, return None as distance analysis requires more complex processing
            # This would be implemented in a more advanced version
            return None

        except Exception as ex:
            logger.warning(f"Distance performance analysis failed: {ex}")
            return None

    def _generate_recommendations(
        self, insights: list[LocationInsight], summary: GeoPerformanceSummary
    ) -> list[str]:
        """Generate actionable recommendations."""
        recommendations = []

        # Top performers
        top_performers = [i for i in insights if i.performance_score >= 80]
        if top_performers:
            locations = ", ".join([i.location_name for i in top_performers[:3]])
            recommendations.append(
                f"Increase budget allocation to top-performing locations: {locations}"
            )

        # Underperformers
        underperformers = [i for i in insights if i.performance_score <= 40]
        if underperformers:
            locations = ", ".join([i.location_name for i in underperformers[:3]])
            recommendations.append(
                f"Consider reducing spend or excluding underperforming locations: {locations}"
            )

        # Budget reallocation
        if summary.budget_reallocation_potential > 20:
            recommendations.append(
                f"Potential {summary.budget_reallocation_potential:.1f}% improvement through budget reallocation"
            )

        # Expansion opportunities
        if summary.expansion_opportunities:
            locations = ", ".join(summary.expansion_opportunities[:3])
            recommendations.append(
                f"Consider expanding to high-performing locations: {locations}"
            )

        return recommendations

    def _create_dashboard_metrics(
        self, summary: GeoPerformanceSummary, insights: list[LocationInsight]
    ) -> dict[str, float]:
        """Create key metrics for dashboard display."""
        top_performer_score = insights[0].performance_score if insights else 0.0
        bottom_performer_score = insights[-1].performance_score if insights else 0.0

        return {
            "total_locations": float(summary.total_locations),
            "average_cpa": summary.average_cpa,
            "average_roas": summary.average_roas,
            "budget_reallocation_potential": summary.budget_reallocation_potential,
            "top_performer_score": top_performer_score,
            "bottom_performer_score": bottom_performer_score,
            "performance_spread": top_performer_score - bottom_performer_score,
            "high_performers_count": float(
                len([i for i in insights if i.performance_score >= 80])
            ),
            "underperformers_count": float(
                len([i for i in insights if i.performance_score <= 40])
            ),
        }

    def get_name(self) -> str:
        """Return analyzer name."""
        return "geo_performance"

    def get_description(self) -> str:
        """Return analyzer description."""
        return "Analyzes geographic performance to identify location-based optimization opportunities"

    async def _enhance_with_store_visit_data(
        self,
        performance_data: list[GeoPerformanceData],
        start_date: datetime,
        end_date: datetime,
    ) -> list[GeoPerformanceData]:
        """Enhance geographic performance data with GA4 store visit data.

        Args:
            performance_data: Current geographic performance data
            start_date: Analysis start date
            end_date: Analysis end date

        Returns:
            Enhanced performance data with store visit metrics
        """
        if not self.ga4_client:
            logger.warning("GA4 client not available, skipping store visit enhancement")
            return performance_data

        try:
            # Get store location data from proper store location service
            store_locations = self._get_store_locations(performance_data)

            if not store_locations:
                logger.warning("No store location data available for GA4 attribution")
                return performance_data

            # Get store visit attribution data from GA4
            store_visits = self.ga4_client.get_store_visit_attribution(
                start_date, end_date, store_locations
            )

            if not store_visits:
                logger.info("No store visit data found in GA4 for date range")
                return performance_data

            # Create lookup for store visits by location
            visits_by_location = {}
            for visit in store_visits:
                location_id = visit.get("store_location_id", "")
                if location_id:
                    if location_id not in visits_by_location:
                        visits_by_location[location_id] = []
                    visits_by_location[location_id].append(visit)

            # Enhance performance data with store visit metrics
            enhanced_data = []
            for geo_data in performance_data:
                store_id = f"store_{geo_data.location_name.lower().replace(' ', '_')}"
                store_visits_for_location = visits_by_location.get(store_id, [])

                if store_visits_for_location:
                    # Calculate store visit metrics
                    total_store_visits = len(store_visits_for_location)
                    converted_visits = sum(
                        1
                        for visit in store_visits_for_location
                        if visit.get("store_visit_converted", False)
                    )
                    total_store_revenue = sum(
                        visit.get("conversion_value", 0)
                        for visit in store_visits_for_location
                        if visit.get("conversion_value")
                    )
                    avg_distance = (
                        sum(
                            visit.get("distance_to_store", 0)
                            for visit in store_visits_for_location
                        )
                        / total_store_visits
                        if total_store_visits > 0
                        else 0
                    )

                    # Calculate store visit conversion rate
                    store_visit_rate = (
                        (total_store_visits / geo_data.clicks * 100)
                        if geo_data.clicks > 0
                        else 0.0
                    )
                    store_conversion_rate = (
                        (converted_visits / total_store_visits * 100)
                        if total_store_visits > 0
                        else 0.0
                    )

                    # Create enhanced geo data with store visit metrics
                    enhanced_geo_data = GeoPerformanceData(
                        location_name=geo_data.location_name,
                        level=geo_data.level,
                        impressions=geo_data.impressions,
                        clicks=geo_data.clicks,
                        cost=geo_data.cost,
                        conversions=geo_data.conversions,
                        conversion_value=geo_data.conversion_value,
                        ctr=geo_data.ctr,
                        avg_cpc=geo_data.avg_cpc,
                        cost_per_conversion=geo_data.cost_per_conversion,
                        roas=geo_data.roas,
                        performance_score=geo_data.performance_score,
                        # Add store visit data as metadata for now
                        # In a full implementation, these would be proper fields
                    )

                    # Store visit data in metadata for reporting
                    if not hasattr(enhanced_geo_data, "metadata"):
                        enhanced_geo_data.metadata = {}
                    enhanced_geo_data.metadata.update(
                        {
                            "store_visits": total_store_visits,
                            "store_visit_rate": store_visit_rate,
                            "store_conversions": converted_visits,
                            "store_conversion_rate": store_conversion_rate,
                            "store_revenue": total_store_revenue,
                            "avg_distance_km": avg_distance,
                            "ga4_enhanced": True,
                        }
                    )

                    enhanced_data.append(enhanced_geo_data)

                    logger.info(
                        f"Enhanced {geo_data.location_name} with GA4 store visit data: "
                        f"{total_store_visits} visits, {store_conversion_rate:.1f}% conversion rate"
                    )
                else:
                    enhanced_data.append(geo_data)

            logger.info(
                f"Enhanced {len([d for d in enhanced_data if hasattr(d, 'metadata') and d.metadata.get('ga4_enhanced')])} locations with GA4 store visit data"
            )
            return enhanced_data

        except Exception as e:
            logger.error(
                f"Failed to enhance geographic data with GA4 store visits: {e}"
            )
            # Return original data if GA4 enhancement fails
            return performance_data

    def _get_store_locations(self, performance_data: List[Any]) -> List[Dict[str, Any]]:
        """Get store location data from store location service.

        This method should be implemented to connect to your actual store location
        database or service (e.g., Google My Business, internal store database).

        Args:
            performance_data: Geographic performance data to match against stores

        Returns:
            List of store location dictionaries with keys:
            - store_id: Unique identifier for the store
            - latitude: Store latitude coordinate
            - longitude: Store longitude coordinate
            - location_name: Human readable store location name
            - address: Optional store address
        """
        # TODO: Replace with actual store location service integration
        # Example integrations:
        # - Google My Business API
        # - Internal store database
        # - Third-party store locator service

        logger.warning(
            "Store location service not implemented. "
            "Please implement _get_store_locations() method to connect to your "
            "store location database for accurate store visit attribution."
        )

        return []  # Return empty list until proper implementation
