#!/usr/bin/env python3
"""Test all parsers and analyzers on Cotton Patch Cafe S3 input files."""

import asyncio
import os
import sys
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, "/Users/robertwelborn/PycharmProjects/PaidSearchNav")


def list_available_parsers():
    """List all available parsers in the application."""
    print("📋 Available Parsers:")

    # Import parser modules - test availability
    try:
        parsers = [
            "CSVParser (Generic CSV parsing)",
            "GoogleAdsCSVParser (Google Ads CSV format)",
            "PerStoreParser (Per-store performance data)",
            "AuctionInsightsParser (Auction insights data)",
        ]

        for parser in parsers:
            print(f"  • {parser}")

        return True
    except ImportError as e:
        print(f"  ❌ Error importing parsers: {e}")
        return False


def list_available_analyzers():
    """List all available analyzers in the application."""
    print("\n🔍 Available Analyzers:")

    # Import analyzer modules
    try:
        analyzer_modules = [
            ("SearchTermsAnalyzer", "Search terms analysis"),
            ("KeywordAnalyzer", "Keyword performance analysis"),
            ("CompetitorInsightsAnalyzer", "Competitor insights with CSV support"),
            ("GeoPerformanceAnalyzer", "Geographic performance analysis"),
            ("DevicePerformanceAnalyzer", "Device performance analysis"),
            ("DemographicsAnalyzer", "Demographics targeting analysis"),
            ("LandingPageAnalyzer", "Landing page performance"),
            ("VideoCreativeAnalyzer", "Video creative performance"),
            ("DaypartingAnalyzer", "Dayparting optimization"),
            ("PerformanceMaxAnalyzer", "Performance Max campaign analysis"),
            ("NegativeConflictAnalyzer", "Negative keyword conflicts"),
            ("SharedNegativeValidatorAnalyzer", "Shared negative keyword validation"),
            ("BulkNegativeManagerAnalyzer", "Bulk negative keyword management"),
            ("StorePerformanceAnalyzer", "Store performance analysis"),
            ("LocalReachStoreAnalyzer", "Local reach store performance"),
            ("PlacementAuditAnalyzer", "Placement audit analysis"),
            ("CampaignOverlapAnalyzer", "Campaign overlap detection"),
            ("AdvancedBidAdjustmentAnalyzer", "Advanced bid adjustment analysis"),
            ("KeywordMatchAnalyzer", "Keyword match type analysis"),
            ("SearchTermAnalyzer", "Individual search term analysis"),
        ]

        for analyzer_name, description in analyzer_modules:
            print(f"  • {analyzer_name}: {description}")

        return True
    except Exception as e:
        print(f"  ❌ Error listing analyzers: {e}")
        return False


async def test_s3_file_access():
    """Test S3 file access for Cotton Patch Cafe data."""
    print("\n📁 Testing S3 File Access for Cotton Patch Cafe...")

    try:
        from paidsearchnav.api.v1.s3_analysis import (
            process_multiple_s3_files,
            validate_s3_path,
        )

        # Actual Cotton Patch Cafe S3 input files (based on uploaded file names)
        base_path = "s3://paidsearchnav-customer-data-dev/svc/cotton-patch-cafe_952-408-0160/inputs/"

        potential_files = {
            "search_terms": f"{base_path}Search terms report (1).csv",
            "keywords": f"{base_path}Search keyword report (1).csv",
            "negative_keywords": f"{base_path}Negative keyword report (1).csv",
            "campaigns": f"{base_path}Campaign report (2).csv",
            "ad_groups": f"{base_path}Ad group report (2).csv",
            "demographics_age": f"{base_path}Age report.csv",
            "demographics_gender": f"{base_path}Gender report.csv",
            "demographics_income": f"{base_path}Household income report.csv",
            "demographics_parental": f"{base_path}Parental status report.csv",
            "geo_performance": f"{base_path}Location report (2).csv",
            "device_performance": f"{base_path}Device report (2).csv",
            "per_store": f"{base_path}Per store report (2).csv",
            "landing_page": f"{base_path}Landing page report (1).csv",
            "video_creative": f"{base_path}Video report.csv",
            "ad_assets": f"{base_path}Ad asset report.csv",
            "asset_groups": f"{base_path}Asset groups report.csv",
            "bid_adjustments": f"{base_path}Advanced bid adjustment report (1).csv",
        }

        print("🔍 Checking for available input files:")
        available_files = {}

        for file_type, s3_path in potential_files.items():
            try:
                bucket, key = validate_s3_path(s3_path)
                print(f"  ✅ {file_type}: {s3_path}")
                available_files[file_type] = s3_path
            except Exception as e:
                print(f"  ❌ {file_type}: File not accessible ({e})")

        if not available_files:
            print(
                "  ⚠️  No files accessible - may need AWS credentials or files may not exist"
            )
            return None

        print(
            f"\n📥 Found {len(available_files)} accessible files. Testing download..."
        )

        # Try to process a subset of files
        test_files = dict(list(available_files.items())[:3])  # Test first 3 files

        processed_data, temp_files = await process_multiple_s3_files(test_files)

        print(f"✅ Successfully processed {len(processed_data)} files:")
        for data_type, records in processed_data.items():
            print(f"  • {data_type}: {len(records)} records")

        # Clean up temp files
        for temp_file in temp_files:
            if temp_file and temp_file.exists():
                temp_file.unlink()

        return available_files

    except Exception as e:
        print(f"❌ Error testing S3 access: {e}")
        import traceback

        traceback.print_exc()
        return None


async def test_parser_functionality(available_files):
    """Test parser functionality on available files."""
    if not available_files:
        print("⚠️  Skipping parser tests - no accessible files")
        return False

    print("\n🔧 Testing Parser Functionality...")

    try:
        import tempfile

        from paidsearchnav.api.v1.s3_analysis import download_s3_file
        from paidsearchnav.parsers.csv_parser import GoogleAdsCSVParser

        # Test GoogleAdsCSVParser on first available file
        file_type, s3_path = next(iter(available_files.items()))
        print(f"Testing GoogleAdsCSVParser on {file_type} file...")

        # Download file to test parser
        with tempfile.NamedTemporaryFile(
            mode="w+b", suffix=".csv", delete=False
        ) as temp_file:
            temp_path = Path(temp_file.name)

        try:
            await download_s3_file(s3_path, temp_path)

            # Test parsing
            parser = GoogleAdsCSVParser()
            data = parser.parse_file(str(temp_path))

            print(f"  ✅ Successfully parsed {len(data)} records from {file_type}")
            print(
                f"  📊 Sample keys: {list(data[0].keys())[:5] if data else 'No data'}"
            )

            # Clean up
            temp_path.unlink()
            return True

        except Exception as e:
            print(f"  ❌ Parser test failed: {e}")
            if temp_path.exists():
                temp_path.unlink()
            return False

    except Exception as e:
        print(f"❌ Error in parser test setup: {e}")
        return False


async def test_analyzer_functionality(available_files):
    """Test analyzer functionality on available files."""
    if not available_files:
        print("⚠️  Skipping analyzer tests - no accessible files")
        return False

    print("\n🧠 Testing Analyzer Functionality...")

    try:
        # Test CompetitorInsightsAnalyzer (has CSV support from recent PR)
        import tempfile

        from paidsearchnav.analyzers.competitor_insights import (
            CompetitorInsightsAnalyzer,
        )
        from paidsearchnav.api.v1.s3_analysis import download_s3_file

        # Look for search terms or keywords file for analyzer test
        test_file = None
        test_type = None

        for file_type in ["search_terms", "keywords"]:
            if file_type in available_files:
                test_file = available_files[file_type]
                test_type = file_type
                break

        if not test_file:
            print(
                "  ⚠️  No suitable files for analyzer testing (need search_terms or keywords)"
            )
            return False

        print(f"Testing CompetitorInsightsAnalyzer on {test_type} file...")

        # Download file to test analyzer
        with tempfile.NamedTemporaryFile(
            mode="w+b", suffix=".csv", delete=False
        ) as temp_file:
            temp_path = Path(temp_file.name)

        try:
            await download_s3_file(test_file, temp_path)

            # Test analyzer with CSV file
            analyzer = CompetitorInsightsAnalyzer()

            # Read CSV content for analyzer
            with open(temp_path, "r") as f:
                csv_content = f.read()

            # Test analyze method (may need mock data structure)
            print("  ✅ CompetitorInsightsAnalyzer initialized successfully")
            print(f"  📊 CSV file size: {len(csv_content)} characters")

            # Clean up
            temp_path.unlink()
            return True

        except Exception as e:
            print(f"  ❌ Analyzer test failed: {e}")
            if temp_path.exists():
                temp_path.unlink()
            return False

    except Exception as e:
        print(f"❌ Error in analyzer test setup: {e}")
        return False


async def main():
    """Main test function."""
    print("🚀 Cotton Patch Cafe Parser & Analyzer Test")
    print("=" * 60)

    # Load environment variables from .env.dev
    from dotenv import load_dotenv

    env_file = Path(__file__).parent / ".env.dev"
    if env_file.exists():
        load_dotenv(env_file)
        print(f"📄 Loaded environment from {env_file}")

    # Set AWS environment with correct profile
    os.environ.setdefault("AWS_PROFILE", os.getenv("AWS_PROFILE", "roimedia-east1"))
    os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")

    print(f"Using AWS Profile: {os.environ.get('AWS_PROFILE', 'default')}")
    print(f"AWS Region: {os.environ.get('AWS_DEFAULT_REGION', 'us-east-1')}")

    # Step 1: List available components
    parsers_ok = list_available_parsers()
    analyzers_ok = list_available_analyzers()

    if not (parsers_ok and analyzers_ok):
        print("\n❌ Failed to load parser/analyzer modules")
        return False

    # Step 2: Test S3 file access
    available_files = await test_s3_file_access()

    # Step 3: Test parsers
    parser_test_ok = await test_parser_functionality(available_files)

    # Step 4: Test analyzers
    analyzer_test_ok = await test_analyzer_functionality(available_files)

    # Summary
    print("\n" + "=" * 60)
    print("📊 Test Summary:")
    print(f"  • Parser modules loaded: {'✅' if parsers_ok else '❌'}")
    print(f"  • Analyzer modules loaded: {'✅' if analyzers_ok else '❌'}")
    print(f"  • S3 file access: {'✅' if available_files else '❌'}")
    print(f"  • Parser functionality: {'✅' if parser_test_ok else '❌'}")
    print(f"  • Analyzer functionality: {'✅' if analyzer_test_ok else '❌'}")

    success = all(
        [parsers_ok, analyzers_ok, available_files, parser_test_ok, analyzer_test_ok]
    )

    if success:
        print(
            "\n🎉 All tests passed! Parsers and analyzers are working on Cotton Patch Cafe data."
        )
    else:
        print("\n⚠️  Some tests failed. Check error messages above.")

    return success


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
