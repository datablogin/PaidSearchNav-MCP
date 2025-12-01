#!/usr/bin/env python3
"""
Direct test of analyzers with Topgolf account data.

This test directly instantiates and calls analyzers, using the server's
get_keywords and get_search_terms functions as data providers.
"""

import asyncio
import json
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def count_output_lines(summary_dict: dict) -> int:
    """Count approximate lines in formatted output."""
    lines = 0
    lines += 5  # Header info (period, customer, summary stats)
    lines += 2 * len(summary_dict.get("top_recommendations", []))  # Each rec ~2 lines
    lines += len(summary_dict.get("implementation_steps", []))
    lines += 5  # Footer/notes
    return lines


async def test_analyzer(name: str, analyzer_class, **kwargs):
    """Test a single analyzer directly."""
    print(f"\n{'='*80}")
    print(f"Testing: {name}")
    print(f"{'='*80}")
    print(f"Parameters: {json.dumps({k: v for k, v in kwargs.items() if k != 'analyzer_kwargs'}, indent=2)}")

    try:
        # Extract analyzer-specific kwargs
        analyzer_kwargs = kwargs.pop('analyzer_kwargs', {})

        # Instantiate analyzer
        analyzer = analyzer_class(**analyzer_kwargs)

        # Run analysis
        start_time = time.time()
        summary = await analyzer.analyze(**kwargs)
        duration = time.time() - start_time

        # Convert to dict
        summary_dict = summary.model_dump()

        # Calculate metrics
        line_count = count_output_lines(summary_dict)
        json_lines = len(json.dumps(summary_dict, indent=2).split('\n'))

        # Print results
        print(f"\n✅ SUCCESS")
        print(f"   Duration: {duration:.2f} seconds")
        print(f"   Estimated formatted output: {line_count} lines")
        print(f"   JSON response size: {json_lines} lines")
        print(f"   Records analyzed: {summary_dict['total_records_analyzed']}")
        print(f"   Estimated savings: ${summary_dict['estimated_monthly_savings']:,.2f}")
        print(f"   Primary issue: {summary_dict['primary_issue']}")
        print(f"   Top recommendations: {len(summary_dict['top_recommendations'])}")
        print(f"   Implementation steps: {len(summary_dict['implementation_steps'])}")

        # Validation checks
        checks = []
        checks.append(("Duration < 30s", duration < 30.0, f"{duration:.2f}s"))
        checks.append(("Formatted output < 100 lines", line_count < 100, f"{line_count} lines"))
        checks.append(("Has recommendations", len(summary_dict['top_recommendations']) > 0,
                      f"{len(summary_dict['top_recommendations'])} recommendations"))
        checks.append(("≤10 recommendations", len(summary_dict['top_recommendations']) <= 10,
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
            print(f"\n   Top 3 Recommendations:")
            for i, rec in enumerate(summary_dict['top_recommendations'][:3], 1):
                if isinstance(rec, dict):
                    # Try different key names depending on analyzer
                    item = rec.get('keyword') or rec.get('search_term') or rec.get('location') or rec.get('conflict') or 'N/A'
                    savings = rec.get('estimated_savings', 0)
                    action = rec.get('recommended_match_type') or rec.get('action') or rec.get('recommendation', '')
                    print(f"   {i}. {item}")
                    if action:
                        print(f"      Action: {action}")
                    print(f"      Savings: ${savings:,.2f}/month")
                else:
                    print(f"   {i}. {rec}")

        # Show implementation steps
        if summary_dict['implementation_steps']:
            print(f"\n   Implementation Steps:")
            for i, step in enumerate(summary_dict['implementation_steps'], 1):
                print(f"   {i}. {step}")

        return all_passed, summary_dict

    except Exception as e:
        print(f"❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False, None


async def main():
    """Run all analyzer tests."""
    print("="*80)
    print("ORCHESTRATION LAYER - DIRECT ANALYZER TEST")
    print("Testing with Topgolf Production Data")
    print("="*80)

    # Import analyzers
    try:
        from paidsearchnav_mcp.analyzers import (
            KeywordMatchAnalyzer,
            SearchTermWasteAnalyzer,
            NegativeConflictAnalyzer,
            GeoPerformanceAnalyzer,
            PMaxCannibalizationAnalyzer,
        )
    except ImportError as e:
        print(f"❌ Failed to import analyzers: {e}")
        return 1

    # Topgolf account details
    customer_id = "5777461198"

    # Last 90 days (Google Ads API limit)
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")

    print(f"\nTest Configuration:")
    print(f"  Customer ID: {customer_id}")
    print(f"  Date Range: {start_date} to {end_date}")

    results = {}
    summaries = {}

    # Test 1: KeywordMatchAnalyzer (most critical)
    passed, summary = await test_analyzer(
        "KeywordMatchAnalyzer",
        KeywordMatchAnalyzer,
        customer_id=customer_id,
        start_date=start_date,
        end_date=end_date,
    )
    results["KeywordMatchAnalyzer"] = passed
    summaries["KeywordMatchAnalyzer"] = summary

    # Test 2: SearchTermWasteAnalyzer
    passed, summary = await test_analyzer(
        "SearchTermWasteAnalyzer",
        SearchTermWasteAnalyzer,
        customer_id=customer_id,
        start_date=start_date,
        end_date=end_date,
    )
    results["SearchTermWasteAnalyzer"] = passed
    summaries["SearchTermWasteAnalyzer"] = summary

    # Test 3: NegativeConflictAnalyzer (no date range)
    passed, summary = await test_analyzer(
        "NegativeConflictAnalyzer",
        NegativeConflictAnalyzer,
        customer_id=customer_id,
    )
    results["NegativeConflictAnalyzer"] = passed
    summaries["NegativeConflictAnalyzer"] = summary

    # Test 4: GeoPerformanceAnalyzer
    passed, summary = await test_analyzer(
        "GeoPerformanceAnalyzer",
        GeoPerformanceAnalyzer,
        customer_id=customer_id,
        start_date=start_date,
        end_date=end_date,
    )
    results["GeoPerformanceAnalyzer"] = passed
    summaries["GeoPerformanceAnalyzer"] = summary

    # Test 5: PMaxCannibalizationAnalyzer
    passed, summary = await test_analyzer(
        "PMaxCannibalizationAnalyzer",
        PMaxCannibalizationAnalyzer,
        customer_id=customer_id,
        start_date=start_date,
        end_date=end_date,
    )
    results["PMaxCannibalizationAnalyzer"] = passed
    summaries["PMaxCannibalizationAnalyzer"] = summary

    # Summary
    print(f"\n{'='*80}")
    print(f"FINAL RESULTS")
    print(f"{'='*80}")

    for analyzer_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        summary = summaries.get(analyzer_name)
        if summary:
            savings = summary.get('estimated_monthly_savings', 0)
            recs = len(summary.get('top_recommendations', []))
            print(f"{status} - {analyzer_name}: ${savings:,.2f} savings, {recs} recommendations")
        else:
            print(f"{status} - {analyzer_name}")

    passed_count = sum(1 for p in results.values() if p)
    total_count = len(results)

    print(f"\nPassed: {passed_count}/{total_count}")

    # Calculate total potential savings
    total_savings = sum(
        s.get('estimated_monthly_savings', 0)
        for s in summaries.values()
        if s
    )
    print(f"Total Potential Monthly Savings: ${total_savings:,.2f}")

    if passed_count == total_count:
        print(f"\n🎉 All analyzers passed validation!")
        print(f"\n✅ Phase 2.5 Manual Verification: COMPLETE")
        print(f"   - All analyzers execute successfully")
        print(f"   - All responses are compact (<100 lines formatted)")
        print(f"   - All provide actionable recommendations")
        return 0
    else:
        print(f"\n⚠️  {total_count - passed_count} analyzer(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
