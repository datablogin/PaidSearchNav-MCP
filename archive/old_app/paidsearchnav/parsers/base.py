"""Base parser interface for all data parsers in PaidSearchNav."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List


class BaseParser(ABC):
    """Abstract base class for all parsers.

    This class defines the interface that all parsers must implement
    to ensure consistent behavior across different data formats.
    """

    @abstractmethod
    def parse(self, file_path: Path) -> List[Dict[str, Any]]:
        """Parse the file and return a list of dictionaries.

        Args:
            file_path: Path to the file to parse.

        Returns:
            List of dictionaries containing the parsed data.

        Raises:
            FileNotFoundError: If the file doesn't exist.
            ValueError: If the file format is invalid.
        """
        pass

    @abstractmethod
    def validate(self, data: List[Dict[str, Any]]) -> bool:
        """Validate the parsed data.

        Args:
            data: List of dictionaries containing parsed data.

        Returns:
            True if data is valid, False otherwise.
        """
        pass
