# PMax Analyzer Example

## Example: Retail Sporting Goods - PMax Cannibalization

### Account Structure
- 3 Search campaigns (Brand, Generic, Competitor)
- 1 PMax campaign (All Products)
- Monthly spend: $18,000 total ($12,000 Search, $6,000 PMax)

### Overlap Analysis (90 days)

| Search Term | Search CPA | PMax CPA | Search Conv | PMax Conv | Monthly Waste |
|-------------|------------|----------|-------------|-----------|---------------|
| nike running shoes | $32 | $58 | 45 | 23 | $598 |
| running shoes near me | $28 | $62 | 38 | 15 | $510 |
| best running shoes 2025 | $35 | $54 | 28 | 18 | $342 |
| women's running shoes | $30 | $48 | 32 | 22 | $396 |
| trail running shoes | $38 | $59 | 18 | 12 | $252 |
| **Total Top 5** | **-** | **-** | **161** | **90** | **$2,098** |

### Analysis Output

# PMax Cannibalization Analysis

## Executive Summary
- **Overlapping Search Terms**: 47
- **Total Monthly Waste**: $3,240
- **PMax Negative Keywords Needed**: 25
- **Expected CPA Improvement**: 18%

### Key Findings
- PMax CPA averages 52% higher than Search on overlapping terms
- 62% of PMax conversions come from search (should be <30%)
- Search campaigns losing impression share to PMax
- PMax performing well on Display/YouTube (keep those)

## Critical Cannibalization (Top 5)

### 1. "nike running shoes"
- **Search**: $32 CPA, 45 conv/mo
- **PMax**: $58 CPA, 23 conv/mo (+81% CPA)
- **Waste**: $598/month
- **Action**: Add as exact match negative to PMax

### 2. "running shoes near me"
- **Search**: $28 CPA, 38 conv/mo
- **PMax**: $62 CPA, 15 conv/mo (+121% CPA)
- **Waste**: $510/month
- **Action**: Add as phrase match negative to PMax
- **Note**: Local intent should be Search-only

### 3. "best running shoes 2025"
- **Search**: $35 CPA, 28 conv/mo
- **PMax**: $54 CPA, 18 conv/mo (+54% CPA)
- **Waste**: $342/month

### 4. "women's running shoes"
- **Search**: $30 CPA, 32 conv/mo
- **PMax**: $48 CPA, 22 conv/mo (+60% CPA)
- **Waste**: $396/month

### 5. "trail running shoes"
- **Search**: $38 CPA, 18 conv/mo
- **PMax**: $59 CPA, 12 conv/mo (+55% CPA)
- **Waste**: $252/month

## PMax Negative Keyword Recommendations

Add to PMax Asset Group "All Products":

**Brand Terms** (Exact Match):
- [nike running shoes]
- [adidas running shoes]
- [brooks running shoes]

**Local Intent** (Phrase Match):
- "near me"
- "nearby"
- "closest store"

**High-Intent Generic** (Phrase Match):
- "best running shoes"
- "top running shoes"
- "running shoes 2025"

**Gender-Specific** (Phrase Match):
- "women's running shoes"
- "men's running shoes"

**Product-Specific** (Phrase Match):
- "trail running shoes"
- "marathon running shoes"
- "stability running shoes"

## Expected Results

**Immediate Impact** (14 days):
- Search impression share: +25%
- Search conversions: +15-20/month
- PMax search spend: -$1,800/month
- Account CPA: $45 → $37 (-18%)

**PMax Refocus** (30 days):
- PMax search conversions: -90/month
- PMax display conversions: +30/month (better targeting)
- PMax video conversions: +15/month
- Overall: Better performance, lower cost

## Implementation

1. Add 25 negative keywords to PMax asset group "All Products"
2. Monitor Search impression share daily for 7 days
3. Check PMax search term report weekly
4. Verify display/video performance improves
5. Re-analyze monthly for new overlaps

**Result**: $3,240/month savings, better campaign efficiency
