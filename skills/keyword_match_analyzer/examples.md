# Keyword Match Type Analysis Examples

This document provides concrete examples showing expected inputs and outputs for the Keyword Match Analyzer skill.

## Example 1: Clear Exact Match Opportunity

### Input Data

**Keywords from MCP `get_keywords`**:
```json
{
  "status": "success",
  "data": [
    {
      "keyword": "running shoes",
      "match_type": "BROAD",
      "impressions": 10000,
      "clicks": 450,
      "cost_micros": 22500000,
      "conversions": 45,
      "conversion_value_micros": 4500000,
      "quality_score": 8,
      "campaign_name": "Footwear - General",
      "ad_group_name": "Running Shoes"
    }
  ]
}
```

**Search Terms from MCP `get_search_terms`**:
```json
{
  "status": "success",
  "data": [
    {
      "search_term": "running shoes",
      "keyword": "running shoes",
      "impressions": 7500,
      "clicks": 380,
      "cost_micros": 19000000,
      "conversions": 40
    },
    {
      "search_term": "best running shoes",
      "keyword": "running shoes",
      "impressions": 1500,
      "clicks": 45,
      "cost_micros": 2250000,
      "conversions": 3
    },
    {
      "search_term": "cheap running shoes",
      "keyword": "running shoes",
      "impressions": 1000,
      "clicks": 25,
      "cost_micros": 1250000,
      "conversions": 2
    }
  ]
}
```

### Expected Analysis Output

```markdown
## HIGH Priority Recommendation: Convert "running shoes" to Exact Match

**Impact**: $1,050/month savings potential

**Analysis**:
- Current match type: BROAD
- Total spend: $225.00 (90 days) = $75/month
- Primary search term: "running shoes" (exact) captures 75% of impressions
- Performance split:
  - Exact matches: CPA $47.50, Conversion rate 10.5%
  - Variant matches: CPA $87.50, Conversion rate 5.7%

**Why this matters**:
The keyword "running shoes" in broad match is triggering mostly exact match queries anyway (75% of traffic). The remaining 25% of traffic from variants like "best running shoes" and "cheap running shoes" has nearly 2× higher CPA and much lower conversion rates.

**Recommended Action**:
1. Add new keyword: `[running shoes]` (EXACT match)
2. Set initial bid: $0.50 (current avg CPC)
3. Monitor for 7 days
4. If performing well, pause broad match version
5. Add variants as phrase match if needed: `"best running shoes"`

**Expected Results**:
- Monthly savings: ~$1,050 (eliminating low-performing variant traffic)
- Conversion rate improvement: Expect ~8-10% from focusing on exact matches
- Small impression share reduction: 5-8% (acceptable trade-off)

**Risk Level**: Low
- Won't lose primary traffic (exact match queries will still trigger)
- Easy to rollback if needed
- Conservative estimate assumes 50% of variant spend is recoverable
```

---

## Example 2: Do NOT Recommend (Insufficient Data)

### Input Data

```json
{
  "keyword": "athletic footwear",
  "match_type": "PHRASE",
  "impressions": 500,
  "clicks": 15,
  "cost_micros": 750000,
  "conversions": 1,
  "quality_score": 7
}
```

### Expected Output

```markdown
## Keywords Excluded from Analysis

### "athletic footwear" - Insufficient Click Volume

**Reason**: Only 15 clicks in 90-day period (minimum threshold: 100 clicks)

**Current Performance**:
- Impressions: 500
- Clicks: 15 (CTR: 3.0%)
- Cost: $7.50
- Conversions: 1 (CPA: $7.50)

**Recommendation**: Continue monitoring

**Why no action**:
With only 15 clicks, we don't have enough data to make a confident optimization decision. The keyword appears to be performing well (low CPA), but the sample size is too small to draw conclusions.

**Next Steps**:
- Re-evaluate when keyword reaches 100+ clicks
- If keyword remains low-volume after 6 months, consider pausing
- For now, monitor quality score and maintain current match type
```

---

## Example 3: Multiple Issues (High-Cost Broad + Low Quality Score)

### Input Data

```json
{
  "keyword": "shoes",
  "match_type": "BROAD",
  "impressions": 50000,
  "clicks": 1200,
  "cost_micros": 60000000,
  "conversions": 10,
  "conversion_value_micros": 1000000,
  "quality_score": 4
}
```

### Expected Output

```markdown
## CRITICAL: High-Priority Issue with "shoes" Keyword

**Status**: 🚨 Immediate action required

**Multiple Problems Identified**:

### Issue 1: Extremely Broad Keyword with Poor Performance
- Match type: BROAD
- Keyword text: "shoes" (too generic)
- Cost: $600 (90 days) = $200/month
- Conversions: 10
- CPA: $60.00
- ROAS: 0.17 (losing money on every conversion!)

### Issue 2: Low Quality Score Increasing Costs
- Quality Score: 4/10
- Estimated CPC premium: 50-70% above QS 7+
- Cost impact: $100-140/month in unnecessary spend

### Root Cause Analysis

This keyword is problematic for multiple reasons:

1. **Too Broad**: "shoes" (no modifier) triggers irrelevant searches
   - Likely matching: dress shoes, kids shoes, basketball shoes, etc.
   - Your store sells: running shoes specifically
   - Result: Wasted impressions and clicks

2. **Poor Ad Relevance**: Low QS indicates ad copy doesn't match search intent
   - Generic keyword → Generic searches → Poor match with specific ads
   - Low expected CTR from irrelevant impressions

3. **Hemorrhaging Budget**: $200/month for only 10 conversions at negative ROAS

### Recommended Actions (in priority order)

**IMMEDIATE (Today)**:
1. ⏸️ **PAUSE this keyword immediately**
   - Savings: $200/month
   - Risk of pausing: Minimal (poor performer)

2. 📝 **Add negative keywords** to prevent similar issues:
   - Add "dress shoes" as negative
   - Add "kids shoes" as negative
   - Add "basketball shoes" as negative
   - (Anything outside your product category)

**Week 1**:
3. ✏️ **Replace with specific keywords**:
   - Add: `[running shoes]` (exact match)
   - Add: `"running shoes for men"` (phrase match)
   - Add: `"trail running shoes"` (phrase match)
   - Set bids 30% lower initially ($0.35 vs $0.50)

4. 🎯 **Improve quality score** for replacement keywords:
   - Ensure ad copy mentions "running shoes" explicitly
   - Use ad extensions (sitelinks to running shoe categories)
   - Verify landing page is running shoes specific

### Expected Results

**If you pause only**:
- Save: $200/month
- Lose: 10 conversions/month (but they weren't profitable anyway)

**If you pause + add specific keywords**:
- Save: $120/month (less ad waste)
- Gain: Better quality traffic from specific terms
- Expect: 15-20 conversions/month at profitable CPA
- Quality Score: Should reach 7+ with proper implementation

**Success Metrics (30 days after implementation)**:
- ✅ New keyword QS ≥ 7
- ✅ CPA < $30 (vs $60 previously)
- ✅ ROAS > 1.5 (vs 0.17 previously)
- ✅ Conversion volume maintained or improved
```

---

## Example 4: Duplicate Keywords Across Match Types

### Input Data

```json
[
  {
    "keyword": "running shoes",
    "match_type": "BROAD",
    "clicks": 450,
    "cost_micros": 22500000,
    "conversions": 45
  },
  {
    "keyword": "running shoes",
    "match_type": "PHRASE",
    "clicks": 280,
    "cost_micros": 11200000,
    "conversions": 35
  },
  {
    "keyword": "running shoes",
    "match_type": "EXACT",
    "clicks": 150,
    "cost_micros": 6000000,
    "conversions": 20
  }
]
```

### Expected Output

```markdown
## MEDIUM Priority: Consolidate "running shoes" Duplicate Keywords

**Issue**: Same keyword exists in BROAD, PHRASE, and EXACT match types

**Current Performance by Match Type**:

| Match Type | Clicks | Cost | Conversions | CPA | Conversion Rate |
|------------|--------|------|-------------|-----|-----------------|
| EXACT      | 150    | $60  | 20          | $3.00 | 13.3% |
| PHRASE     | 280    | $112 | 35          | $3.20 | 12.5% |
| BROAD      | 450    | $225 | 45          | $5.00 | 10.0% |

**Analysis**:

The exact and phrase match versions significantly outperform broad:
- EXACT CPA: $3.00
- PHRASE CPA: $3.20
- BROAD CPA: $5.00 (67% higher than exact!)

**Why this is wasteful**:
1. All three keywords compete with each other in the same auction
2. Google Ads prioritizes more specific match types, BUT:
   - Broad still captures "leaked" impressions
   - These leaked impressions are lower quality
3. Budget is spread thin across all three

**Recommended Consolidation**:

**Option A: Keep EXACT only (Most Conservative)**
- Pause: BROAD and PHRASE
- Expected impact:
  - Lose ~15% impression share
  - Save: ~$110/month (from eliminating higher-CPA traffic)
  - Maintain: Most profitable traffic

**Option B: Keep EXACT + PHRASE (Balanced)**
- Pause: BROAD only
- Keep: EXACT and PHRASE (complementary)
- Expected impact:
  - Lose ~5% impression share
  - Save: ~$90/month
  - Maintain: 90%+ of current conversions

**Option C: Test & Learn (Recommended)**
1. Week 1-2: Pause BROAD, monitor EXACT and PHRASE
2. If impression share drops >10%, re-enable PHRASE
3. After 30 days, determine optimal configuration

**Implementation Steps**:

1. Set BROAD keyword status to "Paused"
2. Monitor daily for first week:
   - Check impression share (should stay >85%)
   - Verify CPA remains <$4.00
   - Watch conversion volume
3. After 7 days:
   - If conversions dropped >20%: Re-enable BROAD at lower bid
   - If conversions stable: Keep paused, enjoy savings
4. Re-evaluate in 30 days

**Expected Monthly Savings**: $90-110 (based on Option B or A)

**Risk**: Low
- Easy to rollback if needed
- Won't lose exact match traffic (highest priority)
- PHRASE provides safety net for variants
```

---

## Example 5: Good Performance (No Changes Needed)

### Input Data

```json
{
  "keyword": "trail running shoes waterproof",
  "match_type": "PHRASE",
  "impressions": 2500,
  "clicks": 180,
  "cost_micros": 7200000,
  "conversions": 22,
  "conversion_value_micros": 2640000,
  "quality_score": 9
}
```

### Expected Output

```markdown
## ✅ Well-Optimized Keyword: "trail running shoes waterproof"

**Status**: No action needed - Continue monitoring

**Performance Summary**:
- Match Type: PHRASE (appropriate for specific, long-tail keyword)
- Quality Score: 9/10 (excellent)
- CTR: 7.2% (above average)
- CPA: $32.73
- ROAS: 3.67 (strong profitability)
- Conversion Rate: 12.2%

**Why this is performing well**:

1. **Specific keyword**: 4-word phrase targets high-intent shoppers
2. **Appropriate match type**: PHRASE allows variants while maintaining relevance
3. **High quality score**: Indicates excellent ad/landing page relevance
4. **Strong ROAS**: Every dollar spent generates $3.67 in revenue

**Monitoring Recommendations**:

- ✅ Current strategy: Keep as-is
- 📊 Monitor: Ensure QS stays ≥8
- 🔍 Consider: If performance stays strong for 60+ days, increase bid by 10-15% to capture more impression share
- 🎯 Expand: Look for similar long-tail, specific keywords

**Similar Keywords to Consider Adding**:
- "gore tex trail running shoes" (phrase)
- "waterproof hiking shoes" (phrase)
- "trail shoes for wet conditions" (phrase)

These would follow the same successful pattern: specific, high-intent, phrase match.
```

---

## Key Patterns to Notice

### When to Recommend Exact Match Conversion
- ✅ Search term concentration: >70% from one exact variant
- ✅ Minimum volume: >100 clicks
- ✅ Clear performance difference between exact and broad traffic
- ❌ Don't recommend if: Keyword needs broad reach (brand terms, informational)

### When to Pause Keywords
- ✅ Zero conversions with >$100 spend
- ✅ ROAS <0.5 (losing significant money)
- ✅ Quality Score <4 and high spend
- ❌ Don't pause if: Keyword is new (<30 days) or seasonal

### When to Consolidate Duplicates
- ✅ Same keyword in multiple match types
- ✅ Clear performance winner (CPA difference >30%)
- ✅ Sufficient data in all match types
- ❌ Don't consolidate if: Match types serve different purposes

### When to Leave Alone
- ✅ Quality Score ≥8
- ✅ ROAS >2.0
- ✅ CPA below target
- ✅ Match type appropriate for keyword specificity
