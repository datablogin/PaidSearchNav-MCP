# BigQuery Deployment Guide

Complete deployment guide for setting up the BigQuery hybrid pipeline in development, staging, and production environments.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Google Cloud Setup](#google-cloud-setup)
3. [Environment Configuration](#environment-configuration)
4. [Development Deployment](#development-deployment)
5. [Production Deployment](#production-deployment)
6. [Verification and Testing](#verification-and-testing)
7. [Monitoring Setup](#monitoring-setup)
8. [Maintenance Procedures](#maintenance-procedures)

## Prerequisites

### System Requirements

- **Docker**: Version 20.10 or higher
- **Kubernetes**: Version 1.21 or higher (for production)
- **Python**: Version 3.10 or higher
- **PostgreSQL**: Version 13 or higher
- **Redis**: Version 6.0 or higher

### Access Requirements

- **Google Cloud Project**: With billing enabled
- **BigQuery API**: Enabled in the project
- **IAM Permissions**: To create service accounts and assign roles
- **Container Registry**: Access to push/pull Docker images

### Network Requirements

```bash
# Required outbound connections
443/tcp  # HTTPS to Google APIs
5432/tcp # PostgreSQL (if external)
6379/tcp # Redis (if external)
9090/tcp # Prometheus (if monitoring enabled)
```

## Google Cloud Setup

### 1. Enable Required APIs

```bash
# Enable necessary Google Cloud APIs
gcloud services enable bigquery.googleapis.com
gcloud services enable bigquerystorage.googleapis.com
gcloud services enable cloudresourcemanager.googleapis.com
gcloud services enable iam.googleapis.com
```

### 2. Create Service Account

```bash
# Create service account for BigQuery access
gcloud iam service-accounts create paidsearchnav-bigquery \
  --display-name="PaidSearchNav BigQuery Service Account" \
  --description="Service account for PaidSearchNav BigQuery operations"

# Get the service account email
SA_EMAIL=$(gcloud iam service-accounts list \
  --filter="displayName:PaidSearchNav BigQuery Service Account" \
  --format="value(email)")

echo "Service Account: $SA_EMAIL"
```

### 3. Assign IAM Roles

```bash
# Assign required roles to the service account
ROLES=(
  "roles/bigquery.dataEditor"
  "roles/bigquery.jobUser"
  "roles/bigquery.metadataViewer"
  "roles/bigquery.resourceViewer"
)

for ROLE in "${ROLES[@]}"; do
  gcloud projects add-iam-policy-binding $GOOGLE_CLOUD_PROJECT \
    --member="serviceAccount:$SA_EMAIL" \
    --role="$ROLE"
done
```

### 4. Create and Download Service Account Key

```bash
# Create service account key
gcloud iam service-accounts keys create service-account-key.json \
  --iam-account=$SA_EMAIL

# Secure the key file
chmod 600 service-account-key.json
```

### 5. Create BigQuery Datasets

```bash
# Create main analytics dataset
bq mk --dataset \
  --location=US \
  --description="PaidSearchNav analytics data" \
  $GOOGLE_CLOUD_PROJECT:paidsearchnav_analytics

# Create staging dataset
bq mk --dataset \
  --location=US \
  --description="PaidSearchNav staging data" \
  $GOOGLE_CLOUD_PROJECT:paidsearchnav_staging

# Verify datasets
bq ls --project_id=$GOOGLE_CLOUD_PROJECT
```

## Environment Configuration

### Base Configuration Template

Create a `.env` file with the following template:

```bash
# =============================================================================
# PaidSearchNav BigQuery Configuration
# =============================================================================

# Environment
ENV=development  # development, staging, production
DEBUG=true

# Google Cloud Configuration
GOOGLE_CLOUD_PROJECT=your-gcp-project-id
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json
BIGQUERY_LOCATION=US
BIGQUERY_DATASET=paidsearchnav_analytics
BIGQUERY_STAGING_DATASET=paidsearchnav_staging

# Database Configuration
DATABASE_URL=postgresql://user:password@localhost:5432/paidsearchnav
REDIS_URL=redis://localhost:6379/0

# Authentication
JWT_SECRET_KEY=your-secret-key-generate-a-secure-one
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# BigQuery Cost Monitoring
PSN_BIGQUERY_COST_MONITORING_ENABLED=true
PSN_BIGQUERY_ALERT_COOLDOWN_HOURS=1
PSN_BIGQUERY_EMERGENCY_LIMIT_MULTIPLIER=5

# Budget Limits (USD)
PSN_STANDARD_DAILY_LIMIT=10.00
PSN_PREMIUM_DAILY_LIMIT=50.00
PSN_ENTERPRISE_DAILY_LIMIT=200.00
PSN_STANDARD_MONTHLY_LIMIT=300.00
PSN_PREMIUM_MONTHLY_LIMIT=1500.00
PSN_ENTERPRISE_MONTHLY_LIMIT=6000.00

# Rate Limits
PSN_RATE_LIMIT_REAL_TIME=10/minute
PSN_RATE_LIMIT_BUDGET_ENFORCEMENT=20/minute
PSN_RATE_LIMIT_ANALYTICS=5/minute
PSN_RATE_LIMIT_REPORTS=5/minute
PSN_RATE_LIMIT_BUDGET_CONFIG=10/minute

# Logging and Monitoring
LOG_LEVEL=INFO
LOG_FORMAT=json
PSN_ENABLE_CORRELATION_IDS=true
PSN_METRICS_ENABLED=false
PSN_TRACING_ENABLED=false

# Security
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8080
ALLOWED_METHODS=GET,POST,PUT,DELETE,OPTIONS
ALLOWED_HEADERS=Content-Type,Authorization,X-Correlation-ID
```

### Environment-Specific Configurations

#### Development Environment

```bash
# development.env
ENV=development
DEBUG=true
LOG_LEVEL=DEBUG

# Relaxed limits for testing
PSN_STANDARD_DAILY_LIMIT=1.00
PSN_PREMIUM_DAILY_LIMIT=5.00
PSN_ENTERPRISE_DAILY_LIMIT=10.00

# Higher rate limits for development
PSN_RATE_LIMIT_REAL_TIME=100/minute
PSN_RATE_LIMIT_ANALYTICS=50/minute

# Local services
DATABASE_URL=postgresql://localhost:5432/paidsearchnav_dev
REDIS_URL=redis://localhost:6379/1
```

#### Staging Environment

```bash
# staging.env
ENV=staging
DEBUG=false
LOG_LEVEL=DEBUG

# Production-like but with safety nets
PSN_STANDARD_DAILY_LIMIT=2.00
PSN_PREMIUM_DAILY_LIMIT=10.00
PSN_ENTERPRISE_DAILY_LIMIT=25.00

# Disable real alerts in staging
PSN_ALERT_MANAGER_ENABLED=false

# Staging-specific URLs
DATABASE_URL=postgresql://staging-db:5432/paidsearchnav
REDIS_URL=redis://staging-redis:6379/0
```

#### Production Environment

```bash
# production.env
ENV=production
DEBUG=false
LOG_LEVEL=INFO

# Full production limits
PSN_STANDARD_DAILY_LIMIT=10.00
PSN_PREMIUM_DAILY_LIMIT=50.00
PSN_ENTERPRISE_DAILY_LIMIT=200.00

# Enable all monitoring
PSN_METRICS_ENABLED=true
PSN_TRACING_ENABLED=true
PSN_ALERT_MANAGER_ENABLED=true

# Production security
ALLOWED_ORIGINS=https://app.paidsearchnav.com
JWT_EXPIRATION_HOURS=8

# Production services (use secrets management)
DATABASE_URL=${DATABASE_URL_SECRET}
REDIS_URL=${REDIS_URL_SECRET}
```

## Development Deployment

### 1. Local Development Setup

```bash
# Clone repository
git clone https://github.com/datablogin/PaidSearchNav.git
cd PaidSearchNav

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -e ".[dev,test]"

# Set up environment variables
cp docs/bigquery/deployment/development.env .env
# Edit .env with your specific values

# Start local dependencies
docker-compose up -d postgres redis

# Run database migrations
alembic upgrade head

# Start the application
uvicorn paidsearchnav.api.main:app --reload --port 8000
```

### 2. Docker Development Setup

```dockerfile
# Dockerfile.dev
FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy application code
COPY . .

# Install in development mode
RUN pip install -e ".[dev,test]"

# Expose port
EXPOSE 8000

# Development command
CMD ["uvicorn", "paidsearchnav.api.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"]
```

```yaml
# docker-compose.dev.yml
version: '3.8'

services:
  app:
    build:
      context: .
      dockerfile: Dockerfile.dev
    ports:
      - "8000:8000"
    env_file:
      - .env
    volumes:
      - .:/app
      - ./service-account-key.json:/app/service-account-key.json:ro
    depends_on:
      - postgres
      - redis

  postgres:
    image: postgres:13
    environment:
      POSTGRES_DB: paidsearchnav_dev
      POSTGRES_USER: dev_user
      POSTGRES_PASSWORD: dev_password
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:6-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

volumes:
  postgres_data:
  redis_data:
```

### 3. Development Verification

```bash
# Start development environment
docker-compose -f docker-compose.dev.yml up -d

# Wait for services to be ready
sleep 30

# Test API health
curl http://localhost:8000/health

# Test BigQuery health
curl http://localhost:8000/api/v1/bigquery/health

# Test authentication (replace with actual token)
curl -H "Authorization: Bearer test_token" \
  http://localhost:8000/api/v1/bigquery/cost-monitoring/real-time

# Run tests
pytest tests/unit/platforms/bigquery/
pytest tests/api/test_bigquery_*.py
```

## Production Deployment

### 1. Production Docker Image

```dockerfile
# Dockerfile.prod
FROM python:3.10-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

FROM python:3.10-slim

# Create non-root user
RUN useradd --create-home --shell /bin/bash appuser

WORKDIR /app

# Copy Python dependencies from builder
COPY --from=builder /root/.local /home/appuser/.local

# Copy application code
COPY --chown=appuser:appuser . .

# Install application
RUN pip install --user --no-deps .

# Switch to non-root user
USER appuser

# Update PATH to include user installed packages
ENV PATH=/home/appuser/.local/bin:$PATH

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Expose port
EXPOSE 8000

# Production command
CMD ["gunicorn", "paidsearchnav.api.main:app", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000"]
```

### 2. Kubernetes Deployment

```yaml
# k8s/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: paidsearchnav
---
# k8s/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: bigquery-config
  namespace: paidsearchnav
data:
  ENV: "production"
  DEBUG: "false"
  LOG_LEVEL: "INFO"
  LOG_FORMAT: "json"
  BIGQUERY_LOCATION: "US"
  BIGQUERY_DATASET: "paidsearchnav_analytics"
  PSN_BIGQUERY_COST_MONITORING_ENABLED: "true"
  PSN_STANDARD_DAILY_LIMIT: "10.00"
  PSN_PREMIUM_DAILY_LIMIT: "50.00"
  PSN_ENTERPRISE_DAILY_LIMIT: "200.00"
  PSN_RATE_LIMIT_REAL_TIME: "10/minute"
  PSN_RATE_LIMIT_ANALYTICS: "5/minute"
---
# k8s/secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: bigquery-secrets
  namespace: paidsearchnav
type: Opaque
data:
  DATABASE_URL: <base64-encoded-database-url>
  REDIS_URL: <base64-encoded-redis-url>
  JWT_SECRET_KEY: <base64-encoded-jwt-secret>
  GOOGLE_APPLICATION_CREDENTIALS_JSON: <base64-encoded-service-account-json>
---
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: paidsearchnav-api
  namespace: paidsearchnav
spec:
  replicas: 3
  selector:
    matchLabels:
      app: paidsearchnav-api
  template:
    metadata:
      labels:
        app: paidsearchnav-api
    spec:
      containers:
      - name: api
        image: your-registry/paidsearchnav:latest
        ports:
        - containerPort: 8000
        envFrom:
        - configMapRef:
            name: bigquery-config
        - secretRef:
            name: bigquery-secrets
        env:
        - name: GOOGLE_APPLICATION_CREDENTIALS
          value: "/tmp/service-account.json"
        volumeMounts:
        - name: service-account
          mountPath: /tmp
          readOnly: true
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 10
        resources:
          requests:
            memory: "256Mi"
            cpu: "250m"
          limits:
            memory: "512Mi"
            cpu: "500m"
      volumes:
      - name: service-account
        secret:
          secretName: bigquery-secrets
          items:
          - key: GOOGLE_APPLICATION_CREDENTIALS_JSON
            path: service-account.json
---
# k8s/service.yaml
apiVersion: v1
kind: Service
metadata:
  name: paidsearchnav-api-service
  namespace: paidsearchnav
spec:
  selector:
    app: paidsearchnav-api
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: ClusterIP
---
# k8s/ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: paidsearchnav-ingress
  namespace: paidsearchnav
  annotations:
    kubernetes.io/ingress.class: "nginx"
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
    nginx.ingress.kubernetes.io/rate-limit: "100"
spec:
  tls:
  - hosts:
    - api.paidsearchnav.com
    secretName: paidsearchnav-tls
  rules:
  - host: api.paidsearchnav.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: paidsearchnav-api-service
            port:
              number: 80
```

### 3. Deployment Scripts

```bash
#!/bin/bash
# deploy.sh - Production deployment script

set -e

ENVIRONMENT=${1:-production}
IMAGE_TAG=${2:-latest}
NAMESPACE=paidsearchnav

echo "🚀 Deploying PaidSearchNav BigQuery to $ENVIRONMENT"

# 1. Build and push Docker image
echo "Building Docker image..."
docker build -f Dockerfile.prod -t paidsearchnav:$IMAGE_TAG .
docker tag paidsearchnav:$IMAGE_TAG your-registry/paidsearchnav:$IMAGE_TAG
docker push your-registry/paidsearchnav:$IMAGE_TAG

# 2. Create namespace if it doesn't exist
kubectl create namespace $NAMESPACE --dry-run=client -o yaml | kubectl apply -f -

# 3. Apply secrets (ensure they exist)
if [ ! -f "k8s/secrets.$ENVIRONMENT.yaml" ]; then
    echo "❌ Secrets file not found: k8s/secrets.$ENVIRONMENT.yaml"
    exit 1
fi

# 4. Apply configurations
echo "Applying Kubernetes configurations..."
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secrets.$ENVIRONMENT.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/ingress.yaml

# 5. Update deployment with new image
kubectl set image deployment/paidsearchnav-api \
  api=your-registry/paidsearchnav:$IMAGE_TAG \
  -n $NAMESPACE

# 6. Wait for rollout to complete
echo "Waiting for deployment to complete..."
kubectl rollout status deployment/paidsearchnav-api -n $NAMESPACE --timeout=300s

# 7. Verify deployment
echo "Verifying deployment..."
kubectl get pods -n $NAMESPACE
kubectl get services -n $NAMESPACE
kubectl get ingress -n $NAMESPACE

echo "✅ Deployment complete!"
```

### 4. Secrets Management

```bash
#!/bin/bash
# create-secrets.sh - Create Kubernetes secrets

NAMESPACE=paidsearchnav
ENVIRONMENT=${1:-production}

# Encode secrets
DATABASE_URL_B64=$(echo -n "$DATABASE_URL" | base64 -w 0)
REDIS_URL_B64=$(echo -n "$REDIS_URL" | base64 -w 0)
JWT_SECRET_B64=$(echo -n "$JWT_SECRET_KEY" | base64 -w 0)
SA_JSON_B64=$(base64 -w 0 < service-account-key.json)

# Create secrets YAML
cat > k8s/secrets.$ENVIRONMENT.yaml << EOF
apiVersion: v1
kind: Secret
metadata:
  name: bigquery-secrets
  namespace: $NAMESPACE
type: Opaque
data:
  DATABASE_URL: $DATABASE_URL_B64
  REDIS_URL: $REDIS_URL_B64
  JWT_SECRET_KEY: $JWT_SECRET_B64
  GOOGLE_APPLICATION_CREDENTIALS_JSON: $SA_JSON_B64
EOF

echo "✅ Secrets file created: k8s/secrets.$ENVIRONMENT.yaml"
echo "⚠️  Remember to store this file securely and not commit to git!"
```

## Verification and Testing

### 1. Deployment Verification

```bash
#!/bin/bash
# verify-deployment.sh - Verify BigQuery deployment

NAMESPACE=paidsearchnav
API_URL="https://api.paidsearchnav.com"

echo "🔍 Verifying BigQuery deployment..."

# 1. Check pod status
echo "Checking pod status..."
kubectl get pods -n $NAMESPACE -l app=paidsearchnav-api

# 2. Check service endpoints
echo "Checking service endpoints..."
kubectl get endpoints -n $NAMESPACE

# 3. Test API health
echo "Testing API health..."
curl -f $API_URL/health || {
    echo "❌ API health check failed"
    exit 1
}

# 4. Test BigQuery health
echo "Testing BigQuery health..."
curl -f $API_URL/api/v1/bigquery/health || {
    echo "❌ BigQuery health check failed"
    exit 1
}

# 5. Test authentication endpoint
echo "Testing authentication..."
# This would require a valid test token
# curl -H "Authorization: Bearer $TEST_TOKEN" $API_URL/api/v1/user/profile

# 6. Check logs for errors
echo "Checking recent logs..."
kubectl logs -n $NAMESPACE -l app=paidsearchnav-api --tail=50 | grep -i error

echo "✅ Deployment verification complete!"
```

### 2. Integration Tests

```python
#!/usr/bin/env python3
# integration_test.py - Integration tests for deployed BigQuery API

import requests
import os
import time

API_BASE = os.getenv("API_BASE", "https://api.paidsearchnav.com")
TEST_TOKEN = os.getenv("TEST_TOKEN")

def test_api_health():
    """Test API health endpoint."""
    response = requests.get(f"{API_BASE}/health")
    assert response.status_code == 200
    print("✅ API health check passed")

def test_bigquery_health():
    """Test BigQuery health endpoint."""
    response = requests.get(f"{API_BASE}/api/v1/bigquery/health")
    assert response.status_code == 200
    print("✅ BigQuery health check passed")

def test_authentication():
    """Test authentication."""
    if not TEST_TOKEN:
        print("⚠️  No test token provided, skipping auth test")
        return
    
    headers = {"Authorization": f"Bearer {TEST_TOKEN}"}
    response = requests.get(f"{API_BASE}/api/v1/user/profile", headers=headers)
    assert response.status_code in [200, 403]  # 403 is ok for invalid test token
    print("✅ Authentication test passed")

def test_bigquery_endpoints():
    """Test BigQuery endpoints with authentication."""
    if not TEST_TOKEN:
        print("⚠️  No test token provided, skipping BigQuery endpoint tests")
        return
    
    headers = {"Authorization": f"Bearer {TEST_TOKEN}"}
    
    # Test real-time costs (should require premium tier)
    response = requests.get(
        f"{API_BASE}/api/v1/bigquery/cost-monitoring/real-time",
        headers=headers
    )
    assert response.status_code in [200, 402, 403]  # Various valid responses
    print("✅ BigQuery real-time endpoint test passed")

if __name__ == "__main__":
    print("🧪 Running integration tests...")
    
    test_api_health()
    test_bigquery_health()
    test_authentication()
    test_bigquery_endpoints()
    
    print("✅ All integration tests passed!")
```

### 3. Load Testing

```bash
#!/bin/bash
# load_test.sh - Simple load test for BigQuery endpoints

API_BASE="https://api.paidsearchnav.com"
CONCURRENT_USERS=10
DURATION=60  # seconds

echo "🔥 Running load test..."
echo "API: $API_BASE"
echo "Concurrent users: $CONCURRENT_USERS"
echo "Duration: $DURATION seconds"

# Install required tools if not available
which ab > /dev/null || {
    echo "Installing apache2-utils for ab (Apache Bench)..."
    sudo apt-get update && sudo apt-get install -y apache2-utils
}

# Test health endpoint
echo "Testing health endpoint..."
ab -n 1000 -c $CONCURRENT_USERS -t $DURATION "$API_BASE/health"

# Test BigQuery health endpoint
echo "Testing BigQuery health endpoint..."
ab -n 500 -c 5 -t $DURATION "$API_BASE/api/v1/bigquery/health"

echo "✅ Load test complete!"
```

## Monitoring Setup

### 1. Prometheus Configuration

```yaml
# prometheus/bigquery-monitoring.yml
groups:
- name: bigquery.rules
  rules:
  - alert: BigQueryHighCosts
    expr: bigquery_daily_cost_usd > 100
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "High BigQuery costs detected"
      description: "Daily BigQuery costs exceeded $100"

  - alert: BigQueryRateLimitExceeded
    expr: rate(bigquery_rate_limit_exceeded_total[5m]) > 0.1
    for: 2m
    labels:
      severity: warning
    annotations:
      summary: "BigQuery rate limits being exceeded"

  - alert: BigQueryCircuitBreakerActive
    expr: bigquery_circuit_breaker_active == 1
    for: 0m
    labels:
      severity: critical
    annotations:
      summary: "BigQuery circuit breaker activated"
      description: "Emergency circuit breaker is active, BigQuery operations suspended"
```

### 2. Grafana Dashboard

```json
{
  "dashboard": {
    "title": "BigQuery Cost Monitoring",
    "panels": [
      {
        "title": "Real-time Daily Costs",
        "type": "graph",
        "targets": [
          {
            "expr": "bigquery_daily_cost_usd",
            "legendFormat": "{{customer_id}}"
          }
        ]
      },
      {
        "title": "Budget Utilization",
        "type": "graph",
        "targets": [
          {
            "expr": "bigquery_budget_utilization_percentage",
            "legendFormat": "{{customer_id}}"
          }
        ]
      },
      {
        "title": "API Request Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(bigquery_api_requests_total[5m])",
            "legendFormat": "{{endpoint}}"
          }
        ]
      }
    ]
  }
}
```

## Maintenance Procedures

### 1. Regular Maintenance Tasks

```bash
#!/bin/bash
# maintenance.sh - Regular maintenance tasks

echo "🔧 Running BigQuery maintenance tasks..."

# 1. Clean up old cost monitoring data
echo "Cleaning up old monitoring data..."
psql $DATABASE_URL -c "
DELETE FROM cost_monitoring_cache 
WHERE created_at < NOW() - INTERVAL '7 days';
"

# 2. Rotate service account keys (quarterly)
echo "Checking service account key age..."
KEY_AGE=$(gcloud iam service-accounts keys list \
  --iam-account=$SA_EMAIL \
  --format="value(validAfterTime)" | head -1)

# 3. Update BigQuery dataset permissions
echo "Verifying BigQuery permissions..."
bq show --dataset $GOOGLE_CLOUD_PROJECT:paidsearchnav_analytics

# 4. Clean up old BigQuery job history (optional)
echo "Cleaning up old job history..."
# Note: BigQuery automatically expires job history after 180 days

# 5. Check disk space and logs
echo "Checking system resources..."
df -h
kubectl top nodes
kubectl top pods -n paidsearchnav

echo "✅ Maintenance tasks complete!"
```

### 2. Security Updates

```bash
#!/bin/bash
# security-update.sh - Security update procedures

echo "🔒 Performing security updates..."

# 1. Update base Docker images
docker pull python:3.10-slim
docker build -f Dockerfile.prod -t paidsearchnav:security-update .

# 2. Rotate JWT secret (coordinate with team)
# NEW_JWT_SECRET=$(openssl rand -base64 32)
# kubectl patch secret bigquery-secrets -n paidsearchnav -p='{"data":{"JWT_SECRET_KEY":"'$(echo -n $NEW_JWT_SECRET | base64 -w 0)'"}}'

# 3. Update dependencies
pip-audit --fix

# 4. Scan for vulnerabilities
trivy image paidsearchnav:security-update

echo "✅ Security updates complete!"
```

### 3. Backup Procedures

```bash
#!/bin/bash
# backup.sh - Backup critical data

echo "💾 Running backup procedures..."

# 1. Backup BigQuery datasets
echo "Backing up BigQuery datasets..."
bq extract \
  --destination_format=PARQUET \
  $GOOGLE_CLOUD_PROJECT:paidsearchnav_analytics.cost_monitoring \
  gs://paidsearchnav-backups/bigquery/$(date +%Y%m%d)/cost_monitoring_*.parquet

# 2. Backup PostgreSQL metadata
echo "Backing up PostgreSQL..."
pg_dump $DATABASE_URL | gzip > backups/postgres_$(date +%Y%m%d_%H%M%S).sql.gz

# 3. Backup configuration
echo "Backing up configuration..."
kubectl get configmap bigquery-config -n paidsearchnav -o yaml > backups/config_$(date +%Y%m%d).yaml

echo "✅ Backup procedures complete!"
```

---

*For configuration details, see the [Configuration Reference](configuration.md)*
*For troubleshooting issues, see the [Troubleshooting Guide](troubleshooting.md)*