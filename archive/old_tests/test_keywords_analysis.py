#!/usr/bin/env python3
"""Test script to demonstrate keywords analysis directly."""

import asyncio
import json
from datetime import datetime
from pathlib import Path

from paidsearchnav.analyzers.keyword_analyzer import KeywordAnalyzer
from paidsearchnav.parsers.csv_parser import GoogleAdsCSVParser


class CSVDataProvider:
    """Data provider that uses parsed CSV data."""

    def __init__(self, data, data_type: str):
        self.data = data
        self.data_type = data_type

    async def get_keywords(self, *args, **kwargs):
        """Return keywords if data type matches."""
        if self.data_type == "keywords":
            return self.data
        return []

    async def get_search_terms(self, *args, **kwargs):
        """Return search terms if data type matches."""
        return []

    async def get_geo_performance(self, *args, **kwargs):
        """Return geo performance data if data type matches."""
        return []

    async def get_negative_keywords(self, *args, **kwargs):
        """Return negative keywords if data type matches."""
        return []


async def analyze_keywords():
    """Analyze the Fitness Connection keywords CSV."""
    print("🔍 Starting Keywords Analysis for Fitness Connection")

    # Parse the CSV file (properly formatted with headers)
    csv_path = Path("final_keyword_file.csv")
    parser = GoogleAdsCSVParser(file_type="keywords", strict_validation=False)

    print(f"📊 Parsing CSV file: {csv_path}")
    records = parser.parse(csv_path)
    print(f"✅ Parsed {len(records)} keyword records")

    # Create data provider
    data_provider = CSVDataProvider(records, "keywords")

    # Initialize analyzer
    analyzer = KeywordAnalyzer(data_provider=data_provider)

    # Run analysis
    print("🔧 Running keyword analysis...")
    result = await analyzer.analyze(
        customer_id="2879C12F-C38",
        start_date=datetime(2025, 5, 18),
        end_date=datetime(2025, 8, 15),
    )

    print("📈 Analysis Complete!")
    print(f"  - Analysis ID: {result.analysis_id}")
    print(f"  - Total Records: {len(records)}")
    print(f"  - Recommendations: {len(result.recommendations)}")

    # Display metrics
    print("\n📊 Key Metrics:")
    metrics = result.metrics.model_dump()
    for key, value in metrics.items():
        if isinstance(value, float):
            print(f"  - {key}: {value:.2f}")
        else:
            print(f"  - {key}: {value}")

    # Display top recommendations
    print("\n💡 Top Recommendations:")
    for i, rec in enumerate(result.recommendations[:5], 1):
        print(f"\n{i}. {rec.title}")
        print(f"   Priority: {rec.priority}")
        print(f"   Type: {rec.type}")
        print(f"   Description: {rec.description}")
        if hasattr(rec, "affected_items") and rec.affected_items:
            print(f"   Affected Items: {len(rec.affected_items)} items")

    # Save results to JSON
    output_data = {
        "analysis_id": result.analysis_id,
        "customer_id": "2879C12F-C38",
        "file_type": "keywords",
        "total_records": len(records),
        "metrics": metrics,
        "recommendations": [
            {
                "id": f"rec_{i + 1}",
                "type": rec.type,
                "priority": rec.priority,
                "title": rec.title,
                "description": rec.description,
                "affected_items": getattr(rec, "affected_items", []),
                "estimated_impact": getattr(rec, "estimated_impact", None),
            }
            for i, rec in enumerate(result.recommendations)
        ],
        "analysis_timestamp": datetime.now().isoformat(),
        "s3_source": "s3://paidsearchnav-customer-data-dev/ret/fitness-connection_2879C12F-C38/inputs/Search keyword report (1).csv",
    }

    output_file = "fitness_connection_keywords_analysis.json"
    with open(output_file, "w") as f:
        json.dump(output_data, f, indent=2)

    print(f"\n💾 Results saved to: {output_file}")
    print("📁 Raw data insights available in result.raw_data")

    return result


if __name__ == "__main__":
    asyncio.run(analyze_keywords())
