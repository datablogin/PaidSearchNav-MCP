#!/usr/bin/env python3
"""
Transform Google Ads CSV exports to match expected format.
"""

import csv
import sys
from pathlib import Path

from match_type_mapping import normalize_match_type

# Constants for ID generation
CAMPAIGN_ID_START = 1000
AD_GROUP_ID_START = 2000
KEYWORD_ID_START = 3000


def transform_search_terms_csv(input_file, output_file):
    """Transform search terms CSV to expected format."""

    try:
        with open(input_file, "r", encoding="utf-8") as infile:
            # Read all lines
            lines = infile.readlines()

        # Find the actual header line (contains "Search term")
        header_index = -1
        for i, line in enumerate(lines):
            if line.strip() and "Search term" in line and "Match type" in line:
                header_index = i
                break

        if header_index == -1:
            print("Error: Could not find header line")
            return

        print(
            f"Found header at line {header_index + 1}: {lines[header_index].strip()[:50]}..."
        )

        # Create a CSV reader starting from the header line
        import io

        csv_data = io.StringIO("".join(lines[header_index:]))
        reader = csv.DictReader(csv_data)

        # Required columns for the parser
        output_columns = [
            "Search term",
            "Match type",
            "Campaign",
            "Campaign ID",
            "Ad group",
            "Ad group ID",
            "Keyword",
            "Keyword ID",
            "Impressions",
            "Clicks",
            "Cost",
            "Conversions",
            "Conversion value",
        ]

        with open(output_file, "w", newline="", encoding="utf-8") as outfile:
            writer = csv.DictWriter(outfile, fieldnames=output_columns)
            writer.writeheader()

            campaign_id_counter = CAMPAIGN_ID_START
            ad_group_id_counter = AD_GROUP_ID_START
            keyword_id_counter = KEYWORD_ID_START

            # Track unique campaigns and ad groups for consistent IDs
            campaign_ids = {}
            ad_group_ids = {}

            row_count = 0
            for row in reader:
                # Skip total rows
                if row.get("Search term", "").startswith("Total:"):
                    continue

                # Skip empty rows
                if not row.get("Search term", "").strip():
                    continue

                row_count += 1

                # Debug first row
                if row_count == 1:
                    print(f"First data row keys: {list(row.keys())}")
                    print(f"First data row: {dict(list(row.items())[:5])}")

                # Generate consistent IDs
                campaign_key = row.get("Campaign", "")
                if campaign_key and campaign_key not in campaign_ids:
                    campaign_ids[campaign_key] = str(campaign_id_counter)
                    campaign_id_counter += 1

                ad_group_key = f"{campaign_key}|{row.get('Ad group', '')}"
                if ad_group_key != "|" and ad_group_key not in ad_group_ids:
                    ad_group_ids[ad_group_key] = str(ad_group_id_counter)
                    ad_group_id_counter += 1

                # Transform the row
                output_row = {
                    "Search term": row.get("Search term", ""),
                    "Match type": normalize_match_type(row.get("Match type", "")),
                    "Campaign": row.get("Campaign", ""),
                    "Campaign ID": campaign_ids.get(campaign_key, ""),
                    "Ad group": row.get("Ad group", ""),
                    "Ad group ID": ad_group_ids.get(ad_group_key, ""),
                    "Keyword": "",  # Not provided in export
                    "Keyword ID": str(keyword_id_counter),
                    "Impressions": row.get("Impr.", "0"),
                    "Clicks": row.get("Clicks", "0"),
                    "Cost": row.get("Cost", "0.00").replace("$", "").replace(",", ""),
                    "Conversions": row.get("Conversions", "0.00"),
                    "Conversion value": row.get("Conv. value", "0.00")
                    .replace("$", "")
                    .replace(",", ""),
                }

                keyword_id_counter += 1
                writer.writerow(output_row)

            print(f"Processed {row_count} data rows")

        print(f"Transformed {input_file} -> {output_file}")

    except FileNotFoundError:
        print(f"Error: Input file {input_file} not found")
        raise
    except csv.Error as e:
        print(f"Error parsing CSV: {e}")
        raise
    except Exception as e:
        print(f"Unexpected error during transformation: {e}")
        raise


def main():
    if len(sys.argv) < 2:
        print("Usage: python transform_google_ads_csv.py <input_file>")
        sys.exit(1)

    input_file = Path(sys.argv[1])
    if not input_file.exists():
        print(f"Error: File {input_file} not found")
        sys.exit(1)

    output_file = input_file.parent / f"{input_file.stem}-transformed.csv"

    if "search" in input_file.stem.lower():
        transform_search_terms_csv(input_file, output_file)
    else:
        print("Currently only search terms transformation is supported")
        sys.exit(1)


if __name__ == "__main__":
    main()
