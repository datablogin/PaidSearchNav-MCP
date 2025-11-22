"""Secure secrets handling for logging module."""

import logging
import re
from typing import Any, Dict, List, Optional, Pattern, Set, Union, cast


class SecretsRegistry:
    """Registry for tracking sensitive field names and patterns."""

    def __init__(self):
        """Initialize the secrets registry."""
        self._sensitive_keys: Set[str] = set()
        self._secret_patterns: List[Pattern[str]] = []
        self._whitelist_patterns: List[Pattern[str]] = []
        self._disabled_loggers: Set[str] = set()
        self._audit_logger: Optional[logging.Logger] = None
        self._enable_audit_logging: bool = False
        self._max_recursion_depth: int = (
            10  # Prevent infinite recursion on deep structures
        )

        # Performance optimizations
        self._fast_patterns: List[Pattern[str]] = []  # Patterns likely to match quickly
        self._slow_patterns: List[Pattern[str]] = []  # Patterns that are more expensive
        self._pattern_cache_enabled: bool = True
        self._contains_secret_cache: Dict[
            str, bool
        ] = {}  # Simple string cache for frequently checked values
        self._max_cache_size: int = 1000

        self._setup_default_patterns()

    def _setup_default_patterns(self) -> None:
        """Set up default patterns for common secret formats."""
        # Fast patterns - specific prefixes that can be checked quickly
        fast_patterns = [
            # Google AI keys (AIza followed by 35+ chars)
            r"\bAIza[A-Za-z0-9_-]{35,}\b",
            # OpenAI keys (sk- followed by 32+ chars)
            r"\bsk-[A-Za-z0-9]{32,}\b",
            # Slack bot tokens (xoxb- followed by structured format)
            r"\bxoxb-\d{10,}-\d{12,}-[A-Za-z0-9]{24}\b",
            # Slack user tokens (xoxp- followed by structured format)
            r"\bxoxp-\d{10,}-\d{12,}-\d{12,}-[A-Za-z0-9]{32}\b",
            # GitHub personal access tokens (ghp_ followed by 36-40 chars)
            r"\bghp_[A-Za-z0-9]{36,40}\b",
            # GitHub OAuth tokens (gho_ followed by 36 chars)
            r"\bgho_[A-Za-z0-9]{36}\b",
            # GitHub app tokens (ghs_ followed by 36 chars)
            r"\bghs_[A-Za-z0-9]{36}\b",
            # SendGrid API keys
            r"\bSG\.[A-Za-z0-9_-]{22}\.[A-Za-z0-9_-]{43}\b",
            # JWT tokens (more specific pattern)
            r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b",
        ]

        # Slow patterns - more general patterns that require more computation
        slow_patterns = [
            # Base64 encoded secrets (more specific - must be properly formatted)
            r"\b[A-Za-z0-9+/]{32,}={0,2}\b",
            # Hex encoded secrets (more specific - 64+ chars to avoid UUIDs/hashes)
            r"\b[a-fA-F0-9]{64,}\b",
            # Generic secret-like patterns (more conservative)
            r"\b[A-Za-z0-9]{50,}\b",
            # URLs with credentials
            r"https?://[^:]+:[^@]+@[^\s]+",
            # Connection strings
            r"[^=]*=.*;.*password=[^;]+",
            # Common password patterns
            r'\bpassword\s*[:=]\s*[\'"][^\'\"]+[\'"]',
            r'\bpwd\s*[:=]\s*[\'"][^\'\"]+[\'"]',
            r'\bsecret\s*[:=]\s*[\'"][^\'\"]+[\'"]',
            r'\btoken\s*[:=]\s*[\'"][^\'\"]+[\'"]',
            r'\bkey\s*[:=]\s*[\'"][^\'\"]+[\'"]',
        ]

        # Compile fast patterns
        for pattern in fast_patterns:
            try:
                compiled = re.compile(pattern, re.IGNORECASE)
                self._fast_patterns.append(compiled)
                self._secret_patterns.append(compiled)
            except re.error:
                # Skip invalid patterns
                pass

        # Compile slow patterns
        for pattern in slow_patterns:
            try:
                compiled = re.compile(pattern, re.IGNORECASE)
                self._slow_patterns.append(compiled)
                self._secret_patterns.append(compiled)
            except re.error:
                # Skip invalid patterns
                pass

        # Common sensitive field names
        self._sensitive_keys.update(
            {
                "password",
                "pwd",
                "pass",
                "passwd",
                "secret",
                "token",
                "key",
                "api_key",
                "apikey",
                "access_token",
                "refresh_token",
                "auth_token",
                "webhook_url",
                "dsn",
                "connection_string",
                "smtp_password",
                "db_password",
                "redis_password",
                "private_key",
                "cert",
                "certificate",
                "authorization",
                "bearer",
                "basic_auth",
                "client_secret",
                "consumer_secret",
                "slack_webhook_url",
                "sentry_dsn",
                "google_api_key",
                "openai_api_key",
            }
        )

        # Add default whitelist patterns to prevent common false positives
        default_whitelist_patterns = [
            # UUIDs (don't mask standard UUIDs)
            r"\b[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}\b",
            # Git commit hashes (40 chars)
            r"\b[a-fA-F0-9]{40}\b",
            # Common test/example patterns
            r"\bexample[-_][a-zA-Z0-9]+",
            r"\btest[-_][a-zA-Z0-9]+",
            r"\bdemo[-_][a-zA-Z0-9]+",
            r"\bsample[-_][a-zA-Z0-9]+",
            # Unix timestamps (standalone, not part of structured tokens)
            r"(?<![-_])\b\d{10,13}(?![-_])\b",
            # Simple numeric IDs (standalone, not part of structured tokens)
            r"(?<![-_])\b[0-9]{8,15}(?![-_])\b",
        ]

        for pattern in default_whitelist_patterns:
            try:
                self._whitelist_patterns.append(re.compile(pattern, re.IGNORECASE))
            except re.error:
                # Skip invalid patterns
                pass

    def add_sensitive_key(self, key: str) -> None:
        """Add a sensitive field name to the registry.

        Args:
            key: Field name to mark as sensitive
        """
        self._sensitive_keys.add(key.lower())

    def add_secret_pattern(self, pattern: str) -> None:
        """Add a regex pattern for detecting secrets.

        Args:
            pattern: Regex pattern string
        """
        try:
            compiled_pattern = re.compile(pattern, re.IGNORECASE)
            self._secret_patterns.append(compiled_pattern)

            # Add to appropriate performance category
            # Custom patterns are conservatively added to slow patterns
            # unless they have obvious fast characteristics
            if self._is_fast_pattern(pattern):
                self._fast_patterns.append(compiled_pattern)
            else:
                self._slow_patterns.append(compiled_pattern)

        except re.error as e:
            raise ValueError(f"Invalid regex pattern: {pattern}") from e

    def _is_fast_pattern(self, pattern: str) -> bool:
        """Determine if a pattern should be classified as fast.

        Fast patterns typically have specific prefixes or are highly constrained.

        Args:
            pattern: Regex pattern string

        Returns:
            True if pattern should be classified as fast
        """
        # Patterns with specific prefixes are usually fast
        fast_indicators = [
            r"\bsk-",
            r"\bAIza",
            r"\bxoxb-",
            r"\bxoxp-",
            r"\bghp_",
            r"\bgho_",
            r"\bghs_",
            r"\bSG\.",
            r"\beyJ",
            r"\bCUST-",
            r"\bAPI-",
        ]

        for indicator in fast_indicators:
            if indicator in pattern:
                return True

        return False

    def add_whitelist_pattern(self, pattern: str) -> None:
        """Add a regex pattern for whitelisting false positives.

        Args:
            pattern: Regex pattern string for values that should NOT be masked
        """
        try:
            compiled_pattern = re.compile(pattern, re.IGNORECASE)
            self._whitelist_patterns.append(compiled_pattern)
        except re.error as e:
            raise ValueError(f"Invalid whitelist pattern: {pattern}") from e

    def disable_masking_for_logger(self, logger_name: str) -> None:
        """Disable secret masking for a specific logger (performance optimization).

        Args:
            logger_name: Name of the logger to disable masking for
        """
        self._disabled_loggers.add(logger_name)

    def enable_masking_for_logger(self, logger_name: str) -> None:
        """Re-enable secret masking for a specific logger.

        Args:
            logger_name: Name of the logger to re-enable masking for
        """
        self._disabled_loggers.discard(logger_name)

    def is_logger_masking_disabled(self, logger_name: str) -> bool:
        """Check if secret masking is disabled for a specific logger.

        Args:
            logger_name: Name of the logger to check

        Returns:
            True if masking is disabled for this logger
        """
        return logger_name in self._disabled_loggers

    def enable_audit_logging(
        self, audit_logger: Optional[logging.Logger] = None
    ) -> None:
        """Enable audit logging of secret detection events.

        Args:
            audit_logger: Optional custom logger for audit events.
                         If None, uses a default audit logger.
        """
        self._enable_audit_logging = True
        if audit_logger is not None:
            self._audit_logger = audit_logger
        else:
            self._audit_logger = logging.getLogger("paidsearchnav.security.audit")

    def disable_audit_logging(self) -> None:
        """Disable audit logging of secret detection events."""
        self._enable_audit_logging = False
        self._audit_logger = None

    def set_max_recursion_depth(self, depth: int) -> None:
        """Set maximum recursion depth for nested data structures.

        Args:
            depth: Maximum recursion depth (must be >= 1)

        Raises:
            ValueError: If depth is less than 1
        """
        if depth < 1:
            raise ValueError("Maximum recursion depth must be at least 1")
        self._max_recursion_depth = depth

    def get_max_recursion_depth(self) -> int:
        """Get the current maximum recursion depth.

        Returns:
            Current maximum recursion depth
        """
        return self._max_recursion_depth

    def enable_pattern_cache(self) -> None:
        """Enable pattern matching cache for better performance."""
        self._pattern_cache_enabled = True

    def disable_pattern_cache(self) -> None:
        """Disable pattern matching cache."""
        self._pattern_cache_enabled = False
        self._contains_secret_cache.clear()

    def clear_pattern_cache(self) -> None:
        """Clear the pattern matching cache."""
        self._contains_secret_cache.clear()

    def set_cache_size(self, size: int) -> None:
        """Set maximum cache size for pattern matching.

        Args:
            size: Maximum number of cached results
        """
        if size < 0:
            raise ValueError("Cache size must be non-negative")
        self._max_cache_size = size
        # Trim cache if it's too large
        if len(self._contains_secret_cache) > size:
            # Remove oldest entries (simple FIFO)
            items = list(self._contains_secret_cache.items())
            self._contains_secret_cache = dict(items[-size:])

    def get_cache_stats(self) -> Dict[str, int]:
        """Get cache statistics for debugging performance.

        Returns:
            Dictionary with cache statistics
        """
        return {
            "cache_size": len(self._contains_secret_cache),
            "max_cache_size": self._max_cache_size,
            "cache_enabled": self._pattern_cache_enabled,
        }

    def _audit_log_secret_detection(
        self,
        context: str,
        field_name: Optional[str] = None,
        pattern_type: Optional[str] = None,
    ) -> None:
        """Log audit event when a secret is detected and masked.

        Args:
            context: Context where the secret was detected (e.g., "log_message", "extra_field")
            field_name: Name of the field containing the secret (if applicable)
            pattern_type: Type of pattern that detected the secret (if applicable)
        """
        if not self._enable_audit_logging or not self._audit_logger:
            return

        audit_data = {
            "event": "secret_masked",
            "context": context,
            "timestamp": "auto",  # Will be added by logger
        }

        if field_name:
            audit_data["field_name"] = field_name
        if pattern_type:
            audit_data["pattern_type"] = pattern_type

        self._audit_logger.warning("Secret detected and masked", extra=audit_data)

    def is_sensitive_key(self, key: str) -> bool:
        """Check if a field name is sensitive.

        Args:
            key: Field name to check

        Returns:
            True if the key is sensitive
        """
        return key.lower() in self._sensitive_keys

    def contains_secret(self, value: str) -> bool:
        """Check if a string contains a secret pattern.

        Args:
            value: String to check

        Returns:
            True if the value contains a secret pattern
        """
        if not isinstance(value, str) or len(value) < 8:
            return False

        # Check cache first for frequently accessed values
        if self._pattern_cache_enabled and value in self._contains_secret_cache:
            return self._contains_secret_cache[value]

        # Check whitelist first - if it matches, don't treat as secret
        for pattern in self._whitelist_patterns:
            if pattern.search(value):
                result = False
                break
        else:
            # Check fast patterns first (more likely to match and faster)
            result = self._check_fast_patterns_only(value)
            if not result:
                # Only check slow patterns if fast patterns didn't match
                # For very short strings, skip expensive slow patterns unless they have secret indicators
                if len(value) < 16 and not self._has_secret_indicators(value):
                    result = False
                else:
                    result = self._check_slow_patterns_only(value)

        # Cache the result for future lookups
        if self._pattern_cache_enabled and self._max_cache_size > 0:
            # Implement simple cache size management
            if len(self._contains_secret_cache) >= self._max_cache_size:
                # Remove oldest entry (simple FIFO eviction) if cache is not empty
                if self._contains_secret_cache:
                    oldest_key = next(iter(self._contains_secret_cache))
                    del self._contains_secret_cache[oldest_key]
            self._contains_secret_cache[value] = result

        return result

    def _check_fast_patterns_only(self, value: str) -> bool:
        """Check only fast patterns for quick detection.

        Args:
            value: String to check

        Returns:
            True if any fast pattern matches
        """
        for pattern in self._fast_patterns:
            if pattern.search(value):
                return True
        return False

    def _check_slow_patterns_only(self, value: str) -> bool:
        """Check only slow patterns for comprehensive detection.

        Args:
            value: String to check

        Returns:
            True if any slow pattern matches
        """
        for pattern in self._slow_patterns:
            if pattern.search(value):
                return True
        return False

    def mask_secrets_in_dict(
        self,
        data: Dict[str, Any],
        mask: str = "***REDACTED***",
        logger_name: Optional[str] = None,
        _recursion_depth: int = 0,
    ) -> Dict[str, Any]:
        """Recursively mask secrets in a dictionary.

        Args:
            data: Dictionary to process
            mask: String to use for masking
            logger_name: Name of the logger (for performance optimization)
            _recursion_depth: Internal recursion depth tracking

        Returns:
            Dictionary with secrets masked
        """
        if not isinstance(data, dict):
            return data

        # Performance optimization: skip masking for disabled loggers
        if logger_name and self.is_logger_masking_disabled(logger_name):
            return data

        # Prevent infinite recursion on deeply nested structures
        if _recursion_depth >= self._max_recursion_depth:
            # At max depth, just mask any string values but don't recurse further
            masked_data = {}
            for key, value in data.items():
                if self.is_sensitive_key(key):
                    masked_data[key] = mask
                    self._audit_log_secret_detection("extra_field", field_name=key)
                elif isinstance(value, str):
                    original_value = value
                    masked_value = self._mask_secrets_in_string(value, mask)
                    masked_data[key] = masked_value
                    if masked_value != original_value:
                        self._audit_log_secret_detection(
                            "extra_field", field_name=key, pattern_type="pattern_match"
                        )
                else:
                    # Don't recurse further, just keep the value as-is
                    masked_data[key] = value
            return masked_data

        masked_data = {}
        for key, value in data.items():
            if self.is_sensitive_key(key):
                masked_data[key] = mask
                self._audit_log_secret_detection("extra_field", field_name=key)
            elif isinstance(value, dict):
                masked_data[key] = cast(
                    Any,
                    self.mask_secrets_in_dict(
                        value, mask, logger_name, _recursion_depth + 1
                    ),
                )
            elif isinstance(value, list):
                masked_data[key] = cast(
                    Any,
                    self._mask_secrets_in_list(
                        value, mask, logger_name, _recursion_depth + 1
                    ),
                )
            elif isinstance(value, str):
                # Always use string masking to preserve context
                original_value = value
                masked_value = self._mask_secrets_in_string(value, mask)
                masked_data[key] = masked_value
                if masked_value != original_value:
                    self._audit_log_secret_detection(
                        "extra_field", field_name=key, pattern_type="pattern_match"
                    )
            else:
                masked_data[key] = value
        return masked_data

    def _mask_secrets_in_list(
        self,
        data: List[Any],
        mask: str,
        logger_name: Optional[str] = None,
        _recursion_depth: int = 0,
    ) -> List[Any]:
        """Recursively mask secrets in a list.

        Args:
            data: List to process
            mask: String to use for masking
            logger_name: Name of the logger (for performance optimization)
            _recursion_depth: Internal recursion depth tracking

        Returns:
            List with secrets masked
        """
        # Prevent infinite recursion on deeply nested structures
        if _recursion_depth >= self._max_recursion_depth:
            # At max depth, just mask string values but don't recurse further
            masked_list = []
            for item in data:
                if isinstance(item, str):
                    original_item = item
                    masked_item = self._mask_secrets_in_string(item, mask)
                    masked_list.append(masked_item)
                    if masked_item != original_item:
                        self._audit_log_secret_detection(
                            "list_item", pattern_type="pattern_match"
                        )
                else:
                    # Don't recurse further, just keep the item as-is
                    masked_list.append(item)
            return masked_list

        masked_list = []
        for item in data:
            if isinstance(item, dict):
                masked_list.append(
                    cast(
                        Any,
                        self.mask_secrets_in_dict(
                            item, mask, logger_name, _recursion_depth + 1
                        ),
                    )
                )
            elif isinstance(item, list):
                masked_list.append(
                    cast(
                        Any,
                        self._mask_secrets_in_list(
                            item, mask, logger_name, _recursion_depth + 1
                        ),
                    )
                )
            elif isinstance(item, str):
                # Always use string masking to preserve context
                original_item = item
                masked_item = self._mask_secrets_in_string(item, mask)
                masked_list.append(masked_item)
                if masked_item != original_item:
                    self._audit_log_secret_detection(
                        "list_item", pattern_type="pattern_match"
                    )
            else:
                masked_list.append(item)
        return masked_list

    def _mask_secrets_in_string(self, text: str, mask: str) -> str:
        """Mask secrets found within a string using regex patterns.

        Args:
            text: String to process
            mask: String to use for masking

        Returns:
            String with secrets masked
        """
        # Early exit for short strings or strings with no secret-like characters
        if len(text) < 8:
            return text

        # Quick pre-check: if the string doesn't contain common secret indicators,
        # we can skip pattern matching entirely
        if not self._has_secret_indicators(text):
            return text

        masked_text = text

        # Apply fast patterns first (they're more specific and likely to match)
        for pattern in self._fast_patterns:
            masked_text = pattern.sub(mask, masked_text)

        # Apply slow patterns only if the string still looks like it might contain secrets
        # This is an optimization - if fast patterns already found and masked something,
        # we still want to check for other types of secrets
        for pattern in self._slow_patterns:
            masked_text = pattern.sub(mask, masked_text)

        return masked_text

    def _has_secret_indicators(self, text: str) -> bool:
        """Quick check for common secret indicators to avoid expensive regex matching.

        Args:
            text: String to check

        Returns:
            True if the string might contain secrets
        """
        # Quick character-based heuristics to filter out obvious non-secrets
        # This is much faster than regex for eliminating common cases

        # Check for common secret prefixes/indicators
        secret_indicators = [
            "sk-",
            "AIza",
            "xoxb-",
            "xoxp-",
            "ghp_",
            "gho_",
            "ghs_",
            "SG.",
            "eyJ",
            "password",
            "secret",
            "token",
            "key",
            "api_key",
            "://",
            "=",
            ":",
        ]

        text_lower = text.lower()
        for indicator in secret_indicators:
            if indicator.lower() in text_lower:
                return True

        # Check for long alphanumeric strings (potential secrets)
        alphanumeric_count = sum(1 for c in text if c.isalnum())
        if alphanumeric_count > 20 and len(text) > 30:
            return True

        return False


# Global secrets registry instance
_secrets_registry = SecretsRegistry()


def get_secrets_registry() -> SecretsRegistry:
    """Get the global secrets registry instance.

    Returns:
        SecretsRegistry instance
    """
    return _secrets_registry


def mask_secrets(
    data: Union[str, Dict[str, Any], List[Any]],
    mask: str = "***REDACTED***",
    logger_name: Optional[str] = None,
) -> Union[str, Dict[str, Any], List[Any]]:
    """Mask secrets in various data types.

    Args:
        data: Data to process (string, dict, or list)
        mask: String to use for masking
        logger_name: Name of the logger (for performance optimization)

    Returns:
        Data with secrets masked
    """
    registry = get_secrets_registry()

    # Performance optimization: skip masking for disabled loggers
    if logger_name and registry.is_logger_masking_disabled(logger_name):
        return data

    if isinstance(data, dict):
        return registry.mask_secrets_in_dict(data, mask, logger_name)
    elif isinstance(data, list):
        return registry._mask_secrets_in_list(data, mask, logger_name)
    elif isinstance(data, str):
        original_data = data
        masked_data = registry._mask_secrets_in_string(data, mask)
        if masked_data != original_data:
            registry._audit_log_secret_detection(
                "log_message", pattern_type="pattern_match"
            )
        return masked_data
    else:
        return data
