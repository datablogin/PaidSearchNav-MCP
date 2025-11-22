#!/usr/bin/env python3
"""Test script to generate multi-report Google Ads Script for Fitness Connection."""

from paidsearchnav.platforms.google.scripts.base import ScriptConfig
from paidsearchnav.platforms.google.scripts.quarterly_data_extraction import (
    MultiReportScript,
)


def main():
    """Generate multi-report script for testing."""

    # Use standard date range format
    date_range = "LAST_90_DAYS"

    # Create configuration for Fitness Connection
    from paidsearchnav.platforms.google.scripts.base import ScriptType

    config = ScriptConfig(
        name="Fitness Connection Multi Report - Search Terms + Keywords",
        type=ScriptType.NEGATIVE_KEYWORD,
        description="Combined extraction of search terms and keyword performance data",
        schedule="on_demand",
        parameters={
            "customer_id": "646-990-6417",
            "date_range": date_range,
            "include_geographic_data": True,
            "include_quality_score": True,
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
            ],
        },
    )

    # Generate the script
    script_generator = MultiReportScript(None, config)
    script_code = script_generator.generate_script()

    # Save to file
    output_file = "fitness_connection_multi_report.js"
    with open(output_file, "w") as f:
        f.write(script_code)

    print("Multi-report script generated successfully!")
    print(f"File: {output_file}")
    print("Customer ID: 646-990-6417 (Fitness Connection)")
    print(f"Date Range: {date_range}")
    print("Features:")
    print("  - Search Terms Performance Report")
    print("  - Keyword Performance Report")
    print("  - Geographic data included")
    print("  - Quality score data included")
    print("  - Bid recommendations")
    print("  - Local intent detection")
    print("\nThis script will generate TWO CSV files:")
    print("  1. search_terms_performance_YYYY-MM-DD_HH-MM.csv")
    print("  2. keyword_performance_YYYY-MM-DD_HH-MM.csv")


if __name__ == "__main__":
    main()
