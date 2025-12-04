# Cost Efficiency Suite

## Overview
Complete suite of 5 Claude Skills for conducting quarterly Google Ads keyword audits focused on cost efficiency and ROAS improvement.

## Included Skills

1. **KeywordMatchAnalyzer** - Exact match keyword opportunities ($1,500-5,000/mo savings)
2. **SearchTermAnalyzer** - Negative keyword recommendations ($2,000-7,000/mo savings)
3. **NegativeConflictAnalyzer** - Fix negatives blocking positives (5-10% impression share recovery)
4. **GeoPerformanceAnalyzer** - Location bid optimization (15-25% ROAS improvement)
5. **PMaxAnalyzer** - Performance Max cannibalization prevention (10-20% CPA improvement)

## Business Value

- **Total Impact**: $5,000-$15,000/month for mid-sized accounts
- **ROI**: 10-20x on audit cost
- **Use Frequency**: Quarterly minimum
- **Best For**: Retail businesses, e-commerce, multi-location brands

## How to Use

### Prerequisites
1. Claude Desktop or API access
2. PaidSearchNav MCP server connected
3. Google Ads account access
4. Minimum 90 days of campaign data

### Running the Suite

**Option 1: Individual Skills** (Recommended for first run)
```
Run KeywordMatchAnalyzer for customer ID 1234567890

[Review output, then continue...]

Run SearchTermAnalyzer for customer ID 1234567890

[Continue through all 5 skills...]
```

**Option 2: Full Audit Workflow**
```
Run a complete quarterly audit using the Cost Efficiency Suite
for customer ID 1234567890 covering the last 90 days.
```

### Execution Order
1. KeywordMatchAnalyzer (quick wins on match types)
2. SearchTermAnalyzer (eliminate waste first)
3. NegativeConflictAnalyzer (recover lost impressions)
4. GeoPerformanceAnalyzer (optimize locations)
5. PMaxAnalyzer (fix cannibalization)

## Expected Results

### Typical Quarterly Audit Output
- **Total Wasted Spend Identified**: $8,000-$25,000
- **Negative Keywords to Add**: 50-150
- **Positive Keywords Blocked**: 10-30
- **Location Bid Adjustments**: 15-40
- **PMax Conflicts**: 20-60 search terms

### Performance Improvements (30-60 days)
- Cost savings: 20-35%
- ROAS improvement: 15-30%
- Impression share recovery: 5-15%
- CPA improvement: 15-25%

## Documentation

Each skill includes:
- **skill.json** - Metadata and configuration
- **prompt.md** - Analysis methodology and instructions
- **examples.md** - Real-world examples with sample data
- **README.md** - Usage guide and best practices

## Workflow Integration

### Quarterly Audit Schedule
- **Week 1**: Run all 5 skills, generate reports
- **Week 2**: Implement high-priority recommendations
- **Week 3**: Monitor results, adjust as needed
- **Week 4**: Document learnings, plan next quarter

### Best Practices
1. Start with one campaign/account as pilot
2. Document all changes with before/after metrics
3. Implement critical recommendations first
4. Monitor for 7-14 days before scaling changes
5. Re-run quarterly to track improvement trends

## Support

For issues or questions:
- GitHub: https://github.com/datablogin/PaidSearchNav/issues
- Tag with `skill:cost-efficiency-suite`

## Version History
- **1.0.0**: Initial release with all 5 Tier 1 analyzers
