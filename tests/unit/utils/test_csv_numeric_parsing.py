"""Tests for CSV numeric parsing utilities."""

import pandas as pd

from paidsearchnav_mcp.utils.csv_parsing import (
    clean_numeric_value,
    get_common_numeric_columns,
    normalize_dataframe_numerics,
)


class TestCleanNumericValue:
    """Test clean_numeric_value function."""

    def test_clean_comma_separated_integers(self):
        """Test cleaning comma-separated integer values."""
        assert clean_numeric_value("4,894") == 4894
        assert clean_numeric_value("22,108") == 22108
        assert clean_numeric_value("1,000,000") == 1000000

    def test_clean_currency_values(self):
        """Test cleaning currency formatted values."""
        assert clean_numeric_value("$1,234.56") == 1234.56
        assert clean_numeric_value("$10,000") == 10000
        assert clean_numeric_value("$0.99") == 0.99

    def test_clean_percentage_values(self):
        """Test cleaning percentage values."""
        assert clean_numeric_value("12.5%") == 12.5
        assert clean_numeric_value("100%") == 100
        assert clean_numeric_value("0.5%") == 0.5

    def test_clean_accounting_format(self):
        """Test cleaning accounting format (negative in parentheses)."""
        assert clean_numeric_value("(1,234)") == -1234
        assert clean_numeric_value("($500.00)") == -500.0

    def test_handle_empty_values(self):
        """Test handling of empty/null values."""
        assert clean_numeric_value("") is None
        assert clean_numeric_value(None) is None
        assert clean_numeric_value(pd.NA) is None

    def test_handle_invalid_values(self):
        """Test handling of invalid numeric strings."""
        assert clean_numeric_value("N/A") is None
        assert clean_numeric_value("--") is None
        assert clean_numeric_value("null") is None
        assert clean_numeric_value("invalid") is None

    def test_handle_existing_numbers(self):
        """Test handling of already numeric values."""
        assert clean_numeric_value(1234) == 1234
        assert clean_numeric_value(1234.56) == 1234.56
        assert clean_numeric_value(0) == 0

    def test_whitespace_handling(self):
        """Test handling of values with whitespace."""
        assert clean_numeric_value("  1,234  ") == 1234
        assert clean_numeric_value("\t$500.00\n") == 500.0

    def test_integer_vs_float_detection(self):
        """Test proper integer vs float detection."""
        assert isinstance(clean_numeric_value("1234"), int)
        assert isinstance(clean_numeric_value("1234.0"), float)
        assert isinstance(clean_numeric_value("1234.56"), float)


class TestNormalizeDataFrameNumerics:
    """Test normalize_dataframe_numerics function."""

    def test_clean_dataframe_columns(self):
        """Test cleaning numeric columns in DataFrame."""
        df = pd.DataFrame(
            {
                "impressions": ["4,894", "22,108", "1,000"],
                "cost": ["$1,234.56", "$500.00", "$10.99"],
                "text_column": ["keyword1", "keyword2", "keyword3"],
            }
        )

        numeric_cols = ["impressions", "cost"]
        cleaned_df = normalize_dataframe_numerics(df, numeric_cols)

        assert cleaned_df["impressions"].tolist() == [4894, 22108, 1000]
        assert cleaned_df["cost"].tolist() == [1234.56, 500.0, 10.99]
        assert cleaned_df["text_column"].tolist() == [
            "keyword1",
            "keyword2",
            "keyword3",
        ]

    def test_handle_missing_columns(self):
        """Test handling of missing columns gracefully."""
        df = pd.DataFrame({"impressions": ["1,000", "2,000"], "clicks": ["100", "200"]})

        # Include a column that doesn't exist
        numeric_cols = ["impressions", "clicks", "nonexistent_column"]
        cleaned_df = normalize_dataframe_numerics(df, numeric_cols)

        assert cleaned_df["impressions"].tolist() == [1000, 2000]
        assert cleaned_df["clicks"].tolist() == [100, 200]

    def test_fill_none_values(self):
        """Test that None values are filled with 0."""
        df = pd.DataFrame(
            {"impressions": ["1,000", "N/A", "--"], "clicks": ["100", "", "200"]}
        )

        numeric_cols = ["impressions", "clicks"]
        cleaned_df = normalize_dataframe_numerics(df, numeric_cols)

        assert cleaned_df["impressions"].tolist() == [1000, 0, 0]
        assert cleaned_df["clicks"].tolist() == [100, 0, 200]


class TestGetCommonNumericColumns:
    """Test get_common_numeric_columns function."""

    def test_returns_dict(self):
        """Test that function returns a dictionary."""
        result = get_common_numeric_columns()
        assert isinstance(result, dict)

    def test_contains_expected_types(self):
        """Test that result contains expected report types."""
        result = get_common_numeric_columns()
        expected_types = ["keywords", "search_terms", "campaigns", "store_performance"]

        for report_type in expected_types:
            assert report_type in result
            assert isinstance(result[report_type], list)

    def test_keywords_columns(self):
        """Test keywords numeric columns."""
        result = get_common_numeric_columns()
        keywords_cols = result["keywords"]

        expected_cols = ["impressions", "clicks", "cost", "conversions"]
        for col in expected_cols:
            assert col in keywords_cols

    def test_store_performance_columns(self):
        """Test store performance numeric columns."""
        result = get_common_numeric_columns()
        store_cols = result["store_performance"]

        expected_cols = ["local_impressions", "store_visits", "call_clicks"]
        for col in expected_cols:
            assert col in store_cols


class TestRealWorldScenarios:
    """Test real-world CSV parsing scenarios."""

    def test_cotton_patch_cafe_numeric_formats(self):
        """Test formats found in Cotton Patch Cafe data."""
        # These are actual problematic values from the test
        test_values = ["4,894", "3,099", "4,628", "9,848", "22,108", "1,480"]

        expected_values = [4894, 3099, 4628, 9848, 22108, 1480]

        for test_val, expected in zip(test_values, expected_values):
            assert clean_numeric_value(test_val) == expected

    def test_google_ads_cost_formats(self):
        """Test Google Ads cost formatting."""
        test_values = ["1,234.56", "$1,234.56", "0.50", "10,000.00"]

        expected_values = [1234.56, 1234.56, 0.5, 10000.0]

        for test_val, expected in zip(test_values, expected_values):
            assert clean_numeric_value(test_val) == expected

    def test_mixed_format_dataframe(self):
        """Test DataFrame with mixed numeric formats (like real CSV exports)."""
        df = pd.DataFrame(
            {
                "campaign_name": ["Campaign 1", "Campaign 2", "Campaign 3"],
                "impressions": ["4,894", "22,108", "1,000"],
                "clicks": ["123", "456", "789"],
                "cost": ["$1,234.56", "$500.00", "$10.99"],
                "conversions": ["5.5", "10.0", "2.25"],
                "quality_score": ["7", "8", "9"],
            }
        )

        numeric_cols = ["impressions", "clicks", "cost", "conversions", "quality_score"]
        cleaned_df = normalize_dataframe_numerics(df, numeric_cols)

        # Verify all numeric columns are properly cleaned
        assert cleaned_df["impressions"].dtype in ["int64", "float64"]
        assert cleaned_df["clicks"].dtype in ["int64", "float64"]
        assert cleaned_df["cost"].dtype in ["int64", "float64"]
        assert cleaned_df["conversions"].dtype in ["int64", "float64"]
        assert cleaned_df["quality_score"].dtype in ["int64", "float64"]

        # Verify values are correct
        assert cleaned_df["impressions"].tolist() == [4894, 22108, 1000]
        assert cleaned_df["cost"].tolist() == [1234.56, 500.0, 10.99]
        assert cleaned_df["conversions"].tolist() == [5.5, 10.0, 2.25]
