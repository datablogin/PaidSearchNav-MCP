"""Tests for Audit Logger."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from paidsearchnav_mcp.security.audit_logger import (
    AuditEvent,
    AuditEventType,
    AuditLogger,
    AuditSeverity,
    ComplianceReport,
    SecurityAlert,
)


@pytest.fixture
def audit_logger():
    """Create AuditLogger instance."""
    return AuditLogger()


@pytest.fixture
def mock_storage():
    """Create mock storage backend."""
    return MagicMock()


@pytest.fixture
def mock_alerting():
    """Create mock alerting backend."""
    return MagicMock()


@pytest.fixture
def audit_logger_with_backends(mock_storage, mock_alerting):
    """Create AuditLogger with backends."""
    return AuditLogger(storage_backend=mock_storage, alerting_backend=mock_alerting)


class TestAuditLogger:
    """Test Audit Logger functionality."""

    def test_initialization(self, audit_logger):
        """Test logger initialization."""
        assert audit_logger.storage is None
        assert audit_logger.alerting is None
        assert isinstance(audit_logger._event_buffer, list)
        assert isinstance(audit_logger._alert_rules, dict)
        assert isinstance(audit_logger._compliance_requirements, dict)

    def test_log_event(self, audit_logger):
        """Test logging an audit event."""
        event = audit_logger.log_event(
            event_type=AuditEventType.ACCESS_GRANTED,
            action="Read file",
            result="success",
            user_id="user-123",
            customer_id="cust-456",
            resource_id="file.csv",
        )

        assert isinstance(event, AuditEvent)
        assert event.event_type == AuditEventType.ACCESS_GRANTED
        assert event.action == "Read file"
        assert event.result == "success"
        assert event.user_id == "user-123"
        assert event.customer_id == "cust-456"
        assert event.resource_id == "file.csv"
        assert event.severity == AuditSeverity.INFO

    def test_log_event_with_metadata(self, audit_logger):
        """Test logging event with metadata."""
        metadata = {"file_size": 1024, "duration_ms": 100}

        event = audit_logger.log_event(
            event_type=AuditEventType.DATA_UPLOAD,
            action="Upload data",
            result="success",
            metadata=metadata,
        )

        # Check that our metadata is included (audit logger may add additional metadata)
        for key, value in metadata.items():
            assert event.metadata[key] == value

    def test_log_access_event_granted(self, audit_logger):
        """Test logging access granted event."""
        event = audit_logger.log_access_event(
            granted=True,
            user_id="user-123",
            customer_id="cust-456",
            resource_path="/data/file.csv",
            access_level="READ",
            ip_address="192.168.1.100",
        )

        assert event.event_type == AuditEventType.ACCESS_GRANTED
        assert event.severity == AuditSeverity.INFO
        assert event.result == "granted"
        assert event.metadata["access_level"] == "READ"

    def test_log_access_event_denied(self, audit_logger):
        """Test logging access denied event."""
        event = audit_logger.log_access_event(
            granted=False,
            user_id="user-123",
            customer_id="cust-456",
            resource_path="/data/file.csv",
            access_level="WRITE",
            reason="Insufficient permissions",
        )

        assert event.event_type == AuditEventType.ACCESS_DENIED
        assert event.severity == AuditSeverity.WARNING
        assert event.result == "denied"
        assert event.metadata["reason"] == "Insufficient permissions"

    def test_log_data_operation(self, audit_logger):
        """Test logging data operation event."""
        event = audit_logger.log_data_operation(
            operation="upload",
            user_id="user-123",
            customer_id="cust-456",
            file_path="/data/report.pdf",
            file_size=2048000,
            success=True,
            duration_ms=500,
        )

        assert event.event_type == AuditEventType.DATA_UPLOAD
        assert event.severity == AuditSeverity.INFO
        assert event.result == "success"
        assert event.metadata["file_size"] == 2048000
        assert event.metadata["duration_ms"] == 500

    def test_log_security_event_success(self, audit_logger):
        """Test logging successful security event."""
        event = audit_logger.log_security_event(
            event_type=AuditEventType.LOGIN_SUCCESS,
            user_id="user-123",
            success=True,
            ip_address="192.168.1.100",
        )

        assert event.event_type == AuditEventType.LOGIN_SUCCESS
        assert event.severity == AuditSeverity.INFO
        assert event.result == "success"

    def test_log_security_event_failure(self, audit_logger):
        """Test logging failed security event."""
        event = audit_logger.log_security_event(
            event_type=AuditEventType.LOGIN_FAILURE,
            user_id="user-123",
            success=False,
            reason="Invalid password",
        )

        assert event.event_type == AuditEventType.LOGIN_FAILURE
        assert event.severity == AuditSeverity.WARNING
        assert event.result == "failure"
        assert event.metadata["reason"] == "Invalid password"

    def test_get_events_no_filter(self, audit_logger):
        """Test getting events without filters."""
        # Log some events
        audit_logger.log_event(
            event_type=AuditEventType.ACCESS_GRANTED, action="Test1", result="success"
        )
        audit_logger.log_event(
            event_type=AuditEventType.DATA_UPLOAD, action="Test2", result="success"
        )

        events = audit_logger.get_events()
        assert len(events) == 2

    def test_get_events_with_customer_filter(self, audit_logger):
        """Test getting events filtered by customer."""
        # Log events for different customers
        audit_logger.log_event(
            event_type=AuditEventType.ACCESS_GRANTED,
            action="Test1",
            result="success",
            customer_id="cust-123",
        )
        audit_logger.log_event(
            event_type=AuditEventType.ACCESS_GRANTED,
            action="Test2",
            result="success",
            customer_id="cust-456",
        )

        events = audit_logger.get_events(customer_id="cust-123")
        assert len(events) == 1
        assert events[0].customer_id == "cust-123"

    def test_get_events_with_time_filter(self, audit_logger):
        """Test getting events filtered by time."""
        now = datetime.now(timezone.utc)

        # Log event
        event = audit_logger.log_event(
            event_type=AuditEventType.ACCESS_GRANTED, action="Test", result="success"
        )

        # Get events after now - 1 hour
        events = audit_logger.get_events(start_time=now - timedelta(hours=1))
        assert len(events) == 1

        # Get events before now - 1 hour
        events = audit_logger.get_events(end_time=now - timedelta(hours=1))
        assert len(events) == 0

    def test_generate_compliance_report_gdpr(self, audit_logger):
        """Test GDPR compliance report generation."""
        start_date = datetime.now(timezone.utc) - timedelta(days=30)
        end_date = datetime.now(timezone.utc) + timedelta(
            hours=1
        )  # Include future events for test

        # Log some events
        audit_logger.log_event(
            event_type=AuditEventType.DATA_DELETION_REQUEST,
            action="Delete user data",
            result="success",
            customer_id="cust-123",
        )

        # Verify event was logged
        events = audit_logger.get_events()
        assert len(events) > 0, "No events found in buffer after logging"

        report = audit_logger.generate_compliance_report(
            framework="GDPR", start_date=start_date, end_date=end_date
        )

        assert isinstance(report, ComplianceReport)
        assert report.framework == "GDPR"
        assert report.total_events >= 1
        assert "right_to_be_forgotten" in report.requirements_checked

    def test_generate_compliance_report_soc2(self, audit_logger):
        """Test SOC2 compliance report generation."""
        start_date = datetime.now(timezone.utc) - timedelta(days=7)
        end_date = datetime.now(timezone.utc) + timedelta(
            hours=1
        )  # Add buffer for test timing

        # Log some events
        for _ in range(15):
            audit_logger.log_event(
                event_type=AuditEventType.ACCESS_DENIED,
                action="Unauthorized access",
                result="denied",
            )

        report = audit_logger.generate_compliance_report(
            framework="SOC2", start_date=start_date, end_date=end_date
        )

        assert report.framework == "SOC2"
        assert report.warnings > 0  # Too many access denials
        assert "access_control" in report.requirements_checked

    def test_check_alert_conditions_failed_logins(self, audit_logger_with_backends):
        """Test alert triggering for multiple failed logins."""
        user_id = "user-123"

        # Simulate multiple failed login attempts
        for _ in range(6):
            audit_logger_with_backends.log_security_event(
                event_type=AuditEventType.LOGIN_FAILURE, user_id=user_id, success=False
            )

        # Verify alert was triggered
        audit_logger_with_backends.alerting.send_alert.assert_called()
        call_args = audit_logger_with_backends.alerting.send_alert.call_args
        alert = call_args[0][0]

        assert isinstance(alert, SecurityAlert)
        assert alert.alert_type == "multiple_failed_logins"
        assert alert.severity == AuditSeverity.WARNING

    def test_check_alert_conditions_data_exfiltration(self, audit_logger_with_backends):
        """Test alert triggering for potential data exfiltration."""
        user_id = "user-123"

        # Simulate large data downloads
        for i in range(5):
            audit_logger_with_backends.log_data_operation(
                operation="download",
                user_id=user_id,
                customer_id="cust-456",
                file_path=f"/data/file{i}.csv",
                file_size=250 * 1024 * 1024,  # 250 MB each
                success=True,
            )

        # Verify alert was triggered
        audit_logger_with_backends.alerting.send_alert.assert_called()
        call_args = audit_logger_with_backends.alerting.send_alert.call_args
        alert = call_args[0][0]

        assert alert.alert_type == "data_exfiltration"
        assert alert.severity == AuditSeverity.CRITICAL

    def test_get_statistics(self, audit_logger):
        """Test getting audit statistics."""
        # Log various events
        audit_logger.log_event(
            event_type=AuditEventType.ACCESS_GRANTED,
            action="Test",
            result="success",
            user_id="user-123",
            customer_id="cust-456",
        )
        audit_logger.log_event(
            event_type=AuditEventType.ACCESS_DENIED,
            action="Test",
            result="failure",
            user_id="user-456",
            customer_id="cust-456",
        )

        stats = audit_logger.get_statistics()

        assert stats["total_events"] == 2
        assert stats["by_result"]["success"] == 1
        assert stats["by_result"]["failure"] == 1
        assert stats["unique_users"] == 2
        assert stats["unique_customers"] == 1

    def test_event_buffer_limit(self, audit_logger):
        """Test event buffer size limit."""
        # Log many events to exceed buffer limit
        for i in range(10001):
            audit_logger.log_event(
                event_type=AuditEventType.ACCESS_GRANTED,
                action=f"Test {i}",
                result="success",
            )

        # Buffer should be limited to 5000 most recent events
        assert len(audit_logger._event_buffer) == 5000

    def test_store_event_with_storage(self, audit_logger_with_backends):
        """Test storing event with storage backend."""
        event = audit_logger_with_backends.log_event(
            event_type=AuditEventType.DATA_UPLOAD, action="Upload", result="success"
        )

        # Verify event was stored
        audit_logger_with_backends.storage.store_audit_event.assert_called_once()
        call_args = audit_logger_with_backends.storage.store_audit_event.call_args
        stored_data = call_args[0][0]

        assert stored_data["event_id"] == event.event_id
        assert stored_data["event_type"] == event.event_type
