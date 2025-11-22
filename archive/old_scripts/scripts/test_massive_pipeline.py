#!/usr/bin/env python3
"""
Production Scale Pipeline Testing with Massive TopGolf Dataset
Tests the complete pipeline with 206,676 search terms
"""

import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime
from typing import Any, Dict, List

import psutil

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
logger = logging.getLogger(__name__)


class MassivePipelineTester:
    """Test complete pipeline with massive dataset"""

    def __init__(self, massive_data_file: str):
        self.massive_data_file = massive_data_file
        self.start_time = time.time()
        self.process = psutil.Process()
        self.initial_memory = self.process.memory_info().rss / 1024 / 1024  # MB

    def log_performance_metrics(self, stage: str):
        """Log current performance metrics"""
        current_time = time.time()
        elapsed = current_time - self.start_time
        memory_mb = self.process.memory_info().rss / 1024 / 1024
        memory_delta = memory_mb - self.initial_memory

        logger.info(f"🔍 {stage} Performance:")
        logger.info(f"   Elapsed Time: {elapsed:.1f} seconds")
        logger.info(f"   Memory Usage: {memory_mb:.1f} MB (+{memory_delta:.1f} MB)")
        logger.info(f"   CPU Percent: {self.process.cpu_percent():.1f}%")

    def load_massive_dataset(self) -> Dict[str, Any]:
        """Load massive dataset and validate size"""
        logger.info("📥 Loading massive dataset...")
        logger.info(f"   File: {self.massive_data_file}")

        load_start = time.time()

        with open(self.massive_data_file, "r") as f:
            data = json.load(f)

        load_time = time.time() - load_start
        file_size_mb = os.path.getsize(self.massive_data_file) / 1024 / 1024

        search_terms_count = len(data.get("search_terms", []))
        keywords_count = len(data.get("keywords", []))

        logger.info("✅ Massive Dataset Loaded Successfully:")
        logger.info(f"   Search Terms: {search_terms_count:,}")
        logger.info(f"   Keywords: {keywords_count:,}")
        logger.info(f"   File Size: {file_size_mb:.1f} MB")
        logger.info(f"   Load Time: {load_time:.1f} seconds")

        self.log_performance_metrics("Data Loading")

        return data

    def test_data_processing(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Test data processing and validation at scale"""
        logger.info("🔄 Testing Data Processing at Scale...")

        search_terms = data.get("search_terms", [])
        keywords = data.get("keywords", [])

        process_start = time.time()

        # Simulate processing tasks
        results = {
            "data_validation": self.validate_data_quality(search_terms),
            "performance_metrics": self.calculate_performance_metrics(search_terms),
            "cost_analysis": self.analyze_cost_distribution(search_terms),
            "conversion_analysis": self.analyze_conversion_patterns(search_terms),
        }

        process_time = time.time() - process_start

        logger.info(f"✅ Data Processing Complete: {process_time:.1f} seconds")
        self.log_performance_metrics("Data Processing")

        return results

    def validate_data_quality(self, search_terms: List[Dict]) -> Dict[str, Any]:
        """Validate data quality across massive dataset"""
        logger.info("   🔍 Validating data quality...")

        total_terms = len(search_terms)
        valid_terms = 0
        missing_fields = 0
        zero_impression_terms = 0
        high_cost_terms = 0

        for term in search_terms:
            # Check required fields
            required_fields = [
                "search_term",
                "clicks",
                "impressions",
                "cost_micros",
                "conversions",
            ]
            if all(
                field in term and term[field] is not None for field in required_fields
            ):
                valid_terms += 1
            else:
                missing_fields += 1

            # Check data patterns
            if term.get("impressions", 0) == 0:
                zero_impression_terms += 1

            if term.get("cost_micros", 0) > 100_000_000:  # $100+ per term
                high_cost_terms += 1

        return {
            "total_terms": total_terms,
            "valid_terms": valid_terms,
            "data_quality_rate": round((valid_terms / total_terms) * 100, 2),
            "missing_fields": missing_fields,
            "zero_impression_terms": zero_impression_terms,
            "high_cost_terms": high_cost_terms,
        }

    def calculate_performance_metrics(self, search_terms: List[Dict]) -> Dict[str, Any]:
        """Calculate aggregate performance metrics"""
        logger.info("   📊 Calculating performance metrics...")

        total_cost = (
            sum(term.get("cost_micros", 0) for term in search_terms) / 1_000_000
        )
        total_clicks = sum(term.get("clicks", 0) for term in search_terms)
        total_impressions = sum(term.get("impressions", 0) for term in search_terms)
        total_conversions = sum(term.get("conversions", 0) for term in search_terms)

        return {
            "total_ad_spend": round(total_cost, 2),
            "total_clicks": total_clicks,
            "total_impressions": total_impressions,
            "total_conversions": total_conversions,
            "overall_ctr": round((total_clicks / total_impressions) * 100, 2)
            if total_impressions > 0
            else 0,
            "overall_conversion_rate": round(
                (total_conversions / total_clicks) * 100, 2
            )
            if total_clicks > 0
            else 0,
            "average_cpa": round(total_cost / total_conversions, 2)
            if total_conversions > 0
            else 0,
            "average_cpc": round(total_cost / total_clicks, 2)
            if total_clicks > 0
            else 0,
        }

    def analyze_cost_distribution(self, search_terms: List[Dict]) -> Dict[str, Any]:
        """Analyze cost distribution patterns"""
        logger.info("   💰 Analyzing cost distribution...")

        costs = [term.get("cost_micros", 0) / 1_000_000 for term in search_terms]
        costs.sort(reverse=True)

        # Top spending terms
        top_10_percent_count = len(costs) // 10
        top_10_percent_cost = sum(costs[:top_10_percent_count])
        total_cost = sum(costs)

        # Cost brackets
        high_cost = len([c for c in costs if c > 100])
        medium_cost = len([c for c in costs if 10 <= c <= 100])
        low_cost = len([c for c in costs if c < 10])

        return {
            "total_cost": round(total_cost, 2),
            "top_10_percent_cost": round(top_10_percent_cost, 2),
            "top_10_percent_share": round((top_10_percent_cost / total_cost) * 100, 2)
            if total_cost > 0
            else 0,
            "high_cost_terms": high_cost,
            "medium_cost_terms": medium_cost,
            "low_cost_terms": low_cost,
            "max_term_cost": round(max(costs) if costs else 0, 2),
            "median_cost": round(costs[len(costs) // 2] if costs else 0, 2),
        }

    def analyze_conversion_patterns(self, search_terms: List[Dict]) -> Dict[str, Any]:
        """Analyze conversion patterns across massive dataset"""
        logger.info("   🎯 Analyzing conversion patterns...")

        converting_terms = [
            term for term in search_terms if term.get("conversions", 0) > 0
        ]
        high_converting = [
            term for term in search_terms if term.get("conversions", 0) >= 5
        ]
        zero_converting = [
            term for term in search_terms if term.get("conversions", 0) == 0
        ]

        return {
            "total_converting_terms": len(converting_terms),
            "high_converting_terms": len(high_converting),
            "zero_converting_terms": len(zero_converting),
            "conversion_term_rate": round(
                (len(converting_terms) / len(search_terms)) * 100, 2
            ),
            "high_conversion_rate": round(
                (len(high_converting) / len(search_terms)) * 100, 2
            ),
            "avg_conversions_per_term": round(
                sum(term.get("conversions", 0) for term in search_terms)
                / len(search_terms),
                2,
            ),
        }

    def test_ml_pipeline(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Test ML pipeline with massive dataset"""
        logger.info("🤖 Testing ML Pipeline at Scale...")

        try:
            # Import ML components
            from paidsearchnav.ml.feature_engineering import FeatureEngineer
            from paidsearchnav.ml.insights_generator import InsightsGenerator
            from paidsearchnav.ml.predictive_models import PredictiveModels

            search_terms = data.get("search_terms", [])

            ml_start = time.time()

            # Feature Engineering (sample for performance)
            sample_size = min(10000, len(search_terms))  # Sample for ML processing
            sample_terms = search_terms[:sample_size]

            logger.info(f"   🔧 Feature engineering on {sample_size:,} terms...")
            feature_engineer = FeatureEngineer()
            features = feature_engineer.engineer_features(sample_terms)

            logger.info("   🧠 Training predictive models...")
            models = PredictiveModels()
            model_results = models.train_and_evaluate(features)

            logger.info("   💡 Generating insights...")
            insights_gen = InsightsGenerator()
            insights = insights_gen.generate_comprehensive_insights(
                features, model_results
            )

            ml_time = time.time() - ml_start

            logger.info(f"✅ ML Pipeline Complete: {ml_time:.1f} seconds")
            self.log_performance_metrics("ML Pipeline")

            return {
                "ml_processing_time": ml_time,
                "sample_size_processed": sample_size,
                "features_generated": len(features) if features else 0,
                "models_trained": len(model_results) if model_results else 0,
                "insights_generated": len(insights) if insights else 0,
                "ml_success": True,
            }

        except Exception as e:
            logger.error(f"❌ ML Pipeline Error: {e}")
            return {"ml_processing_time": 0, "ml_success": False, "error": str(e)}

    def test_analyzer_performance(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Test analyzer performance with sample of massive dataset"""
        logger.info("🔍 Testing Analyzer Performance...")

        try:
            # Import analyzers
            from paidsearchnav.analyzers.keyword_analyzer import KeywordAnalyzer
            from paidsearchnav.analyzers.search_terms import SearchTermsAnalyzer

            search_terms = data.get("search_terms", [])
            keywords = data.get("keywords", [])

            # Sample for analyzer testing (analyzers can be memory intensive)
            sample_size = min(5000, len(search_terms))
            sample_terms = search_terms[:sample_size]
            sample_keywords = keywords[: min(1000, len(keywords))]

            analyzer_start = time.time()

            logger.info(
                f"   📋 Testing search terms analyzer on {sample_size:,} terms..."
            )
            search_analyzer = SearchTermsAnalyzer()
            search_results = asyncio.run(
                search_analyzer.analyze(
                    sample_terms,
                    datetime.now().strftime("%Y-%m-%d"),
                    datetime.now().strftime("%Y-%m-%d"),
                )
            )

            logger.info(
                f"   🔑 Testing keyword analyzer on {len(sample_keywords):,} keywords..."
            )
            keyword_analyzer = KeywordAnalyzer()
            keyword_results = asyncio.run(
                keyword_analyzer.analyze(
                    sample_keywords,
                    datetime.now().strftime("%Y-%m-%d"),
                    datetime.now().strftime("%Y-%m-%d"),
                )
            )

            analyzer_time = time.time() - analyzer_start

            logger.info(
                f"✅ Analyzer Performance Test Complete: {analyzer_time:.1f} seconds"
            )
            self.log_performance_metrics("Analyzer Performance")

            return {
                "analyzer_processing_time": analyzer_time,
                "sample_terms_processed": sample_size,
                "sample_keywords_processed": len(sample_keywords),
                "search_analyzer_success": search_results is not None,
                "keyword_analyzer_success": keyword_results is not None,
                "analyzers_success": True,
            }

        except Exception as e:
            logger.error(f"❌ Analyzer Performance Error: {e}")
            return {
                "analyzer_processing_time": 0,
                "analyzers_success": False,
                "error": str(e),
            }

    def run_comprehensive_test(self) -> Dict[str, Any]:
        """Run comprehensive pipeline test"""
        logger.info("🚀 MASSIVE SCALE PIPELINE TESTING")
        logger.info("=" * 80)
        logger.info("Testing complete pipeline with 206,676+ search terms")
        logger.info("=" * 80)

        try:
            # Load massive dataset
            data = self.load_massive_dataset()

            # Test data processing
            processing_results = self.test_data_processing(data)

            # Test ML pipeline
            ml_results = self.test_ml_pipeline(data)

            # Test analyzer performance
            analyzer_results = self.test_analyzer_performance(data)

            # Calculate total execution time
            total_time = time.time() - self.start_time
            final_memory = self.process.memory_info().rss / 1024 / 1024
            memory_peak = final_memory - self.initial_memory

            # Compile comprehensive results
            results = {
                "test_timestamp": datetime.now().isoformat(),
                "test_duration_seconds": round(total_time, 1),
                "initial_memory_mb": round(self.initial_memory, 1),
                "final_memory_mb": round(final_memory, 1),
                "memory_peak_mb": round(memory_peak, 1),
                "dataset_info": {
                    "search_terms": len(data.get("search_terms", [])),
                    "keywords": len(data.get("keywords", [])),
                    "campaigns": len(data.get("campaigns", [])),
                    "total_ad_spend": data.get("summary", {}).get("total_ad_spend", 0),
                },
                "processing_results": processing_results,
                "ml_results": ml_results,
                "analyzer_results": analyzer_results,
                "overall_success": (
                    processing_results.get("data_quality_rate", 0) > 95
                    and ml_results.get("ml_success", False)
                    and analyzer_results.get("analyzers_success", False)
                ),
            }

            logger.info("=" * 80)
            logger.info("✅ MASSIVE SCALE PIPELINE TESTING COMPLETE")
            logger.info("=" * 80)
            logger.info("📊 Final Results:")
            logger.info(f"   Total Execution Time: {total_time:.1f} seconds")
            logger.info(f"   Memory Peak Usage: {memory_peak:.1f} MB")
            logger.info(
                f"   Search Terms Processed: {len(data.get('search_terms', [])):,}"
            )
            logger.info(
                f"   Total Ad Spend Analyzed: ${results['dataset_info']['total_ad_spend']:,.2f}"
            )
            logger.info(
                f"   Overall Success: {'✅ PASS' if results['overall_success'] else '❌ FAIL'}"
            )

            return results

        except Exception as e:
            logger.error(f"❌ Massive Scale Pipeline Test Failed: {e}")
            raise


def main():
    """Main testing function"""
    # Find the massive dataset file
    massive_data_file = "/Users/robertwelborn/PycharmProjects/PaidSearchNav/topgolf_massive_dataset_20250823_131943.json"

    if not os.path.exists(massive_data_file):
        logger.error(f"❌ Massive dataset file not found: {massive_data_file}")
        return False

    # Run comprehensive test
    tester = MassivePipelineTester(massive_data_file)
    results = tester.run_comprehensive_test()

    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"/Users/robertwelborn/PycharmProjects/PaidSearchNav/massive_pipeline_test_results_{timestamp}.json"

    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)

    logger.info(f"💾 Results saved to: {output_file}")

    return results["overall_success"]


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
