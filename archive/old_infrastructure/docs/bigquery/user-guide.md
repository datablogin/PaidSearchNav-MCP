# BigQuery Hybrid Pipeline User Guide

This guide provides comprehensive instructions for using PaidSearchNav's BigQuery hybrid pipeline functionality for cost-effective, real-time Google Ads analytics.

## Table of Contents

1. [Overview](#overview)
2. [Getting Started](#getting-started)
3. [Cost Monitoring](#cost-monitoring)
4. [Real-time Analytics](#real-time-analytics)
5. [Budget Management](#budget-management)
6. [Troubleshooting](#troubleshooting)

## Overview

The BigQuery hybrid pipeline provides enterprise-grade analytics capabilities with built-in cost monitoring and budget controls. It combines the power of BigQuery's analytics engine with intelligent cost management to deliver insights while keeping expenses under control.

### Key Benefits

- **Real-time Insights**: Get analytics results in seconds instead of minutes
- **Cost Control**: Automatic budget enforcement prevents runaway costs
- **Scalability**: Handle datasets of any size efficiently
- **Security**: Enterprise-grade security with role-based access controls

## Getting Started

### Prerequisites

- **Account Tier**: Premium or Enterprise tier required
- **Permissions**: Appropriate role assignments (user, admin, or super_admin)
- **Google Cloud**: Valid Google Cloud credentials and BigQuery access

### Authentication

All BigQuery operations require authentication. The system uses your existing PaidSearchNav credentials:

```bash
# Your API requests should include the authentication header
Authorization: Bearer <your_jwt_token>
```

### First Steps

1. **Verify Access**: Check if BigQuery is enabled for your account
2. **Understand Limits**: Review your tier's cost limits and quotas
3. **Set Up Monitoring**: Configure alert preferences (admin only)

## Cost Monitoring

### Real-time Cost Tracking

The system provides sub-5-minute cost tracking using BigQuery's `INFORMATION_SCHEMA`:

```http
GET /api/v1/bigquery/cost-monitoring/real-time?customer_id=your_customer_id&lookback_hours=1
```

**Response Example**:
```json
{
  "success": true,
  "data": {
    "customer_id": "customer_123",
    "timestamp": "2025-08-22T10:30:00Z",
    "recent_cost_usd": 2.45,
    "daily_cost_usd": 12.80,
    "monthly_cost_usd": 234.50,
    "daily_limit_usd": 50.00,
    "daily_usage_percentage": 25.6,
    "status": "within_budget"
  }
}
```

### Cost Status Indicators

| Status | Description | Action Required |
|--------|-------------|-----------------|
| `within_budget` | Normal usage levels | None |
| `moderate_usage` | 50-80% of budget used | Monitor closely |
| `approaching_limit` | 80-95% of budget used | Review usage patterns |
| `over_budget` | Exceeded daily limit | Immediate attention |
| `emergency` | Emergency limit triggered | Operations suspended |

### Budget Enforcement

The system automatically enforces budget limits:

```http
POST /api/v1/bigquery/cost-monitoring/budget-enforcement?customer_id=your_customer_id&additional_cost_usd=5.00
```

**Response Example**:
```json
{
  "success": true,
  "data": {
    "allowed": true,
    "daily_cost_usd": 17.80,
    "enforcement_actions": [],
    "alerts_triggered": [
      {
        "threshold_percentage": 50.0,
        "threshold_amount_usd": 25.0,
        "current_cost_usd": 17.80,
        "priority": "medium",
        "action": "monitor"
      }
    ]
  }
}
```

## Real-time Analytics

### Available Analytics

1. **Cost Analytics**: Comprehensive cost breakdowns and trends
2. **Anomaly Detection**: Unusual usage pattern identification
3. **Performance Analysis**: Query performance and optimization suggestions
4. **ROI Analysis**: BigQuery vs CSV operation comparisons

### Getting Cost Analytics

```http
GET /api/v1/bigquery/cost-monitoring/analytics?customer_id=your_customer_id&period_days=30
```

**Key Metrics Returned**:
- Total costs and trends
- Operation type breakdowns
- Most expensive queries
- Efficiency metrics
- ROI analysis
- Optimization recommendations

### Anomaly Detection

```http
GET /api/v1/bigquery/cost-monitoring/anomaly-detection?customer_id=your_customer_id&lookback_days=7
```

**Pattern Types Detected**:
- **Sudden Spikes**: >300% of baseline usage
- **Sustained High Usage**: Multiple days above 150% baseline
- **Off-hours Usage**: Unusual activity outside business hours
- **Large Query Anomalies**: Individual queries exceeding thresholds

### Summary Reports

Generate automated reports for regular review:

```http
GET /api/v1/bigquery/cost-monitoring/reports/weekly?customer_id=your_customer_id
```

**Available Report Types**:
- `daily`: Last 24 hours summary
- `weekly`: 7-day analysis and trends
- `monthly`: 30-day comprehensive review

## Budget Management

### Customer Tiers

Each tier has predefined budget limits:

| Tier | Daily Limit | Monthly Limit | Emergency Limit |
|------|-------------|---------------|-----------------|
| Standard | $10 | $300 | $50 |
| Premium | $50 | $1,500 | $200 |
| Enterprise | $200 | $6,000 | $1,000 |

### Alert Thresholds

Default alert thresholds (customizable by admins):

- **50% threshold**: Monitoring alert (Medium priority)
- **80% threshold**: Review required (High priority)
- **95% threshold**: Throttling warning (Critical priority)

### Grace Periods

The system includes configurable grace periods:
- **Standard Grace**: 1 hour for budget overruns
- **Emergency Protection**: Immediate circuit breaker activation
- **Throttling**: Automatic slowdown of export operations

### Admin Budget Configuration

Administrators can configure custom budget limits:

```http
POST /api/v1/bigquery/cost-monitoring/budget-config
```

**Parameters**:
- `customer_id`: Target customer
- `tier`: Customer tier (standard/premium/enterprise)
- `daily_limit_usd`: Daily budget limit
- `monthly_limit_usd`: Monthly budget limit
- `emergency_limit_usd`: Emergency circuit breaker limit

**Validation Rules**:
- Daily limit: $1.00 - $10,000
- Monthly limit: $10.00 - $100,000
- Monthly must be ≥ 20x daily limit
- Emergency limit: 1x - 20x daily limit

## Best Practices

### Cost Optimization

1. **Schedule Large Operations**: Run intensive analytics during off-peak hours
2. **Use Materialized Views**: Cache frequently accessed data
3. **Monitor Query Patterns**: Review expensive queries regularly
4. **Set Reasonable Limits**: Configure budgets based on actual usage patterns

### Performance Tips

1. **Batch Operations**: Group multiple queries when possible
2. **Use Filters**: Limit data processing with date ranges and customer filters
3. **Monitor Rate Limits**: Respect API rate limits (10 requests/minute for real-time)
4. **Cache Results**: Store frequently accessed analytics locally

### Security Considerations

1. **Access Control**: Only request data for customers you have access to
2. **API Keys**: Protect your authentication tokens
3. **Data Privacy**: Follow data handling policies for customer information
4. **Audit Trails**: All operations are logged for security and compliance

## Error Handling

### Common Error Codes

| Code | Error | Solution |
|------|-------|----------|
| 402 | Payment Required | Upgrade to premium tier |
| 403 | Access Denied | Check customer access permissions |
| 429 | Rate Limit Exceeded | Reduce request frequency |
| 502 | BigQuery Unavailable | Retry after delay |

### Rate Limiting

API endpoints have different rate limits:

- **Real-time costs**: 10 requests/minute
- **Budget enforcement**: 20 requests/minute
- **Analytics**: 5 requests/minute
- **Reports**: 5 requests/minute
- **Budget config**: 10 requests/minute (admin only)

## Troubleshooting

### Common Issues

**Issue**: "BigQuery integration not enabled"
- **Solution**: Upgrade to premium tier or contact support

**Issue**: "Access denied" for customer data
- **Solution**: Verify you have permission to access the specified customer

**Issue**: "Budget enforcement blocking operations"
- **Solution**: Review current usage and consider budget adjustments

**Issue**: Real-time data seems delayed
- **Solution**: BigQuery has a 5-minute processing delay; this is normal

## Testing and Development

### Testing the BigQuery Integration

#### 1. Integration Testing

Test the complete data pipeline flow:

```bash
# Run integration tests
pytest tests/integration/test_bigquery_pipeline.py -v

# Test specific components
pytest tests/integration/test_cost_monitoring.py -v
pytest tests/integration/test_budget_enforcement.py -v
```

#### 2. Mock Services for Development

When developing locally without BigQuery access:

```python
# Use mock BigQuery client
export MOCK_BIGQUERY=true
export BIGQUERY_EMULATOR_HOST=localhost:9050

# Start BigQuery emulator (optional)
docker run -p 9050:9050 \
  gcr.io/google.com/cloudsdktool/cloud-sdk:latest \
  gcloud beta emulators bigquery start --host-port=0.0.0.0:9050
```

#### 3. End-to-End Testing

Test the complete workflow:

```bash
# 1. Test cost monitoring API
curl -X GET "http://localhost:8000/api/v1/bigquery/cost-monitoring/real-time" \
  -H "Authorization: Bearer $TEST_TOKEN"

# 2. Test budget enforcement
curl -X POST "http://localhost:8000/api/v1/bigquery/cost-monitoring/budget-enforcement" \
  -H "Authorization: Bearer $TEST_TOKEN" \
  -d '{"customer_id": "test_customer", "additional_cost_usd": 5.0}'

# 3. Test analytics endpoint
curl -X GET "http://localhost:8000/api/v1/bigquery/cost-monitoring/analytics?period_days=7" \
  -H "Authorization: Bearer $TEST_TOKEN"
```

#### 4. Performance Testing

Test system performance under load:

```python
# Load testing script
import asyncio
import aiohttp
import time

async def test_endpoint_performance():
    """Test API endpoint performance under load."""
    start_time = time.time()
    
    async with aiohttp.ClientSession() as session:
        tasks = []
        for i in range(100):  # 100 concurrent requests
            task = session.get(
                'http://localhost:8000/api/v1/bigquery/cost-monitoring/real-time',
                headers={'Authorization': f'Bearer {token}'}
            )
            tasks.append(task)
        
        responses = await asyncio.gather(*tasks)
        
    end_time = time.time()
    print(f"100 requests completed in {end_time - start_time:.2f} seconds")

# Run performance test
asyncio.run(test_endpoint_performance())
```

#### 5. Test Data Management

Manage test data for consistent testing:

```sql
-- Create test dataset
CREATE SCHEMA IF NOT EXISTS test_bigquery_analytics;

-- Insert test cost data
INSERT INTO test_bigquery_analytics.job_costs 
(job_id, customer_id, cost_usd, created_at)
VALUES 
  ('test_job_1', 'test_customer', 2.50, CURRENT_TIMESTAMP()),
  ('test_job_2', 'test_customer', 1.75, CURRENT_TIMESTAMP());

-- Clean up test data
DELETE FROM test_bigquery_analytics.job_costs 
WHERE customer_id = 'test_customer';
```

### Getting Help

1. **Check Status**: Use the real-time monitoring endpoint to check system status
2. **Review Logs**: Check application logs for detailed error information
3. **Run Tests**: Execute the test suite to verify functionality
4. **Contact Support**: For persistent issues, contact your system administrator
5. **Documentation**: Refer to the [API Reference](api-reference.md) for detailed examples

---

*For technical implementation details, see the [Architecture Overview](architecture.md)*
*For API specifications, see the [API Reference](api-reference.md)*