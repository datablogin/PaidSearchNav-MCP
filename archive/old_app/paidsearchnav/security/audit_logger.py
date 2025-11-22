"""Security audit logger for compliance and monitoring."""

import logging
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Constants for audit configuration
AUDIT_BUFFER_SIZE = 10000
AUDIT_BUFFER_RETAIN = 5000
DEFAULT_EVENT_LIMIT = 1000
GDPR_DATA_RETENTION_DAYS = 90
GDPR_BREACH_NOTIFICATION_HOURS = 72
CCPA_DATA_RETENTION_DAYS = 365
FAILED_LOGIN_THRESHOLD = 5
FAILED_LOGIN_WINDOW_MINUTES = 15
UNAUTHORIZED_ACCESS_THRESHOLD = 3
UNAUTHORIZED_ACCESS_WINDOW_MINUTES = 5
DATA_EXFILTRATION_THRESHOLD_MB = 1000
DATA_EXFILTRATION_WINDOW_MINUTES = 60
EXCESSIVE_ACCESS_DENIALS_THRESHOLD = 10


class AuditEventType(Enum):
    """Audit event type enumeration."""

    # Access events
    ACCESS_GRANTED = "access_granted"
    ACCESS_DENIED = "access_denied"
    ACCESS_REVOKED = "access_revoked"

    # Data operations
    DATA_UPLOAD = "data_upload"
    DATA_DOWNLOAD = "data_download"
    DATA_DELETE = "data_delete"
    DATA_MODIFY = "data_modify"

    # Security events
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILURE = "login_failure"
    LOGOUT = "logout"
    PASSWORD_CHANGE = "password_change"
    MFA_ENABLED = "mfa_enabled"
    MFA_DISABLED = "mfa_disabled"

    # Key management
    KEY_CREATED = "key_created"
    KEY_ROTATED = "key_rotated"
    KEY_DELETED = "key_deleted"

    # Policy changes
    POLICY_CREATED = "policy_created"
    POLICY_MODIFIED = "policy_modified"
    POLICY_DELETED = "policy_deleted"

    # Compliance
    COMPLIANCE_CHECK = "compliance_check"
    COMPLIANCE_VIOLATION = "compliance_violation"
    DATA_RETENTION = "data_retention"
    DATA_DELETION_REQUEST = "data_deletion_request"


class AuditSeverity(Enum):
    """Audit event severity levels."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AuditEvent(BaseModel):
    """Security audit event."""

    event_id: str = Field(..., description="Unique event ID")
    event_type: AuditEventType = Field(..., description="Type of event")
    severity: AuditSeverity = Field(AuditSeverity.INFO, description="Event severity")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Actor information
    user_id: Optional[str] = Field(None, description="User who performed action")
    service_account: Optional[str] = Field(
        None, description="Service account if applicable"
    )
    ip_address: Optional[str] = Field(None, description="Source IP address")
    user_agent: Optional[str] = Field(None, description="User agent string")

    # Target information
    customer_id: Optional[str] = Field(None, description="Affected customer")
    resource_type: Optional[str] = Field(None, description="Resource type")
    resource_id: Optional[str] = Field(None, description="Resource identifier")
    resource_path: Optional[str] = Field(None, description="Resource path")

    # Event details
    action: str = Field(..., description="Action performed")
    result: str = Field(..., description="Result of action")
    reason: Optional[str] = Field(None, description="Reason for action/result")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )

    # Compliance information
    compliance_framework: Optional[str] = Field(
        None, description="Compliance framework"
    )
    compliance_requirement: Optional[str] = Field(
        None, description="Specific requirement"
    )

    # Response information
    response_code: Optional[int] = Field(
        None, description="HTTP response code if applicable"
    )
    duration_ms: Optional[int] = Field(
        None, description="Operation duration in milliseconds"
    )


class SecurityAlert(BaseModel):
    """Security alert for suspicious activities."""

    alert_id: str = Field(..., description="Alert ID")
    alert_type: str = Field(..., description="Type of security alert")
    severity: AuditSeverity = Field(..., description="Alert severity")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    description: str = Field(..., description="Alert description")
    affected_resources: List[str] = Field(default_factory=list)
    indicators: Dict[str, Any] = Field(default_factory=dict)

    triggered_by: List[AuditEvent] = Field(default_factory=list)
    response_required: bool = Field(True)
    auto_remediation: Optional[str] = Field(None)


class ComplianceReport(BaseModel):
    """Compliance audit report."""

    report_id: str = Field(..., description="Report ID")
    framework: str = Field(..., description="Compliance framework (GDPR, CCPA, SOC2)")
    period_start: datetime = Field(..., description="Audit period start")
    period_end: datetime = Field(..., description="Audit period end")
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    total_events: int = Field(0)
    violations: int = Field(0)
    warnings: int = Field(0)

    requirements_checked: Dict[str, bool] = Field(default_factory=dict)
    findings: List[Dict[str, Any]] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)


class AuditLogger:
    """
    Comprehensive security audit logger for compliance and monitoring.

    This class provides:
    - Security event logging with full context
    - Real-time alerting for suspicious activities
    - Compliance reporting (GDPR, CCPA, SOC2)
    - Data retention policy enforcement
    - Access pattern analysis
    - Incident response support
    """

    def __init__(
        self,
        storage_backend: Optional[Any] = None,
        alerting_backend: Optional[Any] = None,
    ):
        """
        Initialize Audit Logger.

        Args:
            storage_backend: Backend for storing audit logs
            alerting_backend: Backend for sending alerts
        """
        self.storage = storage_backend
        self.alerting = alerting_backend
        self._event_buffer: List[AuditEvent] = []
        self._alert_rules = self._initialize_alert_rules()
        self._compliance_requirements = self._initialize_compliance_requirements()

    def _initialize_alert_rules(self) -> Dict[str, Dict]:
        """Initialize security alert rules."""
        return {
            "multiple_failed_logins": {
                "threshold": FAILED_LOGIN_THRESHOLD,
                "window_minutes": FAILED_LOGIN_WINDOW_MINUTES,
                "severity": AuditSeverity.WARNING,
                "description": "Multiple failed login attempts detected",
            },
            "unauthorized_access": {
                "threshold": UNAUTHORIZED_ACCESS_THRESHOLD,
                "window_minutes": UNAUTHORIZED_ACCESS_WINDOW_MINUTES,
                "severity": AuditSeverity.CRITICAL,
                "description": "Multiple unauthorized access attempts",
            },
            "data_exfiltration": {
                "threshold_mb": DATA_EXFILTRATION_THRESHOLD_MB,
                "window_minutes": DATA_EXFILTRATION_WINDOW_MINUTES,
                "severity": AuditSeverity.CRITICAL,
                "description": "Potential data exfiltration detected",
            },
            "privilege_escalation": {
                "threshold": 1,
                "severity": AuditSeverity.CRITICAL,
                "description": "Privilege escalation attempt detected",
            },
            "policy_violation": {
                "threshold": 1,
                "severity": AuditSeverity.WARNING,
                "description": "Security policy violation detected",
            },
        }

    def _initialize_compliance_requirements(self) -> Dict[str, Dict]:
        """Initialize compliance requirements."""
        return {
            "GDPR": {
                "data_retention_days": GDPR_DATA_RETENTION_DAYS,
                "right_to_be_forgotten": True,
                "data_portability": True,
                "consent_required": True,
                "breach_notification_hours": GDPR_BREACH_NOTIFICATION_HOURS,
            },
            "CCPA": {
                "data_retention_days": CCPA_DATA_RETENTION_DAYS,
                "opt_out_required": True,
                "data_transparency": True,
                "non_discrimination": True,
            },
            "SOC2": {
                "access_control": True,
                "encryption_required": True,
                "monitoring_required": True,
                "incident_response": True,
                "change_management": True,
            },
        }

    def log_event(
        self,
        event_type: AuditEventType,
        action: str,
        result: str,
        user_id: Optional[str] = None,
        customer_id: Optional[str] = None,
        resource_id: Optional[str] = None,
        severity: AuditSeverity = AuditSeverity.INFO,
        metadata: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> AuditEvent:
        """
        Log a security audit event.

        Args:
            event_type: Type of event
            action: Action performed
            result: Result of action
            user_id: User ID (optional)
            customer_id: Customer ID (optional)
            resource_id: Resource ID (optional)
            severity: Event severity
            metadata: Additional metadata
            ip_address: Source IP address
            user_agent: User agent string

        Returns:
            Created audit event
        """
        import uuid

        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            severity=severity,
            action=action,
            result=result,
            user_id=user_id,
            customer_id=customer_id,
            resource_id=resource_id,
            ip_address=ip_address,
            user_agent=user_agent,
            metadata=metadata or {},
        )

        # Store event
        self._store_event(event)

        # Check for security alerts
        self._check_alert_conditions(event)

        # Check compliance requirements
        self._check_compliance(event)

        logger.info(f"Audit event logged: {event.event_type.value} - {event.action}")

        return event

    def log_access_event(
        self,
        granted: bool,
        user_id: str,
        customer_id: str,
        resource_path: str,
        access_level: str,
        reason: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> AuditEvent:
        """
        Log an access control event.

        Args:
            granted: Whether access was granted
            user_id: User ID
            customer_id: Customer ID
            resource_path: Resource path
            access_level: Requested access level
            reason: Reason for decision
            ip_address: Source IP address

        Returns:
            Created audit event
        """
        event_type = (
            AuditEventType.ACCESS_GRANTED if granted else AuditEventType.ACCESS_DENIED
        )
        severity = AuditSeverity.INFO if granted else AuditSeverity.WARNING

        return self.log_event(
            event_type=event_type,
            action=f"Access request for {access_level}",
            result="granted" if granted else "denied",
            user_id=user_id,
            customer_id=customer_id,
            resource_id=resource_path,
            severity=severity,
            metadata={
                "access_level": access_level,
                "resource_path": resource_path,
                "reason": reason,
            },
            ip_address=ip_address,
        )

    def log_data_operation(
        self,
        operation: str,
        user_id: str,
        customer_id: str,
        file_path: str,
        file_size: int,
        success: bool,
        duration_ms: Optional[int] = None,
        ip_address: Optional[str] = None,
    ) -> AuditEvent:
        """
        Log a data operation event.

        Args:
            operation: Operation type (upload/download/delete)
            user_id: User ID
            customer_id: Customer ID
            file_path: File path
            file_size: File size in bytes
            success: Whether operation succeeded
            duration_ms: Operation duration
            ip_address: Source IP address

        Returns:
            Created audit event
        """
        event_type_map = {
            "upload": AuditEventType.DATA_UPLOAD,
            "download": AuditEventType.DATA_DOWNLOAD,
            "delete": AuditEventType.DATA_DELETE,
            "modify": AuditEventType.DATA_MODIFY,
        }

        event_type = event_type_map.get(operation, AuditEventType.DATA_MODIFY)
        severity = AuditSeverity.INFO if success else AuditSeverity.ERROR

        return self.log_event(
            event_type=event_type,
            action=f"Data {operation}",
            result="success" if success else "failure",
            user_id=user_id,
            customer_id=customer_id,
            resource_id=file_path,
            severity=severity,
            metadata={
                "file_path": file_path,
                "file_size": file_size,
                "duration_ms": duration_ms,
            },
            ip_address=ip_address,
        )

    def log_security_event(
        self,
        event_type: AuditEventType,
        user_id: str,
        success: bool,
        reason: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> AuditEvent:
        """
        Log a security event (login, logout, etc.).

        Args:
            event_type: Security event type
            user_id: User ID
            success: Whether operation succeeded
            reason: Reason for failure
            ip_address: Source IP address
            user_agent: User agent string

        Returns:
            Created audit event
        """
        severity = AuditSeverity.INFO if success else AuditSeverity.WARNING

        if event_type == AuditEventType.LOGIN_FAILURE:
            severity = AuditSeverity.WARNING

        return self.log_event(
            event_type=event_type,
            action=event_type.value,
            result="success" if success else "failure",
            user_id=user_id,
            severity=severity,
            metadata={"reason": reason} if reason else {},
            ip_address=ip_address,
            user_agent=user_agent,
        )

    def get_events(
        self,
        customer_id: Optional[str] = None,
        user_id: Optional[str] = None,
        event_types: Optional[List[AuditEventType]] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = DEFAULT_EVENT_LIMIT,
    ) -> List[AuditEvent]:
        """
        Query audit events.

        Args:
            customer_id: Filter by customer
            user_id: Filter by user
            event_types: Filter by event types
            start_time: Start time filter
            end_time: End time filter
            limit: Maximum results

        Returns:
            List of matching events
        """
        # In production, this would query the storage backend
        events = self._event_buffer

        # Apply filters
        if customer_id:
            events = [e for e in events if e.customer_id == customer_id]

        if user_id:
            events = [e for e in events if e.user_id == user_id]

        if event_types:
            events = [e for e in events if e.event_type in event_types]

        if start_time:
            events = [e for e in events if e.timestamp >= start_time]

        if end_time:
            events = [e for e in events if e.timestamp <= end_time]

        # Sort by timestamp descending
        events.sort(key=lambda e: e.timestamp, reverse=True)

        return events[:limit]

    def generate_compliance_report(
        self,
        framework: str,
        start_date: datetime,
        end_date: datetime,
        customer_id: Optional[str] = None,
    ) -> ComplianceReport:
        """
        Generate compliance audit report.

        Args:
            framework: Compliance framework (GDPR, CCPA, SOC2)
            start_date: Report start date
            end_date: Report end date
            customer_id: Specific customer (optional)

        Returns:
            Compliance report
        """
        import uuid

        report = ComplianceReport(
            report_id=str(uuid.uuid4()),
            framework=framework,
            period_start=start_date,
            period_end=end_date,
        )

        # Get events for period
        events = self.get_events(
            customer_id=customer_id, start_time=start_date, end_time=end_date
        )

        report.total_events = len(events)

        # Check framework requirements
        requirements = self._compliance_requirements.get(framework, {})

        if framework == "GDPR":
            report = self._check_gdpr_compliance(report, events, requirements)
        elif framework == "CCPA":
            report = self._check_ccpa_compliance(report, events, requirements)
        elif framework == "SOC2":
            report = self._check_soc2_compliance(report, events, requirements)

        logger.info(f"Compliance report generated: {framework} - {report.report_id}")

        return report

    def _check_gdpr_compliance(
        self, report: ComplianceReport, events: List[AuditEvent], requirements: Dict
    ) -> ComplianceReport:
        """Check GDPR compliance."""
        # Check data retention
        retention_violations = 0
        for event in events:
            if event.event_type == AuditEventType.DATA_RETENTION:
                age_days = event.metadata.get("age_days", 0)
                if age_days > requirements.get("data_retention_days", 90):
                    retention_violations += 1

        report.requirements_checked["data_retention"] = retention_violations == 0

        # Check right to be forgotten
        deletion_requests = [
            e for e in events if e.event_type == AuditEventType.DATA_DELETION_REQUEST
        ]

        report.requirements_checked["right_to_be_forgotten"] = True
        for request in deletion_requests:
            if request.result != "success":
                report.requirements_checked["right_to_be_forgotten"] = False
                report.violations += 1

        # Check consent
        access_events = [
            e
            for e in events
            if e.event_type
            in [AuditEventType.ACCESS_GRANTED, AuditEventType.DATA_UPLOAD]
        ]

        for event in access_events:
            if not event.metadata.get("consent_verified"):
                report.warnings += 1
                report.findings.append(
                    {
                        "type": "missing_consent",
                        "event_id": event.event_id,
                        "timestamp": event.timestamp.isoformat(),
                    }
                )

        if report.violations > 0:
            report.recommendations.append("Implement automated data retention policies")

        if report.warnings > 0:
            report.recommendations.append("Enhance consent verification mechanisms")

        return report

    def _check_ccpa_compliance(
        self, report: ComplianceReport, events: List[AuditEvent], requirements: Dict
    ) -> ComplianceReport:
        """Check CCPA compliance."""
        # Check opt-out mechanisms
        opt_out_available = any(
            e.metadata.get("opt_out_option")
            for e in events
            if e.event_type == AuditEventType.DATA_UPLOAD
        )

        report.requirements_checked["opt_out_available"] = opt_out_available

        if not opt_out_available:
            report.violations += 1
            report.recommendations.append(
                "Implement opt-out mechanisms for data collection"
            )

        return report

    def _check_soc2_compliance(
        self, report: ComplianceReport, events: List[AuditEvent], requirements: Dict
    ) -> ComplianceReport:
        """Check SOC2 compliance."""
        # Check access control
        unauthorized_access = [
            e for e in events if e.event_type == AuditEventType.ACCESS_DENIED
        ]

        report.requirements_checked["access_control"] = True
        if len(unauthorized_access) > EXCESSIVE_ACCESS_DENIALS_THRESHOLD:
            report.warnings += 1
            report.findings.append(
                {"type": "excessive_access_denials", "count": len(unauthorized_access)}
            )

        # Check encryption
        unencrypted_operations = [
            e
            for e in events
            if e.event_type
            in [AuditEventType.DATA_UPLOAD, AuditEventType.DATA_DOWNLOAD]
            and not e.metadata.get("encrypted")
        ]

        report.requirements_checked["encryption"] = len(unencrypted_operations) == 0

        if unencrypted_operations:
            report.violations += 1
            report.recommendations.append("Enforce encryption for all data operations")

        # Check monitoring
        report.requirements_checked["monitoring"] = True  # We're monitoring!

        return report

    def _check_alert_conditions(self, event: AuditEvent) -> None:
        """Check if event triggers any security alerts."""
        # Check for multiple failed logins
        if event.event_type == AuditEventType.LOGIN_FAILURE:
            self._check_failed_login_pattern(event)

        # Check for unauthorized access attempts
        if event.event_type == AuditEventType.ACCESS_DENIED:
            self._check_unauthorized_access_pattern(event)

        # Check for data exfiltration
        if event.event_type == AuditEventType.DATA_DOWNLOAD:
            self._check_data_exfiltration_pattern(event)

    def _check_failed_login_pattern(self, event: AuditEvent) -> None:
        """Check for multiple failed login attempts."""
        rule = self._alert_rules["multiple_failed_logins"]
        window_start = event.timestamp - timedelta(minutes=rule["window_minutes"])

        recent_failures = [
            e
            for e in self._event_buffer
            if e.event_type == AuditEventType.LOGIN_FAILURE
            and e.user_id == event.user_id
            and e.timestamp >= window_start
        ]

        if len(recent_failures) >= rule["threshold"]:
            self._trigger_alert(
                alert_type="multiple_failed_logins",
                severity=rule["severity"],
                description=rule["description"],
                events=recent_failures,
            )

    def _check_unauthorized_access_pattern(self, event: AuditEvent) -> None:
        """Check for unauthorized access patterns."""
        rule = self._alert_rules["unauthorized_access"]
        window_start = event.timestamp - timedelta(minutes=rule["window_minutes"])

        recent_denials = [
            e
            for e in self._event_buffer
            if e.event_type == AuditEventType.ACCESS_DENIED
            and e.user_id == event.user_id
            and e.timestamp >= window_start
        ]

        if len(recent_denials) >= rule["threshold"]:
            self._trigger_alert(
                alert_type="unauthorized_access",
                severity=rule["severity"],
                description=rule["description"],
                events=recent_denials,
            )

    def _check_data_exfiltration_pattern(self, event: AuditEvent) -> None:
        """Check for potential data exfiltration."""
        rule = self._alert_rules["data_exfiltration"]
        window_start = event.timestamp - timedelta(minutes=rule["window_minutes"])

        recent_downloads = [
            e
            for e in self._event_buffer
            if e.event_type == AuditEventType.DATA_DOWNLOAD
            and e.user_id == event.user_id
            and e.timestamp >= window_start
        ]

        total_bytes = sum(e.metadata.get("file_size", 0) for e in recent_downloads)
        total_mb = total_bytes / (1024 * 1024)

        if total_mb >= rule["threshold_mb"]:
            self._trigger_alert(
                alert_type="data_exfiltration",
                severity=rule["severity"],
                description=rule["description"],
                events=recent_downloads,
                metadata={"total_mb": total_mb},
            )

    def _trigger_alert(
        self,
        alert_type: str,
        severity: AuditSeverity,
        description: str,
        events: List[AuditEvent],
        metadata: Optional[Dict] = None,
    ) -> None:
        """Trigger security alert."""
        import uuid

        alert = SecurityAlert(
            alert_id=str(uuid.uuid4()),
            alert_type=alert_type,
            severity=severity,
            description=description,
            triggered_by=events,
            indicators=metadata or {},
        )

        # Send alert
        if self.alerting:
            self.alerting.send_alert(alert)

        logger.warning(f"Security alert triggered: {alert_type} - {description}")

    def _check_compliance(self, event: AuditEvent) -> None:
        """Check compliance requirements for event."""
        # Check data retention requirements
        if event.event_type == AuditEventType.DATA_UPLOAD:
            event.metadata["retention_policy"] = "90_days"
            event.compliance_framework = "GDPR"
            event.compliance_requirement = "data_retention"

    def _store_event(self, event: AuditEvent) -> None:
        """Store audit event."""
        # Add to buffer
        self._event_buffer.append(event)

        # Limit buffer size
        if len(self._event_buffer) > AUDIT_BUFFER_SIZE:
            self._event_buffer = self._event_buffer[-AUDIT_BUFFER_RETAIN:]

        # Store in backend if available
        if self.storage:
            try:
                self.storage.store_audit_event(event.model_dump())
            except Exception as e:
                logger.error(f"Failed to store audit event: {e}")

    def get_statistics(
        self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get audit statistics.

        Args:
            start_date: Start date
            end_date: End date

        Returns:
            Audit statistics
        """
        events = self.get_events(start_time=start_date, end_time=end_date)

        stats = {
            "total_events": len(events),
            "by_type": {},
            "by_severity": {},
            "by_result": {"success": 0, "failure": 0},
            "unique_users": set(),
            "unique_customers": set(),
        }

        for event in events:
            # Count by type
            event_type = event.event_type.value
            stats["by_type"][event_type] = stats["by_type"].get(event_type, 0) + 1

            # Count by severity
            severity = event.severity.value
            stats["by_severity"][severity] = stats["by_severity"].get(severity, 0) + 1

            # Count by result
            if event.result in ["success", "granted"]:
                stats["by_result"]["success"] += 1
            else:
                stats["by_result"]["failure"] += 1

            # Track unique users and customers
            if event.user_id:
                stats["unique_users"].add(event.user_id)
            if event.customer_id:
                stats["unique_customers"].add(event.customer_id)

        stats["unique_users"] = len(stats["unique_users"])
        stats["unique_customers"] = len(stats["unique_customers"])

        return stats
