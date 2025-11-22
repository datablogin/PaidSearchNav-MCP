#!/usr/bin/env python3
"""
Demonstrate advanced reporting capabilities.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))


def demo_available_exporters():
    """Show all available exporters in the system."""
    print("=== Available Exporters ===")

    try:
        from paidsearchnav.exporters.search_terms_exporter import SearchTermsExporter

        st_exporter = SearchTermsExporter()
        print(f"✓ SearchTermsExporter: {st_exporter.get_supported_formats()}")
    except ImportError as e:
        print(f"✗ SearchTermsExporter: {e}")

    try:
        from paidsearchnav.exporters.keyword_match_exporter import KeywordMatchExporter

        km_exporter = KeywordMatchExporter()
        print(f"✓ KeywordMatchExporter: {km_exporter.get_supported_formats()}")
    except ImportError as e:
        print(f"✗ KeywordMatchExporter: {e}")

    try:
        from paidsearchnav.exporters.pmax_exporter import PmaxExporter

        pmax_exporter = PmaxExporter()
        print(f"✓ PmaxExporter: {pmax_exporter.get_supported_formats()}")
    except ImportError as e:
        print(f"✗ PmaxExporter: {e}")


def demo_cli_capabilities():
    """Show CLI capabilities."""
    print("\n=== CLI Capabilities ===")
    print("Available commands:")
    print("1. python -m paidsearchnav.cli.main parse-csv")
    print("   - Parse CSV files from Google Ads exports")
    print("   - Supports: keywords, search_terms, geo reports")
    print("   - Options: validation, sampling, encoding")

    print("\n2. python -m paidsearchnav.cli.main auth")
    print("   - Manage Google Ads API authentication")

    print("\n3. python -m paidsearchnav.cli.main scheduler")
    print("   - Manage scheduled audits")


def demo_api_endpoints():
    """Show available API endpoints for reporting."""
    print("\n=== API Endpoints ===")

    api_endpoints = [
        "GET /api/v1/reports - List available reports",
        "POST /api/v1/reports/generate - Generate new report",
        "GET /api/v1/reports/{id} - Get specific report",
        "GET /api/v1/reports/{id}/export - Export report in various formats",
        "GET /api/v1/results - Get analysis results",
        "POST /api/v1/upload - Upload CSV for analysis",
    ]

    for endpoint in api_endpoints:
        print(f"  {endpoint}")


def demo_analysis_workflows():
    """Show different analysis workflows possible."""
    print("\n=== Analysis Workflows ===")

    workflows = [
        {
            "name": "Search Terms Analysis",
            "steps": [
                "1. Export search terms report from Google Ads",
                "2. Transform CSV format (if needed)",
                "3. Process with: python process_test_data.py process --type search_terms",
                "4. Analyze with: python run_analysis.py",
                "5. Export results with: python test_reporting_tools.py",
            ],
        },
        {
            "name": "Keyword Analysis",
            "steps": [
                "1. Export keywords report from Google Ads",
                "2. Process with: python process_test_data.py process --type keywords",
                "3. Run keyword analyzer",
                "4. Generate recommendations report",
            ],
        },
        {
            "name": "CLI Analysis",
            "steps": [
                "1. python -m paidsearchnav.cli.main parse-csv --file report.csv --type search_term",
                "2. Use API or custom scripts for analysis",
                "3. Generate reports via API endpoints",
            ],
        },
    ]

    for workflow in workflows:
        print(f"\n{workflow['name']}:")
        for step in workflow["steps"]:
            print(f"  {step}")


def demo_export_formats():
    """Show all available export formats."""
    print("\n=== Export Formats Available ===")

    formats = {
        "SearchTermsExporter": ["csv", "xlsx", "json"],
        "ReportGenerator": ["html", "pdf", "csv", "json"],
        "Custom Exports": ["HTML reports", "CSV summaries", "JSON data"],
    }

    for exporter, format_list in formats.items():
        print(f"{exporter}: {', '.join(format_list)}")


def main():
    """Run the demo."""
    print("PaidSearchNav - Reporting Tools Demo")
    print("=" * 50)

    demo_available_exporters()
    demo_cli_capabilities()
    demo_api_endpoints()
    demo_analysis_workflows()
    demo_export_formats()

    print("\n=== Next Steps ===")
    print("You can now:")
    print("1. Upload another client's CSV files to test_data/google_ads_exports/")
    print("2. Run different analyzers on the same data")
    print("3. Export results in different formats")
    print("4. Use the CLI tools for batch processing")
    print("5. Set up the API for automated reporting")

    print(f"\nTest data exports are in: {Path('exports').absolute()}")


if __name__ == "__main__":
    main()
