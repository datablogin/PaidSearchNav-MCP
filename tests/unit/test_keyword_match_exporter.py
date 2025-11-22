"""Unit tests for KeywordMatchExporter."""

import csv
import io
import json
from datetime import datetime

import pandas as pd
import pytest

from paidsearchnav.core.models import (
    Keyword,
    KeywordMatchAnalysisResult,
    KeywordMatchType,
    KeywordStatus,
    Recommendation,
    RecommendationPriority,
    RecommendationType,
)
from paidsearchnav.exporters.keyword_match_exporter import KeywordMatchExporter


@pytest.fixture
def sample_keywords():
    """Create sample keywords for testing."""
    return [
        Keyword(
            keyword_id="1",
            campaign_id="123",
            campaign_name="Widgets Campaign",
            ad_group_id="456",
            ad_group_name="Widget Ad Group",
            text="cheap widgets",
            match_type=KeywordMatchType.BROAD,
            status=KeywordStatus.ENABLED,
            quality_score=5,
            impressions=10000,
            clicks=500,
            cost=2000.0,
            conversions=10.0,
            conversion_value=1000.0,
        ),
        Keyword(
            keyword_id="2",
            campaign_id="123",
            campaign_name="Widgets Campaign",
            ad_group_id="456",
            ad_group_name="Widget Ad Group",
            text="discount widgets",
            match_type=KeywordMatchType.PHRASE,
            status=KeywordStatus.ENABLED,
            quality_score=4,
            impressions=5000,
            clicks=200,
            cost=800.0,
            conversions=5.0,
            conversion_value=500.0,
        ),
    ]


@pytest.fixture
def sample_analysis_result(sample_keywords):
    """Create sample analysis result for testing."""
    return KeywordMatchAnalysisResult(
        customer_id="12345",
        analyzer_name="Keyword Match Type Analyzer",
        start_date=datetime(2024, 1, 1),
        end_date=datetime(2024, 1, 31),
        total_keywords=50,
        match_type_stats={
            "BROAD": {
                "count": 20,
                "impressions": 100000,
                "clicks": 5000,
                "cost": 10000.0,
                "conversions": 100.0,
                "conversion_value": 10000.0,
                "ctr": 5.0,
                "avg_cpc": 2.0,
                "cpa": 100.0,
                "roas": 1.0,
            },
            "PHRASE": {
                "count": 20,
                "impressions": 80000,
                "clicks": 4000,
                "cost": 6000.0,
                "conversions": 120.0,
                "conversion_value": 12000.0,
                "ctr": 5.0,
                "avg_cpc": 1.5,
                "cpa": 50.0,
                "roas": 2.0,
            },
            "EXACT": {
                "count": 10,
                "impressions": 40000,
                "clicks": 3000,
                "cost": 4000.0,
                "conversions": 100.0,
                "conversion_value": 10000.0,
                "ctr": 7.5,
                "avg_cpc": 1.33,
                "cpa": 40.0,
                "roas": 2.5,
            },
        },
        high_cost_broad_keywords=sample_keywords[:1],
        low_quality_keywords=sample_keywords,
        duplicate_opportunities=[
            {
                "keyword_text": "widget store",
                "match_types_found": ["BROAD", "PHRASE", "EXACT"],
                "recommended_match_type": "EXACT",
                "potential_savings": 500.0,
                "keywords": [],
            }
        ],
        potential_savings=2500.0,
        recommendations=[
            Recommendation(
                type=RecommendationType.PAUSE_KEYWORDS,
                priority=RecommendationPriority.HIGH,
                title="Reduce broad match usage",
                description="Broad match keywords have poor ROAS. Consider pausing or converting to exact match.",
            ),
            Recommendation(
                type=RecommendationType.IMPROVE_QUALITY_SCORE,
                priority=RecommendationPriority.MEDIUM,
                title="Improve low quality keywords",
                description="2 keywords have quality score < 7. Improve ad relevance and landing pages.",
            ),
        ],
    )


@pytest.fixture
def exporter():
    """Create KeywordMatchExporter instance."""
    return KeywordMatchExporter()


class TestKeywordMatchExporter:
    """Test KeywordMatchExporter functionality."""

    def test_supported_formats(self, exporter):
        """Test getting supported export formats."""
        formats = exporter.get_supported_formats()
        assert "csv" in formats
        assert "xlsx" in formats
        assert "json" in formats

    def test_export_csv_basic(self, exporter, sample_analysis_result):
        """Test basic CSV export."""
        csv_bytes = exporter.export(
            data=sample_analysis_result,
            filename="test.csv",
            format="csv",
        )

        # Decode and parse CSV
        csv_content = csv_bytes.decode("utf-8-sig")
        reader = csv.reader(io.StringIO(csv_content))
        rows = list(reader)

        # Check summary section exists
        assert any("Keyword Match Type Analysis Summary" in row for row in rows)
        assert any("Analysis Date:" in row[0] if row else False for row in rows)
        assert any(
            "Total Keywords Analyzed:" in row[0] if row else False for row in rows
        )
        assert any(
            "Potential Monthly Savings:" in row[0] if row else False for row in rows
        )

        # Check match type performance section
        assert any("Match Type Performance" in row for row in rows)
        assert any("BROAD" in row[0] if row else False for row in rows)
        assert any("PHRASE" in row[0] if row else False for row in rows)
        assert any("EXACT" in row[0] if row else False for row in rows)

        # Check issues summary
        assert any("Issues Found" in row for row in rows)
        assert any(
            "High-Cost Broad Keywords:" in row[0] if row else False for row in rows
        )

    def test_export_csv_with_details(self, exporter, sample_analysis_result):
        """Test CSV export with detailed keyword lists."""
        csv_bytes = exporter.export(
            data=sample_analysis_result,
            filename="test.csv",
            format="csv",
            include_details=True,
        )

        csv_content = csv_bytes.decode("utf-8-sig")

        # Check for detailed sections
        assert "High-Cost Broad Match Keywords" in csv_content
        assert "cheap widgets" in csv_content  # Specific keyword
        assert "Low Quality Score Keywords" in csv_content

    def test_export_csv_without_details(self, exporter, sample_analysis_result):
        """Test CSV export without detailed keyword lists."""
        csv_bytes = exporter.export(
            data=sample_analysis_result,
            filename="test.csv",
            format="csv",
            include_details=False,
        )

        csv_content = csv_bytes.decode("utf-8-sig")

        # Should not include detailed keyword lists
        assert "High-Cost Broad Match Keywords" not in csv_content
        assert "cheap widgets" not in csv_content

    def test_export_xlsx_basic(self, exporter, sample_analysis_result):
        """Test basic Excel export."""
        xlsx_bytes = exporter.export(
            data=sample_analysis_result,
            filename="test.xlsx",
            format="xlsx",
        )

        # Read Excel file
        excel_file = pd.ExcelFile(io.BytesIO(xlsx_bytes))

        # Check sheets exist
        assert "Summary" in excel_file.sheet_names
        assert "Match Type Performance" in excel_file.sheet_names
        assert "Recommendations" in excel_file.sheet_names
        assert "High-Cost Broad" in excel_file.sheet_names
        assert "Low Quality" in excel_file.sheet_names

        # Check summary sheet
        summary_df = pd.read_excel(excel_file, sheet_name="Summary")
        assert not summary_df.empty

        # Check performance sheet
        perf_df = pd.read_excel(excel_file, sheet_name="Match Type Performance")
        assert not perf_df.empty
        assert "Match Type" in perf_df.columns
        assert "Cost" in perf_df.columns
        assert "ROAS" in perf_df.columns

    def test_export_xlsx_with_duplicates(self, exporter, sample_analysis_result):
        """Test Excel export with duplicate opportunities sheet."""
        xlsx_bytes = exporter.export(
            data=sample_analysis_result,
            filename="test.xlsx",
            format="xlsx",
            include_duplicates=True,
        )

        excel_file = pd.ExcelFile(io.BytesIO(xlsx_bytes))
        assert "Duplicates" in excel_file.sheet_names

        # Check duplicates sheet
        dup_df = pd.read_excel(excel_file, sheet_name="Duplicates")
        assert not dup_df.empty

    def test_export_json_basic(self, exporter, sample_analysis_result):
        """Test basic JSON export."""
        json_bytes = exporter.export(
            data=sample_analysis_result,
            filename="test.json",
            format="json",
        )

        # Parse JSON
        json_data = json.loads(json_bytes.decode("utf-8"))

        # Check structure
        assert "analysis_metadata" in json_data
        assert "summary" in json_data
        assert "match_type_performance" in json_data
        assert "recommendations" in json_data

        # Check metadata
        assert json_data["analysis_metadata"]["customer_id"] == "12345"
        assert json_data["summary"]["total_keywords"] == 50
        assert json_data["summary"]["potential_monthly_savings"] == 2500.0

        # Check match type performance
        assert "BROAD" in json_data["match_type_performance"]
        assert json_data["match_type_performance"]["BROAD"]["count"] == 20

        # Check recommendations
        assert len(json_data["recommendations"]) == 2
        assert json_data["recommendations"][0]["priority"] == "HIGH"

    def test_export_json_with_details(self, exporter, sample_analysis_result):
        """Test JSON export with detailed keyword lists."""
        json_bytes = exporter.export(
            data=sample_analysis_result,
            filename="test.json",
            format="json",
            include_details=True,
        )

        json_data = json.loads(json_bytes.decode("utf-8"))

        # Check for detailed sections
        assert "high_cost_broad_keywords" in json_data
        assert len(json_data["high_cost_broad_keywords"]) == 1
        assert json_data["high_cost_broad_keywords"][0]["keyword"] == "cheap widgets"

        assert "low_quality_keywords" in json_data
        assert len(json_data["low_quality_keywords"]) == 2

    def test_export_json_with_duplicates(self, exporter, sample_analysis_result):
        """Test JSON export with duplicate opportunities."""
        json_bytes = exporter.export(
            data=sample_analysis_result,
            filename="test.json",
            format="json",
            include_duplicates=True,
        )

        json_data = json.loads(json_bytes.decode("utf-8"))

        assert "duplicate_opportunities" in json_data
        assert len(json_data["duplicate_opportunities"]) == 1
        assert json_data["duplicate_opportunities"][0]["keyword_text"] == "widget store"

    def test_export_unsupported_format(self, exporter, sample_analysis_result):
        """Test exporting to unsupported format."""
        with pytest.raises(ValueError, match="Unsupported format"):
            exporter.export(
                data=sample_analysis_result,
                filename="test.txt",
                format="txt",
            )

    def test_export_invalid_data(self, exporter):
        """Test exporting invalid data type."""
        with pytest.raises(ValueError, match="must be a KeywordMatchAnalysisResult"):
            exporter.export(
                data={"invalid": "data"},
                filename="test.csv",
                format="csv",
            )

    def test_csv_formatting(self, exporter, sample_analysis_result):
        """Test CSV formatting of numbers and percentages."""
        csv_bytes = exporter.export(
            data=sample_analysis_result,
            filename="test.csv",
            format="csv",
        )

        csv_content = csv_bytes.decode("utf-8-sig")

        # Check currency formatting
        assert "$2,500.00" in csv_content  # Potential savings
        assert "$10,000.00" in csv_content  # Broad match cost

        # Check percentage formatting
        assert "5.00%" in csv_content  # CTR

    def test_json_null_handling(self, exporter):
        """Test JSON export handles keywords with no conversions."""
        # Create keyword with no conversions
        keyword = Keyword(
            keyword_id="1",
            campaign_id="123",
            campaign_name="Campaign",
            ad_group_id="456",
            ad_group_name="Ad Group",
            text="no conversions",
            match_type=KeywordMatchType.BROAD,
            status=KeywordStatus.ENABLED,
            quality_score=7,
            impressions=1000,
            clicks=100,
            cost=200.0,
            conversions=0.0,
            conversion_value=0.0,
        )

        result = KeywordMatchAnalysisResult(
            customer_id="12345",
            analyzer_name="Test",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
            total_keywords=1,
            match_type_stats={},
            high_cost_broad_keywords=[keyword],
            low_quality_keywords=[],
            duplicate_opportunities=[],
            potential_savings=0.0,
            recommendations=[],
        )

        json_bytes = exporter.export(
            data=result,
            filename="test.json",
            format="json",
            include_details=True,
        )

        json_data = json.loads(json_bytes.decode("utf-8"))

        # CPA should be null when no conversions
        assert json_data["high_cost_broad_keywords"][0]["cpa"] is None
