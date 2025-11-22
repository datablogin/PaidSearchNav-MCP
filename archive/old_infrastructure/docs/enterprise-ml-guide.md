# Enterprise ML Guide: Causal Inference for PPC Analytics

## Overview

The Enterprise ML module integrates state-of-the-art causal inference methods into PaidSearchNav, providing scientifically rigorous insights for bid optimization, anomaly detection, and automated campaign analysis. This module leverages the extensive CausalInferenceTools library to ensure all insights are based on proper causal relationships rather than mere correlations.

## Key Features

### 🎯 **Causal Bid Optimization**
- Personalized bid recommendations using meta-learners (T-learner, X-learner)
- Heterogeneous treatment effect estimation for keyword-level optimization
- Confidence intervals and statistical significance testing
- ROI impact projections with uncertainty quantification

### 🔍 **Causal Anomaly Detection**
- Detect performance anomalies using rigorous causal methods
- Distinguish between correlation and causation in performance changes
- Automated root cause analysis with causal attribution
- Real-time monitoring with statistical alerting

### 💡 **Automated Causal Insights**
- Generate actionable insights with proper causal interpretation
- Multiple insight templates for different use cases
- Business-friendly explanations of causal relationships
- Sensitivity analysis for robustness checking

### 🧪 **A/B Testing Framework**
- Compare different causal methods scientifically
- Statistical power calculations and early stopping rules
- Comprehensive model validation and diagnostics
- Synthetic data validation with known ground truth

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Enterprise ML API                        │
├─────────────────────────────────────────────────────────────┤
│  /bid-predictions  /anomaly-detection  /insights  /models  │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│                 CausalMLService                             │
├─────────────────────────────────────────────────────────────┤
│  • Bid Optimization    • Anomaly Detection                 │
│  • Insights Generation • Model Training & Evaluation       │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│              CausalInferenceTools Library                  │
├─────────────────────────────────────────────────────────────┤
│  • AIPW, TMLE, G-Computation   • Meta-Learners (T, X, R)  │
│  • Causal Forests              • Sensitivity Analysis      │
│  • Mediation Analysis          • Validation Suite          │
└─────────────────────────────────────────────────────────────┘
```

## Getting Started

### Prerequisites

1. **Enterprise Tier**: ML features require enterprise tier subscription
2. **CausalInferenceTools**: Library must be installed and accessible
3. **Sufficient Data**: Minimum sample sizes vary by method (100-1000+ samples)
4. **Clean Data**: Proper treatment/outcome variables and covariates

### Installation

```bash
# Ensure CausalInferenceTools is available
pip install -e /path/to/CausalInferenceTools/libs/causal_inference

# Install PaidSearchNav with ML dependencies
pip install -e ".[ml,enterprise]"
```

### Configuration

```python
from paidsearchnav.ml.causal_service import CausalMLService, CausalMLConfig

# Configure ML service
config = CausalMLConfig(
    enable_caching=True,
    cache_ttl_hours=24,
    min_training_data_size=100,
    bootstrap_samples=1000,
    random_state=42
)

# Initialize service
ml_service = CausalMLService(config=config)
```

## API Endpoints

### Health Check
```bash
GET /api/v1/enterprise/ml/health
```

Returns ML service status and availability.

### Bid Optimization

#### Generate Bid Recommendations
```bash
POST /api/v1/enterprise/ml/bid-predictions
```

**Request:**
```json
{
  "customer_id": "customer_123",
  "keyword_data": {
    "dataframe": [
      {
        "keyword_id": "kw1",
        "keyword_text": "running shoes",
        "current_bid": 2.50,
        "impressions": 10000,
        "clicks": 500,
        "conversions": 25,
        "cost": 1250.0,
        "revenue": 2500.0,
        "quality_score": 7.2
      }
    ]
  },
  "method": "t_learner",
  "target_metric": "conversion_rate",
  "max_recommendations": 50
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "customer_id": "customer_123",
    "method_used": "t_learner",
    "recommendations": [
      {
        "keyword_id": "kw1",
        "keyword_text": "running shoes",
        "current_bid": 2.50,
        "recommended_bid": 3.10,
        "expected_effect": 0.15,
        "confidence_interval": [0.08, 0.22],
        "p_value": 0.003,
        "expected_conversions": 28.75,
        "roi_improvement": 15.2,
        "reasoning": "T-learner analysis suggests bid increase will improve conversion rate",
        "method_used": "t_learner",
        "model_confidence": 0.92
      }
    ],
    "total_recommendations": 1
  }
}
```

### Anomaly Detection

#### Detect Performance Anomalies
```bash
POST /api/v1/enterprise/ml/anomaly-detection
```

**Request:**
```json
{
  "customer_id": "customer_123",
  "performance_data": {
    "dataframe": [
      {
        "campaign_id": "camp1",
        "date": "2024-01-15",
        "impressions": 5000,
        "clicks": 150,
        "conversions": 8,
        "cost": 375.0,
        "revenue": 800.0
      }
    ]
  },
  "detection_window_days": 7,
  "target_metrics": ["conversion_rate", "roas", "ctr"],
  "method": "aipw"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "customer_id": "customer_123",
    "anomalies": [
      {
        "anomaly_id": "anom_456",
        "anomaly_type": "conversion_rate_anomaly",
        "severity": "high",
        "confidence_score": 0.94,
        "affected_metrics": ["conversion_rate"],
        "baseline_values": {"conversion_rate": 0.055},
        "observed_values": {"conversion_rate": 0.032},
        "deviation_magnitude": 0.023,
        "potential_causes": [
          "Landing page issues",
          "Technical website problems",
          "Increased competition"
        ],
        "recommended_actions": [
          "Review landing page performance",
          "Check website functionality",
          "Analyze user journey data"
        ],
        "method_used": "aipw",
        "false_positive_probability": 0.05
      }
    ],
    "total_anomalies": 1,
    "critical_anomalies": 0,
    "high_priority_anomalies": 1
  }
}
```

### Insights Generation

#### Generate Automated Insights
```bash
POST /api/v1/enterprise/ml/insights
```

**Request:**
```json
{
  "customer_id": "customer_123",
  "analysis_data": {
    "dataframe": [
      {
        "campaign_id": "camp1",
        "treatment": "bid_increase",
        "outcome_metrics": {
          "conversions": 15,
          "revenue": 1500.0
        },
        "covariates": {
          "impressions": 8000,
          "device": "mobile",
          "quality_score": 8.1
        }
      }
    ]
  },
  "max_insights": 10
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "insights": [
      {
        "insight_id": "insight_789",
        "insight_type": "positive_effect",
        "title": "Bid Optimization Impact: Positive Impact Detected",
        "description": "Bid increase of $0.50 caused a positive effect of 0.125 on conversions with 95% confidence",
        "effect_size": 0.125,
        "confidence_interval": [0.06, 0.19],
        "p_value": 0.002,
        "priority": "high",
        "actionable": true,
        "estimated_impact": 1250.0,
        "method_used": "aipw"
      }
    ],
    "summary": {
      "total": 1,
      "by_type": {"positive_effect": 1},
      "by_priority": {"high": 1},
      "actionable": 1
    }
  }
}
```

### Model Training

#### Train Custom Model
```bash
POST /api/v1/enterprise/ml/custom-models
```

**Request:**
```json
{
  "customer_id": "customer_123",
  "model_type": "bid_optimization",
  "training_data": {
    "dataframe": [/* training data */]
  },
  "method": "causal_forest",
  "model_name": "bidding_model_v1"
}
```

#### Get Model Status
```bash
GET /api/v1/enterprise/ml/custom-models/{model_id}
```

#### List Customer Models
```bash
GET /api/v1/enterprise/ml/custom-models?customer_id={customer_id}
```

## Causal Methods

### Overview of Methods

| Method | Best For | Sample Size | Robustness | Interpretability |
|--------|----------|-------------|------------|------------------|
| **G-Computation** | Simple cases, small samples | 100+ | Medium | High |
| **IPW** | When treatment model is reliable | 500+ | Medium | Medium |
| **AIPW** | General use, double robustness | 1000+ | High | Medium |
| **TMLE** | Efficiency, complex models | 1000+ | High | Low |
| **T-Learner** | Heterogeneous effects | 1000+ | Medium | High |
| **X-Learner** | Imbalanced treatments | 500+ | Medium | High |
| **Causal Forest** | Personalization, many features | 2000+ | High | Low |

### Method Selection Guidelines

#### For Bid Optimization:
- **Small datasets (< 1000)**: G-Computation or IPW
- **Medium datasets (1000-5000)**: T-Learner or AIPW
- **Large datasets (5000+)**: Causal Forest or X-Learner
- **Imbalanced treatments**: X-Learner or AIPW

#### For Anomaly Detection:
- **Time series**: AIPW with time-varying covariates
- **Complex patterns**: Causal Forest
- **Simple detection**: G-Computation

#### For Insights Generation:
- **Business explanations**: T-Learner or G-Computation
- **Robust estimates**: AIPW or TMLE
- **Heterogeneity analysis**: Causal Forest

## Data Requirements

### Minimum Data Standards

#### For Bid Optimization:
```python
required_columns = [
    'keyword_id',           # Unique identifier
    'current_bid',          # Current bid amount
    'impressions',          # Number of impressions
    'clicks',              # Number of clicks
    'conversions',         # Number of conversions
    'cost',               # Total cost
    'revenue',            # Total revenue
    'quality_score',      # Google Ads quality score (optional)
]

minimum_sample_size = 100  # Per keyword
```

#### For Anomaly Detection:
```python
required_columns = [
    'date',               # Time identifier
    'campaign_id',        # Campaign identifier
    'impressions',        # Performance metrics
    'clicks',
    'conversions',
    'cost',
    'revenue',
]

minimum_time_periods = 30  # Days of data
```

### Data Quality Checks

1. **Completeness**: No missing values in key columns
2. **Consistency**: Data types and formats are correct
3. **Variation**: Sufficient variation in treatment and outcomes
4. **Outliers**: Extreme values identified and handled
5. **Temporal**: Proper time ordering for time series data

## Model Validation

### Validation Framework

The enterprise ML module includes comprehensive validation:

1. **Synthetic Data Validation**: Test on data with known ground truth
2. **Cross-Validation**: K-fold validation for robustness
3. **Orthogonality Checks**: Verify causal assumptions
4. **Balance Diagnostics**: Assess covariate balance
5. **Sensitivity Analysis**: Test robustness to assumptions

### Validation Metrics

```python
validation_results = {
    "ate_bias": 0.02,              # Bias in treatment effect estimate
    "ate_rmse": 0.15,              # Root mean square error
    "coverage_probability": 0.94,   # CI coverage rate
    "orthogonality_score": 0.85,   # Orthogonality condition
    "balance_score": 0.78,         # Covariate balance
    "overlap_score": 0.92,         # Propensity overlap
    "validation_passed": true,     # Overall validation result
    "risk_level": "low"            # Risk assessment
}
```

## Best Practices

### Data Preparation
1. **Clean Data**: Remove duplicates, handle missing values
2. **Feature Engineering**: Create relevant covariates
3. **Treatment Definition**: Clearly define treatment variables
4. **Outcome Measurement**: Ensure accurate outcome tracking

### Method Selection
1. **Start Simple**: Begin with G-Computation or AIPW
2. **Check Assumptions**: Validate causal assumptions
3. **Compare Methods**: Use A/B testing framework
4. **Validate Results**: Always perform robustness checks

### Interpretation
1. **Causal Language**: Use "caused by" not "associated with"
2. **Uncertainty**: Always report confidence intervals
3. **Business Context**: Relate findings to business metrics
4. **Actionability**: Provide clear recommendations

### Monitoring
1. **Model Drift**: Monitor model performance over time
2. **Data Quality**: Continuous data quality monitoring
3. **A/B Testing**: Regular testing of model improvements
4. **Business Impact**: Track actual vs predicted outcomes

## Troubleshooting

### Common Issues

#### "CausalInferenceTools not available"
- Ensure library is installed in Python path
- Check import paths and dependencies
- Verify library compatibility

#### "Insufficient data for analysis"
- Increase sample size (minimum 100-1000 depending on method)
- Aggregate data across time periods if needed
- Consider simpler methods for small samples

#### "No significant treatment effect"
- Check treatment variable definition
- Verify sufficient treatment variation
- Consider confounding variables
- Try different causal methods

#### "Model validation failed"
- Review data quality and completeness
- Check for violations of causal assumptions
- Consider different modeling approaches
- Examine sensitivity analysis results

### Error Codes

| Code | Description | Resolution |
|------|-------------|------------|
| `E001` | Missing required columns | Check data schema |
| `E002` | Insufficient sample size | Increase data volume |
| `E003` | No treatment variation | Review treatment definition |
| `E004` | Model convergence failure | Try different method |
| `E005` | Validation failure | Review assumptions |

## Performance Optimization

### Caching Strategy
- Model predictions cached for 24 hours
- Training results stored for reuse
- Configurable cache TTL

### Parallel Processing
- Multi-threaded model training
- Batch processing for large datasets
- Asynchronous API endpoints

### Memory Management
- Streaming data processing for large files
- Automatic memory cleanup
- Configurable batch sizes

## Security & Privacy

### Data Protection
- All data encrypted in transit and at rest
- No sensitive data logged
- Customer data isolation

### Access Control
- Enterprise tier required for ML features
- Customer-level access control
- Admin-only management endpoints

### Audit Logging
- All ML operations logged
- Model training and deployment tracked
- API access monitoring

## Support

### Documentation
- API reference: `/docs/api-reference`
- Method guides: `/docs/methods`
- Examples: `/docs/examples`

### Monitoring
- Health checks: `/enterprise/ml/health`
- Performance metrics available
- Error alerting configured

### Contact
- Technical support: support@paidsearchnav.com
- Enterprise success manager for implementation guidance
- Community forum for best practices

---

*This guide covers the enterprise ML capabilities in PaidSearchNav. For additional support or advanced use cases, contact your enterprise success manager.*