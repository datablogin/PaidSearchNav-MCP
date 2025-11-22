"""Common GraphQL type definitions."""

from dataclasses import dataclass
from datetime import datetime
from typing import Generic, List, Optional, TypeVar

import strawberry

T = TypeVar("T")


@strawberry.input
@dataclass
class DateRange:
    """Date range filter type."""

    start_date: datetime
    end_date: datetime


@strawberry.type
@dataclass
class PageInfo:
    """Pagination information following Relay spec."""

    has_next_page: bool
    has_previous_page: bool
    start_cursor: Optional[str] = None
    end_cursor: Optional[str] = None


@strawberry.type
@dataclass
class Connection(Generic[T]):
    """Generic connection type for pagination."""

    edges: List[T]
    page_info: PageInfo
    total_count: int
