# PaidSearchNav AWS ECS Fargate Deployment Quick Start

This guide will help you deploy PaidSearchNav to AWS ECS Fargate step by step.

## Prerequisites Checklist

- [ ] AWS Account with appropriate permissions
- [ ] AWS CLI configured (`aws configure`)
- [ ] Terraform installed (>= 1.0)
- [ ] Docker installed
- [ ] Google Ads API credentials ready

## Step 1: Prepare Environment Variables

Create a `.env.deployment` file (DO NOT COMMIT):

```bash
# AWS Configuration
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export AWS_REGION=us-east-1
export ECR_REGISTRY=$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# Google Ads API Credentials
export GOOGLE_ADS_DEVELOPER_TOKEN="your-developer-token"
export GOOGLE_ADS_CLIENT_ID="your-client-id"
export GOOGLE_ADS_CLIENT_SECRET="your-client-secret"

# Application Secrets
export JWT_SECRET_KEY="$(openssl rand -base64 32)"
export DATABASE_PASSWORD="$(openssl rand -base64 16)"
```

Load the environment:
```bash
source .env.deployment
```

## Step 2: Build and Push Docker Image

```bash
# Create ECR repository
aws ecr describe-repositories --repository-names paidsearchnav/dev --region $AWS_REGION || \
  aws ecr create-repository --repository-name paidsearchnav/dev --region $AWS_REGION

# Login to ECR
aws ecr get-login-password --region $AWS_REGION | \
  docker login --username AWS --password-stdin $ECR_REGISTRY

# Build and push image
docker build -t paidsearchnav:latest .
docker tag paidsearchnav:latest $ECR_REGISTRY/paidsearchnav/dev:latest
docker push $ECR_REGISTRY/paidsearchnav/dev:latest

# Save the image URI
export ECR_IMAGE_URI=$ECR_REGISTRY/paidsearchnav/dev:latest
echo "ECR Image URI: $ECR_IMAGE_URI"
```

## Step 3: Setup Terraform Backend

```bash
cd infrastructure/terraform

# Create S3 backend for Terraform state
./scripts/setup-backend.sh dev

# This will create a backend-dev.tf file
```

## Step 4: Initialize Terraform

```bash
# Initialize with the backend
terraform init -backend-config=backend-dev.tf
```

## Step 5: Create Secrets File

Create `infrastructure/terraform/secrets.tfvars`:

```hcl
google_ads_developer_token = "YOUR_DEVELOPER_TOKEN"
google_ads_client_id      = "YOUR_CLIENT_ID"
google_ads_client_secret  = "YOUR_CLIENT_SECRET"
jwt_secret_key           = "YOUR_JWT_SECRET"
ecr_image_uri           = "YOUR_ECR_IMAGE_URI_FROM_STEP_2"
```

## Step 6: Deploy Infrastructure

```bash
# Plan the deployment
terraform plan -var-file=environments/dev.tfvars -var-file=secrets.tfvars

# Review the plan, then apply
terraform apply -var-file=environments/dev.tfvars -var-file=secrets.tfvars
```

## Step 7: Run Database Migrations

After the infrastructure is created:

```bash
# Get outputs from Terraform
CLUSTER=$(terraform output -raw ecs_cluster_name)
SUBNET_IDS=$(terraform output -json private_subnet_ids | jq -r 'join(",")')
SECURITY_GROUP=$(terraform output -raw ecs_security_group_id)

# Get the latest task definition
TASK_DEF=$(aws ecs list-task-definitions \
  --family-prefix paidsearchnav-dev-api \
  --query 'taskDefinitionArns[0]' \
  --output text)

# Run migrations
aws ecs run-task \
  --cluster $CLUSTER \
  --task-definition $TASK_DEF \
  --network-configuration "awsvpcConfiguration={subnets=[$SUBNET_IDS],securityGroups=[$SECURITY_GROUP],assignPublicIp=DISABLED}" \
  --overrides '{"containerOverrides":[{"name":"api","command":["alembic","upgrade","head"]}]}' \
  --launch-type FARGATE
```

## Step 8: Verify Deployment

```bash
# Get the ALB URL
ALB_URL=$(terraform output -raw alb_dns_name)
echo "Application URL: http://$ALB_URL"

# Check health endpoint
curl -f http://$ALB_URL/api/v1/health

# View logs
aws logs tail /ecs/paidsearchnav/dev/api --follow
```

## Step 9: Test the API

```bash
# Test the API is working
curl http://$ALB_URL/api/v1/version

# View API documentation
echo "API Docs: http://$ALB_URL/docs"
echo "ReDoc: http://$ALB_URL/redoc"
```

## Common Issues and Solutions

### 1. Task fails to start
```bash
# Check task status
aws ecs describe-tasks \
  --cluster $CLUSTER \
  --tasks $(aws ecs list-tasks --cluster $CLUSTER --query 'taskArns[0]' --output text)

# View detailed logs
aws logs get-log-events \
  --log-group-name /ecs/paidsearchnav/dev/api \
  --log-stream-name $(aws logs describe-log-streams \
    --log-group-name /ecs/paidsearchnav/dev/api \
    --order-by LastEventTime \
    --descending \
    --query 'logStreams[0].logStreamName' \
    --output text)
```

### 2. Database connection issues
- Check RDS security group allows connections from ECS
- Verify database credentials in Secrets Manager
- Ensure RDS is in the same VPC as ECS

### 3. Image pull errors
- Verify ECR repository exists
- Check task execution role has ECR permissions
- Ensure image URI is correct in task definition

## Next Steps

1. **Set up CI/CD**: Configure GitHub Actions for automated deployments
2. **Configure monitoring**: Set up CloudWatch dashboards and alarms
3. **Enable auto-scaling**: Configure ECS service auto-scaling policies
4. **Set up domain**: Configure Route53 and SSL certificate

## Cleanup (Development Environment)

To destroy the infrastructure and avoid charges:

```bash
# Remove all resources
terraform destroy -var-file=environments/dev.tfvars -var-file=secrets.tfvars

# Delete ECR images
aws ecr delete-repository --repository-name paidsearchnav/dev --force

# Delete S3 backend (optional - keeps state history)
# aws s3 rb s3://YOUR_BACKEND_BUCKET --force
```

## Production Deployment

For production deployment:
1. Use `prod.tfvars` instead of `dev.tfvars`
2. Enable Multi-AZ RDS
3. Increase resource allocations
4. Configure domain and SSL
5. Set up monitoring alerts
6. Enable deletion protection

## Support

If you encounter issues:
1. Check CloudWatch logs
2. Review Terraform output
3. Verify AWS permissions
4. Check the DEPLOYMENT.md for detailed troubleshooting