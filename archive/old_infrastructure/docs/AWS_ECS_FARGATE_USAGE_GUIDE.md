# PaidSearchNav AWS ECS Fargate Container Usage Guide

This guide provides comprehensive examples of using PaidSearchNav's AWS ECS Fargate containers to execute the various features outlined in the project README.md. The examples demonstrate how to leverage containerized deployments for scalable Google Ads keyword auditing.

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Container Specifications](#container-specifications) 
- [Feature Examples](#feature-examples)
  - [1. REST API Operations](#1-rest-api-operations)
  - [2. CSV File Analysis](#2-csv-file-analysis)
  - [3. Automated Scheduled Audits](#3-automated-scheduled-audits)
  - [4. Geographic Performance Analysis](#4-geographic-performance-analysis)
  - [5. Bulk Account Discovery and Management](#5-bulk-account-discovery-and-management)
  - [6. Performance Max Campaign Analysis](#6-performance-max-campaign-analysis)
  - [7. Emergency Audit Response](#7-emergency-audit-response)
  - [8. Real-time Audit Progress Monitoring](#8-real-time-audit-progress-monitoring)
  - [9. Batch Processing and Data Export](#9-batch-processing-and-data-export)
  - [10. Container Security and Secrets Management](#10-container-security-and-secrets-management)
- [Monitoring and Observability](#monitoring-and-observability)
- [Cost Optimization](#cost-optimization)
- [S3 Integration Deployment](#s3-integration-deployment)
- [Deployment Patterns](#deployment-patterns)
- [Conclusion](#conclusion)

## Architecture Overview

PaidSearchNav is deployed on AWS ECS Fargate with the following architecture:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Application   │    │   Load Balancer │    │     Client      │
│   Load Balancer │◄───┤     (ALB)       │◄───┤   Applications  │
│                 │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    ECS Fargate Cluster                         │
├─────────────────┬───────────────────┬───────────────────────────┤
│   API Service   │ Scheduler Service │    One-time Tasks        │
│   (2-10 tasks)  │    (1 task)       │   (Ad-hoc analysis)      │
├─────────────────┼───────────────────┼───────────────────────────┤
│ - REST API      │ - Background Jobs │ - Bulk CSV Analysis       │
│ - OAuth2        │ - Scheduled       │ - Account Discovery       │
│ - CSV Analysis  │   Audits          │ - Emergency Audits        │
│ - Real-time     │ - Queue           │ - Data Migration          │
│   Updates       │   Management      │                           │
└─────────────────┴───────────────────┴───────────────────────────┘
         │                    │                         │
         ▼                    ▼                         ▼
┌─────────────────┐  ┌──────────────┐   ┌───────────────────┐
│   PostgreSQL    │  │    Redis     │   │  AWS Secrets      │
│   RDS Instance  │  │ ElastiCache  │   │    Manager        │
└─────────────────┘  └──────────────┘   └───────────────────┘
```

## Container Specifications

### Base Container Image
- **Base Image**: `python:3.10-slim`
- **Multi-stage build**: Optimized for production
- **Security**: Non-root user (appuser)
- **Health Checks**: Built-in `/api/v1/health` endpoint
- **Resource Efficiency**: Minimal runtime dependencies

### Service Configurations

#### API Service
- **CPU**: 512-1024 units
- **Memory**: 1024-2048 MB
- **Ports**: 8000 (HTTP)
- **Auto-scaling**: 2-10 instances
- **Health Check**: HTTP GET `/api/v1/health`

#### Scheduler Service  
- **CPU**: 256-512 units
- **Memory**: 512-1024 MB
- **Instances**: 1 (singleton)
- **Purpose**: Background job processing

## Feature Examples

### 1. REST API Operations

#### Starting the API Service
```bash
# Deploy via Terraform (recommended)
cd infrastructure/terraform
terraform apply

# Or via ECS Console
aws ecs run-task \
  --cluster paidsearchnav-prod \
  --task-definition paidsearchnav-prod-api:latest \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-12345],securityGroups=[sg-67890],assignPublicIp=ENABLED}"
```

#### Example API Usage with Container
```python
import httpx
import asyncio

class PaidSearchNavClient:
    def __init__(self, base_url="https://api.yourdomain.com"):
        self.base_url = base_url.rstrip("/")
    
    async def test_container_health(self):
        """Test that the Fargate container is healthy"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.base_url}/api/v1/health/full")
            health_data = response.json()
            
            print("Container Health Status:")
            for component, status in health_data.get("components", {}).items():
                print(f"  {component}: {status['status']}")
            
            return health_data
    
    async def authenticate_and_get_customers(self, auth_token):
        """Get customer list using OAuth2 token"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/v1/customers",
                headers=headers
            )
            return response.json()

# Usage
async def main():
    client = PaidSearchNavClient("https://your-fargate-api.com")
    health = await client.test_container_health()
    print(f"API Status: {health['status']}")

asyncio.run(main())
```

### 2. CSV File Analysis

The containerized API provides powerful CSV analysis without requiring Google Ads API authentication:

```bash
# Upload search terms CSV to Fargate container
curl -X POST https://your-fargate-api.com/api/v1/analyze-csv \
  -F "file=@quarterly_search_terms.csv" \
  -F "data_type=search_terms" | jq

# Example response:
{
  "filename": "quarterly_search_terms.csv",
  "total_rows": 15847,
  "analysis_summary": {
    "total_cost": 125847.32,
    "total_clicks": 28945,
    "total_conversions": 1456.0,
    "avg_cpc": 4.35,
    "conversion_rate": 5.03,
    "negative_keyword_candidates": 234,
    "local_intent_terms": 89,
    "sample_local_terms": [
      "coffee shop near me",
      "restaurant open now",
      "pizza delivery nearby"
    ]
  },
  "recommendations": [
    "Consider adding 'jobs' as negative keyword (0% conversion rate)",
    "Optimize for local intent terms (89 opportunities found)"
  ]
}
```

### 3. Automated Scheduled Audits

#### Task Definition for Scheduled Audit
```json
{
  "family": "paidsearchnav-scheduled-audit",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "1024",
  "memory": "2048",
  "executionRoleArn": "arn:aws:iam::account:role/ecsTaskExecutionRole",
  "taskRoleArn": "arn:aws:iam::account:role/ecsTaskRole",
  "containerDefinitions": [
    {
      "name": "audit-runner",
      "image": "your-ecr-repo/paidsearchnav:latest",
      "command": [
        "python", "-m", "paidsearchnav.cli.main",
        "scheduler", "run",
        "--customer-id", "${CUSTOMER_ID}",
        "--analyzers", "all",
        "--start-date", "${START_DATE}",
        "--end-date", "${END_DATE}"
      ],
      "environment": [
        {"name": "PSN_ENV", "value": "production"},
        {"name": "PSN_HEADLESS", "value": "true"}
      ],
      "secrets": [
        {
          "name": "PSN_GOOGLE_ADS_DEVELOPER_TOKEN",
          "valueFrom": "arn:aws:secretsmanager:region:account:secret:psn-secrets:google_ads_developer_token::"
        },
        {
          "name": "PSN_DATABASE_URL",
          "valueFrom": "arn:aws:secretsmanager:region:account:secret:psn-secrets:database_url::"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/paidsearchnav/audit-jobs",
          "awslogs-region": "us-west-2",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ]
}
```

#### CloudWatch Events Rule for Monthly Audits
```json
{
  "Name": "MonthlyAuditSchedule",
  "ScheduleExpression": "cron(0 2 1 * ? *)",
  "State": "ENABLED",
  "Targets": [
    {
      "Id": "1",
      "Arn": "arn:aws:ecs:us-west-2:account:cluster/paidsearchnav-prod",
      "RoleArn": "arn:aws:iam::account:role/CloudWatchEventsRole",
      "EcsParameters": {
        "TaskDefinitionArn": "arn:aws:ecs:us-west-2:account:task-definition/paidsearchnav-scheduled-audit",
        "LaunchType": "FARGATE",
        "NetworkConfiguration": {
          "AwsVpcConfiguration": {
            "Subnets": ["subnet-12345", "subnet-67890"],
            "SecurityGroups": ["sg-audit-tasks"],
            "AssignPublicIp": "DISABLED"
          }
        }
      },
      "Input": "{\"containerOverrides\":[{\"name\":\"audit-runner\",\"environment\":[{\"name\":\"CUSTOMER_ID\",\"value\":\"1234567890\"},{\"name\":\"START_DATE\",\"value\":\"last_month\"},{\"name\":\"END_DATE\",\"value\":\"yesterday\"}]}]}"
    }
  ]
}
```

### 4. Geographic Performance Analysis

#### One-time Geographic Analysis Task
```bash
# Run geographic analysis for multiple locations
aws ecs run-task \
  --cluster paidsearchnav-prod \
  --task-definition paidsearchnav-geo-analysis:latest \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-12345],securityGroups=[sg-67890],assignPublicIp=DISABLED}" \
  --overrides '{
    "containerOverrides": [{
      "name": "geo-analyzer",
      "command": [
        "python", "-m", "paidsearchnav.cli.main",
        "geo", "analyze",
        "--customer-id", "1234567890",
        "--locations", "Seattle,Portland,San Francisco,Los Angeles",
        "--location-types", "CITY,POSTAL_CODE",
        "--min-impressions", "500",
        "--format", "json",
        "--output-file", "/tmp/geo_analysis.json"
      ]
    }]
  }'

# Monitor task completion
aws ecs describe-tasks --cluster paidsearchnav-prod --tasks task-id
```

#### Container Environment for Geographic Analysis
```dockerfile
# Specialized container for geo analysis
FROM your-ecr-repo/paidsearchnav:latest

# Add geo-specific dependencies
RUN pip install folium geopy

# Set geo analysis defaults
ENV PSN_GEO_MIN_IMPRESSIONS=100
ENV PSN_GEO_PERFORMANCE_THRESHOLD=0.15
ENV PSN_GEO_INCLUDE_RADIUS_TARGETS=true

# Default command for geo analysis
CMD ["python", "-m", "paidsearchnav.cli.main", "geo", "analyze", "--help"]
```

### 5. Bulk Account Discovery and Management

#### Multi-Account Discovery Task
```python
# Python script for container-based account discovery
import asyncio
import json
from paidsearchnav.core.auth import GoogleAdsAuth
from paidsearchnav.platforms.google import GoogleAdsClient

async def discover_all_accounts():
    """Run account discovery across MCC hierarchy"""
    
    # Initialize in headless mode (required for containers)
    auth = GoogleAdsAuth(headless=True)
    client = GoogleAdsClient(auth_provider=auth)
    
    # Discover account hierarchy
    root_mccs = ["1234567890", "9876543210"]  # Your MCC IDs
    all_accounts = []
    
    for mcc_id in root_mccs:
        accounts = await client.get_account_hierarchy(mcc_id)
        all_accounts.extend(accounts)
        
        print(f"MCC {mcc_id}: Found {len(accounts)} accounts")
    
    # Save results
    with open("/tmp/discovered_accounts.json", "w") as f:
        json.dump(all_accounts, f, indent=2)
    
    return all_accounts

# Task definition for account discovery
discovery_task_def = {
  "family": "paidsearchnav-account-discovery",
  "cpu": "512",
  "memory": "1024",
  "containerDefinitions": [{
    "name": "account-discovery",
    "image": "your-ecr-repo/paidsearchnav:latest",
    "command": ["python", "-c", "import asyncio; from discover_accounts import discover_all_accounts; asyncio.run(discover_all_accounts())"],
    "environment": [
      {"name": "PSN_HEADLESS", "value": "true"},
      {"name": "PSN_LOG_LEVEL", "value": "INFO"}
    ]
  }]
}
```

### 6. Performance Max Campaign Analysis

#### Specialized PMax Analysis Container
```bash
# Run Performance Max analysis with enhanced insights
aws ecs run-task \
  --cluster paidsearchnav-prod \
  --task-definition paidsearchnav-pmax-analyzer \
  --overrides '{
    "containerOverrides": [{
      "name": "pmax-analyzer",
      "environment": [
        {"name": "PSN_PMAX_INCLUDE_SHOPPING", "value": "true"},
        {"name": "PSN_PMAX_CATEGORY_DEPTH", "value": "5"},
        {"name": "PSN_PMAX_MIN_ASSET_IMPRESSIONS", "value": "2000"},
        {"name": "CUSTOMER_ID", "value": "1234567890"},
        {"name": "ANALYSIS_PERIOD", "value": "last_quarter"}
      ],
      "command": [
        "python", "-m", "paidsearchnav.cli.main",
        "scheduler", "run",
        "--customer-id", "${CUSTOMER_ID}",
        "--analyzers", "pmax",
        "--date-range", "${ANALYSIS_PERIOD}",
        "--priority", "high"
      ]
    }]
  }'
```

### 7. Emergency Audit Response

For urgent performance issues, quickly spin up high-priority audit containers:

```bash
# Emergency audit with immediate results
aws ecs run-task \
  --cluster paidsearchnav-prod \
  --task-definition paidsearchnav-emergency-audit \
  --launch-type FARGATE \
  --overrides '{
    "containerOverrides": [{
      "name": "emergency-audit",
      "cpu": 1024,
      "memory": 2048,
      "environment": [
        {"name": "CUSTOMER_ID", "value": "1234567890"},
        {"name": "AUDIT_PRIORITY", "value": "critical"},
        {"name": "FOCUS_AREAS", "value": "negative_conflicts,search_terms"}
      ],
      "command": [
        "python", "-m", "paidsearchnav.cli.main",
        "scheduler", "run",
        "--customer-id", "${CUSTOMER_ID}",
        "--analyzers", "${FOCUS_AREAS}",
        "--date-range", "last_7_days",
        "--priority", "high"
      ]
    }]
  }' \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-12345],securityGroups=[sg-67890],assignPublicIp=DISABLED}"
```

### 8. Real-time Audit Progress Monitoring

#### WebSocket Connection to Fargate Container
```javascript
// Connect to running audit for real-time progress
const WebSocket = require('ws');

class AuditMonitor {
  constructor(apiUrl, authToken) {
    this.apiUrl = apiUrl;
    this.authToken = authToken;
  }
  
  async monitorAudit(auditId) {
    const wsUrl = `wss://${this.apiUrl}/ws/v1/audits/${auditId}?token=${this.authToken}`;
    const ws = new WebSocket(wsUrl);
    
    ws.on('open', () => {
      console.log(`Connected to audit ${auditId} progress stream`);
    });
    
    ws.on('message', (data) => {
      const event = JSON.parse(data.toString());
      
      switch(event.type) {
        case 'audit_progress':
          console.log(`Progress: ${event.progress}% - ${event.stage}`);
          console.log(`ETA: ${event.estimated_completion}`);
          break;
          
        case 'analyzer_completed':
          console.log(`✅ ${event.analyzer} completed`);
          console.log(`Found ${event.findings_count} findings`);
          break;
          
        case 'audit_completed':
          console.log(`🎉 Audit completed successfully`);
          console.log(`Total findings: ${event.total_findings}`);
          console.log(`Report URL: ${event.report_url}`);
          break;
          
        case 'error':
          console.error(`❌ Error: ${event.message}`);
          break;
      }
    });
    
    // Keep connection alive
    setInterval(() => {
      ws.send(JSON.stringify({type: 'ping'}));
    }, 30000);
  }
}

// Usage
const monitor = new AuditMonitor('your-fargate-api.com', 'jwt_token');
monitor.monitorAudit('audit_12345');
```

### 9. Batch Processing and Data Export

#### BigQuery Export Container
```yaml
# docker-compose.override.yml for BigQuery export
version: '3.8'
services:
  bigquery-exporter:
    image: your-ecr-repo/paidsearchnav:latest
    environment:
      - PSN_ENV=production
      - PSN_EXPORT_DESTINATION=bigquery
      - GOOGLE_APPLICATION_CREDENTIALS=/app/credentials/bigquery-key.json
    volumes:
      - ./credentials:/app/credentials:ro
    command: >
      python -m paidsearchnav.api.exports.bigquery_exporter
      --customer-ids 1234567890,9876543210
      --data-types audit_results,recommendations,search_terms
      --dataset-id paidsearchnav_data
      --batch-size 10000
```

#### Automated Report Generation
```bash
# Generate and email monthly reports
aws ecs run-task \
  --cluster paidsearchnav-prod \
  --task-definition paidsearchnav-report-generator \
  --overrides '{
    "containerOverrides": [{
      "name": "report-generator",
      "command": [
        "python", "-m", "paidsearchnav.cli.main",
        "reports", "generate-bulk",
        "--customer-ids", "1234567890,2345678901,3456789012",
        "--date-range", "last_month",
        "--format", "pdf",
        "--include-summary",
        "--email-recipients", "team@company.com,client@retailer.com"
      ]
    }]
  }'
```

### 10. Container Security and Secrets Management

#### Secrets Configuration
```json
{
  "google_ads_developer_token": "your_developer_token",
  "google_ads_client_id": "your_client_id.apps.googleusercontent.com",
  "google_ads_client_secret": "GOCSPX-your_client_secret",
  "database_url": "postgresql://user:pass@rds-endpoint:5432/paidsearchnav",
  "database_sync_url": "postgresql://user:pass@rds-endpoint:5432/paidsearchnav",
  "jwt_secret_key": "your-jwt-secret-key-here",
  "secret_key": "your-app-secret-key-here"
}
```

#### IAM Task Role Permissions
The PaidSearchNav ECS tasks now use the `PaidSearchNavS3Role` which includes S3 access:

**Role ARN**: `arn:aws:iam::039612890670:role/PaidSearchNavS3Role`

This role includes permissions for:
- **S3 Operations**: Upload, download, list, and delete customer audit data
- **Secrets Manager**: Access to encrypted application secrets
- **CloudWatch Logs**: Write application logs

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowBucketListAndLocation",
      "Effect": "Allow",
      "Action": [
        "s3:ListBucket",
        "s3:GetBucketLocation",
        "s3:GetBucketVersioning"
      ],
      "Resource": [
        "arn:aws:s3:::paidsearchnav-customer-data",
        "arn:aws:s3:::paidsearchnav-customer-data-dev"
      ]
    },
    {
      "Sid": "AllowObjectOperations",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:GetObjectVersion",
        "s3:GetObjectMetadata",
        "s3:PutObject",
        "s3:PutObjectAcl",
        "s3:DeleteObject",
        "s3:DeleteObjectVersion"
      ],
      "Resource": [
        "arn:aws:s3:::paidsearchnav-customer-data/PaidSearchNav/*",
        "arn:aws:s3:::paidsearchnav-customer-data-dev/PaidSearchNav/*"
      ]
    },
    {
      "Sid": "AllowMultipartUploads",
      "Effect": "Allow",
      "Action": [
        "s3:ListMultipartUploadParts",
        "s3:AbortMultipartUpload",
        "s3:ListBucketMultipartUploads"
      ],
      "Resource": [
        "arn:aws:s3:::paidsearchnav-customer-data",
        "arn:aws:s3:::paidsearchnav-customer-data/PaidSearchNav/*",
        "arn:aws:s3:::paidsearchnav-customer-data-dev",
        "arn:aws:s3:::paidsearchnav-customer-data-dev/PaidSearchNav/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Resource": [
        "arn:aws:secretsmanager:*:*:secret:paidsearchnav/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": [
        "arn:aws:logs:*:*:log-group:/ecs/paidsearchnav/*"
      ]
    }
  ]
}
```

## Monitoring and Observability

### CloudWatch Metrics
```python
# Custom metrics from container
import boto3
cloudwatch = boto3.client('cloudwatch')

# Track audit completions
cloudwatch.put_metric_data(
    Namespace='PaidSearchNav/Audits',
    MetricData=[
        {
            'MetricName': 'AuditsCompleted',
            'Value': 1,
            'Unit': 'Count',
            'Dimensions': [
                {'Name': 'CustomerID', 'Value': '1234567890'},
                {'Name': 'Environment', 'Value': 'production'}
            ]
        }
    ]
)
```

### Container Health Monitoring
```bash
# Health check endpoint returns detailed status
curl https://your-fargate-api.com/api/v1/health/full | jq

{
  "status": "healthy",
  "version": "0.1.0",
  "timestamp": "2025-08-09T15:30:00Z",
  "components": {
    "database": {"status": "healthy", "response_time_ms": 45},
    "google_ads": {"status": "healthy", "quota_remaining": "85%"},
    "redis": {"status": "healthy", "memory_usage": "23%"},
    "scheduler": {"status": "healthy", "active_jobs": 3},
    "alerts": {"status": "healthy", "channels_active": 3},
    "disk_space": {"status": "healthy", "usage": "34%"}
  }
}
```

## Cost Optimization

### Fargate Spot Usage
```terraform
# Use Fargate Spot for scheduler service (cost savings)
resource "aws_ecs_service" "scheduler" {
  # ... other configuration ...
  
  capacity_provider_strategy {
    capacity_provider = "FARGATE_SPOT"
    weight            = 100
    base              = 0
  }
}
```

### Resource Right-Sizing
```bash
# Monitor container resource utilization
aws cloudwatch get-metric-statistics \
  --namespace AWS/ECS \
  --metric-name CPUUtilization \
  --dimensions Name=ServiceName,Value=paidsearchnav-prod-api \
               Name=ClusterName,Value=paidsearchnav-prod \
  --start-time 2025-08-01T00:00:00Z \
  --end-time 2025-08-09T00:00:00Z \
  --period 3600 \
  --statistics Average
```

## S3 Integration Deployment

### Quick Deployment with S3 Support

To deploy ECS services with S3 integration support, use the provided deployment script:

```bash
# Deploy updated task definitions with S3 role
./docs/deploy-ecs-with-s3.sh roimedia-east1

# Example output:
# 🚀 Deploying ECS Task Definitions with S3 Integration
# 📋 Creating CloudWatch Log Groups...
# ✅ Log groups created
# 📦 Registering ECS Task Definitions...
# ✅ API Task Definition: arn:aws:ecs:us-east-1:039612890670:task-definition/paidsearchnav-prod-api:42
# ✅ Scheduler Task Definition: arn:aws:ecs:us-east-1:039612890670:task-definition/paidsearchnav-prod-scheduler:12
# 🔒 Validating S3 permissions...
# ✅ Production bucket (paidsearchnav-customer-data) accessible
# 🎉 Deployment completed successfully!
```

### S3 Environment Variables

The updated task definitions include these S3-specific environment variables:

```json
{
  "environment": [
    {"name": "PSN_S3_ENABLED", "value": "true"},
    {"name": "PSN_S3_BUCKET_NAME", "value": "paidsearchnav-customer-data"},
    {"name": "PSN_S3_REGION", "value": "us-east-1"},
    {"name": "PSN_S3_PREFIX", "value": "PaidSearchNav"}
  ]
}
```

### S3 Folder Structure Created by Tasks

When ECS tasks run, they will automatically create this folder structure in S3:

```
s3://paidsearchnav-customer-data/
└── PaidSearchNav/
    └── {customer-name}/
        └── {customer-number}/
            └── {YYYY-MM-DD}/
                ├── inputs/
                │   ├── search-terms.csv
                │   ├── keywords.csv
                │   └── campaigns.csv
                └── outputs/
                    ├── reports/
                    │   ├── audit-summary.pdf
                    │   ├── recommendations.json
                    │   └── performance-analysis.xlsx
                    └── actionable_files/
                        ├── negative-keywords.csv
                        ├── bid-adjustments.csv
                        └── pause-keywords.csv
```

### Testing S3 Integration

After deployment, test S3 integration with a curl command:

```bash
# Test file upload via API
curl -X POST https://your-fargate-api.com/api/v1/customers/1234567890/audits/upload \
  -H "Authorization: Bearer your_jwt_token" \
  -F "file=@sample-data.csv" \
  -F "data_type=search_terms" \
  -F "audit_date=2025-08-10"

# Expected response:
{
  "upload_result": {
    "key": "PaidSearchNav/CustomerName/1234567890/2025-08-10/inputs/sample-data.csv",
    "bucket": "paidsearchnav-customer-data",
    "size": 2048576,
    "etag": "d41d8cd98f00b204e9800998ecf8427e"
  },
  "status": "uploaded",
  "message": "File successfully uploaded and ready for analysis"
}
```

## Deployment Patterns

### Blue/Green Deployment
```bash
# Deploy new version with zero downtime
aws ecs update-service \
  --cluster paidsearchnav-prod \
  --service paidsearchnav-prod-api \
  --task-definition paidsearchnav-prod-api:42 \
  --deployment-configuration "maximumPercent=200,minimumHealthyPercent=100"
```

### Rolling Updates
```bash
# Gradual rollout of new features
aws ecs update-service \
  --cluster paidsearchnav-prod \
  --service paidsearchnav-prod-api \
  --task-definition paidsearchnav-prod-api:43 \
  --deployment-configuration "maximumPercent=150,minimumHealthyPercent=75"
```

## Conclusion

This guide demonstrates how PaidSearchNav's containerized architecture enables scalable, reliable execution of Google Ads auditing workflows on AWS ECS Fargate. Key benefits include:

- **Scalability**: Auto-scaling based on demand
- **Reliability**: Health checks and service recovery
- **Security**: Secrets management and IAM roles
- **Cost Efficiency**: Fargate Spot for non-critical workloads
- **Observability**: Comprehensive monitoring and logging

The examples show how to leverage containers for:
1. REST API services with OAuth2 authentication
2. Automated scheduled audits
3. Real-time progress monitoring
4. Emergency response capabilities
5. Bulk data processing and export
6. Geographic performance analysis
7. Performance Max campaign insights

For production deployment, use the provided Terraform configurations and customize the environment variables and secrets according to your specific requirements.