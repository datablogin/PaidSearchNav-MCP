"""CSV-based data provider implementation."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from paidsearchnav_mcp.core.exceptions import DataError
from paidsearchnav_mcp.data_providers.base import DataProvider
from paidsearchnav_mcp.parsers.csv_parser import CSVParser
from paidsearchnav_mcp.security.rate_limiting import validate_multiple_id_lists

if TYPE_CHECKING:
    from paidsearchnav_mcp.models.campaign import Campaign
    from paidsearchnav_mcp.models.keyword import Keyword
    from paidsearchnav_mcp.models.search_term import SearchTerm

logger = logging.getLogger(__name__)


class CSVDataProvider(DataProvider):
    """Data provider implementation for CSV file-based data.

    This provider loads data from CSV files exported from Google Ads,
    providing an alternative to API-based data access. Useful for:
    - Testing with real data exports
    - Working offline
    - Processing historical exports
    - Avoiding API rate limits
    """

    def __init__(self, data_directory: Path | str | None = None):
        """Initialize the CSV data provider.

        Args:
            data_directory: Base directory containing CSV files.
                           If not provided, uses current working directory.
        """
        self.data_directory = Path(data_directory) if data_directory else Path.cwd()
        self._parser_cache: dict[str, CSVParser] = {}

    def _get_parser(self, file_type: str) -> CSVParser:
        """Get or create a parser for the specified file type."""
        if file_type not in self._parser_cache:
            self._parser_cache[file_type] = CSVParser(
                file_type=file_type,
                encoding="utf-8",
                preserve_unmapped=True,  # Be lenient with CSV data
            )
        return self._parser_cache[file_type]

    def _find_csv_file(self, pattern: str) -> Path | None:
        """Find a CSV file matching the pattern in the data directory."""
        # Validate pattern doesn't contain path traversal sequences
        if ".." in pattern or "/" in pattern or "\\" in pattern:
            raise ValueError(
                f"Invalid file pattern: {pattern}. Pattern cannot contain path traversal sequences."
            )

        # Try exact match first
        exact_path = self.data_directory / f"{pattern}.csv"
        if exact_path.exists():
            # Ensure the resolved path is within data_directory
            try:
                exact_path.resolve().relative_to(self.data_directory.resolve())
                return exact_path
            except ValueError:
                logger.warning(
                    f"File path {exact_path} is outside data directory {self.data_directory}"
                )
                return None

        # Try pattern matching
        for file_path in self.data_directory.glob(f"*{pattern}*.csv"):
            # Ensure each found path is within data_directory
            try:
                file_path.resolve().relative_to(self.data_directory.resolve())
                return file_path
            except ValueError:
                logger.warning(
                    f"File path {file_path} is outside data directory {self.data_directory}"
                )
                continue

        return None

    async def get_search_terms(
        self,
        customer_id: str,
        start_date: datetime,
        end_date: datetime,
        campaigns: list[str] | None = None,
        ad_groups: list[str] | None = None,
        page_size: int | None = None,
        max_results: int | None = None,
    ) -> list[SearchTerm]:
        """Load search terms from CSV file."""
        # Validate ID list sizes to prevent DoS
        validated = validate_multiple_id_lists(campaigns=campaigns, ad_groups=ad_groups)
        campaigns = validated["campaigns"]
        ad_groups = validated["ad_groups"]
        file_path = self._find_csv_file("search_terms")
        if not file_path:
            logger.warning(f"No search terms CSV file found in {self.data_directory}")
            return []

        try:
            parser = self._get_parser("search_terms")
            all_terms = parser.parse(file_path)

            # Filter by date range
            filtered_terms = [
                term
                for term in all_terms
                if term.date_start
                and start_date.date() <= term.date_start <= end_date.date()
            ]

            # Filter by campaigns if specified
            if campaigns:
                campaign_set = set(campaigns)
                filtered_terms = [
                    term
                    for term in filtered_terms
                    if term.campaign_name in campaign_set
                ]

            # Filter by ad groups if specified
            if ad_groups:
                ad_group_set = set(ad_groups)
                filtered_terms = [
                    term
                    for term in filtered_terms
                    if term.ad_group_name in ad_group_set
                ]

            logger.info(f"Loaded {len(filtered_terms)} search terms from {file_path}")
            return filtered_terms

        except (FileNotFoundError, PermissionError, OSError) as e:
            raise DataError(f"Failed to access CSV file: {str(e)}")
        except ValueError as e:
            raise DataError(f"Failed to parse search terms CSV: {str(e)}")
        except Exception as e:
            raise DataError(
                f"Unexpected error loading search terms from CSV: {str(e)}"
            ) from e

    async def get_keywords(
        self,
        customer_id: str,
        campaigns: list[str] | None = None,
        ad_groups: list[str] | None = None,
        campaign_id: str | None = None,
        include_metrics: bool = True,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        page_size: int | None = None,
        max_results: int | None = None,
    ) -> list[Keyword]:
        """Load keywords from CSV file."""
        # Validate ID list sizes to prevent DoS
        validated = validate_multiple_id_lists(campaigns=campaigns, ad_groups=ad_groups)
        campaigns = validated["campaigns"]
        ad_groups = validated["ad_groups"]
        file_path = self._find_csv_file("keywords")
        if not file_path:
            logger.warning(f"No keywords CSV file found in {self.data_directory}")
            return []

        try:
            parser = self._get_parser("keywords")
            all_keywords = parser.parse(file_path)

            # Filter by campaigns if specified
            if campaigns:
                campaign_set = set(campaigns)
                all_keywords = [
                    kw for kw in all_keywords if kw.campaign_name in campaign_set
                ]

            # Filter by ad groups if specified
            if ad_groups:
                ad_group_set = set(ad_groups)
                all_keywords = [
                    kw for kw in all_keywords if kw.ad_group_name in ad_group_set
                ]

            # Filter by campaign_id if specified
            if campaign_id:
                all_keywords = [
                    kw for kw in all_keywords if kw.campaign_id == campaign_id
                ]

            logger.info(f"Loaded {len(all_keywords)} keywords from {file_path}")
            return all_keywords

        except (FileNotFoundError, PermissionError, OSError) as e:
            raise DataError(f"Failed to access CSV file: {str(e)}")
        except ValueError as e:
            raise DataError(f"Failed to parse keywords CSV: {str(e)}")
        except Exception as e:
            raise DataError(
                f"Unexpected error loading keywords from CSV: {str(e)}"
            ) from e

    async def get_negative_keywords(
        self,
        customer_id: str,
        include_shared_sets: bool = True,
        page_size: int | None = None,
        max_results: int | None = None,
    ) -> list[dict[str, Any]]:
        """Load negative keywords from CSV file."""
        file_path = self._find_csv_file("negative_keywords")
        if not file_path:
            logger.warning(
                f"No negative keywords CSV file found in {self.data_directory}"
            )
            return []

        try:
            parser = self._get_parser("negative_keywords")
            negatives = parser.parse(file_path)

            # Convert to expected dictionary format
            result = []
            for neg in negatives:
                result.append(
                    {
                        "text": getattr(neg, "text", getattr(neg, "keyword", "")),
                        "match_type": getattr(neg, "match_type", "EXACT"),
                        "level": getattr(neg, "level", "CAMPAIGN"),
                        "campaign_name": getattr(neg, "campaign_name", ""),
                        "ad_group_name": getattr(neg, "ad_group_name", ""),
                        "shared_set_name": getattr(neg, "shared_set_name", ""),
                    }
                )

            # Filter out shared set negatives if not requested
            if not include_shared_sets:
                result = [neg for neg in result if not neg.get("shared_set_name")]

            logger.info(f"Loaded {len(result)} negative keywords from {file_path}")
            return result

        except (FileNotFoundError, PermissionError, OSError) as e:
            raise DataError(f"Failed to access CSV file: {str(e)}")
        except ValueError as e:
            raise DataError(f"Failed to parse negative keywords CSV: {str(e)}")
        except Exception as e:
            raise DataError(
                f"Unexpected error loading negative keywords from CSV: {str(e)}"
            ) from e

    async def get_campaigns(
        self,
        customer_id: str,
        campaign_types: list[str] | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        page_size: int | None = None,
        max_results: int | None = None,
    ) -> list[Campaign]:
        """Load campaigns from CSV file."""
        file_path = self._find_csv_file("campaigns")
        if not file_path:
            logger.warning(f"No campaigns CSV file found in {self.data_directory}")
            return []

        try:
            parser = self._get_parser("campaigns")
            all_campaigns = parser.parse(file_path)

            # Filter by campaign types if specified
            if campaign_types:
                type_set = set(campaign_types)
                all_campaigns = [
                    camp
                    for camp in all_campaigns
                    if getattr(camp, "campaign_type", "SEARCH") in type_set
                ]

            logger.info(f"Loaded {len(all_campaigns)} campaigns from {file_path}")
            return all_campaigns

        except (FileNotFoundError, PermissionError, OSError) as e:
            raise DataError(f"Failed to access CSV file: {str(e)}")
        except ValueError as e:
            raise DataError(f"Failed to parse campaigns CSV: {str(e)}")
        except Exception as e:
            raise DataError(
                f"Unexpected error loading campaigns from CSV: {str(e)}"
            ) from e

    async def get_shared_negative_lists(
        self,
        customer_id: str,
    ) -> list[dict[str, Any]]:
        """Load shared negative keyword lists from CSV file."""
        file_path = self._find_csv_file("shared_negative_lists")
        if not file_path:
            logger.warning(
                f"No shared negative lists CSV file found in {self.data_directory}"
            )
            return []

        try:
            # Use generic CSV parser for shared lists
            parser = self._get_parser("generic")
            data = parser.parse(file_path)

            # Convert to expected format
            result = []
            for item in data:
                result.append(
                    {
                        "id": getattr(item, "id", ""),
                        "name": getattr(item, "name", ""),
                        "negative_count": getattr(item, "negative_count", 0),
                    }
                )

            logger.info(f"Loaded {len(result)} shared negative lists from {file_path}")
            return result

        except (FileNotFoundError, PermissionError, OSError) as e:
            raise DataError(f"Failed to access CSV file: {str(e)}")
        except ValueError as e:
            raise DataError(f"Failed to parse shared negative lists CSV: {str(e)}")
        except Exception as e:
            raise DataError(
                f"Unexpected error loading shared negative lists from CSV: {str(e)}"
            ) from e

    async def get_campaign_shared_sets(
        self,
        customer_id: str,
        campaign_id: str,
    ) -> list[dict[str, Any]]:
        """Get shared sets applied to a specific campaign from CSV."""
        # This would typically require a mapping file or be included in campaign data
        raise NotImplementedError(
            "Campaign shared sets mapping not implemented for CSV provider. "
            "This requires specialized CSV structure or additional mapping files."
        )

    async def get_shared_set_negatives(
        self,
        customer_id: str,
        shared_set_id: str,
    ) -> list[dict[str, Any]]:
        """Get negative keywords from a specific shared set from CSV."""
        file_path = self._find_csv_file("shared_set_negatives")
        if not file_path:
            # Try the general negative keywords file
            return await self.get_negative_keywords(
                customer_id, include_shared_sets=True
            )

        try:
            parser = self._get_parser("generic")
            data = parser.parse(file_path)

            # Filter by shared set ID
            result = []
            for item in data:
                if getattr(item, "shared_set_id", "") == shared_set_id:
                    result.append(
                        {
                            "text": getattr(item, "text", getattr(item, "keyword", "")),
                        }
                    )

            logger.info(
                f"Loaded {len(result)} negatives for shared set {shared_set_id}"
            )
            return result

        except (FileNotFoundError, PermissionError, OSError) as e:
            raise DataError(f"Failed to access CSV file: {str(e)}")
        except ValueError as e:
            raise DataError(f"Failed to parse shared set negatives CSV: {str(e)}")
        except Exception as e:
            raise DataError(
                f"Unexpected error loading shared set negatives from CSV: {str(e)}"
            ) from e

    async def get_placement_data(
        self,
        customer_id: str,
        start_date: datetime,
        end_date: datetime,
        campaigns: list[str] | None = None,
        ad_groups: list[str] | None = None,
        page_size: int | None = None,
        max_results: int | None = None,
    ) -> list[dict[str, Any]]:
        """Load placement data from CSV file."""
        file_path = self._find_csv_file("placements")
        if not file_path:
            logger.warning(f"No placements CSV file found in {self.data_directory}")
            return []

        try:
            parser = self._get_parser("placements")
            data = parser.parse(file_path)

            # Convert to expected format
            result = []
            for item in data:
                placement = {
                    "placement_id": getattr(item, "placement_id", ""),
                    "placement_name": getattr(
                        item, "placement_name", getattr(item, "domain", "")
                    ),
                    "display_name": getattr(
                        item, "display_name", getattr(item, "placement_name", "")
                    ),
                    "impressions": getattr(item, "impressions", 0),
                    "clicks": getattr(item, "clicks", 0),
                    "cost": getattr(item, "cost", 0.0),
                    "conversions": getattr(item, "conversions", 0.0),
                    "conversion_value": getattr(item, "conversion_value", 0.0),
                    "ctr": getattr(item, "ctr", 0.0),
                    "cpc": getattr(item, "cpc", 0.0),
                    "cpa": getattr(item, "cpa", 0.0),
                    "roas": getattr(item, "roas", 0.0),
                    "campaign_ids": [getattr(item, "campaign_id", "")]
                    if hasattr(item, "campaign_id")
                    else [],
                    "ad_group_ids": [getattr(item, "ad_group_id", "")]
                    if hasattr(item, "ad_group_id")
                    else [],
                }

                # Filter by campaigns if specified
                if campaigns and placement["campaign_ids"]:
                    if not any(cid in campaigns for cid in placement["campaign_ids"]):
                        continue

                # Filter by ad groups if specified
                if ad_groups and placement["ad_group_ids"]:
                    if not any(aid in ad_groups for aid in placement["ad_group_ids"]):
                        continue

                result.append(placement)

            logger.info(f"Loaded {len(result)} placements from {file_path}")
            return result

        except (FileNotFoundError, PermissionError, OSError) as e:
            raise DataError(f"Failed to access CSV file: {str(e)}")
        except ValueError as e:
            raise DataError(f"Failed to parse placement data CSV: {str(e)}")
        except Exception as e:
            raise DataError(
                f"Unexpected error loading placement data from CSV: {str(e)}"
            ) from e

    def load_search_terms(self, file_path: str | Path) -> list[SearchTerm]:
        """Load search terms from a specific CSV file.

        This is a convenience method for direct file loading.
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise DataError(f"File not found: {file_path}")

        try:
            parser = self._get_parser("search_terms")
            return parser.parse(file_path)
        except (FileNotFoundError, PermissionError, OSError) as e:
            raise DataError(f"Failed to access CSV file: {str(e)}")
        except ValueError as e:
            raise DataError(f"Failed to parse search terms CSV: {str(e)}")
        except Exception as e:
            raise DataError(
                f"Unexpected error loading search terms from {file_path}: {str(e)}"
            ) from e
