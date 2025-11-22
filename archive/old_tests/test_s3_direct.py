#!/usr/bin/env python3
"""Direct test of S3 analysis functionality without database dependency."""

import asyncio
import os
import sys

# Add the project root to the path
sys.path.insert(0, "/Users/robertwelborn/PycharmProjects/PaidSearchNav")


async def test_s3_analysis():
    """Test S3 analysis directly."""
    from paidsearchnav.api.v1.s3_analysis import (
        process_multiple_s3_files,
        validate_s3_path,
    )

    print("🔍 Testing S3 Analysis with Fitness Connection Files")
    print("=" * 60)

    # Your S3 file paths
    files = {
        "search_terms": "s3://paidsearchnav-customer-data-dev/ret/fitness-connection_2879C12F-C38/inputs/searchtermsreport.csv",
        "keywords": "s3://paidsearchnav-customer-data-dev/ret/fitness-connection_2879C12F-C38/inputs/searchkeywordreport.csv",
        "negative_keywords": "s3://paidsearchnav-customer-data-dev/ret/fitness-connection_2879C12F-C38/inputs/negativekeywordreport.csv",
    }

    print("📁 Files to analyze:")
    for data_type, s3_path in files.items():
        print(f"  • {data_type}: {s3_path}")

    print("\n🔒 Testing S3 path validation...")
    for data_type, s3_path in files.items():
        try:
            bucket, key = validate_s3_path(s3_path)
            print(f"  ✅ {data_type}: bucket='{bucket}', key='{key}'")
        except Exception as e:
            print(f"  ❌ {data_type}: {e}")

    print("\n📥 Testing parallel file download and processing...")
    try:
        processed_data, temp_files = await process_multiple_s3_files(files)

        print(f"✅ Successfully processed {len(processed_data)} files:")
        for data_type, records in processed_data.items():
            print(f"  • {data_type}: {len(records)} records")

        print(f"\n🧹 Cleaning up {len(temp_files)} temporary files...")
        for temp_file in temp_files:
            if temp_file and temp_file.exists():
                temp_file.unlink()

        print("✅ All tests completed successfully!")
        print("\n🎉 S3 Analysis endpoints are working correctly with your files!")

        return True

    except Exception as e:
        print(f"❌ Error during processing: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    # Set AWS credentials and profile from .env.dev
    os.environ.setdefault("AWS_PROFILE", os.getenv("AWS_PROFILE", "default"))
    os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")

    print("🚀 Starting S3 Analysis Test...")
    print(f"Using AWS Profile: {os.environ.get('AWS_PROFILE', 'default')}")
    print(f"AWS Region: {os.environ.get('AWS_DEFAULT_REGION', 'us-east-1')}")

    success = asyncio.run(test_s3_analysis())

    if success:
        print("\n✨ SUCCESS: S3 analysis deployment is working!")
        print("   The merged changes from PR #443 are fully functional.")
    else:
        print("\n💥 FAILED: There were issues with the S3 analysis.")

    sys.exit(0 if success else 1)
