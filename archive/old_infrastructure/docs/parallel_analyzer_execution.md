# Parallel Analyzer Execution

PaidSearchNav now supports parallel execution of independent analyzers during audit jobs, significantly improving performance for comprehensive audits.

## Overview

Previously, analyzers were executed sequentially, which could lead to long audit times when running multiple analyzers. With parallel execution, independent analyzers can now run concurrently, reducing total execution time.

## Configuration

### Environment Variable

You can configure the maximum number of analyzers to run in parallel using the `PSN_SCHEDULER_MAX_PARALLEL_ANALYZERS` environment variable:

```bash
# Set maximum to 5 parallel analyzers
export PSN_SCHEDULER_MAX_PARALLEL_ANALYZERS=5
```

### Default Settings

- **Default parallelism**: 3 analyzers
- **Minimum**: 1 (sequential execution)
- **Maximum**: 10 analyzers

## How It Works

1. **Task Preparation**: All requested analyzers are prepared as asynchronous tasks
2. **Semaphore Control**: A semaphore limits the number of concurrent executions based on the configured maximum
3. **Parallel Execution**: Analyzers run concurrently using `asyncio.gather()`
4. **Error Isolation**: Errors in one analyzer don't affect others
5. **Result Collection**: Results are collected as analyzers complete

## Performance Benefits

### Example Timing Improvements

For an audit running all 6 analyzers, each taking approximately 10 seconds:

- **Sequential execution**: ~60 seconds
- **Parallel (max=3)**: ~20 seconds  
- **Parallel (max=6)**: ~10 seconds

### Resource Usage

- **Memory**: Minimal increase as analyzers already existed in memory
- **CPU**: Better utilization of multi-core systems
- **API Calls**: No change in total API calls, but may hit rate limits faster

## Analyzer Independence

All PaidSearchNav analyzers are independent and can run in parallel:

- `keyword_match`: Keyword Match Type Analyzer
- `search_terms`: Search Terms Analyzer
- `negative_conflicts`: Negative Keyword Conflicts Analyzer
- `geo_performance`: Geo Performance Analyzer
- `pmax`: Performance Max Analyzer
- `shared_negatives`: Shared Negative Validator Analyzer

## Error Handling

Parallel execution maintains robust error handling:

- Errors in one analyzer don't cascade to others
- Each analyzer's error is captured independently
- The audit report includes all successful results and error details

## Best Practices

### Choosing Parallelism Level

1. **Small accounts** (< 10k keywords): 2-3 parallel analyzers
2. **Medium accounts** (10k-100k keywords): 3-5 parallel analyzers
3. **Large accounts** (> 100k keywords): Consider memory usage, may need lower parallelism

### API Rate Limiting

When increasing parallelism:

1. Monitor Google Ads API rate limit usage
2. Consider implementing additional rate limiting if needed
3. Use circuit breaker patterns for resilience

### Resource Monitoring

For production deployments:

1. Monitor memory usage during parallel execution
2. Track API quota consumption
3. Log analyzer execution times for optimization

## Implementation Details

### Code Structure

```python
# In scheduler/jobs.py
async def _run_analyzer(self, analyzer_name, ...):
    """Run a single analyzer with error handling."""
    try:
        result = await analyzer.analyze(...)
        await self.storage.save_analysis(result)
        return (analyzer_name, result, None)
    except Exception as e:
        return (analyzer_name, None, error_info)

# Parallel execution with semaphore
semaphore = asyncio.Semaphore(self.max_parallel_analyzers)

async def run_with_semaphore(task):
    async with semaphore:
        return await task

results = await asyncio.gather(
    *[run_with_semaphore(task) for task in tasks],
    return_exceptions=False
)
```

### Configuration Schema

```python
class SchedulerConfig(BaseModel):
    max_parallel_analyzers: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum number of analyzers to run in parallel"
    )
```

## Troubleshooting

### High Memory Usage

If experiencing high memory usage:

1. Reduce `PSN_SCHEDULER_MAX_PARALLEL_ANALYZERS`
2. Monitor individual analyzer memory consumption
3. Consider implementing memory limits per analyzer

### API Rate Limit Errors

If hitting API rate limits:

1. Reduce parallelism level
2. Implement exponential backoff
3. Use the circuit breaker configuration

### Slow Performance

If not seeing expected improvements:

1. Check that analyzers are CPU-bound vs I/O-bound
2. Monitor network latency to Google Ads API
3. Profile individual analyzer performance

## Future Enhancements

Potential improvements for parallel execution:

1. **Dynamic parallelism**: Adjust based on system resources
2. **Priority queues**: Run critical analyzers first
3. **Dependency management**: Handle analyzer dependencies
4. **Progress reporting**: Real-time progress via WebSocket
5. **Partial results**: Stream results as analyzers complete