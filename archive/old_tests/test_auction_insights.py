#!/usr/bin/env python3
"""Test auction_insights CSV parsing and analysis."""

import asyncio
import os
import sys

# Add the project root to the path
sys.path.insert(0, "/Users/robertwelborn/PycharmProjects/PaidSearchNav")


async def test_auction_insights_s3():
    """Test auction_insights with S3 files."""
    print("🎯 Testing S3-based auction insights analysis...")

    # Actual Fitness Connection auction insights report file
    auction_insights_files = {
        "auction_insights": "s3://paidsearchnav-customer-data-dev/ret/fitness-connection_2879C12F-C38/inputs/Auction insights report (1).csv"
    }

    try:
        from paidsearchnav.api.v1.s3_analysis import process_multiple_s3_files

        print("📥 Attempting to download and process auction insights file...")

        # Set AWS credentials
        os.environ.setdefault("AWS_PROFILE", os.getenv("AWS_PROFILE", "default"))
        os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")

        processed_data, temp_files = await process_multiple_s3_files(
            auction_insights_files
        )

        if "auction_insights" in processed_data:
            records = processed_data["auction_insights"]
            print(
                f"✅ Successfully processed {len(records)} auction insights records from S3"
            )

            if records:
                print("\n🎯 Competitor analysis:")
                competitors = {}
                total_impression_share = 0

                for record in records:
                    # Handle both dict and Pydantic model objects
                    if hasattr(record, "competitor_domain"):
                        competitor = getattr(record, "competitor_domain", "Unknown")
                        impression_share = getattr(record, "impression_share", 0)
                        overlap_rate = getattr(record, "overlap_rate", 0)
                        top_of_page_rate = getattr(record, "top_of_page_rate", 0)
                    else:
                        competitor = record.get(
                            "competitor_domain",
                            record.get("display_url_domain", "Unknown"),
                        )
                        impression_share = record.get(
                            "impression_share", record.get("impr_share", 0)
                        )
                        overlap_rate = record.get("overlap_rate", 0)
                        top_of_page_rate = record.get("top_of_page_rate", 0)

                    if competitor not in competitors:
                        competitors[competitor] = {
                            "impression_share": 0,
                            "overlap_rate": 0,
                            "top_of_page_rate": 0,
                            "records": 0,
                        }

                    # Handle percentage strings like "25.5%"
                    try:
                        impr_share_val = (
                            float(
                                str(impression_share).replace("%", "").replace(",", "")
                            )
                            if impression_share
                            else 0
                        )
                        overlap_val = (
                            float(str(overlap_rate).replace("%", "").replace(",", ""))
                            if overlap_rate
                            else 0
                        )
                        top_page_val = (
                            float(
                                str(top_of_page_rate).replace("%", "").replace(",", "")
                            )
                            if top_of_page_rate
                            else 0
                        )

                        competitors[competitor]["impression_share"] += impr_share_val
                        competitors[competitor]["overlap_rate"] += overlap_val
                        competitors[competitor]["top_of_page_rate"] += top_page_val
                        competitors[competitor]["records"] += 1

                    except (ValueError, TypeError):
                        competitors[competitor]["records"] += 1

                # Sort by impression share and show top competitors
                sorted_competitors = sorted(
                    competitors.items(),
                    key=lambda x: x[1]["impression_share"],
                    reverse=True,
                )

                print("\n🏆 Top Competitors by Impression Share:")
                for i, (competitor, stats) in enumerate(sorted_competitors[:10]):
                    avg_impression_share = (
                        stats["impression_share"] / stats["records"]
                        if stats["records"] > 0
                        else 0
                    )
                    avg_overlap = (
                        stats["overlap_rate"] / stats["records"]
                        if stats["records"] > 0
                        else 0
                    )
                    avg_top_page = (
                        stats["top_of_page_rate"] / stats["records"]
                        if stats["records"] > 0
                        else 0
                    )

                    print(f"  {i + 1:2d}. {competitor}")
                    print(f"      Impression Share: {avg_impression_share:.1f}%")
                    print(f"      Overlap Rate: {avg_overlap:.1f}%")
                    print(f"      Top of Page: {avg_top_page:.1f}%")
                    print()

                # Summary stats
                total_competitors = len(competitors)
                high_overlap_competitors = len(
                    [
                        c
                        for c in competitors.values()
                        if (c["overlap_rate"] / c["records"] if c["records"] > 0 else 0)
                        > 50
                    ]
                )

                print("📈 Auction Insights Summary:")
                print(f"  • Total Competitors: {total_competitors}")
                print(
                    f"  • High Overlap Competitors (>50%): {high_overlap_competitors}"
                )
                print(f"  • Total Records Analyzed: {len(records)}")

        # Cleanup
        for temp_file in temp_files:
            if temp_file and temp_file.exists():
                temp_file.unlink()

        return True

    except Exception as e:
        print(f"❌ S3 auction insights test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("🚀 Starting Auction Insights Testing...")

    # Test S3 processing
    success = asyncio.run(test_auction_insights_s3())

    if success:
        print("\n✨ SUCCESS: Auction insights testing completed!")
        print("   Ready to test next CSV parser type.")
    else:
        print("\n💥 FAILED: Auction insights testing had issues.")
        print("   Please check the auction insights report format.")

    sys.exit(0 if success else 1)
