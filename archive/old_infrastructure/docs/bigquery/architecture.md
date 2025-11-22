# BigQuery Hybrid Pipeline Architecture

This document provides a comprehensive overview of the BigQuery hybrid pipeline architecture, design decisions, and system components.

## Table of Contents

1. [System Overview](#system-overview)
2. [Core Components](#core-components)
3. [Data Flow](#data-flow)
4. [Security Architecture](#security-architecture)
5. [Cost Management System](#cost-management-system)
6. [Performance Considerations](#performance-considerations)
7. [Scalability Design](#scalability-design)
8. [Technology Stack](#technology-stack)

## System Overview

The BigQuery hybrid pipeline is designed as a enterprise-grade analytics platform that combines the power of Google BigQuery with intelligent cost management and real-time monitoring capabilities.

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Client Applications                       │
│  Web UI │ Mobile App │ API Clients │ Dashboards │ Scripts       │
└─────────────────────┬───────────────────────────────────────────┘
                      │ HTTPS/REST API
┌─────────────────────▼───────────────────────────────────────────┐
│                      API Gateway Layer                          │
│  ┌─────────────┐ ┌──────────────┐ ┌─────────────┐ ┌──────────┐ │
│  │Authentication│ │Rate Limiting │ │ Validation  │ │ Logging  │ │
│  │   & AuthZ    │ │   & Quotas   │ │ & Schemas   │ │ & Metrics│ │
│  └─────────────┘ └──────────────┘ └─────────────┘ └──────────┘ │
└─────────────────────┬───────────────────────────────────────────┘
                      │ Internal API
┌─────────────────────▼───────────────────────────────────────────┐
│                   Business Logic Layer                          │
│  ┌─────────────┐ ┌──────────────┐ ┌─────────────┐ ┌──────────┐ │
│  │  BigQuery   │ │     Cost     │ │   Alert     │ │Analytics │ │
│  │   Service   │ │   Monitor    │ │  Manager    │ │ Engine   │ │
│  └─────────────┘ └──────────────┘ └─────────────┘ └──────────┘ │
└─────────────────────┬───────────────────────────────────────────┘
                      │ Data Operations
┌─────────────────────▼───────────────────────────────────────────┐
│                    Data Access Layer                            │
│  ┌─────────────┐ ┌──────────────┐ ┌─────────────┐ ┌──────────┐ │
│  │  BigQuery   │ │  PostgreSQL  │ │    Redis    │ │   File   │ │
│  │   Client    │ │   Database   │ │    Cache    │ │ Storage  │ │
│  └─────────────┘ └──────────────┘ └─────────────┘ └──────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### Design Principles

1. **Cost-First Design**: Every operation considers cost implications
2. **Real-time Monitoring**: Sub-5-minute cost and performance tracking
3. **Fail-Safe Operations**: Graceful degradation and circuit breakers
4. **Scalable Architecture**: Horizontal scaling with minimal overhead
5. **Security by Default**: Role-based access control and data isolation

## Core Components

### 1. API Gateway Layer

**Location**: `paidsearchnav/api/routes/bigquery.py`

The API gateway provides the external interface with comprehensive security and monitoring:

- **Authentication**: JWT token validation with role-based permissions
- **Rate Limiting**: Slowapi-based rate limiting (10-20 requests/minute)
- **Input Validation**: Pydantic models for request/response validation
- **Error Handling**: Consistent error responses with proper HTTP codes

```python
# Example: Customer access validation
def validate_customer_access(current_user: Dict[str, Any], requested_customer_id: Optional[str]):
    if requested_customer_id:
        user_customer_id = current_user.get("customer_id")
        user_role = current_user.get("role", "user")
        
        # Admin users can access any customer data
        if user_role in ["admin", "super_admin"]:
            return
            
        # Regular users can only access their own customer data
        if user_customer_id != requested_customer_id:
            raise HTTPException(status_code=403, detail="Access denied")
```

### 2. Cost Management System

**Location**: `paidsearchnav/platforms/bigquery/cost_monitor_enhanced.py`

The heart of the cost management system provides real-time monitoring and budget enforcement:

#### Core Classes

- **`EnhancedBigQueryCostMonitor`**: Main monitoring orchestrator
- **`CustomerBudgetConfig`**: Pydantic model for budget configuration
- **`CostThreshold`**: Alert threshold definitions
- **`CostUsagePattern`**: Anomaly detection patterns

#### Key Features

```python
class EnhancedBigQueryCostMonitor:
    async def get_real_time_costs(self, customer_id: Optional[str] = None, lookback_hours: int = 1):
        """Get real-time BigQuery costs with <5 minute delay."""
        # Queries BigQuery INFORMATION_SCHEMA.JOBS_BY_PROJECT
        # Calculates costs: $5/TB + $0.04/slot-hour
        # Returns comprehensive cost breakdown
    
    async def check_budget_enforcement(self, customer_id: str, additional_cost_usd: float = 0.0):
        """Check budget limits and enforce controls."""
        # Validates against daily/monthly/emergency limits
        # Triggers alerts and throttling as needed
        # Returns enforcement decision
    
    async def detect_unusual_patterns(self, customer_id: Optional[str] = None, lookback_days: int = 7):
        """Detect unusual cost usage patterns."""
        # Spike detection (>300% baseline)
        # Sustained high usage identification
        # Off-hours usage anomalies
        # Large query cost anomalies
```

### 3. BigQuery Service Layer

**Location**: `paidsearchnav/platforms/bigquery/service.py`

Provides high-level BigQuery operations with integrated cost tracking:

- **Query Execution**: Parameterized query execution with cost tracking
- **Schema Management**: BigQuery schema validation and migration
- **Connection Management**: Efficient connection pooling and lifecycle
- **Timeout Configuration**: Configurable timeouts for different operation types

### 4. Alert Management System

**Location**: `paidsearchnav/alerts/manager.py` (external integration)

Handles alert processing with sophisticated logic:

- **Multi-Channel Alerts**: Email, Slack, webhook notifications
- **Alert Deduplication**: Prevents alert flooding with cooldown periods
- **Escalation Policies**: Automatic escalation for critical issues
- **Alert Correlation**: Groups related alerts for better context

## Data Flow

### 1. Cost Tracking Flow

```
┌─────────────┐    ┌─────────────────┐    ┌──────────────────┐
│  API Call   │───▶│  BigQuery Job   │───▶│ INFORMATION_     │
│             │    │   Execution     │    │ SCHEMA Query     │
└─────────────┘    └─────────────────┘    └──────────────────┘
                                                    │
┌─────────────┐    ┌─────────────────┐    ┌──────────────────┘
│ Cost Alert  │◀───│ Budget Monitor  │◀───│ Real-time Cost
│  Triggered  │    │  Evaluation     │    │  Calculation
└─────────────┘    └─────────────────┘    └──────────────────┘
```

### 2. Budget Enforcement Flow

```
Operation Request
       │
       ▼
┌─────────────────┐    YES   ┌──────────────────┐
│ Get Current     │─────────▶│ Allow Operation  │
│ Cost + Proposed │          │                  │
│ Additional Cost │          └──────────────────┘
└─────────────────┘
       │ NO
       ▼
┌─────────────────┐    ┌─────────────────────┐
│ Check Grace     │───▶│ Apply Throttling    │
│ Period Status   │    │ or Circuit Breaker  │
└─────────────────┘    └─────────────────────┘
       │
       ▼
┌─────────────────┐
│ Send Alert &    │
│ Block Operation │
└─────────────────┘
```

### 3. Analytics Generation Flow

```
Historical Data Collection
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│ Job History     │    │ Cost Patterns   │    │ Usage Metrics   │
│ (INFORMATION_   │    │ Analysis        │    │ Aggregation     │
│ SCHEMA)         │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 ▼
                    ┌─────────────────────┐
                    │ Analytics Engine    │
                    │ • Cost trends       │
                    │ • Efficiency metrics│
                    │ • Recommendations   │
                    │ • ROI analysis      │
                    └─────────────────────┘
                                 │
                                 ▼
                    ┌─────────────────────┐
                    │ Report Generation   │
                    │ • Executive summary │
                    │ • Detailed metrics  │
                    │ • Action items      │
                    └─────────────────────┘
```

## Security Architecture

### 1. Authentication and Authorization

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   JWT Token     │───▶│ Role Validation │───▶│ Resource Access │
│   Validation    │    │                 │    │   Control       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │                       │                       │
    ┌────▼────┐             ┌────▼────┐             ┌────▼────┐
    │ Token   │             │ User    │             │Customer │
    │ Expiry  │             │ Role    │             │ Data    │
    │ Check   │             │ Check   │             │Isolation│
    └─────────┘             └─────────┘             └─────────┘
```

### 2. Data Isolation

- **Customer Data Segregation**: All queries include customer ID filters
- **Row-Level Security**: BigQuery row-level security policies (when applicable)
- **API-Level Filtering**: Customer access validation before data queries
- **Audit Logging**: All data access operations are logged with user context

### 3. Secrets Management

- **Environment Variables**: Sensitive configuration via environment variables
- **Google Cloud IAM**: Service account authentication for BigQuery
- **JWT Tokens**: Time-limited authentication tokens
- **API Key Rotation**: Regular rotation of API keys and service account keys

## Cost Management System

### 1. Real-time Cost Calculation

The system uses BigQuery's `INFORMATION_SCHEMA.JOBS_BY_PROJECT` to calculate costs in real-time:

```sql
SELECT 
    job_id,
    creation_time,
    total_bytes_processed,
    total_slot_ms,
    total_bytes_processed / POWER(1024, 4) * 5.0 as query_cost_usd,
    total_slot_ms / 1000 / 3600 * 0.04 as slot_cost_usd,
    (total_bytes_processed / POWER(1024, 4) * 5.0) +
    (total_slot_ms / 1000 / 3600 * 0.04) as total_cost_usd
FROM `{project_id}.region-us.INFORMATION_SCHEMA.JOBS_BY_PROJECT`
WHERE creation_time >= @start_time
  AND creation_time <= @current_time
  AND job_type = 'QUERY'
  AND state = 'DONE'
```

### 2. Budget Enforcement Tiers

| Tier | Daily Limit | Monthly Limit | Emergency Limit | Features |
|------|-------------|---------------|-----------------|----------|
| Standard | $10 | $300 | $50 | Basic monitoring |
| Premium | $50 | $1,500 | $200 | Real-time alerts |
| Enterprise | $200 | $6,000 | $1,000 | ML predictions |

### 3. Alert Thresholds

Default alert configuration (customizable):

```python
default_thresholds = [
    CostThreshold(percentage=50.0, priority=AlertPriority.MEDIUM, action="monitor"),
    CostThreshold(percentage=80.0, priority=AlertPriority.HIGH, action="review"),
    CostThreshold(percentage=95.0, priority=AlertPriority.CRITICAL, action="throttle"),
]
```

## Performance Considerations

### 1. Query Optimization

- **Parameterized Queries**: All BigQuery queries use parameters to leverage query cache
- **Result Caching**: Expensive analytics results cached in Redis
- **Batch Operations**: Multiple customer queries batched when possible
- **Materialized Views**: Frequently accessed data pre-computed

### 2. Rate Limiting Strategy

```python
# Rate limits designed to prevent BigQuery quota exhaustion
rate_limits = {
    "real_time_costs": "10/minute",      # Conservative for real-time queries
    "budget_enforcement": "20/minute",    # Higher for quick decisions
    "analytics": "5/minute",              # Lower for expensive operations
    "reports": "5/minute",                # Lower for complex aggregations
}
```

### 3. Connection Management

- **Connection Pooling**: Efficient connection reuse for BigQuery clients
- **Timeout Configuration**: Different timeouts for different operation types
- **Circuit Breakers**: Automatic failover when BigQuery is unavailable

## Scalability Design

### 1. Horizontal Scaling

- **Stateless Services**: All business logic is stateless and horizontally scalable
- **Database Scaling**: PostgreSQL with read replicas for metadata operations
- **Cache Scaling**: Redis cluster for distributed caching
- **Load Balancing**: API gateway with load balancer for multiple instances

### 2. Data Partitioning

- **Customer-based Partitioning**: Customer data naturally partitioned
- **Time-based Partitioning**: Cost data partitioned by date ranges
- **Regional Distribution**: Multi-region BigQuery datasets for global access

### 3. Caching Strategy

```python
# Multi-level caching strategy
cache_layers = {
    "real_time_costs": "1 minute TTL",     # Very short for real-time data
    "budget_configs": "10 minutes TTL",    # Moderate for configuration
    "analytics": "1 hour TTL",             # Longer for expensive calculations
    "historical_data": "24 hours TTL",     # Longest for stable historical data
}
```

## Technology Stack

### Backend Services
- **API Framework**: FastAPI with async/await support
- **Authentication**: JWT tokens with role-based access control
- **Rate Limiting**: slowapi (async-compatible rate limiting)
- **Validation**: Pydantic models for request/response validation

### Data Storage
- **Analytics Database**: Google BigQuery for large-scale analytics
- **Metadata Database**: PostgreSQL for application metadata
- **Cache Layer**: Redis for high-performance caching
- **File Storage**: Google Cloud Storage for exports and backups

### Monitoring and Observability
- **Metrics**: Prometheus metrics collection
- **Logging**: Structured JSON logging with correlation IDs
- **Tracing**: OpenTelemetry for distributed tracing (optional)
- **Alerting**: Custom alert manager with multiple notification channels

### Infrastructure
- **Container Runtime**: Docker containers
- **Orchestration**: Kubernetes for production deployments
- **CI/CD**: GitHub Actions for automated testing and deployment
- **Secret Management**: Environment variables with external secret providers

## Extension Points

### 1. Adding New Cost Metrics

```python
# Extend the cost calculation in cost_monitor_enhanced.py
class CustomCostCalculator:
    def calculate_storage_costs(self, bytes_stored: int, days: int) -> float:
        """Calculate BigQuery storage costs."""
        storage_tb = bytes_stored / (1024 ** 4)
        return storage_tb * 0.02 * days  # $0.02 per TB per month
    
    def calculate_streaming_costs(self, rows_streamed: int) -> float:
        """Calculate BigQuery streaming insert costs."""
        return rows_streamed * 0.01 / 200000  # $0.01 per 200K rows
```

### 2. Custom Alert Handlers

```python
# Extend alert processing in alerts/processors.py
class CustomAlertProcessor(BaseAlertProcessor):
    async def process_cost_alert(self, alert: CostAlert) -> bool:
        """Custom processing for cost-related alerts."""
        # Custom logic for specific alert types
        # Integration with external systems
        # Custom escalation rules
        return True
```

### 3. New Analytics Engines

```python
# Add new analytics in platforms/bigquery/analytics.py
class MLPredictiveAnalytics:
    async def predict_cost_trends(self, customer_id: str, days_ahead: int) -> Dict:
        """Use ML to predict future cost trends."""
        # Machine learning model integration
        # Predictive analytics algorithms
        # Trend forecasting
        return predictions
```

## Decision Log

### Why BigQuery for Analytics?
- **Scalability**: Handles petabyte-scale datasets efficiently
- **Performance**: Sub-second query response for most operations
- **Cost-effectiveness**: Pay-per-query model aligns with usage-based pricing
- **Integration**: Native Google Ads integration and extensive ecosystem

### Why Real-time Cost Monitoring?
- **Budget Control**: Prevents runaway costs from automated operations
- **User Experience**: Immediate feedback on operation costs
- **Operational Safety**: Early warning system for unusual usage patterns
- **Compliance**: Real-time budget enforcement for financial controls

### Why Hybrid Architecture?
- **Flexibility**: Combines BigQuery power with traditional database benefits
- **Cost Optimization**: Uses BigQuery only when necessary, PostgreSQL for metadata
- **Performance**: Local caching reduces BigQuery query costs
- **Reliability**: Fallback options when BigQuery is unavailable

---

*For operational procedures, see the [Deployment Guide](deployment.md)*
*For performance optimization, see the [Performance Tuning Guide](performance-tuning.md)*