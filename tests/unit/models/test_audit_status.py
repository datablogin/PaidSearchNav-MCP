"""Unit tests for AuditStatus model."""

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from paidsearchnav.core.models import AuditState, AuditStatus


class TestAuditStatus:
    """Test AuditStatus model."""

    def test_create_audit_status(self):
        """Test creating an audit status."""
        status = AuditStatus(
            audit_id="exec-123",
            customer_id="1234567890",
            audit_type="keyword_match",
            state=AuditState.PENDING,
        )

        assert status.audit_id == "exec-123"
        assert status.customer_id == "1234567890"
        assert status.audit_type == "keyword_match"
        assert status.state == "pending"
        assert status.progress == 0.0
        assert status.retry_count == 0
        assert status.schedule_id is None
        assert status.result_id is None
        assert status.error_message is None
        assert status.completed_at is None
        assert isinstance(status.started_at, datetime)
        assert status.metrics == {}

    def test_audit_status_with_all_fields(self):
        """Test audit status with all fields."""
        started = datetime.now(timezone.utc)
        completed = started + timedelta(minutes=5)

        status = AuditStatus(
            audit_id="exec-456",
            schedule_id="sched-789",
            customer_id="9876543210",
            audit_type="search_term",
            state=AuditState.COMPLETED,
            progress=100.0,
            started_at=started,
            completed_at=completed,
            result_id="result-999",
            error_message=None,
            retry_count=0,
            metrics={
                "keywords_analyzed": 150,
                "issues_found": 25,
                "duration_seconds": 300,
            },
        )

        assert status.schedule_id == "sched-789"
        assert status.state == "completed"
        assert status.progress == 100.0
        assert status.completed_at == completed
        assert status.result_id == "result-999"
        assert status.metrics["keywords_analyzed"] == 150
        assert status.metrics["issues_found"] == 25

    def test_audit_state_enum(self):
        """Test AuditState enum values."""
        assert AuditState.PENDING == "pending"
        assert AuditState.RUNNING == "running"
        assert AuditState.COMPLETED == "completed"
        assert AuditState.FAILED == "failed"
        assert AuditState.CANCELLED == "cancelled"
        assert AuditState.RETRYING == "retrying"

    def test_is_terminal_property(self):
        """Test is_terminal property."""
        # Non-terminal states
        for state in [AuditState.PENDING, AuditState.RUNNING, AuditState.RETRYING]:
            status = AuditStatus(
                audit_id="test-001",
                customer_id="1234567890",
                audit_type="keyword_match",
                state=state,
            )
            assert status.is_terminal is False

        # Terminal states
        for state in [AuditState.COMPLETED, AuditState.FAILED, AuditState.CANCELLED]:
            status = AuditStatus(
                audit_id="test-002",
                customer_id="1234567890",
                audit_type="keyword_match",
                state=state,
            )
            assert status.is_terminal is True

    def test_is_running_property(self):
        """Test is_running property."""
        status = AuditStatus(
            audit_id="test-003",
            customer_id="1234567890",
            audit_type="keyword_match",
            state=AuditState.RUNNING,
        )
        assert status.is_running is True

        status.state = AuditState.PENDING
        assert status.is_running is False

    def test_is_successful_property(self):
        """Test is_successful property."""
        status = AuditStatus(
            audit_id="test-004",
            customer_id="1234567890",
            audit_type="keyword_match",
            state=AuditState.COMPLETED,
        )
        assert status.is_successful is True

        status.state = AuditState.FAILED
        assert status.is_successful is False

    def test_duration_seconds_property(self):
        """Test duration_seconds property."""
        started = datetime.now(timezone.utc)

        # No completed_at
        status = AuditStatus(
            audit_id="test-005",
            customer_id="1234567890",
            audit_type="keyword_match",
            state=AuditState.RUNNING,
            started_at=started,
        )
        assert status.duration_seconds is None

        # With completed_at
        completed = started + timedelta(seconds=150)
        status.completed_at = completed
        assert status.duration_seconds == 150.0

    def test_can_retry_property(self):
        """Test can_retry property."""
        # Can retry - failed with low retry count
        status = AuditStatus(
            audit_id="test-006",
            customer_id="1234567890",
            audit_type="keyword_match",
            state=AuditState.FAILED,
            retry_count=2,
        )
        assert status.can_retry is True

        # Cannot retry - max retries reached
        status.retry_count = 3
        assert status.can_retry is False

        # Cannot retry - not failed
        status.state = AuditState.COMPLETED
        status.retry_count = 0
        assert status.can_retry is False

    def test_to_summary_dict(self):
        """Test to_summary_dict method."""
        started = datetime.now(timezone.utc)
        completed = started + timedelta(minutes=10)

        status = AuditStatus(
            audit_id="test-007",
            schedule_id="sched-123",
            customer_id="1234567890",
            audit_type="geo_performance",
            state=AuditState.COMPLETED,
            progress=100.0,
            started_at=started,
            completed_at=completed,
            retry_count=1,
            error_message=None,
        )

        summary = status.to_summary_dict()

        assert summary["audit_id"] == "test-007"
        assert summary["schedule_id"] == "sched-123"
        assert summary["customer_id"] == "1234567890"
        assert summary["audit_type"] == "geo_performance"
        assert summary["state"] == "completed"
        assert summary["progress"] == 100.0
        assert summary["started_at"] == started.isoformat()
        assert summary["completed_at"] == completed.isoformat()
        assert summary["duration_seconds"] == 600.0
        assert summary["retry_count"] == 1
        assert summary["error_message"] is None

    def test_required_fields_validation(self):
        """Test validation of required fields."""
        with pytest.raises(ValidationError) as exc_info:
            AuditStatus()

        errors = exc_info.value.errors()
        assert len(errors) == 4
        required_fields = {error["loc"][0] for error in errors}
        assert required_fields == {"audit_id", "customer_id", "audit_type", "state"}

    def test_invalid_state(self):
        """Test invalid state value."""
        with pytest.raises(ValidationError) as exc_info:
            AuditStatus(
                audit_id="test-008",
                customer_id="1234567890",
                audit_type="keyword_match",
                state="invalid_state",
            )

        errors = exc_info.value.errors()
        assert any("state" in str(error["loc"]) for error in errors)

    def test_progress_validation(self):
        """Test progress field constraints."""
        status = AuditStatus(
            audit_id="test-009",
            customer_id="1234567890",
            audit_type="keyword_match",
            state=AuditState.RUNNING,
            progress=50.5,
        )
        assert status.progress == 50.5

        # Progress must be between 0 and 100
        with pytest.raises(ValidationError) as exc_info:
            AuditStatus(
                audit_id="test-009b",
                customer_id="1234567890",
                audit_type="keyword_match",
                state=AuditState.RUNNING,
                progress=150.0,
            )
        assert "Progress must be between 0 and 100" in str(exc_info.value)

        with pytest.raises(ValidationError) as exc_info:
            AuditStatus(
                audit_id="test-009c",
                customer_id="1234567890",
                audit_type="keyword_match",
                state=AuditState.RUNNING,
                progress=-10.0,
            )
        assert "Progress must be between 0 and 100" in str(exc_info.value)

    def test_datetime_serialization(self):
        """Test datetime serialization."""
        now = datetime.now(timezone.utc)
        status = AuditStatus(
            audit_id="test-010",
            customer_id="1234567890",
            audit_type="keyword_match",
            state=AuditState.RUNNING,
            started_at=now,
        )

        # Test model_dump_json
        json_str = status.model_dump_json()
        # Check that datetime is serialized (format may vary)
        assert "started_at" in json_str
        assert '"state":"running"' in json_str

    def test_error_message_handling(self):
        """Test error message in failed audits."""
        error_msg = "Failed to connect to Google Ads API"
        status = AuditStatus(
            audit_id="test-011",
            customer_id="1234567890",
            audit_type="keyword_match",
            state=AuditState.FAILED,
            error_message=error_msg,
            retry_count=1,
        )

        assert status.error_message == error_msg
        assert status.can_retry is True

        summary = status.to_summary_dict()
        assert summary["error_message"] == error_msg
