#!/usr/bin/env python3
"""
Test geo performance analyzer on real Google Ads account data.
"""

import asyncio
import os
from datetime import datetime, timedelta

from dotenv import load_dotenv

from paidsearchnav.analyzers.geo_performance import GeoPerformanceAnalyzer
from paidsearchnav.platforms.google import GoogleAdsAPIClient

# Load environment variables
load_dotenv()


def validate_environment():
    """Validate all required environment variables are present."""
    required_vars = [
        "PSN_GOOGLE_ADS_DEVELOPER_TOKEN",
        "PSN_GOOGLE_ADS_CLIENT_ID",
        "PSN_GOOGLE_ADS_CLIENT_SECRET",
        "PSN_GOOGLE_ADS_REFRESH_TOKEN",
        "PSN_GOOGLE_ADS_CLIENT_CUSTOMER_ID",
    ]

    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)

    if missing_vars:
        print("❌ Error: Missing required environment variables:")
        for var in missing_vars:
            print(f"   - {var}")
        print("\nPlease set these variables in your .env file.")
        return False

    return True


async def test_geo_performance():
    """Test geo performance analyzer on the configured Google Ads account."""

    # Validate environment variables
    if not validate_environment():
        return False

    client_customer_id = os.getenv("PSN_GOOGLE_ADS_CLIENT_CUSTOMER_ID", "").replace(
        "-", ""
    )

    try:
        # Initialize Google Ads client
        print("🔧 Initializing Google Ads client...")
        client = GoogleAdsAPIClient(
            developer_token=os.getenv("PSN_GOOGLE_ADS_DEVELOPER_TOKEN"),
            client_id=os.getenv("PSN_GOOGLE_ADS_CLIENT_ID"),
            client_secret=os.getenv("PSN_GOOGLE_ADS_CLIENT_SECRET"),
            refresh_token=os.getenv("PSN_GOOGLE_ADS_REFRESH_TOKEN"),
            login_customer_id=os.getenv("PSN_GOOGLE_ADS_LOGIN_CUSTOMER_ID", "").replace(
                "-", ""
            ),
        )

        # Initialize geo performance analyzer
        print("🌍 Initializing Geo Performance Analyzer...")
        analyzer = GeoPerformanceAnalyzer(
            api_client=client,
            min_impressions=50,  # Lower threshold for testing
            min_clicks=5,
            performance_threshold=0.2,
            top_locations_count=10,
        )

        print(f"🎯 Running geo analysis on customer account: {client_customer_id}")
        print("=" * 60)

        # Set date range (last 30 days)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)

        print(
            f"📅 Analysis period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"
        )

        # Test analyzer metadata
        print(f"📊 Analyzer name: {analyzer.get_name()}")
        print(f"📝 Description: {analyzer.get_description()}")

        # Run the analysis
        print("⚡ Starting geo performance analysis...")
        result = await analyzer.analyze(
            customer_id=client_customer_id, start_date=start_date, end_date=end_date
        )

        # Display results
        print("\n🎉 Geo Analysis Complete!")
        print("=" * 60)

        print("📈 Analysis Summary:")
        print(f"   - Geographic levels analyzed: {len(result.geographic_data)}")
        print(f"   - Total recommendations: {len(result.recommendations)}")

        # Show geographic data by level
        geo_levels = {}
        for geo_data in result.geographic_data:
            level = geo_data.level.value
            if level not in geo_levels:
                geo_levels[level] = []
            geo_levels[level].append(geo_data)

        print("\n🗺️  Geographic Data by Level:")
        for level, data_list in geo_levels.items():
            print(f"   - {level}: {len(data_list)} locations")

            # Show top performers
            sorted_data = sorted(
                data_list, key=lambda x: x.performance_metrics.ctr, reverse=True
            )
            for geo in sorted_data[:3]:
                metrics = geo.performance_metrics
                print(
                    f"     • {geo.location_name}: CTR {metrics.ctr:.2%}, CPC ${metrics.cpc:.2f}, {metrics.impressions} impr"
                )

            if len(sorted_data) > 3:
                print(f"     ... and {len(sorted_data) - 3} more")

        # Show distance performance if available
        if hasattr(result, "distance_performance") and result.distance_performance:
            print("\n📏 Distance Performance:")
            for distance_data in result.distance_performance:
                metrics = distance_data.performance_metrics
                print(
                    f"   - {distance_data.distance_range}: CTR {metrics.ctr:.2%}, {metrics.impressions} impr"
                )

        # Show recommendations by priority
        if result.recommendations:
            print("\n💡 Recommendations by Priority:")

            priorities = {}
            for rec in result.recommendations:
                priority = rec.priority.value
                if priority not in priorities:
                    priorities[priority] = []
                priorities[priority].append(rec)

            for priority in ["HIGH", "MEDIUM", "LOW"]:
                if priority in priorities:
                    recs = priorities[priority]
                    print(f"   {priority}: {len(recs)} recommendations")

                    for rec in recs[:3]:
                        print(f"     • {rec.type.value}: {rec.description}")

                    if len(recs) > 3:
                        print(f"     ... and {len(recs) - 3} more")

        # Show performance summary if available
        if hasattr(result, "summary"):
            summary = result.summary
            print("\n📊 Performance Summary:")
            print(f"   - Top performing location: {summary.top_performing_location}")
            print(
                f"   - Worst performing location: {summary.worst_performing_location}"
            )
            print(f"   - Average CTR: {summary.average_ctr:.2%}")
            print(f"   - Average CPC: ${summary.average_cpc:.2f}")

        print("\n✅ Geo performance analysis completed successfully!")
        return True

    except Exception as e:
        print(f"❌ Error during geo analysis: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    asyncio.run(test_geo_performance())
