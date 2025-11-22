#!/usr/bin/env python3
"""
Cotton Patch Cafe - Live Analyzer Suite
Run KeywordAnalyzer and SearchTermsAnalyzer with live data
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

from paidsearchnav.analyzers import KeywordAnalyzer, SearchTermsAnalyzer
from paidsearchnav.core.config import Settings
from paidsearchnav.data_providers.google_ads import GoogleAdsDataProvider
from paidsearchnav.platforms.google.client import GoogleAdsAPIClient


def setup_logging():
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )
    return logging.getLogger(__name__)


async def run_cotton_patch_analyzers():
    """Run live analyzers on Cotton Patch Cafe account."""
    logger = setup_logging()

    try:
        logger.info("🍽️ Running Cotton Patch Cafe Analyzer Suite")
        logger.info("=" * 60)
        logger.info("📊 Account: 952-408-0160")
        logger.info("🏢 Property: Cotton Patch Cafe")

        # Load settings
        settings = Settings.from_env()
        if not settings.google_ads:
            logger.error("❌ Google Ads configuration not found")
            return False

        # Initialize client and data provider
        client = GoogleAdsAPIClient(
            developer_token=settings.google_ads.developer_token.get_secret_value(),
            client_id=settings.google_ads.client_id,
            client_secret=settings.google_ads.client_secret.get_secret_value(),
            refresh_token=settings.google_ads.refresh_token.get_secret_value()
            if settings.google_ads.refresh_token
            else None,
            login_customer_id=settings.google_ads.login_customer_id,
        )

        data_provider = GoogleAdsDataProvider(client)
        customer_id = "952-408-0160"

        # Date range for analysis (last 30 days)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)

        logger.info(f"📅 Analysis period: {start_date.date()} to {end_date.date()}")

        results = {}

        # 1. Run KeywordAnalyzer
        logger.info("\n🎯 Running KeywordAnalyzer...")
        try:
            keyword_analyzer = KeywordAnalyzer(data_provider=data_provider)
            keyword_result = await keyword_analyzer.analyze(
                customer_id=customer_id, start_date=start_date, end_date=end_date
            )

            logger.info("✅ KeywordAnalyzer completed!")
            logger.info(
                f"📊 Found {len(keyword_result.recommendations)} keyword recommendations"
            )

            # Save keyword analysis result
            results["keyword_analysis"] = {
                "analyzer": "KeywordAnalyzer",
                "customer_id": customer_id,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "recommendations_count": len(keyword_result.recommendations),
                "timestamp": datetime.now().isoformat(),
                "success": True,
            }

        except Exception as e:
            logger.error(f"❌ KeywordAnalyzer failed: {e}")
            results["keyword_analysis"] = {
                "analyzer": "KeywordAnalyzer",
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

        # 2. Run SearchTermsAnalyzer
        logger.info("\n🔍 Running SearchTermsAnalyzer...")
        try:
            search_terms_analyzer = SearchTermsAnalyzer(data_provider=data_provider)
            search_terms_result = await search_terms_analyzer.analyze(
                customer_id=customer_id, start_date=start_date, end_date=end_date
            )

            logger.info("✅ SearchTermsAnalyzer completed!")
            logger.info(
                f"📊 Found {len(search_terms_result.recommendations)} search term recommendations"
            )

            # Save search terms analysis result
            results["search_terms_analysis"] = {
                "analyzer": "SearchTermsAnalyzer",
                "customer_id": customer_id,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "recommendations_count": len(search_terms_result.recommendations),
                "timestamp": datetime.now().isoformat(),
                "success": True,
            }

        except Exception as e:
            logger.error(f"❌ SearchTermsAnalyzer failed: {e}")
            results["search_terms_analysis"] = {
                "analyzer": "SearchTermsAnalyzer",
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

        # Save combined results
        output_dir = Path("customers/cotton_patch")
        output_dir.mkdir(parents=True, exist_ok=True)

        # Save individual analyzer results
        for analyzer_name, result in results.items():
            filename = (
                f"live_{analyzer_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            )
            filepath = output_dir / filename

            with open(filepath, "w") as f:
                json.dump(result, f, indent=2)

            logger.info(f"💾 Saved {analyzer_name} to: {filepath}")

        # Summary
        successful_analyses = sum(
            1 for result in results.values() if result.get("success")
        )

        logger.info("\n🎉 Cotton Patch Analyzer Suite Complete!")
        logger.info(f"✅ Successful analyses: {successful_analyses}/{len(results)}")

        if successful_analyses > 0:
            total_recommendations = sum(
                result.get("recommendations_count", 0)
                for result in results.values()
                if result.get("success")
            )
            logger.info(f"📊 Total recommendations generated: {total_recommendations}")
            logger.info("🚀 Ready for optimization implementation!")

        return successful_analyses > 0

    except Exception as e:
        logger.error(f"❌ Analyzer suite failed: {e}")
        import traceback

        logger.error(f"Stack trace: {traceback.format_exc()}")
        return False


if __name__ == "__main__":
    success = asyncio.run(run_cotton_patch_analyzers())

    if success:
        print("\n🎉 Cotton Patch Cafe analyzer suite completed successfully!")
        print("✅ Live analysis data collected")
        print("📊 Ready for comprehensive optimization planning")
    else:
        print("\n❌ Cotton Patch Cafe analyzer suite failed")
        print("🔧 Check logs for details")
