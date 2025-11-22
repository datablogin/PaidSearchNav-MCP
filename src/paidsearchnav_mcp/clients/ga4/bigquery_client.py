"""GA4 BigQuery native integration client for PaidSearchNav.

This module provides direct access to GA4 BigQuery export tables for enhanced
analytics integration without requiring GA4 API access.
"""

import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    from google.cloud import bigquery
    from google.cloud.exceptions import GoogleCloudError
    from google.oauth2 import service_account

    BIGQUERY_AVAILABLE = True
except ImportError:
    BIGQUERY_AVAILABLE = False
    bigquery = None
    GoogleCloudError = Exception

logger = logging.getLogger(__name__)


class GA4BigQueryClient:
    """Client for accessing GA4 BigQuery export tables directly."""

    def __init__(
        self,
        project_id: str,
        ga4_dataset_id: str,
        location: str = "US",
        credentials_path: Optional[str] = None,
    ):
        """Initialize the GA4 BigQuery client.

        Args:
            project_id: Google Cloud project ID where GA4 exports are stored
            ga4_dataset_id: GA4 BigQuery dataset ID (e.g., analytics_123456789)
            location: BigQuery dataset location
            credentials_path: Optional path to service account credentials file
        """
        if not BIGQUERY_AVAILABLE:
            raise ImportError(
                "Google Cloud BigQuery is required for GA4 integration. "
                "Install with: pip install google-cloud-bigquery"
            )

        self.project_id = project_id
        self.ga4_dataset_id = ga4_dataset_id
        self.location = location
        self.credentials_path = credentials_path
        self._client = None
        self._last_request_time = 0.0
        self._min_request_interval = 0.1  # 100ms between requests

    def _get_client(self) -> bigquery.Client:
        """Get or create BigQuery client with explicit credential management."""
        if self._client is None:
            try:
                if self.credentials_path:
                    credentials = service_account.Credentials.from_service_account_file(
                        self.credentials_path
                    )
                    self._client = bigquery.Client(
                        project=self.project_id,
                        location=self.location,
                        credentials=credentials,
                    )
                    logger.info("Using service account credentials for BigQuery client")
                else:
                    # Use default credentials with validation
                    self._client = bigquery.Client(
                        project=self.project_id, location=self.location
                    )
                    logger.info("Using default credentials for BigQuery client")

                # Test the connection
                self._client.get_dataset(self.ga4_dataset_id)
                logger.info(
                    f"Successfully authenticated with BigQuery for dataset {self.ga4_dataset_id}"
                )

            except Exception as e:
                logger.error(f"Failed to authenticate with BigQuery: {e}")
                raise GoogleCloudError(f"Authentication failed: {e}")

        return self._client

    def _apply_rate_limiting(self):
        """Apply rate limiting to prevent BigQuery quota exhaustion."""
        current_time = time.time()
        time_since_last_request = current_time - self._last_request_time

        if time_since_last_request < self._min_request_interval:
            sleep_time = self._min_request_interval - time_since_last_request
            time.sleep(sleep_time)

        self._last_request_time = time.time()

    def discover_ga4_tables(self) -> List[str]:
        """Discover all available GA4 event tables in the dataset.

        Returns:
            List of table names (e.g., events_20241201, events_intraday_20241201)
        """
        try:
            client = self._get_client()
            dataset_ref = client.dataset(self.ga4_dataset_id)

            tables = []
            for table in client.list_tables(dataset_ref):
                if table.table_id.startswith(("events_", "events_intraday_")):
                    tables.append(table.table_id)

            logger.info(f"Discovered {len(tables)} GA4 event tables")
            return sorted(tables)

        except GoogleCloudError as e:
            logger.error(f"Failed to discover GA4 tables: {e}")
            return []

    def get_table_schema(self, table_name: str) -> Optional[List[Dict[str, Any]]]:
        """Get schema for a specific GA4 table.

        Args:
            table_name: GA4 table name (e.g., events_20241201)

        Returns:
            Table schema as list of field dictionaries
        """
        try:
            client = self._get_client()
            table_ref = client.dataset(self.ga4_dataset_id).table(table_name)
            table = client.get_table(table_ref)

            schema = []
            for field in table.schema:
                schema.append(
                    {
                        "name": field.name,
                        "type": field.field_type,
                        "mode": field.mode,
                        "description": field.description or "",
                    }
                )

            return schema

        except GoogleCloudError as e:
            logger.error(f"Failed to get schema for table {table_name}: {e}")
            return None

    def get_gclid_sessions(
        self,
        start_date: datetime,
        end_date: datetime,
        gclid_list: List[str],
    ) -> List[Dict[str, Any]]:
        """Get GA4 session data for specific Google Click IDs.

        Args:
            start_date: Start date for data extraction
            end_date: End date for data extraction
            gclid_list: List of Google Click IDs to match

        Returns:
            List of session records with GA4 metrics
        """
        if not gclid_list:
            return []

        date_range = self._get_date_range(start_date, end_date)

        query = f"""
        WITH session_data AS (
          SELECT
            user_pseudo_id,
            (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'session_id') as session_id,
            (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'gclid') as gclid,
            (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'wbraid') as wbraid,
            (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'gbraid') as gbraid,
            TIMESTAMP_MICROS(event_timestamp) as event_timestamp,
            event_name,
            (SELECT value.int_value FROM UNNEST(event_params) WHERE key = 'session_engaged') as session_engaged,
            (SELECT value.int_value FROM UNNEST(event_params) WHERE key = 'engagement_time_msec') as engagement_time_msec,
            (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'page_location') as page_location,
            geo.country,
            geo.region,
            geo.city,
            device.category as device_category,
            traffic_source.source,
            traffic_source.medium,
            traffic_source.name as campaign_name,
            (SELECT value.double_value FROM UNNEST(event_params) WHERE key = 'value') as event_value,
            ecommerce.transaction_id,
            ecommerce.purchase_revenue_in_usd
          FROM
            `{self.project_id}.{self.ga4_dataset_id}.events_*`
          WHERE
            _TABLE_SUFFIX BETWEEN '{date_range["start_suffix"]}' AND '{date_range["end_suffix"]}'
            AND (
              (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'gclid') IN UNNEST(@gclid_list)
              OR (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'wbraid') IN UNNEST(@gclid_list)
              OR (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'gbraid') IN UNNEST(@gclid_list)
            )
        ),
        session_metrics AS (
          SELECT
            session_id,
            gclid,
            wbraid,
            gbraid,
            user_pseudo_id,
            MIN(event_timestamp) as session_start,
            MAX(event_timestamp) as session_end,
            MAX(session_engaged) = 1 as session_engaged,
            SUM(engagement_time_msec) as total_engagement_time_msec,
            COUNT(DISTINCT CASE WHEN event_name = 'page_view' THEN CONCAT(user_pseudo_id, event_timestamp) END) as page_views,
            COUNT(DISTINCT CASE WHEN event_name = 'session_start' THEN user_pseudo_id END) > 0 as is_new_user,
            MAX(CASE WHEN event_name = 'purchase' THEN event_value END) as purchase_value,
            MAX(CASE WHEN event_name = 'purchase' THEN transaction_id END) as transaction_id,
            STRING_AGG(DISTINCT page_location ORDER BY event_timestamp LIMIT 1) as landing_page,
            MAX(country) as country,
            MAX(region) as region,
            MAX(city) as city,
            MAX(device_category) as device_category,
            MAX(source) as traffic_source,
            MAX(medium) as traffic_medium,
            MAX(campaign_name) as campaign_name
          FROM session_data
          WHERE session_id IS NOT NULL
          GROUP BY session_id, gclid, wbraid, gbraid, user_pseudo_id
        )
        SELECT
          session_id,
          COALESCE(gclid, wbraid, gbraid) as attribution_id,
          gclid,
          wbraid,
          gbraid,
          user_pseudo_id as ga4_user_id,
          session_start as event_timestamp,
          session_engaged,
          total_engagement_time_msec as engagement_time_msec,
          TIMESTAMP_DIFF(session_end, session_start, SECOND) as session_duration_seconds,
          page_views,
          is_new_user as first_visit,
          landing_page,
          CASE
            WHEN page_views = 1 AND total_engagement_time_msec < 10000 THEN
              ROUND(100.0, 2)  -- 100% bounce rate for single page view with <10s engagement
            WHEN page_views = 1 THEN
              ROUND(80.0, 2)   -- 80% bounce rate for single page view with >10s engagement
            ELSE
              ROUND(0.0, 2)    -- 0% bounce rate for multi-page sessions
          END as bounce_rate,
          purchase_value,
          transaction_id,
          country,
          region,
          city,
          device_category,
          traffic_source,
          traffic_medium,
          campaign_name,
          CURRENT_TIMESTAMP() as created_at
        FROM session_metrics
        ORDER BY session_start DESC
        """

        # Create job config with parameterized query
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ArrayQueryParameter("gclid_list", "STRING", gclid_list),
            ]
        )

        return self._execute_query(query, job_config)

    def get_store_visit_attribution(
        self,
        start_date: datetime,
        end_date: datetime,
        store_locations: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Get store visit attribution data from GA4.

        Args:
            start_date: Start date for data extraction
            end_date: End date for data extraction
            store_locations: List of store location data with lat/lng

        Returns:
            List of store visit attribution records
        """
        date_range = self._get_date_range(start_date, end_date)

        # Build store location conditions for proximity detection
        store_conditions = []
        for store in store_locations:
            lat = store.get("latitude")
            lng = store.get("longitude")
            store_id = store.get("store_id", "unknown")

            if lat and lng:
                # Use ST_DWITHIN for proper geospatial distance calculation (1000m = 1km)
                store_conditions.append(f"""
                    ST_DWITHIN(
                        ST_GEOGPOINT(geo.longitude, geo.latitude),
                        ST_GEOGPOINT({lng}, {lat}),
                        1000  -- 1km radius in meters
                    ) THEN '{store_id}'
                """)

        store_case_when = " ".join(
            [f"WHEN {condition}" for condition in store_conditions]
        )

        query = f"""
        WITH store_visits AS (
          SELECT
            user_pseudo_id,
            (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'session_id') as session_id,
            (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'gclid') as gclid,
            TIMESTAMP_MICROS(event_timestamp) as visit_timestamp,
            geo.country,
            geo.region,
            geo.city,
            geo.latitude,
            geo.longitude,
            CASE
              {store_case_when}
              ELSE 'unknown'
            END as nearest_store_id,
            event_name,
            (SELECT value.double_value FROM UNNEST(event_params) WHERE key = 'value') as event_value
          FROM
            `{self.project_id}.{self.ga4_dataset_id}.events_*`
          WHERE
            _TABLE_SUFFIX BETWEEN '{date_range["start_suffix"]}' AND '{date_range["end_suffix"]}'
            AND event_name IN ('store_locator_used', 'directions_requested', 'phone_call_clicked', 'store_visit')
            AND (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'gclid') IS NOT NULL
        ),
        conversion_events AS (
          SELECT
            user_pseudo_id,
            (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'session_id') as session_id,
            TIMESTAMP_MICROS(event_timestamp) as conversion_timestamp,
            event_name as conversion_event,
            (SELECT value.double_value FROM UNNEST(event_params) WHERE key = 'value') as conversion_value,
            ecommerce.transaction_id
          FROM
            `{self.project_id}.{self.ga4_dataset_id}.events_*`
          WHERE
            _TABLE_SUFFIX BETWEEN '{date_range["start_suffix"]}' AND '{date_range["end_suffix"]}'
            AND event_name IN ('purchase', 'lead', 'sign_up', 'contact')
        )
        SELECT
          sv.gclid,
          sv.session_id,
          sv.user_pseudo_id as ga4_user_id,
          sv.visit_timestamp as event_timestamp,
          sv.nearest_store_id as store_location_id,
          CASE
            WHEN sv.latitude IS NOT NULL AND sv.longitude IS NOT NULL THEN
              ST_DISTANCE(
                ST_GEOGPOINT(sv.longitude, sv.latitude),
                ST_GEOGPOINT(
                  (SELECT longitude FROM UNNEST({store_locations}) WHERE store_id = sv.nearest_store_id),
                  (SELECT latitude FROM UNNEST({store_locations}) WHERE store_id = sv.nearest_store_id)
                )
              ) / 1000  -- Convert to kilometers
            ELSE NULL
          END as distance_to_store,
          sv.country,
          sv.region,
          sv.city,
          COUNT(DISTINCT ce.session_id) > 0 as store_visit_converted,
          MAX(ce.conversion_value) as conversion_value,
          MAX(ce.transaction_id) as transaction_id,
          COUNT(DISTINCT sv.session_id) as store_interaction_count,
          CURRENT_TIMESTAMP() as created_at
        FROM store_visits sv
        LEFT JOIN conversion_events ce
          ON sv.user_pseudo_id = ce.user_pseudo_id
          AND ce.conversion_timestamp BETWEEN sv.visit_timestamp AND TIMESTAMP_ADD(sv.visit_timestamp, INTERVAL 7 DAY)
        WHERE sv.gclid IS NOT NULL
          AND sv.nearest_store_id != 'unknown'
        GROUP BY
          sv.gclid, sv.session_id, sv.user_pseudo_id, sv.visit_timestamp,
          sv.nearest_store_id, sv.latitude, sv.longitude, sv.country, sv.region, sv.city
        ORDER BY sv.visit_timestamp DESC
        """

        return self._execute_query(query)

    def get_ga4_revenue_attribution(
        self,
        start_date: datetime,
        end_date: datetime,
        attribution_model: str = "last_click",
    ) -> List[Dict[str, Any]]:
        """Get GA4 e-commerce revenue attribution data.

        Args:
            start_date: Start date for data extraction
            end_date: End date for data extraction
            attribution_model: Attribution model to use

        Returns:
            List of revenue attribution records
        """
        date_range = self._get_date_range(start_date, end_date)

        query = f"""
        WITH attribution_sessions AS (
          SELECT
            user_pseudo_id,
            (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'session_id') as session_id,
            (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'gclid') as gclid,
            TIMESTAMP_MICROS(event_timestamp) as session_timestamp,
            traffic_source.source,
            traffic_source.medium,
            traffic_source.name as campaign_name,
            (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'campaign_id') as google_ads_campaign_id,
            FIRST_VALUE(TIMESTAMP_MICROS(event_timestamp)) OVER (
              PARTITION BY user_pseudo_id
              ORDER BY event_timestamp
              ROWS UNBOUNDED PRECEDING
            ) as first_touch_timestamp,
            LAST_VALUE(TIMESTAMP_MICROS(event_timestamp)) OVER (
              PARTITION BY user_pseudo_id
              ORDER BY event_timestamp
              ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
            ) as last_touch_timestamp
          FROM
            `{self.project_id}.{self.ga4_dataset_id}.events_*`
          WHERE
            _TABLE_SUFFIX BETWEEN '{date_range["start_suffix"]}' AND '{date_range["end_suffix"]}'
            AND event_name = 'session_start'
            AND (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'gclid') IS NOT NULL
        ),
        purchase_events AS (
          SELECT
            user_pseudo_id,
            (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'session_id') as session_id,
            TIMESTAMP_MICROS(event_timestamp) as purchase_timestamp,
            ecommerce.transaction_id,
            ecommerce.purchase_revenue_in_usd as purchase_revenue,
            ARRAY_LENGTH(ecommerce.items) as item_count,
            (
              SELECT SUM(item.quantity)
              FROM UNNEST(ecommerce.items) as item
            ) as total_quantity
          FROM
            `{self.project_id}.{self.ga4_dataset_id}.events_*`
          WHERE
            _TABLE_SUFFIX BETWEEN '{date_range["start_suffix"]}' AND '{date_range["end_suffix"]}'
            AND event_name = 'purchase'
            AND ecommerce.transaction_id IS NOT NULL
        )
        SELECT
          CASE
            WHEN '{attribution_model}' = 'first_click' THEN
              (SELECT gclid FROM attribution_sessions a2 WHERE a2.user_pseudo_id = pe.user_pseudo_id AND a2.session_timestamp = a.first_touch_timestamp LIMIT 1)
            WHEN '{attribution_model}' = 'last_click' THEN
              (SELECT gclid FROM attribution_sessions a2 WHERE a2.user_pseudo_id = pe.user_pseudo_id AND a2.session_timestamp = a.last_touch_timestamp LIMIT 1)
            ELSE a.gclid  -- Default to session gclid for linear/time-decay
          END as gclid,
          pe.session_id,
          pe.user_pseudo_id as ga4_user_id,
          pe.purchase_timestamp as event_timestamp,
          pe.transaction_id,
          pe.purchase_revenue as item_revenue_usd,
          pe.total_quantity as item_purchase_quantity,
          a.campaign_name,
          a.source as traffic_source,
          a.medium as traffic_medium,
          '{attribution_model}' as attribution_model,
          CASE
            WHEN '{attribution_model}' = 'linear' THEN
              pe.purchase_revenue / (SELECT COUNT(*) FROM attribution_sessions a3 WHERE a3.user_pseudo_id = pe.user_pseudo_id)
            ELSE pe.purchase_revenue
          END as attributed_revenue,
          CURRENT_TIMESTAMP() as created_at
        FROM purchase_events pe
        LEFT JOIN attribution_sessions a
          ON pe.user_pseudo_id = a.user_pseudo_id
          AND a.session_timestamp <= pe.purchase_timestamp
        WHERE a.gclid IS NOT NULL
        ORDER BY pe.purchase_timestamp DESC
        """

        return self._execute_query(query)

    def get_ga4_revenue_attribution_multi_model(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Get GA4 revenue attribution data for all attribution models in a single query.

        This is more efficient than calling get_ga4_revenue_attribution multiple times.

        Args:
            start_date: Start date for data extraction
            end_date: End date for data extraction

        Returns:
            Dictionary with attribution model names as keys and attribution data as values
        """
        date_range = self._get_date_range(start_date, end_date)

        query = f"""
        WITH attribution_sessions AS (
          SELECT
            user_pseudo_id,
            (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'session_id') as session_id,
            (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'gclid') as gclid,
            TIMESTAMP_MICROS(event_timestamp) as session_timestamp,
            traffic_source.source,
            traffic_source.medium,
            traffic_source.name as campaign_name,
            (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'campaign_id') as google_ads_campaign_id,
            FIRST_VALUE(TIMESTAMP_MICROS(event_timestamp)) OVER (
              PARTITION BY user_pseudo_id
              ORDER BY event_timestamp
              ROWS UNBOUNDED PRECEDING
            ) as first_touch_timestamp,
            LAST_VALUE(TIMESTAMP_MICROS(event_timestamp)) OVER (
              PARTITION BY user_pseudo_id
              ORDER BY event_timestamp
              ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
            ) as last_touch_timestamp
          FROM
            `{self.project_id}.{self.ga4_dataset_id}.events_*`
          WHERE
            _TABLE_SUFFIX BETWEEN '{date_range["start_suffix"]}' AND '{date_range["end_suffix"]}'
            AND event_name = 'session_start'
            AND (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'gclid') IS NOT NULL
        ),
        purchase_events AS (
          SELECT
            user_pseudo_id,
            (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'session_id') as session_id,
            ecommerce.transaction_id,
            ecommerce.purchase_revenue_in_usd as revenue,
            TIMESTAMP_MICROS(event_timestamp) as purchase_timestamp
          FROM
            `{self.project_id}.{self.ga4_dataset_id}.events_*`
          WHERE
            _TABLE_SUFFIX BETWEEN '{date_range["start_suffix"]}' AND '{date_range["end_suffix"]}'
            AND event_name = 'purchase'
            AND ecommerce.purchase_revenue_in_usd IS NOT NULL
        ),
        attribution_analysis AS (
          SELECT
            s.user_pseudo_id,
            s.session_id,
            s.gclid,
            s.campaign_name,
            s.google_ads_campaign_id,
            p.transaction_id,
            p.revenue,
            p.purchase_timestamp,
            -- Last click attribution
            s.session_timestamp = s.last_touch_timestamp as is_last_click,
            -- First click attribution
            s.session_timestamp = s.first_touch_timestamp as is_first_click,
            -- Linear attribution weight (1/total_sessions for this user)
            1.0 / COUNT(*) OVER (PARTITION BY s.user_pseudo_id) as linear_weight
          FROM attribution_sessions s
          JOIN purchase_events p ON s.user_pseudo_id = p.user_pseudo_id
        )
        SELECT
          'last_click' as attribution_model,
          user_pseudo_id,
          session_id,
          gclid,
          campaign_name,
          google_ads_campaign_id,
          transaction_id,
          CASE WHEN is_last_click THEN revenue ELSE 0 END as attributed_revenue,
          purchase_timestamp
        FROM attribution_analysis
        WHERE is_last_click

        UNION ALL

        SELECT
          'first_click' as attribution_model,
          user_pseudo_id,
          session_id,
          gclid,
          campaign_name,
          google_ads_campaign_id,
          transaction_id,
          CASE WHEN is_first_click THEN revenue ELSE 0 END as attributed_revenue,
          purchase_timestamp
        FROM attribution_analysis
        WHERE is_first_click

        UNION ALL

        SELECT
          'linear' as attribution_model,
          user_pseudo_id,
          session_id,
          gclid,
          campaign_name,
          google_ads_campaign_id,
          transaction_id,
          revenue * linear_weight as attributed_revenue,
          purchase_timestamp
        FROM attribution_analysis

        ORDER BY attribution_model, purchase_timestamp DESC
        """

        results = self._execute_query(query)

        # Group results by attribution model
        attribution_data = {"last_click": [], "first_click": [], "linear": []}

        for row in results:
            model = row.get("attribution_model")
            if model in attribution_data:
                attribution_data[model].append(row)

        return attribution_data

    def validate_gclid_matching(
        self,
        google_ads_data: List[Dict[str, Any]],
        start_date: datetime,
        end_date: datetime,
    ) -> Dict[str, Any]:
        """Validate GCLID matching between Google Ads and GA4 data.

        Args:
            google_ads_data: Google Ads data with GCLIDs
            start_date: Start date for validation
            end_date: End date for validation

        Returns:
            Validation report with match rates and data quality metrics
        """
        if not google_ads_data:
            return {
                "total_google_ads_clicks": 0,
                "matched_sessions": 0,
                "match_rate_percent": 0.0,
                "unmatched_gclids": [],
                "data_quality_score": 0.0,
            }

        # Extract GCLIDs from Google Ads data
        ads_gclids = [
            record.get("gclid") for record in google_ads_data if record.get("gclid")
        ]

        if not ads_gclids:
            return {
                "total_google_ads_clicks": len(google_ads_data),
                "matched_sessions": 0,
                "match_rate_percent": 0.0,
                "unmatched_gclids": [],
                "data_quality_score": 0.0,
                "error": "No GCLIDs found in Google Ads data",
            }

        # Get matching GA4 sessions
        ga4_sessions = self.get_gclid_sessions(start_date, end_date, ads_gclids)

        matched_gclids = {
            session.get("gclid") for session in ga4_sessions if session.get("gclid")
        }
        unmatched_gclids = [
            gclid for gclid in ads_gclids if gclid not in matched_gclids
        ]

        match_rate = (
            (len(matched_gclids) / len(ads_gclids)) * 100 if ads_gclids else 0.0
        )

        # Calculate data quality score based on match rate and data completeness
        data_quality_score = min(
            100.0, match_rate + (10 if len(ga4_sessions) > 0 else 0)
        )

        return {
            "total_google_ads_clicks": len(ads_gclids),
            "matched_sessions": len(matched_gclids),
            "match_rate_percent": round(match_rate, 2),
            "unmatched_gclids": unmatched_gclids[:10],  # Sample of unmatched
            "total_unmatched": len(unmatched_gclids),
            "data_quality_score": round(data_quality_score, 2),
            "validation_timestamp": datetime.utcnow().isoformat(),
            "ga4_dataset": self.ga4_dataset_id,
        }

    def _get_date_range(
        self, start_date: datetime, end_date: datetime
    ) -> Dict[str, str]:
        """Convert datetime range to GA4 table suffix format.

        Args:
            start_date: Start date
            end_date: End date

        Returns:
            Dictionary with start_suffix and end_suffix for table sharding
        """
        return {
            "start_suffix": start_date.strftime("%Y%m%d"),
            "end_suffix": end_date.strftime("%Y%m%d"),
        }

    def _execute_query(
        self, query: str, job_config: Optional[bigquery.QueryJobConfig] = None
    ) -> List[Dict[str, Any]]:
        """Execute BigQuery query and return results.

        Args:
            query: SQL query to execute
            job_config: Optional BigQuery job configuration

        Returns:
            List of result dictionaries
        """
        query_context = query[:100] + "..." if len(query) > 100 else query

        try:
            # Apply rate limiting
            self._apply_rate_limiting()

            client = self._get_client()

            # Configure query job for cost control
            if job_config is None:
                job_config = bigquery.QueryJobConfig()

            # Always apply cost controls
            job_config.maximum_bytes_billed = 10 * 1024 * 1024 * 1024  # 10GB limit
            job_config.use_query_cache = True
            job_config.dry_run = False

            query_job = client.query(query, job_config=job_config)
            results = query_job.result()

            # Convert to list of dictionaries
            records = []
            for row in results:
                record = {}
                for key, value in row.items():
                    # Handle timestamp conversion
                    if isinstance(value, datetime):
                        record[key] = value.isoformat()
                    else:
                        record[key] = value
                records.append(record)

            logger.info(f"Query executed successfully, returned {len(records)} records")
            logger.info(f"Query processed {query_job.total_bytes_processed} bytes")

            return records

        except GoogleCloudError as e:
            logger.error(f"BigQuery query failed for query [{query_context}]: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error executing query [{query_context}]: {e}")
            raise

    def estimate_query_cost(self, query: str) -> Dict[str, Any]:
        """Estimate the cost of running a BigQuery query.

        Args:
            query: SQL query to estimate

        Returns:
            Cost estimation details
        """
        try:
            client = self._get_client()

            # Run dry run to get cost estimate
            job_config = bigquery.QueryJobConfig(dry_run=True, use_query_cache=True)
            query_job = client.query(query, job_config=job_config)

            # Calculate estimated cost ($5 per TB)
            bytes_processed = query_job.total_bytes_processed
            estimated_cost_usd = (bytes_processed / (1024**4)) * 5.0  # $5 per TB

            return {
                "bytes_processed": bytes_processed,
                "estimated_cost_usd": round(estimated_cost_usd, 4),
                "query_valid": True,
                "cost_estimate_timestamp": datetime.utcnow().isoformat(),
            }

        except GoogleCloudError as e:
            logger.error(f"Query cost estimation failed: {e}")
            return {
                "bytes_processed": 0,
                "estimated_cost_usd": 0.0,
                "query_valid": False,
                "error": str(e),
            }
