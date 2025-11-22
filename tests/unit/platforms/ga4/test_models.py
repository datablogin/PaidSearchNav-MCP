"""Unit tests for GA4 data models."""

from datetime import datetime

import pytest
from pydantic import ValidationError

from paidsearchnav.platforms.ga4.models import (
    GA4Alert,
    GA4AlertThreshold,
    GA4APIRequest,
    GA4CostEstimate,
    GA4QuotaUsage,
    GA4SessionMetrics,
    GA4ValidationResult,
)


class TestGA4SessionMetrics:
    """Test GA4SessionMetrics model."""

    def test_valid_session_metrics(self):
        """Test creating valid session metrics."""
        metrics = GA4SessionMetrics(
            property_id="123456789",
            source="google",
            medium="cpc",
            country="US",
            device_category="desktop",
            sessions=100,
            bounce_rate=0.3,
            avg_session_duration=180.0,
            conversions=5.0,
            revenue=250.0,
            conversion_rate=0.05,
        )

        assert metrics.property_id == "123456789"
        assert metrics.sessions == 100
        assert metrics.bounce_rate == 0.3
        assert metrics.conversion_rate == 0.05

    def test_invalid_bounce_rate_raises_error(self):
        """Test that invalid bounce rate raises validation error."""
        with pytest.raises(ValidationError, match="Rate must be between 0.0 and 1.0"):
            GA4SessionMetrics(
                property_id="123456789",
                source="google",
                medium="cpc",
                country="US",
                device_category="desktop",
                bounce_rate=1.5,  # Invalid: > 1.0
            )

    def test_invalid_conversion_rate_raises_error(self):
        """Test that invalid conversion rate raises validation error."""
        with pytest.raises(ValidationError, match="Rate must be between 0.0 and 1.0"):
            GA4SessionMetrics(
                property_id="123456789",
                source="google",
                medium="cpc",
                country="US",
                device_category="desktop",
                conversion_rate=-0.1,  # Invalid: < 0.0
            )


class TestGA4ValidationResult:
    """Test GA4ValidationResult model."""

    def test_variance_calculation(self):
        """Test automatic variance calculation."""
        result = GA4ValidationResult(
            property_id="123456789",
            validation_type="sessions",
            api_total=100.0,
            bigquery_total=95.0,
            variance_percentage=5.26,
            is_within_tolerance=False,
            tolerance_percentage=5.0,
        )

        # Should calculate 5.26% variance
        assert abs(result.variance_percentage - 5.26) < 0.1
        assert result.is_within_tolerance is False  # 5.26% > 5% tolerance

    def test_tolerance_check(self):
        """Test tolerance checking logic."""
        result = GA4ValidationResult(
            property_id="123456789",
            validation_type="sessions",
            api_total=100.0,
            bigquery_total=98.0,  # 2% variance
            variance_percentage=2.04,
            is_within_tolerance=True,
            tolerance_percentage=5.0,
        )

        assert result.variance_percentage < 5.0
        assert result.is_within_tolerance is True

    def test_zero_bigquery_total_handling(self):
        """Test handling of zero BigQuery total."""
        result = GA4ValidationResult(
            property_id="123456789",
            validation_type="sessions",
            api_total=100.0,
            bigquery_total=0.0,
            variance_percentage=100.0,
            is_within_tolerance=False,
            tolerance_percentage=5.0,
        )

        assert result.variance_percentage == 100.0
        assert result.is_within_tolerance is False


class TestGA4AlertThreshold:
    """Test GA4AlertThreshold model."""

    def test_valid_threshold(self):
        """Test creating valid alert threshold."""
        threshold = GA4AlertThreshold(
            metric_name="bounceRate",
            threshold_value=0.8,
            comparison_operator="greater_than",
            alert_severity="medium",
            cooldown_minutes=30,
        )

        assert threshold.metric_name == "bounceRate"
        assert threshold.threshold_value == 0.8
        assert threshold.enabled is True

    def test_invalid_operator_raises_error(self):
        """Test that invalid comparison operator raises error."""
        with pytest.raises(ValidationError, match="Invalid operator"):
            GA4AlertThreshold(
                metric_name="bounceRate",
                threshold_value=0.8,
                comparison_operator="invalid_operator",
                alert_severity="medium",
            )

    def test_invalid_severity_raises_error(self):
        """Test that invalid severity raises error."""
        with pytest.raises(ValidationError, match="Invalid severity"):
            GA4AlertThreshold(
                metric_name="bounceRate",
                threshold_value=0.8,
                comparison_operator="greater_than",
                alert_severity="invalid_severity",
            )


class TestGA4Alert:
    """Test GA4Alert model."""

    @pytest.fixture
    def sample_threshold(self):
        """Create sample alert threshold."""
        return GA4AlertThreshold(
            metric_name="bounceRate",
            threshold_value=0.8,
            comparison_operator="greater_than",
            alert_severity="medium",
        )

    def test_alert_creation(self, sample_threshold):
        """Test creating GA4 alert."""
        alert = GA4Alert(
            property_id="123456789",
            threshold=sample_threshold,
            current_value=0.85,
            message="High bounce rate detected",
        )

        assert alert.property_id == "123456789"
        assert alert.current_value == 0.85
        assert alert.is_resolved is False
        assert alert.duration_minutes is None

    def test_alert_resolution(self, sample_threshold):
        """Test alert resolution."""
        alert = GA4Alert(
            property_id="123456789",
            threshold=sample_threshold,
            current_value=0.85,
            message="High bounce rate detected",
            triggered_at=datetime(2025, 1, 1, 10, 0, 0),
        )

        # Resolve alert
        alert.resolved_at = datetime(2025, 1, 1, 10, 30, 0)

        assert alert.is_resolved is True
        assert alert.duration_minutes == 30.0


class TestGA4CostEstimate:
    """Test GA4CostEstimate model."""

    def test_daily_projected_cost(self):
        """Test daily cost projection calculation."""
        estimate = GA4CostEstimate(
            property_id="123456789",
            requests_count=100,
            estimated_cost_usd=0.01,
            period_start=datetime(2025, 1, 1, 10, 0, 0),
            period_end=datetime(2025, 1, 1, 12, 0, 0),  # 2 hours
            cost_per_request=0.0001,
        )

        # Should project $0.12 for full day (0.01 for 2 hours * 12 = $0.12)
        daily_projection = estimate.daily_projected_cost
        assert abs(daily_projection - 0.12) < 0.001

    def test_zero_period_handling(self):
        """Test handling when period is zero."""
        estimate = GA4CostEstimate(
            property_id="123456789",
            requests_count=100,
            estimated_cost_usd=0.01,
            period_start=datetime(2025, 1, 1, 10, 0, 0),
            period_end=datetime(2025, 1, 1, 10, 0, 0),  # Same time
        )

        assert estimate.daily_projected_cost == 0.01


class TestGA4QuotaUsage:
    """Test GA4QuotaUsage model."""

    def test_quota_limit_properties(self):
        """Test quota limit checking properties."""
        quota = GA4QuotaUsage(
            property_id="123456789",
            requests_today=85000,  # High usage
            requests_this_hour=2500,  # High hourly usage
        )

        assert quota.is_approaching_daily_limit is True  # > 80k
        assert quota.is_approaching_hourly_limit is True  # > 2k

    def test_normal_quota_usage(self):
        """Test normal quota usage levels."""
        quota = GA4QuotaUsage(
            property_id="123456789",
            requests_today=1000,
            requests_this_hour=50,
        )

        assert quota.is_approaching_daily_limit is False
        assert quota.is_approaching_hourly_limit is False


class TestGA4APIRequest:
    """Test GA4APIRequest model."""

    def test_valid_date_formats(self):
        """Test valid date format validation."""
        # Test GA4 date constant
        request1 = GA4APIRequest(
            property_id="123456789",
            start_date="7daysAgo",
            end_date="yesterday",
            dimensions=["source"],
            metrics=["sessions"],
        )
        assert request1.start_date == "7daysAgo"

        # Test YYYY-MM-DD format
        request2 = GA4APIRequest(
            property_id="123456789",
            start_date="2025-01-01",
            end_date="2025-01-07",
            dimensions=["source"],
            metrics=["sessions"],
        )
        assert request2.start_date == "2025-01-01"

    def test_invalid_date_format_raises_error(self):
        """Test that invalid date format raises error."""
        with pytest.raises(ValidationError, match="Date must be in YYYY-MM-DD format"):
            GA4APIRequest(
                property_id="123456789",
                start_date="invalid-date",
                end_date="yesterday",
                dimensions=["source"],
                metrics=["sessions"],
            )
