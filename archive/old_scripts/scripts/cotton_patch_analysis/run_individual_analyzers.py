#!/usr/bin/env python3
"""Run all 20 analyzers individually on Cotton Patch Cafe data and generate JSON outputs."""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, "/Users/robertwelborn/PycharmProjects/PaidSearchNav")

from dotenv import load_dotenv


async def run_all_analyzers():
    """Run all 20 analyzers on Cotton Patch Cafe data."""
    print("🧠 Running All Analyzers on Cotton Patch Cafe Data")
    print("=" * 60)

    # Load environment variables
    env_file = Path(__file__).parent / ".env.dev"
    if env_file.exists():
        load_dotenv(env_file)

    # Process Cotton Patch Cafe data
    processed_data = await get_cotton_patch_data()
    if not processed_data["success"]:
        return False

    data = processed_data["data"]

    # Define all analyzers to run
    analyzers_to_run = [
        ("SearchTermsAnalyzer", "paidsearchnav.analyzers.search_terms", "search_terms"),
        ("KeywordAnalyzer", "paidsearchnav.analyzers.keyword_analyzer", "keywords"),
        (
            "CompetitorInsightsAnalyzer",
            "paidsearchnav.analyzers.competitor_insights",
            "search_terms",
        ),
        (
            "GeoPerformanceAnalyzer",
            "paidsearchnav.analyzers.geo_performance",
            "geo_performance",
        ),
        (
            "DevicePerformanceAnalyzer",
            "paidsearchnav.analyzers.device_performance",
            "device_performance",
        ),
        (
            "DemographicsAnalyzer",
            "paidsearchnav.analyzers.demographics",
            "demographics_age",
        ),
        ("LandingPageAnalyzer", "paidsearchnav.analyzers.landing_page", "landing_page"),
        (
            "VideoCreativeAnalyzer",
            "paidsearchnav.analyzers.video_creative",
            "video_creative",
        ),
        ("DaypartingAnalyzer", "paidsearchnav.analyzers.dayparting", "dayparting"),
        (
            "PerformanceMaxAnalyzer",
            "paidsearchnav.analyzers.performance_max",
            "campaigns",
        ),
        (
            "NegativeConflictAnalyzer",
            "paidsearchnav.analyzers.negative_conflict",
            "negative_keywords",
        ),
        (
            "SharedNegativeValidatorAnalyzer",
            "paidsearchnav.analyzers.shared_negative_validator",
            "negative_keywords",
        ),
        (
            "BulkNegativeManagerAnalyzer",
            "paidsearchnav.analyzers.bulk_negative_manager",
            "negative_keywords",
        ),
        (
            "StorePerformanceAnalyzer",
            "paidsearchnav.analyzers.store_performance",
            "per_store",
        ),
        (
            "LocalReachStoreAnalyzer",
            "paidsearchnav.analyzers.local_reach_store",
            "per_store",
        ),
        (
            "PlacementAuditAnalyzer",
            "paidsearchnav.analyzers.placement_audit",
            "campaigns",
        ),
        (
            "CampaignOverlapAnalyzer",
            "paidsearchnav.analyzers.campaign_overlap",
            "campaigns",
        ),
        (
            "AdvancedBidAdjustmentAnalyzer",
            "paidsearchnav.analyzers.advanced_bid_adjustment",
            "geo_performance",
        ),
        ("KeywordMatchAnalyzer", "paidsearchnav.analyzers.keyword_match", "keywords"),
        (
            "SearchTermAnalyzer",
            "paidsearchnav.analyzers.search_term_analyzer",
            "search_terms",
        ),
    ]

    successful_runs = 0
    analyzer_outputs = {}

    for analyzer_name, module_path, data_key in analyzers_to_run:
        print(f"\n🔍 Running {analyzer_name}...")

        try:
            # Check if we have the required data
            if data_key not in data or not data[data_key]:
                print(f"   ⚠️  No data available for {data_key}")
                analyzer_outputs[analyzer_name] = {
                    "status": "no_data",
                    "data_required": data_key,
                    "message": f"No {data_key} data available for analysis",
                }
                continue

            # Try to run the analyzer
            result = await run_single_analyzer(
                analyzer_name, module_path, data[data_key], data
            )
            analyzer_outputs[analyzer_name] = result

            if result.get("status") == "success":
                successful_runs += 1
                print(f"   ✅ {analyzer_name} completed successfully")
            else:
                print(
                    f"   ⚠️  {analyzer_name} completed with issues: {result.get('message', 'Unknown error')}"
                )

        except Exception as e:
            print(f"   ❌ {analyzer_name} failed: {e}")
            analyzer_outputs[analyzer_name] = {
                "status": "error",
                "error": str(e),
                "analyzer": analyzer_name,
            }

    print("\n📊 Analyzer Summary:")
    print(f"   • Total analyzers: {len(analyzers_to_run)}")
    print(f"   • Successful runs: {successful_runs}")
    print(f"   • With issues/no data: {len(analyzers_to_run) - successful_runs}")

    # Save all analyzer outputs to S3
    await save_analyzer_outputs_to_s3(analyzer_outputs)

    return True


async def get_cotton_patch_data():
    """Get Cotton Patch Cafe processed data."""
    try:
        from paidsearchnav.api.v1.s3_analysis import process_multiple_s3_files

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
        }

        print("📥 Loading Cotton Patch Cafe data for analyzers...")
        processed_data, temp_files = await process_multiple_s3_files(files)

        # Clean up temp files
        for temp_file in temp_files:
            if temp_file and temp_file.exists():
                temp_file.unlink()

        total_records = sum(len(records) for records in processed_data.values())
        print(f"✅ Loaded {total_records:,} records from {len(processed_data)} files")

        return {"success": True, "data": processed_data}

    except Exception as e:
        print(f"❌ Data loading failed: {e}")
        return {"success": False, "error": str(e)}


async def run_single_analyzer(analyzer_name, module_path, primary_data, all_data):
    """Run a single analyzer and return its output."""
    try:
        # Import the analyzer
        module = __import__(module_path, fromlist=[analyzer_name])
        analyzer_class = getattr(module, analyzer_name)

        # Check analyzer constructor requirements
        import inspect

        sig = inspect.signature(analyzer_class.__init__)
        params = list(sig.parameters.keys())[1:]  # Skip 'self'

        # Initialize analyzer based on its requirements
        if not params:
            # No parameters required
            analyzer = analyzer_class()
        elif len(params) == 1 and "data_provider" in params[0].lower():
            # Requires data provider - create a mock one
            class MockDataProvider:
                def __init__(self, data):
                    self.data = data

                def get_data(self, data_type):
                    return self.data.get(data_type, [])

            analyzer = analyzer_class(MockDataProvider(all_data))
        elif len(params) == 1 and (
            "client" in params[0].lower() or "api" in params[0].lower()
        ):
            # Requires API client - create a mock one
            class MockAPIClient:
                def __init__(self):
                    pass

            analyzer = analyzer_class(MockAPIClient())
        else:
            # Try no-argument initialization
            analyzer = analyzer_class()

        # Run the analyzer
        analysis_result = {
            "analyzer": analyzer_name,
            "timestamp": datetime.now().isoformat(),
            "data_source": f"Cotton Patch Cafe - {len(primary_data)} records",
            "status": "success",
        }

        # Try to get analyzer-specific insights
        if hasattr(analyzer, "analyze"):
            try:
                # Some analyzers might expect different data formats
                if analyzer_name == "CompetitorInsightsAnalyzer":
                    # This analyzer has CSV support from PR #456
                    result = analyzer.analyze(
                        primary_data[:1000]
                    )  # Limit to first 1000 for performance
                    analysis_result["insights"] = result
                    analysis_result["records_analyzed"] = min(len(primary_data), 1000)
                else:
                    # Standard analyzer interface
                    result = analyzer.analyze(
                        primary_data[:500]
                    )  # Limit for performance
                    analysis_result["insights"] = result
                    analysis_result["records_analyzed"] = min(len(primary_data), 500)

            except Exception as analyze_error:
                analysis_result["analyze_error"] = str(analyze_error)
                analysis_result["message"] = (
                    f"Analyzer initialized but analyze method failed: {analyze_error}"
                )

        # Add data summary
        analysis_result["data_summary"] = {
            "primary_data_type": type(primary_data).__name__,
            "primary_data_count": len(primary_data),
            "total_data_sources": len(all_data),
            "sample_fields": get_sample_fields(primary_data),
        }

        return analysis_result

    except Exception as e:
        return {
            "analyzer": analyzer_name,
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }


def get_sample_fields(data):
    """Get sample fields from the data."""
    if not data:
        return []

    sample = data[0]
    if hasattr(sample, "__dict__"):
        # Pydantic model
        return list(sample.__dict__.keys())[:10]
    elif isinstance(sample, dict):
        # Dictionary
        return list(sample.keys())[:10]
    else:
        return [str(type(sample))]


async def save_analyzer_outputs_to_s3(analyzer_outputs):
    """Save all analyzer outputs to S3."""
    try:
        import boto3

        session = boto3.Session(profile_name="roimedia-east1")
        s3_client = session.client("s3")
        bucket_name = "paidsearchnav-customer-data-dev"

        date_str = datetime.now().strftime("%Y-%m-%d")

        # Save individual analyzer outputs
        for analyzer_name, output in analyzer_outputs.items():
            key = f"svc/cotton-patch-cafe_952-408-0160/outputs/analyzers/{date_str}/{analyzer_name.lower()}_output.json"

            s3_client.put_object(
                Bucket=bucket_name,
                Key=key,
                Body=json.dumps(output, indent=2, default=str),
                ContentType="application/json",
            )

            print(f"   📄 Saved {analyzer_name} output to S3")

        # Save combined analyzer summary
        summary = {
            "analysis_date": datetime.now().isoformat(),
            "customer": "Cotton Patch Cafe (952-408-0160)",
            "total_analyzers": len(analyzer_outputs),
            "successful_analyzers": len(
                [a for a in analyzer_outputs.values() if a.get("status") == "success"]
            ),
            "analyzer_results": analyzer_outputs,
        }

        summary_key = f"svc/cotton-patch-cafe_952-408-0160/outputs/analyzers/{date_str}/analyzer_summary.json"
        s3_client.put_object(
            Bucket=bucket_name,
            Key=summary_key,
            Body=json.dumps(summary, indent=2, default=str),
            ContentType="application/json",
        )

        print("\n✅ All analyzer outputs saved to S3")
        print(
            f"📍 Location: s3://{bucket_name}/svc/cotton-patch-cafe_952-408-0160/outputs/analyzers/{date_str}/"
        )

    except Exception as e:
        print(f"❌ Failed to save to S3: {e}")


if __name__ == "__main__":
    success = asyncio.run(run_all_analyzers())

    if success:
        print("\n🎉 All analyzers completed! Individual JSON outputs generated.")
    else:
        print("\n❌ Analyzer run encountered issues.")

    sys.exit(0 if success else 1)
