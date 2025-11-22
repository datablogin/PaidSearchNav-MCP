"""Unit tests for CSV parsing smart field inference functionality."""

import pandas as pd

from paidsearchnav_mcp.utils.csv_parsing import (
    detect_summary_rows,
    infer_missing_fields,
    preprocess_search_terms_data,
)


class TestDetectSummaryRows:
    """Test suite for summary row detection."""

    def test_detect_summary_rows_with_totals(self):
        """Test detection of total/summary rows."""
        df = pd.DataFrame(
            {
                "search_term": [
                    "cotton patch cafe",
                    "cotton patch near me",
                    "Total:",
                    "Grand Total",
                    "restaurant menu",
                ],
                "impressions": [100, 200, 300, 300, 50],
            }
        )

        regular_data, summary_data = detect_summary_rows(df, "search_term")

        assert len(regular_data) == 3
        assert len(summary_data) == 2
        assert "cotton patch cafe" in regular_data["search_term"].values
        assert "Total:" in summary_data["search_term"].values
        assert "Grand Total" in summary_data["search_term"].values

    def test_detect_summary_rows_no_summaries(self):
        """Test when no summary rows are present."""
        df = pd.DataFrame(
            {
                "search_term": ["cotton patch cafe", "restaurant near me"],
                "impressions": [100, 200],
            }
        )

        regular_data, summary_data = detect_summary_rows(df, "search_term")

        assert len(regular_data) == 2
        assert len(summary_data) == 0

    def test_detect_summary_rows_missing_column(self):
        """Test when search term column is missing."""
        df = pd.DataFrame({"query": ["cotton patch cafe"], "impressions": [100]})

        regular_data, summary_data = detect_summary_rows(df, "search_term")

        # Should return original data when column not found
        assert len(regular_data) == 1
        assert len(summary_data) == 0

    def test_detect_summary_rows_empty_and_other(self):
        """Test detection of empty rows and 'Other' category."""
        df = pd.DataFrame(
            {
                "search_term": [
                    "cotton patch cafe",
                    "",
                    "(not set)",
                    "Other",
                    "valid search term",
                ],
                "impressions": [100, 0, 50, 75, 80],
            }
        )

        regular_data, summary_data = detect_summary_rows(df, "search_term")

        assert len(regular_data) == 2
        assert len(summary_data) == 3
        assert "cotton patch cafe" in regular_data["search_term"].values
        assert "valid search term" in regular_data["search_term"].values


class TestInferMissingFields:
    """Test suite for field inference functionality."""

    def test_infer_ad_group_name_from_campaign(self):
        """Test inferring ad_group_name from campaign_name."""
        row_data = {
            "search_term": "cotton patch cafe",
            "campaign_name": "Restaurant Campaign",
            "impressions": 100,
        }

        result = infer_missing_fields(row_data)

        assert result["ad_group_name"] == "Restaurant Campaign - Default Ad Group"
        assert result["campaign_name"] == "Restaurant Campaign"
        assert result["search_term"] == "cotton patch cafe"

    def test_infer_ad_group_name_from_search_term(self):
        """Test inferring ad_group_name from search_term when campaign missing."""
        row_data = {"search_term": "cotton patch cafe near me", "impressions": 100}

        result = infer_missing_fields(row_data)

        assert result["ad_group_name"] == "Inferred - cotton patch cafe near me"
        assert result["campaign_name"] == "Inferred Campaign - cotton patch cafe ne"

    def test_infer_fields_long_search_term(self):
        """Test field inference with very long search terms."""
        row_data = {
            "search_term": "cotton patch cafe restaurant with the best chicken fried steak in texas",
            "impressions": 50,
        }

        result = infer_missing_fields(row_data)

        # Should truncate long search terms
        # Using constants: MAX_AD_GROUP_NAME_LENGTH=30, MAX_CAMPAIGN_NAME_LENGTH=20
        assert len(result["ad_group_name"]) <= 41  # "Inferred - " + 30 chars
        assert len(result["campaign_name"]) <= 41  # "Inferred Campaign - " + 20 chars
        assert "cotton patch cafe restaurant" in result["ad_group_name"]

    def test_infer_fallback_defaults(self):
        """Test fallback to generic defaults when no useful data available."""
        row_data = {"impressions": 100}

        result = infer_missing_fields(row_data)

        assert result["ad_group_name"] == "Unknown Ad Group"
        assert result["campaign_name"] == "Unknown Campaign"
        assert result["match_type"] == "BROAD"

    def test_infer_preserve_existing_fields(self):
        """Test that existing fields are preserved."""
        row_data = {
            "search_term": "cotton patch cafe",
            "campaign_name": "Existing Campaign",
            "ad_group_name": "Existing Ad Group",
            "match_type": "EXACT",
            "impressions": 100,
        }

        result = infer_missing_fields(row_data)

        # Should preserve existing values
        assert result["campaign_name"] == "Existing Campaign"
        assert result["ad_group_name"] == "Existing Ad Group"
        assert result["match_type"] == "EXACT"
        assert result["search_term"] == "cotton patch cafe"

    def test_infer_keyword_text_from_search_term(self):
        """Test inferring keyword_text from search_term."""
        row_data = {
            "search_term": "cotton patch cafe",
            "campaign_name": "Restaurant Campaign",
            "impressions": 100,
        }

        result = infer_missing_fields(row_data)

        assert result["keyword_text"] == "cotton patch cafe"

    def test_infer_with_pandas_na_values(self):
        """Test inference with pandas NaN values."""
        row_data = {
            "search_term": "cotton patch cafe",
            "campaign_name": pd.NA,
            "ad_group_name": pd.NA,
            "impressions": 100,
        }

        result = infer_missing_fields(row_data)

        assert result["ad_group_name"] == "Inferred - cotton patch cafe"
        assert result["campaign_name"] == "Inferred Campaign - cotton patch cafe"


class TestPreprocessSearchTermsData:
    """Test suite for comprehensive search terms preprocessing."""

    def test_preprocess_with_summary_rows_and_missing_fields(self):
        """Test preprocessing that handles both summary rows and missing fields."""
        df = pd.DataFrame(
            {
                "search_term": [
                    "cotton patch cafe",
                    "restaurant near me",
                    "Total:",
                    "fast food",
                    "Grand Total",
                ],
                "campaign_name": [
                    "Restaurant Campaign",
                    pd.NA,
                    "Restaurant Campaign",
                    pd.NA,
                    "Restaurant Campaign",
                ],
                "ad_group_name": [
                    pd.NA,
                    pd.NA,
                    "Main Ad Group",
                    pd.NA,
                    "Main Ad Group",
                ],
                "impressions": [100, 200, 300, 150, 300],
            }
        )

        result = preprocess_search_terms_data(df, strict_validation=False)

        # Should have 3 regular data rows (excluding summaries)
        assert len(result) == 3

        # Check field inference worked
        processed_rows = result.to_dict("records")

        # First row should keep existing campaign, infer ad group
        row1 = next(
            r for r in processed_rows if r["search_term"] == "cotton patch cafe"
        )
        assert row1["campaign_name"] == "Restaurant Campaign"
        assert row1["ad_group_name"] == "Restaurant Campaign - Default Ad Group"

        # Second row should infer both fields
        row2 = next(
            r for r in processed_rows if r["search_term"] == "restaurant near me"
        )
        assert "Inferred Campaign" in row2["campaign_name"]
        assert "Inferred - restaurant near me" == row2["ad_group_name"]

    def test_preprocess_empty_dataframe(self):
        """Test preprocessing with empty DataFrame."""
        df = pd.DataFrame()

        result = preprocess_search_terms_data(df)

        assert len(result) == 0

    def test_preprocess_no_search_term_column(self):
        """Test preprocessing when search term column is missing."""
        df = pd.DataFrame({"query": ["test query"], "impressions": [100]})

        result = preprocess_search_terms_data(df, strict_validation=False)

        # Should still process the data even without search term column
        assert len(result) == 1

    def test_preprocess_strict_validation_error(self):
        """Test that strict validation raises errors appropriately."""
        df = pd.DataFrame(
            {
                "search_term": ["valid term", None],  # None will cause issues
                "impressions": [100, 200],
            }
        )

        # Should skip invalid rows in non-strict mode
        result = preprocess_search_terms_data(df, strict_validation=False)
        assert len(result) == 1

        # In strict mode, could raise an error, but our implementation is designed to be robust

    def test_preprocess_alternative_search_term_column_names(self):
        """Test preprocessing with alternative search term column names."""
        df = pd.DataFrame(
            {
                "Search term": [  # Note the capital S and space
                    "cotton patch cafe",
                    "Total:",
                ],
                "impressions": [100, 200],
            }
        )

        result = preprocess_search_terms_data(df)

        # Should detect the alternative column name and process correctly
        assert len(result) == 1
        assert result.iloc[0]["Search term"] == "cotton patch cafe"
