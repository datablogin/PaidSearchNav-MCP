# Secret Detection Guide

This document explains how the secret detection system works in PaidSearchNav and how to use it effectively.

## Overview

The PaidSearchNav project uses multiple layers of secret detection to prevent accidental exposure of credentials and API keys:

1. **GitLeaks** - Primary secret detection tool for comprehensive scanning
2. **detect-secrets** - Additional secret detection with baseline management
3. **Pre-commit hooks** - Local development protection
4. **CI/CD integration** - Automated scanning on every push and PR

## Tools Used

### GitLeaks
- **Purpose**: Comprehensive secret detection with custom rules
- **Configuration**: `.gitleaks.toml`
- **Runs**: Pre-commit hooks, CI/CD pipeline, dedicated workflow
- **Features**: Custom rules for Google Ads API keys, database strings, JWT secrets

### detect-secrets
- **Purpose**: Entropy-based detection with allowlist management
- **Configuration**: `.secrets.baseline`
- **Runs**: Pre-commit hooks
- **Features**: High entropy string detection, baseline allowlist

### Pre-commit Hooks
- **Configuration**: `.pre-commit-config.yaml`
- **Purpose**: Prevent commits containing secrets at development time
- **Installation**: See installation section below

## Installation and Setup

### 1. Install Pre-commit Hooks

```bash
# Install pre-commit (if not already installed)
pip install pre-commit

# Install hooks
pre-commit install

# Install push hooks (optional but recommended)
pre-commit install --hook-type pre-push
```

### 2. Initial Setup

```bash
# Run hooks against all files (first time setup)
pre-commit run --all-files

# Update hooks to latest versions
pre-commit autoupdate
```

## What Gets Detected

### Google Ads API Credentials
- Developer tokens (PSN_GOOGLE_ADS_DEVELOPER_TOKEN)
- Client secrets (PSN_GOOGLE_ADS_CLIENT_SECRET, GOCSPX- format)
- Client IDs (PSN_GOOGLE_ADS_CLIENT_ID)
- Refresh tokens (PSN_GOOGLE_ADS_REFRESH_TOKEN)

### Database Credentials
- Connection strings (PSN_STORAGE_CONNECTION_STRING)
- PostgreSQL, MySQL, SQLite URLs with credentials

### Cloud Services
- AWS Access Keys (AKIA format)
- AWS Secret Access Keys
- BigQuery service account JSON files

### Application Secrets
- JWT secrets
- PSN secret keys
- Redis passwords

### General Patterns
- High entropy strings (base64, hex)
- Private keys (RSA, SSH, etc.)
- Generic API keys and tokens

## Handling False Positives

### Method 1: Update GitLeaks Allowlist

Edit `.gitleaks.toml` and add patterns to the `[allowlist].regexes` section:

```toml
[allowlist]
regexes = [
  # Add your pattern here
  '''my_specific_false_positive_pattern''',
]
```

### Method 2: Update detect-secrets Baseline

```bash
# Scan and update baseline
detect-secrets scan --baseline .secrets.baseline

# Review and approve legitimate secrets
detect-secrets audit .secrets.baseline
```

### Method 3: Add Inline Comments

For GitLeaks, you can add allowlist comments:

```python
secret_key = "not-a-real-secret"  # gitleaks:allow
```

## Working with Legitimate Secrets

### Environment Variables
Use environment variables for runtime configuration:

```python
import os

# Good: Use environment variables
google_ads_developer_token = os.getenv('PSN_GOOGLE_ADS_DEVELOPER_TOKEN')

# Bad: Hardcoded secret
google_ads_developer_token = 'your-actual-token-here'
```

### .env Files
Use `.env` files for local development (ensure they're in `.gitignore`):

```bash
# .env.example (safe to commit)
PSN_GOOGLE_ADS_DEVELOPER_TOKEN=your_token_here
PSN_GOOGLE_ADS_CLIENT_ID=your_client_id_here

# .env (never commit)
PSN_GOOGLE_ADS_DEVELOPER_TOKEN=actual_token_value
PSN_GOOGLE_ADS_CLIENT_ID=actual_client_id_value
```

### GitHub Secrets
For CI/CD, use GitHub Secrets:

1. Go to repository Settings > Secrets and variables > Actions
2. Add secrets like `PSN_GOOGLE_ADS_DEVELOPER_TOKEN`
3. Reference in workflows:

```yaml
env:
  PSN_GOOGLE_ADS_DEVELOPER_TOKEN: ${{ secrets.PSN_GOOGLE_ADS_DEVELOPER_TOKEN }}
```

## CI/CD Integration

### Secret Detection Workflow
- **File**: `.github/workflows/secret-detection.yml`
- **Triggers**: Push to main/develop, pull requests
- **Features**:
  - Comprehensive GitLeaks scanning
  - PR comments on detection
  - Artifact upload for reports
  - Differential scanning for PRs

### Main CI Workflow
- **File**: `.github/workflows/ci.yml`
- **Integration**: GitLeaks step added to main CI pipeline
- **Behavior**: Fails the build if secrets are detected

## Troubleshooting

### Common Issues

#### Pre-commit Hook Fails
```bash
# Skip hooks temporarily (NOT recommended)
git commit --no-verify -m "temporary skip"

# Better: Fix the issue and recommit
# Remove the secret, add to allowlist, or use environment variable
```

#### False Positive in CI
1. Check the CI logs for the specific detection
2. Add the pattern to `.gitleaks.toml` allowlist
3. Commit and push the updated configuration

#### High Entropy String Detection
These are often legitimate secrets. Consider:
1. Using environment variables instead
2. Adding specific patterns to allowlist if truly not sensitive
3. Updating the entropy threshold in `.secrets.baseline`

### Manual Testing

```bash
# Test GitLeaks locally
gitleaks detect --config=.gitleaks.toml --verbose --source=.

# Test specific file
gitleaks detect --config=.gitleaks.toml --source=path/to/file.py

# Test detect-secrets
detect-secrets scan path/to/file.py
```

## Best Practices

### Development
1. **Never commit secrets** - Use environment variables
2. **Review changes** before committing
3. **Keep allowlists minimal** - Only add true false positives
4. **Use descriptive names** for non-secret configuration

### Secret Management
1. **Environment Variables**: For runtime configuration
2. **GitHub Secrets**: For CI/CD
3. **Azure Key Vault**: For production secrets (future enhancement)
4. **Least Privilege**: Only provide necessary access

### Maintenance
1. **Regular Updates**: Keep tools and configurations updated
2. **Baseline Review**: Periodically audit the secrets baseline
3. **Pattern Updates**: Update detection patterns as needed
4. **Team Training**: Ensure all team members understand the system

## Resources

- [GitLeaks Documentation](https://github.com/gitleaks/gitleaks)
- [detect-secrets Documentation](https://github.com/Yelp/detect-secrets)
- [Pre-commit Documentation](https://pre-commit.com/)
- [GitHub Secrets Documentation](https://docs.github.com/en/actions/security-guides/encrypted-secrets)
- [12-Factor App Config](https://12factor.net/config)

## Support

If you encounter issues with secret detection:

1. Check this documentation first
2. Review the CI logs for specific error details
3. Test locally using the manual testing commands
4. Update allowlists for legitimate false positives
5. Consult with the security team for complex cases