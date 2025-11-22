"""Repository for managing Google Ads account data."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from paidsearchnav.core.models.account import (
    Account,
    AccountHierarchy,
    AuditOptInStatus,
    SyncResult,
)
from paidsearchnav.storage.repository import AnalysisRepository

logger = logging.getLogger(__name__)


class AccountRepository:
    """Repository for account hierarchy and audit configuration.

    This is a simple file-based implementation for MVP.
    Future versions could use database storage.
    """

    def __init__(self, analysis_repo: AnalysisRepository):
        """Initialize account repository.

        Args:
            analysis_repo: Analysis repository for accessing settings
        """
        self.analysis_repo = analysis_repo
        # Use the data directory from settings
        self.data_dir = Path(analysis_repo.settings.data_dir) / "accounts"
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # File paths
        self.hierarchy_file = self.data_dir / "hierarchy.json"
        self.sync_history_file = self.data_dir / "sync_history.json"

    async def get_account_hierarchy(
        self, root_mcc: str | None = None
    ) -> AccountHierarchy | None:
        """Get stored account hierarchy.

        Args:
            root_mcc: Optional root MCC to filter by

        Returns:
            AccountHierarchy or None if not found
        """
        if not self.hierarchy_file.exists():
            return None

        try:
            with open(self.hierarchy_file, "r") as f:
                data = json.load(f)

            # Reconstruct hierarchy
            accounts = {}
            for customer_id, account_data in data.get("accounts", {}).items():
                # Convert timestamps
                if account_data.get("last_sync"):
                    account_data["last_sync"] = datetime.fromisoformat(
                        account_data["last_sync"]
                    )
                if account_data.get("created_at"):
                    account_data["created_at"] = datetime.fromisoformat(
                        account_data["created_at"]
                    )
                if account_data.get("updated_at"):
                    account_data["updated_at"] = datetime.fromisoformat(
                        account_data["updated_at"]
                    )

                accounts[customer_id] = Account(**account_data)

            hierarchy = AccountHierarchy(
                root_customer_id=data.get("root_customer_id"),
                accounts=accounts,
                last_sync=datetime.fromisoformat(data["last_sync"]),
            )

            # Filter by root MCC if specified
            if root_mcc and hierarchy.root_customer_id != root_mcc:
                return None

            return hierarchy

        except Exception as e:
            logger.error(f"Failed to load account hierarchy: {e}")
            return None

    async def save_account_hierarchy(self, hierarchy: AccountHierarchy) -> bool:
        """Save account hierarchy to storage.

        Args:
            hierarchy: Account hierarchy to save

        Returns:
            True if saved successfully
        """
        try:
            # Convert to JSON-serializable format
            data = {
                "root_customer_id": hierarchy.root_customer_id,
                "last_sync": hierarchy.last_sync.isoformat(),
                "accounts": {},
            }

            for customer_id, account in hierarchy.accounts.items():
                account_dict = account.model_dump()
                # Convert datetime fields
                for field in ["last_sync", "created_at", "updated_at"]:
                    if account_dict.get(field):
                        account_dict[field] = account_dict[field].isoformat()
                data["accounts"][customer_id] = account_dict

            # Save to file
            with open(self.hierarchy_file, "w") as f:
                json.dump(data, f, indent=2)

            logger.info(
                f"Saved account hierarchy with {len(hierarchy.accounts)} accounts"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to save account hierarchy: {e}")
            return False

    async def save_sync_history(self, sync_result: SyncResult) -> bool:
        """Save sync history for audit trail.

        Args:
            sync_result: Sync result to save

        Returns:
            True if saved successfully
        """
        try:
            # Load existing history
            history = []
            if self.sync_history_file.exists():
                with open(self.sync_history_file, "r") as f:
                    history = json.load(f)

            # Add new sync result
            sync_data = sync_result.model_dump()
            sync_data["timestamp"] = sync_data["timestamp"].isoformat()
            if sync_data.get("hierarchy"):
                # Don't store full hierarchy in history
                sync_data["hierarchy"] = None

            history.append(sync_data)

            # Keep only last 100 sync results
            if len(history) > 100:
                history = history[-100:]

            # Save back
            with open(self.sync_history_file, "w") as f:
                json.dump(history, f, indent=2)

            return True

        except Exception as e:
            logger.error(f"Failed to save sync history: {e}")
            return False

    async def get_account(self, customer_id: str) -> Account | None:
        """Get a specific account by customer ID.

        Args:
            customer_id: Google Ads customer ID

        Returns:
            Account or None if not found
        """
        hierarchy = await self.get_account_hierarchy()
        if not hierarchy:
            return None

        return hierarchy.get_account(customer_id)

    async def update_audit_status(
        self,
        customer_id: str,
        audit_status: AuditOptInStatus,
        audit_settings: dict[str, bool] | None = None,
    ) -> bool:
        """Update audit status for an account.

        Args:
            customer_id: Google Ads customer ID
            audit_status: New audit status
            audit_settings: Optional audit settings to update

        Returns:
            True if updated successfully
        """
        hierarchy = await self.get_account_hierarchy()
        if not hierarchy:
            logger.error("No account hierarchy found")
            return False

        account = hierarchy.get_account(customer_id)
        if not account:
            logger.error(f"Account {customer_id} not found")
            return False

        # Update status
        account.audit_status = audit_status
        account.updated_at = datetime.utcnow()

        # Update settings if provided
        if audit_settings:
            account.audit_settings.update(audit_settings)

        # Save back
        return await self.save_account_hierarchy(hierarchy)

    async def get_opted_in_accounts(self) -> list[Account]:
        """Get all accounts opted in for auditing.

        Returns:
            List of opted-in accounts
        """
        hierarchy = await self.get_account_hierarchy()
        if not hierarchy:
            return []

        return hierarchy.get_opted_in_accounts()

    async def get_customers_for_user(self, user_id: str) -> list[dict[str, Any]]:
        """Get customers accessible by a user.

        This is a simplified implementation for MVP.
        In production, this would check user permissions.

        Args:
            user_id: User ID

        Returns:
            List of customer data dictionaries
        """
        hierarchy = await self.get_account_hierarchy()
        if not hierarchy:
            return []

        # For MVP, return all accessible accounts
        return [
            {
                "customer_id": account.customer_id,
                "name": account.name,
                "account_type": account.account_type.value,
            }
            for account in hierarchy.accounts.values()
            if account.accessible
        ]
