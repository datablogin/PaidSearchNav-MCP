#!/usr/bin/env python3
"""
Run analysis on Themis and Legent search terms data and generate HTML and PDF reports.
"""

import json
import sys
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, str(Path.cwd().parent))

try:
    from paidsearchnav.parsers.csv_parser import CSVParser

    # Mock analyzer and data provider for now
    class MockDataProvider:
        pass

    class MockSearchTermAnalyzer:
        def __init__(self, data_provider=None):
            self.data_provider = data_provider

        def analyze_search_terms(self, search_terms):
            """Mock analysis that classifies search terms."""
            results = []

            for term in search_terms:
                # Simple classification logic based on metrics
                if hasattr(term, "metrics") and term.metrics:
                    conversions = getattr(term.metrics, "conversions", 0)
                    cost = getattr(term.metrics, "cost", 0)

                    if conversions > 0 and cost > 0:
                        cpa = cost / conversions
                        if cpa <= 50:  # Good CPA
                            classification = "ADD_CANDIDATE"
                            reason = f"High performing: {conversions} conversions, CPA: ${cpa:.2f}"
                        else:
                            classification = "REVIEW_NEEDED"
                            reason = f"Moderate performance: {conversions} conversions, CPA: ${cpa:.2f}"
                    else:
                        classification = "NEGATIVE_CANDIDATE"
                        reason = f"Wasteful spend: ${cost:.2f} cost, no conversions"
                else:
                    classification = "REVIEW_NEEDED"
                    reason = "No metrics available"

                # Create analysis result
                result = {
                    "search_term": getattr(term, "search_term", str(term)),
                    "campaign_name": getattr(term, "campaign_name", "Unknown Campaign"),
                    "ad_group_name": getattr(term, "ad_group_name", "Unknown Ad Group"),
                    "classification": classification,
                    "classification_reason": reason,
                    "metrics": term.metrics.model_dump()
                    if hasattr(term, "metrics") and term.metrics
                    else {},
                }
                results.append(result)

            return results

    def main():
        print("=== Themis and Legent Search Terms Analysis ===")

        # Process the data
        csv_path = Path("sample_data/sample_search_terms.csv")
        print(f"Processing: {csv_path}")

        if not csv_path.exists():
            print(f"Error: File not found: {csv_path}")
            return

        # Parse CSV data
        parser = CSVParser(file_type="search_terms")
        search_terms = parser.parse(csv_path)
        print(f"Parsed {len(search_terms)} search terms")

        # Run analysis
        analyzer = MockSearchTermAnalyzer()
        results = analyzer.analyze_search_terms(search_terms)
        print(f"Analysis complete: {len(results)} results")

        # Categorize results
        add_candidates = [r for r in results if r["classification"] == "ADD_CANDIDATE"]
        negative_candidates = [
            r for r in results if r["classification"] == "NEGATIVE_CANDIDATE"
        ]
        review_needed = [r for r in results if r["classification"] == "REVIEW_NEEDED"]

        print(f"Add Candidates: {len(add_candidates)}")
        print(f"Negative Candidates: {len(negative_candidates)}")
        print(f"Review Needed: {len(review_needed)}")

        # Save analysis results
        output_dir = Path("analysis_results")
        output_dir.mkdir(exist_ok=True)
        analysis_file = output_dir / "themis_legent_analysis.json"

        analysis_output = {
            "total_search_terms": len(search_terms),
            "classifications": {
                "add_candidates": add_candidates,
                "negative_candidates": negative_candidates,
                "review_needed": review_needed,
            },
            "summary": {
                "add_count": len(add_candidates),
                "negative_count": len(negative_candidates),
                "review_count": len(review_needed),
            },
        }

        with open(analysis_file, "w") as f:
            json.dump(analysis_output, f, indent=2, default=str)

        print(f"Analysis saved to: {analysis_file}")

        # Generate HTML report
        print("\n=== Generating HTML Report ===")
        html_content = generate_html_report(analysis_output)

        exports_dir = Path("exports")
        exports_dir.mkdir(exist_ok=True)
        html_file = exports_dir / "themis_legent_report.html"

        with open(html_file, "w") as f:
            f.write(html_content)

        print(f"HTML report saved to: {html_file}")

        # Generate PDF report (basic version)
        print("\n=== Generating PDF Report ===")
        try:
            generate_pdf_report(
                analysis_output, exports_dir / "themis_legent_report.pdf"
            )
            print(f"PDF report saved to: {exports_dir / 'themis_legent_report.pdf'}")
        except ImportError as e:
            print(f"PDF generation requires additional dependencies: {e}")
            print("Install with: pip install reportlab")

            # Create a simple text report instead
            text_report = generate_text_report(analysis_output)
            text_file = exports_dir / "themis_legent_report.txt"
            with open(text_file, "w") as f:
                f.write(text_report)
            print(f"Text report saved to: {text_file}")

    def generate_html_report(analysis_data):
        """Generate HTML report from analysis data."""
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Themis & Legent Search Terms Analysis Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }}
        .header {{ color: #1a73e8; border-bottom: 3px solid #1a73e8; padding-bottom: 10px; margin-bottom: 30px; }}
        .summary {{ background: #f8f9fa; padding: 20px; margin: 20px 0; border-radius: 8px; border-left: 5px solid #1a73e8; }}
        .metric {{ display: inline-block; margin: 10px 20px 10px 0; }}
        .metric-value {{ font-size: 2em; font-weight: bold; color: #1a73e8; }}
        .metric-label {{ font-size: 0.9em; color: #666; }}
        .section {{ margin: 30px 0; }}
        .section h2 {{ color: #333; border-bottom: 2px solid #e0e0e0; padding-bottom: 5px; }}
        table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background-color: #f2f2f2; font-weight: bold; }}
        .add-candidate {{ background-color: #e8f5e8; }}
        .negative-candidate {{ background-color: #ffeaea; }}
        .review-needed {{ background-color: #fff3cd; }}
        .classification {{ padding: 4px 8px; border-radius: 4px; font-size: 0.85em; font-weight: bold; }}
        .add {{ background: #28a745; color: white; }}
        .negative {{ background: #dc3545; color: white; }}
        .review {{ background: #ffc107; color: black; }}
    </style>
</head>
<body>
    <h1 class="header">Themis & Legent Search Terms Analysis Report</h1>

    <div class="summary">
        <h3>Executive Summary</h3>
        <div class="metric">
            <div class="metric-value">{analysis_data["total_search_terms"]}</div>
            <div class="metric-label">Total Search Terms</div>
        </div>
        <div class="metric">
            <div class="metric-value">{analysis_data["summary"]["add_count"]}</div>
            <div class="metric-label">Add Candidates</div>
        </div>
        <div class="metric">
            <div class="metric-value">{analysis_data["summary"]["negative_count"]}</div>
            <div class="metric-label">Negative Candidates</div>
        </div>
        <div class="metric">
            <div class="metric-value">{analysis_data["summary"]["review_count"]}</div>
            <div class="metric-label">Review Needed</div>
        </div>
    </div>"""

        # Add Candidates Section
        if analysis_data["classifications"]["add_candidates"]:
            html += """
    <div class="section">
        <h2>🟢 Add Candidates - High Performing Search Terms</h2>
        <table>
            <tr>
                <th>Search Term</th>
                <th>Campaign</th>
                <th>Ad Group</th>
                <th>Classification Reason</th>
            </tr>"""

            for term in analysis_data["classifications"]["add_candidates"]:
                html += f"""
            <tr class="add-candidate">
                <td><strong>{term["search_term"]}</strong></td>
                <td>{term["campaign_name"]}</td>
                <td>{term["ad_group_name"]}</td>
                <td>{term["classification_reason"]}</td>
            </tr>"""

            html += """
        </table>
    </div>"""

        # Negative Candidates Section
        if analysis_data["classifications"]["negative_candidates"]:
            html += """
    <div class="section">
        <h2>🔴 Negative Candidates - Wasteful Spend</h2>
        <table>
            <tr>
                <th>Search Term</th>
                <th>Campaign</th>
                <th>Ad Group</th>
                <th>Classification Reason</th>
            </tr>"""

            for term in analysis_data["classifications"]["negative_candidates"]:
                html += f"""
            <tr class="negative-candidate">
                <td><strong>{term["search_term"]}</strong></td>
                <td>{term["campaign_name"]}</td>
                <td>{term["ad_group_name"]}</td>
                <td>{term["classification_reason"]}</td>
            </tr>"""

            html += """
        </table>
    </div>"""

        # Review Needed Section
        if analysis_data["classifications"]["review_needed"]:
            html += """
    <div class="section">
        <h2>🟡 Review Needed - Requires Manual Assessment</h2>
        <table>
            <tr>
                <th>Search Term</th>
                <th>Campaign</th>
                <th>Ad Group</th>
                <th>Classification Reason</th>
            </tr>"""

            for term in analysis_data["classifications"]["review_needed"]:
                html += f"""
            <tr class="review-needed">
                <td><strong>{term["search_term"]}</strong></td>
                <td>{term["campaign_name"]}</td>
                <td>{term["ad_group_name"]}</td>
                <td>{term["classification_reason"]}</td>
            </tr>"""

            html += """
        </table>
    </div>"""

        html += (
            """
    <hr style="margin: 40px 0;">
    <p style="text-align: center; color: #666; font-size: 0.9em;">
        <em>Report generated by PaidSearchNav - Themis & Legent Analysis</em><br>
        Generated on: """
            + str(Path.cwd())
            + """
    </p>
</body>
</html>"""
        )

        return html

    def generate_pdf_report(analysis_data, output_path):
        """Generate PDF report using reportlab."""
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
            from reportlab.lib.units import inch
            from reportlab.platypus import (
                Paragraph,
                SimpleDocTemplate,
                Spacer,
                Table,
                TableStyle,
            )

            # Create PDF document
            doc = SimpleDocTemplate(str(output_path), pagesize=A4)
            styles = getSampleStyleSheet()
            story = []

            # Title
            title_style = ParagraphStyle(
                "CustomTitle",
                parent=styles["Heading1"],
                fontSize=24,
                spaceAfter=30,
                textColor=colors.HexColor("#1a73e8"),
            )
            story.append(
                Paragraph("Themis & Legent Search Terms Analysis Report", title_style)
            )
            story.append(Spacer(1, 20))

            # Summary
            summary_data = [
                ["Metric", "Count"],
                ["Total Search Terms", str(analysis_data["total_search_terms"])],
                ["Add Candidates", str(analysis_data["summary"]["add_count"])],
                [
                    "Negative Candidates",
                    str(analysis_data["summary"]["negative_count"]),
                ],
                ["Review Needed", str(analysis_data["summary"]["review_count"])],
            ]

            summary_table = Table(summary_data)
            summary_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f2f2f2")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, 0), 12),
                        ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                        ("BACKGROUND", (0, 1), (-1, -1), colors.white),
                        ("GRID", (0, 0), (-1, -1), 1, colors.black),
                    ]
                )
            )

            story.append(Paragraph("Executive Summary", styles["Heading2"]))
            story.append(summary_table)
            story.append(Spacer(1, 20))

            # Add sections for each classification
            sections = [
                (
                    "Add Candidates - High Performing Search Terms",
                    analysis_data["classifications"]["add_candidates"],
                    colors.HexColor("#e8f5e8"),
                ),
                (
                    "Negative Candidates - Wasteful Spend",
                    analysis_data["classifications"]["negative_candidates"],
                    colors.HexColor("#ffeaea"),
                ),
                (
                    "Review Needed - Manual Assessment Required",
                    analysis_data["classifications"]["review_needed"],
                    colors.HexColor("#fff3cd"),
                ),
            ]

            for section_title, terms, bg_color in sections:
                if terms:
                    story.append(Paragraph(section_title, styles["Heading2"]))

                    # Create table data
                    table_data = [["Search Term", "Campaign", "Classification Reason"]]
                    for term in terms[:10]:  # Limit to first 10 for PDF
                        table_data.append(
                            [
                                term["search_term"][:40]
                                + ("..." if len(term["search_term"]) > 40 else ""),
                                term["campaign_name"][:25]
                                + ("..." if len(term["campaign_name"]) > 25 else ""),
                                term["classification_reason"][:50]
                                + (
                                    "..."
                                    if len(term["classification_reason"]) > 50
                                    else ""
                                ),
                            ]
                        )

                    if len(terms) > 10:
                        table_data.append(
                            [f"... and {len(terms) - 10} more terms", "", ""]
                        )

                    table = Table(
                        table_data, colWidths=[2.5 * inch, 2 * inch, 2.5 * inch]
                    )
                    table.setStyle(
                        TableStyle(
                            [
                                (
                                    "BACKGROUND",
                                    (0, 0),
                                    (-1, 0),
                                    colors.HexColor("#f2f2f2"),
                                ),
                                ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                                ("FONTSIZE", (0, 0), (-1, 0), 10),
                                ("FONTSIZE", (0, 1), (-1, -1), 8),
                                ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                                ("BACKGROUND", (0, 1), (-1, -1), bg_color),
                                ("GRID", (0, 0), (-1, -1), 1, colors.black),
                                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                            ]
                        )
                    )

                    story.append(table)
                    story.append(Spacer(1, 20))

            # Build PDF
            doc.build(story)

        except ImportError:
            raise ImportError("reportlab library required for PDF generation")

    def generate_text_report(analysis_data):
        """Generate text report as fallback."""
        report = f"""
THEMIS & LEGENT SEARCH TERMS ANALYSIS REPORT
=============================================

EXECUTIVE SUMMARY
-----------------
Total Search Terms: {analysis_data["total_search_terms"]}
Add Candidates: {analysis_data["summary"]["add_count"]}
Negative Candidates: {analysis_data["summary"]["negative_count"]}
Review Needed: {analysis_data["summary"]["review_count"]}

"""

        # Add sections
        sections = [
            (
                "ADD CANDIDATES - HIGH PERFORMING SEARCH TERMS",
                analysis_data["classifications"]["add_candidates"],
            ),
            (
                "NEGATIVE CANDIDATES - WASTEFUL SPEND",
                analysis_data["classifications"]["negative_candidates"],
            ),
            (
                "REVIEW NEEDED - MANUAL ASSESSMENT REQUIRED",
                analysis_data["classifications"]["review_needed"],
            ),
        ]

        for title, terms in sections:
            if terms:
                report += f"\n{title}\n"
                report += "=" * len(title) + "\n\n"

                for i, term in enumerate(terms, 1):
                    report += f"{i}. {term['search_term']}\n"
                    report += f"   Campaign: {term['campaign_name']}\n"
                    report += f"   Ad Group: {term['ad_group_name']}\n"
                    report += f"   Reason: {term['classification_reason']}\n\n"

        report += "\n" + "=" * 50 + "\n"
        report += "Report generated by PaidSearchNav\n"

        return report

    if __name__ == "__main__":
        main()

except ImportError as e:
    print(f"Import error: {e}")
    print(
        "Please ensure you're running from the correct directory with the virtual environment activated."
    )
