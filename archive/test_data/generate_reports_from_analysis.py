#!/usr/bin/env python3
"""
Generate HTML and PDF reports from existing analysis results.
"""

import json
from datetime import datetime
from pathlib import Path


def generate_html_report(analysis_data, output_path):
    """Generate HTML report from analysis data."""

    # Extract summary data
    total_terms = analysis_data.get("total_search_terms", 0)
    classifications = analysis_data.get("classifications", {})
    add_candidates = classifications.get("add_candidates", [])
    negative_candidates = classifications.get("negative_candidates", [])
    already_covered = classifications.get("already_covered", [])
    review_needed = classifications.get("review_needed", [])
    recommendations = analysis_data.get("recommendations", [])

    # Calculate total cost savings
    total_savings = sum(
        term.get("metrics", {}).get("cost", 0) for term in negative_candidates
    )

    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Themis Legal - Search Terms Analysis Report</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
            margin: 40px auto;
            max-width: 1200px;
            line-height: 1.6;
            color: #333;
        }}
        .header {{
            color: #1a73e8;
            border-bottom: 3px solid #1a73e8;
            padding-bottom: 15px;
            margin-bottom: 30px;
        }}
        .summary {{
            background: #f8f9fa;
            padding: 25px;
            margin: 20px 0;
            border-radius: 8px;
            border-left: 5px solid #1a73e8;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .metric-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }}
        .metric {{
            text-align: center;
            padding: 15px;
            background: white;
            border-radius: 8px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}
        .metric-value {{
            font-size: 2.5em;
            font-weight: bold;
            color: #1a73e8;
            margin-bottom: 5px;
        }}
        .metric-label {{
            font-size: 0.9em;
            color: #666;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .section {{
            margin: 40px 0;
            background: white;
            padding: 25px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .section h2 {{
            color: #333;
            border-bottom: 2px solid #e0e0e0;
            padding-bottom: 10px;
            margin-bottom: 20px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 15px 0;
        }}
        th, td {{
            padding: 12px 15px;
            text-align: left;
            border-bottom: 1px solid #e0e0e0;
        }}
        th {{
            background-color: #f8f9fa;
            font-weight: 600;
            color: #555;
            text-transform: uppercase;
            font-size: 0.85em;
            letter-spacing: 0.5px;
        }}
        tr:hover {{
            background-color: #f8f9fa;
        }}
        .add-candidate {{ background-color: #e8f5e9; }}
        .negative-candidate {{ background-color: #ffebee; }}
        .already-covered {{ background-color: #e3f2fd; }}
        .recommendation {{
            background: #fff3cd;
            padding: 20px;
            margin: 15px 0;
            border-radius: 8px;
            border-left: 4px solid #ffc107;
        }}
        .recommendation h4 {{
            margin: 0 0 10px 0;
            color: #856404;
        }}
        .priority-high {{
            color: #d32f2f;
            font-weight: bold;
        }}
        .priority-medium {{
            color: #f57c00;
            font-weight: bold;
        }}
        .priority-low {{
            color: #388e3c;
        }}
        .footer {{
            margin-top: 60px;
            padding-top: 30px;
            border-top: 1px solid #e0e0e0;
            text-align: center;
            color: #666;
            font-size: 0.9em;
        }}
        .cost {{
            font-weight: 600;
            color: #d32f2f;
        }}
        .conversions {{
            font-weight: 600;
            color: #388e3c;
        }}
    </style>
</head>
<body>
    <h1 class="header">Themis Legal - Search Terms Analysis Report</h1>

    <div class="summary">
        <h2 style="margin-top: 0;">Executive Summary</h2>
        <p>Analysis of {total_terms} search terms from Google Ads campaigns, identifying optimization opportunities to improve cost efficiency and conversion performance.</p>

        <div class="metric-grid">
            <div class="metric">
                <div class="metric-value">{total_terms}</div>
                <div class="metric-label">Total Search Terms</div>
            </div>
            <div class="metric">
                <div class="metric-value">{len(add_candidates)}</div>
                <div class="metric-label">Add Candidates</div>
            </div>
            <div class="metric">
                <div class="metric-value">{len(negative_candidates)}</div>
                <div class="metric-label">Negative Keywords</div>
            </div>
            <div class="metric">
                <div class="metric-value">${total_savings:,.2f}</div>
                <div class="metric-label">Potential Savings</div>
            </div>
        </div>
    </div>"""

    # Recommendations Section
    if recommendations:
        html += """
    <div class="section">
        <h2>📋 Key Recommendations</h2>"""

        for rec in recommendations:
            priority = rec.get("priority", "MEDIUM")
            priority_class = f"priority-{priority.lower()}"
            html += f"""
        <div class="recommendation">
            <h4><span class="{priority_class}">[{priority}]</span> {rec.get("title", rec.get("description", ""))}</h4>
            <p>{rec.get("description", "")}</p>
        </div>"""

        html += """
    </div>"""

    # Add Candidates Section
    if add_candidates:
        html += """
    <div class="section">
        <h2>✅ Add Candidates - High Performing Search Terms</h2>
        <p>These search terms are driving conversions and should be added as keywords for better control and optimization.</p>
        <table>
            <tr>
                <th>Search Term</th>
                <th>Campaign</th>
                <th>Ad Group</th>
                <th>Impressions</th>
                <th>Clicks</th>
                <th>Cost</th>
                <th>Conversions</th>
                <th>CPA</th>
                <th>Recommendation</th>
            </tr>"""

        for term in add_candidates[:20]:  # Limit to top 20
            metrics = term.get("metrics", {})
            impressions = metrics.get("impressions", 0)
            clicks = metrics.get("clicks", 0)
            cost = metrics.get("cost", 0)
            conversions = metrics.get("conversions", 0)
            cpa = metrics.get("cpa", 0)

            html += f"""
            <tr class="add-candidate">
                <td><strong>{term.get("search_term", "")}</strong></td>
                <td>{term.get("campaign_name", "")}</td>
                <td>{term.get("ad_group_name", "")}</td>
                <td>{impressions:,}</td>
                <td>{clicks:,}</td>
                <td class="cost">${cost:,.2f}</td>
                <td class="conversions">{conversions}</td>
                <td>${cpa:,.2f}</td>
                <td>{term.get("recommendation", "Add as keyword")}</td>
            </tr>"""

        if len(add_candidates) > 20:
            html += f"""
            <tr>
                <td colspan="9" style="text-align: center; font-style: italic;">
                    ... and {len(add_candidates) - 20} more high-performing search terms
                </td>
            </tr>"""

        html += """
        </table>
    </div>"""

    # Negative Candidates Section
    if negative_candidates:
        html += """
    <div class="section">
        <h2>🚫 Negative Keywords - Wasteful Spend</h2>
        <p>These search terms are not converting and should be added as negative keywords to reduce wasted spend.</p>
        <table>
            <tr>
                <th>Search Term</th>
                <th>Campaign</th>
                <th>Ad Group</th>
                <th>Impressions</th>
                <th>Clicks</th>
                <th>Cost</th>
                <th>Conversions</th>
                <th>Recommendation</th>
            </tr>"""

        for term in negative_candidates[:20]:  # Limit to top 20
            metrics = term.get("metrics", {})
            impressions = metrics.get("impressions", 0)
            clicks = metrics.get("clicks", 0)
            cost = metrics.get("cost", 0)
            conversions = metrics.get("conversions", 0)

            html += f"""
            <tr class="negative-candidate">
                <td><strong>{term.get("search_term", "")}</strong></td>
                <td>{term.get("campaign_name", "")}</td>
                <td>{term.get("ad_group_name", "")}</td>
                <td>{impressions:,}</td>
                <td>{clicks:,}</td>
                <td class="cost">${cost:,.2f}</td>
                <td>{conversions}</td>
                <td>{term.get("recommendation", "Add as negative keyword")}</td>
            </tr>"""

        if len(negative_candidates) > 20:
            html += f"""
            <tr>
                <td colspan="8" style="text-align: center; font-style: italic;">
                    ... and {len(negative_candidates) - 20} more wasteful search terms
                </td>
            </tr>"""

        html += """
        </table>
    </div>"""

    # Footer
    html += f"""
    <div class="footer">
        <p>
            <strong>Report Generated:</strong> {datetime.now().strftime("%B %d, %Y at %I:%M %p")}<br>
            <em>PaidSearchNav - Google Ads Optimization Platform</em><br>
            <small>Themis Legal Search Terms Analysis</small>
        </p>
    </div>
</body>
</html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    return html


def generate_pdf_report(analysis_data, output_path):
    """Generate PDF report from analysis data."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import inch
        from reportlab.platypus import (
            PageBreak,
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

        # Custom styles
        title_style = ParagraphStyle(
            "CustomTitle",
            parent=styles["Heading1"],
            fontSize=24,
            spaceAfter=30,
            textColor=colors.HexColor("#1a73e8"),
            alignment=TA_CENTER,
        )

        heading_style = ParagraphStyle(
            "CustomHeading",
            parent=styles["Heading2"],
            fontSize=16,
            spaceAfter=12,
            textColor=colors.HexColor("#333333"),
        )

        # Title
        story.append(
            Paragraph("Themis Legal<br/>Search Terms Analysis Report", title_style)
        )
        story.append(Spacer(1, 20))

        # Summary section
        total_terms = analysis_data.get("total_search_terms", 0)
        classifications = analysis_data.get("classifications", {})
        add_candidates = classifications.get("add_candidates", [])
        negative_candidates = classifications.get("negative_candidates", [])
        recommendations = analysis_data.get("recommendations", [])

        # Calculate savings
        total_savings = sum(
            term.get("metrics", {}).get("cost", 0) for term in negative_candidates
        )

        # Executive Summary
        story.append(Paragraph("Executive Summary", heading_style))

        summary_data = [
            ["Metric", "Value"],
            ["Total Search Terms Analyzed", str(total_terms)],
            ["Add Candidates (High Performers)", str(len(add_candidates))],
            ["Negative Keywords (Wasteful Spend)", str(len(negative_candidates))],
            ["Potential Cost Savings", f"${total_savings:,.2f}"],
        ]

        summary_table = Table(summary_data, colWidths=[3 * inch, 2 * inch])
        summary_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f8f9fa")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), 12),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.white),
                    ("GRID", (0, 0), (-1, -1), 1, colors.grey),
                    ("FONTNAME", (1, 1), (1, -1), "Helvetica-Bold"),
                ]
            )
        )

        story.append(summary_table)
        story.append(Spacer(1, 30))

        # Key Recommendations
        if recommendations:
            story.append(Paragraph("Key Recommendations", heading_style))

            for i, rec in enumerate(recommendations[:5], 1):
                priority = rec.get("priority", "MEDIUM")
                desc = rec.get("description", rec.get("title", ""))

                rec_text = f"<b>{i}. [{priority}]</b> {desc}"
                story.append(Paragraph(rec_text, styles["Normal"]))
                story.append(Spacer(1, 10))

            story.append(Spacer(1, 20))

        # Add new page for detailed tables
        story.append(PageBreak())

        # Top Add Candidates
        if add_candidates:
            story.append(
                Paragraph(
                    "Top Performing Search Terms (Add as Keywords)", heading_style
                )
            )

            # Create table data
            table_data = [["Search Term", "Campaign", "Conv.", "CPA", "Action"]]

            for term in add_candidates[:15]:
                metrics = term.get("metrics", {})
                conversions = metrics.get("conversions", 0)
                cpa = metrics.get("cpa", 0)

                table_data.append(
                    [
                        term.get("search_term", "")[:35]
                        + ("..." if len(term.get("search_term", "")) > 35 else ""),
                        term.get("campaign_name", "")[:25]
                        + ("..." if len(term.get("campaign_name", "")) > 25 else ""),
                        f"{conversions:.1f}",
                        f"${cpa:.2f}",
                        "Add as keyword",
                    ]
                )

            if len(add_candidates) > 15:
                table_data.append(
                    [f"... and {len(add_candidates) - 15} more", "", "", "", ""]
                )

            add_table = Table(
                table_data,
                colWidths=[2.5 * inch, 2 * inch, 0.8 * inch, 0.8 * inch, 1.2 * inch],
            )
            add_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8f5e9")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                        ("ALIGN", (2, 0), (3, -1), "RIGHT"),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, -1), 9),
                        ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                        ("GRID", (0, 0), (-1, -1), 1, colors.grey),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ]
                )
            )

            story.append(add_table)
            story.append(Spacer(1, 30))

        # Top Negative Candidates
        if negative_candidates:
            story.append(
                Paragraph("Wasteful Search Terms (Add as Negatives)", heading_style)
            )

            # Create table data
            table_data = [["Search Term", "Campaign", "Clicks", "Cost", "Action"]]

            for term in negative_candidates[:15]:
                metrics = term.get("metrics", {})
                clicks = metrics.get("clicks", 0)
                cost = metrics.get("cost", 0)

                table_data.append(
                    [
                        term.get("search_term", "")[:35]
                        + ("..." if len(term.get("search_term", "")) > 35 else ""),
                        term.get("campaign_name", "")[:25]
                        + ("..." if len(term.get("campaign_name", "")) > 25 else ""),
                        str(clicks),
                        f"${cost:.2f}",
                        "Add as negative",
                    ]
                )

            if len(negative_candidates) > 15:
                table_data.append(
                    [f"... and {len(negative_candidates) - 15} more", "", "", "", ""]
                )

            neg_table = Table(
                table_data,
                colWidths=[2.5 * inch, 2 * inch, 0.8 * inch, 0.8 * inch, 1.2 * inch],
            )
            neg_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#ffebee")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                        ("ALIGN", (2, 0), (3, -1), "RIGHT"),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, -1), 9),
                        ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                        ("GRID", (0, 0), (-1, -1), 1, colors.grey),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ]
                )
            )

            story.append(neg_table)

        # Footer
        story.append(Spacer(1, 40))
        footer_style = ParagraphStyle(
            "Footer",
            parent=styles["Normal"],
            fontSize=10,
            textColor=colors.grey,
            alignment=TA_CENTER,
        )
        story.append(
            Paragraph(
                f"Report Generated: {datetime.now().strftime('%B %d, %Y')}",
                footer_style,
            )
        )
        story.append(
            Paragraph("PaidSearchNav - Google Ads Optimization Platform", footer_style)
        )

        # Build PDF
        doc.build(story)

    except ImportError:
        # Fallback to text if reportlab not available
        with open(output_path.with_suffix(".txt"), "w") as f:
            f.write(generate_text_report(analysis_data))
        raise ImportError("reportlab library required for PDF generation")


def generate_text_report(analysis_data):
    """Generate text report as fallback."""
    total_terms = analysis_data.get("total_search_terms", 0)
    classifications = analysis_data.get("classifications", {})
    add_candidates = classifications.get("add_candidates", [])
    negative_candidates = classifications.get("negative_candidates", [])
    recommendations = analysis_data.get("recommendations", [])

    total_savings = sum(
        term.get("metrics", {}).get("cost", 0) for term in negative_candidates
    )

    report = f"""
THEMIS LEGAL - SEARCH TERMS ANALYSIS REPORT
==========================================
Generated: {datetime.now().strftime("%B %d, %Y at %I:%M %p")}

EXECUTIVE SUMMARY
-----------------
Total Search Terms Analyzed: {total_terms}
Add Candidates: {len(add_candidates)}
Negative Keywords: {len(negative_candidates)}
Potential Cost Savings: ${total_savings:,.2f}

KEY RECOMMENDATIONS
-------------------
"""

    for i, rec in enumerate(recommendations[:5], 1):
        priority = rec.get("priority", "MEDIUM")
        desc = rec.get("description", rec.get("title", ""))
        report += f"{i}. [{priority}] {desc}\n"

    report += "\n"

    # Add sections
    if add_candidates:
        report += """
HIGH PERFORMING SEARCH TERMS (TOP 10)
-------------------------------------
"""
        for term in add_candidates[:10]:
            metrics = term.get("metrics", {})
            report += f"• {term.get('search_term', '')}\n"
            report += f"  Campaign: {term.get('campaign_name', '')}\n"
            report += f"  Conversions: {metrics.get('conversions', 0)}, CPA: ${metrics.get('cpa', 0):.2f}\n\n"

    if negative_candidates:
        report += """
WASTEFUL SEARCH TERMS (TOP 10)
------------------------------
"""
        for term in negative_candidates[:10]:
            metrics = term.get("metrics", {})
            report += f"• {term.get('search_term', '')}\n"
            report += f"  Campaign: {term.get('campaign_name', '')}\n"
            report += f"  Cost: ${metrics.get('cost', 0):.2f}, Clicks: {metrics.get('clicks', 0)}, Conversions: 0\n\n"

    report += "\n" + "=" * 50 + "\n"
    report += "Report generated by PaidSearchNav\n"

    return report


def main(analysis_file_path=None):
    """Generate reports from existing analysis data.

    Args:
        analysis_file_path: Optional path to the analysis file. If not provided, uses default.
    """
    print("=== Generating Reports from Themis Legal Analysis ===")

    # Use provided path or default
    if analysis_file_path:
        analysis_file = Path(analysis_file_path)
    else:
        # Default to the file created by analyze_themis_legal_proper.py
        analysis_file = Path("analysis_results/themis_legal_analysis_proper.json")

    if not analysis_file.exists():
        print(f"Error: Analysis file not found: {analysis_file}")
        print(f"Current working directory: {Path.cwd()}")
        print(f"Expected path: {analysis_file.absolute()}")
        return

    print(f"Loading analysis from: {analysis_file}")

    try:
        with open(analysis_file, "r") as f:
            analysis_data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in file {analysis_file}: {e}")
        return
    except Exception as e:
        print(f"Error reading file {analysis_file}: {e}")
        return

    print(
        f"Loaded analysis with {analysis_data.get('total_search_terms', 0)} search terms"
    )

    # Validate analysis data structure
    if "classifications" not in analysis_data:
        print("Error: Analysis data missing 'classifications' field")
        return

    if not isinstance(analysis_data["classifications"], dict):
        print("Error: 'classifications' field must be a dictionary")
        return

    # Create exports directory
    exports_dir = Path("exports")
    exports_dir.mkdir(exist_ok=True)

    # Generate HTML report
    print("\n=== Generating HTML Report ===")
    html_path = exports_dir / "themis_legal_report.html"
    generate_html_report(analysis_data, html_path)
    print(f"✓ HTML report saved to: {html_path}")

    # Generate PDF report
    print("\n=== Generating PDF Report ===")
    pdf_path = exports_dir / "themis_legal_report.pdf"
    try:
        generate_pdf_report(analysis_data, pdf_path)
        print(f"✓ PDF report saved to: {pdf_path}")
    except ImportError as e:
        print(f"⚠ PDF generation failed: {e}")
        text_path = exports_dir / "themis_legal_report.txt"
        if text_path.exists():
            print(f"✓ Text report saved to: {text_path}")

    # Summary
    print("\n=== Report Generation Complete ===")
    print("Reports generated for Themis Legal search terms analysis")
    print(f"- Total search terms: {analysis_data.get('total_search_terms', 0)}")
    classifications = analysis_data.get("classifications", {})
    print(f"- Add candidates: {len(classifications.get('add_candidates', []))}")
    print(
        f"- Negative candidates: {len(classifications.get('negative_candidates', []))}"
    )

    total_savings = sum(
        term.get("metrics", {}).get("cost", 0)
        for term in classifications.get("negative_candidates", [])
    )
    print(f"- Potential savings: ${total_savings:,.2f}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate reports from analysis data")
    parser.add_argument(
        "--analysis-file", type=str, help="Path to the analysis JSON file"
    )

    args = parser.parse_args()
    main(args.analysis_file)
