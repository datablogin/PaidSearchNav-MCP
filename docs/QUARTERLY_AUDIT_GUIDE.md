# Quarterly Google Ads Audit Guide

## Overview
This guide provides step-by-step instructions for conducting a complete quarterly Google Ads audit using the PaidSearchNav Cost Efficiency Suite.

## Audit Objectives

1. **Eliminate Wasted Spend** - Identify and stop spending on non-converting searches
2. **Recover Lost Impressions** - Fix conflicts blocking high-performing keywords
3. **Optimize Match Types** - Convert to exact match where appropriate for cost control
4. **Improve Geographic Targeting** - Adjust bids based on location performance
5. **Prevent Cannibalization** - Stop PMax from stealing Search traffic at higher CPAs

**Expected Results**: 20-35% reduction in wasted spend, 15-30% ROAS improvement

---

## Prerequisites

### Data Requirements
- ✅ Minimum 90 days of campaign history
- ✅ At least $1,000 total spend in analysis period
- ✅ Active campaigns (not paused)

### Technical Requirements
- ✅ Claude Desktop or API access
- ✅ PaidSearchNav MCP server connected
- ✅ Google Ads account access configured
- ✅ All 5 Cost Efficiency Suite skills loaded

### Time Requirements
- **Analysis**: 45-90 minutes
- **Implementation**: 2-4 hours
- **Monitoring**: 2 weeks

---

## Audit Workflow

### Week 0: Preparation

**Day 1-2: Data Collection**
1. Verify MCP server is connected to Google Ads
2. Confirm date range: Use full previous quarter (90 days)
3. Export current performance benchmarks:
   - Overall account CPA, ROAS, conversion rate
   - Impression share by campaign
   - Top 20 keywords by spend

**Day 3: Baseline Documentation**
- Document current performance metrics
- Take screenshots of key reports
- Note any recent major changes (new campaigns, budget changes, etc.)

---

### Week 1: Analysis

Run all 5 skills in sequence. Each produces a detailed report with recommendations.

#### Monday: KeywordMatchAnalyzer

**Prompt**:
```
Analyze keyword match types for customer ID [CUSTOMER_ID]
from [START_DATE] to [END_DATE] and identify exact match opportunities.
```

**What to Look For**:
- Keywords with >70% impression concentration on one search term
- High-performing broad/phrase keywords ready for exact match
- Estimated savings from match type conversion

**Expected Output**:
- 10-30 exact match opportunities
- $1,500-5,000/month potential savings
- Specific conversion recommendations

**Action Items**:
- Review top 10 recommendations
- Verify search term data supports conversion
- Flag for implementation (don't implement yet)

---

#### Tuesday: SearchTermAnalyzer

**Prompt**:
```
Analyze search terms for customer ID [CUSTOMER_ID]
from [START_DATE] to [END_DATE] and identify negative keyword opportunities.
```

**What to Look For**:
- Zero-conversion search terms with >$50 spend
- Irrelevant intent patterns (jobs, free, DIY)
- Low CTR queries (<1%) with high impressions

**Expected Output**:
- 50-150 negative keyword recommendations
- Breakdown by level (Account, Campaign, Ad Group)
- $2,000-7,000/month potential savings

**Action Items**:
- Start with account-level shared list negatives (highest impact)
- Verify terms are truly irrelevant (check brand, local intent)
- Prioritize critical recommendations (>$200 waste each)

---

#### Wednesday: NegativeConflictAnalyzer

**Prompt**:
```
Analyze negative keyword conflicts for customer ID [CUSTOMER_ID]
and identify which negatives are blocking high-value keywords.
```

**What to Look For**:
- Critical conflicts (>10 conversions blocked)
- Shared list conflicts (affect all campaigns)
- Broad match negatives blocking multiple positives

**Expected Output**:
- 10-50 conflicts identified
- Severity assessment (Critical, High, Medium, Low)
- 5-10% impression share recovery potential

**Action Items**:
- Fix critical conflicts immediately (top 5)
- Review shared negative lists for overly broad terms
- Plan to replace broad negatives with phrase/exact

---

#### Thursday: GeoPerformanceAnalyzer

**Prompt**:
```
Analyze geographic performance for customer ID [CUSTOMER_ID]
from [START_DATE] to [END_DATE] and recommend location bid adjustments.
```

**What to Look For**:
- Locations with ROAS >2x account average (bid up)
- Locations with ROAS <0.5x account average (bid down or exclude)
- Zero-conversion locations with >$500 spend (exclude)

**Expected Output**:
- 15-40 location bid adjustment recommendations
- 3-10 location exclusions
- 15-25% ROAS improvement potential

**Action Items**:
- Verify store proximity for retail businesses
- Check if poor locations have legitimate business reasons
- Plan bid adjustments in 10% increments

---

#### Friday: PMaxAnalyzer

**Prompt**:
```
Analyze Performance Max cannibalization for customer ID [CUSTOMER_ID]
and recommend negative keywords to improve efficiency.
```

**What to Look For**:
- Search terms where PMax CPA >30% higher than Search
- High-intent keywords being stolen by PMax
- Brand terms in PMax (should be Search-only)

**Expected Output**:
- 20-60 overlapping search terms
- PMax negative keyword recommendations
- 10-20% CPA improvement potential

**Action Items**:
- Add brand terms as PMax negatives immediately
- Review "near me" terms (usually better in Search)
- Plan to refocus PMax on Display/YouTube

---

### Week 2: Implementation

#### Monday-Tuesday: High-Priority Changes

**Priority 1: Fix Critical Conflicts** (NegativeConflictAnalyzer)
- Remove negatives blocking high-value keywords
- Expected time: 30 minutes
- Impact: Immediate impression share recovery

**Priority 2: Add Account-Level Negatives** (SearchTermAnalyzer)
- Create or update shared negative keyword list
- Add 15-30 most impactful negatives
- Expected time: 45 minutes
- Impact: Immediate cost savings

**Priority 3: Add PMax Negatives** (PMaxAnalyzer)
- Add brand terms and high-intent keywords as PMax negatives
- Expected time: 30 minutes
- Impact: Stop cannibalization immediately

#### Wednesday-Thursday: Medium-Priority Changes

**Priority 4: Convert to Exact Match** (KeywordMatchAnalyzer)
- Add exact match versions of top 10 recommendations
- Optionally pause broad/phrase versions
- Expected time: 1 hour
- Impact: Cost control, better targeting

**Priority 5: Location Bid Adjustments** (GeoPerformanceAnalyzer)
- Implement top 10 bid adjustments
- Start with ±20%, can increase to ±50% later
- Expected time: 45 minutes
- Impact: ROAS improvement

#### Friday: Remaining Changes

**Priority 6: Campaign/Ad Group Negatives** (SearchTermAnalyzer)
- Add campaign-specific and ad group-specific negatives
- Expected time: 1-2 hours
- Impact: Precision targeting

**Priority 7: Additional Match Type Conversions** (KeywordMatchAnalyzer)
- Convert remaining recommended keywords
- Expected time: 1 hour
- Impact: Incremental improvements

---

### Week 3-4: Monitoring

#### Daily Checks (First 7 Days)
- Impression share changes
- CPA trends
- Conversion volume (ensure not over-blocked)
- Search terms report (check for new waste)

#### Weekly Review
- Compare to baseline metrics
- Verify savings match estimates
- Identify any issues (over-blocking, lost traffic)
- Adjust as needed

#### Week 4: Results Documentation
- Calculate actual savings vs estimated
- Document lessons learned
- Update audit playbook with account-specific insights
- Schedule next quarterly audit

---

## Implementation Checklist

### Before Making Changes
- [ ] Export current negative keyword lists (backup)
- [ ] Document baseline performance metrics
- [ ] Take screenshots of key reports
- [ ] Create change log document

### Making Changes
- [ ] Fix critical negative conflicts (Day 1)
- [ ] Add account-level shared negatives (Day 1)
- [ ] Add PMax negatives for brand/high-intent terms (Day 1)
- [ ] Convert top 10 keywords to exact match (Day 2)
- [ ] Implement top 10 location bid adjustments (Day 2)
- [ ] Add campaign-level negatives (Day 3)
- [ ] Add ad group-level negatives (Day 3)
- [ ] Convert remaining keyword match types (Day 4)
- [ ] Implement remaining location adjustments (Day 4)
- [ ] Document all changes in change log

### Monitoring (Days 5-14)
- [ ] Check impression share daily
- [ ] Monitor conversion volume daily
- [ ] Review search terms report weekly
- [ ] Verify cost savings weekly
- [ ] Adjust if over-blocking detected

### Results (Day 30)
- [ ] Measure actual vs estimated savings
- [ ] Calculate ROI on audit
- [ ] Document lessons learned
- [ ] Update playbook with insights
- [ ] Schedule next quarterly audit

---

## Expected Results Timeline

### Week 1 (Days 1-7)
- **Cost Savings**: 10-15% (from negatives and conflict fixes)
- **Impression Share**: +5-10% (from conflict fixes)
- **CPA**: -5-10% (from negatives and PMax fixes)

### Week 2 (Days 8-14)
- **Cost Savings**: 15-25% (match type conversions kicking in)
- **ROAS**: +10-15% (location adjustments working)
- **CPA**: -10-15% (combined effects)

### Week 4 (Days 15-30)
- **Cost Savings**: 20-35% (full implementation impact)
- **ROAS**: +15-30% (optimized geo targeting)
- **CPA**: -15-25% (all optimizations combined)
- **Impression Share**: +10-20% (conflicts fixed, no over-blocking)

### Quarter 2 and Beyond
- Run audit quarterly
- Expect 5-10% incremental improvements each quarter
- Diminishing returns after 2-3 audits (account becomes well-optimized)

---

## Troubleshooting

### Issue: Conversions Dropped After Implementation
**Cause**: Likely over-blocked with negatives
**Fix**:
1. Review negative keywords added
2. Check for broad match negatives blocking good terms
3. Remove overly aggressive negatives
4. Re-run NegativeConflictAnalyzer to find new conflicts

### Issue: No Cost Savings Detected
**Cause**: Recommendations not implemented correctly
**Fix**:
1. Verify all changes were actually saved in Google Ads
2. Check that shared negative lists were applied to campaigns
3. Ensure sufficient time has passed (7 days minimum)
4. Re-run SearchTermAnalyzer to verify negative terms stopped triggering

### Issue: Impression Share Decreased
**Cause**: Negatives were too aggressive or budget wasn't reallocated
**Fix**:
1. Check which keywords lost impression share
2. Review if negative keywords are blocking them
3. Increase budgets for high-performing campaigns
4. Remove negatives if needed

### Issue: PMax Still Cannibalizing
**Cause**: Negatives not added correctly to PMax asset groups
**Fix**:
1. Verify negatives were added to asset groups (not campaign)
2. Use exact match negatives for specificity
3. Wait 7-14 days for PMax learning to adjust
4. Consider reducing PMax budget if severe

---

## Best Practices

### Do's
✅ Document everything - changes, results, insights
✅ Start conservative - can always add more negatives later
✅ Monitor daily for first week
✅ Implement high-priority changes first
✅ Verify changes in Google Ads UI (don't just trust MCP)
✅ Keep a change log with dates and reasoning

### Don'ts
❌ Don't implement all changes at once (hard to diagnose issues)
❌ Don't add single-word broad match negatives (too aggressive)
❌ Don't forget to check brand/local terms before blocking
❌ Don't skip monitoring phase (critical for catching problems)
❌ Don't expect instant results (allow 7-14 days)
❌ Don't ignore conversion volume drops (means over-blocking)

---

## Advanced Tips

### For Large Accounts (>$50K/month spend)
- Run audit monthly instead of quarterly
- Implement changes in batches (one campaign at a time)
- Use A/B testing for major changes
- Consider dedicated analyst for ongoing optimization

### For Seasonal Businesses
- Run audit at start of peak season (3-4 weeks before)
- Use 12 months of data to account for seasonality
- Be conservative with negatives that might be seasonal

### For Multi-Location Businesses
- Run GeoPerformanceAnalyzer first (highest impact)
- Analyze by store location, not just DMA
- Correlate performance with store opening dates
- Consider radius targeting around top locations

---

## Next Steps

After completing your first audit:
1. Schedule quarterly audits (recurring calendar event)
2. Create account-specific playbook with learnings
3. Train team members on process
4. Consider automating monthly checks for critical metrics
5. Share results with stakeholders (show ROI)

---

## Support

- **Questions**: Create GitHub issue with tag `quarterly-audit`
- **Skill Issues**: See individual skill README files
- **MCP Server Issues**: Check server logs and documentation

---

**Remember**: The goal is continuous improvement, not perfection. Each quarterly audit builds on the last, making your account progressively more efficient.
