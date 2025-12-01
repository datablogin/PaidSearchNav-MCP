# PMax Analyzer Claude Skill

## Overview
Analyzes Performance Max campaign search term overlap with standard Search campaigns and recommends negative keywords to prevent cannibalization and CPA inflation.

## Business Value
- **Typical Impact**: Prevents 10-20% CPA increase from PMax cannibalization
- **Cost Savings**: $1,000-$5,000/month for accounts with both PMax and Search
- **Use Frequency**: Monthly review (PMax changes frequently)
- **Best For**: Accounts running both PMax and Search campaigns

## What It Does
1. Identifies search terms triggering both PMax and Search
2. Compares performance (CPA, ROAS, conversion rate)
3. Calculates waste from higher PMax CPAs
4. Recommends PMax negative keywords to stop cannibalization
5. Provides strategic guidance on PMax vs Search balance

## Required MCP Tools
- `get_campaigns` - Identify PMax and Search campaigns
- `get_search_terms` - Performance data by campaign type

## Key Insights
- PMax search terms typically have 30-60% higher CPA than optimized Search campaigns
- PMax is better for display/video/Discover, not search
- Adding negatives to PMax allows Search to own high-intent queries
- Most accounts should limit PMax search inventory

## How to Use
```
Analyze Performance Max cannibalization for customer ID 1234567890
and recommend negative keywords to improve efficiency.
```

## Performance Expectations
- CPA improvement: 10-20% overall
- Cost savings: Based on cannibalization severity
- Search campaign performance recovery within 7-14 days
- PMax refocuses on non-search inventory (usually improves there)

## Common Issues
1. **PMax stealing brand traffic** - Add brand terms as negatives
2. **PMax taking local intent** - Add "near me" terms as negatives
3. **PMax on high-intent keywords** - Add converting keywords as PMax negatives
4. **Over-cannibalization** - Consider pausing PMax if >30% overlap

## Best Practices
- Review monthly (PMax learning changes targeting)
- Start with exact match negatives
- Monitor Search impression share recovery
- Don't over-block PMax (it needs some search for learning)

## Version History
- **1.0.0**: Initial release with cannibalization detection and negative keyword recommendations
