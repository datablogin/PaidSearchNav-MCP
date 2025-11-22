"""Tests for anomaly detection functionality."""

from datetime import datetime

import numpy as np
import pytest

from paidsearchnav.comparison.anomaly import AnomalyDetector
from paidsearchnav.comparison.models import MetricType, TrendDataPoint


class TestAnomalyDetector:
    """Test the anomaly detector."""

    @pytest.fixture
    def detector(self):
        """Create anomaly detector instance."""
        return AnomalyDetector(z_score_threshold=2.5, iqr_multiplier=1.5)

    def test_detect_z_score_anomaly(self, detector):
        """Test z-score based anomaly detection."""
        # Normal data with one outlier
        historical_values = [100, 102, 98, 101, 99, 103, 97, 101, 200]  # 200 is outlier
        current_value = 200

        is_anomaly, z_score = detector._detect_z_score_anomaly(
            current_value, historical_values[:-1]
        )

        assert is_anomaly is True
        assert z_score > 2.5

        # Test normal value
        normal_value = 101
        is_anomaly, z_score = detector._detect_z_score_anomaly(
            normal_value, historical_values[:-1]
        )

        assert is_anomaly is False
        assert z_score < 2.5

    def test_detect_iqr_anomaly(self, detector):
        """Test IQR-based anomaly detection."""
        # Data with outliers
        historical_values = [10, 12, 11, 13, 14, 12, 11, 13, 12]

        # Test extreme outlier
        outlier_value = 30
        is_anomaly, deviation = detector._detect_iqr_anomaly(
            outlier_value, historical_values
        )
        assert is_anomaly is True
        assert deviation > 0

        # Test normal value
        normal_value = 12
        is_anomaly, deviation = detector._detect_iqr_anomaly(
            normal_value, historical_values
        )
        assert is_anomaly is False
        assert deviation == 0.0

    def test_detect_trend_anomaly(self, detector):
        """Test trend-based anomaly detection."""
        # Create data with clear upward trend
        historical_values = [100 + i * 10 for i in range(10)]  # 100, 110, 120, ...

        # Value that continues the trend
        expected_value = 200  # Next in sequence
        is_anomaly, deviation = detector._detect_trend_anomaly(
            expected_value, historical_values, datetime.now()
        )
        assert is_anomaly is False

        # Value that breaks the trend
        anomaly_value = 250  # Much higher than expected
        is_anomaly, deviation = detector._detect_trend_anomaly(
            anomaly_value, historical_values, datetime.now()
        )
        assert is_anomaly is True
        assert deviation > 2.0

    def test_detect_anomalies_complete(self, detector):
        """Test complete anomaly detection with all methods."""
        historical_values = [100 + np.random.normal(0, 5) for _ in range(20)]
        current_value = 150  # Clear anomaly
        timestamp = datetime(2024, 1, 15)

        alert = detector.detect_anomalies(
            current_value, historical_values, MetricType.CONVERSIONS, timestamp
        )

        assert alert is not None
        assert alert.metric_type == MetricType.CONVERSIONS
        assert alert.actual_value == 150
        assert alert.deviation_percentage > 40  # ~50% deviation
        assert alert.severity in ["high", "critical"]
        assert len(alert.possible_causes) > 0
        assert len(alert.recommended_actions) > 0

    def test_detect_anomalies_insufficient_data(self, detector):
        """Test anomaly detection with insufficient historical data."""
        historical_values = [100, 102, 98]  # Less than minimum required
        current_value = 150

        alert = detector.detect_anomalies(
            current_value, historical_values, MetricType.CTR, datetime.now()
        )

        assert alert is None  # Should not detect anomalies with insufficient data

    def test_determine_severity(self, detector):
        """Test severity determination for different metrics."""
        # Test critical metric with high deviation
        severity = detector._determine_severity(60, 4.0, MetricType.CONVERSIONS)
        assert severity == "critical"

        # Test critical metric with medium deviation
        severity = detector._determine_severity(25, 2.8, MetricType.CONVERSION_RATE)
        assert severity == "medium"

        # Test high sensitivity metric
        severity = detector._determine_severity(55, 3.8, MetricType.CTR)
        assert severity == "high"

        # Test normal metric with low deviation
        severity = detector._determine_severity(30, 2.6, MetricType.IMPRESSIONS)
        assert severity == "low"

    def test_generate_possible_causes(self, detector):
        """Test generation of possible causes for anomalies."""
        # Weekend anomaly
        weekend_timestamp = datetime(2024, 1, 13)  # Saturday
        causes = detector._generate_possible_causes(
            MetricType.CTR, -20.0, weekend_timestamp
        )
        assert any("weekend" in cause.lower() for cause in causes)

        # CTR decrease
        causes = detector._generate_possible_causes(
            MetricType.CTR, -15.0, datetime.now()
        )
        assert any("ad fatigue" in cause.lower() for cause in causes)
        assert any("competition" in cause.lower() for cause in causes)

        # Conversion decrease
        causes = detector._generate_possible_causes(
            MetricType.CONVERSIONS, -30.0, datetime.now()
        )
        assert any("technical issues" in cause.lower() for cause in causes)
        assert any("tracking" in cause.lower() for cause in causes)

        # Wasted spend increase
        causes = detector._generate_possible_causes(
            MetricType.WASTED_SPEND, 50.0, datetime.now()
        )
        assert any("search terms" in cause.lower() for cause in causes)
        assert any("broad match" in cause.lower() for cause in causes)

    def test_generate_recommended_actions(self, detector):
        """Test generation of recommended actions."""
        # Critical CTR drop
        actions = detector._generate_recommended_actions(
            MetricType.CTR, -25.0, "critical"
        )
        assert any("investigate immediately" in action.lower() for action in actions)
        assert any("search term" in action.lower() for action in actions)
        assert any("ad copy" in action.lower() for action in actions)

        # High CPC increase
        actions = detector._generate_recommended_actions(
            MetricType.COST_PER_CONVERSION, 40.0, "high"
        )
        assert any("auction insights" in action.lower() for action in actions)
        assert any("bidding strategy" in action.lower() for action in actions)

        # Conversion drop
        actions = detector._generate_recommended_actions(
            MetricType.CONVERSIONS, -20.0, "high"
        )
        assert any("tracking" in action.lower() for action in actions)
        assert any("website analytics" in action.lower() for action in actions)

    def test_detect_pattern_anomalies(self, detector):
        """Test pattern-based anomaly detection across multiple data points."""
        # Create data with anomalies at specific positions
        data_points = []
        for i in range(20):
            value = 100 + np.random.normal(0, 5)
            if i in [10, 15]:  # Insert anomalies
                value = 150

            data_points.append(
                TrendDataPoint(
                    timestamp=datetime(2024, 1, i + 1),
                    value=value,
                    metric_type=MetricType.TOTAL_SPEND,
                )
            )

        # Detect pattern anomalies
        alerts = detector.detect_pattern_anomalies(data_points)

        # Should detect anomalies around positions 10 and 15
        assert len(alerts) >= 2
        anomaly_dates = [alert.timestamp.day for alert in alerts]
        assert any(d in range(10, 13) for d in anomaly_dates)  # Around day 11
        assert any(d in range(15, 18) for d in anomaly_dates)  # Around day 16
