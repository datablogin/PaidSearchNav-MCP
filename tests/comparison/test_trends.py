"""Tests for trend analysis functionality."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import numpy as np
import pytest

from paidsearchnav_mcp.comparison.models import AuditResult, MetricType, TrendGranularity
from paidsearchnav_mcp.comparison.trends import TrendAnalyzer


class TestTrendAnalyzer:
    """Test the trend analyzer."""

    @pytest.fixture
    def mock_repository(self):
        """Create mock repository."""
        return AsyncMock()

    @pytest.fixture
    def analyzer(self, mock_repository):
        """Create trend analyzer instance."""
        return TrendAnalyzer(mock_repository)

    @pytest.fixture
    def sample_audits(self):
        """Create sample audit results over time."""
        audits = []
        base_date = datetime(2024, 1, 1)

        for i in range(12):  # 12 months of data
            audit_date = base_date + timedelta(days=30 * i)
            audits.append(
                AuditResult(
                    id=f"audit-{i}",
                    customer_id="customer-123",
                    status="completed",
                    created_at=audit_date,
                    summary={
                        "total_issues": 20 - i,  # Decreasing issues over time
                        "metrics": {
                            "total_spend": 10000.0 + i * 500,  # Increasing spend
                            "wasted_spend": 2000.0 - i * 100,  # Decreasing waste
                            "ctr": 2.5 + i * 0.1,  # Improving CTR
                            "conversion_rate": 3.0 + i * 0.05,  # Improving CVR
                            "conversions": 75 + i * 5,  # More conversions
                            "roas": 4.0 + i * 0.1,  # Improving ROAS
                        },
                    },
                )
            )

        return audits

    @pytest.mark.asyncio
    async def test_generate_trend_analysis(
        self, analyzer, mock_repository, sample_audits
    ):
        """Test generating trend analysis."""
        # Setup mock
        analyzer._get_audits_in_range = AsyncMock(return_value=sample_audits)

        # Generate trends
        results = await analyzer.generate_trend_analysis(
            customer_id="customer-123",
            metric_types=[MetricType.CTR, MetricType.CONVERSIONS],
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 12, 31),
            granularity=TrendGranularity.MONTHLY,
        )

        # Verify results
        assert len(results) == 2
        assert MetricType.CTR in results
        assert MetricType.CONVERSIONS in results

        # Check CTR trend
        ctr_trend = results[MetricType.CTR]
        assert ctr_trend.customer_id == "customer-123"
        assert ctr_trend.metric_type == MetricType.CTR
        assert len(ctr_trend.data_points) == 12
        assert ctr_trend.trend_direction == "increasing"
        assert ctr_trend.trend_strength > 0.5  # Should be strong positive trend

    def test_extract_metric_value(self, analyzer):
        """Test extracting metric values from audit results."""
        audit = AuditResult(
            id="audit-1",
            customer_id="customer-123",
            status="completed",
            created_at=datetime(2024, 1, 1),
            summary={
                "total_issues": 15,
                "metrics": {
                    "total_spend": 10000.0,
                    "ctr": 2.5,
                    "conversions": 100,
                },
            },
        )

        # Test various metric extractions
        assert analyzer._extract_metric_value(audit, MetricType.TOTAL_SPEND) == 10000.0
        assert analyzer._extract_metric_value(audit, MetricType.CTR) == 2.5
        assert analyzer._extract_metric_value(audit, MetricType.CONVERSIONS) == 100
        assert analyzer._extract_metric_value(audit, MetricType.ISSUES_COUNT) == 15

    def test_group_audits_by_granularity(self, analyzer, sample_audits):
        """Test grouping audits by different granularities."""
        # Test monthly grouping
        monthly_groups = analyzer._group_audits_by_granularity(
            sample_audits[:3], TrendGranularity.MONTHLY
        )
        assert len(monthly_groups) == 3  # 3 different months

        # Test quarterly grouping
        quarterly_groups = analyzer._group_audits_by_granularity(
            sample_audits[:6], TrendGranularity.QUARTERLY
        )
        assert len(quarterly_groups) == 2  # Q1 and Q2

    def test_calculate_trend(self, analyzer):
        """Test trend calculation."""
        from paidsearchnav.comparison.models import TrendDataPoint

        # Create increasing trend data
        data_points = [
            TrendDataPoint(
                timestamp=datetime(2024, 1, i),
                value=100.0 + i * 10,  # Linear increase
                metric_type=MetricType.CONVERSIONS,
            )
            for i in range(1, 11)
        ]

        direction, strength = analyzer._calculate_trend(data_points)
        assert direction == "increasing"
        assert strength > 0.8  # Should be strong linear trend

        # Create stable trend data
        stable_points = [
            TrendDataPoint(
                timestamp=datetime(2024, 1, i),
                value=100.0 + np.random.normal(0, 1),  # Small random variations
                metric_type=MetricType.CTR,
            )
            for i in range(1, 11)
        ]

        direction, strength = analyzer._calculate_trend(stable_points)
        assert direction == "stable"

    def test_detect_anomalies(self, analyzer):
        """Test anomaly detection."""
        from paidsearchnav.comparison.models import TrendDataPoint

        # Create data with one anomaly
        data_points = []
        for i in range(1, 11):
            value = 100.0 + np.random.normal(0, 5)  # Normal variation
            if i == 7:
                value = 200.0  # Anomaly

            data_points.append(
                TrendDataPoint(
                    timestamp=datetime(2024, 1, i),
                    value=value,
                    metric_type=MetricType.TOTAL_SPEND,
                )
            )

        # Detect anomalies
        results = analyzer._detect_anomalies(data_points)

        # Check that anomaly was detected
        anomaly_detected = False
        for dp, is_anomaly, score in results:
            if dp.timestamp.day == 7 and is_anomaly:
                anomaly_detected = True
                assert score > 2.5  # High z-score

        assert anomaly_detected

    @patch("paidsearchnav.comparison.trends.signal.detrend")
    @patch("paidsearchnav.comparison.trends.np.correlate")
    def test_detect_seasonality(self, mock_correlate, mock_detrend, analyzer):
        """Test seasonality detection."""
        from paidsearchnav.comparison.models import TrendDataPoint

        # Create seasonal data (quarterly pattern)
        data_points = []
        for i in range(24):  # 2 years
            month = i % 12
            # Higher values in Q4 (months 9, 10, 11)
            seasonal_factor = 1.5 if month in [9, 10, 11] else 1.0
            value = 1000.0 * seasonal_factor + np.random.normal(0, 50)

            data_points.append(
                TrendDataPoint(
                    timestamp=datetime(2023, 1, 1) + timedelta(days=30 * i),
                    value=value,
                    metric_type=MetricType.CONVERSIONS,
                )
            )

        # Mock detrending and autocorrelation
        mock_detrend.return_value = np.array([dp.value for dp in data_points])
        # High autocorrelation at lag 12 (yearly seasonality)
        mock_autocorr = np.zeros(24)
        mock_autocorr[0] = 1.0
        mock_autocorr[12] = 0.6  # High correlation at 12 months
        mock_correlate.return_value = np.concatenate(
            [mock_autocorr[::-1], mock_autocorr]
        )

        # Test seasonality detection
        has_seasonality = analyzer._detect_seasonality(data_points)
        assert has_seasonality is True

    def test_generate_forecast(self, analyzer):
        """Test forecast generation."""
        from paidsearchnav.comparison.models import TrendDataPoint

        # Create linear trend data
        data_points = [
            TrendDataPoint(
                timestamp=datetime(2024, 1, 1) + timedelta(days=30 * i),
                value=1000.0 + i * 100,  # $100 increase per month
                metric_type=MetricType.TOTAL_SPEND,
            )
            for i in range(6)
        ]

        # Generate forecast
        forecast = analyzer._generate_forecast(
            data_points, forecast_periods=3, granularity=TrendGranularity.MONTHLY
        )

        # Verify forecast
        assert len(forecast) == 3
        # Should continue linear trend
        assert forecast[0].value > data_points[-1].value
        assert forecast[1].value > forecast[0].value
        assert forecast[2].value > forecast[1].value

    def test_generate_trend_insights(self, analyzer):
        """Test trend insight generation."""
        from paidsearchnav.comparison.models import TrendAnalysis, TrendDataPoint

        # Create sample trend analysis
        data_points = [
            TrendDataPoint(
                timestamp=datetime(2024, 1, i),
                value=100.0 + i * 10,
                metric_type=MetricType.CONVERSIONS,
                is_anomaly=(i == 5),  # One anomaly
            )
            for i in range(1, 11)
        ]

        analysis = TrendAnalysis(
            customer_id="customer-123",
            metric_type=MetricType.CONVERSIONS,
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 10, 31),
            granularity=TrendGranularity.MONTHLY,
            data_points=data_points,
            trend_direction="increasing",
            trend_strength=0.9,
            seasonality_detected=True,
            anomalies_detected=1,
        )

        # Add forecast
        analysis.forecast = [
            TrendDataPoint(
                timestamp=datetime(2024, 11, 1),
                value=210.0,
                metric_type=MetricType.CONVERSIONS,
            )
        ]

        # Generate insights
        insights = analyzer._generate_trend_insights(analysis)

        # Verify insights
        assert len(insights) > 0
        assert any("strong increasing trend" in insight for insight in insights)
        assert any("anomalies detected" in insight.lower() for insight in insights)
        assert any("seasonal pattern" in insight.lower() for insight in insights)
        assert any("forecast" in insight.lower() for insight in insights)
