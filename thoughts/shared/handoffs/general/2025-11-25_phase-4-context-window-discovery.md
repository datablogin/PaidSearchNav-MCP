---
date: 2025-11-25T23:00:00+0000
researcher: Claude (Sonnet 4.5)
git_commit: TBD
branch: feature/phase-2-bigquery-mcp-integration
repository: PaidSearchNav-MCP
topic: "Phase 4 Context Window Discovery & Strategy Pivot"
tags: [architecture, phase-2.5, orchestration-layer, context-limits, plan-revision]
status: Plan updated, ready for Phase 2.5 implementation
last_updated: 2025-11-25
last_updated_by: Claude (Sonnet 4.5)
type: strategy_handoff
---

# Handoff: Phase 4 Context Window Discovery & Plan Revision

## Executive Summary

**Critical Discovery**: Claude Desktop cannot handle production-scale Google Ads data analysis using the original skills-based architecture. Skills hit context window limits with 500+ records, requiring a fundamental architecture change.

**Solution Implemented**: Added Phase 2.5 to implementation plan - orchestration layer that moves analysis logic from Claude (skills) to MCP server, returning only summaries instead of raw data.

**Status**: Plan updated in `thoughts/shared/plans/2025-11-22-mcp-skills-refactoring-implementation.md`. Ready to begin Phase 2.5 implementation.

---

## What We Discovered

### Original Architecture (Didn't Work)

```
Claude Desktop Skill (200 lines)
    ↓
get_keywords() → 5000 records (~200KB JSON)
    ↓
Claude analyzes raw data
    ↓
❌ Context window exhaustion → Conversation compacts → Hangs
```

### Testing Results

| Test Configuration | Lines | Data Size | Result |
|-------------------|-------|-----------|--------|
| Original skills | 200-280 | 500 records | ❌ Failed - context exhaustion |
| Refactored v1 | 169 | 500 records | ❌ Failed - still too much |
| Ultra-minimal v2 | 51 | 500 records | ⚠️ Partially works but unreliable |
| TestMinimal | 25 | 0 (no analysis) | ✅ Works perfectly |

**Test Account**: Topgolf (customer_id: 5777461198, 1000+ keywords)

### Root Cause Analysis

**Three compounding factors**:

1. **Large Data Volumes**:
   - Production accounts have 1000-5000+ keywords/search terms
   - Even with pagination (limit=500), responses are 50-100KB JSON
   - Multiple MCP calls (keywords + search terms) = 100-200KB total

2. **Verbose Skill Prompts**:
   - Original prompts were 200-280 lines (detailed methodology, examples, formulas)
   - Even ultra-minimal prompts (51 lines) still problematic
   - Context consumed by: prompt + data + Claude's working memory for analysis

3. **Claude Desktop Limitations**:
   - When context approaches limit, Desktop "compacts" conversation
   - After 1-2 compactions, stops responding entirely
   - No graceful degradation - just hangs

**Conclusion**: Claude Desktop is **not suitable** for analyzing raw production data. Server must do the analysis.

---

## Architecture Change: Orchestration Layer

### New Two-Layer Design

```
┌─────────────────────────────────────┐
│  Claude Desktop (Lightweight)       │
│  - 20-50 line skill prompts         │
│  - Call orchestration tools         │
│  - Format summaries for display     │
└────────────┬────────────────────────┘
             │ MCP Protocol
             ▼
┌─────────────────────────────────────┐
│  MCP Server (Heavy Lifting)         │
│                                      │
│  Layer 1: Orchestration Tools ⭐NEW │
│  ├─ analyze_keyword_match_types()  │
│  ├─ analyze_search_term_waste()    │
│  ├─ analyze_negative_conflicts()   │
│  ├─ analyze_geo_performance()      │
│  └─ analyze_pmax_cannibalization() │
│                                      │
│  Returns: Summary + Top 10 only    │
│  (~50 lines vs 5000 lines)         │
│                                      │
│  Layer 2: Data Tools ✅ DONE        │
│  ├─ get_keywords() (paginated)     │
│  ├─ get_search_terms() (paginated) │
│  └─ ... (4 more tools)             │
└─────────────────────────────────────┘
```

### Key Principles

1. **Server Does Analysis**:
   - Fetch ALL data with automatic pagination (server-side)
   - Perform calculations (match type stats, opportunity detection, etc.)
   - Return only actionable insights

2. **Skills Are Formatters**:
   - Call one orchestration tool
   - Format the summary as a professional report
   - No data analysis logic in skills

3. **Response Size Control**:
   - Orchestration tools return max 100 lines
   - Executive summary: 5-10 lines
   - Top 10 recommendations: ~30 lines
   - Implementation steps: ~10 lines
   - Total: <100 lines (vs 5000+ raw records)

---

## Phase 2.5: Implementation Plan

### Directory Structure

```
src/paidsearchnav_mcp/analyzers/
├── __init__.py
├── base.py                      # AnalysisSummary model + BaseAnalyzer class
├── keyword_match.py             # 5 analyzer implementations
├── search_term_waste.py
├── negative_conflicts.py
├── geo_performance.py
└── pmax_cannibalization.py
```

### Implementation Steps

**For each of 5 analyzers** (4-6 hours each):

1. **Extract Logic**:
   - From: `skills/*/prompt.md` (analysis methodology)
   - From: `archive/old_app/paidsearchnav/analyzers/*.py` (original code)
   - Create: `src/paidsearchnav_mcp/analyzers/*.py` (new analyzer class)

2. **Implement Analyzer Class**:
   ```python
   class KeywordMatchAnalyzer(BaseAnalyzer):
       async def analyze(customer_id, start_date, end_date) -> AnalysisSummary:
           # Fetch all data with automatic pagination
           keywords = await self._fetch_all_keywords(...)
           search_terms = await self._fetch_all_search_terms(...)

           # Perform analysis
           opportunities = self._find_exact_match_opportunities(...)

           # Return summary only (not raw data)
           return AnalysisSummary(
               total_records_analyzed=len(keywords),
               estimated_monthly_savings=...,
               top_recommendations=[...],  # Top 10 only
               implementation_steps=[...]
           )
   ```

3. **Add Orchestration Tool**:
   ```python
   # In server.py
   @mcp.tool()
   async def analyze_keyword_match_types(...) -> dict:
       analyzer = KeywordMatchAnalyzer()
       summary = await analyzer.analyze(...)
       return summary.model_dump()
   ```

4. **Update Skill Prompt** (reduce from 200 lines → 50 lines):
   ```markdown
   # Keyword Match Type Analysis

   Call `analyze_keyword_match_types(customer_id, start_date, end_date)`
   and format as a professional report.

   [Output format template - 30 lines]
   ```

5. **Test**:
   - Unit tests for analyzer logic
   - Integration test with Topgolf account (5777461198)
   - Verify: completes in <30 seconds, returns <100 lines, no context issues

### Timeline

- **Per analyzer**: 4-6 hours
- **Total for 5 analyzers**: 20-30 hours
- **Testing & refinement**: 5-10 hours
- **Total Phase 2.5**: ~35-40 hours

---

## Updated Project Status

### Completed Phases ✅

- ✅ **Phase 0**: Repository cleanup, code archived
- ✅ **Phase 1**: Google Ads API integration (all 6 data tools working)
- ✅ **Phase 2**: BigQuery integration (query + schema tools working)
- ✅ **Phase 3**: KeywordMatchAnalyzer skill created (needs Phase 2.5 update)
- ✅ **Phase 4**: 4 additional skills created (all need Phase 2.5 updates)

### Current Phase ⏳

- **Phase 2.5**: Add orchestration layer (NEW - critical for production use)
  - Status: Plan documented, ready to implement
  - Files to create: 6 (base.py + 5 analyzers)
  - Tools to add: 5 orchestration MCP tools
  - Skills to update: 5 (reduce prompts, call orchestration tools)

### Remaining Phases 📋

- Phase 5: Convert Tier 2 & 3 analyzers (19 more skills)
- Phase 6: Production deployment
- Phase 7: Archive old repository
- Phase 8: Extract skills to separate repo

---

## Key Learnings

### What Worked ✅

1. **MCP Server Implementation**: Flawless
   - All 6 data retrieval tools work perfectly
   - Pagination implemented correctly
   - Redis caching working
   - Error handling robust

2. **TestMinimal Validation**: Brilliant debugging approach
   - 25-line skill proved MCP integration works
   - Isolated the problem to prompt size + data volume
   - Confirmed server is not the issue

3. **Parallel Refactoring**: Efficient
   - 5 agents refactored 5 skills simultaneously
   - Reduced prompts from 1037 lines → 564 lines (46% reduction)
   - Pattern emerged for ultra-minimal prompts

### What Didn't Work ❌

1. **Skills as Data Analyzers**: Fundamentally broken
   - Claude Desktop cannot handle 500+ records
   - Prompts + data + analysis = context explosion
   - No amount of prompt optimization solves this

2. **Original Plan Assumption**: Wrong
   - Plan assumed skills would analyze raw data
   - Assumed Claude Desktop could handle "medium" datasets
   - Reality: Must analyze server-side, return summaries only

3. **Progressive Refinement**: Wasted effort
   - Spent hours reducing prompts from 280 → 169 → 51 lines
   - Still didn't work reliably
   - Should have pivoted to orchestration immediately

### What We Learned 💡

1. **Context Window Limits Are Real**:
   - Not just theoretical - production blocker
   - Skills are **not** a replacement for server-side logic
   - Claude Desktop is for **formatting**, not **analysis**

2. **MCP Server is More Powerful Than Expected**:
   - Can handle unlimited data sizes
   - Perfect place for analysis logic
   - Returns compact summaries = best UX

3. **Skills Should Be Simple**:
   - 20-50 lines maximum
   - Call orchestration tools
   - Format results for display
   - No business logic in skills

---

## Files Modified

### Plan Document
- **Updated**: `thoughts/shared/plans/2025-11-22-mcp-skills-refactoring-implementation.md`
  - Added "Current State Analysis (Updated: 2025-11-25)"
  - Revised architecture diagram (two-layer design)
  - Updated success criteria
  - **Inserted Phase 2.5** with complete implementation guide

### Skills Created/Refactored
- `skills/keyword_match_analyzer/` - Created Phase 3, refactored Phase 4
- `skills/search_term_analyzer/` - Created Phase 4, refactored
- `skills/negative_conflict_analyzer/` - Created Phase 4, refactored
- `skills/geo_performance_analyzer/` - Created Phase 4, refactored
- `skills/pmax_analyzer/` - Created Phase 4, refactored
- `skills/test_minimal/` - Created for validation (25 lines, works perfectly)

### Documentation
- `docs/SKILL_HANG_ISSUE_ANALYSIS.md` - Root cause analysis
- `docs/SKILL_CATALOG.md` - Skill inventory
- `docs/QUARTERLY_AUDIT_GUIDE.md` - User guide
- `docs/SKILL_TESTING_GUIDE.md` - Testing procedures

### Backups Created
- All original prompts backed up with `.backup` extension
- `prompt_169lines.backup` - First refactor attempt
- `prompt_v2.md` - Ultra-minimal version (51 lines)

---

## Next Steps

### Immediate (Start Phase 2.5)

1. **Create analyzer base** (`src/paidsearchnav_mcp/analyzers/base.py`):
   - AnalysisSummary model
   - BaseAnalyzer abstract class
   - Helper methods (format_currency, calculate_savings)

2. **Implement KeywordMatchAnalyzer first**:
   - Extract logic from skill prompt + archived analyzer
   - Implement `analyze()` method
   - Add automatic pagination helpers
   - Return AnalysisSummary with top 10 recommendations

3. **Add orchestration tool**:
   - `analyze_keyword_match_types()` in server.py
   - Test with Topgolf account (5777461198)
   - Verify: <30 seconds, <100 lines response, no context issues

4. **Update skill to use orchestration tool**:
   - Reduce prompt from 169 lines → ~50 lines
   - Call orchestration tool, format output
   - Test in Claude Desktop → Should work perfectly

5. **Repeat for 4 remaining analyzers**:
   - SearchTermWasteAnalyzer
   - NegativeConflictAnalyzer
   - GeoPerformanceAnalyzer
   - PMaxCannibalizationAnalyzer

### Success Metrics

- ✅ All 5 orchestration tools work with large accounts (5777461198)
- ✅ All 5 skills work in Claude Desktop without context issues
- ✅ Responses complete in <30 seconds
- ✅ Output is <100 lines (summary + top 10 only)
- ✅ Recommendations match original analyzer logic

---

## Risks & Mitigations

### Risk 1: Analysis Logic Extraction
**Risk**: Business logic scattered across prompts and old analyzers, hard to extract
**Mitigation**:
- Prompts have detailed methodology (use as spec)
- Old analyzers have working code (use as reference)
- Can test recommendations against old output for validation

### Risk 2: Performance
**Risk**: Server-side analysis might be slow for large accounts
**Mitigation**:
- Use async/await throughout
- Leverage Redis caching
- Pagination already tested and fast
- Can add progress indicators if needed

### Risk 3: Skill Complexity
**Risk**: Even 50-line skills might be too complex
**Mitigation**:
- TestMinimal proves 25 lines works
- Skills will be mostly output template (30 lines) + 20 lines logic
- Can simplify further if needed (just show raw JSON from orchestration tool)

---

## References

- **Implementation Plan**: `thoughts/shared/plans/2025-11-22-mcp-skills-refactoring-implementation.md`
- **Previous Handoff**: `thoughts/shared/handoffs/general/2025-11-24_23-28-02_phase-4-mcp-skills-implementation.md`
- **Issue Analysis**: `docs/SKILL_HANG_ISSUE_ANALYSIS.md`
- **Testing Guide**: `docs/SKILL_TESTING_GUIDE.md`

---

**Ready to proceed with Phase 2.5 implementation!**
