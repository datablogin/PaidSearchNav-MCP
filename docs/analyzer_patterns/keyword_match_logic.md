# Keyword Match Type Analyzer - Business Logic Documentation

**Extracted from**: [archive/old_app/paidsearchnav/analyzers/keyword_match.py](../../archive/old_app/paidsearchnav/analyzers/keyword_match.py)

**Purpose**: Analyzes keyword performance across match types (Broad, Phrase, Exact) to identify optimization opportunities and cost inefficiencies.

## Core Configuration Parameters

| Parameter | Default | Purpose |
|-----------|---------|---------|
| `min_impressions` | 100 | Minimum impressions required to include keyword in analysis |
| `high_cost_threshold` | $100.00 | Cost threshold to flag high-cost keywords |
| `low_roi_threshold` | 1.5 | ROAS threshold to identify low ROI keywords |
| `max_broad_cpa_multiplier` | 2.0 | Max acceptable CPA multiplier for broad match vs account average |

## Analysis Methodology

### 1. Data Collection
- Fetch all keywords from Google Ads API
- Filter by optional parameters: campaigns, ad_groups
- Apply minimum impressions filter (≥100 impressions)

### 2. Match Type Statistics Calculation

For each match type (BROAD, PHRASE, EXACT), calculate:
- **Count**: Number of keywords
- **Impressions**: Total impressions
- **Clicks**: Total clicks
- **Cost**: Total spend
- **Conversions**: Total conversions
- **Conversion Value**: Total conversion value

**Derived Metrics**:
- **CTR**: `(clicks / impressions) × 100`
- **Avg CPC**: `cost / clicks`
- **CPA**: `cost / conversions`
- **ROAS**: `conversion_value / cost`
- **Conversion Rate**: `(conversions / clicks) × 100`

### 3. Problem Identification

#### A. High-Cost Broad Match Keywords

**Criteria** (ALL must be met):
1. Match type = BROAD
2. Cost ≥ `high_cost_threshold` ($100)
3. EITHER:
   - ROAS < `low_roi_threshold` (1.5), OR
   - Has conversions with CPA > 0

**Output**: Sorted by cost descending

#### B. Low Quality Keywords

**Criteria**:
1. Quality Score < 7 (flag `is_low_quality`)
2. Cost > 0

**Output**: Sorted by cost descending

#### C. Duplicate Keyword Opportunities

**Process**:
1. Group keywords by normalized text (lowercase, trimmed)
2. For groups with multiple keywords:
   - Calculate performance by match type within the group
   - Identify best-performing match type (lowest CPA)
   - Calculate potential savings from consolidating to best match type

**Output**: Sorted by potential savings descending

### 4. Potential Savings Calculation

**Two sources of savings**:

#### A. Broad Match Optimization
1. Calculate overall account CPA: `total_cost / total_conversions`
2. If `broad_match_CPA > (overall_CPA × max_broad_cpa_multiplier)`:
   - Calculate excess cost ratio
   - Estimate savings: `broad_cost × excess_ratio × 0.5`

#### B. Top 10 High-Cost Keywords
For each of the 10 worst performers:
- **No conversions**: Assume 80% savings (`cost × 0.8`)
- **High CPA** (> 2× overall CPA): Estimate `(keyword_CPA - overall_CPA) × conversions × 0.5`

### 5. Recommendation Generation

#### Recommendation Type 1: Reduce Broad Match Usage
**Triggers**:
- Broad match spend > 50% of total spend
- Broad match ROAS < `low_roi_threshold`

**Priority**: HIGH
**Action**: Pause poor performers or convert to phrase/exact match

---

#### Recommendation Type 2: Optimize High-Cost Broad Keywords
**Triggers**:
- Any high-cost broad keywords found

**Priority**: HIGH
**Details**: List count and top keyword example with spend/conversions

---

#### Recommendation Type 3: Improve Low Quality Keywords
**Triggers**:
- Any low quality keywords found (QS < 7)

**Priority**: MEDIUM
**Details**: Total spend on low quality keywords
**Action**: Improve ad relevance, landing pages, expected CTR

---

#### Recommendation Type 4: Consolidate Duplicate Keywords
**Triggers**:
- Duplicate opportunities identified

**Priority**: MEDIUM
**Details**: Number of duplicates and total potential savings

---

#### Recommendation Type 5: Increase Exact Match Coverage
**Triggers**:
- Exact match keywords < 30% of total keywords

**Priority**: LOW
**Action**: Add exact match versions of top performing queries

## Business Rules & Edge Cases

### Minimum Data Requirements
- **Keywords must have ≥100 impressions** to be included in analysis
- This prevents noise from low-volume keywords

### ROAS vs CPA Logic
The analyzer checks BOTH metrics because:
- **ROAS** measures revenue efficiency (prefer ≥1.5)
- **CPA** measures cost efficiency (compared to account average)
- A keyword can have good ROAS but still be expensive (high CPA)

### Broad Match Multiplier
- Broad match is expected to have higher CPA than exact/phrase
- The `max_broad_cpa_multiplier` (2.0) allows 2× the account average CPA
- Exceeding this triggers optimization recommendations

### Conservative Savings Estimates
- Savings calculations use 50-80% multipliers
- This accounts for uncertainty and prevents over-promising

### Quality Score Threshold
- QS < 7 is considered "low quality"
- These keywords cost more per click due to lower ad rank
- Improving QS can reduce CPC by 20-50%

## Output Structure

```python
KeywordMatchAnalysisResult(
    customer_id: str,
    analyzer_name: str,
    start_date: datetime,
    end_date: datetime,
    total_keywords: int,
    match_type_stats: dict[str, dict],
    high_cost_broad_keywords: list[Keyword],
    low_quality_keywords: list[Keyword],
    duplicate_opportunities: list[dict],
    potential_savings: float,
    recommendations: list[Recommendation]
)
```

## Example Scenario

**Input**:
- Account with 150 keywords
- 60% spend on broad match
- Broad match ROAS: 0.8 (below 1.5 threshold)
- Overall account ROAS: 2.5
- 5 keywords with QS < 7 spending $500/month

**Expected Recommendations**:
1. **HIGH**: Reduce broad match usage (60% spend, poor ROAS)
2. **HIGH**: Optimize high-cost broad keywords (specific examples)
3. **MEDIUM**: Improve 5 low quality keywords ($500 wasted)
4. **LOW**: Increase exact match coverage (if <30%)

**Estimated Savings**: $2,000-3,000/month from broad match optimization

## Key Insights for Skill Conversion

### What to Preserve
1. **Multi-factor evaluation**: Don't rely on single metrics
2. **Configurable thresholds**: Allow customization per account
3. **Priority ranking**: HIGH/MEDIUM/LOW helps clients focus
4. **Conservative estimates**: Under-promise, over-deliver

### What Could Be Enhanced
1. **Search term analysis**: Original analyzer doesn't use search term data
2. **Seasonality awareness**: Could flag seasonal keywords
3. **Brand vs non-brand**: Different thresholds for brand terms
4. **Mobile vs desktop**: Performance can vary significantly

### Critical Business Context
- This analyzer targets **cost efficiency**, not growth
- Quarterly audit context means data is typically 90 days
- Clients are retail businesses focused on store visits
- Recommendations must be actionable (not just insights)

## Data Dependencies

### Required from Google Ads API
- Keywords with metrics (impressions, clicks, cost, conversions, conversion_value)
- Match type field
- Quality Score (for low quality detection)

### Optional Filters
- Campaign IDs (analyze specific campaigns)
- Ad Group IDs (analyze specific ad groups)

### Could Benefit From (not in original)
- Search term report (to see actual queries)
- Device performance split
- Geographic performance data
