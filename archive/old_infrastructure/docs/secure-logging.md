# Secure Logging Practices

This document explains how PaidSearchNav implements secure logging to prevent credential exposure in logs.

## Overview

The logging system automatically detects and masks sensitive information such as API keys, passwords, tokens, and other secrets before writing them to log files or sending them to external services.

## Features

### Automatic Secret Detection

The system uses multiple detection methods:

1. **Sensitive Field Names**: Automatically masks values for fields with sensitive names like:
   - `password`, `pwd`, `pass`, `passwd`
   - `secret`, `token`, `key`, `api_key`, `apikey`
   - `access_token`, `refresh_token`, `auth_token`
   - `webhook_url`, `dsn`, `connection_string`
   - And many more...

2. **Pattern-Based Detection**: Uses regex patterns to detect common secret formats:
   - Google API keys (`AIzaSy...`)
   - OpenAI keys (`sk-...`)
   - Slack tokens (`xoxb-...`, `xoxp-...`)
   - GitHub tokens (`ghp_...`, `gho_...`, `ghs_...`)
   - JWT tokens (`eyJ...`)
   - Base64 encoded secrets
   - Hex encoded secrets
   - URLs with embedded credentials
   - And more...

### Comprehensive Coverage

Secret masking works across all logging components:

- **Log Messages**: Secrets in log message text are masked
- **Structured Data**: Secrets in extra fields and context data are masked
- **Exception Tracebacks**: Secrets in exception messages and tracebacks are masked
- **All Formatters**: JSON, Pretty JSON, and Colored formatters all apply masking

## Configuration

### Environment Variables

You can configure secret masking behavior using these environment variables:

```bash
# Enable/disable secret masking (default: true)
PSN_LOG_ENABLE_SECRET_MASKING=true

# Custom mask string (default: "***REDACTED***")
PSN_LOG_SECRET_MASK_STRING="[HIDDEN]"

# Additional sensitive field names (comma-separated)
PSN_LOG_CUSTOM_SENSITIVE_KEYS="my_secret_field,custom_token,private_data"

# Additional regex patterns for secret detection (comma-separated)
PSN_LOG_CUSTOM_SECRET_PATTERNS="CUSTOM-[A-Z0-9]{16},MYKEY-[a-f0-9]{32}"

# Regex patterns for whitelisting false positives (comma-separated)
PSN_LOG_WHITELIST_PATTERNS="example-[a-f0-9]{8},test-data-[0-9]+"

# Logger names to disable secret masking for (performance optimization)
PSN_LOG_DISABLED_MASKING_LOGGERS="high.throughput.logger,performance.critical"

# Enable audit logging of secret detection events (default: false)
PSN_LOG_ENABLE_AUDIT_LOGGING=true
```

### Programmatic Configuration

You can also configure secret masking programmatically:

```python
from paidsearchnav.logging import get_secrets_registry
import logging

# Get the global secrets registry
registry = get_secrets_registry()

# Add custom sensitive field names
registry.add_sensitive_key("my_custom_secret")
registry.add_sensitive_key("internal_token")

# Add custom regex patterns
registry.add_secret_pattern(r"MYAPP-[A-Z0-9]{20}")
registry.add_secret_pattern(r"custom_key_[a-f0-9]{16}")

# Add whitelist patterns for false positives
registry.add_whitelist_pattern(r"example-[a-f0-9]{8}")
registry.add_whitelist_pattern(r"test-data-[0-9]+")

# Performance optimization: disable masking for high-throughput loggers
registry.disable_masking_for_logger("high.throughput.logger")
registry.disable_masking_for_logger("performance.critical.logger")

# Enable audit logging with custom logger
audit_logger = logging.getLogger("security.audit")
registry.enable_audit_logging(audit_logger)

# Or enable with default audit logger
registry.enable_audit_logging()
```

## Usage Examples

### Basic Logging with Automatic Masking

```python
from paidsearchnav.logging import get_logger

logger = get_logger(__name__)

# These will be automatically masked
logger.info("User authenticated with API key: sk-1234567890abcdef1234567890abcdef")
logger.error("Failed to connect with password: secret123")

# Structured logging also masks secrets
logger.info("Authentication attempt", extra={
    "user_id": "12345",
    "api_key": "AIzaSyDxxxxxxxxxxxxxxxxxxxxxxxxxxx",  # Will be masked
    "timestamp": "2024-01-01T00:00:00Z"  # Will not be masked
})
```

### Manual Secret Masking

You can also manually mask secrets in your own data:

```python
from paidsearchnav.logging import mask_secrets

# Mask secrets in a dictionary
data = {
    "username": "john_doe",
    "password": "secret123",  # Will be masked
    "config": {
        "api_key": "sk-1234567890abcdef1234567890abcdef",  # Will be masked
        "timeout": 30  # Will not be masked
    }
}

masked_data = mask_secrets(data)
print(masked_data)
# Output: {
#     "username": "john_doe", 
#     "password": "***REDACTED***",
#     "config": {
#         "api_key": "***REDACTED***",
#         "timeout": 30
#     }
# }

# Mask secrets in a string
text = "My secret key is sk-1234567890abcdef1234567890abcdef"
masked_text = mask_secrets(text)
print(masked_text)
# Output: "My secret key is ***REDACTED***"

# Use custom mask string
masked_data = mask_secrets(data, mask="[HIDDEN]")
```

## Enhanced Features

### Performance Optimizations

For high-throughput applications, you can disable secret masking for specific loggers:

```python
from paidsearchnav.logging import get_secrets_registry

registry = get_secrets_registry()

# Disable masking for performance-critical loggers
registry.disable_masking_for_logger("metrics.collector")
registry.disable_masking_for_logger("high.frequency.events")

# Re-enable when needed
registry.enable_masking_for_logger("metrics.collector")
```

### Audit Logging

Enable audit logging to track when secrets are detected and masked:

```python
from paidsearchnav.logging import get_secrets_registry
import logging

# Configure audit logging
registry = get_secrets_registry()
registry.enable_audit_logging()

# Now all secret detections will be logged to 'paidsearchnav.security.audit'
logger = logging.getLogger("myapp")
logger.info("User login", extra={"api_key": "sk-secret123"})
# This will trigger an audit log: "Secret detected and masked"
```

### Whitelist for False Positives

Handle known false positives with whitelist patterns:

```python
from paidsearchnav.logging import get_secrets_registry

registry = get_secrets_registry()

# Add patterns for legitimate data that looks like secrets
registry.add_whitelist_pattern(r"example-[a-f0-9]{32}")  # Example IDs
registry.add_whitelist_pattern(r"test-data-[0-9]+")     # Test identifiers

# These will now NOT be masked even though they match secret patterns
data = {
    "real_secret": "sk-1234567890abcdef1234567890abcdef",  # Will be masked
    "example_id": "example-abcd1234567890abcdef123456789012",  # Will NOT be masked
    "test_id": "test-data-12345"  # Will NOT be masked
}
```

## Best Practices

### 1. Use Structured Logging

Always use structured logging with extra fields rather than embedding secrets in message strings:

```python
# Good - secrets in structured fields are reliably masked
logger.info("Authentication successful", extra={
    "user_id": user_id,
    "api_key": api_key  # Will be masked
})

# Less reliable - pattern matching may miss some formats
logger.info(f"Authentication successful for {user_id} with key {api_key}")
```

### 2. Avoid Logging Secrets Unnecessarily

The best practice is to avoid logging secrets at all:

```python
# Good - don't log the actual secret
logger.info("API authentication successful", extra={
    "user_id": user_id,
    "key_hash": hashlib.sha256(api_key.encode()).hexdigest()[:8]  # Log a hash prefix instead
})

# Bad - logging the actual secret (even though it will be masked)
logger.info("API authentication successful", extra={
    "user_id": user_id,
    "api_key": api_key
})
```

### 3. Use Consistent Field Names

Use standard field names for sensitive data to ensure they're caught by the sensitive key detection:

```python
# Good - standard field names are automatically detected
logger.info("Database connected", extra={
    "username": db_user,
    "password": db_pass  # Will be masked
})

# Less reliable - non-standard field names might not be detected
logger.info("Database connected", extra={
    "db_user": db_user,
    "db_secret": db_pass  # Might not be detected without custom configuration
})
```

### 4. Test Your Logging

Always test that your logging doesn't expose secrets:

```python
import logging
from io import StringIO

# Capture log output for testing
log_capture = StringIO()
handler = logging.StreamHandler(log_capture)
logger.addHandler(handler)

# Log something with a secret
logger.info("Test", extra={"api_key": "sk-test123456789"})

# Verify the secret is masked
log_output = log_capture.getvalue()
assert "sk-test123456789" not in log_output
assert "***REDACTED***" in log_output
```

## API Reference

### `mask_secrets(data, mask="***REDACTED***")`

Mask secrets in various data types.

**Parameters:**
- `data`: Data to process (string, dict, list, or other)
- `mask`: String to use for masking (default: "***REDACTED***")

**Returns:** Data with secrets masked

### `get_secrets_registry()`

Get the global secrets registry instance.

**Returns:** `SecretsRegistry` instance

### `SecretsRegistry` Methods

#### `add_sensitive_key(key: str)`
Add a field name to be treated as sensitive.

#### `add_secret_pattern(pattern: str)`
Add a regex pattern for detecting secrets.

#### `add_whitelist_pattern(pattern: str)`
Add a regex pattern for whitelisting false positives.

#### `disable_masking_for_logger(logger_name: str)`
Disable secret masking for a specific logger (performance optimization).

#### `enable_masking_for_logger(logger_name: str)`
Re-enable secret masking for a specific logger.

#### `is_logger_masking_disabled(logger_name: str) -> bool`
Check if secret masking is disabled for a specific logger.

#### `enable_audit_logging(audit_logger: Optional[logging.Logger] = None)`
Enable audit logging of secret detection events.

#### `disable_audit_logging()`
Disable audit logging of secret detection events.

#### `is_sensitive_key(key: str) -> bool`
Check if a field name is marked as sensitive.

#### `contains_secret(value: str) -> bool`
Check if a string contains a secret pattern.

#### `mask_secrets_in_dict(data: dict, mask: str, logger_name: str = None) -> dict`
Recursively mask secrets in a dictionary.