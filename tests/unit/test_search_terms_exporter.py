"""Unit tests for SearchTermsExporter."""

import csv
import io
import json
from datetime import datetime

import pandas as pd
import pytest

from paidsearchnav.core.models import (
    SearchTerm,
    SearchTermAnalysisResult,
    SearchTermClassification,
    SearchTermMetrics,
)
from paidsearchnav.exporters.search_terms_exporter import SearchTermsExporter


@pytest.fixture
def sample_search_terms():
    """Create sample search terms for testing."""
    return [
        SearchTerm(
            search_term="widgets near me",
            campaign_id="123",
            campaign_name="Widgets Campaign",
            ad_group_id="456",
            ad_group_name="Widget Ad Group",
            date_start=datetime(2024, 1, 1).date(),
            date_end=datetime(2024, 1, 31).date(),
            metrics=SearchTermMetrics(
                impressions=1000,
                clicks=100,
                cost=200.0,
                conversions=10.0,
                conversion_value=1000.0,
            ),
            classification=SearchTermClassification.ADD_CANDIDATE,
            classification_reason="High performing",
            recommendation="Add as Exact match keyword",
            has_location=True,
            has_near_me=True,
        ),
        SearchTerm(
            search_term="cheap widgets",
            campaign_id="123",
            campaign_name="Widgets Campaign",
            ad_group_id="456",
            ad_group_name="Widget Ad Group",
            date_start=datetime(2024, 1, 1).date(),
            date_end=datetime(2024, 1, 31).date(),
            metrics=SearchTermMetrics(
                impressions=500,
                clicks=50,
                cost=100.0,
                conversions=0.0,
                conversion_value=0.0,
            ),
            classification=SearchTermClassification.NEGATIVE_CANDIDATE,
            classification_reason="Wasteful spend",
            recommendation="Add as negative keyword at campaign level",
            has_location=False,
            has_near_me=False,
        ),
    ]


@pytest.fixture
def sample_analysis_result(sample_search_terms):
    """Create sample analysis result for testing."""
    from paidsearchnav.core.models import (
        Recommendation,
        RecommendationPriority,
        RecommendationType,
    )

    return SearchTermAnalysisResult(
        customer_id="12345",
        analysis_type="search_terms",
        analyzer_name="Search Terms Analyzer",
        start_date=datetime(2024, 1, 1),
        end_date=datetime(2024, 1, 31),
        total_search_terms=2,
        total_impressions=1500,
        total_clicks=150,
        total_cost=300.0,
        total_conversions=10.0,
        add_candidates=[sample_search_terms[0]],
        negative_candidates=[sample_search_terms[1]],
        already_covered=[],
        review_needed=[],
        classification_summary={
            SearchTermClassification.ADD_CANDIDATE: 1,
            SearchTermClassification.NEGATIVE_CANDIDATE: 1,
        },
        local_intent_terms=1,
        near_me_terms=1,
        potential_savings=100.0,
        potential_revenue=1000.0,
        recommendations=[
            Recommendation(
                type=RecommendationType.ADD_KEYWORD,
                priority=RecommendationPriority.HIGH,
                title="Add high-performing keywords",
                description="Add 1 high-performing search terms as keywords",
            ),
            Recommendation(
                type=RecommendationType.ADD_NEGATIVE,
                priority=RecommendationPriority.HIGH,
                title="Add negative keywords",
                description="Add 1 negative keywords to save $100.00",
            ),
        ],
    )


@pytest.fixture
def exporter():
    """Create SearchTermsExporter instance."""
    return SearchTermsExporter()


class TestSearchTermsExporter:
    """Test SearchTermsExporter functionality."""

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
        assert any("Search Terms Analysis Summary" in row for row in rows)
        assert any("Analysis Date:" in row[0] if row else False for row in rows)
        assert any("Total Search Terms:" in row[0] if row else False for row in rows)

        # Check classification summary
        assert any("Classification Summary" in row for row in rows)
        assert any("Add Candidates" in row[0] if row else False for row in rows)
        assert any("Negative Candidates" in row[0] if row else False for row in rows)

    def test_export_csv_with_details(self, exporter, sample_analysis_result):
        """Test CSV export with detailed search terms."""
        csv_bytes = exporter.export(
            data=sample_analysis_result,
            filename="test.csv",
            format="csv",
            include_details=True,
        )

        csv_content = csv_bytes.decode("utf-8-sig")

        # Check for search term details
        assert "widgets near me" in csv_content
        assert "cheap widgets" in csv_content
        assert "Add Candidates - High Performing Search Terms" in csv_content
        assert "Negative Candidates - Poor Performing Search Terms" in csv_content

    def test_export_csv_without_details(self, exporter, sample_analysis_result):
        """Test CSV export without detailed search terms."""
        csv_bytes = exporter.export(
            data=sample_analysis_result,
            filename="test.csv",
            format="csv",
            include_details=False,
        )

        csv_content = csv_bytes.decode("utf-8-sig")

        # Should not include individual search terms
        assert "widgets near me" not in csv_content
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
        assert "Add Candidates" in excel_file.sheet_names
        assert "Negative Candidates" in excel_file.sheet_names
        assert "Recommendations" in excel_file.sheet_names

        # Check summary sheet
        summary_df = pd.read_excel(excel_file, sheet_name="Summary")
        assert not summary_df.empty
        assert "Total Search Terms" in summary_df["Metric"].values

        # Check add candidates sheet
        add_df = pd.read_excel(excel_file, sheet_name="Add Candidates")
        assert not add_df.empty
        assert "widgets near me" in add_df["Search Term"].values

    def test_export_xlsx_with_review(self, exporter, sample_analysis_result):
        """Test Excel export with review needed sheet."""
        # Add a review needed term
        review_term = SearchTerm(
            search_term="widget reviews",
            campaign_id="123",
            campaign_name="Widgets Campaign",
            ad_group_id="456",
            ad_group_name="Widget Ad Group",
            date_start=datetime(2024, 1, 1).date(),
            date_end=datetime(2024, 1, 31).date(),
            metrics=SearchTermMetrics(
                impressions=200,
                clicks=20,
                cost=40.0,
                conversions=0.5,
                conversion_value=50.0,
            ),
            classification=SearchTermClassification.REVIEW_NEEDED,
            classification_reason="Borderline performance",
        )
        sample_analysis_result.review_needed.append(review_term)

        xlsx_bytes = exporter.export(
            data=sample_analysis_result,
            filename="test.xlsx",
            format="xlsx",
            include_review=True,
        )

        excel_file = pd.ExcelFile(io.BytesIO(xlsx_bytes))
        assert "Review Needed" in excel_file.sheet_names

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
        assert "summary" in json_data
        assert "add_candidates" in json_data
        assert "negative_candidates" in json_data
        assert "recommendations" in json_data

        # Check summary data
        assert json_data["summary"]["account"] == "12345"
        assert json_data["summary"]["summary"]["total_search_terms"] == 2

        # Check search terms
        assert len(json_data["add_candidates"]) == 1
        assert json_data["add_candidates"][0]["search_term"] == "widgets near me"
        assert json_data["add_candidates"][0]["local_intent"] is True

    def test_export_json_with_limit(self, exporter, sample_analysis_result):
        """Test JSON export with limit."""
        # Add more candidates to test limit
        for i in range(10):
            sample_analysis_result.add_candidates.append(
                SearchTerm(
                    search_term=f"widget {i}",
                    campaign_id="123",
                    campaign_name="Campaign",
                    ad_group_id="456",
                    ad_group_name="Ad Group",
                    date_start=datetime(2024, 1, 1).date(),
                    date_end=datetime(2024, 1, 31).date(),
                    metrics=SearchTermMetrics(
                        impressions=100,
                        clicks=10,
                        cost=20.0,
                        conversions=1.0,
                        conversion_value=100.0,
                    ),
                )
            )

        json_bytes = exporter.export(
            data=sample_analysis_result,
            filename="test.json",
            format="json",
            limit=5,
        )

        json_data = json.loads(json_bytes.decode("utf-8"))
        assert len(json_data["add_candidates"]) == 5  # Limited to 5

    def test_export_unsupported_format(self, exporter, sample_analysis_result):
        """Test exporting to unsupported format."""
        with pytest.raises(ValueError, match="Unsupported format"):
            exporter.export(
                data=sample_analysis_result,
                filename="test.txt",
                format="txt",
            )

    def test_csv_metrics_formatting(self, exporter, sample_analysis_result):
        """Test CSV metrics are properly formatted."""
        csv_bytes = exporter.export(
            data=sample_analysis_result,
            filename="test.csv",
            format="csv",
            include_details=True,
        )

        csv_content = csv_bytes.decode("utf-8-sig")

        # Check currency formatting
        assert "$300.00" in csv_content  # Total cost
        assert "$200.00" in csv_content  # Cost for a search term

        # Check percentage formatting
        assert "10.00" in csv_content  # CTR or conversion rate

    def test_json_null_handling(self, exporter, sample_analysis_result):
        """Test JSON export handles null values properly."""
        # Add term with no CPA (no conversions)
        term = SearchTerm(
            search_term="no conversions",
            campaign_id="123",
            campaign_name="Campaign",
            ad_group_id="456",
            ad_group_name="Ad Group",
            date_start=datetime(2024, 1, 1).date(),
            date_end=datetime(2024, 1, 31).date(),
            metrics=SearchTermMetrics(
                impressions=100,
                clicks=10,
                cost=20.0,
                conversions=0.0,
                conversion_value=0.0,
            ),
        )
        sample_analysis_result.negative_candidates.append(term)

        json_bytes = exporter.export(
            data=sample_analysis_result,
            filename="test.json",
            format="json",
        )

        json_data = json.loads(json_bytes.decode("utf-8"))

        # Find the term with no conversions
        no_conv_term = next(
            t
            for t in json_data["negative_candidates"]
            if t["search_term"] == "no conversions"
        )

        # CPA should be null when no conversions
        assert no_conv_term["metrics"]["cpa"] is None
