"""Repository implementation for storing analysis results."""

import logging
import re
from datetime import datetime
from urllib.parse import urlparse, urlunparse

from sqlalchemy import and_, create_engine, desc, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker

from paidsearchnav.core.config import Settings
from paidsearchnav.core.interfaces import Storage
from paidsearchnav.core.models.analysis import AnalysisResult
from paidsearchnav.storage.models import AnalysisRecord, Base, Customer
from paidsearchnav.storage.session_metrics import get_session_metrics

logger = logging.getLogger(__name__)


# Security and validation constants
class SecurityConfig:
    """Security configuration constants."""

    MAX_STRING_LENGTH = 255
    MAX_ANALYSIS_TYPE_LENGTH = 50
    MAX_ANALYZER_NAME_LENGTH = 100
    MIN_CUSTOMER_ID_LENGTH = 8
    MAX_CUSTOMER_ID_LENGTH = 12
    MAX_QUERY_LIMIT = 1000

    # SQL injection patterns using regex for more precise detection
    SQL_INJECTION_PATTERNS = [
        r";\s*(DROP|DELETE|UPDATE|INSERT|ALTER|CREATE|TRUNCATE)\s+",  # Dangerous SQL commands after semicolon
        r"\bUNION\s+SELECT\b",  # Union-based injection
        r"--\s*$",  # SQL comments at end of line
        r"/\*.*?\*/",  # SQL block comments
        r'\b(OR|AND)\s+[\'"]?\d+[\'"]?\s*=\s*[\'"]?\d+[\'"]?',  # Boolean-based injection
    ]


def _detect_sql_injection(value: str) -> bool:
    """Detect potential SQL injection patterns using regex."""
    for pattern in SecurityConfig.SQL_INJECTION_PATTERNS:
        if re.search(pattern, value, re.IGNORECASE):
            return True
    return False


def _validate_string_input(value: str, field_name: str, max_length: int = None) -> str:
    """Validate string input to prevent injection attacks."""
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")

    # Use default max length from config if not specified
    if max_length is None:
        max_length = SecurityConfig.MAX_STRING_LENGTH

    if len(value) > max_length:
        raise ValueError(f"{field_name} cannot exceed {max_length} characters")

    # Check for SQL injection patterns
    if _detect_sql_injection(value):
        logger.warning(
            f"Potential SQL injection attempt detected in {field_name}: {value[:50]}..."
        )
        raise ValueError(f"{field_name} contains potentially malicious SQL patterns")

    return value.strip()


def _convert_postgres_url_scheme(url: str, target_scheme: str) -> str:
    """Convert PostgreSQL URL scheme properly using urllib.parse.

    Args:
        url: Database URL to convert
        target_scheme: Target scheme ('postgresql' or 'postgresql+asyncpg')

    Returns:
        Converted URL with new scheme
    """
    if not url or not url.startswith(("postgresql://", "postgresql+asyncpg://")):
        return url

    parsed = urlparse(url)

    # Replace the scheme portion
    new_parsed = parsed._replace(scheme=target_scheme)
    return urlunparse(new_parsed)


def _validate_customer_id(customer_id: str) -> str:
    """Validate Google Ads customer ID format.

    Google Ads customer IDs are typically 8-12 digits, sometimes with hyphens.
    Examples: 123-456-7890, 1234567890, 12345678
    """
    if not customer_id or not customer_id.strip():
        raise ValueError("Customer ID cannot be empty")

    # Clean and validate format
    cleaned_id = customer_id.replace("-", "").strip()
    if not cleaned_id.isdigit():
        raise ValueError("Customer ID must contain only digits and hyphens")

    # More flexible length validation based on actual Google Ads customer ID formats
    if (
        len(cleaned_id) < SecurityConfig.MIN_CUSTOMER_ID_LENGTH
        or len(cleaned_id) > SecurityConfig.MAX_CUSTOMER_ID_LENGTH
    ):
        raise ValueError(
            f"Customer ID must be between {SecurityConfig.MIN_CUSTOMER_ID_LENGTH} and {SecurityConfig.MAX_CUSTOMER_ID_LENGTH} digits"
        )

    return cleaned_id


class AnalysisRepository(Storage):
    """SQLAlchemy-based storage implementation."""

    def __init__(self, settings: Settings):
        """Initialize the repository with database connection."""
        self.settings = settings

        # Configure session metrics based on settings
        self.session_metrics = get_session_metrics()
        if hasattr(settings.logging, "session_logging"):
            self.session_metrics.enabled = settings.logging.session_logging.enabled
            self.session_metrics.log_interval = (
                settings.logging.session_logging.metrics_interval
            )
            self.detailed_logging = settings.logging.session_logging.detailed_logging
        else:
            self.detailed_logging = False

        # Determine database URL based on storage configuration
        if settings.storage.connection_string:
            # Use configured connection string (PostgreSQL or other)
            connection_string = settings.storage.connection_string.get_secret_value()

            # Ensure we have proper sync and async URLs using proper URL parsing
            if connection_string.startswith("postgresql+asyncpg://"):
                # Convert async URL to sync for sync engine
                db_url = _convert_postgres_url_scheme(
                    connection_string, "postgresql+pg8000"
                )
                async_db_url = connection_string
            elif connection_string.startswith("postgresql://"):
                # Standard PostgreSQL URL - use pg8000 for sync, create async version
                db_url = _convert_postgres_url_scheme(
                    connection_string, "postgresql+pg8000"
                )
                async_db_url = _convert_postgres_url_scheme(
                    connection_string, "postgresql+asyncpg"
                )
            else:
                # For other databases, handle SQLite specifically
                if connection_string.startswith("sqlite:///"):
                    db_url = connection_string
                    async_db_url = connection_string.replace(
                        "sqlite:///", "sqlite+aiosqlite:///"
                    )
                elif connection_string.startswith("sqlite+aiosqlite:///"):
                    db_url = connection_string.replace(
                        "sqlite+aiosqlite:///", "sqlite:///"
                    )
                    async_db_url = connection_string
                else:
                    # For other databases, use the same URL
                    db_url = connection_string
                    async_db_url = connection_string
        elif settings.environment in ["production", "prod"]:
            # Fallback to legacy database_url for production
            fallback_url = (
                settings.database_url.get_secret_value()
                if settings.database_url
                else None
            )
            fallback_url = fallback_url or self._build_postgres_url()

            # Ensure proper sync/async URLs using proper URL parsing
            if fallback_url.startswith("postgresql+asyncpg://"):
                db_url = _convert_postgres_url_scheme(fallback_url, "postgresql+pg8000")
                async_db_url = fallback_url
            elif fallback_url.startswith("sqlite:///"):
                db_url = fallback_url
                async_db_url = fallback_url.replace(
                    "sqlite:///", "sqlite+aiosqlite:///"
                )
            elif fallback_url.startswith("sqlite+aiosqlite:///"):
                db_url = fallback_url.replace("sqlite+aiosqlite:///", "sqlite:///")
                async_db_url = fallback_url
            else:
                # Assume PostgreSQL
                db_url = _convert_postgres_url_scheme(fallback_url, "postgresql+pg8000")
                async_db_url = _convert_postgres_url_scheme(
                    fallback_url, "postgresql+asyncpg"
                )
        else:
            # Use SQLite for development (fallback)
            db_path = settings.data_dir / "paidsearchnav.db"
            db_url = f"sqlite:///{db_path}"
            async_db_url = f"sqlite+aiosqlite:///{db_path}"

        # Create engines with connection pooling
        engine_kwargs = {
            "echo": settings.debug,
            "pool_size": 5,
            "max_overflow": 10,
            "pool_timeout": 30,
            "pool_recycle": 3600,  # Recycle connections after 1 hour
            "pool_pre_ping": True,  # Verify connections before using
        }

        # SQLite doesn't support connection pooling the same way
        if db_url.startswith("sqlite"):
            # Remove pooling options for SQLite
            engine_kwargs = {"echo": settings.debug}

        self.engine = create_engine(db_url, **engine_kwargs)

        # Async engine configuration
        async_engine_kwargs = {
            "echo": settings.debug,
        }
        if not async_db_url.startswith("sqlite"):
            async_engine_kwargs.update(
                {
                    "pool_size": 5,
                    "max_overflow": 10,
                    "pool_timeout": 30,
                    "pool_recycle": 3600,
                    "pool_pre_ping": True,  # Verify connections before using
                }
            )

        self.async_engine = create_async_engine(async_db_url, **async_engine_kwargs)

        # Create session factories
        self.SessionLocal = sessionmaker(
            bind=self.engine, autocommit=False, autoflush=False
        )
        self.AsyncSessionLocal = async_sessionmaker(
            self.async_engine, expire_on_commit=False, class_=AsyncSession
        )

        # Create tables if they don't exist
        Base.metadata.create_all(bind=self.engine)

        logger.info(f"Storage initialized with {db_url}")
        if not db_url.startswith("sqlite"):
            logger.info(
                f"Connection pool configured: size={engine_kwargs.get('pool_size', 5)}, max_overflow={engine_kwargs.get('max_overflow', 10)}"
            )

    def _build_postgres_url(self) -> str:
        """Build PostgreSQL URL from environment variables with proper validation and escaping."""
        import re
        from urllib.parse import quote_plus

        # Get raw values
        host = self.settings.get_env("STORAGE_DB_HOST", "localhost")
        port = self.settings.get_env("STORAGE_DB_PORT", "5432")
        user = self.settings.get_env("STORAGE_DB_USER", "paidsearchnav")
        password = self.settings.get_env("STORAGE_DB_PASSWORD", "")
        database = self.settings.get_env("STORAGE_DB_NAME", "paidsearchnav")

        # Validate port is numeric
        if not port.isdigit():
            if self.settings.environment == "production":
                raise ValueError("Invalid database configuration")
            else:
                raise ValueError(f"Database port must be numeric, got: {port}")

        port_int = int(port)
        if not (1 <= port_int <= 65535):
            if self.settings.environment == "production":
                raise ValueError("Invalid database configuration")
            else:
                raise ValueError(
                    f"Database port must be between 1 and 65535, got: {port_int}"
                )

        # Validate host format (basic hostname/IP validation)
        if not re.match(r"^[a-zA-Z0-9.-]+$", host):
            if self.settings.environment == "production":
                raise ValueError("Invalid database configuration")
            else:
                raise ValueError(f"Invalid database host format: {host}")

        # Validate database name (alphanumeric, underscore, hyphen only)
        if not re.match(r"^[a-zA-Z0-9_-]+$", database):
            if self.settings.environment == "production":
                raise ValueError("Invalid database configuration")
            else:
                raise ValueError(f"Invalid database name format: {database}")

        # Validate username (alphanumeric, underscore, hyphen only)
        if not re.match(r"^[a-zA-Z0-9_-]+$", user):
            if self.settings.environment == "production":
                raise ValueError("Invalid database configuration")
            else:
                raise ValueError(f"Invalid database username format: {user}")

        # URL-encode all components to prevent injection
        encoded_host = quote_plus(host)
        encoded_user = quote_plus(user)
        encoded_database = quote_plus(database)

        if password:
            # Validate password doesn't contain dangerous characters for logging
            if any(char in password for char in ["\n", "\r", "\t"]):
                raise ValueError(
                    "Database password contains invalid control characters"
                )
            encoded_password = quote_plus(password)
            return f"postgresql://{encoded_user}:{encoded_password}@{encoded_host}:{port}/{encoded_database}"
        else:
            return (
                f"postgresql://{encoded_user}@{encoded_host}:{port}/{encoded_database}"
            )

    async def save_analysis(self, result: AnalysisResult) -> str:
        """Save analysis results and return ID."""
        # Validate input data
        validated_customer_id = _validate_customer_id(result.customer_id)
        validated_analysis_type = _validate_string_input(
            result.analysis_type,
            "analysis_type",
            SecurityConfig.MAX_ANALYSIS_TYPE_LENGTH,
        )
        validated_analyzer_name = _validate_string_input(
            result.analyzer_name,
            "analyzer_name",
            SecurityConfig.MAX_ANALYZER_NAME_LENGTH,
        )

        async with self.AsyncSessionLocal() as session:
            # Use session metrics for optimized logging
            self.session_metrics.session_opened("save_analysis", result.customer_id)
            if self.detailed_logging:
                logger.debug(
                    f"Session opened for save_analysis (customer: {result.customer_id})"
                )
            try:
                # Create database record
                record = AnalysisRecord(
                    customer_id=validated_customer_id,
                    analysis_type=validated_analysis_type,
                    analyzer_name=validated_analyzer_name,
                    start_date=result.start_date,
                    end_date=result.end_date,
                    status=result.status,
                    total_recommendations=result.total_recommendations,
                    critical_issues=result.metrics.critical_issues,
                    potential_cost_savings=result.metrics.potential_cost_savings,
                    potential_conversion_increase=result.metrics.potential_conversion_increase,
                    result_data=result.model_dump(mode="json"),
                )

                session.add(record)
                await session.commit()

                # Update the result with the generated ID
                result.analysis_id = record.id

                logger.info(
                    f"Saved analysis {record.id} for customer {result.customer_id} "
                    f"({result.analysis_type})"
                )
                logger.debug(f"Session committed successfully for analysis {record.id}")

                self.session_metrics.session_closed("save_analysis", success=True)
                return record.id

            except Exception as e:
                await session.rollback()
                logger.error(f"Failed to save analysis: {e}")
                logger.debug("Session rolled back due to error")
                self.session_metrics.session_closed("save_analysis", success=False)
                raise
            finally:
                if self.detailed_logging:
                    logger.debug("Session closed for save_analysis")

    async def get_analysis(self, analysis_id: str) -> AnalysisResult | None:
        """Retrieve analysis results by ID."""
        # Validate analysis ID format
        if (
            not analysis_id
            or not isinstance(analysis_id, str)
            or len(analysis_id.strip()) == 0
        ):
            raise ValueError("Analysis ID cannot be empty")

        async with self.AsyncSessionLocal() as session:
            self.session_metrics.session_opened("get_analysis")
            if self.detailed_logging:
                logger.debug(f"Session opened for get_analysis (id: {analysis_id})")
            try:
                # Query for the record
                result = await session.get(AnalysisRecord, analysis_id)

                if not result:
                    return None

                # Convert back to AnalysisResult
                analysis_result = AnalysisResult.model_validate(result.result_data)
                analysis_result.analysis_id = result.id

                self.session_metrics.session_closed("get_analysis", success=True)
                return analysis_result

            except Exception as e:
                logger.error(f"Failed to retrieve analysis {analysis_id}: {e}")
                self.session_metrics.session_closed("get_analysis", success=False)
                raise
            finally:
                if self.detailed_logging:
                    logger.debug(f"Session closed for get_analysis (id: {analysis_id})")

    async def list_analyses(
        self,
        customer_id: str | None = None,
        analysis_type: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 100,
    ) -> list[AnalysisResult]:
        """List analyses with optional filters."""
        # Validate input parameters
        if customer_id:
            customer_id = _validate_customer_id(customer_id)
        if analysis_type:
            analysis_type = _validate_string_input(
                analysis_type, "analysis_type", SecurityConfig.MAX_ANALYSIS_TYPE_LENGTH
            )
        if limit < 1 or limit > SecurityConfig.MAX_QUERY_LIMIT:
            raise ValueError(
                f"Limit must be between 1 and {SecurityConfig.MAX_QUERY_LIMIT}"
            )

        async with self.AsyncSessionLocal() as session:
            self.session_metrics.session_opened("list_analyses", customer_id)
            if self.detailed_logging:
                logger.debug(
                    f"Session opened for list_analyses (customer: {customer_id}, type: {analysis_type})"
                )
            try:
                # Build query
                stmt = select(AnalysisRecord)

                # Apply filters
                filters = []
                if customer_id:
                    filters.append(AnalysisRecord.customer_id == customer_id)
                if analysis_type:
                    filters.append(AnalysisRecord.analysis_type == analysis_type)
                if start_date:
                    filters.append(AnalysisRecord.created_at >= start_date)
                if end_date:
                    filters.append(AnalysisRecord.created_at <= end_date)

                if filters:
                    stmt = stmt.where(and_(*filters))

                # Order by creation date descending and apply limit
                stmt = stmt.order_by(desc(AnalysisRecord.created_at)).limit(limit)

                # Execute query
                results = await session.execute(stmt)
                records = results.scalars().all()

                # Convert to AnalysisResult objects
                analyses = []
                for record in records:
                    analysis = AnalysisResult.model_validate(record.result_data)
                    analysis.analysis_id = record.id
                    analyses.append(analysis)

                logger.info(f"Retrieved {len(analyses)} analyses")
                logger.debug("Session completed successfully for list_analyses")
                self.session_metrics.session_closed("list_analyses", success=True)
                return analyses

            except Exception as e:
                logger.error(f"Failed to list analyses: {e}")
                self.session_metrics.session_closed("list_analyses", success=False)
                raise
            finally:
                if self.detailed_logging:
                    logger.debug("Session closed for list_analyses")

    async def delete_analysis(self, analysis_id: str) -> bool:
        """Delete analysis results."""
        # Validate analysis ID format
        if (
            not analysis_id
            or not isinstance(analysis_id, str)
            or len(analysis_id.strip()) == 0
        ):
            raise ValueError("Analysis ID cannot be empty")

        async with self.AsyncSessionLocal() as session:
            self.session_metrics.session_opened("delete_analysis")
            if self.detailed_logging:
                logger.debug(f"Session opened for delete_analysis (id: {analysis_id})")
            try:
                # Get the record
                result = await session.get(AnalysisRecord, analysis_id)

                if not result:
                    return False

                # Delete it
                await session.delete(result)
                await session.commit()

                logger.info(f"Deleted analysis {analysis_id}")
                logger.debug(
                    f"Session committed successfully for delete_analysis {analysis_id}"
                )
                self.session_metrics.session_closed("delete_analysis", success=True)
                return True

            except Exception as e:
                await session.rollback()
                logger.error(f"Failed to delete analysis {analysis_id}: {e}")
                logger.debug("Session rolled back due to error")
                self.session_metrics.session_closed("delete_analysis", success=False)
                raise
            finally:
                if self.detailed_logging:
                    logger.debug(
                        f"Session closed for delete_analysis (id: {analysis_id})"
                    )

    async def compare_analyses(self, analysis_id_1: str, analysis_id_2: str) -> dict:
        """Compare two analysis runs."""
        # Get both analyses
        analysis_1 = await self.get_analysis(analysis_id_1)
        analysis_2 = await self.get_analysis(analysis_id_2)

        if not analysis_1 or not analysis_2:
            raise ValueError("One or both analyses not found")

        if analysis_1.customer_id != analysis_2.customer_id:
            raise ValueError("Cannot compare analyses from different customers")

        if analysis_1.analysis_type != analysis_2.analysis_type:
            raise ValueError("Cannot compare different analysis types")

        # Compare recommendations
        recs_1 = {
            f"{r.type}:{r.action_data.get('keyword_text', '')}"
            for r in analysis_1.recommendations
        }
        recs_2 = {
            f"{r.type}:{r.action_data.get('keyword_text', '')}"
            for r in analysis_2.recommendations
        }

        added = recs_2 - recs_1
        resolved = recs_1 - recs_2
        unchanged = recs_1 & recs_2

        # Compare metrics
        cost_savings_change = (
            analysis_2.metrics.potential_cost_savings
            - analysis_1.metrics.potential_cost_savings
        )
        conversion_change = (
            analysis_2.metrics.potential_conversion_increase
            - analysis_1.metrics.potential_conversion_increase
        )

        comparison = {
            "analysis_1": {
                "id": analysis_1.analysis_id,
                "date": analysis_1.created_at.isoformat(),
                "recommendations": analysis_1.total_recommendations,
                "cost_savings": analysis_1.metrics.potential_cost_savings,
            },
            "analysis_2": {
                "id": analysis_2.analysis_id,
                "date": analysis_2.created_at.isoformat(),
                "recommendations": analysis_2.total_recommendations,
                "cost_savings": analysis_2.metrics.potential_cost_savings,
            },
            "changes": {
                "recommendations_added": len(added),
                "recommendations_resolved": len(resolved),
                "recommendations_unchanged": len(unchanged),
                "cost_savings_change": cost_savings_change,
                "conversion_change": conversion_change,
            },
            "details": {
                "added": list(added),
                "resolved": list(resolved),
            },
        }

        return comparison

    async def get_latest_analysis(
        self, customer_id: str, analysis_type: str
    ) -> AnalysisResult | None:
        """Get the most recent analysis for a customer and type."""
        analyses = await self.list_analyses(
            customer_id=customer_id, analysis_type=analysis_type, limit=1
        )

        return analyses[0] if analyses else None

    async def save_analysis_with_files(
        self,
        result: AnalysisResult,
        input_files: list,
        output_files: list,
    ) -> str:
        """Save analysis results with linked S3 files.

        Args:
            result: Analysis result to save
            input_files: List of S3FileReference objects for input files
            output_files: List of S3FileReference objects for output files

        Returns:
            Analysis ID

        Raises:
            ValueError: If validation fails
        """
        from paidsearchnav.core.models.audit_files import S3FileReference
        from paidsearchnav.storage.file_tracker import FileTracker

        # First save the analysis
        analysis_id = await self.save_analysis(result)

        # Then track the files using proper session lifecycle management
        async with self.AsyncSessionLocal() as session:
            # Create file tracker with the actual session
            file_tracker = FileTracker(session)

            try:
                # Track input files
                for input_file in input_files:
                    if isinstance(input_file, S3FileReference):
                        await file_tracker.track_analysis_file(analysis_id, input_file)

                # Track output files
                for output_file in output_files:
                    if isinstance(output_file, S3FileReference):
                        await file_tracker.track_analysis_file(analysis_id, output_file)

                await session.commit()

                logger.info(
                    f"Saved analysis {analysis_id} with {len(input_files)} input files "
                    f"and {len(output_files)} output files"
                )

            except Exception as e:
                await session.rollback()
                logger.error(f"Failed to save analysis files for {analysis_id}: {e}")
                # Delete the analysis record if file linking failed
                await self.delete_analysis(analysis_id)
                raise

        return analysis_id

    async def get_analysis_with_files(self, analysis_id: str):
        """Get analysis result with all associated files.

        Args:
            analysis_id: Analysis ID to retrieve

        Returns:
            AnalysisWithFiles object or None if not found
        """
        from paidsearchnav.core.models.audit_files import (
            AnalysisWithFiles,
            FileCategory,
        )
        from paidsearchnav.storage.file_tracker import FileTracker

        # Get the base analysis
        analysis = await self.get_analysis(analysis_id)
        if not analysis:
            return None

        # Get associated files
        async with self.AsyncSessionLocal() as session:
            file_tracker = FileTracker(session)

            # Get all files by categories efficiently in a single query
            all_categories = [
                FileCategory.INPUT_CSV,
                FileCategory.INPUT_KEYWORDS,
                FileCategory.INPUT_SEARCH_TERMS,
                FileCategory.OUTPUT_REPORT,
                FileCategory.OUTPUT_ACTIONABLE,
                FileCategory.OUTPUT_SUMMARY,
                FileCategory.OUTPUT_SCRIPTS,
            ]
            files_by_category = await file_tracker.get_files_by_categories(
                analysis_id, all_categories
            )

            # Organize input files
            input_files = []
            input_files.extend(files_by_category.get(FileCategory.INPUT_CSV, []))
            input_files.extend(files_by_category.get(FileCategory.INPUT_KEYWORDS, []))
            input_files.extend(
                files_by_category.get(FileCategory.INPUT_SEARCH_TERMS, [])
            )

            # Organize output files
            output_files = []
            output_files.extend(files_by_category.get(FileCategory.OUTPUT_REPORT, []))
            output_files.extend(
                files_by_category.get(FileCategory.OUTPUT_ACTIONABLE, [])
            )
            output_files.extend(files_by_category.get(FileCategory.OUTPUT_SUMMARY, []))
            output_files.extend(files_by_category.get(FileCategory.OUTPUT_SCRIPTS, []))

            # Determine S3 folder path from files or create default
            s3_folder_path = ""
            if input_files or output_files:
                all_files = input_files + output_files
                if all_files:
                    # Extract folder path from first file using URL parsing for security
                    from urllib.parse import urlparse

                    file_path = all_files[0].file_path
                    try:
                        parsed_url = urlparse(file_path)
                        if parsed_url.scheme == "s3":
                            # Get path without filename
                            path_parts = parsed_url.path.strip("/").split("/")
                            if path_parts:
                                folder_parts = (
                                    path_parts[:-1] if len(path_parts) > 1 else []
                                )
                                s3_folder_path = (
                                    f"s3://{parsed_url.netloc}/{'/'.join(folder_parts)}"
                                )
                            else:
                                s3_folder_path = f"s3://{parsed_url.netloc}"
                    except (ValueError, AttributeError) as e:
                        # Fallback to safe default if URL parsing fails
                        logger.warning(f"Failed to parse S3 file path {file_path}: {e}")
                        s3_folder_path = ""

            return AnalysisWithFiles(
                analysis=analysis,
                input_files=input_files,
                output_files=output_files,
                s3_folder_path=s3_folder_path,
            )

    async def list_customer_audits(
        self,
        customer_id: str,
        google_ads_account_id: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list:
        """List audit summaries for a customer.

        Args:
            customer_id: Customer ID to filter by
            google_ads_account_id: Optional Google Ads account ID filter
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            List of AuditSummary objects
        """
        from paidsearchnav.core.models.audit_files import AuditSummary
        from paidsearchnav.storage.file_tracker import FileTracker

        # Get analyses for customer
        analyses = await self.list_analyses(
            customer_id=customer_id,
            start_date=start_date,
            end_date=end_date,
            limit=1000,
        )

        # Filter by Google Ads account if specified
        if google_ads_account_id:
            analyses = [
                a
                for a in analyses
                if hasattr(a, "google_ads_account_id")
                and getattr(a, "google_ads_account_id", None) == google_ads_account_id
            ]

        # Convert to audit summaries
        audit_summaries = []

        async with self.AsyncSessionLocal() as session:
            file_tracker = FileTracker(session)

            for analysis in analyses:
                # Get file counts
                input_files = []
                output_files = []

                try:
                    from paidsearchnav.core.models.audit_files import FileCategory

                    # Count input files
                    for category in [
                        FileCategory.INPUT_CSV,
                        FileCategory.INPUT_KEYWORDS,
                        FileCategory.INPUT_SEARCH_TERMS,
                    ]:
                        files = await file_tracker.get_files_by_category(
                            analysis.analysis_id, category
                        )
                        input_files.extend(files)

                    # Count output files
                    for category in [
                        FileCategory.OUTPUT_REPORT,
                        FileCategory.OUTPUT_ACTIONABLE,
                        FileCategory.OUTPUT_SUMMARY,
                        FileCategory.OUTPUT_SCRIPTS,
                    ]:
                        files = await file_tracker.get_files_by_category(
                            analysis.analysis_id, category
                        )
                        output_files.extend(files)

                except Exception as e:
                    logger.warning(
                        f"Error counting files for analysis {analysis.analysis_id}: {e}"
                    )

                # Determine S3 folder path from files
                s3_folder_path = ""
                all_files = input_files + output_files
                if all_files:
                    # Extract folder path from first file using URL parsing for security
                    from urllib.parse import urlparse

                    file_path = all_files[0].file_path
                    try:
                        parsed_url = urlparse(file_path)
                        if parsed_url.scheme == "s3":
                            # Get path without filename
                            path_parts = parsed_url.path.strip("/").split("/")
                            if path_parts:
                                folder_parts = (
                                    path_parts[:-1] if len(path_parts) > 1 else []
                                )
                                s3_folder_path = (
                                    f"s3://{parsed_url.netloc}/{'/'.join(folder_parts)}"
                                )
                            else:
                                s3_folder_path = f"s3://{parsed_url.netloc}"
                    except (ValueError, AttributeError) as e:
                        # Fallback to safe default if URL parsing fails
                        logger.warning(f"Failed to parse S3 file path {file_path}: {e}")
                        s3_folder_path = ""

                # Create audit summary
                summary = AuditSummary(
                    analysis_id=analysis.analysis_id,
                    customer_name=customer_id,  # Customer ID used as name (customer management is outside this scope)
                    google_ads_account_id=getattr(
                        analysis, "google_ads_account_id", ""
                    ),
                    audit_date=analysis.created_at,
                    status=analysis.status,
                    total_recommendations=analysis.total_recommendations,
                    cost_savings=analysis.metrics.potential_cost_savings,
                    input_file_count=len(input_files),
                    output_file_count=len(output_files),
                    s3_folder_path=s3_folder_path,
                    analysis_type=analysis.analysis_type,
                    total_file_size=sum(
                        f.file_size for f in input_files + output_files
                    ),
                )

                audit_summaries.append(summary)

        return audit_summaries

    async def get_audit_files(self, analysis_id: str):
        """Get all files for an audit organized by type.

        Args:
            analysis_id: Analysis ID to get files for

        Returns:
            AuditFileSet object
        """
        from paidsearchnav.core.models.audit_files import (
            AuditFileSet,
            FileCategory,
        )
        from paidsearchnav.storage.file_tracker import FileTracker

        async with self.AsyncSessionLocal() as session:
            file_tracker = FileTracker(session)

            # Get all files by categories efficiently in a single query
            all_categories = [
                FileCategory.INPUT_CSV,
                FileCategory.INPUT_KEYWORDS,
                FileCategory.INPUT_SEARCH_TERMS,
                FileCategory.OUTPUT_REPORT,
                FileCategory.OUTPUT_ACTIONABLE,
                FileCategory.OUTPUT_SCRIPTS,
                FileCategory.AUDIT_LOG,
            ]
            files_by_category = await file_tracker.get_files_by_categories(
                analysis_id, all_categories
            )

            # Organize files by type
            input_files = []
            input_files.extend(files_by_category.get(FileCategory.INPUT_CSV, []))
            input_files.extend(files_by_category.get(FileCategory.INPUT_KEYWORDS, []))
            input_files.extend(
                files_by_category.get(FileCategory.INPUT_SEARCH_TERMS, [])
            )

            output_reports = files_by_category.get(FileCategory.OUTPUT_REPORT, [])

            output_actionable = []
            output_actionable.extend(
                files_by_category.get(FileCategory.OUTPUT_ACTIONABLE, [])
            )
            output_actionable.extend(
                files_by_category.get(FileCategory.OUTPUT_SCRIPTS, [])
            )

            audit_logs = files_by_category.get(FileCategory.AUDIT_LOG, [])

            # Determine S3 folder path
            s3_folder_path = ""
            all_files = input_files + output_reports + output_actionable + audit_logs
            if all_files:
                # Extract folder path from first file using URL parsing for security
                from urllib.parse import urlparse

                file_path = all_files[0].file_path
                try:
                    parsed_url = urlparse(file_path)
                    if parsed_url.scheme == "s3":
                        # Get path without filename
                        path_parts = parsed_url.path.strip("/").split("/")
                        if path_parts:
                            folder_parts = (
                                path_parts[:-1] if len(path_parts) > 1 else []
                            )
                            s3_folder_path = (
                                f"s3://{parsed_url.netloc}/{'/'.join(folder_parts)}"
                            )
                        else:
                            s3_folder_path = f"s3://{parsed_url.netloc}"
                except (ValueError, AttributeError) as e:
                    # Fallback to safe default if URL parsing fails
                    logger.warning(f"Failed to parse S3 file path {file_path}: {e}")
                    s3_folder_path = ""

            return AuditFileSet(
                analysis_id=analysis_id,
                input_files=input_files,
                output_reports=output_reports,
                output_actionable=output_actionable,
                audit_logs=audit_logs,
                s3_folder_path=s3_folder_path,
            )

    async def archive_old_analyses(self, retention_days: int = 90):
        """Archive old analyses and their files.

        Args:
            retention_days: Number of days to retain analyses

        Returns:
            ArchiveReport object
        """
        from datetime import datetime, timedelta

        from paidsearchnav.core.models.audit_files import ArchiveReport
        from paidsearchnav.storage.file_tracker import FileTracker

        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)

        # Get old analyses
        old_analyses = await self.list_analyses(
            end_date=cutoff_date,
            limit=10000,  # Large limit to get all old analyses
        )

        archived_count = 0
        files_archived = 0
        space_freed = 0
        errors = []

        async with self.AsyncSessionLocal() as session:
            file_tracker = FileTracker(session)

            for analysis in old_analyses:
                try:
                    # Get analysis files
                    analysis_files = await file_tracker.get_analysis_files(
                        analysis.analysis_id
                    )

                    # Count files and space
                    file_count = len(analysis_files)
                    file_space = sum(f.file_size for f in analysis_files)

                    # Delete file records (in a real system, you'd move files to archive storage)
                    deleted_files = await file_tracker.delete_analysis_files(
                        analysis.analysis_id
                    )

                    # Delete analysis record
                    await self.delete_analysis(analysis.analysis_id)

                    archived_count += 1
                    files_archived += deleted_files
                    space_freed += file_space

                    logger.info(
                        f"Archived analysis {analysis.analysis_id} with {deleted_files} files"
                    )

                except Exception as e:
                    error_msg = (
                        f"Failed to archive analysis {analysis.analysis_id}: {e}"
                    )
                    logger.error(error_msg)
                    errors.append(error_msg)

        return ArchiveReport(
            archived_count=archived_count,
            files_archived=files_archived,
            space_freed=space_freed,
            errors=errors,
        )


class CustomerRepository:
    """Repository for customer database operations."""

    def __init__(self, session: AsyncSession):
        """Initialize the repository with a database session.

        Args:
            session: Async database session
        """
        self.session = session

    async def get_by_id(self, customer_id: str) -> Customer | None:
        """Get customer by ID.

        Args:
            customer_id: Customer ID to retrieve

        Returns:
            Customer object if found, None otherwise
        """
        try:
            result = await self.session.get(Customer, customer_id)
            return result
        except Exception as e:
            logger.error(f"Failed to get customer {customer_id}: {e}")
            raise

    async def create(self, customer: Customer) -> Customer:
        """Create a new customer.

        Args:
            customer: Customer object to create

        Returns:
            Created customer object
        """
        try:
            self.session.add(customer)
            await self.session.flush()  # Flush to get ID without committing
            return customer
        except Exception as e:
            logger.error(f"Failed to create customer: {e}")
            raise

    async def update(self, customer: Customer) -> Customer:
        """Update an existing customer.

        Args:
            customer: Customer object with updates

        Returns:
            Updated customer object
        """
        try:
            await self.session.merge(customer)
            await self.session.flush()
            return customer
        except Exception as e:
            logger.error(f"Failed to update customer {customer.id}: {e}")
            raise

    async def delete(self, customer_id: str) -> bool:
        """Delete a customer by ID.

        Args:
            customer_id: Customer ID to delete

        Returns:
            True if deleted, False if not found
        """
        try:
            customer = await self.get_by_id(customer_id)
            if customer:
                await self.session.delete(customer)
                await self.session.flush()
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to delete customer {customer_id}: {e}")
            raise

    async def list_by_user(self, user_id: str, limit: int = 100) -> list[Customer]:
        """List customers for a specific user.

        Args:
            user_id: User ID to filter by
            limit: Maximum number of customers to return

        Returns:
            List of customer objects
        """
        try:
            stmt = (
                select(Customer)
                .where(Customer.user_id == user_id)
                .order_by(desc(Customer.created_at))
                .limit(limit)
            )

            result = await self.session.execute(stmt)
            customers = result.scalars().all()
            return list(customers)
        except Exception as e:
            logger.error(f"Failed to list customers for user {user_id}: {e}")
            raise

    async def exists(self, customer_id: str) -> bool:
        """Check if a customer exists.

        Args:
            customer_id: Customer ID to check

        Returns:
            True if customer exists, False otherwise
        """
        try:
            customer = await self.get_by_id(customer_id)
            return customer is not None
        except Exception:
            return False
