# Bug Report: GeoPerformanceAnalyzer KeyError 'revenue_micros'

**Date**: 2025-11-30
**Issue**: #20
**Severity**: HIGH
**Status**: FIXED
**Affected Component**: GeoPerformanceAnalyzer

## Summary

The GeoPerformanceAnalyzer crashed with a `KeyError: 'revenue_micros'` when attempting to calculate ROAS (Return on Ad Spend) metrics. The analyzer was using an incorrect field name that doesn't exist in the Google Ads API response.

## Error Details

### Error Message
```
KeyError: 'revenue_micros'
```

### Stack Trace
```python
File "src/paidsearchnav_mcp/analyzers/geo_performance.py", line 101
    avg_roas = statistics.mean(
        loc["revenue_micros"] / 1_000_000 / (loc["cost_micros"] / 1_000_000)
        ~~~^^^^^^^^^^^^^^^^^^
KeyError: 'revenue_micros'
```

### Affected Lines
- Line 101: ROAS calculation in average metrics
- Line 116: Revenue extraction in recommendation loop

## Root Cause Analysis

### Investigation Process

1. **Examined server.py** (`get_geo_performance` function)
   - Server calls `client.get_geographic_performance()`
   - Returns data from client without modification

2. **Examined client.py** (`get_geographic_performance` method)
   - Lines 1493-1503: Google Ads API query
   - Line 1503: Query uses `metrics.conversions_value` (API field name)
   - Line 1581: Client maps to `conversion_value_micros` (response field name)

3. **Identified the mismatch**
   - Analyzer expected: `revenue_micros` ❌
   - Client provides: `conversion_value_micros` ✅

### Google Ads API Field Mapping

**API Query Field** → **Client Response Field**
```python
# In client.py line 1503:
query = """
    SELECT
        metrics.conversions_value  # Google Ads API field name
    FROM geographic_view
"""

# In client.py line 1581:
"conversion_value_micros": conversions_value,  # Response field name
```

### Available Fields in Response

The `get_geographic_performance` response includes:
- `campaign_id`
- `campaign_name`
- `location_name`
- `location_type`
- `criterion_id`
- `impressions`
- `clicks`
- `conversions`
- `cost_micros`
- `conversion_value_micros` ✅ (correct field)
- `country_name`
- `region_name`
- `city_name`

## Solution

### Code Changes

**File**: `src/paidsearchnav_mcp/analyzers/geo_performance.py`

#### Change 1: Line 101 (ROAS Calculation)

**Before:**
```python
avg_roas = statistics.mean(
    loc["revenue_micros"] / 1_000_000 / (loc["cost_micros"] / 1_000_000)
    for loc in locations_with_conversions
    if loc.get("cost_micros", 0) > 0
)
```

**After:**
```python
avg_roas = statistics.mean(
    loc.get("conversion_value_micros", 0) / 1_000_000 / (loc["cost_micros"] / 1_000_000)
    for loc in locations_with_conversions
    if loc.get("cost_micros", 0) > 0 and loc.get("conversion_value_micros", 0) > 0
)
```

**Changes:**
1. Replaced `loc["revenue_micros"]` with `loc.get("conversion_value_micros", 0)` (correct field name)
2. Used `.get()` instead of direct access for safety
3. Added check: `loc.get("conversion_value_micros", 0) > 0` to prevent ROAS calculation with zero conversion value

#### Change 2: Line 116 (Revenue Extraction)

**Before:**
```python
revenue = loc.get("revenue_micros", 0) / 1_000_000
```

**After:**
```python
revenue = loc.get("conversion_value_micros", 0) / 1_000_000
```

**Changes:**
1. Replaced `"revenue_micros"` with `"conversion_value_micros"` (correct field name)

## Testing

### Test Command
```bash
source .venv/bin/activate
python scripts/test_orchestration_direct.py
```

### Test Results

**Before Fix:**
```
❌ FAILED - KeyError: 'revenue_micros'
```

**After Fix:**
```
✅ SUCCESS - GeoPerformanceAnalyzer
   Duration: 4.88 seconds
   Records analyzed: 14
   Estimated savings: $12,878.20
   Top recommendations: 10
   Implementation steps: 4

   Validation Checks:
   ✅ Duration < 30s: 4.88s
   ✅ Formatted output < 100 lines: 34 lines
   ✅ Has recommendations: 10 recommendations
   ✅ ≤10 recommendations: 10 recommendations
   ✅ Has implementation steps: 4 steps
```

### Test Configuration
- Customer ID: 5777461198 (Topgolf)
- Date Range: 2025-09-01 to 2025-11-30
- Geographic Level: CITY

## Impact Assessment

### Before Fix
- **Functionality**: BROKEN - GeoPerformanceAnalyzer crashed on every execution
- **User Impact**: HIGH - Geographic performance analysis completely unavailable
- **Data Loss**: None (read-only operation)
- **Error Rate**: 100% failure rate

### After Fix
- **Functionality**: WORKING - Analyzer completes successfully
- **User Impact**: RESOLVED - Full geographic performance analysis available
- **Performance**: 4.88 seconds (within 30s target)
- **Output Quality**: Valid recommendations with proper ROAS calculations

### Business Impact
- **Blocked Workflow**: Quarterly geo performance audits were impossible
- **Recovery**: Immediate - fix enables geo bid adjustment recommendations
- **Savings Potential**: $12,878.20/month identified in test run

## Prevention

### Why This Happened
1. **Field Name Inconsistency**: Different naming conventions between API, client, and analyzer
2. **No Type Checking**: Python's dynamic typing allowed incorrect field access
3. **Missing Integration Tests**: No test validating field names match between components

### Preventive Measures
1. **Documentation**: Document field mappings in client.py
2. **Validation**: Add field validation in analyzers
3. **Testing**: Add integration tests that validate field names
4. **Constants**: Consider using typed dataclasses for API responses

### Related Issues
- Similar issues could exist in other analyzers
- Recommend audit of all analyzer field access patterns

## Lessons Learned

1. **Always validate field names** when accessing nested dictionaries
2. **Use `.get()` with defaults** instead of direct dictionary access
3. **Check client implementation** to understand actual field names
4. **Integration tests are critical** for catching field name mismatches

## References

- **GitHub Issue**: [#20](https://github.com/datablogin/PaidSearchNav-MCP/issues/20)
- **Fixed Files**:
  - `src/paidsearchnav_mcp/analyzers/geo_performance.py` (lines 101, 116)
- **Reference Files**:
  - `src/paidsearchnav_mcp/clients/google/client.py` (lines 1503, 1581)
  - `src/paidsearchnav_mcp/server.py` (get_geo_performance function)

## Timeline

- **2025-11-30 16:00**: Bug discovered during testing
- **2025-11-30 16:15**: Investigation completed, root cause identified
- **2025-11-30 16:30**: Fix implemented and tested
- **2025-11-30 16:45**: GitHub issue #20 created
- **2025-11-30 17:00**: Documentation completed
