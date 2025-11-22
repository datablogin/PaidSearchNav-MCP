"""Base interfaces for all analyzers and components."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import TYPE_CHECKING, Any

# Import DataProvider from its new location
from paidsearchnav.data_providers.base import DataProvider

if TYPE_CHECKING:
    from paidsearchnav.core.models.analysis import AnalysisResult

# Re-export DataProvider for backward compatibility
__all__ = ["DataProvider", "Analyzer", "ReportGenerator", "Storage", "Exporter"]


class Analyzer(ABC):
    """Base interface for all audit analyzers."""

    @abstractmethod
    async def analyze(
        self,
        customer_id: str,
        start_date: datetime,
        end_date: datetime,
        **kwargs: Any,
    ) -> AnalysisResult:
        """Run the analysis and return results."""
        pass

    @abstractmethod
    def get_name(self) -> str:
        """Get analyzer name."""
        pass

    @abstractmethod
    def get_description(self) -> str:
        """Get analyzer description."""
        pass


class ReportGenerator(ABC):
    """Interface for report generators."""

    @abstractmethod
    def generate(
        self,
        analysis_results: list[AnalysisResult],
        format: str = "html",
        **kwargs: Any,
    ) -> bytes:
        """Generate a report from analysis results."""
        pass

    @abstractmethod
    def get_supported_formats(self) -> list[str]:
        """Get list of supported output formats."""
        pass


class Storage(ABC):
    """Interface for data persistence."""

    @abstractmethod
    async def save_analysis(self, result: AnalysisResult) -> str:
        """Save analysis results and return ID."""
        pass

    @abstractmethod
    async def get_analysis(self, analysis_id: str) -> AnalysisResult | None:
        """Retrieve analysis results by ID."""
        pass

    @abstractmethod
    async def list_analyses(
        self,
        customer_id: str | None = None,
        analysis_type: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 100,
    ) -> list[AnalysisResult]:
        """List analyses with optional filters."""
        pass

    @abstractmethod
    async def delete_analysis(self, analysis_id: str) -> bool:
        """Delete analysis results."""
        pass


class Exporter(ABC):
    """Interface for data exporters."""

    @abstractmethod
    def export(
        self,
        data: Any,
        filename: str,
        format: str = "csv",
        **kwargs: Any,
    ) -> bytes:
        """Export data to specified format."""
        pass

    @abstractmethod
    def get_supported_formats(self) -> list[str]:
        """Get list of supported export formats."""
        pass
