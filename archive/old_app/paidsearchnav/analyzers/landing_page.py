"""Landing Page Performance and Conversion Analyzer for campaign optimization."""

import logging
from datetime import datetime
from typing import Any, List, Optional

import pandas as pd

from paidsearchnav.core.interfaces import Analyzer
from paidsearchnav.core.models.landing_page import (
    ABTestOpportunity,
    ConversionFunnel,
    LandingPageAnalysisResult,
    LandingPageAnalysisSummary,
    LandingPageMetrics,
    OptimizationType,
    PageOptimization,
    PagePerformanceStatus,
    TrafficSource,
    TrafficSourcePerformance,
)
from paidsearchnav.platforms.ga4.bigquery_client import GA4BigQueryClient

logger = logging.getLogger(__name__)


class LandingPageAnalyzer(Analyzer):
    """Analyzes landing page performance to identify conversion optimization opportunities."""

    # Business logic thresholds
    MIN_CLICKS_FOR_ANALYSIS = 50
    MIN_IMPRESSIONS_FOR_ANALYSIS = 100
    HIGH_CONVERSION_THRESHOLD = 5.0  # %
    LOW_CONVERSION_THRESHOLD = 1.0  # %
    HIGH_CTR_THRESHOLD = 10.0  # %
    LOW_CTR_THRESHOLD = 2.0  # %
    HIGH_CPC_THRESHOLD = 5.0  # USD
    LOW_CPC_THRESHOLD = 1.0  # USD

    # Performance variance thresholds
    SIGNIFICANT_CONVERSION_VARIANCE = 25.0  # %
    SIGNIFICANT_CTR_VARIANCE = 20.0  # %
    SIGNIFICANT_COST_VARIANCE = 30.0  # %

    # KPI thresholds
    MIN_PAGE_COVERAGE = 90.0  # %
    MIN_TRAFFIC_THRESHOLD = 50  # visits
    MIN_CONVERSION_ATTRIBUTION = 85.0  # %
    MIN_DATA_COMPLETENESS = 90.0  # %
    MIN_ACTIONABLE_INSIGHTS = 4

    # Funnel estimation rates (configurable constants as per Claude's recommendation)
    ESTIMATED_ENGAGEMENT_RATE = 0.7  # 70% of clicks result in engaged sessions
    ESTIMATED_FORM_START_RATE = 0.3  # 30% of clicks start forms

    def __init__(
        self,
        min_clicks: int = 50,
        conversion_value: float = 50.0,
        mobile_speed_threshold: int = 50,
        ga4_client: Optional[GA4BigQueryClient] = None,
    ):
        """Initialize the landing page analyzer.

        Args:
            min_clicks: Minimum clicks required for analysis
            conversion_value: Average value per conversion
            mobile_speed_threshold: Minimum mobile speed score threshold
            ga4_client: Optional GA4 BigQuery client for enhanced analytics
        """
        self.min_clicks = min_clicks
        self.conversion_value = conversion_value
        self.mobile_speed_threshold = mobile_speed_threshold
        self.ga4_client = ga4_client

    def get_name(self) -> str:
        """Get analyzer name."""
        return "Landing Page Performance and Conversion Analyzer"

    def get_description(self) -> str:
        """Get analyzer description."""
        return (
            "Evaluates landing page effectiveness, user experience optimization opportunities, "
            "and provides conversion optimization recommendations for fitness industry campaigns."
        )

    async def analyze(
        self,
        customer_id: str,
        start_date: datetime,
        end_date: datetime,
        **kwargs: Any,
    ) -> LandingPageAnalysisResult:
        """Analyze landing page performance for a customer.

        Args:
            customer_id: Customer ID
            start_date: Start date for analysis
            end_date: End date for analysis
            **kwargs: Additional parameters (landing_page_data)

        Returns:
            Landing page analysis result
        """
        # Validate customer ID (as per Claude's recommendation)
        if not customer_id or not customer_id.strip():
            raise ValueError("Customer ID is required and cannot be empty")

        logger.info(
            f"Starting landing page analysis for customer {customer_id}",
            extra={
                "customer_id": customer_id,
                "date_range": f"{start_date} to {end_date}",
                "analyzer": self.get_name(),
            },
        )

        # Validate date range
        if start_date > end_date:
            raise ValueError(
                f"Start date ({start_date}) must be before end date ({end_date})"
            )

        try:
            # Extract landing page data from kwargs
            landing_page_data = kwargs.get("landing_page_data")

            if landing_page_data is None or (
                isinstance(landing_page_data, pd.DataFrame) and landing_page_data.empty
            ):
                logger.warning("No landing page data provided for analysis")
                return self._create_empty_result(customer_id, start_date, end_date)

            # Validate required columns
            self._validate_landing_page_data(landing_page_data)

            # Convert raw data to structured models
            landing_pages = self._convert_to_landing_pages(landing_page_data)

            if not landing_pages:
                logger.warning("No valid landing pages found in data")
                return self._create_empty_result(customer_id, start_date, end_date)

            # Enhance with GA4 data if available
            if self.ga4_client:
                landing_pages = await self._enhance_with_ga4_data(
                    landing_pages, landing_page_data, start_date, end_date
                )

            # Analyze conversion funnels
            conversion_funnels = self._analyze_conversion_funnels(landing_pages)

            # Generate optimization recommendations
            optimizations = self._generate_optimizations(landing_pages)

            # Analyze traffic source performance
            traffic_performance = self._analyze_traffic_sources(
                landing_pages, landing_page_data
            )

            # Identify A/B testing opportunities
            ab_test_opportunities = self._identify_ab_test_opportunities(landing_pages)

            # Create summary
            summary = self._create_summary(
                landing_pages, optimizations, ab_test_opportunities
            )

            return LandingPageAnalysisResult(
                customer_id=customer_id,
                analysis_date=datetime.now(),
                start_date=start_date,
                end_date=end_date,
                landing_pages=landing_pages,
                conversion_funnels=conversion_funnels,
                optimizations=optimizations,
                traffic_source_performance=traffic_performance,
                ab_test_opportunities=ab_test_opportunities,
                summary=summary,
                metadata={
                    "analyzer_version": "1.0.0",
                    "thresholds": {
                        "min_clicks": self.min_clicks,
                        "conversion_value": self.conversion_value,
                        "mobile_speed_threshold": self.mobile_speed_threshold,
                    },
                },
            )

        except Exception as e:
            logger.error(f"Error analyzing landing pages: {str(e)}")
            raise

    def _validate_landing_page_data(self, data: pd.DataFrame) -> None:
        """Validate required columns exist in landing page data.

        Args:
            data: Raw landing page DataFrame

        Raises:
            ValueError: If required columns are missing
        """
        required_columns = ["Landing page", "Clicks", "Impr.", "Cost"]
        missing = set(required_columns) - set(data.columns)
        if missing:
            raise ValueError(
                f"Missing required columns in landing page data: {missing}"
            )

    def _convert_to_landing_pages(
        self, landing_page_data: pd.DataFrame
    ) -> List[LandingPageMetrics]:
        """Convert raw landing page data to structured models.

        Args:
            landing_page_data: Raw landing page DataFrame

        Returns:
            List of LandingPageMetrics objects
        """
        landing_pages = []

        # Clean column names for easier access
        data_clean = landing_page_data.copy()
        data_clean.columns = [
            col.replace(" ", "_").replace(".", "").replace("/", "_")
            for col in data_clean.columns
        ]

        # Check for conversion data and warn if missing (as per Claude's recommendation)
        if "Conversions" not in data_clean.columns:
            logger.warning(
                "No conversion data available in landing page report. "
                "Conversion metrics will be set to zero."
            )

        for row in data_clean.itertuples(index=False):
            try:
                # Skip total rows
                landing_page = getattr(row, "Landing_page", "")
                if not landing_page or "Total:" in str(landing_page):
                    continue

                # Parse metrics
                clicks = self._safe_int(getattr(row, "Clicks", 0))
                impressions = self._safe_int(getattr(row, "Impr", 0))
                cost = self._safe_float(getattr(row, "Cost", 0))
                ctr = self._safe_float(getattr(row, "CTR", "0%"))
                avg_cpc = self._safe_float(getattr(row, "Avg_CPC", 0))

                # Calculate conversions if available
                conversions = self._safe_float(getattr(row, "Conversions", 0))
                conversion_rate = (conversions / clicks * 100) if clicks > 0 else 0.0
                cost_per_conversion = (cost / conversions) if conversions > 0 else 0.0

                # Parse mobile metrics
                mobile_speed = self._safe_int(getattr(row, "Mobile_speed_score", 0))
                mobile_friendly_ctr = self._safe_float(
                    getattr(row, "Mobile-friendly_click_rate", "0%")
                )
                valid_amp_ctr = self._safe_float(
                    getattr(row, "Valid_AMP_click_rate", "0%")
                )

                # Create landing page metrics
                page_metrics = LandingPageMetrics(
                    url=landing_page,
                    clicks=clicks,
                    impressions=impressions,
                    ctr=ctr,
                    cost=cost,
                    avg_cpc=avg_cpc,
                    conversions=conversions,
                    conversion_rate=conversion_rate,
                    cost_per_conversion=cost_per_conversion,
                    mobile_speed_score=mobile_speed if mobile_speed > 0 else None,
                    mobile_friendly_click_rate=mobile_friendly_ctr
                    if mobile_friendly_ctr > 0
                    else None,
                    valid_amp_click_rate=valid_amp_ctr if valid_amp_ctr > 0 else None,
                )

                landing_pages.append(page_metrics)

            except Exception as e:
                logger.warning(f"Error parsing landing page row: {str(e)}")
                continue

        return landing_pages

    def _analyze_conversion_funnels(
        self, landing_pages: List[LandingPageMetrics]
    ) -> List[ConversionFunnel]:
        """Analyze conversion funnels for landing pages.

        Args:
            landing_pages: List of landing page metrics

        Returns:
            List of ConversionFunnel objects
        """
        funnels = []

        for page in landing_pages:
            if page.clicks < self.min_clicks:
                continue

            funnel = ConversionFunnel(
                page_url=page.url,
                impressions=page.impressions,
                clicks=page.clicks,
                page_views=page.clicks,  # Assuming 1:1 for now
                engaged_sessions=int(page.clicks * self.ESTIMATED_ENGAGEMENT_RATE),
                form_starts=int(page.clicks * self.ESTIMATED_FORM_START_RATE),
                form_completions=int(page.conversions),
                conversions=page.conversions,
            )

            funnels.append(funnel)

        return funnels

    def _generate_optimizations(
        self, landing_pages: List[LandingPageMetrics]
    ) -> List[PageOptimization]:
        """Generate optimization recommendations for landing pages.

        Args:
            landing_pages: List of landing page metrics

        Returns:
            List of PageOptimization objects
        """
        optimizations = []

        # Calculate average metrics for comparison
        pages_with_data = [lp for lp in landing_pages if lp.clicks >= self.min_clicks]
        if not pages_with_data:
            return optimizations

        avg_conversion_rate = sum(lp.conversion_rate for lp in pages_with_data) / len(
            pages_with_data
        )
        avg_ctr = sum(lp.ctr for lp in pages_with_data) / len(pages_with_data)
        avg_cpc = sum(lp.avg_cpc for lp in pages_with_data) / len(pages_with_data)

        for page in pages_with_data:
            # Check for low conversion rate
            if page.conversion_rate < self.LOW_CONVERSION_THRESHOLD:
                optimization = PageOptimization(
                    page_url=page.url,
                    optimization_type=OptimizationType.CONVERSION_RATE,
                    priority="High" if page.cost > 500 else "Medium",
                    current_performance=f"{page.conversion_rate:.2f}% conversion rate",
                    recommended_action="Review page content, form placement, and call-to-action clarity",
                    expected_impact="Increase conversions by 20-30%",
                    reasoning=f"Conversion rate ({page.conversion_rate:.2f}%) is significantly below average ({avg_conversion_rate:.2f}%)",
                    estimated_improvement=30.0,
                    estimated_revenue_impact=page.clicks * 0.03 * self.conversion_value,
                    confidence_score=0.75,
                    implementation_complexity="Medium",
                )
                optimizations.append(optimization)

            # Check for low CTR
            if page.ctr < self.LOW_CTR_THRESHOLD and page.impressions > 1000:
                optimization = PageOptimization(
                    page_url=page.url,
                    optimization_type=OptimizationType.CONTENT_RELEVANCE,
                    priority="Medium",
                    current_performance=f"{page.ctr:.2f}% CTR",
                    recommended_action="Improve ad-to-page relevance and meta descriptions",
                    expected_impact="Increase CTR by 15-25%",
                    reasoning=f"CTR ({page.ctr:.2f}%) is below optimal threshold",
                    estimated_improvement=20.0,
                    confidence_score=0.70,
                    implementation_complexity="Low",
                )
                optimizations.append(optimization)

            # Check for mobile optimization
            if (
                page.mobile_speed_score
                and page.mobile_speed_score < self.mobile_speed_threshold
            ):
                optimization = PageOptimization(
                    page_url=page.url,
                    optimization_type=OptimizationType.PAGE_SPEED,
                    priority="High" if page.mobile_speed_score < 30 else "Medium",
                    current_performance=f"Mobile speed score: {page.mobile_speed_score}",
                    recommended_action="Optimize images, reduce JavaScript, enable caching",
                    expected_impact="Reduce bounce rate by 10-20%",
                    reasoning=f"Mobile speed score ({page.mobile_speed_score}) is below threshold ({self.mobile_speed_threshold})",
                    estimated_improvement=15.0,
                    confidence_score=0.80,
                    implementation_complexity="Medium",
                )
                optimizations.append(optimization)

            # Check for high cost per conversion
            if page.cost_per_conversion > avg_cpc * 20 and page.conversions > 0:
                optimization = PageOptimization(
                    page_url=page.url,
                    optimization_type=OptimizationType.TRAFFIC_ALLOCATION,
                    priority="High",
                    current_performance=f"${page.cost_per_conversion:.2f} per conversion",
                    recommended_action="Reduce traffic or improve page conversion rate",
                    expected_impact="Reduce cost per conversion by 30-40%",
                    reasoning="Cost per conversion is significantly above acceptable threshold",
                    estimated_improvement=35.0,
                    estimated_revenue_impact=page.cost * 0.35,
                    confidence_score=0.85,
                    implementation_complexity="Low",
                )
                optimizations.append(optimization)

        # Sort by priority and estimated impact
        optimizations.sort(
            key=lambda x: (
                {"High": 3, "Medium": 2, "Low": 1}.get(x.priority, 0),
                x.estimated_revenue_impact or 0,
            ),
            reverse=True,
        )

        return optimizations[:10]  # Return top 10 optimizations

    def _analyze_traffic_sources(
        self,
        landing_pages: List[LandingPageMetrics],
        raw_data: pd.DataFrame,
    ) -> List[TrafficSourcePerformance]:
        """Analyze performance by traffic source.

        Args:
            landing_pages: List of landing page metrics
            raw_data: Raw landing page data

        Returns:
            List of TrafficSourcePerformance objects
        """
        traffic_sources = {}

        # Check for traffic source totals in raw data
        for _, row in raw_data.iterrows():
            if pd.isna(row.get("Landing page", "")):
                continue

            landing_page = str(row.get("Landing page", ""))
            if "Total:" in landing_page:
                source_name = landing_page.replace("Total:", "").strip()
                source_type = self._map_traffic_source(source_name)

                if source_type != TrafficSource.UNKNOWN:
                    if source_type not in traffic_sources:
                        traffic_sources[source_type] = TrafficSourcePerformance(
                            source=source_type
                        )

                    perf = traffic_sources[source_type]
                    perf.total_clicks = self._safe_int(row.get("Clicks", 0))
                    perf.total_impressions = self._safe_int(row.get("Impr.", 0))
                    perf.total_cost = self._safe_float(row.get("Cost", 0))
                    perf.avg_ctr = self._safe_float(row.get("CTR", "0%"))
                    perf.avg_cpc = self._safe_float(row.get("Avg. CPC", 0))

        # If no traffic source totals found, aggregate from landing pages
        if not traffic_sources:
            # Create a default search source with all data
            search_source = TrafficSourcePerformance(source=TrafficSource.SEARCH)

            for page in landing_pages:
                search_source.pages.append(page.url)
                search_source.total_clicks += page.clicks
                search_source.total_impressions += page.impressions
                search_source.total_cost += page.cost
                search_source.total_conversions += page.conversions

            if search_source.total_impressions > 0:
                search_source.avg_ctr = (
                    search_source.total_clicks / search_source.total_impressions * 100
                )
            if search_source.total_clicks > 0:
                search_source.avg_cpc = (
                    search_source.total_cost / search_source.total_clicks
                )
                search_source.avg_conversion_rate = (
                    search_source.total_conversions / search_source.total_clicks * 100
                )

            # Find top and worst performers
            if landing_pages:
                sorted_pages = sorted(
                    landing_pages, key=lambda x: x.efficiency_score, reverse=True
                )
                search_source.top_performing_page = (
                    sorted_pages[0].url if sorted_pages else None
                )
                search_source.worst_performing_page = (
                    sorted_pages[-1].url if sorted_pages else None
                )

            traffic_sources[TrafficSource.SEARCH] = search_source

        return list(traffic_sources.values())

    def _identify_ab_test_opportunities(
        self, landing_pages: List[LandingPageMetrics]
    ) -> List[ABTestOpportunity]:
        """Identify A/B testing opportunities.

        Args:
            landing_pages: List of landing page metrics

        Returns:
            List of ABTestOpportunity objects
        """
        opportunities = []

        # Sort pages by traffic volume
        high_traffic_pages = sorted(
            [lp for lp in landing_pages if lp.clicks >= self.min_clicks],
            key=lambda x: x.clicks,
            reverse=True,
        )[:5]  # Top 5 high-traffic pages

        for page in high_traffic_pages:
            # Test opportunity for low-converting high-traffic pages
            if page.conversion_rate < 2.0 and page.clicks > 500:
                opportunity = ABTestOpportunity(
                    control_page=page.url,
                    variant_suggestions=[
                        "Simplified form with fewer fields",
                        "Prominent testimonials above fold",
                        "Urgency messaging with limited-time offer",
                        "Video content showing gym facilities",
                    ],
                    test_hypothesis="Simplified forms and social proof will increase conversions",
                    success_metrics=[
                        "Conversion Rate",
                        "Form Completion Rate",
                        "Cost per Conversion",
                    ],
                    expected_duration_days=14,
                    minimum_sample_size=1000,
                    potential_uplift=25.0,
                    priority="High",
                    reasoning=f"High traffic ({page.clicks} clicks) but low conversion rate ({page.conversion_rate:.2f}%)",
                )
                opportunities.append(opportunity)

            # Test opportunity for pages with poor mobile performance
            elif page.mobile_speed_score and page.mobile_speed_score < 50:
                opportunity = ABTestOpportunity(
                    control_page=page.url,
                    variant_suggestions=[
                        "AMP version of the page",
                        "Lazy-loaded images and content",
                        "Simplified mobile-first design",
                    ],
                    test_hypothesis="Improved mobile performance will reduce bounce rate and increase conversions",
                    success_metrics=[
                        "Mobile Conversion Rate",
                        "Page Load Time",
                        "Bounce Rate",
                    ],
                    expected_duration_days=21,
                    minimum_sample_size=500,
                    potential_uplift=15.0,
                    priority="Medium",
                    reasoning=f"Poor mobile speed score ({page.mobile_speed_score}) impacting user experience",
                )
                opportunities.append(opportunity)

        return opportunities[:5]  # Return top 5 opportunities

    def _create_summary(
        self,
        landing_pages: List[LandingPageMetrics],
        optimizations: List[PageOptimization],
        ab_tests: List[ABTestOpportunity],
    ) -> LandingPageAnalysisSummary:
        """Create analysis summary.

        Args:
            landing_pages: List of landing page metrics
            optimizations: List of optimizations
            ab_tests: List of A/B test opportunities

        Returns:
            LandingPageAnalysisSummary object
        """
        pages_with_data = [lp for lp in landing_pages if lp.clicks >= self.min_clicks]

        total_clicks = sum(lp.clicks for lp in landing_pages)
        total_impressions = sum(lp.impressions for lp in landing_pages)
        total_cost = sum(lp.cost for lp in landing_pages)
        total_conversions = sum(lp.conversions for lp in landing_pages)

        avg_conversion_rate = (
            (total_conversions / total_clicks * 100) if total_clicks > 0 else 0.0
        )
        avg_ctr = (
            (total_clicks / total_impressions * 100) if total_impressions > 0 else 0.0
        )
        avg_cpc = (total_cost / total_clicks) if total_clicks > 0 else 0.0

        # Identify top and bottom performers
        sorted_pages = sorted(
            landing_pages, key=lambda x: x.efficiency_score, reverse=True
        )
        top_performers = [p.url for p in sorted_pages[:5] if p.has_sufficient_data]
        bottom_performers = [p.url for p in sorted_pages[-5:] if p.has_sufficient_data]

        # Calculate potential improvements
        potential_cost_savings = sum(
            opt.estimated_revenue_impact
            for opt in optimizations
            if opt.estimated_revenue_impact
            and opt.optimization_type == OptimizationType.TRAFFIC_ALLOCATION
        )
        potential_conversion_increase = sum(
            opt.estimated_improvement or 0
            for opt in optimizations
            if opt.optimization_type == OptimizationType.CONVERSION_RATE
        )

        # Generate key insights
        key_insights = []

        if avg_conversion_rate < 1.0:
            key_insights.append(
                f"Overall conversion rate ({avg_conversion_rate:.2f}%) is below industry benchmark"
            )

        if len(pages_with_data) < len(landing_pages) * 0.5:
            key_insights.append(
                f"Only {len(pages_with_data)} of {len(landing_pages)} pages have sufficient data for analysis"
            )

        if potential_cost_savings > 1000:
            key_insights.append(
                f"Potential cost savings of ${potential_cost_savings:.2f} through optimization"
            )

        if ab_tests:
            key_insights.append(
                f"{len(ab_tests)} high-value A/B testing opportunities identified"
            )

        mobile_issues = [
            lp
            for lp in landing_pages
            if lp.mobile_speed_score and lp.mobile_speed_score < 50
        ]
        if mobile_issues:
            key_insights.append(
                f"{len(mobile_issues)} pages have poor mobile performance scores"
            )

        # Calculate data quality score
        data_quality_score = (
            (len(pages_with_data) / len(landing_pages) * 100) if landing_pages else 0.0
        )

        return LandingPageAnalysisSummary(
            total_pages_analyzed=len(landing_pages),
            pages_with_sufficient_data=len(pages_with_data),
            total_clicks=total_clicks,
            total_impressions=total_impressions,
            total_cost=total_cost,
            total_conversions=total_conversions,
            avg_conversion_rate=avg_conversion_rate,
            avg_ctr=avg_ctr,
            avg_cpc=avg_cpc,
            top_performing_pages=top_performers,
            bottom_performing_pages=bottom_performers,
            optimization_opportunities=len(optimizations),
            potential_cost_savings=potential_cost_savings,
            potential_conversion_increase=potential_conversion_increase,
            key_insights=key_insights[:5],  # Top 5 insights
            data_quality_score=data_quality_score,
            analysis_confidence=min(data_quality_score, 90.0),
        )

    def _map_traffic_source(self, source_name: str) -> TrafficSource:
        """Map source name to TrafficSource enum.

        Args:
            source_name: Source name string

        Returns:
            TrafficSource enum value
        """
        source_upper = source_name.upper()

        if "SEARCH" in source_upper:
            return TrafficSource.SEARCH
        elif "DISPLAY" in source_upper:
            return TrafficSource.DISPLAY
        elif "VIDEO" in source_upper:
            return TrafficSource.VIDEO
        elif "SHOPPING" in source_upper:
            return TrafficSource.SHOPPING
        elif "DEMAND" in source_upper or "GEN" in source_upper:
            return TrafficSource.DEMAND_GEN
        elif "SMART" in source_upper:
            return TrafficSource.SMART
        else:
            return TrafficSource.UNKNOWN

    def _determine_performance_status(
        self, metrics: LandingPageMetrics, avg_conversion_rate: float
    ) -> PagePerformanceStatus:
        """Determine page performance status.

        Args:
            metrics: Page metrics
            avg_conversion_rate: Average conversion rate

        Returns:
            PagePerformanceStatus
        """
        if metrics.clicks < self.min_clicks:
            return PagePerformanceStatus.INSUFFICIENT_DATA

        efficiency = metrics.efficiency_score

        if efficiency >= 80:
            return PagePerformanceStatus.TOP_PERFORMER
        elif efficiency >= 60:
            return PagePerformanceStatus.ABOVE_AVERAGE
        elif efficiency >= 40:
            return PagePerformanceStatus.AVERAGE
        elif efficiency >= 20:
            return PagePerformanceStatus.BELOW_AVERAGE
        else:
            return PagePerformanceStatus.POOR_PERFORMER

    def _safe_float(self, value: Any) -> float:
        """Safely convert value to float.

        Args:
            value: Value to convert

        Returns:
            Float value or 0.0
        """
        if pd.isna(value):
            return 0.0

        if isinstance(value, str):
            # Remove percentage sign and commas
            value = value.replace("%", "").replace(",", "").replace("$", "").strip()
            if value == "--" or not value:
                return 0.0

        try:
            return float(value)
        except (ValueError, TypeError):
            return 0.0

    def _safe_int(self, value: Any) -> int:
        """Safely convert value to integer.

        Args:
            value: Value to convert

        Returns:
            Integer value or 0
        """
        if pd.isna(value):
            return 0

        if isinstance(value, str):
            # Remove commas
            value = value.replace(",", "").strip()
            if value == "--" or not value:
                return 0

        try:
            return int(float(value))
        except (ValueError, TypeError):
            return 0

    def _create_empty_result(
        self, customer_id: str, start_date: datetime, end_date: datetime
    ) -> LandingPageAnalysisResult:
        """Create empty result when no data is available.

        Args:
            customer_id: Customer ID
            start_date: Start date
            end_date: End date

        Returns:
            Empty LandingPageAnalysisResult
        """
        return LandingPageAnalysisResult(
            customer_id=customer_id,
            analysis_date=datetime.now(),
            start_date=start_date,
            end_date=end_date,
            landing_pages=[],
            conversion_funnels=[],
            optimizations=[],
            traffic_source_performance=[],
            ab_test_opportunities=[],
            summary=LandingPageAnalysisSummary(
                total_pages_analyzed=0,
                pages_with_sufficient_data=0,
                total_clicks=0,
                total_impressions=0,
                total_cost=0.0,
                total_conversions=0.0,
                avg_conversion_rate=0.0,
                avg_ctr=0.0,
                avg_cpc=0.0,
                top_performing_pages=[],
                bottom_performing_pages=[],
                optimization_opportunities=0,
                potential_cost_savings=0.0,
                potential_conversion_increase=0.0,
                key_insights=["No landing page data available for analysis"],
                data_quality_score=0.0,
                analysis_confidence=0.0,
            ),
            metadata={"error": "No landing page data provided"},
        )

    async def _enhance_with_ga4_data(
        self,
        landing_pages: List[LandingPageMetrics],
        raw_data: pd.DataFrame,
        start_date: datetime,
        end_date: datetime,
    ) -> List[LandingPageMetrics]:
        """Enhance landing page metrics with real GA4 session data.

        Args:
            landing_pages: Current landing page metrics
            raw_data: Raw landing page data from Google Ads
            start_date: Analysis start date
            end_date: Analysis end date

        Returns:
            Enhanced landing page metrics with GA4 data
        """
        if not self.ga4_client:
            logger.warning("GA4 client not available, skipping GA4 enhancement")
            return landing_pages

        try:
            # Extract GCLIDs from raw Google Ads data if available
            gclids = []
            if "GCLID" in raw_data.columns:
                gclids = raw_data["GCLID"].dropna().tolist()
            elif hasattr(raw_data, "gclid"):
                gclids = raw_data["gclid"].dropna().tolist()

            if not gclids:
                logger.warning(
                    "No GCLIDs found in landing page data, cannot enhance with GA4"
                )
                return landing_pages

            # Get GA4 session data for matching GCLIDs
            ga4_sessions = self.ga4_client.get_gclid_sessions(
                start_date, end_date, gclids
            )

            if not ga4_sessions:
                logger.warning("No matching GA4 sessions found for provided GCLIDs")
                return landing_pages

            # Create lookup for GA4 data by landing page URL
            ga4_by_landing_page = {}
            for session in ga4_sessions:
                landing_page = session.get("landing_page", "")
                if landing_page:
                    if landing_page not in ga4_by_landing_page:
                        ga4_by_landing_page[landing_page] = []
                    ga4_by_landing_page[landing_page].append(session)

            # Enhance landing page metrics with GA4 data
            enhanced_pages = []
            for page in landing_pages:
                enhanced_page = page

                # Find matching GA4 sessions for this landing page
                matching_sessions = ga4_by_landing_page.get(page.url, [])

                if matching_sessions:
                    # Calculate GA4 metrics
                    total_sessions = len(matching_sessions)
                    engaged_sessions = sum(
                        1 for s in matching_sessions if s.get("session_engaged", False)
                    )
                    total_bounce_events = sum(
                        s.get("bounce_rate", 0) for s in matching_sessions
                    )
                    total_session_duration = sum(
                        s.get("session_duration_seconds", 0) for s in matching_sessions
                    )
                    total_page_views = sum(
                        s.get("page_views", 1) for s in matching_sessions
                    )

                    # Calculate enhanced metrics
                    real_bounce_rate = (
                        (total_bounce_events / total_sessions)
                        if total_sessions > 0
                        else 0.0
                    )
                    avg_session_duration = (
                        (total_session_duration / total_sessions)
                        if total_sessions > 0
                        else 0.0
                    )
                    engagement_rate = (
                        (engaged_sessions / total_sessions * 100)
                        if total_sessions > 0
                        else 0.0
                    )
                    avg_pages_per_session = (
                        (total_page_views / total_sessions)
                        if total_sessions > 0
                        else 1.0
                    )

                    # Update page metrics with real GA4 data
                    enhanced_page = LandingPageMetrics(
                        url=page.url,
                        clicks=page.clicks,
                        impressions=page.impressions,
                        ctr=page.ctr,
                        cost=page.cost,
                        avg_cpc=page.avg_cpc,
                        conversions=page.conversions,
                        conversion_rate=page.conversion_rate,
                        cost_per_conversion=page.cost_per_conversion,
                        mobile_speed_score=page.mobile_speed_score,
                        mobile_friendly_click_rate=page.mobile_friendly_click_rate,
                        valid_amp_click_rate=page.valid_amp_click_rate,
                        # Enhanced GA4 metrics
                        bounce_rate=real_bounce_rate,
                        avg_session_duration=avg_session_duration,
                        pages_per_session=avg_pages_per_session,
                        engagement_rate=engagement_rate,
                        ga4_sessions=total_sessions,
                    )

                    logger.info(
                        f"Enhanced {page.url} with GA4 data: "
                        f"{total_sessions} sessions, {real_bounce_rate:.1f}% bounce rate, "
                        f"{avg_session_duration:.1f}s avg duration"
                    )

                enhanced_pages.append(enhanced_page)

            logger.info(
                f"Enhanced {len(enhanced_pages)} landing pages with GA4 session data"
            )
            return enhanced_pages

        except Exception as e:
            logger.error(f"Failed to enhance landing pages with GA4 data: {e}")
            # Return original data if GA4 enhancement fails
            return landing_pages
