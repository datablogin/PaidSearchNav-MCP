#!/usr/bin/env python3
"""
Export Comprehensive Actionable Data for TopGolf
================================================

This script runs all analyzers against live TopGolf data and exports
specific, actionable lists that can be used directly in Google Ads Editor
or campaign management tools.

Usage:
    python scripts/export_topgolf_actionable_data.py --config configs/topgolf.json --date-range 2025-08-24:2025-08-31
"""

import argparse
import asyncio
import csv
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# ruff: noqa: E402
from paidsearchnav.analyzers import (
    DaypartingAnalyzer,
    GeoPerformanceAnalyzer,
    KeywordAnalyzer,
    NegativeConflictAnalyzer,
    PerformanceMaxAnalyzer,
    SearchTermsAnalyzer,
)
from paidsearchnav.core.config import Settings
from paidsearchnav.data_providers.google_ads import GoogleAdsDataProvider

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class ActionableDataExporter:
    """Export actionable data from all analyzer results for any client."""

    def __init__(self, config_file: Path | None = None):
        """Initialize with optional client config."""
        self.settings = Settings.from_env(client_config_file=config_file)

        # Load customer ID from config file
        if config_file and config_file.exists():
            import json

            with open(config_file) as f:
                client_config = json.load(f)
            self.customer_id = client_config["customer_id"]
            client_name = client_config["client_name"].lower().replace(" ", "_")
            self.output_dir = Path(f"customers/{client_name}")
        else:
            raise ValueError(
                "Config file is required to determine customer ID and output directory"
            )

        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize Google Ads API client
        from paidsearchnav.platforms.google.client import GoogleAdsAPIClient

        api_client = GoogleAdsAPIClient(
            developer_token=self.settings.google_ads.developer_token.get_secret_value(),
            client_id=self.settings.google_ads.client_id,
            client_secret=self.settings.google_ads.client_secret.get_secret_value(),
            refresh_token=self.settings.google_ads.refresh_token.get_secret_value(),
            settings=self.settings,
        )

        # Initialize data provider
        self.provider = GoogleAdsDataProvider(api_client)

        # Results storage
        self.actionable_data = {
            "keywords_to_pause": [],
            "keywords_to_optimize": [],
            "keywords_to_increase_bids": [],
            "keywords_to_decrease_bids": [],
            "ad_groups_to_consolidate": [],
            "campaigns_to_adjust": [],
            "search_terms_to_add": [],
            "search_terms_to_negative": [],
            "geo_adjustments": [],
            "dayparting_adjustments": [],
            "negative_conflicts": [],
            "pmax_optimizations": [],
        }

    async def run_all_analyzers(self, start_date: datetime, end_date: datetime):
        """Run all analyzers and extract actionable data."""
        logger.info(
            f"🚀 Running comprehensive analysis for TopGolf ({self.customer_id})"
        )
        logger.info(f"📅 Date range: {start_date.date()} to {end_date.date()}")

        # 1. Keyword Analysis
        await self._run_keyword_analysis(start_date, end_date)

        # 2. Search Terms Analysis
        await self._run_search_terms_analysis(start_date, end_date)

        # 3. Geo Performance Analysis
        await self._run_geo_analysis(start_date, end_date)

        # 4. Dayparting Analysis
        await self._run_dayparting_analysis(start_date, end_date)

        # 5. Negative Conflict Analysis
        await self._run_negative_conflict_analysis(start_date, end_date)

        # 6. Performance Max Analysis
        await self._run_pmax_analysis(start_date, end_date)

    async def _run_keyword_analysis(self, start_date: datetime, end_date: datetime):
        """Extract actionable keyword data."""
        logger.info("🔍 Running KeywordAnalyzer...")

        try:
            analyzer = KeywordAnalyzer(self.provider)
            result = await analyzer.analyze(
                customer_id=self.customer_id, start_date=start_date, end_date=end_date
            )

            # Extract specific actionable lists
            if hasattr(result, "high_cost_low_conversion"):
                self.actionable_data["keywords_to_pause"] = [
                    {
                        "keyword_text": getattr(k, "keyword_text", str(k)),
                        "keyword_id": getattr(k, "id", None),
                        "campaign_name": getattr(k, "campaign_name", None),
                        "ad_group_name": getattr(k, "ad_group_name", None),
                        "cost": getattr(k, "cost", 0),
                        "conversions": getattr(k, "conversions", 0),
                        "reason": "High cost, zero conversions",
                    }
                    for k in result.high_cost_low_conversion[:20]
                ]

            if hasattr(result, "low_quality_keywords"):
                self.actionable_data["keywords_to_optimize"] = [
                    {
                        "keyword_text": getattr(k, "keyword_text", str(k)),
                        "keyword_id": getattr(k, "id", None),
                        "campaign_name": getattr(k, "campaign_name", None),
                        "ad_group_name": getattr(k, "ad_group_name", None),
                        "quality_score": getattr(k, "quality_score", None),
                        "cost": getattr(k, "cost", 0),
                        "reason": "Low quality score",
                    }
                    for k in result.low_quality_keywords[:20]
                ]

            logger.info(
                f"✅ KeywordAnalyzer: {len(self.actionable_data['keywords_to_pause'])} to pause, {len(self.actionable_data['keywords_to_optimize'])} to optimize"
            )

        except Exception as e:
            logger.error(f"❌ KeywordAnalyzer failed: {e}")

    async def _run_search_terms_analysis(
        self, start_date: datetime, end_date: datetime
    ):
        """Extract actionable search terms data."""
        logger.info("🔍 Running SearchTermsAnalyzer...")

        try:
            analyzer = SearchTermsAnalyzer(self.provider)
            result = await analyzer.analyze(
                customer_id=self.customer_id, start_date=start_date, end_date=end_date
            )

            # Extract add candidates and negative candidates
            if hasattr(result, "analysis_metrics") and hasattr(
                result.analysis_metrics, "metadata"
            ):
                metadata = result.analysis_metrics.metadata

                # Add candidates (high-performing search terms to add as keywords)
                if "add_candidates" in metadata:
                    self.actionable_data["search_terms_to_add"] = [
                        {
                            "search_term": term.get("search_term", ""),
                            "campaign_name": term.get("campaign_name", ""),
                            "ad_group_name": term.get("ad_group_name", ""),
                            "conversions": term.get("conversions", 0),
                            "cost": term.get("cost", 0),
                            "clicks": term.get("clicks", 0),
                            "ctr": term.get("ctr", 0),
                            "conversion_rate": term.get("conversion_rate", 0),
                            "reason": "High-performing search term",
                        }
                        for term in metadata["add_candidates"][:50]
                    ]

                # Negative candidates (wasteful search terms to block)
                if "negative_candidates" in metadata:
                    self.actionable_data["search_terms_to_negative"] = [
                        {
                            "search_term": term.get("search_term", ""),
                            "campaign_name": term.get("campaign_name", ""),
                            "ad_group_name": term.get("ad_group_name", ""),
                            "cost": term.get("cost", 0),
                            "conversions": term.get("conversions", 0),
                            "clicks": term.get("clicks", 0),
                            "reason": "Wasting budget",
                        }
                        for term in metadata["negative_candidates"][:50]
                    ]

            logger.info(
                f"✅ SearchTermsAnalyzer: {len(self.actionable_data['search_terms_to_add'])} to add, {len(self.actionable_data['search_terms_to_negative'])} to negative"
            )

        except Exception as e:
            logger.error(f"❌ SearchTermsAnalyzer failed: {e}")

    async def _run_geo_analysis(self, start_date: datetime, end_date: datetime):
        """Extract geo performance actionable data."""
        logger.info("🔍 Running GeoPerformanceAnalyzer...")

        try:
            analyzer = GeoPerformanceAnalyzer(self.provider)
            result = await analyzer.analyze(
                customer_id=self.customer_id, start_date=start_date, end_date=end_date
            )

            # Extract geo-specific adjustments
            self.actionable_data["geo_adjustments"] = [
                {
                    "location": rec.description,
                    "recommended_action": rec.title,
                    "priority": rec.priority.value
                    if hasattr(rec.priority, "value")
                    else str(rec.priority),
                }
                for rec in result.recommendations
            ]

            logger.info(
                f"✅ GeoPerformanceAnalyzer: {len(self.actionable_data['geo_adjustments'])} location adjustments"
            )

        except Exception as e:
            logger.error(f"❌ GeoPerformanceAnalyzer failed: {e}")

    async def _run_dayparting_analysis(self, start_date: datetime, end_date: datetime):
        """Extract dayparting actionable data."""
        logger.info("🔍 Running DaypartingAnalyzer...")

        try:
            analyzer = DaypartingAnalyzer(self.provider)
            result = await analyzer.analyze(
                customer_id=self.customer_id, start_date=start_date, end_date=end_date
            )

            self.actionable_data["dayparting_adjustments"] = [
                {
                    "time_period": rec.title,
                    "recommended_action": rec.description,
                    "priority": rec.priority.value
                    if hasattr(rec.priority, "value")
                    else str(rec.priority),
                }
                for rec in result.recommendations
            ]

            logger.info(
                f"✅ DaypartingAnalyzer: {len(self.actionable_data['dayparting_adjustments'])} time adjustments"
            )

        except Exception as e:
            logger.error(f"❌ DaypartingAnalyzer failed: {e}")

    async def _run_negative_conflict_analysis(
        self, start_date: datetime, end_date: datetime
    ):
        """Extract negative keyword conflicts."""
        logger.info("🔍 Running NegativeConflictAnalyzer...")

        try:
            analyzer = NegativeConflictAnalyzer(self.provider)
            result = await analyzer.analyze(
                customer_id=self.customer_id, start_date=start_date, end_date=end_date
            )

            self.actionable_data["negative_conflicts"] = [
                {
                    "conflict_description": rec.title,
                    "resolution": rec.description,
                    "priority": rec.priority.value
                    if hasattr(rec.priority, "value")
                    else str(rec.priority),
                }
                for rec in result.recommendations
            ]

            logger.info(
                f"✅ NegativeConflictAnalyzer: {len(self.actionable_data['negative_conflicts'])} conflicts found"
            )

        except Exception as e:
            logger.error(f"❌ NegativeConflictAnalyzer failed: {e}")

    async def _run_pmax_analysis(self, start_date: datetime, end_date: datetime):
        """Extract Performance Max optimizations."""
        logger.info("🔍 Running PerformanceMaxAnalyzer...")

        try:
            analyzer = PerformanceMaxAnalyzer(self.provider)
            result = await analyzer.analyze(
                customer_id=self.customer_id, start_date=start_date, end_date=end_date
            )

            self.actionable_data["pmax_optimizations"] = [
                {
                    "optimization_type": rec.title,
                    "description": rec.description,
                    "priority": rec.priority.value
                    if hasattr(rec.priority, "value")
                    else str(rec.priority),
                }
                for rec in result.recommendations
            ]

            logger.info(
                f"✅ PerformanceMaxAnalyzer: {len(self.actionable_data['pmax_optimizations'])} optimizations"
            )

        except Exception as e:
            logger.error(f"❌ PerformanceMaxAnalyzer failed: {e}")

    def export_to_csv(self):
        """Export actionable data to CSV files for campaign management."""
        logger.info("📊 Exporting actionable data to CSV files...")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Keywords to pause
        if self.actionable_data["keywords_to_pause"]:
            pause_file = (
                self.output_dir / f"actionable_keywords_to_pause_{timestamp}.csv"
            )
            with open(pause_file, "w", newline="") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=[
                        "keyword_text",
                        "keyword_id",
                        "campaign_name",
                        "ad_group_name",
                        "cost",
                        "conversions",
                        "reason",
                    ],
                )
                writer.writeheader()
                writer.writerows(self.actionable_data["keywords_to_pause"])
            logger.info(f"✅ Keywords to pause: {pause_file}")

        # Keywords to optimize
        if self.actionable_data["keywords_to_optimize"]:
            optimize_file = (
                self.output_dir / f"actionable_keywords_to_optimize_{timestamp}.csv"
            )
            with open(optimize_file, "w", newline="") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=[
                        "keyword_text",
                        "keyword_id",
                        "campaign_name",
                        "ad_group_name",
                        "quality_score",
                        "cost",
                        "reason",
                    ],
                )
                writer.writeheader()
                writer.writerows(self.actionable_data["keywords_to_optimize"])
            logger.info(f"✅ Keywords to optimize: {optimize_file}")

        # Search terms to add
        if self.actionable_data["search_terms_to_add"]:
            add_file = (
                self.output_dir / f"actionable_search_terms_to_add_{timestamp}.csv"
            )
            with open(add_file, "w", newline="") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=[
                        "search_term",
                        "campaign_name",
                        "ad_group_name",
                        "conversions",
                        "cost",
                        "clicks",
                        "ctr",
                        "conversion_rate",
                        "reason",
                    ],
                )
                writer.writeheader()
                writer.writerows(self.actionable_data["search_terms_to_add"])
            logger.info(f"✅ Search terms to add: {add_file}")

        # Search terms to negative
        if self.actionable_data["search_terms_to_negative"]:
            negative_file = (
                self.output_dir / f"actionable_search_terms_to_negative_{timestamp}.csv"
            )
            with open(negative_file, "w", newline="") as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=[
                        "search_term",
                        "campaign_name",
                        "ad_group_name",
                        "cost",
                        "conversions",
                        "clicks",
                        "reason",
                    ],
                )
                writer.writeheader()
                writer.writerows(self.actionable_data["search_terms_to_negative"])
            logger.info(f"✅ Search terms to negative: {negative_file}")

    def export_master_json(self):
        """Export comprehensive master JSON with all actionable data."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        master_file = self.output_dir / f"topgolf_complete_action_plan_{timestamp}.json"

        # Add summary statistics
        summary = {
            "export_timestamp": datetime.now().isoformat(),
            "customer_id": self.customer_id,
            "total_actionable_items": sum(
                len(items) for items in self.actionable_data.values()
            ),
            "summary": {
                "keywords_to_pause": len(self.actionable_data["keywords_to_pause"]),
                "keywords_to_optimize": len(
                    self.actionable_data["keywords_to_optimize"]
                ),
                "search_terms_to_add": len(self.actionable_data["search_terms_to_add"]),
                "search_terms_to_negative": len(
                    self.actionable_data["search_terms_to_negative"]
                ),
                "geo_adjustments": len(self.actionable_data["geo_adjustments"]),
                "dayparting_adjustments": len(
                    self.actionable_data["dayparting_adjustments"]
                ),
            },
        }

        export_data = {"summary": summary, "actionable_data": self.actionable_data}

        with open(master_file, "w") as f:
            json.dump(export_data, f, indent=2, default=str)

        logger.info(f"✅ Master action plan: {master_file}")
        return master_file

    def print_summary(self):
        """Print actionable summary."""
        logger.info("\n" + "=" * 60)
        logger.info("🎯 TOPGOLF ACTIONABLE RECOMMENDATIONS SUMMARY")
        logger.info("=" * 60)

        total_items = sum(len(items) for items in self.actionable_data.values())
        logger.info(f"📊 Total actionable items: {total_items}")

        if self.actionable_data["keywords_to_pause"]:
            total_waste = sum(
                item.get("cost", 0)
                for item in self.actionable_data["keywords_to_pause"]
            )
            logger.info(
                f"⏸️  Keywords to pause: {len(self.actionable_data['keywords_to_pause'])} (saves ${total_waste:.2f})"
            )

        if self.actionable_data["keywords_to_optimize"]:
            logger.info(
                f"🔧 Keywords to optimize: {len(self.actionable_data['keywords_to_optimize'])}"
            )

        if self.actionable_data["search_terms_to_add"]:
            potential_conversions = sum(
                item.get("conversions", 0)
                for item in self.actionable_data["search_terms_to_add"]
            )
            logger.info(
                f"➕ Search terms to add: {len(self.actionable_data['search_terms_to_add'])} ({potential_conversions} conversions)"
            )

        if self.actionable_data["search_terms_to_negative"]:
            waste_prevented = sum(
                item.get("cost", 0)
                for item in self.actionable_data["search_terms_to_negative"]
            )
            logger.info(
                f"🚫 Search terms to negative: {len(self.actionable_data['search_terms_to_negative'])} (prevents ${waste_prevented:.2f} waste)"
            )


def parse_date_range(date_range_str: str) -> tuple[datetime, datetime]:
    """Parse date range string in format YYYY-MM-DD:YYYY-MM-DD."""
    try:
        start_str, end_str = date_range_str.split(":")
        start_date = datetime.strptime(start_str, "%Y-%m-%d")
        end_date = datetime.strptime(end_str, "%Y-%m-%d")
        return start_date, end_date
    except ValueError:
        raise ValueError("Date range must be in format YYYY-MM-DD:YYYY-MM-DD")


async def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(description="Export TopGolf actionable data")
    parser.add_argument("--config", type=Path, help="Client config file")
    parser.add_argument(
        "--date-range", required=True, help="Date range in format YYYY-MM-DD:YYYY-MM-DD"
    )

    args = parser.parse_args()

    # Parse date range
    start_date, end_date = parse_date_range(args.date_range)

    # Initialize exporter
    exporter = ActionableDataExporter(args.config)

    try:
        # Run all analyzers
        await exporter.run_all_analyzers(start_date, end_date)

        # Export to CSV files
        exporter.export_to_csv()

        # Export master JSON
        master_file = exporter.export_master_json()

        # Print summary
        exporter.print_summary()

        logger.info("\n🎉 Export completed successfully!")
        logger.info(f"📁 Files saved in: {exporter.output_dir}")
        logger.info(f"📋 Master plan: {master_file}")

    except Exception as e:
        logger.error(f"❌ Export failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
