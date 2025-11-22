"""Tests for DevicePerformanceAnalyzer."""

from datetime import datetime, timezone

import pytest

from paidsearchnav.analyzers.device_performance import DevicePerformanceAnalyzer
from paidsearchnav.core.models import (
    DeviceInsight,
    DevicePerformanceAnalysisResult,
    DevicePerformanceData,
    DevicePerformanceSummary,
    DeviceType,
)


class TestDevicePerformanceAnalyzer:
    """Test cases for DevicePerformanceAnalyzer."""

    @pytest.fixture
    def analyzer(self):
        """Create analyzer instance."""
        return DevicePerformanceAnalyzer(
            min_impressions=100,
            min_clicks=10,
            cpc_variance_threshold=0.15,
            conversion_rate_threshold=0.20,
        )

    @pytest.fixture
    def sample_device_data(self):
        """Sample device performance data."""
        return [
            {
                "customer_id": "123456789",
                "campaign_id": "1111",
                "campaign": "Test Campaign",
                "device": "Mobile phones",
                "level": "Campaign",
                "bid_adjustment": -0.20,
                "impressions": 5000,
                "clicks": 250,
                "conversions": 10.0,
                "cost": 500.0,
                "conversion_value": 800.0,
            },
            {
                "customer_id": "123456789",
                "campaign_id": "1111",
                "campaign": "Test Campaign",
                "device": "Computers",
                "level": "Campaign",
                "bid_adjustment": 0.10,
                "impressions": 2000,
                "clicks": 120,
                "conversions": 8.0,
                "cost": 300.0,
                "conversion_value": 1000.0,
            },
            {
                "customer_id": "123456789",
                "campaign_id": "1111",
                "campaign": "Test Campaign",
                "device": "Tablets",
                "level": "Campaign",
                "bid_adjustment": -0.50,
                "impressions": 500,
                "clicks": 15,
                "conversions": 0.5,
                "cost": 45.0,
                "conversion_value": 50.0,
            },
        ]

    @pytest.fixture
    def start_date(self):
        """Start date for analysis."""
        return datetime(2023, 1, 1, tzinfo=timezone.utc)

    @pytest.fixture
    def end_date(self):
        """End date for analysis."""
        return datetime(2023, 1, 31, tzinfo=timezone.utc)

    @pytest.mark.asyncio
    async def test_analyze_success(
        self, analyzer, sample_device_data, start_date, end_date
    ):
        """Test successful device performance analysis."""
        result = await analyzer.analyze(
            customer_id="123456789",
            start_date=start_date,
            end_date=end_date,
            device_data=sample_device_data,
        )

        assert isinstance(result, DevicePerformanceAnalysisResult)
        assert result.customer_id == "123456789"
        assert result.analyzer_name == "device_performance"
        assert len(result.performance_data) == 3  # All devices meet minimum thresholds
        assert len(result.insights) == 3
        assert len(result.device_shares) == 3
        assert result.recommendations_count > 0

    @pytest.mark.asyncio
    async def test_analyze_no_data(self, analyzer, start_date, end_date):
        """Test analysis with no device data."""
        result = await analyzer.analyze(
            customer_id="123456789",
            start_date=start_date,
            end_date=end_date,
            device_data=[],
        )

        assert isinstance(result, DevicePerformanceAnalysisResult)
        assert len(result.performance_data) == 0
        assert len(result.insights) == 0
        assert len(result.device_shares) == 0
        assert result.device_recommendations == [
            "No device data available for analysis"
        ]

    @pytest.mark.asyncio
    async def test_analyze_insufficient_data(self, analyzer, start_date, end_date):
        """Test analysis with data below minimum thresholds."""
        low_volume_data = [
            {
                "customer_id": "123456789",
                "campaign_id": "1111",
                "campaign": "Test Campaign",
                "device": "Mobile phones",
                "impressions": 50,  # Below minimum
                "clicks": 5,  # Below minimum
                "conversions": 1.0,
                "cost": 10.0,
                "conversion_value": 20.0,
            }
        ]

        result = await analyzer.analyze(
            customer_id="123456789",
            start_date=start_date,
            end_date=end_date,
            device_data=low_volume_data,
        )

        assert len(result.performance_data) == 0
        assert result.device_recommendations == [
            "No device data available for analysis"
        ]

    def test_convert_to_performance_data(
        self, analyzer, sample_device_data, start_date, end_date
    ):
        """Test conversion of raw data to performance models."""
        performance_data = analyzer._convert_to_performance_data(
            sample_device_data, start_date, end_date
        )

        assert len(performance_data) == 3

        mobile_data = next(
            d for d in performance_data if d.device_type == DeviceType.MOBILE
        )
        assert mobile_data.campaign_name == "Test Campaign"
        assert mobile_data.impressions == 5000
        assert mobile_data.clicks == 250
        assert mobile_data.bid_adjustment == -0.20
        assert mobile_data.cost == 500.0
        assert mobile_data.ctr == 0.05  # 250/5000
        assert mobile_data.avg_cpc == 2.0  # 500/250

    def test_map_device_type(self, analyzer):
        """Test device type mapping."""
        assert analyzer._map_device_type("Mobile phones") == DeviceType.MOBILE
        assert analyzer._map_device_type("Computers") == DeviceType.DESKTOP
        assert analyzer._map_device_type("Tablets") == DeviceType.TABLET
        assert analyzer._map_device_type("Unknown Device") == DeviceType.UNKNOWN

    def test_filter_performance_data(self, analyzer):
        """Test filtering of performance data by thresholds."""
        data = [
            DevicePerformanceData(
                customer_id="123",
                campaign_id="111",
                campaign_name="Test",
                device_type=DeviceType.MOBILE,
                impressions=1000,  # Above threshold
                clicks=50,  # Above threshold
                conversions=2.0,
                cost_micros=100_000_000,
                conversion_value_micros=200_000_000,
                start_date=datetime.now(),
                end_date=datetime.now(),
            ),
            DevicePerformanceData(
                customer_id="123",
                campaign_id="111",
                campaign_name="Test",
                device_type=DeviceType.DESKTOP,
                impressions=50,  # Below threshold
                clicks=5,  # Below threshold
                conversions=1.0,
                cost_micros=50_000_000,
                conversion_value_micros=100_000_000,
                start_date=datetime.now(),
                end_date=datetime.now(),
            ),
        ]

        filtered = analyzer._filter_performance_data(data)
        assert len(filtered) == 1
        assert filtered[0].device_type == DeviceType.MOBILE

    def test_calculate_device_shares(self, analyzer, start_date, end_date):
        """Test calculation of device share metrics."""
        data = [
            DevicePerformanceData(
                customer_id="123",
                campaign_id="111",
                campaign_name="Test",
                device_type=DeviceType.MOBILE,
                impressions=1000,
                clicks=100,
                conversions=5.0,
                cost_micros=200_000_000,  # $200
                conversion_value_micros=500_000_000,  # $500
                start_date=start_date,
                end_date=end_date,
            ),
            DevicePerformanceData(
                customer_id="123",
                campaign_id="111",
                campaign_name="Test",
                device_type=DeviceType.DESKTOP,
                impressions=500,
                clicks=50,
                conversions=3.0,
                cost_micros=100_000_000,  # $100
                conversion_value_micros=300_000_000,  # $300
                start_date=start_date,
                end_date=end_date,
            ),
        ]

        shares = analyzer._calculate_device_shares(data)
        assert len(shares) == 2

        mobile_share = next(s for s in shares if s.device_type == DeviceType.MOBILE)
        assert mobile_share.click_share == pytest.approx(
            100 / 150, abs=0.01
        )  # 100 out of 150 total clicks
        assert mobile_share.cost_share == pytest.approx(
            200 / 300, abs=0.01
        )  # $200 out of $300 total cost

    def test_calculate_performance_score(self, analyzer):
        """Test performance score calculation."""
        # Perfect performance (all metrics at average)
        # CPC score: 100 - (1-1)*50 = 100
        # Conversion score: (1-1)*25 + 50 = 50
        # ROAS score: (1-1)*25 + 50 = 50
        # Weighted: 100*0.4 + 50*0.4 + 50*0.2 = 70
        score = analyzer._calculate_performance_score(1.0, 1.0, 1.0)
        assert score == 70.0

        # High performance (all metrics better than average)
        score = analyzer._calculate_performance_score(
            0.5, 1.5, 1.5
        )  # Lower CPC, higher conversion rate and ROAS
        assert score > 70.0

        # Low performance (all metrics worse than average)
        score = analyzer._calculate_performance_score(
            2.0, 0.5, 0.5
        )  # Higher CPC, lower conversion rate and ROAS
        assert score < 45.0

    def test_needs_mobile_optimization(self, analyzer, start_date, end_date):
        """Test mobile optimization detection."""
        # Mobile CPC significantly higher than desktop
        mobile_data = [
            DevicePerformanceData(
                customer_id="123",
                campaign_id="111",
                campaign_name="Test",
                device_type=DeviceType.MOBILE,
                impressions=1000,
                clicks=100,
                conversions=5.0,
                cost_micros=300_000_000,  # $3 CPC
                conversion_value_micros=500_000_000,
                start_date=start_date,
                end_date=end_date,
            )
        ]

        desktop_data = [
            DevicePerformanceData(
                customer_id="123",
                campaign_id="111",
                campaign_name="Test",
                device_type=DeviceType.DESKTOP,
                impressions=1000,
                clicks=100,
                conversions=5.0,
                cost_micros=200_000_000,  # $2 CPC
                conversion_value_micros=500_000_000,
                start_date=start_date,
                end_date=end_date,
            )
        ]

        # Mobile CPC is 50% higher (3/2 = 1.5), which exceeds 40% threshold
        assert analyzer._needs_mobile_optimization(mobile_data, desktop_data) is True

        # Lower the mobile cost so it's not significantly higher
        mobile_data[0].cost_micros = 220_000_000  # $2.20 CPC, only 10% higher
        assert analyzer._needs_mobile_optimization(mobile_data, desktop_data) is False

    def test_calculate_cpc_variance(self, analyzer, start_date, end_date):
        """Test CPC variance calculation."""
        data = [
            DevicePerformanceData(
                customer_id="123",
                campaign_id="111",
                campaign_name="Test",
                device_type=DeviceType.MOBILE,
                impressions=1000,
                clicks=100,
                conversions=5.0,
                cost_micros=300_000_000,  # $3 CPC
                conversion_value_micros=500_000_000,
                start_date=start_date,
                end_date=end_date,
            ),
            DevicePerformanceData(
                customer_id="123",
                campaign_id="111",
                campaign_name="Test",
                device_type=DeviceType.DESKTOP,
                impressions=1000,
                clicks=100,
                conversions=5.0,
                cost_micros=200_000_000,  # $2 CPC
                conversion_value_micros=500_000_000,
                start_date=start_date,
                end_date=end_date,
            ),
        ]

        variance = analyzer._calculate_cpc_variance(data)
        # Variance should be (3-2)/2 * 100 = 50%
        assert variance == pytest.approx(50.0, abs=0.1)

    def test_get_bid_adjustment_recommendation(self, analyzer):
        """Test bid adjustment recommendations."""
        # Mobile with high CPC
        rec = analyzer._get_bid_adjustment_recommendation(DeviceType.MOBILE, 1.4, 1.0)
        assert "Decrease mobile bid adjustments" in rec

        # Desktop with high conversion rate
        rec = analyzer._get_bid_adjustment_recommendation(DeviceType.DESKTOP, 1.0, 1.4)
        assert "Increase desktop bid adjustments" in rec

        # Tablet with low conversion rate
        rec = analyzer._get_bid_adjustment_recommendation(DeviceType.TABLET, 1.0, 0.6)
        assert "Decrease tablet bid adjustments" in rec or "exclude" in rec

    def test_calculate_bid_adjustments(self, analyzer):
        """Test bid adjustment calculations."""
        insights = [
            DeviceInsight(
                device_type=DeviceType.MOBILE,
                performance_score=85.0,  # High performer
                cpc_vs_average=1.0,
                conversion_rate_vs_average=1.0,
                roas_vs_average=1.0,
                click_share=0.6,
                cost_share=0.6,
                conversion_share=0.6,
                recommended_action="INCREASE_INVESTMENT",
                bid_adjustment_recommendation="Test",
                budget_recommendation="Test",
                optimization_opportunity="Test",
            ),
            DeviceInsight(
                device_type=DeviceType.DESKTOP,
                performance_score=30.0,  # Low performer
                cpc_vs_average=1.0,
                conversion_rate_vs_average=1.0,
                roas_vs_average=1.0,
                click_share=0.3,
                cost_share=0.3,
                conversion_share=0.3,
                recommended_action="REDUCE_INVESTMENT",
                bid_adjustment_recommendation="Test",
                budget_recommendation="Test",
                optimization_opportunity="Test",
            ),
        ]

        adjustments = analyzer._calculate_bid_adjustments(insights)

        assert "Mobile phones" in adjustments
        assert "Computers" in adjustments

        # High performer should get positive adjustment
        assert adjustments["Mobile phones"] > 0

        # Low performer should get negative adjustment
        assert adjustments["Computers"] < 0

    def test_get_name_and_description(self, analyzer):
        """Test analyzer metadata."""
        assert analyzer.get_name() == "device_performance"
        assert "device performance" in analyzer.get_description().lower()
        assert "optimization" in analyzer.get_description().lower()

    @pytest.mark.asyncio
    async def test_analyze_handles_invalid_data(self, analyzer, start_date, end_date):
        """Test analysis handles invalid data gracefully."""
        invalid_data = [
            {
                "device": "Mobile phones",
                "impressions": "invalid",  # Invalid numeric value
                "clicks": 100,
                "cost": 50.0,
            },
            {
                "device": "Computers",
                # Missing required fields
            },
        ]

        result = await analyzer.analyze(
            customer_id="123456789",
            start_date=start_date,
            end_date=end_date,
            device_data=invalid_data,
        )

        # Should handle gracefully and return empty result
        assert len(result.performance_data) == 0

    @pytest.mark.asyncio
    async def test_analyze_invalid_date_range(self, analyzer, start_date, end_date):
        """Test analysis validates date range properly."""
        with pytest.raises(ValueError, match="Start date .* must be before end date"):
            await analyzer.analyze(
                customer_id="123456789",
                start_date=end_date,  # End date as start date
                end_date=start_date,  # Start date as end date
                device_data=[],
            )

    def test_group_data_by_device_type(self, analyzer, start_date, end_date):
        """Test device data grouping functionality."""
        data = [
            DevicePerformanceData(
                customer_id="123",
                campaign_id="111",
                campaign_name="Test",
                device_type=DeviceType.MOBILE,
                impressions=1000,
                clicks=100,
                conversions=5.0,
                cost_micros=200_000_000,
                conversion_value_micros=500_000_000,
                start_date=start_date,
                end_date=end_date,
            ),
            DevicePerformanceData(
                customer_id="123",
                campaign_id="111",
                campaign_name="Test",
                device_type=DeviceType.DESKTOP,
                impressions=500,
                clicks=50,
                conversions=3.0,
                cost_micros=100_000_000,
                conversion_value_micros=300_000_000,
                start_date=start_date,
                end_date=end_date,
            ),
            DevicePerformanceData(
                customer_id="123",
                campaign_id="111",
                campaign_name="Test",
                device_type=DeviceType.MOBILE,  # Another mobile entry
                impressions=800,
                clicks=80,
                conversions=4.0,
                cost_micros=160_000_000,
                conversion_value_micros=400_000_000,
                start_date=start_date,
                end_date=end_date,
            ),
        ]

        groups = analyzer._group_data_by_device_type(data)

        assert len(groups) == 2  # Mobile and Desktop
        assert DeviceType.MOBILE in groups
        assert DeviceType.DESKTOP in groups
        assert len(groups[DeviceType.MOBILE]) == 2  # Two mobile entries
        assert len(groups[DeviceType.DESKTOP]) == 1  # One desktop entry

    def test_negative_cost_conversion_value_handling(
        self, analyzer, start_date, end_date
    ):
        """Test handling of negative cost and conversion values."""
        test_data = [
            {
                "customer_id": "123456789",
                "campaign_id": "1111",
                "campaign": "Test Campaign",
                "device": "Mobile phones",
                "impressions": 1000,
                "clicks": 100,
                "conversions": 5.0,
                "cost": -50.0,  # Negative cost
                "conversion_value": -100.0,  # Negative conversion value
            }
        ]

        performance_data = analyzer._convert_to_performance_data(
            test_data, start_date, end_date
        )

        assert len(performance_data) == 1
        mobile_data = performance_data[0]
        assert mobile_data.cost == 0.0  # Should be clamped to 0
        assert mobile_data.conversion_value == 0.0  # Should be clamped to 0

    def test_create_dashboard_metrics(self, analyzer):
        """Test dashboard metrics creation."""
        summary = DevicePerformanceSummary(
            customer_id="123",
            analysis_date=datetime.now(),
            date_range_start=datetime.now(),
            date_range_end=datetime.now(),
            total_devices=3,
            total_cost=1000.0,
            total_conversions=20.0,
            total_clicks=500,
            total_impressions=10000,
            average_cpc=2.0,
            average_conversion_rate=0.04,
            average_roas=1.5,
            device_distribution={"Mobile": 2, "Desktop": 1},
            cpc_variance_percentage=25.0,
            conversion_rate_variance_percentage=30.0,
            optimization_potential=30.0,
            mobile_optimization_needed=True,
            desktop_opportunity=True,
            tablet_underperformance=False,
        )

        insights = [
            DeviceInsight(
                device_type=DeviceType.MOBILE,
                performance_score=80.0,
                cpc_vs_average=1.0,
                conversion_rate_vs_average=1.0,
                roas_vs_average=1.0,
                click_share=0.6,
                cost_share=0.6,
                conversion_share=0.6,
                recommended_action="INCREASE_INVESTMENT",
                bid_adjustment_recommendation="Test",
                budget_recommendation="Test",
                optimization_opportunity="Test",
            ),
            DeviceInsight(
                device_type=DeviceType.DESKTOP,
                performance_score=60.0,
                cpc_vs_average=1.0,
                conversion_rate_vs_average=1.0,
                roas_vs_average=1.0,
                click_share=0.4,
                cost_share=0.4,
                conversion_share=0.4,
                recommended_action="MAINTAIN_CURRENT",
                bid_adjustment_recommendation="Test",
                budget_recommendation="Test",
                optimization_opportunity="Test",
            ),
        ]

        metrics = analyzer._create_dashboard_metrics(summary, insights)

        assert metrics["total_devices"] == 3.0
        assert metrics["average_cpc"] == 2.0
        assert metrics["average_conversion_rate"] == 4.0  # Converted to percentage
        assert metrics["cpc_variance_percentage"] == 25.0
        assert metrics["optimization_potential"] == 30.0
        assert (
            metrics["mobile_optimization_needed"] == 1.0
        )  # Boolean converted to float
        assert metrics["desktop_opportunity"] == 1.0
