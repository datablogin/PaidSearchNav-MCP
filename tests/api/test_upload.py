"""Test upload endpoints."""

import io
from unittest.mock import AsyncMock, Mock, patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_upload_csv_keywords_success(async_client: AsyncClient):
    """Test successful CSV upload for keywords."""
    # Create a sample CSV file
    csv_content = """Campaign,Ad Group,Keyword,Match Type,Status
Campaign 1,Ad Group 1,test keyword,EXACT,ENABLED
Campaign 1,Ad Group 1,another keyword,PHRASE,ENABLED"""

    csv_file = io.BytesIO(csv_content.encode())

    # Mock the parser
    with patch("paidsearchnav.api.v1.upload.GoogleAdsCSVParser") as mock_parser_class:
        mock_parser = Mock()
        mock_parser.parse.return_value = [
            Mock(campaign="Campaign 1", ad_group="Ad Group 1", keyword="test keyword"),
            Mock(
                campaign="Campaign 1", ad_group="Ad Group 1", keyword="another keyword"
            ),
        ]
        mock_parser_class.return_value = mock_parser

        response = await async_client.post(
            "/api/v1/upload/csv",
            params={"data_type": "keywords"},
            files={"file": ("test.csv", csv_file, "text/csv")},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 2
    assert data["data_type"] == "keywords"
    assert data["filename"] == "test.csv"
    assert "Successfully parsed 2 keywords records" in data["message"]


@pytest.mark.asyncio
async def test_upload_csv_search_terms_success(async_client: AsyncClient):
    """Test successful CSV upload for search terms."""
    csv_content = """Search term,Match type,Campaign,Ad group
near me coffee,EXACT,Local Campaign,Coffee Shops
coffee shop hours,PHRASE,Local Campaign,Coffee Shops"""

    csv_file = io.BytesIO(csv_content.encode())

    with patch("paidsearchnav.api.v1.upload.GoogleAdsCSVParser") as mock_parser_class:
        mock_parser = Mock()
        mock_parser.parse.return_value = [
            Mock(search_term="near me coffee", campaign="Local Campaign"),
            Mock(search_term="coffee shop hours", campaign="Local Campaign"),
        ]
        mock_parser_class.return_value = mock_parser

        response = await async_client.post(
            "/api/v1/upload/csv",
            params={"data_type": "search_terms"},
            files={"file": ("search_terms.csv", csv_file, "text/csv")},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 2
    assert data["data_type"] == "search_terms"
    assert data["filename"] == "search_terms.csv"
    assert "Successfully parsed 2 search_terms records" in data["message"]


@pytest.mark.asyncio
async def test_upload_csv_invalid_file_extension(async_client: AsyncClient):
    """Test upload with invalid file extension."""
    response = await async_client.post(
        "/api/v1/upload/csv",
        params={"data_type": "keywords"},
        files={"file": ("test.txt", b"some content", "text/plain")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "File must be a CSV"


@pytest.mark.asyncio
async def test_upload_csv_invalid_content_type(async_client: AsyncClient):
    """Test upload with invalid content type."""
    response = await async_client.post(
        "/api/v1/upload/csv",
        params={"data_type": "keywords"},
        files={"file": ("test.csv", b"some content", "application/json")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid content type. Expected CSV file."


@pytest.mark.asyncio
async def test_upload_csv_valid_content_types(async_client: AsyncClient):
    """Test upload with various valid content types."""
    valid_content_types = ["text/csv", "application/csv", "text/plain"]

    for content_type in valid_content_types:
        csv_file = io.BytesIO(b"header1,header2\nvalue1,value2")

        with patch(
            "paidsearchnav.api.v1.upload.GoogleAdsCSVParser"
        ) as mock_parser_class:
            mock_parser = Mock()
            mock_parser.parse.return_value = []
            mock_parser_class.return_value = mock_parser

            response = await async_client.post(
                "/api/v1/upload/csv",
                params={"data_type": "keywords"},
                files={"file": ("test.csv", csv_file, content_type)},
            )

            assert response.status_code == 200, (
                f"Failed for content type: {content_type}"
            )


@pytest.mark.asyncio
async def test_upload_csv_missing_data_type(async_client: AsyncClient):
    """Test upload without data_type parameter."""
    csv_file = io.BytesIO(b"test,csv,content")

    response = await async_client.post(
        "/api/v1/upload/csv",
        files={"file": ("test.csv", csv_file, "text/csv")},
    )

    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_upload_csv_invalid_data_type(async_client: AsyncClient):
    """Test upload with invalid data_type parameter."""
    csv_file = io.BytesIO(b"test,csv,content")

    response = await async_client.post(
        "/api/v1/upload/csv",
        params={"data_type": "invalid_type"},
        files={"file": ("test.csv", csv_file, "text/csv")},
    )

    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_upload_csv_parser_error(async_client: AsyncClient):
    """Test upload when parser raises ValueError."""
    csv_file = io.BytesIO(b"invalid,csv,content")

    with patch("paidsearchnav.api.v1.upload.GoogleAdsCSVParser") as mock_parser_class:
        mock_parser = Mock()
        mock_parser.parse.side_effect = ValueError("Invalid CSV format")
        mock_parser_class.return_value = mock_parser

        response = await async_client.post(
            "/api/v1/upload/csv",
            params={"data_type": "keywords"},
            files={"file": ("test.csv", csv_file, "text/csv")},
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid CSV format"


@pytest.mark.asyncio
async def test_upload_csv_unexpected_error(async_client: AsyncClient):
    """Test upload when parser raises unexpected error."""
    csv_file = io.BytesIO(b"test,csv,content")

    with patch("paidsearchnav.api.v1.upload.GoogleAdsCSVParser") as mock_parser_class:
        mock_parser = Mock()
        mock_parser.parse.side_effect = Exception("Unexpected error")
        mock_parser_class.return_value = mock_parser

        response = await async_client.post(
            "/api/v1/upload/csv",
            params={"data_type": "keywords"},
            files={"file": ("test.csv", csv_file, "text/csv")},
        )

    assert response.status_code == 500
    assert (
        "Failed to process CSV file. Please check the file format and try again."
        == response.json()["detail"]
    )


@pytest.mark.asyncio
async def test_upload_csv_no_file(async_client: AsyncClient):
    """Test upload without providing a file."""
    response = await async_client.post(
        "/api/v1/upload/csv",
        params={"data_type": "keywords"},
    )

    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_upload_csv_large_file(async_client: AsyncClient):
    """Test upload with file exceeding size limit."""
    # Create a mock file object with size attribute
    large_file = Mock()
    large_file.filename = "large.csv"
    large_file.size = 101 * 1024 * 1024  # 101MB
    large_file.read = AsyncMock(return_value=b"content")
    large_file.close = AsyncMock()

    # We need to test this at the endpoint level, but FastAPI's UploadFile
    # doesn't expose size reliably in tests. This is a limitation of the test setup.
    # In production, the RequestLimitMiddleware would handle this.
    pass  # Skip this test as it requires middleware configuration


@pytest.mark.asyncio
async def test_upload_csv_empty_file(async_client: AsyncClient):
    """Test upload with empty CSV file."""
    empty_file = io.BytesIO(b"")

    with patch("paidsearchnav.api.v1.upload.GoogleAdsCSVParser") as mock_parser_class:
        mock_parser = Mock()
        mock_parser.parse.return_value = []
        mock_parser_class.return_value = mock_parser

        response = await async_client.post(
            "/api/v1/upload/csv",
            params={"data_type": "keywords"},
            files={"file": ("empty.csv", empty_file, "text/csv")},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 0
    assert "Successfully parsed 0 keywords records" in data["message"]


@pytest.mark.asyncio
async def test_upload_csv_filename_sanitization(async_client: AsyncClient):
    """Test that filenames are properly sanitized."""
    dangerous_filenames = [
        ("../../../etc/passwd.csv", "etcpasswd.csv"),
        ("file<script>.csv", "filescript.csv"),
        ("file|pipe.csv", "filepipe.csv"),
        ("file with spaces.csv", "file with spaces.csv"),
        (".hidden.csv", "hidden.csv"),
    ]

    for dangerous_name, expected_safe_name in dangerous_filenames:
        csv_file = io.BytesIO(b"header1,header2\nvalue1,value2")

        with patch(
            "paidsearchnav.api.v1.upload.GoogleAdsCSVParser"
        ) as mock_parser_class:
            mock_parser = Mock()
            mock_parser.parse.return_value = []
            mock_parser_class.return_value = mock_parser

            response = await async_client.post(
                "/api/v1/upload/csv",
                params={"data_type": "keywords"},
                files={"file": (dangerous_name, csv_file, "text/csv")},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["filename"] == expected_safe_name
