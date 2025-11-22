#!/bin/bash

# Deploy ECS Task Definitions with S3 Integration
# Usage: ./deploy-ecs-with-s3.sh [profile]

set -e

AWS_PROFILE=${1:-roimedia-east1}
REGION="us-east-1"

echo "🚀 Deploying ECS Task Definitions with S3 Integration"
echo "Using AWS Profile: $AWS_PROFILE"
echo "Region: $REGION"

# Function to check if AWS CLI is configured
check_aws_cli() {
    if ! command -v aws &> /dev/null; then
        echo "❌ AWS CLI is not installed"
        exit 1
    fi
    
    if ! aws sts get-caller-identity --profile $AWS_PROFILE &> /dev/null; then
        echo "❌ AWS CLI not configured or profile '$AWS_PROFILE' not found"
        exit 1
    fi
}

# Function to create CloudWatch Log Groups
create_log_groups() {
    echo "📋 Creating CloudWatch Log Groups..."
    
    # API service log group
    aws logs create-log-group \
        --profile $AWS_PROFILE \
        --region $REGION \
        --log-group-name "/ecs/paidsearchnav/api" \
        --no-cli-pager \
        2>/dev/null || echo "  ℹ️  Log group /ecs/paidsearchnav/api already exists"
    
    # Scheduler service log group
    aws logs create-log-group \
        --profile $AWS_PROFILE \
        --region $REGION \
        --log-group-name "/ecs/paidsearchnav/scheduler" \
        --no-cli-pager \
        2>/dev/null || echo "  ℹ️  Log group /ecs/paidsearchnav/scheduler already exists"
    
    echo "✅ Log groups created"
}

# Function to register task definitions
register_task_definitions() {
    echo "📦 Registering ECS Task Definitions..."
    
    # Register API service task definition
    echo "  📱 Registering API service task definition..."
    API_TASK_ARN=$(aws ecs register-task-definition \
        --profile $AWS_PROFILE \
        --region $REGION \
        --cli-input-json file://docs/ecs-task-definition-with-s3.json \
        --no-cli-pager \
        --query 'taskDefinition.taskDefinitionArn' \
        --output text)
    
    echo "  ✅ API Task Definition: $API_TASK_ARN"
    
    # Register scheduler service task definition
    echo "  ⏰ Registering scheduler service task definition..."
    SCHEDULER_TASK_ARN=$(aws ecs register-task-definition \
        --profile $AWS_PROFILE \
        --region $REGION \
        --cli-input-json file://docs/ecs-scheduler-task-definition.json \
        --no-cli-pager \
        --query 'taskDefinition.taskDefinitionArn' \
        --output text)
    
    echo "  ✅ Scheduler Task Definition: $SCHEDULER_TASK_ARN"
}

# Function to validate S3 permissions
validate_s3_permissions() {
    echo "🔒 Validating S3 permissions..."
    
    # Check if S3 buckets exist
    if aws s3 ls s3://paidsearchnav-customer-data --profile $AWS_PROFILE &> /dev/null; then
        echo "  ✅ Production bucket (paidsearchnav-customer-data) accessible"
    else
        echo "  ⚠️  Production bucket (paidsearchnav-customer-data) not found or not accessible"
    fi
    
    if aws s3 ls s3://paidsearchnav-customer-data-dev --profile $AWS_PROFILE &> /dev/null; then
        echo "  ✅ Development bucket (paidsearchnav-customer-data-dev) accessible"
    else
        echo "  ⚠️  Development bucket (paidsearchnav-customer-data-dev) not found or not accessible"
    fi
}

# Function to create or update ECS services
update_ecs_services() {
    echo "🔄 Updating ECS Services..."
    
    # Note: This assumes you have an existing ECS cluster
    # You may need to create the cluster first or update the service names
    
    echo "  ℹ️  To update your ECS services with the new task definitions, run:"
    echo ""
    echo "  # Update API service"
    echo "  aws ecs update-service \\"
    echo "    --profile $AWS_PROFILE \\"
    echo "    --region $REGION \\"
    echo "    --cluster your-cluster-name \\"
    echo "    --service paidsearchnav-api \\"
    echo "    --task-definition $API_TASK_ARN"
    echo ""
    echo "  # Update scheduler service"
    echo "  aws ecs update-service \\"
    echo "    --profile $AWS_PROFILE \\"
    echo "    --region $REGION \\"
    echo "    --cluster your-cluster-name \\"
    echo "    --service paidsearchnav-scheduler \\"
    echo "    --task-definition $SCHEDULER_TASK_ARN"
}

# Main execution
main() {
    echo "Starting deployment process..."
    
    check_aws_cli
    create_log_groups
    register_task_definitions
    validate_s3_permissions
    update_ecs_services
    
    echo ""
    echo "🎉 Deployment completed successfully!"
    echo ""
    echo "Next steps:"
    echo "1. Update your container image with S3 integration code"
    echo "2. Push new image to ECR"
    echo "3. Update ECS services with the commands shown above"
    echo "4. Test S3 integration with a sample upload"
    echo ""
    echo "S3 Configuration:"
    echo "  Production Bucket: paidsearchnav-customer-data"
    echo "  Development Bucket: paidsearchnav-customer-data-dev"
    echo "  IAM Role: PaidSearchNavS3Role"
    echo "  Folder Structure: PaidSearchNav/{customer-name}/{customer-number}/{date}/"
}

# Run main function
main "$@"