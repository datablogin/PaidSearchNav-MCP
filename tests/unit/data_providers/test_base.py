"""Tests for the base DataProvider interface."""

import pytest

from paidsearchnav.data_providers.base import DataProvider


class TestDataProviderInterface:
    """Test the DataProvider abstract base class."""

    def test_cannot_instantiate_abstract_class(self):
        """Test that DataProvider cannot be instantiated directly."""
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            DataProvider()

    def test_all_abstract_methods_defined(self):
        """Test that all expected abstract methods are defined."""
        expected_methods = [
            "get_search_terms",
            "get_keywords",
            "get_negative_keywords",
            "get_campaigns",
            "get_shared_negative_lists",
            "get_campaign_shared_sets",
            "get_shared_set_negatives",
            "get_placement_data",
        ]

        for method_name in expected_methods:
            assert hasattr(DataProvider, method_name)
            method = getattr(DataProvider, method_name)
            assert hasattr(method, "__isabstractmethod__")
            assert method.__isabstractmethod__ is True
