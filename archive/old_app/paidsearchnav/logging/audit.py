"""Audit logging functionality for capturing job outputs."""

import json
import os
import platform
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from paidsearchnav.core.models.analysis import AnalysisResult
from paidsearchnav.logging.config import get_logger

logger = get_logger(__name__)


class AuditLogger:
    """Logger for capturing audit job outputs."""

    def __init__(
        self,
        audit_dir: Path | None = None,
        log_file_permissions: int = 0o600,
        log_dir_permissions: int = 0o700,
    ):
        """Initialize audit logger.

        Args:
            audit_dir: Directory to store audit logs
            log_file_permissions: Permissions for log files (default: 0o600 - owner read/write only)
            log_dir_permissions: Permissions for log directories (default: 0o700 - owner only)
        """
        self.audit_dir = audit_dir or Path("/var/log/paidsearchnav/audits")
        self.log_file_permissions = log_file_permissions
        self.log_dir_permissions = log_dir_permissions

        # Create audit directory with secure permissions
        self._create_secure_directory(self.audit_dir)

    def log_analysis_start(
        self,
        customer_id: str,
        analysis_type: str,
        job_id: str,
        config: dict[str, Any],
    ) -> None:
        """Log the start of an analysis job.

        Args:
            customer_id: Customer ID
            analysis_type: Type of analysis
            job_id: Unique job ID
            config: Job configuration
        """
        audit_entry = {
            "event": "analysis_started",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "customer_id": customer_id,
            "analysis_type": analysis_type,
            "job_id": job_id,
            "config": config,
        }

        self._write_audit_log(customer_id, job_id, audit_entry)

        logger.info(
            "Analysis started",
            extra={
                "customer_id": customer_id,
                "analysis_type": analysis_type,
                "job_id": job_id,
            },
        )

    def log_analysis_complete(
        self,
        customer_id: str,
        analysis_type: str,
        job_id: str,
        result: AnalysisResult,
        duration_seconds: float,
    ) -> None:
        """Log the completion of an analysis job.

        Args:
            customer_id: Customer ID
            analysis_type: Type of analysis
            job_id: Unique job ID
            result: Analysis result
            duration_seconds: Job duration
        """
        audit_entry = {
            "event": "analysis_completed",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "customer_id": customer_id,
            "analysis_type": analysis_type,
            "job_id": job_id,
            "duration_seconds": duration_seconds,
            "result_summary": {
                "total_recommendations": result.total_recommendations,
                "critical_issues": result.metrics.critical_issues
                if result.metrics
                else 0,
                "potential_cost_savings": result.metrics.potential_cost_savings
                if result.metrics
                else 0,
                "analysis_id": result.analysis_id,
            },
        }

        self._write_audit_log(customer_id, job_id, audit_entry)

        # Also save full result
        self._save_analysis_result(customer_id, job_id, result)

        logger.info(
            "Analysis completed",
            extra={
                "customer_id": customer_id,
                "analysis_type": analysis_type,
                "job_id": job_id,
                "duration_seconds": duration_seconds,
                "total_recommendations": result.total_recommendations,
            },
        )

    def log_analysis_failed(
        self,
        customer_id: str,
        analysis_type: str,
        job_id: str,
        error: Exception,
        duration_seconds: float,
    ) -> None:
        """Log a failed analysis job.

        Args:
            customer_id: Customer ID
            analysis_type: Type of analysis
            job_id: Unique job ID
            error: Exception that caused failure
            duration_seconds: Job duration before failure
        """
        audit_entry = {
            "event": "analysis_failed",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "customer_id": customer_id,
            "analysis_type": analysis_type,
            "job_id": job_id,
            "duration_seconds": duration_seconds,
            "error": {
                "type": type(error).__name__,
                "message": str(error),
            },
        }

        self._write_audit_log(customer_id, job_id, audit_entry)

        logger.error(
            "Analysis failed",
            extra={
                "customer_id": customer_id,
                "analysis_type": analysis_type,
                "job_id": job_id,
                "duration_seconds": duration_seconds,
                "error_type": type(error).__name__,
            },
            exc_info=error,
        )

    def log_api_call(
        self,
        customer_id: str,
        service: str,
        method: str,
        endpoint: str,
        status_code: int | None = None,
        duration_ms: float | None = None,
        error: str | None = None,
    ) -> None:
        """Log an API call for audit purposes.

        Args:
            customer_id: Customer ID
            service: Service name (e.g., "google_ads")
            method: HTTP method
            endpoint: API endpoint
            status_code: Response status code
            duration_ms: Request duration in milliseconds
            error: Error message if failed
        """
        audit_entry = {
            "event": "api_call",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "customer_id": customer_id,
            "service": service,
            "method": method,
            "endpoint": endpoint,
            "status_code": status_code,
            "duration_ms": duration_ms,
            "error": error,
        }

        # Use date-based log file for API calls
        log_file = (
            self.audit_dir
            / "api_calls"
            / f"{datetime.now(timezone.utc):%Y-%m-%d}.jsonl"
        )

        # Write to file with secure permissions
        self._create_secure_file(log_file, json.dumps(audit_entry) + "\n")

        logger.debug(
            f"API call: {method} {endpoint}",
            extra={
                "customer_id": customer_id,
                "service": service,
                "status_code": status_code,
                "duration_ms": duration_ms,
            },
        )

    def _write_audit_log(
        self, customer_id: str, job_id: str, entry: dict[str, Any]
    ) -> None:
        """Write an audit log entry.

        Args:
            customer_id: Customer ID
            job_id: Job ID
            entry: Log entry data
        """
        # Create customer-specific directory with secure permissions
        customer_dir = self.audit_dir / customer_id
        self._create_secure_directory(customer_dir)

        # Write to job-specific log file with secure permissions
        log_file = customer_dir / f"{job_id}.jsonl"
        self._create_secure_file(log_file, json.dumps(entry) + "\n")

    def _save_analysis_result(
        self, customer_id: str, job_id: str, result: AnalysisResult
    ) -> None:
        """Save full analysis result.

        Args:
            customer_id: Customer ID
            job_id: Job ID
            result: Analysis result
        """
        # Create results directory with secure permissions
        results_dir = self.audit_dir / customer_id / "results"
        self._create_secure_directory(results_dir)

        # Save result as JSON with secure permissions
        result_file = results_dir / f"{job_id}_result.json"
        content = json.dumps(result.model_dump(mode="json"), indent=2)

        # Use write mode for full file replacement
        result_file.parent.mkdir(parents=True, exist_ok=True)
        with open(result_file, "w") as f:
            f.write(content)

        # Apply secure permissions
        self._apply_secure_permissions(result_file, self.log_file_permissions)

    def search_audits(
        self,
        customer_id: str | None = None,
        analysis_type: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search audit logs.

        Args:
            customer_id: Filter by customer ID
            analysis_type: Filter by analysis type
            start_date: Filter by start date
            end_date: Filter by end date
            status: Filter by status (completed, failed)

        Returns:
            List of matching audit entries
        """
        results = []

        # Determine which directories to search
        if customer_id:
            search_dirs = [self.audit_dir / customer_id]
        else:
            search_dirs = [
                d
                for d in self.audit_dir.iterdir()
                if d.is_dir() and d.name != "api_calls"
            ]

        for customer_dir in search_dirs:
            for log_file in customer_dir.glob("*.jsonl"):
                if log_file.name.startswith("results"):
                    continue

                with open(log_file) as f:
                    for line in f:
                        try:
                            entry = json.loads(line)

                            # Apply filters
                            if (
                                analysis_type
                                and entry.get("analysis_type") != analysis_type
                            ):
                                continue

                            if start_date:
                                entry_time = datetime.fromisoformat(entry["timestamp"])
                                if entry_time < start_date:
                                    continue

                            if end_date:
                                entry_time = datetime.fromisoformat(entry["timestamp"])
                                if entry_time > end_date:
                                    continue

                            if status:
                                if (
                                    status == "completed"
                                    and entry["event"] != "analysis_completed"
                                ):
                                    continue
                                elif (
                                    status == "failed"
                                    and entry["event"] != "analysis_failed"
                                ):
                                    continue

                            results.append(entry)

                        except (json.JSONDecodeError, KeyError):
                            continue

        # Sort by timestamp
        results.sort(key=lambda x: x["timestamp"], reverse=True)

        return results

    def _create_secure_directory(self, path: Path) -> None:
        """Create a directory with secure permissions.

        Args:
            path: Directory path to create
        """
        if not path.exists():
            # Create directory with secure permissions
            path.mkdir(parents=True, exist_ok=True)
            self._apply_secure_permissions(path, self.log_dir_permissions)
        elif not path.is_dir():
            raise ValueError(f"{path} exists but is not a directory")
        else:
            # Check and fix permissions on existing directory
            self._apply_secure_permissions(path, self.log_dir_permissions)

    def _create_secure_file(self, path: Path, content: str) -> None:
        """Create or append to a file with secure permissions.

        Args:
            path: File path
            content: Content to write
        """
        # Ensure parent directory exists with secure permissions
        self._create_secure_directory(path.parent)

        # Check if file needs to be created
        file_exists = path.exists()

        # Write content
        with open(path, "a") as f:
            f.write(content)

        # Apply secure permissions
        self._apply_secure_permissions(path, self.log_file_permissions)

    def _apply_secure_permissions(self, path: Path, permissions: int) -> None:
        """Apply file permissions with platform compatibility.

        Args:
            path: Path to file or directory
            permissions: Octal permissions to apply
        """
        if platform.system() == "Windows":
            # Windows has a different permission model
            # Skip detailed permission setting on Windows
            return

        try:
            # Only set permissions if they differ from expected
            current_perms = path.stat().st_mode & 0o777
            if current_perms != permissions:
                os.chmod(path, permissions)
        except (OSError, PermissionError) as e:
            # Log warning but continue - permission setting is best effort
            logger.warning(f"Could not set permissions on {path}: {e}")


# Global audit logger instance
_audit_logger: AuditLogger | None = None


def get_audit_logger(
    log_file_permissions: int = 0o600, log_dir_permissions: int = 0o700
) -> AuditLogger:
    """Get the global audit logger instance.

    Args:
        log_file_permissions: Permissions for log files (default: 0o600)
        log_dir_permissions: Permissions for log directories (default: 0o700)

    Returns:
        AuditLogger instance
    """
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger(
            log_file_permissions=log_file_permissions,
            log_dir_permissions=log_dir_permissions,
        )
    return _audit_logger
