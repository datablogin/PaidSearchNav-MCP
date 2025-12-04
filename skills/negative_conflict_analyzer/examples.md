# Negative Conflict Analyzer Examples

## Example 1: E-commerce Retailer - Running Shoes

### Scenario
Account selling athletic footwear with aggressive negative keyword strategy causing conflicts.

### Input Data
- **Positive Keywords**: 342 active
- **Negative Keywords**: 1,247 (87 shared, 640 campaign-level, 520 ad group-level)
- **Date Range**: Last 90 days

### Sample Conflicts

| Positive Keyword | Match | Conversions | Value | Blocking Negative | Negative Match | Level | Severity |
|------------------|-------|-------------|-------|-------------------|----------------|-------|----------|
| blue running shoes | Phrase | 15 | $1,650 | running | Broad | Campaign | CRITICAL |
| women's athletic shoes | Phrase | 12 | $1,320 | athletic | Broad | Shared | CRITICAL |
| nike running sneakers | Exact | 8 | $960 | sneakers | Broad | Campaign | HIGH |
| trail running shoes waterproof | Phrase | 6 | $720 | waterproof | Broad | Ad Group | HIGH |

### Analysis Output

# Negative Keyword Conflict Report

## Executive Summary

- **Positive Keywords Analyzed**: 342
- **Negative Keywords Analyzed**: 1,247
- **Total Conflicts Found**: 47
- **Critical Conflicts**: 12
- **High-Priority Conflicts**: 18
- **Estimated Monthly Revenue Loss**: $8,430

### Key Findings
- Shared negative list causing 58% of critical conflicts
- Single-word broad match negatives are primary issue
- Top 5 conflicts account for $4,920 (58%) of revenue loss

---

## Critical Conflicts (12 total)

### 1. "women's athletic shoes" blocked by "athletic"

**Positive Keyword**: women's athletic shoes
- **Match Type**: Phrase
- **Conversions**: 12 conversions
- **Conv. Value**: $1,320
- **Quality Score**: 9
- **Impression Share**: 28% (should be 60%+)

**Blocking Negative**: "athletic"
- **Match Type**: Broad
- **Level**: Account-level shared list "Irrelevant Terms"
- **Reason Added**: To block "athletic events", "athletic clubs"

**Impact**:
- Revenue Lost: $1,320/month
- Conversions Lost: 12/month
- Impression share reduced by ~40%

**Resolution**:
1. ✅ **Recommended**: Remove broad "athletic" from shared list
   - Add specific phrase negatives: "athletic events", "athletic clubs", "athletic scholarships"
   - Precision targeting without blocking product terms
2. ⚠️ Alternative: Change to phrase match "athletic events"
3. ❌ Not recommended: Keep as-is (losing too much revenue)

---

### 2. "blue running shoes" blocked by "running"

**Positive Keyword**: blue running shoes
- **Match Type**: Phrase
- **Conversions**: 15
- **Conv. Value**: $1,650
- **Quality Score**: 8

**Blocking Negative**: "running"
- **Match Type**: Broad
- **Level**: Campaign "Running Shoes"

**Impact**: $1,650/month lost

**Resolution**:
1. ✅ Remove broad "running"
2. ✅ Add phrase negatives: "running clubs", "running events", "running coaching"

[Continue for remaining 10 critical conflicts...]

---

## High-Priority Conflicts (18 total)

### Top 5 by Revenue Impact

1. **nike running sneakers** ($960/mo) - Blocked by broad "sneakers"
2. **trail running shoes waterproof** ($720/mo) - Blocked by broad "waterproof"
3. **lightweight running shoes women** ($640/mo) - Blocked by broad "lightweight"
4. **cushioned running shoes** ($580/mo) - Blocked by broad "cushioned"
5. **stability running shoes** ($520/mo) - Blocked by phrase "running shoes" (!)

---

## Conflict Analysis by Level

### Account-Level Shared Lists (27 conflicts, $4,890 revenue loss)

**Shared List**: "Irrelevant Terms"
- Applied to: All campaigns (15 campaigns)
- Conflicts: 27
- Revenue Lost: $4,890/month

**Problem Negatives**:
| Negative | Type | Conflicts | Revenue Lost | Fix |
|----------|------|-----------|--------------|-----|
| athletic | Broad | 8 | $1,820 | Change to phrase "athletic events" |
| shoes | Broad | 6 | $1,240 | Remove (too broad) |
| running | Broad | 5 | $1,130 | Change to specific phrases |
| women | Broad | 4 | $490 | Change to "women's jobs" |
| waterproof | Broad | 4 | $210 | Change to "waterproof boots" |

**Recommended Actions**:
1. Remove "shoes" entirely (way too broad for shoe retailer!)
2. Make all others phrase match with specific intent
3. Consider separate shared lists for different campaign types

---

### Campaign-Level Negatives (15 conflicts, $2,670 revenue loss)

**Campaign**: "Running Shoes - Women's"
- Conflicts: 8
- Revenue Lost: $1,540/month

**Problem Pattern**: Overly aggressive single-word broad negatives
- "running" blocking "women's running shoes"
- "sneakers" blocking "women's running sneakers"
- "training" blocking "women's training shoes"

**Fix**: Replace broad single-word negatives with phrase match 2-3 word negatives targeting actual irrelevant intent.

---

### Ad Group-Level Negatives (5 conflicts, $870 revenue loss)

**Ad Group**: "Blue Running Shoes"
- Conflicts: 3
- Lower priority (ad group-specific, easier to fix)

---

## Resolution Recommendations

### Immediate Actions (This Week)

#### 1. Fix Shared List "Irrelevant Terms"
**Impact**: Recover $4,890/month (58% of total loss)

Steps:
1. Go to Tools & Settings → Shared Library → Negative keyword lists
2. Click "Irrelevant Terms"
3. Remove: "athletic", "shoes", "running", "women"
4. Add phrase match replacements:
   - "athletic events"
   - "athletic clubs"
   - "athletic scholarships"
   - "running clubs"
   - "running events"
   - "marathon training"
   - "women's jobs"
   - "women's rights"
5. Save changes
6. Monitor for 7 days - verify no irrelevant traffic spike

#### 2. Fix Top 3 Campaign Conflicts
**Impact**: Recover $2,330/month

**Campaign: "Running Shoes"**:
- Remove broad "running"
- Add phrases: "running clubs", "running events", "running coaching"

**Campaign: "Athletic Footwear"**:
- Remove broad "athletic" (handled by shared list fix)

**Campaign: "Women's Shoes"**:
- Remove broad "women"
- Add "women's jobs", "women's basketball" (if not selling that)

---

### Week 2-4 Actions (High-Priority)

Review and fix remaining 18 high-priority conflicts:
- Focus on campaign-level negatives
- Pattern: Most are overly broad single-word negatives
- Solution: Replace with 2-3 word phrase negatives targeting actual bad intent

---

### Monthly Audit (Medium/Low Priority)

- Review ad group-level conflicts (lower urgency)
- Validate shared list effectiveness
- Check for new conflicts from recent negative additions

---

## Expected Results

### Immediate Impact (7-14 days)
- Impression share increase: +15-25% on affected keywords
- Clicks increase: +20-30% on previously blocked keywords
- Conversions increase: +12-18 conversions/month
- Revenue increase: $8,000-10,000/month

### Quality Score Impact (30-60 days)
- Better impression share → higher CTR → improved Quality Score
- Expected QS improvement: +0.5 to +1.5 points on affected keywords
- Lower CPCs from better QS: 5-8% reduction

### Long-term Benefits
- Smarter negative keyword strategy (phrase/exact vs broad)
- Less conflict risk from future negative additions
- Better campaign performance from full keyword participation

---

## Implementation Checklist

**Before Making Changes**:
- [ ] Export current negative keyword lists (backup)
- [ ] Document current performance metrics (impressions, clicks, conversions)
- [ ] Take screenshots of impression share for affected keywords
- [ ] Note current Quality Scores

**Making Changes**:
- [ ] Fix shared list "Irrelevant Terms" (highest impact)
- [ ] Update top 3 campaign negatives
- [ ] Document all changes in change log

**After Changes (7 days)**:
- [ ] Monitor search terms report for irrelevant traffic
- [ ] Check impression share improvement
- [ ] Verify conversion increase
- [ ] Adjust if needed (re-add more specific negatives)

**30-Day Review**:
- [ ] Measure actual revenue recovery
- [ ] Check Quality Score changes
- [ ] Re-run conflict analysis
- [ ] Document lessons learned

---

## Lessons Learned

### Anti-Patterns to Avoid

1. **Single-word broad match negatives**
   - "shoes" in a shoe retailer account ❌
   - "running" in a running shoe campaign ❌
   - Always use 2+ words or phrase match

2. **Overly aggressive shared lists**
   - Applying one shared list to ALL campaigns ❌
   - Create campaign-type-specific shared lists instead ✅

3. **Not checking conflicts before adding negatives**
   - Always search existing keywords before adding negative ✅
   - Use preview tool to see what will be blocked

### Best Practices

1. **Phrase match by default**
   - More precise than broad
   - Less likely to block good keywords
   - Example: "running clubs" instead of "running"

2. **2-3 word negatives**
   - "athletic events" not "athletic"
   - "women's jobs" not "women"
   - Targets specific bad intent

3. **Regular conflict audits**
   - Quarterly minimum
   - After bulk negative keyword additions
   - When impression share drops unexpectedly

4. **Test before scaling**
   - Add negatives to one campaign first
   - Monitor for 7 days
   - If no issues, apply to others

---

This example demonstrates how a well-intentioned negative keyword strategy can backfire when using overly broad terms. The fix is straightforward but high-impact: replace broad single-word negatives with specific 2-3 word phrase match negatives that target actual irrelevant intent.
