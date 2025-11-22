"""Integration tests for negative keyword CSV parsing with real test data."""

from datetime import datetime
from pathlib import Path

import pytest

from paidsearchnav.analyzers.negative_conflicts import NegativeConflictAnalyzer
from paidsearchnav.analyzers.shared_negatives import SharedNegativeValidatorAnalyzer

# Path to test data directory
TEST_DATA_DIR = Path(__file__).parent.parent.parent / "test_data"


class TestNegativeKeywordCSVIntegration:
    """Integration tests using real CSV test data files."""

    @pytest.mark.integration
    def test_parse_negative_keywords_export(self):
        """Test parsing the negative_keywords_export.csv file."""
        csv_path = TEST_DATA_DIR / "google_ads_exports" / "negative_keywords_export.csv"

        if not csv_path.exists():
            pytest.skip(f"Test data file not found: {csv_path}")

        # Parse the CSV
        analyzer = NegativeConflictAnalyzer.from_csv(csv_path)

        # Verify data was loaded
        assert analyzer._csv_negative_keywords is not None
        assert len(analyzer._csv_negative_keywords) > 0

        # Check that we have different levels of negatives
        levels = {kw["level"] for kw in analyzer._csv_negative_keywords}
        assert "CAMPAIGN" in levels or "AD_GROUP" in levels

        # Check that we have different match types
        match_types = {kw["match_type"] for kw in analyzer._csv_negative_keywords}
        assert len(match_types) > 0  # Should have at least one match type

    @pytest.mark.integration
    def test_parse_shared_negative_lists_export(self):
        """Test parsing the shared_negative_lists_export.csv file."""
        csv_path = (
            TEST_DATA_DIR / "google_ads_exports" / "shared_negative_lists_export.csv"
        )

        if not csv_path.exists():
            pytest.skip(f"Test data file not found: {csv_path}")

        # Parse the CSV
        analyzer = SharedNegativeValidatorAnalyzer.from_csv(csv_path)

        # Verify data was loaded
        assert analyzer._csv_shared_lists is not None
        assert len(analyzer._csv_shared_lists) > 0

        # Check that lists have negative keywords
        for shared_list in analyzer._csv_shared_lists:
            assert "name" in shared_list
            assert "negative_keywords" in shared_list
            assert len(shared_list["negative_keywords"]) > 0

            # Check keyword structure
            for keyword in shared_list["negative_keywords"]:
                assert "text" in keyword
                assert "match_type" in keyword
                assert keyword["match_type"] in ["EXACT", "PHRASE", "BROAD"]

    @pytest.mark.integration
    def test_parse_fitness_connection_negative_report(self):
        """Test parsing the Fitness Connection negative keyword report."""
        csv_path = (
            TEST_DATA_DIR / "exports" / "Negative-keyword-report-fitness-connection.csv"
        )

        if not csv_path.exists():
            pytest.skip(f"Test data file not found: {csv_path}")

        # Parse the CSV
        analyzer = NegativeConflictAnalyzer.from_csv(csv_path)

        # Verify data was loaded
        assert analyzer._csv_negative_keywords is not None
        assert len(analyzer._csv_negative_keywords) > 0

        # Check that keywords are properly parsed
        for keyword in analyzer._csv_negative_keywords:
            assert keyword["text"]  # Should have text
            assert keyword["match_type"] in ["EXACT", "PHRASE", "BROAD"]
            assert keyword["level"] in ["CAMPAIGN", "AD_GROUP", "SHARED"]

            # Fitness Connection data typically has campaign names
            if keyword["campaign_name"]:
                assert "PP_FIT" in keyword["campaign_name"] or keyword["campaign_name"]

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_analyze_with_real_csv_data(self):
        """Test running analysis with real CSV data."""
        csv_path = TEST_DATA_DIR / "google_ads_exports" / "negative_keywords_export.csv"

        if not csv_path.exists():
            pytest.skip(f"Test data file not found: {csv_path}")

        # Load analyzer with CSV data
        analyzer = NegativeConflictAnalyzer.from_csv(csv_path)

        # Run analysis (without positive keywords)
        result = await analyzer.analyze(
            customer_id="test_customer",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        # Verify result structure
        assert result is not None
        assert result.analyzer_name == "Negative Keyword Conflict Analyzer"
        assert result.analysis_type == "negative_conflicts"
        assert result.metrics is not None
        assert result.metrics.custom_metrics["total_negative_keywords"] > 0

        # Check raw data structure
        assert "summary" in result.raw_data
        assert result.raw_data["summary"]["total_negative_keywords"] > 0

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_shared_validator_with_real_csv_data(self):
        """Test SharedNegativeValidatorAnalyzer with real CSV data."""
        csv_path = (
            TEST_DATA_DIR / "google_ads_exports" / "shared_negative_lists_export.csv"
        )

        if not csv_path.exists():
            pytest.skip(f"Test data file not found: {csv_path}")

        # Load analyzer with CSV data
        analyzer = SharedNegativeValidatorAnalyzer.from_csv(csv_path)

        # Run analysis (without campaigns)
        result = await analyzer.analyze(
            customer_id="test_customer",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        # Verify result structure
        assert result is not None
        assert result.analyzer_name == "Shared Negative List Validator"
        assert result.analysis_type == "shared_negative_validation"
        assert result.metrics is not None
        assert result.metrics.custom_metrics["total_shared_lists"] > 0

        # Check raw data structure
        assert "validation_status" in result.raw_data
        assert "shared_lists_found" in result.raw_data
        assert result.raw_data["shared_lists_found"] > 0


class TestCSVErrorHandling:
    """Test error handling for various CSV format issues."""

    @pytest.mark.integration
    def test_handle_malformed_csv(self, tmp_path):
        """Test handling of malformed CSV data."""
        # Create a malformed CSV with inconsistent columns
        csv_content = """Campaign,Campaign ID,Ad group
"Campaign 1",123,"Ad Group 1",extra_column
"Campaign 2",124
"""
        csv_path = tmp_path / "malformed.csv"
        csv_path.write_text(csv_content)

        # Should handle gracefully or raise appropriate error
        with pytest.raises(ValueError):
            NegativeConflictAnalyzer.from_csv(csv_path)

    @pytest.mark.integration
    def test_handle_encoding_issues(self, tmp_path):
        """Test handling of encoding issues."""
        # Create a file with non-UTF-8 encoding
        csv_content = b"Campaign,Negative keyword\nCampaign 1,\xff\xfe"
        csv_path = tmp_path / "encoding_issue.csv"
        csv_path.write_bytes(csv_content)

        # Should raise encoding error
        with pytest.raises(ValueError, match="Encoding error"):
            NegativeConflictAnalyzer.from_csv(csv_path)
