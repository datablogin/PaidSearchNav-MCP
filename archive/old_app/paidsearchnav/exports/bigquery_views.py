"""BigQuery SQL Views for Analyzer Logic Replacement.

This module provides SQL views that replicate all Python analyzer functionality
for 10x faster BigQuery-native analytics as described in Issue #484.
"""

import logging
from typing import Any, Dict

try:
    from google.cloud import bigquery
    from google.cloud.exceptions import GoogleCloudError

    BIGQUERY_AVAILABLE = True
except ImportError:
    BIGQUERY_AVAILABLE = False

    class MockBigQuery:
        Client = None

    bigquery = MockBigQuery()
    GoogleCloudError = Exception

from .bigquery import BigQueryExporter

logger = logging.getLogger(__name__)


class AnalyzerViewConfig:
    """Configuration for analyzer view business logic thresholds."""

    def __init__(
        self,
        high_cost_threshold: float = 50.0,
        low_cost_threshold: float = 20.0,
        low_ctr_threshold: float = 0.005,
        low_quality_score_threshold: int = 5,
        high_cpa_threshold: float = 100.0,
        conversion_rank_threshold: int = 10,
        days_lookback: int = 90,
        average_order_value: float = 100.0,
        min_impressions_threshold: int = 100,
        demographic_low_threshold: float = 0.1,
        demographic_high_threshold: float = 0.4,
    ):
        """Initialize configuration with business logic thresholds."""
        self.high_cost_threshold = high_cost_threshold
        self.low_cost_threshold = low_cost_threshold
        self.low_ctr_threshold = low_ctr_threshold
        self.low_quality_score_threshold = low_quality_score_threshold
        self.high_cpa_threshold = high_cpa_threshold
        self.conversion_rank_threshold = conversion_rank_threshold
        self.days_lookback = days_lookback
        self.average_order_value = average_order_value
        self.min_impressions_threshold = min_impressions_threshold
        self.demographic_low_threshold = demographic_low_threshold
        self.demographic_high_threshold = demographic_high_threshold


class BigQueryAnalyzerViews:
    """Creates and manages BigQuery views that replicate Python analyzer logic."""

    def __init__(
        self,
        bigquery_exporter: BigQueryExporter,
        config: AnalyzerViewConfig | None = None,
    ):
        """Initialize with BigQuery exporter instance and optional configuration."""
        if not BIGQUERY_AVAILABLE:
            raise ImportError(
                "Google Cloud BigQuery is not installed. "
                "Install with: pip install google-cloud-bigquery"
            )
        self.exporter = bigquery_exporter
        self.config = config or AnalyzerViewConfig()
        self.client = None
        self.dataset_ref = None

    def _get_client(self) -> bigquery.Client:
        """Get BigQuery client from exporter."""
        if self.client is None:
            self.client = self.exporter._get_client()
        return self.client

    def _get_dataset_ref(self) -> bigquery.DatasetReference:
        """Get dataset reference from exporter."""
        if self.dataset_ref is None:
            self.dataset_ref = self.exporter._get_dataset_ref()
        return self.dataset_ref

    def validate_required_tables(self) -> Dict[str, bool]:
        """Validate that all required tables exist before creating views."""
        required_tables = [
            "search_terms",
            "keywords",
            "campaigns",
            "ad_groups",
            "geographic_performance",
            "negative_keywords",
            "demographics",
            "device_performance",
        ]

        validation_results = {}
        client = self._get_client()
        dataset_ref = self._get_dataset_ref()

        for table_name in required_tables:
            try:
                table_ref = dataset_ref.table(table_name)
                client.get_table(
                    table_ref
                )  # Will raise exception if table doesn't exist
                validation_results[table_name] = True
                logger.info(f"Table {table_name} exists and is accessible")
            except Exception as e:
                validation_results[table_name] = False
                logger.warning(f"Table {table_name} not found or not accessible: {e}")

        return validation_results

    def create_all_analyzer_views(self) -> Dict[str, bool]:
        """Create all analyzer views and return status for each."""
        # First validate required tables exist
        table_validation = self.validate_required_tables()
        missing_tables = [
            table for table, exists in table_validation.items() if not exists
        ]

        if missing_tables:
            logger.warning(
                f"Missing required tables: {missing_tables}. Some views may fail to create."
            )

        results = {}

        # Core analyzer views
        core_views = [
            (
                "analyzer_search_terms_recommendations",
                self._get_search_terms_recommendations_sql(),
            ),
            (
                "analyzer_keywords_bid_recommendations",
                self._get_keywords_bid_recommendations_sql(),
            ),
            (
                "analyzer_campaign_performance_insights",
                self._get_campaign_performance_insights_sql(),
            ),
            (
                "analyzer_ad_group_quality_scores",
                self._get_ad_group_quality_scores_sql(),
            ),
            ("analyzer_geographic_performance", self._get_geographic_performance_sql()),
        ]

        # Advanced analytics views
        advanced_views = [
            ("analyzer_local_intent_detection", self._get_local_intent_detection_sql()),
            (
                "analyzer_match_type_optimization",
                self._get_match_type_optimization_sql(),
            ),
            ("analyzer_quality_score_insights", self._get_quality_score_insights_sql()),
            (
                "analyzer_cost_efficiency_metrics",
                self._get_cost_efficiency_metrics_sql(),
            ),
            ("analyzer_performance_trends", self._get_performance_trends_sql()),
        ]

        # Complex algorithm views
        complex_views = [
            (
                "analyzer_negative_keyword_conflicts",
                self._get_negative_keyword_conflicts_sql(),
            ),
            (
                "analyzer_budget_allocation_recommendations",
                self._get_budget_allocation_recommendations_sql(),
            ),
            (
                "analyzer_demographic_performance_insights",
                self._get_demographic_performance_insights_sql(),
            ),
            (
                "analyzer_device_cross_performance",
                self._get_device_cross_performance_sql(),
            ),
            (
                "analyzer_seasonal_trend_detection",
                self._get_seasonal_trend_detection_sql(),
            ),
        ]

        # GA4 integration views
        ga4_views = [
            (
                "analyzer_ga4_session_attribution",
                self._get_ga4_session_attribution_sql(),
            ),
            (
                "analyzer_ga4_store_visit_performance",
                self._get_ga4_store_visit_performance_sql(),
            ),
            (
                "analyzer_ga4_revenue_attribution",
                self._get_ga4_revenue_attribution_sql(),
            ),
        ]

        all_views = core_views + advanced_views + complex_views + ga4_views

        for view_name, sql in all_views:
            try:
                results[view_name] = self._create_view(view_name, sql)
                logger.info(f"Successfully created view: {view_name}")
            except Exception as e:
                logger.error(f"Failed to create view {view_name}: {e}")
                results[view_name] = False

        return results

    def _substitute_sql_parameters(self, sql: str) -> str:
        """Safely substitute SQL parameters to prevent injection."""
        dataset_ref = self._get_dataset_ref()

        # Validate that project_id and dataset_id are safe (alphanumeric, hyphens, underscores only)
        import re

        project_pattern = r"^[a-zA-Z0-9\-_]+$"
        dataset_pattern = r"^[a-zA-Z0-9_]+$"

        if not re.match(project_pattern, dataset_ref.project):
            raise ValueError(f"Invalid project_id format: {dataset_ref.project}")
        if not re.match(dataset_pattern, dataset_ref.dataset_id):
            raise ValueError(f"Invalid dataset_id format: {dataset_ref.dataset_id}")

        # Safe substitution using string replacement (not format to avoid injection)
        substituted_sql = sql
        substituted_sql = substituted_sql.replace("{project_id}", dataset_ref.project)
        substituted_sql = substituted_sql.replace(
            "{dataset_id}", dataset_ref.dataset_id
        )

        return substituted_sql

    def _create_view(self, view_name: str, sql: str) -> bool:
        """Create or replace a view in BigQuery."""
        try:
            client = self._get_client()
            dataset_ref = self._get_dataset_ref()

            # Safely substitute SQL parameters
            substituted_sql = self._substitute_sql_parameters(sql)

            view_ref = dataset_ref.table(view_name)
            view = bigquery.Table(view_ref)
            view.view_query = substituted_sql

            # Create or replace the view
            client.create_table(view, exists_ok=True)
            logger.info(f"Created/updated view: {view_name}")
            return True

        except GoogleCloudError as e:
            logger.error(f"Failed to create view {view_name}: {e}")
            return False

    def drop_view(self, view_name: str) -> bool:
        """Drop a view from BigQuery."""
        try:
            client = self._get_client()
            dataset_ref = self._get_dataset_ref()
            view_ref = dataset_ref.table(view_name)

            client.delete_table(view_ref)
            logger.info(f"Dropped view: {view_name}")
            return True

        except GoogleCloudError as e:
            logger.error(f"Failed to drop view {view_name}: {e}")
            return False

    def validate_view_results(
        self, view_name: str, sample_size: int = 100
    ) -> Dict[str, Any]:
        """Validate view results by running a sample query."""
        try:
            client = self._get_client()
            dataset_ref = self._get_dataset_ref()

            query = f"""
            SELECT *
            FROM `{dataset_ref.project}.{dataset_ref.dataset_id}.{view_name}`
            LIMIT {sample_size}
            """

            query_job = client.query(query)
            results = query_job.result()

            row_count = sum(1 for _ in results)

            return {
                "success": True,
                "row_count": row_count,
                "view_name": view_name,
                "message": f"View validation successful. Retrieved {row_count} rows.",
            }

        except Exception as e:
            return {
                "success": False,
                "view_name": view_name,
                "error": str(e),
                "message": f"View validation failed: {e}",
            }

    # Core Analyzer View SQL Definitions

    def _get_search_terms_recommendations_sql(self) -> str:
        """SQL for search terms analyzer view."""
        return f"""
        SELECT
            search_term,
            campaign_name,
            ad_group_name,
            SUM(cost) as total_cost,
            SUM(conversions) as total_conversions,
            SUM(clicks) as total_clicks,
            SUM(impressions) as total_impressions,
            SAFE_DIVIDE(SUM(clicks), SUM(impressions)) * 100 as ctr_percent,
            SAFE_DIVIDE(SUM(cost), SUM(conversions)) as cost_per_conversion,

            -- Local intent scoring
            CASE
                WHEN REGEXP_CONTAINS(LOWER(search_term), r'\\b(near me|nearby|local|close to|around me)\\b') THEN 0.9
                WHEN REGEXP_CONTAINS(LOWER(search_term), r'\\b(in [a-z]+|[a-z]+ area|[a-z]+ store)\\b') THEN 0.7
                WHEN REGEXP_CONTAINS(LOWER(search_term), r'\\b(store|location|address|hours)\\b') THEN 0.5
                ELSE 0.2
            END as local_intent_score,

            -- Recommendation logic
            CASE
                WHEN SUM(conversions) = 0 AND SUM(cost) > {self.config.high_cost_threshold} THEN 'HIGH_PRIORITY_NEGATIVE'
                WHEN SUM(conversions) = 0 AND SUM(cost) > {self.config.low_cost_threshold} THEN 'CONSIDER_NEGATIVE'
                WHEN SAFE_DIVIDE(SUM(clicks), SUM(impressions)) < {self.config.low_ctr_threshold} AND SUM(impressions) > 1000 THEN 'LOW_CTR_NEGATIVE'
                WHEN SUM(conversions) > 0 AND SAFE_DIVIDE(SUM(cost), SUM(conversions)) > {self.config.high_cpa_threshold} THEN 'HIGH_CPA_REVIEW'
                WHEN REGEXP_CONTAINS(LOWER(search_term), r'\\b(near me|nearby|local)\\b') AND SUM(conversions) > 0 THEN 'HIGH_VALUE_LOCAL'
                ELSE 'KEEP_ACTIVE'
            END as recommendation_type,

            -- Estimated impact
            CASE
                WHEN SUM(conversions) = 0 AND SUM(cost) > {self.config.high_cost_threshold} THEN SUM(cost)
                WHEN SUM(conversions) = 0 AND SUM(cost) > {self.config.low_cost_threshold} THEN SUM(cost) * 0.8
                ELSE 0
            END as estimated_savings,

            COUNT(*) as data_points,
            CURRENT_TIMESTAMP() as analysis_timestamp

        FROM `{{project_id}}.{{dataset_id}}.search_terms`
        WHERE date >= DATE_SUB(CURRENT_DATE(), INTERVAL {self.config.days_lookback} DAY)
        GROUP BY search_term, campaign_name, ad_group_name
        HAVING SUM(impressions) > {self.config.min_impressions_threshold}  -- Filter out very low volume terms
        """

    def _get_keywords_bid_recommendations_sql(self) -> str:
        """SQL for keyword bid recommendations view."""
        return """
        SELECT
            keyword_text,
            keyword_match_type,
            campaign_name,
            ad_group_name,
            keyword_id,

            -- Performance metrics
            SUM(cost) as total_cost,
            SUM(conversions) as total_conversions,
            SUM(clicks) as total_clicks,
            SUM(impressions) as total_impressions,
            AVG(quality_score) as avg_quality_score,
            AVG(first_page_cpc) as avg_first_page_cpc,
            AVG(top_of_page_cpc) as avg_top_of_page_cpc,

            -- Calculated metrics
            SAFE_DIVIDE(SUM(clicks), SUM(impressions)) * 100 as ctr_percent,
            SAFE_DIVIDE(SUM(cost), SUM(clicks)) as avg_cpc,
            SAFE_DIVIDE(SUM(cost), SUM(conversions)) as cost_per_conversion,
            SAFE_DIVIDE(SUM(conversions), SUM(clicks)) * 100 as conversion_rate,

            -- Bid recommendation logic
            CASE
                WHEN AVG(impression_share) < 50 AND SUM(conversions) > 0 AND SAFE_DIVIDE(SUM(cost), SUM(conversions)) < 50 THEN 'INCREASE_BID'
                WHEN AVG(impression_share) > 90 AND SAFE_DIVIDE(SUM(cost), SUM(conversions)) > 100 THEN 'DECREASE_BID'
                WHEN SUM(conversions) = 0 AND SUM(cost) > 100 THEN 'PAUSE_KEYWORD'
                WHEN AVG(quality_score) < 5 AND SUM(impressions) > 1000 THEN 'IMPROVE_QUALITY'
                WHEN SAFE_DIVIDE(SUM(clicks), SUM(impressions)) < 0.01 AND SUM(impressions) > 1000 THEN 'REVIEW_RELEVANCE'
                ELSE 'MONITOR'
            END as bid_recommendation,

            -- Suggested bid adjustment
            CASE
                WHEN AVG(impression_share) < 50 AND SUM(conversions) > 0 THEN GREATEST(AVG(first_page_cpc) * 1.2, SAFE_DIVIDE(SUM(cost), SUM(clicks)) * 1.3)
                WHEN AVG(impression_share) > 90 AND SAFE_DIVIDE(SUM(cost), SUM(conversions)) > 100 THEN SAFE_DIVIDE(SUM(cost), SUM(clicks)) * 0.7
                ELSE SAFE_DIVIDE(SUM(cost), SUM(clicks))
            END as suggested_max_cpc,

            -- Priority scoring
            CASE
                WHEN SUM(conversions) = 0 AND SUM(cost) > 100 THEN 'HIGH'
                WHEN AVG(impression_share) < 30 AND SUM(conversions) > 2 THEN 'HIGH'
                WHEN AVG(quality_score) < 4 THEN 'MEDIUM'
                ELSE 'LOW'
            END as optimization_priority,

            CURRENT_TIMESTAMP() as analysis_timestamp

        FROM `{project_id}.{dataset_id}.keywords`
        WHERE date >= DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY)
        AND status = 'ENABLED'
        GROUP BY keyword_text, keyword_match_type, campaign_name, ad_group_name, keyword_id
        HAVING SUM(impressions) > 50  -- Filter out very low volume keywords
        """

    def _get_campaign_performance_insights_sql(self) -> str:
        """SQL for campaign performance insights view."""
        return """
        SELECT
            campaign_name,
            campaign_id,
            campaign_type,
            campaign_status,

            -- Performance aggregates
            SUM(cost) as total_cost,
            SUM(conversions) as total_conversions,
            SUM(clicks) as total_clicks,
            SUM(impressions) as total_impressions,

            -- Calculated metrics
            SAFE_DIVIDE(SUM(cost), SUM(conversions)) as cost_per_conversion,
            SAFE_DIVIDE(SUM(clicks), SUM(impressions)) * 100 as ctr_percent,
            SAFE_DIVIDE(SUM(conversions), SUM(clicks)) * 100 as conversion_rate,
            SAFE_DIVIDE(SUM(cost), SUM(clicks)) as avg_cpc,

            -- Budget utilization
            AVG(budget_amount) as avg_daily_budget,
            SAFE_DIVIDE(SUM(cost), (AVG(budget_amount) * 90)) * 100 as budget_utilization_percent,

            -- Performance categorization
            CASE
                WHEN SUM(conversions) > 50 AND SAFE_DIVIDE(SUM(cost), SUM(conversions)) < 30 THEN 'HIGH_PERFORMER'
                WHEN SUM(conversions) > 10 AND SAFE_DIVIDE(SUM(cost), SUM(conversions)) < 75 THEN 'GOOD_PERFORMER'
                WHEN SUM(conversions) > 0 AND SAFE_DIVIDE(SUM(cost), SUM(conversions)) < 150 THEN 'AVERAGE_PERFORMER'
                WHEN SUM(conversions) = 0 AND SUM(cost) > 500 THEN 'UNDERPERFORMER'
                ELSE 'MONITOR'
            END as performance_category,

            -- Optimization recommendations
            CASE
                WHEN SAFE_DIVIDE(SUM(cost), (AVG(budget_amount) * 90)) < 0.5 AND SUM(conversions) > 0 THEN 'INCREASE_BUDGET'
                WHEN SAFE_DIVIDE(SUM(cost), (AVG(budget_amount) * 90)) > 0.95 AND SAFE_DIVIDE(SUM(cost), SUM(conversions)) < 50 THEN 'BUDGET_CONSTRAINED'
                WHEN SUM(conversions) = 0 AND SUM(cost) > 500 THEN 'RESTRUCTURE_CAMPAIGN'
                WHEN SAFE_DIVIDE(SUM(clicks), SUM(impressions)) < 0.02 THEN 'IMPROVE_AD_RELEVANCE'
                ELSE 'OPTIMIZE_KEYWORDS'
            END as optimization_recommendation,

            -- Trend analysis (comparing to previous period)
            LAG(SUM(conversions), 1) OVER (PARTITION BY campaign_id ORDER BY DATE_TRUNC(date, MONTH)) as prev_month_conversions,
            LAG(SUM(cost), 1) OVER (PARTITION BY campaign_id ORDER BY DATE_TRUNC(date, MONTH)) as prev_month_cost,

            CURRENT_TIMESTAMP() as analysis_timestamp

        FROM `{project_id}.{dataset_id}.campaigns`
        WHERE date >= DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY)
        AND campaign_status = 'ENABLED'
        GROUP BY campaign_name, campaign_id, campaign_type, campaign_status
        HAVING SUM(impressions) > 100
        """

    def _get_ad_group_quality_scores_sql(self) -> str:
        """SQL for ad group quality scores view."""
        return """
        SELECT
            campaign_name,
            ad_group_name,
            ad_group_id,

            -- Quality metrics aggregates
            AVG(quality_score) as avg_quality_score,
            COUNT(CASE WHEN quality_score >= 7 THEN 1 END) as high_quality_keywords,
            COUNT(CASE WHEN quality_score <= 5 THEN 1 END) as low_quality_keywords,
            COUNT(*) as total_keywords,

            -- Performance metrics
            SUM(cost) as total_cost,
            SUM(conversions) as total_conversions,
            SUM(clicks) as total_clicks,
            SUM(impressions) as total_impressions,

            -- Quality distribution
            SAFE_DIVIDE(COUNT(CASE WHEN quality_score >= 7 THEN 1 END), COUNT(*)) * 100 as high_quality_percentage,
            SAFE_DIVIDE(COUNT(CASE WHEN quality_score <= 5 THEN 1 END), COUNT(*)) * 100 as low_quality_percentage,

            -- Historical trends
            AVG(expected_ctr) as avg_expected_ctr,
            AVG(ad_relevance) as avg_ad_relevance,
            AVG(landing_page_experience) as avg_landing_page_experience,

            -- Quality score categorization
            CASE
                WHEN AVG(quality_score) >= 8 THEN 'EXCELLENT'
                WHEN AVG(quality_score) >= 6 THEN 'GOOD'
                WHEN AVG(quality_score) >= 4 THEN 'AVERAGE'
                ELSE 'POOR'
            END as quality_category,

            -- Optimization recommendations
            CASE
                WHEN SAFE_DIVIDE(COUNT(CASE WHEN quality_score <= 5 THEN 1 END), COUNT(*)) > 0.5 THEN 'URGENT_QS_IMPROVEMENT'
                WHEN AVG(ad_relevance) < 3 THEN 'IMPROVE_AD_RELEVANCE'
                WHEN AVG(landing_page_experience) < 3 THEN 'IMPROVE_LANDING_PAGE'
                WHEN AVG(expected_ctr) < 3 THEN 'IMPROVE_AD_CTR'
                WHEN AVG(quality_score) < 6 THEN 'GENERAL_QS_IMPROVEMENT'
                ELSE 'MAINTAIN_QUALITY'
            END as quality_recommendation,

            -- Estimated impact of quality improvements
            CASE
                WHEN AVG(quality_score) < 5 THEN SUM(cost) * 0.3  -- 30% potential savings
                WHEN AVG(quality_score) < 7 THEN SUM(cost) * 0.15  -- 15% potential savings
                ELSE 0
            END as estimated_cost_savings,

            CURRENT_TIMESTAMP() as analysis_timestamp

        FROM `{project_id}.{dataset_id}.keywords`
        WHERE date >= DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY)
        AND status = 'ENABLED'
        AND quality_score IS NOT NULL
        GROUP BY campaign_name, ad_group_name, ad_group_id
        HAVING COUNT(*) >= 5  -- Only analyze ad groups with sufficient keywords
        """

    def _get_geographic_performance_sql(self) -> str:
        """SQL for geographic performance analysis view."""
        return """
        SELECT
            location_name,
            location_type,
            campaign_name,

            -- Performance metrics
            SUM(cost) as total_cost,
            SUM(conversions) as total_conversions,
            SUM(clicks) as total_clicks,
            SUM(impressions) as total_impressions,

            -- Calculated metrics
            SAFE_DIVIDE(SUM(cost), SUM(conversions)) as cost_per_conversion,
            SAFE_DIVIDE(SUM(clicks), SUM(impressions)) * 100 as ctr_percent,
            SAFE_DIVIDE(SUM(conversions), SUM(clicks)) * 100 as conversion_rate,

            -- Geographic performance scoring
            CASE
                WHEN SUM(conversions) >= 10 AND SAFE_DIVIDE(SUM(cost), SUM(conversions)) < 50 THEN 'HIGH_PERFORMER'
                WHEN SUM(conversions) >= 5 AND SAFE_DIVIDE(SUM(cost), SUM(conversions)) < 100 THEN 'GOOD_PERFORMER'
                WHEN SUM(conversions) > 0 AND SAFE_DIVIDE(SUM(cost), SUM(conversions)) < 200 THEN 'AVERAGE_PERFORMER'
                WHEN SUM(conversions) = 0 AND SUM(cost) > 200 THEN 'UNDERPERFORMER'
                ELSE 'INSUFFICIENT_DATA'
            END as performance_category,

            -- Bid adjustment recommendations
            CASE
                WHEN SUM(conversions) >= 10 AND SAFE_DIVIDE(SUM(cost), SUM(conversions)) < 30 THEN 'INCREASE_BID_20_PERCENT'
                WHEN SUM(conversions) >= 5 AND SAFE_DIVIDE(SUM(cost), SUM(conversions)) < 50 THEN 'INCREASE_BID_10_PERCENT'
                WHEN SAFE_DIVIDE(SUM(cost), SUM(conversions)) > 150 THEN 'DECREASE_BID_20_PERCENT'
                WHEN SUM(conversions) = 0 AND SUM(cost) > 200 THEN 'EXCLUDE_LOCATION'
                ELSE 'MAINTAIN_CURRENT_BID'
            END as bid_recommendation,

            -- Local intent analysis
            CASE
                WHEN location_type = 'City' AND SUM(conversions) > 0 THEN 'LOCAL_OPPORTUNITY'
                WHEN location_type = 'State' AND SUM(conversions) > 20 THEN 'EXPAND_LOCAL_TARGETING'
                ELSE 'STANDARD_TARGETING'
            END as local_strategy,

            -- Ranking within campaign
            RANK() OVER (PARTITION BY campaign_name ORDER BY SUM(conversions) DESC, SUM(cost) ASC) as conversion_rank,
            RANK() OVER (PARTITION BY campaign_name ORDER BY SAFE_DIVIDE(SUM(cost), SUM(conversions)) ASC) as efficiency_rank,

            CURRENT_TIMESTAMP() as analysis_timestamp

        FROM `{project_id}.{dataset_id}.geographic_performance`
        WHERE date >= DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY)
        GROUP BY location_name, location_type, campaign_name
        HAVING SUM(impressions) > 100
        """

    def _get_local_intent_detection_sql(self) -> str:
        """SQL for local intent detection view."""
        return """
        SELECT
            search_term,
            campaign_name,
            ad_group_name,

            -- Local intent signals
            CASE
                WHEN REGEXP_CONTAINS(LOWER(search_term), r'\\b(near me|nearby|close to|around me)\\b') THEN 'EXPLICIT_LOCAL'
                WHEN REGEXP_CONTAINS(LOWER(search_term), r'\\b(in [a-z]+|[a-z]+ area|local)\\b') THEN 'GEOGRAPHIC_LOCAL'
                WHEN REGEXP_CONTAINS(LOWER(search_term), r'\\b(store|location|address|hours|directions)\\b') THEN 'BUSINESS_LOCAL'
                WHEN REGEXP_CONTAINS(LOWER(search_term), r'\\b(delivery|pickup|open now)\\b') THEN 'SERVICE_LOCAL'
                ELSE 'NON_LOCAL'
            END as intent_category,

            -- Local intent scoring (0-1 scale)
            CASE
                WHEN REGEXP_CONTAINS(LOWER(search_term), r'\\b(near me|nearby)\\b') THEN 0.95
                WHEN REGEXP_CONTAINS(LOWER(search_term), r'\\b(local|close to|around me)\\b') THEN 0.85
                WHEN REGEXP_CONTAINS(LOWER(search_term), r'\\b(in [a-z]+|[a-z]+ area)\\b') THEN 0.75
                WHEN REGEXP_CONTAINS(LOWER(search_term), r'\\b(store|location|hours)\\b') THEN 0.65
                WHEN REGEXP_CONTAINS(LOWER(search_term), r'\\b(address|directions|open now)\\b') THEN 0.55
                WHEN REGEXP_CONTAINS(LOWER(search_term), r'\\b(delivery|pickup)\\b') THEN 0.45
                ELSE 0.1
            END as local_intent_score,

            -- Performance metrics
            SUM(cost) as total_cost,
            SUM(conversions) as total_conversions,
            SUM(clicks) as total_clicks,
            SUM(impressions) as total_impressions,

            -- Local performance analysis
            SAFE_DIVIDE(SUM(conversions), SUM(clicks)) * 100 as conversion_rate,
            SAFE_DIVIDE(SUM(cost), SUM(conversions)) as cost_per_conversion,

            -- Optimization recommendations
            CASE
                WHEN REGEXP_CONTAINS(LOWER(search_term), r'\\b(near me|nearby|local)\\b') AND SUM(conversions) > 0 THEN 'HIGH_VALUE_LOCAL_KEYWORD'
                WHEN REGEXP_CONTAINS(LOWER(search_term), r'\\b(store|location)\\b') AND SUM(conversions) = 0 AND SUM(cost) > 20 THEN 'REVIEW_LOCAL_TARGETING'
                WHEN REGEXP_CONTAINS(LOWER(search_term), r'\\b(delivery|pickup)\\b') AND SUM(conversions) > 0 THEN 'EXPAND_SERVICE_KEYWORDS'
                WHEN REGEXP_CONTAINS(LOWER(search_term), r'\\b(near me|nearby)\\b') AND SUM(impressions) < 100 THEN 'INCREASE_LOCAL_BIDS'
                ELSE 'STANDARD_OPTIMIZATION'
            END as local_optimization_recommendation,

            -- Geographic expansion opportunities
            CASE
                WHEN REGEXP_CONTAINS(LOWER(search_term), r'\\b(near me|nearby)\\b') AND SUM(conversions) > 2 THEN 'EXPAND_RADIUS_TARGETING'
                WHEN REGEXP_CONTAINS(LOWER(search_term), r'\\b(local|area)\\b') AND SUM(conversions) > 1 THEN 'ADD_SIMILAR_LOCATIONS'
                ELSE 'NO_EXPANSION_NEEDED'
            END as geographic_expansion_opportunity,

            COUNT(*) as data_points,
            CURRENT_TIMESTAMP() as analysis_timestamp

        FROM `{project_id}.{dataset_id}.search_terms`
        WHERE date >= DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY)
        GROUP BY search_term, campaign_name, ad_group_name
        HAVING SUM(impressions) > 10
        """

    def _get_match_type_optimization_sql(self) -> str:
        """SQL for match type optimization view."""
        return """
        WITH keyword_performance AS (
            SELECT
                keyword_text,
                keyword_match_type,
                campaign_name,
                ad_group_name,
                SUM(cost) as cost,
                SUM(conversions) as conversions,
                SUM(clicks) as clicks,
                SUM(impressions) as impressions,
                SAFE_DIVIDE(SUM(cost), SUM(conversions)) as cpa,
                SAFE_DIVIDE(SUM(clicks), SUM(impressions)) * 100 as ctr
            FROM `{project_id}.{dataset_id}.keywords`
            WHERE date >= DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY)
            AND status = 'ENABLED'
            GROUP BY keyword_text, keyword_match_type, campaign_name, ad_group_name
        ),
        match_type_comparison AS (
            SELECT
                keyword_text,
                campaign_name,
                ad_group_name,
                MAX(CASE WHEN keyword_match_type = 'EXACT' THEN cpa END) as exact_cpa,
                MAX(CASE WHEN keyword_match_type = 'PHRASE' THEN cpa END) as phrase_cpa,
                MAX(CASE WHEN keyword_match_type = 'BROAD' THEN cpa END) as broad_cpa,
                MAX(CASE WHEN keyword_match_type = 'EXACT' THEN conversions END) as exact_conversions,
                MAX(CASE WHEN keyword_match_type = 'PHRASE' THEN conversions END) as phrase_conversions,
                MAX(CASE WHEN keyword_match_type = 'BROAD' THEN conversions END) as broad_conversions,
                MAX(CASE WHEN keyword_match_type = 'EXACT' THEN ctr END) as exact_ctr,
                MAX(CASE WHEN keyword_match_type = 'PHRASE' THEN ctr END) as phrase_ctr,
                MAX(CASE WHEN keyword_match_type = 'BROAD' THEN ctr END) as broad_ctr
            FROM keyword_performance
            GROUP BY keyword_text, campaign_name, ad_group_name
        )
        SELECT
            kp.keyword_text,
            kp.keyword_match_type,
            kp.campaign_name,
            kp.ad_group_name,
            kp.cost,
            kp.conversions,
            kp.clicks,
            kp.impressions,
            kp.cpa,
            kp.ctr,

            -- Match type analysis
            CASE
                WHEN kp.keyword_match_type = 'BROAD' AND kp.conversions = 0 AND kp.cost > 50 THEN 'NARROW_TO_PHRASE'
                WHEN kp.keyword_match_type = 'PHRASE' AND kp.conversions = 0 AND kp.cost > 30 THEN 'NARROW_TO_EXACT'
                WHEN kp.keyword_match_type = 'EXACT' AND kp.conversions > 5 AND kp.cpa < 50 THEN 'EXPAND_TO_PHRASE'
                WHEN kp.keyword_match_type = 'PHRASE' AND kp.conversions > 10 AND kp.cpa < 75 THEN 'EXPAND_TO_BROAD'
                WHEN kp.keyword_match_type = 'BROAD' AND kp.ctr < 1 AND kp.impressions > 1000 THEN 'ADD_NEGATIVE_KEYWORDS'
                ELSE 'MAINTAIN_CURRENT'
            END as match_type_recommendation,

            -- Performance comparison with other match types
            mtc.exact_cpa,
            mtc.phrase_cpa,
            mtc.broad_cpa,
            mtc.exact_conversions,
            mtc.phrase_conversions,
            mtc.broad_conversions,

            -- Best performing match type for this keyword
            CASE
                WHEN mtc.exact_conversions > COALESCE(mtc.phrase_conversions, 0) AND mtc.exact_conversions > COALESCE(mtc.broad_conversions, 0) THEN 'EXACT'
                WHEN mtc.phrase_conversions > COALESCE(mtc.broad_conversions, 0) THEN 'PHRASE'
                WHEN mtc.broad_conversions > 0 THEN 'BROAD'
                ELSE 'INSUFFICIENT_DATA'
            END as best_performing_match_type,

            -- Optimization priority
            CASE
                WHEN kp.keyword_match_type = 'BROAD' AND kp.cost > 100 AND kp.conversions = 0 THEN 'HIGH'
                WHEN kp.keyword_match_type = 'PHRASE' AND kp.cost > 50 AND kp.conversions = 0 THEN 'HIGH'
                WHEN kp.ctr < 0.5 AND kp.impressions > 1000 THEN 'MEDIUM'
                WHEN kp.conversions > 0 AND kp.cpa > 100 THEN 'MEDIUM'
                ELSE 'LOW'
            END as optimization_priority,

            CURRENT_TIMESTAMP() as analysis_timestamp

        FROM keyword_performance kp
        LEFT JOIN match_type_comparison mtc
            ON kp.keyword_text = mtc.keyword_text
            AND kp.campaign_name = mtc.campaign_name
            AND kp.ad_group_name = mtc.ad_group_name
        WHERE kp.impressions > 50
        """

    def _get_quality_score_insights_sql(self) -> str:
        """SQL for quality score insights view."""
        return """
        SELECT
            keyword_text,
            keyword_match_type,
            campaign_name,
            ad_group_name,
            keyword_id,

            -- Quality metrics
            AVG(quality_score) as avg_quality_score,
            AVG(expected_ctr) as avg_expected_ctr,
            AVG(ad_relevance) as avg_ad_relevance,
            AVG(landing_page_experience) as avg_landing_page_experience,

            -- Performance metrics
            SUM(cost) as total_cost,
            SUM(conversions) as total_conversions,
            SUM(clicks) as total_clicks,
            SUM(impressions) as total_impressions,

            -- Historical quality trends
            LAG(AVG(quality_score), 1) OVER (PARTITION BY keyword_id ORDER BY DATE_TRUNC(date, MONTH)) as prev_month_quality_score,
            LAG(AVG(expected_ctr), 1) OVER (PARTITION BY keyword_id ORDER BY DATE_TRUNC(date, MONTH)) as prev_month_expected_ctr,

            -- Quality improvement opportunities
            CASE
                WHEN AVG(quality_score) < 5 THEN 'CRITICAL_IMPROVEMENT_NEEDED'
                WHEN AVG(quality_score) < 7 THEN 'IMPROVEMENT_RECOMMENDED'
                WHEN AVG(quality_score) >= 8 THEN 'EXCELLENT_QUALITY'
                ELSE 'GOOD_QUALITY'
            END as quality_status,

            -- Specific improvement recommendations
            CASE
                WHEN AVG(expected_ctr) < 3 THEN 'IMPROVE_AD_CTR'
                WHEN AVG(ad_relevance) < 3 THEN 'IMPROVE_AD_RELEVANCE'
                WHEN AVG(landing_page_experience) < 3 THEN 'IMPROVE_LANDING_PAGE'
                WHEN AVG(quality_score) < 5 THEN 'COMPREHENSIVE_OPTIMIZATION'
                ELSE 'MAINTAIN_QUALITY'
            END as improvement_focus,

            -- Impact estimation
            CASE
                WHEN AVG(quality_score) < 5 THEN SUM(cost) * 0.4  -- 40% potential CPC reduction
                WHEN AVG(quality_score) < 7 THEN SUM(cost) * 0.2  -- 20% potential CPC reduction
                ELSE 0
            END as estimated_cpc_savings,

            -- Quality score distribution
            COUNT(CASE WHEN quality_score = 10 THEN 1 END) as perfect_score_days,
            COUNT(CASE WHEN quality_score >= 7 THEN 1 END) as good_score_days,
            COUNT(CASE WHEN quality_score <= 5 THEN 1 END) as poor_score_days,
            COUNT(*) as total_days,

            CURRENT_TIMESTAMP() as analysis_timestamp

        FROM `{project_id}.{dataset_id}.keywords`
        WHERE date >= DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY)
        AND status = 'ENABLED'
        AND quality_score IS NOT NULL
        GROUP BY keyword_text, keyword_match_type, campaign_name, ad_group_name, keyword_id
        HAVING COUNT(*) >= 30  -- At least 30 days of data
        """

    def _get_cost_efficiency_metrics_sql(self) -> str:
        """SQL for cost efficiency metrics view with optimized window functions."""
        return f"""
        SELECT
            campaign_name,
            campaign_type,
            campaign_id,

            -- Cost metrics
            SUM(cost) as total_cost,
            SUM(conversions) as total_conversions,
            SUM(clicks) as total_clicks,
            SUM(impressions) as total_impressions,

            -- Efficiency metrics
            SAFE_DIVIDE(SUM(cost), SUM(conversions)) as cost_per_conversion,
            SAFE_DIVIDE(SUM(cost), SUM(clicks)) as cost_per_click,
            SAFE_DIVIDE(SUM(clicks), SUM(impressions)) * 100 as click_through_rate,
            SAFE_DIVIDE(SUM(conversions), SUM(clicks)) * 100 as conversion_rate,

            -- Benchmarking using window functions (more efficient than CROSS JOIN)
            PERCENTILE_CONT(SAFE_DIVIDE(cost, conversions), 0.50) OVER (PARTITION BY campaign_type) as industry_median_cpa,
            PERCENTILE_CONT(SAFE_DIVIDE(clicks, impressions), 0.50) OVER (PARTITION BY campaign_type) as industry_median_ctr,

            -- Efficiency scoring using window function benchmarks
            CASE
                WHEN SAFE_DIVIDE(SUM(cost), SUM(conversions)) <=
                    PERCENTILE_CONT(SAFE_DIVIDE(cost, conversions), 0.25) OVER (PARTITION BY campaign_type) THEN 'HIGHLY_EFFICIENT'
                WHEN SAFE_DIVIDE(SUM(cost), SUM(conversions)) <=
                    PERCENTILE_CONT(SAFE_DIVIDE(cost, conversions), 0.50) OVER (PARTITION BY campaign_type) THEN 'EFFICIENT'
                WHEN SAFE_DIVIDE(SUM(cost), SUM(conversions)) <=
                    PERCENTILE_CONT(SAFE_DIVIDE(cost, conversions), 0.75) OVER (PARTITION BY campaign_type) THEN 'AVERAGE_EFFICIENCY'
                ELSE 'INEFFICIENT'
            END as efficiency_category,

            -- Waste identification
            CASE
                WHEN SUM(conversions) = 0 AND SUM(cost) > {self.config.high_cost_threshold * 10} THEN SUM(cost)
                WHEN SAFE_DIVIDE(SUM(cost), SUM(conversions)) >
                    PERCENTILE_CONT(SAFE_DIVIDE(cost, conversions), 0.75) OVER (PARTITION BY campaign_type) * 2 THEN SUM(cost) * 0.5
                ELSE 0
            END as estimated_waste,

            -- Optimization potential
            CASE
                WHEN SAFE_DIVIDE(SUM(cost), SUM(conversions)) >
                    PERCENTILE_CONT(SAFE_DIVIDE(cost, conversions), 0.50) OVER (PARTITION BY campaign_type) * 1.5 THEN
                    (SAFE_DIVIDE(SUM(cost), SUM(conversions)) -
                     PERCENTILE_CONT(SAFE_DIVIDE(cost, conversions), 0.50) OVER (PARTITION BY campaign_type)) * SUM(conversions)
                ELSE 0
            END as potential_savings,

            -- ROI analysis using configurable AOV
            CASE
                WHEN SUM(conversions) > 0 THEN
                    ((SUM(conversions) * {self.config.average_order_value}) - SUM(cost)) / SUM(cost) * 100
                ELSE -100
            END as estimated_roi_percent,

            -- Efficiency recommendations
            CASE
                WHEN SUM(conversions) = 0 AND SUM(cost) > {self.config.high_cost_threshold * 10} THEN 'PAUSE_AND_RESTRUCTURE'
                WHEN SAFE_DIVIDE(SUM(cost), SUM(conversions)) >
                    PERCENTILE_CONT(SAFE_DIVIDE(cost, conversions), 0.75) OVER (PARTITION BY campaign_type) * 2 THEN 'MAJOR_OPTIMIZATION_NEEDED'
                WHEN SAFE_DIVIDE(SUM(cost), SUM(conversions)) >
                    PERCENTILE_CONT(SAFE_DIVIDE(cost, conversions), 0.50) OVER (PARTITION BY campaign_type) * 1.5 THEN 'OPTIMIZATION_OPPORTUNITY'
                WHEN SAFE_DIVIDE(SUM(cost), SUM(conversions)) <=
                    PERCENTILE_CONT(SAFE_DIVIDE(cost, conversions), 0.25) OVER (PARTITION BY campaign_type) THEN 'SCALE_UP_INVESTMENT'
                ELSE 'MAINTAIN_CURRENT_STRATEGY'
            END as efficiency_recommendation,

            CURRENT_TIMESTAMP() as analysis_timestamp

        FROM `{{project_id}}.{{dataset_id}}.campaigns`
        WHERE date >= DATE_SUB(CURRENT_DATE(), INTERVAL {self.config.days_lookback} DAY)
        AND campaign_status = 'ENABLED'
        AND conversions > 0  -- Only include campaigns with conversions for meaningful benchmarks
        GROUP BY campaign_name, campaign_type, campaign_id
        HAVING SUM(impressions) > {self.config.min_impressions_threshold * 10}  -- Higher threshold for campaign-level analysis
        """

    def _get_performance_trends_sql(self) -> str:
        """SQL for performance trends analysis view."""
        return """
        WITH weekly_metrics AS (
            SELECT
                campaign_name,
                DATE_TRUNC(date, WEEK) as week_start,
                SUM(cost) as weekly_cost,
                SUM(conversions) as weekly_conversions,
                SUM(clicks) as weekly_clicks,
                SUM(impressions) as weekly_impressions
            FROM `{project_id}.{dataset_id}.campaigns`
            WHERE date >= DATE_SUB(CURRENT_DATE(), INTERVAL 12 WEEK)
            GROUP BY campaign_name, DATE_TRUNC(date, WEEK)
        ),
        trend_analysis AS (
            SELECT
                campaign_name,
                week_start,
                weekly_cost,
                weekly_conversions,
                weekly_clicks,
                weekly_impressions,

                -- Calculate week-over-week changes
                LAG(weekly_cost, 1) OVER (PARTITION BY campaign_name ORDER BY week_start) as prev_week_cost,
                LAG(weekly_conversions, 1) OVER (PARTITION BY campaign_name ORDER BY week_start) as prev_week_conversions,

                -- Calculate moving averages
                AVG(weekly_cost) OVER (PARTITION BY campaign_name ORDER BY week_start ROWS BETWEEN 3 PRECEDING AND CURRENT ROW) as cost_moving_avg,
                AVG(weekly_conversions) OVER (PARTITION BY campaign_name ORDER BY week_start ROWS BETWEEN 3 PRECEDING AND CURRENT ROW) as conversions_moving_avg
            FROM weekly_metrics
        )
        SELECT
            campaign_name,
            week_start,
            weekly_cost,
            weekly_conversions,
            weekly_clicks,
            weekly_impressions,

            -- Week-over-week changes
            SAFE_DIVIDE((weekly_cost - prev_week_cost), prev_week_cost) * 100 as cost_change_percent,
            SAFE_DIVIDE((weekly_conversions - prev_week_conversions), prev_week_conversions) * 100 as conversions_change_percent,

            -- Trend classification
            CASE
                WHEN SAFE_DIVIDE((weekly_conversions - prev_week_conversions), prev_week_conversions) > 0.2 THEN 'STRONG_POSITIVE'
                WHEN SAFE_DIVIDE((weekly_conversions - prev_week_conversions), prev_week_conversions) > 0.1 THEN 'POSITIVE'
                WHEN SAFE_DIVIDE((weekly_conversions - prev_week_conversions), prev_week_conversions) > -0.1 THEN 'STABLE'
                WHEN SAFE_DIVIDE((weekly_conversions - prev_week_conversions), prev_week_conversions) > -0.2 THEN 'NEGATIVE'
                ELSE 'STRONG_NEGATIVE'
            END as conversion_trend,

            -- Efficiency trends
            CASE
                WHEN SAFE_DIVIDE(weekly_cost, weekly_conversions) < SAFE_DIVIDE(prev_week_cost, prev_week_conversions) * 0.9 THEN 'IMPROVING_EFFICIENCY'
                WHEN SAFE_DIVIDE(weekly_cost, weekly_conversions) > SAFE_DIVIDE(prev_week_cost, prev_week_conversions) * 1.1 THEN 'DECLINING_EFFICIENCY'
                ELSE 'STABLE_EFFICIENCY'
            END as efficiency_trend,

            -- Seasonality detection
            CASE
                WHEN weekly_conversions > conversions_moving_avg * 1.3 THEN 'SEASONAL_PEAK'
                WHEN weekly_conversions < conversions_moving_avg * 0.7 THEN 'SEASONAL_LOW'
                ELSE 'NORMAL_PATTERN'
            END as seasonality_indicator,

            -- Recommendations based on trends
            CASE
                WHEN SAFE_DIVIDE((weekly_conversions - prev_week_conversions), prev_week_conversions) < -0.3 THEN 'INVESTIGATE_DECLINE'
                WHEN SAFE_DIVIDE((weekly_conversions - prev_week_conversions), prev_week_conversions) > 0.3 THEN 'SCALE_UP_SUCCESSFUL_CAMPAIGN'
                WHEN SAFE_DIVIDE(weekly_cost, weekly_conversions) > SAFE_DIVIDE(prev_week_cost, prev_week_conversions) * 1.2 THEN 'OPTIMIZE_FOR_EFFICIENCY'
                ELSE 'MAINTAIN_CURRENT_STRATEGY'
            END as trend_recommendation,

            cost_moving_avg,
            conversions_moving_avg,
            CURRENT_TIMESTAMP() as analysis_timestamp

        FROM trend_analysis
        WHERE prev_week_cost IS NOT NULL  -- Exclude first week since no comparison
        ORDER BY campaign_name, week_start DESC
        """

    # Complex Algorithm Views

    def _get_negative_keyword_conflicts_sql(self) -> str:
        """SQL for negative keyword conflicts detection view."""
        return """
        WITH negative_keywords AS (
            SELECT DISTINCT
                campaign_name,
                ad_group_name,
                LOWER(TRIM(negative_keyword)) as negative_keyword,
                match_type as negative_match_type
            FROM `{project_id}.{dataset_id}.negative_keywords`
            WHERE status = 'ACTIVE'
        ),
        positive_keywords AS (
            SELECT DISTINCT
                campaign_name,
                ad_group_name,
                LOWER(TRIM(keyword_text)) as keyword_text,
                keyword_match_type,
                SUM(conversions) as total_conversions,
                SUM(cost) as total_cost
            FROM `{project_id}.{dataset_id}.keywords`
            WHERE date >= DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY)
            AND status = 'ENABLED'
            GROUP BY campaign_name, ad_group_name, keyword_text, keyword_match_type
        )
        SELECT
            pk.campaign_name,
            pk.ad_group_name,
            pk.keyword_text as positive_keyword,
            pk.keyword_match_type,
            nk.negative_keyword,
            nk.negative_match_type,
            pk.total_conversions,
            pk.total_cost,

            -- Conflict detection logic
            CASE
                WHEN nk.negative_match_type = 'EXACT' AND pk.keyword_text = nk.negative_keyword THEN 'EXACT_CONFLICT'
                WHEN nk.negative_match_type = 'PHRASE' AND REGEXP_CONTAINS(pk.keyword_text, CONCAT('\\\\b', REGEXP_REPLACE(nk.negative_keyword, r'\\s+', '\\\\s+'), '\\\\b')) THEN 'PHRASE_CONFLICT'
                WHEN nk.negative_match_type = 'BROAD' AND
                     (SELECT COUNT(*) FROM UNNEST(SPLIT(nk.negative_keyword, ' ')) AS neg_word
                      WHERE neg_word IN UNNEST(SPLIT(pk.keyword_text, ' '))) > 0 THEN 'BROAD_CONFLICT'
                ELSE 'NO_CONFLICT'
            END as conflict_type,

            -- Impact assessment
            CASE
                WHEN pk.total_conversions > 5 AND pk.total_cost / pk.total_conversions < 50 THEN 'HIGH_IMPACT'
                WHEN pk.total_conversions > 1 AND pk.total_cost / pk.total_conversions < 100 THEN 'MEDIUM_IMPACT'
                WHEN pk.total_conversions > 0 THEN 'LOW_IMPACT'
                ELSE 'MINIMAL_IMPACT'
            END as impact_level,

            -- Recommendations
            CASE
                WHEN pk.total_conversions > 5 AND pk.total_cost / pk.total_conversions < 50 THEN 'REMOVE_NEGATIVE_KEYWORD'
                WHEN pk.total_conversions > 1 AND pk.total_cost / pk.total_conversions < 100 THEN 'REVIEW_NEGATIVE_KEYWORD'
                WHEN pk.total_conversions = 0 AND pk.total_cost > 100 THEN 'KEEP_NEGATIVE_KEYWORD'
                ELSE 'MONITOR_PERFORMANCE'
            END as recommendation,

            -- Estimated revenue impact
            CASE
                WHEN pk.total_conversions > 0 THEN pk.total_conversions * 100  -- Assuming $100 AOV
                ELSE 0
            END as estimated_blocked_revenue,

            CURRENT_TIMESTAMP() as analysis_timestamp

        FROM positive_keywords pk
        INNER JOIN negative_keywords nk
            ON pk.campaign_name = nk.campaign_name
            AND (pk.ad_group_name = nk.ad_group_name OR nk.ad_group_name IS NULL)  -- Account for campaign-level negatives
        WHERE (
            (nk.negative_match_type = 'EXACT' AND pk.keyword_text = nk.negative_keyword) OR
            (nk.negative_match_type = 'PHRASE' AND REGEXP_CONTAINS(pk.keyword_text, CONCAT('\\\\b', REGEXP_REPLACE(nk.negative_keyword, r'\\s+', '\\\\s+'), '\\\\b'))) OR
            (nk.negative_match_type = 'BROAD' AND
             (SELECT COUNT(*) FROM UNNEST(SPLIT(nk.negative_keyword, ' ')) AS neg_word
              WHERE neg_word IN UNNEST(SPLIT(pk.keyword_text, ' '))) > 0)
        )
        ORDER BY pk.total_conversions DESC, pk.total_cost DESC
        """

    def _get_budget_allocation_recommendations_sql(self) -> str:
        """SQL for budget allocation recommendations view."""
        return """
        WITH campaign_performance AS (
            SELECT
                campaign_name,
                campaign_id,
                AVG(budget_amount) as daily_budget,
                SUM(cost) as total_cost,
                SUM(conversions) as total_conversions,
                SUM(clicks) as total_clicks,
                SUM(impressions) as total_impressions,
                SAFE_DIVIDE(SUM(cost), SUM(conversions)) as cost_per_conversion,
                SAFE_DIVIDE(SUM(cost), 90) as avg_daily_spend,
                MAX(cost) as max_daily_spend,
                SAFE_DIVIDE(SUM(cost), AVG(budget_amount) * 90) as budget_utilization
            FROM `{project_id}.{dataset_id}.campaigns`
            WHERE date >= DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY)
            AND campaign_status = 'ENABLED'
            GROUP BY campaign_name, campaign_id
        ),
        performance_ranking AS (
            SELECT
                *,
                RANK() OVER (ORDER BY total_conversions DESC) as conversion_rank,
                RANK() OVER (ORDER BY cost_per_conversion ASC) as efficiency_rank,
                RANK() OVER (ORDER BY budget_utilization DESC) as utilization_rank
            FROM campaign_performance
            WHERE total_conversions > 0
        )
        SELECT
            campaign_name,
            campaign_id,
            daily_budget,
            total_cost,
            total_conversions,
            cost_per_conversion,
            avg_daily_spend,
            budget_utilization,
            conversion_rank,
            efficiency_rank,

            -- Budget allocation scoring
            CASE
                WHEN conversion_rank <= 5 AND efficiency_rank <= 5 THEN 'HIGH_PRIORITY'
                WHEN conversion_rank <= 10 AND efficiency_rank <= 10 THEN 'MEDIUM_PRIORITY'
                WHEN total_conversions > 0 AND cost_per_conversion < 100 THEN 'MAINTAIN_BUDGET'
                ELSE 'LOW_PRIORITY'
            END as budget_priority,

            -- Budget recommendations
            CASE
                WHEN budget_utilization > 0.95 AND cost_per_conversion < 50 THEN 'INCREASE_BUDGET_50_PERCENT'
                WHEN budget_utilization > 0.85 AND cost_per_conversion < 75 THEN 'INCREASE_BUDGET_25_PERCENT'
                WHEN budget_utilization < 0.5 AND total_conversions > 5 THEN 'DECREASE_BUDGET_25_PERCENT'
                WHEN budget_utilization < 0.3 THEN 'DECREASE_BUDGET_50_PERCENT'
                WHEN total_conversions = 0 AND total_cost > 500 THEN 'PAUSE_CAMPAIGN'
                ELSE 'MAINTAIN_CURRENT_BUDGET'
            END as budget_recommendation,

            -- Optimal budget calculation
            CASE
                WHEN budget_utilization > 0.95 AND cost_per_conversion < 50 THEN daily_budget * 1.5
                WHEN budget_utilization > 0.85 AND cost_per_conversion < 75 THEN daily_budget * 1.25
                WHEN budget_utilization < 0.5 AND total_conversions > 5 THEN daily_budget * 0.75
                WHEN budget_utilization < 0.3 THEN daily_budget * 0.5
                ELSE daily_budget
            END as recommended_daily_budget,

            -- Budget reallocation potential
            CASE
                WHEN conversion_rank <= 5 AND budget_utilization > 0.9 THEN
                    LEAST(daily_budget * 0.5, 100)  -- Suggest additional budget up to $100
                WHEN conversion_rank > 20 AND budget_utilization < 0.5 THEN
                    daily_budget * 0.3  -- Suggest reducing budget by 30%
                ELSE 0
            END as budget_reallocation_amount,

            -- ROI-based budget optimization
            CASE
                WHEN total_conversions > 0 THEN
                    ((total_conversions * 100) - total_cost) / total_cost * 100  -- Assuming $100 AOV
                ELSE -100
            END as estimated_roi_percent,

            -- Monthly budget projection
            recommended_daily_budget * 30 as recommended_monthly_budget,

            CURRENT_TIMESTAMP() as analysis_timestamp

        FROM performance_ranking
        WHERE total_impressions > 1000  -- Filter out very low volume campaigns
        ORDER BY conversion_rank ASC, efficiency_rank ASC
        """

    def _get_demographic_performance_insights_sql(self) -> str:
        """SQL for demographic performance insights view."""
        return """
        SELECT
            campaign_name,
            age_range,
            gender,
            household_income,

            -- Performance metrics
            SUM(cost) as total_cost,
            SUM(conversions) as total_conversions,
            SUM(clicks) as total_clicks,
            SUM(impressions) as total_impressions,

            -- Calculated metrics
            SAFE_DIVIDE(SUM(cost), SUM(conversions)) as cost_per_conversion,
            SAFE_DIVIDE(SUM(clicks), SUM(impressions)) * 100 as ctr_percent,
            SAFE_DIVIDE(SUM(conversions), SUM(clicks)) * 100 as conversion_rate,

            -- Demographic performance scoring
            CASE
                WHEN SUM(conversions) >= 20 AND SAFE_DIVIDE(SUM(cost), SUM(conversions)) < 40 THEN 'HIGH_PERFORMER'
                WHEN SUM(conversions) >= 10 AND SAFE_DIVIDE(SUM(cost), SUM(conversions)) < 75 THEN 'GOOD_PERFORMER'
                WHEN SUM(conversions) >= 5 AND SAFE_DIVIDE(SUM(cost), SUM(conversions)) < 150 THEN 'AVERAGE_PERFORMER'
                WHEN SUM(conversions) = 0 AND SUM(cost) > 200 THEN 'UNDERPERFORMER'
                ELSE 'INSUFFICIENT_DATA'
            END as performance_category,

            -- Bid adjustment recommendations
            CASE
                WHEN SUM(conversions) >= 20 AND SAFE_DIVIDE(SUM(cost), SUM(conversions)) < 30 THEN 'INCREASE_BID_30_PERCENT'
                WHEN SUM(conversions) >= 10 AND SAFE_DIVIDE(SUM(cost), SUM(conversions)) < 50 THEN 'INCREASE_BID_15_PERCENT'
                WHEN SAFE_DIVIDE(SUM(cost), SUM(conversions)) > 150 THEN 'DECREASE_BID_25_PERCENT'
                WHEN SUM(conversions) = 0 AND SUM(cost) > 200 THEN 'EXCLUDE_DEMOGRAPHIC'
                ELSE 'MAINTAIN_CURRENT_BID'
            END as bid_adjustment_recommendation,

            -- Audience insights
            CASE
                WHEN age_range IN ('25-34', '35-44') AND SUM(conversions) > 10 THEN 'PRIME_AGE_DEMOGRAPHIC'
                WHEN gender = 'Female' AND SUM(conversions) > SUM(conversions) * 0.6 THEN 'FEMALE_SKEWED_PERFORMANCE'  -- This logic needs refinement in real implementation
                WHEN household_income = 'Top 10%' AND SUM(conversions) > 5 THEN 'HIGH_VALUE_AUDIENCE'
                ELSE 'STANDARD_DEMOGRAPHIC'
            END as audience_insight,

            -- Cross-demographic analysis
            RANK() OVER (PARTITION BY campaign_name ORDER BY SUM(conversions) DESC) as conversion_rank_within_campaign,
            RANK() OVER (PARTITION BY campaign_name ORDER BY SAFE_DIVIDE(SUM(cost), SUM(conversions)) ASC) as efficiency_rank_within_campaign,

            -- Market share opportunity
            CASE
                WHEN SAFE_DIVIDE(SUM(impressions), (SELECT SUM(impressions) FROM `{project_id}.{dataset_id}.demographics` WHERE campaign_name = d.campaign_name)) < 0.1
                     AND SUM(conversions) > 0 THEN 'UNDERUTILIZED_SEGMENT'
                WHEN SAFE_DIVIDE(SUM(impressions), (SELECT SUM(impressions) FROM `{project_id}.{dataset_id}.demographics` WHERE campaign_name = d.campaign_name)) > 0.4
                     AND SUM(conversions) = 0 THEN 'OVERSATURATED_SEGMENT'
                ELSE 'BALANCED_SEGMENT'
            END as market_share_analysis,

            CURRENT_TIMESTAMP() as analysis_timestamp

        FROM `{project_id}.{dataset_id}.demographics` d
        WHERE date >= DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY)
        GROUP BY campaign_name, age_range, gender, household_income
        HAVING SUM(impressions) > 500  -- Filter out very low volume segments
        """

    def _get_device_cross_performance_sql(self) -> str:
        """SQL for device cross-performance analysis view."""
        return """
        WITH device_performance AS (
            SELECT
                campaign_name,
                device,
                SUM(cost) as device_cost,
                SUM(conversions) as device_conversions,
                SUM(clicks) as device_clicks,
                SUM(impressions) as device_impressions,
                SAFE_DIVIDE(SUM(cost), SUM(conversions)) as device_cpa,
                SAFE_DIVIDE(SUM(clicks), SUM(impressions)) * 100 as device_ctr,
                SAFE_DIVIDE(SUM(conversions), SUM(clicks)) * 100 as device_conversion_rate
            FROM `{project_id}.{dataset_id}.device_performance`
            WHERE date >= DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY)
            GROUP BY campaign_name, device
        ),
        campaign_totals AS (
            SELECT
                campaign_name,
                SUM(device_cost) as total_campaign_cost,
                SUM(device_conversions) as total_campaign_conversions,
                AVG(device_cpa) as avg_campaign_cpa
            FROM device_performance
            WHERE device_conversions > 0
            GROUP BY campaign_name
        )
        SELECT
            dp.campaign_name,
            dp.device,
            dp.device_cost,
            dp.device_conversions,
            dp.device_clicks,
            dp.device_impressions,
            dp.device_cpa,
            dp.device_ctr,
            dp.device_conversion_rate,

            -- Device share analysis
            SAFE_DIVIDE(dp.device_cost, ct.total_campaign_cost) * 100 as cost_share_percent,
            SAFE_DIVIDE(dp.device_conversions, ct.total_campaign_conversions) * 100 as conversion_share_percent,

            -- Cross-device performance comparison
            CASE
                WHEN dp.device_cpa < ct.avg_campaign_cpa * 0.8 THEN 'OUTPERFORMING_DEVICE'
                WHEN dp.device_cpa > ct.avg_campaign_cpa * 1.2 THEN 'UNDERPERFORMING_DEVICE'
                ELSE 'AVERAGE_PERFORMING_DEVICE'
            END as device_performance_category,

            -- Device-specific optimization recommendations
            CASE
                WHEN dp.device = 'Mobile' AND dp.device_conversion_rate < 2 THEN 'OPTIMIZE_MOBILE_EXPERIENCE'
                WHEN dp.device = 'Desktop' AND dp.device_cpa > ct.avg_campaign_cpa * 1.5 THEN 'REDUCE_DESKTOP_BIDS'
                WHEN dp.device = 'Tablet' AND dp.device_conversions = 0 AND dp.device_cost > 100 THEN 'EXCLUDE_TABLET'
                WHEN dp.device_cpa < ct.avg_campaign_cpa * 0.7 AND dp.device_conversions > 5 THEN 'INCREASE_DEVICE_BIDS'
                ELSE 'MONITOR_DEVICE_PERFORMANCE'
            END as device_recommendation,

            -- Bid adjustment suggestions
            CASE
                WHEN dp.device_cpa < ct.avg_campaign_cpa * 0.7 THEN 25  -- Increase bids by 25%
                WHEN dp.device_cpa < ct.avg_campaign_cpa * 0.8 THEN 15  -- Increase bids by 15%
                WHEN dp.device_cpa > ct.avg_campaign_cpa * 1.3 THEN -30 -- Decrease bids by 30%
                WHEN dp.device_cpa > ct.avg_campaign_cpa * 1.2 THEN -15 -- Decrease bids by 15%
                ELSE 0  -- No adjustment
            END as suggested_bid_adjustment_percent,

            -- Device trend analysis
            CASE
                WHEN dp.device = 'Mobile' AND SAFE_DIVIDE(dp.device_conversions, ct.total_campaign_conversions) > 0.6 THEN 'MOBILE_DOMINANT'
                WHEN dp.device = 'Desktop' AND SAFE_DIVIDE(dp.device_conversions, ct.total_campaign_conversions) > 0.5 THEN 'DESKTOP_DOMINANT'
                WHEN SAFE_DIVIDE(dp.device_conversions, ct.total_campaign_conversions) < 0.1 THEN 'MINOR_DEVICE_CONTRIBUTOR'
                ELSE 'BALANCED_DEVICE_PERFORMANCE'
            END as device_behavior_pattern,

            -- ROI by device
            CASE
                WHEN dp.device_conversions > 0 THEN
                    ((dp.device_conversions * 100) - dp.device_cost) / dp.device_cost * 100  -- Assuming $100 AOV
                ELSE -100
            END as device_roi_percent,

            ct.avg_campaign_cpa,
            CURRENT_TIMESTAMP() as analysis_timestamp

        FROM device_performance dp
        JOIN campaign_totals ct ON dp.campaign_name = ct.campaign_name
        WHERE dp.device_impressions > 100  -- Filter out very low volume devices
        ORDER BY dp.campaign_name, dp.device_conversions DESC
        """

    def _get_seasonal_trend_detection_sql(self) -> str:
        """SQL for seasonal trend detection view."""
        return """
        WITH daily_metrics AS (
            SELECT
                DATE(date) as analysis_date,
                EXTRACT(MONTH FROM date) as month_number,
                EXTRACT(DAYOFWEEK FROM date) as day_of_week,
                EXTRACT(WEEK FROM date) as week_number,
                campaign_name,
                SUM(cost) as daily_cost,
                SUM(conversions) as daily_conversions,
                SUM(clicks) as daily_clicks,
                SUM(impressions) as daily_impressions
            FROM `{project_id}.{dataset_id}.campaigns`
            WHERE date >= DATE_SUB(CURRENT_DATE(), INTERVAL 365 DAY)  -- Full year of data
            GROUP BY date, campaign_name
        ),
        moving_averages AS (
            SELECT
                *,
                AVG(daily_conversions) OVER (PARTITION BY campaign_name ORDER BY analysis_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) as weekly_avg_conversions,
                AVG(daily_cost) OVER (PARTITION BY campaign_name ORDER BY analysis_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) as weekly_avg_cost,
                AVG(daily_conversions) OVER (PARTITION BY campaign_name ORDER BY analysis_date ROWS BETWEEN 29 PRECEDING AND CURRENT ROW) as monthly_avg_conversions
            FROM daily_metrics
        ),
        seasonal_patterns AS (
            SELECT
                campaign_name,
                month_number,
                day_of_week,
                AVG(daily_conversions) as avg_monthly_conversions,
                AVG(daily_cost) as avg_monthly_cost,
                STDDEV(daily_conversions) as conversion_volatility,
                COUNT(*) as data_points
            FROM daily_metrics
            WHERE analysis_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 365 DAY)
            GROUP BY campaign_name, month_number, day_of_week
        )
        SELECT
            ma.campaign_name,
            ma.analysis_date,
            ma.month_number,
            ma.day_of_week,
            ma.daily_conversions,
            ma.daily_cost,
            ma.weekly_avg_conversions,
            ma.monthly_avg_conversions,

            -- Seasonal indicators
            CASE
                WHEN ma.daily_conversions > ma.monthly_avg_conversions * 1.5 THEN 'PEAK_PERFORMANCE'
                WHEN ma.daily_conversions < ma.monthly_avg_conversions * 0.5 THEN 'LOW_PERFORMANCE'
                WHEN ma.daily_conversions > ma.weekly_avg_conversions * 1.2 THEN 'ABOVE_AVERAGE'
                WHEN ma.daily_conversions < ma.weekly_avg_conversions * 0.8 THEN 'BELOW_AVERAGE'
                ELSE 'NORMAL_PERFORMANCE'
            END as performance_indicator,

            -- Day of week patterns
            CASE
                WHEN ma.day_of_week IN (2, 3, 4, 5) AND ma.daily_conversions > ma.weekly_avg_conversions * 1.1 THEN 'WEEKDAY_STRONG'
                WHEN ma.day_of_week IN (1, 7) AND ma.daily_conversions > ma.weekly_avg_conversions * 1.1 THEN 'WEEKEND_STRONG'
                WHEN ma.day_of_week IN (2, 3, 4, 5) AND ma.daily_conversions < ma.weekly_avg_conversions * 0.9 THEN 'WEEKDAY_WEAK'
                WHEN ma.day_of_week IN (1, 7) AND ma.daily_conversions < ma.weekly_avg_conversions * 0.9 THEN 'WEEKEND_WEAK'
                ELSE 'CONSISTENT_PATTERN'
            END as day_of_week_pattern,

            -- Monthly seasonal trends
            CASE
                WHEN ma.month_number IN (11, 12, 1) AND ma.daily_conversions > ma.monthly_avg_conversions * 1.2 THEN 'HOLIDAY_BOOST'
                WHEN ma.month_number IN (6, 7, 8) AND ma.daily_conversions < ma.monthly_avg_conversions * 0.8 THEN 'SUMMER_SLOWDOWN'
                WHEN ma.month_number IN (1, 2) AND ma.daily_conversions < ma.monthly_avg_conversions * 0.9 THEN 'POST_HOLIDAY_DIP'
                WHEN ma.month_number IN (9, 10) AND ma.daily_conversions > ma.monthly_avg_conversions * 1.1 THEN 'BACK_TO_SCHOOL_BOOST'
                ELSE 'STABLE_MONTHLY_PATTERN'
            END as monthly_seasonal_pattern,

            -- Volatility assessment
            sp.conversion_volatility,
            CASE
                WHEN sp.conversion_volatility > ma.monthly_avg_conversions * 0.5 THEN 'HIGH_VOLATILITY'
                WHEN sp.conversion_volatility > ma.monthly_avg_conversions * 0.25 THEN 'MEDIUM_VOLATILITY'
                ELSE 'LOW_VOLATILITY'
            END as volatility_level,

            -- Optimization recommendations based on seasonal patterns
            CASE
                WHEN ma.month_number IN (11, 12) AND ma.daily_conversions > ma.monthly_avg_conversions * 1.2 THEN 'INCREASE_HOLIDAY_BUDGET'
                WHEN ma.day_of_week IN (1, 7) AND ma.daily_conversions < ma.weekly_avg_conversions * 0.8 THEN 'REDUCE_WEEKEND_BIDS'
                WHEN ma.day_of_week IN (2, 3, 4, 5) AND ma.daily_conversions > ma.weekly_avg_conversions * 1.1 THEN 'INCREASE_WEEKDAY_BIDS'
                WHEN ma.month_number IN (6, 7, 8) AND ma.daily_conversions < ma.monthly_avg_conversions * 0.8 THEN 'SUMMER_BUDGET_REDUCTION'
                ELSE 'MAINTAIN_CURRENT_STRATEGY'
            END as seasonal_recommendation,

            -- Year-over-year comparison (if available)
            LAG(ma.daily_conversions, 365) OVER (PARTITION BY ma.campaign_name ORDER BY ma.analysis_date) as same_day_last_year_conversions,

            CURRENT_TIMESTAMP() as analysis_timestamp

        FROM moving_averages ma
        JOIN seasonal_patterns sp
            ON ma.campaign_name = sp.campaign_name
            AND ma.month_number = sp.month_number
            AND ma.day_of_week = sp.day_of_week
        WHERE ma.analysis_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY)  -- Focus on recent 90 days
        ORDER BY ma.campaign_name, ma.analysis_date DESC
        """

    # GA4 Integration Views

    def _get_ga4_session_attribution_sql(self) -> str:
        """SQL for GA4 session attribution view combining Google Ads and GA4 data."""
        return """
        WITH google_ads_clicks AS (
          SELECT
            ad_id,
            campaign_name,
            ad_group_name,
            keyword_text,
            gclid,
            date as click_date,
            cost,
            clicks,
            impressions,
            conversions as ads_conversions
          FROM `{project_id}.{dataset_id}.analytics_data`
          WHERE date >= DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY)
            AND gclid IS NOT NULL
        ),
        ga4_sessions AS (
          SELECT
            session_id,
            gclid,
            ga4_user_id,
            event_timestamp,
            session_engaged,
            engagement_time_msec,
            first_visit,
            bounce_rate,
            landing_page,
            country,
            region,
            city,
            device_category
          FROM `{project_id}.{dataset_id}.analytics_data`
          WHERE date >= DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY)
            AND session_id IS NOT NULL
            AND gclid IS NOT NULL
        )
        SELECT
          gac.campaign_name,
          gac.ad_group_name,
          gac.keyword_text,
          gac.gclid,
          gac.click_date,
          gac.cost as ads_cost,
          gac.clicks as ads_clicks,
          gac.impressions,
          gac.ads_conversions,

          -- GA4 session metrics
          COUNT(DISTINCT gas.session_id) as ga4_sessions,
          COUNT(DISTINCT CASE WHEN gas.session_engaged THEN gas.session_id END) as engaged_sessions,
          COUNT(DISTINCT CASE WHEN gas.first_visit THEN gas.session_id END) as new_user_sessions,
          AVG(gas.engagement_time_msec) / 1000 as avg_engagement_time_seconds,
          AVG(gas.bounce_rate) as avg_bounce_rate,

          -- Session quality metrics
          SAFE_DIVIDE(COUNT(DISTINCT CASE WHEN gas.session_engaged THEN gas.session_id END), COUNT(DISTINCT gas.session_id)) * 100 as session_engagement_rate,
          SAFE_DIVIDE(COUNT(DISTINCT CASE WHEN gas.first_visit THEN gas.session_id END), COUNT(DISTINCT gas.session_id)) * 100 as new_user_rate,

          -- Geographic and device insights
          STRING_AGG(DISTINCT gas.country ORDER BY gas.country LIMIT 3) as top_countries,
          STRING_AGG(DISTINCT gas.device_category ORDER BY gas.device_category LIMIT 3) as device_types,
          STRING_AGG(DISTINCT gas.landing_page ORDER BY gas.landing_page LIMIT 1) as primary_landing_page,

          -- Attribution quality score
          CASE
            WHEN COUNT(DISTINCT gas.session_id) >= gac.clicks * 0.8 THEN 'HIGH_ATTRIBUTION_QUALITY'
            WHEN COUNT(DISTINCT gas.session_id) >= gac.clicks * 0.5 THEN 'MEDIUM_ATTRIBUTION_QUALITY'
            WHEN COUNT(DISTINCT gas.session_id) > 0 THEN 'LOW_ATTRIBUTION_QUALITY'
            ELSE 'NO_GA4_DATA'
          END as attribution_quality,

          -- Session performance insights
          CASE
            WHEN AVG(gas.engagement_time_msec) > 30000 AND AVG(gas.bounce_rate) < 40 THEN 'HIGH_QUALITY_TRAFFIC'
            WHEN AVG(gas.engagement_time_msec) > 15000 AND AVG(gas.bounce_rate) < 60 THEN 'MEDIUM_QUALITY_TRAFFIC'
            WHEN AVG(gas.engagement_time_msec) > 5000 THEN 'LOW_QUALITY_TRAFFIC'
            ELSE 'VERY_LOW_QUALITY_TRAFFIC'
          END as traffic_quality_assessment,

          CURRENT_TIMESTAMP() as analysis_timestamp

        FROM google_ads_clicks gac
        LEFT JOIN ga4_sessions gas ON gac.gclid = gas.gclid
        WHERE gac.gclid IS NOT NULL
        GROUP BY
          gac.campaign_name, gac.ad_group_name, gac.keyword_text,
          gac.gclid, gac.click_date, gac.cost, gac.clicks, gac.impressions, gac.ads_conversions
        HAVING COUNT(DISTINCT gas.session_id) > 0  -- Only include rows with GA4 data
        ORDER BY gac.cost DESC, COUNT(DISTINCT gas.session_id) DESC
        """

    def _get_ga4_store_visit_performance_sql(self) -> str:
        """SQL for GA4 store visit performance view."""
        return """
        WITH store_visit_data AS (
          SELECT
            gclid,
            session_id,
            ga4_user_id,
            store_location_id,
            distance_to_store,
            store_visit_converted,
            event_timestamp,
            country,
            region,
            city
          FROM `{project_id}.{dataset_id}.analytics_data`
          WHERE date >= DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY)
            AND store_location_id IS NOT NULL
            AND gclid IS NOT NULL
        ),
        google_ads_geo AS (
          SELECT
            campaign_name,
            ad_group_name,
            gclid,
            cost,
            clicks,
            conversions as ads_conversions,
            location_name
          FROM `{project_id}.{dataset_id}.analytics_data`
          WHERE date >= DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY)
            AND gclid IS NOT NULL
        )
        SELECT
          gag.campaign_name,
          gag.location_name as ads_location,
          svd.store_location_id,
          svd.country,
          svd.region,
          svd.city,

          -- Campaign performance metrics
          SUM(gag.cost) as total_cost,
          SUM(gag.clicks) as total_clicks,
          SUM(gag.ads_conversions) as ads_conversions,

          -- Store visit metrics
          COUNT(DISTINCT svd.session_id) as total_store_visits,
          COUNT(DISTINCT CASE WHEN svd.store_visit_converted THEN svd.session_id END) as converted_store_visits,
          AVG(svd.distance_to_store) as avg_distance_to_store_km,

          -- Performance calculations
          SAFE_DIVIDE(COUNT(DISTINCT svd.session_id), SUM(gag.clicks)) * 100 as store_visit_rate,
          SAFE_DIVIDE(COUNT(DISTINCT CASE WHEN svd.store_visit_converted THEN svd.session_id END), COUNT(DISTINCT svd.session_id)) * 100 as store_conversion_rate,
          SAFE_DIVIDE(SUM(gag.cost), COUNT(DISTINCT svd.session_id)) as cost_per_store_visit,
          SAFE_DIVIDE(SUM(gag.cost), COUNT(DISTINCT CASE WHEN svd.store_visit_converted THEN svd.session_id END)) as cost_per_store_conversion,

          -- Store performance categorization
          CASE
            WHEN COUNT(DISTINCT CASE WHEN svd.store_visit_converted THEN svd.session_id END) >= 10
                 AND SAFE_DIVIDE(SUM(gag.cost), COUNT(DISTINCT CASE WHEN svd.store_visit_converted THEN svd.session_id END)) < 50 THEN 'HIGH_PERFORMING_STORE'
            WHEN COUNT(DISTINCT CASE WHEN svd.store_visit_converted THEN svd.session_id END) >= 5
                 AND SAFE_DIVIDE(SUM(gag.cost), COUNT(DISTINCT CASE WHEN svd.store_visit_converted THEN svd.session_id END)) < 100 THEN 'GOOD_PERFORMING_STORE'
            WHEN COUNT(DISTINCT svd.session_id) >= 10
                 AND SAFE_DIVIDE(COUNT(DISTINCT CASE WHEN svd.store_visit_converted THEN svd.session_id END), COUNT(DISTINCT svd.session_id)) > 0.1 THEN 'AVERAGE_PERFORMING_STORE'
            WHEN COUNT(DISTINCT svd.session_id) > 0 THEN 'LOW_PERFORMING_STORE'
            ELSE 'NO_STORE_VISITS'
          END as store_performance_category,

          -- Distance analysis
          CASE
            WHEN AVG(svd.distance_to_store) < 5 THEN 'HYPERLOCAL_TRAFFIC'
            WHEN AVG(svd.distance_to_store) < 15 THEN 'LOCAL_TRAFFIC'
            WHEN AVG(svd.distance_to_store) < 50 THEN 'REGIONAL_TRAFFIC'
            ELSE 'DISTANT_TRAFFIC'
          END as traffic_proximity_category,

          -- Optimization recommendations
          CASE
            WHEN SAFE_DIVIDE(COUNT(DISTINCT svd.session_id), SUM(gag.clicks)) > 0.2
                 AND SAFE_DIVIDE(COUNT(DISTINCT CASE WHEN svd.store_visit_converted THEN svd.session_id END), COUNT(DISTINCT svd.session_id)) > 0.15 THEN 'INCREASE_LOCAL_BUDGET'
            WHEN AVG(svd.distance_to_store) > 25
                 AND SAFE_DIVIDE(COUNT(DISTINCT CASE WHEN svd.store_visit_converted THEN svd.session_id END), COUNT(DISTINCT svd.session_id)) < 0.05 THEN 'TIGHTEN_RADIUS_TARGETING'
            WHEN COUNT(DISTINCT svd.session_id) = 0 THEN 'IMPROVE_LOCAL_TARGETING'
            WHEN SAFE_DIVIDE(COUNT(DISTINCT CASE WHEN svd.store_visit_converted THEN svd.session_id END), COUNT(DISTINCT svd.session_id)) < 0.05 THEN 'OPTIMIZE_STORE_EXPERIENCE'
            ELSE 'MAINTAIN_CURRENT_STRATEGY'
          END as store_optimization_recommendation,

          CURRENT_TIMESTAMP() as analysis_timestamp

        FROM google_ads_geo gag
        LEFT JOIN store_visit_data svd ON gag.gclid = svd.gclid
        GROUP BY
          gag.campaign_name, gag.location_name, svd.store_location_id,
          svd.country, svd.region, svd.city
        HAVING SUM(gag.clicks) > 10  -- Minimum traffic threshold
        ORDER BY total_cost DESC, total_store_visits DESC
        """

    def _get_ga4_revenue_attribution_sql(self) -> str:
        """SQL for GA4 revenue attribution comparison view."""
        return """
        WITH ads_revenue AS (
          SELECT
            campaign_name,
            ad_group_name,
            gclid,
            date,
            cost,
            conversions as ads_conversions,
            conversion_value as ads_conversion_value
          FROM `{project_id}.{dataset_id}.analytics_data`
          WHERE date >= DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY)
            AND gclid IS NOT NULL
            AND conversions > 0
        ),
        ga4_revenue AS (
          SELECT
            gclid,
            transaction_id,
            ga4_user_id,
            item_revenue_usd,
            item_purchase_quantity,
            attribution_model,
            event_timestamp
          FROM `{project_id}.{dataset_id}.analytics_data`
          WHERE date >= DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY)
            AND gclid IS NOT NULL
            AND transaction_id IS NOT NULL
            AND item_revenue_usd > 0
        )
        SELECT
          ar.campaign_name,
          ar.ad_group_name,
          ar.gclid,
          ar.date,
          ar.cost,
          ar.ads_conversions,
          ar.ads_conversion_value,

          -- GA4 revenue metrics by attribution model
          COUNT(DISTINCT CASE WHEN gr.attribution_model = 'last_click' THEN gr.transaction_id END) as ga4_last_click_transactions,
          SUM(CASE WHEN gr.attribution_model = 'last_click' THEN gr.item_revenue_usd END) as ga4_last_click_revenue,
          COUNT(DISTINCT CASE WHEN gr.attribution_model = 'first_click' THEN gr.transaction_id END) as ga4_first_click_transactions,
          SUM(CASE WHEN gr.attribution_model = 'first_click' THEN gr.item_revenue_usd END) as ga4_first_click_revenue,
          COUNT(DISTINCT CASE WHEN gr.attribution_model = 'linear' THEN gr.transaction_id END) as ga4_linear_transactions,
          SUM(CASE WHEN gr.attribution_model = 'linear' THEN gr.item_revenue_usd END) as ga4_linear_revenue,

          -- Revenue comparison and attribution analysis
          SAFE_DIVIDE(SUM(CASE WHEN gr.attribution_model = 'last_click' THEN gr.item_revenue_usd END), ar.cost) as ga4_last_click_roas,
          SAFE_DIVIDE(SUM(CASE WHEN gr.attribution_model = 'first_click' THEN gr.item_revenue_usd END), ar.cost) as ga4_first_click_roas,
          SAFE_DIVIDE(SUM(CASE WHEN gr.attribution_model = 'linear' THEN gr.item_revenue_usd END), ar.cost) as ga4_linear_roas,
          SAFE_DIVIDE(ar.ads_conversion_value, ar.cost) as ads_roas,

          -- Attribution model comparison
          CASE
            WHEN SUM(CASE WHEN gr.attribution_model = 'last_click' THEN gr.item_revenue_usd END) > ar.ads_conversion_value * 1.2 THEN 'GA4_SHOWS_HIGHER_VALUE'
            WHEN SUM(CASE WHEN gr.attribution_model = 'last_click' THEN gr.item_revenue_usd END) < ar.ads_conversion_value * 0.8 THEN 'ADS_SHOWS_HIGHER_VALUE'
            WHEN ABS(SUM(CASE WHEN gr.attribution_model = 'last_click' THEN gr.item_revenue_usd END) - ar.ads_conversion_value) / ar.ads_conversion_value < 0.2 THEN 'ATTRIBUTION_ALIGNED'
            ELSE 'ATTRIBUTION_UNCLEAR'
          END as attribution_comparison,

          -- Data quality assessment
          CASE
            WHEN COUNT(DISTINCT gr.transaction_id) = 0 THEN 'NO_GA4_DATA'
            WHEN COUNT(DISTINCT gr.transaction_id) >= ar.ads_conversions * 0.8 THEN 'HIGH_DATA_QUALITY'
            WHEN COUNT(DISTINCT gr.transaction_id) >= ar.ads_conversions * 0.5 THEN 'MEDIUM_DATA_QUALITY'
            ELSE 'LOW_DATA_QUALITY'
          END as data_quality_assessment,

          -- Blended attribution metrics
          (
            COALESCE(SUM(CASE WHEN gr.attribution_model = 'last_click' THEN gr.item_revenue_usd END), 0) +
            COALESCE(SUM(CASE WHEN gr.attribution_model = 'first_click' THEN gr.item_revenue_usd END), 0) +
            COALESCE(SUM(CASE WHEN gr.attribution_model = 'linear' THEN gr.item_revenue_usd END), 0)
          ) / 3 as blended_ga4_revenue,

          -- Optimization insights
          CASE
            WHEN SUM(CASE WHEN gr.attribution_model = 'linear' THEN gr.item_revenue_usd END) > SUM(CASE WHEN gr.attribution_model = 'last_click' THEN gr.item_revenue_usd END) * 1.3 THEN 'STRONG_ASSIST_VALUE'
            WHEN SUM(CASE WHEN gr.attribution_model = 'first_click' THEN gr.item_revenue_usd END) > SUM(CASE WHEN gr.attribution_model = 'last_click' THEN gr.item_revenue_usd END) * 1.2 THEN 'HIGH_AWARENESS_VALUE'
            WHEN COUNT(DISTINCT gr.transaction_id) > ar.ads_conversions THEN 'GA4_CAPTURES_MORE_VALUE'
            ELSE 'STANDARD_ATTRIBUTION'
          END as attribution_insight,

          CURRENT_TIMESTAMP() as analysis_timestamp

        FROM ads_revenue ar
        LEFT JOIN ga4_revenue gr ON ar.gclid = gr.gclid
        GROUP BY
          ar.campaign_name, ar.ad_group_name, ar.gclid, ar.date,
          ar.cost, ar.ads_conversions, ar.ads_conversion_value
        HAVING ar.cost > 10  -- Minimum cost threshold
        ORDER BY ar.cost DESC, blended_ga4_revenue DESC
        """
