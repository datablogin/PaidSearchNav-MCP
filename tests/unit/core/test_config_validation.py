"""Tests for configuration validation."""

import pytest
from pydantic import ValidationError

from paidsearchnav_mcp.core.config import AnalyzerThresholds


class TestAnalyzerThresholdsValidation:
    """Test validation of AnalyzerThresholds configuration."""

    def test_valid_default_configuration(self):
        """Test that default configuration is valid."""
        thresholds = AnalyzerThresholds()

        # Should not raise any validation errors
        assert thresholds.min_impressions == 10
        assert thresholds.default_cpa_fallback == 100.0
        assert thresholds.min_roas_for_add == 2.0

    def test_min_roas_for_add_validation(self):
        """Test validation of min_roas_for_add threshold."""
        # Should fail with ROAS < 1.0 (unprofitable)
        with pytest.raises(ValidationError) as exc_info:
            AnalyzerThresholds(min_roas_for_add=0.5)

        assert "min_roas_for_add should be >= 1.0 for profitability" in str(
            exc_info.value
        )

    def test_pmax_threshold_ordering_validation(self):
        """Test validation of Performance Max threshold ordering."""
        # Should fail when excellent <= good
        with pytest.raises(ValidationError) as exc_info:
            AnalyzerThresholds(
                pmax_good_roas_threshold=5.0,
                pmax_excellent_roas_threshold=5.0,  # Same value
            )

        assert (
            "pmax_excellent_roas_threshold must be greater than pmax_good_roas_threshold"
            in str(exc_info.value)
        )

        # Should fail when excellent < good
        with pytest.raises(ValidationError) as exc_info:
            AnalyzerThresholds(
                pmax_good_roas_threshold=5.0,
                pmax_excellent_roas_threshold=3.0,  # Lower value
            )

        assert (
            "pmax_excellent_roas_threshold must be greater than pmax_good_roas_threshold"
            in str(exc_info.value)
        )

    def test_cpa_multiplier_validation(self):
        """Test validation of CPA multiplier threshold."""
        # Should fail with excessive multiplier
        with pytest.raises(ValidationError) as exc_info:
            AnalyzerThresholds(max_cpa_multiplier=15.0)

        assert "max_cpa_multiplier should not exceed 10.0" in str(exc_info.value)

    def test_ctr_threshold_validation(self):
        """Test validation of CTR threshold for negatives."""
        # Should fail with unreasonably high CTR threshold
        with pytest.raises(ValidationError) as exc_info:
            AnalyzerThresholds(max_ctr_for_negative=10.0)

        assert "max_ctr_for_negative should not exceed 5.0%" in str(exc_info.value)

    def test_conversion_threshold_validation(self):
        """Test validation of conversion threshold."""
        # Should fail with too restrictive conversion requirement
        with pytest.raises(ValidationError) as exc_info:
            AnalyzerThresholds(min_conversions_for_add=150.0)

        assert "min_conversions_for_add should not exceed 100" in str(exc_info.value)

    def test_valid_custom_configuration(self):
        """Test that valid custom configuration passes validation."""
        thresholds = AnalyzerThresholds(
            min_impressions=50,
            min_clicks_for_negative=20,
            max_cpa_multiplier=3.0,
            min_conversions_for_add=2.0,
            min_roas_for_add=1.5,
            max_ctr_for_negative=2.0,
            min_impressions_for_ctr_check=200,
            default_cpa_fallback=50.0,
            pmax_good_roas_threshold=2.0,
            pmax_excellent_roas_threshold=4.0,
        )

        # Should not raise validation errors
        assert thresholds.min_impressions == 50
        assert thresholds.default_cpa_fallback == 50.0
        assert thresholds.pmax_excellent_roas_threshold == 4.0

    def test_default_cpa_fallback_positive(self):
        """Test that default CPA fallback must be positive."""
        # Should fail with zero or negative CPA
        with pytest.raises(ValidationError) as exc_info:
            AnalyzerThresholds(default_cpa_fallback=0.0)

        # The Field(gt=0.0) constraint should catch this
        assert "greater than 0" in str(exc_info.value)

        with pytest.raises(ValidationError) as exc_info:
            AnalyzerThresholds(default_cpa_fallback=-10.0)

        assert "greater than 0" in str(exc_info.value)

    def test_boundary_values(self):
        """Test validation with boundary values."""
        # Test minimum valid ROAS
        thresholds = AnalyzerThresholds(min_roas_for_add=1.0)
        assert thresholds.min_roas_for_add == 1.0

        # Test maximum valid CPA multiplier
        thresholds = AnalyzerThresholds(max_cpa_multiplier=10.0)
        assert thresholds.max_cpa_multiplier == 10.0

        # Test maximum valid CTR threshold
        thresholds = AnalyzerThresholds(max_ctr_for_negative=5.0)
        assert thresholds.max_ctr_for_negative == 5.0

        # Test maximum valid conversion threshold
        thresholds = AnalyzerThresholds(min_conversions_for_add=100.0)
        assert thresholds.min_conversions_for_add == 100.0

    def test_field_constraints(self):
        """Test that individual field constraints work."""
        # Test negative impressions
        with pytest.raises(ValidationError):
            AnalyzerThresholds(min_impressions=-1)

        # Test zero impressions
        with pytest.raises(ValidationError):
            AnalyzerThresholds(min_impressions=0)

        # Test negative clicks
        with pytest.raises(ValidationError):
            AnalyzerThresholds(min_clicks_for_negative=0)

        # Test CTR percentage bounds
        with pytest.raises(ValidationError):
            AnalyzerThresholds(max_ctr_for_negative=101.0)  # Over 100%

        with pytest.raises(ValidationError):
            AnalyzerThresholds(max_ctr_for_negative=-1.0)  # Negative
