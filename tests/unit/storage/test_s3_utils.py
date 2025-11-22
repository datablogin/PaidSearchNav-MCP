"""Tests for S3 path utilities."""

from datetime import datetime

import pytest

from paidsearchnav.storage.s3_utils import (
    S3_BUCKET_BASE,
    get_analysis_input_path,
    get_analysis_output_path,
    get_audit_results_path,
    get_customer_base_path,
    get_google_ads_account_path,
    validate_s3_path,
)


class TestS3PathGeneration:
    """Test S3 path generation functions."""

    def test_get_customer_base_path(self):
        """Test customer base path generation."""
        customer_id = "123e4567-e89b-12d3-a456-426614174000"
        path = get_customer_base_path(customer_id)
        assert path == f"{S3_BUCKET_BASE}/{customer_id}"

    def test_get_customer_base_path_empty(self):
        """Test customer base path with empty ID."""
        with pytest.raises(ValueError, match="Customer ID cannot be empty"):
            get_customer_base_path("")

    def test_get_google_ads_account_path(self):
        """Test Google Ads account path generation."""
        customer_id = "123e4567-e89b-12d3-a456-426614174000"
        google_ads_id = "1234567890"
        path = get_google_ads_account_path(customer_id, google_ads_id)
        assert path == f"{S3_BUCKET_BASE}/{customer_id}/{google_ads_id}"

    def test_get_google_ads_account_path_validation(self):
        """Test Google Ads account path validation."""
        with pytest.raises(ValueError):
            get_google_ads_account_path("", "1234567890")

        with pytest.raises(ValueError):
            get_google_ads_account_path("customer-123", "")

    def test_get_analysis_input_path(self):
        """Test analysis input path generation."""
        customer_id = "123e4567-e89b-12d3-a456-426614174000"
        google_ads_id = "1234567890"
        date = datetime(2023, 12, 25)

        path = get_analysis_input_path(customer_id, google_ads_id, date)
        expected = f"{S3_BUCKET_BASE}/{customer_id}/{google_ads_id}/input/20231225"
        assert path == expected

    def test_get_analysis_input_path_default_date(self):
        """Test analysis input path with default date."""
        customer_id = "123e4567-e89b-12d3-a456-426614174000"
        google_ads_id = "1234567890"

        path = get_analysis_input_path(customer_id, google_ads_id)
        # Just verify it contains today's date format
        assert "/input/" in path
        assert len(path.split("/")[-1]) == 8  # YYYYMMDD format

    def test_get_analysis_output_path(self):
        """Test analysis output path generation."""
        customer_id = "123e4567-e89b-12d3-a456-426614174000"
        google_ads_id = "1234567890"
        analysis_type = "search_terms"
        date = datetime(2023, 12, 25)

        path = get_analysis_output_path(customer_id, google_ads_id, analysis_type, date)
        expected = f"{S3_BUCKET_BASE}/{customer_id}/{google_ads_id}/output/20231225/{analysis_type}"
        assert path == expected

    def test_get_analysis_output_path_validation(self):
        """Test analysis output path validation."""
        with pytest.raises(ValueError, match="Analysis type cannot be empty"):
            get_analysis_output_path("customer-123", "1234567890", "")

    def test_get_audit_results_path(self):
        """Test audit results path generation."""
        customer_id = "123e4567-e89b-12d3-a456-426614174000"
        audit_id = "audit-123"

        path = get_audit_results_path(customer_id, audit_id)
        expected = f"{S3_BUCKET_BASE}/{customer_id}/audits/{audit_id}"
        assert path == expected

    def test_get_audit_results_path_validation(self):
        """Test audit results path validation."""
        with pytest.raises(ValueError, match="Audit ID cannot be empty"):
            get_audit_results_path("customer-123", "")


class TestS3PathValidation:
    """Test S3 path validation."""

    def test_validate_s3_path_valid(self):
        """Test validation of valid S3 paths."""
        valid_paths = [
            "s3://bucket/path/to/file",
            "s3://bucket-name/folder/subfolder",
            "s3://my-bucket/customer-123/data.csv",
        ]

        for path in valid_paths:
            assert validate_s3_path(path) is True

    def test_validate_s3_path_empty(self):
        """Test validation of empty path."""
        with pytest.raises(ValueError, match="S3 path cannot be empty"):
            validate_s3_path("")

    def test_validate_s3_path_invalid_prefix(self):
        """Test validation of path without s3:// prefix."""
        with pytest.raises(ValueError, match="S3 path must start with 's3://'"):
            validate_s3_path("http://bucket/path")

    def test_validate_s3_path_directory_traversal(self):
        """Test validation prevents directory traversal."""
        with pytest.raises(ValueError, match="S3 path cannot contain '\\.\\.'"):
            validate_s3_path("s3://bucket/../etc/passwd")

    def test_validate_s3_path_dangerous_patterns(self):
        """Test validation of paths with dangerous patterns."""
        dangerous_paths = [
            "s3://bucket//double-slash",  # Double slash after protocol
            "s3://bucket/path\\backslash",
            "s3://bucket/pipe|character",
            "s3://bucket/ampersand&command",
            "s3://bucket/semicolon;command",
            "s3://bucket/dollar$variable",
            "s3://bucket/backtick`command`",
            "s3://bucket/parenthesis(test)",
            "s3://bucket/lessthan<greaterthan>",
        ]

        for path in dangerous_paths:
            with pytest.raises(ValueError):
                validate_s3_path(path)
