"""GA4 Analytics Analyzer for real-time analytics and campaign optimization.

This analyzer provides real-time GA4 metrics integration for enhanced
campaign performance monitoring and optimization recommendations.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import pandas as pd

from paidsearchnav.core.config import GA4Config
from paidsearchnav.core.interfaces import Analyzer
from paidsearchnav.core.models.analysis import AnalysisResult
from paidsearchnav.platforms.ga4.client import GA4APIError, GA4DataClient
from paidsearchnav.platforms.ga4.models import (
    GA4ConversionMetrics,
    GA4DataFreshness,
    GA4LandingPageMetrics,
    GA4SessionMetrics,
)

logger = logging.getLogger(__name__)


class GA4AnalyticsAnalyzer(Analyzer):
    """Analyzer for real-time GA4 metrics and performance insights."""

    def __init__(self, config: GA4Config):
        """Initialize the GA4 analytics analyzer.

        Args:
            config: GA4 configuration
        """
        self.config = config
        self.client = GA4DataClient(config)
        self._data_freshness_cache: Dict[str, GA4DataFreshness] = {}

    def get_name(self) -> str:
        """Get analyzer name."""
        return "GA4 Analytics Analyzer"

    def get_description(self) -> str:
        """Get analyzer description."""
        return (
            "Real-time GA4 analytics integration providing session metrics, "
            "conversion tracking, and performance insights for campaign optimization"
        )

    async def analyze(
        self,
        customer_id: str,
        start_date: datetime,
        end_date: datetime,
        **kwargs: Any,
    ) -> AnalysisResult:
        """Run GA4 analytics analysis.

        Args:
            customer_id: Customer identifier
            start_date: Analysis start date
            end_date: Analysis end date
            **kwargs: Additional analysis parameters

        Returns:
            GA4 analysis results
        """
        logger.info(
            f"Starting GA4 analytics analysis for customer {customer_id} "
            f"from {start_date} to {end_date}"
        )

        try:
            # Check data freshness
            data_freshness = await self._check_data_freshness()

            # Get real-time metrics if available
            realtime_metrics = None
            if self.config.enable_realtime_data:
                realtime_metrics = await self._get_realtime_insights()

            # Get historical session metrics
            session_metrics = await self._get_session_analysis(start_date, end_date)

            # Get conversion analysis
            conversion_metrics = await self._get_conversion_analysis(
                start_date, end_date
            )

            # Get landing page performance
            landing_page_metrics = await self._get_landing_page_analysis(
                start_date, end_date
            )

            # Generate insights and recommendations
            insights = self._generate_insights(
                session_metrics,
                conversion_metrics,
                landing_page_metrics,
                realtime_metrics,
            )

            # Create analysis result
            result_data = {
                "customer_id": customer_id,
                "analysis_type": "ga4_analytics",
                "start_date": start_date,
                "end_date": end_date,
                "data_freshness": data_freshness.dict(),
                "session_metrics": session_metrics,
                "conversion_metrics": conversion_metrics,
                "landing_page_metrics": landing_page_metrics,
                "insights": insights,
                "recommendations": self._generate_recommendations(insights),
                "metadata": {
                    "property_id": self.config.property_id,
                    "realtime_enabled": self.config.enable_realtime_data,
                    "analysis_timestamp": datetime.utcnow().isoformat(),
                    "quota_usage": self.client.get_request_stats(),
                },
            }

            if realtime_metrics:
                result_data["realtime_metrics"] = realtime_metrics

            return AnalysisResult(
                analyzer_name=self.get_name(),
                customer_id=customer_id,
                analysis_date=datetime.utcnow(),
                data=result_data,
                success=True,
                errors=[],
                metadata={
                    "data_freshness_hours": data_freshness.data_lag_hours,
                    "total_sessions_analyzed": self._calculate_total_sessions(
                        session_metrics
                    ),
                    "ga4_property_id": self.config.property_id,
                },
            )

        except Exception as e:
            logger.error(f"GA4 analytics analysis failed: {e}")
            return AnalysisResult(
                analyzer_name=self.get_name(),
                customer_id=customer_id,
                analysis_date=datetime.utcnow(),
                data={},
                success=False,
                errors=[str(e)],
                metadata={"error_type": type(e).__name__},
            )

    async def _check_data_freshness(self) -> GA4DataFreshness:
        """Check GA4 data freshness for the property."""
        try:
            # Get latest data timestamp from GA4
            realtime_data = await self.client.get_realtime_metrics(
                dimensions=["date"], metrics=["activeUsers"], limit=1
            )

            # Estimate data lag based on real-time API availability
            current_time = datetime.utcnow()
            if realtime_data["row_count"] > 0:
                data_lag_hours = 0.1  # Real-time data is very fresh
                last_data_timestamp = current_time - timedelta(minutes=6)
                is_realtime = True
            else:
                # Fall back to historical API - typically 24-48 hour lag
                data_lag_hours = 24.0
                last_data_timestamp = current_time - timedelta(hours=24)
                is_realtime = False

            freshness = GA4DataFreshness(
                property_id=self.config.property_id,
                last_data_timestamp=last_data_timestamp,
                data_lag_hours=data_lag_hours,
                is_realtime=is_realtime,
            )

            self._data_freshness_cache[self.config.property_id] = freshness
            return freshness

        except Exception as e:
            logger.warning(f"Could not determine data freshness: {e}")
            # Return conservative estimate
            return GA4DataFreshness(
                property_id=self.config.property_id,
                last_data_timestamp=datetime.utcnow() - timedelta(hours=48),
                data_lag_hours=48.0,
                is_realtime=False,
            )

    async def _get_realtime_insights(self) -> Optional[Dict[str, Any]]:
        """Get real-time insights from GA4."""
        try:
            # Get current active users by source
            active_users_data = await self.client.get_realtime_metrics(
                dimensions=["source", "medium", "country"],
                metrics=["activeUsers", "conversions"],
                limit=100,
            )

            # Get real-time conversion events
            conversions_data = await self.client.get_realtime_metrics(
                dimensions=["eventName", "source", "medium"],
                metrics=["conversions"],
                filters={"eventName": "purchase,submit_lead_form,phone_call"},
                limit=50,
            )

            return {
                "active_users": active_users_data,
                "recent_conversions": conversions_data,
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.warning(f"Failed to get real-time insights: {e}")
            return None

    async def _get_session_analysis(
        self, start_date: datetime, end_date: datetime
    ) -> List[GA4SessionMetrics]:
        """Get session metrics analysis."""
        try:
            # Format dates for GA4 API
            start_str = start_date.strftime("%Y-%m-%d")
            end_str = end_date.strftime("%Y-%m-%d")

            session_data = await self.client.get_historical_metrics(
                start_date=start_str,
                end_date=end_str,
                dimensions=["source", "medium", "country", "deviceCategory"],
                metrics=[
                    "sessions",
                    "bounceRate",
                    "averageSessionDuration",
                    "conversions",
                    "totalRevenue",
                    "sessionConversionRate",
                ],
                limit=5000,
            )

            session_metrics = []
            for row in session_data.get("rows", []):
                try:
                    metrics = GA4SessionMetrics(
                        property_id=self.config.property_id,
                        source=row.get("source", ""),
                        medium=row.get("medium", ""),
                        country=row.get("country", ""),
                        device_category=row.get("deviceCategory", ""),
                        sessions=int(row.get("sessions", 0)),
                        bounce_rate=float(row.get("bounceRate", 0.0)),
                        avg_session_duration=float(
                            row.get("averageSessionDuration", 0.0)
                        ),
                        conversions=float(row.get("conversions", 0.0)),
                        revenue=float(row.get("totalRevenue", 0.0)),
                        conversion_rate=float(row.get("sessionConversionRate", 0.0)),
                    )
                    session_metrics.append(metrics)
                except Exception as e:
                    logger.warning(f"Failed to parse session row: {e}")
                    continue

            return session_metrics

        except Exception as e:
            logger.error(f"Failed to get session analysis: {e}")
            raise GA4APIError(f"Session analysis failed: {e}")

    async def _get_conversion_analysis(
        self, start_date: datetime, end_date: datetime
    ) -> List[GA4ConversionMetrics]:
        """Get conversion metrics analysis."""
        try:
            start_str = start_date.strftime("%Y-%m-%d")
            end_str = end_date.strftime("%Y-%m-%d")

            conversion_data = await self.client.get_conversion_metrics(
                start_date=start_str,
                end_date=end_str,
                conversion_events=["purchase", "generate_lead", "contact"],
            )

            conversion_metrics = []
            for row in conversion_data.get("rows", []):
                try:
                    metrics = GA4ConversionMetrics(
                        property_id=self.config.property_id,
                        source=row.get("source", ""),
                        medium=row.get("medium", ""),
                        campaign_name=row.get("campaignName", ""),
                        country=row.get("country", ""),
                        conversions=float(row.get("conversions", 0.0)),
                        revenue=float(row.get("totalRevenue", 0.0)),
                        conversion_rate=float(row.get("sessionConversionRate", 0.0)),
                    )
                    conversion_metrics.append(metrics)
                except Exception as e:
                    logger.warning(f"Failed to parse conversion row: {e}")
                    continue

            return conversion_metrics

        except Exception as e:
            logger.error(f"Failed to get conversion analysis: {e}")
            raise GA4APIError(f"Conversion analysis failed: {e}")

    async def _get_landing_page_analysis(
        self, start_date: datetime, end_date: datetime
    ) -> List[GA4LandingPageMetrics]:
        """Get landing page performance analysis."""
        try:
            start_str = start_date.strftime("%Y-%m-%d")
            end_str = end_date.strftime("%Y-%m-%d")

            landing_page_data = await self.client.get_landing_page_metrics(
                start_date=start_str, end_date=end_str
            )

            landing_page_metrics = []
            for row in landing_page_data.get("rows", []):
                try:
                    metrics = GA4LandingPageMetrics(
                        property_id=self.config.property_id,
                        landing_page=row.get("landingPage", ""),
                        source=row.get("source", ""),
                        medium=row.get("medium", ""),
                        country=row.get("country", ""),
                        sessions=int(row.get("sessions", 0)),
                        bounce_rate=float(row.get("bounceRate", 0.0)),
                        avg_session_duration=float(
                            row.get("averageSessionDuration", 0.0)
                        ),
                        exit_rate=float(row.get("exitRate", 0.0)),
                        conversions=float(row.get("conversions", 0.0)),
                        revenue=float(row.get("totalRevenue", 0.0)),
                    )
                    landing_page_metrics.append(metrics)
                except Exception as e:
                    logger.warning(f"Failed to parse landing page row: {e}")
                    continue

            return landing_page_metrics

        except Exception as e:
            logger.error(f"Failed to get landing page analysis: {e}")
            raise GA4APIError(f"Landing page analysis failed: {e}")

    def _generate_insights(
        self,
        session_metrics: List[GA4SessionMetrics],
        conversion_metrics: List[GA4ConversionMetrics],
        landing_page_metrics: List[GA4LandingPageMetrics],
        realtime_metrics: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Generate insights from GA4 metrics."""
        insights = {
            "session_insights": self._analyze_session_patterns(session_metrics),
            "conversion_insights": self._analyze_conversion_patterns(
                conversion_metrics
            ),
            "landing_page_insights": self._analyze_landing_page_patterns(
                landing_page_metrics
            ),
            "cross_platform_insights": self._analyze_cross_platform_patterns(
                session_metrics, conversion_metrics
            ),
        }

        if realtime_metrics:
            insights["realtime_insights"] = self._analyze_realtime_patterns(
                realtime_metrics
            )

        return insights

    def _analyze_session_patterns(
        self, session_metrics: List[GA4SessionMetrics]
    ) -> Dict[str, Any]:
        """Analyze session patterns for optimization opportunities."""
        if not session_metrics:
            return {"warning": "No session data available"}

        df = pd.DataFrame([metric.dict() for metric in session_metrics])

        insights = {
            "total_sessions": df["sessions"].sum(),
            "avg_bounce_rate": df["bounce_rate"].mean(),
            "avg_session_duration": df["avg_session_duration"].mean(),
            "total_conversions": df["conversions"].sum(),
            "total_revenue": df["revenue"].sum(),
            "top_sources": df.groupby("source")["sessions"].sum().nlargest(5).to_dict(),
            "best_performing_countries": (
                df.groupby("country")["conversion_rate"].mean().nlargest(3).to_dict()
            ),
            "device_performance": (
                df.groupby("device_category")
                .agg(
                    {
                        "sessions": "sum",
                        "bounce_rate": "mean",
                        "conversion_rate": "mean",
                    }
                )
                .to_dict()
            ),
        }

        # Identify high-bounce rate sources
        high_bounce_sources = (
            df[df["bounce_rate"] > 0.7].groupby("source")["sessions"].sum()
        )
        if not high_bounce_sources.empty:
            insights["high_bounce_sources"] = high_bounce_sources.to_dict()

        # Identify low-performing countries
        low_performance_countries = (
            df[df["conversion_rate"] < 0.01].groupby("country")["sessions"].sum()
        )
        if not low_performance_countries.empty:
            insights["low_performance_countries"] = low_performance_countries.to_dict()

        return insights

    def _analyze_conversion_patterns(
        self, conversion_metrics: List[GA4ConversionMetrics]
    ) -> Dict[str, Any]:
        """Analyze conversion patterns for attribution insights."""
        if not conversion_metrics:
            return {"warning": "No conversion data available"}

        df = pd.DataFrame([metric.dict() for metric in conversion_metrics])

        insights = {
            "total_conversions": df["conversions"].sum(),
            "total_revenue": df["revenue"].sum(),
            "avg_conversion_rate": df["conversion_rate"].mean(),
            "top_converting_sources": df.groupby("source")["conversions"]
            .sum()
            .nlargest(5)
            .to_dict(),
            "highest_revenue_campaigns": (
                df.groupby("campaign_name")["revenue"].sum().nlargest(5).to_dict()
            ),
            "conversion_by_country": df.groupby("country")["conversions"]
            .sum()
            .to_dict(),
        }

        # Calculate ROAS by source/medium
        source_medium_roas = (
            df.groupby(["source", "medium"])
            .apply(
                lambda x: x["revenue"].sum()
                / max(x["conversions"].sum() * self.config.average_cpa_usd, 1)
            )
            .to_dict()
        )
        insights["roas_by_source_medium"] = {
            f"{source}/{medium}": roas
            for (source, medium), roas in source_medium_roas.items()
        }

        return insights

    def _analyze_landing_page_patterns(
        self, landing_page_metrics: List[GA4LandingPageMetrics]
    ) -> Dict[str, Any]:
        """Analyze landing page performance patterns."""
        if not landing_page_metrics:
            return {"warning": "No landing page data available"}

        df = pd.DataFrame([metric.dict() for metric in landing_page_metrics])

        insights = {
            "total_landing_page_sessions": df["sessions"].sum(),
            "avg_bounce_rate": df["bounce_rate"].mean(),
            "avg_exit_rate": df["exit_rate"].mean(),
            "best_performing_pages": (
                df.groupby("landing_page")["conversion_rate"]
                .mean()
                .nlargest(5)
                .to_dict()
            ),
            "highest_traffic_pages": (
                df.groupby("landing_page")["sessions"].sum().nlargest(5).to_dict()
            ),
            "pages_needing_optimization": (
                df[df["bounce_rate"] > 0.8]
                .groupby("landing_page")["sessions"]
                .sum()
                .to_dict()
            ),
        }

        # Identify pages with high exit rates but good traffic
        high_exit_good_traffic = (
            df[(df["exit_rate"] > 0.6) & (df["sessions"] > 100)]
            .groupby("landing_page")["sessions"]
            .sum()
        )

        if not high_exit_good_traffic.empty:
            insights["optimization_opportunities"] = high_exit_good_traffic.to_dict()

        return insights

    def _analyze_cross_platform_patterns(
        self,
        session_metrics: List[GA4SessionMetrics],
        conversion_metrics: List[GA4ConversionMetrics],
    ) -> Dict[str, Any]:
        """Analyze cross-platform patterns between GA4 and Google Ads data."""
        insights = {
            "data_integration_status": "active",
            "attribution_coverage": self._calculate_attribution_coverage(
                session_metrics, conversion_metrics
            ),
            "source_medium_performance": self._analyze_source_medium_performance(
                session_metrics, conversion_metrics
            ),
        }

        return insights

    def _analyze_realtime_patterns(
        self, realtime_metrics: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze real-time metrics for immediate insights."""
        insights = {
            "current_active_users": 0,
            "recent_conversions": 0,
            "top_current_sources": {},
            "real_time_alerts": [],
        }

        # Analyze active users
        active_users_data = realtime_metrics.get("active_users", {})
        if active_users_data.get("rows"):
            total_active = sum(
                int(row.get("activeUsers", 0)) for row in active_users_data["rows"]
            )
            insights["current_active_users"] = total_active

            # Top current sources
            source_users = {}
            for row in active_users_data["rows"]:
                source = row.get("source", "unknown")
                users = int(row.get("activeUsers", 0))
                source_users[source] = source_users.get(source, 0) + users

            insights["top_current_sources"] = dict(
                sorted(source_users.items(), key=lambda x: x[1], reverse=True)[:5]
            )

        # Analyze recent conversions
        conversions_data = realtime_metrics.get("recent_conversions", {})
        if conversions_data.get("rows"):
            total_conversions = sum(
                float(row.get("conversions", 0)) for row in conversions_data["rows"]
            )
            insights["recent_conversions"] = total_conversions

        return insights

    def _generate_recommendations(
        self, insights: Dict[str, Any]
    ) -> List[Dict[str, str]]:
        """Generate actionable recommendations from GA4 insights."""
        recommendations = []

        # Session-based recommendations
        session_insights = insights.get("session_insights", {})
        if session_insights.get("avg_bounce_rate", 0) > 0.7:
            recommendations.append(
                {
                    "type": "landing_page_optimization",
                    "priority": "high",
                    "title": "Optimize High Bounce Rate Pages",
                    "description": (
                        f"Average bounce rate of {session_insights.get('avg_bounce_rate', 0):.1%} "
                        "indicates landing page optimization opportunities."
                    ),
                    "action": "Review top traffic landing pages for user experience improvements",
                }
            )

        # Source-based recommendations
        high_bounce_sources = session_insights.get("high_bounce_sources", {})
        if high_bounce_sources:
            top_bounce_source = max(high_bounce_sources, key=high_bounce_sources.get)
            recommendations.append(
                {
                    "type": "traffic_source_optimization",
                    "priority": "medium",
                    "title": f"Optimize {top_bounce_source} Traffic Quality",
                    "description": (
                        f"Source '{top_bounce_source}' has high bounce rate with "
                        f"{high_bounce_sources[top_bounce_source]} sessions"
                    ),
                    "action": "Review ad creative and targeting for this source",
                }
            )

        # Conversion-based recommendations
        conversion_insights = insights.get("conversion_insights", {})
        if conversion_insights.get("avg_conversion_rate", 0) < 0.02:  # Less than 2%
            recommendations.append(
                {
                    "type": "conversion_optimization",
                    "priority": "high",
                    "title": "Improve Conversion Rate",
                    "description": (
                        f"Low conversion rate of {conversion_insights.get('avg_conversion_rate', 0):.1%} "
                        "suggests conversion funnel optimization needed"
                    ),
                    "action": "Analyze conversion funnel and implement A/B tests",
                }
            )

        # Real-time recommendations
        realtime_insights = insights.get("realtime_insights")
        if realtime_insights and realtime_insights.get("current_active_users", 0) > 100:
            recommendations.append(
                {
                    "type": "real_time_opportunity",
                    "priority": "medium",
                    "title": "High Current Traffic Detected",
                    "description": (
                        f"Currently {realtime_insights['current_active_users']} active users. "
                        "Consider real-time bid adjustments."
                    ),
                    "action": "Monitor real-time performance and adjust bids if needed",
                }
            )

        return recommendations

    def _calculate_attribution_coverage(
        self,
        session_metrics: List[GA4SessionMetrics],
        conversion_metrics: List[GA4ConversionMetrics],
    ) -> float:
        """Calculate attribution coverage percentage."""
        if not session_metrics or not conversion_metrics:
            return 0.0

        total_ga4_sessions = sum(metric.sessions for metric in session_metrics)
        total_ga4_conversions = sum(metric.conversions for metric in conversion_metrics)

        if total_ga4_sessions == 0:
            return 0.0

        # Simple coverage calculation - can be enhanced with gclid matching
        return min(100.0, (total_ga4_conversions / total_ga4_sessions) * 100)

    def _analyze_source_medium_performance(
        self,
        session_metrics: List[GA4SessionMetrics],
        conversion_metrics: List[GA4ConversionMetrics],
    ) -> Dict[str, Any]:
        """Analyze source/medium performance across session and conversion data."""
        performance = {}

        # Group session metrics by source/medium
        session_df = pd.DataFrame([metric.dict() for metric in session_metrics])
        if not session_df.empty:
            session_performance = (
                session_df.groupby(["source", "medium"])
                .agg(
                    {
                        "sessions": "sum",
                        "bounce_rate": "mean",
                        "conversion_rate": "mean",
                        "revenue": "sum",
                    }
                )
                .to_dict("index")
            )

            performance["session_performance"] = {
                f"{source}/{medium}": metrics
                for (source, medium), metrics in session_performance.items()
            }

        # Group conversion metrics by source/medium
        conversion_df = pd.DataFrame([metric.dict() for metric in conversion_metrics])
        if not conversion_df.empty:
            conversion_performance = (
                conversion_df.groupby(["source", "medium"])
                .agg(
                    {"conversions": "sum", "revenue": "sum", "conversion_rate": "mean"}
                )
                .to_dict("index")
            )

            performance["conversion_performance"] = {
                f"{source}/{medium}": metrics
                for (source, medium), metrics in conversion_performance.items()
            }

        return performance

    def _calculate_total_sessions(
        self, session_metrics: List[GA4SessionMetrics]
    ) -> int:
        """Calculate total sessions from metrics."""
        return sum(metric.sessions for metric in session_metrics)

    async def get_realtime_dashboard_data(self) -> Dict[str, Any]:
        """Get real-time dashboard data for live monitoring.

        Returns:
            Real-time dashboard data
        """
        try:
            # Get current active users and traffic sources
            active_users = await self.client.get_realtime_metrics(
                dimensions=["source", "medium", "country"],
                metrics=["activeUsers"],
                limit=50,
            )

            # Get recent conversions
            recent_conversions = await self.client.get_realtime_metrics(
                dimensions=["eventName"], metrics=["conversions"], limit=20
            )

            dashboard_data = {
                "active_users": active_users,
                "recent_conversions": recent_conversions,
                "last_updated": datetime.utcnow().isoformat(),
                "property_id": self.config.property_id,
                "data_freshness": "real-time"
                if self.config.enable_realtime_data
                else "historical",
            }

            return dashboard_data

        except Exception as e:
            logger.error(f"Failed to get real-time dashboard data: {e}")
            raise GA4APIError(f"Real-time dashboard data failed: {e}")

    async def validate_data_quality(self) -> Dict[str, Any]:
        """Validate GA4 data quality and completeness."""
        try:
            # Test basic API connectivity
            connection_success, connection_message = self.client.test_connection()

            if not connection_success:
                return {"status": "failed", "message": connection_message, "checks": {}}

            # Run data quality checks
            checks = {}

            # Check data availability
            yesterday_data = await self.client.get_historical_metrics(
                start_date="yesterday",
                end_date="yesterday",
                dimensions=["source"],
                metrics=["sessions"],
                limit=1,
            )

            checks["data_availability"] = {
                "status": "pass" if yesterday_data.get("row_count", 0) > 0 else "fail",
                "message": f"Data available: {yesterday_data.get('row_count', 0)} rows",
            }

            # Check real-time data if enabled
            if self.config.enable_realtime_data:
                try:
                    realtime_data = await self.client.get_realtime_metrics(
                        dimensions=["source"], metrics=["activeUsers"], limit=1
                    )
                    checks["realtime_availability"] = {
                        "status": "pass"
                        if realtime_data.get("row_count", 0) >= 0
                        else "fail",
                        "message": "Real-time data accessible",
                    }
                except Exception as e:
                    checks["realtime_availability"] = {
                        "status": "warning",
                        "message": f"Real-time data not available: {e}",
                    }

            # Check property metadata
            try:
                metadata = self.client.authenticator.get_property_metadata(
                    self.config.property_id
                )
                checks["property_metadata"] = {
                    "status": "pass" if metadata else "fail",
                    "message": f"Property metadata accessible: {len(metadata.get('dimensions', []))} dimensions, {len(metadata.get('metrics', []))} metrics"
                    if metadata
                    else "No metadata available",
                }
            except Exception as e:
                checks["property_metadata"] = {
                    "status": "fail",
                    "message": f"Property metadata failed: {e}",
                }

            overall_status = (
                "pass"
                if all(check["status"] == "pass" for check in checks.values())
                else "warning"
            )

            return {
                "status": overall_status,
                "message": "GA4 data quality validation completed",
                "checks": checks,
                "property_id": self.config.property_id,
                "checked_at": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Data quality validation failed: {e}")
            return {
                "status": "failed",
                "message": f"Data quality validation failed: {e}",
                "checks": {},
            }
