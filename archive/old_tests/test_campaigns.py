#!/usr/bin/env python3
"""Test campaigns CSV parsing and analysis."""

import asyncio
import os
import sys
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, "/Users/robertwelborn/PycharmProjects/PaidSearchNav")


async def test_campaigns_parsing():
    """Test campaigns CSV parsing with sample data."""

    from paidsearchnav.parsers.csv_parser import CSVParser

    print("🚀 Testing Campaigns CSV Parsing")
    print("=" * 45)

    # Check if you have a campaigns file locally
    test_files = ["campaign_report.csv", "campaigns_report.csv", "campaignreport.csv"]

    test_file = None
    for filename in test_files:
        if Path(filename).exists():
            test_file = Path(filename)
            break

    if not test_file:
        print("📁 No campaigns test file found. Expected files:")
        for filename in test_files:
            print(f"  • {filename}")
        print("\n💡 Please provide a Google Ads Campaign report CSV file")
        return False

    print(f"📄 Using test file: {test_file}")

    # Test CSV parsing
    print("\n🔍 Testing CSV parsing...")
    try:
        parser = CSVParser()

        # Parse the CSV file
        parsed_data = parser.parse_csv(test_file, "campaigns")

        print(f"✅ Successfully parsed {len(parsed_data)} campaign records")

        if parsed_data:
            # Show sample record
            sample = parsed_data[0]
            print("\n📋 Sample record fields:")
            for key, value in sample.items():
                print(f"  • {key}: {value}")

            # Test required fields for campaigns
            required_fields = ["campaign_name", "campaign_state"]
            missing_fields = [field for field in required_fields if field not in sample]

            if missing_fields:
                print(f"\n⚠️  Missing required fields: {missing_fields}")
            else:
                print("\n✅ All required fields present")

            # Show campaign insights
            if len(parsed_data) > 1:
                print("\n📊 Campaign insights:")
                campaign_names = [
                    record.get("campaign_name", "N/A") for record in parsed_data[:5]
                ]
                for name in campaign_names:
                    print(f"  • {name}")

        return True

    except Exception as e:
        print(f"❌ CSV parsing failed: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_campaigns_s3():
    """Test campaigns with S3 files."""
    print("\n📊 Testing S3-based campaigns analysis...")

    # Actual Fitness Connection campaign report file
    campaigns_files = {
        "campaigns": "s3://paidsearchnav-customer-data-dev/ret/fitness-connection_2879C12F-C38/inputs/campaignreport.csv"
    }

    try:
        from paidsearchnav.api.v1.s3_analysis import process_multiple_s3_files

        print("📥 Attempting to download and process campaigns file...")

        # Set AWS credentials
        os.environ.setdefault("AWS_PROFILE", os.getenv("AWS_PROFILE", "default"))
        os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")

        processed_data, temp_files = await process_multiple_s3_files(campaigns_files)

        if "campaigns" in processed_data:
            records = processed_data["campaigns"]
            print(f"✅ Successfully processed {len(records)} campaign records from S3")

            if records:
                print("\n🎯 Sample campaigns:")
                campaigns = []
                for record in records[:10]:  # Show first 10 campaigns
                    # Handle both dict and Pydantic model objects
                    if hasattr(record, "name"):
                        # Pydantic model object - Campaign model uses 'name' not 'campaign_name'
                        campaign_name = getattr(record, "name", "Unknown")
                        status = getattr(record, "status", "Unknown")
                        cost = getattr(record, "cost", 0)
                    else:
                        # Dictionary object
                        campaign_name = record.get(
                            "name", record.get("campaign_name", "Unknown")
                        )
                        status = record.get(
                            "status", record.get("campaign_state", "Unknown")
                        )
                        cost = record.get("cost", 0)
                    campaigns.append((campaign_name, status, cost))

                for name, status, cost in campaigns:
                    cost_str = (
                        f"${cost:,.2f}"
                        if isinstance(cost, (int, float))
                        else f"${cost}"
                    )
                    print(f"  • {name} [{status}] - {cost_str}")

                # Show summary stats
                total_campaigns = len(records)
                enabled_campaigns = 0
                total_cost = 0.0

                for r in records:
                    if hasattr(r, "status"):
                        if getattr(r, "status", "") == "ENABLED":
                            enabled_campaigns += 1
                        cost_val = getattr(r, "cost", 0)
                    else:
                        if r.get("status", r.get("campaign_state", "")) == "ENABLED":
                            enabled_campaigns += 1
                        cost_val = r.get("cost", 0)

                    if cost_val:
                        total_cost += float(cost_val)

                print("\n📈 Campaign Summary:")
                print(f"  • Total Campaigns: {total_campaigns}")
                print(f"  • Enabled Campaigns: {enabled_campaigns}")
                print(f"  • Total Cost: ${total_cost:,.2f}")

        # Cleanup
        for temp_file in temp_files:
            if temp_file and temp_file.exists():
                temp_file.unlink()

        return True

    except Exception as e:
        print(f"❌ S3 campaigns test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("🚀 Starting Campaigns Testing...")

    # Test local CSV parsing first
    success1 = asyncio.run(test_campaigns_parsing())

    # Test S3 processing
    success2 = asyncio.run(test_campaigns_s3())

    if success1 or success2:
        print("\n✨ SUCCESS: Campaigns testing completed!")
        print("   Ready to test next CSV parser type.")
    else:
        print("\n💥 FAILED: Campaigns testing had issues.")
        print("   Please check the campaign report format.")

    sys.exit(0 if (success1 or success2) else 1)
