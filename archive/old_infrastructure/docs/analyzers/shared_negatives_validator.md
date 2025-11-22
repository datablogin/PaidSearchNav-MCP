# Shared Negative Validator Analyzer

The Shared Negative Validator Analyzer validates that campaigns are using shared negative keyword lists consistently and identifies potential conflicts with campaign goals.

## Overview

This analyzer helps ensure that:
- Campaigns have appropriate shared negative lists applied
- There are no conflicts between shared negatives and active keywords
- Shared negative list coverage is consistent across the account

## Performance Optimizations (Issue #70)

As of the latest update, the SharedNegativeValidator includes significant performance optimizations:

### 1. Batch API Calls

Previously, API calls to fetch shared set negatives were made sequentially. Now they execute in parallel using `asyncio.gather()`:

```python
# Old approach (sequential)
for shared_list in shared_lists:
    negatives = await self.data_provider.get_shared_set_negatives(customer_id, shared_list["id"])

# New approach (parallel)
negative_tasks = [
    self.data_provider.get_shared_set_negatives(customer_id, shared_list["id"])
    for shared_list in shared_lists
]
all_negatives_results = await asyncio.gather(*negative_tasks)
```

**Performance Impact**: For accounts with 10 shared lists, this reduces API call time from ~10 seconds to ~1 second (10x improvement).

### 2. Pagination Support

Large campaigns with thousands of keywords now use pagination to avoid memory issues and API timeouts:

```python
keywords = await self.data_provider.get_keywords(
    customer_id, 
    campaigns=[campaign.campaign_id],
    page_size=self.keywords_page_size  # Default: 1000
)
```

**Benefits**:
- Handles campaigns with 100k+ keywords efficiently
- Reduces memory usage for large datasets
- Avoids API timeout errors

### 3. Configurable Conflicts Limit

The number of conflicts reported per campaign is now configurable to prevent overwhelming reports:

```python
analyzer = SharedNegativeValidatorAnalyzer(
    data_provider,
    max_conflicts_per_campaign=10  # Default: 10
)
```

**Benefits**:
- Keeps reports focused on most important conflicts
- Improves report generation performance
- Reduces memory usage for conflict storage

## Configuration

### Initialization Parameters

```python
SharedNegativeValidatorAnalyzer(
    data_provider: DataProvider,
    min_impressions: int = 1000,           # Minimum impressions for relevance
    conflict_threshold: float = 0.1,       # Percentage threshold for conflicts
    max_conflicts_per_campaign: int = 10,  # Max conflicts to show per campaign
    keywords_page_size: int = 1000,        # Page size for keyword fetching
)
```

### Performance Tuning

For optimal performance based on account size:

| Account Size | Keywords Page Size | Max Conflicts | Expected Performance |
|--------------|-------------------|---------------|---------------------|
| Small (<10k keywords) | 5000 | 20 | <5 seconds |
| Medium (10k-100k) | 1000 | 10 | <30 seconds |
| Large (>100k) | 500 | 5 | <60 seconds |

## Analysis Process

1. **Campaign Filtering**: Identifies relevant campaigns based on:
   - Active status (ENABLED or PAUSED)
   - Minimum impressions threshold
   - Campaign type (Search, Shopping, PMax, Local)

2. **Shared List Mapping**: Maps each campaign to its applied shared negative lists

3. **Missing List Detection**: Identifies campaigns missing expected shared lists based on:
   - Campaign type
   - List naming conventions
   - Business rules

4. **Conflict Detection** (if enabled):
   - Fetches campaign keywords with pagination
   - Compares against all shared negatives in parallel
   - Identifies blocking conflicts

5. **Coverage Calculation**: Calculates shared list usage statistics

## Output

The analyzer returns an `AnalysisResult` with:

### Metrics
- Total campaigns analyzed
- Campaigns missing shared lists
- Campaigns with conflicts
- Shared list coverage percentage
- Potential cost savings estimate

### Recommendations
- Apply missing shared lists (HIGH priority for high-spend campaigns)
- Resolve negative keyword conflicts (HIGH priority)
- Improve overall coverage (MEDIUM priority)

### Raw Data
```json
{
  "validation_status": "NEEDS_ATTENTION",
  "campaigns_analyzed": 45,
  "shared_lists_found": 5,
  "missing_list_campaigns": [
    {
      "campaign_id": "12345",
      "campaign_name": "Brand - Search",
      "missing_lists": ["Competitors", "General Negatives"],
      "priority": "high",
      "estimated_impact": {
        "wasted_spend_risk": 500.00,
        "impressions_at_risk": 10000
      }
    }
  ],
  "conflict_campaigns": [
    {
      "campaign_id": "67890",
      "campaign_name": "Products - Shopping",
      "total_conflicts": 25,
      "conflicts": [  // Limited by max_conflicts_per_campaign
        {
          "keyword": "blue shoes",
          "negative": "blue",
          "impressions_blocked": 1500
        }
      ]
    }
  ]
}
```

## Best Practices

1. **Run Regularly**: Execute monthly to catch new campaigns missing shared lists
2. **Prioritize High-Spend**: Focus on campaigns with significant spend first
3. **Review Conflicts**: Manually review conflicts before removing negatives
4. **Standardize Naming**: Use consistent shared list naming conventions

## Integration with Other Analyzers

The Shared Negative Validator works well in combination with:
- **Negative Conflicts Analyzer**: For campaign-level negative analysis
- **Search Terms Analyzer**: To identify terms that should be added to shared lists
- **Keyword Match Type Analyzer**: To ensure proper match type usage with negatives

## Troubleshooting

### Slow Performance

If the analyzer is running slowly:
1. Reduce `keywords_page_size` for large campaigns
2. Disable conflict checking with `check_conflicts=False`
3. Increase `min_impressions` threshold to analyze fewer campaigns

### Memory Issues

For accounts with many keywords:
1. Reduce `max_conflicts_per_campaign` to store fewer conflicts
2. Use smaller `keywords_page_size` values
3. Process campaigns in batches

### API Rate Limits

If hitting Google Ads API rate limits:
1. The parallel execution respects rate limits automatically
2. Consider reducing the number of concurrent audits
3. Use circuit breaker configuration in settings