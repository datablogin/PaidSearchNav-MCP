# Audit Scheduler Documentation

The PaidSearchNav scheduler provides automated and on-demand audit execution capabilities for quarterly Google Ads audits.

## Overview

The scheduler is built using APScheduler and provides:
- Automated quarterly audits
- On-demand audit triggers
- Job status tracking and history
- Retry logic with exponential backoff
- CLI and API interfaces

## Architecture

### Components

1. **AuditScheduler** (`scheduler.py`)
   - Core scheduler implementation using APScheduler
   - Manages job execution and lifecycle
   - Handles retry logic and error recovery

2. **Jobs** (`jobs.py`)
   - `AuditJob`: Runs full audits with multiple analyzers
   - `SingleAnalyzerJob`: Runs individual analyzers

3. **Storage** (`storage.py`)
   - Job history persistence using SQLAlchemy
   - Tracks execution status, results, and errors

4. **API** (`api.py`)
   - RESTful-style API for programmatic access
   - Trigger audits, manage schedules, query history

5. **CLI** (`cli.py`)
   - Command-line interface for scheduler operations

## Configuration

Add these settings to your `.env` file:

```bash
# Scheduler Configuration
PSN_SCHEDULER_ENABLED=true
PSN_SCHEDULER_DEFAULT_SCHEDULE="0 0 1 */3 *"  # Quarterly at midnight
PSN_SCHEDULER_TIMEZONE=UTC
PSN_SCHEDULER_MAX_CONCURRENT_AUDITS=5
PSN_SCHEDULER_RETRY_ATTEMPTS=3
PSN_SCHEDULER_JOB_STORE_URL=postgresql://user:pass@localhost/psn_jobs  # Optional
```

## CLI Usage

### Start the Scheduler Service

```bash
psn scheduler start
```

### Run an Immediate Audit

```bash
# Run full audit
psn scheduler run --customer-id 123456789

# Run specific analyzers
psn scheduler run --customer-id 123456789 \
  --analyzers keyword_match \
  --analyzers search_terms

# Specify date range
psn scheduler run --customer-id 123456789 \
  --start-date 2024-01-01 \
  --end-date 2024-03-31 \
  --report --report-format html --report-format pdf
```

### Schedule Recurring Audits

```bash
# Schedule quarterly audits
psn scheduler schedule --customer-id 123456789 \
  --schedule "0 0 1 */3 *" \
  --analyzers keyword_match search_terms negative_conflicts

# Disable scheduled audits
psn scheduler schedule --customer-id 123456789 \
  --schedule "0 0 1 */3 *" \
  --disable
```

### Check Job Status

```bash
# Get status of specific job
psn scheduler status job_123456

# View job history
psn scheduler history

# Filter history
psn scheduler history --customer-id 123456789 \
  --status completed \
  --page 1 --page-size 20
```

### Cancel a Job

```bash
psn scheduler cancel job_123456
```

## API Usage

### Python API

```python
from paidsearchnav.scheduler.api import SchedulerAPI, TriggerAuditRequest

# Initialize API
api = SchedulerAPI()

# Trigger immediate audit
request = TriggerAuditRequest(
    customer_id="123456789",
    analyzers=["keyword_match", "search_terms"],
    generate_report=True,
    report_formats=["html", "pdf"]
)

result = await api.trigger_audit(request)
print(f"Started audit: {result['execution_id']}")

# Check status
status = await api.get_job_status(result['job_id'])
print(f"Status: {status.status}")

# Get history
history = await api.get_job_history(
    customer_id="123456789",
    status="completed"
)
```

### REST API (Future Enhancement)

The scheduler API can be exposed via FastAPI or Flask for HTTP access.

## Job Types

### Quarterly Audit Job
- Runs all or specified analyzers
- Covers 90-day period by default
- Generates comprehensive reports
- Suitable for scheduled execution

### On-Demand Audit Job
- Custom date ranges
- Selective analyzer execution
- Immediate execution
- Suitable for ad-hoc analysis

### Single Analyzer Job
- Runs one specific analyzer
- Lightweight execution
- Useful for targeted analysis

## Retry Logic

The scheduler implements exponential backoff for failed jobs:

- **Initial delay**: 1 second
- **Max delay**: 5 minutes
- **Exponential base**: 2
- **Max attempts**: 3 (configurable)
- **Jitter**: Added to prevent thundering herd

Retryable errors include:
- Network/connection errors
- Rate limit errors (429)
- Temporary API unavailability
- Quota exceeded errors

## Job Storage

Job execution history is stored in the database with:
- Job identification (ID, type)
- Execution timestamps
- Status tracking
- Result data (JSON)
- Error messages
- Retry counts

## Monitoring

### Logging
All scheduler operations are logged:
- Job scheduling/cancellation
- Execution start/completion
- Retry attempts
- Errors and failures

### Metrics (Future Enhancement)
- Job success/failure rates
- Execution duration
- Retry statistics
- Queue depth

## Error Handling

1. **Job Failures**
   - Logged with full error details
   - Stored in job history
   - Retried based on error type

2. **Scheduler Failures**
   - Graceful shutdown on errors
   - State preservation in job store
   - Recovery on restart

3. **Resource Limits**
   - Concurrent job limits
   - Memory management
   - API rate limiting

## Best Practices

1. **Scheduling**
   - Use UTC for all schedules
   - Avoid scheduling during peak hours
   - Stagger jobs for multiple customers

2. **Resource Management**
   - Monitor concurrent job count
   - Set appropriate retry limits
   - Use job store for persistence

3. **Error Recovery**
   - Check job history for failures
   - Manually retry failed jobs
   - Monitor retry patterns

## Troubleshooting

### Common Issues

1. **Jobs not running**
   - Check scheduler is started
   - Verify cron expression
   - Check timezone settings

2. **Jobs failing**
   - Review error in job history
   - Check API credentials
   - Verify analyzer configuration

3. **Performance issues**
   - Reduce concurrent job limit
   - Check database performance
   - Monitor API rate limits

### Debug Commands

```bash
# Check scheduler logs
tail -f logs/paidsearchnav.log | grep scheduler

# Verify job in APScheduler
psn scheduler list-jobs  # Future enhancement

# Test analyzer directly
psn analyze --customer-id 123456789 --analyzer keyword_match
```

## Migration Guide

### Adding the Scheduler to Existing Installation

1. Update dependencies:
   ```bash
   uv pip install -e ".[dev,test]"
   ```

2. Run database migration:
   ```bash
   alembic upgrade head
   ```

3. Configure environment variables

4. Start scheduler service

## Future Enhancements

1. **Web Dashboard**
   - Visual job management
   - Real-time status updates
   - Historical analytics

2. **Distributed Execution**
   - Multiple worker support
   - Queue-based job distribution
   - Horizontal scaling

3. **Advanced Scheduling**
   - Dependency management
   - Conditional execution
   - Dynamic scheduling

4. **Integrations**
   - Webhook notifications
   - Slack/email alerts
   - External job triggers