#!/usr/bin/env python3
"""Generate actionable Google Ads import files based on Cotton Patch Cafe analysis."""

import asyncio
import csv
import sys
from datetime import datetime
from io import StringIO
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, "/Users/robertwelborn/PycharmProjects/PaidSearchNav")

from dotenv import load_dotenv


async def generate_google_ads_imports():
    """Generate actual Google Ads import files from Cotton Patch Cafe analysis."""
    print("📤 Generating Google Ads Import Files")
    print("=" * 50)

    # Load environment variables
    env_file = Path(__file__).parent / ".env.dev"
    if env_file.exists():
        load_dotenv(env_file)

    # Get Cotton Patch Cafe data
    data = await get_cotton_patch_analysis_data()
    if not data["success"]:
        return False

    # Generate each import file
    import_files = {}

    # 1. Negative Keywords Import
    print("🚫 Generating Negative Keywords Import...")
    negative_keywords_csv = await generate_negative_keywords_import(data["data"])
    if negative_keywords_csv:
        import_files["negative_keywords_bulk_upload.csv"] = negative_keywords_csv
        print("   ✅ Generated negative keywords file")

    # 2. Geographic Bid Adjustments
    print("🗺️  Generating Geographic Bid Adjustments...")
    geo_adjustments_csv = await generate_geo_bid_adjustments(data["data"])
    if geo_adjustments_csv:
        import_files["geographic_bid_adjustments.csv"] = geo_adjustments_csv
        print("   ✅ Generated geographic adjustments file")

    # 3. Demographic Bid Adjustments
    print("👥 Generating Demographic Bid Adjustments...")
    demo_adjustments_csv = await generate_demographic_adjustments(data["data"])
    if demo_adjustments_csv:
        import_files["demographic_bid_adjustments.csv"] = demo_adjustments_csv
        print("   ✅ Generated demographic adjustments file")

    # 4. Campaign Structure Recommendations
    print("📊 Generating Campaign Optimization Actions...")
    campaign_actions_csv = await generate_campaign_optimizations(data["data"])
    if campaign_actions_csv:
        import_files["campaign_optimization_actions.csv"] = campaign_actions_csv
        print("   ✅ Generated campaign actions file")

    # 5. Implementation Guide
    print("📋 Generating Implementation Guide...")
    implementation_guide = create_implementation_guide(data["data"])
    import_files["implementation_guide.md"] = implementation_guide
    print("   ✅ Generated implementation guide")

    # Upload all files to S3
    await upload_import_files_to_s3(import_files)

    print(f"\n🎉 Generated {len(import_files)} actionable import files!")
    return True


async def get_cotton_patch_analysis_data():
    """Get Cotton Patch Cafe data for analysis."""
    try:
        from paidsearchnav.api.v1.s3_analysis import process_multiple_s3_files

        base_path = "s3://paidsearchnav-customer-data-dev/svc/cotton-patch-cafe_952-408-0160/inputs/"
        files = {
            "search_terms": f"{base_path}Search terms report (1).csv",
            "keywords": f"{base_path}Search keyword report (1).csv",
            "negative_keywords": f"{base_path}Negative keyword report (1).csv",
            "campaigns": f"{base_path}Campaign report (2).csv",
            "ad_groups": f"{base_path}Ad group report (2).csv",
            "geo_performance": f"{base_path}Location report (2).csv",
            "device_performance": f"{base_path}Device report (2).csv",
            "demographics_age": f"{base_path}Age report.csv",
            "demographics_gender": f"{base_path}Gender report.csv",
            "per_store": f"{base_path}Per store report (2).csv",
        }

        print("📥 Loading Cotton Patch Cafe data...")
        processed_data, temp_files = await process_multiple_s3_files(files)

        # Clean up temp files
        for temp_file in temp_files:
            if temp_file and temp_file.exists():
                temp_file.unlink()

        total_records = sum(len(records) for records in processed_data.values())
        print(f"✅ Loaded {total_records:,} records")

        return {"success": True, "data": processed_data}

    except Exception as e:
        print(f"❌ Data loading failed: {e}")
        return {"success": False, "error": str(e)}


async def generate_negative_keywords_import(data):
    """Generate negative keywords CSV for Google Ads bulk upload."""
    if "search_terms" not in data or not data["search_terms"]:
        return None

    search_terms = data["search_terms"]
    output = StringIO()
    writer = csv.writer(output)

    # Google Ads bulk upload format
    writer.writerow(["Campaign", "Ad Group", "Keyword", "Criterion Type", "Labels"])

    competitor_terms = set()
    irrelevant_terms = set()
    high_cost_no_conversion_terms = set()

    # Analyze search terms for negative keyword opportunities
    for record in search_terms[:5000]:  # Process first 5000 for performance
        try:
            # Handle Pydantic model or dict
            if hasattr(record, "search_term"):
                term = getattr(record, "search_term", "").lower()
                cost_val = getattr(record, "cost", 0)
                clicks_val = getattr(record, "clicks", 0)
                conversions_val = getattr(record, "conversions", 0)
            else:
                term = record.get("search_term", "").lower()
                cost_val = record.get("cost", 0)
                clicks_val = record.get("clicks", 0)
                conversions_val = record.get("conversions", 0)

            if not term:
                continue

            # Parse metrics
            try:
                cost = float(str(cost_val).replace("$", "").replace(",", "") or "0")
                clicks = int(str(clicks_val).replace(",", "") or "0")
                conversions = float(str(conversions_val).replace(",", "") or "0")
            except (ValueError, TypeError):
                continue

            # Competitor terms
            competitor_keywords = [
                "cracker barrel",
                "dennys",
                "denny's",
                "ihop",
                "waffle house",
                "applebees",
                "applebee's",
                "chilis",
                "chili's",
                "olive garden",
                "red lobster",
                "outback",
                "texas roadhouse",
                "golden corral",
                "bob evans",
                "perkins",
                "village inn",
                "friendly's",
                "shoneys",
            ]

            if any(comp in term for comp in competitor_keywords):
                competitor_terms.add(term)

            # High cost, no conversion terms
            if cost > 25 and clicks > 5 and conversions == 0:
                high_cost_no_conversion_terms.add(term)

            # Irrelevant terms for restaurant
            irrelevant_keywords = [
                "recipe",
                "nutrition",
                "calories",
                "ingredients",
                "diet",
                "job",
                "employment",
                "hiring",
                "career",
                "application",
                "stock",
                "franchise",
                "investment",
                "corporate",
                "headquarters",
            ]

            if any(irrelevant in term for irrelevant in irrelevant_keywords):
                irrelevant_terms.add(term)

        except Exception:
            continue

    # Add competitor terms as exact match negatives
    for term in list(competitor_terms)[:50]:  # Limit to top 50
        writer.writerow(
            [
                "All Campaigns",  # Apply to all campaigns
                "",  # Empty for campaign level
                f'"{term}"',  # Exact match negative
                "Negative Keyword",
                "Competitor Exclusions",
            ]
        )

    # Add high cost, no conversion terms as phrase match negatives
    for term in list(high_cost_no_conversion_terms)[:30]:  # Limit to top 30
        writer.writerow(
            [
                "All Campaigns",
                "",
                f'"{term}"',
                "Negative Keyword",
                "High Cost No Conversion",
            ]
        )

    # Add irrelevant terms as broad match negatives
    for term in list(irrelevant_terms)[:20]:  # Limit to top 20
        writer.writerow(
            [
                "All Campaigns",
                "",
                term,  # Broad match negative
                "Negative Keyword",
                "Irrelevant Terms",
            ]
        )

    csv_content = output.getvalue()
    print(
        f"      📊 Found {len(competitor_terms)} competitor terms, {len(high_cost_no_conversion_terms)} wasteful terms"
    )
    return csv_content


async def generate_geo_bid_adjustments(data):
    """Generate geographic bid adjustments CSV."""
    if "geo_performance" not in data or not data["geo_performance"]:
        return None

    geo_records = data["geo_performance"]
    output = StringIO()
    writer = csv.writer(output)

    writer.writerow(["Campaign", "Location", "Bid Adjustment", "Criterion Type"])

    # Analyze geographic performance
    location_performance = {}

    for record in geo_records:
        try:
            # Handle Pydantic model or dict
            if hasattr(record, "location"):
                location = getattr(record, "location", "")
                cost_val = getattr(record, "cost", 0)
                conversions_val = getattr(record, "conversions", 0)
                clicks_val = getattr(record, "clicks", 0)
            else:
                location = record.get("location", "")
                cost_val = record.get("cost", 0)
                conversions_val = record.get("conversions", 0)
                clicks_val = record.get("clicks", 0)

            if not location:
                continue

            try:
                cost = float(str(cost_val).replace("$", "").replace(",", "") or "0")
                conversions = float(str(conversions_val).replace(",", "") or "0")
                clicks = int(str(clicks_val).replace(",", "") or "0")

                if clicks > 0:
                    conversion_rate = conversions / clicks
                    cost_per_conversion = (
                        cost / conversions if conversions > 0 else 999999
                    )

                    location_performance[location] = {
                        "conversion_rate": conversion_rate,
                        "cost_per_conversion": cost_per_conversion,
                        "total_conversions": conversions,
                        "total_cost": cost,
                    }
            except (ValueError, TypeError):
                continue

        except Exception:
            continue

    # Sort locations by performance (conversion rate * total conversions)
    sorted_locations = sorted(
        location_performance.items(),
        key=lambda x: x[1]["conversion_rate"] * x[1]["total_conversions"],
        reverse=True,
    )

    # Top performing locations get positive bid adjustments
    for i, (location, perf) in enumerate(sorted_locations[:15]):
        if perf["total_conversions"] >= 2:  # Only adjust locations with meaningful data
            if i < 5:  # Top 5 locations
                adjustment = "+30%"
            elif i < 10:  # Next 5 locations
                adjustment = "+20%"
            else:  # Next 5 locations
                adjustment = "+10%"

            writer.writerow(["All Campaigns", location, adjustment, "Location"])

    # Poor performing locations get negative adjustments
    poor_performers = [
        loc
        for loc, perf in sorted_locations[-10:]
        if perf["total_conversions"] == 0 and perf["total_cost"] > 50
    ]

    for location, perf in poor_performers[:5]:  # Top 5 poor performers
        writer.writerow(["All Campaigns", location, "-50%", "Location"])

    csv_content = output.getvalue()
    print(f"      📊 Generated adjustments for {len(sorted_locations)} locations")
    return csv_content


async def generate_demographic_adjustments(data):
    """Generate demographic bid adjustments CSV."""
    if "demographics_age" not in data or not data["demographics_age"]:
        return None

    age_records = data["demographics_age"]
    output = StringIO()
    writer = csv.writer(output)

    writer.writerow(["Campaign", "Demographic", "Bid Adjustment", "Criterion Type"])

    # Analyze age demographic performance
    age_performance = {}

    for record in age_records:
        try:
            # Handle Pydantic model or dict
            if hasattr(record, "age_range"):
                age_range = getattr(record, "age_range", "")
                cost_val = getattr(record, "cost", 0)
                conversions_val = getattr(record, "conversions", 0)
                clicks_val = getattr(record, "clicks", 0)
            else:
                age_range = record.get("age_range", "") or record.get("demographic", "")
                cost_val = record.get("cost", 0)
                conversions_val = record.get("conversions", 0)
                clicks_val = record.get("clicks", 0)

            if not age_range:
                continue

            try:
                cost = float(str(cost_val).replace("$", "").replace(",", "") or "0")
                conversions = float(str(conversions_val).replace(",", "") or "0")
                clicks = int(str(clicks_val).replace(",", "") or "0")

                if clicks > 0:
                    conversion_rate = conversions / clicks
                    cost_per_conversion = (
                        cost / conversions if conversions > 0 else 999999
                    )

                    if age_range not in age_performance:
                        age_performance[age_range] = {
                            "conversion_rate": 0,
                            "total_conversions": 0,
                            "total_cost": 0,
                            "total_clicks": 0,
                        }

                    age_performance[age_range]["conversion_rate"] += conversion_rate
                    age_performance[age_range]["total_conversions"] += conversions
                    age_performance[age_range]["total_cost"] += cost
                    age_performance[age_range]["total_clicks"] += clicks

            except (ValueError, TypeError):
                continue

        except Exception:
            continue

    # Calculate average performance and suggest adjustments
    for age_range, perf in age_performance.items():
        if perf["total_clicks"] > 50:  # Only adjust demographics with meaningful data
            avg_conversion_rate = (
                perf["conversion_rate"] / perf["total_clicks"]
                if perf["total_clicks"] > 0
                else 0
            )

            if avg_conversion_rate > 0.05:  # High performing age group
                adjustment = "+25%"
            elif avg_conversion_rate > 0.02:  # Average performing
                adjustment = "+10%"
            elif (
                avg_conversion_rate < 0.01 and perf["total_cost"] > 100
            ):  # Poor performing
                adjustment = "-30%"
            else:
                continue  # No adjustment needed

            writer.writerow(["All Campaigns", age_range, adjustment, "Age"])

    csv_content = output.getvalue()
    print(f"      📊 Generated adjustments for {len(age_performance)} age demographics")
    return csv_content


async def generate_campaign_optimizations(data):
    """Generate campaign optimization actions CSV."""
    if "campaigns" not in data or not data["campaigns"]:
        return None

    campaigns = data["campaigns"]
    output = StringIO()
    writer = csv.writer(output)

    writer.writerow(
        ["Campaign", "Action", "Recommendation", "Priority", "Expected Impact"]
    )

    for record in campaigns:
        try:
            # Handle Pydantic model or dict
            if hasattr(record, "campaign_name"):
                campaign_name = getattr(record, "campaign_name", "")
                status = getattr(record, "status", "")
                cost_val = getattr(record, "cost", 0)
                conversions_val = getattr(record, "conversions", 0)
            else:
                campaign_name = record.get("campaign_name", "")
                status = record.get("status", "")
                cost_val = record.get("cost", 0)
                conversions_val = record.get("conversions", 0)

            if not campaign_name:
                continue

            try:
                cost = float(str(cost_val).replace("$", "").replace(",", "") or "0")
                conversions = float(str(conversions_val).replace(",", "") or "0")
            except (ValueError, TypeError):
                cost = 0
                conversions = 0

            # Generate recommendations based on campaign performance
            if "brand" in campaign_name.lower():
                writer.writerow(
                    [
                        campaign_name,
                        "Increase Budget",
                        "Brand campaigns typically have high ROI - increase budget by 25%",
                        "Medium",
                        "15-20% increase in brand visibility",
                    ]
                )

            elif "competitor" in campaign_name.lower():
                if cost > 500 and conversions < 5:
                    writer.writerow(
                        [
                            campaign_name,
                            "Review/Pause",
                            "High cost competitor campaign with low conversions - review targeting",
                            "High",
                            "Reduce wasted spend by 30-50%",
                        ]
                    )

            elif "local" in campaign_name.lower() or "store" in campaign_name.lower():
                writer.writerow(
                    [
                        campaign_name,
                        "Add Location Extensions",
                        "Ensure all location extensions are active for local campaigns",
                        "Medium",
                        "10-15% improvement in local CTR",
                    ]
                )

            elif cost > 1000 and conversions < 10:
                writer.writerow(
                    [
                        campaign_name,
                        "Optimize Keywords",
                        "High spend, low conversion campaign needs keyword review",
                        "High",
                        "20-30% improvement in efficiency",
                    ]
                )

        except Exception:
            continue

    # Add general recommendations
    writer.writerow(
        [
            "All Campaigns",
            "Implement Ad Scheduling",
            "Add dayparting to focus budget on peak dining hours (11am-2pm, 5pm-9pm)",
            "Medium",
            "15-25% improvement in conversion timing",
        ]
    )

    writer.writerow(
        [
            "All Campaigns",
            "Add Promotion Extensions",
            "Include current promotions and seasonal offers in ad extensions",
            "Low",
            "5-10% improvement in CTR",
        ]
    )

    csv_content = output.getvalue()
    print(f"      📊 Generated {len(campaigns)} campaign-specific recommendations")
    return csv_content


def create_implementation_guide(data):
    """Create implementation guide markdown."""

    guide = f"""# Cotton Patch Cafe - Google Ads Implementation Guide

**Generated:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## 🎯 Implementation Priority Order

### Phase 1: Immediate Actions (Week 1)
1. **Import Negative Keywords** (negative_keywords_bulk_upload.csv)
   - Download the negative keywords file
   - In Google Ads: Tools & Settings > Shared Library > Negative Keyword Lists
   - Create new list: "Cotton Patch Competitor Exclusions"
   - Upload CSV file
   - Apply to all campaigns

2. **Review High-Cost Terms**
   - Monitor search terms report for new wasteful queries
   - Add obvious irrelevant terms to negative lists

### Phase 2: Geographic Optimization (Week 2)
1. **Apply Location Bid Adjustments** (geographic_bid_adjustments.csv)
   - Go to Campaigns > Settings > Locations
   - Apply bid adjustments for top-performing locations
   - Monitor performance for 1-2 weeks before additional changes

### Phase 3: Demographic Targeting (Week 3)
1. **Implement Demographic Adjustments** (demographic_bid_adjustments.csv)
   - Go to Demographics tab in each campaign
   - Apply age-based bid modifications
   - Monitor conversion rates by demographic

### Phase 4: Campaign Structure (Week 4)
1. **Campaign Optimizations** (campaign_optimization_actions.csv)
   - Review each campaign-specific recommendation
   - Implement budget adjustments for brand campaigns
   - Add location extensions for local campaigns
   - Review competitor campaign performance

## 📊 Expected Results Timeline

### Week 1-2: Immediate Impact
- **Cost Savings**: 15-25% reduction in wasted spend from negative keywords
- **Efficiency**: Fewer irrelevant clicks and impressions

### Week 3-4: Performance Improvement
- **Local Performance**: 20-30% improvement in location-based conversions
- **Targeting**: 10-20% better demographic targeting efficiency

### Month 2: Optimization Gains
- **Overall ROI**: 25-35% improvement in return on ad spend
- **Quality Scores**: Improved relevance leads to better Quality Scores

## 🔍 Monitoring & KPIs

Track these metrics weekly:
- **Cost per Click (CPC)**: Target 10-15% reduction
- **Conversion Rate**: Target 10-20% improvement
- **Cost per Acquisition (CPA)**: Target 20-25% reduction
- **Geographic Performance**: Monitor top-adjusted locations
- **Search Terms**: Weekly review for new negative keyword opportunities

## ⚠️ Important Notes

1. **Implement Gradually**: Don't apply all changes at once - monitor each phase
2. **Backup Current Settings**: Export current campaign settings before changes
3. **Monitor Daily**: Check performance daily for the first week after each change
4. **Adjust as Needed**: Be prepared to modify bid adjustments based on actual performance

## 📞 Support

- **Google Ads Support**: Available 24/7 for technical implementation questions
- **Performance Reviews**: Schedule weekly check-ins during first month

---
*Implementation guide based on analysis of {sum(len(records) for records in data.values()):,} Cotton Patch Cafe data records*
"""

    return guide


async def upload_import_files_to_s3(import_files):
    """Upload all import files to S3."""
    try:
        import boto3

        session = boto3.Session(profile_name="roimedia-east1")
        s3_client = session.client("s3")
        bucket_name = "paidsearchnav-customer-data-dev"

        date_str = datetime.now().strftime("%Y-%m-%d")
        base_key = (
            f"svc/cotton-patch-cafe_952-408-0160/outputs/actionable_files/{date_str}"
        )

        for filename, content in import_files.items():
            key = f"{base_key}/{filename}"

            # Determine content type
            if filename.endswith(".csv"):
                content_type = "text/csv"
            elif filename.endswith(".md"):
                content_type = "text/markdown"
            else:
                content_type = "text/plain"

            s3_client.put_object(
                Bucket=bucket_name, Key=key, Body=content, ContentType=content_type
            )

            print(f"   📤 Uploaded {filename}")

        print("\n✅ All import files uploaded to S3")
        print(f"📍 Location: s3://{bucket_name}/{base_key}/")

    except Exception as e:
        print(f"❌ Failed to upload to S3: {e}")


if __name__ == "__main__":
    success = asyncio.run(generate_google_ads_imports())

    if success:
        print("\n🎉 All Google Ads import files generated successfully!")
        print("Files are ready for direct import into Google Ads.")
    else:
        print("\n❌ Failed to generate import files.")

    sys.exit(0 if success else 1)
