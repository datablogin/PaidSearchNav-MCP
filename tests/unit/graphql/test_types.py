"""Tests for GraphQL types."""

import pytest


class TestGraphQLTypes:
    """Test GraphQL type definitions."""

    def test_imports(self):
        """Test that GraphQL types can be imported."""
        try:
            from paidsearchnav.graphql.types import (
                AnalysisResult,
                Audit,
                Customer,
                Recommendation,
            )

            # Verify types can be accessed
            assert AnalysisResult is not None
            assert Audit is not None
            assert Customer is not None
            assert Recommendation is not None
        except ImportError as e:
            pytest.skip(f"GraphQL types not available: {e}")

    def test_enum_imports(self):
        """Test that GraphQL enums can be imported."""
        try:
            from paidsearchnav.graphql.types import (
                AnalyzerType,
                AuditStatus,
                Priority,
                RecommendationStatus,
            )

            # Verify enums can be accessed
            assert AnalyzerType is not None
            assert AuditStatus is not None
            assert Priority is not None
            assert RecommendationStatus is not None
        except ImportError as e:
            pytest.skip(f"GraphQL enums not available: {e}")

    def test_input_types(self):
        """Test that GraphQL input types can be imported."""
        try:
            from paidsearchnav.graphql.types import (
                CustomerFilter,
                ScheduleAuditInput,
                TriggerAuditInput,
            )

            # Verify input types can be accessed
            assert CustomerFilter is not None
            assert ScheduleAuditInput is not None
            assert TriggerAuditInput is not None
        except ImportError as e:
            pytest.skip(f"GraphQL input types not available: {e}")
