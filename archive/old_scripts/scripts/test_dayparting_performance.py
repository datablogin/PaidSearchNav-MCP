#!/usr/bin/env python3
"""
Performance test for the improved DaypartingAnalyzer with realistic data volumes.
Tests memory usage, query efficiency, and response times.
"""

import asyncio
import logging
import os
import time
from datetime import datetime, timedelta
from pathlib import Path

import psutil

from paidsearchnav.analyzers import DaypartingAnalyzer
from paidsearchnav.core.config import Settings
from paidsearchnav.platforms.google.client import GoogleAdsAPIClient


def setup_logging():
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )
    return logging.getLogger(__name__)


def get_memory_usage():
    """Get current memory usage in MB."""
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / 1024 / 1024


async def test_dayparting_performance():
    """Test DaypartingAnalyzer performance with different date ranges."""
    logger = setup_logging()

    try:
        logger.info("🚀 Testing DaypartingAnalyzer Performance")
        logger.info("=" * 60)

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

        analyzer = DaypartingAnalyzer(api_client=client)
        customer_id = "577-746-1198"  # TopGolf

        # Test different date ranges to measure performance (keeping under 60 days)
        test_scenarios = [
            {"days": 7, "name": "1 Week"},
            {"days": 14, "name": "2 Weeks"},
            {"days": 30, "name": "1 Month"},
            {"days": 45, "name": "6 Weeks"},
        ]

        results = []

        for scenario in test_scenarios:
            logger.info(f"\n📊 Testing {scenario['name']} ({scenario['days']} days)")
            logger.info("-" * 40)

            end_date = datetime.now()
            start_date = end_date - timedelta(days=scenario["days"])

            # Memory before
            memory_before = get_memory_usage()

            # Timing
            start_time = time.time()

            try:
                # Run analysis
                result = await analyzer.analyze(
                    customer_id=customer_id, start_date=start_date, end_date=end_date
                )

                end_time = time.time()
                memory_after = get_memory_usage()

                # Calculate metrics
                duration = end_time - start_time
                memory_delta = memory_after - memory_before

                scenario_result = {
                    "scenario": scenario["name"],
                    "days": scenario["days"],
                    "duration_seconds": round(duration, 2),
                    "memory_before_mb": round(memory_before, 1),
                    "memory_after_mb": round(memory_after, 1),
                    "memory_delta_mb": round(memory_delta, 1),
                    "recommendations": len(result.recommendations),
                    "best_days": len(result.best_performing_days),
                    "best_hours": len(result.best_performing_hours),
                    "potential_savings": result.potential_savings,
                    "success": True,
                }

                results.append(scenario_result)

                logger.info(
                    f"✅ {scenario['name']}: {duration:.2f}s, {memory_delta:+.1f}MB memory"
                )
                logger.info(
                    f"   📈 {len(result.recommendations)} recommendations, ${result.potential_savings:,.2f} potential savings"
                )

            except Exception as e:
                logger.error(f"❌ {scenario['name']} failed: {e}")
                scenario_result = {
                    "scenario": scenario["name"],
                    "days": scenario["days"],
                    "error": str(e),
                    "success": False,
                }
                results.append(scenario_result)

        # Performance Analysis
        logger.info("\n📊 PERFORMANCE ANALYSIS")
        logger.info("=" * 60)

        successful_results = [r for r in results if r.get("success")]

        if successful_results:
            # Performance scaling analysis
            logger.info("🏁 Performance Scaling:")
            for result in successful_results:
                days = result["days"]
                duration = result["duration_seconds"]
                memory = result["memory_delta_mb"]

                # Calculate performance metrics
                seconds_per_day = duration / days if days > 0 else 0
                mb_per_day = memory / days if days > 0 else 0

                logger.info(
                    f"   {result['scenario']:10} | {duration:6.2f}s | {memory:+6.1f}MB | {seconds_per_day:.3f}s/day | {mb_per_day:.2f}MB/day"
                )

            # Efficiency analysis
            avg_duration = sum(r["duration_seconds"] for r in successful_results) / len(
                successful_results
            )
            max_memory = max(r["memory_delta_mb"] for r in successful_results)

            logger.info("\n🎯 Efficiency Metrics:")
            logger.info(f"   Average duration: {avg_duration:.2f} seconds")
            logger.info(f"   Max memory usage: {max_memory:+.1f} MB")
            logger.info(
                f"   Memory efficiency: {'✅ Good' if max_memory < 100 else '⚠️ High' if max_memory < 500 else '❌ Excessive'}"
            )
            logger.info(
                f"   Time efficiency: {'✅ Fast' if avg_duration < 10 else '⚠️ Moderate' if avg_duration < 30 else '❌ Slow'}"
            )

        # Save results
        output_file = (
            Path("customers/topgolf")
            / f"dayparting_performance_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        output_file.parent.mkdir(parents=True, exist_ok=True)

        import json

        with open(output_file, "w") as f:
            json.dump(
                {
                    "test_timestamp": datetime.now().isoformat(),
                    "customer_id": customer_id,
                    "test_type": "performance_scaling",
                    "results": results,
                    "summary": {
                        "total_scenarios": len(test_scenarios),
                        "successful_scenarios": len(successful_results),
                        "avg_duration": avg_duration if successful_results else None,
                        "max_memory": max_memory if successful_results else None,
                        "performance_grade": "A"
                        if successful_results and avg_duration < 10 and max_memory < 100
                        else "B"
                        if successful_results
                        else "F",
                    },
                },
                f,
                indent=2,
            )

        logger.info(f"\n💾 Results saved to: {output_file}")

        return len(successful_results) > 0

    except Exception as e:
        logger.error(f"❌ Performance test failed: {e}")
        import traceback

        logger.error(f"Stack trace: {traceback.format_exc()}")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_dayparting_performance())

    if success:
        print("\n🎉 Performance test completed!")
        print("✅ DaypartingAnalyzer performance validated")
        print("📊 Check the results file for detailed metrics")
    else:
        print("\n❌ Performance test failed")
        print("🔧 Check the logs above for error details")
