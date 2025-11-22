"""Customer-related GraphQL types."""

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Optional

import strawberry

if TYPE_CHECKING:
    pass


@strawberry.type
@dataclass
class Customer:
    """Customer GraphQL type."""

    id: strawberry.ID
    name: str
    google_ads_account_id: str
    created_at: datetime
    updated_at: datetime
    is_active: bool = True


@strawberry.input
@dataclass
class CustomerFilter:
    """Customer filter input type."""

    is_active: Optional[bool] = None
    name_contains: Optional[str] = None
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None
