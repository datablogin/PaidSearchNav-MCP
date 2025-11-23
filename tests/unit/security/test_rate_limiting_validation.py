"""Unit tests for rate limiting functionality."""

import os
from unittest.mock import patch

import pytest

from paidsearchnav_mcp.security.rate_limiting import (
    DEFAULT_MAX_IDS_PER_REQUEST,
    MAX_IDS_ENV_VAR,
    RateLimitError,
    get_max_ids_per_request,
    paginate_id_list,
    validate_id_list_size,
    validate_multiple_id_lists,
)


class TestGetMaxIdsPerRequest:
    """Test configuration of max IDs per request."""

    def test_default_value(self):
        """Test default value is returned when env var not set."""
        with patch.dict(os.environ, {}, clear=True):
            assert get_max_ids_per_request() == DEFAULT_MAX_IDS_PER_REQUEST

    def test_env_var_override(self):
        """Test environment variable overrides default."""
        with patch.dict(os.environ, {MAX_IDS_ENV_VAR: "500"}):
            assert get_max_ids_per_request() == 500

    def test_invalid_env_var_falls_back_to_default(self):
        """Test invalid env var value falls back to default."""
        with patch.dict(os.environ, {MAX_IDS_ENV_VAR: "not-a-number"}):
            assert get_max_ids_per_request() == DEFAULT_MAX_IDS_PER_REQUEST


class TestValidateIdListSize:
    """Test ID list size validation."""

    def test_none_list_returns_none(self):
        """Test None list is allowed."""
        assert validate_id_list_size(None, "test") is None

    def test_empty_list_allowed(self):
        """Test empty list is allowed."""
        result = validate_id_list_size([], "test")
        assert result == []

    def test_list_under_limit_allowed(self):
        """Test list under limit is allowed."""
        test_list = list(range(100))
        result = validate_id_list_size(test_list, "test", max_size=1000)
        assert result == test_list

    def test_list_at_limit_allowed(self):
        """Test list exactly at limit is allowed."""
        test_list = list(range(100))
        result = validate_id_list_size(test_list, "test", max_size=100)
        assert result == test_list

    def test_list_over_limit_raises_error(self):
        """Test list over limit raises RateLimitError."""
        test_list = list(range(101))
        with pytest.raises(RateLimitError) as exc_info:
            validate_id_list_size(test_list, "campaigns", max_size=100)

        assert "Too many campaigns provided: 101 exceeds maximum of 100" in str(
            exc_info.value
        )
        assert "use pagination" in str(exc_info.value)

    def test_uses_default_max_when_not_specified(self):
        """Test uses get_max_ids_per_request when max_size not specified."""
        with patch.dict(os.environ, {MAX_IDS_ENV_VAR: "50"}):
            test_list = list(range(51))
            with pytest.raises(RateLimitError) as exc_info:
                validate_id_list_size(test_list, "ad_groups")

            assert "51 exceeds maximum of 50" in str(exc_info.value)


class TestValidateMultipleIdLists:
    """Test validation of multiple ID lists."""

    def test_all_none_lists(self):
        """Test all None lists are allowed."""
        result = validate_multiple_id_lists(
            campaigns=None, ad_groups=None, keywords=None
        )
        assert result == {"campaigns": None, "ad_groups": None, "keywords": None}

    def test_mixed_lists(self):
        """Test mix of None and valid lists."""
        result = validate_multiple_id_lists(
            campaigns=["1", "2", "3"], ad_groups=None, keywords=[]
        )
        assert result == {
            "campaigns": ["1", "2", "3"],
            "ad_groups": None,
            "keywords": [],
        }

    def test_one_list_exceeds_limit(self):
        """Test error when one list exceeds limit."""
        with patch(
            "paidsearchnav.security.rate_limiting.get_max_ids_per_request",
            return_value=2,
        ):
            with pytest.raises(RateLimitError) as exc_info:
                validate_multiple_id_lists(
                    campaigns=["1", "2"],
                    ad_groups=["a", "b", "c"],  # This exceeds limit
                    keywords=["k1"],
                )

            assert "Too many ad_groups provided" in str(exc_info.value)

    def test_all_lists_valid(self):
        """Test all lists within limits."""
        with patch(
            "paidsearchnav.security.rate_limiting.get_max_ids_per_request",
            return_value=5,
        ):
            result = validate_multiple_id_lists(
                campaigns=["1", "2", "3"],
                ad_groups=["a", "b"],
                keywords=["k1", "k2", "k3", "k4"],
            )
            assert len(result) == 3
            assert result["campaigns"] == ["1", "2", "3"]
            assert result["ad_groups"] == ["a", "b"]
            assert result["keywords"] == ["k1", "k2", "k3", "k4"]


class TestPaginateIdList:
    """Test ID list pagination."""

    def test_empty_list(self):
        """Test empty list returns empty pages."""
        assert paginate_id_list([]) == []

    def test_single_page(self):
        """Test list that fits in one page."""
        test_list = [1, 2, 3, 4, 5]
        pages = paginate_id_list(test_list, page_size=10)
        assert pages == [[1, 2, 3, 4, 5]]

    def test_exact_pages(self):
        """Test list that exactly fills pages."""
        test_list = list(range(10))
        pages = paginate_id_list(test_list, page_size=5)
        assert pages == [[0, 1, 2, 3, 4], [5, 6, 7, 8, 9]]

    def test_partial_last_page(self):
        """Test list with partial last page."""
        test_list = list(range(12))
        pages = paginate_id_list(test_list, page_size=5)
        assert pages == [[0, 1, 2, 3, 4], [5, 6, 7, 8, 9], [10, 11]]

    def test_uses_default_page_size(self):
        """Test uses get_max_ids_per_request when page_size not specified."""
        with patch(
            "paidsearchnav.security.rate_limiting.get_max_ids_per_request",
            return_value=3,
        ):
            test_list = list(range(10))
            pages = paginate_id_list(test_list)
            assert pages == [[0, 1, 2], [3, 4, 5], [6, 7, 8], [9]]

    def test_preserves_string_ids(self):
        """Test pagination preserves string IDs."""
        test_list = ["id1", "id2", "id3", "id4", "id5"]
        pages = paginate_id_list(test_list, page_size=2)
        assert pages == [["id1", "id2"], ["id3", "id4"], ["id5"]]
