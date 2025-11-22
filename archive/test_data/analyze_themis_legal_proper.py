#!/usr/bin/env python3
"""
Properly analyze Themis Legal search terms data using the transformed JSON.
"""

import json
from datetime import datetime
from pathlib import Path


def validate_search_term(term):
    """Validate that a search term has the required structure.

    Args:
        term: Dictionary containing search term data

    Returns:
        bool: True if valid, False otherwise
    """
    required_fields = ["search_term", "campaign_name", "ad_group_name"]
    for field in required_fields:
        if field not in term or not term[field]:
            return False

    # Validate metrics if present
    if "metrics" in term and term["metrics"]:
        metrics = term["metrics"]
        metric_fields = ["impressions", "clicks", "cost", "conversions"]
        for field in metric_fields:
            if field in metrics and not isinstance(metrics[field], (int, float)):
                return False

    return True


def analyze_search_terms(search_terms):
    """Analyze search terms and classify them based on performance."""
    classifications = {
        "add_candidates": [],
        "negative_candidates": [],
        "already_covered": [],
        "review_needed": [],
    }

    # Validate input
    if not search_terms:
        print("Warning: No search terms provided for analysis")
        return classifications

    for term in search_terms:
        # Skip invalid terms
        if not validate_search_term(term):
            print(
                f"Warning: Skipping invalid search term: {term.get('search_term', 'Unknown')}"
            )
            continue

        # Get metrics
        metrics = term.get("metrics", {})
        impressions = metrics.get("impressions", 0)
        clicks = metrics.get("clicks", 0)
        cost = metrics.get("cost", 0)
        conversions = metrics.get("conversions", 0)
        ctr = metrics.get("ctr", 0)
        cpa = metrics.get("cpa", 0)
        conversion_rate = metrics.get("conversion_rate", 0)

        # Classify based on performance
        if conversions > 0:
            # Has conversions - potential add candidate
            if cpa <= 100:  # Good CPA for legal industry
                classification = "ADD_CANDIDATE"
                reason = f"High performing: {conversions} conversions, CPA: ${cpa:.2f}"
                recommendation = (
                    f"Add as {term.get('match_type', 'Phrase match')} keyword"
                )
            else:
                classification = "REVIEW_NEEDED"
                reason = f"Has conversions but high CPA: {conversions} conversions, CPA: ${cpa:.2f}"
                recommendation = "Review for optimization opportunities"
        elif clicks > 0 and cost > 50:
            # Spending money with no conversions
            classification = "NEGATIVE_CANDIDATE"
            reason = (
                f"Wasteful spend: ${cost:.2f} cost, {clicks} clicks, no conversions"
            )
            recommendation = "Add as negative keyword"
        elif impressions > 100 and clicks == 0:
            # High impressions, no clicks - irrelevant
            classification = "NEGATIVE_CANDIDATE"
            reason = f"Low relevance: {impressions} impressions, no clicks"
            recommendation = "Consider as negative keyword"
        else:
            # Low volume or new term
            classification = "REVIEW_NEEDED"
            reason = f"Low volume: {impressions} impressions, {clicks} clicks"
            recommendation = "Monitor performance"

        # Create result object with all data
        result = {
            "search_term": term.get("search_term", ""),
            "campaign_id": term.get("campaign_id", ""),
            "campaign_name": term.get("campaign_name", ""),
            "ad_group_id": term.get("ad_group_id", ""),
            "ad_group_name": term.get("ad_group_name", ""),
            "keyword_id": term.get("keyword_id", ""),
            "keyword_text": term.get("keyword_text", ""),
            "match_type": term.get("match_type", ""),
            "metrics": metrics,
            "classification": classification,
            "classification_reason": reason,
            "recommendation": recommendation,
            "has_near_me": term.get("has_near_me", False),
            "has_location": term.get("has_location", False),
            "location_terms": term.get("location_terms", []),
        }

        # Add to appropriate category
        if classification == "ADD_CANDIDATE":
            classifications["add_candidates"].append(result)
        elif classification == "NEGATIVE_CANDIDATE":
            classifications["negative_candidates"].append(result)
        elif classification == "REVIEW_NEEDED":
            classifications["review_needed"].append(result)

    return classifications


def generate_recommendations(classifications):
    """Generate actionable recommendations based on analysis."""
    recommendations = []

    # Add candidates recommendation
    add_count = len(classifications["add_candidates"])
    if add_count > 0:
        top_performer = max(
            classifications["add_candidates"],
            key=lambda x: x["metrics"].get("conversions", 0),
        )
        recommendations.append(
            {
                "type": "ADD_KEYWORD",
                "priority": "HIGH",
                "title": f"Add {add_count} high-performing search terms as keywords",
                "description": f"Add {add_count} high-performing search terms as keywords, starting with '{top_performer['search_term']}' ({top_performer['metrics'].get('conversions', 0)} conversions)",
            }
        )

    # Negative candidates recommendation
    neg_count = len(classifications["negative_candidates"])
    if neg_count > 0:
        total_waste = sum(
            t["metrics"].get("cost", 0) for t in classifications["negative_candidates"]
        )
        recommendations.append(
            {
                "type": "ADD_NEGATIVE",
                "priority": "HIGH",
                "title": f"Add {neg_count} negative keywords to reduce waste",
                "description": f"Add {neg_count} negative keywords to save ${total_waste:.2f} in wasted spend",
            }
        )

    # Location optimization
    location_terms = [
        t
        for t in classifications["add_candidates"]
        if t.get("has_near_me") or t.get("has_location")
    ]
    if location_terms:
        recommendations.append(
            {
                "type": "OPTIMIZE_LOCATION",
                "priority": "MEDIUM",
                "title": "Optimize for local search intent",
                "description": f"Found {len(location_terms)} high-performing local searches. Ensure location extensions are active and consider local-focused ad copy.",
            }
        )

    return recommendations


def main(data_file_path=None):
    """Main analysis function.

    Args:
        data_file_path: Optional path to the data file. If not provided, uses default.
    """
    print("=== Themis Legal Search Terms Analysis ===")

    # Use provided path or default
    if data_file_path:
        data_file = Path(data_file_path)
    else:
        data_file = Path(
            "google_ads_exports/search_terms/processed/search-terms-report-Themis-Legal-transformed_parsed.json"
        )

    if not data_file.exists():
        print(f"Error: Data file not found: {data_file}")
        print(f"Current working directory: {Path.cwd()}")
        print(f"Expected path: {data_file.absolute()}")
        return

    print(f"Loading data from: {data_file}")

    try:
        with open(data_file, "r") as f:
            search_terms = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in file {data_file}: {e}")
        return
    except Exception as e:
        print(f"Error reading file {data_file}: {e}")
        return

    print(f"Loaded {len(search_terms)} search terms")

    # Run analysis
    print("\nAnalyzing search terms...")
    classifications = analyze_search_terms(search_terms)

    # Generate recommendations
    recommendations = generate_recommendations(classifications)

    # Print summary
    print("\n=== Analysis Summary ===")
    print(f"Total search terms: {len(search_terms)}")
    print(f"Add candidates: {len(classifications['add_candidates'])}")
    print(f"Negative candidates: {len(classifications['negative_candidates'])}")
    print(f"Review needed: {len(classifications['review_needed'])}")

    # Calculate totals
    total_cost = sum(t.get("metrics", {}).get("cost", 0) for t in search_terms)
    total_conversions = sum(
        t.get("metrics", {}).get("conversions", 0) for t in search_terms
    )
    waste_amount = sum(
        t["metrics"].get("cost", 0) for t in classifications["negative_candidates"]
    )

    print(f"\nTotal spend: ${total_cost:.2f}")
    print(f"Total conversions: {total_conversions}")
    if total_cost > 0:
        savings_percentage = waste_amount / total_cost * 100
        print(
            f"Potential savings: ${waste_amount:.2f} ({savings_percentage:.1f}% of spend)"
        )
    else:
        print(f"Potential savings: ${waste_amount:.2f}")

    # Save analysis results
    output_dir = Path("analysis_results")
    output_dir.mkdir(exist_ok=True)
    output_file = output_dir / "themis_legal_analysis_proper.json"

    analysis_output = {
        "analysis_date": datetime.now().isoformat(),
        "total_search_terms": len(search_terms),
        "total_cost": total_cost,
        "total_conversions": total_conversions,
        "classifications": classifications,
        "recommendations": recommendations,
        "summary": {
            "add_count": len(classifications["add_candidates"]),
            "negative_count": len(classifications["negative_candidates"]),
            "review_count": len(classifications["review_needed"]),
            "potential_savings": waste_amount,
            "savings_percentage": (waste_amount / total_cost * 100)
            if total_cost > 0
            else 0,
        },
    }

    with open(output_file, "w") as f:
        json.dump(analysis_output, f, indent=2, default=str)

    print(f"\nAnalysis saved to: {output_file}")

    # Show top recommendations
    print("\n=== Top Recommendations ===")
    for i, rec in enumerate(recommendations[:3], 1):
        print(f"\n{i}. [{rec['priority']}] {rec['title']}")
        print(f"   {rec['description']}")

    # Show top performers
    if classifications["add_candidates"]:
        print("\n=== Top Performing Search Terms ===")
        sorted_performers = sorted(
            classifications["add_candidates"],
            key=lambda x: x["metrics"].get("conversions", 0),
            reverse=True,
        )
        for term in sorted_performers[:5]:
            metrics = term["metrics"]
            print(f"\n• {term['search_term']}")
            print(f"  Campaign: {term['campaign_name']}")
            print(
                f"  Performance: {metrics.get('conversions', 0)} conv, "
                f"${metrics.get('cost', 0):.2f} cost, "
                f"${metrics.get('cpa', 0):.2f} CPA"
            )

    # Show biggest waste
    if classifications["negative_candidates"]:
        print("\n=== Biggest Wasteful Spend ===")
        sorted_waste = sorted(
            classifications["negative_candidates"],
            key=lambda x: x["metrics"].get("cost", 0),
            reverse=True,
        )
        for term in sorted_waste[:5]:
            metrics = term["metrics"]
            print(f"\n• {term['search_term']}")
            print(f"  Campaign: {term['campaign_name']}")
            print(
                f"  Waste: ${metrics.get('cost', 0):.2f} cost, "
                f"{metrics.get('clicks', 0)} clicks, "
                f"0 conversions"
            )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Analyze Google Ads search terms data")
    parser.add_argument(
        "--data-file", type=str, help="Path to the transformed JSON data file"
    )

    args = parser.parse_args()
    main(args.data_file)
