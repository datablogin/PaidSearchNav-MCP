#!/usr/bin/env python3
"""
Process Google Ads CSV exports in the test data directory.

This script helps you:
1. Parse CSV files from Google Ads exports
2. Run analyses on the data
3. Save results for review
"""

import json
import logging

# Add the project root to the Python path
import sys
from pathlib import Path
from typing import Optional

import click

sys.path.insert(0, str(Path(__file__).parent.parent))

from paidsearchnav.parsers.csv_parser import GoogleAdsCSVParser

# Set up logging
log_dir = Path(__file__).parent / "logs"
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(log_dir / "processing.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


class TestDataProcessor:
    """Process test data CSV files."""

    def __init__(self, base_dir: Path = None):
        self.base_dir = base_dir or Path(__file__).parent
        # Create parsers for different file types
        self.keyword_parser = GoogleAdsCSVParser(file_type="keywords")
        self.search_term_parser = GoogleAdsCSVParser(file_type="search_terms")
        self.results_dir = self.base_dir / "analysis_results"
        self.results_dir.mkdir(exist_ok=True)

    def process_keywords_file(self, csv_path: Path) -> dict:
        """Process a keywords CSV file."""
        logger.info(f"Processing keywords file: {csv_path}")

        try:
            # Parse the CSV
            keywords = self.keyword_parser.parse(csv_path)
            logger.info(f"Parsed {len(keywords)} keywords")
        except Exception as e:
            logger.error(f"Failed to parse keywords file {csv_path}: {e}")
            raise

        # Save parsed data
        parsed_path = (
            csv_path.parent.parent / "processed" / f"{csv_path.stem}_parsed.json"
        )
        parsed_path.parent.mkdir(exist_ok=True)

        try:
            with open(parsed_path, "w") as f:
                json.dump([k.model_dump() for k in keywords], f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save parsed keywords: {e}")
            raise

        return {
            "file": str(csv_path),
            "keywords_count": len(keywords),
            "parsed_file": str(parsed_path),
        }

    def process_search_terms_file(self, csv_path: Path) -> dict:
        """Process a search terms CSV file."""
        logger.info(f"Processing search terms file: {csv_path}")

        try:
            # Parse the CSV
            search_terms = self.search_term_parser.parse(csv_path)
            logger.info(f"Parsed {len(search_terms)} search terms")
        except Exception as e:
            logger.error(f"Failed to parse search terms file {csv_path}: {e}")
            raise

        # Save parsed data
        parsed_path = (
            csv_path.parent.parent / "processed" / f"{csv_path.stem}_parsed.json"
        )
        parsed_path.parent.mkdir(exist_ok=True)

        try:
            with open(parsed_path, "w") as f:
                json.dump(
                    [st.model_dump() for st in search_terms], f, indent=2, default=str
                )
        except Exception as e:
            logger.error(f"Failed to save parsed search terms: {e}")
            raise

        return {
            "file": str(csv_path),
            "search_terms_count": len(search_terms),
            "parsed_file": str(parsed_path),
        }


@click.group()
def cli():
    """Process Google Ads test data."""
    pass


@cli.command()
@click.option(
    "--type",
    "data_type",
    type=click.Choice(["keywords", "search_terms"]),
    required=True,
    help="Type of data to process",
)
@click.option(
    "--file",
    "csv_file",
    type=click.Path(exists=True),
    help="Specific CSV file to process",
)
def process(data_type: str, csv_file: Optional[str]):
    """Process CSV files in the test data directory."""
    processor = TestDataProcessor()

    if csv_file:
        # Process specific file
        csv_path = Path(csv_file)
        if data_type == "keywords":
            result = processor.process_keywords_file(csv_path)
        else:
            result = processor.process_search_terms_file(csv_path)

        click.echo(json.dumps(result, indent=2))
    else:
        # Process all files of the given type
        raw_dir = processor.base_dir / "google_ads_exports" / data_type / "raw"
        if not raw_dir.exists():
            click.echo(f"No {data_type} files found in {raw_dir}")
            return

        results = []
        for csv_path in raw_dir.glob("*.csv"):
            if data_type == "keywords":
                result = processor.process_keywords_file(csv_path)
            else:
                result = processor.process_search_terms_file(csv_path)
            results.append(result)

        click.echo(json.dumps(results, indent=2))


@cli.command()
def list_files():
    """List all CSV files in the test data directory."""
    processor = TestDataProcessor()
    exports_dir = processor.base_dir / "google_ads_exports"

    for data_type in [
        "keywords",
        "search_terms",
        "campaigns",
        "geo_performance",
        "negative_keywords",
    ]:
        raw_dir = exports_dir / data_type / "raw"
        if raw_dir.exists():
            files = list(raw_dir.glob("*.csv"))
            if files:
                click.echo(f"\n{data_type.upper()}:")
                for f in files:
                    click.echo(f"  - {f.name}")


@cli.command()
def test_sample():
    """Test processing with sample data."""
    processor = TestDataProcessor()
    sample_dir = processor.base_dir / "sample_data"

    click.echo("Processing sample files...")

    # Process sample keywords
    keywords_file = sample_dir / "sample_keywords.csv"
    if keywords_file.exists():
        result = processor.process_keywords_file(keywords_file)
        click.echo(f"Keywords: {result}")

    # Process sample search terms
    search_terms_file = sample_dir / "sample_search_terms.csv"
    if search_terms_file.exists():
        result = processor.process_search_terms_file(search_terms_file)
        click.echo(f"Search Terms: {result}")


if __name__ == "__main__":
    cli()
