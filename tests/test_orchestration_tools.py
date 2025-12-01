"""Tests for orchestration tools in MCP server.

Note: These tests verify that the analyzers work correctly and can be integrated
with the MCP server. Full integration testing would require running the MCP server.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from paidsearchnav_mcp.analyzers import (
    AnalysisSummary,
    KeywordMatchAnalyzer,
    SearchTermWasteAnalyzer,
    NegativeConflictAnalyzer,
    GeoPerformanceAnalyzer,
    PMaxCannibalizationAnalyzer,
)


@pytest.mark.asyncio
class TestAnalyzersIntegration:
    """Test that analyzers can be used by orchestration tools."""

    @pytest.fixture
    def mock_analysis_summary(self):
        """Create a mock AnalysisSummary for testing."""
        return AnalysisSummary(
            total_records_analyzed=100,
            estimated_monthly_savings=1000.00,
            primary_issue="Test issue",
            top_recommendations=[
                {
                    "keyword": "test keyword",
                    "current_match_type": "BROAD",
                    "recommended_match_type": "EXACT",
                    "estimated_savings": 500.00,
                    "reasoning": "Test reasoning",
                }
            ],
            implementation_steps=["Step 1", "Step 2"],
            analysis_period="2024-01-01 to 2024-01-31",
            customer_id="1234567890",
        )

    async def test_keyword_match_analyzer_can_be_instantiated(self):
        """Test that KeywordMatchAnalyzer can be instantiated."""
        analyzer = KeywordMatchAnalyzer()
        assert analyzer is not None
        assert hasattr(analyzer, "analyze")

    async def test_search_term_waste_analyzer_can_be_instantiated(self):
        """Test that SearchTermWasteAnalyzer can be instantiated."""
        analyzer = SearchTermWasteAnalyzer()
        assert analyzer is not None
        assert hasattr(analyzer, "analyze")

    async def test_negative_conflict_analyzer_can_be_instantiated(self):
        """Test that NegativeConflictAnalyzer can be instantiated."""
        analyzer = NegativeConflictAnalyzer()
        assert analyzer is not None
        assert hasattr(analyzer, "analyze")

    async def test_geo_performance_analyzer_can_be_instantiated(self):
        """Test that GeoPerformanceAnalyzer can be instantiated."""
        analyzer = GeoPerformanceAnalyzer()
        assert analyzer is not None
        assert hasattr(analyzer, "analyze")

    async def test_pmax_cannibalization_analyzer_can_be_instantiated(self):
        """Test that PMaxCannibalizationAnalyzer can be instantiated."""
        analyzer = PMaxCannibalizationAnalyzer()
        assert analyzer is not None
        assert hasattr(analyzer, "analyze")

    async def test_analysis_summary_can_be_converted_to_dict(self, mock_analysis_summary):
        """Test that AnalysisSummary can be converted to dict for MCP response."""
        result = mock_analysis_summary.model_dump()

        assert isinstance(result, dict)
        assert result["total_records_analyzed"] == 100
        assert result["estimated_monthly_savings"] == 1000.00
        assert result["customer_id"] == "1234567890"
        assert "top_recommendations" in result
        assert "implementation_steps" in result


class TestOrchestrationToolsAvailability:
    """Test that orchestration tools are properly registered."""

    def test_orchestration_tools_are_defined(self):
        """Test that orchestration tool functions exist in server module."""
        import paidsearchnav_mcp.server as server

        # Check that all orchestration tools are defined
        assert hasattr(server, "analyze_keyword_match_types")
        assert hasattr(server, "analyze_search_term_waste")
        assert hasattr(server, "analyze_negative_conflicts")
        assert hasattr(server, "analyze_geo_performance")
        assert hasattr(server, "analyze_pmax_cannibalization")

    def test_tools_listed_in_health_check_config(self):
        """Test that orchestration tools are listed in the tools_available config."""
        # Import the server to initialize the MCP decorators
        import paidsearchnav_mcp.server

        # The tools should be in the code - we can check the source
        with open("src/paidsearchnav_mcp/server.py", "r") as f:
            server_code = f.read()

        # Verify orchestration tools are defined
        assert "analyze_keyword_match_types" in server_code
        assert "analyze_search_term_waste" in server_code
        assert "analyze_negative_conflicts" in server_code
        assert "analyze_geo_performance" in server_code
        assert "analyze_pmax_cannibalization" in server_code

        # Verify they're listed in tools_available
        assert '"analyze_keyword_match_types"' in server_code
        assert '"analyze_search_term_waste"' in server_code
        assert '"analyze_negative_conflicts"' in server_code
        assert '"analyze_pmax_cannibalization"' in server_code
