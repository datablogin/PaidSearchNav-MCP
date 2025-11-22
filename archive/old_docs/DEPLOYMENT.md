# PaidSearchNav AWS Deployment Guide

## Prerequisites

1. **AWS Account** with appropriate permissions
2. **AWS CLI** configured with credentials
3. **Terraform** (>= 1.0) installed
4. **Docker** installed
5. **Google Ads API** credentials

## Quick Start

### 1. Build and Push Docker Image

```bash
# Set your AWS account ID and region
export AWS_ACCOUNT_ID=123456789012
export AWS_REGION=us-east-1
export ECR_REGISTRY=$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# Create ECR repository (first time only)
aws ecr create-repository --repository-name paidsearchnav/prod --region $AWS_REGION

# Login to ECR
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR_REGISTRY

# Build and tag image
docker build -t paidsearchnav:latest .
docker tag paidsearchnav:latest $ECR_REGISTRY/paidsearchnav/prod:latest

# Push to ECR
docker push $ECR_REGISTRY/paidsearchnav/prod:latest
```

### 2. Deploy Infrastructure with Terraform

```bash
cd infrastructure/terraform

# Initialize Terraform
terraform init

# Create secrets file (do not commit!)
cat > secrets.tfvars <<EOF
google_ads_developer_token = "your-developer-token"
google_ads_client_id      = "your-client-id"
google_ads_client_secret  = "your-client-secret"
jwt_secret_key           = "your-jwt-secret"
ecr_image_uri           = "$ECR_REGISTRY/paidsearchnav/prod:latest"
EOF

# Plan deployment
terraform plan -var-file=environments/dev.tfvars -var-file=secrets.tfvars

# Deploy
terraform apply -var-file=environments/dev.tfvars -var-file=secrets.tfvars
```

### 3. Run Database Migrations

```bash
# Get the task definition and cluster from Terraform outputs
CLUSTER=$(terraform output -raw ecs_cluster_name)
TASK_DEF=$(aws ecs list-task-definitions --family-prefix paidsearchnav-dev-api --query 'taskDefinitionArns[0]' --output text)

# Run migrations
aws ecs run-task \
  --cluster $CLUSTER \
  --task-definition $TASK_DEF \
  --network-configuration "awsvpcConfiguration={subnets=[$(terraform output -json private_subnet_ids | jq -r 'join(",")')]}" \
  --overrides '{"containerOverrides":[{"name":"api","command":["alembic","upgrade","head"]}]}'
```

### 4. Access Your Application

```bash
# Get the ALB URL
echo "Application URL: http://$(terraform output -raw alb_dns_name)"
```

## Environment Configuration

### Development Environment

- Minimal resources for cost optimization
- Single AZ deployment
- Fargate Spot for background tasks
- No Multi-AZ RDS

### Production Environment

```bash
# Deploy production
terraform apply -var-file=environments/prod.tfvars -var-file=secrets.tfvars
```

- Multi-AZ deployment
- Auto-scaling enabled
- Enhanced monitoring
- 30-day backup retention

## CI/CD Pipeline with GitHub Actions

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy to AWS

on:
  push:
    branches: [main]
  workflow_dispatch:

env:
  AWS_REGION: us-east-1
  ECR_REPOSITORY: paidsearchnav/prod

jobs:
  deploy:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Configure AWS credentials
      uses: aws-actions/configure-aws-credentials@v2
      with:
        aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
        aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
        aws-region: ${{ env.AWS_REGION }}
    
    - name: Login to Amazon ECR
      id: login-ecr
      uses: aws-actions/amazon-ecr-login@v1
    
    - name: Build, tag, and push image
      env:
        ECR_REGISTRY: ${{ steps.login-ecr.outputs.registry }}
        IMAGE_TAG: ${{ github.sha }}
      run: |
        docker build -t $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG .
        docker push $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG
        docker tag $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG $ECR_REGISTRY/$ECR_REPOSITORY:latest
        docker push $ECR_REGISTRY/$ECR_REPOSITORY:latest
    
    - name: Update ECS service
      run: |
        aws ecs update-service \
          --cluster paidsearchnav-prod \
          --service paidsearchnav-prod-api \
          --force-new-deployment
```

## Monitoring and Maintenance

### CloudWatch Dashboards

Create a custom dashboard for monitoring:

```bash
aws cloudwatch put-dashboard \
  --dashboard-name PaidSearchNav-$ENVIRONMENT \
  --dashboard-body file://cloudwatch-dashboard.json
```

### Alarms

Key metrics to monitor:
- ECS CPU/Memory utilization
- RDS CPU/connections
- ALB target health
- API response times

### Log Analysis

```bash
# View API logs
aws logs tail /ecs/paidsearchnav/prod/api --follow

# Search for errors
aws logs filter-log-events \
  --log-group-name /ecs/paidsearchnav/prod/api \
  --filter-pattern "ERROR"
```

## Cost Optimization Tips

1. **Use Reserved Instances**: Save 30-50% on RDS
2. **Schedule Dev Environment**: Turn off during nights/weekends
3. **Enable Fargate Spot**: 70% savings for background tasks
4. **Right-size Resources**: Monitor and adjust based on usage
5. **S3 Lifecycle Policies**: Archive old reports

### Scheduled Scaling Example

```bash
# Scale down dev environment at night
aws application-autoscaling put-scheduled-action \
  --service-namespace ecs \
  --resource-id service/paidsearchnav-dev/paidsearchnav-dev-api \
  --scheduled-action-name scale-down-night \
  --schedule "cron(0 20 ? * MON-FRI *)" \
  --scalable-target-action MinCapacity=0,MaxCapacity=0

# Scale up in the morning
aws application-autoscaling put-scheduled-action \
  --service-namespace ecs \
  --resource-id service/paidsearchnav-dev/paidsearchnav-dev-api \
  --scheduled-action-name scale-up-morning \
  --schedule "cron(0 8 ? * MON-FRI *)" \
  --scalable-target-action MinCapacity=1,MaxCapacity=2
```

## Troubleshooting

### Common Issues

1. **Task fails to start**
   - Check CloudWatch logs
   - Verify security groups
   - Ensure secrets are accessible

2. **Database connection errors**
   - Verify RDS security group
   - Check database credentials in Secrets Manager
   - Ensure VPC connectivity

3. **High costs**
   - Review CloudWatch metrics
   - Enable cost allocation tags
   - Use AWS Cost Explorer

### Rollback Procedure

```bash
# List previous task definitions
aws ecs list-task-definitions --family-prefix paidsearchnav-prod-api

# Update service with previous version
aws ecs update-service \
  --cluster paidsearchnav-prod \
  --service paidsearchnav-prod-api \
  --task-definition paidsearchnav-prod-api:PREVIOUS_VERSION
```

## Security Best Practices

1. **Secrets Management**
   - Never commit secrets to git
   - Use AWS Secrets Manager
   - Rotate credentials regularly

2. **Network Security**
   - Keep RDS in private subnets
   - Use security groups restrictively
   - Enable VPC Flow Logs

3. **Access Control**
   - Use IAM roles, not keys
   - Enable MFA for AWS console
   - Audit with CloudTrail

## Backup and Restore Procedures

### Database Backups

#### Automated Backups
- RDS automatically creates daily snapshots
- Retention period: 7 days (configurable)
- Point-in-time recovery available within retention window

#### Manual Backup
```bash
# Create manual snapshot
aws rds create-db-snapshot \
  --db-instance-identifier paidsearchnav-${ENV}-db \
  --db-snapshot-identifier paidsearchnav-${ENV}-manual-$(date +%Y%m%d-%H%M%S)

# List snapshots
aws rds describe-db-snapshots \
  --db-instance-identifier paidsearchnav-${ENV}-db
```

#### Restore from Snapshot
```bash
# Restore to new instance
aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier paidsearchnav-${ENV}-db-restored \
  --db-snapshot-identifier <snapshot-id>

# Update Terraform to point to new instance
# Update infrastructure/terraform/rds.tf with new instance details
```

#### Point-in-Time Recovery
```bash
# Restore to specific time
aws rds restore-db-instance-to-point-in-time \
  --source-db-instance-identifier paidsearchnav-${ENV}-db \
  --target-db-instance-identifier paidsearchnav-${ENV}-db-pitr \
  --restore-time 2024-01-01T12:00:00.000Z
```

### Application State Backup

#### Export Application Data
```bash
# Connect to ECS task
aws ecs execute-command \
  --cluster paidsearchnav-${ENV} \
  --task <task-id> \
  --container api \
  --interactive \
  --command "/bin/bash"

# Export data using application CLI
python -m paidsearchnav.cli export-data --output /tmp/backup.json

# Copy backup locally
aws s3 cp /tmp/backup.json s3://your-backup-bucket/paidsearchnav/backup-$(date +%Y%m%d).json
```

### Disaster Recovery

#### Full Environment Recovery
1. **Restore RDS from snapshot**
   ```bash
   # Use latest automated snapshot or specific manual snapshot
   aws rds restore-db-instance-from-db-snapshot \
     --db-instance-identifier paidsearchnav-${ENV}-db \
     --db-snapshot-identifier <snapshot-id>
   ```

2. **Rebuild infrastructure**
   ```bash
   cd infrastructure/terraform
   terraform init
   terraform plan -var-file=secrets.tfvars
   terraform apply -var-file=secrets.tfvars
   ```

3. **Deploy latest application version**
   ```bash
   # Force new deployment
   aws ecs update-service \
     --cluster paidsearchnav-${ENV} \
     --service paidsearchnav-${ENV}-api \
     --force-new-deployment
   ```

4. **Verify services**
   - Check health endpoint: `https://your-domain/api/v1/health`
   - Monitor CloudWatch dashboards
   - Test critical functionality

### Backup Best Practices

1. **Regular Testing**
   - Test restore procedures monthly
   - Document restore times
   - Verify data integrity

2. **Backup Monitoring**
   - Set up CloudWatch alarms for failed backups
   - Monitor backup storage costs
   - Review backup retention policies

3. **Cross-Region Backups** (Production only)
   ```bash
   # Copy snapshots to another region
   aws rds copy-db-snapshot \
     --source-db-snapshot-identifier <source-snapshot> \
     --target-db-snapshot-identifier <target-snapshot> \
     --source-region us-east-1 \
     --region us-west-2
   ```

## Support

For issues or questions:
- Check CloudWatch logs first
- Review Terraform state
- Contact your DevOps team