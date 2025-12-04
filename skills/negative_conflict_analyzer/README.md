# Negative Conflict Analyzer Claude Skill

## Overview

Detects negative keywords that block positive keywords, causing lost impressions, clicks, and revenue. Critical for maintaining healthy campaign performance and maximizing impression share.

## Business Value

- **Typical Impact**: 5-10% impression share recovery
- **Average Revenue Recovery**: $2,000-$8,000/month for mid-sized accounts
- **Use Frequency**: Quarterly audits + after bulk negative keyword additions
- **ROI**: High - recovers proven performers being blocked

## What It Does

1. **Identifies Conflicts** - Finds negatives blocking positives based on match type rules
2. **Assesses Severity** - Prioritizes by conversion value and Quality Score
3. **Calculates Impact** - Estimates revenue/impression loss from each conflict
4. **Provides Solutions** - Specific fix recommendations (remove, change match type, or refine)

## Required MCP Tools

- `get_keywords` - Fetches active positive keywords with performance data
- `get_negative_keywords` - Retrieves all negatives (shared, campaign, ad group levels)

## Key Features

### Conflict Detection Rules

- **Exact Match Negative**: Blocks only identical keyword text
- **Phrase Match Negative**: Blocks if phrase appears in positive
- **Broad Match Negative**: Blocks if all words appear (any order)

### Severity Levels

- **CRITICAL**: >10 conversions or QS ≥8 (immediate action)
- **HIGH**: 5-10 conversions or >100 clicks (fix within 7 days)
- **MEDIUM**: >10 clicks (review within 30 days)
- **LOW**: Minimal activity (monitor)

### Multi-Level Analysis

- Account-level shared lists (highest conflict risk)
- Campaign-level negatives
- Ad group-level negatives

## How to Use

```
Analyze negative keyword conflicts for customer ID 1234567890
and identify which negatives are blocking high-value keywords.
```

Claude will generate a detailed conflict report with prioritized fixes.

## Performance Expectations

### Immediate Impact (7-14 days)
- Impression share: +15-25% on affected keywords
- Clicks: +20-30% recovery
- Conversions: +12-18 additional conversions/month
- Revenue: Based on blocked keyword conversion values

### Long-term (30-60 days)
- Quality Score improvement: +0.5 to +1.5 points
- CPC reduction: 5-8% from better Quality Scores
- Sustained revenue recovery

## Common Issues Fixed

1. **Overly Broad Shared Negatives** - Single-word broad negatives blocking multiple products
2. **Cascade Blocking** - Campaign negatives blocking own positive keywords
3. **Poor Match Type Strategy** - Broad when phrase/exact would be better
4. **Forgotten Negatives** - Old negatives no longer relevant but still blocking

## Best Practices

- Run quarterly (minimum) or after bulk negative additions
- Fix critical conflicts immediately (proven revenue loss)
- Replace broad single-word negatives with 2-3 word phrases
- Test changes in one campaign before scaling
- Document all changes for future reference

## Related Skills

- **SearchTermAnalyzer**: Finds new negatives (complement to conflict detection)
- **KeywordMatchAnalyzer**: Optimizes match types for cost efficiency

## Version History

- **1.0.0**: Initial release with multi-level conflict detection and severity assessment
