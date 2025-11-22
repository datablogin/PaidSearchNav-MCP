"""Report generator implementation for PaidSearchNav audits."""

import csv
import io
import json
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Flowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from paidsearchnav.core.interfaces import ReportGenerator
from paidsearchnav.core.models import (
    AnalysisResult,
    KeywordMatchAnalysisResult,
    RecommendationPriority,
    SearchTermAnalysisResult,
)


class ReportFormat(str, Enum):
    """Supported report output formats."""

    HTML = "html"
    PDF = "pdf"
    CSV = "csv"
    JSON = "json"


class ReportGeneratorImpl(ReportGenerator):
    """Implementation of the ReportGenerator interface.

    Generates comprehensive audit reports in multiple formats including
    HTML, PDF, CSV, and JSON. Supports white-label customization for agencies.
    """

    def __init__(
        self,
        template_dir: Path | None = None,
        company_name: str = "PaidSearchNav",
        company_logo_path: Path | None = None,
    ):
        """Initialize report generator.

        Args:
            template_dir: Directory containing report templates
            company_name: Company name for white-label reports
            company_logo_path: Path to company logo for branded reports
        """
        self.company_name = company_name
        self.company_logo_path = company_logo_path

        # Set up template directory
        if template_dir is None:
            template_dir = Path(__file__).parent / "templates"
        self.template_dir = template_dir

        # Initialize Jinja2 environment for HTML templates
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            autoescape=select_autoescape(["html", "xml"]),
        )

    def generate(
        self,
        analysis_results: list[AnalysisResult],
        format: str = "html",
        **kwargs: Any,
    ) -> bytes:
        """Generate a report from analysis results.

        Args:
            analysis_results: List of analysis results from various analyzers
            format: Output format (html, pdf, csv, json)
            **kwargs: Additional format-specific options

        Returns:
            Report content as bytes

        Raises:
            ValueError: If format is not supported or inputs are invalid
        """
        # Input validation
        if not isinstance(analysis_results, list):
            raise ValueError("analysis_results must be a list")

        if not all(isinstance(result, AnalysisResult) for result in analysis_results):
            raise ValueError(
                "All items in analysis_results must be AnalysisResult instances"
            )

        if format not in self.get_supported_formats():
            raise ValueError(f"Unsupported format: {format}")

        # Route to appropriate generator method
        if format == ReportFormat.HTML:
            return self._generate_html(analysis_results, **kwargs)
        elif format == ReportFormat.PDF:
            return self._generate_pdf(analysis_results, **kwargs)
        elif format == ReportFormat.CSV:
            return self._generate_csv(analysis_results, **kwargs)
        elif format == ReportFormat.JSON:
            return self._generate_json(analysis_results, **kwargs)
        else:
            raise ValueError(f"Unsupported format: {format}")

    def get_supported_formats(self) -> list[str]:
        """Get list of supported output formats."""
        return [f.value for f in ReportFormat]

    def _generate_html(
        self, analysis_results: list[AnalysisResult], **kwargs: Any
    ) -> bytes:
        """Generate HTML report.

        Kwargs:
            include_sections: List of sections to include. Defaults to all.
                Options: 'executive_summary', 'metrics', 'recommendations', 'analyzer_details'
            exclude_sections: List of sections to exclude. Takes precedence over include_sections.
        """
        # Prepare report data
        report_data = self._prepare_report_data(analysis_results)

        # Handle section inclusion/exclusion
        default_sections = {
            "executive_summary",
            "metrics",
            "recommendations",
            "analyzer_details",
        }
        include_sections = set(kwargs.get("include_sections", default_sections))
        exclude_sections = set(kwargs.get("exclude_sections", []))
        active_sections = include_sections - exclude_sections

        # Add section flags to report data
        report_data["show_executive_summary"] = "executive_summary" in active_sections
        report_data["show_metrics"] = "metrics" in active_sections
        report_data["show_recommendations"] = "recommendations" in active_sections
        report_data["show_analyzer_details"] = "analyzer_details" in active_sections

        # Add company branding
        report_data["company_name"] = self.company_name
        report_data["generated_at"] = datetime.now().strftime("%B %d, %Y at %I:%M %p")

        # Check if template exists
        template_path = self.template_dir / "audit_report.html"
        if not template_path.exists():
            raise FileNotFoundError(
                f"HTML template not found at {template_path}. "
                "Please ensure the template directory contains 'audit_report.html'"
            )

        # Render template
        template = self.jinja_env.get_template("audit_report.html")
        html_content = template.render(**report_data)

        return html_content.encode("utf-8")

    def _generate_pdf(
        self, analysis_results: list[AnalysisResult], **kwargs: Any
    ) -> bytes:
        """Generate PDF report.

        Raises:
            RuntimeError: If PDF generation fails
        """
        try:
            # Prepare report data
            report_data = self._prepare_report_data(analysis_results)

            # Create PDF in memory
            buffer = io.BytesIO()
            doc = SimpleDocTemplate(
                buffer,
                pagesize=letter,
                rightMargin=72,
                leftMargin=72,
                topMargin=72,
                bottomMargin=18,
            )

            # Build story (PDF content)
            story: list[Flowable] = []
            styles = getSampleStyleSheet()

            # Add custom styles
            styles.add(
                ParagraphStyle(
                    name="CustomTitle",
                    parent=styles["Heading1"],
                    fontSize=24,
                    textColor=colors.HexColor("#1a73e8"),
                    spaceAfter=30,
                    alignment=TA_CENTER,
                )
            )

            # Title
            story.append(
                Paragraph(
                    f"{self.company_name} Google Ads Audit Report",
                    styles["CustomTitle"],
                )
            )
            story.append(Spacer(1, 0.2 * inch))

            # Executive Summary
            story.append(Paragraph("Executive Summary", styles["Heading1"]))
            story.append(
                Paragraph(report_data["executive_summary"], styles["BodyText"])
            )
            story.append(Spacer(1, 0.3 * inch))

            # Key Metrics
            story.append(Paragraph("Key Metrics", styles["Heading1"]))
            metrics_data = [
                ["Metric", "Value"],
                ["Total Recommendations", str(report_data["total_recommendations"])],
                ["Critical Issues", str(report_data["critical_issues"])],
                ["Potential Monthly Savings", f"${report_data['total_savings']:,.2f}"],
                ["Analyzers Run", str(len(analysis_results))],
            ]

            metrics_table = Table(metrics_data, colWidths=[3 * inch, 2 * inch])
            metrics_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, 0), 14),
                        ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                        ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                        ("GRID", (0, 0), (-1, -1), 1, colors.black),
                    ]
                )
            )
            story.append(metrics_table)
            story.append(PageBreak())

            # Recommendations by Priority
            story.append(Paragraph("Recommendations by Priority", styles["Heading1"]))

            for priority in ["critical", "high", "medium", "low"]:
                if report_data[f"{priority}_recommendations"]:
                    story.append(
                        Paragraph(f"{priority.title()} Priority", styles["Heading2"])
                    )
                    for rec in report_data[f"{priority}_recommendations"][
                        :5
                    ]:  # Top 5 per priority
                        story.append(Paragraph(f"• {rec['title']}", styles["BodyText"]))
                        story.append(
                            Paragraph(f"  {rec['description']}", styles["Normal"])
                        )
                        if rec.get("estimated_impact"):
                            story.append(
                                Paragraph(
                                    f"  Impact: {rec['estimated_impact']}",
                                    styles["Italic"],
                                )
                            )
                        story.append(Spacer(1, 0.1 * inch))

            # Build PDF
            doc.build(story)
            buffer.seek(0)
            return buffer.read()
        except Exception as e:
            raise RuntimeError(f"Failed to generate PDF report: {str(e)}") from e

    def _generate_csv(
        self, analysis_results: list[AnalysisResult], **kwargs: Any
    ) -> bytes:
        """Generate CSV report with recommendations."""
        output = io.StringIO()

        # Define CSV columns
        fieldnames = [
            "Analyzer",
            "Priority",
            "Type",
            "Title",
            "Description",
            "Estimated Impact",
            "Monthly Savings",
            "Customer ID",
            "Date Range",
        ]

        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        # Write recommendations from all analyzers
        for result in analysis_results:
            for rec in result.recommendations:
                writer.writerow(
                    {
                        "Analyzer": result.analyzer_name,
                        "Priority": rec.priority
                        if isinstance(rec.priority, str)
                        else rec.priority.value,
                        "Type": rec.type
                        if isinstance(rec.type, str)
                        else rec.type.value,
                        "Title": rec.title,
                        "Description": rec.description,
                        "Estimated Impact": rec.estimated_impact or "",
                        "Monthly Savings": f"${rec.estimated_cost_savings:.2f}"
                        if rec.estimated_cost_savings
                        else "",
                        "Customer ID": result.customer_id,
                        "Date Range": f"{result.start_date} to {result.end_date}",
                    }
                )

        # Add summary metrics if requested
        if kwargs.get("include_summary", True):
            output.write("\n\nSummary Metrics\n")
            output.write("Metric,Value\n")

            report_data = self._prepare_report_data(analysis_results)
            output.write(
                f"Total Recommendations,{report_data['total_recommendations']}\n"
            )
            output.write(f"Critical Issues,{report_data['critical_issues']}\n")
            output.write(
                f"Potential Monthly Savings,${report_data['total_savings']:.2f}\n"
            )

        return output.getvalue().encode("utf-8")

    def _generate_json(
        self, analysis_results: list[AnalysisResult], **kwargs: Any
    ) -> bytes:
        """Generate JSON report."""
        report_data = self._prepare_report_data(analysis_results)

        # Convert to JSON-serializable format
        json_data: dict[str, Any] = {
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "company_name": self.company_name,
                "analyzer_count": len(analysis_results),
            },
            "summary": {
                "executive_summary": report_data["executive_summary"],
                "total_recommendations": report_data["total_recommendations"],
                "critical_issues": report_data["critical_issues"],
                "total_savings": report_data["total_savings"],
            },
            "recommendations": {
                "critical": report_data["critical_recommendations"],
                "high": report_data["high_recommendations"],
                "medium": report_data["medium_recommendations"],
                "low": report_data["low_recommendations"],
            },
            "analyzer_results": [],
        }

        # Add detailed analyzer results
        for result in analysis_results:
            analyzer_data = {
                "analyzer_name": result.analyzer_name,
                "customer_id": result.customer_id,
                "date_range": {
                    "start": str(result.start_date),
                    "end": str(result.end_date),
                },
                "summary": {},
            }

            # Use to_summary_dict if available
            if hasattr(result, "to_summary_dict"):
                analyzer_data["summary"] = result.to_summary_dict()
            else:
                # Fallback to basic summary
                analyzer_data["summary"] = {
                    "recommendation_count": len(result.recommendations),
                    "metrics": result.metrics.model_dump() if result.metrics else {},
                }

            json_data["analyzer_results"].append(analyzer_data)

        # Pretty print JSON
        json_str = json.dumps(json_data, indent=2, default=str)
        return json_str.encode("utf-8")

    def _prepare_report_data(
        self, analysis_results: list[AnalysisResult]
    ) -> dict[str, Any]:
        """Prepare consolidated report data from analysis results."""
        # Initialize report data structure
        report_data: dict[str, Any] = {
            "analysis_results": analysis_results,
            "total_recommendations": 0,
            "critical_issues": 0,
            "total_savings": 0.0,
            "critical_recommendations": [],
            "high_recommendations": [],
            "medium_recommendations": [],
            "low_recommendations": [],
            "executive_summary": "",
            "analyzer_summaries": {},
        }

        # Process each analysis result
        for result in analysis_results:
            # Count recommendations
            report_data["total_recommendations"] += len(result.recommendations)

            # Categorize recommendations by priority
            for rec in result.recommendations:
                rec_dict = {
                    "analyzer": result.analyzer_name,
                    "type": rec.type if isinstance(rec.type, str) else rec.type.value,
                    "title": rec.title,
                    "description": rec.description,
                    "estimated_impact": rec.estimated_impact,
                    "cost_savings": rec.estimated_cost_savings,
                }

                if rec.priority == RecommendationPriority.CRITICAL:
                    report_data["critical_issues"] += 1
                    report_data["critical_recommendations"].append(rec_dict)
                elif rec.priority == RecommendationPriority.HIGH:
                    report_data["high_recommendations"].append(rec_dict)
                elif rec.priority == RecommendationPriority.MEDIUM:
                    report_data["medium_recommendations"].append(rec_dict)
                else:
                    report_data["low_recommendations"].append(rec_dict)

                # Sum up savings
                if rec.estimated_cost_savings:
                    report_data["total_savings"] += rec.estimated_cost_savings

            # Get analyzer-specific summaries
            if hasattr(result, "to_summary_dict"):
                report_data["analyzer_summaries"][result.analyzer_name] = (
                    result.to_summary_dict()
                )

            # Add specialized data for certain result types
            if isinstance(result, SearchTermAnalysisResult):
                if result.potential_savings:
                    report_data["total_savings"] += result.potential_savings
            elif isinstance(result, KeywordMatchAnalysisResult):
                if result.potential_savings:
                    report_data["total_savings"] += result.potential_savings

        # Generate executive summary
        report_data["executive_summary"] = self._generate_executive_summary(report_data)

        return report_data

    def _generate_executive_summary(self, report_data: dict[str, Any]) -> str:
        """Generate executive summary text."""
        summary_parts = []

        # Overview
        summary_parts.append(
            f"This Google Ads audit analyzed {len(report_data['analysis_results'])} areas of your account "
            f"and identified {report_data['total_recommendations']} optimization opportunities."
        )

        # Critical issues
        if report_data["critical_issues"] > 0:
            summary_parts.append(
                f"We found {report_data['critical_issues']} critical issues that require immediate attention "
                f"to prevent wasted spend and improve campaign performance."
            )

        # Savings potential
        if report_data["total_savings"] > 0:
            summary_parts.append(
                f"By implementing our recommendations, you could save approximately "
                f"${report_data['total_savings']:,.2f} per month in wasted ad spend."
            )

        # Top findings
        if report_data["critical_recommendations"]:
            summary_parts.append(
                "The most important findings include: "
                + ", ".join(
                    [
                        rec["title"]
                        for rec in report_data["critical_recommendations"][:3]
                    ]
                )
                + "."
            )

        return " ".join(summary_parts)
