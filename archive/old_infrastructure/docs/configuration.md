# Configuration Guide

This guide explains how to configure PaidSearchNav for your environment.

## Overview

PaidSearchNav uses a hierarchical configuration system that supports:
- Environment variables with `PSN_` prefix
- `.env` files for local development
- Cloud secret managers (AWS, GCP, HashiCorp Vault)
- Multiple environments (development, staging, production)

## Quick Start

1. Copy the example configuration:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and add your credentials:
   ```bash
   # Required Google Ads credentials
   PSN_GOOGLE_ADS_DEVELOPER_TOKEN=your-developer-token
   PSN_GOOGLE_ADS_CLIENT_ID=your-client-id.apps.googleusercontent.com
   PSN_GOOGLE_ADS_CLIENT_SECRET=your-client-secret
   ```

3. Configure your storage backend:
   ```bash
   # For PostgreSQL
   PSN_STORAGE_BACKEND=postgresql
   PSN_STORAGE_CONNECTION_STRING=postgresql://user:password@localhost:5432/paidsearchnav
   
   # For BigQuery
   PSN_STORAGE_BACKEND=bigquery
   PSN_STORAGE_PROJECT_ID=your-gcp-project
   PSN_STORAGE_DATASET_NAME=paidsearchnav
   ```

## Configuration Options

### Core Settings

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `PSN_ENVIRONMENT` | Application environment | `development` | No |
| `PSN_SECRET_PROVIDER` | Secret management provider | `environment` | No |

### Google Ads Configuration

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `PSN_GOOGLE_ADS_DEVELOPER_TOKEN` | Google Ads API developer token | - | Yes |
| `PSN_GOOGLE_ADS_CLIENT_ID` | OAuth2 client ID | - | Yes |
| `PSN_GOOGLE_ADS_CLIENT_SECRET` | OAuth2 client secret | - | Yes |
| `PSN_GOOGLE_ADS_REFRESH_TOKEN` | OAuth2 refresh token | - | No |
| `PSN_GOOGLE_ADS_LOGIN_CUSTOMER_ID` | MCC account ID (10 digits) | - | No |
| `PSN_GOOGLE_ADS_API_VERSION` | Google Ads API version | `v18` | No |

### Storage Configuration

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `PSN_STORAGE_BACKEND` | Storage backend (`postgresql`, `bigquery`, `firestore`) | `postgresql` | No |
| `PSN_STORAGE_CONNECTION_STRING` | PostgreSQL connection string | - | Yes (PostgreSQL) |
| `PSN_STORAGE_PROJECT_ID` | GCP project ID | - | Yes (BigQuery/Firestore) |
| `PSN_STORAGE_DATASET_NAME` | BigQuery dataset name | - | Yes (BigQuery) |
| `PSN_STORAGE_RETENTION_DAYS` | Data retention period in days | `90` | No |

### Scheduler Configuration

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `PSN_SCHEDULER_ENABLED` | Enable scheduled audits | `true` | No |
| `PSN_SCHEDULER_DEFAULT_SCHEDULE` | CRON schedule | `0 0 1 */3 *` | No |
| `PSN_SCHEDULER_TIMEZONE` | Timezone for scheduling | `UTC` | No |
| `PSN_SCHEDULER_MAX_CONCURRENT_AUDITS` | Maximum concurrent jobs | `5` | No |
| `PSN_SCHEDULER_RETRY_ATTEMPTS` | Retry attempts for failed jobs | `3` | No |

### Logging Configuration

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `PSN_LOGGING_LEVEL` | Log level | `INFO` | No |
| `PSN_LOGGING_FORMAT` | Log format (`json`, `text`) | `json` | No |
| `PSN_LOGGING_SENTRY_DSN` | Sentry DSN for error tracking | - | No |
| `PSN_LOGGING_SLACK_WEBHOOK_URL` | Slack webhook for alerts | - | No |
| `PSN_LOGGING_EMAIL_ALERTS_TO` | Email addresses (comma-separated) | - | No |

### Feature Flags

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `PSN_ENABLE_PMAX_ANALYSIS` | Enable Performance Max analysis | `true` | No |
| `PSN_ENABLE_GEO_DASHBOARD` | Enable geographic dashboard | `true` | No |
| `PSN_ENABLE_AUTO_NEGATIVES` | Enable automatic negative suggestions | `false` | No |

## Secret Management

### Environment Variables (Default)

The default method stores secrets as environment variables or in `.env` files.

```bash
PSN_SECRET_PROVIDER=environment
```

### AWS Secrets Manager

Store secrets in AWS Secrets Manager:

```bash
PSN_SECRET_PROVIDER=aws_secrets_manager
AWS_DEFAULT_REGION=us-east-1
```

Create a secret named `paidsearchnav/{environment}` with your configuration:

```json
{
  "developer_token": "your-token",
  "client_secret": "your-secret",
  "connection_string": "postgresql://..."
}
```

### GCP Secret Manager

Store secrets in GCP Secret Manager:

```bash
PSN_SECRET_PROVIDER=gcp_secret_manager
GCP_PROJECT_ID=your-project
```

Create a secret named `paidsearchnav-{environment}` with your configuration.

### HashiCorp Vault

Store secrets in Vault:

```bash
PSN_SECRET_PROVIDER=hashicorp_vault
VAULT_URL=https://vault.example.com
VAULT_TOKEN=your-vault-token
```

Store secrets at path `secret/data/paidsearchnav/{environment}`.

## Usage in Code

```python
from paidsearchnav.core.config import get_settings

# Get configuration
settings = get_settings()

# Access configuration values
print(f"Environment: {settings.environment}")
print(f"API Version: {settings.google_ads.api_version}")
print(f"Storage Backend: {settings.storage.backend}")

# Check feature flags
if settings.features.enable_pmax_analysis:
    # Run Performance Max analysis
    pass
```

## Security Best Practices

1. **Never commit secrets**: Always use `.env` files or secret managers
2. **Use appropriate secret provider**: Use cloud secret managers in production
3. **Limit access**: Restrict access to production secrets
4. **Rotate credentials**: Regularly rotate API tokens and passwords
5. **Validate configuration**: The system validates required settings on startup

## Troubleshooting

### Missing Configuration

If you see an error like:
```
ValueError: Configuration errors: PSN_GOOGLE_ADS_DEVELOPER_TOKEN is required
```

Make sure all required environment variables are set in your `.env` file or environment.

### Invalid Storage Backend

If you see an error about storage configuration:
```
ValueError: PSN_STORAGE_CONNECTION_STRING is required for PostgreSQL backend
```

Ensure you've provided the correct configuration for your chosen storage backend.

### Secret Manager Issues

If secrets aren't loading from cloud providers:
1. Check that the secret provider is correctly configured
2. Verify you have appropriate IAM permissions
3. Ensure the secret name follows the expected pattern
4. Check logs for specific error messages