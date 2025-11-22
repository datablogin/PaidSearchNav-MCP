"""Database integration module providing unified interface for database operations."""

import asyncio
import logging
import re
import time
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from urllib.parse import urlparse

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool, QueuePool

from paidsearchnav.core.config import get_settings
from paidsearchnav.core.models.analysis import AnalysisResult
from paidsearchnav.monitoring.database_metrics import create_pool_monitor
from paidsearchnav.storage.models import Base
from paidsearchnav.storage.repository import AnalysisRepository

logger = logging.getLogger(__name__)

# Pre-compiled regex patterns for performance
PASSWORD_MASK_PATTERN = re.compile(r"://([^:]+):([^@]+)@")


def validate_customer_id(customer_id: str) -> str:
    """Validate customer ID format.

    Args:
        customer_id: Google Ads customer ID to validate

    Returns:
        Cleaned customer ID

    Raises:
        ValueError: If customer ID is invalid
    """
    if not customer_id or not customer_id.strip():
        raise ValueError("Customer ID cannot be empty")

    # Remove hyphens and validate
    cleaned_id = customer_id.strip().replace("-", "")
    if not cleaned_id.isdigit():
        raise ValueError("Customer ID must contain only digits and hyphens")

    # Google Ads customer IDs are typically 8-12 digits
    if len(cleaned_id) < 8 or len(cleaned_id) > 12:
        raise ValueError("Customer ID must be 8-12 digits")

    return customer_id.strip()


def validate_database_url(url: str) -> None:
    """Validate database URL format and security.

    Args:
        url: Database URL to validate

    Raises:
        ValueError: If URL is invalid or insecure
    """
    if not url:
        raise ValueError("Database URL cannot be empty")

    # Parse URL
    try:
        parsed = urlparse(url)
    except Exception as e:
        raise ValueError(f"Invalid database URL format: {e}")

    # Check scheme
    valid_schemes = {
        "sqlite",
        "sqlite+aiosqlite",
        "postgresql",
        "postgresql+asyncpg",
        "postgres",
        "postgresql+pg8000",
        "mysql",
        "mysql+aiomysql",
    }

    if parsed.scheme not in valid_schemes:
        raise ValueError(f"Unsupported database scheme: {parsed.scheme}")

    # Warn about passwords in URLs (but don't block)
    if parsed.password:
        logger.warning(
            "Database URL contains password - consider using environment variables"
        )


class DatabaseConnection:
    """Manages async database connections with pooling and retry logic."""

    def __init__(
        self,
        database_url: Optional[str] = None,
        pool_size: int = 10,
        max_overflow: int = 20,
        pool_timeout: float = 30.0,
        echo: bool = False,
    ):
        """Initialize database connection manager.

        Args:
            database_url: Database connection URL (defaults to config)
            pool_size: Number of connections to maintain in pool
            max_overflow: Maximum overflow connections allowed
            pool_timeout: Timeout for getting connection from pool
            echo: Whether to log SQL statements
        """
        # Get settings or use minimal defaults for testing
        try:
            self.config = get_settings()
        except Exception:
            # If settings fail to load (e.g., in tests), create minimal config
            from paidsearchnav.core.config import Settings

            self.config = Settings(
                environment="development",
                data_dir=Path.home() / ".paidsearchnav",
            )

        self.database_url = database_url or self._get_database_url()

        # Validate database URL
        try:
            validate_database_url(self.database_url)
        except ValueError as e:
            logger.error(f"Invalid database URL: {e}")
            raise

        self.pool_size = pool_size
        self.max_overflow = max_overflow
        self.pool_timeout = pool_timeout
        self.echo = echo
        self._engine: Optional[AsyncEngine] = None
        self._session_factory: Optional[sessionmaker] = None
        self._retry_count = 3
        self._retry_delay = 1.0
        self._pool_monitor = None
        self._is_draining = False
        self._drain_lock = asyncio.Lock()

    def _get_database_url(self) -> str:
        """Get database URL from config, converting to async if needed."""
        # Get database URL from settings
        if self.config.database_url:
            db_url = self.config.database_url.get_secret_value()
        else:
            # Default to SQLite for development
            db_url = f"sqlite:///{self.config.data_dir}/paidsearchnav.db"

        # Convert sync URLs to async
        if db_url.startswith("sqlite://"):
            return db_url.replace("sqlite://", "sqlite+aiosqlite://")
        elif db_url.startswith("postgresql://"):
            return db_url.replace("postgresql://", "postgresql+asyncpg://")
        elif db_url.startswith("postgres://"):
            return db_url.replace("postgres://", "postgresql+asyncpg://")

        return db_url

    async def initialize(self) -> None:
        """Initialize database connection and create tables if needed."""
        try:
            # Create engine with appropriate pooling strategy
            poolclass = NullPool if "sqlite" in self.database_url else QueuePool

            # Mask password in logs
            safe_url = self._mask_password_in_url(self.database_url)
            logger.info(f"Initializing database connection to: {safe_url}")

            # Create engine kwargs based on pool class
            engine_kwargs = {
                "echo": self.echo,
                "poolclass": poolclass,
                "pool_pre_ping": True,  # Verify connections before use
            }

            # Only add pool parameters for QueuePool
            if poolclass == QueuePool:
                engine_kwargs.update(
                    {
                        "pool_size": self.pool_size,
                        "max_overflow": self.max_overflow,
                        "pool_timeout": self.pool_timeout,
                    }
                )

            self._engine = create_async_engine(self.database_url, **engine_kwargs)

            # Initialize pool monitor for non-SQLite databases
            if poolclass == QueuePool and self._engine:
                try:
                    # Use the async engine's sync_engine attribute for monitoring
                    # This ensures we're monitoring the actual pool being used
                    if hasattr(self._engine, "sync_engine"):
                        self._pool_monitor = create_pool_monitor(
                            self._engine.sync_engine, database_name="main"
                        )
                        logger.info("Database pool monitoring initialized")
                    else:
                        logger.info(
                            "Pool monitoring not available - sync_engine not accessible"
                        )
                except AttributeError as e:
                    logger.warning(f"Failed to access sync engine for monitoring: {e}")
                except ImportError as e:
                    logger.error(
                        f"Failed to import monitoring dependencies: {e}", exc_info=True
                    )
                except ValueError as e:
                    logger.error(
                        f"Invalid configuration for pool monitoring: {e}", exc_info=True
                    )
                except Exception as e:
                    # Log unexpected errors with full stack trace for debugging
                    logger.error(
                        f"Unexpected error initializing pool monitoring: {type(e).__name__}: {e}",
                        exc_info=True,
                    )

            # Create session factory
            self._session_factory = sessionmaker(
                self._engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )

            # Create tables if they don't exist
            async with self._engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            logger.info("Database connection initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize database connection: {e}")
            raise

    def _mask_password_in_url(self, url: str) -> str:
        """Mask password in database URL for safe logging."""
        # Use pre-compiled regex pattern for better performance
        return PASSWORD_MASK_PATTERN.sub(r"://\1:****@", url)

    async def execute_query(
        self, query: str, params: Optional[Union[tuple, dict]] = None
    ) -> List[Dict[str, Any]]:
        """Execute a query and return results.

        Args:
            query: SQL query to execute
            params: Query parameters (tuple for positional, dict for named)

        Returns:
            List of dictionaries containing query results
        """
        if not self._engine:
            raise RuntimeError("Database connection not initialized")

        for attempt in range(self._retry_count):
            try:
                async with self.get_session() as session:
                    # Convert string query to SQLAlchemy text
                    stmt = sa.text(query)

                    # Bind parameters if provided
                    if params:
                        if isinstance(params, dict):
                            stmt = stmt.bindparams(**params)
                        else:
                            # For positional params, SQLAlchemy doesn't support ? placeholders
                            # in text() queries. Convert to named parameters safely.
                            param_dict = {f"param_{i}": v for i, v in enumerate(params)}
                            # Use regex to safely replace ? placeholders
                            import re

                            def replacer(match):
                                replacer.count = getattr(replacer, "count", -1) + 1
                                return f":param_{replacer.count}"

                            query = re.sub(r"\?", replacer, query)
                            stmt = sa.text(query).bindparams(**param_dict)

                    result = await session.execute(stmt)

                    # Convert rows to dictionaries
                    rows = result.fetchall()
                    if rows and hasattr(rows[0], "_asdict"):
                        return [row._asdict() for row in rows]
                    elif rows and hasattr(rows[0], "_mapping"):
                        return [dict(row._mapping) for row in rows]
                    else:
                        return [dict(row) for row in rows] if rows else []

            except Exception as e:
                if attempt < self._retry_count - 1:
                    logger.warning(
                        f"Query execution failed (attempt {attempt + 1}/{self._retry_count}): {e}"
                    )
                    await asyncio.sleep(self._retry_delay * (attempt + 1))
                else:
                    logger.error(
                        f"Query execution failed after {self._retry_count} attempts: {e}"
                    )
                    raise

    @asynccontextmanager
    async def get_session(self) -> AsyncSession:
        """Get a database session with automatic cleanup."""
        if not self._session_factory:
            raise RuntimeError("Database connection not initialized")

        # Prevent new connections during draining
        if self._is_draining:
            raise RuntimeError(
                "Connection pool is draining, no new connections allowed"
            )

        async with self._session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    def get_pool_health(self) -> Dict[str, Any]:
        """Get connection pool health status.

        Returns:
            Dictionary containing pool health status and metrics
        """
        if self._is_draining:
            return {
                "status": "draining",
                "message": "Connection pool is draining for maintenance",
                "metrics": {},
            }

        if self._pool_monitor:
            return self._pool_monitor.get_health_status()
        else:
            return {
                "status": "unknown",
                "message": "Pool monitoring not available (SQLite or not initialized)",
                "metrics": {},
            }

    async def drain_connections(self, timeout: float = 30.0) -> None:
        """Drain all connections gracefully before closing.

        Args:
            timeout: Maximum time to wait for connections to drain (seconds)
        """
        async with self._drain_lock:
            if self._is_draining:
                logger.warning("Connection pool is already draining")
                return

            self._is_draining = True
            logger.info("Starting connection pool drain")

            try:
                if self._engine and hasattr(self._engine.pool, "checked_out"):
                    start_time = asyncio.get_event_loop().time()

                    # Wait for all connections to be returned
                    while self._engine.pool.checked_out() > 0:
                        elapsed = asyncio.get_event_loop().time() - start_time
                        if elapsed > timeout:
                            logger.warning(
                                f"Connection drain timeout after {timeout}s, "
                                f"{self._engine.pool.checked_out()} connections still active"
                            )
                            break

                        # Log progress
                        if int(elapsed) % 5 == 0:
                            logger.info(
                                f"Waiting for {self._engine.pool.checked_out()} "
                                f"connections to close..."
                            )

                        await asyncio.sleep(0.5)

                    logger.info("Connection pool drain completed")
            finally:
                self._is_draining = False

    async def close(self) -> None:
        """Close database connection and cleanup resources."""
        if self._engine:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None
            logger.info("Database connection closed")


class AnalysisStorageService:
    """High-level interface for storing and retrieving analysis results."""

    def __init__(self, connection: Optional[DatabaseConnection] = None):
        """Initialize storage service.

        Args:
            connection: Database connection to use (creates new if not provided)
        """
        self.connection = connection or DatabaseConnection()
        self._repository: Optional[AnalysisRepository] = None
        self._cache: Dict[str, Tuple[float, Any]] = {}  # (timestamp, data)
        self._cache_ttl = 300  # 5 minutes

    async def initialize(self) -> None:
        """Initialize the storage service."""
        if not self.connection._engine:
            await self.connection.initialize()

        # Initialize repository with the settings
        # Note: The repository will create its own database connection
        # This is a limitation of the current architecture
        self._repository = AnalysisRepository(settings=self.connection.config)

    def _is_cache_expired(self, timestamp: float) -> bool:
        """Check if a cache entry has expired."""
        return (time.time() - timestamp) > self._cache_ttl

    def _clean_expired_cache(self) -> None:
        """Remove expired entries from cache."""
        current_time = time.time()
        expired_keys = [
            key
            for key, (timestamp, _) in self._cache.items()
            if self._is_cache_expired(timestamp)
        ]
        for key in expired_keys:
            del self._cache[key]

    async def store_analysis(
        self, customer_id: str, analysis_type: str, data: Dict[str, Any]
    ) -> str:
        """Store analysis results and return ID.

        Args:
            customer_id: Google Ads customer ID
            analysis_type: Type of analysis performed
            data: Analysis data to store

        Returns:
            ID of the stored analysis
        """
        if not self._repository:
            raise RuntimeError("Storage service not initialized")

        # Validate inputs
        customer_id = validate_customer_id(customer_id)

        if not analysis_type or not analysis_type.strip():
            raise ValueError("Analysis type cannot be empty")

        if not isinstance(data, dict):
            raise ValueError("Data must be a dictionary")

        # Create AnalysisResult object
        analysis_result = AnalysisResult(
            customer_id=customer_id,
            analysis_type=analysis_type,
            analyzer_name="database_integration",
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow(),
            status="completed",
            raw_data=data,
        )

        # Store using repository
        analysis_id = await self._repository.save_analysis(analysis_result)

        # Invalidate cache for this customer
        cache_key = f"{customer_id}:{analysis_type}"
        if cache_key in self._cache:
            del self._cache[cache_key]

        logger.info(
            f"Stored {analysis_type} analysis for customer {customer_id} with ID {analysis_id}"
        )

        return analysis_id

    async def store_analyses_batch(self, analyses: List[Dict[str, Any]]) -> List[str]:
        """Store multiple analyses in a batch operation.

        Args:
            analyses: List of analysis data dictionaries

        Returns:
            List of IDs for stored analyses
        """
        if not self._repository:
            raise RuntimeError("Storage service not initialized")

        analysis_ids = []

        # Store each analysis using the repository for consistency
        for analysis in analyses:
            # Validate inputs
            customer_id = validate_customer_id(analysis["customer_id"])

            if (
                not analysis.get("analysis_type")
                or not analysis["analysis_type"].strip()
            ):
                raise ValueError("Analysis type cannot be empty")

            if not isinstance(analysis.get("data"), dict):
                raise ValueError("Data must be a dictionary")

            # Create AnalysisResult object
            analysis_result = AnalysisResult(
                customer_id=customer_id,
                analysis_type=analysis["analysis_type"],
                analyzer_name=analysis.get("analyzer_name", "database_integration"),
                start_date=analysis.get("start_date", datetime.utcnow()),
                end_date=analysis.get("end_date", datetime.utcnow()),
                status="completed",
                raw_data=analysis["data"],
            )

            # Store using repository
            analysis_id = await self._repository.save_analysis(analysis_result)
            analysis_ids.append(analysis_id)

            # Invalidate cache for this customer
            cache_key = f"{customer_id}:{analysis['analysis_type']}"
            if cache_key in self._cache:
                del self._cache[cache_key]

        logger.info(f"Stored {len(analysis_ids)} analyses in batch operation")
        return analysis_ids

    async def get_analysis(
        self, customer_id: str, analysis_type: str, use_cache: bool = True
    ) -> Optional[Dict[str, Any]]:
        """Retrieve analysis results.

        Args:
            customer_id: Google Ads customer ID
            analysis_type: Type of analysis to retrieve
            use_cache: Whether to use cached results

        Returns:
            Analysis data or None if not found
        """
        if not self._repository:
            raise RuntimeError("Storage service not initialized")

        # Validate inputs
        customer_id = validate_customer_id(customer_id)

        # Check cache first
        cache_key = f"{customer_id}:{analysis_type}"
        if use_cache and cache_key in self._cache:
            timestamp, cached_data = self._cache[cache_key]
            if not self._is_cache_expired(timestamp):
                logger.debug(f"Returning cached analysis for {cache_key}")
                return cached_data
            else:
                # Remove expired entry
                del self._cache[cache_key]

        # Retrieve from repository
        analyses = await self._repository.list_analyses(
            customer_id=customer_id,
            analysis_type=analysis_type,
            limit=1,
        )

        if analyses:
            analysis = analyses[0]
            # Convert AnalysisResult to dictionary for API consistency
            analysis_dict = {
                "analysis_id": analysis.analysis_id,
                "customer_id": analysis.customer_id,
                "analysis_type": analysis.analysis_type,
                "analyzer_name": analysis.analyzer_name,
                "start_date": analysis.start_date,
                "end_date": analysis.end_date,
                "status": analysis.status,
                "result_data": analysis.raw_data,  # Use the raw_data from the analysis
                "created_at": getattr(analysis, "created_at", analysis.end_date),
                "updated_at": getattr(analysis, "updated_at", analysis.end_date),
            }
            # Cache the result with timestamp
            if use_cache:
                self._cache[cache_key] = (time.time(), analysis_dict)
            return analysis_dict

        return None

    async def list_analyses(
        self,
        customer_id: str,
        limit: int = 10,
        analysis_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List analyses for a customer.

        Args:
            customer_id: Google Ads customer ID
            limit: Maximum number of results to return
            analysis_type: Filter by analysis type (optional)

        Returns:
            List of analysis records
        """
        if not self._repository:
            raise RuntimeError("Storage service not initialized")

        # Get analyses from repository
        analyses = await self._repository.list_analyses(
            customer_id=customer_id,
            analysis_type=analysis_type,
            limit=limit,
        )

        # Convert AnalysisResult objects to dictionaries for API consistency
        return [
            {
                "analysis_id": analysis.analysis_id,
                "customer_id": analysis.customer_id,
                "analysis_type": analysis.analysis_type,
                "analyzer_name": analysis.analyzer_name,
                "start_date": analysis.start_date,
                "end_date": analysis.end_date,
                "status": analysis.status,
                "result_data": analysis.raw_data,
                "created_at": getattr(analysis, "created_at", analysis.end_date),
                "updated_at": getattr(analysis, "updated_at", analysis.end_date),
            }
            for analysis in analyses
        ]

    async def delete_analysis(self, analysis_id: str) -> bool:
        """Delete an analysis by ID.

        Args:
            analysis_id: ID of analysis to delete

        Returns:
            True if deleted, False if not found
        """
        if not self._repository:
            raise RuntimeError("Storage service not initialized")

        # Try to get the analysis first to know which cache key to invalidate
        try:
            # Get analysis details to find customer_id and type
            analysis = await self._repository.get_analysis(analysis_id)
            if analysis:
                # Invalidate specific cache entry
                cache_key = f"{analysis.customer_id}:{analysis.analysis_type}"
                if cache_key in self._cache:
                    del self._cache[cache_key]
                    logger.debug(f"Invalidated cache for key: {cache_key}")
        except KeyError as e:
            # Analysis not found - no cache to invalidate
            logger.debug(f"Analysis {analysis_id} not found, no cache to invalidate")
        except asyncio.TimeoutError as e:
            # Database timeout - clear cache to be safe
            logger.warning(
                f"Timeout getting analysis {analysis_id}, clearing cache: {e}"
            )
            self._cache.clear()
        except Exception as e:
            # Unexpected error - log details but proceed with deletion
            logger.warning(
                f"Error getting analysis {analysis_id} for cache invalidation: "
                f"{type(e).__name__}: {e}. Proceeding with deletion.",
                exc_info=True,
            )

        return await self._repository.delete_analysis(analysis_id)

    async def compare_analyses(
        self,
        customer_id: str,
        analysis_id_1: str,
        analysis_id_2: str,
    ) -> Optional[Dict[str, Any]]:
        """Compare two analysis runs.

        Args:
            customer_id: Google Ads customer ID
            analysis_id_1: First analysis ID
            analysis_id_2: Second analysis ID

        Returns:
            Comparison results or None if analyses not found
        """
        if not self._repository:
            raise RuntimeError("Storage service not initialized")

        # Get the base comparison from repository
        base_comparison = await self._repository.compare_analyses(
            analysis_id_1=analysis_id_1,
            analysis_id_2=analysis_id_2,
        )

        # Get the raw data for both analyses
        analysis_1 = await self._repository.get_analysis(analysis_id_1)
        analysis_2 = await self._repository.get_analysis(analysis_id_2)

        if not analysis_1 or not analysis_2:
            return None

        # Add raw data field comparisons
        raw_data_1 = analysis_1.raw_data or {}
        raw_data_2 = analysis_2.raw_data or {}

        # Find changed fields
        all_keys = set(raw_data_1.keys()) | set(raw_data_2.keys())
        field_changes = {}

        for key in all_keys:
            old_value = raw_data_1.get(key)
            new_value = raw_data_2.get(key)

            if old_value != new_value:
                field_changes[key] = {"old": old_value, "new": new_value}

        # Merge with base comparison
        if "changes" not in base_comparison:
            base_comparison["changes"] = {}

        # Add field-level changes to the comparison
        base_comparison["changes"].update(field_changes)

        return base_comparison

    async def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics for database operations.

        Returns:
            Dictionary containing performance metrics
        """
        # Clean expired cache entries first
        self._clean_expired_cache()

        metrics = {
            "cache_size": len(self._cache),
            "cache_ttl": self._cache_ttl,
        }

        # Add connection pool metrics using the monitor
        if self.connection._pool_monitor:
            try:
                pool_metrics = self.connection._pool_monitor.collect_metrics()
                metrics.update(
                    {
                        "pool_size": pool_metrics.get("pool_size", 0),
                        "pool_available": pool_metrics.get("checked_in", 0),
                        "pool_in_use": pool_metrics.get("checked_out", 0),
                        "pool_overflow": pool_metrics.get("overflow", 0),
                        "pool_total": pool_metrics.get("total", 0),
                        "pool_utilization_percent": pool_metrics.get(
                            "utilization_percent", 0.0
                        ),
                    }
                )
            except Exception as e:
                logger.warning(f"Failed to collect pool metrics: {e}")
        elif self.connection._engine:
            # Fallback to basic metrics for async engines
            pool = self.connection._engine.pool
            if hasattr(pool, "size") and callable(pool.size):
                metrics["pool_size"] = pool.size()
            if hasattr(pool, "checked_in") and callable(pool.checked_in):
                metrics["pool_available"] = pool.checked_in()
            if hasattr(pool, "checked_out") and callable(pool.checked_out):
                metrics["pool_in_use"] = pool.checked_out()

        return metrics

    async def close(self) -> None:
        """Close storage service and cleanup resources."""
        # Clear cache
        self._cache.clear()

        if self.connection:
            await self.connection.close()
