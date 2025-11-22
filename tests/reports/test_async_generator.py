"""Tests for async report generator."""

import asyncio
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from paidsearchnav_mcp.models import (
    AnalysisMetrics,
    AnalysisResult,
    Recommendation,
    RecommendationPriority,
    RecommendationType,
)
from paidsearchnav_mcp.reports.async_generator import AsyncReportGenerator


@pytest.fixture
def sample_analysis_results():
    """Create sample analysis results for testing."""
    return [
        AnalysisResult(
            analyzer_name="Test Analyzer 1",
            analysis_type="test_analysis",
            customer_id="test-customer-123",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
            metrics=AnalysisMetrics(
                total_keywords_analyzed=100,
                issues_found=2,
                critical_issues=1,
                potential_cost_savings=800.0,
            ),
            recommendations=[
                Recommendation(
                    type=RecommendationType.ADD_NEGATIVE_KEYWORDS,
                    priority=RecommendationPriority.CRITICAL,
                    title="Block irrelevant searches",
                    description="Add negative keywords to prevent wasted spend",
                    estimated_impact="High reduction in wasted spend",
                    estimated_cost_savings=500.0,
                ),
                Recommendation(
                    type=RecommendationType.OPTIMIZE_KEYWORDS,
                    priority=RecommendationPriority.HIGH,
                    title="Optimize match types",
                    description="Change broad match keywords to phrase match",
                    estimated_impact="Better targeting",
                    estimated_cost_savings=300.0,
                ),
            ],
        ),
        AnalysisResult(
            analyzer_name="Test Analyzer 2",
            analysis_type="test_analysis_2",
            customer_id="test-customer-123",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
            metrics=AnalysisMetrics(
                total_keywords_analyzed=50,
                issues_found=1,
                potential_cost_savings=200.0,
            ),
            recommendations=[
                Recommendation(
                    type=RecommendationType.OPTIMIZE_BIDDING,
                    priority=RecommendationPriority.MEDIUM,
                    title="Adjust bids",
                    description="Lower bids on underperforming keywords",
                    estimated_impact="Cost reduction",
                    estimated_cost_savings=200.0,
                ),
            ],
        ),
    ]


@pytest.fixture
def template_dir(tmp_path):
    """Create a temporary template directory with test template."""
    template_path = tmp_path / "templates"
    template_path.mkdir()

    # Create a simple test template
    template_content = """
    <!DOCTYPE html>
    <html>
    <head><title>Test Report</title></head>
    <body>
        <h1>{{ company_name }} Report</h1>
        <p>{{ executive_summary }}</p>
        <p>Total Recommendations: {{ total_recommendations }}</p>
        <p>Critical Issues: {{ critical_issues }}</p>
        <p>Total Savings: ${{ "%.2f"|format(total_savings) }}</p>
    </body>
    </html>
    """

    (template_path / "audit_report.html").write_text(template_content.strip())
    return template_path


class TestAsyncReportGenerator:
    """Test async report generator functionality."""

    @pytest.mark.asyncio
    async def test_generate_async_html(self, sample_analysis_results, template_dir):
        """Test async HTML report generation."""
        generator = AsyncReportGenerator(
            template_dir=template_dir,
            company_name="Test Company",
            max_concurrent_sections=2,
        )

        result = await generator.generate_async(sample_analysis_results, format="html")

        assert isinstance(result, bytes)
        html_content = result.decode("utf-8")
        assert "Test Company Report" in html_content
        assert "Total Recommendations: 3" in html_content
        assert "Critical Issues: 1" in html_content
        assert "Total Savings: $1000.00" in html_content

    @pytest.mark.asyncio
    async def test_generate_async_pdf(self, sample_analysis_results, template_dir):
        """Test async PDF report generation."""
        generator = AsyncReportGenerator(
            template_dir=template_dir,
            company_name="Test Company",
        )

        result = await generator.generate_async(sample_analysis_results, format="pdf")

        assert isinstance(result, bytes)
        # PDF files start with %PDF
        assert result.startswith(b"%PDF")

    @pytest.mark.asyncio
    async def test_generate_async_csv(self, sample_analysis_results, template_dir):
        """Test async CSV report generation."""
        generator = AsyncReportGenerator(template_dir=template_dir)

        result = await generator.generate_async(sample_analysis_results, format="csv")

        assert isinstance(result, bytes)
        csv_content = result.decode("utf-8")
        assert "Analyzer,Priority,Type,Title,Description" in csv_content
        assert "Test Analyzer 1" in csv_content
        assert "Block irrelevant searches" in csv_content
        assert "$500.00" in csv_content

    @pytest.mark.asyncio
    async def test_generate_async_json(self, sample_analysis_results, template_dir):
        """Test async JSON report generation."""
        generator = AsyncReportGenerator(template_dir=template_dir)

        result = await generator.generate_async(sample_analysis_results, format="json")

        assert isinstance(result, bytes)
        json_content = result.decode("utf-8")

        # Verify it's valid JSON
        import json

        data = json.loads(json_content)

        assert data["metadata"]["company_name"] == "PaidSearchNav"
        assert data["metadata"]["analyzer_count"] == 2
        assert data["summary"]["total_recommendations"] == 3
        assert data["summary"]["critical_issues"] == 1
        assert data["summary"]["total_savings"] == 1000.0

    @pytest.mark.asyncio
    async def test_generate_async_invalid_format(self, sample_analysis_results):
        """Test async generation with invalid format."""
        generator = AsyncReportGenerator()

        with pytest.raises(ValueError, match="Unsupported format"):
            await generator.generate_async(sample_analysis_results, format="invalid")

    @pytest.mark.asyncio
    async def test_generate_async_invalid_input(self):
        """Test async generation with invalid input."""
        generator = AsyncReportGenerator()

        # Test with non-list input
        with pytest.raises(ValueError, match="analysis_results must be a list"):
            await generator.generate_async("not a list", format="html")

        # Test with list containing non-AnalysisResult items
        with pytest.raises(
            ValueError, match="All items in analysis_results must be AnalysisResult"
        ):
            await generator.generate_async(
                [{"not": "an analysis result"}], format="html"
            )

    @pytest.mark.asyncio
    async def test_concurrent_processing(self, sample_analysis_results, template_dir):
        """Test concurrent processing of report sections."""
        generator = AsyncReportGenerator(
            template_dir=template_dir,
            max_concurrent_sections=2,
        )

        # Add more analysis results to test concurrency
        large_results = sample_analysis_results * 5  # 10 results total

        start_time = asyncio.get_event_loop().time()
        result = await generator.generate_async(large_results, format="json")
        end_time = asyncio.get_event_loop().time()

        assert isinstance(result, bytes)

        # Verify the semaphore limited concurrent processing
        # (Can't easily test timing, but verify result is correct)
        import json

        data = json.loads(result.decode("utf-8"))
        assert len(data["analyzer_results"]) == 10

    @pytest.mark.asyncio
    async def test_stream_report_sections(self, sample_analysis_results, template_dir):
        """Test streaming report generation."""
        generator = AsyncReportGenerator(
            template_dir=template_dir,
            company_name="Test Company",
        )

        chunks = []
        async for chunk in generator.stream_report_sections(
            sample_analysis_results,
            format="html",
            include_sections=["executive_summary", "metrics"],
        ):
            chunks.append(chunk)

        # Should have header, sections, and footer
        assert len(chunks) >= 3

        # Combine all chunks
        full_content = b"".join(chunks).decode("utf-8")

        # Verify HTML structure
        assert "<!DOCTYPE html>" in full_content
        assert "</html>" in full_content
        assert "Executive Summary" in full_content
        assert "Key Metrics" in full_content

    @pytest.mark.asyncio
    async def test_stream_report_sections_invalid_format(self, sample_analysis_results):
        """Test streaming with unsupported format."""
        generator = AsyncReportGenerator()

        with pytest.raises(
            ValueError, match="Streaming is currently only supported for HTML"
        ):
            async for _ in generator.stream_report_sections(
                sample_analysis_results, format="pdf"
            ):
                pass

    @pytest.mark.asyncio
    async def test_backward_compatibility(self, sample_analysis_results, template_dir):
        """Test that synchronous generate method still works."""
        generator = AsyncReportGenerator(
            template_dir=template_dir,
            company_name="Test Company",
        )

        # The base class generate method should still work
        result = generator.generate(sample_analysis_results, format="html")

        assert isinstance(result, bytes)
        html_content = result.decode("utf-8")
        assert "Test Company Report" in html_content

    @pytest.mark.asyncio
    async def test_prepare_report_data_async(self, sample_analysis_results):
        """Test async preparation of report data."""
        generator = AsyncReportGenerator(max_concurrent_sections=2)

        report_data = await generator._prepare_report_data_async(
            sample_analysis_results
        )

        assert report_data["total_recommendations"] == 3
        assert report_data["critical_issues"] == 1
        assert report_data["total_savings"] == 1000.0
        assert len(report_data["critical_recommendations"]) == 1
        assert len(report_data["high_recommendations"]) == 1
        assert len(report_data["medium_recommendations"]) == 1
        assert report_data["executive_summary"] != ""

    @pytest.mark.asyncio
    async def test_process_analyzer_result_async(self, sample_analysis_results):
        """Test async processing of individual analyzer results."""
        generator = AsyncReportGenerator(max_concurrent_sections=1)

        analyzer_data = await generator._process_analyzer_result_async(
            sample_analysis_results[0]
        )

        assert analyzer_data["analyzer_name"] == "Test Analyzer 1"
        assert analyzer_data["customer_id"] == "test-customer-123"
        assert "date_range" in analyzer_data
        assert "summary" in analyzer_data

    @pytest.mark.asyncio
    async def test_template_not_found(self, sample_analysis_results):
        """Test handling of missing template file."""
        generator = AsyncReportGenerator(
            template_dir=Path("/nonexistent/path"),
        )

        with pytest.raises(FileNotFoundError, match="HTML template not found"):
            await generator.generate_async(sample_analysis_results, format="html")

    @pytest.mark.asyncio
    async def test_pdf_generation_error_handling(
        self, sample_analysis_results, template_dir
    ):
        """Test error handling in PDF generation."""
        generator = AsyncReportGenerator(template_dir=template_dir)

        # Mock the PDF generation to raise an error
        with patch.object(
            generator, "_generate_pdf_content", side_effect=Exception("PDF error")
        ):
            with pytest.raises(RuntimeError, match="Failed to generate PDF report"):
                await generator.generate_async(sample_analysis_results, format="pdf")

    @pytest.mark.asyncio
    async def test_custom_sections_in_streaming(
        self, sample_analysis_results, template_dir
    ):
        """Test streaming with custom section selection."""
        generator = AsyncReportGenerator(
            template_dir=template_dir,
            company_name="Test Company",
        )

        chunks = []
        async for chunk in generator.stream_report_sections(
            sample_analysis_results,
            format="html",
            include_sections=["recommendations", "analyzer_details"],
        ):
            chunks.append(chunk)

        full_content = b"".join(chunks).decode("utf-8")

        # Should include selected sections
        assert "Recommendations" in full_content
        assert "Analyzer Details" in full_content

        # Should not include excluded sections
        assert "Executive Summary" not in full_content
        assert "Key Metrics" not in full_content

    @pytest.mark.asyncio
    async def test_concurrent_semaphore_limiting(self, sample_analysis_results):
        """Test that semaphore properly limits concurrent operations."""
        generator = AsyncReportGenerator(max_concurrent_sections=1)

        # Track concurrent executions
        concurrent_count = 0
        max_concurrent = 0

        original_method = generator._process_analysis_result_async

        async def mock_process_result(result):
            nonlocal concurrent_count, max_concurrent
            async with generator._semaphore:  # Use the generator's semaphore
                concurrent_count += 1
                max_concurrent = max(max_concurrent, concurrent_count)
                await asyncio.sleep(0.01)  # Simulate work
                concurrent_count -= 1
                return {
                    "total_recommendations": 0,
                    "critical_issues": 0,
                    "total_savings": 0.0,
                    "critical_recommendations": [],
                    "high_recommendations": [],
                    "medium_recommendations": [],
                    "low_recommendations": [],
                    "analyzer_summaries": {},
                }

        # Replace the method with our mock that still uses the semaphore
        generator._process_analysis_result_async = mock_process_result

        # Process multiple results
        tasks = [
            generator._process_analysis_result_async(result)
            for result in sample_analysis_results * 3
        ]
        await asyncio.gather(*tasks)

        # With semaphore=1, max concurrent should be 1
        assert max_concurrent == 1

    @pytest.mark.asyncio
    async def test_semaphore_bounds_validation(self):
        """Test that semaphore bounds are properly validated."""
        # Test too low
        with pytest.raises(
            ValueError, match="max_concurrent_sections must be at least 1"
        ):
            AsyncReportGenerator(max_concurrent_sections=0)

        # Test too high
        with pytest.raises(
            ValueError, match="max_concurrent_sections must not exceed 50"
        ):
            AsyncReportGenerator(max_concurrent_sections=51)

        # Test valid values
        generator = AsyncReportGenerator(max_concurrent_sections=1)
        assert generator.max_concurrent_sections == 1

        generator = AsyncReportGenerator(max_concurrent_sections=50)
        assert generator.max_concurrent_sections == 50
