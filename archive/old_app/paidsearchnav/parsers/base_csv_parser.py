"""Abstract base class for CSV parsers with generic typing support."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Generic, List, Optional, TypeVar

T = TypeVar("T", bound=Dict[str, str])


@dataclass
class ColumnMapping:
    """Maps CSV column names to model field names."""

    # Required fields
    campaign: str
    ad_group: str

    # Keyword-specific fields
    keyword: Optional[str] = None
    match_type: Optional[str] = None

    # Search term fields
    search_term: Optional[str] = None

    # Performance metrics
    impressions: Optional[str] = None
    clicks: Optional[str] = None
    cost: Optional[str] = None
    conversions: Optional[str] = None

    # Geo fields
    location: Optional[str] = None
    location_type: Optional[str] = None

    def get_mapping_dict(self) -> Dict[str, str]:
        """Return a dictionary of non-None mappings."""
        return {k: v for k, v in self.__dict__.items() if v is not None}


class CSVParsingError(Exception):
    """Raised when CSV parsing fails."""

    def __init__(
        self,
        message: str,
        row_number: Optional[int] = None,
        column: Optional[str] = None,
        value: Optional[str] = None,
    ):
        self.row_number = row_number
        self.column = column
        self.value = value

        detail_parts = []
        if row_number is not None:
            detail_parts.append(f"row {row_number}")
        if column:
            detail_parts.append(f"column '{column}'")
        if value:
            detail_parts.append(f"value '{value}'")

        if detail_parts:
            super().__init__(f"{message} (at {', '.join(detail_parts)})")
        else:
            super().__init__(message)


class BaseCSVParser(ABC, Generic[T]):
    """Abstract base class for CSV parsers with generic typing.

    This class provides a generic interface for CSV parsers that can
    work with different row types while ensuring type safety.

    Type Parameters:
        T: The type of dictionary that represents a parsed row.
           Must be a subtype of Dict[str, str].
    """

    @abstractmethod
    def parse(self, file_path: Path) -> List[T]:
        """Parse a CSV file and return typed rows.

        Args:
            file_path: Path to the CSV file to parse.

        Returns:
            List of dictionaries of type T containing the parsed data.

        Raises:
            FileNotFoundError: If the file doesn't exist.
            ValueError: If the CSV format is invalid.
        """
        pass

    @abstractmethod
    def validate_headers(self, headers: List[str]) -> bool:
        """Validate that the CSV headers are correct for this parser.

        Args:
            headers: List of header strings from the CSV file.

        Returns:
            True if headers are valid for this parser, False otherwise.
        """
        pass
