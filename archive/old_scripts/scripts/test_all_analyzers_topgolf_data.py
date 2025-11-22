#!/usr/bin/env python3
"""
Test All 21 Analyzers Against TopGolf Real Data
Comprehensive analyzer testing with the extracted TopGolf dataset
"""

import json
import logging
import os
import sys
from datetime import datetime
from typing import Any, Dict, List

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Import all analyzers (using correct class names)
from paidsearchnav.analyzers.ad_group_performance import AdGroupPerformanceAnalyzer
from paidsearchnav.analyzers.advanced_bid_adjustment import (
    AdvancedBidAdjustmentAnalyzer,
)
from paidsearchnav.analyzers.bulk_negative_manager import BulkNegativeManagerAnalyzer
from paidsearchnav.analyzers.campaign_overlap import CampaignOverlapAnalyzer
from paidsearchnav.analyzers.competitor_insights import CompetitorInsightsAnalyzer
from paidsearchnav.analyzers.dayparting import DaypartingAnalyzer
from paidsearchnav.analyzers.demographics import DemographicsAnalyzer
from paidsearchnav.analyzers.device_performance import DevicePerformanceAnalyzer
from paidsearchnav.analyzers.geo_performance import GeoPerformanceAnalyzer
from paidsearchnav.analyzers.keyword_analyzer import KeywordAnalyzer
from paidsearchnav.analyzers.keyword_match import KeywordMatchAnalyzer
from paidsearchnav.analyzers.landing_page import LandingPageAnalyzer
from paidsearchnav.analyzers.local_reach_store_performance import (
    LocalReachStoreAnalyzer,
)
from paidsearchnav.analyzers.negative_conflicts import NegativeConflictAnalyzer
from paidsearchnav.analyzers.placement_audit import PlacementAuditAnalyzer
from paidsearchnav.analyzers.pmax import PerformanceMaxAnalyzer
from paidsearchnav.analyzers.search_term_analyzer import SearchTermAnalyzer
from paidsearchnav.analyzers.search_terms import SearchTermsAnalyzer
from paidsearchnav.analyzers.shared_negatives import SharedNegativeValidatorAnalyzer
from paidsearchnav.analyzers.store_performance import StorePerformanceAnalyzer
from paidsearchnav.analyzers.video_creative import VideoCreativeAnalyzer
from paidsearchnav.core.config import Settings

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TopGolfAnalyzerTester:
    """Test all analyzers with TopGolf real data"""

    def __init__(self, data_file_path: str):
        """Initialize with TopGolf data file path"""
        self.data_file_path = data_file_path
        self.data = self._load_data()
        self.results = {}
        self.settings = Settings.from_env()

        # Initialize all 21 analyzers (using correct class names)
        self.analyzers = {
            "SearchTermsAnalyzer": SearchTermsAnalyzer(self.settings),
            "SearchTermAnalyzer": SearchTermAnalyzer(self.settings),
            "KeywordAnalyzer": KeywordAnalyzer(self.settings),
            "DevicePerformanceAnalyzer": DevicePerformanceAnalyzer(self.settings),
            "GeoPerformanceAnalyzer": GeoPerformanceAnalyzer(self.settings),
            "DaypartingAnalyzer": DaypartingAnalyzer(self.settings),
            "DemographicsAnalyzer": DemographicsAnalyzer(self.settings),
            "AdGroupPerformanceAnalyzer": AdGroupPerformanceAnalyzer(self.settings),
            "CampaignOverlapAnalyzer": CampaignOverlapAnalyzer(self.settings),
            "NegativeConflictAnalyzer": NegativeConflictAnalyzer(self.settings),
            "SharedNegativeValidatorAnalyzer": SharedNegativeValidatorAnalyzer(
                self.settings
            ),
            "CompetitorInsightsAnalyzer": CompetitorInsightsAnalyzer(self.settings),
            "LandingPageAnalyzer": LandingPageAnalyzer(self.settings),
            "VideoCreativeAnalyzer": VideoCreativeAnalyzer(self.settings),
            "PlacementAuditAnalyzer": PlacementAuditAnalyzer(self.settings),
            "PerformanceMaxAnalyzer": PerformanceMaxAnalyzer(self.settings),
            "StorePerformanceAnalyzer": StorePerformanceAnalyzer(self.settings),
            "LocalReachStoreAnalyzer": LocalReachStoreAnalyzer(self.settings),
            "KeywordMatchAnalyzer": KeywordMatchAnalyzer(self.settings),
            "AdvancedBidAdjustmentAnalyzer": AdvancedBidAdjustmentAnalyzer(
                self.settings
            ),
            "BulkNegativeManagerAnalyzer": BulkNegativeManagerAnalyzer(self.settings),
        }

    def _load_data(self) -> Dict[str, Any]:
        """Load TopGolf data from JSON file"""
        try:
            with open(self.data_file_path, "r") as f:
                data = json.load(f)
            logger.info(
                f"✅ Loaded TopGolf data: {len(data.get('search_terms', []))} search terms, "
                f"{len(data.get('keywords', []))} keywords, {len(data.get('campaigns', []))} campaigns"
            )
            return data
        except Exception as e:
            logger.error(f"❌ Error loading data from {self.data_file_path}: {e}")
            raise

    def _convert_to_analyzer_format(
        self, data_type: str, raw_data: List[Dict]
    ) -> List[Dict]:
        """Convert TopGolf JSON data to format expected by analyzers"""
        if data_type == "search_terms":
            return [
                {
                    "customer_id": item.get("customer_id", "577-746-1198"),
                    "date": item.get("date", "2025-08-15"),
                    "campaign_id": item.get("campaign_id"),
                    "campaign_name": item.get("campaign_name"),
                    "ad_group_id": item.get("ad_group_id"),
                    "ad_group_name": item.get("ad_group_name"),
                    "search_term": item.get("search_term"),
                    "impressions": int(item.get("impressions", 0)),
                    "clicks": int(item.get("clicks", 0)),
                    "cost": float(item.get("cost_micros", 0)) / 1000000.0,
                    "conversions": float(item.get("conversions", 0)),
                    "conversions_value": float(item.get("conversions_value", 0)),
                    "local_intent_score": float(item.get("local_intent_score", 0)),
                    "negative_recommendation": item.get(
                        "negative_recommendation", "KEEP_ACTIVE"
                    ),
                }
                for item in raw_data
            ]

        elif data_type == "keywords":
            return [
                {
                    "customer_id": item.get("customer_id", "577-746-1198"),
                    "date": item.get("date", "2025-08-15"),
                    "campaign_id": item.get("campaign_id"),
                    "campaign_name": item.get("campaign_name"),
                    "ad_group_id": item.get("ad_group_id"),
                    "ad_group_name": item.get("ad_group_name"),
                    "keyword": item.get("keyword"),
                    "match_type": item.get("match_type", "BROAD"),
                    "impressions": int(item.get("impressions", 0)),
                    "clicks": int(item.get("clicks", 0)),
                    "cost": float(item.get("cost_micros", 0)) / 1000000.0,
                    "conversions": float(item.get("conversions", 0)),
                    "conversions_value": float(item.get("conversions_value", 0)),
                    "quality_score": float(item.get("quality_score", 0)),
                    "cpc_bid": float(item.get("cpc_bid_micros", 0)) / 1000000.0,
                }
                for item in raw_data
            ]

        elif data_type == "campaigns":
            return [
                {
                    "customer_id": item.get("customer_id", "577-746-1198"),
                    "date": item.get("date", "2025-08-15"),
                    "campaign_id": item.get("campaign_id"),
                    "campaign_name": item.get("campaign_name"),
                    "campaign_type": item.get("campaign_type", "SEARCH"),
                    "impressions": int(item.get("impressions", 0)),
                    "clicks": int(item.get("clicks", 0)),
                    "cost": float(item.get("cost_micros", 0)) / 1000000.0,
                    "conversions": float(item.get("conversions", 0)),
                    "conversions_value": float(item.get("conversions_value", 0)),
                }
                for item in raw_data
            ]

        return raw_data

    def test_analyzer(self, name: str, analyzer) -> Dict[str, Any]:
        """Test a single analyzer with TopGolf data"""
        logger.info(f"🔍 Testing {name}...")

        try:
            # Prepare data based on analyzer requirements
            if "SearchTerms" in name:
                test_data = self._convert_to_analyzer_format(
                    "search_terms", self.data.get("search_terms", [])
                )
            elif "Keyword" in name:
                test_data = self._convert_to_analyzer_format(
                    "keywords", self.data.get("keywords", [])
                )
            elif "Campaign" in name:
                test_data = self._convert_to_analyzer_format(
                    "campaigns", self.data.get("campaigns", [])
                )
            else:
                # Use search terms as default for analyzers that can work with general data
                test_data = self._convert_to_analyzer_format(
                    "search_terms", self.data.get("search_terms", [])
                )

            if not test_data:
                return {
                    "status": "skipped",
                    "reason": "No suitable data available",
                    "data_points": 0,
                }

            # Run the analyzer
            start_time = datetime.now()
            start_date = "2025-08-24"
            end_date = "2025-08-31"

            if hasattr(analyzer, "analyze"):
                # Try calling analyze with different parameter combinations
                try:
                    result = analyzer.analyze(test_data, start_date, end_date)
                except TypeError:
                    try:
                        result = analyzer.analyze(test_data)
                    except TypeError as e:
                        return {
                            "status": "error",
                            "reason": f"Could not call analyze method: {str(e)}",
                            "data_points": len(test_data),
                        }
            elif hasattr(analyzer, "run_analysis"):
                try:
                    result = analyzer.run_analysis(test_data, start_date, end_date)
                except TypeError:
                    try:
                        result = analyzer.run_analysis(test_data)
                    except TypeError as e:
                        return {
                            "status": "error",
                            "reason": f"Could not call run_analysis method: {str(e)}",
                            "data_points": len(test_data),
                        }
            else:
                # Try to find any analysis method
                methods = [
                    method
                    for method in dir(analyzer)
                    if "analyze" in method.lower() and not method.startswith("_")
                ]
                if methods:
                    method = getattr(analyzer, methods[0])
                    try:
                        result = method(test_data, start_date, end_date)
                    except TypeError:
                        try:
                            result = method(test_data)
                        except TypeError as e:
                            return {
                                "status": "error",
                                "reason": f"Could not call {methods[0]} method: {str(e)}",
                                "data_points": len(test_data),
                            }
                else:
                    return {
                        "status": "error",
                        "reason": f"No suitable analysis method found for {name}",
                        "data_points": len(test_data),
                    }

            end_time = datetime.now()
            execution_time = (end_time - start_time).total_seconds()

            return {
                "status": "success",
                "data_points": len(test_data),
                "execution_time_seconds": execution_time,
                "result_summary": self._summarize_result(result),
                "has_recommendations": bool(
                    result.get("recommendations")
                    or result.get("negative_keywords")
                    or result.get("opportunities")
                ),
            }

        except Exception as e:
            logger.error(f"❌ Error testing {name}: {e}")
            return {
                "status": "error",
                "reason": str(e),
                "data_points": len(test_data) if "test_data" in locals() else 0,
            }

    def _summarize_result(self, result: Any) -> Dict[str, Any]:
        """Create a summary of analyzer results"""
        if not result:
            return {"type": "empty"}

        if isinstance(result, dict):
            summary = {"type": "dict", "keys": list(result.keys())}

            # Count recommendations/opportunities
            if "recommendations" in result:
                summary["recommendation_count"] = (
                    len(result["recommendations"])
                    if isinstance(result["recommendations"], list)
                    else 1
                )
            if "negative_keywords" in result:
                summary["negative_keyword_count"] = (
                    len(result["negative_keywords"])
                    if isinstance(result["negative_keywords"], list)
                    else 1
                )
            if "opportunities" in result:
                summary["opportunity_count"] = (
                    len(result["opportunities"])
                    if isinstance(result["opportunities"], list)
                    else 1
                )

            return summary

        elif isinstance(result, list):
            return {"type": "list", "length": len(result)}

        else:
            return {"type": type(result).__name__}

    def run_all_tests(self) -> Dict[str, Any]:
        """Run all analyzer tests"""
        logger.info("🚀 STARTING COMPREHENSIVE ANALYZER TESTING")
        logger.info("=" * 60)
        logger.info("TopGolf Customer ID: 577-746-1198")
        logger.info(f"Data File: {self.data_file_path}")
        logger.info(f"Total Analyzers: {len(self.analyzers)}")
        logger.info("=" * 60)

        results = {}
        successful_tests = 0
        failed_tests = 0
        skipped_tests = 0

        for name, analyzer in self.analyzers.items():
            result = self.test_analyzer(name, analyzer)
            results[name] = result

            if result["status"] == "success":
                successful_tests += 1
                logger.info(
                    f"✅ {name}: {result['data_points']} data points, {result['execution_time_seconds']:.2f}s"
                )
            elif result["status"] == "error":
                failed_tests += 1
                logger.error(f"❌ {name}: {result['reason']}")
            else:
                skipped_tests += 1
                logger.warning(f"⚠️ {name}: {result['reason']}")

        # Generate summary report
        summary = {
            "timestamp": datetime.now().isoformat(),
            "customer_id": "577-746-1198",
            "data_source": self.data_file_path,
            "total_analyzers": len(self.analyzers),
            "successful_tests": successful_tests,
            "failed_tests": failed_tests,
            "skipped_tests": skipped_tests,
            "success_rate": f"{(successful_tests / len(self.analyzers) * 100):.1f}%",
            "analyzer_results": results,
        }

        logger.info("=" * 60)
        logger.info("🏆 ANALYZER TESTING SUMMARY")
        logger.info("=" * 60)
        logger.info(
            f"✅ Successful: {successful_tests}/{len(self.analyzers)} ({summary['success_rate']})"
        )
        logger.info(f"❌ Failed: {failed_tests}/{len(self.analyzers)}")
        logger.info(f"⚠️ Skipped: {skipped_tests}/{len(self.analyzers)}")

        return summary

    def save_results(self, results: Dict[str, Any]) -> str:
        """Save test results to file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"/Users/robertwelborn/PycharmProjects/PaidSearchNav/topgolf_analyzer_test_results_{timestamp}.json"

        with open(output_path, "w") as f:
            json.dump(results, f, indent=2)

        logger.info(f"💾 Results saved to: {output_path}")
        return output_path


def main():
    """Main test execution"""
    data_file = "/Users/robertwelborn/PycharmProjects/PaidSearchNav/customers/topgolf/topgolf_real_data_20250822_181442.json"

    if not os.path.exists(data_file):
        logger.error(f"❌ Data file not found: {data_file}")
        return False

    # Initialize tester
    tester = TopGolfAnalyzerTester(data_file)

    # Run all tests
    results = tester.run_all_tests()

    # Save results
    output_path = tester.save_results(results)

    # Generate markdown report
    markdown_path = generate_markdown_report(results, output_path)

    logger.info("=" * 60)
    logger.info("✅ ANALYZER TESTING COMPLETED")
    logger.info("=" * 60)
    logger.info(f"JSON Results: {output_path}")
    logger.info(f"Markdown Report: {markdown_path}")

    return results["success_rate"] != "0.0%"


def generate_markdown_report(results: Dict[str, Any], json_path: str) -> str:
    """Generate a markdown report of analyzer test results"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = f"/Users/robertwelborn/PycharmProjects/PaidSearchNav/topgolf_analyzer_test_report_{timestamp}.md"

    with open(report_path, "w") as f:
        f.write("# TopGolf Analyzer Testing Report\n\n")
        f.write(f"**Generated:** {results['timestamp']}\n")
        f.write(f"**Customer ID:** {results['customer_id']}\n")
        f.write(f"**Data Source:** {results['data_source']}\n")
        f.write(f"**Success Rate:** {results['success_rate']}\n\n")

        f.write("## Summary\n")
        f.write(
            f"- ✅ Successful: {results['successful_tests']}/{results['total_analyzers']}\n"
        )
        f.write(
            f"- ❌ Failed: {results['failed_tests']}/{results['total_analyzers']}\n"
        )
        f.write(
            f"- ⚠️ Skipped: {results['skipped_tests']}/{results['total_analyzers']}\n\n"
        )

        f.write("## Detailed Results\n\n")

        for analyzer_name, result in results["analyzer_results"].items():
            f.write(f"### {analyzer_name}\n")
            f.write(f"**Status:** {result['status'].upper()}\n")
            f.write(f"**Data Points:** {result['data_points']}\n")

            if result["status"] == "success":
                f.write(
                    f"**Execution Time:** {result['execution_time_seconds']:.2f}s\n"
                )
                f.write(f"**Has Recommendations:** {result['has_recommendations']}\n")
                f.write(f"**Result Summary:** {result['result_summary']}\n")
            elif result["status"] == "error":
                f.write(f"**Error:** {result['reason']}\n")
            else:
                f.write(f"**Reason:** {result['reason']}\n")

            f.write("\n")

        f.write("## Next Steps\n")
        f.write("1. Review failed analyzers and fix any issues\n")
        f.write("2. Test ML model training with this validated data\n")
        f.write("3. Run API endpoint tests\n")
        f.write("4. Execute end-to-end pipeline test\n")

    return report_path


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
