# Search Term Analyzer Claude Skill

## Overview

The Search Term Analyzer is a Claude skill designed to identify wasted spend on irrelevant search terms in Google Ads campaigns and recommend negative keywords to eliminate budget waste.

## Business Value

- **Typical Impact**: 15-20% reduction in wasted ad spend
- **Average Monthly Savings**: $1,500 - $7,000 for mid-sized accounts
- **Use Frequency**: Quarterly audits + on-demand for performance issues
- **ROI**: High - directly eliminates non-converting spend

## What It Does

### Primary Functions

1. **Identifies Wasted Spend**
   - Search terms with high cost and zero conversions
   - Low-relevance queries (CTR <1%)
   - Irrelevant intent patterns (jobs, free, DIY, etc.)

2. **Recommends Negative Keywords**
   - Account-level (shared lists) for broad irrelevance
   - Campaign-level for campaign-specific waste
   - Ad group-level for granular optimization

3. **Mines Opportunities**
   - High-converting search terms not in keyword list
   - Patterns suggesting new exact/phrase match additions

4. **Intent Classification**
   - TRANSACTIONAL: Buying intent
   - INFORMATIONAL: Research/learning
   - NAVIGATIONAL: Brand/site seeking
   - LOCAL: Location-based searches

## Required MCP Tools

This skill requires connection to the PaidSearchNav MCP server with these tools:

- `get_search_terms` - Fetches search term performance data
- `get_negative_keywords` - Retrieves existing negative keyword lists

## How to Use

### Prerequisites

1. Install Claude Desktop or Claude API access
2. Connect PaidSearchNav MCP server
3. Have Google Ads account access via MCP server

### Loading the Skill

**Option 1: Direct Prompt** (Recommended)
1. Copy the contents of `prompt.md` and `examples.md`
2. Paste into Claude conversation
3. Claude will now operate as a Search Term Analyzer

**Option 2: Skill Package** (When available)
1. Upload the `.zip` package to Claude
2. Reference the skill in your conversation

### Example Usage

```
Analyze search terms for customer ID 1234567890
for the last 90 days and identify negative keyword
opportunities.
```

Claude will:
1. Fetch search term data via MCP
2. Analyze performance and intent
3. Identify waste patterns
4. Generate prioritized negative keyword recommendations
5. Provide implementation guide

### Sample Output

```markdown
# Search Term Waste Analysis

## Executive Summary
- Total Search Terms: 1,247
- Wasted Spend: $4,780
- Negative Keyword Recommendations: 127
- Estimated Monthly Savings: $1,593

## Critical Negative Keywords
[Priority-ranked table of waste terms]

## Negative Keyword Recommendations by Level
- Account-Level: 18 terms ($892/mo savings)
- Campaign-Level: 32 terms ($401/mo savings)
- Ad Group-Level: 77 terms ($156/mo savings)

## Implementation Guide
[Step-by-step instructions]
```

## Key Features

### Intelligence Layers

1. **Pattern Recognition**
   - Pre-compiled regex patterns for intent classification
   - Identifies irrelevant queries (jobs, free, DIY)
   - Detects informational vs transactional intent

2. **Performance Thresholds**
   - Zero conversion spend: >$50 cost, 0 conversions
   - Low relevance: CTR <1%, >100 impressions
   - High cost/low value: Cost >$100, negative ROAS

3. **Conflict Prevention**
   - Checks existing negative keywords
   - Validates against positive keywords (>80% similarity check)
   - Considers recent conversion activity (<7 days)

4. **Level Optimization**
   - Account-level: Broad irrelevance across all campaigns
   - Campaign-level: Campaign-specific waste
   - Ad group-level: Granular targeting issues

### Retail Business Optimization

This skill is optimized for retail businesses with physical locations:

- **Protects local intent searches** - "near me", store locations
- **Preserves location-based traffic** - High-converting for retail
- **Conservative with brand terms** - Even competitors can indicate purchase intent

## Best Practices

### When to Run

- **Quarterly audits** (recommended minimum)
- After major campaign changes
- When CPA increases unexpectedly
- Before budget increases (clean up waste first)
- After launching new products/campaigns

### Optimal Settings

- **Date Range**: 90 days minimum for statistical significance
- **Cost Threshold**: Adjust based on account size
  - Small accounts (<$5K/mo): $50 threshold
  - Medium accounts ($5K-$50K/mo): $100 threshold
  - Large accounts (>$50K/mo): $200 threshold

### Analysis Tips

1. **Start Conservative**
   - Implement account-level negatives first
   - Monitor for 7 days
   - Then add campaign/ad group negatives

2. **Seasonal Awareness**
   - Don't block terms during off-peak if they might convert during peak
   - Consider 12-month data for seasonal businesses

3. **Verification Steps**
   - Always check existing negatives first
   - Verify no positive keyword conflicts
   - Review location-based terms carefully

4. **Documentation**
   - Save the analysis report
   - Track savings over time
   - Re-run quarterly to measure improvement

## Performance Expectations

### Immediate Impact (7-14 days)
- Cost reduction: 8-12%
- Impression reduction: 10-15% (losing irrelevant impressions)
- Click reduction: 6-10% (losing low-quality clicks)
- CPA improvement: 5-8%

### Long-term Impact (30-60 days)
- Quality Score improvement: +0.5 to +1.5 points
- CPC reduction: 3-5% (from better Quality Scores)
- Conversion rate increase: 8-12% (more qualified traffic)
- Total ROAS improvement: 15-20%

## Technical Details

### Analysis Algorithms

**Intent Classification**:
- Uses pattern matching with pre-compiled regex
- Priority order: LOCAL > NAVIGATIONAL > INFORMATIONAL > TRANSACTIONAL
- Defaults to TRANSACTIONAL if no pattern matches

**Negative Keyword Identification**:
```
IF cost > threshold AND conversions = 0 THEN
  priority = CRITICAL
ELSE IF ctr < 1% AND impressions > 100 THEN
  priority = HIGH
ELSE IF irrelevant_pattern_match THEN
  priority = CRITICAL
```

**Level Determination**:
```
IF term_irrelevant_to_all_campaigns THEN
  level = ACCOUNT
ELSE IF term_irrelevant_to_one_campaign THEN
  level = CAMPAIGN
ELSE
  level = AD_GROUP
```

### Data Requirements

**Minimum for Reliable Analysis**:
- 90 days of search term data
- At least 100 search terms
- Minimum $1,000 total spend in analysis period

**Optimal Dataset**:
- 180 days of data (captures seasonality)
- 500+ search terms
- $10,000+ total spend

## Limitations

### What It Can't Do

- **Does not automatically implement negatives** - Requires manual implementation in Google Ads
- **Cannot access search term data for PMax campaigns** - Limited visibility by Google
- **Does not predict future performance** - Based on historical data only
- **Cannot detect all match type conflicts** - Manual review recommended for complex scenarios

### Edge Cases

1. **Low Volume Accounts**: Requires minimum 100 search terms for statistical significance
2. **Brand New Campaigns**: Wait 30 days minimum before analyzing
3. **Seasonal Businesses**: May need 12-month data for accurate patterns
4. **Multi-Language Accounts**: Intent patterns optimized for English

## Troubleshooting

### Common Issues

**Issue**: "No search terms found"
- **Cause**: Date range too short or new account
- **Solution**: Extend date range to 90+ days

**Issue**: "All terms flagged as negative"
- **Cause**: Thresholds too aggressive for account size
- **Solution**: Increase cost threshold, review recommendations manually

**Issue**: "Local terms flagged as negative"
- **Cause**: Algorithm not detecting local intent
- **Solution**: Review "near me" and location terms carefully before implementing

**Issue**: "Savings estimates seem high"
- **Cause**: Estimates assume 100% of waste can be eliminated
- **Solution**: Expect 60-80% of estimated savings in practice

## Version History

- **1.0.0** (Current)
  - Initial release
  - Intent classification
  - Multi-level negative keyword recommendations
  - Opportunity mining
  - Retail business optimization

## Support & Feedback

For issues, questions, or feature requests:
- GitHub Issues: https://github.com/datablogin/PaidSearchNav/issues
- Tag issues with `skill:search-term-analyzer`

## Related Skills

- **KeywordMatchAnalyzer**: Identifies exact match opportunities
- **NegativeConflictAnalyzer**: Finds negatives blocking positives
- **GeoPerformanceAnalyzer**: Location-based optimization (pairs well for retail)
- **PMaxAnalyzer**: Performance Max campaign analysis

## License

Part of the PaidSearchNav project
See main repository for license details
