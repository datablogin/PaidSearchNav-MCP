"""Cross-platform attribution analyzer for comprehensive customer journey analysis."""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List

import numpy as np

from paidsearchnav.attribution.engine import AttributionEngine
from paidsearchnav.attribution.journey_builder import CustomerJourneyBuilder
from paidsearchnav.attribution.ml_attribution import MLAttributionAnalyzer
from paidsearchnav.attribution.models import (
    AttributionModel,
    AttributionModelType,
    CrossPlatformMetrics,
)
from paidsearchnav.core.config import BigQueryConfig, GA4Config
from paidsearchnav.core.interfaces import Analyzer
from paidsearchnav.core.models.analysis import AnalysisResult
from paidsearchnav.ml.causal_service import CausalMLService
from paidsearchnav.platforms.bigquery.service import BigQueryService
from paidsearchnav.platforms.ga4.client import GA4DataClient

logger = logging.getLogger(__name__)


class AttributionAnalyzerConfig:
    """Configuration class for attribution analyzer thresholds and parameters."""

    # Performance settings
    BATCH_SIZE = 50
    BIGQUERY_TIMEOUT = 60.0
    GA4_TIMEOUT = 30.0

    # Data quality thresholds
    MIN_GCLID_MATCH_RATE = 0.7
    MIN_MULTI_TOUCH_RATE = 0.6
    MIN_ML_JOURNEYS = 10

    # Analysis thresholds
    HIGH_VARIANCE_THRESHOLD = 1000.0
    SAME_DAY_JOURNEY_HIGH_THRESHOLD = 0.8
    SAME_DAY_JOURNEY_LOW_THRESHOLD = 0.3
    SECOND_CHANNEL_SIGNIFICANCE_THRESHOLD = 0.2

    # Customer ID validation
    MAX_CUSTOMER_ID_LENGTH = 50


class CrossPlatformAttributionAnalyzer(Analyzer):
    """Advanced cross-platform attribution analyzer combining Google Ads, GA4, and ML insights."""

    def __init__(
        self,
        bigquery_config: BigQueryConfig,
        ga4_config: GA4Config,
        causal_service: CausalMLService,
    ):
        """Initialize cross-platform attribution analyzer.

        Args:
            bigquery_config: BigQuery configuration
            ga4_config: GA4 configuration
            causal_service: ML causal inference service
        """
        self.bigquery_config = bigquery_config
        self.ga4_config = ga4_config
        self.causal_service = causal_service

        # Initialize clients and services
        self.bigquery_client = BigQueryService(bigquery_config)
        self.ga4_client = GA4DataClient(ga4_config)
        self.journey_builder = CustomerJourneyBuilder(
            self.bigquery_client, self.ga4_client
        )
        self.attribution_engine = AttributionEngine()
        self.ml_analyzer = MLAttributionAnalyzer(causal_service)

        # Default attribution models
        self._default_models = self._create_default_attribution_models()

    def get_name(self) -> str:
        """Get analyzer name."""
        return "Cross-Platform Attribution Analyzer"

    def get_description(self) -> str:
        """Get analyzer description."""
        return (
            "Advanced multi-touch attribution analysis combining Google Ads, GA4, "
            "and ML-powered predictive insights for comprehensive customer journey optimization"
        )

    async def analyze(
        self,
        customer_id: str,
        start_date: datetime,
        end_date: datetime,
        attribution_model_type: str = "time_decay",
        include_ml_predictions: bool = True,
        **kwargs: Any,
    ) -> AnalysisResult:
        """Run cross-platform attribution analysis.

        Args:
            customer_id: Customer identifier
            start_date: Analysis start date
            end_date: Analysis end date
            attribution_model_type: Attribution model to use
            include_ml_predictions: Whether to include ML predictions
            **kwargs: Additional analysis parameters

        Returns:
            Comprehensive attribution analysis results
        """
        # Input validation for security
        if not customer_id or not customer_id.strip():
            raise ValueError("customer_id parameter is required and cannot be empty")

        if not isinstance(customer_id, str):
            raise TypeError("customer_id must be a string")

        if len(customer_id) > AttributionAnalyzerConfig.MAX_CUSTOMER_ID_LENGTH:
            raise ValueError(
                f"customer_id exceeds maximum length of {AttributionAnalyzerConfig.MAX_CUSTOMER_ID_LENGTH} characters"
            )

        # Sanitize customer_id to prevent injection
        customer_id = customer_id.strip()

        logger.info(f"Starting cross-platform attribution analysis for {customer_id}")

        try:
            # Build customer journeys
            (
                journeys,
                journey_touches,
            ) = await self.journey_builder.build_customer_journeys(
                customer_id, start_date, end_date, include_non_converting=True
            )

            if not journeys:
                return self._create_empty_result(
                    customer_id, "No customer journeys found"
                )

            # Enrich with store visits if available
            (
                journeys,
                journey_touches,
            ) = await self.journey_builder.enrich_with_store_visits(
                journeys, journey_touches
            )

            # Get attribution model
            attribution_model = self._get_attribution_model(attribution_model_type)

            # Calculate attribution for all journeys using async batch processing
            attribution_tasks = []
            for journey in journeys:
                touches = journey_touches.get(journey.journey_id, [])
                if touches:
                    task = self.attribution_engine.calculate_attribution(
                        journey, touches, attribution_model
                    )
                    attribution_tasks.append(task)

            # Process in batches to avoid overwhelming the system
            batch_size = AttributionAnalyzerConfig.BATCH_SIZE
            attribution_results = []

            for i in range(0, len(attribution_tasks), batch_size):
                batch = attribution_tasks[i : i + batch_size]
                batch_results = await asyncio.gather(*batch, return_exceptions=True)

                # Filter out exceptions and log them
                for result in batch_results:
                    if isinstance(result, Exception):
                        logger.warning(f"Attribution calculation failed: {result}")
                    else:
                        attribution_results.append(result)

            # Generate cross-platform metrics
            cross_platform_metrics = await self._generate_cross_platform_metrics(
                customer_id, start_date, end_date, attribution_results
            )

            # ML predictions if enabled
            ml_insights = []
            if (
                include_ml_predictions
                and len(journeys) >= AttributionAnalyzerConfig.MIN_ML_JOURNEYS
            ):
                try:
                    # Train/load ML model
                    ml_model = await self.ml_analyzer.train_attribution_model(
                        customer_id, journeys, journey_touches
                    )

                    # Generate ML-powered insights
                    ml_insights = await self.ml_analyzer.generate_predictive_insights(
                        customer_id, journeys, journey_touches, ml_model
                    )

                except Exception as e:
                    logger.warning(f"ML analysis failed: {e}")

            # Generate journey insights
            journey_insights = self.journey_builder.get_journey_insights(
                journeys, journey_touches
            )

            # Identify anomalies
            anomalies = self.journey_builder.detect_anomalies_in_journeys(
                journeys, journey_touches
            )

            # Validate data quality
            quality_metrics = await self.journey_builder.validate_journey_data_quality(
                journeys, journey_touches
            )

            # Path analysis
            path_analysis = self.journey_builder.calculate_path_analysis(
                journeys, journey_touches
            )

            # Cross-device analysis
            cross_device_journeys = self.journey_builder.identify_cross_device_journeys(
                journeys, journey_touches
            )

            # Assisted conversions
            assisted_conversions = self.journey_builder.identify_assisted_conversions(
                journeys, journey_touches
            )

            # Generate recommendations
            recommendations = self._generate_recommendations(
                attribution_results, journey_insights, ml_insights, quality_metrics
            )

            # Create comprehensive result
            analysis_data = {
                "customer_id": customer_id,
                "analysis_type": "cross_platform_attribution",
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "attribution_model": attribution_model.model_name,
                "attribution_model_type": attribution_model_type,
                # Journey analysis
                "total_journeys": len(journeys),
                "converting_journeys": len([j for j in journeys if j.converted]),
                "total_touchpoints": sum(
                    len(touches) for touches in journey_touches.values()
                ),
                "journey_insights": journey_insights,
                "quality_metrics": quality_metrics,
                # Attribution results
                "attribution_summary": self.attribution_engine.get_attribution_summary(
                    attribution_results
                ),
                "cross_platform_metrics": cross_platform_metrics,
                "path_analysis": dict(list(path_analysis.items())[:10]),  # Top 10 paths
                # Advanced analysis
                "cross_device_journeys": len(cross_device_journeys),
                "assisted_conversions": dict(list(assisted_conversions.items())[:10]),
                "anomalies": anomalies[:20],  # Top 20 anomalies
                # ML insights
                "ml_insights": [insight.dict() for insight in ml_insights],
                "ml_predictions_included": include_ml_predictions
                and len(ml_insights) > 0,
                # Recommendations
                "recommendations": recommendations,
                "insights_count": len(ml_insights),
                # Metadata
                "analysis_timestamp": datetime.utcnow().isoformat(),
                "data_sources": ["google_ads", "ga4", "bigquery"],
                "ml_enabled": include_ml_predictions,
            }

            # Create successful result
            return AnalysisResult(
                analyzer_name=self.get_name(),
                customer_id=customer_id,
                analysis_date=datetime.utcnow(),
                data=analysis_data,
                success=True,
                errors=[],
                metadata={
                    "journeys_analyzed": len(journeys),
                    "attribution_model": attribution_model_type,
                    "data_quality_score": quality_metrics.get(
                        "data_quality_score", 0.0
                    ),
                    "ml_insights_generated": len(ml_insights),
                    "total_attributed_revenue": sum(
                        r.total_attributed_value for r in attribution_results
                    ),
                },
            )

        except Exception as e:
            logger.error(f"Cross-platform attribution analysis failed: {e}")
            return AnalysisResult(
                analyzer_name=self.get_name(),
                customer_id=customer_id,
                analysis_date=datetime.utcnow(),
                data={"error": str(e)},
                success=False,
                errors=[str(e)],
                metadata={"error_type": type(e).__name__},
            )

    def _create_default_attribution_models(self) -> Dict[str, AttributionModel]:
        """Create default attribution models."""
        return {
            "first_touch": AttributionModel(
                model_name="First Touch Attribution",
                model_type=AttributionModelType.FIRST_TOUCH,
            ),
            "last_touch": AttributionModel(
                model_name="Last Touch Attribution",
                model_type=AttributionModelType.LAST_TOUCH,
            ),
            "linear": AttributionModel(
                model_name="Linear Attribution",
                model_type=AttributionModelType.LINEAR,
            ),
            "time_decay": AttributionModel(
                model_name="Time Decay Attribution (7 days)",
                model_type=AttributionModelType.TIME_DECAY,
                time_decay_half_life_days=7.0,
            ),
            "position_based": AttributionModel(
                model_name="Position Based Attribution (40/60)",
                model_type=AttributionModelType.POSITION_BASED,
                position_based_first_weight=0.4,
                position_based_last_weight=0.6,
            ),
        }

    def _get_attribution_model(self, model_type: str) -> AttributionModel:
        """Get attribution model by type."""
        if model_type in self._default_models:
            return self._default_models[model_type]

        # Default to time decay if unknown
        logger.warning(f"Unknown attribution model '{model_type}', using time_decay")
        return self._default_models["time_decay"]

    async def _generate_cross_platform_metrics(
        self,
        customer_id: str,
        start_date: datetime,
        end_date: datetime,
        attribution_results: List,
    ) -> CrossPlatformMetrics:
        """Generate cross-platform performance metrics."""
        try:
            # Get Google Ads metrics from BigQuery
            google_ads_query = f"""
            SELECT
                SUM(clicks) as total_clicks,
                SUM(impressions) as total_impressions,
                SUM(cost_micros) / 1000000.0 as total_cost,
                SUM(conversions) as total_conversions,
                SUM(conversion_value_micros) / 1000000.0 as total_conversion_value
            FROM `{self.bigquery_client.config.project_id}.{self.bigquery_client.config.dataset_id}.search_terms`
            WHERE customer_id = @customer_id
              AND DATE(click_timestamp) BETWEEN @start_date AND @end_date
            """

            # Configure query parameters to prevent SQL injection
            from google.cloud import bigquery

            query_params = [
                bigquery.ScalarQueryParameter("customer_id", "STRING", customer_id),
                bigquery.ScalarQueryParameter(
                    "start_date", "DATE", start_date.strftime("%Y-%m-%d")
                ),
                bigquery.ScalarQueryParameter(
                    "end_date", "DATE", end_date.strftime("%Y-%m-%d")
                ),
            ]

            # Execute with timeout to prevent hanging operations
            google_ads_metrics = await asyncio.wait_for(
                self.bigquery_client.analytics.execute_parameterized_query(
                    google_ads_query, query_params
                ),
                timeout=AttributionAnalyzerConfig.BIGQUERY_TIMEOUT,
            )

            # Get GA4 metrics
            start_str = start_date.strftime("%Y-%m-%d")
            end_str = end_date.strftime("%Y-%m-%d")

            # Execute GA4 query with timeout
            ga4_metrics = await asyncio.wait_for(
                self.ga4_client.get_historical_metrics(
                    start_date=start_str,
                    end_date=end_str,
                    dimensions=[],
                    metrics=[
                        "sessions",
                        "users",
                        "screenPageViews",
                        "bounceRate",
                        "conversions",
                        "totalRevenue",
                    ],
                    limit=1,
                ),
                timeout=AttributionAnalyzerConfig.GA4_TIMEOUT,
            )

            # Calculate attribution metrics
            total_attributed_revenue = sum(
                r.total_attributed_value for r in attribution_results
            )
            google_ads_attributed = sum(
                r.google_ads_attributed_revenue for r in attribution_results
            )

            # GCLID match rate calculation
            total_touches_with_gclid = sum(
                len([t for t in journey_touches if hasattr(t, "gclid") and t.gclid])
                for journey_touches in [
                    getattr(r, "touch_attributions", []) for r in attribution_results
                ]
            )
            total_touches = sum(
                len(getattr(r, "touch_attributions", [])) for r in attribution_results
            )
            gclid_match_rate = (
                total_touches_with_gclid / total_touches if total_touches > 0 else 0.0
            )

            # Cross-platform ROAS
            google_ads_cost = (
                google_ads_metrics.iloc[0]["total_cost"]
                if not google_ads_metrics.empty
                else 0.0
            )
            cross_platform_roas = (
                google_ads_attributed / google_ads_cost if google_ads_cost > 0 else 0.0
            )

            # Multi-touch journey analysis
            multi_touch_journeys = sum(
                1
                for r in attribution_results
                if len(getattr(r, "touch_attributions", [])) > 1
            )
            single_touch_journeys = len(attribution_results) - multi_touch_journeys

            return CrossPlatformMetrics(
                customer_id=customer_id,
                date=start_date,
                google_ads_clicks=int(google_ads_metrics.iloc[0]["total_clicks"])
                if not google_ads_metrics.empty
                else 0,
                google_ads_impressions=int(
                    google_ads_metrics.iloc[0]["total_impressions"]
                )
                if not google_ads_metrics.empty
                else 0,
                google_ads_cost=google_ads_cost,
                google_ads_conversions=float(
                    google_ads_metrics.iloc[0]["total_conversions"]
                )
                if not google_ads_metrics.empty
                else 0.0,
                google_ads_conversion_value=float(
                    google_ads_metrics.iloc[0]["total_conversion_value"]
                )
                if not google_ads_metrics.empty
                else 0.0,
                ga4_sessions=int(ga4_metrics["rows"][0].get("sessions", 0))
                if ga4_metrics.get("rows")
                else 0,
                ga4_users=int(ga4_metrics["rows"][0].get("users", 0))
                if ga4_metrics.get("rows")
                else 0,
                ga4_pageviews=int(ga4_metrics["rows"][0].get("screenPageViews", 0))
                if ga4_metrics.get("rows")
                else 0,
                ga4_bounce_rate=float(ga4_metrics["rows"][0].get("bounceRate", 0.0))
                if ga4_metrics.get("rows")
                else 0.0,
                ga4_conversion_rate=float(
                    ga4_metrics["rows"][0].get("conversions", 0.0)
                )
                if ga4_metrics.get("rows")
                else 0.0,
                ga4_revenue=float(ga4_metrics["rows"][0].get("totalRevenue", 0.0))
                if ga4_metrics.get("rows")
                else 0.0,
                attributed_revenue_google_ads=google_ads_attributed,
                attributed_revenue_organic=sum(
                    r.organic_attributed_revenue for r in attribution_results
                ),
                attributed_revenue_direct=sum(
                    r.direct_attributed_revenue for r in attribution_results
                ),
                attributed_revenue_other=total_attributed_revenue
                - google_ads_attributed,
                gclid_match_rate=gclid_match_rate,
                cross_platform_roas=cross_platform_roas,
                multi_touch_journeys_count=multi_touch_journeys,
                single_touch_journeys_count=single_touch_journeys,
            )

        except Exception as e:
            logger.error(f"Failed to generate cross-platform metrics: {e}")
            # Return minimal metrics
            return CrossPlatformMetrics(customer_id=customer_id, date=start_date)

    def _generate_recommendations(
        self,
        attribution_results: List,
        journey_insights: Dict[str, Any],
        ml_insights: List,
        quality_metrics: Dict[str, Any],
    ) -> List[Dict[str, str]]:
        """Generate actionable recommendations from attribution analysis."""
        recommendations = []

        # Data quality recommendations
        gclid_match_rate = quality_metrics.get("gclid_match_rate", 0.0)
        if gclid_match_rate < AttributionAnalyzerConfig.MIN_GCLID_MATCH_RATE:
            recommendations.append(
                {
                    "type": "data_quality",
                    "priority": "high",
                    "title": "Improve GCLID Tracking",
                    "description": f"GCLID match rate of {gclid_match_rate:.1%} is below recommended 70%",
                    "action": "Review Google Ads auto-tagging and GA4 configuration",
                }
            )

        # Journey optimization recommendations
        multi_touch_rate = quality_metrics.get("multi_touch_rate", 0.0)
        if multi_touch_rate > AttributionAnalyzerConfig.MIN_MULTI_TOUCH_RATE:
            recommendations.append(
                {
                    "type": "attribution_model",
                    "priority": "medium",
                    "title": "Consider Multi-Touch Attribution",
                    "description": f"{multi_touch_rate:.1%} of journeys have multiple touchpoints",
                    "action": "Switch from last-touch to time-decay or position-based attribution",
                }
            )

        # Cross-platform optimization
        if attribution_results:
            attribution_summary = self.attribution_engine.get_attribution_summary(
                attribution_results
            )
            top_channels = attribution_summary.get("top_channels_by_revenue", [])

            if len(top_channels) >= 2:
                second_channel_revenue = top_channels[1][1]["attributed_revenue"]
                total_revenue = attribution_summary["period_summary"][
                    "total_attributed_revenue"
                ]

                if (
                    second_channel_revenue / total_revenue
                    > AttributionAnalyzerConfig.SECOND_CHANNEL_SIGNIFICANCE_THRESHOLD
                ):  # Second channel has significant share
                    recommendations.append(
                        {
                            "type": "channel_optimization",
                            "priority": "medium",
                            "title": "Optimize Cross-Channel Strategy",
                            "description": "Multiple channels driving significant revenue - consider unified strategy",
                            "action": "Implement cross-channel campaign optimization and shared audiences",
                        }
                    )

        # ML-based recommendations
        for ml_insight in ml_insights:
            if hasattr(ml_insight, "priority") and ml_insight.priority in [
                "high",
                "critical",
            ]:
                recommendations.append(
                    {
                        "type": "ml_insight",
                        "priority": ml_insight.priority,
                        "title": ml_insight.title,
                        "description": ml_insight.description,
                        "action": ml_insight.recommended_actions[0]
                        if ml_insight.recommended_actions
                        else "Review ML insight details",
                    }
                )

        # Journey length recommendations
        avg_journey_length = journey_insights.get("journey_length_distribution", {})
        same_day_rate = (
            avg_journey_length.get("same_day", 0) / len(attribution_results)
            if attribution_results
            else 0
        )

        if same_day_rate > AttributionAnalyzerConfig.SAME_DAY_JOURNEY_HIGH_THRESHOLD:
            recommendations.append(
                {
                    "type": "journey_optimization",
                    "priority": "low",
                    "title": "Quick Decision Journeys Detected",
                    "description": f"{same_day_rate:.1%} of journeys convert same-day",
                    "action": "Focus on immediate conversion optimization and urgency messaging",
                }
            )
        elif same_day_rate < AttributionAnalyzerConfig.SAME_DAY_JOURNEY_LOW_THRESHOLD:
            recommendations.append(
                {
                    "type": "journey_optimization",
                    "priority": "medium",
                    "title": "Long Consideration Journeys Detected",
                    "description": f"Only {same_day_rate:.1%} of journeys convert same-day",
                    "action": "Implement retargeting campaigns and nurturing sequences for extended journeys",
                }
            )

        return recommendations

    def _create_empty_result(self, customer_id: str, reason: str) -> AnalysisResult:
        """Create empty analysis result."""
        return AnalysisResult(
            analyzer_name=self.get_name(),
            customer_id=customer_id,
            analysis_date=datetime.utcnow(),
            data={"message": reason},
            success=False,
            errors=[reason],
            metadata={"reason": reason},
        )

    async def compare_attribution_models(
        self,
        customer_id: str,
        start_date: datetime,
        end_date: datetime,
        model_types: List[str] = None,
    ) -> Dict[str, Any]:
        """Compare multiple attribution models for the same data.

        Args:
            customer_id: Customer identifier
            start_date: Analysis start date
            end_date: Analysis end date
            model_types: Attribution models to compare

        Returns:
            Attribution model comparison results
        """
        if not model_types:
            model_types = [
                "first_touch",
                "last_touch",
                "linear",
                "time_decay",
                "position_based",
            ]

        logger.info(f"Comparing {len(model_types)} attribution models")

        try:
            # Build journeys once
            (
                journeys,
                journey_touches,
            ) = await self.journey_builder.build_customer_journeys(
                customer_id, start_date, end_date, include_non_converting=False
            )

            if not journeys:
                return {"error": "No customer journeys found for comparison"}

            # Compare models
            model_results = {}

            # Process models in parallel for better performance
            model_tasks = []
            model_names = []

            for model_type in model_types:
                attribution_model = self._get_attribution_model(model_type)
                model_names.append(model_type)

                # Create tasks for all journeys for this model
                journey_tasks = []
                for journey in journeys:
                    touches = journey_touches.get(journey.journey_id, [])
                    if touches:
                        task = self.attribution_engine.calculate_attribution(
                            journey, touches, attribution_model
                        )
                        journey_tasks.append(task)

                model_tasks.append(journey_tasks)

            # Execute all model calculations in parallel
            all_model_results = []
            for model_journey_tasks in model_tasks:
                if model_journey_tasks:
                    # Process each model's journeys in batches
                    model_results_list = []
                    batch_size = AttributionAnalyzerConfig.BATCH_SIZE

                    for i in range(0, len(model_journey_tasks), batch_size):
                        batch = model_journey_tasks[i : i + batch_size]
                        batch_results = await asyncio.gather(
                            *batch, return_exceptions=True
                        )

                        # Filter successful results
                        for result in batch_results:
                            if not isinstance(result, Exception):
                                model_results_list.append(result)

                    all_model_results.append(model_results_list)
                else:
                    all_model_results.append([])

            # Build model_results dictionary
            model_results = {}
            for i, model_type in enumerate(model_names):
                model_attribution_results = all_model_results[i]
                model_summary = self.attribution_engine.get_attribution_summary(
                    model_attribution_results
                )
                model_results[model_type] = model_summary

            # Generate comparison insights
            comparison = self._generate_model_comparison_insights(model_results)

            return {
                "customer_id": customer_id,
                "analysis_period": f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
                "models_compared": model_types,
                "journeys_analyzed": len(journeys),
                "model_results": model_results,
                "comparison_insights": comparison,
                "recommended_model": comparison.get("recommended_model"),
                "analysis_timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Attribution model comparison failed: {e}")
            return {"error": str(e)}

    def _generate_model_comparison_insights(
        self, model_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate insights from attribution model comparison."""
        insights = {}

        # Extract total attributed revenue for each model
        model_revenues = {}
        for model_name, results in model_results.items():
            period_summary = results.get("period_summary", {})
            model_revenues[model_name] = period_summary.get(
                "total_attributed_revenue", 0.0
            )

        # Find model with highest attributed revenue
        if model_revenues:
            best_model = max(model_revenues, key=model_revenues.get)
            worst_model = min(model_revenues, key=model_revenues.get)

            insights["recommended_model"] = best_model
            insights["revenue_spread"] = {
                "highest": {"model": best_model, "revenue": model_revenues[best_model]},
                "lowest": {
                    "model": worst_model,
                    "revenue": model_revenues[worst_model],
                },
                "difference": model_revenues[best_model] - model_revenues[worst_model],
            }

        # Analyze channel attribution differences
        channel_variations = {}
        for model_name, results in model_results.items():
            channel_performance = results.get("channel_performance", {})
            for channel, metrics in channel_performance.items():
                if channel not in channel_variations:
                    channel_variations[channel] = {}
                channel_variations[channel][model_name] = metrics.get(
                    "attributed_revenue", 0.0
                )

        # Find channels with highest attribution variance
        high_variance_channels = []
        for channel, model_revenues in channel_variations.items():
            if len(model_revenues) > 1:
                revenues = list(model_revenues.values())
                variance = np.var(revenues) if revenues else 0.0

                if variance > AttributionAnalyzerConfig.HIGH_VARIANCE_THRESHOLD:
                    high_variance_channels.append(
                        {
                            "channel": channel,
                            "variance": variance,
                            "model_attribution": model_revenues,
                        }
                    )

        insights["high_variance_channels"] = sorted(
            high_variance_channels, key=lambda x: x["variance"], reverse=True
        )[:5]

        return insights

    async def generate_attribution_report(
        self,
        customer_id: str,
        start_date: datetime,
        end_date: datetime,
        report_type: str = "comprehensive",
    ) -> Dict[str, Any]:
        """Generate comprehensive attribution analysis report.

        Args:
            customer_id: Customer identifier
            start_date: Report start date
            end_date: Report end date
            report_type: Type of report: summary, comprehensive, executive

        Returns:
            Attribution analysis report
        """
        logger.info(f"Generating {report_type} attribution report for {customer_id}")

        try:
            # Run full attribution analysis
            analysis_result = await self.analyze(
                customer_id, start_date, end_date, include_ml_predictions=True
            )

            if not analysis_result.success:
                return {
                    "error": "Attribution analysis failed",
                    "details": analysis_result.errors,
                }

            analysis_data = analysis_result.data

            # Generate report based on type
            if report_type == "executive":
                return self._generate_executive_report(analysis_data)
            elif report_type == "comprehensive":
                return self._generate_comprehensive_report(analysis_data)
            else:  # summary
                return self._generate_summary_report(analysis_data)

        except Exception as e:
            logger.error(f"Attribution report generation failed: {e}")
            return {"error": str(e)}

    def _generate_executive_report(
        self, analysis_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate executive summary report."""
        attribution_summary = analysis_data.get("attribution_summary", {})
        period_summary = attribution_summary.get("period_summary", {})
        cross_platform_metrics = analysis_data.get("cross_platform_metrics", {})

        return {
            "report_type": "executive_summary",
            "customer_id": analysis_data["customer_id"],
            "period": f"{analysis_data['start_date']} to {analysis_data['end_date']}",
            # Key metrics
            "key_metrics": {
                "total_attributed_revenue": period_summary.get(
                    "total_attributed_revenue", 0.0
                ),
                "conversion_count": period_summary.get("total_conversions", 0),
                "cross_platform_roas": getattr(
                    cross_platform_metrics, "cross_platform_roas", 0.0
                ),
                "multi_touch_journey_rate": analysis_data.get(
                    "cross_device_journeys", 0
                )
                / max(analysis_data.get("total_journeys", 1), 1),
            },
            # Top insights
            "top_insights": analysis_data.get("recommendations", [])[:3],
            # Performance by channel
            "channel_performance": attribution_summary.get(
                "top_channels_by_revenue", []
            )[:5],
            # Data quality
            "data_quality_score": analysis_data.get("quality_metrics", {}).get(
                "data_quality_score", 0.0
            ),
            "report_generated": datetime.utcnow().isoformat(),
        }

    def _generate_comprehensive_report(
        self, analysis_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate comprehensive detailed report."""
        return {
            "report_type": "comprehensive",
            "analysis_data": analysis_data,
            "report_generated": datetime.utcnow().isoformat(),
        }

    def _generate_summary_report(self, analysis_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate summary report."""
        attribution_summary = analysis_data.get("attribution_summary", {})

        return {
            "report_type": "summary",
            "customer_id": analysis_data["customer_id"],
            "period": f"{analysis_data['start_date']} to {analysis_data['end_date']}",
            "attribution_summary": attribution_summary,
            "top_recommendations": analysis_data.get("recommendations", [])[:5],
            "quality_score": analysis_data.get("quality_metrics", {}).get(
                "data_quality_score", 0.0
            ),
            "report_generated": datetime.utcnow().isoformat(),
        }
