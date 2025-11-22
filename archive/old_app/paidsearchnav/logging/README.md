# Logging and Monitoring

This module provides comprehensive logging and monitoring infrastructure for PaidSearchNav.

## Features

### Structured Logging
- JSON-formatted logs for easy parsing and analysis
- Contextual logging with customer ID, job ID, etc.
- Multiple log levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- Automatic third-party library log level management

### Alert Channels
- **Slack**: Real-time alerts to Slack channels
- **Email**: SMTP-based email alerts
- **Sentry**: Error tracking and aggregation
- Configurable alert levels and filtering

### Monitoring & Metrics
- Performance timing with decorators and context managers
- Counter and gauge metrics
- Job execution tracking
- API call monitoring

### Audit Logging
- Complete audit trail of all analysis jobs
- API call logging for compliance
- Searchable audit history
- Result archival

## Configuration

### Environment Variables

```bash
# Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
PSN_LOG_LEVEL=INFO

# Format (true for JSON, false for plain text)
PSN_LOG_JSON_FORMAT=true

# File logging
PSN_LOG_FILE=/var/log/paidsearchnav/app.log
PSN_LOG_MAX_SIZE_MB=100
PSN_LOG_RETENTION_DAYS=30

# Alerts
PSN_LOG_ENABLE_ALERTS=true
PSN_LOG_ALERT_LEVEL=ERROR

# Slack
PSN_SLACK_WEBHOOK_URL=https://hooks.slack.com/services/xxx
PSN_SLACK_CHANNEL=#alerts

# Email
PSN_SMTP_HOST=smtp.gmail.com
PSN_SMTP_PORT=587
PSN_SMTP_USERNAME=alerts@example.com
PSN_SMTP_PASSWORD=xxx
PSN_EMAIL_FROM=alerts@example.com
PSN_EMAIL_TO=admin@example.com,ops@example.com

# Sentry
PSN_SENTRY_DSN=https://xxx@sentry.io/project
```

### Programmatic Configuration

```python
from paidsearchnav.logging import configure_logging, LogConfig, LogLevel
from paidsearchnav.core.config import Settings

settings = Settings()
config = LogConfig(
    level=LogLevel.INFO,
    json_format=True,
    enable_alerts=True,
    slack_webhook_url="https://hooks.slack.com/xxx",
    email_to=["admin@example.com"],
)

configure_logging(settings, config)
```

## Usage

### Basic Logging

```python
from paidsearchnav.logging import get_logger

logger = get_logger(__name__)

logger.debug("Debug message")
logger.info("Info message")
logger.warning("Warning message")
logger.error("Error message", exc_info=True)
logger.critical("Critical message")
```

### Contextual Logging

```python
from paidsearchnav.logging import add_context, LogContext

# Add context for all subsequent logs
add_context(customer_id="123", job_id="abc")
logger.info("Processing started")  # Will include context

# Temporary context
with LogContext(request_id="xyz"):
    logger.info("Handling request")  # Includes request_id
# request_id removed after context
```

### Performance Monitoring

```python
from paidsearchnav.logging.monitoring import timer, timed, track_job

# Time a code block
with timer("api.request", tags={"endpoint": "/search"}):
    response = make_api_request()

# Decorator for functions
@timed("analyzer.process")
def process_data():
    pass

# Track job execution
@track_job("keyword_analysis")
async def analyze_keywords(customer_id: str, job_id: str):
    # Automatically tracks start, completion/failure, duration
    pass
```

### Audit Logging

```python
from paidsearchnav.logging.audit import get_audit_logger

audit = get_audit_logger()

# Log analysis job
audit.log_analysis_start(
    customer_id="123",
    analysis_type="keyword_match",
    job_id="job-001",
    config={"days": 90},
)

# Log completion
audit.log_analysis_complete(
    customer_id="123",
    analysis_type="keyword_match",
    job_id="job-001",
    result=analysis_result,
    duration_seconds=120.5,
)

# Search audit logs
results = audit.search_audits(
    customer_id="123",
    analysis_type="keyword_match",
    start_date=datetime.now() - timedelta(days=7),
)
```

## Alert Examples

### Slack Alert
```python
logger.error("Critical issue detected", extra={
    "customer_id": "123",
    "analysis_id": "abc",
    "error_details": "Database connection failed",
})
```

Results in Slack message:
```
🔴 ERROR: Critical issue detected
Logger: paidsearchnav.analyzer
Module: keyword_match
Customer ID: 123
Analysis ID: abc
```

### Email Alert
HTML-formatted email with:
- Color-coded severity level
- Full context and metadata
- Exception details if applicable
- Timestamp and location info

## Best Practices

1. **Use appropriate log levels**:
   - DEBUG: Detailed diagnostic info
   - INFO: General informational messages
   - WARNING: Warning conditions
   - ERROR: Error conditions
   - CRITICAL: Critical conditions requiring immediate attention

2. **Include context**:
   ```python
   logger.info("Analysis completed", extra={
       "customer_id": customer_id,
       "duration_seconds": duration,
       "recommendations_count": len(recommendations),
   })
   ```

3. **Use structured data**:
   ```python
   # Good - structured data
   logger.info("API call completed", extra={
       "status_code": 200,
       "duration_ms": 150,
       "endpoint": "/search",
   })
   
   # Avoid - unstructured strings
   logger.info(f"API call to /search returned 200 in 150ms")
   ```

4. **Handle sensitive data**:
   ```python
   # Never log sensitive data
   logger.info("User authenticated", extra={
       "user_id": user_id,
       # Don't log: password, api_keys, tokens
   })
   ```

5. **Use audit logging for compliance**:
   ```python
   # Log all Google Ads API calls
   audit.log_api_call(
       customer_id=customer_id,
       service="google_ads",
       method="POST",
       endpoint="/v14/customers/search",
       status_code=200,
       duration_ms=250,
   )
   ```

## Integration with Analyzers

```python
from paidsearchnav.logging import get_logger, add_context
from paidsearchnav.logging.monitoring import track_job

logger = get_logger(__name__)

class KeywordMatchAnalyzer:
    @track_job("keyword_match_analysis")
    async def analyze(self, customer_id: str, job_id: str):
        add_context(customer_id=customer_id, job_id=job_id)
        
        logger.info("Starting keyword match analysis")
        
        try:
            # Analysis logic
            result = await self._perform_analysis()
            
            logger.info("Analysis completed", extra={
                "total_keywords": result.total_keywords,
                "issues_found": result.issues_found,
            })
            
            return result
            
        except Exception as e:
            logger.error("Analysis failed", exc_info=True)
            raise
```

## Log Aggregation

Logs can be aggregated using various tools:

1. **CloudWatch Logs** (AWS):
   - JSON format enables CloudWatch Insights queries
   - Set up log groups per environment
   - Create metric filters for alerts

2. **Stackdriver** (GCP):
   - Native JSON log support
   - Advanced querying and alerting
   - Integration with GCP services

3. **ELK Stack**:
   - Elasticsearch for storage
   - Logstash for processing
   - Kibana for visualization

4. **Datadog**:
   - APM integration
   - Custom dashboards
   - Anomaly detection

## Troubleshooting

### No logs appearing
1. Check log level: `PSN_LOG_LEVEL`
2. Verify logging is configured: `configure_logging()`
3. Check handler configuration

### Alerts not sending
1. Verify credentials (Slack webhook, SMTP settings)
2. Check alert level: `PSN_LOG_ALERT_LEVEL`
3. Test connectivity to external services

### Performance impact
1. Use async handlers for alerts
2. Implement log sampling for high-volume endpoints
3. Rotate logs regularly

### Disk space issues
1. Configure log rotation: `PSN_LOG_MAX_SIZE_MB`
2. Set retention policy: `PSN_LOG_RETENTION_DAYS`
3. Archive old audit logs