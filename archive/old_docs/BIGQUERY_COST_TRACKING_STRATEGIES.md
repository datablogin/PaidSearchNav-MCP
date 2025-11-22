# BigQuery Customer Cost Tracking Strategies

## 🎯 Overview

For accurate customer billing, we need to track BigQuery costs at the customer level. This document outlines multiple strategies to achieve precise cost attribution.

## 💰 BigQuery Pricing Model

**Understanding BigQuery costs:**
- **Storage**: $0.02 per GB per month
- **Queries**: $5.00 per TB of data processed
- **Streaming Inserts**: $0.05 per 200MB
- **Slots (compute)**: $0.04 per slot per hour (optional)

## 🏗️ Strategy 1: Customer-Specific Datasets (Recommended)

### Implementation
Create separate datasets per customer for complete cost isolation.

```sql
-- Customer-specific datasets
CREATE SCHEMA `fitness-connection-469620.customer_646_990_6417`
CREATE SCHEMA `fitness-connection-469620.customer_952_408_0160` 
```

### Advantages
✅ **Perfect cost isolation** - Each customer has dedicated storage/compute  
✅ **Simple billing** - Direct BigQuery billing reports by dataset  
✅ **Data privacy** - Complete customer data separation  
✅ **Easy cost tracking** - Use BigQuery's native cost reporting  

### Cost Tracking Implementation
```python
class CustomerDatasetManager:
    def get_customer_dataset(self, customer_id: str) -> str:
        """Get customer-specific dataset name."""
        clean_id = customer_id.replace("-", "_")
        return f"customer_{clean_id}"
    
    async def get_customer_costs(self, customer_id: str, date_range: str) -> Dict[str, float]:
        """Get BigQuery costs for specific customer dataset."""
        dataset = self.get_customer_dataset(customer_id)
        
        query = f"""
        SELECT 
            SUM(total_bytes_processed) / POWER(1024, 4) as tb_processed,
            SUM(total_bytes_processed) / POWER(1024, 4) * 5.0 as query_cost_usd,
            SUM(total_slot_ms) / 1000 / 3600 * 0.04 as slot_cost_usd
        FROM `{self.project_id}.region-us.INFORMATION_SCHEMA.JOBS_BY_PROJECT`
        WHERE creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {date_range})
        AND destination_table.dataset_id = '{dataset}'
        """
        
        result = await self.execute_query(query)
        return {
            "customer_id": customer_id,
            "tb_processed": result["tb_processed"],
            "query_cost_usd": result["query_cost_usd"],
            "slot_cost_usd": result["slot_cost_usd"],
            "total_cost_usd": result["query_cost_usd"] + result["slot_cost_usd"]
        }
```

## 🏗️ Strategy 2: Query Labels & Job Metadata

### Implementation
Use BigQuery job labels to tag all queries with customer information.

```python
class CustomerQueryTracker:
    async def execute_customer_query(self, customer_id: str, query: str):
        """Execute query with customer tracking labels."""
        from google.cloud import bigquery
        
        client = bigquery.Client()
        job_config = bigquery.QueryJobConfig(
            labels={
                "customer_id": customer_id.replace("-", "_"),
                "service": "paidsearchnav",
                "tier": "premium",
                "analyzer": "search_terms"  # Dynamic based on analysis type
            },
            use_query_cache=True,
            maximum_bytes_billed=1_000_000_000  # 1GB limit per query
        )
        
        query_job = client.query(query, job_config=job_config)
        return query_job.result()
    
    async def get_customer_query_costs(self, customer_id: str) -> Dict[str, Any]:
        """Get costs for all queries tagged with customer ID."""
        clean_id = customer_id.replace("-", "_")
        
        cost_query = f"""
        SELECT 
            labels.value as customer_label,
            SUM(total_bytes_processed) / POWER(1024, 4) as tb_processed,
            SUM(total_bytes_processed) / POWER(1024, 4) * 5.0 as estimated_cost_usd,
            COUNT(*) as query_count,
            AVG(total_bytes_processed) as avg_bytes_per_query
        FROM `{self.project_id}.region-us.INFORMATION_SCHEMA.JOBS_BY_PROJECT`,
        UNNEST(labels) as labels
        WHERE labels.key = 'customer_id' 
        AND labels.value = '{clean_id}'
        AND creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 1 DAY)
        GROUP BY labels.value
        """
        
        return await self.execute_query(cost_query)
```

## 🏗️ Strategy 3: Table-Level Cost Attribution

### Implementation
Add customer_id to all tables and track costs by data volume per customer.

```sql
-- Enhanced table schema with customer tracking
CREATE TABLE `paid_search_nav.search_terms` (
    customer_id STRING NOT NULL,
    date DATE NOT NULL,
    search_term STRING,
    -- ... other fields
    storage_bytes_estimate INT64,  -- Track approximate storage per row
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
)
PARTITION BY date
CLUSTER BY customer_id;

-- Cost tracking view
CREATE VIEW customer_storage_costs AS
SELECT 
    customer_id,
    DATE(created_at) as usage_date,
    COUNT(*) as rows_created,
    SUM(storage_bytes_estimate) / POWER(1024, 3) as gb_stored,
    SUM(storage_bytes_estimate) / POWER(1024, 3) * 0.02 as monthly_storage_cost_usd
FROM `paid_search_nav.search_terms`
GROUP BY customer_id, DATE(created_at);
```

### Python Implementation
```python
class TableCostTracker:
    async def track_customer_data_usage(self, customer_id: str, table_name: str, data: List[Dict]) -> Dict[str, float]:
        """Track data insertion and estimate costs."""
        
        # Estimate storage size
        estimated_bytes = sum(len(str(row).encode('utf-8')) for row in data)
        estimated_gb = estimated_bytes / (1024**3)
        
        # Calculate costs
        storage_cost_monthly = estimated_gb * 0.02  # $0.02 per GB per month
        streaming_cost = (estimated_bytes / (200 * 1024**2)) * 0.05  # $0.05 per 200MB
        
        # Store cost tracking record
        cost_record = {
            "customer_id": customer_id,
            "table_name": table_name,
            "timestamp": datetime.utcnow(),
            "rows_inserted": len(data),
            "bytes_inserted": estimated_bytes,
            "estimated_storage_cost_monthly": storage_cost_monthly,
            "streaming_insert_cost": streaming_cost,
            "total_estimated_cost": storage_cost_monthly + streaming_cost
        }
        
        await self.store_cost_record(cost_record)
        return cost_record
```

## 🏗️ Strategy 4: Real-Time Cost Monitoring Service

### Implementation
Create a dedicated service that monitors BigQuery usage in real-time.

```python
class RealTimeCostMonitor:
    def __init__(self):
        self.customer_budgets = {}  # customer_id -> daily_budget_usd
        self.current_usage = {}     # customer_id -> current_day_usage_usd
        
    async def monitor_query_execution(self, customer_id: str, query_job):
        """Monitor query execution and track costs."""
        # Wait for job completion
        query_job.result()
        
        # Calculate actual costs
        bytes_processed = query_job.total_bytes_processed or 0
        cost_usd = (bytes_processed / (1024**4)) * 5.0  # $5 per TB
        
        # Update usage tracking
        today = datetime.now().date()
        usage_key = f"{customer_id}:{today}"
        
        if usage_key not in self.current_usage:
            self.current_usage[usage_key] = 0
        
        self.current_usage[usage_key] += cost_usd
        
        # Check budget alerts
        daily_budget = self.customer_budgets.get(customer_id, 100.0)
        current_usage = self.current_usage.get(usage_key, 0)
        
        if current_usage > daily_budget * 0.8:  # 80% threshold
            await self.send_budget_alert(customer_id, current_usage, daily_budget)
        
        # Store detailed cost record
        await self.store_cost_detail({
            "customer_id": customer_id,
            "job_id": query_job.job_id,
            "timestamp": datetime.utcnow(),
            "bytes_processed": bytes_processed,
            "cost_usd": cost_usd,
            "query_type": query_job.labels.get("analyzer", "unknown"),
            "daily_usage_total": current_usage
        })
        
        return cost_usd
```

## 🏗️ Strategy 5: Google Cloud Billing Export Integration

### Implementation
Export BigQuery costs to BigQuery for detailed analysis (meta approach).

```sql
-- Enable billing export to BigQuery first, then query it
SELECT 
    service.description as service_name,
    labels.value as customer_id,
    SUM(cost) as total_cost_usd,
    SUM(usage.amount) as usage_amount,
    usage.unit as usage_unit
FROM `billing_export.gcp_billing_export_v1_XXXXXX`
CROSS JOIN UNNEST(labels) as labels
WHERE service.description = "BigQuery"
AND labels.key = "customer_id"
AND export_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 1 DAY)
GROUP BY service_name, customer_id, usage_unit
ORDER BY total_cost_usd DESC;
```

## 💡 Hybrid Approach (Recommended)

Combine multiple strategies for maximum accuracy:

```python
class ComprehensiveCostTracker:
    def __init__(self):
        self.dataset_manager = CustomerDatasetManager()
        self.query_tracker = CustomerQueryTracker() 
        self.table_tracker = TableCostTracker()
        self.realtime_monitor = RealTimeCostMonitor()
    
    async def track_customer_operation(self, customer_id: str, operation_type: str, **kwargs):
        """Comprehensive cost tracking for any customer operation."""
        
        cost_breakdown = {
            "customer_id": customer_id,
            "operation_type": operation_type,
            "timestamp": datetime.utcnow(),
            "costs": {}
        }
        
        # Strategy 1: Dataset-level tracking
        if operation_type == "query":
            dataset_costs = await self.dataset_manager.get_customer_costs(customer_id, "1 HOUR")
            cost_breakdown["costs"]["dataset_level"] = dataset_costs
        
        # Strategy 2: Query label tracking  
        if "query_job" in kwargs:
            query_costs = await self.realtime_monitor.monitor_query_execution(
                customer_id, kwargs["query_job"]
            )
            cost_breakdown["costs"]["query_level"] = query_costs
        
        # Strategy 3: Table-level tracking
        if operation_type == "data_insert" and "data" in kwargs:
            table_costs = await self.table_tracker.track_customer_data_usage(
                customer_id, kwargs.get("table_name"), kwargs["data"]
            )
            cost_breakdown["costs"]["table_level"] = table_costs
        
        # Calculate total estimated cost
        total_cost = sum(
            cost for cost_type in cost_breakdown["costs"].values() 
            for cost in (cost_type.values() if isinstance(cost_type, dict) else [cost_type])
            if isinstance(cost, (int, float))
        )
        
        cost_breakdown["total_estimated_cost_usd"] = total_cost
        
        # Store comprehensive cost record
        await self.store_comprehensive_cost_record(cost_breakdown)
        
        return cost_breakdown
```

## 📊 Cost Reporting & Billing Integration

### Customer Billing Report
```python
class CustomerBillingReporter:
    async def generate_monthly_bill(self, customer_id: str, month: str) -> Dict[str, Any]:
        """Generate detailed monthly BigQuery bill for customer."""
        
        bill = {
            "customer_id": customer_id,
            "billing_period": month,
            "bigquery_usage": {
                "storage_gb_hours": 0,
                "query_tb_processed": 0,
                "streaming_inserts_mb": 0,
                "slot_hours": 0
            },
            "costs": {
                "storage_cost_usd": 0,
                "query_cost_usd": 0,
                "streaming_cost_usd": 0,
                "slot_cost_usd": 0,
                "total_cost_usd": 0
            },
            "usage_details": []
        }
        
        # Get comprehensive usage data
        usage_data = await self.get_customer_monthly_usage(customer_id, month)
        
        # Calculate detailed costs
        for usage_record in usage_data:
            detail = {
                "date": usage_record["date"],
                "operation_type": usage_record["operation_type"],
                "resource_usage": usage_record["resource_usage"],
                "cost_usd": usage_record["cost_usd"]
            }
            bill["usage_details"].append(detail)
            
            # Aggregate usage
            for metric in bill["bigquery_usage"]:
                if metric in usage_record:
                    bill["bigquery_usage"][metric] += usage_record[metric]
        
        # Calculate total costs
        bill["costs"]["total_cost_usd"] = sum(bill["costs"].values())
        
        return bill
```

## 🔧 Implementation Priority

### Phase 1: Basic Tracking (Immediate)
1. **Query Labels** - Tag all queries with customer_id
2. **Real-time Monitoring** - Track costs as queries execute
3. **Budget Alerts** - Prevent cost overruns

### Phase 2: Enhanced Tracking (Month 1)
1. **Customer Datasets** - Separate datasets for largest customers
2. **Table-level Attribution** - Track storage costs by customer
3. **Billing Reports** - Monthly cost breakdowns

### Phase 3: Advanced Tracking (Month 2)
1. **Billing Export Integration** - Use Google Cloud billing data
2. **Predictive Cost Models** - Forecast customer usage
3. **Automated Cost Optimization** - Query optimization by cost

## 💰 Cost Management Best Practices

### Budget Controls
```python
CUSTOMER_BUDGET_LIMITS = {
    "646-990-6417": {"daily": 50.0, "monthly": 1000.0},  # Fitness Connection
    "952-408-0160": {"daily": 25.0, "monthly": 500.0},   # Cotton Patch Cafe
}

async def enforce_budget_limits(customer_id: str, estimated_cost: float):
    """Enforce budget limits before executing expensive operations."""
    limits = CUSTOMER_BUDGET_LIMITS.get(customer_id, {"daily": 10.0, "monthly": 100.0})
    current_usage = await get_current_usage(customer_id)
    
    if current_usage["daily"] + estimated_cost > limits["daily"]:
        raise BudgetExceededException(
            f"Daily budget exceeded: {current_usage['daily'] + estimated_cost} > {limits['daily']}"
        )
```

This comprehensive approach ensures accurate customer billing while preventing cost overruns! 💡