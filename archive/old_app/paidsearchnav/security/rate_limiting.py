"""Rate limiting utilities for preventing DoS attacks through large ID lists."""

from __future__ import annotations

import os
from typing import Any, TypeVar

from paidsearchnav.core.exceptions import ValidationError

# Type variable for generic list validation
T = TypeVar("T")

# Default maximum IDs per request
DEFAULT_MAX_IDS_PER_REQUEST = 1000

# Environment variable for configuration
MAX_IDS_ENV_VAR = "PSN_MAX_IDS_PER_REQUEST"


class RateLimitError(ValidationError):
    """Raised when rate limiting thresholds are exceeded."""

    pass


def get_max_ids_per_request() -> int:
    """Get the maximum number of IDs allowed per request.

    Returns:
        Maximum number of IDs allowed
    """
    try:
        return int(os.getenv(MAX_IDS_ENV_VAR, str(DEFAULT_MAX_IDS_PER_REQUEST)))
    except ValueError:
        return DEFAULT_MAX_IDS_PER_REQUEST


def validate_id_list_size(
    id_list: list[T] | None,
    list_name: str,
    max_size: int | None = None,
) -> list[T] | None:
    """Validate that an ID list doesn't exceed size limits.

    Args:
        id_list: List of IDs to validate
        list_name: Name of the list for error messages (e.g., "campaigns", "ad_groups")
        max_size: Maximum allowed size (uses get_max_ids_per_request if None)

    Returns:
        The validated list

    Raises:
        RateLimitError: If the list exceeds the maximum size
    """
    if id_list is None:
        return None

    if max_size is None:
        max_size = get_max_ids_per_request()

    if len(id_list) > max_size:
        raise RateLimitError(
            f"Too many {list_name} provided: {len(id_list)} exceeds maximum of {max_size}. "
            f"Please use pagination or reduce the number of {list_name} in your request."
        )

    return id_list


def validate_multiple_id_lists(
    **kwargs: list[Any] | None,
) -> dict[str, list[Any] | None]:
    """Validate multiple ID lists at once.

    Args:
        **kwargs: Named ID lists to validate

    Returns:
        Dictionary of validated lists

    Raises:
        RateLimitError: If any list exceeds the maximum size
    """
    max_size = get_max_ids_per_request()
    result = {}

    for name, id_list in kwargs.items():
        result[name] = validate_id_list_size(id_list, name, max_size)

    return result


def paginate_id_list(
    id_list: list[T],
    page_size: int | None = None,
) -> list[list[T]]:
    """Split a large ID list into pages.

    Args:
        id_list: List of IDs to paginate
        page_size: Size of each page (uses get_max_ids_per_request if None)

    Returns:
        List of pages, each containing up to page_size items
    """
    if not id_list:
        return []

    if page_size is None:
        page_size = get_max_ids_per_request()

    pages = []
    for i in range(0, len(id_list), page_size):
        pages.append(id_list[i : i + page_size])

    return pages
