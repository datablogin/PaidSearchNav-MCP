# Manual Skill Testing Guide

## Overview

This guide provides step-by-step instructions for manually testing each Claude Skill to ensure it works correctly with the PaidSearchNav MCP server.

## Testing Prerequisites

### Environment Setup
- ✅ Claude Desktop installed and running
- ✅ PaidSearchNav MCP server configured in Claude Desktop settings
- ✅ MCP server successfully connected (verify in Claude Desktop)
- ✅ Test Google Ads account access (customer ID ready)

### Test Data Requirements
- ✅ Google Ads account with **minimum 90 days of history**
- ✅ At least **$1,000 total spend** in test period
- ✅ **Active campaigns** (not all paused)
- ✅ Mixture of match types, search terms, and geographic data

### Recommended Test Account Profile
For best testing results, use an account with:
- 5-10 active campaigns
- 50-200 active keywords
- Mix of Search and PMax campaigns (if testing PMaxAnalyzer)
- Geographic targeting (for GeoPerformanceAnalyzer)
- Some existing negative keywords (for NegativeConflictAnalyzer)

---

## Testing Methodology

For each skill, we'll:
1. **Load the skill** into Claude Desktop
2. **Run the analysis** with test prompts
3. **Verify the output** against expected format
4. **Validate recommendations** make business sense
5. **Check performance** (should complete in <30 seconds)

---

## Option 1: Testing with Packaged Skills (Recommended)

### Step 1: Prepare Packaged Skills

```bash
# From project root
cd /Users/robertwelborn/PycharmProjects/PaidSearchNav-MCP

# Package all skills (if not already done)
python3 scripts/package_skill.py --all --output dist

# Verify .zip files exist
ls -lh dist/*.zip
```

You should see 5 .zip files in the dist/ directory.

### Step 2: Load Skills into Claude Desktop

**For Each Skill**:
1. Open Claude Desktop
2. Start a new conversation
3. Click the attachment button (📎)
4. Select the skill .zip file (e.g., `KeywordMatchAnalyzer_v1.0.0.zip`)
5. Upload the file
6. Claude will process and load the skill

**Note**: You may need to load one skill per conversation, or Claude may be able to handle multiple skills in one conversation depending on the implementation.

---

## Option 2: Testing with Direct Prompts

If packaged skills don't work or you want to test the raw prompts:

### Step 1: Copy Skill Prompt

```bash
# View a skill's prompt
cat skills/keyword_match_analyzer/prompt.md
```

### Step 2: Paste into Claude

1. Open Claude Desktop
2. Start a new conversation
3. Copy the **entire contents** of `prompt.md`
4. Paste into Claude
5. Claude now operates as that skill

---

## Testing Each Skill

### Test 1: KeywordMatchAnalyzer

**Objective**: Verify it identifies exact match opportunities correctly.

**Test Prompt**:
```
Analyze keyword match types for customer ID [YOUR_CUSTOMER_ID]
from [START_DATE] to [END_DATE] and identify exact match opportunities.

Example:
Analyze keyword match types for customer ID 1234567890
from 2025-08-01 to 2025-10-31 and identify exact match opportunities.
```

**Expected Output Format**:
```markdown
# Keyword Match Type Analysis

## Executive Summary
- Total Keywords Analyzed: [number]
- Exact Match Opportunities: [number]
- Estimated Monthly Savings: $[amount]

## Top Exact Match Opportunities

| Keyword | Current Match | Impressions | Clicks | Conversions | Reason |
|---------|---------------|-------------|--------|-------------|--------|
| ... | ... | ... | ... | ... | ... |

## Implementation Guide
[Step-by-step instructions]
```

**Validation Checklist**:
- [ ] Analysis completes in <30 seconds
- [ ] Output is formatted markdown
- [ ] Recommendations include specific keywords
- [ ] Metrics are realistic (not all zeros or impossibly high)
- [ ] Reasons for recommendations make sense
- [ ] Implementation guide is clear and actionable
- [ ] MCP tools were called successfully (no errors)

**Business Logic Validation**:
- [ ] Only recommends exact match for keywords with concentrated search terms
- [ ] Doesn't recommend exact match for keywords already exact match
- [ ] Performance thresholds are applied (≥100 clicks minimum)
- [ ] Savings estimates are reasonable (not >100% of current spend)

---

### Test 2: SearchTermAnalyzer

**Objective**: Verify it identifies negative keyword opportunities and classifies intent.

**Test Prompt**:
```
Analyze search terms for customer ID [YOUR_CUSTOMER_ID]
from [START_DATE] to [END_DATE] and identify negative keyword opportunities.
```

**Expected Output Format**:
```markdown
# Search Term Waste Analysis

## Executive Summary
- Total Search Terms Analyzed: [number]
- Wasted Spend Identified: $[amount]
- Negative Keyword Recommendations: [number]

## Critical Negative Keywords (Add Immediately)

| Search Term | Spend | Conversions | CTR | Reason | Level |
|-------------|-------|-------------|-----|--------|-------|
| ... | ... | ... | ... | ... | ... |

## Intent Analysis
- TRANSACTIONAL: [stats]
- INFORMATIONAL: [stats]
- NAVIGATIONAL: [stats]
- LOCAL: [stats]

## Negative Keyword Recommendations by Level
[Account, Campaign, Ad Group levels]
```

**Validation Checklist**:
- [ ] Analysis completes in <30 seconds
- [ ] Output is formatted markdown
- [ ] Intent classification is present
- [ ] Negative recommendations are specific
- [ ] Level recommendations are appropriate
- [ ] Implementation guide is included

**Business Logic Validation**:
- [ ] Zero conversion terms with >$50 spend are flagged
- [ ] Intent patterns are correctly classified
- [ ] "Near me" searches are NOT recommended as negatives (local intent)
- [ ] Brand terms are NOT recommended as negatives (unless not your brand)
- [ ] Irrelevant patterns (jobs, free, DIY) are caught
- [ ] Recommendations are grouped by level (Account, Campaign, Ad Group)

---

### Test 3: NegativeConflictAnalyzer

**Objective**: Verify it detects negative keywords blocking positive keywords.

**Test Prompt**:
```
Analyze negative keyword conflicts for customer ID [YOUR_CUSTOMER_ID]
and identify which negatives are blocking high-value keywords.
```

**Expected Output Format**:
```markdown
# Negative Keyword Conflict Report

## Executive Summary
- Positive Keywords Analyzed: [number]
- Negative Keywords Analyzed: [number]
- Conflicts Found: [number]
- Critical Conflicts: [number]
- Estimated Revenue Loss: $[amount]

## Critical Conflicts

| Positive Keyword | Conversions | Value | Blocking Negative | Match Type | Level | Severity |
|------------------|-------------|-------|-------------------|------------|-------|----------|
| ... | ... | ... | ... | ... | ... | ... |

## Resolution Recommendations
[Specific actions to fix conflicts]
```

**Validation Checklist**:
- [ ] Analysis completes in <30 seconds
- [ ] Output is formatted markdown
- [ ] Conflicts are specific and detailed
- [ ] Severity levels are assigned
- [ ] Resolution options are provided
- [ ] Impact estimates are present

**Business Logic Validation**:
- [ ] Match type conflict rules are correct:
  - Exact negative only blocks exact positive
  - Phrase negative blocks if phrase appears in positive
  - Broad negative blocks if all words appear
- [ ] Severity is based on conversions and Quality Score
- [ ] Resolution options make sense (remove, change match type, refine)
- [ ] High-converting keywords are prioritized (Critical severity)
- [ ] Shared list conflicts are identified separately

**Manual Verification Test**:
Create a known conflict to verify detection:
1. Add a broad negative keyword (e.g., "shoes") to a campaign
2. Ensure there's a positive keyword containing that word (e.g., "running shoes")
3. Run the analyzer
4. Verify it detects the conflict ✅

---

### Test 4: GeoPerformanceAnalyzer

**Objective**: Verify it identifies location bid adjustment opportunities.

**Test Prompt**:
```
Analyze geographic performance for customer ID [YOUR_CUSTOMER_ID]
from [START_DATE] to [END_DATE] and recommend location bid adjustments.
```

**Expected Output Format**:
```markdown
# Geographic Performance Analysis

## Executive Summary
- Locations Analyzed: [number]
- Account ROAS: [value]
- Locations to Bid Up: [number]
- Locations to Bid Down: [number]
- Locations to Exclude: [number]

## Top Performing Locations (Bid Up)

| Location | Conversions | ROAS | Conv Rate | vs Avg | Recommendation |
|----------|-------------|------|-----------|--------|----------------|
| ... | ... | ... | ... | ... | ... |

## Underperforming Locations (Bid Down)
[Table]

## Locations to Exclude
[Table]

## Implementation Guide
[Step-by-step instructions]
```

**Validation Checklist**:
- [ ] Analysis completes in <30 seconds
- [ ] Output is formatted markdown
- [ ] Locations are specific (city, DMA, or region)
- [ ] Bid adjustment recommendations are reasonable (±20% to ±50%)
- [ ] Exclusion recommendations have justification
- [ ] Performance metrics are included

**Business Logic Validation**:
- [ ] Bid up recommendations: ROAS ≥2x average, conv rate ≥1.5x average
- [ ] Bid down recommendations: ROAS ≤0.5x average, conv rate ≤0.5x average
- [ ] Exclusion recommendations: >$500 spend AND 0 conversions
- [ ] Account averages are calculated correctly
- [ ] Recommendations consider sufficient volume (≥10 conversions for bid ups)

**Retail-Specific Validation** (if applicable):
- [ ] Store proximity insights are mentioned
- [ ] "Near me" search performance is analyzed
- [ ] Local intent searches are given priority

---

### Test 5: PMaxAnalyzer

**Objective**: Verify it detects Performance Max cannibalization of Search campaigns.

**Test Prompt**:
```
Analyze Performance Max cannibalization for customer ID [YOUR_CUSTOMER_ID]
and recommend negative keywords to improve efficiency.
```

**Note**: This test requires the account to have **both** Performance Max and standard Search campaigns. If the test account doesn't have PMax, you'll need to use a different account or create a test PMax campaign.

**Expected Output Format**:
```markdown
# PMax Cannibalization Analysis

## Executive Summary
- PMax Campaigns: [number]
- Search Campaigns: [number]
- Overlapping Search Terms: [number]
- Monthly Waste from Cannibalization: $[amount]
- Recommended PMax Negative Keywords: [number]

## Cannibalization Summary

| Search Term | Search CPA | PMax CPA | CPA Increase | Monthly Waste | Severity |
|-------------|------------|----------|--------------|---------------|----------|
| ... | ... | ... | ... | ... | ... |

## PMax Negative Keyword Recommendations
[Specific terms to add as PMax negatives]
```

**Validation Checklist**:
- [ ] Analysis completes in <30 seconds
- [ ] Output is formatted markdown
- [ ] Overlapping search terms are identified
- [ ] Performance comparison is clear (Search vs PMax)
- [ ] Negative keyword recommendations are specific
- [ ] Implementation guide includes asset group instructions

**Business Logic Validation**:
- [ ] Only flags overlaps where PMax CPA is worse than Search
- [ ] Severity based on CPA difference and spend
- [ ] Brand terms are high priority for PMax negatives
- [ ] Local intent terms ("near me") are flagged for Search-only
- [ ] Recommendations are asset group-level (not campaign-level)

**Manual Verification Test** (if possible):
1. Identify a search term appearing in both PMax and Search reports
2. Compare CPAs manually
3. Verify the analyzer detects it and calculates impact correctly ✅

---

## Performance Testing

For each skill, measure execution time:

### Method 1: Manual Timing
1. Note start time when you send the prompt
2. Note end time when analysis completes
3. Calculate duration
4. **Expected**: <30 seconds per skill

### Method 2: Claude's Response Time
- Claude Desktop shows "Thinking..." duration
- This should be <30 seconds for data fetching and analysis
- Note: First run may be slower due to MCP server cache warming

**Performance Benchmarks**:
- **Small account** (<100 keywords): 5-15 seconds
- **Medium account** (100-1000 keywords): 15-30 seconds
- **Large account** (>1000 keywords): May exceed 30 seconds on first run, <30s on subsequent runs

If a skill takes >60 seconds:
- ❌ Performance issue - report as bug
- Check MCP server logs for slow queries
- Verify account size isn't exceptionally large

---

## Output Quality Testing

### Markdown Formatting Validation

For each skill output, verify:
- [ ] Proper markdown headers (# ## ###)
- [ ] Tables render correctly
- [ ] Bullet points are formatted
- [ ] Code blocks (if any) are fenced with ```
- [ ] Links are clickable
- [ ] No raw JSON or data dumps

### Content Completeness

Each skill should include:
- [ ] Executive Summary section
- [ ] Detailed findings with tables
- [ ] Specific, actionable recommendations
- [ ] Implementation guide with steps
- [ ] Expected results/impact estimates

### Business Sense Check

For each recommendation:
- [ ] Makes logical business sense
- [ ] Aligns with best practices
- [ ] Doesn't recommend obviously wrong actions
- [ ] Impact estimates are realistic (not 1000% ROAS increase)
- [ ] Considers account-specific context

---

## Integration Testing: Full Quarterly Audit

After individual skill testing, run a complete quarterly audit workflow:

### Step 1: Preparation
```
Document current account metrics for customer ID [YOUR_CUSTOMER_ID]:
- Overall CPA
- Overall ROAS
- Total conversions
- Impression share
```

### Step 2: Run All 5 Skills in Sequence

**In a single Claude conversation** (or separate conversations):

```
1. Run KeywordMatchAnalyzer for customer ID [YOUR_CUSTOMER_ID] from [START_DATE] to [END_DATE]

[Wait for completion]

2. Run SearchTermAnalyzer for customer ID [YOUR_CUSTOMER_ID] from [START_DATE] to [END_DATE]

[Wait for completion]

3. Run NegativeConflictAnalyzer for customer ID [YOUR_CUSTOMER_ID]

[Wait for completion]

4. Run GeoPerformanceAnalyzer for customer ID [YOUR_CUSTOMER_ID] from [START_DATE] to [END_DATE]

[Wait for completion]

5. Run PMaxAnalyzer for customer ID [YOUR_CUSTOMER_ID]

[Wait for completion]
```

### Step 3: Aggregate Results

**Validation**:
- [ ] All 5 skills completed successfully
- [ ] Total execution time: <5 minutes
- [ ] No duplicate recommendations across skills
- [ ] Combined savings estimates are reasonable (15-35% of spend)
- [ ] Recommendations don't contradict each other

**Expected Combined Output**:
- Total opportunities: 50-200 across all skills
- Combined estimated savings: $5,000-$15,000/month (mid-sized account)
- Mix of recommendation types (negatives, match types, geo, conflicts)

### Step 4: Validate Combined Logic

Check for potential conflicts:
- [ ] SearchTermAnalyzer negative recommendations don't conflict with KeywordMatchAnalyzer exact match recommendations
- [ ] NegativeConflictAnalyzer fixes aren't undone by SearchTermAnalyzer new negatives
- [ ] GeoPerformanceAnalyzer recommendations are compatible with other optimizations

---

## Troubleshooting

### Issue: Skill doesn't respond or times out

**Possible Causes**:
1. MCP server not connected
2. Google Ads API credentials issue
3. Customer ID incorrect
4. Account has insufficient data

**Debug Steps**:
```bash
# Check MCP server logs
tail -f ~/.local/share/Claude/logs/mcp*.log

# Verify server is running
ps aux | grep mcp

# Test MCP connection manually
# (specific command depends on your MCP server setup)
```

### Issue: Output is just raw data, no analysis

**Cause**: Skill prompt may not have loaded correctly

**Fix**:
1. Reload the skill (re-upload .zip or re-paste prompt)
2. Start a fresh conversation
3. Try the direct prompt method instead of packaged skill

### Issue: Recommendations seem wrong or nonsensical

**Possible Causes**:
1. Test account has unusual data patterns
2. Insufficient data volume (<90 days or <$1000 spend)
3. Logic bug in skill prompt

**Debug Steps**:
1. Verify test account meets minimum data requirements
2. Try with a different test account
3. Compare recommendations to original analyzer logic in `archive/old_app/`
4. Report discrepancy as potential bug

### Issue: MCP tool errors

**Example Error**: `Error calling get_keywords: Permission denied`

**Fix**:
1. Verify Google Ads API access is configured
2. Check MCP server has correct credentials
3. Ensure customer ID has appropriate access level
4. Review MCP server logs for detailed error

---

## Test Results Documentation

### Create Test Report

For each skill, document:

```markdown
## [Skill Name] Test Results

**Test Date**: [Date]
**Tester**: [Your Name]
**Test Account**: [Customer ID] (anonymized)
**Account Size**: [Small/Medium/Large]

### Execution
- Load Method: [Packaged / Direct Prompt]
- Completion Time: [seconds]
- MCP Errors: [None / List errors]

### Output Quality
- Markdown Formatting: ✅/❌
- Content Completeness: ✅/❌
- Business Logic: ✅/❌

### Recommendations Sample
- Number of Recommendations: [X]
- Top Recommendation: [Brief description]
- Estimated Impact: $[amount] or [percentage]

### Issues Found
- [List any issues, or "None"]

### Overall Assessment
- Status: ✅ PASS / ❌ FAIL
- Notes: [Any additional observations]
```

### Aggregate Test Report

After testing all skills:

```markdown
# Cost Efficiency Suite - Manual Test Results

**Test Date**: [Date]
**Total Test Time**: [minutes]

## Skills Tested

1. KeywordMatchAnalyzer: ✅ PASS
2. SearchTermAnalyzer: ✅ PASS
3. NegativeConflictAnalyzer: ✅ PASS
4. GeoPerformanceAnalyzer: ✅ PASS
5. PMaxAnalyzer: ✅ PASS

## Integration Test
- Full Audit Workflow: ✅ PASS
- Total Time: [minutes]
- Combined Results: Realistic and actionable

## Issues Found
[List any issues]

## Recommendations for Improvement
[Any suggestions]

## Approval
- Ready for Production: ✅ YES / ❌ NO
- Tested By: [Name]
- Date: [Date]
```

---

## Next Steps After Manual Testing

1. **Document results** in test report
2. **Fix any issues** found during testing
3. **Create automated tests** based on manual test cases
4. **Update plan** with test completion checkmarks
5. **Prepare for production deployment**

---

## Quick Test Checklist

Use this for rapid testing:

**Per Skill** (5 minutes each):
- [ ] Load skill successfully
- [ ] Run test prompt
- [ ] Completes in <30 seconds
- [ ] Output is markdown formatted
- [ ] Recommendations make business sense
- [ ] Implementation guide is clear

**Integration Test** (15 minutes):
- [ ] Run all 5 skills in sequence
- [ ] Total time <5 minutes
- [ ] Combined results are reasonable
- [ ] No conflicting recommendations

**Total Time**: ~40 minutes for complete manual test suite

---

Good luck with testing! Report any issues you find to the development team.
