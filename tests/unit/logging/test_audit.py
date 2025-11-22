"""Tests for audit logging functionality."""

import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from paidsearchnav_mcp.models.analysis import (
    AnalysisMetrics,
    AnalysisResult,
    Recommendation,
    RecommendationPriority,
    RecommendationType,
)
from paidsearchnav_mcp.logging.audit import AuditLogger, get_audit_logger


class TestAuditLogger:
    """Test AuditLogger class."""

    def setup_method(self):
        """Set up test method."""
        self.temp_dir = tempfile.mkdtemp()
        self.audit_logger = AuditLogger(audit_dir=Path(self.temp_dir))

    def teardown_method(self):
        """Clean up test method."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_log_analysis_start(self):
        """Test logging analysis start."""
        self.audit_logger.log_analysis_start(
            customer_id="123",
            analysis_type="keyword_match",
            job_id="job-001",
            config={"param": "value"},
        )

        # Check log file exists
        log_file = Path(self.temp_dir) / "123" / "job-001.jsonl"
        assert log_file.exists()

        # Check content
        with open(log_file) as f:
            entry = json.loads(f.readline())
            assert entry["event"] == "analysis_started"
            assert entry["customer_id"] == "123"
            assert entry["analysis_type"] == "keyword_match"
            assert entry["job_id"] == "job-001"
            assert entry["config"] == {"param": "value"}

    def test_log_analysis_complete(self):
        """Test logging analysis completion."""
        result = AnalysisResult(
            customer_id="123",
            analysis_type="keyword_match",
            analyzer_name="KeywordMatchAnalyzer",
            start_date=datetime.now(timezone.utc) - timedelta(days=30),
            end_date=datetime.now(timezone.utc),
            analysis_id="analysis-001",
            metrics=AnalysisMetrics(
                critical_issues=5,
                potential_cost_savings=500.0,
            ),
            recommendations=[
                Recommendation(
                    type=RecommendationType.PAUSE_KEYWORD,
                    priority=RecommendationPriority.HIGH,
                    title="Pause low performers",
                    description="Test",
                ),
            ],
        )

        self.audit_logger.log_analysis_complete(
            customer_id="123",
            analysis_type="keyword_match",
            job_id="job-001",
            result=result,
            duration_seconds=120.5,
        )

        # Check audit log
        log_file = Path(self.temp_dir) / "123" / "job-001.jsonl"
        with open(log_file) as f:
            # Skip to completion entry
            for line in f:
                entry = json.loads(line)
                if entry["event"] == "analysis_completed":
                    assert entry["duration_seconds"] == 120.5
                    assert entry["result_summary"]["total_recommendations"] == 1
                    assert entry["result_summary"]["critical_issues"] == 5
                    break

        # Check result file
        result_file = Path(self.temp_dir) / "123" / "results" / "job-001_result.json"
        assert result_file.exists()

    def test_log_analysis_failed(self):
        """Test logging analysis failure."""
        error = ValueError("Test error")

        self.audit_logger.log_analysis_failed(
            customer_id="123",
            analysis_type="keyword_match",
            job_id="job-001",
            error=error,
            duration_seconds=30.0,
        )

        # Check log file
        log_file = Path(self.temp_dir) / "123" / "job-001.jsonl"
        with open(log_file) as f:
            entry = json.loads(f.readline())
            assert entry["event"] == "analysis_failed"
            assert entry["duration_seconds"] == 30.0
            assert entry["error"]["type"] == "ValueError"
            assert entry["error"]["message"] == "Test error"

    def test_log_api_call(self):
        """Test logging API calls."""
        self.audit_logger.log_api_call(
            customer_id="123",
            service="google_ads",
            method="POST",
            endpoint="/v14/customers/123/googleAds:search",
            status_code=200,
            duration_ms=250.5,
        )

        # Check log file
        log_file = (
            Path(self.temp_dir) / "api_calls" / f"{datetime.now():%Y-%m-%d}.jsonl"
        )
        assert log_file.exists()

        with open(log_file) as f:
            entry = json.loads(f.readline())
            assert entry["event"] == "api_call"
            assert entry["customer_id"] == "123"
            assert entry["service"] == "google_ads"
            assert entry["method"] == "POST"
            assert entry["status_code"] == 200
            assert entry["duration_ms"] == 250.5

    def test_search_audits_basic(self):
        """Test basic audit search."""
        # Create some test entries
        self.audit_logger.log_analysis_start(
            customer_id="123",
            analysis_type="keyword_match",
            job_id="job-001",
            config={},
        )
        self.audit_logger.log_analysis_complete(
            customer_id="123",
            analysis_type="keyword_match",
            job_id="job-001",
            result=self._create_test_result(),
            duration_seconds=60,
        )

        # Search all
        results = self.audit_logger.search_audits()
        assert len(results) == 2

        # Search by customer
        results = self.audit_logger.search_audits(customer_id="123")
        assert len(results) == 2

        # Search by type
        results = self.audit_logger.search_audits(analysis_type="keyword_match")
        assert len(results) == 2

        # Search non-existent
        results = self.audit_logger.search_audits(customer_id="999")
        assert len(results) == 0

    def test_search_audits_by_status(self):
        """Test searching audits by status."""
        # Create completed and failed entries
        self.audit_logger.log_analysis_complete(
            customer_id="123",
            analysis_type="test",
            job_id="job-001",
            result=self._create_test_result(),
            duration_seconds=60,
        )
        self.audit_logger.log_analysis_failed(
            customer_id="123",
            analysis_type="test",
            job_id="job-002",
            error=Exception("Failed"),
            duration_seconds=30,
        )

        # Search completed
        results = self.audit_logger.search_audits(status="completed")
        assert len(results) == 1
        assert results[0]["job_id"] == "job-001"

        # Search failed
        results = self.audit_logger.search_audits(status="failed")
        assert len(results) == 1
        assert results[0]["job_id"] == "job-002"

    def test_search_audits_by_date(self):
        """Test searching audits by date range."""
        # Create entry
        self.audit_logger.log_analysis_start(
            customer_id="123",
            analysis_type="test",
            job_id="job-001",
            config={},
        )

        # Search with date range
        results = self.audit_logger.search_audits(
            start_date=datetime.now(timezone.utc) - timedelta(hours=1),
            end_date=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        assert len(results) == 1

        # Search outside range
        results = self.audit_logger.search_audits(
            end_date=datetime.now(timezone.utc) - timedelta(days=1),
        )
        assert len(results) == 0

    def _create_test_result(self) -> AnalysisResult:
        """Create a test analysis result."""
        return AnalysisResult(
            customer_id="123",
            analysis_type="test",
            analyzer_name="TestAnalyzer",
            start_date=datetime.now(timezone.utc) - timedelta(days=30),
            end_date=datetime.now(timezone.utc),
            metrics=AnalysisMetrics(),
        )


class TestGetAuditLogger:
    """Test get_audit_logger function."""

    def test_get_audit_logger(self):
        """Test getting global audit logger."""
        # Mock the audit directory to avoid permission issues
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("paidsearchnav.logging.audit.Path") as mock_path:
                mock_path.return_value = Path(tmpdir)

                logger1 = get_audit_logger()
                logger2 = get_audit_logger()

                # Should return same instance
                assert logger1 is logger2
                assert isinstance(logger1, AuditLogger)
