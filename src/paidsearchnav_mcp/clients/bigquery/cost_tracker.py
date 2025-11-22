"""Customer-specific BigQuery cost tracking and billing."""

import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

from .cost_monitor_enhanced import EnhancedBigQueryCostMonitor

logger = logging.getLogger(__name__)


class CustomerCostTracker:
    """Track BigQuery costs by customer for accurate billing."""

    def __init__(self, config, authenticator, database_url: Optional[str] = None):
        """Initialize cost tracker."""
        self.config = config
        self.authenticator = authenticator
        self.database_url = database_url
        self.cost_records = []  # Fallback in-memory storage
        self._use_database = database_url is not None

        # Initialize enhanced cost monitor for advanced features
        self._enhanced_monitor = EnhancedBigQueryCostMonitor(config, authenticator)

    async def track_query_execution(
        self, customer_id: str, query_job, analyzer_type: str = "unknown"
    ) -> Dict[str, Any]:
        """Track costs for a specific customer query execution."""

        try:
            # Wait for job completion to get actual costs
            query_job.result()

            # Get actual resource usage
            bytes_processed = query_job.total_bytes_processed or 0
            slot_millis = query_job.slot_millis or 0

            # Calculate costs based on BigQuery pricing
            query_cost_usd = self._calculate_query_cost(bytes_processed)
            slot_cost_usd = self._calculate_slot_cost(slot_millis)
            total_cost_usd = query_cost_usd + slot_cost_usd

            # Create cost record
            cost_record = {
                "customer_id": customer_id,
                "job_id": query_job.job_id,
                "timestamp": datetime.utcnow(),
                "analyzer_type": analyzer_type,
                "bytes_processed": bytes_processed,
                "slot_millis": slot_millis,
                "query_cost_usd": float(query_cost_usd),
                "slot_cost_usd": float(slot_cost_usd),
                "total_cost_usd": float(total_cost_usd),
                "job_duration_seconds": (
                    query_job.ended - query_job.started
                ).total_seconds()
                if query_job.ended
                else None,
                "query_type": "analytics",
            }

            # Store cost record
            await self._store_cost_record(cost_record)

            # Check budget limits
            await self._check_budget_limits(customer_id, total_cost_usd)

            # Enhanced budget enforcement check
            enforcement_result = await self._enhanced_monitor.check_budget_enforcement(
                customer_id, total_cost_usd
            )
            if not enforcement_result.get("allowed", True):
                logger.warning(
                    f"Budget enforcement triggered for customer {customer_id}: {enforcement_result.get('reason', 'Unknown')}"
                )
                cost_record["budget_enforcement"] = enforcement_result

            logger.info(
                f"Query cost tracked: Customer {customer_id}, "
                f"Analyzer {analyzer_type}, Cost ${total_cost_usd:.4f}"
            )

            return cost_record

        except Exception as e:
            logger.error(f"Failed to track query cost for customer {customer_id}: {e}")
            return {"customer_id": customer_id, "error": str(e), "total_cost_usd": 0.0}

    async def track_streaming_insert(
        self, customer_id: str, table_name: str, data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Track costs for streaming data inserts."""

        try:
            # Estimate data size
            estimated_bytes = sum(len(str(row).encode("utf-8")) for row in data)
            estimated_mb = estimated_bytes / (1024 * 1024)

            # Calculate streaming insert costs ($0.05 per 200MB)
            streaming_cost_usd = (estimated_mb / 200) * 0.05

            # Estimate storage costs ($0.02 per GB per month)
            estimated_gb = estimated_bytes / (1024**3)
            monthly_storage_cost_usd = estimated_gb * 0.02

            cost_record = {
                "customer_id": customer_id,
                "table_name": table_name,
                "timestamp": datetime.utcnow(),
                "operation_type": "streaming_insert",
                "rows_inserted": len(data),
                "bytes_inserted": estimated_bytes,
                "streaming_cost_usd": float(streaming_cost_usd),
                "monthly_storage_cost_usd": float(monthly_storage_cost_usd),
                "total_cost_usd": float(streaming_cost_usd),  # Only immediate costs
            }

            await self._store_cost_record(cost_record)

            logger.info(
                f"Streaming cost tracked: Customer {customer_id}, "
                f"Table {table_name}, {len(data)} rows, Cost ${streaming_cost_usd:.4f}"
            )

            return cost_record

        except Exception as e:
            logger.error(
                f"Failed to track streaming cost for customer {customer_id}: {e}"
            )
            return {"customer_id": customer_id, "error": str(e), "total_cost_usd": 0.0}

    async def get_customer_daily_costs(
        self, customer_id: str, target_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """Get BigQuery costs for a specific customer and date."""

        if target_date is None:
            target_date = date.today()

        try:
            # Query actual BigQuery job costs from INFORMATION_SCHEMA
            client = await self.authenticator.get_client()

            query = f"""
            SELECT
                COUNT(*) as total_jobs,
                SUM(total_bytes_processed) as total_bytes_processed,
                SUM(total_slot_ms) as total_slot_ms,
                SUM(total_bytes_processed) / POWER(1024, 4) * 5.0 as query_cost_usd,
                SUM(total_slot_ms) / 1000 / 3600 * 0.04 as slot_cost_usd,
                (SUM(total_bytes_processed) / POWER(1024, 4) * 5.0) +
                (SUM(total_slot_ms) / 1000 / 3600 * 0.04) as total_cost_usd
            FROM `{self.config.project_id}.region-us.INFORMATION_SCHEMA.JOBS_BY_PROJECT`
            WHERE DATE(creation_time) = @target_date
            AND (
                -- Look for customer ID in various places
                user_email LIKE @customer_email_pattern
                OR job_id LIKE @customer_job_pattern
                OR EXISTS (
                    SELECT 1 FROM UNNEST(labels) as label
                    WHERE label.key = 'customer_id' AND label.value = @customer_label
                )
            )
            """

            from google.cloud import bigquery

            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("target_date", "DATE", target_date),
                    bigquery.ScalarQueryParameter(
                        "customer_email_pattern", "STRING", f"%{customer_id}%"
                    ),
                    bigquery.ScalarQueryParameter(
                        "customer_job_pattern", "STRING", f"%{customer_id}%"
                    ),
                    bigquery.ScalarQueryParameter(
                        "customer_label", "STRING", customer_id.replace("-", "_")
                    ),
                ]
            )

            query_job = client.query(query, job_config=job_config)
            results = list(query_job.result())

            if results:
                row = results[0]
                return {
                    "customer_id": customer_id,
                    "date": target_date.isoformat(),
                    "total_jobs": int(row.total_jobs or 0),
                    "total_bytes_processed": int(row.total_bytes_processed or 0),
                    "total_slot_ms": int(row.total_slot_ms or 0),
                    "query_cost_usd": float(row.query_cost_usd or 0),
                    "slot_cost_usd": float(row.slot_cost_usd or 0),
                    "total_cost_usd": float(row.total_cost_usd or 0),
                    "data_source": "bigquery_information_schema",
                }

            return {
                "customer_id": customer_id,
                "date": target_date.isoformat(),
                "total_cost_usd": 0.0,
                "message": "No BigQuery usage found for this date",
            }

        except Exception as e:
            logger.error(f"Failed to get daily costs for customer {customer_id}: {e}")
            return {
                "customer_id": customer_id,
                "date": target_date.isoformat(),
                "error": str(e),
                "total_cost_usd": 0.0,
            }

    async def get_customer_monthly_bill(
        self, customer_id: str, year: int, month: int
    ) -> Dict[str, Any]:
        """Generate detailed monthly BigQuery bill for customer."""

        # Calculate date range for the month
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(year, month + 1, 1) - timedelta(days=1)

        bill = {
            "customer_id": customer_id,
            "billing_period": f"{year}-{month:02d}",
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "usage_summary": {
                "total_queries": 0,
                "total_bytes_processed": 0,
                "total_slot_hours": 0,
                "total_streaming_inserts": 0,
            },
            "cost_breakdown": {
                "query_processing_usd": 0.0,
                "compute_slots_usd": 0.0,
                "streaming_inserts_usd": 0.0,
                "storage_usd": 0.0,
                "total_usd": 0.0,
            },
            "daily_costs": [],
            "analyzer_usage": {},
            "generated_at": datetime.utcnow().isoformat(),
        }

        # Get daily costs for each day in the month
        current_date = start_date
        while current_date <= end_date:
            daily_cost = await self.get_customer_daily_costs(customer_id, current_date)
            bill["daily_costs"].append(daily_cost)

            # Aggregate usage
            if "error" not in daily_cost:
                bill["usage_summary"]["total_queries"] += daily_cost.get(
                    "total_jobs", 0
                )
                bill["usage_summary"]["total_bytes_processed"] += daily_cost.get(
                    "total_bytes_processed", 0
                )
                bill["cost_breakdown"]["query_processing_usd"] += daily_cost.get(
                    "query_cost_usd", 0
                )
                bill["cost_breakdown"]["compute_slots_usd"] += daily_cost.get(
                    "slot_cost_usd", 0
                )

            current_date += timedelta(days=1)

        # Calculate total costs
        bill["cost_breakdown"]["total_usd"] = sum(
            [
                bill["cost_breakdown"]["query_processing_usd"],
                bill["cost_breakdown"]["compute_slots_usd"],
                bill["cost_breakdown"]["streaming_inserts_usd"],
                bill["cost_breakdown"]["storage_usd"],
            ]
        )

        return bill

    async def set_customer_budget(
        self, customer_id: str, daily_limit_usd: float, monthly_limit_usd: float
    ) -> Dict[str, Any]:
        """Set budget limits for a customer."""

        budget_config = {
            "customer_id": customer_id,
            "daily_limit_usd": daily_limit_usd,
            "monthly_limit_usd": monthly_limit_usd,
            "updated_at": datetime.utcnow(),
            "alerts_enabled": True,
        }

        # Store budget configuration (would use database in real implementation)
        await self._store_budget_config(budget_config)

        return budget_config

    def _calculate_query_cost(self, bytes_processed: int) -> Decimal:
        """Calculate query cost based on bytes processed."""
        tb_processed = Decimal(bytes_processed) / Decimal(1024**4)
        return tb_processed * Decimal("5.0")  # $5 per TB

    def _calculate_slot_cost(self, slot_millis: int) -> Decimal:
        """Calculate slot cost based on slot milliseconds used."""
        slot_hours = Decimal(slot_millis) / Decimal(1000) / Decimal(3600)
        return slot_hours * Decimal("0.04")  # $0.04 per slot hour

    async def _store_cost_record(self, cost_record: Dict[str, Any]):
        """Store cost record with database persistence."""
        if self._use_database:
            await self._store_to_database(cost_record)
        else:
            # Fallback to in-memory storage
            self.cost_records.append(cost_record)
            logger.debug(
                f"Stored cost record (in-memory): {cost_record['customer_id']} - "
                f"${cost_record.get('total_cost_usd', 0):.4f}"
            )

    async def _store_to_database(self, cost_record: Dict[str, Any]):
        """Store cost record to database table."""
        try:
            # Create cost tracking table SQL
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS bigquery_cost_tracking (
                id SERIAL PRIMARY KEY,
                customer_id VARCHAR(255) NOT NULL,
                job_id VARCHAR(255),
                table_name VARCHAR(255),
                timestamp TIMESTAMP NOT NULL,
                operation_type VARCHAR(50) NOT NULL,
                analyzer_type VARCHAR(50),
                bytes_processed BIGINT DEFAULT 0,
                slot_millis BIGINT DEFAULT 0,
                rows_inserted INTEGER DEFAULT 0,
                bytes_inserted BIGINT DEFAULT 0,
                query_cost_usd DECIMAL(10, 6) DEFAULT 0,
                slot_cost_usd DECIMAL(10, 6) DEFAULT 0,
                streaming_cost_usd DECIMAL(10, 6) DEFAULT 0,
                monthly_storage_cost_usd DECIMAL(10, 6) DEFAULT 0,
                total_cost_usd DECIMAL(10, 6) DEFAULT 0,
                job_duration_seconds DECIMAL(10, 3),
                query_type VARCHAR(50),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_customer_timestamp (customer_id, timestamp),
                INDEX idx_operation_type (operation_type)
            );
            """

            # Insert cost record SQL
            insert_sql = """
            INSERT INTO bigquery_cost_tracking (
                customer_id, job_id, table_name, timestamp, operation_type,
                analyzer_type, bytes_processed, slot_millis, rows_inserted,
                bytes_inserted, query_cost_usd, slot_cost_usd, streaming_cost_usd,
                monthly_storage_cost_usd, total_cost_usd, job_duration_seconds, query_type
            ) VALUES (
                %(customer_id)s, %(job_id)s, %(table_name)s, %(timestamp)s, %(operation_type)s,
                %(analyzer_type)s, %(bytes_processed)s, %(slot_millis)s, %(rows_inserted)s,
                %(bytes_inserted)s, %(query_cost_usd)s, %(slot_cost_usd)s, %(streaming_cost_usd)s,
                %(monthly_storage_cost_usd)s, %(total_cost_usd)s, %(job_duration_seconds)s, %(query_type)s
            )
            """

            # Note: In a real implementation, this would use the database connection
            # from the application's database pool. For now, we'll log the SQL and data
            # and fall back to in-memory storage.

            logger.info(f"Would execute: {create_table_sql}")
            logger.info(f"Would insert cost record: {cost_record}")

            # Fallback to in-memory for now
            self.cost_records.append(cost_record)
            logger.debug(
                f"Stored cost record (database fallback): {cost_record['customer_id']} - "
                f"${cost_record.get('total_cost_usd', 0):.4f}"
            )

        except Exception as e:
            logger.error(f"Failed to store cost record to database: {e}")
            # Fallback to in-memory storage
            self.cost_records.append(cost_record)
            logger.debug("Fallback to in-memory storage for cost record")

    async def _store_budget_config(self, budget_config: Dict[str, Any]):
        """Store budget configuration (implement with actual database)."""
        # In production, store in database
        logger.info(
            f"Budget set for customer {budget_config['customer_id']}: ${budget_config['daily_limit_usd']}/day"
        )

    async def _check_budget_limits(self, customer_id: str, additional_cost: float):
        """Check if customer is approaching budget limits."""
        # Get current daily usage
        daily_costs = await self.get_customer_daily_costs(customer_id)
        current_usage = daily_costs.get("total_cost_usd", 0)

        # Default budget limits (would load from database)
        daily_limit = 50.0  # $50 per day default

        if current_usage + additional_cost > daily_limit * 0.9:  # 90% threshold
            logger.warning(
                f"Customer {customer_id} approaching daily budget: "
                f"${current_usage + additional_cost:.2f} / ${daily_limit:.2f}"
            )

            # In production, would send alert/notification
            await self._send_budget_alert(
                customer_id, current_usage + additional_cost, daily_limit
            )

    async def _send_budget_alert(
        self, customer_id: str, current_usage: float, limit: float
    ):
        """Send budget alert (implement with actual notification system)."""
        logger.warning(
            f"BUDGET ALERT: Customer {customer_id} has used ${current_usage:.2f} of ${limit:.2f} daily limit"
        )
        # In production: send email, Slack notification, etc.

    # === ENHANCED COST MONITORING METHODS ===

    async def get_real_time_cost_monitoring(self, customer_id: str) -> Dict[str, Any]:
        """Get real-time cost monitoring data for a customer."""
        return await self._enhanced_monitor.get_real_time_costs(customer_id)

    async def check_enhanced_budget_enforcement(
        self, customer_id: str, additional_cost: float = 0.0
    ) -> Dict[str, Any]:
        """Check enhanced budget enforcement with throttling and circuit breakers."""
        return await self._enhanced_monitor.check_budget_enforcement(
            customer_id, additional_cost
        )

    async def detect_cost_anomalies(
        self, customer_id: str, lookback_days: int = 7
    ) -> List[Dict[str, Any]]:
        """Detect unusual cost patterns for a customer."""
        patterns = await self._enhanced_monitor.detect_unusual_patterns(
            customer_id, lookback_days
        )
        return [pattern.dict() for pattern in patterns]

    async def generate_comprehensive_cost_analytics(
        self, customer_id: str, period_days: int = 30
    ) -> Dict[str, Any]:
        """Generate comprehensive cost analytics for a customer."""
        return await self._enhanced_monitor.generate_cost_analytics(
            customer_id, period_days
        )

    async def get_automated_cost_report(
        self, customer_id: str, report_type: str = "weekly"
    ) -> Dict[str, Any]:
        """Generate automated cost summary reports."""
        return await self._enhanced_monitor.get_cost_summary_report(
            customer_id, report_type
        )

    async def configure_customer_budget(
        self,
        customer_id: str,
        tier: str,
        daily_limit_usd: float,
        monthly_limit_usd: float,
        emergency_limit_usd: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Configure enhanced budget limits for a customer."""
        budget_config = await self._enhanced_monitor.set_customer_budget(
            customer_id, tier, daily_limit_usd, monthly_limit_usd, emergency_limit_usd
        )
        return budget_config.dict()

    async def get_all_customer_budgets(self) -> Dict[str, Dict[str, Any]]:
        """Get all customer budget configurations."""
        budgets = await self._enhanced_monitor.get_customer_budgets()
        return {customer_id: config.dict() for customer_id, config in budgets.items()}


class CustomerBillingReporter:
    """Generate customer billing reports for BigQuery usage."""

    def __init__(self, cost_tracker: CustomerCostTracker):
        self.cost_tracker = cost_tracker

    async def generate_invoice_data(
        self, customer_id: str, year: int, month: int
    ) -> Dict[str, Any]:
        """Generate invoice data for customer billing system integration."""

        monthly_bill = await self.cost_tracker.get_customer_monthly_bill(
            customer_id, year, month
        )

        # Convert to invoice format
        invoice_data = {
            "customer_id": customer_id,
            "invoice_period": monthly_bill["billing_period"],
            "service_name": "PaidSearchNav Premium Analytics",
            "line_items": [
                {
                    "description": "BigQuery Data Processing",
                    "unit": "TB processed",
                    "quantity": monthly_bill["usage_summary"]["total_bytes_processed"]
                    / (1024**4),
                    "unit_price": 5.00,
                    "total": monthly_bill["cost_breakdown"]["query_processing_usd"],
                },
                {
                    "description": "BigQuery Compute Slots",
                    "unit": "slot-hours",
                    "quantity": monthly_bill["usage_summary"]["total_slot_hours"],
                    "unit_price": 0.04,
                    "total": monthly_bill["cost_breakdown"]["compute_slots_usd"],
                },
            ],
            "subtotal": monthly_bill["cost_breakdown"]["total_usd"],
            "total": monthly_bill["cost_breakdown"]["total_usd"],
            "currency": "USD",
        }

        return invoice_data
