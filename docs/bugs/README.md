# Bug Reports - Phase 2.5 Production Testing

This directory contains comprehensive bug reports for issues discovered during Phase 2.5 production testing with Topgolf data (customer ID: 5777461198).

## Testing Summary

**Date**: 2025-11-27
**Test Environment**: Production Topgolf account
**Date Range**: 2025-08-29 to 2025-11-27 (90 days)
**Analyzers Tested**: 5
**Results**: 2 passed ✅, 3 failed ❌

### Passing Analyzers
- **SearchTermAnalyzer**: ~25s, correct output ✅
- **NegativeConflictAnalyzer**: ~22s, correct output ✅

### Failing Analyzers
1. **KeywordMatchAnalyzer**: Returns 0 keywords (no error)
2. **GeoPerformanceAnalyzer**: GAQL syntax error
3. **PMaxCannibalizationAnalyzer**: 96.49s (3x target)

## Bug Reports

### 1. KeywordMatchAnalyzer Returns No Data
**File**: `2025-11-27-keyword-match-no-data.md`
**Status**: Open
**Priority**: Medium
**Component**: `skills/keyword_match_analyzer`

**Summary**: Analyzer completes successfully but returns 0 keywords, likely due to overly restrictive filter (min_impressions=100) or no keyword data in the 90-day window.

**Key Findings**:
- Duration: 27.24s ✅ (within target)
- Output format: Correct ✅
- Data quality: 0 keywords ❌
- Root cause: Likely filter too restrictive for account size

**Proposed Solutions**:
1. Make impression threshold configurable (default: 50 instead of 100)
2. Add graceful handling with helpful error messages
3. Implement adaptive threshold based on account size

**Test File**: `/Users/robertwelborn/PycharmProjects/PaidSearchNav-MCP/tests/bugs/test_keyword_match_no_data.py`

**Estimated Effort**: 4-5 hours

---

### 2. GeoPerformanceAnalyzer GAQL Query Error
**File**: `2025-11-27-geo-performance-gaql-error.md`
**Status**: Open
**Priority**: High
**Component**: `src/paidsearchnav_mcp/clients/google/client.py:2207-2265`

**Summary**: Google Ads API rejects query with "unexpected input OR" error. The `_get_location_names()` function uses unsupported OR operator in GAQL WHERE clause.

**Key Findings**:
- Duration before failure: 5.10s
- Error: `query_error: UNEXPECTED_INPUT: Error in query: unexpected input OR`
- Location: `client.py:2247` in `_get_location_names()`
- Root cause: GAQL does not support OR operator in WHERE clauses

**Current (Buggy) Code**:
```python
criterion_filter = " OR ".join(
    [f"geo_target_constant.id = {cid}" for cid in criterion_ids]
)
query = f"... WHERE {criterion_filter}"
# Generates: WHERE id = 1 OR id = 2 OR id = 3  ← INVALID GAQL
```

**Proposed Fix**:
```python
criterion_ids_str = ", ".join(criterion_ids)
query = f"... WHERE geo_target_constant.id IN ({criterion_ids_str})"
# Generates: WHERE id IN (1, 2, 3)  ← VALID GAQL
```

**Test File**: `/Users/robertwelborn/PycharmProjects/PaidSearchNav-MCP/tests/bugs/test_geo_performance_gaql.py`

**Estimated Effort**: 3 hours

**Impact**: CRITICAL - Completely blocks GeoPerformanceAnalyzer

---

### 3. PMaxCannibalizationAnalyzer Performance Issue
**File**: `2025-11-27-pmax-analyzer-slow.md`
**Status**: Open
**Priority**: Medium
**Component**: `skills/pmax_analyzer`

**Summary**: Analyzer completes successfully but takes 96.49 seconds, which is 3.2x the 30-second target. Output is correct but duration is unacceptable for production.

**Key Findings**:
- Duration: 96.49s ❌ (target: <30s)
- Output format: Correct ✅
- Data accuracy: Correct ✅
- Root cause: Sequential API calls + excessive data retrieval

**Performance Analysis**:
```
Current (Sequential):
  get_campaigns():           2s
  get_search_terms(PMax):   40s  ┐
  get_search_terms(Search): 40s  ├─ Sequential = 80s
  cross_analysis():          2s  ┘
  format_output():           1s
  Total:                    ~96s

Target (Parallel + Optimized):
  get_campaigns():           2s
  get_search_terms(PMax):   15s  ┐
  get_search_terms(Search): 15s  ├─ Parallel = max(15s, 15s) = 15s
  cross_analysis():          2s  ┘
  format_output():           1s
  Total:                    ~25s  ✅
```

**Proposed Optimizations**:
1. **Parallelize API calls** (HIGH PRIORITY): Use `asyncio.gather()` for PMax and Search term fetching
   - Expected improvement: 50% reduction (96s → 48s)

2. **Add data filters** (MEDIUM PRIORITY): Filter for cost ≥ $1 OR impressions ≥ 50
   - Expected improvement: 30% reduction in data volume

3. **Increase page size** (MEDIUM PRIORITY): Change limit from 500 to 2000
   - Expected improvement: 75% fewer API calls

4. **Optimize date range** (LOW PRIORITY): Use 60 days instead of 90
   - Expected improvement: 33% less data

**Combined Expected Result**: 96s → 25-30s (70% improvement)

**Test File**: `/Users/robertwelborn/PycharmProjects/PaidSearchNav-MCP/tests/bugs/test_pmax_performance.py`

**Estimated Effort**: 7-10 hours

---

## Test Suite Organization

All bug tests are located in `/Users/robertwelborn/PycharmProjects/PaidSearchNav-MCP/tests/bugs/`

### Test Structure

Each test file contains:
1. **Bug Reproduction Tests**: Demonstrate the bug in isolation
2. **Fix Validation Tests**: Verify the fix works correctly
3. **Edge Case Tests**: Handle boundary conditions
4. **Regression Tests**: Ensure fixes don't break existing functionality
5. **Integration Tests**: Validate against real API (skipped in CI)
6. **Performance Tests**: Benchmark execution time

### Running Tests

```bash
# Run all bug tests
pytest tests/bugs/ -v

# Run specific bug test
pytest tests/bugs/test_keyword_match_no_data.py -v
pytest tests/bugs/test_geo_performance_gaql.py -v
pytest tests/bugs/test_pmax_performance.py -v

# Run only bug reproduction tests
pytest tests/bugs/ -v -k "bug_reproduction"

# Run only fix validation tests
pytest tests/bugs/ -v -k "fix_"

# Run integration tests (requires Google Ads API credentials)
pytest tests/bugs/ -v -m "not skip"

# Run performance benchmarks
pytest tests/bugs/test_pmax_performance.py -v -k "performance"
```

### Test Coverage

| Bug | Reproduction Tests | Fix Tests | Edge Cases | Integration | Performance |
|-----|-------------------|-----------|------------|-------------|-------------|
| Keyword Match No Data | 2 | 4 | 2 | 1 | 1 |
| Geo Performance GAQL | 3 | 6 | 3 | 1 | 1 |
| PMax Performance | 2 | 4 | 0 | 1 | 3 |
| **Total** | **7** | **14** | **5** | **3** | **5** |

---

## Bug Priority Matrix

| Priority | Bug | Impact | Effort | Status |
|----------|-----|--------|--------|--------|
| **HIGH** | Geo Performance GAQL | Blocks analyzer | 3h | Open |
| **MEDIUM** | PMax Performance | Poor UX | 7-10h | Open |
| **MEDIUM** | Keyword Match No Data | Confusing results | 4-5h | Open |

### Recommended Fix Order

1. **GeoPerformanceAnalyzer GAQL Error** (HIGH)
   - Critical blocker
   - Quick fix (3 hours)
   - Simple code change (OR → IN)

2. **KeywordMatchAnalyzer No Data** (MEDIUM)
   - Affects data quality
   - Medium effort (4-5 hours)
   - Requires threshold tuning

3. **PMaxCannibalizationAnalyzer Performance** (MEDIUM)
   - Affects UX but functional
   - Higher effort (7-10 hours)
   - Multiple optimizations needed

---

## Success Criteria

### GeoPerformanceAnalyzer
- [ ] Query uses IN operator instead of OR
- [ ] No GAQL syntax errors
- [ ] Returns valid location data
- [ ] All unit tests pass
- [ ] Integration test with Topgolf account passes

### KeywordMatchAnalyzer
- [ ] Returns >0 keywords for accounts with active keywords
- [ ] Configurable min_impressions threshold (default: 50)
- [ ] Graceful handling when no data found
- [ ] Helpful error messages with suggested actions
- [ ] All unit tests pass
- [ ] Integration test with Topgolf account passes

### PMaxCannibalizationAnalyzer
- [ ] Completes in <30s for typical accounts
- [ ] Completes in <60s for large accounts
- [ ] No accuracy regression (same cannibalization detection)
- [ ] Parallel API fetching implemented
- [ ] Data filters applied
- [ ] All unit tests pass
- [ ] Performance benchmarks pass
- [ ] Integration test with Topgolf account passes

---

## Related Documentation

- **Phase 2.5 Testing**: `thoughts/shared/handoffs/general/2025-11-25_phase-4-context-window-discovery.md`
- **Skill Documentation**: `docs/SKILL_CATALOG.md`
- **Testing Guide**: `docs/SKILL_TESTING_GUIDE.md`
- **Client Code**: `src/paidsearchnav_mcp/clients/google/client.py`

---

## Contributing

When fixing these bugs:

1. **Read the bug report** thoroughly
2. **Run the reproduction tests** to understand the issue
3. **Implement the fix** according to proposed solution
4. **Validate with fix tests** to ensure it works
5. **Run all tests** to prevent regression
6. **Update documentation** as needed
7. **Create PR** with reference to bug report

### PR Template for Bug Fixes

```markdown
## Bug Fix: [Bug Name]

**Bug Report**: docs/bugs/2025-11-27-[bug-name].md

### Changes
- [List of changes made]

### Testing
- [ ] Bug reproduction tests pass (demonstrate bug is fixed)
- [ ] Fix validation tests pass
- [ ] Edge case tests pass
- [ ] No regression in existing tests
- [ ] Integration test with real API passes (if applicable)

### Performance Impact (if applicable)
- Before: [duration]
- After: [duration]
- Improvement: [percentage]

### Related Issues
Closes #[issue number]
```

---

## Notes

- All bugs discovered during production testing with real customer data
- Test customer: Topgolf (5777461198)
- Date range: 90 days (2025-08-29 to 2025-11-27)
- All test files include both unit and integration tests
- Integration tests require Google Ads API credentials (skipped in CI)
- Performance tests use scaled-down timing (1ms = 1s in production)

For questions or clarifications, refer to the individual bug reports.
