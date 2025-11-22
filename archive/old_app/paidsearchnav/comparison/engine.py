"""Core engine for comparing audit results."""

import logging
from typing import Any, Dict, List, Optional

import numpy as np
from scipy import stats

from paidsearchnav.storage.api_repository import APIRepository

from .models import (
    AuditResult,
    ComparisonMetrics,
    ComparisonOptions,
    ComparisonResult,
    ImplementationStatus,
    Recommendation,
)

logger = logging.getLogger(__name__)


class AuditComparator:
    """Engine for comparing audit results and tracking progress."""

    def __init__(self, repository: APIRepository):
        """Initialize the comparator with a repository."""
        self.repository = repository

    async def compare_audits(
        self,
        baseline_audit_id: str,
        comparison_audit_id: str,
        options: Optional[ComparisonOptions] = None,
    ) -> ComparisonResult:
        """Compare two audit results with configurable options."""
        if options is None:
            options = ComparisonOptions()

        # Fetch audit results
        baseline_audit = await self._get_audit_result(baseline_audit_id)
        comparison_audit = await self._get_audit_result(comparison_audit_id)

        if not baseline_audit or not comparison_audit:
            raise ValueError("One or both audit results not found")

        # Calculate comparison metrics
        metrics = self._calculate_comparison_metrics(
            baseline_audit, comparison_audit, options
        )

        # Generate insights
        insights = self._generate_insights(metrics, baseline_audit, comparison_audit)

        # Generate warnings
        warnings = self._generate_warnings(metrics)

        # Create result
        result = ComparisonResult(
            baseline_audit_id=baseline_audit_id,
            comparison_audit_id=comparison_audit_id,
            baseline_date=baseline_audit.created_at,
            comparison_date=comparison_audit.created_at,
            metrics=metrics,
            insights=insights,
            warnings=warnings,
        )

        # Add optional breakdowns
        if options.breakdown_by_campaign:
            result.breakdown_by_campaign = await self._get_campaign_breakdown(
                baseline_audit, comparison_audit, options
            )

        if options.breakdown_by_ad_group:
            result.breakdown_by_ad_group = await self._get_ad_group_breakdown(
                baseline_audit, comparison_audit, options
            )

        if options.include_recommendations:
            result.recommendations_comparison = await self._compare_recommendations(
                baseline_audit_id, comparison_audit_id
            )

        return result

    def _calculate_comparison_metrics(
        self,
        baseline: AuditResult,
        comparison: AuditResult,
        options: ComparisonOptions,
    ) -> ComparisonMetrics:
        """Calculate all comparison metrics between two audits."""
        baseline_metrics = baseline.summary.get("metrics", {})
        comparison_metrics = comparison.summary.get("metrics", {})

        # Cost efficiency calculations
        baseline_spend = baseline_metrics.get("total_spend", 0)
        comparison_spend = comparison_metrics.get("total_spend", 0)
        spend_change = comparison_spend - baseline_spend
        spend_change_pct = self._calculate_percentage_change(
            baseline_spend, comparison_spend
        )

        baseline_wasted = baseline_metrics.get("wasted_spend", 0)
        comparison_wasted = comparison_metrics.get("wasted_spend", 0)
        wasted_reduction = baseline_wasted - comparison_wasted
        wasted_reduction_pct = self._calculate_percentage_change(
            baseline_wasted, comparison_wasted, inverse=True
        )

        baseline_cpc = baseline_metrics.get("cost_per_conversion", 0)
        comparison_cpc = comparison_metrics.get("cost_per_conversion", 0)
        cpc_change = comparison_cpc - baseline_cpc
        cpc_change_pct = self._calculate_percentage_change(baseline_cpc, comparison_cpc)

        baseline_roas = baseline_metrics.get("roas", 0)
        comparison_roas = comparison_metrics.get("roas", 0)
        roas_change = comparison_roas - baseline_roas
        roas_change_pct = self._calculate_percentage_change(
            baseline_roas, comparison_roas
        )

        # Performance metrics
        baseline_ctr = baseline_metrics.get("ctr", 0)
        comparison_ctr = comparison_metrics.get("ctr", 0)
        ctr_improvement = comparison_ctr - baseline_ctr
        ctr_improvement_pct = self._calculate_percentage_change(
            baseline_ctr, comparison_ctr
        )

        baseline_cvr = baseline_metrics.get("conversion_rate", 0)
        comparison_cvr = comparison_metrics.get("conversion_rate", 0)
        cvr_change = comparison_cvr - baseline_cvr
        cvr_change_pct = self._calculate_percentage_change(baseline_cvr, comparison_cvr)

        baseline_qs = baseline_metrics.get("avg_quality_score", 0)
        comparison_qs = comparison_metrics.get("avg_quality_score", 0)
        qs_trend = comparison_qs - baseline_qs

        # Volume metrics
        baseline_impressions = baseline_metrics.get("impressions", 0)
        comparison_impressions = comparison_metrics.get("impressions", 0)
        impressions_change = comparison_impressions - baseline_impressions
        impressions_change_pct = self._calculate_percentage_change(
            baseline_impressions, comparison_impressions
        )

        baseline_clicks = baseline_metrics.get("clicks", 0)
        comparison_clicks = comparison_metrics.get("clicks", 0)
        clicks_change = comparison_clicks - baseline_clicks
        clicks_change_pct = self._calculate_percentage_change(
            baseline_clicks, comparison_clicks
        )

        baseline_conversions = baseline_metrics.get("conversions", 0)
        comparison_conversions = comparison_metrics.get("conversions", 0)
        conversions_change = comparison_conversions - baseline_conversions
        conversions_change_pct = self._calculate_percentage_change(
            baseline_conversions, comparison_conversions
        )

        # Optimization progress
        baseline_issues = baseline.summary.get("total_issues", 0)
        comparison_issues = comparison.summary.get("total_issues", 0)
        issues_resolved = max(0, baseline_issues - comparison_issues)
        new_issues = max(0, comparison_issues - baseline_issues)

        # Coverage metrics
        baseline_keywords = baseline_metrics.get("keywords_analyzed", 0)
        comparison_keywords = comparison_metrics.get("keywords_analyzed", 0)
        keywords_change = comparison_keywords - baseline_keywords

        # Create metrics object
        metrics = ComparisonMetrics(
            total_spend_change=spend_change,
            total_spend_change_pct=spend_change_pct,
            wasted_spend_reduction=wasted_reduction,
            wasted_spend_reduction_pct=wasted_reduction_pct,
            cost_per_conversion_change=cpc_change,
            cost_per_conversion_change_pct=cpc_change_pct,
            roas_change=roas_change,
            roas_change_pct=roas_change_pct,
            ctr_improvement=ctr_improvement,
            ctr_improvement_pct=ctr_improvement_pct,
            conversion_rate_change=cvr_change,
            conversion_rate_change_pct=cvr_change_pct,
            quality_score_trend=qs_trend,
            impressions_change=impressions_change,
            impressions_change_pct=impressions_change_pct,
            clicks_change=clicks_change,
            clicks_change_pct=clicks_change_pct,
            conversions_change=conversions_change,
            conversions_change_pct=conversions_change_pct,
            recommendations_implemented=0,  # To be calculated separately
            recommendations_pending=0,
            issues_resolved=issues_resolved,
            new_issues_found=new_issues,
            keywords_analyzed_change=keywords_change,
            negative_keywords_added=0,  # To be calculated separately
            match_type_optimizations=0,  # To be calculated separately
        )

        # Add statistical significance tests if requested
        if options.include_statistical_tests:
            metrics.is_statistically_significant = self._test_statistical_significance(
                baseline, comparison, options
            )

        return metrics

    def _calculate_percentage_change(
        self, baseline: float, comparison: float, inverse: bool = False
    ) -> float:
        """Calculate percentage change between two values."""
        if baseline == 0:
            return 0.0 if comparison == 0 else (100.0 if not inverse else -100.0)

        if inverse:
            # For metrics where decrease is good (like wasted spend)
            return ((baseline - comparison) / baseline) * 100
        else:
            return ((comparison - baseline) / baseline) * 100

    def _test_statistical_significance(
        self,
        baseline: AuditResult,
        comparison: AuditResult,
        options: ComparisonOptions,
    ) -> Dict[str, bool]:
        """Test statistical significance of metric changes."""
        significance_results = {}

        baseline_metrics = baseline.summary.get("metrics", {})
        comparison_metrics = comparison.summary.get("metrics", {})

        # CTR significance test (using binomial test)
        baseline_impressions = baseline_metrics.get("impressions", 0)
        baseline_clicks = baseline_metrics.get("clicks", 0)
        comparison_impressions = comparison_metrics.get("impressions", 0)
        comparison_clicks = comparison_metrics.get("clicks", 0)

        if (
            baseline_impressions >= options.minimum_sample_size
            and comparison_impressions >= options.minimum_sample_size
        ):
            # Perform chi-square test for CTR
            baseline_ctr = baseline_clicks / baseline_impressions
            comparison_ctr = comparison_clicks / comparison_impressions

            # Create contingency table
            observed = np.array(
                [
                    [baseline_clicks, baseline_impressions - baseline_clicks],
                    [comparison_clicks, comparison_impressions - comparison_clicks],
                ]
            )

            chi2, p_value, _, _ = stats.chi2_contingency(observed)
            significance_results["ctr"] = p_value < (1 - options.confidence_level)

        # Conversion rate significance test
        baseline_conversions = baseline_metrics.get("conversions", 0)
        comparison_conversions = comparison_metrics.get("conversions", 0)

        if (
            baseline_clicks >= options.minimum_sample_size
            and comparison_clicks >= options.minimum_sample_size
        ):
            # Test conversion rate significance
            observed = np.array(
                [
                    [baseline_conversions, baseline_clicks - baseline_conversions],
                    [
                        comparison_conversions,
                        comparison_clicks - comparison_conversions,
                    ],
                ]
            )

            chi2, p_value, _, _ = stats.chi2_contingency(observed)
            significance_results["conversion_rate"] = p_value < (
                1 - options.confidence_level
            )

        return significance_results

    def _generate_insights(
        self,
        metrics: ComparisonMetrics,
        baseline: AuditResult,
        comparison: AuditResult,
    ) -> List[str]:
        """Generate human-readable insights from comparison."""
        insights = []

        # Cost efficiency insights
        if metrics.wasted_spend_reduction_pct > 10:
            insights.append(
                f"Excellent progress! Wasted spend reduced by {metrics.wasted_spend_reduction_pct:.1f}%, "
                f"saving ${metrics.wasted_spend_reduction:,.2f}"
            )

        if metrics.roas_change_pct > 5:
            insights.append(
                f"ROAS improved by {metrics.roas_change_pct:.1f}%, indicating better return on ad spend"
            )

        # Performance insights
        if metrics.ctr_improvement_pct > 5:
            insights.append(
                f"CTR improved by {metrics.ctr_improvement_pct:.1f}%, suggesting more relevant ads/keywords"
            )

        if metrics.conversion_rate_change_pct > 5:
            insights.append(
                f"Conversion rate increased by {metrics.conversion_rate_change_pct:.1f}%, "
                f"resulting in {metrics.conversions_change} more conversions"
            )

        # Quality score insights
        if metrics.quality_score_trend > 0.5:
            insights.append(
                f"Quality scores improved by {metrics.quality_score_trend:.1f} points on average"
            )

        # Issue resolution insights
        if metrics.issues_resolved > 0:
            insights.append(
                f"{metrics.issues_resolved} issues were resolved since the last audit"
            )

        if metrics.new_issues_found > 0:
            insights.append(
                f"{metrics.new_issues_found} new issues detected that require attention"
            )

        # Statistical significance
        if metrics.is_statistically_significant.get("ctr", False):
            insights.append("CTR improvement is statistically significant")

        if metrics.is_statistically_significant.get("conversion_rate", False):
            insights.append("Conversion rate improvement is statistically significant")

        return insights

    def _generate_warnings(self, metrics: ComparisonMetrics) -> List[str]:
        """Generate warnings for concerning trends."""
        warnings = []

        # Performance warnings
        if metrics.ctr_improvement_pct < -5:
            warnings.append(
                f"CTR decreased by {abs(metrics.ctr_improvement_pct):.1f}% - investigate ad relevance"
            )

        if metrics.conversion_rate_change_pct < -5:
            warnings.append(
                f"Conversion rate dropped by {abs(metrics.conversion_rate_change_pct):.1f}% - "
                f"check landing pages and user experience"
            )

        # Cost warnings
        if metrics.cost_per_conversion_change_pct > 10:
            warnings.append(
                f"Cost per conversion increased by {metrics.cost_per_conversion_change_pct:.1f}% - "
                f"review bidding strategy"
            )

        if metrics.total_spend_change_pct > 20 and metrics.conversions_change_pct < 10:
            warnings.append(
                "Spend increased significantly without proportional conversion growth"
            )

        # Quality score warnings
        if metrics.quality_score_trend < -0.5:
            warnings.append(
                f"Quality scores declined by {abs(metrics.quality_score_trend):.1f} points - "
                f"may lead to higher costs"
            )

        # New issues warning
        if metrics.new_issues_found > metrics.issues_resolved:
            warnings.append(
                f"More new issues found ({metrics.new_issues_found}) than resolved ({metrics.issues_resolved})"
            )

        return warnings

    async def _get_audit_result(self, audit_id: str) -> Optional[AuditResult]:
        """Fetch audit result from repository."""
        try:
            # TODO: Implement actual audit fetching when repository method is available
            # For now, return None to indicate the audit wasn't found
            logger.warning(
                f"Audit fetching not implemented. Returning None for audit {audit_id}"
            )
            return None
        except Exception as e:
            logger.error(f"Error fetching audit {audit_id}: {e}")
            return None

    async def _get_campaign_breakdown(
        self,
        baseline: AuditResult,
        comparison: AuditResult,
        options: ComparisonOptions,
    ) -> Dict[str, ComparisonMetrics]:
        """Get comparison metrics broken down by campaign."""
        # Campaign breakdown requires detailed campaign-level data
        # which should be available in the audit details
        campaign_breakdown = {}

        # Check if campaign data is available in the audit results
        baseline_campaigns = baseline.details.get("campaigns", {})
        comparison_campaigns = comparison.details.get("campaigns", {})

        if not baseline_campaigns or not comparison_campaigns:
            logger.warning(
                "Campaign-level data not available in audit results. "
                "Campaign breakdown will be empty."
            )
            return {}

        # Process each campaign that appears in either audit
        all_campaigns = set(baseline_campaigns.keys()) | set(
            comparison_campaigns.keys()
        )

        for campaign_id in all_campaigns:
            baseline_data = baseline_campaigns.get(campaign_id, {})
            comparison_data = comparison_campaigns.get(campaign_id, {})

            # Skip if no metrics available for this campaign
            if not baseline_data and not comparison_data:
                continue

            # Calculate metrics for this campaign
            # Note: This is a simplified implementation
            # In production, you would calculate all metrics
            campaign_breakdown[campaign_id] = ComparisonMetrics(
                total_spend_change=0.0,
                total_spend_change_pct=0.0,
                wasted_spend_reduction=0.0,
                wasted_spend_reduction_pct=0.0,
                cost_per_conversion_change=0.0,
                cost_per_conversion_change_pct=0.0,
                roas_change=0.0,
                roas_change_pct=0.0,
                ctr_improvement=0.0,
                ctr_improvement_pct=0.0,
                conversion_rate_change=0.0,
                conversion_rate_change_pct=0.0,
                quality_score_trend=0.0,
                impressions_change=0,
                impressions_change_pct=0.0,
                clicks_change=0,
                clicks_change_pct=0.0,
                conversions_change=0,
                conversions_change_pct=0.0,
                recommendations_implemented=0,
                recommendations_pending=0,
                issues_resolved=0,
                new_issues_found=0,
                keywords_analyzed_change=0,
                negative_keywords_added=0,
                match_type_optimizations=0,
            )

        return campaign_breakdown

    async def _get_ad_group_breakdown(
        self,
        baseline: AuditResult,
        comparison: AuditResult,
        options: ComparisonOptions,
    ) -> Dict[str, ComparisonMetrics]:
        """Get comparison metrics broken down by ad group."""
        # Ad group breakdown requires detailed ad group-level data
        ad_group_breakdown = {}

        # Check if ad group data is available in the audit results
        baseline_ad_groups = baseline.details.get("ad_groups", {})
        comparison_ad_groups = comparison.details.get("ad_groups", {})

        if not baseline_ad_groups or not comparison_ad_groups:
            logger.warning(
                "Ad group-level data not available in audit results. "
                "Ad group breakdown will be empty."
            )
            return {}

        # Process each ad group that appears in either audit
        all_ad_groups = set(baseline_ad_groups.keys()) | set(
            comparison_ad_groups.keys()
        )

        for ad_group_id in all_ad_groups:
            baseline_data = baseline_ad_groups.get(ad_group_id, {})
            comparison_data = comparison_ad_groups.get(ad_group_id, {})

            # Skip if no metrics available for this ad group
            if not baseline_data and not comparison_data:
                continue

            # Calculate metrics for this ad group
            # Note: This is a simplified implementation
            # In production, you would calculate all metrics
            ad_group_breakdown[ad_group_id] = ComparisonMetrics(
                total_spend_change=0.0,
                total_spend_change_pct=0.0,
                wasted_spend_reduction=0.0,
                wasted_spend_reduction_pct=0.0,
                cost_per_conversion_change=0.0,
                cost_per_conversion_change_pct=0.0,
                roas_change=0.0,
                roas_change_pct=0.0,
                ctr_improvement=0.0,
                ctr_improvement_pct=0.0,
                conversion_rate_change=0.0,
                conversion_rate_change_pct=0.0,
                quality_score_trend=0.0,
                impressions_change=0,
                impressions_change_pct=0.0,
                clicks_change=0,
                clicks_change_pct=0.0,
                conversions_change=0,
                conversions_change_pct=0.0,
                recommendations_implemented=0,
                recommendations_pending=0,
                issues_resolved=0,
                new_issues_found=0,
                keywords_analyzed_change=0,
                negative_keywords_added=0,
                match_type_optimizations=0,
            )

        return ad_group_breakdown

    async def _compare_recommendations(
        self, baseline_audit_id: str, comparison_audit_id: str
    ) -> Dict[str, Any]:
        """Compare recommendations between two audits."""
        # TODO: Implement actual recommendation fetching when repository method is available
        # For now, return empty lists
        baseline_recs = []
        comparison_recs = []

        # Analyze recommendation changes
        baseline_types = {r.type for r in baseline_recs}
        comparison_types = {r.type for r in comparison_recs}

        return {
            "baseline_count": len(baseline_recs),
            "comparison_count": len(comparison_recs),
            "new_recommendation_types": list(comparison_types - baseline_types),
            "resolved_recommendation_types": list(baseline_types - comparison_types),
            "persistent_recommendation_types": list(baseline_types & comparison_types),
        }

    async def track_implementation(
        self,
        recommendations: List[Recommendation],
        current_account_state: Dict[str, Any],
    ) -> List[ImplementationStatus]:
        """Track which recommendations have been implemented."""
        implementation_statuses = []

        for rec in recommendations:
            status = self._check_implementation_status(rec, current_account_state)
            implementation_statuses.append(status)

        return implementation_statuses

    def _check_implementation_status(
        self, recommendation: Recommendation, account_state: Dict[str, Any]
    ) -> ImplementationStatus:
        """Check if a specific recommendation has been implemented."""
        # Implementation checking requires access to current account state
        # which would typically come from the Google Ads API

        # For now, we'll return a sensible default that indicates
        # the check couldn't be performed due to missing account data
        if not account_state:
            logger.warning(
                f"No account state provided for recommendation {recommendation.id}. "
                "Cannot verify implementation status."
            )
            return ImplementationStatus(
                recommendation_id=recommendation.id,
                audit_id=recommendation.audit_id,
                status="unknown",
                notes="Account state data not available for verification",
            )

        # In a full implementation, you would check the specific
        # recommendation type against the current account state
        # For example:
        # - For negative keyword recommendations, check if the keyword was added
        # - For bid adjustments, check if the bid was changed
        # - For ad copy changes, check if the ad text was updated

        return ImplementationStatus(
            recommendation_id=recommendation.id,
            audit_id=recommendation.audit_id,
            status="pending",
            notes="Implementation check requires Google Ads API integration",
        )
