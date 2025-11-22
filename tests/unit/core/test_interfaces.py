"""Tests for core interfaces module."""

from __future__ import annotations

from abc import ABC
from datetime import datetime
from typing import Any

import pytest

from paidsearchnav.core.interfaces import (
    Analyzer,
    DataProvider,
    Exporter,
    ReportGenerator,
    Storage,
)
from paidsearchnav.core.models.analysis import AnalysisResult
from paidsearchnav.core.models.campaign import Campaign
from paidsearchnav.core.models.keyword import Keyword
from paidsearchnav.core.models.search_term import SearchTerm


class TestDataProvider:
    """Test DataProvider interface."""

    def test_abstract_base_class(self) -> None:
        """Test that DataProvider is an abstract base class."""
        assert issubclass(DataProvider, ABC)
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            DataProvider()  # type: ignore[abstract]

    def test_abstract_methods(self) -> None:
        """Test that all required abstract methods are defined."""
        abstract_methods = {
            "get_search_terms",
            "get_keywords",
            "get_negative_keywords",
            "get_campaigns",
            "get_shared_negative_lists",
            "get_campaign_shared_sets",
            "get_shared_set_negatives",
            "get_placement_data",
        }
        assert DataProvider.__abstractmethods__ == frozenset(abstract_methods)

    def test_method_signatures(self) -> None:
        """Test that abstract methods have correct signatures."""
        # get_search_terms
        method = DataProvider.get_search_terms
        annotations = method.__annotations__
        assert annotations["customer_id"] == "str"
        assert annotations["start_date"] == "datetime"
        assert annotations["end_date"] == "datetime"
        assert annotations["campaigns"] == "list[str] | None"
        assert annotations["ad_groups"] == "list[str] | None"
        assert annotations["return"] == "list[SearchTerm]"

        # get_keywords
        method = DataProvider.get_keywords
        annotations = method.__annotations__
        assert annotations["customer_id"] == "str"
        assert annotations["campaigns"] == "list[str] | None"
        assert annotations["ad_groups"] == "list[str] | None"
        assert annotations["campaign_id"] == "str | None"
        assert annotations["return"] == "list[Keyword]"

        # get_negative_keywords
        method = DataProvider.get_negative_keywords
        annotations = method.__annotations__
        assert annotations["customer_id"] == "str"
        assert annotations["include_shared_sets"] == "bool"
        assert annotations["return"] == "list[dict[str, Any]]"

        # get_campaigns
        method = DataProvider.get_campaigns
        annotations = method.__annotations__
        assert annotations["customer_id"] == "str"
        assert annotations["campaign_types"] == "list[str] | None"
        assert annotations["start_date"] == "datetime | None"
        assert annotations["end_date"] == "datetime | None"
        assert annotations["return"] == "list[Campaign]"

    def test_implementation(self) -> None:
        """Test that interface can be properly implemented."""

        class ConcreteProvider(DataProvider):
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
                return []

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
                return []

            async def get_negative_keywords(
                self,
                customer_id: str,
                include_shared_sets: bool = True,
                page_size: int | None = None,
                max_results: int | None = None,
            ) -> list[dict[str, Any]]:
                return []

            async def get_campaigns(
                self,
                customer_id: str,
                campaign_types: list[str] | None = None,
                start_date: datetime | None = None,
                end_date: datetime | None = None,
                page_size: int | None = None,
                max_results: int | None = None,
            ) -> list[Campaign]:
                return []

            async def get_shared_negative_lists(
                self,
                customer_id: str,
            ) -> list[dict[str, Any]]:
                return []

            async def get_campaign_shared_sets(
                self,
                customer_id: str,
                campaign_id: str,
            ) -> list[dict[str, Any]]:
                return []

            async def get_shared_set_negatives(
                self,
                customer_id: str,
                shared_set_id: str,
            ) -> list[dict[str, Any]]:
                return []

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
                return []

        # Should be able to instantiate
        provider = ConcreteProvider()
        assert isinstance(provider, DataProvider)


class TestAnalyzer:
    """Test Analyzer interface."""

    def test_abstract_base_class(self) -> None:
        """Test that Analyzer is an abstract base class."""
        assert issubclass(Analyzer, ABC)
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            Analyzer()  # type: ignore[abstract]

    def test_abstract_methods(self) -> None:
        """Test that all required abstract methods are defined."""
        abstract_methods = {"analyze", "get_name", "get_description"}
        assert Analyzer.__abstractmethods__ == frozenset(abstract_methods)

    def test_method_signatures(self) -> None:
        """Test that abstract methods have correct signatures."""
        # analyze
        method = Analyzer.analyze
        annotations = method.__annotations__
        assert annotations["customer_id"] == "str"
        assert annotations["start_date"] == "datetime"
        assert annotations["end_date"] == "datetime"
        assert annotations["kwargs"] == "Any"
        assert annotations["return"] == "AnalysisResult"

        # get_name
        method = Analyzer.get_name
        annotations = method.__annotations__
        assert annotations["return"] == "str"

        # get_description
        method = Analyzer.get_description
        annotations = method.__annotations__
        assert annotations["return"] == "str"

    def test_implementation(self) -> None:
        """Test that interface can be properly implemented."""

        class ConcreteAnalyzer(Analyzer):
            async def analyze(
                self,
                customer_id: str,
                start_date: datetime,
                end_date: datetime,
                **kwargs: Any,
            ) -> AnalysisResult:
                return AnalysisResult(
                    analyzer_name="test",
                    analysis_type="test_analysis",
                    customer_id=customer_id,
                    start_date=start_date,
                    end_date=end_date,
                    data={},
                    metadata={},
                )

            def get_name(self) -> str:
                return "Test Analyzer"

            def get_description(self) -> str:
                return "A test analyzer"

        # Should be able to instantiate
        analyzer = ConcreteAnalyzer()
        assert isinstance(analyzer, Analyzer)
        assert analyzer.get_name() == "Test Analyzer"
        assert analyzer.get_description() == "A test analyzer"


class TestReportGenerator:
    """Test ReportGenerator interface."""

    def test_abstract_base_class(self) -> None:
        """Test that ReportGenerator is an abstract base class."""
        assert issubclass(ReportGenerator, ABC)
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            ReportGenerator()  # type: ignore[abstract]

    def test_abstract_methods(self) -> None:
        """Test that all required abstract methods are defined."""
        abstract_methods = {"generate", "get_supported_formats"}
        assert ReportGenerator.__abstractmethods__ == frozenset(abstract_methods)

    def test_method_signatures(self) -> None:
        """Test that abstract methods have correct signatures."""
        # generate
        method = ReportGenerator.generate
        annotations = method.__annotations__
        assert annotations["analysis_results"] == "list[AnalysisResult]"
        assert annotations["format"] == "str"
        assert annotations["kwargs"] == "Any"
        assert annotations["return"] == "bytes"

        # get_supported_formats
        method = ReportGenerator.get_supported_formats
        annotations = method.__annotations__
        assert annotations["return"] == "list[str]"

    def test_implementation(self) -> None:
        """Test that interface can be properly implemented."""

        class ConcreteReportGenerator(ReportGenerator):
            def generate(
                self,
                analysis_results: list[AnalysisResult],
                format: str = "html",
                **kwargs: Any,
            ) -> bytes:
                return b"<html>Report</html>"

            def get_supported_formats(self) -> list[str]:
                return ["html", "pdf", "csv"]

        # Should be able to instantiate
        generator = ConcreteReportGenerator()
        assert isinstance(generator, ReportGenerator)
        assert generator.get_supported_formats() == ["html", "pdf", "csv"]
        assert generator.generate([]) == b"<html>Report</html>"


class TestStorage:
    """Test Storage interface."""

    def test_abstract_base_class(self) -> None:
        """Test that Storage is an abstract base class."""
        assert issubclass(Storage, ABC)
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            Storage()  # type: ignore[abstract]

    def test_abstract_methods(self) -> None:
        """Test that all required abstract methods are defined."""
        abstract_methods = {
            "save_analysis",
            "get_analysis",
            "list_analyses",
            "delete_analysis",
        }
        assert Storage.__abstractmethods__ == frozenset(abstract_methods)

    def test_method_signatures(self) -> None:
        """Test that abstract methods have correct signatures."""
        # save_analysis
        method = Storage.save_analysis
        annotations = method.__annotations__
        assert annotations["result"] == "AnalysisResult"
        assert annotations["return"] == "str"

        # get_analysis
        method = Storage.get_analysis
        annotations = method.__annotations__
        assert annotations["analysis_id"] == "str"
        assert annotations["return"] == "AnalysisResult | None"

        # list_analyses
        method = Storage.list_analyses
        annotations = method.__annotations__
        assert annotations["customer_id"] == "str | None"
        assert annotations["analysis_type"] == "str | None"
        assert annotations["start_date"] == "datetime | None"
        assert annotations["end_date"] == "datetime | None"
        assert annotations["limit"] == "int"
        assert annotations["return"] == "list[AnalysisResult]"

        # delete_analysis
        method = Storage.delete_analysis
        annotations = method.__annotations__
        assert annotations["analysis_id"] == "str"
        assert annotations["return"] == "bool"

    def test_implementation(self) -> None:
        """Test that interface can be properly implemented."""

        class ConcreteStorage(Storage):
            def __init__(self) -> None:
                self._storage: dict[str, AnalysisResult] = {}

            async def save_analysis(self, result: AnalysisResult) -> str:
                analysis_id = f"analysis_{len(self._storage)}"
                self._storage[analysis_id] = result
                return analysis_id

            async def get_analysis(self, analysis_id: str) -> AnalysisResult | None:
                return self._storage.get(analysis_id)

            async def list_analyses(
                self,
                customer_id: str | None = None,
                analysis_type: str | None = None,
                start_date: datetime | None = None,
                end_date: datetime | None = None,
                limit: int = 100,
            ) -> list[AnalysisResult]:
                results = list(self._storage.values())
                if customer_id:
                    results = [r for r in results if r.customer_id == customer_id]
                return results[:limit]

            async def delete_analysis(self, analysis_id: str) -> bool:
                if analysis_id in self._storage:
                    del self._storage[analysis_id]
                    return True
                return False

        # Should be able to instantiate
        storage = ConcreteStorage()
        assert isinstance(storage, Storage)


class TestExporter:
    """Test Exporter interface."""

    def test_abstract_base_class(self) -> None:
        """Test that Exporter is an abstract base class."""
        assert issubclass(Exporter, ABC)
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            Exporter()  # type: ignore[abstract]

    def test_abstract_methods(self) -> None:
        """Test that all required abstract methods are defined."""
        abstract_methods = {"export", "get_supported_formats"}
        assert Exporter.__abstractmethods__ == frozenset(abstract_methods)

    def test_method_signatures(self) -> None:
        """Test that abstract methods have correct signatures."""
        # export
        method = Exporter.export
        annotations = method.__annotations__
        assert annotations["data"] == "Any"
        assert annotations["filename"] == "str"
        assert annotations["format"] == "str"
        assert annotations["kwargs"] == "Any"
        assert annotations["return"] == "bytes"

        # get_supported_formats
        method = Exporter.get_supported_formats
        annotations = method.__annotations__
        assert annotations["return"] == "list[str]"

    def test_implementation(self) -> None:
        """Test that interface can be properly implemented."""

        class ConcreteExporter(Exporter):
            def export(
                self,
                data: Any,
                filename: str,
                format: str = "csv",
                **kwargs: Any,
            ) -> bytes:
                return b"exported_data"

            def get_supported_formats(self) -> list[str]:
                return ["csv", "json", "xlsx"]

        # Should be able to instantiate
        exporter = ConcreteExporter()
        assert isinstance(exporter, Exporter)
        assert exporter.get_supported_formats() == ["csv", "json", "xlsx"]
        assert exporter.export({}, "test.csv") == b"exported_data"


class TestInterfaceInheritance:
    """Test interface inheritance patterns."""

    def test_multiple_inheritance(self) -> None:
        """Test that classes can implement multiple interfaces."""

        class MultiImplementation(DataProvider, Analyzer):
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
                return []

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
                return []

            async def get_negative_keywords(
                self,
                customer_id: str,
                include_shared_sets: bool = True,
                page_size: int | None = None,
                max_results: int | None = None,
            ) -> list[dict[str, Any]]:
                return []

            async def get_campaigns(
                self,
                customer_id: str,
                campaign_types: list[str] | None = None,
                start_date: datetime | None = None,
                end_date: datetime | None = None,
                page_size: int | None = None,
                max_results: int | None = None,
            ) -> list[Campaign]:
                return []

            async def get_shared_negative_lists(
                self,
                customer_id: str,
            ) -> list[dict[str, Any]]:
                return []

            async def get_campaign_shared_sets(
                self,
                customer_id: str,
                campaign_id: str,
            ) -> list[dict[str, Any]]:
                return []

            async def get_shared_set_negatives(
                self,
                customer_id: str,
                shared_set_id: str,
            ) -> list[dict[str, Any]]:
                return []

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
                return []

            async def analyze(
                self,
                customer_id: str,
                start_date: datetime,
                end_date: datetime,
                **kwargs: Any,
            ) -> AnalysisResult:
                return AnalysisResult(
                    analyzer_name="multi",
                    analysis_type="multi_analysis",
                    customer_id=customer_id,
                    start_date=start_date,
                    end_date=end_date,
                    data={},
                    metadata={},
                )

            def get_name(self) -> str:
                return "Multi Implementation"

            def get_description(self) -> str:
                return "Implements multiple interfaces"

        # Should be able to instantiate
        multi = MultiImplementation()
        assert isinstance(multi, DataProvider)
        assert isinstance(multi, Analyzer)

    def test_interface_type_checking(self) -> None:
        """Test that interfaces can be used for type checking."""

        def process_analyzer(analyzer: Analyzer) -> str:
            return analyzer.get_name()

        class TestAnalyzer(Analyzer):
            async def analyze(
                self,
                customer_id: str,
                start_date: datetime,
                end_date: datetime,
                **kwargs: Any,
            ) -> AnalysisResult:
                return AnalysisResult(
                    analyzer_name="test",
                    analysis_type="test",
                    customer_id=customer_id,
                    start_date=start_date,
                    end_date=end_date,
                    data={},
                    metadata={},
                )

            def get_name(self) -> str:
                return "Test"

            def get_description(self) -> str:
                return "Test analyzer"

        analyzer = TestAnalyzer()
        # Should work with type checking
        result = process_analyzer(analyzer)
        assert result == "Test"
