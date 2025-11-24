# Keyword Match Analyzer Skill

Identifies match type optimization opportunities to reduce wasted spend on broad and phrase match keywords.

## Business Value

Typically saves 15-30% on cost per conversion by:
- Eliminating spend on low-performing search term variants
- Converting inefficient broad match keywords to exact or phrase match
- Consolidating duplicate keywords across match types
- Identifying and pausing wasteful keywords

## Use Cases

### Quarterly Keyword Audits
Run comprehensive analysis every 90 days to identify accumulation of waste and efficiency opportunities.

### Cost Efficiency Deep Dives
When CPA is increasing or ROAS is declining, identify which keywords are driving the problem.

### Match Type Strategy Validation
Verify that broad/phrase match keywords are delivering value or should be converted to exact match.

## Required MCP Tools

This skill requires the following MCP tools to be available:

- **`get_keywords`** - Fetch keywords with match types and performance metrics
  - Required fields: keyword text, match_type, impressions, clicks, cost, conversions, conversion_value, quality_score
  - Recommended date range: 90 days

- **`get_search_terms`** - Fetch search queries triggering ads
  - Required fields: search_term, keyword (triggering), impressions, clicks, cost, conversions
  - Used to identify exact match opportunities

## How It Works

### 1. Data Collection
The skill uses MCP tools to fetch:
- All keywords with ≥100 impressions in the analysis period
- Search term reports to understand actual queries
- Performance metrics aggregated by match type

### 2. Analysis Process

#### Match Type Performance
Calculates aggregate statistics for BROAD, PHRASE, and EXACT match types:
- Cost per acquisition (CPA)
- Return on ad spend (ROAS)
- Conversion rates
- Cost distribution

#### Problem Identification
Finds four types of optimization opportunities:

1. **High-Cost Broad Keywords**: Broad match keywords with cost ≥$100 and poor performance (ROAS <1.5 or high CPA)

2. **Low Quality Score Keywords**: Keywords with QS <7 driving costs up due to poor ad relevance

3. **Duplicate Keywords**: Same keyword text in multiple match types, often with clear performance winner

4. **Exact Match Opportunities**: Keywords where 70%+ of impressions come from exact match search term variant

### 3. Recommendation Generation

Produces prioritized recommendations:

- **HIGH Priority**: Immediate cost savings (pause wasteful keywords, fix duplicates)
- **MEDIUM Priority**: Quality improvements (QS optimization, match type adjustments)
- **LOW Priority**: Growth opportunities (expand exact match coverage)

### 4. Savings Estimation

Calculates conservative savings estimates:
- Broad match optimization: Compare CPA to account average
- Keyword pausing: 80% of spend on zero-conversion keywords
- Consolidation: Eliminate spend on poor-performing duplicates

Uses 50-80% multipliers to avoid over-promising.

## Usage

### Basic Analysis

```
Analyze keywords for customer 1234567890 from 2025-08-01 to 2025-11-22
and recommend match type optimizations
```

The skill will:
1. Fetch keyword data via MCP
2. Calculate performance by match type
3. Identify optimization opportunities
4. Generate prioritized recommendations
5. Estimate potential savings

### With Specific Focus

```
Focus on broad match keywords for customer 1234567890.
Identify which ones should be converted to exact match.
```

### Custom Thresholds

```
Analyze keywords for customer 1234567890 with these criteria:
- Minimum 500 impressions (instead of default 100)
- Flag keywords with CPA >$50
- Consider ROAS threshold of 2.0 (instead of 1.5)
```

## Configuration Options

### Default Thresholds
- **Minimum impressions**: 100
- **High cost threshold**: $100
- **Low ROIS threshold**: 1.5
- **Max broad CPA multiplier**: 2.0× account average
- **Low quality score**: <7

### Customizable Parameters
You can adjust thresholds based on your account:

```
Use these thresholds for my analysis:
- Minimum impressions: 500 (I have high volume)
- High cost threshold: $500 (I have large budgets)
- ROAS threshold: 2.5 (I need higher efficiency)
- Exclude brand keywords from broad match analysis
```

## Output Structure

The skill generates a comprehensive markdown report with:

1. **Executive Summary**
   - Total keywords analyzed
   - Estimated monthly savings
   - Primary issue identified

2. **Match Type Performance Table**
   - Aggregated metrics by BROAD/PHRASE/EXACT
   - Performance comparisons

3. **HIGH Priority Recommendations**
   - Immediate action items
   - Specific keywords to address
   - Expected savings per recommendation

4. **MEDIUM Priority Recommendations**
   - Quality score improvements
   - Consolidation opportunities

5. **LOW Priority Recommendations**
   - Growth opportunities
   - Long-term strategy

6. **Implementation Roadmap**
   - Week-by-week action plan
   - Monitoring guidelines
   - Success metrics

7. **Detailed Analysis**
   - Complete tables of problem keywords
   - Supporting data for all recommendations

## Example Output

See [examples.md](examples.md) for:
- Clear exact match opportunity
- Insufficient data scenarios
- Multiple issues on same keyword
- Duplicate keyword consolidation
- Well-optimized keywords (no action needed)

## Best Practices

### When to Run
- **Quarterly audits**: Every 90 days for comprehensive review
- **Performance investigations**: When CPA spikes or ROAS drops
- **After campaign changes**: Validate impact of recent optimizations
- **Budget planning**: Identify savings opportunities before quarter end

### How to Use Results
1. **Start with HIGH priority**: Focus on immediate savings first
2. **Implement gradually**: Don't change everything at once
3. **Monitor daily**: Watch metrics for first 7 days after changes
4. **Validate assumptions**: Confirm savings materialize as estimated
5. **Iterate**: Re-run analysis after 30 days to measure impact

### Common Mistakes to Avoid
- ❌ Changing too many keywords at once (hard to isolate what works)
- ❌ Ignoring seasonality (don't optimize during peak season)
- ❌ Pausing keywords without checking impression share impact
- ❌ Converting all broad to exact (lose discovery opportunities)
- ✅ Test changes on small subset first
- ✅ Keep detailed records of what changed when
- ✅ Set up alerts for significant metric changes

## Limitations

### Data Requirements
- Requires ≥90 days of data for reliable analysis
- Keywords need ≥100 impressions to be included
- Search term data may be limited by Google Ads privacy thresholds

### Seasonal Considerations
- Analysis is point-in-time, may not account for seasonality
- Holiday periods may skew performance metrics
- Consider year-over-year comparisons for seasonal businesses

### Account-Specific Factors
- Thresholds may need adjustment for very large or very small accounts
- Brand keywords often require different treatment
- Local service businesses may have different optimization priorities

## Monitoring After Implementation

### Week 1: Immediate Impact Check
- [ ] Impression share hasn't dropped >10%
- [ ] CPC trending downward
- [ ] No significant conversion volume loss
- [ ] Quality Score changes noted

### Week 2-3: Performance Validation
- [ ] CPA improving toward target
- [ ] ROAS showing positive trend
- [ ] Conversion rate stable or improving
- [ ] Wasted spend reduction visible

### Week 4: Confirm Sustained Savings
- [ ] Monthly cost savings match estimates
- [ ] No adverse side effects
- [ ] New exact match keywords performing well
- [ ] Quality Score improvements materializing

## Troubleshooting

### "Estimated savings don't materialize"
- Check if changes were implemented correctly
- Verify search volume hasn't dropped
- Look for other account changes (budget, bids, competitors)
- Re-run analysis to see current state

### "Conversions dropped after pausing keywords"
- Review which keywords were paused
- Check search term data for lost opportunities
- Consider re-enabling with lower bids instead of pausing
- Add new exact match keywords to recapture traffic

### "Quality Score not improving"
- QS changes take 7-14 days to reflect
- Ensure ad copy changes were made
- Verify landing page relevance
- Check expected CTR component specifically

## Related Skills

- **Search Term Analyzer**: Identifies negative keyword opportunities (complements this skill)
- **Quality Score Analyzer**: Deep dive on QS improvement strategies
- **Wasted Spend Analyzer**: Broader view of budget leaks across account
- **Ad Copy Performance Analyzer**: Helps improve QS through better ad relevance

## Support

For issues or questions:
- Review [examples.md](examples.md) for common scenarios
- Check [../docs/SKILL_DEVELOPMENT_GUIDE.md](../../docs/SKILL_DEVELOPMENT_GUIDE.md) for technical details
- Consult [../../docs/analyzer_patterns/keyword_match_logic.md](../../docs/analyzer_patterns/keyword_match_logic.md) for business logic

## Version History

### v1.0.0 (Current)
- Initial release
- Converted from legacy KeywordMatchAnalyzer
- Supports BROAD/PHRASE/EXACT analysis
- Conservative savings estimation
- Comprehensive reporting format
