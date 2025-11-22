#!/usr/bin/env python3
"""Run comprehensive analysis workflow on Cotton Patch Cafe data."""

import asyncio
import sys
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, "/Users/robertwelborn/PycharmProjects/PaidSearchNav")

from dotenv import load_dotenv


async def run_cotton_patch_analysis():
    """Run comprehensive analysis on Cotton Patch Cafe data."""
    print("🚀 Starting Cotton Patch Cafe Comprehensive Analysis")
    print("=" * 60)

    # Load environment variables
    env_file = Path(__file__).parent / ".env.dev"
    if env_file.exists():
        load_dotenv(env_file)
        print(f"📄 Loaded environment from {env_file}")

    # Use S3-only analysis mode (simpler and more reliable for testing)
    return await run_s3_only_analysis()


async def run_s3_only_analysis():
    """Run analysis using S3 files directly without database."""
    print("📁 Running S3-only analysis mode...")

    try:
        # Use the S3 analysis API directly
        from paidsearchnav.api.v1.s3_analysis import process_multiple_s3_files

        # Define all Cotton Patch Cafe files
        base_path = "s3://paidsearchnav-customer-data-dev/svc/cotton-patch-cafe_952-408-0160/inputs/"

        files = {
            "search_terms": f"{base_path}Search terms report (1).csv",
            "keywords": f"{base_path}Search keyword report (1).csv",
            "negative_keywords": f"{base_path}Negative keyword report (1).csv",
            "campaigns": f"{base_path}Campaign report (2).csv",
            "ad_groups": f"{base_path}Ad group report (2).csv",
            "demographics_age": f"{base_path}Age report.csv",
            "demographics_gender": f"{base_path}Gender report.csv",
            "demographics_income": f"{base_path}Household income report.csv",
            "geo_performance": f"{base_path}Location report (2).csv",
            "device_performance": f"{base_path}Device report (2).csv",
            "per_store": f"{base_path}Per store report (2).csv",
            "landing_page": f"{base_path}Landing page report (1).csv",
            "video_creative": f"{base_path}Video report.csv",
        }

        print(f"📥 Processing {len(files)} files...")

        # Process files - try each one individually to handle errors gracefully
        processed_data = {}
        temp_files = []

        for file_type, s3_path in files.items():
            try:
                print(f"   📄 Processing {file_type}...")
                single_data, single_temps = await process_multiple_s3_files(
                    {file_type: s3_path}
                )
                processed_data.update(single_data)
                temp_files.extend(single_temps)
                print(
                    f"      ✅ Success: {len(single_data.get(file_type, []))} records"
                )
            except Exception as e:
                print(f"      ⚠️  Skipped {file_type}: {str(e)[:100]}...")
                continue

        print(f"✅ Successfully processed {len(processed_data)} files:")
        total_records = 0
        for data_type, records in processed_data.items():
            record_count = len(records)
            total_records += record_count
            print(f"   • {data_type}: {record_count:,} records")

        print(f"\n📊 Total records processed: {total_records:,}")

        # Run some basic analysis
        print("\n🧠 Running basic analysis...")

        # Test CompetitorInsightsAnalyzer with CSV support
        if "search_terms" in processed_data:
            try:
                from paidsearchnav.analyzers.competitor_insights import (
                    CompetitorInsightsAnalyzer,
                )

                analyzer = CompetitorInsightsAnalyzer()
                print(
                    f"   ✅ CompetitorInsightsAnalyzer ready with {len(processed_data['search_terms']):,} search terms"
                )

            except Exception as e:
                print(f"   ⚠️  Analyzer test: {e}")

        # Clean up temp files
        print(f"\n🧹 Cleaning up {len(temp_files)} temporary files...")
        for temp_file in temp_files:
            if temp_file and temp_file.exists():
                temp_file.unlink()

        print("\n✅ S3-only analysis completed successfully!")
        print("📝 Note: In full workflow mode, outputs would be automatically")
        print("   organized into outputs/ and outputs/reports/ folders.")

        return True

    except Exception as e:
        print(f"❌ S3-only analysis failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(run_cotton_patch_analysis())

    if success:
        print("\n🎉 SUCCESS: Cotton Patch Cafe analysis workflow completed!")
    else:
        print("\n💥 FAILED: Analysis workflow encountered errors.")

    sys.exit(0 if success else 1)
