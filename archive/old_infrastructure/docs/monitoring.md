# Monitoring and Observability Guide

## Overview

PaidSearchNav API includes comprehensive monitoring and observability features to ensure operational excellence in production environments.

## Features

### 1. Distributed Tracing (OpenTelemetry)

The API uses OpenTelemetry for distributed tracing, providing visibility into request flows across services.

#### Configuration

```bash
# Enable tracing (default: true)
export PSN_TRACING_ENABLED=true

# OTLP endpoint for trace export
export PSN_OTLP_ENDPOINT=http://localhost:4317

# Optional: OTLP headers for authentication
export PSN_OTLP_HEADERS='{"api-key": "your-key"}'

# Sampling rate (0.0 to 1.0)
export PSN_TRACING_SAMPLE_RATE=1.0

# Enable console export for debugging
export PSN_TRACING_CONSOLE_EXPORT=false
```

#### Supported Integrations

- Jaeger
- Zipkin
- AWS X-Ray
- Google Cloud Trace
- DataDog APM
- New Relic

### 2. Metrics (Prometheus)

Business and operational metrics are exposed in Prometheus format.

#### Endpoint

```
GET /metrics
```

#### Key Metrics

**Request Metrics:**
- `api_requests_total` - Total API requests by method, endpoint, and status
- `api_request_duration_seconds` - Request duration histogram
- `api_request_size_bytes` - Request size summary
- `api_response_size_bytes` - Response size summary

**Business Metrics:**
- `audits_created_total` - Total audits created by customer and type
- `audits_completed_total` - Total audits completed with status
- `audit_duration_seconds` - Audit processing duration
- `keywords_processed_total` - Keywords processed per audit
- `audit_issues_found_total` - Issues found by type

**Authentication Metrics:**
- `api_auth_attempts_total` - Authentication attempts
- `api_auth_failures_total` - Authentication failures by reason
- `api_rate_limit_hits_total` - Rate limit violations

**Database Metrics:**
- `db_connections_active` - Active database connections
- `db_query_duration_seconds` - Query duration by type

**Background Job Metrics:**
- `background_jobs_active` - Currently running jobs
- `background_jobs_completed_total` - Completed jobs by status
- `background_jobs_duration_seconds` - Job execution duration

**Cache Metrics:**
- `cache_hits_total` - Cache hits by type and pattern
- `cache_misses_total` - Cache misses
- `cache_evictions_total` - Cache evictions by reason

### 3. Structured Logging

All logs include correlation IDs for request tracking.

#### Log Format

```json
{
  "timestamp": "2025-01-23T12:34:56.789Z",
  "level": "INFO",
  "name": "paidsearchnav.api",
  "message": "Request completed",
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
  "service": "paidsearchnav-api",
  "environment": "production",
  "method": "POST",
  "path": "/api/v1/audits",
  "status_code": 201,
  "duration_ms": 234.5
}
```

#### Correlation ID Headers

- Request: `X-Correlation-ID` or `X-Request-ID`
- Response: `X-Correlation-ID`

### 4. Health Checks

#### Basic Health Check
```
GET /api/v1/health
```

Returns basic health status of core services.

#### Comprehensive Health Check
```
GET /api/v1/health/full
```

Returns detailed health information including:
- Database connectivity
- Redis cache status
- Google Ads API configuration
- System resources (CPU, memory, disk)
- Response times

#### Kubernetes Probes

**Liveness Probe:**
```
GET /api/v1/health/live
```

**Readiness Probe:**
```
GET /api/v1/health/ready
```

### 5. Monitoring Endpoints

#### Trace Status
```
GET /api/v1/trace/status
```

Shows current tracing configuration and status.

#### Metrics Summary
```
GET /api/v1/metrics/summary
```

Provides a human-readable summary of key metrics.

#### Correlation Test
```
POST /api/v1/debug/correlation-test
```

Tests correlation ID propagation through the system.

## Integration Examples

### Prometheus Configuration

```yaml
scrape_configs:
  - job_name: 'paidsearchnav-api'
    static_configs:
      - targets: ['api.paidsearchnav.com:8000']
    metrics_path: '/metrics'
    scrape_interval: 30s
```

### Grafana Dashboard

Key queries for monitoring:

```promql
# Request rate
rate(api_requests_total[5m])

# Error rate
rate(api_requests_total{status_code=~"5.."}[5m])

# Response time percentiles
histogram_quantile(0.95, rate(api_request_duration_seconds_bucket[5m]))

# Active audits
sum(rate(audits_created_total[5m])) - sum(rate(audits_completed_total[5m]))

# Cache hit rate
rate(cache_hits_total[5m]) / (rate(cache_hits_total[5m]) + rate(cache_misses_total[5m]))
```

### Alerting Rules

Example Prometheus alerting rules:

```yaml
groups:
  - name: paidsearchnav_api
    rules:
      - alert: HighErrorRate
        expr: rate(api_requests_total{status_code=~"5.."}[5m]) > 0.05
        for: 5m
        annotations:
          summary: "High error rate detected"
          
      - alert: SlowResponseTime
        expr: histogram_quantile(0.95, rate(api_request_duration_seconds_bucket[5m])) > 2
        for: 10m
        annotations:
          summary: "95th percentile response time above 2 seconds"
          
      - alert: DatabaseConnectionFailure
        expr: up{job="paidsearchnav-api"} == 1 and db_connections_active == 0
        for: 2m
        annotations:
          summary: "Database connection pool is empty"
```

## Best Practices

1. **Correlation IDs**: Always include correlation IDs in logs and pass them to downstream services
2. **Sampling**: In high-traffic environments, adjust `PSN_TRACING_SAMPLE_RATE` to reduce overhead
3. **Metrics Cardinality**: Be cautious with high-cardinality labels to avoid metrics explosion
4. **Health Checks**: Use appropriate health check endpoints for different purposes
5. **Log Levels**: Use appropriate log levels (DEBUG in dev, INFO in prod)

## Troubleshooting

### Missing Traces

1. Check if tracing is enabled: `PSN_TRACING_ENABLED=true`
2. Verify OTLP endpoint is accessible
3. Check for errors in application logs
4. Verify sampling rate is not 0

### Missing Metrics

1. Ensure Prometheus endpoint is accessible: `/metrics`
2. Check Prometheus scrape configuration
3. Verify metrics are being registered on startup

### Correlation ID Issues

1. Check middleware order in application startup
2. Verify correlation ID headers are being passed
3. Check structured logging configuration

## Performance Impact

- Tracing: ~1-2% overhead with 100% sampling
- Metrics: Negligible overhead
- Structured logging: ~5-10% overhead vs plain text
- Health checks: Cached for 5 seconds to reduce load