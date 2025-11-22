#!/usr/bin/env python3
"""Test device performance CSV parsing and analysis."""

import asyncio
import os
import sys

# Add the project root to the path
sys.path.insert(0, "/Users/robertwelborn/PycharmProjects/PaidSearchNav")


async def test_device_s3():
    """Test device performance with S3 files."""
    print("📱 Testing S3-based device performance analysis...")

    # Actual Fitness Connection device report file
    device_files = {
        "device": "s3://paidsearchnav-customer-data-dev/ret/fitness-connection_2879C12F-C38/inputs/Device report (2).csv"
    }

    try:
        from paidsearchnav.api.v1.s3_analysis import process_multiple_s3_files

        print("📥 Attempting to download and process device file...")

        # Set AWS credentials
        os.environ.setdefault("AWS_PROFILE", os.getenv("AWS_PROFILE", "default"))
        os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")

        processed_data, temp_files = await process_multiple_s3_files(device_files)

        if "device" in processed_data:
            records = processed_data["device"]
            print(
                f"✅ Successfully processed {len(records)} device performance records from S3"
            )

            if records:
                print("\n📱 Device performance breakdown:")
                devices = {}
                total_cost = 0.0

                for record in records:
                    # Handle both dict and Pydantic model objects
                    if hasattr(record, "device"):
                        device_type = getattr(record, "device", "Unknown")
                        cost = getattr(record, "cost", 0)
                        impressions = getattr(record, "impressions", 0)
                        clicks = getattr(record, "clicks", 0)
                    else:
                        device_type = record.get("device", "Unknown")
                        cost = record.get("cost", 0)
                        impressions = record.get("impressions", 0)
                        clicks = record.get("clicks", 0)

                    if device_type not in devices:
                        devices[device_type] = {
                            "cost": 0,
                            "impressions": 0,
                            "clicks": 0,
                            "records": 0,
                        }

                    # Handle commas in numeric values
                    cost_val = str(cost).replace(",", "") if cost else "0"
                    impr_val = str(impressions).replace(",", "") if impressions else "0"
                    clicks_val = str(clicks).replace(",", "") if clicks else "0"

                    devices[device_type]["cost"] += float(cost_val)
                    devices[device_type]["impressions"] += int(float(impr_val))
                    devices[device_type]["clicks"] += int(float(clicks_val))
                    devices[device_type]["records"] += 1
                    total_cost += float(cost_val)

                for device, stats in devices.items():
                    cost_pct = (
                        (stats["cost"] / total_cost * 100) if total_cost > 0 else 0
                    )
                    ctr = (
                        (stats["clicks"] / stats["impressions"] * 100)
                        if stats["impressions"] > 0
                        else 0
                    )
                    print(
                        f"  • {device}: ${stats['cost']:,.2f} ({cost_pct:.1f}%) - {stats['impressions']:,} impr, {stats['clicks']:,} clicks (CTR: {ctr:.2f}%)"
                    )

                print("\n📈 Device Summary:")
                print(f"  • Total Records: {len(records)}")
                print(f"  • Device Types: {len(devices)}")
                print(f"  • Total Cost: ${total_cost:,.2f}")

        # Cleanup
        for temp_file in temp_files:
            if temp_file and temp_file.exists():
                temp_file.unlink()

        return True

    except Exception as e:
        print(f"❌ S3 device test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("🚀 Starting Device Performance Testing...")

    # Test S3 processing
    success = asyncio.run(test_device_s3())

    if success:
        print("\n✨ SUCCESS: Device performance testing completed!")
        print("   Ready to test next CSV parser type.")
    else:
        print("\n💥 FAILED: Device performance testing had issues.")
        print("   Please check the device report format.")

    sys.exit(0 if success else 1)
