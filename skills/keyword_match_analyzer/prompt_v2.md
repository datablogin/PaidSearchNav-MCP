# Keyword Match Type Optimizer

## Task
Find exact match opportunities to reduce wasted spend.

## Process

1. **Fetch Data** (use limit=500, paginate if has_more=true):
   - `get_keywords(customer_id, start_date, end_date, limit=500)`
   - `get_search_terms(customer_id, start_date, end_date, limit=500)`
   - Filter: keep keywords with ≥100 impressions only

2. **Calculate Match Type Performance**:
   - Group by BROAD, PHRASE, EXACT
   - Calculate: total cost, conversions, CPA, ROAS per match type

3. **Find Exact Match Opportunities**:
   - For each broad/phrase keyword, check if ≥60% of its search terms are exact matches
   - If yes: recommend converting to exact match
   - Calculate savings: current_cost - (estimated_exact_cost × 0.7)

4. **Find High-Cost Wasters**:
   - Broad keywords with: cost >$100 AND (ROAS <1.5 OR CPA >2× account avg)
   - Recommend: pause or convert to phrase/exact

5. **Output**:

```
# Analysis Report
**Period**: [dates] | **Customer**: [id]

## Summary
- Total Keywords: [N]
- Monthly Savings: $[N]

## Match Type Performance
| Type | Count | Cost | CPA | ROAS |
|------|-------|------|-----|------|
| [data rows]

## TOP 10 Recommendations
| Keyword | Current | Cost | Action | Savings |
|---------|---------|------|--------|---------|
| [data rows]

## Next Steps
1. [action]
2. [action]
```

**Keep it concise. Focus on actionable recommendations with dollar impact.**
