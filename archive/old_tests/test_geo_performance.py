#!/usr/bin/env python3
"""Test geo_performance CSV parsing and analysis."""

import asyncio
import os
import sys
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, "/Users/robertwelborn/PycharmProjects/PaidSearchNav")


async def test_geo_performance_parsing():
    """Test geo_performance CSV parsing with sample data."""

    from paidsearchnav.parsers.csv_parser import CSVParser

    print("🌍 Testing Geo Performance CSV Parsing")
    print("=" * 50)

    # Check if you have a geo performance file
    test_files = [
        "geo_performance_report.csv",
        "location_report.csv",
        "geographic_report.csv",
    ]

    test_file = None
    for filename in test_files:
        if Path(filename).exists():
            test_file = Path(filename)
            break

    if not test_file:
        print("📁 No geo performance test file found. Expected files:")
        for filename in test_files:
            print(f"  • {filename}")
        print("\n💡 Please provide a Google Ads Geographic/Location report CSV file")
        return False

    print(f"📄 Using test file: {test_file}")

    # Test CSV parsing
    print("\n🔍 Testing CSV parsing...")
    try:
        parser = CSVParser()

        # Parse the CSV file
        parsed_data = parser.parse_csv(test_file, "geo_performance")

        print(f"✅ Successfully parsed {len(parsed_data)} geo performance records")

        if parsed_data:
            # Show sample record
            sample = parsed_data[0]
            print("\n📋 Sample record fields:")
            for key, value in sample.items():
                print(f"  • {key}: {value}")

            # Test required fields
            required_fields = [
                "location_name",
                "geographic_level",
                "customer_id",
                "campaign_id",
                "campaign_name",
            ]
            missing_fields = [field for field in required_fields if field not in sample]

            if missing_fields:
                print(f"\n⚠️  Missing required fields: {missing_fields}")
            else:
                print("\n✅ All required fields present")

        return True

    except Exception as e:
        print(f"❌ CSV parsing failed: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_geo_performance_s3():
    """Test geo_performance with S3 files if available."""
    print("\n🗳️ Testing S3-based geo performance analysis...")

    # Actual Fitness Connection location report file
    geo_files = {
        "geo_performance": "s3://paidsearchnav-customer-data-dev/ret/fitness-connection_2879C12F-C38/inputs/locationreport.csv"
    }

    try:
        from paidsearchnav.api.v1.s3_analysis import process_multiple_s3_files

        print("📥 Attempting to download and process geo performance file...")

        # Set AWS credentials
        os.environ.setdefault("AWS_PROFILE", os.getenv("AWS_PROFILE", "default"))
        os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")

        processed_data, temp_files = await process_multiple_s3_files(geo_files)

        if "geo_performance" in processed_data:
            records = processed_data["geo_performance"]
            print(
                f"✅ Successfully processed {len(records)} geo performance records from S3"
            )

            if records:
                print("\n📍 Sample locations:")
                locations = set()
                for record in records[:10]:  # Show first 10 locations
                    if "location_name" in record:
                        locations.add(record["location_name"])

                for location in sorted(locations):
                    print(f"  • {location}")

        # Cleanup
        for temp_file in temp_files:
            if temp_file and temp_file.exists():
                temp_file.unlink()

        return True

    except Exception as e:
        print(f"❌ S3 geo performance test failed: {e}")
        return False


if __name__ == "__main__":
    print("🚀 Starting Geo Performance Testing...")

    # Test local CSV parsing first
    success1 = asyncio.run(test_geo_performance_parsing())

    # Test S3 processing if available
    success2 = asyncio.run(test_geo_performance_s3())

    if success1 or success2:
        print("\n✨ SUCCESS: Geo performance testing completed!")
        print("   Ready to test next CSV parser type.")
    else:
        print("\n💥 FAILED: Geo performance testing had issues.")
        print("   Please provide a valid Geographic/Location report CSV file.")

    sys.exit(0 if (success1 or success2) else 1)
