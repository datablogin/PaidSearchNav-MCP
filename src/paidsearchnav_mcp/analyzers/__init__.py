"""Analyzers module for PaidSearchNav MCP server.

This module contains analyzers that perform server-side analysis and return
only summaries, solving context window limitations in Claude Desktop.
"""

from paidsearchnav_mcp.analyzers.base import AnalysisSummary, BaseAnalyzer
from paidsearchnav_mcp.analyzers.geo_performance import GeoPerformanceAnalyzer
from paidsearchnav_mcp.analyzers.keyword_match import KeywordMatchAnalyzer
from paidsearchnav_mcp.analyzers.negative_conflicts import NegativeConflictAnalyzer
from paidsearchnav_mcp.analyzers.pmax_cannibalization import PMaxCannibalizationAnalyzer
from paidsearchnav_mcp.analyzers.search_term_waste import SearchTermWasteAnalyzer

__all__ = [
    "AnalysisSummary",
    "BaseAnalyzer",
    "GeoPerformanceAnalyzer",
    "KeywordMatchAnalyzer",
    "NegativeConflictAnalyzer",
    "PMaxCannibalizationAnalyzer",
    "SearchTermWasteAnalyzer",
]
