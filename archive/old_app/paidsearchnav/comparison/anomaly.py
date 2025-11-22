"""Anomaly detection for audit metrics."""

import logging
from datetime import datetime
from typing import List, Optional, Tuple

import numpy as np

from .models import AnomalyAlert, MetricType, TrendDataPoint

logger = logging.getLogger(__name__)


class AnomalyDetector:
    """Detect anomalies in audit metrics using statistical methods."""

    def __init__(
        self,
        z_score_threshold: float = 2.5,
        iqr_multiplier: float = 1.5,
        min_historical_points: int = 5,
    ):
        """Initialize anomaly detector with configurable thresholds."""
        self.z_score_threshold = z_score_threshold
        self.iqr_multiplier = iqr_multiplier
        self.min_historical_points = min_historical_points

    def detect_anomalies(
        self,
        current_value: float,
        historical_values: List[float],
        metric_type: MetricType,
        timestamp: datetime,
    ) -> Optional[AnomalyAlert]:
        """Detect if current value is anomalous compared to historical data."""
        if len(historical_values) < self.min_historical_points:
            return None

        # Use multiple detection methods
        z_score_anomaly = self._detect_z_score_anomaly(current_value, historical_values)
        iqr_anomaly = self._detect_iqr_anomaly(current_value, historical_values)
        trend_anomaly = self._detect_trend_anomaly(
            current_value, historical_values, timestamp
        )

        # Combine detection methods
        is_anomaly = z_score_anomaly[0] or iqr_anomaly[0] or trend_anomaly[0]

        if not is_anomaly:
            return None

        # Calculate expected value and deviation
        expected_value = np.mean(historical_values)
        deviation_pct = ((current_value - expected_value) / expected_value) * 100

        # Determine severity
        severity = self._determine_severity(
            deviation_pct, z_score_anomaly[1], metric_type
        )

        # Generate possible causes
        possible_causes = self._generate_possible_causes(
            metric_type, deviation_pct, timestamp
        )

        # Generate recommended actions
        recommended_actions = self._generate_recommended_actions(
            metric_type, deviation_pct, severity
        )

        return AnomalyAlert(
            metric_type=metric_type,
            timestamp=timestamp,
            expected_value=expected_value,
            actual_value=current_value,
            deviation_percentage=deviation_pct,
            severity=severity,
            possible_causes=possible_causes,
            recommended_actions=recommended_actions,
        )

    def _detect_z_score_anomaly(
        self, current_value: float, historical_values: List[float]
    ) -> Tuple[bool, float]:
        """Detect anomaly using z-score method."""
        mean = np.mean(historical_values)
        std = np.std(historical_values)

        if std == 0:
            return False, 0.0

        z_score = abs((current_value - mean) / std)
        is_anomaly = z_score > self.z_score_threshold

        return bool(is_anomaly), z_score

    def _detect_iqr_anomaly(
        self, current_value: float, historical_values: List[float]
    ) -> Tuple[bool, float]:
        """Detect anomaly using Interquartile Range (IQR) method."""
        q1 = np.percentile(historical_values, 25)
        q3 = np.percentile(historical_values, 75)
        iqr = q3 - q1

        lower_bound = q1 - (self.iqr_multiplier * iqr)
        upper_bound = q3 + (self.iqr_multiplier * iqr)

        is_anomaly = current_value < lower_bound or current_value > upper_bound

        # Calculate how far outside the bounds
        if current_value < lower_bound:
            deviation = (lower_bound - current_value) / iqr
        elif current_value > upper_bound:
            deviation = (current_value - upper_bound) / iqr
        else:
            deviation = 0.0

        return bool(is_anomaly), deviation

    def _detect_trend_anomaly(
        self,
        current_value: float,
        historical_values: List[float],
        timestamp: datetime,
    ) -> Tuple[bool, float]:
        """Detect anomaly based on trend deviation."""
        if len(historical_values) < 3:
            return False, 0.0

        # Fit a simple linear trend
        x = np.arange(len(historical_values))
        y = np.array(historical_values)

        # Calculate trend line
        z = np.polyfit(x, y, 1)
        p = np.poly1d(z)

        # Predict next value based on trend
        predicted_value = p(len(historical_values))

        # Calculate residuals of historical data
        residuals = y - p(x)
        residual_std = np.std(residuals)

        # For perfect linear trends, use a minimum threshold based on data range
        if residual_std < 1e-6:
            # Use 5% of the data range as the minimum standard deviation
            data_range = np.max(y) - np.min(y)
            residual_std = max(residual_std, data_range * 0.05)

        # Check if current value deviates significantly from trend
        current_residual = current_value - predicted_value
        deviation = abs(current_residual) / residual_std

        is_anomaly = deviation > 2.0  # 2 standard deviations from trend

        return bool(is_anomaly), deviation

    def _determine_severity(
        self, deviation_pct: float, z_score: float, metric_type: MetricType
    ) -> str:
        """Determine severity level of the anomaly."""
        # Different metrics have different sensitivity levels
        critical_metrics = [
            MetricType.CONVERSIONS,
            MetricType.CONVERSION_RATE,
            MetricType.ROAS,
        ]
        high_sensitivity_metrics = [
            MetricType.CTR,
            MetricType.COST_PER_CONVERSION,
            MetricType.WASTED_SPEND,
        ]

        # Base severity on deviation and metric importance
        if metric_type in critical_metrics:
            if abs(deviation_pct) > 50 or z_score > 4:
                return "critical"
            elif abs(deviation_pct) > 30 or z_score > 3:
                return "high"
            elif abs(deviation_pct) > 20 or z_score > 2.5:
                return "medium"
            else:
                return "low"
        elif metric_type in high_sensitivity_metrics:
            if abs(deviation_pct) > 75 or z_score > 4.5:
                return "critical"
            elif abs(deviation_pct) > 50 or z_score > 3.5:
                return "high"
            elif abs(deviation_pct) > 30 or z_score > 2.5:
                return "medium"
            else:
                return "low"
        else:
            if abs(deviation_pct) > 100 or z_score > 5:
                return "critical"
            elif abs(deviation_pct) > 75 or z_score > 4:
                return "high"
            elif abs(deviation_pct) > 50 or z_score > 3:
                return "medium"
            else:
                return "low"

    def _generate_possible_causes(
        self, metric_type: MetricType, deviation_pct: float, timestamp: datetime
    ) -> List[str]:
        """Generate possible causes for the anomaly."""
        causes = []

        # Check if it's a weekend/holiday effect
        if timestamp.weekday() >= 5:  # Saturday or Sunday
            causes.append("Weekend traffic patterns may differ from weekdays")

        # Check for beginning/end of month
        if timestamp.day <= 3 or timestamp.day >= 28:
            causes.append("Beginning or end of month budget changes")

        # Metric-specific causes
        if metric_type == MetricType.CTR:
            if deviation_pct < 0:
                causes.extend(
                    [
                        "Ad fatigue - audiences may have seen ads too frequently",
                        "Increased competition affecting ad positions",
                        "Seasonal relevance changes",
                    ]
                )
            else:
                causes.extend(
                    [
                        "Improved ad copy or creative",
                        "Better keyword-ad relevance",
                        "Competitor absence",
                    ]
                )

        elif metric_type == MetricType.COST_PER_CONVERSION:
            if deviation_pct > 0:
                causes.extend(
                    [
                        "Increased auction competition",
                        "Landing page performance issues",
                        "Targeting too broad audiences",
                    ]
                )
            else:
                causes.extend(
                    [
                        "Improved Quality Scores",
                        "Better conversion rate optimization",
                        "More efficient bidding",
                    ]
                )

        elif metric_type == MetricType.CONVERSIONS:
            if deviation_pct < 0:
                causes.extend(
                    [
                        "Website technical issues or downtime",
                        "Tracking problems or tag errors",
                        "External factors (weather, events, news)",
                        "Inventory or service availability issues",
                    ]
                )
            else:
                causes.extend(
                    [
                        "Successful promotions or sales",
                        "Improved user experience",
                        "Seasonal demand increase",
                        "Effective remarketing campaigns",
                    ]
                )

        elif metric_type == MetricType.WASTED_SPEND:
            if deviation_pct > 0:
                causes.extend(
                    [
                        "New irrelevant search terms triggering ads",
                        "Broad match keywords too aggressive",
                        "Competitor brand bidding",
                        "Click fraud or invalid traffic",
                    ]
                )

        # Add general causes
        causes.append("Recent campaign or bidding strategy changes")
        causes.append("Market conditions or competitor activity")

        return causes

    def _generate_recommended_actions(
        self, metric_type: MetricType, deviation_pct: float, severity: str
    ) -> List[str]:
        """Generate recommended actions based on anomaly type and severity."""
        actions = []

        # Immediate actions for critical/high severity
        if severity in ["critical", "high"]:
            actions.append("Investigate immediately - check account for recent changes")
            actions.append("Review campaign performance reports for affected period")

        # Metric-specific actions
        if metric_type == MetricType.CTR and deviation_pct < 0:
            actions.extend(
                [
                    "Review search term reports for irrelevant queries",
                    "Check ad positions and impression share",
                    "Refresh ad copy and test new variations",
                    "Review keyword Quality Scores",
                ]
            )

        elif metric_type == MetricType.COST_PER_CONVERSION and deviation_pct > 0:
            actions.extend(
                [
                    "Analyze auction insights for increased competition",
                    "Review and optimize landing page performance",
                    "Adjust bidding strategy or bid limits",
                    "Tighten audience targeting",
                ]
            )

        elif metric_type == MetricType.CONVERSIONS and deviation_pct < 0:
            actions.extend(
                [
                    "Verify conversion tracking is working correctly",
                    "Check website analytics for technical issues",
                    "Review landing page load times and functionality",
                    "Confirm inventory/service availability",
                ]
            )

        elif metric_type == MetricType.WASTED_SPEND and deviation_pct > 0:
            actions.extend(
                [
                    "Add negative keywords from search term report",
                    "Review and refine match types",
                    "Implement dayparting if waste occurs at specific times",
                    "Consider geographic bid adjustments",
                ]
            )

        # General actions
        if severity in ["medium", "high", "critical"]:
            actions.append("Set up automated alerts for this metric")
            actions.append("Document findings and actions taken")

        return actions

    def detect_pattern_anomalies(
        self, data_points: List[TrendDataPoint]
    ) -> List[AnomalyAlert]:
        """Detect anomalies in a series of data points using pattern analysis."""
        if len(data_points) < self.min_historical_points:
            return []

        alerts = []
        values = [dp.value for dp in data_points]

        # Sliding window detection
        window_size = min(7, len(data_points) // 2)  # 7 days or half the data

        for i in range(window_size, len(data_points)):
            historical = values[i - window_size : i]
            current = values[i]

            alert = self.detect_anomalies(
                current,
                historical,
                data_points[i].metric_type,
                data_points[i].timestamp,
            )

            if alert:
                alerts.append(alert)

        return alerts
