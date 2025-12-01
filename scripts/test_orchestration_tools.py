#!/usr/bin/env python3
"""
Test orchestration tools with Topgolf account data.

This script tests all 5 orchestration tools with production data to verify:
1. Execution completes in <30 seconds
2. Response is <100 lines (compact summary)
3. Results are actionable and accurate
"""

import asyncio
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from paidsearchnav_mcp.analyzers.keyword_match import KeywordMatchAnalyzer
from paidsearchnav_mcp.analyzers.search_term_waste import SearchTermWasteAnalyzer
from paidsearchnav_mcp.analyzers.negative_conflicts import NegativeConflictAnalyzer
from paidsearchnav_mcp.analyzers.geo_performance import GeoPerformanceAnalyzer
from paidsearchnav_mcp.analyzers.pmax_cannibalization import PMaxCannibalizationAnalyzer


def count_output_lines(summary_dict: dict) -> int:
    """Count approximate lines in formatted output."""
    lines = 0
    lines += 5  # Header info
    lines += len(summary_dict.get("top_recommendations", []))
    lines += len(summary_dict.get("implementation_steps", []))
    lines += 5  # Footer/notes
    return lines


async def test_analyzer(name: str, analyzer, customer_id: str, start_date: str, end_date: str, **kwargs):
    """Test a single analyzer and report results."""
    print(f"\n{'='*80}")
    print(f"Testing: {name}")
    print(f"{'='*80}")

    try:
        start_time = time.time()
        summary = await analyzer.analyze(customer_id, start_date, end_date, **kwargs)
        duration = time.time() - start_time

        # Convert to dict for analysis
        summary_dict = summary.model_dump()

        # Calculate metrics
        line_count = count_output_lines(summary_dict)

        # Print results
        print(f"✅ SUCCESS")
        print(f"   Duration: {duration:.2f} seconds")
        print(f"   Estimated output lines: {line_count}")
        print(f"   Records analyzed: {summary_dict['total_records_analyzed']}")
        print(f"   Estimated savings: ${summary_dict['estimated_monthly_savings']:,.2f}")
        print(f"   Primary issue: {summary_dict['primary_issue']}")
        print(f"   Top recommendations: {len(summary_dict['top_recommendations'])}")

        # Validation checks
        checks = []
        checks.append(("Duration < 30s", duration < 30.0, f"{duration:.2f}s"))
        checks.append(("Output < 100 lines", line_count < 100, f"{line_count} lines"))
        checks.append(("Has recommendations", len(summary_dict['top_recommendations']) > 0,
                      f"{len(summary_dict['top_recommendations'])} recommendations"))
        checks.append(("Has implementation steps", len(summary_dict['implementation_steps']) > 0,
                      f"{len(summary_dict['implementation_steps'])} steps"))

        print(f"\n   Validation Checks:")
        all_passed = True
        for check_name, passed, detail in checks:
            status = "✅" if passed else "❌"
            print(f"   {status} {check_name}: {detail}")
            if not passed:
                all_passed = False

        # Show sample recommendations
        if summary_dict['top_recommendations']:
            print(f"\n   Sample Recommendations (top 3):")
            for i, rec in enumerate(summary_dict['top_recommendations'][:3], 1):
                print(f"   {i}. {rec}")

        return all_passed

    except Exception as e:
        print(f"❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all orchestration tool tests."""
    # Topgolf account details
    customer_id = "5777461198"

    # Last 90 days (Google Ads API limit)
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")

    print(f"Testing Orchestration Tools")
    print(f"Customer ID: {customer_id}")
    print(f"Date Range: {start_date} to {end_date}")
    print(f"{'='*80}")

    results = {}

    # Test 1: KeywordMatchAnalyzer (most critical)
    results["KeywordMatchAnalyzer"] = await test_analyzer(
        "KeywordMatchAnalyzer",
        KeywordMatchAnalyzer(),
        customer_id,
        start_date,
        end_date
    )

    # Test 2: SearchTermWasteAnalyzer
    results["SearchTermWasteAnalyzer"] = await test_analyzer(
        "SearchTermWasteAnalyzer",
        SearchTermWasteAnalyzer(),
        customer_id,
        start_date,
        end_date
    )

    # Test 3: NegativeConflictAnalyzer (no date range needed)
    print(f"\n{'='*80}")
    print(f"Testing: NegativeConflictAnalyzer")
    print(f"{'='*80}")
    try:
        start_time = time.time()
        analyzer = NegativeConflictAnalyzer()
        summary = await analyzer.analyze(customer_id)
        duration = time.time() - start_time

        summary_dict = summary.model_dump()
        line_count = count_output_lines(summary_dict)

        print(f"✅ SUCCESS")
        print(f"   Duration: {duration:.2f} seconds")
        print(f"   Estimated output lines: {line_count}")
        print(f"   Records analyzed: {summary_dict['total_records_analyzed']}")
        print(f"   Primary issue: {summary_dict['primary_issue']}")

        results["NegativeConflictAnalyzer"] = True
    except Exception as e:
        print(f"❌ FAILED: {e}")
        results["NegativeConflictAnalyzer"] = False

    # Test 4: GeoPerformanceAnalyzer
    results["GeoPerformanceAnalyzer"] = await test_analyzer(
        "GeoPerformanceAnalyzer",
        GeoPerformanceAnalyzer(),
        customer_id,
        start_date,
        end_date
    )

    # Test 5: PMaxCannibalizationAnalyzer
    results["PMaxCannibalizationAnalyzer"] = await test_analyzer(
        "PMaxCannibalizationAnalyzer",
        PMaxCannibalizationAnalyzer(),
        customer_id,
        start_date,
        end_date
    )

    # Summary
    print(f"\n{'='*80}")
    print(f"FINAL RESULTS")
    print(f"{'='*80}")

    for analyzer_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {analyzer_name}")

    all_passed = all(results.values())

    if all_passed:
        print(f"\n🎉 All orchestration tools passed validation!")
        return 0
    else:
        print(f"\n⚠️  Some orchestration tools failed validation")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
