"""Data providers module for PaidSearchNav.

This module provides a unified interface for accessing data from various sources:
- Google Ads API
- CSV files
- Mock data for testing
- Specialized providers for specific data types
"""

from paidsearchnav_mcp.data_providers.base import DataProvider
from paidsearchnav_mcp.data_providers.csv_provider import CSVDataProvider
from paidsearchnav_mcp.data_providers.google_ads import GoogleAdsDataProvider
from paidsearchnav_mcp.data_providers.mock_provider import MockDataProvider
from paidsearchnav_mcp.data_providers.search_terms_provider import SearchTermsProvider

__all__ = [
    "DataProvider",
    "GoogleAdsDataProvider",
    "CSVDataProvider",
    "MockDataProvider",
    "SearchTermsProvider",
]
