#!/usr/bin/env python3
"""
Run search terms analysis on real Google Ads account data.
"""

import asyncio
import os
from datetime import datetime, timedelta

from dotenv import load_dotenv

from paidsearchnav.analyzers.search_terms import SearchTermsAnalyzer
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


async def run_analysis():
    """Run search terms analysis on the configured Google Ads account."""

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

        # Initialize search terms analyzer
        print("📊 Initializing Search Terms Analyzer...")
        analyzer = SearchTermsAnalyzer(
            data_provider=client,
            min_impressions=5,  # Lower threshold for testing
            min_clicks_for_negative=5,
            max_cpa_multiplier=2.0,
            min_conversions_for_add=0.5,
        )

        print(f"🎯 Running analysis on customer account: {client_customer_id}")
        print("=" * 60)

        # Set date range (last 30 days)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)

        print(
            f"📅 Analysis period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"
        )

        # Run the analysis
        print("⚡ Starting search terms analysis...")
        result = await analyzer.analyze(
            customer_id=client_customer_id, start_date=start_date, end_date=end_date
        )

        # Display results
        print("\n🎉 Analysis Complete!")
        print("=" * 60)

        print("📈 Analysis Summary:")
        print(f"   - Total search terms analyzed: {len(result.search_terms)}")
        print(f"   - Total recommendations: {len(result.recommendations)}")

        # Group search terms by classification
        classifications = {}
        for search_term in result.search_terms:
            classification = search_term.classification.value
            if classification not in classifications:
                classifications[classification] = []
            classifications[classification].append(search_term)

        print("\n🏷️  Search Terms by Classification:")
        for classification, terms in classifications.items():
            print(f"   - {classification}: {len(terms)} terms")

            # Show a few examples
            for term in terms[:3]:
                metrics = term.metrics
                print(
                    f"     • '{term.query}': {metrics.impressions} impr, {metrics.clicks} clicks, ${metrics.cost:.2f}"
                )

            if len(terms) > 3:
                print(f"     ... and {len(terms) - 3} more")

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

        # Show potential impact
        if hasattr(result, "potential_monthly_savings"):
            print("\n💰 Potential Impact:")
            print(
                f"   - Estimated monthly savings: ${result.potential_monthly_savings:.2f}"
            )

        if hasattr(result, "potential_monthly_revenue"):
            print(
                f"   - Potential additional revenue: ${result.potential_monthly_revenue:.2f}"
            )

        print("\n✅ Search terms analysis completed successfully!")
        return True

    except Exception as e:
        print(f"❌ Error during analysis: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    asyncio.run(run_analysis())
