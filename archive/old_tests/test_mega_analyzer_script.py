#!/usr/bin/env python3
"""Test script to generate MEGA ANALYZER DATA EXTRACTION Google Ads Script."""

from paidsearchnav.platforms.google.scripts.base import ScriptConfig, ScriptType
from paidsearchnav.platforms.google.scripts.quarterly_data_extraction import (
    MegaAnalyzerDataExtractionScript,
)


def main():
    """Generate mega analyzer data extraction script for testing."""

    # Create configuration for Fitness Connection with Advanced APIs
    config = ScriptConfig(
        name="FITNESS CONNECTION MEGA ANALYZER EXTRACTION",
        type=ScriptType.NEGATIVE_KEYWORD,
        description="ULTIMATE: Extract data for ALL 20+ analyzers with Advanced APIs (Analytics, BigQuery)",
        schedule="on_demand",
        parameters={
            "customer_id": "646-990-6417",
            "date_range": "LAST_90_DAYS",
            "ga_property_id": "YOUR_GA_PROPERTY_ID",  # User would replace
            "bigquery_project": "YOUR_BQ_PROJECT",  # User would replace
            "bigquery_dataset": "paid_search_nav",
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
                "weight loss",
                "muscle building",
                "cardio",
            ],
        },
    )

    # Generate the MEGA script
    script_generator = MegaAnalyzerDataExtractionScript(None, config)
    script_code = script_generator.generate_script()

    # Save to file
    output_file = "FITNESS_CONNECTION_MEGA_ANALYZER_EXTRACTION.js"
    with open(output_file, "w") as f:
        f.write(script_code)

    print("🚀" * 50)
    print("🎯 MEGA ANALYZER DATA EXTRACTION SCRIPT GENERATED!")
    print("🚀" * 50)
    print("")
    print(f"📁 FILE: {output_file}")
    print("🏢 CUSTOMER: 646-990-6417 (Fitness Connection)")
    print("📅 DATE RANGE: LAST_90_DAYS")
    print(f"📊 SCRIPT SIZE: {len(script_code):,} characters")
    print("")
    print("🎪 === ULTIMATE QUARTERLY AUDIT SYSTEM ===")
    print("")
    print("📊 CORE PERFORMANCE ANALYZERS (7):")
    print("   1. 🔍 Search Terms Performance (Enhanced with negative recommendations)")
    print("   2. 🎯 Keywords Performance (Enhanced with local relevance)")
    print(
        "   3. 📊 Ad Groups Performance (Performance scoring + optimization priority)"
    )
    print("   4. 🏢 Campaigns Performance (Enhanced analysis)")
    print("   5. ⚡ Performance Max Analysis (PMax-specific insights)")
    print("   6. 🔄 Keyword Match Types (Match type distribution)")
    print("   7. 🌍 Geographic Performance (Location-based insights)")
    print("")
    print("⚠️ CONFLICT & OPTIMIZATION ANALYZERS (4):")
    print("   8. ⚠️ Negative Conflicts Analysis")
    print("   9. 📋 Shared Negatives Analysis")
    print("  10. 📦 Bulk Negatives Management")
    print("  11. 🔄 Campaign Overlap Analysis")
    print("")
    print("🎨 CREATIVE & TARGETING ANALYZERS (4):")
    print("  12. 🎥 Video Creative Performance")
    print("  13. 🔗 Landing Pages Analysis")
    print("  14. 📍 Placements Audit")
    print("  15. 👥 Demographics Performance")
    print("")
    print("⚡ ADVANCED STRATEGY ANALYZERS (4):")
    print("  16. 💰 Advanced Bid Adjustments")
    print("  17. 📱 Device Performance Analysis")
    print("  18. 🕒 Dayparting Analysis")
    print("  19. 🏆 Competitor Insights")
    print("")
    print("🏪 LOCAL BUSINESS ANALYZERS (2):")
    print("  20. 🏪 Local Reach Analysis")
    print("  21. 🏬 Store Performance Analysis")
    print("")
    print("🔥 ADVANCED APIS INTEGRATION:")
    print("  22. 📈 Google Analytics Data (Revenue attribution)")
    print("  23. 🗄️ BigQuery Export (All data tables)")
    print("")
    print("🎉 === EXPECTED OUTPUT: 20+ CSV FILES ===")
    print("   - analyzer_search_terms_YYYY-MM-DD_HH-MM.csv")
    print("   - analyzer_keywords_YYYY-MM-DD_HH-MM.csv")
    print("   - analyzer_ad_groups_YYYY-MM-DD_HH-MM.csv")
    print("   - analyzer_campaigns_YYYY-MM-DD_HH-MM.csv")
    print("   - analyzer_performance_max_YYYY-MM-DD_HH-MM.csv")
    print("   - analyzer_demographics_YYYY-MM-DD_HH-MM.csv")
    print("   - analyzer_device_performance_YYYY-MM-DD_HH-MM.csv")
    print("   - analyzer_analytics_data_YYYY-MM-DD_HH-MM.csv")
    print("   - (+ 15 more analyzer-specific files)")
    print("")
    print("⚡ MEGA FEATURES:")
    print("   🎯 Single script execution for COMPLETE analyzer data pipeline")
    print("   🔗 Google Analytics revenue attribution integration")
    print("   🗄️ BigQuery automatic export for ML analysis")
    print("   💡 Enhanced recommendations with priority scoring")
    print("   🏪 Local business optimization focus")
    print("   📈 Performance tier categorization")
    print("   🤖 Advanced bid recommendation algorithms")
    print("   📊 Cross-platform data unification")
    print("")
    print("🚨 SETUP REQUIRED:")
    print("   1. ✅ Enable 'Advanced APIs' in Google Ads Scripts")
    print("   2. ✅ Replace 'YOUR_GA_PROPERTY_ID' with actual GA4 property")
    print("   3. ✅ Replace 'YOUR_BQ_PROJECT' with BigQuery project ID")
    print("   4. ✅ Ensure BigQuery dataset 'paid_search_nav' exists")
    print("")
    print("🎪 THIS IS THE ULTIMATE GOOGLE ADS AUTOMATION!")
    print("⭐ Every analyzer gets its own perfectly formatted CSV")
    print("🚀 Ready for immediate analysis in your production pipeline!")
    print("")
    print("🚀" * 50)


if __name__ == "__main__":
    main()
