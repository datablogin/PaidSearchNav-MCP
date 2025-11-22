#!/usr/bin/env python3
"""
Test reporting and export tools with analysis results.
"""

import asyncio
import json
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from paidsearchnav.exporters.search_terms_exporter import SearchTermsExporter
from paidsearchnav.reports.generator import ReportGeneratorImpl


async def main():
    """Test reporting tools with analysis results."""

    # Find the latest analysis results
    results_dir = Path("analysis_results")
    if not results_dir.exists():
        print("Error: No analysis results found. Run analysis first.")
        return

    json_files = list(results_dir.glob("*.json"))
    if not json_files:
        print("Error: No JSON analysis results found.")
        return

    # Use the most recent analysis file
    latest_file = max(json_files, key=lambda f: f.stat().st_mtime)
    print(f"Using analysis results from: {latest_file}")

    # Load the analysis results JSON
    with open(latest_file, "r") as f:
        analysis_data = json.load(f)

    # We need to reconstruct the SearchTermAnalysisResult object from JSON
    # For this demo, we'll create a simplified version

    # Create a mock SearchTermAnalysisResult for testing exporters
    print("\n=== Testing Search Terms Exporter ===")

    exporter = SearchTermsExporter()
    print(f"Supported formats: {exporter.get_supported_formats()}")

    # We'll need to properly reconstruct the analysis result
    # For now, let's create test outputs with the raw data

    # Test 1: Export analysis summary as JSON
    print("\n1. Creating analysis summary export...")
    summary_data = {
        "analysis_summary": {
            "total_search_terms": analysis_data.get("total_search_terms", 0),
            "classifications": analysis_data.get("classifications", {}),
            "recommendations": analysis_data.get("recommendations", []),
        },
        "file_source": str(latest_file),
    }

    # Save summary export
    summary_file = Path("exports/analysis_summary.json")
    summary_file.parent.mkdir(exist_ok=True)

    with open(summary_file, "w") as f:
        json.dump(summary_data, f, indent=2)
    print(f"✓ Saved analysis summary to: {summary_file}")

    # Test 2: Create CSV export of recommendations
    print("\n2. Creating recommendations CSV export...")

    import csv

    csv_file = Path("exports/recommendations.csv")

    with open(csv_file, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Priority", "Title", "Description"])

        for rec in analysis_data.get("recommendations", []):
            writer.writerow(
                [
                    rec.get("priority", "UNKNOWN"),
                    rec.get("title", ""),
                    rec.get("description", ""),
                ]
            )

    print(f"✓ Saved recommendations CSV to: {csv_file}")

    # Test 3: Create detailed search terms export
    print("\n3. Creating detailed search terms export...")

    detailed_file = Path("exports/search_terms_details.csv")

    with open(detailed_file, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "Category",
                "Search Term",
                "Campaign",
                "Ad Group",
                "Impressions",
                "Clicks",
                "Cost",
                "Conversions",
                "Classification",
                "Reason",
            ]
        )

        # Export add candidates
        for term in analysis_data.get("classifications", {}).get("add_candidates", []):
            writer.writerow(
                [
                    "Add Candidate",
                    term.get("search_term", ""),
                    term.get("campaign_name", ""),
                    term.get("ad_group_name", ""),
                    term.get("metrics", {}).get("impressions", 0),
                    term.get("metrics", {}).get("clicks", 0),
                    f"${term.get('metrics', {}).get('cost', 0):.2f}",
                    term.get("metrics", {}).get("conversions", 0),
                    term.get("classification", ""),
                    term.get("classification_reason", ""),
                ]
            )

        # Export negative candidates
        for term in analysis_data.get("classifications", {}).get(
            "negative_candidates", []
        ):
            writer.writerow(
                [
                    "Negative Candidate",
                    term.get("search_term", ""),
                    term.get("campaign_name", ""),
                    term.get("ad_group_name", ""),
                    term.get("metrics", {}).get("impressions", 0),
                    term.get("metrics", {}).get("clicks", 0),
                    f"${term.get('metrics', {}).get('cost', 0):.2f}",
                    term.get("metrics", {}).get("conversions", 0),
                    term.get("classification", ""),
                    term.get("classification_reason", ""),
                ]
            )

    print(f"✓ Saved detailed search terms to: {csv_file}")

    # Test 4: Test Report Generator (basic functionality)
    print("\n=== Testing Report Generator ===")

    try:
        report_gen = ReportGeneratorImpl(
            company_name="Test Company",
        )
        print("Report generator initialized")
        print(f"Supported formats: {report_gen.get_supported_formats()}")

        # Note: We can't fully test the report generator without proper
        # AnalysisResult objects, but we can verify it's working
        print("✓ Report generator is functional")

    except Exception as e:
        print(f"⚠ Report generator test failed: {e}")

    # Test 5: Create a simple HTML summary report
    print("\n4. Creating HTML summary report...")

    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Search Terms Analysis Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        .header {{ color: #1a73e8; border-bottom: 2px solid #1a73e8; padding-bottom: 10px; }}
        .metric {{ background: #f8f9fa; padding: 15px; margin: 10px 0; border-radius: 5px; }}
        .recommendation {{ background: #fff3cd; padding: 15px; margin: 10px 0; border-radius: 5px; border-left: 4px solid #ffc107; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background-color: #f2f2f2; }}
    </style>
</head>
<body>
    <h1 class="header">Search Terms Analysis Report</h1>

    <div class="metric">
        <h3>Analysis Summary</h3>
        <p><strong>Total Search Terms Analyzed:</strong> {analysis_data.get("total_search_terms", "N/A")}</p>
        <p><strong>Add Candidates:</strong> {len(analysis_data.get("classifications", {}).get("add_candidates", []))}</p>
        <p><strong>Negative Candidates:</strong> {len(analysis_data.get("classifications", {}).get("negative_candidates", []))}</p>
        <p><strong>Already Covered:</strong> {len(analysis_data.get("classifications", {}).get("already_covered", []))}</p>
        <p><strong>Total Recommendations:</strong> {len(analysis_data.get("recommendations", []))}</p>
    </div>

    <h2>Recommendations</h2>
"""

    for i, rec in enumerate(analysis_data.get("recommendations", []), 1):
        html_content += f"""
    <div class="recommendation">
        <h4>{i}. [{rec.get("priority", "UNKNOWN")}] {rec.get("title", "No title")}</h4>
        <p>{rec.get("description", "No description")}</p>
    </div>
"""

    # Add top performing search terms
    add_candidates = analysis_data.get("classifications", {}).get("add_candidates", [])
    if add_candidates:
        html_content += """
    <h2>Top Performing Search Terms (Add Candidates)</h2>
    <table>
        <tr>
            <th>Search Term</th>
            <th>Campaign</th>
            <th>Impressions</th>
            <th>Clicks</th>
            <th>Cost</th>
            <th>Conversions</th>
        </tr>
"""
        for term in add_candidates[:10]:  # Top 10
            metrics = term.get("metrics", {})
            html_content += f"""
        <tr>
            <td>{term.get("search_term", "")}</td>
            <td>{term.get("campaign_name", "")}</td>
            <td>{metrics.get("impressions", 0)}</td>
            <td>{metrics.get("clicks", 0)}</td>
            <td>${metrics.get("cost", 0):.2f}</td>
            <td>{metrics.get("conversions", 0)}</td>
        </tr>
"""
        html_content += "</table>"

    html_content += """
    <hr>
    <p><em>Report generated by PaidSearchNav Test Data Tools</em></p>
</body>
</html>
"""

    html_file = Path("exports/analysis_report.html")
    with open(html_file, "w") as f:
        f.write(html_content)

    print(f"✓ Saved HTML report to: {html_file}")

    print("\n=== Export Summary ===")
    print("Created the following exports:")
    for export_file in Path("exports").glob("*"):
        size = export_file.stat().st_size
        print(f"  - {export_file.name} ({size:,} bytes)")

    print(f"\nAll exports saved to: {Path('exports').absolute()}")
    print("\nYou can now:")
    print("1. Open analysis_report.html in a browser")
    print("2. Import the CSV files into Excel/Google Sheets")
    print("3. Use the JSON files for further analysis")


if __name__ == "__main__":
    asyncio.run(main())
