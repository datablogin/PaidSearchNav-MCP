#!/usr/bin/env python3
"""
Integration test for orchestration tools using actual MCP server.

This test directly calls the orchestration tool functions from server.py
to verify they work with production Topgolf account data.
"""

import asyncio
import json
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


async def test_orchestration_tool(tool_name: str, tool_func, **kwargs):
    """Test a single orchestration tool."""
    print(f"\n{'='*80}")
    print(f"Testing: {tool_name}")
    print(f"{'='*80}")
    print(f"Parameters: {json.dumps(kwargs, indent=2)}")

    try:
        start_time = time.time()
        result = await tool_func(**kwargs)
        duration = time.time() - start_time

        # Count approximate output lines
        result_str = json.dumps(result, indent=2)
        line_count = len(result_str.split('\n'))

        # Print results
        print(f"\n✅ SUCCESS")
        print(f"   Duration: {duration:.2f} seconds")
        print(f"   Response lines (JSON): {line_count}")

        # Check if it's an error response
        if result.get("status") == "error":
            print(f"   ⚠️  Error response: {result.get('message')}")
            print(f"   Error code: {result.get('error_code')}")
            return False

        # Print summary data
        if "total_records_analyzed" in result:
            print(f"   Records analyzed: {result['total_records_analyzed']}")
        if "estimated_monthly_savings" in result:
            print(f"   Estimated savings: ${result['estimated_monthly_savings']:,.2f}")
        if "primary_issue" in result:
            print(f"   Primary issue: {result['primary_issue']}")
        if "top_recommendations" in result:
            print(f"   Recommendations: {len(result['top_recommendations'])}")

        # Validation checks
        checks = []
        checks.append(("Duration < 30s", duration < 30.0, f"{duration:.2f}s"))
        checks.append(("Has total_records_analyzed", "total_records_analyzed" in result, "✓"))
        checks.append(("Has top_recommendations", "top_recommendations" in result, "✓"))
        checks.append(("Has implementation_steps", "implementation_steps" in result, "✓"))

        print(f"\n   Validation Checks:")
        all_passed = True
        for check_name, passed, detail in checks:
            status = "✅" if passed else "❌"
            print(f"   {status} {check_name}: {detail}")
            if not passed:
                all_passed = False

        # Show sample recommendations
        if result.get("top_recommendations"):
            print(f"\n   Sample Recommendations (top 3):")
            for i, rec in enumerate(result["top_recommendations"][:3], 1):
                # Format recommendation based on structure
                if isinstance(rec, dict):
                    keyword = rec.get('keyword', rec.get('search_term', rec.get('location', 'N/A')))
                    savings = rec.get('estimated_savings', 0)
                    print(f"   {i}. {keyword}: ${savings:,.2f} savings")
                else:
                    print(f"   {i}. {rec}")

        # Show implementation steps
        if result.get("implementation_steps"):
            print(f"\n   Implementation Steps:")
            for i, step in enumerate(result["implementation_steps"][:3], 1):
                print(f"   {i}. {step}")

        return all_passed

    except Exception as e:
        print(f"❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all orchestration tool tests."""
    print("="*80)
    print("ORCHESTRATION TOOLS INTEGRATION TEST")
    print("="*80)

    # Import server functions
    try:
        from paidsearchnav_mcp.server import (
            analyze_keyword_match_types,
            analyze_search_term_waste,
            analyze_negative_conflicts,
            analyze_geo_performance,
            analyze_pmax_cannibalization,
        )
    except ImportError as e:
        print(f"❌ Failed to import server functions: {e}")
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

    # Test 1: KeywordMatchAnalyzer (most critical)
    results["analyze_keyword_match_types"] = await test_orchestration_tool(
        "analyze_keyword_match_types",
        analyze_keyword_match_types,
        customer_id=customer_id,
        start_date=start_date,
        end_date=end_date,
    )

    # Test 2: SearchTermWasteAnalyzer
    results["analyze_search_term_waste"] = await test_orchestration_tool(
        "analyze_search_term_waste",
        analyze_search_term_waste,
        customer_id=customer_id,
        start_date=start_date,
        end_date=end_date,
    )

    # Test 3: NegativeConflictAnalyzer (no date range)
    results["analyze_negative_conflicts"] = await test_orchestration_tool(
        "analyze_negative_conflicts",
        analyze_negative_conflicts,
        customer_id=customer_id,
    )

    # Test 4: GeoPerformanceAnalyzer
    results["analyze_geo_performance"] = await test_orchestration_tool(
        "analyze_geo_performance",
        analyze_geo_performance,
        customer_id=customer_id,
        start_date=start_date,
        end_date=end_date,
    )

    # Test 5: PMaxCannibalizationAnalyzer
    results["analyze_pmax_cannibalization"] = await test_orchestration_tool(
        "analyze_pmax_cannibalization",
        analyze_pmax_cannibalization,
        customer_id=customer_id,
        start_date=start_date,
        end_date=end_date,
    )

    # Summary
    print(f"\n{'='*80}")
    print(f"FINAL RESULTS")
    print(f"{'='*80}")

    for tool_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {tool_name}")

    passed_count = sum(1 for p in results.values() if p)
    total_count = len(results)

    print(f"\nPassed: {passed_count}/{total_count}")

    if passed_count == total_count:
        print(f"\n🎉 All orchestration tools passed validation!")
        return 0
    else:
        print(f"\n⚠️  {total_count - passed_count} orchestration tool(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
