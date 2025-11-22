"""Tests for the reports CLI commands."""

import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner

from paidsearchnav_mcp.cli.main import cli
from paidsearchnav_mcp.storage.models import (
    AnalysisRecord,
    Audit,
    Customer,
    User,
)


@pytest.fixture
def runner():
    """Create a Click test runner."""
    return CliRunner()


@pytest.fixture
def mock_audit():
    """Create a mock audit object."""
    customer = MagicMock(spec=Customer)
    customer.id = "customer-123"
    customer.name = "Test Customer"
    customer.google_ads_customer_id = "1234567890"

    user = MagicMock(spec=User)
    user.id = "user-123"

    audit = MagicMock(spec=Audit)
    audit.id = "audit-123"
    audit.name = "Test Audit"
    audit.status = "completed"
    audit.customer = customer
    audit.customer_id = customer.id
    audit.user = user
    audit.user_id = user.id
    audit.total_recommendations = 42
    audit.critical_issues = 5
    audit.potential_savings = 1500.50
    audit.created_at = datetime.now()
    audit.completed_at = datetime.now()
    audit.to_dict = lambda: {
        "id": audit.id,
        "name": audit.name,
        "status": audit.status,
        "customer_id": audit.customer_id,
        "total_recommendations": audit.total_recommendations,
        "critical_issues": audit.critical_issues,
        "potential_savings": audit.potential_savings,
    }

    return audit


def setup_mock_repo_and_session(
    mock_repo_class, mock_audit=None, mock_analysis_records=None
):
    """Helper to set up mock repository and session."""
    mock_repo = MagicMock()
    mock_repo_class.return_value = mock_repo

    # Create a mock session that properly handles async context manager
    mock_session = MagicMock()
    mock_async_session_context = MagicMock()
    mock_async_session_context.__aenter__ = AsyncMock(return_value=mock_session)
    mock_async_session_context.__aexit__ = AsyncMock(return_value=None)
    mock_repo.AsyncSessionLocal.return_value = mock_async_session_context

    # Mock database queries
    if mock_audit is not None:
        mock_session.get = AsyncMock(return_value=mock_audit)

    if mock_analysis_records is not None:
        # Mock the execute result chain
        mock_scalars = MagicMock()
        mock_scalars.all = MagicMock(return_value=mock_analysis_records)
        mock_execute_result = MagicMock()
        mock_execute_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_execute_result)

    return mock_repo, mock_session


@pytest.fixture
def mock_analysis_records():
    """Create mock analysis records."""
    records = []

    for i, analyzer in enumerate(["search_terms", "keyword_match_types"]):
        record = MagicMock(spec=AnalysisRecord)
        record.id = f"analysis-{i}"
        record.customer_id = "1234567890"
        record.analyzer_name = analyzer
        record.analysis_type = analyzer
        record.start_date = datetime.now() - timedelta(days=30)
        record.end_date = datetime.now()
        record.total_recommendations = 3
        record.critical_issues = 1
        record.potential_cost_savings = 300.0
        record.result_data = {
            "recommendations": [
                {
                    "type": "ADD_NEGATIVE",
                    "priority": "CRITICAL",
                    "title": f"Add '{analyzer} term {j}' as negative keyword",
                    "description": "This term has 0% conversion rate",
                    "estimated_impact": "High",
                    "cost_savings": 100.0 * (j + 1),
                    "keyword": f"{analyzer} term {j}",
                }
                for j in range(3)
            ]
        }
        record.to_dict = lambda r=record: {
            "id": r.id,
            "analyzer_name": r.analyzer_name,
            "result_data": r.result_data,
        }
        records.append(record)

    return records


class TestReportsView:
    """Test the reports view command."""

    @patch("paidsearchnav.cli.reports.AnalysisRepository")
    def test_view_success(
        self, mock_repo_class, runner, mock_audit, mock_analysis_records
    ):
        """Test successful report viewing."""
        # Set up mocks
        setup_mock_repo_and_session(mock_repo_class, mock_audit, mock_analysis_records)

        result = runner.invoke(cli, ["reports", "view", "--audit-id", "audit-123"])

        assert result.exit_code == 0
        assert "Audit Report: Test Audit" in result.output
        assert "Customer: Test Customer" in result.output
        assert "Total Recommendations: 42" in result.output
        assert "Critical Issues: 5" in result.output
        assert "Potential Savings: $1,500.50" in result.output
        assert "search_terms" in result.output
        assert "keyword_match_types" in result.output

    @patch("paidsearchnav.cli.reports.AnalysisRepository")
    def test_view_json_format(
        self, mock_repo_class, runner, mock_audit, mock_analysis_records
    ):
        """Test viewing report in JSON format."""
        # Set up mocks
        mock_repo, mock_session = setup_mock_repo_and_session(mock_repo_class)

        # Mock database queries
        mock_session.get = AsyncMock(return_value=mock_audit)

        # Mock the execute result chain
        mock_scalars = MagicMock()
        mock_scalars.all = MagicMock(return_value=mock_analysis_records)
        mock_execute_result = MagicMock()
        mock_execute_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_execute_result)

        result = runner.invoke(
            cli, ["reports", "view", "--audit-id", "audit-123", "--format", "json"]
        )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["audit"]["id"] == "audit-123"
        assert len(data["analysis_results"]) == 2

    @patch("paidsearchnav.cli.reports.AnalysisRepository")
    def test_view_with_severity_filter(
        self, mock_repo_class, runner, mock_audit, mock_analysis_records
    ):
        """Test viewing report with severity filter."""
        # Set up mocks
        mock_repo, mock_session = setup_mock_repo_and_session(mock_repo_class)

        # Mock database queries
        mock_session.get = AsyncMock(return_value=mock_audit)

        # Mock the execute result chain
        mock_scalars = MagicMock()
        mock_scalars.all = MagicMock(return_value=mock_analysis_records)
        mock_execute_result = MagicMock()
        mock_execute_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_execute_result)

        result = runner.invoke(
            cli,
            ["reports", "view", "--audit-id", "audit-123", "--severity", "critical"],
        )

        assert result.exit_code == 0
        assert "CRIT" in result.output  # Critical priority abbreviated

    @patch("paidsearchnav.cli.reports.AnalysisRepository")
    def test_view_audit_not_found(self, mock_repo_class, runner):
        """Test viewing non-existent audit."""
        # Set up mocks
        mock_repo, mock_session = setup_mock_repo_and_session(mock_repo_class)

        # Mock audit not found
        mock_session.get = AsyncMock(return_value=None)

        result = runner.invoke(cli, ["reports", "view", "--audit-id", "non-existent"])

        assert (
            result.exit_code == 0
        )  # Click doesn't propagate exit codes from async functions
        assert "Error: Audit non-existent not found" in result.output


class TestReportsGenerate:
    """Test the reports generate command."""

    @patch("paidsearchnav.cli.reports.AnalysisRepository")
    @patch("paidsearchnav.cli.reports.ReportGeneratorImpl")
    def test_generate_html_success(
        self,
        mock_generator_class,
        mock_repo_class,
        runner,
        mock_audit,
        mock_analysis_records,
        tmp_path,
    ):
        """Test successful HTML report generation."""
        # Set up mocks
        mock_repo, mock_session = setup_mock_repo_and_session(mock_repo_class)

        # Mock database queries
        mock_session.get = AsyncMock(return_value=mock_audit)

        # Mock the execute result chain
        mock_scalars = MagicMock()
        mock_scalars.all = MagicMock(return_value=mock_analysis_records)
        mock_execute_result = MagicMock()
        mock_execute_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_execute_result)

        # Mock session methods for saving report
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()

        # Mock report generator
        mock_generator = MagicMock()
        mock_generator_class.return_value = mock_generator
        mock_generator.generate.return_value = b"<html>Report content</html>"

        # Generate report
        output_file = tmp_path / "report.html"
        result = runner.invoke(
            cli,
            [
                "reports",
                "generate",
                "--audit-id",
                "audit-123",
                "--format",
                "html",
                "--output",
                str(output_file),
                "--include-summary",
            ],
        )

        assert result.exit_code == 0
        assert "Generating HTML report" in result.output
        assert "Report generated:" in result.output
        assert output_file.exists()
        assert output_file.read_text() == "<html>Report content</html>"

    @patch("paidsearchnav.cli.reports.AnalysisRepository")
    @patch("paidsearchnav.cli.reports.ReportGeneratorImpl")
    def test_generate_pdf_success(
        self,
        mock_generator_class,
        mock_repo_class,
        runner,
        mock_audit,
        mock_analysis_records,
        tmp_path,
    ):
        """Test successful PDF report generation."""
        # Set up mocks
        mock_repo, mock_session = setup_mock_repo_and_session(mock_repo_class)

        # Mock database queries
        mock_session.get = AsyncMock(return_value=mock_audit)

        # Mock the execute result chain
        mock_scalars = MagicMock()
        mock_scalars.all = MagicMock(return_value=mock_analysis_records)
        mock_execute_result = MagicMock()
        mock_execute_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_execute_result)

        # Mock session methods for saving report
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()

        # Mock report generator
        mock_generator = MagicMock()
        mock_generator_class.return_value = mock_generator
        mock_generator.generate.return_value = b"PDF content"

        # Generate report
        output_file = tmp_path / "report.pdf"
        result = runner.invoke(
            cli,
            [
                "reports",
                "generate",
                "--audit-id",
                "audit-123",
                "--format",
                "pdf",
                "--output",
                str(output_file),
            ],
        )

        assert result.exit_code == 0
        assert "Generating PDF report" in result.output
        assert output_file.exists()


class TestReportsExport:
    """Test the reports export command."""

    @patch("paidsearchnav.cli.reports.AnalysisRepository")
    def test_export_csv_success(
        self, mock_repo_class, runner, mock_audit, mock_analysis_records, tmp_path
    ):
        """Test successful CSV export."""
        # Set up mocks
        mock_repo, mock_session = setup_mock_repo_and_session(mock_repo_class)

        # Mock database queries
        mock_session.get = AsyncMock(return_value=mock_audit)

        # Mock the execute result chain
        mock_scalars = MagicMock()
        mock_scalars.all = MagicMock(return_value=mock_analysis_records)
        mock_execute_result = MagicMock()
        mock_execute_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_execute_result)

        # Export data
        output_file = tmp_path / "export.csv"
        result = runner.invoke(
            cli,
            [
                "reports",
                "export",
                "--audit-id",
                "audit-123",
                "--format",
                "csv",
                "--output",
                str(output_file),
            ],
        )

        assert result.exit_code == 0
        assert "Data exported to" in result.output
        assert output_file.exists()

        # Check CSV content
        content = output_file.read_text()
        assert "Analyzer,Priority,Type,Title,Description,Impact,Savings" in content
        assert "search_terms" in content
        assert "keyword_match_types" in content

    @patch("paidsearchnav.cli.reports.AnalysisRepository")
    def test_export_google_ads_editor(
        self, mock_repo_class, runner, mock_audit, mock_analysis_records, tmp_path
    ):
        """Test Google Ads Editor format export."""
        # Set up mocks
        mock_repo, mock_session = setup_mock_repo_and_session(mock_repo_class)

        # Mock database queries
        mock_session.get = AsyncMock(return_value=mock_audit)

        # Mock the execute result chain
        mock_scalars = MagicMock()
        mock_scalars.all = MagicMock(return_value=mock_analysis_records)
        mock_execute_result = MagicMock()
        mock_execute_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_execute_result)

        # Export data
        output_file = tmp_path / "google_ads_editor.csv"
        result = runner.invoke(
            cli,
            [
                "reports",
                "export",
                "--audit-id",
                "audit-123",
                "--format",
                "google_ads_editor",
                "--output",
                str(output_file),
            ],
        )

        assert result.exit_code == 0
        assert "Google Ads Editor file exported" in result.output
        assert output_file.exists()

        # Check Google Ads Editor format
        content = output_file.read_text()
        assert (
            "Action,Campaign,Ad group,Keyword,Match type,Max CPC,Status,Comment"
            in content
        )


class TestReportsCompare:
    """Test the reports compare command."""

    @patch("paidsearchnav.cli.reports.AnalysisRepository")
    def test_compare_success(self, mock_repo_class, runner, mock_audit):
        """Test successful audit comparison."""
        # Create two audits
        audit1 = mock_audit
        audit2 = MagicMock(spec=Audit)
        audit2.id = "audit-456"
        audit2.name = "Test Audit 2"
        audit2.customer = audit1.customer
        audit2.customer_id = audit1.customer_id
        audit2.total_recommendations = 30
        audit2.critical_issues = 2
        audit2.potential_savings = 800.0
        audit2.created_at = datetime.now() + timedelta(days=30)

        # Set up mocks
        mock_repo, mock_session = setup_mock_repo_and_session(mock_repo_class)

        # Mock database queries
        mock_session.get = AsyncMock(side_effect=[audit1, audit2])

        # Mock the execute result chain (empty records)
        mock_scalars = MagicMock()
        mock_scalars.all = MagicMock(return_value=[])
        mock_execute_result = MagicMock()
        mock_execute_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_execute_result)

        result = runner.invoke(
            cli, ["reports", "compare", "--before", "audit-123", "--after", "audit-456"]
        )

        assert result.exit_code == 0
        assert "Audit Comparison" in result.output
        assert "Before: Test Audit" in result.output
        assert "After: Test Audit 2" in result.output
        assert "Metric Changes" in result.output

    @patch("paidsearchnav.cli.reports.AnalysisRepository")
    def test_compare_different_customers(self, mock_repo_class, runner, mock_audit):
        """Test comparison of audits from different customers."""
        # Create two audits with different customers
        audit1 = mock_audit
        audit2 = MagicMock(spec=Audit)
        audit2.customer_id = "different-customer"

        # Set up mocks
        mock_repo, mock_session = setup_mock_repo_and_session(mock_repo_class)

        # Mock database queries
        mock_session.get = AsyncMock(side_effect=[audit1, audit2])

        result = runner.invoke(
            cli, ["reports", "compare", "--before", "audit-123", "--after", "audit-456"]
        )

        assert result.exit_code == 0
        assert "Error: Audits must be for the same customer" in result.output


class TestReportsTrends:
    """Test the reports trends command."""

    @patch("paidsearchnav.cli.reports.AnalysisRepository")
    def test_trends_success(self, mock_repo_class, runner):
        """Test successful trend analysis."""
        # Mock customer
        customer = MagicMock(spec=Customer)
        customer.id = "customer-123"
        customer.name = "Test Customer"
        customer.google_ads_customer_id = "1234567890"

        # Mock audits over time
        audits = []
        for i in range(4):
            audit = MagicMock(spec=Audit)
            audit.created_at = datetime.now() - timedelta(days=30 * (3 - i))
            audit.total_recommendations = 40 - i * 5
            audit.critical_issues = 5 - i
            audit.potential_savings = 1000 - i * 100
            audits.append(audit)

        # Set up mocks
        mock_repo, mock_session = setup_mock_repo_and_session(mock_repo_class)

        # Mock database queries
        # First query returns customer, second query returns audits
        mock_execute_result1 = MagicMock()
        mock_execute_result1.scalar_one_or_none.return_value = customer

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = audits
        mock_execute_result2 = MagicMock()
        mock_execute_result2.scalars.return_value = mock_scalars

        mock_session.execute = AsyncMock(
            side_effect=[mock_execute_result1, mock_execute_result2]
        )

        result = runner.invoke(
            cli, ["reports", "trends", "--customer-id", "1234567890", "--months", "6"]
        )

        assert result.exit_code == 0
        assert "Performance Trends: Test Customer" in result.output
        assert "Audit History" in result.output
        assert "Overall Trend" in result.output
        assert "improvement: Fewer issues found over time" in result.output


class TestReportsQBR:
    """Test the reports qbr command."""

    @patch("paidsearchnav.cli.reports.AnalysisRepository")
    def test_qbr_success(self, mock_repo_class, runner):
        """Test successful QBR generation."""
        # Mock customer
        customer = MagicMock(spec=Customer)
        customer.id = "customer-123"
        customer.name = "Test Customer"
        customer.google_ads_customer_id = "1234567890"

        # Mock audits for Q1
        audits = []
        for i in range(3):
            audit = MagicMock(spec=Audit)
            audit.created_at = datetime(2025, 1 + i, 15)
            audit.name = f"Q1 Audit {i + 1}"
            audit.total_recommendations = 30 + i * 5
            audit.critical_issues = 3 + i
            audit.potential_savings = 500 + i * 100
            audits.append(audit)

        # Set up mocks
        mock_repo, mock_session = setup_mock_repo_and_session(mock_repo_class)

        # Mock database queries
        # First query returns customer
        mock_execute_result1 = MagicMock()
        mock_execute_result1.scalar_one_or_none.return_value = customer

        # Second query returns audits
        mock_scalars1 = MagicMock()
        mock_scalars1.all.return_value = audits
        mock_execute_result2 = MagicMock()
        mock_execute_result2.scalars.return_value = mock_scalars1

        # Third and subsequent queries return empty analysis records
        mock_scalars2 = MagicMock()
        mock_scalars2.all.return_value = []
        mock_execute_result3 = MagicMock()
        mock_execute_result3.scalars.return_value = mock_scalars2

        # Use side_effect to return different results for each call
        mock_session.execute = AsyncMock(
            side_effect=[
                mock_execute_result1,  # customer query
                mock_execute_result2,  # audits query
                mock_execute_result3,  # analysis records query
                mock_execute_result3,  # subsequent analysis records queries
                mock_execute_result3,
            ]
        )

        result = runner.invoke(
            cli,
            ["reports", "qbr", "--customer-id", "1234567890", "--quarter", "Q1-2025"],
        )

        assert result.exit_code == 0
        assert "Quarterly Business Review: Q1-2025" in result.output
        assert "Customer: Test Customer" in result.output
        assert "Total Audits: 3" in result.output
        assert "Quarterly Summary" in result.output
        assert "Audit Timeline" in result.output

    def test_qbr_invalid_quarter_format(self, runner):
        """Test QBR with invalid quarter format."""
        result = runner.invoke(
            cli,
            ["reports", "qbr", "--customer-id", "1234567890", "--quarter", "2025-Q1"],
        )

        assert result.exit_code == 0
        assert "Error: Quarter must be in format Q1-2025" in result.output


class TestReportsBulkGenerate:
    """Test the reports generate-bulk command."""

    @patch("paidsearchnav.cli.reports.AnalysisRepository")
    @patch("paidsearchnav.cli.reports._generate_report")
    def test_bulk_generate_success(self, mock_generate_report, mock_repo_class, runner):
        """Test successful bulk report generation."""
        # Mock customers and audits
        customers = []
        audits = []

        for i in range(2):
            customer = MagicMock(spec=Customer)
            customer.id = f"customer-{i}"
            customer.google_ads_customer_id = f"123456789{i}"
            customers.append(customer)

            audit = MagicMock(spec=Audit)
            audit.id = f"audit-{i}"
            audit.customer_id = customer.id
            audit.status = "completed"
            audit.created_at = datetime.now() - timedelta(days=10)
            audits.append(audit)

        # Set up mocks
        mock_repo, mock_session = setup_mock_repo_and_session(mock_repo_class)

        # Mock database queries
        # Create result objects for each query
        execute_results = []

        # Customer queries
        for customer in customers:
            result = MagicMock()
            result.scalar_one_or_none.return_value = customer
            execute_results.append(result)

        # Audit queries
        for i, audit in enumerate(audits):
            result = MagicMock()
            result.scalar_one_or_none.return_value = audit
            execute_results.append(result)

        mock_session.execute = AsyncMock(side_effect=execute_results)

        # Mock generate_report to succeed
        async def mock_async_func():
            return None

        mock_generate_report.return_value = mock_async_func()

        result = runner.invoke(
            cli,
            [
                "reports",
                "generate-bulk",
                "--customer-ids",
                "1234567890,1234567891",
                "--date-range",
                "last_month",
                "--format",
                "html",
                "--output-dir",
                "/tmp/reports",
            ],
        )

        assert result.exit_code == 0
        assert "Processing customer 1234567890" in result.output
        assert "Processing customer 1234567891" in result.output
