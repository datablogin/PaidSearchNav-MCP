"""Test error handling for upload endpoints."""

import io
from unittest.mock import Mock, patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestUploadErrorHandling:
    """Test suite for upload endpoint error handling."""

    async def test_upload_empty_csv_file(self, async_client: AsyncClient):
        """Test upload with empty CSV file."""
        empty_file = io.BytesIO(b"")

        with patch(
            "paidsearchnav.api.v1.upload.GoogleAdsCSVParser"
        ) as mock_parser_class:
            mock_parser = Mock()
            mock_parser.parse.side_effect = ValueError("CSV file is empty")
            mock_parser_class.return_value = mock_parser

            response = await async_client.post(
                "/api/v1/upload/csv",
                params={"data_type": "keywords"},
                files={"file": ("empty.csv", empty_file, "text/csv")},
            )

        assert response.status_code == 400
        assert (
            "CSV file is empty or contains no valid data rows"
            in response.json()["detail"]
        )

    async def test_upload_csv_only_headers(self, async_client: AsyncClient):
        """Test upload with CSV containing only headers."""
        headers_only = io.BytesIO(b"Keyword,Campaign,Cost\n")

        with patch(
            "paidsearchnav.api.v1.upload.GoogleAdsCSVParser"
        ) as mock_parser_class:
            mock_parser = Mock()
            mock_parser.parse.side_effect = ValueError("CSV file contains no data rows")
            mock_parser_class.return_value = mock_parser

            response = await async_client.post(
                "/api/v1/upload/csv",
                params={"data_type": "keywords"},
                files={"file": ("headers_only.csv", headers_only, "text/csv")},
            )

        assert response.status_code == 400
        assert (
            "CSV file is empty or contains no valid data rows"
            in response.json()["detail"]
        )

    async def test_upload_missing_required_fields(self, async_client: AsyncClient):
        """Test upload with missing required fields."""
        csv_content = """Campaign,Impressions,Clicks
Campaign 1,1000,50
Campaign 2,2000,100"""

        csv_file = io.BytesIO(csv_content.encode())

        with patch(
            "paidsearchnav.api.v1.upload.GoogleAdsCSVParser"
        ) as mock_parser_class:
            mock_parser = Mock()
            mock_parser.parse.side_effect = ValueError(
                "Missing required fields: Keyword ID, Campaign ID, Ad group ID"
            )
            mock_parser_class.return_value = mock_parser

            response = await async_client.post(
                "/api/v1/upload/csv",
                params={"data_type": "keywords"},
                files={"file": ("missing_fields.csv", csv_file, "text/csv")},
            )

        assert response.status_code == 400
        assert "CSV file is missing required columns" in response.json()["detail"]
        assert "Keyword ID" in response.json()["detail"]

    async def test_upload_invalid_numeric_values(self, async_client: AsyncClient):
        """Test upload with invalid numeric values."""
        csv_content = """Keyword,Campaign,Cost,Impressions
keyword1,Campaign 1,not_a_number,also_not_a_number
keyword2,Campaign 1,123.45,1000"""

        csv_file = io.BytesIO(csv_content.encode())

        with patch(
            "paidsearchnav.api.v1.upload.GoogleAdsCSVParser"
        ) as mock_parser_class:
            mock_parser = Mock()
            mock_parser.parse.side_effect = ValueError(
                "Invalid numeric value 'not_a_number' in field 'Cost'"
            )
            mock_parser_class.return_value = mock_parser

            response = await async_client.post(
                "/api/v1/upload/csv",
                params={"data_type": "keywords"},
                files={"file": ("invalid_numeric.csv", csv_file, "text/csv")},
            )

        assert response.status_code == 400
        assert "Data validation error" in response.json()["detail"]
        assert "Invalid numeric value" in response.json()["detail"]

    async def test_upload_encoding_error(self, async_client: AsyncClient):
        """Test upload with encoding error."""
        # Create invalid UTF-8 bytes
        invalid_utf8 = b"\xff\xfe"

        with patch(
            "paidsearchnav.api.v1.upload.GoogleAdsCSVParser"
        ) as mock_parser_class:
            mock_parser = Mock()
            mock_parser.parse.side_effect = ValueError(
                "File encoding error: 'utf-8' codec can't decode. Try a different encoding."
            )
            mock_parser_class.return_value = mock_parser

            response = await async_client.post(
                "/api/v1/upload/csv",
                params={"data_type": "keywords"},
                files={"file": ("encoded.csv", invalid_utf8, "text/csv")},
            )

        assert response.status_code == 400
        json_detail = response.json()["detail"]
        assert "File encoding error" in json_detail

    async def test_upload_csv_format_error(self, async_client: AsyncClient):
        """Test upload with malformed CSV."""
        malformed_csv = io.BytesIO(b"col1,col2,col3\nval1,val2\nval1,val2,val3,val4")

        with patch(
            "paidsearchnav.api.v1.upload.GoogleAdsCSVParser"
        ) as mock_parser_class:
            mock_parser = Mock()
            mock_parser.parse.side_effect = ValueError(
                "CSV format error: Error tokenizing data"
            )
            mock_parser_class.return_value = mock_parser

            response = await async_client.post(
                "/api/v1/upload/csv",
                params={"data_type": "keywords"},
                files={"file": ("malformed.csv", malformed_csv, "text/csv")},
            )

        assert response.status_code == 400
        assert "Invalid CSV format" in response.json()["detail"]

    async def test_upload_file_size_exceeded(self, async_client: AsyncClient):
        """Test upload with file exceeding size limit."""
        large_content = "x" * 1000  # Just a placeholder
        csv_file = io.BytesIO(large_content.encode())

        with patch(
            "paidsearchnav.api.v1.upload.GoogleAdsCSVParser"
        ) as mock_parser_class:
            mock_parser = Mock()
            mock_parser.parse.side_effect = ValueError(
                "File size (101000000 bytes) exceeds maximum allowed size (100000000 bytes)"
            )
            mock_parser_class.return_value = mock_parser

            response = await async_client.post(
                "/api/v1/upload/csv",
                params={"data_type": "search_terms"},
                files={"file": ("large.csv", csv_file, "text/csv")},
            )

        assert response.status_code == 400
        assert "exceeds maximum allowed size" in response.json()["detail"]

    async def test_upload_file_not_found(self, async_client: AsyncClient):
        """Test handling of FileNotFoundError (edge case)."""
        csv_file = io.BytesIO(b"test,data")

        with patch(
            "paidsearchnav.api.v1.upload.GoogleAdsCSVParser"
        ) as mock_parser_class:
            mock_parser = Mock()
            mock_parser.parse.side_effect = FileNotFoundError("File not found")
            mock_parser_class.return_value = mock_parser

            response = await async_client.post(
                "/api/v1/upload/csv",
                params={"data_type": "keywords"},
                files={"file": ("test.csv", csv_file, "text/csv")},
            )

        assert response.status_code == 400
        assert response.json()["detail"] == "Uploaded file could not be found"

    async def test_upload_generic_validation_error(self, async_client: AsyncClient):
        """Test handling of generic validation errors."""
        csv_file = io.BytesIO(b"test,data")

        with patch(
            "paidsearchnav.api.v1.upload.GoogleAdsCSVParser"
        ) as mock_parser_class:
            mock_parser = Mock()
            mock_parser.parse.side_effect = ValueError("Some other validation error")
            mock_parser_class.return_value = mock_parser

            response = await async_client.post(
                "/api/v1/upload/csv",
                params={"data_type": "keywords"},
                files={"file": ("test.csv", csv_file, "text/csv")},
            )

        assert response.status_code == 400
        assert response.json()["detail"] == "Some other validation error"

    async def test_upload_special_filename_characters(self, async_client: AsyncClient):
        """Test that dangerous filename characters are sanitized."""
        csv_content = b"header1,header2\nvalue1,value2"

        dangerous_filenames = [
            "../../../etc/passwd.csv",
            "file<script>alert('xss')</script>.csv",
            "file|pipe|command.csv",
            "file\x00null.csv",
            ".hidden..dotfile.csv",
        ]

        for dangerous_name in dangerous_filenames:
            with patch(
                "paidsearchnav.api.v1.upload.GoogleAdsCSVParser"
            ) as mock_parser_class:
                mock_parser = Mock()
                mock_parser.parse.return_value = []
                mock_parser_class.return_value = mock_parser

                response = await async_client.post(
                    "/api/v1/upload/csv",
                    params={"data_type": "keywords"},
                    files={"file": (dangerous_name, csv_content, "text/csv")},
                )

                assert response.status_code == 200
                # Check that the filename was sanitized
                assert "../" not in response.json()["filename"]
                assert "<script>" not in response.json()["filename"]
                assert "|" not in response.json()["filename"]
                assert "\x00" not in response.json()["filename"]

    async def test_upload_only_empty_rows(self, async_client: AsyncClient):
        """Test upload with CSV containing headers but only empty data rows."""
        csv_content = """Keyword,Campaign,Cost
,,
,,
,,"""

        csv_file = io.BytesIO(csv_content.encode())

        with patch(
            "paidsearchnav.api.v1.upload.GoogleAdsCSVParser"
        ) as mock_parser_class:
            mock_parser = Mock()
            mock_parser.parse.side_effect = ValueError(
                "CSV file contains only empty rows"
            )
            mock_parser_class.return_value = mock_parser

            response = await async_client.post(
                "/api/v1/upload/csv",
                params={"data_type": "keywords"},
                files={"file": ("empty_rows.csv", csv_file, "text/csv")},
            )

        assert response.status_code == 400
        assert (
            "CSV file is empty or contains no valid data rows"
            in response.json()["detail"]
        )
