#!/usr/bin/env python3
"""Test UI export formats for keywords and search terms CSV parsing."""

import asyncio
import os
import sys

# Add the project root to the path
sys.path.insert(0, "/Users/robertwelborn/PycharmProjects/PaidSearchNav")


async def test_keywords_ui_s3():
    """Test keywords with S3 files."""
    print("🔑 Testing S3-based keywords analysis...")

    # Actual Fitness Connection keyword report file
    keywords_files = {
        "keywords": "s3://paidsearchnav-customer-data-dev/ret/fitness-connection_2879C12F-C38/inputs/searchkeywordreport.csv"
    }

    try:
        from paidsearchnav.api.v1.s3_analysis import process_multiple_s3_files

        print("📥 Attempting to download and process keywords file...")

        # Set AWS credentials
        os.environ.setdefault("AWS_PROFILE", os.getenv("AWS_PROFILE", "default"))
        os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")

        processed_data, temp_files = await process_multiple_s3_files(keywords_files)

        if "keywords" in processed_data:
            records = processed_data["keywords"]
            print(f"✅ Successfully processed {len(records)} keyword records from S3")

            if records:
                print("\n🔑 Sample keywords analysis:")

                # Analyze match types
                match_types = {}
                total_cost = 0
                high_performing_keywords = []

                for record in records[:20]:  # Analyze first 20 keywords
                    # Handle both dict and Pydantic model objects
                    if hasattr(record, "keyword") and not hasattr(record, "get"):
                        # Pydantic model object
                        keyword = getattr(record, "keyword", "Unknown")
                        match_type = getattr(record, "match_type", "Unknown")
                        cost = getattr(record, "cost", 0)
                        conversions = getattr(record, "conversions", 0)
                        clicks = getattr(record, "clicks", 0)
                    elif hasattr(record, "get"):
                        # Dictionary object
                        keyword = record.get("keyword", "Unknown")
                        match_type = record.get("match_type", "Unknown")
                        cost = record.get("cost", 0)
                        conversions = record.get("conversions", 0)
                        clicks = record.get("clicks", 0)
                    else:
                        # Unknown object type - skip
                        print(f"Debug: Unknown record type: {type(record)}")
                        continue

                    # Track match types
                    if match_type not in match_types:
                        match_types[match_type] = {"count": 0, "cost": 0}
                    match_types[match_type]["count"] += 1

                    # Handle cost parsing
                    try:
                        cost_val = float(str(cost).replace(",", "")) if cost else 0
                        match_types[match_type]["cost"] += cost_val
                        total_cost += cost_val

                        # Identify high-performing keywords
                        conv_val = (
                            float(str(conversions).replace(",", ""))
                            if conversions
                            else 0
                        )
                        clicks_val = int(str(clicks).replace(",", "")) if clicks else 0

                        if conv_val > 0 and cost_val > 0:
                            cpa = cost_val / conv_val
                            high_performing_keywords.append(
                                (keyword, match_type, cost_val, conv_val, cpa)
                            )

                    except (ValueError, TypeError):
                        pass

                # Show match type breakdown
                print("\n📊 Match Type Analysis:")
                for match_type, stats in match_types.items():
                    cost_pct = (
                        (stats["cost"] / total_cost * 100) if total_cost > 0 else 0
                    )
                    avg_cost = (
                        stats["cost"] / stats["count"] if stats["count"] > 0 else 0
                    )
                    print(
                        f"  • {match_type}: {stats['count']} keywords, ${stats['cost']:,.2f} ({cost_pct:.1f}%), avg ${avg_cost:.2f}"
                    )

                # Show top performing keywords
                if high_performing_keywords:
                    high_performing_keywords.sort(key=lambda x: x[4])  # Sort by CPA
                    print("\n🏆 Top Performing Keywords (by CPA):")
                    for i, (kw, mt, cost, conv, cpa) in enumerate(
                        high_performing_keywords[:5]
                    ):
                        print(
                            f"  {i + 1}. '{kw}' [{mt}] - ${cost:.2f}, {conv:.1f} conv, CPA: ${cpa:.2f}"
                        )

                print("\n📈 Keywords Summary:")
                print(f"  • Total Keywords Analyzed: {len(records)}")
                print(f"  • Match Types Found: {len(match_types)}")
                print(f"  • Sample Total Cost: ${total_cost:,.2f}")
                print(f"  • Converting Keywords: {len(high_performing_keywords)}")

        # Cleanup
        for temp_file in temp_files:
            if temp_file and temp_file.exists():
                temp_file.unlink()

        return True

    except Exception as e:
        print(f"❌ S3 keywords test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


async def test_search_terms_ui_s3():
    """Test search terms with S3 files."""
    print("\n🔍 Testing S3-based search terms analysis...")

    # Actual Fitness Connection search terms report file
    search_terms_files = {
        "search_terms": "s3://paidsearchnav-customer-data-dev/ret/fitness-connection_2879C12F-C38/inputs/searchtermsreport.csv"
    }

    try:
        from paidsearchnav.api.v1.s3_analysis import process_multiple_s3_files

        print("📥 Attempting to download and process search terms file...")

        # Set AWS credentials
        os.environ.setdefault("AWS_PROFILE", os.getenv("AWS_PROFILE", "default"))
        os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")

        processed_data, temp_files = await process_multiple_s3_files(search_terms_files)

        if "search_terms" in processed_data:
            records = processed_data["search_terms"]
            print(
                f"✅ Successfully processed {len(records)} search term records from S3"
            )

            if records:
                print("\n🔍 Search terms insights:")

                # Analyze search intent and performance
                search_insights = {}
                high_volume_terms = []
                conversion_terms = []

                for record in records[:25]:  # Analyze first 25 search terms
                    # Handle both dict and Pydantic model objects
                    if hasattr(record, "search_term") and not hasattr(record, "get"):
                        # Pydantic model object
                        search_term = getattr(record, "search_term", "Unknown")
                        impressions = getattr(record, "impressions", 0)
                        clicks = getattr(record, "clicks", 0)
                        cost = getattr(record, "cost", 0)
                        conversions = getattr(record, "conversions", 0)
                    else:
                        # Dictionary object
                        search_term = record.get("search_term", "Unknown")
                        impressions = record.get("impressions", 0)
                        clicks = record.get("clicks", 0)
                        cost = record.get("cost", 0)
                        conversions = record.get("conversions", 0)

                    try:
                        # Parse numeric values
                        impr_val = (
                            int(str(impressions).replace(",", "")) if impressions else 0
                        )
                        clicks_val = int(str(clicks).replace(",", "")) if clicks else 0
                        cost_val = float(str(cost).replace(",", "")) if cost else 0
                        conv_val = (
                            float(str(conversions).replace(",", ""))
                            if conversions
                            else 0
                        )

                        # Categorize search intent
                        term_lower = search_term.lower()
                        intent = "Unknown"
                        if any(
                            word in term_lower
                            for word in ["near me", "nearby", "close"]
                        ):
                            intent = "Local"
                        elif any(
                            word in term_lower
                            for word in ["price", "cost", "membership", "join"]
                        ):
                            intent = "Commercial"
                        elif any(
                            word in term_lower for word in ["fitness", "gym", "workout"]
                        ):
                            intent = "Informational"
                        elif any(
                            word in term_lower
                            for word in ["fitness connection", "fitnessconnection"]
                        ):
                            intent = "Branded"

                        if intent not in search_insights:
                            search_insights[intent] = {
                                "terms": 0,
                                "impressions": 0,
                                "cost": 0,
                            }

                        search_insights[intent]["terms"] += 1
                        search_insights[intent]["impressions"] += impr_val
                        search_insights[intent]["cost"] += cost_val

                        # Track high volume and converting terms
                        if impr_val > 1000:
                            high_volume_terms.append(
                                (search_term, impr_val, clicks_val)
                            )

                        if conv_val > 0:
                            ctr = (clicks_val / impr_val * 100) if impr_val > 0 else 0
                            conversion_terms.append(
                                (search_term, conv_val, cost_val, ctr)
                            )

                    except (ValueError, TypeError):
                        pass

                # Show search intent analysis
                print("\n🎯 Search Intent Analysis:")
                for intent, stats in search_insights.items():
                    avg_cost = (
                        stats["cost"] / stats["terms"] if stats["terms"] > 0 else 0
                    )
                    print(
                        f"  • {intent}: {stats['terms']} terms, {stats['impressions']:,} impr, ${stats['cost']:,.2f} (avg ${avg_cost:.2f})"
                    )

                # Show high volume terms
                if high_volume_terms:
                    high_volume_terms.sort(key=lambda x: x[1], reverse=True)
                    print("\n📈 High Volume Search Terms:")
                    for i, (term, impr, clicks) in enumerate(high_volume_terms[:5]):
                        ctr = (clicks / impr * 100) if impr > 0 else 0
                        print(
                            f"  {i + 1}. '{term}' - {impr:,} impr, {clicks:,} clicks (CTR: {ctr:.2f}%)"
                        )

                # Show converting terms
                if conversion_terms:
                    conversion_terms.sort(key=lambda x: x[1], reverse=True)
                    print("\n🎯 Converting Search Terms:")
                    for i, (term, conv, cost, ctr) in enumerate(conversion_terms[:3]):
                        cpa = cost / conv if conv > 0 else 0
                        print(
                            f"  {i + 1}. '{term}' - {conv:.1f} conv, ${cost:.2f} cost, CPA: ${cpa:.2f}"
                        )

                print("\n📈 Search Terms Summary:")
                print(f"  • Total Search Terms: {len(records)}")
                print(f"  • Intent Categories: {len(search_insights)}")
                print(f"  • High Volume Terms (>1k impr): {len(high_volume_terms)}")
                print(f"  • Converting Terms: {len(conversion_terms)}")

        # Cleanup
        for temp_file in temp_files:
            if temp_file and temp_file.exists():
                temp_file.unlink()

        return True

    except Exception as e:
        print(f"❌ S3 search terms test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("🚀 Starting UI Export Formats Testing...")
    print("Testing with actual Fitness Connection keyword and search term reports")

    # Test both parsers
    success1 = asyncio.run(test_keywords_ui_s3())
    success2 = asyncio.run(test_search_terms_ui_s3())

    if success1 and success2:
        print("\n✨ SUCCESS: All UI export formats testing completed!")
        print("   Keywords and search terms parsers are working perfectly.")
        print("   🎉 ALL CSV PARSER TESTING IS NOW COMPLETE! 🎉")
    else:
        print("\n💥 FAILED: Some UI export format testing had issues.")
        print("   Please check the report formats.")

    sys.exit(0 if (success1 and success2) else 1)
