#!/usr/bin/env python3
"""Test per_store (local performance) CSV parsing and analysis."""

import asyncio
import os
import sys

# Add the project root to the path
sys.path.insert(0, "/Users/robertwelborn/PycharmProjects/PaidSearchNav")


async def test_per_store_s3():
    """Test per_store performance with S3 files."""
    print("🏪 Testing S3-based per store performance analysis...")

    # Actual Fitness Connection per store report file
    per_store_files = {
        "per_store": "s3://paidsearchnav-customer-data-dev/ret/fitness-connection_2879C12F-C38/inputs/perstorereport.csv"
    }

    try:
        from paidsearchnav.api.v1.s3_analysis import process_multiple_s3_files

        print("📥 Attempting to download and process per store file...")

        # Set AWS credentials
        os.environ.setdefault("AWS_PROFILE", os.getenv("AWS_PROFILE", "default"))
        os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")

        processed_data, temp_files = await process_multiple_s3_files(per_store_files)

        if "per_store" in processed_data:
            records = processed_data["per_store"]
            print(f"✅ Successfully processed {len(records)} per store records from S3")

            if records:
                print("\n🏪 Store performance breakdown:")
                stores = {}

                for record in records[:15]:  # Show first 15 stores
                    # Handle both dict and Pydantic model objects
                    if hasattr(record, "store_name"):
                        store_name = getattr(record, "store_name", "Unknown")
                        city = getattr(record, "city", "")
                        state = getattr(record, "state", "")
                        local_impressions = getattr(record, "local_impressions", 0)
                        store_visits = getattr(record, "store_visits", 0)
                    else:
                        store_name = record.get(
                            "store_name", record.get("store_locations", "Unknown")
                        )
                        city = record.get("city", "")
                        state = record.get("state", record.get("province", ""))
                        local_impressions = record.get("local_impressions", 0)
                        store_visits = record.get("store_visits", 0)

                    location = f"{city}, {state}".strip(", ")
                    if not location:
                        location = "Unknown Location"

                    print(f"  • {store_name} ({location})")

                    # Handle string values that might contain commas
                    try:
                        local_impr_val = (
                            int(str(local_impressions).replace(",", ""))
                            if local_impressions
                            else 0
                        )
                        visits_val = (
                            int(str(store_visits).replace(",", ""))
                            if store_visits
                            else 0
                        )
                        print(f"    - Local Impressions: {local_impr_val:,}")
                        print(f"    - Store Visits: {visits_val:,}")
                    except (ValueError, TypeError):
                        print(f"    - Local Impressions: {local_impressions}")
                        print(f"    - Store Visits: {store_visits}")

                # Summary stats
                total_stores = len(records)
                total_local_impressions = 0
                total_store_visits = 0

                for r in records:
                    if hasattr(r, "local_impressions"):
                        local_impr = getattr(r, "local_impressions", 0)
                        visits = getattr(r, "store_visits", 0)
                    else:
                        local_impr = r.get("local_impressions", 0)
                        visits = r.get("store_visits", 0)

                    try:
                        local_impr_val = (
                            int(str(local_impr).replace(",", "")) if local_impr else 0
                        )
                        visits_val = int(str(visits).replace(",", "")) if visits else 0
                        total_local_impressions += local_impr_val
                        total_store_visits += visits_val
                    except (ValueError, TypeError):
                        pass  # Skip invalid values

                print("\n📈 Store Performance Summary:")
                print(f"  • Total Stores: {total_stores}")
                print(f"  • Total Local Impressions: {total_local_impressions:,}")
                print(f"  • Total Store Visits: {total_store_visits:,}")

                visit_rate = (
                    (total_store_visits / total_local_impressions * 100)
                    if total_local_impressions > 0
                    else 0
                )
                print(f"  • Visit Rate: {visit_rate:.2f}%")

        # Cleanup
        for temp_file in temp_files:
            if temp_file and temp_file.exists():
                temp_file.unlink()

        return True

    except Exception as e:
        print(f"❌ S3 per store test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("🚀 Starting Per Store Performance Testing...")

    # Test S3 processing
    success = asyncio.run(test_per_store_s3())

    if success:
        print("\n✨ SUCCESS: Per store performance testing completed!")
        print("   Ready to test next CSV parser type.")
    else:
        print("\n💥 FAILED: Per store performance testing had issues.")
        print("   Please check the per store report format.")

    sys.exit(0 if success else 1)
