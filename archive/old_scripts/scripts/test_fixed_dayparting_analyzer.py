#!/usr/bin/env python3
"""
Test the fixed DaypartingAnalyzer with TopGolf live data
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

from paidsearchnav.analyzers import DaypartingAnalyzer
from paidsearchnav.core.config import Settings
from paidsearchnav.platforms.google.client import GoogleAdsAPIClient


def setup_logging():
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )
    return logging.getLogger(__name__)


async def test_fixed_dayparting_analyzer():
    """Test the fixed DaypartingAnalyzer with live API data."""
    logger = setup_logging()

    try:
        logger.info("🔧 Testing Fixed DaypartingAnalyzer")
        logger.info("=" * 50)

        # Load settings from environment
        settings = Settings.from_env()

        if not settings.google_ads:
            logger.error("❌ Google Ads configuration not found in environment")
            return False

        # Initialize Google Ads API client
        client = GoogleAdsAPIClient(
            developer_token=settings.google_ads.developer_token.get_secret_value(),
            client_id=settings.google_ads.client_id,
            client_secret=settings.google_ads.client_secret.get_secret_value(),
            refresh_token=settings.google_ads.refresh_token.get_secret_value()
            if settings.google_ads.refresh_token
            else None,
            login_customer_id=settings.google_ads.login_customer_id,
        )

        logger.info("🚀 Google Ads API client initialized")

        # Initialize DaypartingAnalyzer
        analyzer = DaypartingAnalyzer(api_client=client)

        # Test parameters
        customer_id = "577-746-1198"
        start_date = datetime.now() - timedelta(days=7)  # Last 7 days
        end_date = datetime.now()

        logger.info(f"📊 Testing DaypartingAnalyzer for customer {customer_id}")
        logger.info(f"📅 Date range: {start_date.date()} to {end_date.date()}")

        # Run analysis
        result = await analyzer.analyze(
            customer_id=customer_id, start_date=start_date, end_date=end_date
        )

        logger.info("✅ DaypartingAnalyzer completed successfully!")
        logger.info(f"📈 Found {len(result.recommendations)} recommendations")
        logger.info(f"📊 Best performing days: {len(result.best_performing_days)}")
        logger.info(f"📊 Best performing hours: {len(result.best_performing_hours)}")
        logger.info(f"💰 Potential savings: ${result.potential_savings:,.2f}")
        logger.info(
            f"🔄 Potential conversion increase: {result.potential_conversion_increase:,.2f}"
        )

        # Show some sample findings
        if result.best_performing_days:
            logger.info("\n🏆 Top Performing Days:")
            for i, day in enumerate(result.best_performing_days[:3], 1):
                logger.info(
                    f"  {i}. {day.get('day', 'Unknown')}: {day.get('conversion_rate', 0) * 100:.2f}% CVR"
                )

        if result.best_performing_hours:
            logger.info("\n⏰ Top Performing Hours:")
            for i, hour in enumerate(result.best_performing_hours[:3], 1):
                logger.info(
                    f"  {i}. {hour.get('hour', 'Unknown')}: {hour.get('conversion_rate', 0) * 100:.2f}% CVR"
                )

        if result.recommendations:
            logger.info("\n💡 Sample Recommendations:")
            for i, rec in enumerate(result.recommendations[:3], 1):
                logger.info(f"  {i}. {rec.title}")

        # Save results
        output_file = (
            Path("customers/topgolf")
            / f"fixed_dayparting_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # Convert result to dict for JSON serialization
        result_dict = {
            "analyzer": "DaypartingAnalyzer",
            "customer_id": customer_id,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "success": True,
            "recommendations_count": len(result.recommendations),
            "best_performing_days_count": len(result.best_performing_days),
            "best_performing_hours_count": len(result.best_performing_hours),
            "potential_savings": result.potential_savings,
            "potential_conversion_increase": result.potential_conversion_increase,
            "timestamp": datetime.now().isoformat(),
            "fix_applied": "Updated API query to use campaign resource with segments.date and segments.hour",
        }

        with open(output_file, "w") as f:
            json.dump(result_dict, f, indent=2)

        logger.info(f"💾 Results saved to: {output_file}")

        return True

    except Exception as e:
        logger.error(f"❌ DaypartingAnalyzer test failed: {e}")
        import traceback

        logger.error(f"Stack trace: {traceback.format_exc()}")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_fixed_dayparting_analyzer())

    if success:
        print("\n🎉 DaypartingAnalyzer fix successful!")
        print("✅ The analyzer now works with Google Ads API v20")
        print("🚀 Ready for production use!")
    else:
        print("\n❌ DaypartingAnalyzer fix failed")
        print("🔧 Check the logs above for error details")
