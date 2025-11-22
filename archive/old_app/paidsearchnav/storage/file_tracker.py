"""File tracking utilities for analysis results and S3 integration."""

import hashlib
import logging
import mimetypes
from datetime import datetime, timezone
from pathlib import Path
from typing import Union

from sqlalchemy.ext.asyncio import AsyncSession

from paidsearchnav.core.models.audit_files import (
    FileCategory,
    S3FileReference,
)
from paidsearchnav.storage.models import AnalysisFile
from paidsearchnav.storage.s3_utils import validate_s3_path

# Configuration constants
DEFAULT_CHUNK_SIZE = 8192  # 8KB chunks for memory-efficient file processing
MAX_FILE_SIZE_FOR_CHECKSUM = 100 * 1024 * 1024  # 100MB limit for checksum calculation

logger = logging.getLogger(__name__)


class FileTracker:
    """Utility class for tracking files associated with analysis results."""

    def __init__(self, session: AsyncSession):
        """Initialize file tracker with database session.

        Args:
            session: Async database session
        """
        self.session = session

    @staticmethod
    def calculate_checksum(
        file_path: Union[str, Path],
        algorithm: str = "md5",
        max_size: int = MAX_FILE_SIZE_FOR_CHECKSUM,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
    ) -> str:
        """Calculate checksum for a file with memory efficiency.

        Args:
            file_path: Path to the file
            algorithm: Hash algorithm to use ('md5' or 'sha256')
            max_size: Maximum file size to process (bytes)
            chunk_size: Size of chunks to read at once (bytes)

        Returns:
            Hexadecimal checksum string

        Raises:
            ValueError: If algorithm is not supported or file too large
            FileNotFoundError: If file doesn't exist
            OSError: If file cannot be read
        """
        if algorithm not in ["md5", "sha256"]:
            raise ValueError("Algorithm must be 'md5' or 'sha256'")

        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Check file size before processing
        file_size = file_path.stat().st_size
        if file_size > max_size:
            raise ValueError(
                f"File too large for checksum calculation: {file_size} bytes "
                f"(max: {max_size} bytes)"
            )

        hash_obj = hashlib.md5() if algorithm == "md5" else hashlib.sha256()

        try:
            with open(file_path, "rb") as f:
                # Use configurable chunk size for memory efficiency
                for chunk in iter(lambda: f.read(chunk_size), b""):
                    hash_obj.update(chunk)
        except OSError as e:
            raise OSError(f"Error reading file {file_path}: {e}")

        return hash_obj.hexdigest()

    @staticmethod
    def determine_content_type(file_path: Union[str, Path]) -> str:
        """Determine MIME content type for a file.

        Args:
            file_path: Path to the file

        Returns:
            MIME content type string
        """
        file_path = Path(file_path)
        content_type, _ = mimetypes.guess_type(str(file_path))
        return content_type or "application/octet-stream"

    @staticmethod
    def categorize_file(file_name: str, file_path: str = "") -> FileCategory:
        """Automatically categorize a file based on name and path.

        Args:
            file_name: Name of the file
            file_path: Full path to the file (optional)

        Returns:
            FileCategory enum value
        """
        file_name_lower = file_name.lower()
        file_path_lower = file_path.lower()

        # Check path-based categorization first
        if "/input" in file_path_lower or "/inputs" in file_path_lower:
            if file_name_lower.endswith(".csv"):
                return FileCategory.INPUT_CSV
            elif "keyword" in file_name_lower:
                return FileCategory.INPUT_KEYWORDS
            elif "search_term" in file_name_lower or "search-term" in file_name_lower:
                return FileCategory.INPUT_SEARCH_TERMS

        elif "/output" in file_path_lower or "/outputs" in file_path_lower:
            if "report" in file_name_lower or "summary" in file_name_lower:
                if file_name_lower.endswith((".pdf", ".html", ".xlsx")):
                    return FileCategory.OUTPUT_REPORT
                else:
                    return FileCategory.OUTPUT_SUMMARY
            elif "actionable" in file_path_lower or "script" in file_name_lower:
                return FileCategory.OUTPUT_ACTIONABLE
            elif file_name_lower.endswith(".js"):
                return FileCategory.OUTPUT_SCRIPTS

        # File name-based categorization
        if file_name_lower.endswith(".csv"):
            return FileCategory.INPUT_CSV
        elif (
            file_name_lower.endswith((".pdf", ".html", ".xlsx"))
            and "report" in file_name_lower
        ):
            return FileCategory.OUTPUT_REPORT
        elif file_name_lower.endswith((".js", ".txt")) and (
            "script" in file_name_lower or "actionable" in file_name_lower
        ):
            return FileCategory.OUTPUT_ACTIONABLE
        elif file_name_lower.endswith((".log", ".txt")) and "log" in file_name_lower:
            return FileCategory.AUDIT_LOG
        elif "summary" in file_name_lower:
            return FileCategory.OUTPUT_SUMMARY

        return FileCategory.OTHER

    async def create_file_reference(
        self,
        file_path: str,
        file_name: str,
        file_size: int,
        checksum: str = None,
        content_type: str = None,
        file_category: FileCategory = None,
        metadata: dict = None,
    ) -> S3FileReference:
        """Create an S3FileReference from file information.

        Args:
            file_path: Full S3 path to the file
            file_name: Name of the file
            file_size: Size of the file in bytes
            checksum: File checksum (optional, will be calculated if None)
            content_type: MIME content type (optional, will be determined if None)
            file_category: File category (optional, will be categorized if None)
            metadata: Additional metadata (optional)

        Returns:
            S3FileReference instance

        Raises:
            ValueError: If file_path is invalid
        """
        # Validate S3 path
        validate_s3_path(file_path)

        # Determine content type if not provided
        if content_type is None:
            content_type = self.determine_content_type(file_name)

        # Categorize file if not provided
        if file_category is None:
            file_category = self.categorize_file(file_name, file_path)

        # Use empty checksum if not provided (for S3 files we can't calculate locally)
        if checksum is None:
            checksum = ""

        return S3FileReference(
            file_path=file_path,
            file_name=file_name,
            file_size=file_size,
            content_type=content_type,
            checksum=checksum,
            upload_timestamp=datetime.now(timezone.utc),
            file_category=file_category,
            metadata=metadata or {},
        )

    async def track_analysis_file(
        self,
        analysis_id: str,
        file_reference: S3FileReference,
    ) -> AnalysisFile:
        """Track a file in the database for an analysis.

        Args:
            analysis_id: Analysis ID to associate the file with
            file_reference: S3 file reference information

        Returns:
            Created AnalysisFile database record

        Raises:
            ValueError: If analysis_id is invalid or file_reference is incomplete
        """
        if not analysis_id or not analysis_id.strip():
            raise ValueError("Analysis ID cannot be empty")

        # Create database record
        # Handle both enum and string values for file_category
        if isinstance(file_reference.file_category, FileCategory):
            category_value = file_reference.file_category.value
        else:
            category_value = file_reference.file_category

        analysis_file = AnalysisFile(
            analysis_id=analysis_id,
            file_path=file_reference.file_path,
            file_name=file_reference.file_name,
            file_category=category_value,
            file_size=file_reference.file_size,
            content_type=file_reference.content_type,
            checksum=file_reference.checksum,
            file_metadata=file_reference.metadata,
        )

        self.session.add(analysis_file)
        await self.session.flush()  # Flush to get the ID

        logger.info(
            f"Tracked file {file_reference.file_name} "
            f"({category_value}) for analysis {analysis_id}"
        )

        return analysis_file

    async def get_analysis_files(
        self, analysis_id: str, file_category: FileCategory = None
    ) -> list[AnalysisFile]:
        """Get all files tracked for an analysis.

        Args:
            analysis_id: Analysis ID to get files for
            file_category: Optional category filter

        Returns:
            List of AnalysisFile records
        """
        from sqlalchemy import select

        stmt = select(AnalysisFile).where(AnalysisFile.analysis_id == analysis_id)

        if file_category:
            stmt = stmt.where(AnalysisFile.file_category == file_category.value)

        stmt = stmt.order_by(AnalysisFile.created_at)

        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_files_by_category(
        self, analysis_id: str, file_category: FileCategory
    ) -> list[S3FileReference]:
        """Get S3FileReference objects for files of a specific category.

        Args:
            analysis_id: Analysis ID to get files for
            file_category: Category to filter by

        Returns:
            List of S3FileReference objects
        """
        analysis_files = await self.get_analysis_files(analysis_id, file_category)

        references = []
        for af in analysis_files:
            reference = S3FileReference(
                file_path=af.file_path,
                file_name=af.file_name,
                file_size=af.file_size,
                content_type=af.content_type or "application/octet-stream",
                checksum=af.checksum or "",
                upload_timestamp=af.created_at,
                file_category=FileCategory(af.file_category),
                metadata=af.file_metadata or {},
            )
            references.append(reference)

        return references

    async def get_files_by_categories(
        self, analysis_id: str, file_categories: list[FileCategory]
    ) -> dict[FileCategory, list[S3FileReference]]:
        """Get S3FileReference objects for multiple categories efficiently.

        Args:
            analysis_id: Analysis ID to get files for
            file_categories: List of categories to filter by

        Returns:
            Dictionary mapping categories to their files
        """
        if not file_categories:
            return {}

        # Get all files for the categories in a single query
        category_values = [cat.value for cat in file_categories]
        analysis_files = await self.get_analysis_files(analysis_id)

        # Filter by categories
        filtered_files = [
            af for af in analysis_files if af.file_category in category_values
        ]

        # Group files by category
        result = {cat: [] for cat in file_categories}
        for af in filtered_files:
            category = FileCategory(af.file_category)
            if category in file_categories:
                reference = S3FileReference(
                    file_path=af.file_path,
                    file_name=af.file_name,
                    file_size=af.file_size,
                    content_type=af.content_type or "application/octet-stream",
                    checksum=af.checksum or "",
                    upload_timestamp=af.created_at,
                    file_category=category,
                    metadata=af.file_metadata or {},
                )
                result[category].append(reference)

        return result

    async def delete_analysis_files(self, analysis_id: str) -> int:
        """Delete all file tracking records for an analysis.

        Args:
            analysis_id: Analysis ID to delete files for

        Returns:
            Number of files deleted
        """
        from sqlalchemy import delete

        stmt = delete(AnalysisFile).where(AnalysisFile.analysis_id == analysis_id)
        result = await self.session.execute(stmt)

        deleted_count = result.rowcount
        logger.info(f"Deleted {deleted_count} file records for analysis {analysis_id}")

        return deleted_count

    async def get_orphaned_files(self) -> list[AnalysisFile]:
        """Find file records that reference non-existent analyses.

        Returns:
            List of orphaned AnalysisFile records
        """
        from sqlalchemy import select

        from paidsearchnav.storage.models import AnalysisRecord

        # Find analysis files that don't have corresponding analysis records
        stmt = (
            select(AnalysisFile)
            .outerjoin(AnalysisRecord, AnalysisFile.analysis_id == AnalysisRecord.id)
            .where(AnalysisRecord.id.is_(None))
            .order_by(AnalysisFile.created_at)
        )

        result = await self.session.execute(stmt)
        orphaned_files = result.scalars().all()

        if orphaned_files:
            logger.warning(f"Found {len(orphaned_files)} orphaned file records")

        return orphaned_files

    async def cleanup_orphaned_files(self) -> int:
        """Delete orphaned file records.

        Returns:
            Number of orphaned records deleted
        """
        orphaned_files = await self.get_orphaned_files()

        if not orphaned_files:
            return 0

        from sqlalchemy import delete

        orphaned_ids = [f.id for f in orphaned_files]
        stmt = delete(AnalysisFile).where(AnalysisFile.id.in_(orphaned_ids))

        result = await self.session.execute(stmt)
        deleted_count = result.rowcount

        logger.info(f"Cleaned up {deleted_count} orphaned file records")
        return deleted_count
