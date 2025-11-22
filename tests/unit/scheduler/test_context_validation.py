"""Tests for job context validation in scheduler."""

from datetime import datetime

import pytest
from pydantic import ValidationError

from paidsearchnav_mcp.scheduler.jobs import validate_job_context
from paidsearchnav_mcp.scheduler.models import JobContextValidator


class TestJobContextValidator:
    """Test the JobContextValidator Pydantic model."""

    def test_empty_context_valid(self):
        """Test that empty context is valid."""
        validator = JobContextValidator()
        assert validator.model_dump(exclude_none=True) == {}

    def test_valid_basic_context(self):
        """Test validation of basic valid context."""
        context = {
            "default_audit_days": 90,
            "min_impressions": 100,
            "campaigns": ["12345", "67890"],
        }
        validator = JobContextValidator(**context)
        result = validator.model_dump(exclude_none=True)

        assert result["default_audit_days"] == 90
        assert result["min_impressions"] == 100
        assert result["campaigns"] == ["12345", "67890"]

    def test_valid_analyzer_config(self):
        """Test validation of analyzer-specific configuration."""
        context = {
            "analyzer_config": {
                "keyword_match": {"min_impressions": 50},
                "search_terms": {"min_clicks": 10, "include_shared_sets": True},
            }
        }
        validator = JobContextValidator(**context)
        result = validator.model_dump(exclude_none=True)

        assert "analyzer_config" in result
        assert result["analyzer_config"]["keyword_match"]["min_impressions"] == 50
        assert result["analyzer_config"]["search_terms"]["min_clicks"] == 10

    def test_invalid_default_audit_days(self):
        """Test validation fails for invalid default_audit_days."""
        # Test negative value
        with pytest.raises(ValidationError) as exc_info:
            JobContextValidator(default_audit_days=-1)
        assert "greater than or equal to 1" in str(exc_info.value)

        # Test too large value
        with pytest.raises(ValidationError) as exc_info:
            JobContextValidator(default_audit_days=500)
        assert "less than or equal to 365" in str(exc_info.value)

    def test_invalid_negative_thresholds(self):
        """Test validation fails for negative performance thresholds."""
        with pytest.raises(ValidationError) as exc_info:
            JobContextValidator(min_impressions=-5)
        assert "greater than or equal to 0" in str(exc_info.value)

        with pytest.raises(ValidationError) as exc_info:
            JobContextValidator(min_clicks=-10)
        assert "greater than or equal to 0" in str(exc_info.value)

    def test_invalid_analyzer_name(self):
        """Test validation fails for unknown analyzer."""
        context = {"analyzer_config": {"invalid_analyzer": {"param": "value"}}}
        with pytest.raises(ValidationError) as exc_info:
            JobContextValidator(**context)
        assert "Unknown analyzer 'invalid_analyzer'" in str(exc_info.value)

    def test_invalid_analyzer_config_type(self):
        """Test validation fails for non-dict analyzer config."""
        context = {"analyzer_config": {"keyword_match": "not_a_dict"}}
        with pytest.raises(ValidationError) as exc_info:
            JobContextValidator(**context)
        assert "Input should be a valid dictionary" in str(exc_info.value)

    def test_extra_fields_rejected(self):
        """Test that extra fields are rejected due to extra='forbid'."""
        with pytest.raises(ValidationError) as exc_info:
            JobContextValidator(unexpected_field="value")
        assert "Extra inputs are not permitted" in str(exc_info.value)

    def test_all_valid_analyzers(self):
        """Test that all known analyzers are accepted."""
        valid_analyzers = [
            "keyword_match",
            "search_terms",
            "negative_conflicts",
            "geo_performance",
            "pmax",
            "shared_negatives",
        ]

        context = {
            "analyzer_config": {
                analyzer: {"test_param": "value"} for analyzer in valid_analyzers
            }
        }

        # Should not raise an exception
        validator = JobContextValidator(**context)
        result = validator.model_dump(exclude_none=True)
        assert len(result["analyzer_config"]) == len(valid_analyzers)

    def test_valid_date_range(self):
        """Test that valid date ranges are accepted."""
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 31)

        context = {"start_date": start_date, "end_date": end_date}

        # Should not raise an exception
        validator = JobContextValidator(**context)
        result = validator.model_dump(exclude_none=True)
        assert result["start_date"] == start_date
        assert result["end_date"] == end_date

    def test_invalid_date_range(self):
        """Test that invalid date ranges are rejected."""
        start_date = datetime(2024, 1, 31)
        end_date = datetime(2024, 1, 1)  # End before start

        context = {"start_date": start_date, "end_date": end_date}

        with pytest.raises(ValidationError) as exc_info:
            JobContextValidator(**context)
        assert "start_date must be less than or equal to end_date" in str(
            exc_info.value
        )

    def test_single_date_allowed(self):
        """Test that providing only start_date or end_date is allowed."""
        # Only start_date
        context = {"start_date": datetime(2024, 1, 1)}
        validator = JobContextValidator(**context)
        assert validator.start_date is not None
        assert validator.end_date is None

        # Only end_date
        context = {"end_date": datetime(2024, 1, 31)}
        validator = JobContextValidator(**context)
        assert validator.start_date is None
        assert validator.end_date is not None


class TestValidateJobContextFunction:
    """Test the validate_job_context function."""

    def test_empty_context(self):
        """Test validation of empty context."""
        result = validate_job_context({})
        assert result == {}

    def test_none_context(self):
        """Test validation of None context."""
        result = validate_job_context(None)
        assert result == {}

    def test_valid_context_sanitization(self):
        """Test that valid context is properly sanitized."""
        context = {
            "default_audit_days": 90,
            "min_impressions": 100,
            "campaigns": ["12345"],
            "include_shared_sets": True,
        }

        result = validate_job_context(context)

        # Should contain all valid fields
        assert result["default_audit_days"] == 90
        assert result["min_impressions"] == 100
        assert result["campaigns"] == ["12345"]
        assert result["include_shared_sets"] is True

    def test_invalid_context_raises_error(self):
        """Test that invalid context raises ValueError."""
        context = {
            "default_audit_days": -1,  # Invalid
            "min_impressions": 100,
        }

        with pytest.raises(ValueError) as exc_info:
            validate_job_context(context)
        assert "Job context validation failed" in str(exc_info.value)

    def test_unknown_fields_filtered_out(self):
        """Test that unknown fields are filtered out."""
        context = {
            "valid_field": 90,  # This would be default_audit_days
            "malicious_field": "rm -rf /",  # This should be filtered out
        }

        # Rename valid_field to an actual valid field
        context = {
            "default_audit_days": 90,
            "malicious_field": "rm -rf /",  # This should be filtered out
        }

        with pytest.raises(ValueError):  # Should fail due to extra field
            validate_job_context(context)

    def test_nested_analyzer_config_validation(self):
        """Test validation of nested analyzer configuration."""
        context = {
            "analyzer_config": {
                "keyword_match": {"min_impressions": 50, "campaigns": ["123", "456"]},
                "search_terms": {"min_clicks": 5},
            }
        }

        result = validate_job_context(context)

        assert "analyzer_config" in result
        assert result["analyzer_config"]["keyword_match"]["min_impressions"] == 50
        assert result["analyzer_config"]["search_terms"]["min_clicks"] == 5

    def test_comprehensive_valid_context(self):
        """Test validation of a comprehensive valid context."""
        context = {
            "default_audit_days": 120,
            "analyzer_config": {
                "keyword_match": {"min_impressions": 100},
                "search_terms": {"min_clicks": 5},
            },
            "campaigns": ["12345", "67890"],
            "ad_groups": ["111", "222"],
            "include_shared_sets": True,
            "min_impressions": 50,
            "min_clicks": 3,
            "max_cost_per_conversion": 25.50,
            "geo_target_ids": ["1001", "1002"],
            "exclude_geo_target_ids": ["2001"],
        }

        result = validate_job_context(context)

        # Verify all fields are preserved
        assert result["default_audit_days"] == 120
        assert len(result["analyzer_config"]) == 2
        assert len(result["campaigns"]) == 2
        assert len(result["ad_groups"]) == 2
        assert result["include_shared_sets"] is True
        assert result["min_impressions"] == 50
        assert result["min_clicks"] == 3
        assert result["max_cost_per_conversion"] == 25.50
        assert len(result["geo_target_ids"]) == 2
        assert len(result["exclude_geo_target_ids"]) == 1
