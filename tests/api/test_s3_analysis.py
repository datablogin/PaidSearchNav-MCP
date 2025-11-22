"""Test S3-based CSV analysis endpoints."""

from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest
from botocore.exceptions import ClientError, NoCredentialsError
from httpx import AsyncClient

from paidsearchnav.api.dependencies import get_current_user
from paidsearchnav.api.main import app
from paidsearchnav.core.models.analysis import (
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


@pytest.fixture
def mock_s3_client():
    """Mock S3 client."""
    with patch("boto3.client") as mock_boto:
        s3_mock = Mock()
        mock_boto.return_value = s3_mock
        yield s3_mock


@pytest.fixture
def sample_csv_content():
    """Sample CSV content for testing."""
    return """Keyword ID,Campaign ID,Campaign,Ad group ID,Ad group,Keyword,Match type,Status,Impr.,Clicks,Cost
123,456,Campaign 1,789,Ad Group 1,test keyword,EXACT,ENABLED,1000,50,100.00
124,456,Campaign 1,789,Ad Group 1,another keyword,PHRASE,ENABLED,2000,100,200.00"""


class TestS3SingleFileAnalysis:
    """Test single file S3 analysis endpoint."""

    @pytest.mark.asyncio
    async def test_s3_analyze_keywords_success(
        self, async_client: AsyncClient, mock_s3_client, sample_csv_content
    ):
        """Test successful S3 keyword analysis."""
        # Mock S3 download
        mock_temp_file = Mock()
        mock_temp_file.name = "/tmp/test.csv"

        with (
            patch("tempfile.NamedTemporaryFile", return_value=mock_temp_file),
            patch("pathlib.Path.stat") as mock_stat,
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.unlink"),
            patch("builtins.open", mock_open_file(sample_csv_content)),
            patch(
                "paidsearchnav.api.v1.s3_analysis.GoogleAdsCSVParser"
            ) as mock_parser_class,
            patch(
                "paidsearchnav.api.v1.s3_analysis.KeywordAnalyzer"
            ) as mock_analyzer_class,
        ):
            mock_stat.return_value.st_size = 1024

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
                metrics=AnalysisMetrics(total_keywords_analyzed=2, issues_found=0),
                recommendations=[],
                raw_data={"avg_quality_score": 7.5},
            )
            mock_analyzer.analyze = AsyncMock(return_value=mock_result)
            mock_analyzer_class.return_value = mock_analyzer

            response = await async_client.post(
                "/api/v1/csv/s3/analyze",
                params={
                    "s3_path": "s3://test-bucket/ret/customer123/inputs/keywords.csv",
                    "data_type": "keywords",
                    "customer_id": "123-456-7890",
                    "start_date": "2024-01-01",
                    "end_date": "2024-03-31",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["file_type"] == "keywords"
        assert data["total_records"] == 2
        assert (
            data["insights"]["s3_source"]
            == "s3://test-bucket/ret/customer123/inputs/keywords.csv"
        )
        mock_s3_client.download_file.assert_called_once()

    @pytest.mark.asyncio
    async def test_s3_analyze_invalid_path(self, async_client: AsyncClient):
        """Test S3 analysis with invalid S3 path."""
        response = await async_client.post(
            "/api/v1/csv/s3/analyze",
            params={
                "s3_path": "invalid-path",
                "data_type": "keywords",
                "customer_id": "123-456-7890",
                "start_date": "2024-01-01",
                "end_date": "2024-03-31",
            },
        )

        assert response.status_code == 400
        assert "Invalid S3 path" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_s3_analyze_path_traversal_attempt(self, async_client: AsyncClient):
        """Test S3 analysis blocks path traversal attempts."""
        response = await async_client.post(
            "/api/v1/csv/s3/analyze",
            params={
                "s3_path": "s3://bucket/../../../etc/passwd",
                "data_type": "keywords",
                "customer_id": "123-456-7890",
                "start_date": "2024-01-01",
                "end_date": "2024-03-31",
            },
        )

        assert response.status_code == 400
        assert "path traversal detected" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_s3_analyze_no_credentials(self, async_client: AsyncClient):
        """Test S3 analysis with no AWS credentials."""
        with patch("boto3.client", side_effect=NoCredentialsError()):
            response = await async_client.post(
                "/api/v1/csv/s3/analyze",
                params={
                    "s3_path": "s3://test-bucket/keywords.csv",
                    "data_type": "keywords",
                    "customer_id": "123-456-7890",
                    "start_date": "2024-01-01",
                    "end_date": "2024-03-31",
                },
            )

        assert response.status_code == 401
        assert "AWS credentials not configured" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_s3_analyze_file_not_found(
        self, async_client: AsyncClient, mock_s3_client
    ):
        """Test S3 analysis with file not found."""
        mock_s3_client.download_file.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey"}}, "download_file"
        )

        response = await async_client.post(
            "/api/v1/csv/s3/analyze",
            params={
                "s3_path": "s3://test-bucket/nonexistent.csv",
                "data_type": "keywords",
                "customer_id": "123-456-7890",
                "start_date": "2024-01-01",
                "end_date": "2024-03-31",
            },
        )

        assert response.status_code == 404
        assert "S3 file not found" in response.json()["detail"]


class TestS3MultiFileAnalysis:
    """Test multi-file S3 analysis endpoint."""

    @pytest.mark.asyncio
    async def test_s3_analyze_multi_success(
        self, async_client: AsyncClient, mock_s3_client, sample_csv_content
    ):
        """Test successful multi-file S3 analysis."""
        negative_csv_content = """Negative keyword,Match type,Level
cheap,BROAD,Campaign"""

        # Mock S3 downloads
        mock_temp_file = Mock()
        mock_temp_file.name = "/tmp/test.csv"

        with (
            patch("tempfile.NamedTemporaryFile", return_value=mock_temp_file),
            patch("pathlib.Path.stat") as mock_stat,
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.unlink"),
            patch(
                "builtins.open",
                mock_open_file_multi([sample_csv_content, negative_csv_content]),
            ),
            patch(
                "paidsearchnav.api.v1.s3_analysis.GoogleAdsCSVParser"
            ) as mock_parser_class,
            patch(
                "paidsearchnav.api.v1.s3_analysis.NegativeConflictAnalyzer"
            ) as mock_analyzer_class,
        ):
            mock_stat.return_value.st_size = 1024

            # Mock parser for different file types
            def create_parser(file_type, **kwargs):
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
                raw_data={"conflicts": 1},
            )
            mock_analyzer.analyze = AsyncMock(return_value=mock_result)
            mock_analyzer_class.return_value = mock_analyzer

            response = await async_client.post(
                "/api/v1/csv/s3/analyze-multi",
                params={
                    "keywords_file": "s3://test-bucket/keywords.csv",
                    "negative_keywords_file": "s3://test-bucket/negatives.csv",
                    "analysis_type": "negative_keywords",
                    "customer_id": "123-456-7890",
                    "start_date": "2024-01-01",
                    "end_date": "2024-03-31",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["file_type"] == "negative_keywords"
        assert data["total_records"] == 3  # keywords + negatives
        assert len(data["recommendations"]) == 1
        assert data["insights"]["files_processed"] == ["keywords", "negative_keywords"]

    @pytest.mark.asyncio
    async def test_s3_analyze_multi_missing_required_files(
        self, async_client: AsyncClient
    ):
        """Test multi-file analysis with missing required files."""
        response = await async_client.post(
            "/api/v1/csv/s3/analyze-multi",
            params={
                "analysis_type": "negative_keywords",  # Requires keywords_file and negative_keywords_file
                "customer_id": "123-456-7890",
                "start_date": "2024-01-01",
                "end_date": "2024-03-31",
            },
        )

        assert response.status_code == 400
        assert "Missing required files" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_s3_analyze_multi_invalid_s3_paths(self, async_client: AsyncClient):
        """Test multi-file analysis with invalid S3 paths."""
        response = await async_client.post(
            "/api/v1/csv/s3/analyze-multi",
            params={
                "keywords_file": "invalid-path",
                "negative_keywords_file": "s3://bucket/negatives.csv",
                "analysis_type": "negative_keywords",
                "customer_id": "123-456-7890",
                "start_date": "2024-01-01",
                "end_date": "2024-03-31",
            },
        )

        assert response.status_code == 400
        assert "Invalid S3 path" in response.json()["detail"]


class TestS3UploadFunctionality:
    """Test S3 upload functionality."""

    @pytest.mark.asyncio
    async def test_upload_results_to_s3_success(self, mock_s3_client):
        """Test successful S3 upload."""
        from paidsearchnav.api.v1.s3_analysis import upload_results_to_s3

        analysis_data = {
            "analysis_id": "test-123",
            "file_type": "keywords",
            "total_records": 100,
        }

        result = upload_results_to_s3(
            analysis_data,
            "s3://test-bucket/ret/customer123/inputs/keywords.csv",
            "keywords",
        )

        expected_path = (
            "s3://test-bucket/ret/customer123/outputs/test-123_keywords_analysis.json"
        )
        assert result == expected_path
        mock_s3_client.put_object.assert_called_once()

        # Check call arguments
        call_args = mock_s3_client.put_object.call_args
        assert call_args[1]["Bucket"] == "test-bucket"
        assert "customer123" in call_args[1]["Key"]
        assert call_args[1]["ServerSideEncryption"] == "AES256"

    @pytest.mark.asyncio
    async def test_upload_results_s3_access_denied(self, mock_s3_client):
        """Test S3 upload with access denied."""
        from paidsearchnav.api.v1.s3_analysis import upload_results_to_s3

        mock_s3_client.put_object.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied"}}, "put_object"
        )

        with pytest.raises(Exception) as exc_info:
            upload_results_to_s3(
                {"test": "data"}, "s3://test-bucket/ret/customer123/inputs/keywords.csv"
            )

        assert "Access denied" in str(exc_info.value)


def mock_open_file(content: str):
    """Mock file open with specified content."""

    def mock_open(*args, **kwargs):
        from io import StringIO

        return StringIO(content)

    return mock_open


def mock_open_file_multi(contents: list[str]):
    """Mock file open with multiple contents for sequential calls."""
    calls = iter(contents)

    def mock_open(*args, **kwargs):
        from io import StringIO

        try:
            content = next(calls)
            return StringIO(content)
        except StopIteration:
            return StringIO(contents[0])  # Default to first content

    return mock_open
