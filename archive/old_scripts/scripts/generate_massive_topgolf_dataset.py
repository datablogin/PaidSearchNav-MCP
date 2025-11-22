#!/usr/bin/env python3
"""
Generate Massive TopGolf Dataset for Production Scale Testing
Creates a 206,676 search term dataset based on existing TopGolf data pattern
"""

import json
import logging
import random
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_base_data() -> Dict[str, Any]:
    """Load the base TopGolf dataset as a template"""
    base_file = "/Users/robertwelborn/PycharmProjects/PaidSearchNav/topgolf_real_data_20250822_181442.json"
    with open(base_file, "r") as f:
        return json.load(f)


def generate_search_terms(
    base_terms: List[Dict], target_count: int = 206676
) -> List[Dict]:
    """Generate massive search terms dataset based on base patterns"""
    logger.info(
        f"🚀 Generating {target_count:,} search terms from {len(base_terms)} base patterns..."
    )

    # TopGolf search term variations
    topgolf_variations = [
        "topgolf",
        "top golf",
        "topgolf near me",
        "topgolf locations",
        "topgolf prices",
        "topgolf hours",
        "topgolf reservations",
        "book topgolf",
        "topgolf party",
        "topgolf birthday party",
        "topgolf corporate events",
        "topgolf menu",
        "topgolf bay rental",
        "topgolf driving range",
        "topgolf entertainment",
        "topgolf golf",
        "topgolf fun",
        "topgolf activity",
        "topgolf night out",
        "topgolf date night",
        "topgolf team building",
        "topgolf event space",
    ]

    location_modifiers = [
        "near me",
        "in dallas",
        "in austin",
        "in houston",
        "in san antonio",
        "in atlanta",
        "in chicago",
        "in denver",
        "in las vegas",
        "in phoenix",
        "in orlando",
        "in miami",
        "in nashville",
        "in charlotte",
        "in tampa",
        "locations",
        "closest",
        "nearby",
        "around me",
        "local",
    ]

    action_modifiers = [
        "book",
        "reserve",
        "schedule",
        "plan",
        "visit",
        "try",
        "experience",
        "play",
        "enjoy",
        "check out",
        "find",
        "locate",
        "search for",
    ]

    generated_terms = []

    # Use base terms as templates
    for i in range(target_count):
        if i % 10000 == 0:
            logger.info(f"Generated {i:,} terms...")

        base_term = random.choice(base_terms)

        # Create variations
        if i < len(topgolf_variations) * len(location_modifiers):
            # High-volume branded terms
            topgolf_term = random.choice(topgolf_variations)
            location = random.choice(location_modifiers)
            search_term = f"{topgolf_term} {location}".strip()

            # Higher performance for branded terms
            base_clicks = random.randint(50, 500)
            base_impressions = random.randint(base_clicks * 10, base_clicks * 50)
            base_conversions = random.randint(5, int(base_clicks * 0.3))

        elif i < len(topgolf_variations) * len(action_modifiers):
            # Action-based terms
            action = random.choice(action_modifiers)
            topgolf_term = random.choice(topgolf_variations)
            search_term = f"{action} {topgolf_term}".strip()

            # Medium performance
            base_clicks = random.randint(10, 100)
            base_impressions = random.randint(base_clicks * 15, base_clicks * 60)
            base_conversions = random.randint(1, int(base_clicks * 0.2))

        else:
            # Long-tail and generic terms
            if random.random() < 0.3:
                search_term = random.choice(
                    [
                        "golf near me",
                        "driving range",
                        "golf entertainment",
                        "birthday party places",
                        "corporate events venue",
                        "team building activities",
                        "date night ideas",
                        "things to do",
                        "entertainment venues",
                        "golf lessons",
                        "mini golf",
                        "family activities",
                        "weekend plans",
                        "golf simulator",
                        "sports bar",
                    ]
                )
            else:
                # Combine random elements
                elements = random.sample(
                    topgolf_variations + location_modifiers + action_modifiers, 2
                )
                search_term = " ".join(elements)

            # Lower performance for generic terms
            base_clicks = random.randint(1, 25)
            base_impressions = random.randint(base_clicks * 20, base_clicks * 100)
            base_conversions = random.randint(0, int(base_clicks * 0.1))

        # Generate cost (in micros)
        avg_cpc = random.uniform(1.5, 8.5)  # $1.50 to $8.50
        cost_micros = int(base_clicks * avg_cpc * 1000000)

        # Calculate derived metrics
        ctr = (base_clicks / base_impressions) if base_impressions > 0 else 0
        conversion_rate = (base_conversions / base_clicks) if base_clicks > 0 else 0
        cpa = (cost_micros / 1000000 / base_conversions) if base_conversions > 0 else 0

        # Generate random date within last 30 days
        start_date = datetime.now() - timedelta(days=30)
        random_date = start_date + timedelta(days=random.randint(0, 29))

        # Create term record
        term = {
            "date": random_date.strftime("%Y-%m-%d"),
            "customer_id": "577-746-1198",
            "campaign_id": f"campaign_{random.randint(0, 5)}",
            "campaign_name": random.choice(
                [
                    "TopGolf Campaign 1",
                    "TopGolf Brand Campaign",
                    "TopGolf Local Campaign",
                    "TopGolf Generic Campaign",
                    "TopGolf Competitor Campaign",
                    "TopGolf Events Campaign",
                ]
            ),
            "ad_group_id": f"adgroup_{random.randint(1, 20)}",
            "ad_group_name": random.choice(
                [
                    "Topgolf Near Me Ad Group",
                    "Topgolf Brand Ad Group",
                    "Topgolf Reservations Ad Group",
                    "Topgolf Events Ad Group",
                    "Topgolf Locations Ad Group",
                    "Topgolf General Ad Group",
                ]
            ),
            "search_term": search_term,
            "keyword_text": random.choice(
                [search_term, f"[{search_term}]", f'"{search_term}"']
            ),
            "match_type": random.choice(["BROAD", "PHRASE", "EXACT"]),
            "impressions": base_impressions,
            "clicks": base_clicks,
            "cost_micros": cost_micros,
            "conversions": base_conversions,
            "conversion_value": base_conversions * random.uniform(50, 200)
            if base_conversions > 0
            else 0,
            "ctr": round(ctr, 4),
            "avg_cpc": round(avg_cpc, 2),
            "conversion_rate": round(conversion_rate, 4),
            "cpa": round(cpa, 2) if cpa > 0 else 0,
            "local_intent_score": random.uniform(0.1, 1.0)
            if "near me" in search_term or "location" in search_term
            else random.uniform(0.0, 0.5),
        }

        generated_terms.append(term)

    logger.info(f"✅ Generated {len(generated_terms):,} search terms")
    return generated_terms


def generate_keywords(search_terms: List[Dict]) -> List[Dict]:
    """Generate keywords dataset from search terms"""
    logger.info("🔑 Generating keywords dataset...")

    # Extract unique keywords from search terms
    unique_keywords = {}

    for term in search_terms:
        keyword = term["keyword_text"]
        if keyword not in unique_keywords:
            unique_keywords[keyword] = {
                "keyword_id": str(uuid.uuid4())[:8],
                "campaign_id": term["campaign_id"],
                "campaign_name": term["campaign_name"],
                "ad_group_id": term["ad_group_id"],
                "ad_group_name": term["ad_group_name"],
                "text": keyword,
                "match_type": term["match_type"],
                "status": "ENABLED",
                "cpc_bid": round(random.uniform(2.0, 10.0), 2),
                "impressions": 0,
                "clicks": 0,
                "cost": 0,
                "conversions": 0,
                "quality_score": random.randint(4, 10),
            }

        # Aggregate metrics
        unique_keywords[keyword]["impressions"] += term["impressions"]
        unique_keywords[keyword]["clicks"] += term["clicks"]
        unique_keywords[keyword]["cost"] += term["cost_micros"] / 1000000
        unique_keywords[keyword]["conversions"] += term["conversions"]

    keywords = list(unique_keywords.values())
    logger.info(f"✅ Generated {len(keywords):,} unique keywords")
    return keywords


def generate_campaigns() -> List[Dict]:
    """Generate campaigns dataset"""
    campaigns = []
    for i in range(6):
        campaigns.append(
            {
                "campaign_id": f"campaign_{i}",
                "campaign_name": f"TopGolf Campaign {i + 1}",
                "status": "ENABLED",
                "campaign_type": "SEARCH",
                "budget": random.randint(1000, 5000),
                "target_cpa": random.randint(20, 80),
            }
        )

    return campaigns


def calculate_summary_stats(data: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate summary statistics for the massive dataset"""
    search_terms = data["search_terms"]
    keywords = data["keywords"]

    total_cost = sum(term["cost_micros"] for term in search_terms) / 1000000
    total_conversions = sum(term["conversions"] for term in search_terms)
    total_clicks = sum(term["clicks"] for term in search_terms)
    total_impressions = sum(term["impressions"] for term in search_terms)

    high_performers = len([t for t in search_terms if t["conversions"] >= 5])

    return {
        "total_search_terms": len(search_terms),
        "total_keywords": len(keywords),
        "total_campaigns": len(data["campaigns"]),
        "total_ad_spend": round(total_cost, 2),
        "total_conversions": total_conversions,
        "total_clicks": total_clicks,
        "total_impressions": total_impressions,
        "high_performing_terms": high_performers,
        "avg_cpa": round(total_cost / total_conversions, 2)
        if total_conversions > 0
        else 0,
        "overall_ctr": round((total_clicks / total_impressions) * 100, 2)
        if total_impressions > 0
        else 0,
        "overall_conversion_rate": round((total_conversions / total_clicks) * 100, 2)
        if total_clicks > 0
        else 0,
    }


def main():
    """Generate massive TopGolf dataset"""
    logger.info("🚀 GENERATING MASSIVE TOPGOLF DATASET FOR PRODUCTION SCALE TESTING")
    logger.info("=" * 80)
    logger.info("Target: 206,676 search terms (matching actual BigQuery extraction)")
    logger.info("=" * 80)

    start_time = datetime.now()

    try:
        # Load base data
        logger.info("📥 Loading base TopGolf dataset...")
        base_data = load_base_data()
        base_terms = base_data.get("search_terms", [])
        logger.info(f"✅ Loaded {len(base_terms)} base search terms")

        # Generate massive search terms dataset
        massive_search_terms = generate_search_terms(base_terms, 206676)

        # Generate corresponding keywords and campaigns
        massive_keywords = generate_keywords(massive_search_terms)
        campaigns = generate_campaigns()

        # Create complete dataset
        massive_dataset = {
            "customer_id": "577-746-1198",
            "customer_name": "TopGolf",
            "extraction_date": datetime.now().isoformat(),
            "data_source": "Generated from base patterns for production scale testing",
            "search_terms": massive_search_terms,
            "keywords": massive_keywords,
            "campaigns": campaigns,
        }

        # Calculate summary statistics
        summary = calculate_summary_stats(massive_dataset)
        massive_dataset["summary"] = summary

        # Save massive dataset
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"/Users/robertwelborn/PycharmProjects/PaidSearchNav/topgolf_massive_dataset_{timestamp}.json"

        logger.info(f"💾 Saving massive dataset to: {output_file}")
        with open(output_file, "w") as f:
            json.dump(massive_dataset, f, indent=2)

        end_time = datetime.now()
        generation_time = (end_time - start_time).total_seconds()

        logger.info("=" * 80)
        logger.info("✅ MASSIVE DATASET GENERATION COMPLETE")
        logger.info("=" * 80)
        logger.info("📊 Dataset Summary:")
        logger.info(f"   Search Terms: {summary['total_search_terms']:,}")
        logger.info(f"   Keywords: {summary['total_keywords']:,}")
        logger.info(f"   Campaigns: {summary['total_campaigns']:,}")
        logger.info(f"   Total Ad Spend: ${summary['total_ad_spend']:,.2f}")
        logger.info(f"   Total Conversions: {summary['total_conversions']:,}")
        logger.info(f"   High Performers: {summary['high_performing_terms']:,}")
        logger.info(f"   Generation Time: {generation_time:.1f} seconds")
        logger.info(
            f"   File Size: {len(json.dumps(massive_dataset)) / 1024 / 1024:.1f} MB"
        )
        logger.info(f"📁 Output File: {output_file}")

        return output_file

    except Exception as e:
        logger.error(f"❌ Error generating massive dataset: {e}")
        raise


if __name__ == "__main__":
    main()
