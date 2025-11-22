#!/usr/bin/env python3
"""Test script to generate comprehensive quarterly audit Google Ads Script."""

from paidsearchnav.platforms.google.scripts.base import ScriptConfig, ScriptType
from paidsearchnav.platforms.google.scripts.quarterly_data_extraction import (
    ComprehensiveQuarterlyAuditScript,
)


def main():
    """Generate comprehensive quarterly audit script for testing."""

    # Create configuration for Fitness Connection
    config = ScriptConfig(
        name="Fitness Connection Comprehensive Quarterly Audit",
        type=ScriptType.NEGATIVE_KEYWORD,
        description="Complete quarterly audit with all reports: Search Terms + Keywords + Geographic + Campaign Performance",
        schedule="on_demand",
        parameters={
            "customer_id": "646-990-6417",
            "date_range": "LAST_90_DAYS",
            "include_geographic_data": True,
            "include_quality_score": True,
            "include_device_data": True,
            "min_clicks": 1,
            "min_cost": 0.01,
            "min_impressions": 10,
            "location_indicators": [
                "near me",
                "nearby",
                "close to me",
                "in my area",
                "dallas",
                "san antonio",
                "atlanta",
                "fayetteville",
                "texas",
                "georgia",
                "north carolina",
                "nc",
                "gym near",
                "fitness near",
                "workout near",
                "personal training",
                "fitness classes",
                "24 hour gym",
                "fitness center",
                "crossfit",
                "pilates",
                "yoga",
            ],
        },
    )

    # Generate the script
    script_generator = ComprehensiveQuarterlyAuditScript(None, config)
    script_code = script_generator.generate_script()

    # Save to file
    output_file = "fitness_connection_comprehensive_audit.js"
    with open(output_file, "w") as f:
        f.write(script_code)

    print("🎯 COMPREHENSIVE QUARTERLY AUDIT SCRIPT GENERATED!")
    print(f"📁 File: {output_file}")
    print("🏢 Customer: 646-990-6417 (Fitness Connection)")
    print("📅 Date Range: LAST_90_DAYS")
    print("")
    print("📊 REPORTS INCLUDED (4 Total):")
    print("  1. 🔍 Search Terms Performance")
    print("     - Local intent detection")
    print("     - Search term quality scoring")
    print("     - Match type inference")
    print("")
    print("  2. 🎯 Keywords Performance")
    print("     - Quality Score analysis")
    print("     - Bid recommendations")
    print("     - First page/top page CPC data")
    print("")
    print("  3. 🌍 Geographic Performance")
    print("     - Location-based analysis")
    print("     - Local intent scoring")
    print("     - Distance categorization")
    print("")
    print("  4. 📈 Campaign Performance")
    print("     - Budget utilization analysis")
    print("     - Performance scoring")
    print("     - Optimization recommendations")
    print("")
    print("🎉 EXPECTED OUTPUT: 4 CSV FILES")
    print("   - search_terms_performance_YYYY-MM-DD_HH-MM.csv")
    print("   - keyword_performance_YYYY-MM-DD_HH-MM.csv")
    print("   - geographic_performance_YYYY-MM-DD_HH-MM.csv")
    print("   - campaign_performance_YYYY-MM-DD_HH-MM.csv")
    print("")
    print("⚡ FEATURES:")
    print("   - Single script execution for complete quarterly audit")
    print("   - All field compatibility issues resolved")
    print("   - Comprehensive optimization recommendations")
    print("   - Local business focus (fitness industry)")


if __name__ == "__main__":
    main()
