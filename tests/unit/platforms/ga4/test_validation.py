"""Tests for GA4 data validation functionality."""

from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest

from paidsearchnav_mcp.platforms.ga4.bigquery_client import GA4BigQueryClient
from paidsearchnav_mcp.platforms.ga4.validation import GA4DataValidator


class TestGA4DataValidator:
    """Test GA4 data validation functionality."""

    @pytest.fixture
    def mock_ga4_client(self):
        """Mock GA4 BigQuery client."""
        return Mock(spec=GA4BigQueryClient)

    @pytest.fixture
    def validator(self, mock_ga4_client):
        """Create test GA4 data validator."""
        return GA4DataValidator(mock_ga4_client)

    def test_validate_google_ads_data_complete(self, validator):
        """Test Google Ads data validation with complete data."""
        google_ads_data = [
            {"gclid": "gclid1", "cost": 50.0, "conversions": 2},
            {"gclid": "gclid2", "cost": 75.0, "conversions": 3},
            {"gclid": "gclid3", "cost": 25.0, "conversions": 1},
        ]

        result = validator._validate_google_ads_data(google_ads_data)

        assert result["total_records"] == 3
        assert result["records_with_gclids"] == 3
        assert result["gclid_coverage_percent"] == 100.0
        assert result["cost_coverage_percent"] == 100.0
        assert result["conversion_coverage_percent"] == 100.0
        assert result["data_completeness_score"] == 100.0
        assert result["has_gclids"] is True

    def test_validate_google_ads_data_incomplete(self, validator):
        """Test Google Ads data validation with incomplete data."""
        google_ads_data = [
            {"gclid": "gclid1", "cost": 50.0, "conversions": 2},
            {"cost": 75.0, "conversions": 3},  # Missing GCLID
            {"gclid": "gclid3"},  # Missing cost and conversions
        ]

        result = validator._validate_google_ads_data(google_ads_data)

        assert result["total_records"] == 3
        assert result["records_with_gclids"] == 2
        assert result["gclid_coverage_percent"] == 66.67
        assert result["cost_coverage_percent"] == 66.67
        assert result["conversion_coverage_percent"] == 66.67
        assert result["data_completeness_score"] == 66.67

    def test_validate_google_ads_data_empty(self, validator):
        """Test Google Ads data validation with empty data."""
        result = validator._validate_google_ads_data([])

        assert result["total_records"] == 0
        assert result["quality_score"] == 0.0
        assert result["has_gclids"] is False

    def test_validate_ga4_data_availability(self, validator, mock_ga4_client):
        """Test GA4 data availability validation."""
        # Mock recent tables
        recent_date = datetime.now().strftime("%Y%m%d")
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")

        mock_tables = [
            f"events_{recent_date}",
            f"events_{yesterday}",
            f"events_intraday_{recent_date}",
            "events_20240101",  # Old table
        ]

        mock_ga4_client.discover_ga4_tables.return_value = mock_tables

        start_date = datetime.now() - timedelta(days=7)
        end_date = datetime.now()

        result = validator._validate_ga4_data_availability(start_date, end_date)

        assert result["total_tables_available"] == 4
        assert result["recent_tables_count"] >= 2
        assert result["data_lag_days"] <= 1
        assert result["overall_quality_score"] > 50

    def test_validate_ga4_data_availability_no_recent_data(
        self, validator, mock_ga4_client
    ):
        """Test GA4 data availability validation with no recent data."""
        mock_ga4_client.discover_ga4_tables.return_value = [
            "events_20240101",
            "events_20240102",
        ]

        start_date = datetime.now() - timedelta(days=7)
        end_date = datetime.now()

        result = validator._validate_ga4_data_availability(start_date, end_date)

        assert result["recent_tables_count"] == 0
        assert result["data_lag_days"] == 999
        assert result["overall_quality_score"] == 0.0

    def test_generate_data_quality_recommendations_low_gclid_coverage(self, validator):
        """Test recommendations for low GCLID coverage."""
        ads_quality = {"gclid_coverage_percent": 45.0, "quality_score": 45.0}
        ga4_quality = {"overall_quality_score": 80.0, "data_lag_days": 1}
        attribution_quality = {"match_rate_percent": 40.0, "data_quality_score": 40.0}

        recommendations = validator._generate_data_quality_recommendations(
            ads_quality, ga4_quality, attribution_quality
        )

        # Should have recommendations for GCLID tracking and attribution matching
        assert len(recommendations) >= 2
        assert any("GCLID tracking" in rec["title"] for rec in recommendations)
        assert any("attribution matching" in rec["title"] for rec in recommendations)

    def test_generate_data_quality_recommendations_high_quality(self, validator):
        """Test recommendations for high-quality setup."""
        ads_quality = {"gclid_coverage_percent": 95.0, "quality_score": 95.0}
        ga4_quality = {"overall_quality_score": 90.0, "data_lag_days": 1}
        attribution_quality = {"match_rate_percent": 85.0, "data_quality_score": 85.0}

        recommendations = validator._generate_data_quality_recommendations(
            ads_quality, ga4_quality, attribution_quality
        )

        # Should have positive recommendation for excellent setup
        assert any(
            "Excellent attribution setup" in rec["title"] for rec in recommendations
        )

    def test_calculate_overall_quality_score(self, validator):
        """Test overall quality score calculation."""
        ads_quality = {"quality_score": 80.0}
        ga4_quality = {"overall_quality_score": 70.0}
        attribution_quality = {"data_quality_score": 90.0}

        score = validator._calculate_overall_quality_score(
            ads_quality, ga4_quality, attribution_quality
        )

        # Score should be weighted average: 80*0.3 + 70*0.3 + 90*0.4 = 81
        assert score == 81.0

    def test_validate_export_data_quality(self, validator, mock_ga4_client):
        """Test complete export data quality validation."""
        google_ads_data = [
            {"gclid": "gclid1", "cost": 50.0, "conversions": 2},
            {"gclid": "gclid2", "cost": 75.0, "conversions": 3},
        ]

        # Mock GA4 client methods
        mock_ga4_client.validate_gclid_matching.return_value = {
            "total_google_ads_clicks": 2,
            "matched_sessions": 2,
            "match_rate_percent": 100.0,
            "data_quality_score": 95.0,
        }

        validator.ga4_client = mock_ga4_client

        start_date = datetime(2024, 12, 1)
        end_date = datetime(2024, 12, 7)

        with patch.object(
            validator,
            "_validate_ga4_data_availability",
            return_value={"overall_quality_score": 85.0},
        ):
            result = validator.validate_export_data_quality(
                google_ads_data, start_date, end_date
            )

        assert "validation_timestamp" in result
        assert result["google_ads_data_quality"]["total_records"] == 2
        assert result["attribution_quality"]["match_rate_percent"] == 100.0
        assert result["overall_quality_score"] > 80

    def test_validate_real_time_data_sync(self, validator, mock_ga4_client):
        """Test real-time data sync validation."""
        recent_date = datetime.now().strftime("%Y%m%d")
        mock_tables = [
            f"events_{recent_date}",
            f"events_intraday_{recent_date}",
        ]

        mock_ga4_client.discover_ga4_tables.return_value = mock_tables
        mock_ga4_client._execute_query.return_value = [{"event_count": 150}]

        validator.ga4_client = mock_ga4_client

        result = validator.validate_real_time_data_sync(24)

        assert result["intraday_tables_available"] == 1
        assert result["recent_events_count"] == 150
        assert result["sync_quality_score"] > 50
        assert result["real_time_ready"] is True

    def test_run_comprehensive_validation(self, validator, mock_ga4_client):
        """Test comprehensive validation pipeline."""
        google_ads_data = [
            {"gclid": "gclid1", "cost": 50.0, "conversions": 2},
        ]

        start_date = datetime(2024, 12, 1)
        end_date = datetime(2024, 12, 7)

        # Mock all validation methods
        with patch.object(validator, "validate_export_data_quality") as mock_export:
            with patch.object(validator, "validate_real_time_data_sync") as mock_sync:
                mock_export.return_value = {
                    "validation_summary": {"overall_quality_score": 85.0},
                    "recommendations": [],
                }
                mock_sync.return_value = {
                    "real_time_ready": True,
                    "sync_quality_score": 75.0,
                }

                result = validator.run_comprehensive_validation(
                    google_ads_data, start_date, end_date
                )

        assert "validation_summary" in result
        assert "export_data_quality" in result
        assert "real_time_sync_quality" in result
        assert result["validation_summary"]["export_pipeline_ready"] is True
        assert result["validation_summary"]["real_time_ready"] is True
