"""Account models for Google Ads account management."""

from datetime import datetime
from enum import Enum

from pydantic import Field

from paidsearchnav_mcp.models.base import BasePSNModel


class AccountType(str, Enum):
    """Type of Google Ads account."""

    MCC = "MCC"  # Manager account
    STANDARD = "STANDARD"  # Regular advertiser account


class AccountStatus(str, Enum):
    """Google Ads account status."""

    ENABLED = "ENABLED"
    PAUSED = "PAUSED"
    REMOVED = "REMOVED"
    SUSPENDED = "SUSPENDED"
    CANCELED = "CANCELED"


class AuditOptInStatus(str, Enum):
    """Audit opt-in/out status for an account."""

    OPT_IN = "opt-in"
    OPT_OUT = "opt-out"
    PENDING = "pending"


class Account(BasePSNModel):
    """Represents a Google Ads account."""

    customer_id: str = Field(..., description="Google Ads customer ID")
    name: str = Field(..., description="Account descriptive name")
    account_type: AccountType = Field(
        ..., description="Type of account (MCC or STANDARD)"
    )
    status: AccountStatus = Field(..., description="Account status")
    audit_status: AuditOptInStatus = Field(
        default=AuditOptInStatus.PENDING, description="Audit opt-in/out status"
    )

    # Manager hierarchy
    manager_customer_id: str | None = Field(None, description="Parent MCC customer ID")
    is_mcc: bool = Field(False, description="Whether this is a manager account")
    can_manage_clients: bool = Field(
        False, description="Whether account can manage other accounts"
    )

    # Access and metadata
    accessible: bool = Field(
        True, description="Whether account is accessible to the API user"
    )
    access_reason: str | None = Field(
        None, description="Reason for access (e.g., OWNED, MANAGER)"
    )
    currency_code: str | None = Field(None, description="Account currency code")
    time_zone: str | None = Field(None, description="Account time zone")
    test_account: bool = Field(False, description="Whether this is a test account")

    # Audit settings
    audit_settings: dict[str, bool] = Field(
        default_factory=lambda: {
            "include_search": True,
            "include_pmax": True,
            "include_shopping": False,
            "include_display": False,
            "include_video": False,
        },
        description="Campaign types to include in audits",
    )

    # Timestamps
    last_sync: datetime | None = Field(
        None, description="Last time account was synced from API"
    )
    created_at: datetime | None = Field(
        None, description="When account was first discovered"
    )
    updated_at: datetime | None = Field(None, description="Last update timestamp")


class AccountHierarchy(BasePSNModel):
    """Represents a hierarchy of Google Ads accounts."""

    root_customer_id: str | None = Field(None, description="Root MCC customer ID")
    accounts: dict[str, Account] = Field(
        default_factory=dict, description="All accounts keyed by customer ID"
    )
    last_sync: datetime = Field(..., description="When hierarchy was last synced")

    @property
    def total_accounts(self) -> int:
        """Total number of accounts in hierarchy."""
        return len(self.accounts)

    @property
    def total_mccs(self) -> int:
        """Total number of MCC accounts."""
        return sum(1 for acc in self.accounts.values() if acc.is_mcc)

    @property
    def total_opted_in(self) -> int:
        """Total accounts opted in for auditing."""
        return sum(
            1
            for acc in self.accounts.values()
            if acc.audit_status == AuditOptInStatus.OPT_IN
        )

    def get_account(self, customer_id: str) -> Account | None:
        """Get account by customer ID."""
        return self.accounts.get(customer_id)

    def get_opted_in_accounts(self) -> list[Account]:
        """Get all accounts opted in for auditing."""
        return [
            acc
            for acc in self.accounts.values()
            if acc.audit_status == AuditOptInStatus.OPT_IN
        ]


class SyncResult(BasePSNModel):
    """Result of syncing account hierarchy from Google Ads API."""

    success: bool = Field(..., description="Whether sync was successful")
    hierarchy: AccountHierarchy | None = Field(
        None, description="Synced account hierarchy"
    )
    accounts_synced: int = Field(0, description="Number of accounts synced")
    errors: list[str] = Field(
        default_factory=list, description="Any errors encountered"
    )
    sync_duration_seconds: float = Field(..., description="Time taken to sync")
    timestamp: datetime = Field(..., description="When sync occurred")
