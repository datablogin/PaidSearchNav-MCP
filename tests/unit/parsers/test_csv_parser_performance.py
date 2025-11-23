"""Performance tests for large CSV file handling."""

import csv
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from paidsearchnav_mcp.parsers.csv_parser import GoogleAdsCSVParser


class TestCSVParserPerformance:
    """Test performance optimizations for large CSV files."""

    @pytest.fixture
    def large_csv_file(self):
        """Create a large temporary CSV file for testing."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            # Write header - matching expected keyword CSV format
            headers = [
                "Campaign ID",
                "Campaign",
                "Ad group ID",
                "Ad group",
                "Keyword ID",
                "Keyword",
                "Match type",
                "Status",
                "Impressions",
                "Clicks",
                "Cost",
                "Conversions",
                "Quality Score",
            ]
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()

            # Write 10k rows (optimized for CI)
            for i in range(10000):
                writer.writerow(
                    {
                        "Campaign ID": str(1000 + (i % 100)),
                        "Campaign": f"Campaign {i % 100}",
                        "Ad group ID": str(2000 + (i % 1000)),
                        "Ad group": f"Ad Group {i % 1000}",
                        "Keyword ID": str(3000 + i),
                        "Keyword": f"keyword {i}",
                        "Match type": ["EXACT", "PHRASE", "BROAD"][i % 3],
                        "Status": "ENABLED",
                        "Impressions": str(i * 10),
                        "Clicks": str(i),
                        "Cost": f"{i * 0.5:.2f}",
                        "Conversions": str(i // 100),
                        "Quality Score": str((i % 10) + 1),
                    }
                )

            temp_path = Path(f.name)

        yield temp_path

        # Cleanup
        if temp_path.exists():
            temp_path.unlink()

    def test_chunked_reading_memory_efficiency(self, large_csv_file):
        """Test that chunked reading uses less memory than regular parsing."""
        parser = GoogleAdsCSVParser(
            file_type="keywords",
            chunk_size=5000,
            use_chunked_reading=True,
            strict_validation=False,
        )

        # Get initial memory
        initial_memory = parser.get_memory_usage()

        # Parse the file
        records = parser.parse(large_csv_file)

        # Get final memory
        final_memory = parser.get_memory_usage()
        memory_increase = final_memory["rss"] - initial_memory["rss"]

        # Memory increase should be reasonable (less than 500MB for 100k rows)
        assert memory_increase < 500, (
            f"Memory usage increased by {memory_increase:.2f} MB"
        )
        assert len(records) == 10000

    def test_progress_callback(self, large_csv_file):
        """Test that progress callback is called during chunked reading."""
        parser = GoogleAdsCSVParser(
            file_type="keywords",
            chunk_size=10000,
            use_chunked_reading=True,
            strict_validation=False,
        )

        progress_updates = []

        def progress_callback(processed, total):
            progress_updates.append((processed, total))

        # Parse with progress callback
        records = parser.parse(large_csv_file, progress_callback=progress_callback)

        # Should have received progress updates
        assert len(progress_updates) > 0

        # Last update should show all rows processed
        last_processed, last_total = progress_updates[-1]
        assert last_processed == 10000
        assert last_total == 10000

    def test_automatic_chunked_reading_threshold(self):
        """Test that chunked reading is automatically enabled for large files."""
        # Create a file that's just over the threshold
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            # Write header
            writer = csv.writer(f)
            writer.writerow(["Campaign", "Keyword", "Impressions"])

            # Write enough data to exceed 50MB threshold
            # Each row is approximately 40 bytes based on actual output
            rows_needed = (51 * 1024 * 1024) // 40  # 51MB / 40 bytes per row
            for i in range(rows_needed):
                writer.writerow([f"Campaign{i}", f"keyword{i}", str(i * 100)])

            temp_path = Path(f.name)

        try:
            # Verify file size is actually > 50MB
            actual_size = temp_path.stat().st_size
            assert actual_size > 50 * 1024 * 1024, (
                f"File size {actual_size} is not > 50MB"
            )

            parser = GoogleAdsCSVParser(file_type="default", strict_validation=False)

            # Mock parse_chunked to verify it's called
            with patch.object(parser, "parse_chunked", return_value=[]) as mock_chunked:
                parser.parse(temp_path)
                mock_chunked.assert_called_once()

        finally:
            if temp_path.exists():
                temp_path.unlink()

    def test_dtype_optimization(self, large_csv_file):
        """Test that dtype specifications improve performance."""
        parser = GoogleAdsCSVParser(
            file_type="keywords", chunk_size=10000, use_chunked_reading=True
        )

        # Test _prepare_dtype_spec
        dtype_spec = parser._prepare_dtype_spec(large_csv_file)

        # Should have dtype specifications for known columns
        assert "Impressions" in dtype_spec
        assert dtype_spec["Impressions"] == "Int64"
        assert "Cost" in dtype_spec
        assert dtype_spec["Cost"] == "float64"
        assert "Match type" in dtype_spec
        assert dtype_spec["Match type"] == "category"

    def test_performance_benchmark(self, large_csv_file):
        """Benchmark parsing performance for large files."""
        parser = GoogleAdsCSVParser(
            file_type="keywords",
            chunk_size=10000,
            use_chunked_reading=True,
            strict_validation=False,  # Skip validation for speed
        )

        start_time = time.time()
        records = parser.parse(large_csv_file)
        elapsed_time = time.time() - start_time

        # Should parse 100k rows in under 60 seconds
        assert elapsed_time < 60, f"Parsing took {elapsed_time:.2f} seconds"
        assert len(records) == 10000

        # Calculate rows per second
        rows_per_second = len(records) / elapsed_time
        print(f"Performance: {rows_per_second:.0f} rows/second")

    def test_memory_monitoring(self, large_csv_file):
        """Test memory usage monitoring during parsing."""
        parser = GoogleAdsCSVParser(
            file_type="keywords", chunk_size=5000, use_chunked_reading=True
        )

        # Mock logger to capture memory warnings
        with patch("paidsearchnav.parsers.csv_parser.logger") as mock_logger:
            records = parser.parse(large_csv_file)

            # Should log initial and final memory usage
            info_calls = [call for call in mock_logger.info.call_args_list]
            assert any("Initial memory usage" in str(call) for call in info_calls)
            assert any("Final memory usage" in str(call) for call in info_calls)

    def test_encoding_detection_performance(self):
        """Test that encoding detection doesn't read entire large files."""
        # Create a large file with non-UTF8 encoding
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="latin-1"
        ) as f:
            writer = csv.writer(f)
            writer.writerow(["Campaign", "Keyword", "Cost"])

            # Write many rows with latin-1 special characters
            for i in range(50000):
                writer.writerow([f"Campaign{i}", f"keyword{i}", f"{i}£"])

            temp_path = Path(f.name)

        try:
            parser = GoogleAdsCSVParser(
                file_type="keywords",
                encoding="utf-8",  # Wrong encoding
                use_chunked_reading=True,
            )

            # Should detect encoding without reading entire file
            start_time = time.time()

            # This will fail with UTF-8 and trigger encoding detection
            with pytest.raises((ValueError, UnicodeDecodeError)):
                parser.parse(temp_path)

            elapsed_time = time.time() - start_time

            # Encoding detection should be fast (under 1 second)
            assert elapsed_time < 1.0

        finally:
            if temp_path.exists():
                temp_path.unlink()

    @pytest.mark.parametrize("chunk_size", [1000, 5000, 10000, 50000])
    def test_chunk_size_impact(self, chunk_size):
        """Test impact of different chunk sizes on performance."""
        # Create a medium-sized test file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            writer = csv.writer(f)
            writer.writerow(["Campaign", "Keyword", "Impressions"])

            for i in range(50000):
                writer.writerow([f"Campaign{i}", f"keyword{i}", str(i * 100)])

            temp_path = Path(f.name)

        try:
            parser = GoogleAdsCSVParser(
                file_type="default",
                chunk_size=chunk_size,
                use_chunked_reading=True,
                strict_validation=False,
            )

            start_time = time.time()
            records = parser.parse(temp_path)
            elapsed_time = time.time() - start_time

            assert len(records) == 50000
            print(f"Chunk size {chunk_size}: {elapsed_time:.2f} seconds")

        finally:
            if temp_path.exists():
                temp_path.unlink()
