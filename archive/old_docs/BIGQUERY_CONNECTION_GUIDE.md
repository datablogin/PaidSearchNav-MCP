# PaidSearchNav BigQuery Integration Guide

## 🎯 Overview

This guide explains how to connect PaidSearchNav to Google BigQuery for premium analytics capabilities. The integration supports three service tiers:

- **🥉 Standard**: CSV-only analysis (existing functionality)  
- **🥈 Premium**: BigQuery real-time analytics
- **🥇 Enterprise**: BigQuery ML + predictive models

## 🔧 Connection Methods

### Method 1: Application Default Credentials (Recommended for GCP)

**Best for**: Applications running on Google Cloud Platform

```bash
# Install Google Cloud SDK
gcloud auth application-default login

# Set environment variables
export PSN_BIGQUERY__ENABLED=true
export PSN_BIGQUERY__TIER=premium  
export PSN_BIGQUERY__PROJECT_ID=your-project-id
export PSN_BIGQUERY__USE_DEFAULT_CREDENTIALS=true
```

### Method 2: Service Account Key File

**Best for**: Local development or non-GCP environments

1. **Create Service Account**:
   ```bash
   gcloud iam service-accounts create paidsearchnav-bigquery \
     --display-name="PaidSearchNav BigQuery Service Account"
   ```

2. **Grant Permissions**:
   ```bash
   gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
     --member="serviceAccount:paidsearchnav-bigquery@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
     --role="roles/bigquery.admin"
   ```

3. **Download Key File**:
   ```bash
   gcloud iam service-accounts keys create ~/paidsearchnav-bigquery.json \
     --iam-account=paidsearchnav-bigquery@YOUR_PROJECT_ID.iam.gserviceaccount.com
   ```

4. **Configure Environment**:
   ```bash
   export PSN_BIGQUERY__ENABLED=true
   export PSN_BIGQUERY__TIER=premium
   export PSN_BIGQUERY__PROJECT_ID=your-project-id
   export PSN_BIGQUERY__SERVICE_ACCOUNT_PATH=/path/to/service-account.json
   ```

### Method 3: Service Account JSON (For Containers)

**Best for**: Docker containers or CI/CD environments

```bash
export PSN_BIGQUERY__ENABLED=true
export PSN_BIGQUERY__TIER=premium
export PSN_BIGQUERY__PROJECT_ID=your-project-id
export PSN_BIGQUERY__SERVICE_ACCOUNT_JSON='{"type":"service_account","project_id":"your-project",...}'
```

## 📊 BigQuery Setup

### 1. Create BigQuery Dataset

```sql
-- Option 1: Using BigQuery Console
CREATE SCHEMA `your-project-id.paid_search_nav`
OPTIONS (
  location = "US",
  description = "PaidSearchNav analyzer data warehouse"
);

-- Option 2: Using bq command line
bq mk --dataset --location=US your-project-id:paid_search_nav
```

### 2. Set Up Cost Controls

```sql
-- Create budget alert (optional)
-- This requires Google Cloud Billing API
```

### 3. Test Connection

Use the PaidSearchNav API to test the connection:

```bash
# Health check
curl http://localhost:8000/api/v1/bigquery/health

# Configuration check  
curl http://localhost:8000/api/v1/bigquery/config

# Permission test
curl http://localhost:8000/api/v1/bigquery/permissions
```

## 🚀 API Endpoints

### Health & Configuration

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/bigquery/health` | GET | Check BigQuery connectivity |
| `/api/v1/bigquery/config` | GET | View configuration (non-sensitive) |
| `/api/v1/bigquery/usage` | GET | Get usage statistics |
| `/api/v1/bigquery/permissions` | GET | Test permissions |
| `/api/v1/bigquery/cost-alerts` | GET | Check cost alerts |

### Premium Analytics (Premium Tier)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/bigquery/analytics/search-terms` | GET | Search terms insights |
| `/api/v1/bigquery/setup` | POST | Initialize dataset/tables |

### ML Features (Enterprise Tier)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/bigquery/analytics/bid-recommendations` | GET | ML-powered bid recommendations |

## 🔐 Required Permissions

### Minimum Permissions (Premium Tier)

```json
{
  "bindings": [
    {
      "role": "roles/bigquery.dataViewer",
      "members": ["serviceAccount:paidsearchnav-bigquery@PROJECT.iam.gserviceaccount.com"]
    },
    {
      "role": "roles/bigquery.jobUser", 
      "members": ["serviceAccount:paidsearchnav-bigquery@PROJECT.iam.gserviceaccount.com"]
    },
    {
      "role": "roles/bigquery.dataEditor",
      "members": ["serviceAccount:paidsearchnav-bigquery@PROJECT.iam.gserviceaccount.com"]
    }
  ]
}
```

### Full Permissions (Enterprise Tier)

```bash
# Grant BigQuery Admin for full functionality
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:paidsearchnav-bigquery@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/bigquery.admin"
```

## 💰 Cost Management

### Automatic Cost Controls

The application includes built-in cost management:

```bash
# Daily cost limits
export PSN_BIGQUERY__DAILY_COST_LIMIT_USD=100.0
export PSN_BIGQUERY__COST_ALERT_THRESHOLD_USD=80.0

# Query limits  
export PSN_BIGQUERY__MAX_QUERY_BYTES=1000000000  # 1GB per query
export PSN_BIGQUERY__QUERY_TIMEOUT_SECONDS=60
```

### Cost Monitoring

```bash
# Check current usage
curl "http://localhost:8000/api/v1/bigquery/usage?customer_id=646-990-6417"

# Check cost alerts
curl "http://localhost:8000/api/v1/bigquery/cost-alerts?customer_id=646-990-6417"
```

## 📈 Service Tiers

### Standard Tier (Free)
- ✅ CSV-based analysis
- ✅ All existing analyzers
- ❌ No BigQuery features

```bash
export PSN_BIGQUERY__ENABLED=false
export PSN_BIGQUERY__TIER=disabled
```

### Premium Tier ($X + BigQuery costs)
- ✅ Real-time BigQuery analytics
- ✅ Advanced SQL queries
- ✅ Cost monitoring
- ❌ No ML features

```bash
export PSN_BIGQUERY__ENABLED=true
export PSN_BIGQUERY__TIER=premium
export PSN_BIGQUERY__PROJECT_ID=your-project-id
```

### Enterprise Tier (Custom pricing)
- ✅ All Premium features
- ✅ BigQuery ML models
- ✅ Predictive analytics
- ✅ Custom ML models

```bash
export PSN_BIGQUERY__ENABLED=true
export PSN_BIGQUERY__TIER=enterprise
export PSN_BIGQUERY__ENABLE_ML_MODELS=true
export PSN_BIGQUERY__DAILY_COST_LIMIT_USD=500.0
```

## 🔧 Troubleshooting

### Common Issues

1. **Authentication Errors**
   ```bash
   # Check credentials
   gcloud auth list
   
   # Test BigQuery access
   bq ls your-project-id:
   ```

2. **Permission Denied**
   ```bash
   # Verify service account permissions
   gcloud projects get-iam-policy YOUR_PROJECT_ID \
     --flatten="bindings[].members" \
     --filter="bindings.members:paidsearchnav-bigquery"
   ```

3. **Dataset Not Found**
   ```bash
   # Create dataset manually
   bq mk --dataset --location=US your-project-id:paid_search_nav
   ```

4. **Cost Alerts**
   ```bash
   # Check current usage
   curl http://localhost:8000/api/v1/bigquery/cost-alerts
   ```

### Debug Mode

Enable detailed logging:

```bash
export PSN_DEBUG=true
export PSN_LOGGING__LEVEL=DEBUG
```

## 📚 Dependencies

### Required Python Packages

```bash
# Install BigQuery client
pip install google-cloud-bigquery

# For authentication
pip install google-auth google-auth-oauthlib google-auth-httplib2
```

### Docker Setup

```dockerfile
# Add to Dockerfile
RUN pip install google-cloud-bigquery google-auth

# Mount service account key
COPY service-account.json /app/service-account.json
ENV PSN_BIGQUERY__SERVICE_ACCOUNT_PATH=/app/service-account.json
```

## 🎪 Example: Complete Setup

```bash
#!/bin/bash
# Complete BigQuery setup script

# 1. Set project
export PROJECT_ID="fitness-connection-469620"
gcloud config set project $PROJECT_ID

# 2. Enable APIs
gcloud services enable bigquery.googleapis.com
gcloud services enable cloudbilling.googleapis.com

# 3. Create service account
gcloud iam service-accounts create paidsearchnav-bigquery

# 4. Grant permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:paidsearchnav-bigquery@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/bigquery.admin"

# 5. Create key
gcloud iam service-accounts keys create ~/paidsearchnav-bigquery.json \
  --iam-account=paidsearchnav-bigquery@$PROJECT_ID.iam.gserviceaccount.com

# 6. Create dataset
bq mk --dataset --location=US $PROJECT_ID:paid_search_nav

# 7. Configure PaidSearchNav
export PSN_BIGQUERY__ENABLED=true
export PSN_BIGQUERY__TIER=premium
export PSN_BIGQUERY__PROJECT_ID=$PROJECT_ID
export PSN_BIGQUERY__SERVICE_ACCOUNT_PATH=~/paidsearchnav-bigquery.json

# 8. Test connection
curl http://localhost:8000/api/v1/bigquery/health

echo "✅ BigQuery integration setup complete!"
```

## 🚀 Next Steps

1. **Start with Standard tier** to test existing functionality
2. **Upgrade to Premium** when ready for real-time analytics  
3. **Move to Enterprise** for ML-powered insights
4. **Monitor costs** regularly using built-in alerts
5. **Scale up** BigQuery resources as data volume grows

The BigQuery integration is designed to be **cost-aware** and **scalable**, allowing you to start small and grow as your business needs expand.