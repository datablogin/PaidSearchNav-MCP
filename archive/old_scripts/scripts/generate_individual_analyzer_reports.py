#!/usr/bin/env python3
"""
Generate individual analyzer reports for TopGolf customer
Runs each analyzer separately and creates standardized reports
"""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import pandas as pd

from paidsearchnav.analyzers import (
    AdGroupPerformanceAnalyzer,
    AdvancedBidAdjustmentAnalyzer,
    BulkNegativeManagerAnalyzer,
    CampaignOverlapAnalyzer,
    CompetitorInsightsAnalyzer,
    DaypartingAnalyzer,
    DemographicsAnalyzer,
    GeoPerformanceAnalyzer,
    KeywordAnalyzer,
    KeywordMatchAnalyzer,
    LandingPageAnalyzer,
    LocalReachStoreAnalyzer,
    NegativeConflictAnalyzer,
    PerformanceMaxAnalyzer,
    PlacementAuditAnalyzer,
    SearchTermAnalyzer,
    SearchTermsAnalyzer,
    SharedNegativeValidatorAnalyzer,
    VideoCreativeAnalyzer,
)


def setup_logging():
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )
    return logging.getLogger(__name__)


def load_topgolf_data() -> pd.DataFrame:
    """Load the massive TopGolf dataset"""
    data_file = Path("customers/topgolf/topgolf_massive_dataset_20250823_131943.json")
    if not data_file.exists():
        raise FileNotFoundError(f"TopGolf dataset not found at {data_file}")

    with open(data_file, "r") as f:
        data = json.load(f)

    # Extract the search_terms array which contains the actual data
    if "search_terms" in data:
        return pd.DataFrame(data["search_terms"])
    else:
        return pd.DataFrame(data)


def run_analyzer(
    analyzer_class, analyzer_name: str, df: pd.DataFrame, logger
) -> Dict[str, Any]:
    """Run a single analyzer and return results"""
    try:
        logger.info(f"Running {analyzer_name}...")

        # Initialize analyzer with required parameters
        analyzer = analyzer_class()

        # Add required date parameters for analyzers that need them
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 12, 31)

        # Run the analyzer
        if hasattr(analyzer, "analyze"):
            if analyzer_name in ["DaypartingAnalyzer"]:
                results = analyzer.analyze(df, start_date=start_date, end_date=end_date)
            else:
                results = analyzer.analyze(df)
        elif hasattr(analyzer, "process"):
            results = analyzer.process(df)
        else:
            results = {"error": "No analyze/process method found"}

        return {
            "success": True,
            "analyzer": analyzer_name,
            "results": results,
            "records_processed": len(df),
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Error running {analyzer_name}: {str(e)}")
        return {
            "success": False,
            "analyzer": analyzer_name,
            "error": str(e),
            "records_processed": len(df),
            "timestamp": datetime.now().isoformat(),
        }


def generate_report(analyzer_result: Dict[str, Any], date_str: str) -> str:
    """Generate markdown report for an analyzer"""
    analyzer_name = analyzer_result["analyzer"]
    success = analyzer_result["success"]

    # Create report content
    report = f"""# {analyzer_name} Analysis Report - TopGolf

**Generated:** {analyzer_result["timestamp"]}
**Customer:** TopGolf
**Records Processed:** {analyzer_result["records_processed"]:,}
**Status:** {"✅ SUCCESS" if success else "❌ FAILED"}

## Analysis Summary

"""

    if success:
        results = analyzer_result.get("results", {})

        # Extract key findings based on analyzer type
        if analyzer_name == "KeywordAnalyzer":
            report += f"""
### Key Findings
- Total keywords analyzed: {len(results.get("keywords", []))}
- High-performing keywords: {len([k for k in results.get("keywords", []) if k.get("performance_score", 0) > 0.7])}
- Underperforming keywords: {len([k for k in results.get("keywords", []) if k.get("performance_score", 0) < 0.3])}

### Recommendations
1. **Optimize Underperforming Keywords**: Focus on keywords with low performance scores
2. **Scale High Performers**: Increase budgets for top-performing keywords
3. **Match Type Optimization**: Review broad match keywords for efficiency
"""

        elif analyzer_name in ["SearchTermsAnalyzer", "SearchTermAnalyzer"]:
            report += f"""
### Key Findings
- Search terms analyzed: {len(results.get("search_terms", []))}
- Negative keyword suggestions: {len(results.get("negative_suggestions", []))}
- Local intent terms: {len(results.get("local_intent", []))}

### Recommendations
1. **Add Negative Keywords**: Implement suggested negative keywords to reduce waste
2. **Local Intent Optimization**: Focus on "near me" and location-based terms
3. **Search Query Expansion**: Add high-performing search terms as keywords
"""

        elif analyzer_name == "NegativeConflictAnalyzer":
            conflicts = results.get("conflicts", [])
            report += f"""
### Key Findings
- Negative keyword conflicts found: {len(conflicts)}
- Campaigns affected: {len(set(c.get("campaign_id") for c in conflicts))}

### Recommendations
1. **Resolve Conflicts**: Remove or modify negative keywords blocking positive terms
2. **Review Negative Lists**: Audit shared negative keyword lists
3. **Performance Impact**: Monitor affected campaigns for performance recovery
"""

        else:
            # Generic findings for other analyzers
            if isinstance(results, dict):
                report += f"""
### Key Findings
- Analysis completed successfully
- Data points processed: {analyzer_result["records_processed"]:,}
- Results keys: {list(results.keys()) if results else "No specific results"}

### Recommendations
- Review detailed results in the JSON file
- Implement suggested optimizations based on findings
- Monitor performance changes after implementation
"""

    else:
        report += f"""
### Error Details
**Error Message:** {analyzer_result.get("error", "Unknown error")}

### Next Steps
1. Review error message and resolve underlying issues
2. Verify data format compatibility
3. Re-run analyzer after fixes are implemented
"""

    # Add JSON file reference
    json_filename = f"{analyzer_name.lower().replace(' ', '_')}_{date_str}.json"
    report += f"""

## Data Files

**JSON Results:** `{json_filename}`

---
*Generated by PaidSearchNav Analyzer Suite*
"""

    return report


async def main():
    logger = setup_logging()
    date_str = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Create output directory
    output_dir = Path("customers/topgolf")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load TopGolf data
    logger.info("Loading TopGolf massive dataset...")
    df = load_topgolf_data()
    logger.info(f"Loaded {len(df):,} records")

    # Define all analyzers
    analyzers = [
        (KeywordAnalyzer, "KeywordAnalyzer"),
        (SearchTermsAnalyzer, "SearchTermsAnalyzer"),
        (SearchTermAnalyzer, "SearchTermAnalyzer"),
        (NegativeConflictAnalyzer, "NegativeConflictAnalyzer"),
        (GeoPerformanceAnalyzer, "GeoPerformanceAnalyzer"),
        (PerformanceMaxAnalyzer, "PerformanceMaxAnalyzer"),
        (AdGroupPerformanceAnalyzer, "AdGroupPerformanceAnalyzer"),
        (AdvancedBidAdjustmentAnalyzer, "AdvancedBidAdjustmentAnalyzer"),
        (BulkNegativeManagerAnalyzer, "BulkNegativeManagerAnalyzer"),
        (CampaignOverlapAnalyzer, "CampaignOverlapAnalyzer"),
        (CompetitorInsightsAnalyzer, "CompetitorInsightsAnalyzer"),
        (DaypartingAnalyzer, "DaypartingAnalyzer"),
        (DemographicsAnalyzer, "DemographicsAnalyzer"),
        (KeywordMatchAnalyzer, "KeywordMatchAnalyzer"),
        (LandingPageAnalyzer, "LandingPageAnalyzer"),
        (LocalReachStoreAnalyzer, "LocalReachStoreAnalyzer"),
        (PlacementAuditAnalyzer, "PlacementAuditAnalyzer"),
        (SharedNegativeValidatorAnalyzer, "SharedNegativeValidatorAnalyzer"),
        (VideoCreativeAnalyzer, "VideoCreativeAnalyzer"),
    ]

    logger.info(f"Running {len(analyzers)} analyzers...")

    # Run each analyzer and generate reports
    for analyzer_class, analyzer_name in analyzers:
        logger.info(f"\n{'=' * 50}")
        logger.info(f"Processing {analyzer_name}")
        logger.info(f"{'=' * 50}")

        # Run analyzer
        result = run_analyzer(analyzer_class, analyzer_name, df, logger)

        # Generate filenames
        base_name = analyzer_name.lower().replace(" ", "_")
        json_filename = f"{base_name}_{date_str}.json"
        md_filename = f"{base_name}_{date_str}.md"

        # Save JSON results
        json_path = output_dir / json_filename
        with open(json_path, "w") as f:
            json.dump(result, f, indent=2, default=str)

        # Generate and save report
        report_content = generate_report(result, date_str)
        md_path = output_dir / md_filename
        with open(md_path, "w") as f:
            f.write(report_content)

        status = "✅" if result["success"] else "❌"
        logger.info(f"{status} {analyzer_name}: {md_filename}")

    logger.info("\n🎉 All analyzer reports generated in customers/topgolf/")
    logger.info(f"📊 {len(analyzers)} analyzers processed")
    logger.info(f"📁 Files saved with timestamp: {date_str}")


if __name__ == "__main__":
    asyncio.run(main())
