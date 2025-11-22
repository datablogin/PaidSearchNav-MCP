# BigQuery Premium Tier Implementation Plan

## 🎯 **Strategic Overview**

**Goal**: Add BigQuery-powered premium tier while maintaining CSV-based standard tier

**Business Model**: 
- Standard Tier: CSV-based (current pricing)
- Premium Tier: BigQuery real-time (higher margin)
- Enterprise Tier: BigQuery ML (custom pricing)

## 📋 **Phase 1: BigQuery Schema Design**

### **GitHub Issue: #500 - Design BigQuery Data Warehouse Schema**

**Description**: Create comprehensive BigQuery schema for all 20 analyzers

**Acceptance Criteria**:
- [ ] Schema supports all existing analyzer data structures
- [ ] Optimized for query performance (partitioning, clustering)
- [ ] Backward compatible with CSV exports
- [ ] Supports real-time streaming inserts

**KPIs**:
- Query performance: <2 seconds for analyzer queries
- Storage efficiency: <50% increase vs CSV storage
- Schema coverage: 100% of analyzer fields mapped

**Implementation**:
```sql
-- Core tables for all analyzers
CREATE TABLE `paid_search_nav.search_terms` (
    date DATE,
    campaign_id STRING,
    campaign_name STRING,
    ad_group_id STRING, 
    ad_group_name STRING,
    search_term STRING,
    match_type STRING,
    impressions INT64,
    clicks INT64,
    cost FLOAT64,
    conversions FLOAT64,
    ctr FLOAT64,
    cpc FLOAT64,
    local_intent_score FLOAT64,
    quality_score FLOAT64,
    negative_recommendation STRING,
    created_at TIMESTAMP
)
PARTITION BY date
CLUSTER BY campaign_id, ad_group_id;
```

**Tests**:
- Schema validation tests
- Performance benchmark tests
- Data type compatibility tests

---

## 📋 **Phase 2: Dual-Mode Data Pipeline**

### **GitHub Issue: #501 - Implement Hybrid Data Pipeline**

**Description**: Modify mega-script to support both CSV export AND BigQuery streaming

**Acceptance Criteria**:
- [ ] Single script generates both CSV and BigQuery data
- [ ] Customer configurable: CSV-only, BigQuery-only, or both
- [ ] Error handling for BigQuery failures (fallback to CSV)
- [ ] Cost tracking for BigQuery usage

**KPIs**:
- Pipeline success rate: >99%
- BigQuery streaming latency: <30 seconds
- Cost predictability: ±10% of estimates

**Implementation**:
```javascript
function dualModeExtraction(config) {
    var results = extractAnalyzerData();
    
    // Always generate CSVs (fallback)
    if (config.csvEnabled) {
        exportToCSV(results);
    }
    
    // Stream to BigQuery if enabled
    if (config.bigqueryEnabled) {
        streamToBigQuery(results);
    }
    
    return results;
}
```

**Tests**:
- Integration tests for both modes
- Failure scenario tests
- Cost calculation tests

---

## 📋 **Phase 3: BigQuery Analytics Engine**

### **GitHub Issue: #502 - Replace Analyzer Logic with SQL Views**

**Description**: Create SQL views that replicate all 20 Python analyzers

**Acceptance Criteria**:
- [ ] 100% feature parity with Python analyzers
- [ ] SQL views for all recommendation algorithms
- [ ] Real-time analysis capability
- [ ] Performance optimized queries

**KPIs**:
- Analysis speed: 10x faster than CSV parsing
- Result accuracy: 100% match with Python analyzers
- Real-time capability: <5 minute data freshness

**Implementation**:
```sql
-- Search Terms Analyzer View
CREATE VIEW analyzer_search_terms_recommendations AS
SELECT 
    search_term,
    campaign_name,
    SUM(cost) as total_cost,
    SUM(conversions) as total_conversions,
    AVG(local_intent_score) as avg_local_intent,
    CASE 
        WHEN SUM(conversions) = 0 AND SUM(cost) > 50 THEN 'HIGH_PRIORITY_NEGATIVE'
        WHEN AVG(local_intent_score) < 0.3 THEN 'CONSIDER_NEGATIVE'
        ELSE 'KEEP_ACTIVE' 
    END as recommendation_type,
    CURRENT_TIMESTAMP() as analysis_timestamp
FROM `paid_search_nav.search_terms`
WHERE date >= DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY)
GROUP BY search_term, campaign_name;
```

**Tests**:
- SQL logic validation tests
- Performance regression tests
- Data accuracy tests vs Python

---

## 📋 **Phase 4: Premium API Integration**

### **GitHub Issue: #503 - Build BigQuery-Powered API Endpoints**

**Description**: Create new premium API endpoints that query BigQuery directly

**Acceptance Criteria**:
- [ ] New `/premium/analytics/` endpoints
- [ ] Real-time data serving
- [ ] Advanced filtering and aggregation
- [ ] Cost-aware query optimization

**KPIs**:
- API response time: <500ms for standard queries
- Concurrent users: 100+ without degradation
- Cost per query: <$0.01

**Implementation**:
```python
@router.get("/premium/analytics/search-terms")
async def get_search_terms_analytics(
    customer_id: str,
    date_range: Optional[str] = "30d",
    settings: Settings = Depends(get_settings)
):
    if not settings.bigquery_enabled:
        raise HTTPException(status_code=402, detail="Premium tier required")
    
    client = bigquery.Client(project=settings.bigquery_project)
    query = f"""
    SELECT * FROM `paid_search_nav.analyzer_search_terms_recommendations`
    WHERE customer_id = '{customer_id}'
    AND analysis_timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {parse_date_range(date_range)})
    ORDER BY total_cost DESC
    LIMIT 1000
    """
    
    return client.query(query).to_dataframe().to_dict('records')
```

**Tests**:
- API integration tests
- Load testing
- Cost monitoring tests

---

## 📋 **Phase 5: Advanced BigQuery ML Features**

### **GitHub Issue: #504 - Implement BigQuery ML Predictive Analytics**

**Description**: Add ML-powered features using BigQuery ML

**Acceptance Criteria**:
- [ ] Predictive bid recommendations
- [ ] Anomaly detection for campaigns
- [ ] Automated insights generation
- [ ] Custom ML models per customer

**KPIs**:
- Model accuracy: >85% for bid predictions
- Insight generation: 50+ insights per analysis
- Customer engagement: 30% increase in premium conversions

**Implementation**:
```sql
-- Create ML model for bid optimization
CREATE OR REPLACE MODEL `paid_search_nav.bid_optimization_model`
OPTIONS(
    model_type='linear_reg',
    input_label_cols=['optimal_bid']
) AS
SELECT
    impressions,
    clicks,
    cost,
    conversions,
    ctr,
    local_intent_score,
    quality_score,
    optimal_bid
FROM `paid_search_nav.training_data`
WHERE date >= DATE_SUB(CURRENT_DATE(), INTERVAL 365 DAY);
```

**Tests**:
- ML model validation tests
- Prediction accuracy tests
- Feature engineering tests

---

## 🎯 **Implementation Strategy**

### **Recommended Approach: Incremental with GitHub Issues**

**Why break into phases?**
1. **Risk Mitigation**: Each phase can be tested independently
2. **Customer Validation**: Get feedback before full investment
3. **Cost Control**: Monitor BigQuery costs at each stage
4. **Revenue Generation**: Start charging for premium features early

### **Success Metrics by Phase**

**Phase 1**: Schema design completed, performance benchmarks met
**Phase 2**: Dual-mode pipeline deployed, customer choice enabled  
**Phase 3**: SQL analytics match Python accuracy, 10x speed improvement
**Phase 4**: Premium APIs live, revenue from BigQuery tier
**Phase 5**: ML features deployed, enterprise customers acquired

### **Estimated Timeline**

- **Phase 1**: 1 week (schema design)
- **Phase 2**: 2 weeks (dual pipeline)
- **Phase 3**: 3 weeks (SQL analytics)
- **Phase 4**: 2 weeks (premium APIs)
- **Phase 5**: 4 weeks (ML features)

**Total**: ~3 months for full BigQuery premium tier

### **Cost Management Strategy**

1. **Usage Monitoring**: Track BigQuery costs per customer
2. **Query Optimization**: Cache results, optimize SQL
3. **Tier Pricing**: Pass BigQuery costs to premium customers
4. **Cost Alerts**: Automatic alerts for unusual usage

## 🚀 **Next Steps**

1. **Create GitHub issues** for each phase
2. **Start with Phase 1** (schema design)
3. **Set up BigQuery cost monitoring**
4. **Design premium tier pricing**
5. **Plan customer migration strategy**

This approach gives us:
- ✅ **Revenue diversification** (standard + premium tiers)
- ✅ **Technical innovation** (BigQuery ML capabilities) 
- ✅ **Risk management** (incremental implementation)
- ✅ **Customer choice** (CSV or BigQuery based on budget)