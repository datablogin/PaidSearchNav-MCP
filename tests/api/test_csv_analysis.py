"""Test CSV analysis endpoints."""

import io
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest
from httpx import AsyncClient

from paidsearchnav_mcp.api.dependencies import get_current_user
from paidsearchnav_mcp.api.main import app
from paidsearchnav_mcp.models.analysis import (
    AnalysisMetrics,
    AnalysisResult,
    Recommendation,
)


@pytest.fixture(autouse=True)
def override_auth():
    """Override authentication for tests."""
    app.dependency_overrides[get_current_user] = lambda: {
        "user_id": "test-user",
        "customer_id": "123-456-7890",
        "email": "test@example.com",
    }
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_analyze_csv_keywords_success(async_client: AsyncClient):
    """Test successful CSV analysis for keywords."""
    # Create a sample CSV file
    csv_content = """Keyword ID,Campaign ID,Campaign,Ad group ID,Ad group,Keyword,Match type,Status,Impr.,Clicks,Cost
123,456,Campaign 1,789,Ad Group 1,test keyword,EXACT,ENABLED,1000,50,100.00
124,456,Campaign 1,789,Ad Group 1,another keyword,PHRASE,ENABLED,2000,100,200.00"""

    csv_file = io.BytesIO(csv_content.encode())

    # Mock the parser and analyzer
    with (
        patch(
            "paidsearchnav.api.v1.csv_analysis.GoogleAdsCSVParser"
        ) as mock_parser_class,
        patch(
            "paidsearchnav.api.v1.csv_analysis.KeywordAnalyzer"
        ) as mock_analyzer_class,
    ):
        # Mock parser
        mock_parser = Mock()
        mock_parser.parse.return_value = [
            Mock(
                keyword_id="123",
                text="test keyword",
                impressions=1000,
                clicks=50,
                cost=100.0,
            ),
            Mock(
                keyword_id="124",
                text="another keyword",
                impressions=2000,
                clicks=100,
                cost=200.0,
            ),
        ]
        mock_parser_class.return_value = mock_parser

        # Mock analyzer
        mock_analyzer = Mock()
        mock_result = AnalysisResult(
            analysis_type="keyword_analysis",
            analyzer_name="Keyword Analyzer",
            customer_id="123-456-7890",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 3, 31),
            status="completed",
            metrics=AnalysisMetrics(
                total_keywords_analyzed=2,
                issues_found=0,
                critical_issues=0,
            ),
            recommendations=[
                Recommendation(
                    type="ADJUST_BID",
                    priority="MEDIUM",
                    title="Optimize keyword bids",
                    description="Adjust bids based on performance",
                )
            ],
            raw_data={
                "avg_quality_score": 7.5,
                "median_cpc": 2.0,
                "median_cpa": 20.0,
                "optimization_opportunities": 1,
            },
        )

        mock_analyzer.analyze = AsyncMock(return_value=mock_result)
        mock_analyzer_class.return_value = mock_analyzer

        response = await async_client.post(
            "/api/v1/csv/analyze",
            params={
                "data_type": "keywords",
                "customer_id": "123-456-7890",
                "start_date": "2024-01-01",
                "end_date": "2024-03-31",
            },
            files={"file": ("keywords.csv", csv_file, "text/csv")},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["file_type"] == "keywords"
    assert data["total_records"] == 2
    assert data["metrics"]["total_keywords_analyzed"] == 2
    assert len(data["recommendations"]) == 1
    assert data["insights"]["total_keywords"] == 2
    assert data["insights"]["avg_quality_score"] == 7.5


@pytest.mark.asyncio
async def test_analyze_csv_search_terms_success(async_client: AsyncClient):
    """Test successful CSV analysis for search terms."""
    csv_content = """Campaign ID,Campaign,Ad group ID,Ad group,Search term,Impr.,Clicks,Cost
456,Campaign 1,789,Ad Group 1,coffee near me,500,25,50.00
456,Campaign 1,789,Ad Group 1,best coffee shop,300,15,30.00"""

    csv_file = io.BytesIO(csv_content.encode())

    with (
        patch(
            "paidsearchnav.api.v1.csv_analysis.GoogleAdsCSVParser"
        ) as mock_parser_class,
        patch(
            "paidsearchnav.api.v1.csv_analysis.SearchTermsAnalyzer"
        ) as mock_analyzer_class,
    ):
        # Mock parser
        mock_parser = Mock()
        mock_parser.parse.return_value = [
            Mock(search_term="coffee near me", impressions=500, clicks=25, cost=50.0),
            Mock(search_term="best coffee shop", impressions=300, clicks=15, cost=30.0),
        ]
        mock_parser_class.return_value = mock_parser

        # Mock analyzer
        mock_analyzer = Mock()
        mock_result = AnalysisResult(
            analysis_type="search_terms",
            analyzer_name="Search Terms Analyzer",
            customer_id="123-456-7890",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 3, 31),
            status="completed",
            metrics=AnalysisMetrics(
                total_search_terms_analyzed=2,
            ),
            recommendations=[],
            raw_data={
                "negative_keyword_candidates": ["best"],
                "high_cost_low_conversion_terms": [],
                "local_intent_terms": ["coffee near me"],
            },
        )

        mock_analyzer.analyze = AsyncMock(return_value=mock_result)
        mock_analyzer_class.return_value = mock_analyzer

        response = await async_client.post(
            "/api/v1/csv/analyze",
            params={
                "data_type": "search_terms",
                "customer_id": "123-456-7890",
                "start_date": "2024-01-01",
                "end_date": "2024-03-31",
            },
            files={"file": ("search_terms.csv", csv_file, "text/csv")},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["file_type"] == "search_terms"
    assert data["total_records"] == 2
    assert data["insights"]["total_search_terms"] == 2
    assert data["insights"]["negative_keyword_candidates"] == 1
    assert data["insights"]["local_intent_terms"] == 1


@pytest.mark.asyncio
async def test_analyze_multiple_csvs_success(async_client: AsyncClient):
    """Test successful multi-CSV analysis."""
    # Create sample CSV files
    keywords_csv = io.BytesIO(b"""Keyword ID,Campaign ID,Campaign,Ad group ID,Ad group,Keyword,Match type,Status
123,456,Campaign 1,789,Ad Group 1,cheap shoes,EXACT,ENABLED
124,456,Campaign 1,789,Ad Group 1,buy shoes,PHRASE,ENABLED""")

    negative_csv = io.BytesIO(b"""Negative keyword,Match type,Level
cheap,BROAD,Campaign""")

    with (
        patch(
            "paidsearchnav.api.v1.csv_analysis.GoogleAdsCSVParser"
        ) as mock_parser_class,
        patch(
            "paidsearchnav.api.v1.csv_analysis.NegativeConflictAnalyzer"
        ) as mock_analyzer_class,
    ):
        # Mock parser for different file types
        def create_parser(file_type):
            mock_parser = Mock()
            if file_type == "keywords":
                mock_parser.parse.return_value = [
                    Mock(keyword_id="123", text="cheap shoes"),
                    Mock(keyword_id="124", text="buy shoes"),
                ]
            elif file_type == "negative_keywords":
                mock_parser.parse.return_value = [
                    Mock(negative_keyword="cheap", match_type="BROAD"),
                ]
            return mock_parser

        mock_parser_class.side_effect = create_parser

        # Mock analyzer
        mock_analyzer = Mock()
        mock_result = AnalysisResult(
            analysis_type="negative_conflict",
            analyzer_name="Negative Conflict Analyzer",
            customer_id="123-456-7890",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 3, 31),
            status="completed",
            metrics=AnalysisMetrics(),
            recommendations=[
                Recommendation(
                    type="CHANGE_MATCH_TYPE",
                    priority="HIGH",
                    title="Refine negative keyword",
                    description="Change 'cheap' to phrase match",
                )
            ],
            raw_data={
                "conflicts": [
                    {
                        "negative_keyword": "cheap",
                        "conflicting_keyword": "cheap shoes",
                        "match_type": "BROAD",
                        "campaign": "Campaign 1",
                    }
                ]
            },
        )

        mock_analyzer.analyze = AsyncMock(return_value=mock_result)
        mock_analyzer_class.return_value = mock_analyzer

        response = await async_client.post(
            "/api/v1/csv/analyze-multiple",
            params={
                "customer_id": "123-456-7890",
                "start_date": "2024-01-01",
                "end_date": "2024-03-31",
            },
            files={
                "keyword_file": ("keywords.csv", keywords_csv, "text/csv"),
                "negative_keyword_file": ("negatives.csv", negative_csv, "text/csv"),
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["files_analyzed"]["keywords"] == 2
    assert data["files_analyzed"]["negative_keywords"] == 1
    assert len(data["negative_conflicts"]) == 1
    assert data["negative_conflicts"][0]["negative_keyword"] == "cheap"
    assert data["negative_conflicts"][0]["conflicting_keyword"] == "cheap shoes"


@pytest.mark.asyncio
async def test_analyze_csv_invalid_file_type(async_client: AsyncClient):
    """Test CSV analysis with invalid file type."""
    response = await async_client.post(
        "/api/v1/csv/analyze",
        params={
            "data_type": "keywords",
            "customer_id": "123-456-7890",
            "start_date": "2024-01-01",
            "end_date": "2024-03-31",
        },
        files={"file": ("test.txt", b"not a csv", "text/plain")},
    )

    assert response.status_code == 400
    assert "File must be a CSV" in response.json()["detail"]


@pytest.mark.asyncio
async def test_analyze_csv_empty_file(async_client: AsyncClient):
    """Test CSV analysis with empty file."""
    csv_file = io.BytesIO(b"")

    with patch(
        "paidsearchnav.api.v1.csv_analysis.GoogleAdsCSVParser"
    ) as mock_parser_class:
        mock_parser = Mock()
        mock_parser.parse.return_value = []
        mock_parser_class.return_value = mock_parser

        response = await async_client.post(
            "/api/v1/csv/analyze",
            params={
                "data_type": "keywords",
                "customer_id": "123-456-7890",
                "start_date": "2024-01-01",
                "end_date": "2024-03-31",
            },
            files={"file": ("empty.csv", csv_file, "text/csv")},
        )

    assert response.status_code == 400
    assert "No valid records found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_analyze_multiple_no_files(async_client: AsyncClient):
    """Test multi-CSV analysis with no files provided."""
    response = await async_client.post(
        "/api/v1/csv/analyze-multiple",
        params={
            "customer_id": "123-456-7890",
            "start_date": "2024-01-01",
            "end_date": "2024-03-31",
        },
    )

    assert response.status_code == 400
    assert "At least one CSV file must be provided" in response.json()["detail"]
