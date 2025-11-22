"""Trend analysis for audit metrics over time."""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np
from scipy import signal
from sklearn.linear_model import LinearRegression

from paidsearchnav.storage.api_repository import APIRepository

from .models import (
    AuditResult,
    MetricType,
    TrendAnalysis,
    TrendDataPoint,
    TrendGranularity,
)

logger = logging.getLogger(__name__)


class TrendAnalyzer:
    """Analyze trends in audit metrics over time."""

    def __init__(self, repository: APIRepository):
        """Initialize the trend analyzer."""
        self.repository = repository

    async def generate_trend_analysis(
        self,
        customer_id: str,
        metric_types: List[MetricType],
        start_date: datetime,
        end_date: datetime,
        granularity: TrendGranularity = TrendGranularity.MONTHLY,
        include_forecast: bool = False,
        forecast_periods: int = 3,
    ) -> Dict[MetricType, TrendAnalysis]:
        """Generate trend analysis for specified metrics over time period."""
        # Fetch all audit results in date range
        audits = await self._get_audits_in_range(customer_id, start_date, end_date)

        if not audits:
            logger.warning(f"No audits found for customer {customer_id} in date range")
            return {}

        # Group audits by granularity
        grouped_audits = self._group_audits_by_granularity(audits, granularity)

        # Analyze each metric
        results = {}
        for metric_type in metric_types:
            analysis = self._analyze_metric_trend(
                customer_id,
                metric_type,
                grouped_audits,
                start_date,
                end_date,
                granularity,
            )

            # Add forecast if requested
            if include_forecast and len(analysis.data_points) >= 3:
                analysis.forecast = self._generate_forecast(
                    analysis.data_points, forecast_periods, granularity
                )

            # Detect seasonality
            if len(analysis.data_points) >= 12:  # Need at least a year of data
                analysis.seasonality_detected = self._detect_seasonality(
                    analysis.data_points
                )

            # Add insights
            analysis.insights = self._generate_trend_insights(analysis)

            results[metric_type] = analysis

        return results

    def _analyze_metric_trend(
        self,
        customer_id: str,
        metric_type: MetricType,
        grouped_audits: Dict[str, List[AuditResult]],
        start_date: datetime,
        end_date: datetime,
        granularity: TrendGranularity,
    ) -> TrendAnalysis:
        """Analyze trend for a specific metric."""
        data_points = []

        for period_key, audits in sorted(grouped_audits.items()):
            # Get the most recent audit for this period
            latest_audit = max(audits, key=lambda a: a.created_at)

            # Extract metric value
            value = self._extract_metric_value(latest_audit, metric_type)

            if value is not None:
                data_point = TrendDataPoint(
                    timestamp=latest_audit.created_at,
                    value=value,
                    metric_type=metric_type,
                )
                data_points.append(data_point)

        # Calculate trend direction and strength
        trend_direction, trend_strength = self._calculate_trend(data_points)

        # Detect anomalies
        anomalies = self._detect_anomalies(data_points)
        for dp, is_anomaly, score in anomalies:
            dp.is_anomaly = is_anomaly
            dp.anomaly_score = score

        return TrendAnalysis(
            customer_id=customer_id,
            metric_type=metric_type,
            start_date=start_date,
            end_date=end_date,
            granularity=granularity,
            data_points=data_points,
            trend_direction=trend_direction,
            trend_strength=trend_strength,
            anomalies_detected=sum(1 for dp in data_points if dp.is_anomaly),
        )

    def _extract_metric_value(
        self, audit: AuditResult, metric_type: MetricType
    ) -> Optional[float]:
        """Extract specific metric value from audit result."""
        metrics = audit.summary.get("metrics", {})

        # Map metric types to audit result fields
        metric_mapping = {
            MetricType.TOTAL_SPEND: "total_spend",
            MetricType.WASTED_SPEND: "wasted_spend",
            MetricType.COST_PER_CONVERSION: "cost_per_conversion",
            MetricType.ROAS: "roas",
            MetricType.CTR: "ctr",
            MetricType.CONVERSION_RATE: "conversion_rate",
            MetricType.QUALITY_SCORE: "avg_quality_score",
            MetricType.IMPRESSIONS: "impressions",
            MetricType.CLICKS: "clicks",
            MetricType.CONVERSIONS: "conversions",
            MetricType.KEYWORDS_ANALYZED: "keywords_analyzed",
            MetricType.ISSUES_COUNT: "total_issues",
        }

        field_name = metric_mapping.get(metric_type)
        if field_name:
            if field_name == "total_issues":
                return audit.summary.get(field_name, 0)
            return metrics.get(field_name)

        return None

    def _group_audits_by_granularity(
        self, audits: List[AuditResult], granularity: TrendGranularity
    ) -> Dict[str, List[AuditResult]]:
        """Group audits by specified time granularity."""
        grouped = {}

        for audit in audits:
            period_key = self._get_period_key(audit.created_at, granularity)
            if period_key not in grouped:
                grouped[period_key] = []
            grouped[period_key].append(audit)

        return grouped

    def _get_period_key(self, date: datetime, granularity: TrendGranularity) -> str:
        """Get period key for grouping based on granularity."""
        if granularity == TrendGranularity.DAILY:
            return date.strftime("%Y-%m-%d")
        elif granularity == TrendGranularity.WEEKLY:
            # Get week start (Monday)
            week_start = date - timedelta(days=date.weekday())
            return week_start.strftime("%Y-W%U")
        elif granularity == TrendGranularity.MONTHLY:
            return date.strftime("%Y-%m")
        elif granularity == TrendGranularity.QUARTERLY:
            quarter = (date.month - 1) // 3 + 1
            return f"{date.year}-Q{quarter}"
        else:
            return date.strftime("%Y-%m-%d")

    def _calculate_trend(self, data_points: List[TrendDataPoint]) -> Tuple[str, float]:
        """Calculate trend direction and strength using linear regression."""
        if len(data_points) < 2:
            return "stable", 0.0

        # Prepare data for regression
        X = np.array(range(len(data_points))).reshape(-1, 1)
        y = np.array([dp.value for dp in data_points])

        # Fit linear regression
        model = LinearRegression()
        model.fit(X, y)

        # Calculate trend strength (R-squared)
        r_squared = model.score(X, y)

        # Determine trend direction based on slope
        slope = model.coef_[0]
        if abs(slope) < 0.01:  # Threshold for "stable"
            direction = "stable"
        elif slope > 0:
            direction = "increasing"
        else:
            direction = "decreasing"

        return direction, abs(r_squared)

    def _detect_anomalies(
        self, data_points: List[TrendDataPoint], z_threshold: float = 2.5
    ) -> List[Tuple[TrendDataPoint, bool, float]]:
        """Detect anomalies using z-score method."""
        if len(data_points) < 3:
            return [(dp, False, 0.0) for dp in data_points]

        values = np.array([dp.value for dp in data_points])

        # Calculate z-scores
        mean = np.mean(values)
        std = np.std(values)

        if std == 0:
            return [(dp, False, 0.0) for dp in data_points]

        results = []
        for i, dp in enumerate(data_points):
            z_score = abs((dp.value - mean) / std)
            is_anomaly = z_score > z_threshold
            results.append((dp, is_anomaly, z_score))

        return results

    def _detect_seasonality(
        self, data_points: List[TrendDataPoint], min_periods: int = 12
    ) -> bool:
        """Detect if there's seasonality in the data using autocorrelation."""
        if len(data_points) < min_periods:
            return False

        values = np.array([dp.value for dp in data_points])

        # Detrend the data
        detrended = signal.detrend(values)

        # Calculate autocorrelation
        autocorr = np.correlate(detrended, detrended, mode="full")
        autocorr = autocorr[len(autocorr) // 2 :]
        autocorr = autocorr / autocorr[0]  # Normalize

        # Look for significant peaks in autocorrelation
        # Check for yearly (12 months) or quarterly (3 months) seasonality
        seasonal_lags = [3, 4, 12]  # Quarterly, tri-annual, yearly
        for lag in seasonal_lags:
            if lag < len(autocorr) and autocorr[lag] > 0.3:  # Threshold
                return True

        return False

    def _generate_forecast(
        self,
        data_points: List[TrendDataPoint],
        forecast_periods: int,
        granularity: TrendGranularity,
    ) -> List[TrendDataPoint]:
        """Generate forecast using simple linear regression."""
        if len(data_points) < 3:
            return []

        # Prepare data
        X = np.array(range(len(data_points))).reshape(-1, 1)
        y = np.array([dp.value for dp in data_points])

        # Fit model
        model = LinearRegression()
        model.fit(X, y)

        # Generate forecast
        forecast_points = []
        last_timestamp = data_points[-1].timestamp

        for i in range(1, forecast_periods + 1):
            # Calculate next timestamp based on granularity
            if granularity == TrendGranularity.DAILY:
                next_timestamp = last_timestamp + timedelta(days=i)
            elif granularity == TrendGranularity.WEEKLY:
                next_timestamp = last_timestamp + timedelta(weeks=i)
            elif granularity == TrendGranularity.MONTHLY:
                next_timestamp = last_timestamp + timedelta(days=30 * i)
            elif granularity == TrendGranularity.QUARTERLY:
                next_timestamp = last_timestamp + timedelta(days=90 * i)
            else:
                next_timestamp = last_timestamp + timedelta(days=i)

            # Predict value
            future_x = len(data_points) + i - 1
            predicted_value = model.predict([[future_x]])[0]

            forecast_points.append(
                TrendDataPoint(
                    timestamp=next_timestamp,
                    value=max(0, predicted_value),  # Ensure non-negative
                    metric_type=data_points[0].metric_type,
                )
            )

        return forecast_points

    def _generate_trend_insights(self, analysis: TrendAnalysis) -> List[str]:
        """Generate insights about the trend."""
        insights = []

        # Trend direction insight
        if analysis.trend_strength > 0.7:
            strength_desc = "strong"
        elif analysis.trend_strength > 0.4:
            strength_desc = "moderate"
        else:
            strength_desc = "weak"

        if analysis.trend_direction != "stable":
            insights.append(
                f"{analysis.metric_type.value} shows a {strength_desc} "
                f"{analysis.trend_direction} trend"
            )

        # Anomaly insights
        if analysis.anomalies_detected > 0:
            anomaly_dates = [
                dp.timestamp.strftime("%Y-%m-%d")
                for dp in analysis.data_points
                if dp.is_anomaly
            ]
            insights.append(
                f"{analysis.anomalies_detected} anomalies detected on: "
                f"{', '.join(anomaly_dates[:3])}"
            )

        # Seasonality insight
        if analysis.seasonality_detected:
            insights.append(
                f"Seasonal pattern detected in {analysis.metric_type.value}"
            )

        # Forecast insight
        if analysis.forecast:
            last_actual = analysis.data_points[-1].value
            last_forecast = analysis.forecast[-1].value
            change_pct = ((last_forecast - last_actual) / last_actual) * 100

            if abs(change_pct) > 5:
                direction = "increase" if change_pct > 0 else "decrease"
                insights.append(
                    f"Forecast suggests {abs(change_pct):.1f}% {direction} "
                    f"over next {len(analysis.forecast)} periods"
                )

        return insights

    async def _get_audits_in_range(
        self, customer_id: str, start_date: datetime, end_date: datetime
    ) -> List[AuditResult]:
        """Fetch all audit results for customer in date range."""
        try:
            # TODO: Implement actual audit fetching when repository method is available
            # For now, return empty list
            logger.warning(
                f"Audit list fetching not implemented. Returning empty list for customer {customer_id}"
            )
            return []
        except Exception as e:
            logger.error(f"Error fetching audits for trend analysis: {e}")
            return []
