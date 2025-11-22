"""Unit tests for ScheduledAudit model."""

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from paidsearchnav.core.models import AuditFrequency, ScheduledAudit


class TestScheduledAudit:
    """Test ScheduledAudit model."""

    def test_create_scheduled_audit(self):
        """Test creating a scheduled audit."""
        audit = ScheduledAudit(
            id="audit-123",
            customer_id="1234567890",
            audit_type="keyword_match",
            frequency=AuditFrequency.WEEKLY,
        )

        assert audit.id == "audit-123"
        assert audit.customer_id == "1234567890"
        assert audit.audit_type == "keyword_match"
        assert audit.frequency == "weekly"
        assert audit.enabled is True
        assert audit.last_run is None
        assert audit.next_run is None
        assert audit.config == {}

    def test_scheduled_audit_with_all_fields(self):
        """Test scheduled audit with all fields."""
        now = datetime.now(timezone.utc)
        next_run = now + timedelta(days=7)

        audit = ScheduledAudit(
            id="audit-456",
            customer_id="9876543210",
            audit_type="search_term",
            frequency=AuditFrequency.QUARTERLY,
            cron_expression="0 0 1 */3 *",
            config={"include_paused": True, "min_impressions": 100},
            enabled=False,
            last_run=now,
            next_run=next_run,
        )

        assert audit.frequency == "quarterly"
        assert audit.cron_expression == "0 0 1 */3 *"
        assert audit.config["include_paused"] is True
        assert audit.config["min_impressions"] == 100
        assert audit.enabled is False
        assert audit.last_run == now
        assert audit.next_run == next_run

    def test_audit_frequency_enum(self):
        """Test AuditFrequency enum values."""
        assert AuditFrequency.DAILY == "daily"
        assert AuditFrequency.WEEKLY == "weekly"
        assert AuditFrequency.MONTHLY == "monthly"
        assert AuditFrequency.QUARTERLY == "quarterly"
        assert AuditFrequency.ON_DEMAND == "on_demand"

    def test_is_active_property(self):
        """Test is_active property."""
        audit = ScheduledAudit(
            id="audit-789",
            customer_id="1234567890",
            audit_type="keyword_match",
            frequency=AuditFrequency.DAILY,
            enabled=True,
        )
        assert audit.is_active is True

        audit.enabled = False
        assert audit.is_active is False

    def test_is_due_property(self):
        """Test is_due property."""
        now = datetime.now(timezone.utc)

        # Not due - no next_run
        audit = ScheduledAudit(
            id="audit-001",
            customer_id="1234567890",
            audit_type="keyword_match",
            frequency=AuditFrequency.DAILY,
        )
        assert audit.is_due is False

        # Not due - disabled
        audit.next_run = now - timedelta(hours=1)
        audit.enabled = False
        assert audit.is_due is False

        # Due - enabled and past next_run
        audit.enabled = True
        assert audit.is_due is True

        # Not due - future next_run
        audit.next_run = now + timedelta(hours=1)
        assert audit.is_due is False

    def test_has_run_property(self):
        """Test has_run property."""
        audit = ScheduledAudit(
            id="audit-002",
            customer_id="1234567890",
            audit_type="keyword_match",
            frequency=AuditFrequency.DAILY,
        )
        assert audit.has_run is False

        audit.last_run = datetime.now(timezone.utc)
        assert audit.has_run is True

    def test_to_summary_dict(self):
        """Test to_summary_dict method."""
        now = datetime.now(timezone.utc)
        next_run = now + timedelta(days=1)

        audit = ScheduledAudit(
            id="audit-003",
            customer_id="1234567890",
            audit_type="geo_performance",
            frequency=AuditFrequency.MONTHLY,
            enabled=True,
            last_run=now,
            next_run=next_run,
        )

        summary = audit.to_summary_dict()

        assert summary["id"] == "audit-003"
        assert summary["customer_id"] == "1234567890"
        assert summary["audit_type"] == "geo_performance"
        assert summary["frequency"] == "monthly"
        assert summary["enabled"] is True
        assert summary["last_run"] == now.isoformat()
        assert summary["next_run"] == next_run.isoformat()
        assert summary["is_due"] is False

    def test_required_fields_validation(self):
        """Test validation of required fields."""
        with pytest.raises(ValidationError) as exc_info:
            ScheduledAudit()

        errors = exc_info.value.errors()
        assert len(errors) == 4
        required_fields = {error["loc"][0] for error in errors}
        assert required_fields == {"id", "customer_id", "audit_type", "frequency"}

    def test_invalid_frequency(self):
        """Test invalid frequency value."""
        with pytest.raises(ValidationError) as exc_info:
            ScheduledAudit(
                id="audit-004",
                customer_id="1234567890",
                audit_type="keyword_match",
                frequency="invalid_frequency",
            )

        errors = exc_info.value.errors()
        assert any("frequency" in str(error["loc"]) for error in errors)

    def test_datetime_serialization(self):
        """Test datetime serialization."""
        now = datetime.now(timezone.utc)
        audit = ScheduledAudit(
            id="audit-005",
            customer_id="1234567890",
            audit_type="keyword_match",
            frequency=AuditFrequency.DAILY,
            last_run=now,
        )

        # Test model_dump_json
        json_str = audit.model_dump_json()
        # Check that datetime is serialized (format may vary)
        assert "last_run" in json_str
        assert '"frequency":"daily"' in json_str
