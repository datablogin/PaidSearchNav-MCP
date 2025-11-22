# AWS Architecture for PaidSearchNav

## Architecture Overview

This document outlines a cost-optimized, scalable AWS architecture for PaidSearchNav that leverages your team's experience with Docker and ECR.

## Recommended Architecture

### 1. **Core Components**

#### API Layer (ECS Fargate)
- **Service**: ECS Fargate for serverless container management
- **Why**: No EC2 instances to manage, automatic scaling, pay-per-use
- **Configuration**: 
  - 2-4 tasks for high availability
  - Auto-scaling based on CPU/memory utilization
  - Application Load Balancer (ALB) for traffic distribution

#### Database (RDS PostgreSQL)
- **Service**: RDS PostgreSQL with Multi-AZ
- **Instance**: db.t3.medium (can start with db.t3.small)
- **Why**: Managed service, automated backups, read replicas if needed
- **Cost Optimization**: 
  - Use Reserved Instances for 30-50% savings
  - Enable storage auto-scaling
  - Consider Aurora Serverless v2 for variable workloads

#### Caching Layer (ElastiCache Redis)
- **Service**: ElastiCache Redis (cluster mode disabled)
- **Instance**: cache.t3.micro or cache.t3.small
- **Why**: Rate limiting, session storage, query caching
- **Cost Optimization**: Use single node for dev/staging

#### Background Jobs (ECS Fargate)
- **Service**: Separate ECS service for scheduler
- **Configuration**: 1 task running continuously
- **Alternative**: Step Functions + Lambda for scheduled audits (more cost-effective)

### 2. **Supporting Services**

#### Container Registry
- **Service**: Amazon ECR
- **Configuration**: 
  - Lifecycle policies to retain only last 10 images
  - Image scanning on push

#### Secrets Management
- **Service**: AWS Secrets Manager
- **Stores**: 
  - Google Ads API credentials
  - Database passwords
  - JWT secrets
  - API keys

#### Monitoring & Logging
- **CloudWatch**: Application logs, metrics, alarms
- **X-Ray**: Distributed tracing (optional)
- **Cost**: ~$50-100/month for moderate usage

### 3. **Network Architecture**

```
┌─────────────────────────────────────────────────────────────────┐
│                           Internet                               │
└─────────────────────┬───────────────────────────────────────────┘
                      │
                ┌─────▼─────┐
                │    WAF    │ (Optional: $5/month + requests)
                └─────┬─────┘
                      │
                ┌─────▼─────┐
                │    ALB    │ (Application Load Balancer)
                └─────┬─────┘
                      │
        ┌─────────────┴─────────────┐
        │         Public Subnet      │
        │  ┌────────────────────┐   │
        │  │   ECS Fargate      │   │
        │  │  (API Service)     │   │
        │  └────────┬───────────┘   │
        └───────────┼───────────────┘
                    │
        ┌───────────▼───────────────┐
        │      Private Subnet       │
        │  ┌──────────┐ ┌────────┐ │
        │  │   RDS    │ │ Redis  │ │
        │  │PostgreSQL│ │ Cache  │ │
        │  └──────────┘ └────────┘ │
        └───────────────────────────┘
```

### 4. **Cost Optimization Strategies**

#### Compute Optimization
- **Fargate Spot**: 70% discount for background jobs
- **Auto-scaling**: Scale down during off-hours
- **Right-sizing**: Start small, monitor, then adjust

#### Database Optimization
- **Reserved Instances**: 1-year term for 30% savings
- **Scheduled scaling**: Reduce capacity during off-hours
- **Query optimization**: Use Redis cache aggressively

#### Storage Optimization
- **S3 Lifecycle policies**: Move old reports to Glacier
- **ECR policies**: Retain only recent images
- **CloudWatch logs**: 7-day retention for non-critical logs

### 5. **Estimated Monthly Costs**

#### Minimum Production Setup
- **ECS Fargate (API)**: ~$50-100 (2 tasks @ 0.5 vCPU, 1GB RAM)
- **ECS Fargate (Scheduler)**: ~$25 (1 task @ 0.25 vCPU, 0.5GB RAM)
- **RDS PostgreSQL**: ~$30 (db.t3.small, 20GB storage)
- **ElastiCache Redis**: ~$15 (cache.t3.micro)
- **ALB**: ~$20 + data transfer
- **ECR**: ~$5 (10GB storage)
- **Secrets Manager**: ~$4 (10 secrets)
- **Total**: ~$150-200/month

#### Scaled Production Setup
- **ECS Fargate (API)**: ~$200 (4 tasks @ 1 vCPU, 2GB RAM)
- **ECS Fargate (Scheduler)**: ~$50 (2 tasks @ 0.5 vCPU, 1GB RAM)
- **RDS PostgreSQL**: ~$150 (db.t3.medium Multi-AZ, 100GB storage)
- **ElastiCache Redis**: ~$50 (cache.t3.small cluster)
- **ALB + WAF**: ~$50
- **CloudWatch enhanced**: ~$50
- **Total**: ~$550-650/month

### 6. **Deployment Pipeline**

```
Developer Push → GitHub → GitHub Actions → Build Docker Image → 
Push to ECR → Update ECS Task Definition → Rolling Deployment
```

### 7. **Alternative Architectures Considered**

#### Option A: Lambda + API Gateway (Serverless)
- **Pros**: True pay-per-use, no idle costs
- **Cons**: Cold starts, 15-min execution limit, complex for WebSockets
- **Best for**: Sporadic usage patterns

#### Option B: EC2 + Auto Scaling
- **Pros**: Full control, cost-effective at scale
- **Cons**: More management overhead, less flexible
- **Best for**: Predictable high-volume workloads

#### Option C: Kubernetes (EKS)
- **Pros**: Portable, advanced orchestration
- **Cons**: Higher complexity, ~$75/month cluster fee
- **Best for**: Multi-cloud strategy or K8s expertise

### 8. **Security Best Practices**

1. **Network Security**
   - VPC with public/private subnets
   - Security groups with least privilege
   - NACLs for additional protection

2. **Data Security**
   - Encryption at rest (RDS, S3, EBS)
   - Encryption in transit (TLS 1.2+)
   - Secrets rotation via Secrets Manager

3. **Access Control**
   - IAM roles for services
   - No hardcoded credentials
   - CloudTrail for audit logging

### 9. **Disaster Recovery**

- **RDS**: Automated backups, point-in-time recovery
- **Code**: Immutable Docker images in ECR
- **Config**: Infrastructure as Code (Terraform/CDK)
- **RPO**: < 1 hour
- **RTO**: < 30 minutes

## Recommended Next Steps

1. Start with the Minimum Production Setup
2. Implement monitoring and establish baselines
3. Optimize based on actual usage patterns
4. Consider Reserved Instances after 3 months
5. Evaluate Fargate Spot for cost savings

This architecture provides a good balance of cost, performance, and maintainability while leveraging your team's Docker expertise.