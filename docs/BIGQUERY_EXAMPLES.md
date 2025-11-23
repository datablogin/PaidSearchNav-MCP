# BigQuery Query Examples for Google Ads Analysis

This guide provides practical BigQuery query examples for analyzing Google Ads data in PaidSearchNav. These queries help you leverage historical data beyond the API's 90-day limitation.

## Table of Contents

1. [Understanding Google Ads BigQuery Schema](#understanding-google-ads-bigquery-schema)
2. [Historical Search Terms Analysis](#historical-search-terms-analysis)
3. [Campaign Performance Over Time](#campaign-performance-over-time)
4. [Geographic Performance Analysis](#geographic-performance-analysis)
5. [Keyword Performance Trends](#keyword-performance-trends)
6. [Match Type Efficiency Analysis](#match-type-efficiency-analysis)
7. [Performance Max Campaign Analysis](#performance-max-campaign-analysis)
8. [Query Optimization Tips](#query-optimization-tips)

## Understanding Google Ads BigQuery Schema

Google Ads exports data to BigQuery in sharded tables with the suffix `_YYYYMMDD`. Common tables include:

- `SearchTermStats_*` - Search term performance data
- `CampaignStats_*` - Campaign-level metrics
- `AdGroupStats_*` - Ad group-level metrics
- `KeywordStats_*` - Keyword-level metrics
- `GeoStats_*` - Geographic performance data

### Common Field Naming Conventions

- **Segments**: Dimensions (e.g., `segments_date`, `segments_search_term`)
- **Metrics**: Performance metrics (e.g., `metrics_impressions`, `metrics_clicks`)
- **Resources**: Entity attributes (e.g., `campaign_name`, `ad_group_name`)

## Historical Search Terms Analysis

### Query: Get Search Terms Beyond 90-Day API Limit

**Business Value**: Identify long-term search term patterns, discover seasonal keywords, and analyze historical wasted spend.

```sql
-- Get historical search terms with performance metrics
-- This query retrieves all search terms from the past year that have significant traffic
SELECT
  segments_search_term_match_type as match_type,
  segments_search_term as search_term,
  SUM(metrics_impressions) as impressions,
  SUM(metrics_clicks) as clicks,
  SUM(metrics_cost_micros) / 1000000 as cost,
  ROUND(SUM(metrics_clicks) / NULLIF(SUM(metrics_impressions), 0) * 100, 2) as ctr,
  ROUND(SUM(metrics_cost_micros) / NULLIF(SUM(metrics_clicks), 0) / 1000000, 2) as cpc,
  SUM(metrics_conversions) as conversions,
  ROUND(SUM(metrics_conversions) / NULLIF(SUM(metrics_clicks), 0) * 100, 2) as conversion_rate
FROM `project.dataset.SearchTermStats_*`
WHERE _TABLE_SUFFIX BETWEEN '20250101' AND '20251122'
  AND segments_search_term IS NOT NULL
GROUP BY match_type, search_term
HAVING impressions > 100
ORDER BY cost DESC
LIMIT 1000
```

**How to Use**:
1. Replace `project.dataset` with your actual project and dataset IDs
2. Adjust the date range in `_TABLE_SUFFIX` to your desired period
3. Modify the `HAVING` clause to filter by your traffic threshold
4. Export results to identify high-cost, low-converting search terms

### Query: Search Terms with "Near Me" Intent

**Business Value**: For retail businesses with physical locations, identify local search patterns to optimize for in-store visits.

```sql
-- Analyze "near me" and location-based search terms
SELECT
  segments_search_term as search_term,
  SUM(metrics_impressions) as impressions,
  SUM(metrics_clicks) as clicks,
  SUM(metrics_cost_micros) / 1000000 as cost,
  SUM(metrics_conversions) as conversions,
  ROUND(SUM(metrics_cost_micros) / NULLIF(SUM(metrics_conversions), 0) / 1000000, 2) as cost_per_conversion
FROM `project.dataset.SearchTermStats_*`
WHERE _TABLE_SUFFIX BETWEEN '20240101' AND '20251122'
  AND (
    LOWER(segments_search_term) LIKE '%near me%'
    OR LOWER(segments_search_term) LIKE '%nearby%'
    OR LOWER(segments_search_term) LIKE '%close to me%'
    OR LOWER(segments_search_term) LIKE '%around me%'
  )
GROUP BY search_term
HAVING impressions > 50
ORDER BY cost DESC
LIMIT 500
```

## Campaign Performance Over Time

### Query: Monthly Campaign Performance Trends

**Business Value**: Track campaign performance trends to identify seasonality, budget allocation opportunities, and performance degradation.

```sql
-- Monthly campaign performance aggregation
SELECT
  campaign_name,
  FORMAT_DATE('%Y-%m', PARSE_DATE('%Y%m%d', _TABLE_SUFFIX)) as month,
  SUM(metrics_impressions) as impressions,
  SUM(metrics_clicks) as clicks,
  SUM(metrics_cost_micros) / 1000000 as cost,
  SUM(metrics_conversions) as conversions,
  ROUND(SUM(metrics_clicks) / NULLIF(SUM(metrics_impressions), 0) * 100, 2) as ctr,
  ROUND(SUM(metrics_cost_micros) / NULLIF(SUM(metrics_clicks), 0) / 1000000, 2) as avg_cpc,
  ROUND(SUM(metrics_cost_micros) / NULLIF(SUM(metrics_conversions), 0) / 1000000, 2) as cost_per_conversion,
  ROUND(SUM(metrics_conversions) / NULLIF(SUM(metrics_clicks), 0) * 100, 2) as conversion_rate
FROM `project.dataset.CampaignStats_*`
WHERE _TABLE_SUFFIX BETWEEN '20240101' AND '20251122'
  AND campaign_name NOT LIKE '%Test%'
  AND campaign_status = 'ENABLED'
GROUP BY campaign_name, month
ORDER BY campaign_name, month DESC
```

**Analysis Tips**:
- Look for campaigns with declining conversion rates over time
- Identify seasonal patterns in cost and conversions
- Compare year-over-year performance for the same month
- Flag campaigns with increasing cost per conversion

### Query: Week-over-Week Campaign Performance

**Business Value**: Detect sudden performance changes and react quickly to optimization opportunities or issues.

```sql
-- Week-over-week campaign performance comparison
WITH weekly_stats AS (
  SELECT
    campaign_name,
    FORMAT_DATE('%Y-W%V', PARSE_DATE('%Y%m%d', _TABLE_SUFFIX)) as week,
    SUM(metrics_cost_micros) / 1000000 as cost,
    SUM(metrics_clicks) as clicks,
    SUM(metrics_conversions) as conversions
  FROM `project.dataset.CampaignStats_*`
  WHERE _TABLE_SUFFIX >= FORMAT_DATE('%Y%m%d', DATE_SUB(CURRENT_DATE(), INTERVAL 8 WEEK))
  GROUP BY campaign_name, week
)
SELECT
  current.campaign_name,
  current.week as current_week,
  current.cost as current_cost,
  current.conversions as current_conversions,
  previous.cost as previous_cost,
  previous.conversions as previous_conversions,
  ROUND((current.cost - previous.cost) / NULLIF(previous.cost, 0) * 100, 2) as cost_change_pct,
  ROUND((current.conversions - previous.conversions) / NULLIF(previous.conversions, 0) * 100, 2) as conversion_change_pct
FROM weekly_stats current
LEFT JOIN weekly_stats previous
  ON current.campaign_name = previous.campaign_name
  AND current.week = FORMAT_DATE('%Y-W%V', DATE_ADD(PARSE_DATE('%Y-W%V', previous.week), INTERVAL 1 WEEK))
WHERE current.week = FORMAT_DATE('%Y-W%V', DATE_SUB(CURRENT_DATE(), INTERVAL 1 WEEK))
ORDER BY ABS(cost_change_pct) DESC
```

## Geographic Performance Analysis

### Query: Performance by Geographic Location

**Business Value**: For multi-location retail businesses, identify which areas drive the most efficient conversions and where to focus budget.

```sql
-- Geographic performance aggregation
SELECT
  campaign_name,
  geographic_view_country_criterion_id,
  geographic_view_location_type,
  SUM(metrics_impressions) as impressions,
  SUM(metrics_clicks) as clicks,
  SUM(metrics_cost_micros) / 1000000 as cost,
  SUM(metrics_conversions) as conversions,
  ROUND(SUM(metrics_clicks) / NULLIF(SUM(metrics_impressions), 0) * 100, 2) as ctr,
  ROUND(SUM(metrics_cost_micros) / NULLIF(SUM(metrics_conversions), 0) / 1000000, 2) as cost_per_conversion
FROM `project.dataset.GeoStats_*`
WHERE _TABLE_SUFFIX BETWEEN '20240101' AND '20251122'
  AND geographic_view_location_type IN ('LOCATION_OF_PRESENCE', 'LOCATION_OF_INTEREST')
GROUP BY campaign_name, geographic_view_country_criterion_id, geographic_view_location_type
HAVING impressions > 1000
ORDER BY cost DESC
LIMIT 500
```

### Query: City-Level Performance for Retail Locations

**Business Value**: Match Google Ads performance to actual store locations to optimize local targeting.

```sql
-- City-level performance analysis
SELECT
  campaign_name,
  segments_geo_target_city as city,
  segments_geo_target_region as region,
  SUM(metrics_impressions) as impressions,
  SUM(metrics_clicks) as clicks,
  SUM(metrics_cost_micros) / 1000000 as cost,
  SUM(metrics_conversions) as conversions,
  SUM(metrics_all_conversions_value) / 1000000 as conversion_value,
  ROUND(SUM(metrics_cost_micros) / NULLIF(SUM(metrics_conversions), 0) / 1000000, 2) as cost_per_conversion,
  ROUND(SUM(metrics_all_conversions_value) / NULLIF(SUM(metrics_cost_micros), 0), 2) as roas
FROM `project.dataset.GeoStats_*`
WHERE _TABLE_SUFFIX BETWEEN '20240101' AND '20251122'
  AND segments_geo_target_city IS NOT NULL
GROUP BY campaign_name, city, region
HAVING clicks > 100
ORDER BY cost DESC
LIMIT 1000
```

## Keyword Performance Trends

### Query: Keyword Performance Over Time

**Business Value**: Identify keywords with declining performance that need bid adjustments or pausing.

```sql
-- Quarterly keyword performance trends
SELECT
  campaign_name,
  ad_group_name,
  ad_group_criterion_keyword_text as keyword,
  ad_group_criterion_keyword_match_type as match_type,
  CONCAT('Q', EXTRACT(QUARTER FROM PARSE_DATE('%Y%m%d', _TABLE_SUFFIX)), '-', EXTRACT(YEAR FROM PARSE_DATE('%Y%m%d', _TABLE_SUFFIX))) as quarter,
  SUM(metrics_impressions) as impressions,
  SUM(metrics_clicks) as clicks,
  SUM(metrics_cost_micros) / 1000000 as cost,
  SUM(metrics_conversions) as conversions,
  ROUND(SUM(metrics_cost_micros) / NULLIF(SUM(metrics_conversions), 0) / 1000000, 2) as cost_per_conversion,
  ROUND(SUM(metrics_clicks) / NULLIF(SUM(metrics_impressions), 0) * 100, 2) as ctr
FROM `project.dataset.KeywordStats_*`
WHERE _TABLE_SUFFIX BETWEEN '20240101' AND '20251122'
  AND ad_group_criterion_status = 'ENABLED'
GROUP BY campaign_name, ad_group_name, keyword, match_type, quarter
HAVING impressions > 100
ORDER BY campaign_name, ad_group_name, keyword, quarter DESC
```

### Query: Identify Wasted Spend on Non-Converting Keywords

**Business Value**: Find keywords consuming budget without generating conversions, prime candidates for pausing or negative keyword addition.

```sql
-- Keywords with spend but no conversions
SELECT
  campaign_name,
  ad_group_name,
  ad_group_criterion_keyword_text as keyword,
  ad_group_criterion_keyword_match_type as match_type,
  SUM(metrics_impressions) as impressions,
  SUM(metrics_clicks) as clicks,
  SUM(metrics_cost_micros) / 1000000 as cost,
  SUM(metrics_conversions) as conversions,
  ROUND(SUM(metrics_cost_micros) / NULLIF(SUM(metrics_clicks), 0) / 1000000, 2) as avg_cpc
FROM `project.dataset.KeywordStats_*`
WHERE _TABLE_SUFFIX BETWEEN FORMAT_DATE('%Y%m%d', DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY))
  AND FORMAT_DATE('%Y%m%d', CURRENT_DATE())
  AND ad_group_criterion_status = 'ENABLED'
GROUP BY campaign_name, ad_group_name, keyword, match_type
HAVING cost > 50  -- Minimum spend threshold
  AND conversions = 0
ORDER BY cost DESC
LIMIT 500
```

## Match Type Efficiency Analysis

### Query: Compare Match Type Performance

**Business Value**: Determine which match types provide the best ROI to guide bidding strategies and keyword expansion.

```sql
-- Match type performance comparison
SELECT
  ad_group_criterion_keyword_match_type as match_type,
  COUNT(DISTINCT ad_group_criterion_keyword_text) as unique_keywords,
  SUM(metrics_impressions) as total_impressions,
  SUM(metrics_clicks) as total_clicks,
  SUM(metrics_cost_micros) / 1000000 as total_cost,
  SUM(metrics_conversions) as total_conversions,
  ROUND(SUM(metrics_clicks) / NULLIF(SUM(metrics_impressions), 0) * 100, 2) as avg_ctr,
  ROUND(SUM(metrics_cost_micros) / NULLIF(SUM(metrics_clicks), 0) / 1000000, 2) as avg_cpc,
  ROUND(SUM(metrics_cost_micros) / NULLIF(SUM(metrics_conversions), 0) / 1000000, 2) as cost_per_conversion,
  ROUND(SUM(metrics_conversions) / NULLIF(SUM(metrics_clicks), 0) * 100, 2) as conversion_rate
FROM `project.dataset.KeywordStats_*`
WHERE _TABLE_SUFFIX BETWEEN '20240101' AND '20251122'
  AND ad_group_criterion_status = 'ENABLED'
GROUP BY match_type
ORDER BY total_cost DESC
```

### Query: Search Term Match Type Drift Analysis

**Business Value**: Identify how often broad match keywords trigger unintended searches, indicating need for negative keywords.

```sql
-- Analyze search term match type drift
SELECT
  k.ad_group_criterion_keyword_text as keyword,
  k.ad_group_criterion_keyword_match_type as keyword_match_type,
  st.segments_search_term_match_type as search_term_match_type,
  st.segments_search_term as search_term,
  SUM(st.metrics_impressions) as impressions,
  SUM(st.metrics_clicks) as clicks,
  SUM(st.metrics_cost_micros) / 1000000 as cost,
  SUM(st.metrics_conversions) as conversions
FROM `project.dataset.SearchTermStats_*` st
JOIN `project.dataset.KeywordStats_*` k
  ON st.campaign_id = k.campaign_id
  AND st.ad_group_id = k.ad_group_id
  AND st._TABLE_SUFFIX = k._TABLE_SUFFIX
WHERE st._TABLE_SUFFIX BETWEEN '20240801' AND '20251122'
  AND k.ad_group_criterion_keyword_match_type = 'BROAD'
  AND LOWER(st.segments_search_term) != LOWER(k.ad_group_criterion_keyword_text)
GROUP BY keyword, keyword_match_type, search_term_match_type, search_term
HAVING cost > 10
ORDER BY cost DESC
LIMIT 1000
```

## Performance Max Campaign Analysis

### Query: Performance Max Asset Group Performance

**Business Value**: For Performance Max campaigns, identify which asset groups drive the best results.

```sql
-- Performance Max campaign asset group performance
SELECT
  campaign_name,
  asset_group_name,
  SUM(metrics_impressions) as impressions,
  SUM(metrics_clicks) as clicks,
  SUM(metrics_cost_micros) / 1000000 as cost,
  SUM(metrics_conversions) as conversions,
  SUM(metrics_all_conversions_value) / 1000000 as conversion_value,
  ROUND(SUM(metrics_clicks) / NULLIF(SUM(metrics_impressions), 0) * 100, 2) as ctr,
  ROUND(SUM(metrics_cost_micros) / NULLIF(SUM(metrics_conversions), 0) / 1000000, 2) as cost_per_conversion,
  ROUND(SUM(metrics_all_conversions_value) / NULLIF(SUM(metrics_cost_micros), 0), 2) as roas
FROM `project.dataset.AssetGroupStats_*`
WHERE _TABLE_SUFFIX BETWEEN '20240101' AND '20251122'
  AND campaign_advertising_channel_type = 'PERFORMANCE_MAX'
GROUP BY campaign_name, asset_group_name
HAVING impressions > 1000
ORDER BY cost DESC
```

### Query: Performance Max Search Category Performance

**Business Value**: Understand which search categories Performance Max is bidding on to ensure alignment with business goals.

```sql
-- Performance Max search category analysis
SELECT
  campaign_name,
  segments_search_term_view_search_term_category as category,
  SUM(metrics_impressions) as impressions,
  SUM(metrics_clicks) as clicks,
  SUM(metrics_cost_micros) / 1000000 as cost,
  SUM(metrics_conversions) as conversions,
  ROUND(SUM(metrics_cost_micros) / NULLIF(SUM(metrics_conversions), 0) / 1000000, 2) as cost_per_conversion
FROM `project.dataset.SearchTermViewStats_*`
WHERE _TABLE_SUFFIX BETWEEN '20240801' AND '20251122'
  AND campaign_advertising_channel_type = 'PERFORMANCE_MAX'
  AND segments_search_term_view_search_term_category IS NOT NULL
GROUP BY campaign_name, category
HAVING cost > 50
ORDER BY cost DESC
LIMIT 500
```

## Query Optimization Tips

### 1. Use Date Partitioning

```sql
-- Good: Scans only relevant partitions
WHERE _TABLE_SUFFIX BETWEEN '20250101' AND '20250131'

-- Bad: Scans all partitions
WHERE PARSE_DATE('%Y%m%d', _TABLE_SUFFIX) >= '2025-01-01'
```

### 2. Select Only Required Columns

```sql
-- Good: Selects specific columns
SELECT campaign_name, SUM(metrics_cost_micros) as cost
FROM `project.dataset.CampaignStats_*`

-- Bad: Selects all columns
SELECT *
FROM `project.dataset.CampaignStats_*`
```

### 3. Use Appropriate Aggregation Levels

```sql
-- If you need campaign totals, query CampaignStats_*
-- Don't aggregate from KeywordStats_* or SearchTermStats_*
-- This reduces data scanned and improves performance
```

### 4. Preview Query Costs

Before running a query, BigQuery shows estimated bytes processed. Use this to:
- Optimize queries before execution
- Avoid unexpectedly expensive queries
- Compare alternative query approaches

### 5. Use Query Caching

BigQuery caches query results for 24 hours. Identical queries run within this window are free and instant.

## Integration with PaidSearchNav

These queries can be integrated into PaidSearchNav workflows:

1. **Historical Baseline**: Use BigQuery for historical trends before querying the API
2. **Quarterly Audits**: Run comprehensive queries for quarterly reports
3. **Cost Analysis**: Identify wasted spend patterns over extended periods
4. **Seasonal Planning**: Analyze year-over-year patterns for budget planning
5. **Negative Keyword Discovery**: Find consistently poor-performing search terms

## Next Steps

1. **Set Up Alerts**: Create BigQuery scheduled queries with email alerts for anomalies
2. **Build Dashboards**: Connect BigQuery to Data Studio for visual reporting
3. **Automate Exports**: Schedule regular exports of key metrics to Google Sheets
4. **Cost Monitoring**: Set up budget alerts to control BigQuery query costs

## Additional Resources

- [BigQuery SQL Reference](https://cloud.google.com/bigquery/docs/reference/standard-sql/query-syntax)
- [Google Ads Data Transfer Schema](https://developers.google.com/google-ads/api/docs/reporting/overview)
- [BigQuery Best Practices](https://cloud.google.com/bigquery/docs/best-practices-performance-overview)
- [Standard SQL Functions](https://cloud.google.com/bigquery/docs/reference/standard-sql/functions-and-operators)
