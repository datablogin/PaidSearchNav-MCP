"""CSV export implementation with pagination support for large datasets."""

import asyncio
import csv
import logging
import os
import uuid
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from typing import Any, AsyncIterator, Callable, Dict, List, Optional

import aiofiles
import psutil

from .base import (
    ExportFormat,
    ExportProgress,
    ExportResult,
    ExportStatus,
    PaginationConfig,
)

logger = logging.getLogger(__name__)


class CSVExporter:
    """Export data to CSV files with proper formatting and error handling."""

    def __init__(
        self,
        output_dir: Optional[Path] = None,
        pagination_config: Optional[PaginationConfig] = None,
    ):
        """Initialize CSV exporter.

        Args:
            output_dir: Directory to save CSV files (defaults to current working
                directory).
            pagination_config: Pagination configuration for handling large datasets.
        """
        self.output_dir = output_dir or Path.cwd()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.pagination_config = pagination_config or PaginationConfig()
        self._process = psutil.Process(os.getpid())

    async def export_batch(
        self,
        customer_id: str,
        data: Dict[str, List[Dict[str, Any]]],
        metadata: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[Callable] = None,
    ) -> ExportResult:
        """Export batch data to CSV files with pagination support.

        Args:
            customer_id: Customer identifier
            data: Dictionary mapping table names to list of records
            metadata: Optional metadata for the export
            progress_callback: Optional callback for progress updates

        Returns:
            Export result
        """
        export_id = (
            metadata.get("export_id", str(uuid.uuid4()))
            if metadata
            else str(uuid.uuid4())
        )
        started_at = datetime.now(timezone.utc)

        # Initialize progress tracking
        total_records_expected = sum(len(records) for records in data.values())
        current_records_processed = 0

        progress = ExportProgress(
            export_id=export_id,
            current_records=0,
            total_records=total_records_expected,
            current_batch=0,
            total_batches=len(data),
            memory_usage_mb=0.0,
            started_at=started_at,
        )

        try:
            files_created = []
            total_records = 0

            # Create timestamp for file naming
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

            # Progress callback wrapper with error handling
            def table_progress_callback(current: int, total: int):
                nonlocal current_records_processed, progress
                try:
                    progress.current_records = current_records_processed + current
                    progress.memory_usage_mb = (
                        self._process.memory_info().rss / 1024 / 1024
                    )
                    if progress_callback:
                        progress_callback(
                            progress.current_records, progress.total_records
                        )
                except Exception as e:
                    logger.warning(
                        f"Progress callback failed: {e}. Continuing export..."
                    )
                    # Continue processing even if callback fails

            for batch_idx, (table_name, records) in enumerate(data.items()):
                if not records:
                    logger.warning(f"No records to export for table {table_name}")
                    continue

                progress.current_batch = batch_idx + 1
                logger.info(
                    f"Processing table {table_name} ({len(records)} records) - "
                    f"Batch {progress.current_batch}/{progress.total_batches}"
                )

                # Generate filename
                filename = f"{customer_id}_{table_name}_{timestamp}.csv"
                filepath = self.output_dir / filename

                try:
                    # Write CSV file with progress tracking
                    records_written = await self._write_csv_file(
                        filepath, records, table_progress_callback
                    )
                    total_records += records_written
                    current_records_processed += records_written
                    files_created.append(str(filepath))

                    logger.info(
                        f"Created CSV file {filename} with {records_written} records "
                        f"({current_records_processed}/{total_records_expected} total)"
                    )
                except Exception as e:
                    logger.error(f"Failed to write table {table_name}: {e}")
                    # Clean up the partial file if it exists
                    if filepath.exists():
                        try:
                            filepath.unlink()
                            logger.info(f"Cleaned up partial file: {filepath}")
                        except Exception as cleanup_error:
                            logger.warning(
                                f"Failed to clean up partial file {filepath}: {cleanup_error}"
                            )
                    # Re-raise to trigger overall cleanup
                    raise

            # Final progress update
            progress.current_records = current_records_processed
            progress.memory_usage_mb = self._process.memory_info().rss / 1024 / 1024

            completed_at = datetime.now(timezone.utc)
            return ExportResult(
                export_id=export_id,
                status=ExportStatus.COMPLETED,
                destination=ExportFormat.CSV,
                records_exported=total_records,
                started_at=started_at,
                completed_at=completed_at,
                progress=progress,
                metadata={
                    "files_created": files_created,
                    "customer_id": customer_id,
                    "output_directory": str(self.output_dir),
                    "batches_processed": len(data),
                    "streaming_enabled": self.pagination_config.enable_streaming,
                    "batch_size": self.pagination_config.batch_size,
                    "peak_memory_mb": progress.memory_usage_mb,
                },
            )

        except Exception as e:
            logger.error(f"CSV export failed for customer {customer_id}: {e}")

            # Clean up any partially created files
            await self._cleanup_partial_export(files_created, export_id)

            return ExportResult(
                export_id=export_id,
                status=ExportStatus.FAILED,
                destination=ExportFormat.CSV,
                error_message=str(e),
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
                progress=progress,
                metadata={
                    "files_cleaned_up": len(files_created),
                    "partial_export": True,
                },
            )

    async def _cleanup_partial_export(
        self, files_created: List[str], export_id: str
    ) -> None:
        """Clean up files from a failed export.

        Args:
            files_created: List of file paths that were created during export
            export_id: Export identifier for logging
        """
        if not files_created:
            return

        logger.info(
            f"Cleaning up {len(files_created)} files from failed export {export_id}"
        )

        for file_path in files_created:
            try:
                path = Path(file_path)
                if path.exists():
                    path.unlink()
                    logger.debug(f"Cleaned up file: {file_path}")
            except Exception as e:
                logger.warning(f"Failed to clean up file {file_path}: {e}")

        logger.info(f"Cleanup completed for export {export_id}")

    async def _write_csv_file(
        self,
        filepath: Path,
        records: List[Dict[str, Any]],
        progress_callback: Optional[Callable] = None,
    ) -> int:
        """Write records to a CSV file using async operations with memory-efficient streaming.

        Args:
            filepath: Path to write the CSV file
            records: List of records to write
            progress_callback: Optional callback for progress updates (current, total)

        Returns:
            Number of records written
        """
        if not records:
            return 0

        # Get headers from the first record
        headers = list(records[0].keys())
        total_records = len(records)

        # Use streaming approach for large datasets
        if (
            total_records > self.pagination_config.batch_size
            and self.pagination_config.enable_streaming
        ):
            return await self._write_csv_streaming(
                filepath, headers, records, progress_callback
            )
        else:
            # Use memory approach for smaller datasets
            csv_content = await self._generate_csv_content(
                headers, records, progress_callback
            )
            async with aiofiles.open(filepath, "w", encoding="utf-8") as csvfile:
                await csvfile.write(csv_content)
            return len(records)

    async def _generate_csv_content(
        self,
        headers: List[str],
        records: List[Dict[str, Any]],
        progress_callback: Optional[Callable] = None,
    ) -> str:
        """Generate CSV content asynchronously.

        Args:
            headers: Column headers
            records: List of records to write
            progress_callback: Optional callback for progress updates

        Returns:
            CSV content as string
        """
        # Use StringIO to generate CSV content in memory
        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=headers)
        writer.writeheader()

        for i, record in enumerate(records):
            # Clean record data for CSV output
            cleaned_record = self._clean_record_for_csv(record)
            writer.writerow(cleaned_record)

            # Update progress and yield control periodically
            if (
                progress_callback
                and i % self.pagination_config.progress_callback_interval == 0
            ):
                try:
                    progress_callback(i + 1, len(records))
                except Exception as e:
                    logger.warning(
                        f"Progress callback failed during CSV generation: {e}"
                    )
                await asyncio.sleep(0)

        # Final progress update
        if progress_callback:
            try:
                progress_callback(len(records), len(records))
            except Exception as e:
                logger.warning(f"Final progress callback failed: {e}")

        return output.getvalue()

    def _clean_record_for_csv(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Clean a record for CSV output by handling special characters and types.

        Args:
            record: Original record

        Returns:
            Cleaned record safe for CSV output
        """
        cleaned = {}

        for key, value in record.items():
            if value is None:
                cleaned[key] = ""
            elif isinstance(value, (dict, list)):
                # Convert complex types to string representation
                cleaned[key] = str(value)
            elif isinstance(value, bool):
                cleaned[key] = "true" if value else "false"
            elif isinstance(value, (int, float)):
                cleaned[key] = str(value)
            else:
                # Handle string values, escape quotes and handle newlines
                str_value = str(value)
                # Replace newlines with spaces
                str_value = str_value.replace("\n", " ").replace("\r", " ")
                # Remove excessive whitespace
                str_value = " ".join(str_value.split())
                cleaned[key] = str_value

        return cleaned

    def export_to_string(
        self, records: List[Dict[str, Any]], include_headers: bool = True
    ) -> str:
        """Export records to CSV string format.

        Args:
            records: List of records to export
            include_headers: Whether to include header row

        Returns:
            CSV formatted string
        """
        if not records:
            return ""

        output = StringIO()
        headers = list(records[0].keys())
        writer = csv.DictWriter(output, fieldnames=headers)

        if include_headers:
            writer.writeheader()

        for record in records:
            cleaned_record = self._clean_record_for_csv(record)
            writer.writerow(cleaned_record)

        return output.getvalue()

    def get_output_directory(self) -> Path:
        """Get the configured output directory.

        Returns:
            Path to output directory
        """
        return self.output_dir

    def set_output_directory(self, output_dir: Path) -> None:
        """Set the output directory for CSV files.

        Args:
            output_dir: New output directory
        """
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"CSV output directory set to: {self.output_dir}")

    async def _write_csv_streaming(
        self,
        filepath: Path,
        headers: List[str],
        records: List[Dict[str, Any]],
        progress_callback: Optional[Callable] = None,
    ) -> int:
        """Write CSV file using streaming approach to minimize memory usage.

        Args:
            filepath: Path to write the CSV file
            headers: Column headers
            records: List of records to write
            progress_callback: Optional callback for progress updates

        Returns:
            Number of records written
        """
        records_written = 0

        async with aiofiles.open(filepath, "w", encoding="utf-8") as csvfile:
            # Write headers
            header_row = ",".join(f'"{header}"' for header in headers) + "\n"
            await csvfile.write(header_row)

            # Use true streaming with AsyncIterator for better memory efficiency
            async for batch_content, batch_size in self._stream_csv_batches(
                headers, records
            ):
                await csvfile.write(batch_content)
                records_written += batch_size

                # Update progress with error handling
                if progress_callback:
                    try:
                        progress_callback(records_written, len(records))
                    except Exception as e:
                        logger.warning(
                            f"Progress callback failed during streaming: {e}"
                        )

                # Check memory usage and yield control
                await self._check_memory_usage()
                await asyncio.sleep(0)  # Yield control to event loop

        return records_written

    async def _stream_csv_batches(
        self, headers: List[str], records: List[Dict[str, Any]]
    ) -> AsyncIterator[tuple[str, int]]:
        """Stream CSV content in batches to minimize memory usage.

        Args:
            headers: Column headers
            records: List of records to process

        Yields:
            Tuple of (csv_content, batch_size)
        """
        batch_size = self.pagination_config.batch_size

        for i in range(0, len(records), batch_size):
            batch = records[i : i + batch_size]

            # Generate CSV content for this batch without storing the full content in memory
            batch_content = await self._generate_batch_csv_content(headers, batch)

            yield batch_content, len(batch)

            # Clean up batch to free memory
            del batch
            del batch_content

    async def _generate_batch_csv_content(
        self, headers: List[str], records: List[Dict[str, Any]]
    ) -> str:
        """Generate CSV content for a batch of records.

        Args:
            headers: Column headers
            records: Batch of records to process

        Returns:
            CSV content as string without headers
        """
        if not records:
            return ""

        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=headers)

        for record in records:
            cleaned_record = self._clean_record_for_csv(record)
            writer.writerow(cleaned_record)

        return output.getvalue()

    async def _check_memory_usage(self) -> None:
        """Check current memory usage and enforce limits by raising exception if exceeded.

        Raises:
            MemoryError: If memory usage exceeds the configured limit
        """
        memory_info = self._process.memory_info()
        memory_mb = memory_info.rss / 1024 / 1024

        if memory_mb > self.pagination_config.max_memory_mb * 0.8:  # 80% threshold
            logger.warning(
                f"Memory usage approaching limit: {memory_mb:.1f}MB / {self.pagination_config.max_memory_mb}MB"
            )

        if memory_mb > self.pagination_config.max_memory_mb:
            error_msg = (
                f"Memory usage exceeded limit: {memory_mb:.1f}MB / {self.pagination_config.max_memory_mb}MB. "
                f"Export halted to prevent system instability."
            )
            logger.error(error_msg)
            raise MemoryError(error_msg)

    def update_pagination_config(self, pagination_config: PaginationConfig) -> None:
        """Update pagination configuration.

        Args:
            pagination_config: New pagination configuration
        """
        self.pagination_config = pagination_config
        logger.info(
            f"CSV pagination config updated: batch_size={pagination_config.batch_size}, "
            f"max_memory_mb={pagination_config.max_memory_mb}, "
            f"streaming={pagination_config.enable_streaming}"
        )

    async def export_paginated(
        self,
        customer_id: str,
        data_iterator: AsyncIterator[Dict[str, List[Dict[str, Any]]]],
        metadata: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[Callable] = None,
    ) -> ExportResult:
        """Export data using async iterator for true streaming support.

        Args:
            customer_id: Customer identifier
            data_iterator: Async iterator yielding batches of data
            metadata: Optional metadata for the export
            progress_callback: Optional callback for progress updates

        Returns:
            Export result
        """
        export_id = (
            metadata.get("export_id", str(uuid.uuid4()))
            if metadata
            else str(uuid.uuid4())
        )
        started_at = datetime.now(timezone.utc)

        try:
            files_created = []
            total_records = 0
            batch_count = 0

            # Create timestamp for file naming
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

            async for batch_data in data_iterator:
                batch_count += 1

                # Process each table in the batch
                for table_name, records in batch_data.items():
                    if not records:
                        continue

                    # Create unique filename for each batch
                    filename = f"{customer_id}_{table_name}_{timestamp}_batch_{batch_count}.csv"
                    filepath = self.output_dir / filename

                    # Write CSV file
                    records_written = await self._write_csv_file(
                        filepath, records, progress_callback
                    )
                    total_records += records_written
                    files_created.append(str(filepath))

                    logger.info(
                        f"Created CSV batch file {filename} with {records_written} records"
                    )

            completed_at = datetime.now(timezone.utc)
            return ExportResult(
                export_id=export_id,
                status=ExportStatus.COMPLETED,
                destination=ExportFormat.CSV,
                records_exported=total_records,
                started_at=started_at,
                completed_at=completed_at,
                metadata={
                    "files_created": files_created,
                    "customer_id": customer_id,
                    "output_directory": str(self.output_dir),
                    "batches_processed": batch_count,
                    "streaming_mode": True,
                },
            )

        except Exception as e:
            logger.error(f"Paginated CSV export failed for customer {customer_id}: {e}")
            return ExportResult(
                export_id=export_id,
                status=ExportStatus.FAILED,
                destination=ExportFormat.CSV,
                error_message=str(e),
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
            )
