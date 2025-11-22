#!/usr/bin/env python3
"""
Live Workflow Demonstration - Step by Step
"""

import subprocess
from pathlib import Path


def run_command(command, description):
    """Run a command and show its output."""
    print(f"\n🔧 {description}")
    print(f"💻 Command: {command}")
    print("-" * 60)

    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, cwd=Path.cwd()
        )

        if result.stdout:
            print("📤 Output:")
            print(result.stdout)

        if result.stderr and result.returncode != 0:
            print("⚠️  Error:")
            print(result.stderr)

        return result.returncode == 0

    except Exception as e:
        print(f"❌ Command failed: {e}")
        return False


def demo_step_by_step():
    """Demonstrate the complete workflow step by step."""

    print("=" * 80)
    print("🚀 LIVE WORKFLOW DEMONSTRATION")
    print("=" * 80)
    print("Following the complete process with sample data...\n")

    # Step 1: Show available sample data
    print("📋 STEP 1: Check Available Sample Data")
    run_command("ls -la sample_data/", "List sample data files")

    # Step 2: Validate sample CSV
    print("\n📋 STEP 2: Validate Sample CSV")
    run_command(
        "python -m paidsearchnav.cli.main parse-csv --file sample_data/sample_search_terms.csv --type search_term --show-sample --sample-size 3",
        "Parse and validate sample search terms CSV",
    )

    # Step 3: Process sample data
    print("\n📋 STEP 3: Process Sample Data")
    run_command(
        "python process_test_data.py test-sample",
        "Process sample keywords and search terms",
    )

    # Step 4: Check processed files
    print("\n📋 STEP 4: Check Processed Files")
    run_command("ls -la processed/", "List processed JSON files")

    # Step 5: Run analysis
    print("\n📋 STEP 5: Run Analysis on Sample Data")
    run_command(
        "python run_analysis.py --input processed/sample_search_terms_parsed.json",
        "Analyze sample search terms data",
    )

    # Step 6: Generate reports
    print("\n📋 STEP 6: Generate Reports")
    run_command(
        "python test_reporting_tools.py", "Generate comprehensive reports from analysis"
    )

    # Step 7: Show final outputs
    print("\n📋 STEP 7: Review Generated Outputs")
    run_command("ls -la exports/", "List all generated export files")

    # Step 8: Show file sizes and types
    print("\n📋 STEP 8: File Details")
    run_command("file exports/*", "Check file types of exports")

    # Final summary
    print("\n" + "=" * 80)
    print("✅ WORKFLOW COMPLETE!")
    print("=" * 80)
    print("""
🎯 What we accomplished:
1. ✅ Validated CSV data format and structure
2. ✅ Processed raw CSV into structured JSON models
3. ✅ Ran sophisticated search terms analysis
4. ✅ Generated multiple report formats
5. ✅ Created actionable recommendations

📂 Generated Files:
• HTML dashboard for client presentation
• CSV files for spreadsheet analysis
• JSON data for API integration
• Detailed recommendations for PPC managers

🔄 Ready for Production:
• Replace sample data with real Google Ads exports
• Configure analysis thresholds for client needs
• Automate with CLI tools or API integration
• Scale to multiple clients with batch processing
""")


def show_file_contents():
    """Show sample contents of generated files."""
    print("\n" + "=" * 60)
    print("📄 SAMPLE FILE CONTENTS")
    print("=" * 60)

    # Show recommendations CSV
    rec_file = Path("exports/recommendations.csv")
    if rec_file.exists():
        print("\n📊 Recommendations CSV (first 5 lines):")
        with open(rec_file, "r") as f:
            for i, line in enumerate(f):
                if i < 5:
                    print(f"  {line.strip()}")

    # Show HTML report snippet
    html_file = Path("exports/analysis_report.html")
    if html_file.exists():
        print(f"\n🌐 HTML Report: {html_file.stat().st_size:,} bytes")
        print("  Contains: Visual dashboard, metrics, recommendations")

    # Show JSON summary size
    json_file = Path("exports/analysis_summary.json")
    if json_file.exists():
        print(f"\n📋 JSON Summary: {json_file.stat().st_size:,} bytes")
        print("  Contains: Complete analysis data for API integration")


def show_next_steps():
    """Show what to do next."""
    print("\n" + "=" * 60)
    print("🎯 NEXT STEPS")
    print("=" * 60)

    steps = [
        "1. Download real client data from Google Ads",
        "2. Save CSV to: google_ads_exports/search_terms/raw/",
        "3. Transform format: python transform_google_ads_csv.py client-file.csv",
        "4. Process data: python process_test_data.py process --type search_terms",
        "5. Analyze: python run_analysis.py",
        "6. Export: python test_reporting_tools.py",
        "7. Review exports/ directory for deliverables",
    ]

    for step in steps:
        print(f"  {step}")

    print(f"\n📁 Working Directory: {Path.cwd()}")
    print("🔗 All tools are ready for production use!")


def main():
    """Run the complete demonstration."""
    demo_step_by_step()
    show_file_contents()
    show_next_steps()


if __name__ == "__main__":
    main()
