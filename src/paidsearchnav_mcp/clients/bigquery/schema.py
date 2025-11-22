"""Comprehensive BigQuery table schemas for all analyzer data.

This module defines optimized BigQuery schemas for all 20+ analyzers with:
- Date partitioning for cost optimization
- Customer ID clustering for query performance
- Proper data types for storage efficiency
- Support for real-time streaming inserts
"""

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class BigQueryTableSchema:
    """Defines comprehensive BigQuery table schemas for all analyzer data.

    Implements Google BigQuery best practices:
    - Date partitioning on 'date' field for cost optimization
    - Customer ID clustering for query performance
    - Proper field types and descriptions
    - Support for both streaming and batch inserts
    """

    @staticmethod
    def get_search_terms_schema():
        """Schema for search terms analyzer data."""
        try:
            from google.cloud import bigquery

            return [
                bigquery.SchemaField(
                    "date",
                    "DATE",
                    mode="REQUIRED",
                    description="Date of the search term performance",
                ),
                bigquery.SchemaField(
                    "customer_id",
                    "STRING",
                    mode="REQUIRED",
                    description="Google Ads customer ID",
                ),
                bigquery.SchemaField(
                    "campaign_id", "STRING", mode="REQUIRED", description="Campaign ID"
                ),
                bigquery.SchemaField(
                    "campaign_name",
                    "STRING",
                    mode="REQUIRED",
                    description="Campaign name",
                ),
                bigquery.SchemaField(
                    "ad_group_id", "STRING", mode="REQUIRED", description="Ad group ID"
                ),
                bigquery.SchemaField(
                    "ad_group_name",
                    "STRING",
                    mode="REQUIRED",
                    description="Ad group name",
                ),
                bigquery.SchemaField(
                    "search_term",
                    "STRING",
                    mode="REQUIRED",
                    description="User search query",
                ),
                bigquery.SchemaField(
                    "match_type",
                    "STRING",
                    mode="NULLABLE",
                    description="Keyword match type that triggered ad",
                ),
                bigquery.SchemaField(
                    "impressions",
                    "INTEGER",
                    mode="REQUIRED",
                    description="Number of impressions",
                ),
                bigquery.SchemaField(
                    "clicks", "INTEGER", mode="REQUIRED", description="Number of clicks"
                ),
                bigquery.SchemaField(
                    "cost",
                    "FLOAT",
                    mode="REQUIRED",
                    description="Cost in account currency",
                ),
                bigquery.SchemaField(
                    "conversions",
                    "FLOAT",
                    mode="REQUIRED",
                    description="Number of conversions",
                ),
                bigquery.SchemaField(
                    "ctr", "FLOAT", mode="NULLABLE", description="Click-through rate"
                ),
                bigquery.SchemaField(
                    "cpc", "FLOAT", mode="NULLABLE", description="Cost per click"
                ),
                bigquery.SchemaField(
                    "local_intent_score",
                    "FLOAT",
                    mode="NULLABLE",
                    description="Local intent score (0-1)",
                ),
                bigquery.SchemaField(
                    "quality_score",
                    "FLOAT",
                    mode="NULLABLE",
                    description="Search term quality score (0-100)",
                ),
                bigquery.SchemaField(
                    "negative_recommendation",
                    "STRING",
                    mode="NULLABLE",
                    description="Negative keyword recommendation",
                ),
                bigquery.SchemaField(
                    "created_at",
                    "TIMESTAMP",
                    mode="REQUIRED",
                    description="Record creation timestamp",
                ),
                bigquery.SchemaField(
                    "updated_at",
                    "TIMESTAMP",
                    mode="REQUIRED",
                    description="Record update timestamp",
                ),
            ]
        except ImportError:
            logger.warning(
                "Google Cloud BigQuery library not available, returning placeholder schema"
            )
            return []

    @staticmethod
    def get_keywords_schema():
        """Schema for keywords analyzer data."""
        try:
            from google.cloud import bigquery

            return [
                bigquery.SchemaField(
                    "date",
                    "DATE",
                    mode="REQUIRED",
                    description="Date of the keyword performance",
                ),
                bigquery.SchemaField(
                    "customer_id",
                    "STRING",
                    mode="REQUIRED",
                    description="Google Ads customer ID",
                ),
                bigquery.SchemaField(
                    "campaign_id", "STRING", mode="REQUIRED", description="Campaign ID"
                ),
                bigquery.SchemaField(
                    "campaign_name",
                    "STRING",
                    mode="REQUIRED",
                    description="Campaign name",
                ),
                bigquery.SchemaField(
                    "ad_group_id", "STRING", mode="REQUIRED", description="Ad group ID"
                ),
                bigquery.SchemaField(
                    "ad_group_name",
                    "STRING",
                    mode="REQUIRED",
                    description="Ad group name",
                ),
                bigquery.SchemaField(
                    "keyword_id",
                    "STRING",
                    mode="REQUIRED",
                    description="Unique identifier for the keyword",
                ),
                bigquery.SchemaField(
                    "keyword_text",
                    "STRING",
                    mode="REQUIRED",
                    description="Keyword text",
                ),
                bigquery.SchemaField(
                    "match_type",
                    "STRING",
                    mode="REQUIRED",
                    description="Keyword match type",
                ),
                bigquery.SchemaField(
                    "impressions",
                    "INTEGER",
                    mode="REQUIRED",
                    description="Number of impressions",
                ),
                bigquery.SchemaField(
                    "clicks", "INTEGER", mode="REQUIRED", description="Number of clicks"
                ),
                bigquery.SchemaField(
                    "cost",
                    "FLOAT",
                    mode="REQUIRED",
                    description="Cost in account currency",
                ),
                bigquery.SchemaField(
                    "conversions",
                    "FLOAT",
                    mode="REQUIRED",
                    description="Number of conversions",
                ),
                bigquery.SchemaField(
                    "ctr", "FLOAT", mode="NULLABLE", description="Click-through rate"
                ),
                bigquery.SchemaField(
                    "cpc", "FLOAT", mode="NULLABLE", description="Cost per click"
                ),
                bigquery.SchemaField(
                    "quality_score",
                    "INTEGER",
                    mode="NULLABLE",
                    description="Google Ads quality score",
                ),
                bigquery.SchemaField(
                    "bid_recommendation",
                    "STRING",
                    mode="NULLABLE",
                    description="Bid adjustment recommendation",
                ),
                bigquery.SchemaField(
                    "local_relevance",
                    "BOOLEAN",
                    mode="NULLABLE",
                    description="Has local relevance",
                ),
                bigquery.SchemaField(
                    "performance_tier",
                    "STRING",
                    mode="NULLABLE",
                    description="Performance tier classification",
                ),
                bigquery.SchemaField(
                    "created_at",
                    "TIMESTAMP",
                    mode="REQUIRED",
                    description="Record creation timestamp",
                ),
                bigquery.SchemaField(
                    "updated_at",
                    "TIMESTAMP",
                    mode="REQUIRED",
                    description="Record update timestamp",
                ),
            ]
        except ImportError:
            logger.warning(
                "Google Cloud BigQuery library not available, returning placeholder schema"
            )
            return []

    @staticmethod
    def get_campaigns_schema():
        """Schema for campaigns analyzer data."""
        try:
            from google.cloud import bigquery

            return [
                bigquery.SchemaField(
                    "date",
                    "DATE",
                    mode="REQUIRED",
                    description="Date of the campaign performance",
                ),
                bigquery.SchemaField(
                    "customer_id",
                    "STRING",
                    mode="REQUIRED",
                    description="Google Ads customer ID",
                ),
                bigquery.SchemaField(
                    "campaign_id", "STRING", mode="REQUIRED", description="Campaign ID"
                ),
                bigquery.SchemaField(
                    "campaign_name",
                    "STRING",
                    mode="REQUIRED",
                    description="Campaign name",
                ),
                bigquery.SchemaField(
                    "campaign_type",
                    "STRING",
                    mode="REQUIRED",
                    description="Campaign type: SEARCH, DISPLAY, VIDEO, SHOPPING, etc.",
                ),
                bigquery.SchemaField(
                    "campaign_status",
                    "STRING",
                    mode="REQUIRED",
                    description="Campaign status: ENABLED, PAUSED, REMOVED",
                ),
                bigquery.SchemaField(
                    "budget_amount",
                    "FLOAT",
                    mode="NULLABLE",
                    description="Daily budget amount in account currency",
                ),
                bigquery.SchemaField(
                    "impressions",
                    "INTEGER",
                    mode="REQUIRED",
                    description="Number of impressions",
                ),
                bigquery.SchemaField(
                    "clicks", "INTEGER", mode="REQUIRED", description="Number of clicks"
                ),
                bigquery.SchemaField(
                    "cost",
                    "FLOAT",
                    mode="REQUIRED",
                    description="Cost in account currency",
                ),
                bigquery.SchemaField(
                    "conversions",
                    "FLOAT",
                    mode="REQUIRED",
                    description="Number of conversions",
                ),
                bigquery.SchemaField(
                    "ctr", "FLOAT", mode="NULLABLE", description="Click-through rate"
                ),
                bigquery.SchemaField(
                    "cpc", "FLOAT", mode="NULLABLE", description="Cost per click"
                ),
                bigquery.SchemaField(
                    "performance_score",
                    "FLOAT",
                    mode="NULLABLE",
                    description="Campaign performance score",
                ),
                bigquery.SchemaField(
                    "optimization_recommendations",
                    "STRING",
                    mode="NULLABLE",
                    description="Optimization recommendations for the campaign",
                ),
                bigquery.SchemaField(
                    "created_at",
                    "TIMESTAMP",
                    mode="REQUIRED",
                    description="Record creation timestamp",
                ),
                bigquery.SchemaField(
                    "updated_at",
                    "TIMESTAMP",
                    mode="REQUIRED",
                    description="Record update timestamp",
                ),
            ]
        except ImportError:
            return []

    @staticmethod
    def get_ad_groups_schema():
        """Schema for ad groups analyzer data."""
        try:
            from google.cloud import bigquery

            return [
                bigquery.SchemaField(
                    "date",
                    "DATE",
                    mode="REQUIRED",
                    description="Date of the ad group performance",
                ),
                bigquery.SchemaField(
                    "customer_id",
                    "STRING",
                    mode="REQUIRED",
                    description="Google Ads customer ID",
                ),
                bigquery.SchemaField(
                    "campaign_id", "STRING", mode="REQUIRED", description="Campaign ID"
                ),
                bigquery.SchemaField(
                    "campaign_name",
                    "STRING",
                    mode="REQUIRED",
                    description="Campaign name",
                ),
                bigquery.SchemaField(
                    "ad_group_id", "STRING", mode="REQUIRED", description="Ad group ID"
                ),
                bigquery.SchemaField(
                    "ad_group_name",
                    "STRING",
                    mode="REQUIRED",
                    description="Ad group name",
                ),
                bigquery.SchemaField(
                    "ad_group_status",
                    "STRING",
                    mode="REQUIRED",
                    description="Ad group status",
                ),
                bigquery.SchemaField(
                    "ad_group_type",
                    "STRING",
                    mode="NULLABLE",
                    description="Ad group type",
                ),
                bigquery.SchemaField(
                    "impressions",
                    "INTEGER",
                    mode="REQUIRED",
                    description="Number of impressions",
                ),
                bigquery.SchemaField(
                    "clicks", "INTEGER", mode="REQUIRED", description="Number of clicks"
                ),
                bigquery.SchemaField(
                    "cost",
                    "FLOAT",
                    mode="REQUIRED",
                    description="Cost in account currency",
                ),
                bigquery.SchemaField(
                    "conversions",
                    "FLOAT",
                    mode="REQUIRED",
                    description="Number of conversions",
                ),
                bigquery.SchemaField(
                    "ctr", "FLOAT", mode="NULLABLE", description="Click-through rate"
                ),
                bigquery.SchemaField(
                    "cpc", "FLOAT", mode="NULLABLE", description="Cost per click"
                ),
                bigquery.SchemaField(
                    "quality_score",
                    "FLOAT",
                    mode="NULLABLE",
                    description="Average quality score",
                ),
                bigquery.SchemaField(
                    "optimization_score",
                    "FLOAT",
                    mode="NULLABLE",
                    description="Ad group optimization score",
                ),
                bigquery.SchemaField(
                    "optimization_recommendations",
                    "STRING",
                    mode="NULLABLE",
                    description="Optimization recommendations",
                ),
                bigquery.SchemaField(
                    "created_at",
                    "TIMESTAMP",
                    mode="REQUIRED",
                    description="Record creation timestamp",
                ),
                bigquery.SchemaField(
                    "updated_at",
                    "TIMESTAMP",
                    mode="REQUIRED",
                    description="Record update timestamp",
                ),
            ]
        except ImportError:
            logger.warning(
                "Google Cloud BigQuery library not available, returning placeholder schema"
            )
            return []

    @staticmethod
    def get_demographics_schema():
        """Schema for demographics analyzer data."""
        try:
            from google.cloud import bigquery

            return [
                bigquery.SchemaField(
                    "date",
                    "DATE",
                    mode="REQUIRED",
                    description="Date of the demographic performance",
                ),
                bigquery.SchemaField(
                    "customer_id",
                    "STRING",
                    mode="REQUIRED",
                    description="Google Ads customer ID",
                ),
                bigquery.SchemaField(
                    "campaign_id", "STRING", mode="REQUIRED", description="Campaign ID"
                ),
                bigquery.SchemaField(
                    "campaign_name",
                    "STRING",
                    mode="REQUIRED",
                    description="Campaign name",
                ),
                bigquery.SchemaField(
                    "ad_group_id", "STRING", mode="REQUIRED", description="Ad group ID"
                ),
                bigquery.SchemaField(
                    "ad_group_name",
                    "STRING",
                    mode="REQUIRED",
                    description="Ad group name",
                ),
                bigquery.SchemaField(
                    "demographic_type",
                    "STRING",
                    mode="REQUIRED",
                    description="Type: AGE_RANGE, GENDER, HOUSEHOLD_INCOME, PARENTAL_STATUS",
                ),
                bigquery.SchemaField(
                    "demographic_value",
                    "STRING",
                    mode="REQUIRED",
                    description="Specific demographic value",
                ),
                bigquery.SchemaField(
                    "impressions",
                    "INTEGER",
                    mode="REQUIRED",
                    description="Number of impressions",
                ),
                bigquery.SchemaField(
                    "clicks", "INTEGER", mode="REQUIRED", description="Number of clicks"
                ),
                bigquery.SchemaField(
                    "cost",
                    "FLOAT",
                    mode="REQUIRED",
                    description="Cost in account currency",
                ),
                bigquery.SchemaField(
                    "conversions",
                    "FLOAT",
                    mode="REQUIRED",
                    description="Number of conversions",
                ),
                bigquery.SchemaField(
                    "ctr", "FLOAT", mode="NULLABLE", description="Click-through rate"
                ),
                bigquery.SchemaField(
                    "cpc", "FLOAT", mode="NULLABLE", description="Cost per click"
                ),
                bigquery.SchemaField(
                    "conversion_rate",
                    "FLOAT",
                    mode="NULLABLE",
                    description="Conversion rate",
                ),
                bigquery.SchemaField(
                    "performance_score",
                    "FLOAT",
                    mode="NULLABLE",
                    description="Demographic performance score",
                ),
                bigquery.SchemaField(
                    "performance_tier",
                    "STRING",
                    mode="NULLABLE",
                    description="HIGH_PERFORMER, MODERATE_PERFORMER, LOW_PERFORMER",
                ),
                bigquery.SchemaField(
                    "bid_adjustment_recommendation",
                    "FLOAT",
                    mode="NULLABLE",
                    description="Recommended bid adjustment",
                ),
                bigquery.SchemaField(
                    "created_at",
                    "TIMESTAMP",
                    mode="REQUIRED",
                    description="Record creation timestamp",
                ),
                bigquery.SchemaField(
                    "updated_at",
                    "TIMESTAMP",
                    mode="REQUIRED",
                    description="Record update timestamp",
                ),
            ]
        except ImportError:
            logger.warning(
                "Google Cloud BigQuery library not available, returning placeholder schema"
            )
            return []

    @staticmethod
    def get_device_performance_schema():
        """Schema for device performance analyzer data."""
        try:
            from google.cloud import bigquery

            return [
                bigquery.SchemaField(
                    "date",
                    "DATE",
                    mode="REQUIRED",
                    description="Date of the device performance",
                ),
                bigquery.SchemaField(
                    "customer_id",
                    "STRING",
                    mode="REQUIRED",
                    description="Google Ads customer ID",
                ),
                bigquery.SchemaField(
                    "campaign_id", "STRING", mode="REQUIRED", description="Campaign ID"
                ),
                bigquery.SchemaField(
                    "campaign_name",
                    "STRING",
                    mode="REQUIRED",
                    description="Campaign name",
                ),
                bigquery.SchemaField(
                    "ad_group_id", "STRING", mode="NULLABLE", description="Ad group ID"
                ),
                bigquery.SchemaField(
                    "ad_group_name",
                    "STRING",
                    mode="NULLABLE",
                    description="Ad group name",
                ),
                bigquery.SchemaField(
                    "device_type",
                    "STRING",
                    mode="REQUIRED",
                    description="MOBILE, DESKTOP, TABLET",
                ),
                bigquery.SchemaField(
                    "impressions",
                    "INTEGER",
                    mode="REQUIRED",
                    description="Number of impressions",
                ),
                bigquery.SchemaField(
                    "clicks", "INTEGER", mode="REQUIRED", description="Number of clicks"
                ),
                bigquery.SchemaField(
                    "cost",
                    "FLOAT",
                    mode="REQUIRED",
                    description="Cost in account currency",
                ),
                bigquery.SchemaField(
                    "conversions",
                    "FLOAT",
                    mode="REQUIRED",
                    description="Number of conversions",
                ),
                bigquery.SchemaField(
                    "ctr", "FLOAT", mode="NULLABLE", description="Click-through rate"
                ),
                bigquery.SchemaField(
                    "cpc", "FLOAT", mode="NULLABLE", description="Cost per click"
                ),
                bigquery.SchemaField(
                    "conversion_rate",
                    "FLOAT",
                    mode="NULLABLE",
                    description="Conversion rate",
                ),
                bigquery.SchemaField(
                    "device_share_impressions",
                    "FLOAT",
                    mode="NULLABLE",
                    description="Device share of impressions (%)",
                ),
                bigquery.SchemaField(
                    "device_share_clicks",
                    "FLOAT",
                    mode="NULLABLE",
                    description="Device share of clicks (%)",
                ),
                bigquery.SchemaField(
                    "performance_score",
                    "FLOAT",
                    mode="NULLABLE",
                    description="Device performance score",
                ),
                bigquery.SchemaField(
                    "bid_adjustment_recommendation",
                    "FLOAT",
                    mode="NULLABLE",
                    description="Recommended bid adjustment",
                ),
                bigquery.SchemaField(
                    "created_at",
                    "TIMESTAMP",
                    mode="REQUIRED",
                    description="Record creation timestamp",
                ),
                bigquery.SchemaField(
                    "updated_at",
                    "TIMESTAMP",
                    mode="REQUIRED",
                    description="Record update timestamp",
                ),
            ]
        except ImportError:
            logger.warning(
                "Google Cloud BigQuery library not available, returning placeholder schema"
            )
            return []

    @staticmethod
    def get_geo_performance_schema():
        """Schema for geographic performance analyzer data."""
        try:
            from google.cloud import bigquery

            return [
                bigquery.SchemaField(
                    "date",
                    "DATE",
                    mode="REQUIRED",
                    description="Date of the geographic performance",
                ),
                bigquery.SchemaField(
                    "customer_id",
                    "STRING",
                    mode="REQUIRED",
                    description="Google Ads customer ID",
                ),
                bigquery.SchemaField(
                    "campaign_id", "STRING", mode="REQUIRED", description="Campaign ID"
                ),
                bigquery.SchemaField(
                    "campaign_name",
                    "STRING",
                    mode="REQUIRED",
                    description="Campaign name",
                ),
                bigquery.SchemaField(
                    "location_type",
                    "STRING",
                    mode="REQUIRED",
                    description="PHYSICAL_LOCATION, INTEREST_LOCATION",
                ),
                bigquery.SchemaField(
                    "location_name",
                    "STRING",
                    mode="REQUIRED",
                    description="Geographic location name",
                ),
                bigquery.SchemaField(
                    "location_id",
                    "STRING",
                    mode="NULLABLE",
                    description="Google location criteria ID",
                ),
                bigquery.SchemaField(
                    "location_level",
                    "STRING",
                    mode="NULLABLE",
                    description="COUNTRY, STATE, CITY, POSTAL_CODE",
                ),
                bigquery.SchemaField(
                    "impressions",
                    "INTEGER",
                    mode="REQUIRED",
                    description="Number of impressions",
                ),
                bigquery.SchemaField(
                    "clicks", "INTEGER", mode="REQUIRED", description="Number of clicks"
                ),
                bigquery.SchemaField(
                    "cost",
                    "FLOAT",
                    mode="REQUIRED",
                    description="Cost in account currency",
                ),
                bigquery.SchemaField(
                    "conversions",
                    "FLOAT",
                    mode="REQUIRED",
                    description="Number of conversions",
                ),
                bigquery.SchemaField(
                    "ctr", "FLOAT", mode="NULLABLE", description="Click-through rate"
                ),
                bigquery.SchemaField(
                    "cpc", "FLOAT", mode="NULLABLE", description="Cost per click"
                ),
                bigquery.SchemaField(
                    "conversion_rate",
                    "FLOAT",
                    mode="NULLABLE",
                    description="Conversion rate",
                ),
                bigquery.SchemaField(
                    "local_intent_score",
                    "FLOAT",
                    mode="NULLABLE",
                    description="Local intent score (0-1)",
                ),
                bigquery.SchemaField(
                    "distance_from_business",
                    "FLOAT",
                    mode="NULLABLE",
                    description="Distance in miles from business location",
                ),
                bigquery.SchemaField(
                    "performance_tier",
                    "STRING",
                    mode="NULLABLE",
                    description="HIGH_PERFORMER, MODERATE_PERFORMER, LOW_PERFORMER",
                ),
                bigquery.SchemaField(
                    "bid_adjustment_recommendation",
                    "FLOAT",
                    mode="NULLABLE",
                    description="Recommended location bid adjustment",
                ),
                bigquery.SchemaField(
                    "created_at",
                    "TIMESTAMP",
                    mode="REQUIRED",
                    description="Record creation timestamp",
                ),
                bigquery.SchemaField(
                    "updated_at",
                    "TIMESTAMP",
                    mode="REQUIRED",
                    description="Record update timestamp",
                ),
            ]
        except ImportError:
            logger.warning(
                "Google Cloud BigQuery library not available, returning placeholder schema"
            )
            return []

    @staticmethod
    def get_landing_page_schema():
        """Schema for landing page analyzer data."""
        try:
            from google.cloud import bigquery

            return [
                bigquery.SchemaField(
                    "date",
                    "DATE",
                    mode="REQUIRED",
                    description="Date of the landing page performance",
                ),
                bigquery.SchemaField(
                    "customer_id",
                    "STRING",
                    mode="REQUIRED",
                    description="Google Ads customer ID",
                ),
                bigquery.SchemaField(
                    "campaign_id", "STRING", mode="REQUIRED", description="Campaign ID"
                ),
                bigquery.SchemaField(
                    "campaign_name",
                    "STRING",
                    mode="REQUIRED",
                    description="Campaign name",
                ),
                bigquery.SchemaField(
                    "ad_group_id", "STRING", mode="NULLABLE", description="Ad group ID"
                ),
                bigquery.SchemaField(
                    "ad_group_name",
                    "STRING",
                    mode="NULLABLE",
                    description="Ad group name",
                ),
                bigquery.SchemaField(
                    "landing_page_url",
                    "STRING",
                    mode="REQUIRED",
                    description="Landing page URL",
                ),
                bigquery.SchemaField(
                    "page_title",
                    "STRING",
                    mode="NULLABLE",
                    description="Landing page title",
                ),
                bigquery.SchemaField(
                    "impressions",
                    "INTEGER",
                    mode="REQUIRED",
                    description="Number of impressions",
                ),
                bigquery.SchemaField(
                    "clicks", "INTEGER", mode="REQUIRED", description="Number of clicks"
                ),
                bigquery.SchemaField(
                    "cost",
                    "FLOAT",
                    mode="REQUIRED",
                    description="Cost in account currency",
                ),
                bigquery.SchemaField(
                    "conversions",
                    "FLOAT",
                    mode="REQUIRED",
                    description="Number of conversions",
                ),
                bigquery.SchemaField(
                    "ctr", "FLOAT", mode="NULLABLE", description="Click-through rate"
                ),
                bigquery.SchemaField(
                    "cpc", "FLOAT", mode="NULLABLE", description="Cost per click"
                ),
                bigquery.SchemaField(
                    "conversion_rate",
                    "FLOAT",
                    mode="NULLABLE",
                    description="Conversion rate",
                ),
                bigquery.SchemaField(
                    "bounce_rate",
                    "FLOAT",
                    mode="NULLABLE",
                    description="Bounce rate from Google Analytics",
                ),
                bigquery.SchemaField(
                    "page_load_time",
                    "FLOAT",
                    mode="NULLABLE",
                    description="Page load time in seconds",
                ),
                bigquery.SchemaField(
                    "mobile_friendly_score",
                    "INTEGER",
                    mode="NULLABLE",
                    description="Mobile friendliness score (0-100)",
                ),
                bigquery.SchemaField(
                    "page_experience_score",
                    "FLOAT",
                    mode="NULLABLE",
                    description="Core Web Vitals score",
                ),
                bigquery.SchemaField(
                    "optimization_recommendations",
                    "STRING",
                    mode="NULLABLE",
                    description="Page optimization recommendations",
                ),
                bigquery.SchemaField(
                    "created_at",
                    "TIMESTAMP",
                    mode="REQUIRED",
                    description="Record creation timestamp",
                ),
                bigquery.SchemaField(
                    "updated_at",
                    "TIMESTAMP",
                    mode="REQUIRED",
                    description="Record update timestamp",
                ),
            ]
        except ImportError:
            logger.warning(
                "Google Cloud BigQuery library not available, returning placeholder schema"
            )
            return []

    @staticmethod
    def get_dayparting_schema():
        """Schema for dayparting analyzer data."""
        try:
            from google.cloud import bigquery

            return [
                bigquery.SchemaField(
                    "date",
                    "DATE",
                    mode="REQUIRED",
                    description="Date of the dayparting performance",
                ),
                bigquery.SchemaField(
                    "customer_id",
                    "STRING",
                    mode="REQUIRED",
                    description="Google Ads customer ID",
                ),
                bigquery.SchemaField(
                    "campaign_id", "STRING", mode="REQUIRED", description="Campaign ID"
                ),
                bigquery.SchemaField(
                    "campaign_name",
                    "STRING",
                    mode="REQUIRED",
                    description="Campaign name",
                ),
                bigquery.SchemaField(
                    "ad_group_id", "STRING", mode="NULLABLE", description="Ad group ID"
                ),
                bigquery.SchemaField(
                    "ad_group_name",
                    "STRING",
                    mode="NULLABLE",
                    description="Ad group name",
                ),
                bigquery.SchemaField(
                    "day_of_week",
                    "STRING",
                    mode="REQUIRED",
                    description="Day of week (MONDAY, TUESDAY, etc.)",
                ),
                bigquery.SchemaField(
                    "hour_of_day",
                    "INTEGER",
                    mode="REQUIRED",
                    description="Hour of day (0-23)",
                ),
                bigquery.SchemaField(
                    "time_slot",
                    "STRING",
                    mode="NULLABLE",
                    description="Time slot name (MORNING, AFTERNOON, EVENING, NIGHT)",
                ),
                bigquery.SchemaField(
                    "impressions",
                    "INTEGER",
                    mode="REQUIRED",
                    description="Number of impressions",
                ),
                bigquery.SchemaField(
                    "clicks", "INTEGER", mode="REQUIRED", description="Number of clicks"
                ),
                bigquery.SchemaField(
                    "cost",
                    "FLOAT",
                    mode="REQUIRED",
                    description="Cost in account currency",
                ),
                bigquery.SchemaField(
                    "conversions",
                    "FLOAT",
                    mode="REQUIRED",
                    description="Number of conversions",
                ),
                bigquery.SchemaField(
                    "ctr", "FLOAT", mode="NULLABLE", description="Click-through rate"
                ),
                bigquery.SchemaField(
                    "cpc", "FLOAT", mode="NULLABLE", description="Cost per click"
                ),
                bigquery.SchemaField(
                    "conversion_rate",
                    "FLOAT",
                    mode="NULLABLE",
                    description="Conversion rate",
                ),
                bigquery.SchemaField(
                    "hourly_performance_score",
                    "FLOAT",
                    mode="NULLABLE",
                    description="Performance score for this hour",
                ),
                bigquery.SchemaField(
                    "bid_adjustment_recommendation",
                    "FLOAT",
                    mode="NULLABLE",
                    description="Recommended bid adjustment for this time",
                ),
                bigquery.SchemaField(
                    "created_at",
                    "TIMESTAMP",
                    mode="REQUIRED",
                    description="Record creation timestamp",
                ),
                bigquery.SchemaField(
                    "updated_at",
                    "TIMESTAMP",
                    mode="REQUIRED",
                    description="Record update timestamp",
                ),
            ]
        except ImportError:
            logger.warning(
                "Google Cloud BigQuery library not available, returning placeholder schema"
            )
            return []

    @staticmethod
    def get_video_creative_schema():
        """Schema for video creative analyzer data."""
        try:
            from google.cloud import bigquery

            return [
                bigquery.SchemaField(
                    "date",
                    "DATE",
                    mode="REQUIRED",
                    description="Date of the video creative performance",
                ),
                bigquery.SchemaField(
                    "customer_id",
                    "STRING",
                    mode="REQUIRED",
                    description="Google Ads customer ID",
                ),
                bigquery.SchemaField(
                    "campaign_id", "STRING", mode="REQUIRED", description="Campaign ID"
                ),
                bigquery.SchemaField(
                    "campaign_name",
                    "STRING",
                    mode="REQUIRED",
                    description="Campaign name",
                ),
                bigquery.SchemaField(
                    "ad_group_id", "STRING", mode="REQUIRED", description="Ad group ID"
                ),
                bigquery.SchemaField(
                    "ad_group_name",
                    "STRING",
                    mode="REQUIRED",
                    description="Ad group name",
                ),
                bigquery.SchemaField(
                    "ad_id", "STRING", mode="REQUIRED", description="Video ad ID"
                ),
                bigquery.SchemaField(
                    "video_id",
                    "STRING",
                    mode="REQUIRED",
                    description="YouTube video ID",
                ),
                bigquery.SchemaField(
                    "video_title", "STRING", mode="NULLABLE", description="Video title"
                ),
                bigquery.SchemaField(
                    "video_duration",
                    "INTEGER",
                    mode="NULLABLE",
                    description="Video duration in seconds",
                ),
                bigquery.SchemaField(
                    "video_format",
                    "STRING",
                    mode="NULLABLE",
                    description="Video ad format",
                ),
                bigquery.SchemaField(
                    "impressions",
                    "INTEGER",
                    mode="REQUIRED",
                    description="Number of impressions",
                ),
                bigquery.SchemaField(
                    "clicks", "INTEGER", mode="REQUIRED", description="Number of clicks"
                ),
                bigquery.SchemaField(
                    "cost",
                    "FLOAT",
                    mode="REQUIRED",
                    description="Cost in account currency",
                ),
                bigquery.SchemaField(
                    "conversions",
                    "FLOAT",
                    mode="REQUIRED",
                    description="Number of conversions",
                ),
                bigquery.SchemaField(
                    "view_rate", "FLOAT", mode="NULLABLE", description="Video view rate"
                ),
                bigquery.SchemaField(
                    "avg_view_duration",
                    "FLOAT",
                    mode="NULLABLE",
                    description="Average view duration in seconds",
                ),
                bigquery.SchemaField(
                    "completion_rate",
                    "FLOAT",
                    mode="NULLABLE",
                    description="Video completion rate",
                ),
                bigquery.SchemaField(
                    "engagement_rate",
                    "FLOAT",
                    mode="NULLABLE",
                    description="Video engagement rate",
                ),
                bigquery.SchemaField(
                    "ctr", "FLOAT", mode="NULLABLE", description="Click-through rate"
                ),
                bigquery.SchemaField(
                    "cpv", "FLOAT", mode="NULLABLE", description="Cost per view"
                ),
                bigquery.SchemaField(
                    "creative_optimization_score",
                    "FLOAT",
                    mode="NULLABLE",
                    description="Creative optimization score",
                ),
                bigquery.SchemaField(
                    "optimization_recommendations",
                    "STRING",
                    mode="NULLABLE",
                    description="Creative optimization recommendations",
                ),
                bigquery.SchemaField(
                    "created_at",
                    "TIMESTAMP",
                    mode="REQUIRED",
                    description="Record creation timestamp",
                ),
                bigquery.SchemaField(
                    "updated_at",
                    "TIMESTAMP",
                    mode="REQUIRED",
                    description="Record update timestamp",
                ),
            ]
        except ImportError:
            logger.warning(
                "Google Cloud BigQuery library not available, returning placeholder schema"
            )
            return []

    @staticmethod
    def get_store_performance_schema():
        """Schema for store performance analyzer data."""
        try:
            from google.cloud import bigquery

            return [
                bigquery.SchemaField(
                    "date",
                    "DATE",
                    mode="REQUIRED",
                    description="Date of the store performance",
                ),
                bigquery.SchemaField(
                    "customer_id",
                    "STRING",
                    mode="REQUIRED",
                    description="Google Ads customer ID",
                ),
                bigquery.SchemaField(
                    "campaign_id", "STRING", mode="REQUIRED", description="Campaign ID"
                ),
                bigquery.SchemaField(
                    "campaign_name",
                    "STRING",
                    mode="REQUIRED",
                    description="Campaign name",
                ),
                bigquery.SchemaField(
                    "store_id",
                    "STRING",
                    mode="REQUIRED",
                    description="Store identifier",
                ),
                bigquery.SchemaField(
                    "store_name",
                    "STRING",
                    mode="REQUIRED",
                    description="Physical store location name",
                ),
                bigquery.SchemaField(
                    "store_address",
                    "STRING",
                    mode="NULLABLE",
                    description="Store address",
                ),
                bigquery.SchemaField(
                    "store_city",
                    "STRING",
                    mode="NULLABLE",
                    description="City where the store is located",
                ),
                bigquery.SchemaField(
                    "store_state", "STRING", mode="NULLABLE", description="Store state"
                ),
                bigquery.SchemaField(
                    "store_zip", "STRING", mode="NULLABLE", description="Store ZIP code"
                ),
                bigquery.SchemaField(
                    "impressions",
                    "INTEGER",
                    mode="REQUIRED",
                    description="Number of impressions",
                ),
                bigquery.SchemaField(
                    "clicks", "INTEGER", mode="REQUIRED", description="Number of clicks"
                ),
                bigquery.SchemaField(
                    "cost",
                    "FLOAT",
                    mode="REQUIRED",
                    description="Cost in account currency",
                ),
                bigquery.SchemaField(
                    "conversions",
                    "FLOAT",
                    mode="REQUIRED",
                    description="Number of conversions",
                ),
                bigquery.SchemaField(
                    "store_visits",
                    "INTEGER",
                    mode="NULLABLE",
                    description="Number of store visits",
                ),
                bigquery.SchemaField(
                    "calls",
                    "INTEGER",
                    mode="NULLABLE",
                    description="Number of calls generated",
                ),
                bigquery.SchemaField(
                    "directions_requests",
                    "INTEGER",
                    mode="NULLABLE",
                    description="Number of direction requests",
                ),
                bigquery.SchemaField(
                    "ctr", "FLOAT", mode="NULLABLE", description="Click-through rate"
                ),
                bigquery.SchemaField(
                    "cpc", "FLOAT", mode="NULLABLE", description="Cost per click"
                ),
                bigquery.SchemaField(
                    "conversion_rate",
                    "FLOAT",
                    mode="NULLABLE",
                    description="Conversion rate",
                ),
                bigquery.SchemaField(
                    "visit_rate",
                    "FLOAT",
                    mode="NULLABLE",
                    description="Store visit rate",
                ),
                bigquery.SchemaField(
                    "cost_per_visit",
                    "FLOAT",
                    mode="NULLABLE",
                    description="Cost per store visit",
                ),
                bigquery.SchemaField(
                    "performance_score",
                    "FLOAT",
                    mode="NULLABLE",
                    description="Store performance score",
                ),
                bigquery.SchemaField(
                    "local_optimization_recommendations",
                    "STRING",
                    mode="NULLABLE",
                    description="Local optimization recommendations",
                ),
                bigquery.SchemaField(
                    "created_at",
                    "TIMESTAMP",
                    mode="REQUIRED",
                    description="Record creation timestamp",
                ),
                bigquery.SchemaField(
                    "updated_at",
                    "TIMESTAMP",
                    mode="REQUIRED",
                    description="Record update timestamp",
                ),
            ]
        except ImportError:
            logger.warning(
                "Google Cloud BigQuery library not available, returning placeholder schema"
            )
            return []

    @staticmethod
    def get_negative_conflicts_schema():
        """Schema for negative keyword conflicts analyzer data."""
        try:
            from google.cloud import bigquery

            return [
                bigquery.SchemaField(
                    "date", "DATE", mode="REQUIRED", description="Date of analysis"
                ),
                bigquery.SchemaField(
                    "customer_id",
                    "STRING",
                    mode="REQUIRED",
                    description="Google Ads customer ID",
                ),
                bigquery.SchemaField(
                    "campaign_id", "STRING", mode="REQUIRED", description="Campaign ID"
                ),
                bigquery.SchemaField(
                    "campaign_name",
                    "STRING",
                    mode="REQUIRED",
                    description="Campaign name",
                ),
                bigquery.SchemaField(
                    "ad_group_id", "STRING", mode="NULLABLE", description="Ad group ID"
                ),
                bigquery.SchemaField(
                    "ad_group_name",
                    "STRING",
                    mode="NULLABLE",
                    description="Ad group name",
                ),
                bigquery.SchemaField(
                    "positive_keyword",
                    "STRING",
                    mode="REQUIRED",
                    description="Positive keyword being blocked",
                ),
                bigquery.SchemaField(
                    "negative_keyword",
                    "STRING",
                    mode="REQUIRED",
                    description="Negative keyword causing conflict",
                ),
                bigquery.SchemaField(
                    "negative_keyword_level",
                    "STRING",
                    mode="REQUIRED",
                    description="CAMPAIGN, AD_GROUP, SHARED_LIST",
                ),
                bigquery.SchemaField(
                    "conflict_type",
                    "STRING",
                    mode="REQUIRED",
                    description="EXACT_MATCH, PHRASE_MATCH, BROAD_MATCH",
                ),
                bigquery.SchemaField(
                    "severity",
                    "STRING",
                    mode="REQUIRED",
                    description="HIGH, MEDIUM, LOW",
                ),
                bigquery.SchemaField(
                    "potential_impressions_blocked",
                    "INTEGER",
                    mode="NULLABLE",
                    description="Estimated impressions blocked",
                ),
                bigquery.SchemaField(
                    "potential_clicks_blocked",
                    "INTEGER",
                    mode="NULLABLE",
                    description="Estimated clicks blocked",
                ),
                bigquery.SchemaField(
                    "potential_cost_savings",
                    "FLOAT",
                    mode="NULLABLE",
                    description="Potential cost savings if resolved",
                ),
                bigquery.SchemaField(
                    "resolution_recommendation",
                    "STRING",
                    mode="NULLABLE",
                    description="Recommended resolution action",
                ),
                bigquery.SchemaField(
                    "confidence_score",
                    "FLOAT",
                    mode="NULLABLE",
                    description="Confidence in conflict detection (0-1)",
                ),
                bigquery.SchemaField(
                    "created_at",
                    "TIMESTAMP",
                    mode="REQUIRED",
                    description="Record creation timestamp",
                ),
                bigquery.SchemaField(
                    "updated_at",
                    "TIMESTAMP",
                    mode="REQUIRED",
                    description="Record update timestamp",
                ),
            ]
        except ImportError:
            logger.warning(
                "Google Cloud BigQuery library not available, returning placeholder schema"
            )
            return []

    @staticmethod
    def get_shared_negatives_schema():
        """Schema for shared negative keyword lists analyzer data."""
        try:
            from google.cloud import bigquery

            return [
                bigquery.SchemaField(
                    "date", "DATE", mode="REQUIRED", description="Date of analysis"
                ),
                bigquery.SchemaField(
                    "customer_id",
                    "STRING",
                    mode="REQUIRED",
                    description="Google Ads customer ID",
                ),
                bigquery.SchemaField(
                    "shared_list_id",
                    "STRING",
                    mode="REQUIRED",
                    description="Shared negative list ID",
                ),
                bigquery.SchemaField(
                    "shared_list_name",
                    "STRING",
                    mode="REQUIRED",
                    description="Shared negative list name",
                ),
                bigquery.SchemaField(
                    "negative_keyword",
                    "STRING",
                    mode="REQUIRED",
                    description="Negative keyword text",
                ),
                bigquery.SchemaField(
                    "match_type",
                    "STRING",
                    mode="REQUIRED",
                    description="Negative keyword match type",
                ),
                bigquery.SchemaField(
                    "campaigns_applied",
                    "INTEGER",
                    mode="REQUIRED",
                    description="Number of campaigns using this list",
                ),
                bigquery.SchemaField(
                    "campaign_names",
                    "STRING",
                    mode="NULLABLE",
                    description="Comma-separated list of campaign names",
                ),
                bigquery.SchemaField(
                    "keyword_category",
                    "STRING",
                    mode="NULLABLE",
                    description="Category of negative keyword",
                ),
                bigquery.SchemaField(
                    "total_blocked_impressions",
                    "INTEGER",
                    mode="NULLABLE",
                    description="Total impressions blocked",
                ),
                bigquery.SchemaField(
                    "total_blocked_clicks",
                    "INTEGER",
                    mode="NULLABLE",
                    description="Total clicks blocked",
                ),
                bigquery.SchemaField(
                    "total_cost_savings",
                    "FLOAT",
                    mode="NULLABLE",
                    description="Total cost savings",
                ),
                bigquery.SchemaField(
                    "effectiveness_score",
                    "FLOAT",
                    mode="NULLABLE",
                    description="Negative keyword effectiveness score",
                ),
                bigquery.SchemaField(
                    "optimization_recommendation",
                    "STRING",
                    mode="NULLABLE",
                    description="Optimization recommendations",
                ),
                bigquery.SchemaField(
                    "created_at",
                    "TIMESTAMP",
                    mode="REQUIRED",
                    description="Record creation timestamp",
                ),
                bigquery.SchemaField(
                    "updated_at",
                    "TIMESTAMP",
                    mode="REQUIRED",
                    description="Record update timestamp",
                ),
            ]
        except ImportError:
            logger.warning(
                "Google Cloud BigQuery library not available, returning placeholder schema"
            )
            return []

    @staticmethod
    def get_bid_adjustments_schema():
        """Schema for bid adjustments analyzer data."""
        try:
            from google.cloud import bigquery

            return [
                bigquery.SchemaField(
                    "date",
                    "DATE",
                    mode="REQUIRED",
                    description="Date of the bid adjustment analysis",
                ),
                bigquery.SchemaField(
                    "customer_id",
                    "STRING",
                    mode="REQUIRED",
                    description="Google Ads customer ID",
                ),
                bigquery.SchemaField(
                    "campaign_id", "STRING", mode="REQUIRED", description="Campaign ID"
                ),
                bigquery.SchemaField(
                    "campaign_name",
                    "STRING",
                    mode="REQUIRED",
                    description="Campaign name",
                ),
                bigquery.SchemaField(
                    "ad_group_id", "STRING", mode="NULLABLE", description="Ad group ID"
                ),
                bigquery.SchemaField(
                    "ad_group_name",
                    "STRING",
                    mode="NULLABLE",
                    description="Ad group name",
                ),
                bigquery.SchemaField(
                    "adjustment_type",
                    "STRING",
                    mode="REQUIRED",
                    description="DEVICE, LOCATION, DEMOGRAPHIC, TIME",
                ),
                bigquery.SchemaField(
                    "adjustment_dimension",
                    "STRING",
                    mode="REQUIRED",
                    description="Specific dimension being adjusted",
                ),
                bigquery.SchemaField(
                    "current_adjustment",
                    "FLOAT",
                    mode="NULLABLE",
                    description="Current bid adjustment (%)",
                ),
                bigquery.SchemaField(
                    "recommended_adjustment",
                    "FLOAT",
                    mode="REQUIRED",
                    description="Recommended bid adjustment (%)",
                ),
                bigquery.SchemaField(
                    "adjustment_reason",
                    "STRING",
                    mode="NULLABLE",
                    description="Reason for adjustment recommendation",
                ),
                bigquery.SchemaField(
                    "current_performance_score",
                    "FLOAT",
                    mode="NULLABLE",
                    description="Current performance score",
                ),
                bigquery.SchemaField(
                    "projected_performance_score",
                    "FLOAT",
                    mode="NULLABLE",
                    description="Projected performance score",
                ),
                bigquery.SchemaField(
                    "estimated_impact_cost",
                    "FLOAT",
                    mode="NULLABLE",
                    description="Estimated cost impact",
                ),
                bigquery.SchemaField(
                    "estimated_impact_conversions",
                    "FLOAT",
                    mode="NULLABLE",
                    description="Estimated conversion impact",
                ),
                bigquery.SchemaField(
                    "confidence_level",
                    "STRING",
                    mode="NULLABLE",
                    description="HIGH, MEDIUM, LOW",
                ),
                bigquery.SchemaField(
                    "priority_score",
                    "FLOAT",
                    mode="NULLABLE",
                    description="Priority score for implementation",
                ),
                bigquery.SchemaField(
                    "created_at",
                    "TIMESTAMP",
                    mode="REQUIRED",
                    description="Record creation timestamp",
                ),
                bigquery.SchemaField(
                    "updated_at",
                    "TIMESTAMP",
                    mode="REQUIRED",
                    description="Record update timestamp",
                ),
            ]
        except ImportError:
            logger.warning(
                "Google Cloud BigQuery library not available, returning placeholder schema"
            )
            return []

    @staticmethod
    def get_pmax_schema():
        """Schema for Performance Max analyzer data."""
        try:
            from google.cloud import bigquery

            return [
                bigquery.SchemaField(
                    "date",
                    "DATE",
                    mode="REQUIRED",
                    description="Date of Performance Max analysis",
                ),
                bigquery.SchemaField(
                    "customer_id",
                    "STRING",
                    mode="REQUIRED",
                    description="Google Ads customer ID",
                ),
                bigquery.SchemaField(
                    "campaign_id",
                    "STRING",
                    mode="REQUIRED",
                    description="Performance Max campaign ID",
                ),
                bigquery.SchemaField(
                    "campaign_name",
                    "STRING",
                    mode="REQUIRED",
                    description="Performance Max campaign name",
                ),
                bigquery.SchemaField(
                    "asset_group_id",
                    "STRING",
                    mode="NULLABLE",
                    description="Asset group ID",
                ),
                bigquery.SchemaField(
                    "asset_group_name",
                    "STRING",
                    mode="NULLABLE",
                    description="Asset group name",
                ),
                bigquery.SchemaField(
                    "asset_type",
                    "STRING",
                    mode="NULLABLE",
                    description="Type of asset (HEADLINE, DESCRIPTION, IMAGE, etc.)",
                ),
                bigquery.SchemaField(
                    "asset_id",
                    "STRING",
                    mode="NULLABLE",
                    description="Asset unique identifier",
                ),
                bigquery.SchemaField(
                    "asset_text",
                    "STRING",
                    mode="NULLABLE",
                    description="Asset text content",
                ),
                bigquery.SchemaField(
                    "listing_group_type",
                    "STRING",
                    mode="NULLABLE",
                    description="Product listing group type",
                ),
                bigquery.SchemaField(
                    "impressions",
                    "INTEGER",
                    mode="REQUIRED",
                    description="Number of impressions",
                ),
                bigquery.SchemaField(
                    "clicks", "INTEGER", mode="REQUIRED", description="Number of clicks"
                ),
                bigquery.SchemaField(
                    "cost",
                    "FLOAT",
                    mode="REQUIRED",
                    description="Cost in account currency",
                ),
                bigquery.SchemaField(
                    "conversions",
                    "FLOAT",
                    mode="REQUIRED",
                    description="Number of conversions",
                ),
                bigquery.SchemaField(
                    "conversion_value",
                    "FLOAT",
                    mode="NULLABLE",
                    description="Total conversion value",
                ),
                bigquery.SchemaField(
                    "view_through_conversions",
                    "FLOAT",
                    mode="NULLABLE",
                    description="View-through conversions",
                ),
                bigquery.SchemaField(
                    "ctr", "FLOAT", mode="NULLABLE", description="Click-through rate"
                ),
                bigquery.SchemaField(
                    "cpc", "FLOAT", mode="NULLABLE", description="Cost per click"
                ),
                bigquery.SchemaField(
                    "cpa", "FLOAT", mode="NULLABLE", description="Cost per acquisition"
                ),
                bigquery.SchemaField(
                    "roas", "FLOAT", mode="NULLABLE", description="Return on ad spend"
                ),
                bigquery.SchemaField(
                    "asset_performance_score",
                    "FLOAT",
                    mode="NULLABLE",
                    description="Asset performance score",
                ),
                bigquery.SchemaField(
                    "optimization_score",
                    "FLOAT",
                    mode="NULLABLE",
                    description="Campaign optimization score",
                ),
                bigquery.SchemaField(
                    "expansion_recommendations",
                    "STRING",
                    mode="NULLABLE",
                    description="Asset expansion recommendations",
                ),
                bigquery.SchemaField(
                    "created_at",
                    "TIMESTAMP",
                    mode="REQUIRED",
                    description="Record creation timestamp",
                ),
                bigquery.SchemaField(
                    "updated_at",
                    "TIMESTAMP",
                    mode="REQUIRED",
                    description="Record update timestamp",
                ),
            ]
        except ImportError:
            logger.warning(
                "Google Cloud BigQuery library not available, returning placeholder schema"
            )
            return []

    @staticmethod
    def get_analytics_data_schema():
        """Schema for Google Analytics integration data."""
        try:
            from google.cloud import bigquery

            return [
                bigquery.SchemaField(
                    "date",
                    "DATE",
                    mode="REQUIRED",
                    description="Date of analytics data",
                ),
                bigquery.SchemaField(
                    "customer_id",
                    "STRING",
                    mode="REQUIRED",
                    description="Google Ads customer ID",
                ),
                bigquery.SchemaField(
                    "ga_property_id",
                    "STRING",
                    mode="REQUIRED",
                    description="Google Analytics property ID",
                ),
                bigquery.SchemaField(
                    "campaign_id",
                    "STRING",
                    mode="NULLABLE",
                    description="Campaign ID from Google Ads",
                ),
                bigquery.SchemaField(
                    "campaign_name",
                    "STRING",
                    mode="NULLABLE",
                    description="Campaign name",
                ),
                bigquery.SchemaField(
                    "medium",
                    "STRING",
                    mode="REQUIRED",
                    description="Traffic medium (cpc, organic, etc.)",
                ),
                bigquery.SchemaField(
                    "source",
                    "STRING",
                    mode="REQUIRED",
                    description="Traffic source (google, bing, etc.)",
                ),
                bigquery.SchemaField(
                    "landing_page",
                    "STRING",
                    mode="NULLABLE",
                    description="Landing page URL",
                ),
                bigquery.SchemaField(
                    "sessions",
                    "INTEGER",
                    mode="REQUIRED",
                    description="Number of sessions",
                ),
                bigquery.SchemaField(
                    "users", "INTEGER", mode="REQUIRED", description="Number of users"
                ),
                bigquery.SchemaField(
                    "page_views",
                    "INTEGER",
                    mode="REQUIRED",
                    description="Number of page views",
                ),
                bigquery.SchemaField(
                    "bounce_rate",
                    "FLOAT",
                    mode="NULLABLE",
                    description="Bounce rate (%)",
                ),
                bigquery.SchemaField(
                    "session_duration",
                    "FLOAT",
                    mode="NULLABLE",
                    description="Average session duration (seconds)",
                ),
                bigquery.SchemaField(
                    "goal_completions",
                    "INTEGER",
                    mode="NULLABLE",
                    description="Goal completions",
                ),
                bigquery.SchemaField(
                    "goal_value",
                    "FLOAT",
                    mode="NULLABLE",
                    description="Target goal value for optimization",
                ),
                bigquery.SchemaField(
                    "ecommerce_transactions",
                    "INTEGER",
                    mode="NULLABLE",
                    description="E-commerce transactions",
                ),
                bigquery.SchemaField(
                    "ecommerce_revenue",
                    "FLOAT",
                    mode="NULLABLE",
                    description="E-commerce revenue",
                ),
                bigquery.SchemaField(
                    "assisted_conversions",
                    "INTEGER",
                    mode="NULLABLE",
                    description="Assisted conversions",
                ),
                bigquery.SchemaField(
                    "assisted_conversion_value",
                    "FLOAT",
                    mode="NULLABLE",
                    description="Assisted conversion value",
                ),
                bigquery.SchemaField(
                    "gclid",
                    "STRING",
                    mode="NULLABLE",
                    description="Google Click ID for cross-platform attribution",
                ),
                bigquery.SchemaField(
                    "wbraid",
                    "STRING",
                    mode="NULLABLE",
                    description="Web browser attribution ID",
                ),
                bigquery.SchemaField(
                    "gbraid",
                    "STRING",
                    mode="NULLABLE",
                    description="Google browser attribution ID",
                ),
                bigquery.SchemaField(
                    "session_id",
                    "STRING",
                    mode="NULLABLE",
                    description="GA4 session ID for session-level analysis",
                ),
                bigquery.SchemaField(
                    "event_timestamp",
                    "TIMESTAMP",
                    mode="NULLABLE",
                    description="GA4 event timestamp in UTC",
                ),
                bigquery.SchemaField(
                    "session_engaged",
                    "BOOLEAN",
                    mode="NULLABLE",
                    description="Whether the session was engaged (GA4 definition)",
                ),
                bigquery.SchemaField(
                    "engagement_time_msec",
                    "INTEGER",
                    mode="NULLABLE",
                    description="Total engagement time in milliseconds",
                ),
                bigquery.SchemaField(
                    "first_visit",
                    "BOOLEAN",
                    mode="NULLABLE",
                    description="Whether this was a first visit for the user",
                ),
                bigquery.SchemaField(
                    "store_location_id",
                    "STRING",
                    mode="NULLABLE",
                    description="Store location ID for store visit attribution",
                ),
                bigquery.SchemaField(
                    "distance_to_store",
                    "FLOAT",
                    mode="NULLABLE",
                    description="Distance to nearest store in kilometers",
                ),
                bigquery.SchemaField(
                    "store_visit_converted",
                    "BOOLEAN",
                    mode="NULLABLE",
                    description="Whether the store visit resulted in a conversion",
                ),
                bigquery.SchemaField(
                    "item_purchase_quantity",
                    "INTEGER",
                    mode="NULLABLE",
                    description="Quantity of items purchased in GA4 purchase event",
                ),
                bigquery.SchemaField(
                    "item_revenue_usd",
                    "FLOAT",
                    mode="NULLABLE",
                    description="Item revenue in USD from GA4 purchase events",
                ),
                bigquery.SchemaField(
                    "transaction_id",
                    "STRING",
                    mode="NULLABLE",
                    description="GA4 transaction ID for e-commerce events",
                ),
                bigquery.SchemaField(
                    "ga4_user_id",
                    "STRING",
                    mode="NULLABLE",
                    description="GA4 user ID for cross-session attribution",
                ),
                bigquery.SchemaField(
                    "user_ltv",
                    "FLOAT",
                    mode="NULLABLE",
                    description="User lifetime value calculated from GA4 data",
                ),
                bigquery.SchemaField(
                    "attribution_model",
                    "STRING",
                    mode="NULLABLE",
                    description="Attribution model used: last_click, first_click, linear, etc.",
                ),
                bigquery.SchemaField(
                    "created_at",
                    "TIMESTAMP",
                    mode="REQUIRED",
                    description="Record creation timestamp",
                ),
                bigquery.SchemaField(
                    "updated_at",
                    "TIMESTAMP",
                    mode="REQUIRED",
                    description="Record update timestamp",
                ),
            ]
        except ImportError:
            logger.warning(
                "Google Cloud BigQuery library not available, returning placeholder schema"
            )
            return []

    @staticmethod
    def get_cost_tracking_schema():
        """Schema for BigQuery usage monitoring and cost tracking."""
        try:
            from google.cloud import bigquery

            return [
                bigquery.SchemaField(
                    "date",
                    "DATE",
                    mode="REQUIRED",
                    description="Date of BigQuery usage",
                ),
                bigquery.SchemaField(
                    "customer_id", "STRING", mode="REQUIRED", description="Customer ID"
                ),
                bigquery.SchemaField(
                    "project_id",
                    "STRING",
                    mode="REQUIRED",
                    description="BigQuery project ID",
                ),
                bigquery.SchemaField(
                    "dataset_id",
                    "STRING",
                    mode="REQUIRED",
                    description="BigQuery dataset ID",
                ),
                bigquery.SchemaField(
                    "table_name",
                    "STRING",
                    mode="NULLABLE",
                    description="Table name queried",
                ),
                bigquery.SchemaField(
                    "job_id", "STRING", mode="REQUIRED", description="BigQuery job ID"
                ),
                bigquery.SchemaField(
                    "job_type",
                    "STRING",
                    mode="REQUIRED",
                    description="QUERY, LOAD, EXTRACT, COPY",
                ),
                bigquery.SchemaField(
                    "query_type",
                    "STRING",
                    mode="NULLABLE",
                    description="SELECT, INSERT, UPDATE, DELETE",
                ),
                bigquery.SchemaField(
                    "bytes_processed",
                    "INTEGER",
                    mode="REQUIRED",
                    description="Bytes processed by query",
                ),
                bigquery.SchemaField(
                    "bytes_billed",
                    "INTEGER",
                    mode="REQUIRED",
                    description="Bytes billed for query",
                ),
                bigquery.SchemaField(
                    "slot_hours",
                    "FLOAT",
                    mode="NULLABLE",
                    description="Slot hours consumed",
                ),
                bigquery.SchemaField(
                    "estimated_cost_usd",
                    "FLOAT",
                    mode="REQUIRED",
                    description="Estimated cost in USD",
                ),
                bigquery.SchemaField(
                    "execution_time_ms",
                    "INTEGER",
                    mode="NULLABLE",
                    description="Query execution time in milliseconds",
                ),
                bigquery.SchemaField(
                    "cache_hit",
                    "BOOLEAN",
                    mode="NULLABLE",
                    description="Whether query used cached results",
                ),
                bigquery.SchemaField(
                    "tier",
                    "STRING",
                    mode="REQUIRED",
                    description="Customer tier (STANDARD, PREMIUM, ENTERPRISE)",
                ),
                bigquery.SchemaField(
                    "api_endpoint",
                    "STRING",
                    mode="NULLABLE",
                    description="API endpoint that triggered query",
                ),
                bigquery.SchemaField(
                    "user_agent",
                    "STRING",
                    mode="NULLABLE",
                    description="User agent of request",
                ),
                bigquery.SchemaField(
                    "created_at",
                    "TIMESTAMP",
                    mode="REQUIRED",
                    description="Record creation timestamp",
                ),
            ]
        except ImportError:
            logger.warning(
                "Google Cloud BigQuery library not available, returning placeholder schema"
            )
            return []

    @staticmethod
    def get_ml_models_schema():
        """Schema for BigQuery ML models metadata (Enterprise tier)."""
        try:
            from google.cloud import bigquery

            return [
                bigquery.SchemaField(
                    "model_id", "STRING", mode="REQUIRED", description="ML model ID"
                ),
                bigquery.SchemaField(
                    "customer_id", "STRING", mode="REQUIRED", description="Customer ID"
                ),
                bigquery.SchemaField(
                    "model_name",
                    "STRING",
                    mode="REQUIRED",
                    description="BigQuery ML model name identifier",
                ),
                bigquery.SchemaField(
                    "model_type",
                    "STRING",
                    mode="REQUIRED",
                    description="LINEAR_REG, LOGISTIC_REG, KMEANS, etc.",
                ),
                bigquery.SchemaField(
                    "model_purpose",
                    "STRING",
                    mode="REQUIRED",
                    description="BID_OPTIMIZATION, KEYWORD_PREDICTION, etc.",
                ),
                bigquery.SchemaField(
                    "training_data_source",
                    "STRING",
                    mode="REQUIRED",
                    description="Source table for training data",
                ),
                bigquery.SchemaField(
                    "feature_columns",
                    "STRING",
                    mode="NULLABLE",
                    description="JSON array of feature column names",
                ),
                bigquery.SchemaField(
                    "target_column",
                    "STRING",
                    mode="NULLABLE",
                    description="Target column for supervised learning",
                ),
                bigquery.SchemaField(
                    "training_start_date",
                    "DATE",
                    mode="NULLABLE",
                    description="Start date of training data",
                ),
                bigquery.SchemaField(
                    "training_end_date",
                    "DATE",
                    mode="NULLABLE",
                    description="End date of training data",
                ),
                bigquery.SchemaField(
                    "model_accuracy",
                    "FLOAT",
                    mode="NULLABLE",
                    description="Model accuracy score",
                ),
                bigquery.SchemaField(
                    "rmse",
                    "FLOAT",
                    mode="NULLABLE",
                    description="Root mean square error",
                ),
                bigquery.SchemaField(
                    "mae", "FLOAT", mode="NULLABLE", description="Mean absolute error"
                ),
                bigquery.SchemaField(
                    "r_squared", "FLOAT", mode="NULLABLE", description="R-squared value"
                ),
                bigquery.SchemaField(
                    "training_rows",
                    "INTEGER",
                    mode="NULLABLE",
                    description="Number of training rows",
                ),
                bigquery.SchemaField(
                    "validation_rows",
                    "INTEGER",
                    mode="NULLABLE",
                    description="Number of validation rows",
                ),
                bigquery.SchemaField(
                    "model_status",
                    "STRING",
                    mode="REQUIRED",
                    description="TRAINING, ACTIVE, DEPRECATED",
                ),
                bigquery.SchemaField(
                    "last_prediction_date",
                    "DATE",
                    mode="NULLABLE",
                    description="Last date model was used for predictions",
                ),
                bigquery.SchemaField(
                    "retrain_frequency_days",
                    "INTEGER",
                    mode="NULLABLE",
                    description="How often to retrain (days)",
                ),
                bigquery.SchemaField(
                    "created_at",
                    "TIMESTAMP",
                    mode="REQUIRED",
                    description="Model creation timestamp",
                ),
                bigquery.SchemaField(
                    "updated_at",
                    "TIMESTAMP",
                    mode="REQUIRED",
                    description="Model update timestamp",
                ),
            ]
        except ImportError:
            logger.warning(
                "Google Cloud BigQuery library not available, returning placeholder schema"
            )
            return []

    @staticmethod
    def get_table_configurations() -> Dict[str, Dict[str, Any]]:
        """Get BigQuery table configurations with partitioning and clustering."""
        return {
            "search_terms": {
                "partition_field": "date",
                "partition_type": "DAY",
                "cluster_fields": ["customer_id", "campaign_id"],
                "description": "Search terms performance data with negative keyword recommendations",
            },
            "keywords": {
                "partition_field": "date",
                "partition_type": "DAY",
                "cluster_fields": ["customer_id", "campaign_id"],
                "description": "Keyword performance data with bid recommendations",
            },
            "campaigns": {
                "partition_field": "date",
                "partition_type": "DAY",
                "cluster_fields": ["customer_id"],
                "description": "Campaign performance data and optimization insights",
            },
            "ad_groups": {
                "partition_field": "date",
                "partition_type": "DAY",
                "cluster_fields": ["customer_id", "campaign_id"],
                "description": "Ad group performance data and optimization scores",
            },
            "demographics": {
                "partition_field": "date",
                "partition_type": "DAY",
                "cluster_fields": ["customer_id", "demographic_type"],
                "description": "Demographic targeting performance and bid adjustments",
            },
            "device_performance": {
                "partition_field": "date",
                "partition_type": "DAY",
                "cluster_fields": ["customer_id", "device_type"],
                "description": "Device performance analysis and bid adjustments",
            },
            "geo_performance": {
                "partition_field": "date",
                "partition_type": "DAY",
                "cluster_fields": ["customer_id", "location_level"],
                "description": "Geographic performance analysis and local intent scoring",
            },
            "landing_page": {
                "partition_field": "date",
                "partition_type": "DAY",
                "cluster_fields": ["customer_id"],
                "description": "Landing page performance and optimization recommendations",
            },
            "dayparting": {
                "partition_field": "date",
                "partition_type": "DAY",
                "cluster_fields": ["customer_id", "day_of_week"],
                "description": "Time-based performance analysis and bid scheduling",
            },
            "video_creative": {
                "partition_field": "date",
                "partition_type": "DAY",
                "cluster_fields": ["customer_id", "campaign_id"],
                "description": "Video creative performance and engagement metrics",
            },
            "store_performance": {
                "partition_field": "date",
                "partition_type": "DAY",
                "cluster_fields": ["customer_id", "store_id"],
                "description": "Individual store performance and local optimization",
            },
            "negative_conflicts": {
                "partition_field": "date",
                "partition_type": "DAY",
                "cluster_fields": ["customer_id", "severity"],
                "description": "Negative keyword conflicts and resolution recommendations",
            },
            "shared_negatives": {
                "partition_field": "date",
                "partition_type": "DAY",
                "cluster_fields": ["customer_id", "shared_list_id"],
                "description": "Shared negative keyword list analysis and effectiveness",
            },
            "bid_adjustments": {
                "partition_field": "date",
                "partition_type": "DAY",
                "cluster_fields": ["customer_id", "adjustment_type"],
                "description": "Bid adjustment recommendations and performance impact",
            },
            "pmax": {
                "partition_field": "date",
                "partition_type": "DAY",
                "cluster_fields": ["customer_id", "campaign_id"],
                "description": "Performance Max campaign analysis and asset optimization",
            },
            "analytics_data": {
                "partition_field": "date",
                "partition_type": "DAY",
                "cluster_fields": ["customer_id", "medium"],
                "description": "Google Analytics integration data for cross-platform analysis",
            },
            "cost_tracking": {
                "partition_field": "date",
                "partition_type": "DAY",
                "cluster_fields": ["customer_id", "tier"],
                "description": "BigQuery usage monitoring and cost tracking per customer",
            },
            "ml_models": {
                "partition_field": None,  # No partitioning for metadata table
                "partition_type": None,
                "cluster_fields": ["customer_id", "model_type"],
                "description": "ML model metadata and performance metrics (Enterprise tier)",
            },
            "attribution_touches": {
                "partition_field": "date",
                "partition_type": "DAY",
                "cluster_fields": ["customer_id", "customer_journey_id"],
                "description": "Individual customer touchpoints for attribution analysis",
            },
            "customer_journeys": {
                "partition_field": "date",
                "partition_type": "DAY",
                "cluster_fields": ["customer_id", "attribution_model"],
                "description": "Complete customer journeys with attribution analysis",
            },
            "gclid_mappings": {
                "partition_field": "date",
                "partition_type": "DAY",
                "cluster_fields": ["customer_id", "gclid"],
                "description": "GCLID mappings between Google Ads and GA4 for attribution",
            },
            "attribution_results": {
                "partition_field": "date",
                "partition_type": "DAY",
                "cluster_fields": ["customer_id", "attribution_model_type"],
                "description": "Attribution analysis results with cross-platform insights",
            },
        }

    @staticmethod
    def get_attribution_touches_schema():
        """Schema for attribution touches data."""
        try:
            from google.cloud import bigquery

            return [
                bigquery.SchemaField(
                    "date",
                    "DATE",
                    mode="REQUIRED",
                    description="Date of the touchpoint",
                ),
                bigquery.SchemaField(
                    "touch_id",
                    "STRING",
                    mode="REQUIRED",
                    description="Unique touchpoint identifier",
                ),
                bigquery.SchemaField(
                    "customer_journey_id",
                    "STRING",
                    mode="REQUIRED",
                    description="Customer journey this touch belongs to",
                ),
                bigquery.SchemaField(
                    "customer_id",
                    "STRING",
                    mode="REQUIRED",
                    description="Customer identifier",
                ),
                bigquery.SchemaField(
                    "touchpoint_type",
                    "STRING",
                    mode="REQUIRED",
                    description="Type of touchpoint: google_ads_click, ga4_session, etc.",
                ),
                bigquery.SchemaField(
                    "timestamp",
                    "TIMESTAMP",
                    mode="REQUIRED",
                    description="When the touchpoint occurred",
                ),
                bigquery.SchemaField(
                    "gclid",
                    "STRING",
                    mode="NULLABLE",
                    description="Google Click ID for attribution",
                ),
                bigquery.SchemaField(
                    "campaign_id",
                    "STRING",
                    mode="NULLABLE",
                    description="Google Ads campaign ID",
                ),
                bigquery.SchemaField(
                    "campaign_name",
                    "STRING",
                    mode="NULLABLE",
                    description="Campaign name",
                ),
                bigquery.SchemaField(
                    "source", "STRING", mode="NULLABLE", description="Traffic source"
                ),
                bigquery.SchemaField(
                    "medium", "STRING", mode="NULLABLE", description="Traffic medium"
                ),
                bigquery.SchemaField(
                    "landing_page",
                    "STRING",
                    mode="NULLABLE",
                    description="Landing page URL",
                ),
                bigquery.SchemaField(
                    "country", "STRING", mode="NULLABLE", description="User country"
                ),
                bigquery.SchemaField(
                    "device_category",
                    "STRING",
                    mode="NULLABLE",
                    description="Device category",
                ),
                bigquery.SchemaField(
                    "attribution_weight",
                    "FLOAT",
                    mode="REQUIRED",
                    description="Attribution weight (0.0-1.0)",
                ),
                bigquery.SchemaField(
                    "revenue_attributed",
                    "FLOAT",
                    mode="REQUIRED",
                    description="Revenue attributed to this touch",
                ),
                bigquery.SchemaField(
                    "is_conversion_touch",
                    "BOOLEAN",
                    mode="REQUIRED",
                    description="Whether this touch resulted in conversion",
                ),
                bigquery.SchemaField(
                    "conversion_value",
                    "FLOAT",
                    mode="NULLABLE",
                    description="Conversion value if applicable",
                ),
                bigquery.SchemaField(
                    "created_at",
                    "TIMESTAMP",
                    mode="REQUIRED",
                    description="Record creation timestamp",
                ),
                bigquery.SchemaField(
                    "updated_at",
                    "TIMESTAMP",
                    mode="REQUIRED",
                    description="Record update timestamp",
                ),
            ]
        except ImportError:
            logger.warning(
                "Google Cloud BigQuery library not available, returning placeholder schema"
            )
            return []

    @staticmethod
    def get_customer_journeys_schema():
        """Schema for customer journeys data."""
        try:
            from google.cloud import bigquery

            return [
                bigquery.SchemaField(
                    "date", "DATE", mode="REQUIRED", description="Journey start date"
                ),
                bigquery.SchemaField(
                    "journey_id",
                    "STRING",
                    mode="REQUIRED",
                    description="Unique journey identifier",
                ),
                bigquery.SchemaField(
                    "customer_id",
                    "STRING",
                    mode="REQUIRED",
                    description="Customer identifier",
                ),
                bigquery.SchemaField(
                    "first_touch",
                    "TIMESTAMP",
                    mode="REQUIRED",
                    description="First touchpoint timestamp",
                ),
                bigquery.SchemaField(
                    "last_touch",
                    "TIMESTAMP",
                    mode="REQUIRED",
                    description="Last touchpoint timestamp",
                ),
                bigquery.SchemaField(
                    "conversion_timestamp",
                    "TIMESTAMP",
                    mode="NULLABLE",
                    description="Conversion timestamp",
                ),
                bigquery.SchemaField(
                    "total_touches",
                    "INTEGER",
                    mode="REQUIRED",
                    description="Total number of touchpoints",
                ),
                bigquery.SchemaField(
                    "converted",
                    "BOOLEAN",
                    mode="REQUIRED",
                    description="Whether journey resulted in conversion",
                ),
                bigquery.SchemaField(
                    "conversion_value",
                    "FLOAT",
                    mode="REQUIRED",
                    description="Total conversion value",
                ),
                bigquery.SchemaField(
                    "attribution_model",
                    "STRING",
                    mode="REQUIRED",
                    description="Attribution model applied",
                ),
                bigquery.SchemaField(
                    "journey_length_days",
                    "FLOAT",
                    mode="REQUIRED",
                    description="Journey length in days",
                ),
                bigquery.SchemaField(
                    "first_touch_source",
                    "STRING",
                    mode="REQUIRED",
                    description="First touch traffic source",
                ),
                bigquery.SchemaField(
                    "first_touch_medium",
                    "STRING",
                    mode="REQUIRED",
                    description="First touch traffic medium",
                ),
                bigquery.SchemaField(
                    "last_touch_source",
                    "STRING",
                    mode="REQUIRED",
                    description="Last touch traffic source",
                ),
                bigquery.SchemaField(
                    "last_touch_medium",
                    "STRING",
                    mode="REQUIRED",
                    description="Last touch traffic medium",
                ),
                bigquery.SchemaField(
                    "total_attributed_revenue",
                    "FLOAT",
                    mode="REQUIRED",
                    description="Total revenue attributed across all touches",
                ),
                bigquery.SchemaField(
                    "google_ads_attributed_revenue",
                    "FLOAT",
                    mode="REQUIRED",
                    description="Revenue attributed to Google Ads",
                ),
                bigquery.SchemaField(
                    "is_multi_channel",
                    "BOOLEAN",
                    mode="REQUIRED",
                    description="Journey spans multiple channels",
                ),
                bigquery.SchemaField(
                    "is_multi_device",
                    "BOOLEAN",
                    mode="REQUIRED",
                    description="Journey spans multiple devices",
                ),
                bigquery.SchemaField(
                    "created_at",
                    "TIMESTAMP",
                    mode="REQUIRED",
                    description="Record creation timestamp",
                ),
                bigquery.SchemaField(
                    "updated_at",
                    "TIMESTAMP",
                    mode="REQUIRED",
                    description="Record update timestamp",
                ),
            ]
        except ImportError:
            logger.warning(
                "Google Cloud BigQuery library not available, returning placeholder schema"
            )
            return []

    @staticmethod
    def get_gclid_mappings_schema():
        """Schema for GCLID mapping data between Google Ads and GA4."""
        try:
            from google.cloud import bigquery

            return [
                bigquery.SchemaField(
                    "date",
                    "DATE",
                    mode="REQUIRED",
                    description="Date of the click/session",
                ),
                bigquery.SchemaField(
                    "gclid", "STRING", mode="REQUIRED", description="Google Click ID"
                ),
                bigquery.SchemaField(
                    "customer_id",
                    "STRING",
                    mode="REQUIRED",
                    description="Customer identifier",
                ),
                bigquery.SchemaField(
                    "google_ads_click_timestamp",
                    "TIMESTAMP",
                    mode="REQUIRED",
                    description="Google Ads click timestamp",
                ),
                bigquery.SchemaField(
                    "campaign_id",
                    "STRING",
                    mode="REQUIRED",
                    description="Google Ads campaign ID",
                ),
                bigquery.SchemaField(
                    "campaign_name",
                    "STRING",
                    mode="REQUIRED",
                    description="Campaign name",
                ),
                bigquery.SchemaField(
                    "ad_group_id", "STRING", mode="REQUIRED", description="Ad group ID"
                ),
                bigquery.SchemaField(
                    "click_cost",
                    "FLOAT",
                    mode="REQUIRED",
                    description="Cost of the click",
                ),
                bigquery.SchemaField(
                    "ga4_session_id",
                    "STRING",
                    mode="NULLABLE",
                    description="Matched GA4 session ID",
                ),
                bigquery.SchemaField(
                    "session_start_timestamp",
                    "TIMESTAMP",
                    mode="NULLABLE",
                    description="GA4 session start time",
                ),
                bigquery.SchemaField(
                    "landing_page",
                    "STRING",
                    mode="NULLABLE",
                    description="Landing page from GA4",
                ),
                bigquery.SchemaField(
                    "match_confidence",
                    "FLOAT",
                    mode="REQUIRED",
                    description="Match confidence score (0.0-1.0)",
                ),
                bigquery.SchemaField(
                    "time_diff_seconds",
                    "INTEGER",
                    mode="NULLABLE",
                    description="Time difference between click and session",
                ),
                bigquery.SchemaField(
                    "session_converted",
                    "BOOLEAN",
                    mode="REQUIRED",
                    description="Whether session resulted in conversion",
                ),
                bigquery.SchemaField(
                    "conversion_value",
                    "FLOAT",
                    mode="REQUIRED",
                    description="Conversion value",
                ),
                bigquery.SchemaField(
                    "attribution_weight",
                    "FLOAT",
                    mode="REQUIRED",
                    description="Attribution weight for this mapping",
                ),
                bigquery.SchemaField(
                    "created_at",
                    "TIMESTAMP",
                    mode="REQUIRED",
                    description="Record creation timestamp",
                ),
                bigquery.SchemaField(
                    "updated_at",
                    "TIMESTAMP",
                    mode="REQUIRED",
                    description="Record update timestamp",
                ),
            ]
        except ImportError:
            logger.warning(
                "Google Cloud BigQuery library not available, returning placeholder schema"
            )
            return []

    @staticmethod
    def get_attribution_results_schema():
        """Schema for attribution analysis results."""
        try:
            from google.cloud import bigquery

            return [
                bigquery.SchemaField(
                    "date", "DATE", mode="REQUIRED", description="Analysis date"
                ),
                bigquery.SchemaField(
                    "result_id",
                    "STRING",
                    mode="REQUIRED",
                    description="Unique result identifier",
                ),
                bigquery.SchemaField(
                    "customer_journey_id",
                    "STRING",
                    mode="REQUIRED",
                    description="Journey this result belongs to",
                ),
                bigquery.SchemaField(
                    "customer_id",
                    "STRING",
                    mode="REQUIRED",
                    description="Customer identifier",
                ),
                bigquery.SchemaField(
                    "attribution_model_id",
                    "STRING",
                    mode="REQUIRED",
                    description="Attribution model used",
                ),
                bigquery.SchemaField(
                    "attribution_model_type",
                    "STRING",
                    mode="REQUIRED",
                    description="Attribution model type",
                ),
                bigquery.SchemaField(
                    "total_conversion_value",
                    "FLOAT",
                    mode="REQUIRED",
                    description="Total conversion value",
                ),
                bigquery.SchemaField(
                    "total_attributed_value",
                    "FLOAT",
                    mode="REQUIRED",
                    description="Total attributed value",
                ),
                bigquery.SchemaField(
                    "attribution_confidence",
                    "FLOAT",
                    mode="REQUIRED",
                    description="Attribution confidence score",
                ),
                bigquery.SchemaField(
                    "google_ads_attributed_revenue",
                    "FLOAT",
                    mode="REQUIRED",
                    description="Revenue attributed to Google Ads",
                ),
                bigquery.SchemaField(
                    "organic_attributed_revenue",
                    "FLOAT",
                    mode="REQUIRED",
                    description="Revenue attributed to organic traffic",
                ),
                bigquery.SchemaField(
                    "direct_attributed_revenue",
                    "FLOAT",
                    mode="REQUIRED",
                    description="Revenue attributed to direct traffic",
                ),
                bigquery.SchemaField(
                    "cross_platform_roas",
                    "FLOAT",
                    mode="NULLABLE",
                    description="Cross-platform return on ad spend",
                ),
                bigquery.SchemaField(
                    "journey_length_days",
                    "FLOAT",
                    mode="REQUIRED",
                    description="Customer journey length in days",
                ),
                bigquery.SchemaField(
                    "total_touches",
                    "INTEGER",
                    mode="REQUIRED",
                    description="Total touchpoints in journey",
                ),
                bigquery.SchemaField(
                    "predicted_ltv",
                    "FLOAT",
                    mode="NULLABLE",
                    description="Predicted customer lifetime value",
                ),
                bigquery.SchemaField(
                    "conversion_probability",
                    "FLOAT",
                    mode="NULLABLE",
                    description="Predicted conversion probability",
                ),
                bigquery.SchemaField(
                    "model_accuracy",
                    "FLOAT",
                    mode="NULLABLE",
                    description="Attribution model accuracy score",
                ),
                bigquery.SchemaField(
                    "created_at",
                    "TIMESTAMP",
                    mode="REQUIRED",
                    description="Record creation timestamp",
                ),
                bigquery.SchemaField(
                    "updated_at",
                    "TIMESTAMP",
                    mode="REQUIRED",
                    description="Record update timestamp",
                ),
            ]
        except ImportError:
            logger.warning(
                "Google Cloud BigQuery library not available, returning placeholder schema"
            )
            return []

    @staticmethod
    def get_all_schemas() -> Dict[str, List[Any]]:
        """Get all table schemas for BigQuery setup."""
        return {
            "search_terms": BigQueryTableSchema.get_search_terms_schema(),
            "keywords": BigQueryTableSchema.get_keywords_schema(),
            "campaigns": BigQueryTableSchema.get_campaigns_schema(),
            "ad_groups": BigQueryTableSchema.get_ad_groups_schema(),
            "demographics": BigQueryTableSchema.get_demographics_schema(),
            "device_performance": BigQueryTableSchema.get_device_performance_schema(),
            "geo_performance": BigQueryTableSchema.get_geo_performance_schema(),
            "landing_page": BigQueryTableSchema.get_landing_page_schema(),
            "dayparting": BigQueryTableSchema.get_dayparting_schema(),
            "video_creative": BigQueryTableSchema.get_video_creative_schema(),
            "store_performance": BigQueryTableSchema.get_store_performance_schema(),
            "negative_conflicts": BigQueryTableSchema.get_negative_conflicts_schema(),
            "shared_negatives": BigQueryTableSchema.get_shared_negatives_schema(),
            "bid_adjustments": BigQueryTableSchema.get_bid_adjustments_schema(),
            "pmax": BigQueryTableSchema.get_pmax_schema(),
            "analytics_data": BigQueryTableSchema.get_analytics_data_schema(),
            "cost_tracking": BigQueryTableSchema.get_cost_tracking_schema(),
            "ml_models": BigQueryTableSchema.get_ml_models_schema(),
            "attribution_touches": BigQueryTableSchema.get_attribution_touches_schema(),
            "customer_journeys": BigQueryTableSchema.get_customer_journeys_schema(),
            "gclid_mappings": BigQueryTableSchema.get_gclid_mappings_schema(),
            "attribution_results": BigQueryTableSchema.get_attribution_results_schema(),
        }
