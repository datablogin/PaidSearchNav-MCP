#!/usr/bin/env python3
"""Test ad_groups CSV parsing and analysis."""

import asyncio
import os
import sys

# Add the project root to the path
sys.path.insert(0, "/Users/robertwelborn/PycharmProjects/PaidSearchNav")


async def test_ad_groups_s3():
    """Test ad_groups with S3 files."""
    print("📊 Testing S3-based ad groups analysis...")

    # Actual Fitness Connection ad group report file
    ad_groups_files = {
        "ad_groups": "s3://paidsearchnav-customer-data-dev/ret/fitness-connection_2879C12F-C38/inputs/Ad group report (2).csv"
    }

    try:
        from paidsearchnav.api.v1.s3_analysis import process_multiple_s3_files

        print("📥 Attempting to download and process ad groups file...")

        # Set AWS credentials
        os.environ.setdefault("AWS_PROFILE", os.getenv("AWS_PROFILE", "default"))
        os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")

        processed_data, temp_files = await process_multiple_s3_files(ad_groups_files)

        if "ad_groups" in processed_data:
            records = processed_data["ad_groups"]
            print(f"✅ Successfully processed {len(records)} ad group records from S3")

            if records:
                print("\n🎯 Sample ad groups:")
                ad_groups = []
                for record in records[:10]:  # Show first 10 ad groups
                    # Handle both dict and Pydantic model objects
                    if hasattr(record, "name"):
                        # Pydantic model object
                        ad_group_name = getattr(record, "name", "Unknown")
                        campaign_name = getattr(record, "campaign_name", "Unknown")
                        status = getattr(record, "status", "Unknown")
                        cost = getattr(record, "cost", 0)
                    else:
                        # Dictionary object
                        ad_group_name = record.get(
                            "name", record.get("ad_group_name", "Unknown")
                        )
                        campaign_name = record.get(
                            "campaign_name", record.get("campaign", "Unknown")
                        )
                        status = record.get(
                            "status", record.get("ad_group_state", "Unknown")
                        )
                        cost = record.get("cost", 0)
                    ad_groups.append((ad_group_name, campaign_name, status, cost))

                for name, campaign, status, cost in ad_groups:
                    cost_str = (
                        f"${cost:,.2f}"
                        if isinstance(cost, (int, float))
                        else f"${cost}"
                    )
                    print(f"  • {name} [{status}] ({campaign}) - {cost_str}")

                # Show summary stats
                total_ad_groups = len(records)
                enabled_ad_groups = 0
                total_cost = 0.0

                for r in records:
                    if hasattr(r, "status"):
                        if getattr(r, "status", "") == "ENABLED":
                            enabled_ad_groups += 1
                        cost_val = getattr(r, "cost", 0)
                    else:
                        if r.get("status", r.get("ad_group_state", "")) == "ENABLED":
                            enabled_ad_groups += 1
                        cost_val = r.get("cost", 0)

                    if cost_val:
                        total_cost += float(cost_val)

                print("\n📈 Ad Group Summary:")
                print(f"  • Total Ad Groups: {total_ad_groups}")
                print(f"  • Enabled Ad Groups: {enabled_ad_groups}")
                print(f"  • Total Cost: ${total_cost:,.2f}")

        # Cleanup
        for temp_file in temp_files:
            if temp_file and temp_file.exists():
                temp_file.unlink()

        return True

    except Exception as e:
        print(f"❌ S3 ad groups test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("🚀 Starting Ad Groups Testing...")

    # Test S3 processing
    success = asyncio.run(test_ad_groups_s3())

    if success:
        print("\n✨ SUCCESS: Ad Groups testing completed!")
        print("   Ready to test next CSV parser type.")
    else:
        print("\n💥 FAILED: Ad Groups testing had issues.")
        print("   Please check the ad group report format.")

    sys.exit(0 if success else 1)
