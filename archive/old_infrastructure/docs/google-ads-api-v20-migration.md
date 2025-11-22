# Google Ads API v20 Migration Guide

## Overview

This document outlines the migration from previous Google Ads API versions to v20, including field changes, compatibility issues, and implementation timeline.

## Migration Status

### ✅ Completed (as of 2025-06-29)

1. **Campaign Queries (Issue #131)**
   - Verified all campaign fields are v20 compatible
   - Confirmed proper handling of bidding_strategy_type (read-only)
   - Validated metrics and conversion value handling

2. **Keyword Metrics Compatibility (Issue #127)**
   - Removed incompatible metrics from `ad_group_criterion` query
   - Implemented separate `keyword_view` metrics fetching
   - Added `include_metrics` parameter to `get_keywords()` method
   - Metrics are now fetched in a second API call when requested

3. **Negative Keywords Compatibility (Issue #131)**
   - Verified ad group and campaign level negative keyword queries
   - Confirmed all fields are v20 compatible
   - Validated proper handling of keyword properties

4. **Geographic View Field Updates (Issue #129)**
   - Updated field names to v20 schema
   - Implemented location name resolution via `geo_target_constant`
   - Added null safety for optional fields
   - Fixed conversion value handling (no multiplication needed)

5. **Distance Performance Updates**
   - Fixed `conversion_value_micros` field name
   - Added null safety checks
   - Corrected value handling (no multiplication)

6. **Performance Max Implementation (Issue #131)**
   - Added `get_performance_max_data()` method with v20-compatible fields
   - Added `get_performance_max_search_terms()` using campaign_search_term_insight
   - Implemented proper null safety and metric calculations
   - Added support for PMax-specific segments and fields

7. **General Improvements**
   - Added comprehensive null safety throughout
   - Implemented graceful degradation for failed API calls
   - Added proper error logging

### ✅ Completed (as of 2025-06-29) - Issue #128

8. **Shared Negative Keyword Sets Implementation**
   - Added support for fetching shared negative keyword sets
   - Implemented `shared_criterion` and `campaign_shared_set` queries
   - Added proper association between shared sets and campaigns
   - Handles failures gracefully with warning logs

### 🚧 Pending Tasks

1. **Caching Implementation** (Low Priority)
   - Add caching for `geo_target_constant` lookups
   - Consider Redis or in-memory cache for location names

## Breaking Changes

### Field Name Changes

| Resource | Old Field | New Field | Notes |
|----------|-----------|-----------|-------|
| geographic_view | country_name | N/A | Must fetch via geo_target_constant |
| geographic_view | region_name | N/A | Must fetch via geo_target_constant |
| geographic_view | city_name | N/A | Must fetch via geo_target_constant |
| geographic_view | metro_name | N/A | Must fetch via geo_target_constant |
| geographic_view | postal_code | N/A | Must fetch via geo_target_constant |
| metrics | conversion_value_micros | conversions_value | Already in micros, no multiplication |

### Query Structure Changes

1. **Keyword Metrics**: Cannot select metrics directly from `ad_group_criterion`
   - Must use `keyword_view` with date segmentation
   - Requires separate API call

2. **Geographic Data**: Location names not directly available
   - Must extract criterion_id from resource_name
   - Requires secondary lookup to `geo_target_constant`

## Implementation Timeline

### Phase 1: Critical Fixes (Completed)
- **Week 1** (2025-06-29): Fixed all critical API compatibility issues
  - Keyword metrics fetching
  - Geographic field updates
  - Conversion value handling

### Phase 2: Testing & Validation (In Progress)
- **Week 2** (2025-07-06): Integration testing with real API
  - Validate all queries against production API
  - Performance testing with large datasets
  - Edge case handling

### Phase 3: Optimization (Planned)
- **Week 3** (2025-07-13): Performance improvements
  - Implement caching for location lookups
  - Optimize batch API calls
  - Add connection pooling

### Phase 4: Documentation (Planned)
- **Week 4** (2025-07-20): Complete documentation
  - Update all API documentation
  - Create migration guide for users
  - Add troubleshooting guide

## Code Examples

### Fetching Keywords with Metrics

```python
# Old approach (broken in v20)
keywords = await client.get_keywords(customer_id="123")

# New approach
keywords = await client.get_keywords(
    customer_id="123",
    include_metrics=True,  # Triggers separate metrics fetch
    start_date=datetime.now() - timedelta(days=30),
    end_date=datetime.now() - timedelta(days=1)
)
```

### Geographic Performance with Location Names

```python
# Automatically resolves location names
geo_data = await client.get_geographic_performance(
    customer_id="123",
    start_date=start_date,
    end_date=end_date
)

# Each record now includes:
# - city_name, region_name, country_name (resolved)
# - location_type, country_criterion_id (from API)
```

### Performance Max Campaign Data

```python
# Fetch Performance Max campaign metrics
pmax_data = await client.get_performance_max_data(
    customer_id="123",
    start_date=start_date,
    end_date=end_date
)

# Each record includes:
# - Campaign details and status
# - Performance metrics (impressions, clicks, conversions)
# - Video views and interactions
# - Asset group performance segments
```

### Performance Max Search Terms

```python
# Fetch Performance Max search terms with insights
pmax_search_terms = await client.get_performance_max_search_terms(
    customer_id="123",
    start_date=start_date,
    end_date=end_date,
    campaign_ids=["456", "789"]  # Optional: filter by campaigns
)

# Each record includes:
# - Search term and category label
# - Performance metrics (CTR, CPC, CPA)
# - Conversion data
```

### Shared Negative Keyword Sets

```python
# Fetch negative keywords including shared sets
negative_keywords = await client.get_negative_keywords(
    customer_id="123",
    include_shared_sets=True  # NEW: Fetches shared negative keyword sets
)

# Results now include:
# - Campaign level negatives
# - Ad group level negatives
# - Shared set negatives with campaign associations
for negative in negative_keywords:
    if negative["level"] == "shared_set":
        print(f"Shared set: {negative['shared_set_name']}")
        print(f"Applied to: {negative['campaign_name']}")
```

## Testing Checklist

- [x] Unit tests for conversion value handling
- [x] Unit tests for null safety
- [x] Integration tests for keyword metrics
- [x] Integration tests for geographic data
- [x] Integration tests for shared negative keyword sets
- [x] Comprehensive v20 compatibility test suite
- [ ] Load testing with large accounts
- [ ] Real API validation tests

## Known Issues

1. **Keyword Metrics Performance**: Fetching metrics requires a second API call, which may impact performance for large keyword sets.
   - **Mitigation**: Consider batch processing or pagination

2. **Location Resolution Overhead**: Each geographic query may require additional API calls for location names.
   - **Mitigation**: Implement caching for frequently accessed locations

3. **Date Range Requirements**: Keyword metrics now require date ranges, which may not align with all use cases.
   - **Mitigation**: Use sensible defaults (last 30 days)

## Support

For issues related to the v20 migration:
1. Check error messages for field-specific issues
2. Verify API version in error responses
3. Consult Google Ads API v20 documentation
4. File issues with specific error messages and queries