"""Pytest configuration and shared fixtures for MCP tests."""

import sys
from unittest.mock import MagicMock, Mock

# Mock the archived paidsearchnav modules before any imports
# This prevents ModuleNotFoundError when importing paidsearchnav_mcp modules


# Create mock modules for paidsearchnav dependencies
def create_mock_module(name: str):
    """Create a mock module with commonly used attributes."""
    module = MagicMock()
    module.__name__ = name
    return module


# Mock all paidsearchnav submodules that might be imported
paidsearchnav_mocks = {
    "paidsearchnav": create_mock_module("paidsearchnav"),
    "paidsearchnav.core": create_mock_module("paidsearchnav.core"),
    "paidsearchnav.core.circuit_breaker": create_mock_module("paidsearchnav.core.circuit_breaker"),
    "paidsearchnav.core.config": create_mock_module("paidsearchnav.core.config"),
    "paidsearchnav.core.exceptions": create_mock_module("paidsearchnav.core.exceptions"),
    "paidsearchnav.core.models": create_mock_module("paidsearchnav.core.models"),
    "paidsearchnav.core.models.base": create_mock_module("paidsearchnav.core.models.base"),
    "paidsearchnav.core.models.campaign": create_mock_module("paidsearchnav.core.models.campaign"),
    "paidsearchnav.core.models.keyword": create_mock_module("paidsearchnav.core.models.keyword"),
    "paidsearchnav.core.models.search_term": create_mock_module("paidsearchnav.core.models.search_term"),
    "paidsearchnav.platforms": create_mock_module("paidsearchnav.platforms"),
    "paidsearchnav.platforms.google": create_mock_module("paidsearchnav.platforms.google"),
    "paidsearchnav.platforms.google.metrics": create_mock_module("paidsearchnav.platforms.google.metrics"),
    "paidsearchnav.platforms.google.rate_limiting": create_mock_module("paidsearchnav.platforms.google.rate_limiting"),
    "paidsearchnav.platforms.google.validation": create_mock_module("paidsearchnav.platforms.google.validation"),
}

# Add mock classes and functions to modules
paidsearchnav_mocks["paidsearchnav.core.circuit_breaker"].GoogleAdsCircuitBreaker = Mock
paidsearchnav_mocks["paidsearchnav.core.config"].CircuitBreakerConfig = Mock
paidsearchnav_mocks["paidsearchnav.core.config"].Settings = Mock
paidsearchnav_mocks["paidsearchnav.core.config"].SecretProvider = Mock
paidsearchnav_mocks["paidsearchnav.core.exceptions"].APIError = Exception
paidsearchnav_mocks["paidsearchnav.core.exceptions"].AuthenticationError = Exception
paidsearchnav_mocks["paidsearchnav.core.exceptions"].RateLimitError = Exception
paidsearchnav_mocks["paidsearchnav.core.models.base"].BasePSNModel = Mock
paidsearchnav_mocks["paidsearchnav.platforms.google.metrics"].APIEfficiencyMetrics = Mock
paidsearchnav_mocks["paidsearchnav.platforms.google.rate_limiting"].GoogleAdsRateLimiter = Mock
paidsearchnav_mocks["paidsearchnav.platforms.google.rate_limiting"].OperationType = Mock
paidsearchnav_mocks["paidsearchnav.platforms.google.rate_limiting"].account_info_rate_limited = lambda f: f
paidsearchnav_mocks["paidsearchnav.platforms.google.rate_limiting"].report_rate_limited = lambda f: f
paidsearchnav_mocks["paidsearchnav.platforms.google.rate_limiting"].search_rate_limited = lambda f: f
paidsearchnav_mocks["paidsearchnav.platforms.google.validation"].GoogleAdsInputValidator = Mock

# Update sys.modules before any test imports
sys.modules.update(paidsearchnav_mocks)
