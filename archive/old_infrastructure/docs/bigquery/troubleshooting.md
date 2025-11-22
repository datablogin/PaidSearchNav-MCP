# BigQuery Troubleshooting Guide

Comprehensive troubleshooting guide for common issues with the BigQuery hybrid pipeline, including solutions, debugging steps, and preventive measures.

## Table of Contents

1. [Common Issues](#common-issues)
2. [Authentication Problems](#authentication-problems)
3. [Cost Monitoring Issues](#cost-monitoring-issues)
4. [Performance Problems](#performance-problems)
5. [Error Codes Reference](#error-codes-reference)
6. [Debugging Tools](#debugging-tools)
7. [Emergency Procedures](#emergency-procedures)

## Common Issues

### Issue: "BigQuery integration not enabled"

**Symptoms**:
- HTTP 402 error when accessing BigQuery endpoints
- Message: "BigQuery integration not enabled. Upgrade to premium tier."

**Root Causes**:
- User account is on standard tier
- BigQuery service configuration is disabled
- License/subscription issue

**Solutions**:
```bash
# 1. Check user tier in database
SELECT tier FROM users WHERE id = 'user_id';

# 2. Verify BigQuery service configuration
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/bigquery/health

# 3. Contact administrator to upgrade tier
```

**Prevention**:
- Implement clear tier communication in UI
- Add tier validation before BigQuery operations
- Provide upgrade path documentation

### Issue: "Access denied for customer data"

**Symptoms**:
- HTTP 403 error: "Access denied. You can only access data for customer X"
- User cannot access requested customer's analytics

**Root Causes**:
- User requesting data for different customer
- Role permissions not properly configured
- Customer ID mismatch

**Solutions**:
```python
# Check user permissions
def debug_user_access(user_id: str, requested_customer_id: str):
    user = get_user(user_id)
    print(f"User role: {user.role}")
    print(f"User customer_id: {user.customer_id}")
    print(f"Requested customer_id: {requested_customer_id}")
    
    if user.role in ["admin", "super_admin"]:
        print("✓ Admin access - should be allowed")
    elif user.customer_id == requested_customer_id:
        print("✓ Same customer - should be allowed")
    else:
        print("✗ Access should be denied")
```

**Prevention**:
- Implement proper role-based access controls
- Clear error messages indicating access requirements
- Audit customer data access regularly

### Issue: Real-time data appears stale

**Symptoms**:
- Cost data is more than 5 minutes old
- Real-time monitoring shows outdated information
- Freshness indicators show high delay

**Root Causes**:
- BigQuery processing delay (normal)
- Clock synchronization issues
- Query optimization cache interference

**Solutions**:
```python
# Check data freshness
GET /api/v1/bigquery/cost-monitoring/real-time?customer_id=X

# Response includes freshness indicator:
{
  "data_freshness_minutes": 8.5  # Should be < 5 minutes normally
}

# If freshness > 5 minutes, check:
# 1. BigQuery job execution time
# 2. System clock synchronization
# 3. Query cache settings
```

**Prevention**:
- Set appropriate expectations (5-minute delay is normal)
- Monitor freshness metrics
- Implement alerting for excessive delays

## Authentication Problems

### Issue: JWT token expired or invalid

**Symptoms**:
- HTTP 401 error: "Authentication required"
- Intermittent authentication failures
- Token validation errors in logs

**Root Causes**:
- Token expired (24-hour default)
- Invalid token signature
- Clock skew between systems

**Solutions**:
```bash
# 1. Check token expiration
jwt_decode() {
  python3 -c "
import jwt
import sys
token = sys.argv[1]
try:
    payload = jwt.decode(token, options={'verify_signature': False})
    print('Token payload:', payload)
    print('Expires at:', payload.get('exp'))
except Exception as e:
    print('Token decode error:', e)
" "$1"
}

# Usage: jwt_decode "your_jwt_token_here"

# 2. Refresh token
curl -X POST "http://localhost:8000/auth/refresh" \
  -H "Authorization: Bearer $OLD_TOKEN"

# 3. Check system clock synchronization
ntpdate -q pool.ntp.org
```

**Prevention**:
- Implement automatic token refresh
- Monitor token expiration proactively
- Ensure proper NTP synchronization

### Issue: Google Cloud authentication failures

**Symptoms**:
- "Could not automatically determine credentials"
- "Service account key file not found"
- BigQuery operations fail with auth errors

**Root Causes**:
- Missing or invalid service account file
- Incorrect file permissions
- Missing IAM roles

**Solutions**:
```bash
# 1. Verify service account file exists and is readable
ls -la $GOOGLE_APPLICATION_CREDENTIALS
cat $GOOGLE_APPLICATION_CREDENTIALS | jq .

# 2. Test authentication manually
gcloud auth activate-service-account \
  --key-file=$GOOGLE_APPLICATION_CREDENTIALS

# 3. Test BigQuery access
bq ls --project_id=$GOOGLE_CLOUD_PROJECT

# 4. Check IAM roles
gcloud projects get-iam-policy $GOOGLE_CLOUD_PROJECT \
  --flatten="bindings[].members" \
  --format="table(bindings.role)" \
  --filter="bindings.members:serviceAccount:YOUR_SERVICE_ACCOUNT"
```

**Prevention**:
- Secure service account key management
- Regular IAM role audits
- Automated credential validation

## Cost Monitoring Issues

### Issue: Budget enforcement blocking legitimate operations

**Symptoms**:
- Operations rejected with "Budget limit exceeded"
- Emergency circuit breaker activated
- Users unable to perform analysis

**Root Causes**:
- Actual budget limit reached
- Budget configuration error
- Cost calculation misconfiguration

**Solutions**:
```bash
# 1. Check current cost status
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/bigquery/cost-monitoring/real-time?customer_id=X"

# 2. Review budget configuration
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  "http://localhost:8000/api/v1/bigquery/cost-monitoring/budget-config"

# 3. Temporarily increase budget (admin only)
curl -X POST -H "Authorization: Bearer $ADMIN_TOKEN" \
  "http://localhost:8000/api/v1/bigquery/cost-monitoring/budget-config" \
  -d "customer_id=X&tier=premium&daily_limit_usd=100&monthly_limit_usd=3000"

# 4. Reset circuit breaker (if needed)
# This would require database access or admin API
```

**Prevention**:
- Monitor budget utilization trends
- Set up proactive budget alerts
- Implement budget increase workflows

### Issue: Cost calculations appear incorrect

**Symptoms**:
- Reported costs don't match Google Cloud billing
- Large discrepancies in cost tracking
- Negative or unrealistic cost values

**Root Causes**:
- Cost calculation formula errors
- BigQuery pricing changes
- Data type conversion issues

**Solutions**:
```python
# Debug cost calculation manually
def debug_cost_calculation():
    # Example BigQuery job data
    bytes_processed = 1073741824  # 1GB
    slot_ms = 10000  # 10 seconds * 1000ms
    
    # Our calculation
    query_cost = (bytes_processed / (1024**4)) * 5.0  # $5 per TB
    slot_cost = (slot_ms / 1000 / 3600) * 0.04  # $0.04 per slot-hour
    total_cost = query_cost + slot_cost
    
    print(f"Bytes processed: {bytes_processed:,}")
    print(f"Query cost: ${query_cost:.6f}")
    print(f"Slot cost: ${slot_cost:.6f}")
    print(f"Total cost: ${total_cost:.6f}")
    
    # Compare with Google Cloud billing
    # Use BigQuery INFORMATION_SCHEMA.JOBS_BY_PROJECT for validation

debug_cost_calculation()
```

**Prevention**:
- Regular cost calculation validation
- Automated tests for cost formulas
- Monitor BigQuery pricing updates

### Issue: Alert fatigue from excessive notifications

**Symptoms**:
- Too many cost alerts generated
- Users ignoring important alerts
- Alert system considered unreliable

**Root Causes**:
- Alert thresholds set too low
- Insufficient cooldown periods
- Lack of alert prioritization

**Solutions**:
```python
# Review alert configuration
{
  "thresholds": [
    {"percentage": 50.0, "priority": "medium", "action": "monitor"},
    {"percentage": 80.0, "priority": "high", "action": "review"},
    {"percentage": 95.0, "priority": "critical", "action": "throttle"}
  ],
  "cooldown_hours": 1,  # Increase if too many alerts
  "alerts_enabled": true
}

# Adjust thresholds for specific customers
# Increase cooldown periods
# Implement alert escalation policies
```

**Prevention**:
- Tune alert thresholds based on usage patterns
- Implement smart alert grouping
- Regular alert effectiveness reviews

## Performance Problems

### Issue: Slow API response times

**Symptoms**:
- API endpoints taking >10 seconds to respond
- Timeout errors in applications
- Poor user experience

**Root Causes**:
- Expensive BigQuery queries
- Missing query optimization
- Database connection issues

**Solutions**:
```bash
# 1. Check BigQuery job performance
SELECT 
  job_id,
  creation_time,
  total_bytes_processed,
  total_slot_ms,
  total_slot_ms / 1000 as duration_seconds
FROM `project.region.INFORMATION_SCHEMA.JOBS_BY_PROJECT`
WHERE creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 1 HOUR)
ORDER BY total_slot_ms DESC
LIMIT 10;

# 2. Enable query logging for debugging
LOG_LEVEL=DEBUG
PSN_LOG_SQL_QUERIES=true

# 3. Monitor connection pool metrics
curl http://localhost:8000/metrics | grep connection_pool
```

**Prevention**:
- Implement query result caching
- Optimize BigQuery queries
- Monitor performance metrics

### Issue: High BigQuery costs despite budget controls

**Symptoms**:
- Unexpected high costs in Google Cloud billing
- Budget limits being exceeded
- Cost monitoring not preventing overruns

**Root Causes**:
- Cost calculation delays
- Budget enforcement gaps
- External BigQuery usage

**Solutions**:
```bash
# 1. Audit all BigQuery usage
SELECT 
  user_email,
  job_type,
  total_bytes_processed,
  total_cost_usd,
  creation_time
FROM `project.region.INFORMATION_SCHEMA.JOBS_BY_PROJECT`
WHERE creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
ORDER BY total_cost_usd DESC;

# 2. Check for external API usage
# Review Google Cloud console for non-application jobs

# 3. Implement stricter budget controls
# Reduce grace periods
# Lower emergency limits
```

**Prevention**:
- Regular cost audits
- Tighter budget enforcement
- Monitor all BigQuery access points

## Error Codes Reference

### HTTP Error Codes

| Code | Error | Common Causes | Solutions |
|------|-------|---------------|-----------|
| 400 | Bad Request | Invalid parameters, malformed JSON | Validate request format |
| 401 | Unauthorized | Missing/invalid JWT token | Refresh authentication |
| 402 | Payment Required | Insufficient tier access | Upgrade account tier |
| 403 | Forbidden | Insufficient permissions | Check user roles |
| 429 | Too Many Requests | Rate limit exceeded | Reduce request frequency |
| 500 | Internal Server Error | Server-side issues | Check logs, contact support |
| 502 | Bad Gateway | BigQuery service unavailable | Retry after delay |

### BigQuery-Specific Errors

| Error Code | Description | Solutions |
|------------|-------------|-----------|
| `quotaExceeded` | BigQuery quota limit reached | Wait for quota reset |
| `accessDenied` | Insufficient BigQuery permissions | Check IAM roles |
| `notFound` | Dataset or table not found | Verify resource names |
| `invalidQuery` | SQL syntax or logic error | Review query syntax |
| `timeout` | Query execution timeout | Optimize query or increase timeout |

### Application Error Codes

| Error Code | Description | Solutions |
|------------|-------------|-----------|
| `BUDGET_LIMIT_EXCEEDED` | Customer budget limit reached | Increase budget or wait |
| `CIRCUIT_BREAKER_ACTIVE` | Emergency protection triggered | Admin intervention required |
| `VALIDATION_ERROR` | Request validation failed | Fix request parameters |
| `CONFIGURATION_ERROR` | System configuration issue | Check environment variables |

## Debugging Tools

### API Health Check

```bash
#!/bin/bash
# health-check.sh - Comprehensive API health check

echo "=== BigQuery API Health Check ==="

# 1. Basic connectivity
curl -f http://localhost:8000/health || echo "❌ API not responding"

# 2. BigQuery health
curl -f http://localhost:8000/api/v1/bigquery/health || echo "❌ BigQuery integration issue"

# 3. Authentication test
TOKEN="your_test_token"
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/bigquery/cost-monitoring/real-time || echo "❌ Authentication issue"

# 4. Database connectivity
psql $DATABASE_URL -c "SELECT 1;" || echo "❌ Database connection issue"

# 5. Redis connectivity
redis-cli -u $REDIS_URL ping || echo "❌ Redis connection issue"

echo "=== Health Check Complete ==="
```

### Cost Monitoring Debug Script

```python
#!/usr/bin/env python3
# debug-cost-monitoring.py - Debug cost monitoring issues

import asyncio
import os
from google.cloud import bigquery

async def debug_cost_monitoring():
    """Debug cost monitoring functionality."""
    
    # 1. Test BigQuery connection
    try:
        client = bigquery.Client()
        datasets = list(client.list_datasets(max_results=1))
        print("✓ BigQuery connection successful")
    except Exception as e:
        print(f"❌ BigQuery connection failed: {e}")
        return
    
    # 2. Test INFORMATION_SCHEMA access
    try:
        query = f"""
        SELECT COUNT(*) as job_count
        FROM `{client.project}.region-us.INFORMATION_SCHEMA.JOBS_BY_PROJECT`
        WHERE creation_time >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 1 HOUR)
        """
        results = client.query(query).result()
        job_count = list(results)[0].job_count
        print(f"✓ INFORMATION_SCHEMA access successful ({job_count} jobs in last hour)")
    except Exception as e:
        print(f"❌ INFORMATION_SCHEMA access failed: {e}")
    
    # 3. Test cost calculation
    try:
        # Example calculation
        bytes_processed = 1073741824  # 1GB
        tb_processed = bytes_processed / (1024**4)
        cost = tb_processed * 5.0
        print(f"✓ Cost calculation test: 1GB = ${cost:.6f}")
    except Exception as e:
        print(f"❌ Cost calculation failed: {e}")

if __name__ == "__main__":
    asyncio.run(debug_cost_monitoring())
```

### Log Analysis Tools

```bash
# Extract cost monitoring errors from logs
grep "cost_monitor" /var/log/paidsearchnav.log | grep ERROR

# Find authentication failures
grep "403\|401" /var/log/paidsearchnav.log | tail -20

# Monitor BigQuery quota usage
grep "quotaExceeded\|TooManyRequests" /var/log/paidsearchnav.log

# Check rate limiting issues
grep "Rate limit exceeded" /var/log/paidsearchnav.log
```

## Emergency Procedures

### Emergency Circuit Breaker Reset

```bash
#!/bin/bash
# emergency-reset.sh - Reset emergency circuit breakers

echo "⚠️  EMERGENCY CIRCUIT BREAKER RESET ⚠️"
echo "This will allow BigQuery operations to resume."
read -p "Are you sure? (yes/no): " confirm

if [ "$confirm" = "yes" ]; then
    # Reset circuit breaker state (implementation depends on storage)
    # Option 1: Database reset
    psql $DATABASE_URL -c "UPDATE circuit_breakers SET active = false WHERE service = 'bigquery';"
    
    # Option 2: Redis reset
    redis-cli -u $REDIS_URL DEL circuit_breaker:bigquery
    
    # Option 3: API reset (if available)
    curl -X POST -H "Authorization: Bearer $ADMIN_TOKEN" \
      http://localhost:8000/admin/circuit-breaker/reset
    
    echo "✓ Circuit breaker reset complete"
else
    echo "Operation cancelled"
fi
```

### Emergency Budget Increase

```bash
#!/bin/bash
# emergency-budget-increase.sh - Temporarily increase customer budget

CUSTOMER_ID="$1"
NEW_DAILY_LIMIT="$2"
ADMIN_TOKEN="$3"

if [ -z "$CUSTOMER_ID" ] || [ -z "$NEW_DAILY_LIMIT" ] || [ -z "$ADMIN_TOKEN" ]; then
    echo "Usage: $0 <customer_id> <new_daily_limit> <admin_token>"
    exit 1
fi

echo "⚠️  EMERGENCY BUDGET INCREASE ⚠️"
echo "Customer: $CUSTOMER_ID"
echo "New daily limit: $NEW_DAILY_LIMIT"
read -p "Are you sure? (yes/no): " confirm

if [ "$confirm" = "yes" ]; then
    curl -X POST -H "Authorization: Bearer $ADMIN_TOKEN" \
      "http://localhost:8000/api/v1/bigquery/cost-monitoring/budget-config" \
      -d "customer_id=$CUSTOMER_ID&tier=emergency&daily_limit_usd=$NEW_DAILY_LIMIT&monthly_limit_usd=$((NEW_DAILY_LIMIT * 30))"
    
    echo "✓ Emergency budget increase applied"
    echo "⚠️  Remember to revert after emergency is resolved"
else
    echo "Operation cancelled"
fi
```

### Rollback Procedures

```bash
#!/bin/bash
# rollback.sh - Rollback to previous configuration

echo "🔄 CONFIGURATION ROLLBACK"

# 1. Backup current configuration
kubectl get configmap bigquery-config -o yaml > config-backup-$(date +%s).yaml

# 2. Restore previous configuration
kubectl apply -f config-previous.yaml

# 3. Restart services
kubectl rollout restart deployment/paidsearchnav-api

# 4. Verify rollback
kubectl rollout status deployment/paidsearchnav-api

echo "✓ Rollback complete"
```

## Getting Additional Help

### Support Escalation

1. **Level 1**: Check this troubleshooting guide
2. **Level 2**: Review system logs and metrics
3. **Level 3**: Contact system administrator
4. **Level 4**: Escalate to Google Cloud Support (for BigQuery issues)

### Useful Resources

- **Google Cloud Status**: https://status.cloud.google.com/
- **BigQuery Documentation**: https://cloud.google.com/bigquery/docs
- **PaidSearchNav Issues**: https://github.com/datablogin/PaidSearchNav/issues
- **System Monitoring**: Check your monitoring dashboard
- **Log Aggregation**: Check your log management system

### Information to Gather for Support

When contacting support, provide:

1. **Error Details**: Full error messages and stack traces
2. **Request Details**: API endpoints, parameters, timestamps
3. **User Context**: User ID, customer ID, role
4. **System State**: Current configuration, recent changes
5. **Logs**: Relevant log excerpts with correlation IDs
6. **Reproduction Steps**: How to reproduce the issue

---

*For configuration help, see the [Configuration Reference](configuration.md)*
*For performance optimization, see the [Performance Tuning Guide](performance-tuning.md)*