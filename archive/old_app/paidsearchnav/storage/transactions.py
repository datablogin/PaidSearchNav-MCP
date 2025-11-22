"""Database transaction management utilities."""

import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Optional

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class TransactionManager:
    """Manages database transactions with automatic rollback on failure."""

    def __init__(self, session: AsyncSession):
        """Initialize transaction manager.

        Args:
            session: SQLAlchemy async session
        """
        self.session = session
        self._transaction = None
        self._savepoint_counter = 0

    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[AsyncSession, None]:
        """Create a database transaction context.

        Automatically commits on success and rolls back on exception.

        Yields:
            AsyncSession: The database session within the transaction

        Example:
            async with transaction_manager.transaction() as session:
                # Perform database operations
                await session.execute(...)
                await session.execute(...)
                # All operations will be committed together
        """
        try:
            # Start transaction if not already in one
            if not self._transaction:
                self._transaction = await self.session.begin()
            else:
                # Nested transaction - use savepoint
                self._savepoint_counter += 1
                savepoint_name = f"sp_{self._savepoint_counter}"
                await self.session.execute(f"SAVEPOINT {savepoint_name}")

            yield self.session

            # Commit the transaction
            if self._savepoint_counter == 0:
                await self.session.commit()
                self._transaction = None
            else:
                # Release savepoint on success
                savepoint_name = f"sp_{self._savepoint_counter}"
                await self.session.execute(f"RELEASE SAVEPOINT {savepoint_name}")
                self._savepoint_counter -= 1

        except Exception as e:
            # Rollback on error
            logger.error(f"Transaction failed: {e}")

            if self._savepoint_counter == 0:
                await self.session.rollback()
                self._transaction = None
            else:
                # Rollback to savepoint
                savepoint_name = f"sp_{self._savepoint_counter}"
                await self.session.execute(f"ROLLBACK TO SAVEPOINT {savepoint_name}")
                self._savepoint_counter -= 1

            raise

    @asynccontextmanager
    async def batch_operation(
        self, batch_size: int = 100
    ) -> AsyncGenerator[list, None]:
        """Context manager for batch database operations.

        Automatically flushes operations in batches to prevent memory issues.

        Args:
            batch_size: Number of operations to batch before flushing

        Yields:
            list: Buffer for batch operations

        Example:
            async with transaction_manager.batch_operation() as batch:
                for item in large_dataset:
                    batch.append(item)
                    if len(batch) >= 100:
                        await session.bulk_insert_mappings(Model, batch)
                        batch.clear()
        """
        batch_buffer = []

        try:
            yield batch_buffer

            # Final flush if there are remaining items
            if batch_buffer:
                await self._flush_batch(batch_buffer)

        except Exception as e:
            logger.error(f"Batch operation failed: {e}")
            raise

    async def _flush_batch(self, batch: list) -> None:
        """Flush a batch of operations to the database.

        Args:
            batch: List of operations to flush
        """
        try:
            await self.session.flush()
        except SQLAlchemyError as e:
            logger.error(f"Failed to flush batch: {e}")
            raise

    async def execute_with_retry(
        self,
        operation: Any,
        max_retries: int = 3,
        retry_on: Optional[tuple] = None,
    ) -> Any:
        """Execute a database operation with automatic retry on failure.

        Args:
            operation: The database operation to execute
            max_retries: Maximum number of retry attempts
            retry_on: Tuple of exception types to retry on

        Returns:
            The result of the operation

        Raises:
            The last exception if all retries fail
        """
        if retry_on is None:
            retry_on = (SQLAlchemyError,)

        last_exception = None

        for attempt in range(max_retries):
            try:
                async with self.transaction():
                    result = await operation()
                    return result

            except retry_on as e:
                last_exception = e
                logger.warning(
                    f"Database operation failed (attempt {attempt + 1}/{max_retries}): {e}"
                )

                if attempt < max_retries - 1:
                    # Wait before retry with exponential backoff
                    import asyncio

                    await asyncio.sleep(2**attempt)

            except Exception as e:
                # Don't retry on unexpected exceptions
                logger.error(f"Unexpected error in database operation: {e}")
                raise

        # All retries failed
        if last_exception:
            raise last_exception


def create_transaction_manager(session: AsyncSession) -> TransactionManager:
    """Create a new transaction manager instance.

    Args:
        session: SQLAlchemy async session

    Returns:
        TransactionManager instance
    """
    return TransactionManager(session)
