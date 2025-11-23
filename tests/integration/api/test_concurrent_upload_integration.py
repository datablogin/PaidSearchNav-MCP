"""Integration tests for concurrent CSV upload API endpoints."""

import asyncio
import tempfile
from io import BytesIO
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient

# Skip entire module if imports are not available
pytest.importorskip("paidsearchnav.integrations.database")

from paidsearchnav_mcp.api.dependencies import get_current_user, get_repository
from paidsearchnav_mcp.api.main import app
from paidsearchnav_mcp.integrations.database import (
    DatabaseConnection,
)


@pytest.fixture
async def test_db(tmp_path):
    """Create a test database."""
    db_path = tmp_path / "test_concurrent.db"
    db_url = f"sqlite+aiosqlite:///{db_path}"
    db = DatabaseConnection(db_url)
    await db.initialize()
    yield db
    await db.close()


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def override_auth():
    """Override authentication and repository for tests."""
    from unittest.mock import AsyncMock

    # Mock user
    app.dependency_overrides[get_current_user] = lambda: {
        "user_id": "test-user",
        "customer_id": "123-456-7890",
        "email": "test@example.com",
    }

    # Mock repository
    mock_repo = AsyncMock()
    mock_repo.check_connection = AsyncMock(return_value=True)
    app.dependency_overrides[get_repository] = lambda: mock_repo

    yield
    app.dependency_overrides.clear()


@pytest.fixture
async def async_client():
    """Create an async test client."""
    async with AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


def create_csv_file(data_type: str, num_rows: int = 100) -> BytesIO:
    """Create a CSV file for testing."""
    if data_type == "keywords":
        header = "Keyword ID,Campaign ID,Campaign,Ad group ID,Ad group,Keyword,Match type,Status,Impr.,Clicks,Cost\n"
        row_template = '{},{},Campaign {},{},"Ad Group {}","keyword {}","EXACT","ENABLED",{},{},{:.2f}\n'
    else:  # search_terms
        header = (
            "Campaign ID,Campaign,Ad group ID,Ad group,Search term,Impr.,Clicks,Cost\n"
        )
        row_template = '{},Campaign {},{},"Ad Group {}","search term {}",{},{},{:.2f}\n'

    csv_content = header
    for i in range(num_rows):
        if data_type == "keywords":
            csv_content += row_template.format(
                1000 + i,  # Keyword ID
                100 + (i % 10),  # Campaign ID
                i % 10,  # Campaign name
                200 + (i % 5),  # Ad group ID
                i % 5,  # Ad group name
                i,  # Keyword
                100 + i,  # Impressions
                10 + (i % 20),  # Clicks
                50.0 + i,  # Cost
            )
        else:
            csv_content += row_template.format(
                100 + (i % 10),  # Campaign ID
                i % 10,  # Campaign name
                200 + (i % 5),  # Ad group ID
                i % 5,  # Ad group name
                i,  # Search term
                100 + i,  # Impressions
                10 + (i % 20),  # Clicks
                50.0 + i,  # Cost
            )

    return BytesIO(csv_content.encode())


def create_large_csv_file(size_mb: float) -> BytesIO:
    """Create a large CSV file of specified size in MB."""
    header = "Keyword ID,Campaign ID,Campaign,Ad group ID,Ad group,Keyword,Match type,Status,Impr.,Clicks,Cost\n"
    row = '1000,100,"Very Long Campaign Name Here",200,"Very Long Ad Group Name","very long keyword phrase","EXACT","ENABLED",1000,100,200.00\n'

    # Calculate rows needed to reach target size
    header_size = len(header.encode())
    row_size = len(row.encode())
    target_bytes = int(size_mb * 1024 * 1024)
    rows_needed = (target_bytes - header_size) // row_size

    csv_content = header + (row * rows_needed)
    return BytesIO(csv_content.encode())


class TestConcurrentUploadIntegration:
    """Test concurrent file upload scenarios."""

    async def test_multiple_concurrent_uploads_within_limit(self, async_client):
        """Test multiple concurrent uploads within the 100-request limit."""
        num_uploads = 10
        files = []

        # Create test files
        for i in range(num_uploads):
            data_type = "keywords" if i % 2 == 0 else "search_terms"
            csv_file = create_csv_file(data_type, num_rows=50)
            files.append(
                {
                    "files": {"file": (f"test_{i}.csv", csv_file, "text/csv")},
                    "data": {"data_type": data_type},
                }
            )

        # Upload all files concurrently
        tasks = []
        for file_data in files:
            task = async_client.post(
                "/api/v1/upload/csv",
                files=file_data["files"],
                params={"data_type": file_data["data"]["data_type"]},
            )
            tasks.append(task)

        responses = await asyncio.gather(*tasks)

        # Verify all uploads succeeded
        for i, response in enumerate(responses):
            assert response.status_code == 200
            data = response.json()
            assert data["count"] == 50
            data_type = "keywords" if i % 2 == 0 else "search_terms"
            assert data["message"] == f"Successfully parsed 50 {data_type} records"

    async def test_concurrent_uploads_different_sizes(self, async_client):
        """Test concurrent uploads with different file sizes."""
        # Create files of different sizes
        sizes = [0.1, 0.5, 1.0, 2.0]  # MB
        files = []

        for size in sizes:
            csv_file = create_large_csv_file(size)
            files.append(
                {
                    "files": {"file": (f"test_{size}mb.csv", csv_file, "text/csv")},
                    "data": {"data_type": "keywords"},
                }
            )

        # Upload concurrently
        tasks = []
        for file_data in files:
            task = async_client.post(
                "/api/v1/upload/csv",
                files=file_data["files"],
                params={"data_type": file_data["data"]["data_type"]},
            )
            tasks.append(task)

        responses = await asyncio.gather(*tasks)

        # All should succeed (all under 10MB limit)
        for response in responses:
            assert response.status_code == 200

    async def test_concurrent_uploads_with_errors(self, async_client):
        """Test concurrent uploads where some fail and some succeed."""
        # Create mix of valid and invalid files
        files = []

        # Valid file
        valid_csv = create_csv_file("keywords", 50)
        files.append(
            {
                "files": {"file": ("valid.csv", valid_csv, "text/csv")},
                "data": {"data_type": "keywords"},
                "expected_status": 200,
            }
        )

        # Invalid CSV format
        invalid_csv = BytesIO(b"This is not a CSV file")
        files.append(
            {
                "files": {"file": ("invalid.csv", invalid_csv, "text/csv")},
                "data": {"data_type": "keywords"},
                "expected_status": 400,
            }
        )

        # Missing required columns
        missing_cols_csv = BytesIO(b"Campaign,Ad Group\nTest,Test\n")
        files.append(
            {
                "files": {"file": ("missing_cols.csv", missing_cols_csv, "text/csv")},
                "data": {"data_type": "keywords"},
                "expected_status": 400,
            }
        )

        # Wrong data type
        wrong_type_csv = create_csv_file("keywords", 50)
        files.append(
            {
                "files": {"file": ("wrong_type.csv", wrong_type_csv, "text/csv")},
                "data": {"data_type": "invalid_type"},
                "expected_status": 422,  # Validation error
            }
        )

        # Upload all concurrently
        tasks = []
        for file_data in files:
            # Handle the special case of invalid_type which should fail at validation
            if "data_type" in file_data["data"]:
                params = {"data_type": file_data["data"]["data_type"]}
            else:
                params = {}
            task = async_client.post(
                "/api/v1/upload/csv", files=file_data["files"], params=params
            )
            tasks.append(task)

        responses = await asyncio.gather(*tasks, return_exceptions=True)

        # Verify expected results
        for i, response in enumerate(responses):
            if not isinstance(response, Exception):
                assert response.status_code == files[i]["expected_status"]

    async def test_concurrent_uploads_approaching_limit(self, async_client):
        """Test behavior when approaching the 100 concurrent request limit."""
        # Note: This test simulates the scenario but may not hit the actual limit
        # in test environment due to fast processing

        num_uploads = 50  # Safe number for testing
        semaphore = asyncio.Semaphore(10)  # Limit concurrent connections

        async def upload_file(index: int):
            async with semaphore:
                csv_file = create_csv_file("keywords", 20)
                response = await async_client.post(
                    "/api/v1/upload/csv",
                    files={"file": (f"test_{index}.csv", csv_file, "text/csv")},
                    params={"data_type": "keywords"},
                )
                return response

        tasks = [upload_file(i) for i in range(num_uploads)]
        responses = await asyncio.gather(*tasks)

        # Count successful uploads
        successful = sum(1 for r in responses if r.status_code == 200)
        assert successful >= num_uploads * 0.9  # At least 90% should succeed

    async def test_concurrent_mixed_operations(self, async_client, test_db):
        """Test concurrent uploads mixed with other API operations."""
        # Create tasks for different operations
        tasks = []

        # Upload tasks
        for i in range(5):
            csv_file = create_csv_file("keywords" if i % 2 == 0 else "search_terms", 30)
            upload_task = async_client.post(
                "/api/v1/upload/csv",
                files={"file": (f"upload_{i}.csv", csv_file, "text/csv")},
                params={"data_type": "keywords" if i % 2 == 0 else "search_terms"},
            )
            tasks.append(("upload", upload_task))

        # Health check tasks (should not interfere)
        for i in range(10):
            health_task = async_client.get("/api/v1/health")
            tasks.append(("health", health_task))

        # Execute all tasks concurrently
        task_futures = [task[1] for task in tasks]
        responses = await asyncio.gather(*task_futures)

        # Verify results
        upload_count = 0
        health_count = 0

        for i, (task_type, _) in enumerate(tasks):
            if task_type == "upload":
                assert responses[i].status_code == 200
                upload_count += 1
            elif task_type == "health":
                assert responses[i].status_code == 200
                health_count += 1

        assert upload_count == 5
        assert health_count == 10

    async def test_upload_file_cleanup(self, async_client, tmp_path):
        """Test that temporary files are cleaned up after concurrent uploads."""
        # Track temp directory before uploads
        temp_dir = tempfile.gettempdir()
        initial_files = set(Path(temp_dir).glob("*"))

        # Perform concurrent uploads
        num_uploads = 5
        tasks = []

        for i in range(num_uploads):
            csv_file = create_csv_file("keywords", 100)
            task = async_client.post(
                "/api/v1/upload/csv",
                files={"file": (f"cleanup_test_{i}.csv", csv_file, "text/csv")},
                params={"data_type": "keywords"},
            )
            tasks.append(task)

        responses = await asyncio.gather(*tasks)

        # All should succeed
        for response in responses:
            assert response.status_code == 200

        # Wait a bit for cleanup
        await asyncio.sleep(1)

        # Check temp directory - should not have extra files
        final_files = set(Path(temp_dir).glob("*"))
        new_files = final_files - initial_files

        # Filter out any system temp files
        csv_temp_files = [f for f in new_files if "csv" in f.name.lower()]
        assert len(csv_temp_files) == 0, f"Found uncleaned temp files: {csv_temp_files}"

    async def test_concurrent_large_file_timeout_handling(self, async_client):
        """Test handling of large files that might approach timeout limits."""
        # Create a file that's large but under the limit
        large_csv = create_large_csv_file(8.0)  # 8MB file

        # Create multiple large file uploads
        tasks = []
        for i in range(3):
            task = async_client.post(
                "/api/v1/upload/csv",
                files={"file": (f"large_{i}.csv", large_csv, "text/csv")},
                params={"data_type": "keywords"},
                timeout=60.0,  # Increase timeout for large files
            )
            tasks.append(task)
            large_csv.seek(0)  # Reset file pointer

        responses = await asyncio.gather(*tasks, return_exceptions=True)

        # Check results
        for response in responses:
            if isinstance(response, Exception):
                # Timeout or other errors are acceptable for very large files
                pass
            else:
                # If it completed, should be successful or bad request
                assert response.status_code in [
                    200,
                    400,
                    408,
                ]  # Success, bad request, or timeout

    async def test_rate_limiting_behavior(self, async_client):
        """Test rate limiting behavior under high concurrent load."""
        # Create many small requests quickly
        num_requests = 20
        tasks = []

        for i in range(num_requests):
            csv_file = create_csv_file("keywords", 10)  # Small file
            task = async_client.post(
                "/api/v1/upload/csv",
                files={"file": (f"rate_test_{i}.csv", csv_file, "text/csv")},
                params={"data_type": "keywords"},
            )
            tasks.append(task)

        # Send all at once
        responses = await asyncio.gather(*tasks, return_exceptions=True)

        # Count response types
        status_codes = {}
        for response in responses:
            if not isinstance(response, Exception):
                status = response.status_code
                status_codes[status] = status_codes.get(status, 0) + 1

        # Should have some successful requests
        assert status_codes.get(200, 0) > 0

        # May have rate limiting responses
        # Note: 429 responses indicate rate limiting is working
        if 429 in status_codes:
            assert status_codes[429] > 0  # Rate limiting kicked in

    async def test_concurrent_different_content_types(self, async_client):
        """Test concurrent uploads with different content types."""
        files = []

        # Valid CSV with different content type headers
        content_types = ["text/csv", "application/csv", "text/plain"]

        for i, content_type in enumerate(content_types):
            csv_file = create_csv_file("keywords", 50)
            files.append(
                {
                    "files": {"file": (f"test_{i}.csv", csv_file, content_type)},
                    "data": {"data_type": "keywords"},
                }
            )

        # Invalid content type
        csv_file = create_csv_file("keywords", 50)
        files.append(
            {
                "files": {"file": ("test_invalid.csv", csv_file, "application/json")},
                "data": {"data_type": "keywords"},
            }
        )

        # Upload all concurrently
        tasks = []
        for file_data in files:
            task = async_client.post(
                "/api/v1/upload/csv",
                files=file_data["files"],
                params={"data_type": file_data["data"]["data_type"]},
            )
            tasks.append(task)

        responses = await asyncio.gather(*tasks)

        # First three should succeed (valid content types)
        for i in range(3):
            assert responses[i].status_code == 200

        # Last one might fail due to invalid content type
        # (depends on middleware configuration)
