# Bug Report: GeoPerformanceAnalyzer GAQL Query Error

**Date Reported**: 2025-11-27
**Date Fixed**: 2025-11-29
**Status**: ✅ FIXED
**Priority**: High
**Component**: `src/paidsearchnav_mcp/clients/google/client.py`
**Reporter**: Phase 2.5 Production Testing
**GitHub Issue**: #18
**Fix Commit**: [To be added during PR]

## Summary

The GeoPerformanceAnalyzer fails with a GAQL syntax error when executing the `_get_location_names()` function. The Google Ads API returns "unexpected input OR" error, indicating malformed query syntax in the WHERE clause.

## Fix Summary

**Fix Applied**: 2025-11-29

### Changes Made

1. **Query Syntax Fix** (Primary Fix)
   - Replaced OR chain with IN operator for GAQL compliance
   - Changed: `WHERE id = 1 OR id = 2 OR id = 3`
   - To: `WHERE id IN (1, 2, 3)`

2. **Input Validation** (Security Enhancement)
   - Added numeric validation for criterion IDs to prevent injection attacks
   - Invalid IDs are logged and skipped
   - Returns empty dict if no valid IDs remain

3. **Type Handling Fix** (Additional Bug)
   - Fixed `target_type` attribute handling
   - Handles both enum objects (`.name`) and string values
   - Prevents `'str' object has no attribute 'name'` error

### Test Results

✅ **All validation tests pass** (6/6 core tests)
- Query uses IN operator, not OR
- Numeric ID validation works correctly
- Handles 150+ location IDs without errors
- Prevents SQL injection attacks
- GAQL syntax is compliant with v22 spec

✅ **Integration test confirms fix**
- No more "unexpected input OR" errors
- GeoPerformanceAnalyzer progresses past query execution
- Location names are successfully fetched

## Test Details

### Test Configuration
- **Customer ID**: 5777461198 (Topgolf)
- **Date Range**: 2025-08-29 to 2025-11-27 (90 days)
- **Duration Before Failure**: 5.10 seconds
- **Status**: Failed with Google Ads API error

### Error Details

```
Google Ads API error: query_error: UNEXPECTED_INPUT
: Error in query: unexpected input OR.
```

**Error Location**:
- File: `/Users/robertwelborn/PycharmProjects/PaidSearchNav-MCP/src/paidsearchnav_mcp/clients/google/client.py`
- Line: 2247
- Function: `_get_location_names()`
- Method Call: `ga_service.search(customer_id=customer_id, query=query)`

### Expected Behavior
- `get_geographic_performance()` should successfully fetch location data
- `_get_location_names()` should resolve criterion IDs to location names
- GeoPerformanceAnalyzer should complete without GAQL errors

### Actual Behavior
- Function fails during location name resolution
- Google Ads API rejects the GAQL query as malformed
- Analyzer cannot complete analysis

## Root Cause Analysis

### Problem: Malformed OR Clause in WHERE Statement

**Current Code** (lines 2227-2239):
```python
criterion_filter = " OR ".join(
    [f"geo_target_constant.id = {cid}" for cid in criterion_ids]
)

query = f"""
    SELECT
        geo_target_constant.id,
        geo_target_constant.name,
        geo_target_constant.country_code,
        geo_target_constant.target_type,
        geo_target_constant.canonical_name
    FROM geo_target_constant
    WHERE {criterion_filter}
""".strip()
```

### Issue Explanation

When `criterion_ids` contains multiple IDs like `['1023191', '1023192', '1023193']`, the generated query becomes:

```sql
SELECT
    geo_target_constant.id,
    geo_target_constant.name,
    geo_target_constant.country_code,
    geo_target_constant.target_type,
    geo_target_constant.canonical_name
FROM geo_target_constant
WHERE geo_target_constant.id = 1023191 OR geo_target_constant.id = 1023192 OR geo_target_constant.id = 1023193
```

**Why This Fails**:

According to Google Ads Query Language (GAQL) documentation:
1. **OR is not supported in WHERE clauses** for most resource types
2. GAQL uses a more restrictive syntax than SQL
3. Multiple OR conditions are not allowed in v22 API

### Google Ads API v22 GAQL Restrictions

From [Google Ads Query Language docs](https://developers.google.com/google-ads/api/docs/query/grammar):

> The WHERE clause supports only AND operators. OR operators are not supported.

The correct approach is to use the `IN` operator instead:

```sql
WHERE geo_target_constant.id IN (1023191, 1023192, 1023193)
```

## Proposed Solution

### Fix: Replace OR Chain with IN Operator

**Updated Code**:
```python
async def _get_location_names(
    self, customer_id: str, criterion_ids: list[str]
) -> dict[str, dict[str, str]]:
    """Fetch location names for given criterion IDs.

    Args:
        customer_id: Google Ads customer ID
        criterion_ids: List of location criterion IDs

    Returns:
        Dictionary mapping criterion_id to location details
    """
    if not criterion_ids:
        return {}

    client = self._get_client()
    ga_service = client.get_service("GoogleAdsService")

    # Build query for geo_target_constant
    # Use IN operator instead of OR chain (GAQL does not support OR in WHERE)
    criterion_ids_str = ", ".join(criterion_ids)

    query = f"""
        SELECT
            geo_target_constant.id,
            geo_target_constant.name,
            geo_target_constant.country_code,
            geo_target_constant.target_type,
            geo_target_constant.canonical_name
        FROM geo_target_constant
        WHERE geo_target_constant.id IN ({criterion_ids_str})
    """.strip()

    try:
        response = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self._execute_with_circuit_breaker(
                "google_ads_api_search",
                lambda: ga_service.search(customer_id=customer_id, query=query),
            ),
        )

        location_map = {}
        for row in response:
            geo_target = row.geo_target_constant
            location_map[str(geo_target.id)] = {
                "name": geo_target.name,
                "country_code": geo_target.country_code,
                "target_type": geo_target.target_type.name,
                # Add canonical_name if available
            }

        return location_map

    except GoogleAdsException as ex:
        logger.error(f"Failed to fetch location names: {ex}")
        raise APIError(f"Failed to fetch location names: {ex}") from ex
```

### Key Changes

1. **Line 2227-2229**: Replace OR chain with IN operator
   - Before: `" OR ".join([f"geo_target_constant.id = {cid}" for cid in criterion_ids])`
   - After: `", ".join(criterion_ids)` wrapped in `IN (...)`

2. **Query Structure**: Use GAQL-compliant syntax
   - Before: `WHERE id = 1 OR id = 2 OR id = 3`
   - After: `WHERE id IN (1, 2, 3)`

3. **Validation**: Ensure criterion_ids are numeric to prevent injection

### Security Consideration

Since `criterion_ids` are inserted directly into the query, we should validate they are numeric:

```python
# Add validation before building query
validated_ids = []
for cid in criterion_ids:
    if not str(cid).isdigit():
        logger.warning(f"Invalid criterion ID (not numeric): {cid}")
        continue
    validated_ids.append(str(cid))

if not validated_ids:
    return {}

criterion_ids_str = ", ".join(validated_ids)
```

## Investigation Steps

### Step 1: Validate GAQL Syntax
```bash
# Use Google Ads Query Validator
# https://developers.google.com/google-ads/api/fields/v22/geo_target_constant_query_builder

# Test query:
SELECT
    geo_target_constant.id,
    geo_target_constant.name
FROM geo_target_constant
WHERE geo_target_constant.id IN (1023191, 1023192, 1023193)
```

### Step 2: Review Google Ads API Documentation
- Confirm OR operator restrictions in GAQL
- Verify IN operator support for geo_target_constant
- Check for any API version differences (v20 vs v22)

### Step 3: Test Fix with Unit Test
```python
# Create unit test to verify query generation
def test_location_names_query_syntax():
    criterion_ids = ['1023191', '1023192', '1023193']

    # Expected query should use IN, not OR
    expected_query = """
        SELECT
            geo_target_constant.id,
            geo_target_constant.name,
            geo_target_constant.country_code,
            geo_target_constant.target_type,
            geo_target_constant.canonical_name
        FROM geo_target_constant
        WHERE geo_target_constant.id IN (1023191, 1023192, 1023193)
    """.strip()

    # Generate actual query
    actual_query = client._build_location_query(criterion_ids)

    assert "OR" not in actual_query
    assert "IN (" in actual_query
    assert actual_query == expected_query
```

### Step 4: Integration Test with Real API
```python
# Test with production customer ID
async def test_geo_performance_with_real_data():
    client = GoogleAdsClient()
    result = await client.get_geographic_performance(
        customer_id="5777461198",
        start_date=datetime(2025, 8, 29),
        end_date=datetime(2025, 11, 27),
        geographic_level="CITY"
    )

    assert len(result) > 0
    assert "location_name" in result[0]
    assert result[0]["location_name"] != ""
```

## Success Criteria

### Acceptance Tests

1. **Test Case 1: Single Location ID**
   - Given: criterion_ids = ['1023191']
   - When: _get_location_names() is called
   - Then: Query uses `WHERE geo_target_constant.id IN (1023191)`
   - And: Returns location details successfully

2. **Test Case 2: Multiple Location IDs**
   - Given: criterion_ids = ['1023191', '1023192', '1023193']
   - When: _get_location_names() is called
   - Then: Query uses `WHERE geo_target_constant.id IN (1023191, 1023192, 1023193)`
   - And: Returns all location details successfully

3. **Test Case 3: Large ID List**
   - Given: criterion_ids with 100+ IDs
   - When: _get_location_names() is called
   - Then: Query executes without errors
   - And: Returns all location details (may need batching)

4. **Test Case 4: GeoPerformanceAnalyzer End-to-End**
   - Given: Active customer account with geographic data
   - When: GeoPerformanceAnalyzer runs
   - Then: Completes successfully without GAQL errors
   - And: Returns formatted geographic performance report

### Performance Requirements
- Query execution: <5 seconds for 100 locations
- No API errors
- Valid GAQL syntax per v22 spec

## Additional Considerations

### Potential Query Length Limit

If `criterion_ids` list is very large (e.g., 1000+ IDs), the query might exceed GAQL length limits. Consider implementing batching:

```python
async def _get_location_names(
    self, customer_id: str, criterion_ids: list[str]
) -> dict[str, dict[str, str]]:
    """Fetch location names for given criterion IDs."""
    if not criterion_ids:
        return {}

    # Batch into groups of 500 to avoid query length limits
    BATCH_SIZE = 500
    location_map = {}

    for i in range(0, len(criterion_ids), BATCH_SIZE):
        batch = criterion_ids[i:i + BATCH_SIZE]
        batch_results = await self._fetch_location_batch(customer_id, batch)
        location_map.update(batch_results)

    return location_map
```

### Similar Issues in Codebase

Search for other instances of OR chains that should use IN:
```bash
grep -n '" OR ".join' src/paidsearchnav_mcp/clients/google/client.py
```

Audit all GAQL query generation to ensure compliance with API v22 syntax.

## Related Files

- **Bug Location**: `/Users/robertwelborn/PycharmProjects/PaidSearchNav-MCP/src/paidsearchnav_mcp/clients/google/client.py:2207-2265`
- **Caller Function**: `get_geographic_performance()` (line 1433)
- **Analyzer Skill**: `/Users/robertwelborn/PycharmProjects/PaidSearchNav-MCP/skills/geo_performance_analyzer/prompt.md`
- **Test File**: `/Users/robertwelborn/PycharmProjects/PaidSearchNav-MCP/tests/bugs/test_geo_performance_gaql.py`

## Timeline

- **Investigation**: 30 minutes (GAQL syntax review)
- **Fix Implementation**: 1 hour (update query + validation)
- **Testing**: 1.5 hours (unit + integration tests)
- **Total Estimate**: 3 hours

## References

- [Google Ads Query Language Grammar](https://developers.google.com/google-ads/api/docs/query/grammar)
- [GAQL WHERE Clause Restrictions](https://developers.google.com/google-ads/api/docs/query/structure#where)
- [geo_target_constant Resource](https://developers.google.com/google-ads/api/fields/v22/geo_target_constant)
- [Google Ads API v22 Migration Guide](https://developers.google.com/google-ads/api/docs/migration/v22)

## Notes

This is a **critical bug** that completely blocks the GeoPerformanceAnalyzer. The fix is straightforward (replace OR with IN) but requires careful testing to ensure:

1. GAQL syntax is valid per v22 spec
2. Query works with varying numbers of criterion IDs
3. No SQL injection vulnerabilities are introduced
4. Performance is acceptable for large ID lists

Priority should be HIGH due to complete functionality blockage.
