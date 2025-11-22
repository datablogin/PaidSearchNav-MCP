#!/usr/bin/env python3
"""
Test script for PR #476 Quarterly Data Extraction functionality.

This script generates Google Ads Scripts for Search Terms Performance extraction
for both Fitness Connection and Cotton Patch Cafe to test the new functionality.
"""

import json
from datetime import datetime
from unittest.mock import Mock

from paidsearchnav.platforms.google.client import GoogleAdsClient
from paidsearchnav.platforms.google.scripts.base import ScriptConfig, ScriptType
from paidsearchnav.platforms.google.scripts.quarterly_data_extraction import (
    SearchTermsPerformanceScript,
)


def create_fitness_connection_script():
    """Create Search Terms Performance Script for Fitness Connection."""
    print("🏋️  Generating Search Terms Performance Script for Fitness Connection")
    print("=" * 70)

    # Mock client for script generation
    mock_client = Mock(spec=GoogleAdsClient)

    # Fitness Connection specific configuration
    fitness_config = ScriptConfig(
        name="fitness_connection_search_terms_extraction",
        type=ScriptType.NEGATIVE_KEYWORD,
        description="Search Terms Performance extraction for Fitness Connection",
        parameters={
            "date_range": "LAST_90_DAYS",  # Match your UI extract date range
            "customer_id": "6469906417",  # Fitness Connection customer ID
            "include_geographic_data": True,
            "min_clicks": 1,
            "min_cost": 0.01,
            # Fitness-specific location indicators based on their business
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
                "fitness center near",
                "24 hour gym",
                "24/7 gym",
                "cheap gym",
                "gym membership",
                "personal trainer near",
                "group fitness near",
            ],
        },
    )

    # Create script instance
    fitness_script = SearchTermsPerformanceScript(mock_client, fitness_config)

    # Validate parameters
    if not fitness_script.validate_parameters():
        print("❌ Parameter validation failed for Fitness Connection")
        return None

    # Generate the JavaScript code
    script_code = fitness_script.generate_script()

    print("✅ Script generated successfully!")
    print(f"📄 Script length: {len(script_code):,} characters")
    print(f"🎯 Customer ID: {fitness_config.parameters['customer_id']}")
    print(f"📅 Date Range: {fitness_config.parameters['date_range']}")
    print(
        f"📍 Location Indicators: {len(fitness_config.parameters['location_indicators'])} terms"
    )

    return {
        "customer_name": "Fitness Connection",
        "customer_id": fitness_config.parameters["customer_id"],
        "script_code": script_code,
        "config": fitness_config,
        "script_instance": fitness_script,
    }


def create_cotton_patch_script():
    """Create Search Terms Performance Script for Cotton Patch Cafe."""
    print("\n🍽️  Generating Search Terms Performance Script for Cotton Patch Cafe")
    print("=" * 70)

    # Mock client for script generation
    mock_client = Mock(spec=GoogleAdsClient)

    # Cotton Patch Cafe specific configuration
    cotton_patch_config = ScriptConfig(
        name="cotton_patch_cafe_search_terms_extraction",
        type=ScriptType.NEGATIVE_KEYWORD,
        description="Search Terms Performance extraction for Cotton Patch Cafe",
        parameters={
            "date_range": "LAST_90_DAYS",  # Match your UI extract date range
            "customer_id": "9524080160",  # Cotton Patch Cafe customer ID
            "include_geographic_data": True,
            "min_clicks": 1,
            "min_cost": 0.01,
            # Restaurant-specific location indicators
            "location_indicators": [
                "near me",
                "nearby",
                "close to me",
                "in my area",
                "texas",
                "tx",
                "restaurant near",
                "cafe near",
                "food near",
                "dining near",
                "cotton patch near",
                "breakfast near",
                "lunch near",
                "dinner near",
                "family restaurant",
                "casual dining",
                "southern food",
                "comfort food",
                "chicken fried steak",
                "open now",
                "delivery near",
                "takeout near",
                "dine in",
                "hours",
                "location",
                "address",
            ],
        },
    )

    # Create script instance
    cotton_patch_script = SearchTermsPerformanceScript(mock_client, cotton_patch_config)

    # Validate parameters
    if not cotton_patch_script.validate_parameters():
        print("❌ Parameter validation failed for Cotton Patch Cafe")
        return None

    # Generate the JavaScript code
    script_code = cotton_patch_script.generate_script()

    print("✅ Script generated successfully!")
    print(f"📄 Script length: {len(script_code):,} characters")
    print(f"🎯 Customer ID: {cotton_patch_config.parameters['customer_id']}")
    print(f"📅 Date Range: {cotton_patch_config.parameters['date_range']}")
    print(
        f"📍 Location Indicators: {len(cotton_patch_config.parameters['location_indicators'])} terms"
    )

    return {
        "customer_name": "Cotton Patch Cafe",
        "customer_id": cotton_patch_config.parameters["customer_id"],
        "script_code": script_code,
        "config": cotton_patch_config,
        "script_instance": cotton_patch_script,
    }


def analyze_generated_scripts(fitness_result, cotton_patch_result):
    """Analyze the generated scripts for potential issues."""
    print("\n🔍 Analyzing Generated Scripts")
    print("=" * 50)

    issues = []

    # Check both scripts exist
    if not fitness_result:
        issues.append("❌ Fitness Connection script generation failed")
    if not cotton_patch_result:
        issues.append("❌ Cotton Patch Cafe script generation failed")

    if not fitness_result or not cotton_patch_result:
        return issues

    # Analyze script content
    for result in [fitness_result, cotton_patch_result]:
        customer = result["customer_name"]
        script = result["script_code"]

        print(f"\n📊 {customer} Script Analysis:")

        # Check for critical JavaScript elements
        required_elements = [
            "function main()",
            "search_term_view",
            "DriveApp.createFile",
            "detectLocalIntent",
            "classifyLocationType",
            "streamingCSVWriter",
            "GAQL",
            "AdsApp.search",
        ]

        missing_elements = []
        for element in required_elements:
            if element not in script:
                missing_elements.append(element)

        if missing_elements:
            issues.append(f"❌ {customer}: Missing elements: {missing_elements}")
            print(f"   ⚠️  Missing: {', '.join(missing_elements)}")
        else:
            print("   ✅ All required JavaScript elements present")

        # Check for Google Ads API v20 compatibility
        if "search_term_view" in script and "metrics.clicks" in script:
            print("   ✅ Google Ads API v20 compatible queries")
        else:
            issues.append(f"❌ {customer}: May not be API v20 compatible")
            print("   ⚠️  API compatibility concerns")

        # Check customer ID format
        customer_id = result["customer_id"]
        if len(customer_id) == 10 and customer_id.isdigit():
            print(f"   ✅ Valid customer ID format: {customer_id}")
        else:
            issues.append(f"❌ {customer}: Invalid customer ID format: {customer_id}")
            print(f"   ⚠️  Invalid customer ID: {customer_id}")

        # Check location indicators
        config = result["config"]
        location_count = len(config.parameters.get("location_indicators", []))
        print(f"   📍 Location indicators: {location_count}")

        if location_count < 5:
            issues.append(
                f"❌ {customer}: Too few location indicators ({location_count})"
            )
            print("   ⚠️  Consider adding more location indicators")
        else:
            print("   ✅ Good location indicator coverage")

    return issues


def save_scripts_to_files(fitness_result, cotton_patch_result):
    """Save generated scripts to files for inspection."""
    print("\n💾 Saving Generated Scripts")
    print("=" * 40)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if fitness_result:
        fitness_filename = f"fitness_connection_search_terms_script_{timestamp}.js"
        with open(fitness_filename, "w", encoding="utf-8") as f:
            f.write(fitness_result["script_code"])
        print(f"✅ Saved: {fitness_filename}")

    if cotton_patch_result:
        cotton_patch_filename = f"cotton_patch_cafe_search_terms_script_{timestamp}.js"
        with open(cotton_patch_filename, "w", encoding="utf-8") as f:
            f.write(cotton_patch_result["script_code"])
        print(f"✅ Saved: {cotton_patch_filename}")

    # Also save configuration summary
    summary = {
        "generated_at": datetime.utcnow().isoformat(),
        "fitness_connection": {
            "customer_id": fitness_result["customer_id"] if fitness_result else None,
            "date_range": fitness_result["config"].parameters["date_range"]
            if fitness_result
            else None,
            "location_indicators_count": len(
                fitness_result["config"].parameters.get("location_indicators", [])
            )
            if fitness_result
            else 0,
        }
        if fitness_result
        else None,
        "cotton_patch_cafe": {
            "customer_id": cotton_patch_result["customer_id"]
            if cotton_patch_result
            else None,
            "date_range": cotton_patch_result["config"].parameters["date_range"]
            if cotton_patch_result
            else None,
            "location_indicators_count": len(
                cotton_patch_result["config"].parameters.get("location_indicators", [])
            )
            if cotton_patch_result
            else 0,
        }
        if cotton_patch_result
        else None,
    }

    summary_filename = f"script_generation_summary_{timestamp}.json"
    with open(summary_filename, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"✅ Saved: {summary_filename}")


def compare_with_ui_extracts():
    """Compare expected script output with UI extract formats."""
    print("\n🔬 UI Extract Comparison Analysis")
    print("=" * 45)

    # Based on your S3 paths, these are the expected formats
    expected_columns = {
        "search_terms_ui_export": [
            "Campaign",
            "Ad Group",
            "Search Term",
            "Match Type",
            "Clicks",
            "Impressions",
            "Cost",
            "Conversions",
            "Conv. Rate",
            "Cost / Conv.",
            "CPC",
            "CTR",
        ]
    }

    # Our script generates these columns
    script_columns = [
        "Campaign",
        "Ad Group",
        "Search Term",
        "Match Type",
        "Clicks",
        "Impressions",
        "Cost",
        "Conversions",
        "Conv. Rate",
        "Cost / Conv.",
        "CPC",
        "CTR",
        "Impression Share",
        "Geographic Location",
        "Location Type",
        "Is Local Intent",
    ]

    print("📊 Column Comparison:")
    print(f"   UI Export columns: {len(expected_columns['search_terms_ui_export'])}")
    print(f"   Script columns: {len(script_columns)}")

    # Find differences
    ui_cols = set(expected_columns["search_terms_ui_export"])
    script_cols = set(script_columns)

    missing_from_script = ui_cols - script_cols
    extra_in_script = script_cols - ui_cols

    if missing_from_script:
        print(f"   ⚠️  Missing from script: {missing_from_script}")

    if extra_in_script:
        print(f"   ℹ️  Extra in script: {extra_in_script}")

    common_cols = ui_cols & script_cols
    print(f"   ✅ Common columns: {len(common_cols)}")

    # Check for potential header inconsistencies
    print("\n🚨 Potential Issues to Watch For:")
    print("   • UI exports may have different headers per account")
    print("   • Date formats might differ between UI and API")
    print("   • Currency formatting could vary")
    print("   • Geographic data may not be in UI exports")
    print("   • Match type representation might differ")


def main():
    """Main test execution."""
    print("🚀 Testing PR #476 Quarterly Data Extraction Scripts")
    print("=" * 80)
    print(f"📅 Test run: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("🎯 Goal: Generate Search Terms Performance Scripts for validation")
    print()

    # Generate scripts for both accounts
    fitness_result = create_fitness_connection_script()
    cotton_patch_result = create_cotton_patch_script()

    # Analyze the results
    issues = analyze_generated_scripts(fitness_result, cotton_patch_result)

    # Save scripts to files
    save_scripts_to_files(fitness_result, cotton_patch_result)

    # Compare with expected UI formats
    compare_with_ui_extracts()

    # Final summary
    print("\n📋 Test Summary")
    print("=" * 30)

    if issues:
        print(f"❌ Found {len(issues)} issues:")
        for issue in issues:
            print(f"   {issue}")
    else:
        print("✅ No critical issues found!")

    print("\n📊 Results:")
    print(
        f"   • Fitness Connection script: {'✅ Generated' if fitness_result else '❌ Failed'}"
    )
    print(
        f"   • Cotton Patch Cafe script: {'✅ Generated' if cotton_patch_result else '❌ Failed'}"
    )

    success_count = sum(
        [1 for result in [fitness_result, cotton_patch_result] if result]
    )
    print(f"   • Success rate: {success_count}/2 ({success_count / 2 * 100:.0f}%)")

    print("\n💡 Next Steps:")
    print("   1. Review generated JavaScript files")
    print("   2. Test script execution in Google Ads Scripts environment")
    print("   3. Compare output format with UI extracts")
    print("   4. Validate local intent detection accuracy")
    print("   5. Check geographic data inclusion")

    return len(issues) == 0


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
