# Bug Report: KeywordMatchAnalyzer Returns No Data

**Date Reported**: 2025-11-27
**Status**: RESOLVED
**Priority**: HIGH (was Medium - actual bug, not expected behavior)
**Component**: `skills/keyword_match_analyzer`
**Reporter**: Phase 2.5 Production Testing
**Resolved**: 2025-11-29
**Root Cause**: Data structure mismatch between server.py and analyzer

## Summary

The KeywordMatchAnalyzer skill completes successfully but returns 0 keywords when analyzing production Topgolf data (customer ID: 5777461198), despite the account being active with running campaigns.

## Test Details

### Test Configuration
- **Customer ID**: 5777461198 (Topgolf)
- **Date Range**: 2025-08-29 to 2025-11-27 (90 days)
- **Duration**: 27.24 seconds
- **Status**: Completed successfully (no errors)
- **Output Format**: Correct (11 lines of markdown)

### Expected Behavior
- Analyzer should return keyword data for accounts with active search campaigns
- Should show match type performance analysis
- Should provide actionable recommendations for keyword optimization

### Actual Behavior
- Analyzer completes without errors
- Returns "Total Keywords: 0"
- Empty performance tables
- No recommendations generated

### Output Sample
```markdown
# Analysis Report
**Period**: 2025-08-29 to 2025-11-27 | **Customer**: 5777461198

## Summary
- Total Keywords: 0
- Monthly Savings: $0

## Match Type Performance
| Type | Count | Cost | CPA | ROAS |
|------|-------|------|-----|------|

## TOP 10 Recommendations
| Keyword | Current | Cost | Action | Savings |
|---------|---------|------|--------|---------|

## Next Steps
```

## Root Cause Analysis

### Potential Causes (in order of likelihood)

1. **Overly Restrictive Filter** (Most Likely)
   - The analyzer filters for keywords with ≥100 impressions (line 11 of prompt.md)
   - Topgolf account may have keywords below this threshold
   - 90-day window may not capture sufficient impression volume

2. **No Keyword Data in Date Range**
   - Account may use primarily Performance Max or Display campaigns
   - Search campaigns may be paused during the test period
   - Keywords may exist but have no activity in the 90-day window

3. **GAQL Query Issue**
   - `get_keywords()` function may have incorrect WHERE clause
   - Date range filtering may be excluding all data
   - Campaign type filtering may be too restrictive

4. **Pagination Issue**
   - Using `limit=500` but may need pagination
   - Data exists beyond first page but not being retrieved

## Investigation Steps

### Step 1: Verify Account Has Keywords
```python
# Run basic keyword query without filters
keywords = await client.get_keywords(
    customer_id="5777461198",
    start_date=datetime(2025, 8, 29),
    end_date=datetime(2025, 11, 27),
    include_metrics=True
)
print(f"Total keywords (no filter): {len(keywords)}")
print(f"Sample keywords: {keywords[:5]}")
```

### Step 2: Check Impression Distribution
```python
# Analyze impression distribution to validate threshold
impression_counts = [kw.impressions for kw in keywords if kw.impressions > 0]
print(f"Keywords with impressions: {len(impression_counts)}")
print(f"Keywords with ≥100 impressions: {len([i for i in impression_counts if i >= 100])}")
print(f"Impression percentiles:")
print(f"  p50: {np.percentile(impression_counts, 50)}")
print(f"  p75: {np.percentile(impression_counts, 75)}")
print(f"  p90: {np.percentile(impression_counts, 90)}")
```

### Step 3: Test Different Date Ranges
```python
# Try shorter and longer date ranges
date_ranges = [
    (datetime(2025, 10, 28), datetime(2025, 11, 27)),  # 30 days
    (datetime(2025, 5, 29), datetime(2025, 11, 27)),   # 180 days
]

for start, end in date_ranges:
    keywords = await client.get_keywords(
        customer_id="5777461198",
        start_date=start,
        end_date=end,
        include_metrics=True
    )
    filtered = [kw for kw in keywords if kw.impressions >= 100]
    print(f"{start.date()} to {end.date()}: {len(filtered)} keywords ≥100 impressions")
```

### Step 4: Review GAQL Query
```python
# Inspect actual GAQL query being generated
# Add debug logging to client.py get_keywords() method
# Verify:
# - Date range format is correct
# - WHERE clause is properly formed
# - Campaign type filtering is appropriate
```

### Step 5: Test with Different Impression Thresholds
```python
# Test various thresholds to find optimal value
thresholds = [0, 10, 50, 100, 200, 500]
for threshold in thresholds:
    filtered = [kw for kw in keywords if kw.impressions >= threshold]
    total_cost = sum(kw.cost for kw in filtered)
    print(f"Threshold {threshold}: {len(filtered)} keywords, ${total_cost:.2f} cost")
```

## Proposed Solutions

### Solution 1: Make Impression Threshold Configurable
**Priority**: High
**Effort**: Low

Update `prompt.md` to accept a configurable threshold:
```markdown
1. **Fetch Data** (use limit=500, paginate if has_more=true):
   - `get_keywords(customer_id, start_date, end_date, limit=500)`
   - `get_search_terms(customer_id, start_date, end_date, limit=500)`
   - Filter: keep keywords with ≥{min_impressions} impressions (default: 50, configurable)
```

Rationale:
- Different account sizes need different thresholds
- 100 impressions may be too high for smaller accounts
- 50 impressions provides better balance

### Solution 2: Add Graceful Handling for No Data
**Priority**: Medium
**Effort**: Low

Update analyzer to detect and explain no-data scenarios:
```markdown
## Summary
- Total Keywords: 0
- **Note**: No keywords found with ≥100 impressions in the date range.
  Try: Reduce min_impressions threshold or extend date range.
```

### Solution 3: Implement Adaptive Filtering
**Priority**: Low
**Effort**: Medium

Auto-adjust threshold based on account activity:
1. First query without impression filter
2. Calculate p50 (median) impressions
3. Use max(10, p50 * 0.5) as threshold
4. Ensures meaningful data while adapting to account size

### Solution 4: Add Pagination Support
**Priority**: High
**Effort**: Low

Ensure full data retrieval:
```markdown
**Pagination**: Continue fetching with `offset` until `has_more=false`
```

## Success Criteria

### Acceptance Tests
1. **Test Case 1: Active Account Returns Data**
   - Given: Account with active search campaigns
   - When: Analyzer runs with default settings
   - Then: Returns >0 keywords with performance data

2. **Test Case 2: Low-Activity Account Handled Gracefully**
   - Given: Account with keywords but low impressions
   - When: Analyzer runs with min_impressions=100
   - Then: Returns helpful message suggesting threshold reduction

3. **Test Case 3: No Keywords Account**
   - Given: Account with no search campaigns
   - When: Analyzer runs
   - Then: Returns clear message explaining no keyword data available

4. **Test Case 4: Configurable Threshold Works**
   - Given: Account with 50 keywords between 50-99 impressions
   - When: Analyzer runs with min_impressions=50
   - Then: Returns those 50 keywords in analysis

### Performance Requirements
- Duration: <30 seconds (currently 27.24s - PASS)
- Output format: Valid markdown (currently passing)
- Error handling: No crashes (currently passing)

## Related Issues

- **Phase 2.5 Testing**: Production data validation
- **Issue #TBD**: Make analyzer thresholds configurable
- **Documentation**: Update skill examples with threshold guidance

## Testing Notes

### Manual Test Commands
```bash
# Test with Topgolf account
python -m pytest tests/bugs/test_keyword_match_no_data.py -v

# Test with debug logging
PYTHONPATH=. python -c "
import asyncio
from paidsearchnav_mcp.clients.google.client import GoogleAdsClient
from datetime import datetime

async def test():
    client = GoogleAdsClient()
    keywords = await client.get_keywords(
        customer_id='5777461198',
        start_date=datetime(2025, 8, 29),
        end_date=datetime(2025, 11, 27)
    )
    print(f'Total: {len(keywords)}')
    print(f'With ≥100 imp: {len([k for k in keywords if k.impressions >= 100])}')

asyncio.run(test())
"
```

### Additional Test Accounts Needed
- Small account (<1000 keywords)
- Medium account (1000-10000 keywords)
- Large account (>10000 keywords)
- Account with paused campaigns
- Account with only Performance Max (no search)

## Timeline

- **Investigation**: 2 hours
- **Fix Implementation**: 1-2 hours
- **Testing**: 1 hour
- **Total Estimate**: 4-5 hours

## Notes

This may not be a "bug" in the traditional sense - the analyzer may be functioning correctly by filtering out low-quality keywords. However, returning 0 results with no explanation is poor UX and should be improved.

The analyzer should either:
1. Return data by using appropriate thresholds for the account size, OR
2. Provide clear guidance on why no data was returned and how to adjust parameters

## Resolution Summary

**Date Resolved**: 2025-11-29
**Resolution Type**: Bug Fix (Critical Data Structure Mismatch)

### Actual Root Cause

The bug was NOT caused by the min_impressions threshold being too restrictive. The actual issue was a **data structure mismatch** between `server.py` and the analyzer:

1. **Server returns** (lines 645-665 in `server.py`):
   ```python
   {
       "keyword_id": ...,
       "impressions": kw.impressions,  # Top-level field
       "clicks": kw.clicks,
       "cost": kw.cost,
       ...
   }
   ```

2. **Analyzer expected** (original line 97):
   ```python
   k.get("metrics", {}).get("impressions", 0)  # Nested under "metrics"
   ```

This mismatch caused ALL keywords to be filtered out, regardless of threshold.

### Changes Implemented

**File**: `/Users/robertwelborn/PycharmProjects/PaidSearchNav-MCP/src/paidsearchnav_mcp/analyzers/keyword_match.py`

1. **Fixed data structure access** (lines 94-99, 273-282, 355-356, 400-403):
   - Changed from `k.get("metrics", {}).get("impressions", 0)` to `k.get("impressions", 0)`
   - Applied fix to all metric access points in the analyzer

2. **Improved default threshold** (line 29):
   - Changed default from `min_impressions=100` to `min_impressions=50`
   - Provides better balance between data quality and coverage

3. **Added graceful no-data handling** (lines 103-134):
   - Detects when no keywords meet threshold
   - Provides helpful error messages with suggested threshold adjustments
   - Differentiates between "no keywords at all" vs "all filtered out"

**File**: `/Users/robertwelborn/PycharmProjects/PaidSearchNav-MCP/src/paidsearchnav_mcp/server.py`

4. **Made threshold configurable** (lines 1348-1378):
   - Added `min_impressions` parameter to `analyze_keyword_match_types` tool
   - Defaults to 50, but users can override for their account size

### Test Results

**Before Fix** (min_impressions=1):
- Keywords fetched: 500
- Keywords analyzed: **0** (100% filtered out due to bug)

**After Fix**:
```
Threshold | Keywords Analyzed | Monthly Savings
----------|-------------------|----------------
    1     |        84         |    $20.80
   50     |        77         |    $20.80  ✅ NEW DEFAULT
  100     |        72         |    $20.80  (old default)
```

### Impact

- **Before**: Analyzer returned 0 keywords for Topgolf account (broken)
- **After**: Analyzer returns 77 keywords with threshold=50 (working)
- **Performance**: No degradation (same ~27 second execution time)
- **Data Quality**: Better coverage without sacrificing quality

### Lessons Learned

1. **Data contract mismatches are critical**: The server and analyzer must agree on data structure
2. **Test with real data**: Mock tests missed this because they mocked at wrong layer
3. **Debug logging is invaluable**: Detailed logs revealed the exact issue immediately
4. **Threshold alone wasn't the problem**: Even min_impressions=1 returned 0 keywords before fix

## Follow-Up Investigation (2025-11-30)

After the fix was deployed, a follow-up investigation was conducted to understand why the Topgolf account returns only 1 recommendation despite having 77 active keywords.

**Result**: NOT A BUG - Expected behavior for well-optimized accounts.

**Key Findings**:
- Topgolf account has only 0.2% broad match spend (industry average: 20-30%)
- Zero high-cost broad match keywords found (analyzer's primary optimization target)
- Only 1 keyword qualifies for exact match conversion with meaningful savings
- Account is exceptionally well-managed from a match type perspective

**Additional Improvements Made**:
1. Fixed implementation steps to handle 1-2 recommendations gracefully
2. Added positive messaging for well-optimized accounts
3. Updated acceptance criteria to include "well-optimized account" test case

**Full Investigation Report**: `/Users/robertwelborn/PycharmProjects/PaidSearchNav-MCP/docs/bugs/2025-11-30-keyword-match-investigation.md`

## References

- Skill Prompt: `/Users/robertwelborn/PycharmProjects/PaidSearchNav-MCP/skills/keyword_match_analyzer/prompt.md`
- Client Code: `/Users/robertwelborn/PycharmProjects/PaidSearchNav-MCP/src/paidsearchnav_mcp/clients/google/client.py`
- Google Ads API Docs: <https://developers.google.com/google-ads/api/docs/query/overview>
- Follow-Up Investigation: `/Users/robertwelborn/PycharmProjects/PaidSearchNav-MCP/docs/bugs/2025-11-30-keyword-match-investigation.md`
