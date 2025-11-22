#!/usr/bin/env python3
"""
Cotton Patch Cafe - Simple Connectivity Test
Google Ads Account: 952-408-0160
Property ID: 352215406
"""

import asyncio
import logging
from datetime import datetime
from pathlib import Path

from paidsearchnav.core.config import Settings
from paidsearchnav.platforms.google.client import GoogleAdsAPIClient


def setup_logging():
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )
    return logging.getLogger(__name__)


async def test_cotton_patch_simple():
    """Simple connectivity test for Cotton Patch Cafe."""
    logger = setup_logging()

    try:
        logger.info("🧪 Cotton Patch Cafe - Simple Connectivity Test")
        logger.info("=" * 55)
        logger.info("📊 Account: 952-408-0160")
        logger.info("🏢 Property ID: 352215406")

        # Load settings
        settings = Settings.from_env()
        if not settings.google_ads:
            logger.error("❌ Google Ads configuration not found")
            return False

        # Initialize client
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

        customer_id = "952-408-0160"

        # Test raw API access - just get basic campaign data
        try:
            logger.info(f"🔌 Testing raw API access to {customer_id}")

            google_client = client._get_client()
            ga_service = google_client.get_service("GoogleAdsService")

            # Simple query to test connectivity
            query = """
                SELECT
                    campaign.id,
                    campaign.name,
                    campaign.status,
                    metrics.impressions,
                    metrics.clicks,
                    metrics.cost_micros
                FROM campaign
                WHERE campaign.status != 'REMOVED'
                LIMIT 5
            """

            search_request = google_client.get_type("SearchGoogleAdsRequest")
            search_request.customer_id = customer_id.replace("-", "")
            search_request.query = query

            response = ga_service.search(request=search_request)

            campaigns_found = 0
            total_impressions = 0
            total_clicks = 0
            total_cost = 0

            logger.info("\n📊 Sample Campaign Data:")
            for row in response:
                campaigns_found += 1
                campaign_name = row.campaign.name
                impressions = row.metrics.impressions
                clicks = row.metrics.clicks
                cost = row.metrics.cost_micros / 1_000_000

                total_impressions += impressions
                total_clicks += clicks
                total_cost += cost

                logger.info(f"   {campaigns_found}. {campaign_name}")
                logger.info(f"      Impressions: {impressions:,}")
                logger.info(f"      Clicks: {clicks:,}")
                logger.info(f"      Cost: ${cost:.2f}")

                if campaigns_found >= 3:  # Just show first 3
                    break

            # Summary
            logger.info("\n✅ CONNECTIVITY SUCCESS!")
            logger.info(f"📊 Found {campaigns_found}+ active campaigns")
            logger.info("📈 Total Sample Metrics:")
            logger.info(f"   Impressions: {total_impressions:,}")
            logger.info(f"   Clicks: {total_clicks:,}")
            logger.info(f"   Cost: ${total_cost:.2f}")

            if total_clicks > 0:
                ctr = (
                    (total_clicks / total_impressions) * 100
                    if total_impressions > 0
                    else 0
                )
                avg_cpc = total_cost / total_clicks if total_clicks > 0 else 0
                logger.info(f"   CTR: {ctr:.2f}%")
                logger.info(f"   Avg CPC: ${avg_cpc:.2f}")

            # Test keywords access quickly
            logger.info("\n🎯 Testing Keywords Access...")

            keyword_query = """
                SELECT
                    ad_group_criterion.criterion_id,
                    ad_group_criterion.keyword.text,
                    ad_group_criterion.keyword.match_type,
                    metrics.impressions
                FROM keyword_view
                WHERE ad_group_criterion.status != 'REMOVED'
                LIMIT 3
            """

            search_request.query = keyword_query
            keyword_response = ga_service.search(request=search_request)

            keywords_found = 0
            for row in keyword_response:
                keywords_found += 1
                keyword_text = row.ad_group_criterion.keyword.text
                match_type = row.ad_group_criterion.keyword.match_type.name
                impressions = row.metrics.impressions

                logger.info(
                    f"   {keywords_found}. '{keyword_text}' [{match_type}] - {impressions:,} impressions"
                )

                if keywords_found >= 3:
                    break

            logger.info(
                f"✅ Keywords access successful! Found {keywords_found}+ keywords"
            )

            # Save connectivity report
            output_dir = Path("customers/cotton_patch")
            output_dir.mkdir(parents=True, exist_ok=True)

            output_file = (
                output_dir
                / f"connectivity_success_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            )

            import json

            report = {
                "test_timestamp": datetime.now().isoformat(),
                "customer_id": customer_id,
                "property_id": "352215406",
                "account_name": "Cotton Patch Cafe",
                "connectivity_status": "SUCCESS",
                "api_access": "CONFIRMED",
                "campaigns_found": f"{campaigns_found}+",
                "keywords_found": f"{keywords_found}+",
                "sample_metrics": {
                    "impressions": total_impressions,
                    "clicks": total_clicks,
                    "cost": round(total_cost, 2),
                    "ctr": round(ctr, 2) if "ctr" in locals() else 0,
                    "avg_cpc": round(avg_cpc, 2) if "avg_cpc" in locals() else 0,
                },
                "ready_for_analysis": True,
                "recommended_next_steps": [
                    "Run KeywordAnalyzer for keyword optimization",
                    "Run SearchTermsAnalyzer for waste identification",
                    "Run DaypartingAnalyzer for scheduling optimization",
                    "Run full analyzer suite for comprehensive insights",
                ],
            }

            with open(output_file, "w") as f:
                json.dump(report, f, indent=2)

            logger.info(f"\n📄 Report saved: {output_file}")

            return True

        except Exception as e:
            logger.error(f"❌ API connectivity failed: {e}")
            import traceback

            logger.error(f"Stack trace: {traceback.format_exc()}")
            return False

    except Exception as e:
        logger.error(f"❌ Overall test failed: {e}")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_cotton_patch_simple())

    if success:
        print("\n🎉 Cotton Patch Cafe connectivity test SUCCESSFUL!")
        print("✅ Account 952-408-0160 is accessible")
        print("✅ API connection confirmed")
        print("✅ Campaign and keyword data available")
        print("🚀 Ready for full optimization analysis!")
    else:
        print("\n❌ Cotton Patch Cafe connectivity test FAILED")
        print("🔧 Please check account access and permissions")
