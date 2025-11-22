"""Unit tests for PerformanceMaxExporter."""

import json
from datetime import datetime

import pytest

from paidsearchnav.core.models.analysis import (
    PerformanceMaxAnalysisResult,
    Recommendation,
    RecommendationPriority,
    RecommendationType,
)
from paidsearchnav.core.models.campaign import (
    BiddingStrategy,
    Campaign,
    CampaignStatus,
    CampaignType,
)
from paidsearchnav.exporters.pmax_exporter import PerformanceMaxExporter


@pytest.fixture
def sample_pmax_result():
    """Create a sample Performance Max analysis result."""
    campaign = Campaign(
        campaign_id="123456789",
        customer_id="987654321",
        name="Test PMax Campaign",
        status=CampaignStatus.ENABLED,
        type=CampaignType.PERFORMANCE_MAX,
        budget_amount=1000.0,
        budget_currency="USD",
        bidding_strategy=BiddingStrategy.TARGET_ROAS,
        target_roas=3.0,
        impressions=10000,
        clicks=500,
        cost=200.0,
        conversions=50.0,
        conversion_value=1500.0,
    )

    recommendation = Recommendation(
        priority=RecommendationPriority.HIGH,
        type=RecommendationType.OPTIMIZE_BIDDING,
        title="Optimize PMax Campaign",
        description="Campaign performance can be improved",
        estimated_impact="20% improvement in ROAS",
    )

    return PerformanceMaxAnalysisResult(
        customer_id="987654321",
        analyzer_name="Performance Max Analyzer",
        start_date=datetime(2023, 1, 1),
        end_date=datetime(2023, 1, 31),
        pmax_campaigns=[campaign],
        search_term_analysis={
            "total_terms": 100,
            "high_volume_terms": [],
            "irrelevant_terms": [],
            "local_intent_terms": [],
            "brand_terms": [],
        },
        overlap_analysis={
            "overlapping_terms": [],
            "overlap_percentage": 15.0,
        },
        asset_performance={
            "campaigns": [],
            "avg_roas": 7.5,
            "total_spend": 200.0,
        },
        findings=[
            {
                "type": "performance_issue",
                "severity": "MEDIUM",
                "title": "Test Finding",
                "description": "Test description",
            }
        ],
        recommendations=[recommendation],
        summary={
            "total_campaigns": 1,
            "total_spend": 200.0,
            "total_conversions": 50.0,
            "average_roas": 7.5,
        },
        metrics={
            "total_pmax_campaigns": 1.0,
            "active_pmax_campaigns": 1.0,
            "total_pmax_spend": 200.0,
            "total_pmax_conversions": 50.0,
            "avg_pmax_roas": 7.5,
        },
        total_pmax_campaigns=1,
        total_pmax_spend=200.0,
        total_pmax_conversions=50.0,
        avg_pmax_roas=7.5,
        overlap_percentage=15.0,
    )


@pytest.fixture
def exporter():
    """Create a PerformanceMaxExporter instance."""
    return PerformanceMaxExporter()


class TestPerformanceMaxExporter:
    """Test cases for PerformanceMaxExporter."""

    def test_get_supported_formats(self, exporter):
        """Test getting supported export formats."""
        formats = exporter.get_supported_formats()
        assert "csv" in formats
        assert "xlsx" in formats
        assert "json" in formats

    def test_export_invalid_data_type(self, exporter):
        """Test export with invalid data type."""
        with pytest.raises(
            ValueError, match="Data must be a PerformanceMaxAnalysisResult"
        ):
            exporter.export(data="invalid", filename="test.csv")

    def test_export_unsupported_format(self, exporter, sample_pmax_result):
        """Test export with unsupported format."""
        with pytest.raises(ValueError, match="Unsupported format"):
            exporter.export(data=sample_pmax_result, filename="test.txt", format="txt")

    def test_export_csv(self, exporter, sample_pmax_result):
        """Test CSV export."""
        result = exporter.export(
            data=sample_pmax_result, filename="test.csv", format="csv"
        )

        assert isinstance(result, bytes)
        content = result.decode("utf-8")

        # Check for key sections
        assert "Performance Max Analysis Summary" in content
        assert "Campaign Performance" in content
        assert "Recommendations" in content
        assert sample_pmax_result.customer_id in content
        assert "Test PMax Campaign" in content

    def test_export_xlsx(self, exporter, sample_pmax_result):
        """Test Excel export."""
        result = exporter.export(
            data=sample_pmax_result, filename="test.xlsx", format="xlsx"
        )

        assert isinstance(result, bytes)
        assert len(result) > 1000  # Should be a substantial file

    def test_export_json(self, exporter, sample_pmax_result):
        """Test JSON export."""
        result = exporter.export(
            data=sample_pmax_result, filename="test.json", format="json"
        )

        assert isinstance(result, bytes)
        content = result.decode("utf-8")

        # Parse JSON to ensure it's valid
        data = json.loads(content)

        assert "analysis_summary" in data
        assert "campaign_performance" in data
        assert "recommendations" in data
        assert data["analysis_summary"]["customer_id"] == "987654321"
        assert len(data["campaign_performance"]) == 1

    def test_export_csv_with_options(self, exporter, sample_pmax_result):
        """Test CSV export with custom options."""
        result = exporter.export(
            data=sample_pmax_result,
            filename="test.csv",
            format="csv",
            include_details=False,
            include_overlaps=False,
            include_recommendations=False,
        )

        content = result.decode("utf-8")

        # Should still have summary
        assert "Performance Max Analysis Summary" in content
        # Should have campaign performance
        assert "Campaign Performance" in content

    def test_export_xlsx_with_options(self, exporter, sample_pmax_result):
        """Test Excel export with custom options."""
        result = exporter.export(
            data=sample_pmax_result,
            filename="test.xlsx",
            format="xlsx",
            include_details=True,
            include_overlaps=True,
            include_recommendations=True,
        )

        assert isinstance(result, bytes)
        assert len(result) > 1000

    def test_export_json_structure(self, exporter, sample_pmax_result):
        """Test JSON export structure in detail."""
        result = exporter.export(
            data=sample_pmax_result, filename="test.json", format="json"
        )

        data = json.loads(result.decode("utf-8"))

        # Check analysis summary structure
        summary = data["analysis_summary"]
        assert summary["analyzer_name"] == "Performance Max Analyzer"
        assert summary["customer_id"] == "987654321"
        assert summary["total_pmax_campaigns"] == 1
        assert summary["total_pmax_spend"] == 200.0
        assert summary["avg_pmax_roas"] == 7.5

        # Check campaign performance structure
        campaigns = data["campaign_performance"]
        assert len(campaigns) == 1
        assert campaigns[0]["campaign_id"] == "123456789"
        assert campaigns[0]["campaign_name"] == "Test PMax Campaign"
        assert campaigns[0]["performance_status"] == "Good"  # ROAS > 1.5

        # Check recommendations structure
        recommendations = data["recommendations"]
        assert len(recommendations) == 1
        assert recommendations[0]["priority"] == "HIGH"
        assert recommendations[0]["type"] == "OPTIMIZE_BIDDING"
        assert recommendations[0]["title"] == "Optimize PMax Campaign"

    def test_export_with_empty_result(self, exporter):
        """Test export with minimal data."""
        minimal_result = PerformanceMaxAnalysisResult(
            customer_id="123456789",
            analyzer_name="Performance Max Analyzer",
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2023, 1, 31),
        )

        # Should not raise an error
        csv_result = exporter.export(minimal_result, "test.csv", "csv")
        assert isinstance(csv_result, bytes)

        json_result = exporter.export(minimal_result, "test.json", "json")
        assert isinstance(json_result, bytes)

    def test_csv_encoding(self, exporter, sample_pmax_result):
        """Test CSV export handles encoding correctly."""
        result = exporter.export(sample_pmax_result, "test.csv", "csv")

        # Should be properly encoded as UTF-8
        content = result.decode("utf-8")
        assert isinstance(content, str)

        # Check that currency symbols and special characters are handled
        assert "$" in content

    def test_json_serialization(self, exporter, sample_pmax_result):
        """Test JSON export handles serialization correctly."""
        result = exporter.export(sample_pmax_result, "test.json", "json")

        # Should be valid JSON
        data = json.loads(result.decode("utf-8"))

        # Ensure dates are properly serialized
        assert "date_range" in data["analysis_summary"]
        assert "start_date" in data["analysis_summary"]["date_range"]
        assert "end_date" in data["analysis_summary"]["date_range"]
