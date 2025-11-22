"""Async report generator implementation for PaidSearchNav audits."""

import asyncio
import html
import io
import json
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncIterator

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

from paidsearchnav.core.models import (
    AnalysisResult,
    KeywordMatchAnalysisResult,
    RecommendationPriority,
    SearchTermAnalysisResult,
)
from paidsearchnav.reports.generator import ReportFormat, ReportGeneratorImpl


class AsyncReportGenerator(ReportGeneratorImpl):
    """Async-enabled report generator for better performance with large datasets.

    Extends the base ReportGeneratorImpl to provide async versions of all
    generation methods while maintaining backward compatibility.
    """

    def __init__(
        self,
        template_dir: Path | None = None,
        company_name: str = "PaidSearchNav",
        company_logo_path: Path | None = None,
        max_concurrent_sections: int = 4,
    ):
        """Initialize async report generator.

        Args:
            template_dir: Directory containing report templates
            company_name: Company name for white-label reports
            company_logo_path: Path to company logo for branded reports
            max_concurrent_sections: Maximum number of report sections to process concurrently (1-50)

        Raises:
            ValueError: If max_concurrent_sections is out of valid range
        """
        super().__init__(template_dir, company_name, company_logo_path)

        # Validate and set concurrent sections limit
        if max_concurrent_sections < 1:
            raise ValueError("max_concurrent_sections must be at least 1")
        if max_concurrent_sections > 50:
            raise ValueError("max_concurrent_sections must not exceed 50")

        self.max_concurrent_sections = max_concurrent_sections
        self._semaphore = asyncio.Semaphore(max_concurrent_sections)

    async def generate_async(
        self,
        analysis_results: list[AnalysisResult],
        format: str = "html",
        **kwargs: Any,
    ) -> bytes:
        """Asynchronously generate a report from analysis results.

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

        # Route to appropriate async generator method
        if format == ReportFormat.HTML:
            return await self._generate_html_async(analysis_results, **kwargs)
        elif format == ReportFormat.PDF:
            return await self._generate_pdf_async(analysis_results, **kwargs)
        elif format == ReportFormat.CSV:
            return await self._generate_csv_async(analysis_results, **kwargs)
        elif format == ReportFormat.JSON:
            return await self._generate_json_async(analysis_results, **kwargs)
        else:
            raise ValueError(f"Unsupported format: {format}")

    async def _generate_html_async(
        self, analysis_results: list[AnalysisResult], **kwargs: Any
    ) -> bytes:
        """Asynchronously generate HTML report.

        Processes report sections concurrently for better performance.
        """
        # Prepare report data concurrently
        report_data = await self._prepare_report_data_async(analysis_results)

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

        # Render template asynchronously
        template = self.jinja_env.get_template("audit_report.html")

        # Use asyncio to run template rendering in executor to avoid blocking
        loop = asyncio.get_event_loop()
        html_content = await loop.run_in_executor(None, template.render, report_data)

        return html_content.encode("utf-8")

    async def _generate_pdf_async(
        self, analysis_results: list[AnalysisResult], **kwargs: Any
    ) -> bytes:
        """Asynchronously generate PDF report.

        Processes PDF sections concurrently for better performance.
        """
        try:
            # Prepare report data concurrently
            report_data = await self._prepare_report_data_async(analysis_results)

            # Run PDF generation in executor to avoid blocking
            loop = asyncio.get_event_loop()
            pdf_bytes = await loop.run_in_executor(
                None, self._generate_pdf_content, report_data, analysis_results
            )

            return pdf_bytes
        except Exception as e:
            raise RuntimeError(f"Failed to generate PDF report: {str(e)}") from e

    def _generate_pdf_content(
        self, report_data: dict[str, Any], analysis_results: list[AnalysisResult]
    ) -> bytes:
        """Generate PDF content synchronously (called in executor)."""
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
        story.append(Paragraph(report_data["executive_summary"], styles["BodyText"]))
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
                    story.append(Paragraph(f"  {rec['description']}", styles["Normal"]))
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

    async def _generate_csv_async(
        self, analysis_results: list[AnalysisResult], **kwargs: Any
    ) -> bytes:
        """Asynchronously generate CSV report."""
        # Process recommendations concurrently
        loop = asyncio.get_event_loop()
        csv_content = await loop.run_in_executor(
            None, self._generate_csv, analysis_results, **kwargs
        )
        return csv_content

    async def _generate_json_async(
        self, analysis_results: list[AnalysisResult], **kwargs: Any
    ) -> bytes:
        """Asynchronously generate JSON report."""
        # Prepare report data concurrently
        report_data = await self._prepare_report_data_async(analysis_results)

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

        # Process analyzer results concurrently
        analyzer_tasks = []
        for result in analysis_results:
            task = self._process_analyzer_result_async(result)
            analyzer_tasks.append(task)

        analyzer_results = await asyncio.gather(*analyzer_tasks)
        json_data["analyzer_results"] = analyzer_results

        # Pretty print JSON
        json_str = json.dumps(json_data, indent=2, default=str)
        return json_str.encode("utf-8")

    async def _process_analyzer_result_async(
        self, result: AnalysisResult
    ) -> dict[str, Any]:
        """Process a single analyzer result asynchronously."""
        async with self._semaphore:  # Limit concurrent processing
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

            return analyzer_data

    async def _prepare_report_data_async(
        self, analysis_results: list[AnalysisResult]
    ) -> dict[str, Any]:
        """Asynchronously prepare consolidated report data from analysis results."""
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

        # Process each analysis result concurrently and collect individual results
        tasks = []
        for result in analysis_results:
            task = self._process_analysis_result_async(result)
            tasks.append(task)

        # Gather all individual results
        individual_results = await asyncio.gather(*tasks)

        # Merge results in a thread-safe manner
        for result_data in individual_results:
            report_data["total_recommendations"] += result_data["total_recommendations"]
            report_data["critical_issues"] += result_data["critical_issues"]
            report_data["total_savings"] += result_data["total_savings"]
            report_data["critical_recommendations"].extend(
                result_data["critical_recommendations"]
            )
            report_data["high_recommendations"].extend(
                result_data["high_recommendations"]
            )
            report_data["medium_recommendations"].extend(
                result_data["medium_recommendations"]
            )
            report_data["low_recommendations"].extend(
                result_data["low_recommendations"]
            )
            report_data["analyzer_summaries"].update(result_data["analyzer_summaries"])

        # Generate executive summary after all results are processed
        report_data["executive_summary"] = self._generate_executive_summary(report_data)

        return report_data

    async def _process_analysis_result_async(
        self, result: AnalysisResult
    ) -> dict[str, Any]:
        """Process a single analysis result asynchronously."""
        async with self._semaphore:  # Limit concurrent processing
            # Initialize individual result data
            result_data = {
                "total_recommendations": len(result.recommendations),
                "critical_issues": 0,
                "total_savings": 0.0,
                "critical_recommendations": [],
                "high_recommendations": [],
                "medium_recommendations": [],
                "low_recommendations": [],
                "analyzer_summaries": {},
            }

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
                    result_data["critical_issues"] += 1
                    result_data["critical_recommendations"].append(rec_dict)
                elif rec.priority == RecommendationPriority.HIGH:
                    result_data["high_recommendations"].append(rec_dict)
                elif rec.priority == RecommendationPriority.MEDIUM:
                    result_data["medium_recommendations"].append(rec_dict)
                else:
                    result_data["low_recommendations"].append(rec_dict)

                # Sum up savings
                if rec.estimated_cost_savings:
                    result_data["total_savings"] += rec.estimated_cost_savings

            # Get analyzer-specific summaries
            if hasattr(result, "to_summary_dict"):
                result_data["analyzer_summaries"][result.analyzer_name] = (
                    result.to_summary_dict()
                )

            # Add specialized data for certain result types
            if isinstance(result, SearchTermAnalysisResult):
                if result.potential_savings:
                    result_data["total_savings"] += result.potential_savings
            elif isinstance(result, KeywordMatchAnalysisResult):
                if result.potential_savings:
                    result_data["total_savings"] += result.potential_savings

            return result_data

    async def stream_report_sections(
        self,
        analysis_results: list[AnalysisResult],
        format: str = "html",
        **kwargs: Any,
    ) -> AsyncIterator[bytes]:
        """Stream report sections as they are generated for real-time updates.

        This is useful for large reports where you want to show progress
        to the user as sections are completed.

        Args:
            analysis_results: List of analysis results
            format: Output format (currently only supports 'html')
            **kwargs: Additional format-specific options

        Yields:
            Bytes chunks of the report as sections are completed
        """
        if format != "html":
            raise ValueError("Streaming is currently only supported for HTML format")

        # Prepare report data once and reuse for all sections
        report_data = await self._prepare_report_data_async(analysis_results)

        # Prepare header
        header = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>{self.company_name} Audit Report</title>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; }}
                .section {{ margin-bottom: 30px; }}
                .loading {{ color: #666; font-style: italic; }}
            </style>
        </head>
        <body>
            <h1>{self.company_name} Google Ads Audit Report</h1>
        """.encode("utf-8")
        yield header

        # Process sections concurrently and yield as completed
        sections = [
            ("executive_summary", self._generate_executive_summary_section),
            ("metrics", self._generate_metrics_section),
            ("recommendations", self._generate_recommendations_section),
            ("analyzer_details", self._generate_analyzer_details_section),
        ]

        for section_name, section_func in sections:
            if section_name in kwargs.get("include_sections", [s[0] for s in sections]):
                yield f'<div class="section loading">Loading {section_name.replace("_", " ").title()}...</div>'.encode(
                    "utf-8"
                )

                # Generate section
                section_content = await section_func(analysis_results, report_data)

                # Replace loading message with actual content
                yield '<script>document.querySelector(".loading").remove();</script>'.encode(
                    "utf-8"
                )
                yield section_content

        # Footer
        footer = """
        </body>
        </html>
        """.encode("utf-8")
        yield footer

    async def _generate_executive_summary_section(
        self,
        analysis_results: list[AnalysisResult],
        report_data: dict[str, Any] | None = None,
    ) -> bytes:
        """Generate executive summary section."""
        if report_data is None:
            report_data = await self._prepare_report_data_async(analysis_results)
        summary = report_data["executive_summary"]

        html_content = f"""
        <div class="section">
            <h2>Executive Summary</h2>
            <p>{html.escape(summary)}</p>
        </div>
        """
        return html_content.encode("utf-8")

    async def _generate_metrics_section(
        self,
        analysis_results: list[AnalysisResult],
        report_data: dict[str, Any] | None = None,
    ) -> bytes:
        """Generate metrics section."""
        if report_data is None:
            report_data = await self._prepare_report_data_async(analysis_results)

        html_content = f"""
        <div class="section">
            <h2>Key Metrics</h2>
            <table>
                <tr><td>Total Recommendations:</td><td>{html.escape(str(report_data["total_recommendations"]))}</td></tr>
                <tr><td>Critical Issues:</td><td>{html.escape(str(report_data["critical_issues"]))}</td></tr>
                <tr><td>Potential Savings:</td><td>${html.escape(f"{report_data['total_savings']:,.2f}")}</td></tr>
                <tr><td>Analyzers Run:</td><td>{html.escape(str(len(analysis_results)))}</td></tr>
            </table>
        </div>
        """
        return html_content.encode("utf-8")

    async def _generate_recommendations_section(
        self,
        analysis_results: list[AnalysisResult],
        report_data: dict[str, Any] | None = None,
    ) -> bytes:
        """Generate recommendations section."""
        if report_data is None:
            report_data = await self._prepare_report_data_async(analysis_results)

        html_content = '<div class="section"><h2>Recommendations</h2>'

        for priority in ["critical", "high", "medium", "low"]:
            recs = report_data[f"{priority}_recommendations"]
            if recs:
                html_content += f"<h3>{html.escape(priority.title())} Priority</h3><ul>"
                for rec in recs[:5]:
                    html_content += f"<li><strong>{html.escape(rec['title'])}</strong>: {html.escape(rec['description'])}</li>"
                html_content += "</ul>"

        html_content += "</div>"
        return html_content.encode("utf-8")

    async def _generate_analyzer_details_section(
        self,
        analysis_results: list[AnalysisResult],
        report_data: dict[str, Any] | None = None,
    ) -> bytes:
        """Generate analyzer details section."""
        html_content = '<div class="section"><h2>Analyzer Details</h2>'

        for result in analysis_results:
            html_content += f"<h3>{html.escape(result.analyzer_name)}</h3>"
            html_content += f"<p>Recommendations: {html.escape(str(len(result.recommendations)))}</p>"
            if hasattr(result, "to_summary_dict"):
                summary = result.to_summary_dict()
                html_content += (
                    f"<pre>{html.escape(json.dumps(summary, indent=2))}</pre>"
                )

        html_content += "</div>"
        return html_content.encode("utf-8")
