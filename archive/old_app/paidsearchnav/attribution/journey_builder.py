"""Customer journey builder with GCLID matching and cross-platform data integration."""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import pandas as pd

from paidsearchnav.attribution.models import (
    AttributionModelType,
    AttributionTouch,
    ConversionType,
    CustomerJourney,
    GCLIDMapping,
    TouchpointType,
)
from paidsearchnav.platforms.bigquery.service import BigQueryService
from paidsearchnav.platforms.ga4.client import GA4DataClient

logger = logging.getLogger(__name__)


class CustomerJourneyBuilder:
    """Builds customer journeys by combining Google Ads and GA4 data."""

    def __init__(
        self,
        bigquery_client: BigQueryService,
        ga4_client: GA4DataClient,
        session_timeout_minutes: int = 30,
        max_journey_length_days: int = 90,
    ):
        """Initialize journey builder.

        Args:
            bigquery_client: BigQuery client for data access
            ga4_client: GA4 client for analytics data
            session_timeout_minutes: Session timeout for journey segmentation
            max_journey_length_days: Maximum journey length to consider
        """
        self.bigquery_client = bigquery_client
        self.ga4_client = ga4_client
        self.session_timeout_minutes = session_timeout_minutes
        self.max_journey_length_days = max_journey_length_days

    async def build_customer_journeys(
        self,
        customer_id: str,
        start_date: datetime,
        end_date: datetime,
        include_non_converting: bool = False,
    ) -> Tuple[List[CustomerJourney], Dict[str, List[AttributionTouch]]]:
        """Build customer journeys for the specified period.

        Args:
            customer_id: Customer identifier
            start_date: Analysis start date
            end_date: Analysis end date
            include_non_converting: Whether to include non-converting journeys

        Returns:
            Tuple of (journeys, touchpoints_by_journey_id)
        """
        # Input validation for security
        if not customer_id or not customer_id.strip():
            raise ValueError("customer_id parameter is required and cannot be empty")

        if not isinstance(customer_id, str):
            raise TypeError("customer_id must be a string")

        if len(customer_id) > 50:
            raise ValueError("customer_id exceeds maximum length of 50 characters")

        # Sanitize customer_id
        customer_id = customer_id.strip()

        logger.info(
            f"Building customer journeys for {customer_id} from {start_date} to {end_date}"
        )

        try:
            # Get Google Ads click data
            google_ads_data = await self._get_google_ads_data(
                customer_id, start_date, end_date
            )

            # Get GA4 session data
            ga4_data = await self._get_ga4_data(customer_id, start_date, end_date)

            # Create GCLID mappings
            gclid_mappings = self._create_gclid_mappings(google_ads_data, ga4_data)

            # Build unified touchpoints
            all_touches = self._build_unified_touchpoints(
                google_ads_data, ga4_data, gclid_mappings
            )

            # Group touchpoints into customer journeys
            journeys, journey_touches = self._group_into_journeys(
                all_touches, include_non_converting
            )

            logger.info(
                f"Built {len(journeys)} customer journeys with {len(all_touches)} total touchpoints"
            )

            return journeys, journey_touches

        except Exception as e:
            logger.error(f"Failed to build customer journeys: {e}")
            raise

    async def _get_google_ads_data(
        self, customer_id: str, start_date: datetime, end_date: datetime
    ) -> pd.DataFrame:
        """Get Google Ads click and conversion data from BigQuery."""
        query = f"""
        SELECT
            click_timestamp,
            gclid,
            campaign_id,
            campaign_name,
            ad_group_id,
            keyword_id,
            search_term,
            cost_micros / 1000000.0 as click_cost,
            device,
            geo_target,
            landing_page_url,
            conversions,
            conversion_value_micros / 1000000.0 as conversion_value
        FROM `{self.bigquery_client.config.project_id}.{self.bigquery_client.config.dataset_id}.search_terms`
        WHERE customer_id = @customer_id
          AND DATE(click_timestamp) BETWEEN @start_date AND @end_date
          AND gclid IS NOT NULL
          AND gclid != ''
        ORDER BY click_timestamp
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

        return await self.bigquery_client.analytics.execute_parameterized_query(
            query, query_params
        )

    async def _get_ga4_data(
        self, customer_id: str, start_date: datetime, end_date: datetime
    ) -> pd.DataFrame:
        """Get GA4 session and event data."""
        # Use GA4 client to get session data with UTM parameters and gclid
        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")

        session_data = await self.ga4_client.get_historical_metrics(
            start_date=start_str,
            end_date=end_str,
            dimensions=[
                "date",
                "source",
                "medium",
                "campaign",
                "gclid",
                "sessionId",
                "userId",
                "country",
                "deviceCategory",
                "landingPage",
                "sessionStart",
            ],
            metrics=[
                "sessions",
                "conversions",
                "totalRevenue",
                "bounceRate",
                "engagementRate",
                "averageSessionDuration",
            ],
            limit=10000,
        )

        # Convert to DataFrame
        rows = session_data.get("rows", [])
        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows)

        # Parse timestamps
        df["session_start"] = pd.to_datetime(df["sessionStart"], errors="coerce")
        df["date"] = pd.to_datetime(df["date"], errors="coerce")

        return df

    def _create_gclid_mappings(
        self, google_ads_data: pd.DataFrame, ga4_data: pd.DataFrame
    ) -> List[GCLIDMapping]:
        """Create GCLID mappings between Google Ads clicks and GA4 sessions."""
        mappings = []

        if google_ads_data.empty or ga4_data.empty:
            return mappings

        # Filter GA4 data to only sessions with gclid
        ga4_with_gclid = ga4_data[ga4_data["gclid"].notna() & (ga4_data["gclid"] != "")]

        for _, ads_row in google_ads_data.iterrows():
            gclid = ads_row.get("gclid")
            if not gclid:
                continue

            # Find matching GA4 sessions by GCLID
            matching_sessions = ga4_with_gclid[ga4_with_gclid["gclid"] == gclid]

            if matching_sessions.empty:
                # Create mapping without GA4 match
                mapping = GCLIDMapping(
                    gclid=gclid,
                    google_ads_click_timestamp=ads_row["click_timestamp"],
                    campaign_id=ads_row["campaign_id"],
                    campaign_name=ads_row["campaign_name"],
                    ad_group_id=ads_row["ad_group_id"],
                    keyword_id=ads_row.get("keyword_id"),
                    search_term=ads_row.get("search_term"),
                    click_cost=ads_row["click_cost"],
                    match_confidence=0.0,  # No GA4 match
                    session_converted=False,
                    conversion_value=ads_row.get("conversion_value", 0.0),
                    attribution_weight=1.0,  # Default weight
                )
                mappings.append(mapping)
                continue

            # Process each matching session
            for _, ga4_row in matching_sessions.iterrows():
                # Calculate time difference between click and session
                click_time = ads_row["click_timestamp"]
                session_time = ga4_row["session_start"]

                if pd.isna(session_time):
                    time_diff = None
                    match_confidence = 0.8  # Lower confidence without timing
                else:
                    time_diff = abs((session_time - click_time).total_seconds())
                    # Higher confidence for closer timing
                    if time_diff <= 300:  # Within 5 minutes
                        match_confidence = 1.0
                    elif time_diff <= 3600:  # Within 1 hour
                        match_confidence = 0.9
                    elif time_diff <= 7200:  # Within 2 hours
                        match_confidence = 0.8
                    else:
                        match_confidence = 0.6

                # Check if session converted
                session_converted = ga4_row.get("conversions", 0) > 0
                session_revenue = ga4_row.get("totalRevenue", 0.0)

                mapping = GCLIDMapping(
                    gclid=gclid,
                    google_ads_click_timestamp=click_time,
                    campaign_id=ads_row["campaign_id"],
                    campaign_name=ads_row["campaign_name"],
                    ad_group_id=ads_row["ad_group_id"],
                    keyword_id=ads_row.get("keyword_id"),
                    search_term=ads_row.get("search_term"),
                    click_cost=ads_row["click_cost"],
                    ga4_session_id=ga4_row.get("sessionId"),
                    ga4_user_id=ga4_row.get("userId"),
                    session_start_timestamp=session_time,
                    landing_page=ga4_row.get("landingPage"),
                    match_confidence=match_confidence,
                    time_diff_seconds=int(time_diff) if time_diff else None,
                    session_converted=session_converted,
                    conversion_value=session_revenue,
                    attribution_weight=1.0,
                )
                mappings.append(mapping)

        logger.info(f"Created {len(mappings)} GCLID mappings")
        return mappings

    def _build_unified_touchpoints(
        self,
        google_ads_data: pd.DataFrame,
        ga4_data: pd.DataFrame,
        gclid_mappings: List[GCLIDMapping],
    ) -> List[AttributionTouch]:
        """Build unified touchpoint list from all data sources."""
        touches = []

        # Create GCLID lookup for efficient matching
        gclid_lookup = {mapping.gclid: mapping for mapping in gclid_mappings}

        # Process Google Ads clicks
        for _, ads_row in google_ads_data.iterrows():
            gclid = ads_row.get("gclid")
            mapping = gclid_lookup.get(gclid) if gclid else None

            # Determine customer ID (use mapping's customer data if available)
            customer_id = ads_row.get("customer_id", "unknown")

            touch = AttributionTouch(
                customer_id=customer_id,
                touchpoint_type=TouchpointType.GOOGLE_ADS_CLICK,
                timestamp=ads_row["click_timestamp"],
                gclid=gclid,
                campaign_id=ads_row["campaign_id"],
                campaign_name=ads_row["campaign_name"],
                ad_group_id=ads_row["ad_group_id"],
                keyword_id=ads_row.get("keyword_id"),
                search_term=ads_row.get("search_term"),
                source="google",
                medium="cpc",
                country=ads_row.get("geo_target"),
                device_category=ads_row.get("device"),
                landing_page=ads_row.get("landing_page_url"),
                is_conversion_touch=ads_row.get("conversions", 0) > 0,
                conversion_value=ads_row.get("conversion_value", 0.0),
            )

            # Add GA4 session ID if we have a mapping
            if mapping and mapping.ga4_session_id:
                touch.ga4_session_id = mapping.ga4_session_id
                touch.ga4_user_id = mapping.ga4_user_id

            touches.append(touch)

        # Process GA4 sessions
        for _, ga4_row in ga4_data.iterrows():
            gclid = ga4_row.get("gclid")

            # Skip if this session was already captured via Google Ads (has gclid and mapping)
            if gclid and gclid in gclid_lookup:
                continue  # Already captured in Google Ads processing

            # Determine customer ID
            customer_id = ga4_row.get("userId", "unknown")

            # Determine conversion details
            is_converting = ga4_row.get("conversions", 0) > 0
            conversion_value = ga4_row.get("totalRevenue", 0.0)

            touch = AttributionTouch(
                customer_id=customer_id,
                touchpoint_type=TouchpointType.GA4_SESSION,
                timestamp=ga4_row.get("session_start", datetime.utcnow()),
                ga4_session_id=ga4_row.get("sessionId"),
                ga4_user_id=ga4_row.get("userId"),
                source=ga4_row.get("source", ""),
                medium=ga4_row.get("medium", ""),
                landing_page=ga4_row.get("landingPage"),
                country=ga4_row.get("country"),
                device_category=ga4_row.get("deviceCategory"),
                is_conversion_touch=is_converting,
                conversion_value=conversion_value,
            )

            # Set conversion type based on GA4 data
            if is_converting:
                if "purchase" in str(ga4_row.get("eventName", "")).lower():
                    touch.conversion_type = ConversionType.PURCHASE
                elif "lead" in str(ga4_row.get("eventName", "")).lower():
                    touch.conversion_type = ConversionType.LEAD_FORM
                elif "call" in str(ga4_row.get("eventName", "")).lower():
                    touch.conversion_type = ConversionType.PHONE_CALL
                else:
                    touch.conversion_type = ConversionType.CUSTOM

            touches.append(touch)

        logger.info(f"Built {len(touches)} unified touchpoints")
        return touches

    def _group_into_journeys(
        self, touches: List[AttributionTouch], include_non_converting: bool = False
    ) -> Tuple[List[CustomerJourney], Dict[str, List[AttributionTouch]]]:
        """Group touchpoints into customer journeys.

        Args:
            touches: All touchpoints to group
            include_non_converting: Whether to include journeys without conversions

        Returns:
            Tuple of (journeys, touchpoints_by_journey_id)
        """
        if not touches:
            return [], {}

        # Group by customer_id first
        customer_touches = {}
        for touch in touches:
            if touch.customer_id not in customer_touches:
                customer_touches[touch.customer_id] = []
            customer_touches[touch.customer_id].append(touch)

        journeys = []
        journey_touches = {}

        for customer_id, cust_touches in customer_touches.items():
            # Sort touches by timestamp
            cust_touches.sort(key=lambda x: x.timestamp)

            # Split into separate journeys based on session timeouts and conversions
            customer_journeys = self._split_customer_journeys(cust_touches)

            for journey_touches_list in customer_journeys:
                if not journey_touches_list:
                    continue

                # Check if journey has conversion
                has_conversion = any(
                    touch.is_conversion_touch for touch in journey_touches_list
                )

                if not has_conversion and not include_non_converting:
                    continue

                # Create journey
                journey = self._create_journey_from_touches(journey_touches_list)

                if journey:
                    journeys.append(journey)
                    journey_touches[journey.journey_id] = journey_touches_list

                    # Update journey_id on all touches
                    for touch in journey_touches_list:
                        touch.customer_journey_id = journey.journey_id

        return journeys, journey_touches

    def _split_customer_journeys(
        self, customer_touches: List[AttributionTouch]
    ) -> List[List[AttributionTouch]]:
        """Split customer touches into separate journeys based on timeouts."""
        if not customer_touches:
            return []

        journeys = []
        current_journey = []

        for i, touch in enumerate(customer_touches):
            if not current_journey:
                current_journey.append(touch)
                continue

            # Check time gap from last touch
            time_gap = (
                touch.timestamp - current_journey[-1].timestamp
            ).total_seconds() / 60

            # Start new journey if:
            # 1. Time gap exceeds session timeout
            # 2. Previous touch was a conversion
            # 3. Journey length exceeds maximum days
            journey_duration = (touch.timestamp - current_journey[0].timestamp).days

            should_start_new_journey = (
                time_gap > self.session_timeout_minutes
                or current_journey[-1].is_conversion_touch
                or journey_duration > self.max_journey_length_days
            )

            if should_start_new_journey:
                # Finish current journey
                journeys.append(current_journey)
                current_journey = [touch]
            else:
                # Continue current journey
                current_journey.append(touch)

        # Add final journey
        if current_journey:
            journeys.append(current_journey)

        return journeys

    def _create_journey_from_touches(
        self, touches: List[AttributionTouch]
    ) -> Optional[CustomerJourney]:
        """Create customer journey from touchpoints."""
        if not touches:
            return None

        # Sort by timestamp
        touches.sort(key=lambda x: x.timestamp)

        first_touch = touches[0]
        last_touch = touches[-1]

        # Find conversion touch
        conversion_touch = next(
            (touch for touch in reversed(touches) if touch.is_conversion_touch), None
        )

        # Calculate journey metrics
        total_sessions = len(
            set(touch.ga4_session_id for touch in touches if touch.ga4_session_id)
        )
        total_pageviews = sum(touch.page_views or 0 for touch in touches)
        total_engagement = sum(touch.engagement_time_msec or 0 for touch in touches)

        # Journey classification
        unique_sources = set(touch.source for touch in touches if touch.source)
        unique_devices = set(
            touch.device_category for touch in touches if touch.device_category
        )
        unique_countries = set(touch.country for touch in touches if touch.country)

        # Create journey
        journey = CustomerJourney(
            customer_id=first_touch.customer_id,
            first_touch=first_touch.timestamp,
            last_touch=last_touch.timestamp,
            conversion_timestamp=conversion_touch.timestamp
            if conversion_touch
            else None,
            total_touches=len(touches),
            total_sessions=max(1, total_sessions),
            total_pageviews=total_pageviews,
            total_engagement_time_msec=total_engagement,
            converted=conversion_touch is not None,
            conversion_type=conversion_touch.conversion_type
            if conversion_touch
            else None,
            conversion_value=conversion_touch.conversion_value
            if conversion_touch
            else 0.0,
            attribution_model=AttributionModelType.LINEAR,  # Default, will be updated
            is_multi_session=total_sessions > 1,
            is_multi_device=len(unique_devices) > 1,
            is_multi_channel=len(unique_sources) > 1,
            first_touch_source=first_touch.source or "",
            first_touch_medium=first_touch.medium or "",
            first_touch_campaign=first_touch.campaign_name,
            last_touch_source=last_touch.source or "",
            last_touch_medium=last_touch.medium or "",
            last_touch_campaign=last_touch.campaign_name,
            countries_visited=list(unique_countries),
            devices_used=list(unique_devices),
        )

        return journey

    async def enrich_with_store_visits(
        self,
        journeys: List[CustomerJourney],
        journey_touches: Dict[str, List[AttributionTouch]],
    ) -> Tuple[List[CustomerJourney], Dict[str, List[AttributionTouch]]]:
        """Enrich journeys with store visit data if available."""
        try:
            # Query for store visits in the journey periods
            for journey in journeys:
                store_visits = await self._get_store_visits_for_customer(
                    journey.customer_id,
                    journey.first_touch,
                    journey.last_touch
                    + timedelta(days=7),  # Look ahead for delayed visits
                )

                if store_visits:
                    # Add store visit touches
                    for visit in store_visits:
                        store_touch = AttributionTouch(
                            customer_id=journey.customer_id,
                            customer_journey_id=journey.journey_id,
                            touchpoint_type=TouchpointType.STORE_VISIT,
                            timestamp=visit["visit_timestamp"],
                            store_location_id=visit["store_id"],
                            country=visit.get("country"),
                            is_conversion_touch=visit.get("purchase_made", False),
                            conversion_value=visit.get("purchase_amount", 0.0),
                            conversion_type=ConversionType.STORE_VISIT,
                        )

                        journey_touches[journey.journey_id].append(store_touch)

                    # Update journey metadata
                    journey.stores_visited = [v["store_id"] for v in store_visits]
                    journey.total_touches += len(store_visits)

            return journeys, journey_touches

        except Exception as e:
            logger.warning(f"Failed to enrich with store visits: {e}")
            return journeys, journey_touches

    async def _get_store_visits_for_customer(
        self,
        customer_id: str,
        start_date: datetime,
        end_date: datetime,
    ) -> List[Dict]:
        """Get store visit data for customer in date range."""
        # This would query store visit data from BigQuery or another source
        # For now, return empty list as store visit data integration
        # would require additional setup
        return []

    def identify_cross_device_journeys(
        self,
        journeys: List[CustomerJourney],
        journey_touches: Dict[str, List[AttributionTouch]],
    ) -> List[str]:
        """Identify journeys that span multiple devices."""
        cross_device_journeys = []

        for journey in journeys:
            touches = journey_touches.get(journey.journey_id, [])

            # Check if multiple device categories are present
            devices = set(
                touch.device_category for touch in touches if touch.device_category
            )

            if len(devices) > 1:
                cross_device_journeys.append(journey.journey_id)

                # Update journey metadata
                journey.is_multi_device = True
                journey.devices_used = list(devices)

        logger.info(f"Identified {len(cross_device_journeys)} cross-device journeys")
        return cross_device_journeys

    def identify_assisted_conversions(
        self,
        journeys: List[CustomerJourney],
        journey_touches: Dict[str, List[AttributionTouch]],
        assist_window_hours: int = 24,
    ) -> Dict[str, List[str]]:
        """Identify assisted conversions where one channel helps another convert.

        Args:
            journeys: Customer journeys
            journey_touches: Touchpoints by journey ID
            assist_window_hours: Time window to consider assists

        Returns:
            Assisted conversions by assisting channel
        """
        assisted_conversions = {}

        for journey in journeys:
            if not journey.converted:
                continue

            touches = journey_touches.get(journey.journey_id, [])
            if len(touches) < 2:
                continue  # Need multiple touches for assists

            # Find conversion touch
            conversion_touch = next(
                (t for t in reversed(touches) if t.is_conversion_touch), None
            )

            if not conversion_touch:
                continue

            # Find assisting touches within time window
            assist_cutoff = conversion_touch.timestamp - timedelta(
                hours=assist_window_hours
            )

            assisting_touches = [
                touch
                for touch in touches
                if touch.timestamp >= assist_cutoff
                and touch.timestamp < conversion_touch.timestamp
                and not touch.is_conversion_touch
            ]

            # Group assists by channel
            for assist_touch in assisting_touches:
                assist_channel = f"{assist_touch.source}/{assist_touch.medium}"
                conversion_channel = (
                    f"{conversion_touch.source}/{conversion_touch.medium}"
                )

                assist_key = f"{assist_channel} → {conversion_channel}"

                if assist_key not in assisted_conversions:
                    assisted_conversions[assist_key] = []

                assisted_conversions[assist_key].append(journey.journey_id)

        return assisted_conversions

    def calculate_path_analysis(
        self,
        journeys: List[CustomerJourney],
        journey_touches: Dict[str, List[AttributionTouch]],
        min_path_length: int = 2,
    ) -> Dict[str, Dict[str, any]]:
        """Analyze customer journey paths to identify optimal sequences.

        Args:
            journeys: Customer journeys
            journey_touches: Touchpoints by journey ID
            min_path_length: Minimum path length to analyze

        Returns:
            Path analysis results
        """
        path_performance = {}

        for journey in journeys:
            touches = journey_touches.get(journey.journey_id, [])

            if len(touches) < min_path_length:
                continue

            # Build path sequence
            path_sequence = []
            for touch in sorted(touches, key=lambda x: x.timestamp):
                touchpoint_key = f"{touch.source}/{touch.medium}"
                path_sequence.append(touchpoint_key)

            path_key = " → ".join(path_sequence)

            if path_key not in path_performance:
                path_performance[path_key] = {
                    "path": path_key,
                    "total_journeys": 0,
                    "converting_journeys": 0,
                    "total_revenue": 0.0,
                    "avg_journey_length_days": 0.0,
                    "avg_touches": 0.0,
                }

            perf = path_performance[path_key]
            perf["total_journeys"] += 1

            if journey.converted:
                perf["converting_journeys"] += 1
                perf["total_revenue"] += journey.conversion_value

            perf["avg_journey_length_days"] = (
                perf["avg_journey_length_days"] * (perf["total_journeys"] - 1)
                + journey.journey_length_days
            ) / perf["total_journeys"]

            perf["avg_touches"] = (
                perf["avg_touches"] * (perf["total_journeys"] - 1) + len(touches)
            ) / perf["total_journeys"]

        # Calculate conversion rates and metrics
        for path_key, perf in path_performance.items():
            if perf["total_journeys"] > 0:
                perf["conversion_rate"] = (
                    perf["converting_journeys"] / perf["total_journeys"]
                )
                perf["avg_revenue_per_conversion"] = (
                    perf["total_revenue"] / perf["converting_journeys"]
                    if perf["converting_journeys"] > 0
                    else 0.0
                )

        return path_performance

    def detect_anomalies_in_journeys(
        self,
        journeys: List[CustomerJourney],
        journey_touches: Dict[str, List[AttributionTouch]],
    ) -> List[Dict[str, any]]:
        """Detect anomalies in customer journey patterns."""
        anomalies = []

        if not journeys:
            return anomalies

        # Calculate baseline metrics
        journey_lengths = [j.journey_length_days for j in journeys]
        touch_counts = [j.total_touches for j in journeys]
        conversion_values = [j.conversion_value for j in journeys if j.converted]

        avg_length = sum(journey_lengths) / len(journey_lengths)
        avg_touches = sum(touch_counts) / len(touch_counts)
        avg_conversion_value = (
            sum(conversion_values) / len(conversion_values)
            if conversion_values
            else 0.0
        )

        # Detect anomalies
        for journey in journeys:
            # Unusually long journeys
            if journey.journey_length_days > avg_length * 3:
                anomalies.append(
                    {
                        "journey_id": journey.journey_id,
                        "type": "unusually_long_journey",
                        "severity": "medium",
                        "description": f"Journey length {journey.journey_length_days:.1f} days is {journey.journey_length_days / avg_length:.1f}x longer than average",
                        "metric_value": journey.journey_length_days,
                        "baseline_value": avg_length,
                    }
                )

            # Unusually high number of touches
            if journey.total_touches > avg_touches * 2.5:
                anomalies.append(
                    {
                        "journey_id": journey.journey_id,
                        "type": "high_touch_count",
                        "severity": "low",
                        "description": f"Journey has {journey.total_touches} touches, {journey.total_touches / avg_touches:.1f}x higher than average",
                        "metric_value": journey.total_touches,
                        "baseline_value": avg_touches,
                    }
                )

            # Unusually high conversion value
            if (
                journey.converted
                and journey.conversion_value > avg_conversion_value * 5
            ):
                anomalies.append(
                    {
                        "journey_id": journey.journey_id,
                        "type": "high_value_conversion",
                        "severity": "high",
                        "description": f"Conversion value ${journey.conversion_value:.2f} is {journey.conversion_value / avg_conversion_value:.1f}x higher than average",
                        "metric_value": journey.conversion_value,
                        "baseline_value": avg_conversion_value,
                    }
                )

            # Same-source/medium journey (potential bot traffic)
            touches = journey_touches.get(journey.journey_id, [])
            unique_sources = set(touch.source for touch in touches if touch.source)

            if len(touches) > 5 and len(unique_sources) == 1:
                anomalies.append(
                    {
                        "journey_id": journey.journey_id,
                        "type": "single_source_high_touch",
                        "severity": "medium",
                        "description": f"Journey has {len(touches)} touches from single source '{list(unique_sources)[0]}' - potential bot traffic",
                        "metric_value": len(touches),
                        "baseline_value": 1,
                    }
                )

        logger.info(f"Detected {len(anomalies)} journey anomalies")
        return anomalies

    async def validate_journey_data_quality(
        self,
        journeys: List[CustomerJourney],
        journey_touches: Dict[str, List[AttributionTouch]],
    ) -> Dict[str, any]:
        """Validate quality of journey data and GCLID matching."""
        quality_metrics = {
            "total_journeys": len(journeys),
            "converting_journeys": sum(1 for j in journeys if j.converted),
            "avg_journey_length_days": 0.0,
            "avg_touches_per_journey": 0.0,
            "gclid_match_rate": 0.0,
            "multi_touch_rate": 0.0,
            "cross_device_rate": 0.0,
            "data_quality_score": 0.0,
        }

        if not journeys:
            return quality_metrics

        # Calculate basic metrics
        quality_metrics["avg_journey_length_days"] = sum(
            j.journey_length_days for j in journeys
        ) / len(journeys)
        quality_metrics["avg_touches_per_journey"] = sum(
            j.total_touches for j in journeys
        ) / len(journeys)

        # Calculate quality rates
        total_touches = sum(len(touches) for touches in journey_touches.values())
        gclid_touches = sum(
            1
            for touches in journey_touches.values()
            for touch in touches
            if touch.gclid
        )

        quality_metrics["gclid_match_rate"] = (
            gclid_touches / total_touches if total_touches > 0 else 0.0
        )

        quality_metrics["multi_touch_rate"] = sum(
            1 for j in journeys if j.total_touches > 1
        ) / len(journeys)

        quality_metrics["cross_device_rate"] = sum(
            1 for j in journeys if j.is_multi_device
        ) / len(journeys)

        # Calculate overall data quality score (0.0-1.0)
        quality_score = (
            quality_metrics["gclid_match_rate"] * 0.4  # 40% weight on GCLID matching
            + quality_metrics["multi_touch_rate"] * 0.3  # 30% weight on multi-touch
            + quality_metrics["cross_device_rate"] * 0.2  # 20% weight on cross-device
            + (quality_metrics["avg_touches_per_journey"] / 10.0)
            * 0.1  # 10% weight on touch richness
        )
        quality_metrics["data_quality_score"] = min(1.0, quality_score)

        return quality_metrics

    def get_journey_insights(
        self,
        journeys: List[CustomerJourney],
        journey_touches: Dict[str, List[AttributionTouch]],
    ) -> Dict[str, any]:
        """Generate insights about customer journey patterns."""
        insights = {}

        if not journeys:
            return insights

        # Journey length analysis
        journey_lengths = [j.journey_length_days for j in journeys]
        insights["journey_length_distribution"] = {
            "same_day": sum(1 for length in journey_lengths if length < 1),
            "1_3_days": sum(1 for length in journey_lengths if 1 <= length < 3),
            "3_7_days": sum(1 for length in journey_lengths if 3 <= length < 7),
            "7_30_days": sum(1 for length in journey_lengths if 7 <= length < 30),
            "30_plus_days": sum(1 for length in journey_lengths if length >= 30),
        }

        # Touch count analysis
        touch_counts = [j.total_touches for j in journeys]
        insights["touch_count_distribution"] = {
            "single_touch": sum(1 for count in touch_counts if count == 1),
            "2_5_touches": sum(1 for count in touch_counts if 2 <= count <= 5),
            "6_10_touches": sum(1 for count in touch_counts if 6 <= count <= 10),
            "10_plus_touches": sum(1 for count in touch_counts if count > 10),
        }

        # Channel analysis
        first_touch_channels = {}
        last_touch_channels = {}

        for journey in journeys:
            first_channel = f"{journey.first_touch_source}/{journey.first_touch_medium}"
            last_channel = f"{journey.last_touch_source}/{journey.last_touch_medium}"

            first_touch_channels[first_channel] = (
                first_touch_channels.get(first_channel, 0) + 1
            )
            last_touch_channels[last_channel] = (
                last_touch_channels.get(last_channel, 0) + 1
            )

        insights["first_touch_channel_distribution"] = dict(
            sorted(first_touch_channels.items(), key=lambda x: x[1], reverse=True)[:10]
        )
        insights["last_touch_channel_distribution"] = dict(
            sorted(last_touch_channels.items(), key=lambda x: x[1], reverse=True)[:10]
        )

        # Conversion analysis
        converting_journeys = [j for j in journeys if j.converted]
        if converting_journeys:
            insights["conversion_insights"] = {
                "conversion_rate": len(converting_journeys) / len(journeys),
                "avg_conversion_value": sum(
                    j.conversion_value for j in converting_journeys
                )
                / len(converting_journeys),
                "total_attributed_revenue": sum(
                    j.total_attributed_revenue for j in converting_journeys
                ),
            }

        return insights
