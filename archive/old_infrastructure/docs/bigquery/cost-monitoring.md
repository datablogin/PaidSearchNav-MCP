# BigQuery Cost Monitoring Guide

Comprehensive guide for managing and monitoring BigQuery costs with PaidSearchNav's advanced cost management system.

## Table of Contents

1. [Overview](#overview)
2. [Cost Calculation](#cost-calculation)
3. [Budget Management](#budget-management)
4. [Real-time Monitoring](#real-time-monitoring)
5. [Alert System](#alert-system)
6. [Cost Optimization](#cost-optimization)
7. [Reporting and Analytics](#reporting-and-analytics)

## Overview

PaidSearchNav's BigQuery cost monitoring system provides comprehensive cost management with real-time tracking, budget enforcement, and automated alerts to prevent unexpected expenses while maintaining analytical capabilities.

### Key Features

- **Real-time Cost Tracking**: Sub-5-minute cost monitoring using BigQuery INFORMATION_SCHEMA
- **Budget Enforcement**: Automatic throttling and circuit breakers
- **Multi-tier Support**: Different budget levels for standard, premium, and enterprise customers
- **Anomaly Detection**: Automatic detection of unusual usage patterns
- **Cost Analytics**: Detailed breakdowns and optimization recommendations

### Cost Management Philosophy

1. **Prevention over Reaction**: Proactive budget controls prevent cost overruns
2. **Transparency**: Clear visibility into all cost components and drivers
3. **Flexibility**: Configurable limits and thresholds for different use cases
4. **Intelligence**: Smart alerting and pattern recognition to optimize usage

## Cost Calculation

### BigQuery Pricing Model

BigQuery uses a pay-as-you-go model with two main cost components:

```python
# Cost calculation formula used by PaidSearchNav
def calculate_bigquery_cost(bytes_processed: int, slot_ms: int) -> float:
    """Calculate BigQuery cost based on usage."""
    
    # Query costs: $5 per TB of data processed
    tb_processed = bytes_processed / (1024 ** 4)  # Convert to TB
    query_cost = tb_processed * 5.0
    
    # Compute costs: $0.04 per slot-hour
    slot_hours = slot_ms / 1000 / 3600  # Convert ms to hours
    compute_cost = slot_hours * 0.04
    
    return query_cost + compute_cost
```

### Cost Components Breakdown

| Component | Pricing | Description |
|-----------|---------|-------------|
| **Query Processing** | $5.00 per TB | Data processed by queries |
| **Compute (Slots)** | $0.04 per slot-hour | Computational resources used |
| **Storage** | $0.02 per TB/month | Data stored in BigQuery (not tracked real-time) |
| **Streaming** | $0.01 per 200K rows | Real-time data insertion (if used) |

### Real-time Cost Tracking Query

The system uses the following query to track costs in real-time:

```sql
SELECT 
    job_id,
    user_email,
    creation_time,
    total_bytes_processed,
    total_slot_ms,
    
    -- Cost calculations
    total_bytes_processed / POWER(1024, 4) * 5.0 as query_cost_usd,
    total_slot_ms / 1000 / 3600 * 0.04 as slot_cost_usd,
    (total_bytes_processed / POWER(1024, 4) * 5.0) +
    (total_slot_ms / 1000 / 3600 * 0.04) as total_cost_usd,
    
    -- Metadata
    labels,
    job_type,
    state
FROM `{project_id}.region-us.INFORMATION_SCHEMA.JOBS_BY_PROJECT`
WHERE creation_time >= @start_time
  AND creation_time <= @current_time
  AND job_type = 'QUERY'
  AND state = 'DONE'
  AND (
    user_email LIKE @customer_pattern
    OR EXISTS (
      SELECT 1 FROM UNNEST(labels) as label
      WHERE label.key = 'customer_id' AND label.value = @customer_id
    )
  )
ORDER BY creation_time DESC
```

## Budget Management

### Customer Tiers and Default Limits

The system supports three customer tiers with different budget allocations:

```python
# Default budget configurations
TIER_BUDGETS = {
    "standard": {
        "daily_limit_usd": 10.00,
        "monthly_limit_usd": 300.00,
        "emergency_limit_usd": 50.00,
        "features": ["basic_monitoring"]
    },
    "premium": {
        "daily_limit_usd": 50.00,
        "monthly_limit_usd": 1500.00,
        "emergency_limit_usd": 200.00,
        "features": ["real_time_monitoring", "advanced_analytics", "custom_alerts"]
    },
    "enterprise": {
        "daily_limit_usd": 200.00,
        "monthly_limit_usd": 6000.00,
        "emergency_limit_usd": 1000.00,
        "features": ["all_premium_features", "ml_predictions", "priority_support"]
    }
}
```

### Budget Configuration

Administrators can configure custom budgets for specific customers:

```http
POST /api/v1/bigquery/cost-monitoring/budget-config
Content-Type: application/json
Authorization: Bearer <admin_token>

{
  "customer_id": "customer_123",
  "tier": "premium",
  "daily_limit_usd": 75.00,
  "monthly_limit_usd": 2250.00,
  "emergency_limit_usd": 300.00
}
```

### Budget Validation Rules

The system enforces the following validation rules:

1. **Minimum Limits**: Daily ≥ $1.00, Monthly ≥ $10.00
2. **Maximum Limits**: Daily ≤ $10,000, Monthly ≤ $100,000
3. **Ratio Constraints**: Monthly ≥ 20x Daily (ensures reasonable monthly coverage)
4. **Emergency Limits**: 1x ≤ Emergency ≤ 20x Daily

## Real-time Monitoring

### Monitoring Dashboard

The real-time monitoring system provides comprehensive visibility:

```http
GET /api/v1/bigquery/cost-monitoring/real-time?customer_id=customer_123&lookback_hours=1
```

**Response Example**:
```json
{
  "success": true,
  "data": {
    "customer_id": "customer_123",
    "timestamp": "2025-08-22T10:30:00Z",
    "lookback_hours": 1,
    
    // Recent activity (last hour)
    "recent_cost_usd": 2.45,
    "recent_bytes_processed": 1073741824,
    "recent_jobs_count": 15,
    
    // Daily totals
    "daily_cost_usd": 12.80,
    "daily_limit_usd": 50.00,
    "daily_remaining_usd": 37.20,
    "daily_usage_percentage": 25.6,
    
    // Monthly totals
    "monthly_cost_usd": 234.50,
    "monthly_limit_usd": 1500.00,
    "monthly_remaining_usd": 1265.50,
    "monthly_usage_percentage": 15.6,
    
    // Status and alerts
    "status": "within_budget",
    "data_freshness_minutes": 3.2,
    
    // Budget configuration
    "budget_config": {
      "tier": "premium",
      "daily_limit_usd": 50.00,
      "monthly_limit_usd": 1500.00,
      "emergency_limit_usd": 200.00,
      "thresholds": [
        {"percentage": 50.0, "priority": "medium", "action": "monitor"},
        {"percentage": 80.0, "priority": "high", "action": "review"},
        {"percentage": 95.0, "priority": "critical", "action": "throttle"}
      ]
    }
  }
}
```

### Status Indicators

| Status | Usage Range | Description | Recommended Action |
|--------|-------------|-------------|-------------------|
| `within_budget` | 0-50% | Normal operation | Continue monitoring |
| `moderate_usage` | 50-80% | Moderate usage | Review usage patterns |
| `approaching_limit` | 80-95% | High usage | Consider optimization |
| `over_budget` | 95-100% | Budget exceeded | Immediate attention required |
| `emergency` | >100% | Emergency limit hit | Operations suspended |

### Data Freshness

The system provides data freshness indicators:

- **Target Freshness**: < 5 minutes (BigQuery processing delay)
- **Acceptable Range**: 5-10 minutes
- **Alert Threshold**: > 15 minutes (may indicate system issues)

## Alert System

### Alert Thresholds

The system uses a three-tier alert system:

```python
# Default alert thresholds
DEFAULT_THRESHOLDS = [
    {
        "percentage": 50.0,
        "priority": "medium",
        "action": "monitor",
        "description": "Budget halfway point reached"
    },
    {
        "percentage": 80.0,
        "priority": "high", 
        "action": "review",
        "description": "High budget utilization - review usage"
    },
    {
        "percentage": 95.0,
        "priority": "critical",
        "action": "throttle",
        "description": "Budget nearly exhausted - throttling may occur"
    }
]
```

### Alert Cooldown Mechanism

To prevent alert flooding, the system implements cooldown periods:

- **Default Cooldown**: 1 hour per threshold per customer
- **Configurable**: Administrators can adjust cooldown periods
- **Override**: Critical alerts can bypass cooldown for emergency situations

### Alert Channels

Alerts are sent through multiple channels:

1. **API Responses**: Immediate feedback in budget enforcement responses
2. **Email Notifications**: For threshold breaches and emergencies
3. **Webhook Integration**: For integration with external systems
4. **Slack/Teams**: Real-time notifications to operations teams

## Cost Optimization

### Optimization Strategies

#### 1. Query Optimization

```sql
-- Example: Optimize large table scans
-- Instead of scanning entire table:
SELECT * FROM large_table WHERE date_column = '2025-08-22';

-- Use partitioning and clustering:
SELECT * FROM large_table 
WHERE _PARTITIONTIME = TIMESTAMP('2025-08-22')
  AND clustered_column = 'specific_value';
```

#### 2. Materialized Views

```sql
-- Create materialized view for frequently accessed aggregations
CREATE MATERIALIZED VIEW analytics.daily_summary
PARTITION BY DATE(created_at)
AS
SELECT 
  DATE(created_at) as date,
  customer_id,
  COUNT(*) as total_queries,
  SUM(cost_usd) as total_cost
FROM analytics.query_logs
GROUP BY DATE(created_at), customer_id;
```

#### 3. Scheduled Queries

```python
# Schedule expensive operations during off-peak hours
OPTIMIZATION_SCHEDULE = {
    "large_aggregations": "02:00 UTC",  # Low-cost period
    "monthly_reports": "03:00 UTC", 
    "data_exports": "04:00 UTC"
}
```

### Cost Analysis and Recommendations

The system provides automated cost optimization recommendations:

```http
GET /api/v1/bigquery/cost-monitoring/analytics?customer_id=customer_123&period_days=30
```

**Example Recommendations**:
```json
{
  "recommendations": [
    "Schedule large analytics jobs during off-peak hours for potential cost savings",
    "Consider using BigQuery materialized views for frequently accessed data", 
    "Review and optimize expensive queries identified in the analytics",
    "Implement query result caching for repeated analysis patterns"
  ],
  "expensive_queries": [
    {
      "job_id": "job_abc123",
      "cost_usd": 15.75,
      "optimization_potential": "high",
      "suggestions": ["Add WHERE clause to limit data processed", "Use appropriate partitioning"]
    }
  ]
}
```

### Performance vs Cost Trade-offs

| Strategy | Cost Impact | Performance Impact | Use Case |
|----------|-------------|-------------------|-----------|
| **Query Caching** | -30-50% | +50-80% faster | Repeated queries |
| **Materialized Views** | -60-80% | +90% faster | Frequent aggregations |
| **Partitioning** | -40-60% | +70% faster | Time-series data |
| **Clustering** | -20-40% | +30% faster | Filtered queries |
| **Scheduled Jobs** | -20-30% | No change | Batch operations |

## Reporting and Analytics

### Cost Analytics Dashboard

The system provides comprehensive cost analytics:

```http
GET /api/v1/bigquery/cost-monitoring/analytics?customer_id=customer_123&period_days=30
```

**Key Metrics Included**:

1. **Cost Summary**
   - Total costs and trends
   - Average daily costs
   - Peak usage analysis

2. **Operation Breakdown**
   - Cost by operation type (keyword analysis, search terms, etc.)
   - Most expensive operations
   - Usage patterns by time

3. **Efficiency Metrics**
   - Cost per TB processed
   - Cost per customer analysis
   - Tier efficiency comparison

4. **ROI Analysis**
   - BigQuery vs CSV processing costs
   - Time savings quantification
   - Cost-benefit analysis

### Automated Reports

The system generates automated reports:

```http
GET /api/v1/bigquery/cost-monitoring/reports/weekly?customer_id=customer_123
```

**Report Types**:
- **Daily**: Last 24 hours summary with immediate insights
- **Weekly**: 7-day trend analysis with optimization suggestions
- **Monthly**: 30-day comprehensive review with budget planning

### Custom Dashboards

Example Grafana dashboard configuration:

```json
{
  "dashboard": {
    "title": "BigQuery Cost Management",
    "panels": [
      {
        "title": "Real-time Cost Trends",
        "type": "timeseries",
        "targets": [
          {"expr": "bigquery_daily_cost_usd", "legendFormat": "Daily Cost"},
          {"expr": "bigquery_daily_limit_usd", "legendFormat": "Daily Limit"}
        ]
      },
      {
        "title": "Budget Utilization by Customer",
        "type": "bargauge",
        "targets": [
          {"expr": "bigquery_budget_utilization_percentage", "legendFormat": "{{customer_id}}"}
        ]
      },
      {
        "title": "Cost Distribution by Operation",
        "type": "piechart",
        "targets": [
          {"expr": "sum by (operation_type) (bigquery_operation_cost_usd)"}
        ]
      }
    ]
  }
}
```

### Anomaly Detection

The system automatically detects unusual cost patterns:

```http
GET /api/v1/bigquery/cost-monitoring/anomaly-detection?customer_id=customer_123&lookback_days=7
```

**Pattern Types Detected**:

1. **Sudden Spikes**: Cost increases >300% of baseline
2. **Sustained High Usage**: Multiple days >150% of average
3. **Off-hours Usage**: Unusual activity outside business hours
4. **Large Query Anomalies**: Individual queries exceeding thresholds

**Example Response**:
```json
{
  "patterns": [
    {
      "pattern_type": "sudden_spike",
      "severity": "high",
      "description": "Daily cost spiked to $45.30, 3.2x above 7-day average",
      "cost_impact_usd": 31.20,
      "detected_at": "2025-08-22T10:30:00Z",
      "recommendations": [
        "Review queries executed during spike period",
        "Check for automated jobs or scripts causing increase"
      ]
    }
  ]
}
```

## Best Practices

### Cost Management Best Practices

1. **Set Realistic Budgets**: Based on historical usage patterns and business needs
2. **Monitor Trends**: Regular review of cost trends and usage patterns
3. **Optimize Regularly**: Continuous optimization of queries and data access patterns
4. **Use Alerts Wisely**: Configure alert thresholds that are actionable but not overwhelming
5. **Plan for Growth**: Budget for increased usage as business scales

### Operational Best Practices

1. **Regular Reviews**: Weekly cost reviews with stakeholders
2. **Automated Monitoring**: Set up automated monitoring and alerting
3. **Documentation**: Document optimization efforts and their impact
4. **Training**: Ensure team members understand cost implications
5. **Feedback Loop**: Use cost data to inform development decisions

### Security Best Practices

1. **Access Controls**: Limit budget configuration access to authorized personnel
2. **Audit Trails**: Monitor all budget and configuration changes
3. **Data Privacy**: Ensure cost monitoring doesn't expose sensitive customer data
4. **Compliance**: Follow organizational policies for cost management and reporting

---

*For technical implementation details, see the [Architecture Overview](architecture.md)*
*For troubleshooting cost issues, see the [Troubleshooting Guide](troubleshooting.md)*