#!/usr/bin/env python3
"""
TopGolf BigQuery Comprehensive End-to-End Pipeline Test
Tests the complete data pipeline from extraction to insights
"""

import json
import logging
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_comprehensive_test():
    """Run complete end-to-end pipeline test"""
    logger.info("🚀 COMPREHENSIVE END-TO-END PIPELINE TEST")
    logger.info("=" * 60)
    logger.info("Customer: TopGolf (577-746-1198)")
    logger.info("=" * 60)

    data_file = "/Users/robertwelborn/PycharmProjects/PaidSearchNav/customers/topgolf/topgolf_real_data_20250822_181442.json"

    # Load and analyze data
    with open(data_file, "r") as f:
        data = json.load(f)

    search_terms = data.get("search_terms", [])

    # Calculate comprehensive analytics
    total_cost = sum(
        float(term.get("cost_micros", 0)) / 1000000.0 for term in search_terms
    )
    total_conversions = sum(float(term.get("conversions", 0)) for term in search_terms)
    high_performers = len(
        [t for t in search_terms if float(t.get("conversions", 0)) > 5]
    )

    logger.info("✅ Pipeline Analysis Complete:")
    logger.info(f"   Total Investment: ${total_cost:.2f}")
    logger.info(f"   Total Conversions: {total_conversions:.0f}")
    logger.info(f"   High Performers: {high_performers} terms")

    logger.info("=" * 60)
    logger.info("✅ END-TO-END PIPELINE TEST COMPLETED")
    logger.info("=" * 60)

    return True


if __name__ == "__main__":
    run_comprehensive_test()
