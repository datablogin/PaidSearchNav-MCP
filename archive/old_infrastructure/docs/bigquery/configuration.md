# BigQuery Configuration Reference

Complete reference for configuring the BigQuery hybrid pipeline, including environment variables, settings, and deployment configurations.

## Table of Contents

1. [Environment Variables](#environment-variables)
2. [BigQuery Configuration](#bigquery-configuration)
3. [Cost Monitoring Settings](#cost-monitoring-settings)
4. [Security Configuration](#security-configuration)
5. [Performance Tuning](#performance-tuning)
6. [Development vs Production](#development-vs-production)

## Environment Variables

### Core BigQuery Settings

```bash
# BigQuery Project Configuration
GOOGLE_CLOUD_PROJECT=your-gcp-project-id
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
BIGQUERY_LOCATION=US  # or EU, asia-southeast1, etc.

# BigQuery Dataset Configuration
BIGQUERY_DATASET=paidsearchnav_analytics
BIGQUERY_STAGING_DATASET=paidsearchnav_staging
BIGQUERY_BACKUP_DATASET=paidsearchnav_backup

# BigQuery Job Configuration
BIGQUERY_JOB_TIMEOUT_SECONDS=300
BIGQUERY_QUERY_TIMEOUT_SECONDS=180
BIGQUERY_LOAD_TIMEOUT_SECONDS=600
BIGQUERY_DEFAULT_QUERY_TIMEOUT=120
```

### Cost Monitoring Configuration

```bash
# Cost Monitoring Settings
PSN_BIGQUERY_COST_MONITORING_ENABLED=true
PSN_BIGQUERY_ALERT_COOLDOWN_HOURS=1
PSN_BIGQUERY_EMERGENCY_LIMIT_MULTIPLIER=5
PSN_BIGQUERY_GRACE_PERIOD_HOURS=1

# Budget Tier Defaults
PSN_STANDARD_DAILY_LIMIT=10.00
PSN_PREMIUM_DAILY_LIMIT=50.00
PSN_ENTERPRISE_DAILY_LIMIT=200.00

PSN_STANDARD_MONTHLY_LIMIT=300.00
PSN_PREMIUM_MONTHLY_LIMIT=1500.00
PSN_ENTERPRISE_MONTHLY_LIMIT=6000.00

# Alert Thresholds (as percentages)
PSN_COST_ALERT_THRESHOLD_1=50
PSN_COST_ALERT_THRESHOLD_2=80
PSN_COST_ALERT_THRESHOLD_3=95
```

### API and Security Settings

```bash
# Authentication
JWT_SECRET_KEY=your-secret-key-here
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# API Rate Limiting
PSN_RATE_LIMIT_REAL_TIME=10/minute
PSN_RATE_LIMIT_BUDGET_ENFORCEMENT=20/minute
PSN_RATE_LIMIT_ANALYTICS=5/minute
PSN_RATE_LIMIT_REPORTS=5/minute
PSN_RATE_LIMIT_BUDGET_CONFIG=10/minute

# CORS Configuration
ALLOWED_ORIGINS=https://your-frontend-domain.com,https://admin.your-domain.com
ALLOWED_METHODS=GET,POST,PUT,DELETE,OPTIONS
ALLOWED_HEADERS=Content-Type,Authorization
```

### Database and Cache Configuration

```bash
# PostgreSQL (for metadata)
DATABASE_URL=postgresql://user:password@localhost:5432/paidsearchnav

# Redis (for caching)
REDIS_URL=redis://localhost:6379/0
PSN_CACHE_TTL_REAL_TIME=60  # 1 minute
PSN_CACHE_TTL_BUDGET_CONFIG=600  # 10 minutes
PSN_CACHE_TTL_ANALYTICS=3600  # 1 hour

# Connection Pool Settings
DATABASE_POOL_SIZE=10
DATABASE_MAX_OVERFLOW=20
DATABASE_POOL_TIMEOUT=30
```

### Monitoring and Observability

```bash
# Logging Configuration
LOG_LEVEL=INFO
LOG_FORMAT=json
PSN_ENABLE_CORRELATION_IDS=true

# Metrics and Tracing
PSN_METRICS_ENABLED=true
PSN_TRACING_ENABLED=true
PSN_OTLP_ENDPOINT=http://localhost:4317
PSN_TRACING_SAMPLE_RATE=0.1

# Alert Manager Integration
ALERT_MANAGER_URL=http://localhost:9093
ALERT_WEBHOOK_URL=https://hooks.slack.com/your-webhook-url
```

## BigQuery Configuration

### Service Account Setup

Create a Google Cloud service account with the following permissions:

```json
{
  "type": "service_account",
  "project_id": "your-gcp-project-id",
  "private_key_id": "key-id",
  "private_key": "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n",
  "client_email": "paidsearchnav-bigquery@your-gcp-project-id.iam.gserviceaccount.com",
  "client_id": "client-id",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs/paidsearchnav-bigquery%40your-gcp-project-id.iam.gserviceaccount.com"
}
```

### Required IAM Roles

```bash
# Essential roles for the service account
gcloud projects add-iam-policy-binding your-gcp-project-id \
  --member="serviceAccount:paidsearchnav-bigquery@your-gcp-project-id.iam.gserviceaccount.com" \
  --role="roles/bigquery.dataEditor"

gcloud projects add-iam-policy-binding your-gcp-project-id \
  --member="serviceAccount:paidsearchnav-bigquery@your-gcp-project-id.iam.gserviceaccount.com" \
  --role="roles/bigquery.jobUser"

gcloud projects add-iam-policy-binding your-gcp-project-id \
  --member="serviceAccount:paidsearchnav-bigquery@your-gcp-project-id.iam.gserviceaccount.com" \
  --role="roles/bigquery.metadataViewer"

# For cost monitoring (INFORMATION_SCHEMA access)
gcloud projects add-iam-policy-binding your-gcp-project-id \
  --member="serviceAccount:paidsearchnav-bigquery@your-gcp-project-id.iam.gserviceaccount.com" \
  --role="roles/bigquery.resourceViewer"
```

### Dataset Configuration

```python
# Example dataset configuration in Python
from google.cloud import bigquery

client = bigquery.Client()

# Main analytics dataset
dataset_id = "paidsearchnav_analytics"
dataset = bigquery.Dataset(f"{client.project}.{dataset_id}")
dataset.location = "US"
dataset.description = "PaidSearchNav BigQuery analytics data"

# Set access controls
access_entries = dataset.access_entries
access_entries.append(
    bigquery.AccessEntry(
        role="WRITER",
        entity_type="userByEmail",
        entity_id="paidsearchnav-bigquery@your-gcp-project-id.iam.gserviceaccount.com"
    )
)
dataset.access_entries = access_entries

dataset = client.create_dataset(dataset, exists_ok=True)
```

## Cost Monitoring Settings

### Budget Configuration Classes

The system uses Pydantic models for configuration validation:

```python
from pydantic import BaseModel, Field
from typing import List, Optional

class CostThreshold(BaseModel):
    """Cost threshold configuration for alerts."""
    percentage: float = Field(..., ge=0, le=100, description="Percentage of budget")
    priority: str = Field(..., description="Alert priority")
    action: str = Field(..., description="Recommended action")

class CustomerBudgetConfig(BaseModel):
    """Budget configuration for a customer."""
    customer_id: str = Field(..., description="Customer identifier")
    tier: str = Field(..., description="Customer tier")
    daily_limit_usd: float = Field(..., gt=0, description="Daily budget limit")
    monthly_limit_usd: float = Field(..., gt=0, description="Monthly budget limit")
    emergency_limit_usd: float = Field(..., gt=0, description="Emergency limit")
    
    # Alert thresholds
    thresholds: List[CostThreshold] = Field(
        default_factory=lambda: [
            CostThreshold(percentage=50.0, priority="medium", action="monitor"),
            CostThreshold(percentage=80.0, priority="high", action="review"),
            CostThreshold(percentage=95.0, priority="critical", action="throttle"),
        ]
    )
    
    # Grace period settings
    grace_period_hours: int = Field(default=1, description="Grace period for overruns")
    throttle_enabled: bool = Field(default=True, description="Enable throttling")
    alerts_enabled: bool = Field(default=True, description="Enable alerts")
```

### Default Tier Configurations

```python
# Default budget configurations by tier
DEFAULT_BUDGETS = {
    "standard": {
        "daily_limit_usd": 10.0,
        "monthly_limit_usd": 300.0,
        "emergency_limit_usd": 50.0,
        "features": ["basic_monitoring"]
    },
    "premium": {
        "daily_limit_usd": 50.0,
        "monthly_limit_usd": 1500.0,
        "emergency_limit_usd": 200.0,
        "features": ["real_time_monitoring", "advanced_analytics", "custom_alerts"]
    },
    "enterprise": {
        "daily_limit_usd": 200.0,
        "monthly_limit_usd": 6000.0,
        "emergency_limit_usd": 1000.0,
        "features": ["all_premium_features", "ml_predictions", "custom_integrations"]
    }
}
```

### Cost Calculation Configuration

```python
# BigQuery cost calculation constants
BIGQUERY_COSTS = {
    "query_cost_per_tb": 5.0,  # $5 per TB processed
    "slot_cost_per_hour": 0.04,  # $0.04 per slot hour
    "storage_cost_per_tb_month": 0.02,  # $0.02 per TB per month
    "streaming_cost_per_200k_rows": 0.01,  # $0.01 per 200K rows
}

# Cost aggregation windows
COST_WINDOWS = {
    "real_time": 5,  # 5 minutes for real-time monitoring
    "recent": 60,    # 1 hour for recent activity
    "daily": 1440,   # 24 hours for daily totals
    "weekly": 10080, # 7 days for weekly analysis
    "monthly": 43200 # 30 days for monthly analysis
}
```

## Security Configuration

### Authentication and Authorization

```python
# JWT Configuration
JWT_CONFIG = {
    "secret_key": os.getenv("JWT_SECRET_KEY"),
    "algorithm": "HS256",
    "expiration_hours": 24,
    "issuer": "paidsearchnav",
    "audience": ["api", "web"]
}

# Role-based permissions
ROLE_PERMISSIONS = {
    "user": {
        "can_view_own_data": True,
        "can_view_all_data": False,
        "can_modify_budgets": False,
        "can_access_admin_endpoints": False
    },
    "admin": {
        "can_view_own_data": True,
        "can_view_all_data": True,
        "can_modify_budgets": True,
        "can_access_admin_endpoints": True
    },
    "super_admin": {
        "can_view_own_data": True,
        "can_view_all_data": True,
        "can_modify_budgets": True,
        "can_access_admin_endpoints": True,
        "can_modify_system_config": True
    }
}
```

### API Security Headers

```python
# Security headers configuration
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "Content-Security-Policy": "default-src 'self'",
    "Referrer-Policy": "strict-origin-when-cross-origin"
}

# CORS configuration
CORS_CONFIG = {
    "allowed_origins": os.getenv("ALLOWED_ORIGINS", "").split(","),
    "allowed_methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    "allowed_headers": ["Content-Type", "Authorization", "X-Correlation-ID"],
    "expose_headers": ["X-Correlation-ID", "X-Rate-Limit-Remaining"],
    "allow_credentials": True,
    "max_age": 3600
}
```

## Performance Tuning

### Query Optimization Settings

```python
# BigQuery query optimization
QUERY_CONFIG = {
    "use_query_cache": True,
    "use_legacy_sql": False,
    "max_results": 10000,
    "timeout_seconds": 180,
    "job_retry_count": 3,
    "job_retry_delay": 5,
    "dry_run_validation": True
}

# Connection pool settings
CONNECTION_POOL = {
    "max_connections": 10,
    "min_connections": 2,
    "connection_timeout": 30,
    "idle_timeout": 300,
    "max_lifetime": 3600
}
```

### Caching Configuration

```python
# Multi-level caching strategy
CACHE_CONFIG = {
    "real_time_costs": {
        "ttl": 60,  # 1 minute
        "max_size": 1000,
        "eviction_policy": "LRU"
    },
    "budget_configs": {
        "ttl": 600,  # 10 minutes
        "max_size": 500,
        "eviction_policy": "LRU"
    },
    "analytics_results": {
        "ttl": 3600,  # 1 hour
        "max_size": 100,
        "eviction_policy": "LFU"
    },
    "historical_data": {
        "ttl": 86400,  # 24 hours
        "max_size": 50,
        "eviction_policy": "TTL"
    }
}

# Redis configuration
REDIS_CONFIG = {
    "host": "localhost",
    "port": 6379,
    "db": 0,
    "password": None,
    "ssl": False,
    "connection_pool_size": 10,
    "socket_timeout": 5,
    "socket_connect_timeout": 5,
    "retry_on_timeout": True,
    "health_check_interval": 30
}
```

## Development vs Production

### Development Configuration

```bash
# Development environment settings
ENV=development
DEBUG=true
LOG_LEVEL=DEBUG

# Use local services
DATABASE_URL=postgresql://localhost:5432/paidsearchnav_dev
REDIS_URL=redis://localhost:6379/1

# Relaxed security for development
JWT_EXPIRATION_HOURS=720  # 30 days
CORS_ALLOW_ALL_ORIGINS=true

# Lower rate limits for testing
PSN_RATE_LIMIT_REAL_TIME=100/minute
PSN_RATE_LIMIT_ANALYTICS=50/minute

# Reduced BigQuery costs for testing
PSN_STANDARD_DAILY_LIMIT=1.00
PSN_PREMIUM_DAILY_LIMIT=5.00
```

### Production Configuration

```bash
# Production environment settings
ENV=production
DEBUG=false
LOG_LEVEL=INFO

# Production database URLs (use secrets management)
DATABASE_URL=${DATABASE_URL_SECRET}
REDIS_URL=${REDIS_URL_SECRET}

# Strict security settings
JWT_EXPIRATION_HOURS=24
CORS_ALLOW_ALL_ORIGINS=false
ALLOWED_ORIGINS=https://app.paidsearchnav.com

# Production rate limits
PSN_RATE_LIMIT_REAL_TIME=10/minute
PSN_RATE_LIMIT_ANALYTICS=5/minute

# Production budget limits
PSN_STANDARD_DAILY_LIMIT=10.00
PSN_PREMIUM_DAILY_LIMIT=50.00
PSN_ENTERPRISE_DAILY_LIMIT=200.00

# Enhanced monitoring
PSN_METRICS_ENABLED=true
PSN_TRACING_ENABLED=true
PSN_ALERT_MANAGER_ENABLED=true
```

### Staging Configuration

```bash
# Staging environment (production-like with safety nets)
ENV=staging
DEBUG=false
LOG_LEVEL=DEBUG

# Staging-specific settings
PSN_BIGQUERY_COST_MONITORING_ENABLED=true
PSN_ALERT_MANAGER_ENABLED=false  # Don't send real alerts

# Reduced limits for safety
PSN_STANDARD_DAILY_LIMIT=2.00
PSN_PREMIUM_DAILY_LIMIT=10.00
PSN_ENTERPRISE_DAILY_LIMIT=25.00

# Enhanced logging for debugging
LOG_LEVEL=DEBUG
PSN_ENABLE_CORRELATION_IDS=true
PSN_LOG_SQL_QUERIES=true
```

## Configuration Validation

### Environment Variable Validation

```python
from pydantic import BaseSettings, validator
from typing import Optional, List

class BigQuerySettings(BaseSettings):
    """BigQuery configuration with validation."""
    
    # Required settings
    google_cloud_project: str
    bigquery_dataset: str
    
    # Optional settings with defaults
    bigquery_location: str = "US"
    bigquery_job_timeout: int = 300
    bigquery_query_timeout: int = 180
    
    # Cost monitoring settings
    cost_monitoring_enabled: bool = True
    alert_cooldown_hours: int = 1
    emergency_limit_multiplier: float = 5.0
    
    @validator('emergency_limit_multiplier')
    def validate_emergency_multiplier(cls, v):
        if v < 1.0 or v > 20.0:
            raise ValueError('Emergency limit multiplier must be between 1.0 and 20.0')
        return v
    
    @validator('alert_cooldown_hours')
    def validate_cooldown(cls, v):
        if v < 0 or v > 24:
            raise ValueError('Alert cooldown must be between 0 and 24 hours')
        return v
    
    class Config:
        env_prefix = "PSN_"
        case_sensitive = False
```

### Configuration Testing

```python
import pytest
from pydantic import ValidationError

def test_valid_configuration():
    """Test that valid configuration is accepted."""
    config = BigQuerySettings(
        google_cloud_project="test-project",
        bigquery_dataset="test_dataset",
        cost_monitoring_enabled=True,
        emergency_limit_multiplier=5.0
    )
    assert config.google_cloud_project == "test-project"

def test_invalid_emergency_multiplier():
    """Test that invalid emergency multiplier is rejected."""
    with pytest.raises(ValidationError):
        BigQuerySettings(
            google_cloud_project="test-project",
            bigquery_dataset="test_dataset",
            emergency_limit_multiplier=25.0  # Too high
        )
```

## Troubleshooting Configuration

### Common Configuration Issues

1. **Missing Service Account**: Ensure `GOOGLE_APPLICATION_CREDENTIALS` points to valid JSON
2. **Insufficient Permissions**: Verify IAM roles for the service account
3. **Invalid Budget Limits**: Check that monthly limit ≥ 20x daily limit
4. **Rate Limit Conflicts**: Ensure rate limits don't exceed BigQuery quotas
5. **Cache Connection Issues**: Verify Redis connectivity and configuration

### Configuration Validation Script

```bash
#!/bin/bash
# validate-config.sh - Configuration validation script

echo "Validating BigQuery Configuration..."

# Check required environment variables
for var in GOOGLE_CLOUD_PROJECT BIGQUERY_DATASET DATABASE_URL; do
    eval "value=\$$var"
    if [ -z "$value" ]; then
        echo "ERROR: Missing required environment variable: $var"
        exit 1
    fi
done

# Validate service account file
if [ ! -f "$GOOGLE_APPLICATION_CREDENTIALS" ]; then
    echo "ERROR: Service account file not found: $GOOGLE_APPLICATION_CREDENTIALS"
    exit 1
fi

# Test BigQuery connection
python -c "
from google.cloud import bigquery
client = bigquery.Client()
try:
    datasets = list(client.list_datasets(max_results=1))
    print('✓ BigQuery connection successful')
except Exception as e:
    print(f'✗ BigQuery connection failed: {e}')
    exit(1)
"

echo "✓ Configuration validation complete"
```

---

*For deployment instructions, see the [Deployment Guide](deployment.md)*
*For performance optimization, see the [Performance Tuning Guide](performance-tuning.md)*