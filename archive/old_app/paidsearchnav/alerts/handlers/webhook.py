"""Generic webhook alert handler for sending alerts to any HTTP endpoint."""

import base64
import json
import logging
import time
import traceback
from typing import Any, Dict, List, Optional

import httpx
from httpx import Response

from paidsearchnav.logging.handlers import AlertHandler

logger = logging.getLogger(__name__)

# Supported HTTP methods for webhook requests
SUPPORTED_HTTP_METHODS = {"POST", "PUT", "PATCH"}


class WebhookAlertHandler(AlertHandler):
    """Send alerts to a configurable webhook endpoint.

    This handler supports various authentication methods, customizable payloads,
    retry logic, and flexible configuration options for integrating with any
    HTTP-based alerting system.
    """

    def __init__(
        self,
        webhook_url: str,
        method: str = "POST",
        headers: Optional[Dict[str, str]] = None,
        auth_type: Optional[str] = None,
        auth_token: Optional[str] = None,
        timeout: int = 30,
        retry_attempts: int = 3,
        retry_backoff: str = "exponential",
        ssl_verify: bool = True,
        payload_template: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        """Initialize the webhook alert handler.

        Args:
            webhook_url: The URL to send alerts to
            method: HTTP method to use (POST, PUT, PATCH)
            headers: Additional headers to include in requests
            auth_type: Authentication type (bearer, basic, api_key, custom)
            auth_token: Authentication token/credentials
            timeout: Request timeout in seconds
            retry_attempts: Number of retry attempts for failed requests
            retry_backoff: Backoff strategy (exponential, linear)
            ssl_verify: Whether to verify SSL certificates
            payload_template: Custom payload template for formatting alerts
            **kwargs: Additional configuration options
        """
        super().__init__()
        self.webhook_url = webhook_url

        # Validate HTTP method
        self.method = method.upper()
        if self.method not in SUPPORTED_HTTP_METHODS:
            raise ValueError(
                f"Unsupported HTTP method: {method}. "
                f"Supported methods are: {', '.join(SUPPORTED_HTTP_METHODS)}"
            )

        self.headers = headers or {}
        self.auth_type = auth_type
        self.auth_token = auth_token
        self.timeout = timeout
        self.retry_attempts = retry_attempts
        self.retry_backoff = retry_backoff
        self.ssl_verify = ssl_verify
        self.payload_template = payload_template
        self.config = kwargs

        # Add default content type if not specified
        if "Content-Type" not in self.headers:
            self.headers["Content-Type"] = "application/json"

        # Configure authentication headers
        self._configure_authentication()

        # Log warning if SSL verification is disabled
        if not ssl_verify:
            logger.warning(
                f"SSL verification disabled for webhook URL: {webhook_url}. "
                "This should only be used for trusted internal endpoints."
            )

        # Initialize HTTP client
        self.client = httpx.Client(verify=ssl_verify, timeout=timeout)

    def _configure_authentication(self) -> None:
        """Configure authentication headers based on auth type."""
        if not self.auth_type or not self.auth_token:
            return

        if self.auth_type == "bearer":
            self.headers["Authorization"] = f"Bearer {self.auth_token}"
        elif self.auth_type == "api_key":
            # API key can be in header or query param, defaulting to header
            header_name = self.config.get("api_key_header", "X-API-Key")
            self.headers[header_name] = self.auth_token
        elif self.auth_type == "basic":
            # Handle basic auth - validate and encode if necessary
            if self.auth_token:
                # Check if token is already base64 encoded
                try:
                    # Try to decode to see if it's valid base64
                    decoded = base64.b64decode(self.auth_token, validate=True)
                    # Check if decoded value contains colon (username:password format)
                    if b":" in decoded:
                        # Already properly encoded
                        self.headers["Authorization"] = f"Basic {self.auth_token}"
                    else:
                        # Not in username:password format, treat as raw credentials
                        encoded = base64.b64encode(self.auth_token.encode()).decode()
                        self.headers["Authorization"] = f"Basic {encoded}"
                except Exception:
                    # Not valid base64, assume it's raw username:password
                    if ":" not in self.auth_token:
                        logger.warning(
                            "Basic auth token should be in 'username:password' format"
                        )
                    encoded = base64.b64encode(self.auth_token.encode()).decode()
                    self.headers["Authorization"] = f"Basic {encoded}"
        elif self.auth_type == "custom":
            # Custom auth allows arbitrary header configuration
            custom_header = self.config.get("custom_auth_header", "Authorization")
            self.headers[custom_header] = self.auth_token

    def emit(self, record: logging.LogRecord) -> None:
        """Send alert to webhook endpoint.

        Args:
            record: The log record to send
        """
        try:
            if not self.should_alert(record):
                return

            # Format the payload
            payload = self._format_payload(record)

            # Send with retry logic
            self._send_with_retry(payload)

        except Exception as e:
            # Log error but don't raise to prevent breaking the application
            logger.error(f"Failed to send webhook alert: {e}")

    def _format_payload(self, record: logging.LogRecord) -> Dict[str, Any]:
        """Format the alert payload based on template or default format.

        Args:
            record: The log record to format

        Returns:
            Formatted payload dictionary
        """
        # Extract context fields
        context = {}
        for field in ["customer_id", "job_id", "analysis_id"]:
            if hasattr(record, field):
                context[field] = getattr(record, field)

        # Build default payload
        default_payload = {
            "alert_type": "error" if record.levelno >= logging.ERROR else "warning",
            "message": self.format(record),
            "severity": record.levelname,
            "timestamp": record.created,
            "logger": record.name,
            "context": context,
        }

        # Add exception info if available
        if record.exc_info and record.exc_info[0]:
            default_payload["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": traceback.format_exception(*record.exc_info),
            }

        # Apply custom template if provided
        if self.payload_template:
            payload = self._apply_template(default_payload, self.payload_template)
        else:
            payload = default_payload

        return payload

    def _apply_template(
        self, data: Dict[str, Any], template: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Apply a template to format the payload.

        Args:
            data: The source data
            template: The template to apply

        Returns:
            Formatted payload based on template
        """
        result = {}

        for key, value in template.items():
            if (
                isinstance(value, str)
                and value.startswith("{{")
                and value.endswith("}}")
            ):
                # Extract path from template variable
                path = value[2:-2].strip()
                result[key] = self._get_nested_value(data, path)
            elif isinstance(value, dict):
                # Recursively apply template for nested structures
                result[key] = self._apply_template(data, value)
            else:
                # Use literal value
                result[key] = value

        return result

    def _get_nested_value(self, data: Dict[str, Any], path: str) -> Any:
        """Get a value from nested dictionary using dot notation.

        Args:
            data: The data dictionary
            path: Dot-notation path (e.g., "context.customer_id")

        Returns:
            The value at the path or None if not found
        """
        keys = path.split(".")
        value = data

        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return None

        return value

    def _send_with_retry(self, payload: Dict[str, Any]) -> None:
        """Send payload with retry logic.

        Args:
            payload: The payload to send
        """
        last_error = None

        for attempt in range(self.retry_attempts):
            try:
                response = self._send_request(payload)

                # Check if request was successful
                if response.is_success:
                    logger.debug(
                        f"Webhook alert sent successfully to {self.webhook_url}"
                    )
                    return

                # Log non-success status codes
                logger.warning(
                    f"Webhook returned non-success status: {response.status_code}"
                )

                # Don't retry on client errors (4xx)
                if 400 <= response.status_code < 500:
                    return

            except Exception as e:
                last_error = e
                logger.warning(f"Webhook request attempt {attempt + 1} failed: {e}")

            # Calculate backoff delay
            if attempt < self.retry_attempts - 1:
                delay = self._calculate_backoff(attempt)
                time.sleep(delay)

        # All retries failed
        if last_error:
            logger.error(f"All webhook retry attempts failed: {last_error}")

    def _send_request(self, payload: Dict[str, Any]) -> Response:
        """Send the actual HTTP request.

        Args:
            payload: The payload to send

        Returns:
            The HTTP response
        """
        # Prepare request data based on content type
        content_type = self.headers.get("Content-Type", "application/json")

        data: Optional[Any] = None
        json_data: Optional[Dict[str, Any]] = None

        if "json" in content_type:
            json_data = payload
        elif "form" in content_type:
            # Convert dict to form-encoded data
            data = payload
        elif "xml" in content_type.lower():
            # For XML, you would typically use a proper XML serializer
            # For now, we'll raise an error as XML serialization is complex
            raise NotImplementedError(
                "XML content type is not yet supported. "
                "Please use JSON or form-encoded data."
            )
        elif "text" in content_type:
            # For text content types, convert to string representation
            data = str(payload) if not isinstance(payload, str) else payload
        else:
            # For unknown content types, default to JSON string
            logger.warning(
                f"Unknown content type '{content_type}', defaulting to JSON serialization"
            )
            data = json.dumps(payload)

        # Send request
        response = self.client.request(
            method=self.method,
            url=self.webhook_url,
            headers=self.headers,
            json=json_data,
            data=data,
        )

        return response

    def _calculate_backoff(self, attempt: int) -> float:
        """Calculate backoff delay based on strategy.

        Args:
            attempt: The attempt number (0-based)

        Returns:
            Delay in seconds
        """
        if self.retry_backoff == "exponential":
            # Exponential backoff: 1s, 2s, 4s, 8s...
            return min(2**attempt, 30)  # Cap at 30 seconds
        elif self.retry_backoff == "linear":
            # Linear backoff: 1s, 2s, 3s, 4s...
            return min(attempt + 1, 10)  # Cap at 10 seconds
        else:
            # Default to 1 second delay
            return 1.0

    def __del__(self):
        """Cleanup HTTP client on deletion."""
        if hasattr(self, "client"):
            self.client.close()


class BatchWebhookAlertHandler(WebhookAlertHandler):
    """Webhook handler that supports batching multiple alerts.

    This is useful for reducing the number of HTTP requests when
    multiple alerts are generated in quick succession.
    """

    def __init__(self, *args, batch_size: int = 10, **kwargs):
        """Initialize batch webhook handler.

        Args:
            *args: Arguments for parent class
            batch_size: Maximum number of alerts to batch together
            **kwargs: Additional arguments for parent class
        """
        super().__init__(*args, **kwargs)
        self.batch_size = batch_size
        self.alert_buffer: List[Dict[str, Any]] = []

    def emit(self, record: logging.LogRecord) -> None:
        """Add alert to buffer for batch sending.

        Args:
            record: The log record to send
        """
        try:
            if not self.should_alert(record):
                return

            # Format and add to buffer
            payload = self._format_payload(record)
            self.alert_buffer.append(payload)

            # Send batch if buffer is full
            if len(self.alert_buffer) >= self.batch_size:
                self.flush()

        except Exception as e:
            logger.error(f"Failed to buffer webhook alert: {e}")

    def flush(self) -> None:
        """Send all buffered alerts as a batch."""
        if not self.alert_buffer:
            return

        try:
            # Create batch payload with a copy of alerts
            batch_payload = {
                "alerts": self.alert_buffer.copy(),
                "batch_size": len(self.alert_buffer),
                "timestamp": self.alert_buffer[0]["timestamp"],
            }

            # Send batch
            self._send_with_retry(batch_payload)

            # Clear buffer after successful send
            self.alert_buffer.clear()

        except Exception as e:
            logger.error(f"Failed to send webhook batch: {e}")
            # Keep alerts in buffer for next attempt

    def close(self) -> None:
        """Flush any remaining alerts before closing."""
        self.flush()
        super().close()
