# BigQuery API Reference

Complete API documentation for PaidSearchNav's BigQuery hybrid pipeline endpoints with examples, schemas, and authentication details.

## Table of Contents

1. [Authentication](#authentication)
2. [Rate Limiting](#rate-limiting)
3. [Cost Monitoring Endpoints](#cost-monitoring-endpoints)
4. [Error Responses](#error-responses)
5. [Request Examples](#request-examples)

## Authentication

All BigQuery API endpoints require authentication using JWT tokens:

```http
Authorization: Bearer <your_jwt_token>
```

### User Roles and Permissions

| Role | Real-time Monitoring | Budget Enforcement | Analytics | Budget Config |
|------|---------------------|-------------------|-----------|---------------|
| `user` | Own data only | Own data only | Own data only | ❌ |
| `admin` | All customers | All customers | All customers | ✅ |
| `super_admin` | All customers | All customers | All customers | ✅ |

## Rate Limiting

Each endpoint has specific rate limits to prevent BigQuery quota exhaustion:

| Endpoint | Rate Limit | Tier Requirement |
|----------|------------|------------------|
| Real-time costs | 10/minute | Premium+ |
| Budget enforcement | 20/minute | Premium+ |
| Anomaly detection | 10/minute | Premium+ |
| Analytics | 5/minute | Premium+ |
| Reports | 5/minute | Premium+ |
| Budget config (GET) | 20/minute | Premium+ (Admin) |
| Budget config (POST) | 10/minute | Premium+ (Admin) |

## Cost Monitoring Endpoints

### 1. Real-time Cost Monitoring

Get real-time BigQuery costs with sub-5-minute delay.

```http
GET /api/v1/bigquery/cost-monitoring/real-time
```

**Parameters**:
- `customer_id` (optional): Customer ID for cost monitoring
- `lookback_hours` (optional): Lookback period in hours (1-24, default: 1)

**Response Schema**:
```json
{
  "success": true,
  "data": {
    "customer_id": "string",
    "timestamp": "2025-08-22T10:30:00Z",
    "lookback_hours": 1,
    "recent_cost_usd": 2.45,
    "recent_bytes_processed": 1073741824,
    "recent_jobs_count": 15,
    "daily_cost_usd": 12.80,
    "daily_limit_usd": 50.00,
    "daily_remaining_usd": 37.20,
    "daily_usage_percentage": 25.6,
    "monthly_cost_usd": 234.50,
    "monthly_limit_usd": 1500.00,
    "monthly_remaining_usd": 1265.50,
    "monthly_usage_percentage": 15.6,
    "budget_config": {
      "customer_id": "string",
      "tier": "premium",
      "daily_limit_usd": 50.00,
      "monthly_limit_usd": 1500.00,
      "emergency_limit_usd": 200.00
    },
    "status": "within_budget",
    "data_freshness_minutes": 3.2
  },
  "timestamp": "2025-08-22T10:30:00Z"
}
```

**Status Values**:
- `within_budget`: Normal usage (0-50% of limit)
- `moderate_usage`: Moderate usage (50-80% of limit)
- `approaching_limit`: High usage (80-95% of limit)
- `over_budget`: Exceeded daily limit
- `emergency`: Emergency limit triggered

### 2. Budget Enforcement

Check budget limits and get enforcement decisions.

```http
POST /api/v1/bigquery/cost-monitoring/budget-enforcement
```

**Parameters**:
- `customer_id` (required): Customer ID
- `additional_cost_usd` (optional): Additional cost to check (default: 0.0)

**Response Schema**:
```json
{
  "success": true,
  "data": {
    "allowed": true,
    "enforcement_actions": [
      {
        "action": "grace_period_active",
        "reason": "Daily limit exceeded but within grace period",
        "severity": "medium"
      }
    ],
    "alerts_triggered": [
      {
        "threshold_percentage": 50.0,
        "threshold_amount_usd": 25.0,
        "current_cost_usd": 27.50,
        "priority": "medium",
        "action": "monitor"
      }
    ],
    "daily_cost_usd": 27.50,
    "monthly_cost_usd": 456.80,
    "budget_config": {
      "customer_id": "string",
      "tier": "premium",
      "daily_limit_usd": 50.00,
      "monthly_limit_usd": 1500.00,
      "emergency_limit_usd": 200.00
    },
    "status": "moderate_usage"
  },
  "customer_id": "string"
}
```

**Enforcement Actions**:
- `grace_period_active`: Budget exceeded but within grace period
- `throttle_exports`: Automatic throttling applied
- `emergency_circuit_breaker`: All operations suspended

### 3. Anomaly Detection

Detect unusual cost usage patterns.

```http
GET /api/v1/bigquery/cost-monitoring/anomaly-detection
```

**Parameters**:
- `customer_id` (optional): Customer ID for anomaly detection
- `lookback_days` (optional): Lookback period in days (1-30, default: 7)

**Response Schema**:
```json
{
  "success": true,
  "data": {
    "patterns": [
      {
        "pattern_type": "sudden_spike",
        "severity": "high",
        "description": "Daily cost spiked to $45.30, 3.2x above 7-day average",
        "cost_impact_usd": 31.20,
        "detected_at": "2025-08-22T10:30:00Z"
      }
    ],
    "anomalies_detected": 1,
    "analysis_period_days": 7,
    "baseline_daily_average": 14.10
  }
}
```

**Pattern Types**:
- `sudden_spike`: Cost >300% of baseline
- `sustained_high_usage`: Multiple days >150% baseline
- `off_hours_usage`: Unusual activity outside business hours
- `large_query_anomaly`: Individual queries exceeding thresholds

### 4. Cost Analytics

Generate comprehensive cost analytics and insights.

```http
GET /api/v1/bigquery/cost-monitoring/analytics
```

**Parameters**:
- `customer_id` (optional): Customer ID for cost analytics
- `period_days` (optional): Analysis period in days (1-365, default: 30)

**Response Schema**:
```json
{
  "success": true,
  "data": {
    "customer_id": "string",
    "analysis_period_days": 30,
    "generated_at": "2025-08-22T10:30:00Z",
    "cost_summary": {
      "total_cost_usd": 678.50,
      "average_daily_cost_usd": 22.62,
      "peak_daily_cost_usd": 45.30,
      "current_daily_cost_usd": 18.40,
      "cost_trend": "decreasing"
    },
    "operation_breakdown": {
      "keyword_analysis": 271.40,
      "search_terms_analysis": 203.55,
      "performance_analysis": 135.70,
      "export_operations": 67.85
    },
    "query_analysis": {
      "expensive_queries": [
        {
          "job_id": "job_001",
          "cost_usd": 15.75,
          "bytes_processed": 3298534883328,
          "duration_seconds": 180,
          "query_type": "keyword_analysis",
          "created_at": "2025-08-22T08:15:00Z"
        }
      ],
      "average_cost_per_query": 2.35,
      "total_queries_analyzed": 289
    },
    "efficiency_metrics": {
      "cost_per_tb_processed": 4.92,
      "cost_per_customer_analysis": 12.45,
      "tier_efficiency": {
        "customer_tier": "premium",
        "tier_average_daily_cost": 25.00,
        "customer_daily_cost": 22.62,
        "efficiency_ratio": 0.90,
        "efficiency_status": "above_average"
      }
    },
    "roi_analysis": {
      "bigquery_cost_usd": 678.50,
      "csv_equivalent_cost_usd": 240.00,
      "additional_cost_usd": 438.50,
      "time_saved_hours": 120,
      "cost_per_hour_saved": 3.65,
      "roi_analysis": "positive"
    },
    "recommendations": [
      "Schedule large analytics jobs during off-peak hours for potential cost savings",
      "Consider using BigQuery materialized views for frequently accessed data",
      "Review and optimize expensive queries identified in the analytics"
    ],
    "budget_utilization": {
      "average_daily_utilization_percentage": 45.24,
      "days_over_80_percent": 3,
      "days_over_limit": 0,
      "budget_efficiency": "good",
      "recommended_budget_adjustment": null
    }
  }
}
```

### 5. Summary Reports

Generate automated cost summary reports.

```http
GET /api/v1/bigquery/cost-monitoring/reports/{report_type}
```

**Path Parameters**:
- `report_type`: Report type (`daily`, `weekly`, `monthly`)

**Query Parameters**:
- `customer_id` (optional): Customer ID for cost report

**Response Schema**:
```json
{
  "success": true,
  "data": {
    "report_type": "weekly",
    "customer_id": "string",
    "period_days": 7,
    "generated_at": "2025-08-22T10:30:00Z",
    "executive_summary": {
      "total_cost_usd": 158.60,
      "budget_utilization_percentage": 45.2,
      "cost_trend": "stable",
      "unusual_patterns_detected": 1,
      "status": "within_budget"
    },
    "detailed_analytics": {
      // Full analytics object (same as analytics endpoint)
    },
    "unusual_patterns": [
      {
        "pattern_type": "sudden_spike",
        "severity": "medium",
        "description": "Cost spike detected on Tuesday",
        "cost_impact_usd": 12.50,
        "detected_at": "2025-08-20T14:30:00Z"
      }
    ],
    "current_status": {
      // Current real-time status (same as real-time endpoint)
    },
    "action_items": [
      "Monitor costs closely - approaching daily budget limit",
      "Review recent query patterns and consider query optimization"
    ]
  }
}
```

### 6. Budget Configuration (Admin Only)

Configure customer budget limits and thresholds.

#### Set Budget Configuration

```http
POST /api/v1/bigquery/cost-monitoring/budget-config
```

**Parameters** (all required):
- `customer_id`: Customer ID
- `tier`: Customer tier (`standard`, `premium`, `enterprise`)
- `daily_limit_usd`: Daily budget limit in USD (1.00 - 10,000.00)
- `monthly_limit_usd`: Monthly budget limit in USD (10.00 - 100,000.00)
- `emergency_limit_usd` (optional): Emergency circuit breaker limit

**Validation Rules**:
- Monthly limit must be ≥ 20x daily limit
- Emergency limit must be 1x - 20x daily limit
- Admin role required

**Response Schema**:
```json
{
  "success": true,
  "data": {
    "customer_id": "string",
    "tier": "premium",
    "daily_limit_usd": 75.00,
    "monthly_limit_usd": 2250.00,
    "emergency_limit_usd": 300.00,
    "thresholds": [
      {
        "percentage": 50.0,
        "priority": "medium",
        "action": "monitor"
      },
      {
        "percentage": 80.0,
        "priority": "high",
        "action": "review"
      },
      {
        "percentage": 95.0,
        "priority": "critical",
        "action": "throttle"
      }
    ],
    "grace_period_hours": 1,
    "throttle_enabled": true,
    "alerts_enabled": true,
    "created_at": "2025-08-22T10:30:00Z",
    "updated_at": "2025-08-22T10:30:00Z"
  },
  "message": "Budget configuration updated for customer string"
}
```

#### Get Budget Configurations

```http
GET /api/v1/bigquery/cost-monitoring/budget-config
```

**Response Schema**:
```json
{
  "success": true,
  "data": {
    "customer_123": {
      // Customer budget config object
    },
    "customer_456": {
      // Customer budget config object
    }
  },
  "total_customers": 2
}
```

## Error Responses

### Standard Error Format

All errors follow a consistent format:

```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error description"
  },
  "timestamp": "2025-08-22T10:30:00Z"
}
```

### Common Error Codes

| HTTP Code | Error Code | Description |
|-----------|------------|-------------|
| 400 | VALIDATION_ERROR | Invalid parameters or request format |
| 401 | AUTHENTICATION_REQUIRED | Missing or invalid authentication token |
| 402 | PAYMENT_REQUIRED | Premium tier required for this endpoint |
| 403 | ACCESS_DENIED | Insufficient permissions for requested resource |
| 429 | RATE_LIMIT_EXCEEDED | Too many requests, retry after delay |
| 502 | BIGQUERY_UNAVAILABLE | BigQuery service temporarily unavailable |
| 500 | INTERNAL_ERROR | Internal server error |

### BigQuery-Specific Errors

| Error Code | Description | Solution |
|------------|-------------|----------|
| BIGQUERY_QUOTA_EXCEEDED | BigQuery quota limit reached | Wait and retry, or contact support |
| BIGQUERY_API_ERROR | General BigQuery API error | Check BigQuery service status |
| BUDGET_LIMIT_EXCEEDED | Customer budget limit exceeded | Review usage or adjust budget |
| CIRCUIT_BREAKER_ACTIVE | Emergency circuit breaker triggered | Contact admin to reset |

## Request Examples

### cURL Examples

#### Get Real-time Costs
```bash
curl -X GET "https://api.paidsearchnav.com/api/v1/bigquery/cost-monitoring/real-time?customer_id=customer_123&lookback_hours=2" \
  -H "Authorization: Bearer your_jwt_token" \
  -H "Content-Type: application/json"
```

#### Check Budget Enforcement
```bash
curl -X POST "https://api.paidsearchnav.com/api/v1/bigquery/cost-monitoring/budget-enforcement?customer_id=customer_123&additional_cost_usd=5.50" \
  -H "Authorization: Bearer your_jwt_token" \
  -H "Content-Type: application/json"
```

#### Get Analytics
```bash
curl -X GET "https://api.paidsearchnav.com/api/v1/bigquery/cost-monitoring/analytics?customer_id=customer_123&period_days=14" \
  -H "Authorization: Bearer your_jwt_token" \
  -H "Content-Type: application/json"
```

#### Set Budget Configuration (Admin)
```bash
curl -X POST "https://api.paidsearchnav.com/api/v1/bigquery/cost-monitoring/budget-config?customer_id=customer_123&tier=premium&daily_limit_usd=75&monthly_limit_usd=2250&emergency_limit_usd=300" \
  -H "Authorization: Bearer admin_jwt_token" \
  -H "Content-Type: application/json"
```

### JavaScript/Node.js Examples

```javascript
// Get real-time costs with error handling
try {
  const response = await fetch('/api/v1/bigquery/cost-monitoring/real-time?customer_id=customer_123', {
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    }
  });

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  const costData = await response.json();
  console.log('Current daily cost:', costData.data.daily_cost_usd);
} catch (error) {
  console.error('Error fetching cost data:', error);
}

// Check budget enforcement before expensive operation
const enforcement = await fetch('/api/v1/bigquery/cost-monitoring/budget-enforcement?customer_id=customer_123&additional_cost_usd=10', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  }
});

const result = await enforcement.json();
if (result.data.allowed) {
  // Proceed with operation
  console.log('Operation approved');
} else {
  // Handle budget limit
  console.log('Operation blocked:', result.data.enforcement_actions);
}
```

### Python Examples

```python
import requests

# Configuration
BASE_URL = "https://api.paidsearchnav.com"
HEADERS = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

# Get real-time costs with error handling
try:
    response = requests.get(
        f"{BASE_URL}/api/v1/bigquery/cost-monitoring/real-time",
        headers=HEADERS,
        params={
            "customer_id": "customer_123",
            "lookback_hours": 2
        }
    )
    response.raise_for_status()  # Raises HTTPError for bad responses
    
    cost_data = response.json()
    print(f"Daily cost: ${cost_data['data']['daily_cost_usd']}")
except requests.exceptions.RequestException as e:
    print(f"Error fetching cost data: {e}")

# Get analytics
analytics = requests.get(
    f"{BASE_URL}/api/v1/bigquery/cost-monitoring/analytics",
    headers=HEADERS,
    params={
        "customer_id": "customer_123",
        "period_days": 30
    }
)

analytics_data = analytics.json()
print(f"Cost trend: {analytics_data['data']['cost_summary']['cost_trend']}")
```

## SDK Support

While no official SDK is currently available, the API follows RESTful conventions and can be easily integrated with any HTTP client library.

### Recommended Libraries

- **JavaScript**: axios, fetch
- **Python**: requests, httpx
- **Java**: OkHttp, Apache HttpClient
- **C#**: HttpClient
- **Go**: net/http
- **PHP**: Guzzle, cURL

---

*For usage examples and tutorials, see the [User Guide](user-guide.md)*
*For implementation details, see the [Architecture Overview](architecture.md)*