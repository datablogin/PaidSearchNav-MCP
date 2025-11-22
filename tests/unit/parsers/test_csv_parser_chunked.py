"""Tests for chunked CSV parsing functionality."""

import csv
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from paidsearchnav_mcp.parsers.csv_parser import GoogleAdsCSVParser


class TestChunkedCSVParsing:
    """Test chunked CSV parsing for large files."""

    def test_chunked_parsing_is_used_for_large_files(self):
        """Test that chunked parsing is automatically enabled for large files."""
        # Create a file just over the threshold (50MB)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            writer = csv.writer(f)
            writer.writerow(["text", "number"])

            # Write enough data to exceed 50MB threshold
            # Each row is approximately 100 bytes with padding
            padding = "x" * 80  # Add padding to ensure sufficient size
            rows_needed = (51 * 1024 * 1024) // 100  # 51MB / 100 bytes per row
            for i in range(rows_needed):
                writer.writerow([f"Row {i} {padding}", str(i)])

            temp_path = Path(f.name)

        try:
            parser = GoogleAdsCSVParser(file_type="default", strict_validation=False)

            # Spy on parse_chunked method
            original_parse_chunked = parser.parse_chunked
            parser.parse_chunked = MagicMock(return_value=[])

            # Parse should call parse_chunked for large file
            parser.parse(temp_path)
            parser.parse_chunked.assert_called_once()

        finally:
            if temp_path.exists():
                temp_path.unlink()

    def test_chunked_parsing_not_used_for_small_files(self):
        """Test that chunked parsing is not used for small files."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            writer = csv.writer(f)
            writer.writerow(["text", "number"])

            # Write small amount of data
            for i in range(100):
                writer.writerow([f"row {i}", str(i)])

            temp_path = Path(f.name)

        try:
            parser = GoogleAdsCSVParser(file_type="default", strict_validation=False)

            # Spy on parse_chunked method
            parser.parse_chunked = MagicMock()

            # Parse should NOT call parse_chunked for small file
            records = parser.parse(temp_path)
            parser.parse_chunked.assert_not_called()
            assert len(records) == 100

        finally:
            if temp_path.exists():
                temp_path.unlink()

    def test_force_chunked_parsing(self):
        """Test that chunked parsing can be forced with use_chunked_reading=True."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            writer = csv.writer(f)
            writer.writerow(["text", "number"])

            # Write small amount of data
            for i in range(100):
                writer.writerow([f"row {i}", str(i)])

            temp_path = Path(f.name)

        try:
            parser = GoogleAdsCSVParser(
                file_type="default",
                strict_validation=False,
                use_chunked_reading=True,  # Force chunked reading
            )

            # Spy on parse_chunked method
            original_parse_chunked = parser.parse_chunked
            called = False

            def mock_parse_chunked(*args, **kwargs):
                nonlocal called
                called = True
                return original_parse_chunked(*args, **kwargs)

            parser.parse_chunked = mock_parse_chunked

            # Parse should call parse_chunked even for small file
            records = parser.parse(temp_path)
            assert called
            assert len(records) == 100

        finally:
            if temp_path.exists():
                temp_path.unlink()

    def test_progress_callback_functionality(self):
        """Test that progress callback is called correctly."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            writer = csv.writer(f)
            writer.writerow(["Campaign", "Keyword", "Impressions"])

            # Write data that will be processed in chunks
            for i in range(25000):  # More than 2 chunks with default chunk size
                writer.writerow([f"Campaign{i}", f"keyword{i}", str(i * 100)])

            temp_path = Path(f.name)

        try:
            parser = GoogleAdsCSVParser(
                file_type="default",
                strict_validation=False,
                chunk_size=10000,
                use_chunked_reading=True,
            )

            progress_updates = []

            def progress_callback(processed, total):
                progress_updates.append((processed, total))

            # Parse with progress callback
            records = parser.parse(temp_path, progress_callback=progress_callback)

            # Should have multiple progress updates
            assert len(progress_updates) > 0

            # Progress should increase
            if len(progress_updates) > 1:
                for i in range(1, len(progress_updates)):
                    assert progress_updates[i][0] >= progress_updates[i - 1][0]

            # Final progress should match total records
            last_processed, last_total = progress_updates[-1]
            assert last_processed == 25000
            assert last_processed == len(records)

        finally:
            if temp_path.exists():
                temp_path.unlink()

    def test_memory_monitoring_logs(self):
        """Test that memory usage is logged during chunked parsing."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            writer = csv.writer(f)
            writer.writerow(["text"])

            # Write enough for multiple chunks
            for i in range(50000):
                writer.writerow([f"row {i}"])

            temp_path = Path(f.name)

        try:
            parser = GoogleAdsCSVParser(
                file_type="default",
                strict_validation=False,
                chunk_size=5000,
                use_chunked_reading=True,
            )

            # Mock logger to capture memory logs
            with patch("paidsearchnav.parsers.csv_parser.logger") as mock_logger:
                records = parser.parse(temp_path)

                # Check for memory usage logs
                info_calls = [str(call) for call in mock_logger.info.call_args_list]
                assert any("Initial memory usage" in call for call in info_calls)
                assert any("Final memory usage" in call for call in info_calls)
                assert len(records) == 50000

        finally:
            if temp_path.exists():
                temp_path.unlink()

    def test_dtype_optimization_applied(self):
        """Test that dtype optimizations are applied during chunked reading."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            writer = csv.writer(f)
            writer.writerow(["Campaign ID", "Impressions", "Cost", "Match Type"])

            for i in range(1000):
                writer.writerow([str(1000 + i), str(i * 100), f"{i * 0.5}", "EXACT"])

            temp_path = Path(f.name)

        try:
            parser = GoogleAdsCSVParser(
                file_type="default", strict_validation=False, use_chunked_reading=True
            )

            # Test dtype preparation
            dtype_spec = parser._prepare_dtype_spec(temp_path)

            # ID columns should be string
            assert dtype_spec.get("Campaign ID") is str

            # Numeric columns should have appropriate types
            assert dtype_spec.get("Impressions") == "Int64"
            assert dtype_spec.get("Cost") == "float64"

            # Categorical columns
            assert dtype_spec.get("Match Type") == "category"

            # Parse and verify data types are preserved
            records = parser.parse(temp_path)
            assert len(records) == 1000

            # Check first record
            first_record = records[0]
            assert isinstance(first_record["Campaign ID"], str)
            assert first_record["Campaign ID"] == "1000"

        finally:
            if temp_path.exists():
                temp_path.unlink()
