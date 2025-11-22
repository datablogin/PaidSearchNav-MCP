#!/usr/bin/env python3
"""
Run search terms analysis on parsed data.
"""

import asyncio
import json
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from paidsearchnav.analyzers.search_terms import SearchTermsAnalyzer
from paidsearchnav.core.interfaces import DataProvider
from paidsearchnav.core.models.search_term import SearchTerm


class JsonFileDataProvider(DataProvider):
    """Simple data provider that reads from JSON files."""

    def __init__(self, search_terms_file: Path, keywords_file: Path = None):
        self.search_terms_file = search_terms_file
        self.keywords_file = keywords_file

    async def get_search_terms(
        self,
        customer_id,
        start_date=None,
        end_date=None,
        campaigns=None,
        ad_groups=None,
    ):
        """Load search terms from JSON file."""
        with open(self.search_terms_file, "r") as f:
            data = json.load(f)

        search_terms = []
        for item in data:
            search_term = SearchTerm.model_validate(item)
            search_terms.append(search_term)

        return search_terms

    async def get_keywords(self, customer_id, campaigns=None, ad_groups=None):
        """Return empty list for now since we don't have keywords data."""
        return []

    async def get_campaigns(self, customer_id):
        """Not implemented."""
        return []

    async def get_ad_groups(self, customer_id, campaigns=None):
        """Not implemented."""
        return []

    async def get_geographic_performance(
        self, customer_id, start_date, end_date, campaigns=None
    ):
        """Not implemented."""
        return []

    async def get_negative_keywords(self, customer_id, campaigns=None, ad_groups=None):
        """Return empty list for now."""
        return []

    async def get_placement_data(
        self, customer_id, start_date, end_date, campaigns=None
    ):
        """Not implemented."""
        return []

    async def get_shared_negative_lists(self, customer_id):
        """Not implemented."""
        return []

    async def get_campaign_shared_sets(self, customer_id, campaigns=None):
        """Not implemented."""
        return []

    async def get_shared_set_negatives(self, customer_id, shared_set_ids):
        """Not implemented."""
        return []


async def main(input_file=None):
    """Run the analysis."""
    # Path to parsed data - use provided file or default
    if input_file:
        search_terms_file = Path(input_file)
    else:
        # Look for any parsed search terms file
        processed_dir = Path("google_ads_exports/search_terms/processed")
        if processed_dir.exists():
            parsed_files = list(processed_dir.glob("*_parsed.json"))
            if parsed_files:
                search_terms_file = parsed_files[0]
                print(f"Using first found parsed file: {search_terms_file}")
            else:
                print("Error: No parsed search terms files found")
                return
        else:
            print(f"Error: Processed directory not found: {processed_dir}")
            return

    if not search_terms_file.exists():
        print(f"Error: File not found: {search_terms_file}")
        return

    # Create data provider
    data_provider = JsonFileDataProvider(search_terms_file)

    # Create analyzer with thresholds
    from paidsearchnav.core.config import AnalyzerThresholds

    thresholds = AnalyzerThresholds(
        min_impressions=10,  # Only analyze terms with 10+ impressions
    )

    analyzer = SearchTermsAnalyzer(data_provider=data_provider, thresholds=thresholds)

    # Run analysis
    print("Running search terms analysis...")
    from datetime import date, timedelta

    # Use date range from last 30 days
    end_date = date.today()
    start_date = end_date - timedelta(days=30)

    results = await analyzer.analyze(
        customer_id="themis-legal", start_date=start_date, end_date=end_date
    )

    # Display results
    print("\nAnalysis complete!")
    print(f"Total search terms analyzed: {results.total_search_terms}")

    # Show classifications
    print("\nClassifications:")
    print(f"- Add candidates: {len(results.add_candidates)}")
    print(f"- Negative candidates: {len(results.negative_candidates)}")
    print(f"- Already covered: {len(results.already_covered)}")
    print(f"- Review needed: {len(results.review_needed)}")

    # Show recommendations
    print(f"\nRecommendations: {len(results.recommendations)}")
    for rec in results.recommendations[:3]:
        print(f"  - [{rec.priority}] {rec.title}")
        print(f"    {rec.description}")

    # Show some examples
    if results.negative_candidates:
        print("\nNegative Keyword Candidates:")
        for term in results.negative_candidates[:3]:
            print(
                f"  - {term.search_term}: ${term.metrics.cost:.2f} cost, "
                f"{term.metrics.conversions} conversions"
            )

    if results.add_candidates:
        print("\nPositive Keyword Candidates:")
        for term in results.add_candidates[:3]:
            print(
                f"  - {term.search_term}: ${term.metrics.cost:.2f} cost, "
                f"{term.metrics.conversions} conversions"
            )

    # Save full results
    output_file = Path("analysis_results/search_terms_analysis_themis_legal.json")
    output_file.parent.mkdir(exist_ok=True)

    # Convert to dict for JSON serialization
    results_dict = {
        "total_search_terms": results.total_search_terms,
        "classifications": {
            "add_candidates": [term.model_dump() for term in results.add_candidates],
            "negative_candidates": [
                term.model_dump() for term in results.negative_candidates
            ],
            "already_covered": [term.model_dump() for term in results.already_covered],
            "review_needed": [term.model_dump() for term in results.review_needed],
        },
        "recommendations": [rec.model_dump() for rec in results.recommendations],
    }

    with open(output_file, "w") as f:
        json.dump(results_dict, f, indent=2)

    print(f"\nFull results saved to: {output_file}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Run search terms analysis on parsed data"
    )
    parser.add_argument("--input", help="Path to parsed JSON file", default=None)
    args = parser.parse_args()

    asyncio.run(main(args.input))
