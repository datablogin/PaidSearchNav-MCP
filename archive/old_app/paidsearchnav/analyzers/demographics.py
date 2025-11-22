"""Demographics performance analyzer for age, gender, income, and parental status optimization."""

import logging
from datetime import datetime
from typing import Any, Dict

from paidsearchnav.core.interfaces import Analyzer
from paidsearchnav.core.models.demographics import (
    AgeGroup,
    DemographicInsight,
    DemographicPerformance,
    DemographicsAnalysisResult,
    DemographicsAnalysisSummary,
    DemographicSegment,
    DemographicType,
    GenderType,
    IncomePercentile,
    ParentalStatus,
)

logger = logging.getLogger(__name__)


class DemographicsAnalyzer(Analyzer):
    """Analyzes demographics performance to identify targeting optimization opportunities."""

    # Business logic thresholds
    HIGH_PERFORMER_SCORE = 80.0
    MODERATE_PERFORMER_SCORE = 60.0
    LOW_PERFORMER_SCORE = 40.0

    # Data quality thresholds
    MIN_IMPRESSIONS_THRESHOLD = 50
    MIN_INTERACTIONS_THRESHOLD = 5
    MIN_COVERAGE_PERCENTAGE = 80.0
    MIN_COMPLETENESS_SCORE = 90.0

    # Performance variance thresholds
    SIGNIFICANT_CONVERSION_RATE_VARIANCE = 20.0  # 20% difference
    SIGNIFICANT_CPC_VARIANCE = 15.0  # 15% difference
    MIN_ACTIONABLE_RECOMMENDATIONS = 3
    MIN_ROI_IMPACT_POTENTIAL = 10.0  # 10% budget reallocation potential

    def __init__(
        self,
        min_impressions: int = 50,
        min_interactions: int = 5,
        performance_variance_threshold: float = 0.20,
        cost_variance_threshold: float = 0.15,
    ):
        """Initialize the demographics analyzer.

        Args:
            min_impressions: Minimum impressions required for analysis
            min_interactions: Minimum interactions required for analysis
            performance_variance_threshold: Threshold for significant performance variance
            cost_variance_threshold: Threshold for significant cost variance
        """
        self.min_impressions = min_impressions
        self.min_interactions = min_interactions
        self.performance_variance_threshold = performance_variance_threshold
        self.cost_variance_threshold = cost_variance_threshold

    async def analyze(
        self,
        customer_id: str,
        start_date: datetime,
        end_date: datetime,
        **kwargs: Any,
    ) -> DemographicsAnalysisResult:
        """Analyze demographics performance for a customer.

        Args:
            customer_id: Google Ads customer ID
            start_date: Start date for analysis
            end_date: End date for analysis
            **kwargs: Additional parameters (age_data, gender_data, income_data, parental_data)

        Returns:
            Demographics performance analysis result
        """
        logger.info(f"Starting demographics analysis for customer {customer_id}")

        # Validate date range
        if start_date > end_date:
            raise ValueError(
                f"Start date ({start_date}) must be before end date ({end_date})"
            )

        try:
            # Extract demographic data from kwargs
            demographic_data = self._extract_demographic_data(kwargs)

            if not any(demographic_data.values()):
                logger.warning("No demographic data provided for analysis")
                return self._create_empty_result(customer_id, start_date, end_date)

            # Convert raw data to structured models
            segments = self._convert_to_demographic_segments(
                demographic_data, customer_id, start_date, end_date
            )

            # Filter segments by minimum thresholds
            filtered_segments = self._filter_segments_by_thresholds(segments)

            if not filtered_segments:
                logger.warning("No demographic segments meet minimum thresholds")
                return self._create_empty_result(customer_id, start_date, end_date)

            # Calculate performance metrics for each demographic
            performance_by_demographic = self._calculate_demographic_performance(
                filtered_segments
            )

            # Generate analysis summary
            summary = self._generate_analysis_summary(
                customer_id,
                filtered_segments,
                performance_by_demographic,
                start_date,
                end_date,
            )

            # Generate insights and recommendations
            insights = self._generate_demographic_insights(
                performance_by_demographic, summary
            )

            # Generate bid adjustment recommendations
            bid_adjustments = self._generate_bid_adjustment_recommendations(
                performance_by_demographic
            )

            # Generate targeting exclusion recommendations
            exclusion_recommendations = self._generate_exclusion_recommendations(
                performance_by_demographic
            )

            # Generate budget reallocation recommendations
            budget_recommendations = self._generate_budget_reallocation_recommendations(
                performance_by_demographic
            )

            # Generate optimization recommendations
            optimization_recommendations = self._generate_optimization_recommendations(
                insights, summary
            )

            # Create dashboard metrics
            dashboard_metrics = self._create_dashboard_metrics(
                summary, performance_by_demographic
            )

            # Calculate KPIs
            data_quality_kpis = self._calculate_data_quality_kpis(
                summary, filtered_segments
            )
            analysis_value_kpis = self._calculate_analysis_value_kpis(
                insights, performance_by_demographic
            )
            business_impact_kpis = self._calculate_business_impact_kpis(
                performance_by_demographic, summary
            )

            result = DemographicsAnalysisResult(
                customer_id=customer_id,
                analysis_type="demographics_performance",
                analyzer_name=self.get_name(),
                start_date=start_date,
                end_date=end_date,
                segments=filtered_segments,
                performance_by_demographic=performance_by_demographic,
                summary=summary,
                insights=insights,
                bid_adjustment_recommendations=bid_adjustments,
                targeting_exclusion_recommendations=exclusion_recommendations,
                budget_reallocation_recommendations=budget_recommendations,
                optimization_recommendations=optimization_recommendations,
                dashboard_metrics=dashboard_metrics,
                data_quality_kpis=data_quality_kpis,
                analysis_value_kpis=analysis_value_kpis,
                business_impact_kpis=business_impact_kpis,
            )

            logger.info(
                f"Demographics analysis completed with {len(performance_by_demographic)} segments analyzed"
            )
            return result

        except Exception as ex:
            logger.error(f"Demographics analysis failed: {ex}")
            raise

    def _extract_demographic_data(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """Extract demographic data from kwargs."""
        return {
            "age_data": kwargs.get("age_data", []),
            "gender_data": kwargs.get("gender_data", []),
            "income_data": kwargs.get("income_data", []),
            "parental_data": kwargs.get("parental_data", []),
        }

    def _convert_to_demographic_segments(
        self,
        demographic_data: Dict[str, Any],
        customer_id: str,
        start_date: datetime,
        end_date: datetime,
    ) -> list[DemographicSegment]:
        """Convert raw demographic data to structured segments."""
        segments = []

        # Process age data
        for row in demographic_data.get("age_data", []):
            segment = self._create_segment_from_row(
                row, DemographicType.AGE, customer_id, start_date, end_date
            )
            if segment:
                segments.append(segment)

        # Process gender data
        for row in demographic_data.get("gender_data", []):
            segment = self._create_segment_from_row(
                row, DemographicType.GENDER, customer_id, start_date, end_date
            )
            if segment:
                segments.append(segment)

        # Process income data
        for row in demographic_data.get("income_data", []):
            segment = self._create_segment_from_row(
                row, DemographicType.HOUSEHOLD_INCOME, customer_id, start_date, end_date
            )
            if segment:
                segments.append(segment)

        # Process parental status data
        for row in demographic_data.get("parental_data", []):
            segment = self._create_segment_from_row(
                row, DemographicType.PARENTAL_STATUS, customer_id, start_date, end_date
            )
            if segment:
                segments.append(segment)

        return segments

    def _create_segment_from_row(
        self,
        row: Dict[str, Any],
        demographic_type: DemographicType,
        customer_id: str,
        start_date: datetime,
        end_date: datetime,
    ) -> DemographicSegment | None:
        """Create a demographic segment from a data row."""
        try:
            # Map demographic value based on type
            demographic_value = self._map_demographic_value(row, demographic_type)

            if not demographic_value:
                return None

            # Extract numeric values with safety checks
            impressions = self._safe_int(row.get("Impr.", row.get("impressions", 0)))
            clicks = self._safe_int(row.get("Interactions", row.get("clicks", 0)))
            conversions = self._safe_float(
                row.get("Conversions", row.get("conversions", 0))
            )
            cost = self._safe_float(row.get("Cost", row.get("cost", 0)))
            conversion_value = self._safe_float(
                row.get("Conv. value", row.get("conversion_value", 0))
            )
            bid_adjustment = self._safe_float(
                row.get("Bid adj.", row.get("bid_adjustment", 0))
            )

            segment = DemographicSegment(
                customer_id=customer_id,
                campaign_id=row.get("campaign_id", ""),
                campaign_name=row.get("Campaign", row.get("campaign_name", "")),
                ad_group_id=row.get("ad_group_id"),
                ad_group_name=row.get("Ad group", row.get("ad_group_name")),
                demographic_type=demographic_type,
                demographic_value=demographic_value,
                status=row.get("Demographic status", row.get("status", "Enabled")),
                bid_adjustment=bid_adjustment,
                impressions=impressions,
                clicks=clicks,
                conversions=conversions,
                cost_micros=int(cost * 1_000_000),
                conversion_value_micros=int(conversion_value * 1_000_000),
                start_date=start_date,
                end_date=end_date,
            )

            return segment

        except (ValueError, TypeError) as e:
            logger.warning(f"Skipping invalid demographic data row: {e}")
            return None

    def _map_demographic_value(
        self, row: Dict[str, Any], demographic_type: DemographicType
    ) -> str | None:
        """Map demographic value from row based on type."""
        if demographic_type == DemographicType.AGE:
            age = row.get("Age", row.get("age", ""))
            return self._normalize_age_group(age)
        elif demographic_type == DemographicType.GENDER:
            gender = row.get("Gender", row.get("gender", ""))
            return self._normalize_gender(gender)
        elif demographic_type == DemographicType.HOUSEHOLD_INCOME:
            income = row.get("Household income", row.get("household_income", ""))
            return self._normalize_income_percentile(income)
        elif demographic_type == DemographicType.PARENTAL_STATUS:
            parental = row.get("Parental status", row.get("parental_status", ""))
            return self._normalize_parental_status(parental)

        return None

    def _normalize_age_group(self, age: str) -> str:
        """Normalize age group to standard format."""
        age_mapping = {
            "18-24": AgeGroup.AGE_18_24.value,
            "25-34": AgeGroup.AGE_25_34.value,
            "35-44": AgeGroup.AGE_35_44.value,
            "45-54": AgeGroup.AGE_45_54.value,
            "55-64": AgeGroup.AGE_55_64.value,
            "65+": AgeGroup.AGE_65_PLUS.value,
        }
        return age_mapping.get(age, AgeGroup.UNKNOWN.value)

    def _normalize_gender(self, gender: str) -> str:
        """Normalize gender to standard format."""
        gender_mapping = {
            "Male": GenderType.MALE.value,
            "Female": GenderType.FEMALE.value,
            "M": GenderType.MALE.value,
            "F": GenderType.FEMALE.value,
        }
        return gender_mapping.get(gender, GenderType.UNKNOWN.value)

    def _normalize_income_percentile(self, income: str) -> str:
        """Normalize income percentile to standard format."""
        # Direct mapping for known values
        for percentile in IncomePercentile:
            if income == percentile.value:
                return percentile.value
        return IncomePercentile.UNKNOWN.value

    def _normalize_parental_status(self, parental: str) -> str:
        """Normalize parental status to standard format."""
        parental_mapping = {
            "Parent": ParentalStatus.PARENT.value,
            "Not a parent": ParentalStatus.NOT_A_PARENT.value,
        }
        return parental_mapping.get(parental, ParentalStatus.UNKNOWN.value)

    def _safe_int(self, value: Any) -> int:
        """Safely convert value to int."""
        if isinstance(value, str):
            # Remove commas and quotes
            value = value.replace(",", "").replace('"', "")
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return 0

    def _safe_float(self, value: Any) -> float:
        """Safely convert value to float."""
        if isinstance(value, str):
            # Remove commas and quotes
            value = value.replace(",", "").replace('"', "")
        try:
            return float(value)
        except (ValueError, TypeError):
            return 0.0

    def _filter_segments_by_thresholds(
        self, segments: list[DemographicSegment]
    ) -> list[DemographicSegment]:
        """Filter segments by minimum thresholds."""
        return [
            segment
            for segment in segments
            if segment.impressions >= self.min_impressions
            and (segment.clicks + segment.conversions) >= self.min_interactions
        ]

    def _calculate_demographic_performance(
        self, segments: list[DemographicSegment]
    ) -> list[DemographicPerformance]:
        """Calculate performance metrics for each unique demographic."""
        if not segments:
            return []

        # Pre-compute aggregations in single pass - O(n) complexity
        from collections import defaultdict

        grouped_aggregations = defaultdict(
            lambda: {
                "segments": [],
                "impressions": 0,
                "clicks": 0,
                "conversions": 0.0,
                "cost": 0.0,
                "conversion_value": 0.0,
            }
        )

        # Single pass through segments to compute totals and group aggregations
        total_impressions = 0
        total_clicks = 0
        total_cost = 0.0
        total_conversions = 0.0
        total_conversion_value = 0.0

        for segment in segments:
            key = (segment.demographic_type, segment.demographic_value)
            group = grouped_aggregations[key]

            # Accumulate group metrics
            group["segments"].append(segment)
            group["impressions"] += segment.impressions
            group["clicks"] += segment.clicks
            group["conversions"] += segment.conversions
            group["cost"] += segment.cost
            group["conversion_value"] += segment.conversion_value

            # Accumulate totals for averages
            total_impressions += segment.impressions
            total_clicks += segment.clicks
            total_conversions += segment.conversions
            total_cost += segment.cost
            total_conversion_value += segment.conversion_value

        # Calculate average metrics across all segments
        avg_ctr = (
            (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
        )
        avg_conversion_rate = (
            (total_conversions / total_clicks * 100) if total_clicks > 0 else 0
        )
        avg_cpc = total_cost / total_clicks if total_clicks > 0 else 0
        avg_roas = total_conversion_value / total_cost if total_cost > 0 else 0

        performance_list = []

        for (
            demographic_type,
            demographic_value,
        ), aggregations in grouped_aggregations.items():
            # Use pre-computed aggregations
            group_impressions = aggregations["impressions"]
            group_clicks = aggregations["clicks"]
            group_conversions = aggregations["conversions"]
            group_cost = aggregations["cost"]
            group_conversion_value = aggregations["conversion_value"]

            # Calculate derived metrics
            group_ctr = (
                (group_clicks / group_impressions * 100) if group_impressions > 0 else 0
            )
            group_conversion_rate = (
                (group_conversions / group_clicks * 100) if group_clicks > 0 else 0
            )
            group_cpc = group_cost / group_clicks if group_clicks > 0 else 0
            group_cost_per_conversion = (
                group_cost / group_conversions if group_conversions > 0 else 0
            )
            group_roas = group_conversion_value / group_cost if group_cost > 0 else 0

            # Calculate vs average
            ctr_vs_avg = group_ctr / avg_ctr if avg_ctr > 0 else 1.0
            conversion_rate_vs_avg = (
                group_conversion_rate / avg_conversion_rate
                if avg_conversion_rate > 0
                else 1.0
            )
            cpc_vs_avg = group_cpc / avg_cpc if avg_cpc > 0 else 1.0
            roas_vs_avg = group_roas / avg_roas if avg_roas > 0 else 1.0

            # Calculate shares
            impression_share = (
                group_impressions / total_impressions if total_impressions > 0 else 0
            )
            click_share = group_clicks / total_clicks if total_clicks > 0 else 0
            cost_share = group_cost / total_cost if total_cost > 0 else 0
            conversion_share = (
                group_conversions / total_conversions if total_conversions > 0 else 0
            )

            # Calculate performance score
            performance_score = self._calculate_performance_score(
                ctr_vs_avg, conversion_rate_vs_avg, cpc_vs_avg, roas_vs_avg
            )

            performance = DemographicPerformance(
                demographic_type=demographic_type,
                demographic_value=demographic_value,
                segment_count=len(aggregations["segments"]),
                total_impressions=group_impressions,
                total_clicks=group_clicks,
                total_conversions=group_conversions,
                total_cost=group_cost,
                total_conversion_value=group_conversion_value,
                avg_ctr=group_ctr,
                avg_conversion_rate=group_conversion_rate,
                avg_cpc=group_cpc,
                avg_cost_per_conversion=group_cost_per_conversion,
                avg_roas=group_roas,
                ctr_vs_average=ctr_vs_avg,
                conversion_rate_vs_average=conversion_rate_vs_avg,
                cpc_vs_average=cpc_vs_avg,
                roas_vs_average=roas_vs_avg,
                impression_share=impression_share,
                click_share=click_share,
                cost_share=cost_share,
                conversion_share=conversion_share,
                performance_score=performance_score,
            )

            performance_list.append(performance)

        # Sort by performance score
        performance_list.sort(key=lambda x: x.performance_score, reverse=True)
        return performance_list

    def _calculate_performance_score(
        self,
        ctr_vs_avg: float,
        conversion_rate_vs_avg: float,
        cpc_vs_avg: float,
        roas_vs_avg: float,
    ) -> float:
        """Calculate overall performance score (0-100) for a demographic segment."""
        # Convert ratios to scores (50 = average performance)
        ctr_score = max(0, min(100, (ctr_vs_avg - 0.5) * 50 + 50))
        conversion_score = max(0, min(100, (conversion_rate_vs_avg - 0.5) * 50 + 50))
        cpc_score = max(
            0, min(100, 100 - (cpc_vs_avg - 0.5) * 50)
        )  # Lower CPC is better
        roas_score = (
            max(0, min(100, (roas_vs_avg - 0.5) * 50 + 50)) if roas_vs_avg > 0 else 0
        )

        # Weighted average (conversion rate 40%, CPC 30%, CTR 20%, ROAS 10%)
        return (
            conversion_score * 0.4
            + cpc_score * 0.3
            + ctr_score * 0.2
            + roas_score * 0.1
        )

    def _generate_analysis_summary(
        self,
        customer_id: str,
        segments: list[DemographicSegment],
        performance_data: list[DemographicPerformance],
        start_date: datetime,
        end_date: datetime,
    ) -> DemographicsAnalysisSummary:
        """Generate analysis summary."""
        if not segments:
            return self._create_empty_summary(customer_id, start_date, end_date)

        # Calculate data quality metrics
        segments_with_sufficient_data = len(
            [
                s
                for s in segments
                if s.impressions >= self.MIN_IMPRESSIONS_THRESHOLD
                and (s.clicks + s.conversions) >= self.MIN_INTERACTIONS_THRESHOLD
            ]
        )

        total_campaign_impressions = sum(s.impressions for s in segments)
        analyzed_impressions = sum(p.total_impressions for p in performance_data)
        coverage_percentage = (
            (analyzed_impressions / total_campaign_impressions * 100)
            if total_campaign_impressions > 0
            else 0
        )

        unknown_segments = len(
            [p for p in performance_data if "Unknown" in p.demographic_value]
        )
        data_completeness_score = (
            ((len(performance_data) - unknown_segments) / len(performance_data) * 100)
            if performance_data
            else 0
        )

        # Calculate performance metrics
        total_cost = sum(p.total_cost for p in performance_data)
        total_conversions = sum(p.total_conversions for p in performance_data)
        total_clicks = sum(p.total_clicks for p in performance_data)
        total_impressions = sum(p.total_impressions for p in performance_data)

        avg_ctr = (
            (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
        )
        avg_conversion_rate = (
            (total_conversions / total_clicks * 100) if total_clicks > 0 else 0
        )
        avg_cpc = total_cost / total_clicks if total_clicks > 0 else 0
        avg_roas = (
            sum(p.total_conversion_value for p in performance_data) / total_cost
            if total_cost > 0
            else 0
        )

        # Calculate variance metrics
        if len(performance_data) > 1:
            conversion_rates = [
                p.avg_conversion_rate
                for p in performance_data
                if p.avg_conversion_rate > 0
            ]
            cpc_values = [p.avg_cpc for p in performance_data if p.avg_cpc > 0]

            conversion_rate_variance = self._calculate_variance_percentage(
                conversion_rates
            )
            cpc_variance = self._calculate_variance_percentage(cpc_values)
        else:
            conversion_rate_variance = 0.0
            cpc_variance = 0.0

        # Count performance categories
        high_performers = len([p for p in performance_data if p.is_high_performer])
        low_performers = len([p for p in performance_data if p.is_low_performer])

        # Count segments by type
        demographic_counts = {dt: 0 for dt in DemographicType}
        for p in performance_data:
            demographic_counts[p.demographic_type] += 1

        optimization_potential = max(conversion_rate_variance, cpc_variance)

        return DemographicsAnalysisSummary(
            customer_id=customer_id,
            analysis_date=datetime.utcnow(),
            date_range_start=start_date,
            date_range_end=end_date,
            total_segments_analyzed=len(performance_data),
            segments_with_sufficient_data=segments_with_sufficient_data,
            data_completeness_score=data_completeness_score,
            coverage_percentage=coverage_percentage,
            total_cost=total_cost,
            total_conversions=total_conversions,
            total_clicks=total_clicks,
            total_impressions=total_impressions,
            average_ctr=avg_ctr,
            average_conversion_rate=avg_conversion_rate,
            average_cpc=avg_cpc,
            average_roas=avg_roas,
            conversion_rate_variance_percentage=conversion_rate_variance,
            cpc_variance_percentage=cpc_variance,
            high_performing_segments_count=high_performers,
            low_performing_segments_count=low_performers,
            optimization_opportunities_count=high_performers + low_performers,
            optimization_potential_score=optimization_potential,
            age_segments_analyzed=demographic_counts[DemographicType.AGE],
            gender_segments_analyzed=demographic_counts[DemographicType.GENDER],
            income_segments_analyzed=demographic_counts[
                DemographicType.HOUSEHOLD_INCOME
            ],
            parental_segments_analyzed=demographic_counts[
                DemographicType.PARENTAL_STATUS
            ],
        )

    def _calculate_variance_percentage(self, values: list[float]) -> float:
        """Calculate variance percentage for a list of values."""
        if len(values) < 2:
            return 0.0

        min_val = min(values)
        max_val = max(values)

        return ((max_val - min_val) / min_val * 100) if min_val > 0 else 0.0

    def _generate_demographic_insights(
        self,
        performance_data: list[DemographicPerformance],
        summary: DemographicsAnalysisSummary,
    ) -> list[DemographicInsight]:
        """Generate insights for demographic segments."""
        insights = []

        for performance in performance_data:
            # Determine insight type and message
            if performance.is_high_performer:
                insight_type = "opportunity"
                message = f"{performance.demographic_value} shows excellent performance with {performance.performance_score:.1f} score"
                recommended_action = "INCREASE_INVESTMENT"
                impact_potential = "high"
            elif performance.is_low_performer:
                insight_type = "underperformer"
                message = f"{performance.demographic_value} underperforming with {performance.performance_score:.1f} score"
                recommended_action = "REDUCE_INVESTMENT_OR_EXCLUDE"
                impact_potential = "high"
            elif performance.conversion_rate_vs_average >= 1.2:
                insight_type = "optimization"
                message = f"{performance.demographic_value} has {performance.conversion_rate_vs_average:.1%} higher conversion rate than average"
                recommended_action = "INCREASE_BID_ADJUSTMENTS"
                impact_potential = "medium"
            elif performance.cpc_vs_average >= 1.15:
                insight_type = "optimization"
                message = f"{performance.demographic_value} has {performance.cpc_vs_average:.1%} higher CPC than average"
                recommended_action = "DECREASE_BID_ADJUSTMENTS"
                impact_potential = "medium"
            else:
                continue  # Skip segments without notable insights

            # Generate bid adjustment recommendation
            bid_recommendation = self._get_bid_adjustment_recommendation(performance)

            # Calculate potential improvement
            potential_improvement = self._calculate_potential_improvement(performance)

            # Estimate cost impact
            cost_impact = performance.cost_share * potential_improvement

            insight = DemographicInsight(
                demographic_type=performance.demographic_type,
                demographic_value=performance.demographic_value,
                insight_type=insight_type,
                insight_message=message,
                recommended_action=recommended_action,
                bid_adjustment_recommendation=bid_recommendation,
                impact_potential=impact_potential,
                current_performance_score=performance.performance_score,
                potential_improvement=potential_improvement,
                cost_impact_estimate=cost_impact,
            )

            insights.append(insight)

        return insights

    def _get_bid_adjustment_recommendation(
        self, performance: DemographicPerformance
    ) -> str:
        """Get bid adjustment recommendation for a demographic segment."""
        if performance.is_high_performer:
            if performance.cost_share < 0.2:  # Low cost share suggests opportunity
                return "Increase bid adjustments by 15-25% to capture more volume"
            else:
                return "Maintain current bid adjustments, consider increasing budget allocation"
        elif performance.is_low_performer:
            return "Decrease bid adjustments by 20-30% or consider excluding this demographic"
        elif performance.conversion_rate_vs_average >= 1.2:
            return f"Increase bid adjustments by 10-20% due to {performance.conversion_rate_vs_average:.1%} higher conversion rate"
        elif performance.cpc_vs_average >= 1.15:
            return f"Decrease bid adjustments by 10-15% due to {performance.cpc_vs_average:.1%} higher CPC"
        else:
            return "Monitor current bid adjustments"

    def _calculate_potential_improvement(
        self, performance: DemographicPerformance
    ) -> float:
        """Calculate potential improvement percentage for a demographic segment."""
        if performance.is_high_performer:
            return min(
                25.0, (performance.performance_score - 50) / 2
            )  # Up to 25% improvement
        elif performance.is_low_performer:
            return min(
                30.0, (50 - performance.performance_score) / 2
            )  # Up to 30% cost savings
        elif performance.conversion_rate_vs_average >= 1.2:
            return (
                (performance.conversion_rate_vs_average - 1) * 100 / 2
            )  # Half the conversion rate advantage
        elif performance.cpc_vs_average >= 1.15:
            return (
                (performance.cpc_vs_average - 1) * 100 / 2
            )  # Half the CPC disadvantage
        else:
            return 5.0  # Default small improvement

    def _generate_bid_adjustment_recommendations(
        self, performance_data: list[DemographicPerformance]
    ) -> dict[str, float]:
        """Generate bid adjustment recommendations."""
        recommendations = {}

        for performance in performance_data:
            demo_type = performance.demographic_type
            demo_type_str = (
                demo_type.value if hasattr(demo_type, "value") else str(demo_type)
            )
            key = f"{demo_type_str}:{performance.demographic_value}"

            if performance.is_high_performer:
                recommendations[key] = min(
                    0.25, (performance.performance_score - 50) / 200
                )
            elif performance.is_low_performer:
                recommendations[key] = max(
                    -0.30, (performance.performance_score - 50) / 200
                )
            elif performance.conversion_rate_vs_average >= 1.2:
                recommendations[key] = min(
                    0.20, (performance.conversion_rate_vs_average - 1) / 2
                )
            elif performance.cpc_vs_average >= 1.15:
                recommendations[key] = max(-0.15, -(performance.cpc_vs_average - 1) / 2)
            else:
                recommendations[key] = 0.0

        return recommendations

    def _generate_exclusion_recommendations(
        self, performance_data: list[DemographicPerformance]
    ) -> list[str]:
        """Generate targeting exclusion recommendations."""
        exclusions = []

        for performance in performance_data:
            if (
                performance.is_low_performer
                and performance.conversion_rate_vs_average < 0.5
                and performance.cost_share > 0.05
            ):  # At least 5% cost share
                demo_type = performance.demographic_type
                demo_type_str = (
                    demo_type.value if hasattr(demo_type, "value") else str(demo_type)
                )
                exclusions.append(
                    f"Consider excluding {demo_type_str}: {performance.demographic_value} "
                    f"(Performance score: {performance.performance_score:.1f}, "
                    f"Conversion rate: {performance.conversion_rate_vs_average:.1%} of average)"
                )

        return exclusions

    def _generate_budget_reallocation_recommendations(
        self, performance_data: list[DemographicPerformance]
    ) -> list[str]:
        """Generate budget reallocation recommendations."""
        recommendations = []

        high_performers = [
            p for p in performance_data if p.is_high_performer and p.cost_share < 0.3
        ]
        low_performers = [
            p for p in performance_data if p.is_low_performer and p.cost_share > 0.1
        ]

        if high_performers and low_performers:
            total_low_performer_share = sum(p.cost_share for p in low_performers)
            reallocation_potential = min(
                total_low_performer_share * 100, 25.0
            )  # Cap at 25%

            recommendations.append(
                f"Reallocate up to {reallocation_potential:.1f}% of budget from underperforming demographics "
                f"to high-performing segments"
            )

        # Specific recommendations for top performers
        top_performers = sorted(
            performance_data, key=lambda x: x.performance_score, reverse=True
        )[:3]
        for performer in top_performers:
            if performer.is_high_performer and performer.cost_share < 0.2:
                demo_type = performer.demographic_type
                demo_type_str = (
                    demo_type.value if hasattr(demo_type, "value") else str(demo_type)
                )
                recommendations.append(
                    f"Increase budget allocation for {demo_type_str}: {performer.demographic_value} "
                    f"(Performance score: {performer.performance_score:.1f}, Current share: {performer.cost_share:.1%})"
                )

        return recommendations

    def _generate_optimization_recommendations(
        self, insights: list[DemographicInsight], summary: DemographicsAnalysisSummary
    ) -> list[str]:
        """Generate general optimization recommendations."""
        recommendations = []

        # High-level recommendations based on summary
        if (
            summary.conversion_rate_variance_percentage
            > self.SIGNIFICANT_CONVERSION_RATE_VARIANCE
        ):
            recommendations.append(
                f"High conversion rate variance ({summary.conversion_rate_variance_percentage:.1f}%) "
                f"indicates significant demographic targeting optimization opportunities"
            )

        if summary.cpc_variance_percentage > self.SIGNIFICANT_CPC_VARIANCE:
            recommendations.append(
                f"High CPC variance ({summary.cpc_variance_percentage:.1f}%) suggests implementing "
                f"demographic-specific bid adjustments"
            )

        if summary.data_completeness_score < self.MIN_COMPLETENESS_SCORE:
            recommendations.append(
                f"Data completeness is {summary.data_completeness_score:.1f}% - consider improving "
                f"demographic data collection and targeting specificity"
            )

        # Recommendations based on insights
        high_impact_insights = [i for i in insights if i.impact_potential == "high"]
        if len(high_impact_insights) >= self.MIN_ACTIONABLE_RECOMMENDATIONS:
            recommendations.append(
                f"Implement immediate changes for {len(high_impact_insights)} high-impact demographic segments"
            )

        # Performance-based recommendations
        if (
            summary.high_performing_segments_count > 0
            and summary.low_performing_segments_count > 0
        ):
            recommendations.append(
                f"Focus budget on {summary.high_performing_segments_count} high-performing segments "
                f"and reduce investment in {summary.low_performing_segments_count} underperforming segments"
            )

        return recommendations

    def _create_dashboard_metrics(
        self,
        summary: DemographicsAnalysisSummary,
        performance_data: list[DemographicPerformance],
    ) -> dict[str, Any]:
        """Create dashboard metrics."""
        top_performer_score = (
            performance_data[0].performance_score if performance_data else 0.0
        )
        bottom_performer_score = (
            performance_data[-1].performance_score if performance_data else 0.0
        )

        return {
            "total_segments_analyzed": summary.total_segments_analyzed,
            "data_completeness_score": summary.data_completeness_score,
            "coverage_percentage": summary.coverage_percentage,
            "average_conversion_rate": summary.average_conversion_rate,
            "average_cpc": summary.average_cpc,
            "average_roas": summary.average_roas,
            "conversion_rate_variance": summary.conversion_rate_variance_percentage,
            "cpc_variance": summary.cpc_variance_percentage,
            "optimization_potential": summary.optimization_potential_score,
            "high_performers_count": summary.high_performing_segments_count,
            "low_performers_count": summary.low_performing_segments_count,
            "top_performer_score": top_performer_score,
            "bottom_performer_score": bottom_performer_score,
            "performance_spread": top_performer_score - bottom_performer_score,
            "age_segments": summary.age_segments_analyzed,
            "gender_segments": summary.gender_segments_analyzed,
            "income_segments": summary.income_segments_analyzed,
            "parental_segments": summary.parental_segments_analyzed,
        }

    def _calculate_data_quality_kpis(
        self, summary: DemographicsAnalysisSummary, segments: list[DemographicSegment]
    ) -> dict[str, float]:
        """Calculate data quality KPIs."""
        # Check if all segments meet minimum thresholds
        min_impressions_met = (
            all(
                segment.impressions >= self.MIN_IMPRESSIONS_THRESHOLD
                for segment in segments
            )
            if segments
            else True
        )

        min_interactions_met = (
            all(
                (segment.clicks + segment.conversions)
                >= self.MIN_INTERACTIONS_THRESHOLD
                for segment in segments
            )
            if segments
            else True
        )

        return {
            "min_impressions_threshold_met": float(min_impressions_met),
            "min_interactions_threshold_met": float(min_interactions_met),
            "coverage_percentage": summary.coverage_percentage,
            "data_completeness_score": summary.data_completeness_score,
            "segments_with_sufficient_data_ratio": (
                summary.segments_with_sufficient_data / summary.total_segments_analyzed
                if summary.total_segments_analyzed > 0
                else 0.0
            ),
        }

    def _calculate_analysis_value_kpis(
        self,
        insights: list[DemographicInsight],
        performance_data: list[DemographicPerformance],
    ) -> dict[str, float]:
        """Calculate analysis value KPIs."""
        # Performance variance calculations
        if len(performance_data) > 1:
            conversion_rates = [
                p.avg_conversion_rate
                for p in performance_data
                if p.avg_conversion_rate > 0
            ]
            cpc_values = [p.avg_cpc for p in performance_data if p.avg_cpc > 0]

            max_conversion_variance = self._calculate_variance_percentage(
                conversion_rates
            )
            max_cpc_variance = self._calculate_variance_percentage(cpc_values)
        else:
            max_conversion_variance = 0.0
            max_cpc_variance = 0.0

        return {
            "performance_variance_identified": float(
                max_conversion_variance >= self.SIGNIFICANT_CONVERSION_RATE_VARIANCE
            ),
            "cost_efficiency_gaps_found": float(
                max_cpc_variance >= self.SIGNIFICANT_CPC_VARIANCE
            ),
            "actionable_recommendations_generated": float(len(insights)),
            "actionable_recommendations_threshold_met": float(
                len(insights) >= self.MIN_ACTIONABLE_RECOMMENDATIONS
            ),
            "max_conversion_rate_variance": max_conversion_variance,
            "max_cpc_variance": max_cpc_variance,
        }

    def _calculate_business_impact_kpis(
        self,
        performance_data: list[DemographicPerformance],
        summary: DemographicsAnalysisSummary,
    ) -> dict[str, float]:
        """Calculate business impact KPIs."""
        if not performance_data:
            return {
                "conversion_rate_spread": 0.0,
                "cost_per_conversion_variance": 0.0,
                "spend_optimization_potential": 0.0,
                "roi_impact_threshold_met": 0.0,
            }

        # Calculate spreads
        conversion_rates = [
            p.avg_conversion_rate for p in performance_data if p.avg_conversion_rate > 0
        ]
        cpc_values = [p.avg_cpc for p in performance_data if p.avg_cpc > 0]

        conversion_rate_spread = (
            (max(conversion_rates) - min(conversion_rates)) if conversion_rates else 0.0
        )
        cpc_spread = (max(cpc_values) - min(cpc_values)) if cpc_values else 0.0

        # Calculate optimization potential
        high_performers = [p for p in performance_data if p.is_high_performer]
        low_performers = [p for p in performance_data if p.is_low_performer]

        spend_optimization_potential = 0.0
        if high_performers and low_performers:
            low_performer_cost_share = sum(p.cost_share for p in low_performers)
            spend_optimization_potential = min(low_performer_cost_share * 100, 30.0)

        return {
            "conversion_rate_spread": conversion_rate_spread,
            "cost_per_conversion_variance": cpc_spread,
            "spend_optimization_potential": spend_optimization_potential,
            "roi_impact_threshold_met": float(
                spend_optimization_potential >= self.MIN_ROI_IMPACT_POTENTIAL
            ),
        }

    def _create_empty_result(
        self, customer_id: str, start_date: datetime, end_date: datetime
    ) -> DemographicsAnalysisResult:
        """Create empty result when no data is available."""
        empty_summary = self._create_empty_summary(customer_id, start_date, end_date)
        empty_segments = []
        empty_performance = []
        empty_insights = []

        return DemographicsAnalysisResult(
            customer_id=customer_id,
            analysis_type="demographics_performance",
            analyzer_name=self.get_name(),
            start_date=start_date,
            end_date=end_date,
            segments=empty_segments,
            performance_by_demographic=empty_performance,
            summary=empty_summary,
            insights=empty_insights,
            bid_adjustment_recommendations={},
            targeting_exclusion_recommendations=[],
            budget_reallocation_recommendations=[],
            optimization_recommendations=["No demographic data available for analysis"],
            dashboard_metrics={},
            data_quality_kpis=self._calculate_data_quality_kpis(
                empty_summary, empty_segments
            ),
            analysis_value_kpis=self._calculate_analysis_value_kpis(
                empty_insights, empty_performance
            ),
            business_impact_kpis=self._calculate_business_impact_kpis(
                empty_performance, empty_summary
            ),
        )

    def _create_empty_summary(
        self, customer_id: str, start_date: datetime, end_date: datetime
    ) -> DemographicsAnalysisSummary:
        """Create empty summary when no data is available."""
        return DemographicsAnalysisSummary(
            customer_id=customer_id,
            analysis_date=datetime.utcnow(),
            date_range_start=start_date,
            date_range_end=end_date,
        )

    def get_name(self) -> str:
        """Return analyzer name."""
        return "demographics_performance"

    def get_description(self) -> str:
        """Return analyzer description."""
        return "Analyzes age, gender, income, and parental status demographics to identify targeting optimization opportunities"
