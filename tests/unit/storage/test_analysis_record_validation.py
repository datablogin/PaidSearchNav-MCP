"""Tests for AnalysisRecord model validation."""

from datetime import datetime, timezone

import pytest

from paidsearchnav.storage.models import AnalysisRecord


class TestAnalysisRecordValidation:
    """Test AnalysisRecord model validation."""

    def test_valid_customer_id_7_to_10_digits(self):
        """Test that 7-10 digit customer IDs are valid."""
        # Test 7 digits
        record = AnalysisRecord(
            customer_id="1234567",
            analysis_type="keyword_match",
            analyzer_name="KeywordMatchAnalyzer",
            start_date=datetime.now(timezone.utc),
            end_date=datetime.now(timezone.utc),
            result_data={},
        )
        assert record.customer_id == "1234567"

        # Test 10 digits
        record = AnalysisRecord(
            customer_id="1234567890",
            analysis_type="keyword_match",
            analyzer_name="KeywordMatchAnalyzer",
            start_date=datetime.now(timezone.utc),
            end_date=datetime.now(timezone.utc),
            result_data={},
        )
        assert record.customer_id == "1234567890"

    def test_valid_customer_id_with_hyphens(self):
        """Test that customer ID with hyphens gets cleaned."""
        record = AnalysisRecord(
            customer_id="123-456-7890",
            analysis_type="keyword_match",
            analyzer_name="KeywordMatchAnalyzer",
            start_date=datetime.now(timezone.utc),
            end_date=datetime.now(timezone.utc),
            result_data={},
        )
        assert record.customer_id == "1234567890"

    def test_invalid_customer_id_empty(self):
        """Test that empty customer ID raises error."""
        with pytest.raises(ValueError, match="Customer ID cannot be empty"):
            AnalysisRecord(
                customer_id="",
                analysis_type="keyword_match",
                analyzer_name="KeywordMatchAnalyzer",
                start_date=datetime.now(timezone.utc),
                end_date=datetime.now(timezone.utc),
                result_data={},
            )

    def test_invalid_customer_id_whitespace_only(self):
        """Test that whitespace-only customer ID raises error."""
        with pytest.raises(ValueError, match="Customer ID cannot be empty"):
            AnalysisRecord(
                customer_id="   ",
                analysis_type="keyword_match",
                analyzer_name="KeywordMatchAnalyzer",
                start_date=datetime.now(timezone.utc),
                end_date=datetime.now(timezone.utc),
                result_data={},
            )

    def test_invalid_customer_id_contains_letters(self):
        """Test that customer ID with letters raises error."""
        with pytest.raises(
            ValueError, match="Customer ID must contain only digits and hyphens"
        ):
            AnalysisRecord(
                customer_id="123abc7890",
                analysis_type="keyword_match",
                analyzer_name="KeywordMatchAnalyzer",
                start_date=datetime.now(timezone.utc),
                end_date=datetime.now(timezone.utc),
                result_data={},
            )

    def test_invalid_customer_id_wrong_length(self):
        """Test that customer ID with wrong length raises error."""
        # Too short (6 digits)
        with pytest.raises(ValueError, match="Customer ID must be 7-10 digits"):
            AnalysisRecord(
                customer_id="123456",
                analysis_type="keyword_match",
                analyzer_name="KeywordMatchAnalyzer",
                start_date=datetime.now(timezone.utc),
                end_date=datetime.now(timezone.utc),
                result_data={},
            )

        # Too long (11 digits)
        with pytest.raises(ValueError, match="Customer ID must be 7-10 digits"):
            AnalysisRecord(
                customer_id="12345678901",
                analysis_type="keyword_match",
                analyzer_name="KeywordMatchAnalyzer",
                start_date=datetime.now(timezone.utc),
                end_date=datetime.now(timezone.utc),
                result_data={},
            )

    def test_customer_id_strips_whitespace(self):
        """Test that customer ID strips whitespace."""
        record = AnalysisRecord(
            customer_id="  123-456-7890  ",
            analysis_type="keyword_match",
            analyzer_name="KeywordMatchAnalyzer",
            start_date=datetime.now(timezone.utc),
            end_date=datetime.now(timezone.utc),
            result_data={},
        )
        assert record.customer_id == "1234567890"
