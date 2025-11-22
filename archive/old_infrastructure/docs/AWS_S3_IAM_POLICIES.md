# AWS S3 IAM Policy Templates for PaidSearchNav

This document provides IAM policy templates for secure access to the PaidSearchNav S3 bucket infrastructure.

## Application IAM Policy

This policy provides the minimum required permissions for the PaidSearchNav application to operate with S3.

### PaidSearchNav Application Policy
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
        }
    ]
}
```

## Environment-Specific Policies

### Production Environment Policy
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "ProductionS3Access",
            "Effect": "Allow",
            "Action": [
                "s3:ListBucket",
                "s3:GetBucketLocation",
                "s3:GetObject",
                "s3:GetObjectVersion",
                "s3:PutObject",
                "s3:DeleteObject"
            ],
            "Resource": [
                "arn:aws:s3:::paidsearchnav-customer-data",
                "arn:aws:s3:::paidsearchnav-customer-data/PaidSearchNav/*"
            ]
        }
    ]
}
```

### Development Environment Policy
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "DevelopmentS3Access",
            "Effect": "Allow",
            "Action": [
                "s3:ListBucket",
                "s3:GetBucketLocation",
                "s3:GetObject",
                "s3:GetObjectVersion",
                "s3:PutObject",
                "s3:DeleteObject",
                "s3:ListBucketMultipartUploads",
                "s3:ListMultipartUploadParts",
                "s3:AbortMultipartUpload"
            ],
            "Resource": [
                "arn:aws:s3:::paidsearchnav-customer-data-dev",
                "arn:aws:s3:::paidsearchnav-customer-data-dev/PaidSearchNav/*"
            ]
        }
    ]
}
```

## Customer-Isolated Access Policy

This policy restricts access to specific customer data paths:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "CustomerSpecificAccess",
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:PutObject",
                "s3:DeleteObject"
            ],
            "Resource": [
                "arn:aws:s3:::paidsearchnav-customer-data/PaidSearchNav/${aws:userid}/*"
            ]
        },
        {
            "Sid": "ListOwnCustomerData",
            "Effect": "Allow",
            "Action": [
                "s3:ListBucket"
            ],
            "Resource": "arn:aws:s3:::paidsearchnav-customer-data",
            "Condition": {
                "StringLike": {
                    "s3:prefix": [
                        "PaidSearchNav/${aws:userid}/*"
                    ]
                }
            }
        }
    ]
}
```

## ECS Fargate Task Role Policy

For containerized deployments:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "ECSTaskS3Access",
            "Effect": "Allow",
            "Action": [
                "s3:ListBucket",
                "s3:GetBucketLocation",
                "s3:GetObject",
                "s3:GetObjectVersion",
                "s3:PutObject",
                "s3:DeleteObject",
                "s3:ListMultipartUploadParts",
                "s3:AbortMultipartUpload"
            ],
            "Resource": [
                "arn:aws:s3:::paidsearchnav-customer-data",
                "arn:aws:s3:::paidsearchnav-customer-data/PaidSearchNav/*"
            ]
        },
        {
            "Sid": "AllowEC2MetadataAccess",
            "Effect": "Allow",
            "Action": [
                "ec2:DescribeRegions"
            ],
            "Resource": "*"
        }
    ]
}
```

## Cross-Account Access Policy

If you need to grant access from another AWS account:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "CrossAccountS3Access",
            "Effect": "Allow",
            "Principal": {
                "AWS": "arn:aws:iam::ACCOUNT-ID:role/PaidSearchNavRole"
            },
            "Action": [
                "s3:GetObject",
                "s3:PutObject",
                "s3:DeleteObject"
            ],
            "Resource": "arn:aws:s3:::paidsearchnav-customer-data/PaidSearchNav/*"
        }
    ]
}
```

## Bucket Policy Template

Apply this policy directly to the S3 bucket for additional security:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "EnforceSSLRequestsOnly",
            "Effect": "Deny",
            "Principal": "*",
            "Action": "s3:*",
            "Resource": [
                "arn:aws:s3:::paidsearchnav-customer-data",
                "arn:aws:s3:::paidsearchnav-customer-data/*"
            ],
            "Condition": {
                "Bool": {
                    "aws:SecureTransport": "false"
                }
            }
        },
        {
            "Sid": "DenyInsecureConnections",
            "Effect": "Deny",
            "Principal": "*",
            "Action": "s3:*",
            "Resource": [
                "arn:aws:s3:::paidsearchnav-customer-data",
                "arn:aws:s3:::paidsearchnav-customer-data/*"
            ],
            "Condition": {
                "StringNotEquals": {
                    "s3:x-amz-server-side-encryption": "AES256"
                },
                "StringNotEquals": {
                    "s3:x-amz-server-side-encryption": "aws:kms"
                }
            }
        }
    ]
}
```

## Usage Instructions

### 1. Create IAM Role
```bash
aws iam create-role \
    --role-name PaidSearchNavS3Role \
    --assume-role-policy-document file://trust-policy.json
```

### 2. Create and Attach Policy
```bash
aws iam create-policy \
    --policy-name PaidSearchNavS3Policy \
    --policy-document file://s3-policy.json

aws iam attach-role-policy \
    --role-name PaidSearchNavS3Role \
    --policy-arn arn:aws:iam::ACCOUNT-ID:policy/PaidSearchNavS3Policy
```

### 3. Configure Application
Update your `.env` file:
```bash
# For IAM Role (recommended for ECS/EC2)
PSN_S3_ENABLED=true
PSN_S3_BUCKET_NAME=paidsearchnav-customer-data
PSN_S3_REGION=us-west-2

# For IAM User (development only)
PSN_S3_ACCESS_KEY_ID=your-access-key
PSN_S3_SECRET_ACCESS_KEY=your-secret-key
```

## Security Best Practices

1. **Use IAM Roles** instead of IAM users when possible
2. **Enable MFA** for sensitive operations
3. **Rotate access keys** regularly if using IAM users
4. **Monitor access** with CloudTrail and CloudWatch
5. **Use least privilege** principle
6. **Enable versioning** and **MFA delete** on the bucket
7. **Set up lifecycle policies** to manage costs
8. **Use VPC endpoints** for private network access

## Monitoring and Alerting

Consider setting up CloudWatch alarms for:
- Unusual upload/download patterns
- Failed authentication attempts
- Large file operations
- Unauthorized access attempts

## Replace Placeholders

Before using these policies, replace:
- `paidsearchnav-customer-data` with your actual bucket name
- `ACCOUNT-ID` with your AWS account ID
- Adjust resource ARNs as needed for your specific setup