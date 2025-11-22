#!/usr/bin/env python3
"""
Complete Workflow Guide: From CSV Download to Final Reports
"""


def workflow_overview():
    """Show the complete workflow overview."""
    print("=" * 80)
    print("COMPLETE WORKFLOW: CSV DOWNLOAD → ANALYSIS → REPORTS")
    print("=" * 80)

    print("""
┌─────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   DOWNLOAD  │ →  │  TRANSFORM   │ →  │   ANALYZE    │ →  │   EXPORT     │
│   CSV       │    │  & PROCESS   │    │   DATA       │    │   REPORTS    │
└─────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
""")


def step1_csv_download():
    """Step 1: Download CSV from Google Ads."""
    print("\n" + "=" * 60)
    print("STEP 1: DOWNLOAD CSV FROM GOOGLE ADS")
    print("=" * 60)

    print("""
📥 Google Ads Console → Reports → Predefined Reports

Recommended Reports:
┌─────────────────────┬────────────────────────────────────────┐
│ Report Type         │ Use Case                               │
├─────────────────────┼────────────────────────────────────────┤
│ Search Terms        │ Find wasted spend & new keywords      │
│ Keywords            │ Optimize match types & bids           │
│ Geographic          │ Location performance analysis         │
│ Campaign            │ High-level performance overview       │
│ Negative Keywords   │ Audit negative keyword conflicts      │
└─────────────────────┴────────────────────────────────────────┘

📅 Date Range: Last 30 days (recommended for quarterly audits)
📊 Metrics: Include impressions, clicks, cost, conversions
🏷️  Segments: Add campaign, ad group, match type
""")

    print("""
Download Location:
  → Save to: test_data/google_ads_exports/{report_type}/raw/

Example:
  • test_data/google_ads_exports/search_terms/raw/client-search-terms.csv
  • test_data/google_ads_exports/keywords/raw/client-keywords.csv
""")


def step2_data_validation():
    """Step 2: Validate and inspect the CSV."""
    print("\n" + "=" * 60)
    print("STEP 2: VALIDATE & INSPECT CSV DATA")
    print("=" * 60)

    print("""
🔍 Quick Validation:
""")
    print("python -m paidsearchnav.cli.main parse-csv \\")
    print("  --file google_ads_exports/search_terms/raw/client-file.csv \\")
    print("  --type search_term \\")
    print("  --show-sample \\")
    print("  --sample-size 10")

    print("""
This shows:
✓ Number of records parsed
✓ Sample data preview
✓ Data validation results
✓ Column structure verification
""")


def step3_transform_data():
    """Step 3: Transform Google Ads format to expected format."""
    print("\n" + "=" * 60)
    print("STEP 3: TRANSFORM DATA FORMAT")
    print("=" * 60)

    print("""
🔄 Google Ads exports often need format transformation:

Issues Commonly Fixed:
• Extra header rows ("Search terms report", date ranges)
• Column name mismatches ("Impr." vs "Impressions")
• Missing required ID columns
• Different match type formats
""")

    print("""
Transform Command:
""")
    print("python transform_google_ads_csv.py \\")
    print("  google_ads_exports/search_terms/raw/original-file.csv")

    print("""
This creates:
📄 original-file-transformed.csv (cleaned format)

Features:
✓ Generates missing Campaign ID & Ad Group ID
✓ Normalizes match types (EXACT, PHRASE, BROAD)
✓ Removes header rows and totals
✓ Maps column names to expected format
✓ Error handling for malformed data
""")


def step4_process_data():
    """Step 4: Process and parse the data."""
    print("\n" + "=" * 60)
    print("STEP 4: PROCESS & PARSE DATA")
    print("=" * 60)

    print("""
📊 Convert CSV to structured data models:
""")

    print("# Process specific file:")
    print("python process_test_data.py process \\")
    print("  --type search_terms \\")
    print("  --file google_ads_exports/search_terms/raw/file-transformed.csv")

    print("\n# Process all files of a type:")
    print("python process_test_data.py process --type search_terms")

    print("\n# List available files:")
    print("python process_test_data.py list-files")

    print("\n# Test with sample data:")
    print("python process_test_data.py test-sample")

    print("""
Output:
📁 google_ads_exports/search_terms/processed/file_parsed.json

Data Structure:
• Pydantic models for type safety
• Calculated metrics (CTR, CPC, CPA, ROAS)
• Local intent detection
• Structured for analysis
""")


def step5_analyze_data():
    """Step 5: Run analysis on processed data."""
    print("\n" + "=" * 60)
    print("STEP 5: ANALYZE DATA")
    print("=" * 60)

    print("""
🔬 Run sophisticated analysis algorithms:
""")

    print("# Analyze latest processed file:")
    print("python run_analysis.py")

    print("\n# Analyze specific file:")
    print("python run_analysis.py --input path/to/parsed.json")

    print("""
Analysis Features:
┌─────────────────────┬────────────────────────────────────────┐
│ Classification      │ Description                            │
├─────────────────────┼────────────────────────────────────────┤
│ Add Candidates      │ High-performing terms → new keywords  │
│ Negative Candidates │ Poor performers → negative keywords   │
│ Already Covered     │ Terms already captured by keywords    │
│ Review Needed       │ Ambiguous terms needing manual review │
└─────────────────────┴────────────────────────────────────────┘

Smart Detection:
✓ Local intent queries ("near me", city names)
✓ Performance thresholds (configurable)
✓ Cost efficiency analysis
✓ Conversion optimization
✓ Match type recommendations
""")


def step6_generate_reports():
    """Step 6: Generate reports and exports."""
    print("\n" + "=" * 60)
    print("STEP 6: GENERATE REPORTS & EXPORTS")
    print("=" * 60)

    print("""
📊 Multiple export formats for different stakeholders:
""")

    print("python test_reporting_tools.py")

    print("""
Generated Outputs:
┌─────────────────────┬────────────────────────────────────────┐
│ File                │ Purpose                                │
├─────────────────────┼────────────────────────────────────────┤
│ analysis_report.html│ 📱 Visual dashboard for clients       │
│ recommendations.csv │ 📋 Action items for PPC managers      │
│ search_terms_details│ 📊 Granular data for spreadsheets     │
│ analysis_summary.json│ 🔗 API integration & further analysis │
└─────────────────────┴────────────────────────────────────────┘
""")


def advanced_workflows():
    """Show advanced workflow options."""
    print("\n" + "=" * 60)
    print("ADVANCED WORKFLOWS")
    print("=" * 60)

    print("""
🏢 ENTERPRISE WORKFLOW (Multiple Clients):
""")
    print("for client_file in google_ads_exports/*/raw/*.csv; do")
    print('  python transform_google_ads_csv.py "$client_file"')
    print(
        '  python process_test_data.py process --file "${client_file%-*}-transformed.csv"'
    )
    print('  python run_analysis.py --input "processed/${client_file##*/}_parsed.json"')
    print("done")

    print("""
🔄 AUTOMATED WORKFLOW (API Integration):
1. POST /api/v1/upload → Upload CSV
2. GET /api/v1/results/{id} → Get analysis results
3. GET /api/v1/reports/{id}/export?format=pdf → Download report
""")

    print("""
📊 CUSTOM ANALYSIS WORKFLOW:
1. Load JSON analysis results
2. Apply custom business rules
3. Generate specialized reports
4. Integrate with CRM/BI tools
""")


def output_examples():
    """Show examples of outputs."""
    print("\n" + "=" * 60)
    print("OUTPUT EXAMPLES")
    print("=" * 60)

    print("""
📈 ANALYSIS RESULTS EXAMPLE:
""")
    print("Analysis complete!")
    print("Total search terms analyzed: 145")
    print("")
    print("Classifications:")
    print("- Add candidates: 23 (high-performing terms)")
    print("- Negative candidates: 8 (wasted spend)")
    print("- Already covered: 98 (existing keywords)")
    print("- Review needed: 16 (manual review)")
    print("")
    print("Recommendations: 4")
    print("  - [HIGH] Add 23 high-performing search terms as keywords")
    print("  - [HIGH] Add 8 negative keywords to save $245.67 monthly")
    print("  - [MEDIUM] 12 local intent queries need location targeting")
    print("  - [LOW] 5 'near me' searches converting well")

    print("""
💰 BUSINESS VALUE:
• Potential monthly savings: $245.67
• New keyword opportunities: 23 terms
• Wasted spend elimination: 8 negative keywords
• Local optimization: 12 location-specific opportunities
""")


def troubleshooting():
    """Show troubleshooting guide."""
    print("\n" + "=" * 60)
    print("TROUBLESHOOTING")
    print("=" * 60)

    issues = [
        {
            "issue": "CSV parsing fails",
            "solution": "Use transform_google_ads_csv.py to fix format issues",
        },
        {
            "issue": "Missing columns error",
            "solution": "Check CSV has required columns: Search term, Campaign, etc.",
        },
        {
            "issue": "No analysis results",
            "solution": "Verify processed JSON files exist in /processed/ directory",
        },
        {
            "issue": "Import errors",
            "solution": "Run from project root, ensure virtual environment activated",
        },
        {
            "issue": "Empty exports",
            "solution": "Check analysis found add/negative candidates",
        },
    ]

    for i, item in enumerate(issues, 1):
        print(f"{i}. {item['issue']}")
        print(f"   → {item['solution']}")
        print()


def main():
    """Run the complete workflow guide."""
    workflow_overview()
    step1_csv_download()
    step2_data_validation()
    step3_transform_data()
    step4_process_data()
    step5_analyze_data()
    step6_generate_reports()
    advanced_workflows()
    output_examples()
    troubleshooting()

    print("\n" + "=" * 80)
    print("🎯 READY TO START!")
    print("=" * 80)
    print("1. Download a search terms report from Google Ads")
    print("2. Save to: test_data/google_ads_exports/search_terms/raw/")
    print("3. Follow the steps above")
    print("4. View your results in test_data/exports/")
    print("\nHappy auditing! 🚀")


if __name__ == "__main__":
    main()
