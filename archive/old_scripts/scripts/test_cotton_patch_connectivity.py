#!/usr/bin/env python3
"""
Cotton Patch Cafe - Basic Connectivity Test
Google Ads Account: 952-408-0160
Property ID: 352215406
"""

import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path

from paidsearchnav.core.config import Settings
from paidsearchnav.platforms.google.client import GoogleAdsAPIClient


def setup_logging():
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )
    return logging.getLogger(__name__)


async def test_cotton_patch_connectivity():
    """Test basic connectivity to Cotton Patch Cafe Google Ads account."""
    logger = setup_logging()

    try:
        logger.info("🧪 Testing Cotton Patch Cafe Connectivity")
        logger.info("=" * 50)
        logger.info("📊 Account: 952-408-0160")
        logger.info("🏢 Property ID: 352215406")

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

        # Test basic account access
        customer_id = "952-408-0160"

        logger.info(f"🔌 Testing connectivity to account {customer_id}")

        # Test 1: Get campaigns first (this validates account access)
        try:
            logger.info("📋 Test 1: Basic Account Access")

            # Test basic account access by getting campaigns
            campaigns = await client.get_campaigns(
                customer_id=customer_id,
                start_date=datetime.now() - timedelta(days=30),
                end_date=datetime.now(),
            )

            logger.info("✅ Account access successful!")
            logger.info(f"✅ Found {len(campaigns)} campaigns")

        except Exception as e:
            logger.error(f"❌ Account access test failed: {e}")
            return False

        # Show campaign details
        logger.info("\n📊 Test 2: Campaign Details")
        if campaigns:
            for i, campaign in enumerate(campaigns[:3], 1):  # Show first 3
                logger.info(
                    f"   {i}. {campaign.name} - Status: {campaign.status} - Budget: ${campaign.budget_amount:.2f}"
                )
        else:
            logger.warning("⚠️ No campaigns found in account")

        # Test 3: Get keywords (sample)
        try:
            logger.info("\n🎯 Test 3: Keywords Access")

            keywords = await client.get_keywords(
                customer_id=customer_id,
                start_date=datetime.now() - timedelta(days=7),
                end_date=datetime.now(),
                limit=5,  # Just get a few for testing
            )

            logger.info(f"✅ Found {len(keywords)} keywords (sample)")

            if keywords:
                for i, keyword in enumerate(keywords[:3], 1):  # Show first 3
                    logger.info(
                        f"   {i}. '{keyword.text}' - Match: {keyword.match_type} - CPC: ${keyword.avg_cpc:.2f}"
                    )

        except Exception as e:
            logger.error(f"❌ Keywords access test failed: {e}")
            return False

        # Test 4: Get search terms (sample)
        try:
            logger.info("\n🔍 Test 4: Search Terms Access")

            search_terms = await client.get_search_terms(
                customer_id=customer_id,
                start_date=datetime.now() - timedelta(days=7),
                end_date=datetime.now(),
                limit=5,  # Just get a few for testing
            )

            logger.info(f"✅ Found {len(search_terms)} search terms (sample)")

            if search_terms:
                for i, term in enumerate(search_terms[:3], 1):  # Show first 3
                    logger.info(
                        f"   {i}. '{term.search_term}' - Impressions: {term.metrics.impressions}"
                    )

        except Exception as e:
            logger.error(f"❌ Search terms access test failed: {e}")
            return False

        # Test 5: Performance data sample
        try:
            logger.info("\n📈 Test 5: Performance Data")

            # Get basic performance metrics
            if campaigns:
                sample_campaign = campaigns[0]

                logger.info(f"✅ Sample performance data for '{sample_campaign.name}':")
                logger.info(f"   Impressions: {sample_campaign.impressions:,}")
                logger.info(f"   Clicks: {sample_campaign.clicks:,}")
                logger.info(f"   Conversions: {sample_campaign.conversions:.1f}")
                logger.info(f"   Cost: ${sample_campaign.cost:.2f}")

                if sample_campaign.clicks > 0:
                    ctr = (sample_campaign.clicks / sample_campaign.impressions) * 100
                    logger.info(f"   CTR: {ctr:.2f}%")

                if sample_campaign.conversions > 0:
                    conv_rate = (
                        sample_campaign.conversions / sample_campaign.clicks
                    ) * 100
                    cpa = sample_campaign.cost / sample_campaign.conversions
                    logger.info(f"   Conversion Rate: {conv_rate:.2f}%")
                    logger.info(f"   CPA: ${cpa:.2f}")

        except Exception as e:
            logger.error(f"❌ Performance data test failed: {e}")
            return False

        # Summary
        logger.info("\n🎉 CONNECTIVITY TEST SUMMARY")
        logger.info("=" * 50)
        logger.info("✅ Account Access: SUCCESS")
        logger.info("✅ Campaign Data: SUCCESS")
        logger.info("✅ Keywords Data: SUCCESS")
        logger.info("✅ Search Terms Data: SUCCESS")
        logger.info("✅ Performance Metrics: SUCCESS")
        logger.info("\n🚀 Cotton Patch Cafe account is ready for analysis!")

        # Save connectivity report
        output_file = (
            Path("customers/cotton_patch")
            / f"connectivity_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        output_file.parent.mkdir(parents=True, exist_ok=True)

        import json

        connectivity_report = {
            "test_timestamp": datetime.now().isoformat(),
            "customer_id": customer_id,
            "property_id": "352215406",
            "account_name": "Cotton Patch Cafe",
            "connectivity_status": "SUCCESS",
            "tests_completed": [
                "Account Information",
                "Campaign Access",
                "Keywords Access",
                "Search Terms Access",
                "Performance Data",
            ],
            "account_summary": {
                "campaigns_found": len(campaigns) if "campaigns" in locals() else 0,
                "keywords_found": len(keywords) if "keywords" in locals() else 0,
                "search_terms_found": len(search_terms)
                if "search_terms" in locals()
                else 0,
                "api_version": "v20",
                "ready_for_analysis": True,
            },
        }

        with open(output_file, "w") as f:
            json.dump(connectivity_report, f, indent=2)

        logger.info(f"📄 Connectivity report saved to: {output_file}")

        return True

    except Exception as e:
        logger.error(f"❌ Connectivity test failed: {e}")
        import traceback

        logger.error(f"Stack trace: {traceback.format_exc()}")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_cotton_patch_connectivity())

    if success:
        print("\n🎉 Cotton Patch Cafe connectivity test successful!")
        print("✅ Account is ready for full analysis")
        print("🚀 You can now run any analyzer on this account")
    else:
        print("\n❌ Cotton Patch Cafe connectivity test failed")
        print("🔧 Please check account permissions and API configuration")
