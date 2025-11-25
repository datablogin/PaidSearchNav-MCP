# Claude Desktop MCP Server Test Script

This script helps verify that the MCP connector fixes are working correctly in Claude Desktop.

## Prerequisites

1. **Restart Claude Desktop** to pick up the latest MCP server changes:
   ```bash
   # Fully quit Claude Desktop (Cmd+Q)
   # Then relaunch from Applications
   ```

2. **Verify MCP Configuration**:
   - Location: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - Should reference: `/Users/robertwelborn/PycharmProjects/PaidSearchNav-MCP/.venv/bin/python`
   - Should have env var: `GCP_PROJECT_ID=topgolf-460202`

3. **Check Server Logs** (if issues occur):
   ```bash
   tail -f ~/Library/Logs/Claude/mcp-server-paidsearchnav.log
   ```

---

## Test 1: Verify BigQuery Config Resource

**Purpose**: Ensure Claude can access the correct BigQuery project ID

**Paste this into Claude Desktop**:
```
Can you check the resource://bigquery/config resource and tell me:
1. What project_id is configured?
2. What datasets are available?
3. What's the recommended query format?
```

**Expected Result**:
- ✅ Project ID should be: `topgolf-460202`
- ✅ Should list `paidsearchnav_production` (recommended) and `google_ads_export`
- ✅ Should show query format example

**If this fails**: The new BigQuery config resource isn't being recognized. Check that Claude Desktop picked up the server changes.

---

## Test 2: Get Keywords (Basic)

**Purpose**: Verify `get_keywords` tool works without AttributeError

**Paste this into Claude Desktop**:
```
Use the get_keywords tool to fetch keywords for customer ID 5777461198
for the date range 2025-07-01 to 2025-10-31.

Show me:
1. How many keywords were returned
2. The first 3 keywords with their match types and costs
3. Any errors encountered
```

**Expected Result**:
- ✅ Should return thousands of keywords without crashing
- ✅ Each keyword should have: keyword_text, match_type, customer_id, quality_score, etc.
- ✅ No AttributeError about 'text' or 'customer_id'

**If this fails with AttributeError**: The model attribute fixes didn't apply. Check the commit is on the branch.

---

## Test 3: Get Search Terms (Basic)

**Purpose**: Verify `get_search_terms` tool works without AttributeError

**Paste this into Claude Desktop**:
```
Use the get_search_terms tool to fetch search terms for customer ID 5777461198
for the date range 2025-07-01 to 2025-10-31.

Show me:
1. How many search terms were returned
2. The top 5 search terms by cost
3. Any errors encountered
```

**Expected Result**:
- ✅ Should return search terms without crashing
- ✅ Each search term should have: search_term, keyword_text, customer_id, metrics
- ✅ No AttributeError about 'customer_id'

**If this fails with AttributeError**: The SearchTerm model fix didn't apply. Check server.py line 423.

---

## Test 4: BigQuery Fallback with Correct Project ID

**Purpose**: Verify Claude uses correct project ID when falling back to BigQuery

**Paste this into Claude Desktop**:
```
If the get_keywords tool fails for any reason, try querying BigQuery directly.
Before constructing any SQL queries, check the resource://bigquery/config
resource to get the correct project_id.

Fetch keyword data for customer 5777461198 from BigQuery and show me:
1. The project_id you used in the query
2. The full SQL query you constructed
3. Sample results
```

**Expected Result**:
- ✅ Should use project_id: `topgolf-460202` (NOT `topgolf-paid-search`)
- ✅ Query format: `` `topgolf-460202.paidsearchnav_production.keyword_stats_with_keyword_info_view` ``
- ✅ Should successfully return data

**If this fails**: Claude is either:
- Not checking the BigQuery config resource
- Still inferring wrong project ID from context

---

## Test 5: Full Keyword Match Analyzer Skill

**Purpose**: End-to-end test of the KeywordMatchAnalyzer skill

**Paste this into Claude Desktop**:
```
Run the KeywordMatchAnalyzer skill for:
- Customer ID: 5777461198
- Date Range: 2025-07-01 to 2025-10-31

Generate a full keyword match type analysis report following the skill methodology.
```

**Expected Result**:
- ✅ Should fetch both keywords and search terms
- ✅ Should generate comprehensive markdown report with:
  - Match type performance overview
  - High-cost broad match keywords
  - Quality score issues
  - Savings estimates
  - Prioritized recommendations
- ✅ No MCP server crashes
- ✅ No BrokenPipeError in logs

**If this fails**: Check which tool call failed and refer to the specific test above.

---

## Test 6: Authentication Flow (Optional)

**Purpose**: Verify BrokenPipeError protection during auth flows

**Only run this if you need to re-authenticate**:

1. Remove existing tokens:
   ```bash
   rm -rf ~/.paidsearchnav/tokens/*
   ```

2. Restart Claude Desktop (Cmd+Q, then relaunch)

3. Trigger any MCP tool that requires Google Ads API access

**Expected Result**:
- ✅ Should display authentication instructions to stdout
- ✅ If stdout is closed, should fall back to logging
- ✅ MCP server should NOT crash with BrokenPipeError
- ✅ Check logs: `tail -f ~/Library/Logs/Claude/mcp-server-paidsearchnav.log`

---

## Troubleshooting

### MCP Server Not Starting

**Check Claude Desktop config**:
```bash
cat ~/Library/Application\ Support/Claude/claude_desktop_config.json | grep -A 10 paidsearchnav
```

**Verify Python path**:
```bash
ls -la /Users/robertwelborn/PycharmProjects/PaidSearchNav-MCP/.venv/bin/python
```

### AttributeError Still Occurring

**Verify current branch and commit**:
```bash
cd /Users/robertwelborn/PycharmProjects/PaidSearchNav-MCP
git branch
git log -1 --oneline
```

Should show:
- Branch: `feature/phase-2-bigquery-mcp-integration`
- Latest commit: `fix: Critical MCP connector fixes for Phase 4 preparation`

**Force restart Claude Desktop**:
```bash
killall Claude
# Then relaunch from Applications
```

### BigQuery Project ID Still Wrong

**Check resource in Claude Desktop**:
```
Show me the full response from resource://bigquery/config
```

If project_id is empty or wrong, check:
```bash
# Verify .env file
cat /Users/robertwelborn/PycharmProjects/PaidSearchNav-MCP/.env | grep GCP_PROJECT_ID

# Should show: GCP_PROJECT_ID=topgolf-460202
```

### BrokenPipeError in Logs

**Check if fix applied**:
```bash
cd /Users/robertwelborn/PycharmProjects/PaidSearchNav-MCP
grep -n "_safe_print" src/paidsearchnav_mcp/clients/google/auth.py
```

Should show the method at line ~368 and usage in display/polling functions.

---

## Success Criteria

All tests pass when:

| Test | Status | Fix Verified |
|------|--------|--------------|
| 1. BigQuery Config Resource | ✅ | New resource working |
| 2. Get Keywords | ✅ | Model attribute fix working |
| 3. Get Search Terms | ✅ | Model attribute fix working |
| 4. BigQuery Fallback | ✅ | Correct project ID used |
| 5. Full Skill Analysis | ✅ | End-to-end working |
| 6. Auth Flow (Optional) | ✅ | BrokenPipeError protection working |

---

## Quick Test Command (All-in-One)

**Paste this single prompt into Claude Desktop**:

```
I want to test that the MCP server fixes are working. Please:

1. Check resource://bigquery/config and tell me the project_id
2. Fetch keywords for customer 5777461198 (2025-07-01 to 2025-10-31)
3. Fetch search terms for the same customer and dates
4. If you need to use BigQuery, make sure to use the project_id from step 1
5. Summarize any errors you encounter

Be explicit about which tools you're calling and what data you're getting back.
```

**Expected**: All steps complete successfully with correct project_id and no AttributeErrors.

---

## Log Analysis

**View recent errors**:
```bash
tail -100 ~/Library/Logs/Claude/mcp-server-paidsearchnav.log | grep -E "(ERROR|AttributeError|BrokenPipeError)"
```

**Monitor in real-time**:
```bash
tail -f ~/Library/Logs/Claude/mcp-server-paidsearchnav.log
```

---

## Next Steps After Testing

If all tests pass:
- ✅ MCP connector is stable
- ✅ Ready for Phase 4 analyzer conversions
- ✅ Can proceed with converting Priority Tier 1 analyzers

If tests fail:
- Review specific test failure above
- Check troubleshooting section
- Verify commit and branch are correct
- Ensure Claude Desktop fully restarted
