# Geo Performance Analyzer Example

## Example: Multi-Location Sporting Goods Retailer

### Store Locations
- Seattle, WA
- Portland, OR
- San Francisco, CA
- Los Angeles, CA
- San Diego, CA

### Performance Data (90 days)

| Location | Impressions | Clicks | Cost | Conversions | Conv Value | ROAS | Conv Rate |
|----------|-------------|--------|------|-------------|------------|------|-----------|
| Seattle, WA | 45,000 | 2,250 | $4,500 | 112 | $15,680 | 3.48 | 4.98% |
| Portland, OR | 32,000 | 1,600 | $3,200 | 64 | $8,960 | 2.80 | 4.00% |
| San Francisco, CA | 52,000 | 2,080 | $6,240 | 83 | $11,620 | 1.86 | 3.99% |
| Los Angeles, CA | 68,000 | 3,400 | $8,500 | 153 | $21,420 | 2.52 | 4.50% |
| San Diego, CA | 28,000 | 1,120 | $2,800 | 45 | $6,300 | 2.25 | 4.02% |
| Sacramento, CA | 18,000 | 900 | $2,250 | 14 | $1,960 | 0.87 | 1.56% |
| Boise, ID | 12,000 | 480 | $1,440 | 6 | $840 | 0.58 | 1.25% |
| Phoenix, AZ | 22,000 | 880 | $2,640 | 0 | $0 | 0.00 | 0.00% |

**Account Averages**:
- ROAS: 2.06
- Conversion Rate: 3.50%
- CPA: $48.75

### Analysis Output

# Geographic Performance Analysis

## Executive Summary
- **Locations Analyzed**: 8
- **Account ROAS**: 2.06
- **Account Conv Rate**: 3.50%
- **Recommendations**: 3 bid ups, 2 bid downs, 1 exclusion
- **Potential Monthly Impact**: +$4,200 revenue, -$890 waste

## Top Performing Locations (Bid Up)

| Location | Conv | ROAS | Rate | vs Avg | Bid Adj | Revenue Impact |
|----------|------|------|------|--------|---------|----------------|
| Seattle, WA | 112 | 3.48 | 4.98% | +169% ROAS | +40% | +$2,100/mo |
| Los Angeles, CA | 153 | 2.52 | 4.50% | +122% ROAS | +30% | +$1,800/mo |
| Portland, OR | 64 | 2.80 | 4.00% | +136% ROAS | +25% | +$670/mo |

**Total Revenue Increase**: $4,570/month from bid ups

**Rationale**: These locations are near store locations and significantly outperform account average. Increasing bids will capture more high-value traffic.

## Underperforming Locations (Bid Down)

| Location | Spend | ROAS | Rate | vs Avg | Bid Adj | Savings |
|----------|-------|------|------|--------|---------|---------|
| Sacramento, CA | $2,250 | 0.87 | 1.56% | -58% ROAS | -40% | +$540/mo |
| Boise, ID | $1,440 | 0.58 | 1.25% | -72% ROAS | -50% | +$360/mo |

**Total Cost Savings**: $900/month from bid reductions

**Rationale**: No nearby stores (>200 miles). Low performance suggests poor market fit or high competition. Reduce spend but don't fully exclude (small sample size).

## Locations to Exclude

| Location | Spend | Conv | Reason | Savings |
|----------|-------|------|--------|---------|
| Phoenix, AZ | $2,640 | 0 | 0 conversions in 90 days, no nearby store | $880/mo |

**Rationale**: Zero conversions despite moderate spend. No store within 300 miles makes service difficult. Full exclusion recommended.

## Store Proximity Analysis

**Within 30 miles of stores**:
- Average ROAS: 2.85 (+38% vs account)
- Conversion Rate: 4.37% (+25% vs account)
- CPA: $42.30 (-13% vs account)

**100+ miles from stores**:
- Average ROAS: 0.73 (-65% vs account)
- Conversion Rate: 1.41% (-60% vs account)
- CPA: $105.50 (+116% vs account)

**Recommendation**: Prioritize markets within 30-50 miles of existing stores. Consider opening new stores in high-performing distant markets (e.g., if Phoenix showed good performance, it would justify expansion).

## Implementation Steps

1. **Immediate Bid Increases** (This Week):
   - Seattle: +40% bid adjustment
   - Los Angeles: +30% bid adjustment
   - Portland: +25% bid adjustment

2. **Immediate Bid Decreases** (This Week):
   - Sacramento: -40% bid adjustment
   - Boise: -50% bid adjustment

3. **Exclusion**:
   - Phoenix: Exclude location entirely

4. **Monitor** (14 days):
   - Check impression share in bid-up locations
   - Verify cost reduction in bid-down locations
   - Confirm Phoenix exclusion doesn't affect nearby cities

## Expected Results (30 days)

- Revenue from top 3 markets: +$4,570/month
- Cost savings from bid downs: +$900/month
- Waste elimination (Phoenix): +$880/month
- **Total Monthly Benefit**: +$6,350

ROAS improvement: 2.06 → 2.44 (+18%)
