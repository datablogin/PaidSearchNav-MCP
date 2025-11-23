"""Tests for webhook alert handler."""

import logging
from unittest.mock import Mock, patch

import httpx
import pytest
from httpx import Response

from paidsearchnav_mcp.alerts.handlers.webhook import (
    BatchWebhookAlertHandler,
    WebhookAlertHandler,
)


@pytest.fixture
def webhook_url():
    """Test webhook URL."""
    return "https://webhook.example.com/alerts"


@pytest.fixture
def webhook_handler(webhook_url):
    """Create a webhook handler instance."""
    return WebhookAlertHandler(webhook_url=webhook_url)


@pytest.fixture
def batch_webhook_handler(webhook_url):
    """Create a batch webhook handler instance."""
    return BatchWebhookAlertHandler(webhook_url=webhook_url, batch_size=3)


@pytest.fixture
def log_record():
    """Create a test log record."""
    record = logging.LogRecord(
        name="test.logger",
        level=logging.ERROR,
        pathname="test.py",
        lineno=10,
        msg="Test error message",
        args=(),
        exc_info=None,
    )
    record.customer_id = "1234567890"
    record.job_id = "job-123"
    record.analysis_id = "analysis-456"
    return record


class TestWebhookAlertHandler:
    """Tests for WebhookAlertHandler."""

    def test_initialization_default_values(self, webhook_url):
        """Test handler initialization with default values."""
        handler = WebhookAlertHandler(webhook_url=webhook_url)

        assert handler.webhook_url == webhook_url
        assert handler.method == "POST"
        assert handler.timeout == 30
        assert handler.retry_attempts == 3
        assert handler.retry_backoff == "exponential"
        assert handler.ssl_verify is True
        assert handler.headers["Content-Type"] == "application/json"

    def test_initialization_invalid_http_method(self, webhook_url):
        """Test handler initialization with invalid HTTP method."""
        with pytest.raises(ValueError, match="Unsupported HTTP method"):
            WebhookAlertHandler(webhook_url=webhook_url, method="GET")

        with pytest.raises(ValueError, match="Unsupported HTTP method"):
            WebhookAlertHandler(webhook_url=webhook_url, method="DELETE")

    def test_initialization_custom_values(self, webhook_url):
        """Test handler initialization with custom values."""
        custom_headers = {"X-Custom": "value"}
        custom_template = {"alert": "{{message}}"}

        handler = WebhookAlertHandler(
            webhook_url=webhook_url,
            method="PUT",
            headers=custom_headers,
            auth_type="bearer",
            auth_token="secret-token",
            timeout=60,
            retry_attempts=5,
            retry_backoff="linear",
            ssl_verify=False,
            payload_template=custom_template,
        )

        assert handler.method == "PUT"
        assert handler.timeout == 60
        assert handler.retry_attempts == 5
        assert handler.retry_backoff == "linear"
        assert handler.ssl_verify is False
        assert "X-Custom" in handler.headers
        assert handler.payload_template == custom_template

    def test_authentication_bearer(self, webhook_url):
        """Test bearer token authentication configuration."""
        handler = WebhookAlertHandler(
            webhook_url=webhook_url,
            auth_type="bearer",
            auth_token="my-bearer-token",
        )

        assert handler.headers["Authorization"] == "Bearer my-bearer-token"

    def test_authentication_api_key(self, webhook_url):
        """Test API key authentication configuration."""
        handler = WebhookAlertHandler(
            webhook_url=webhook_url,
            auth_type="api_key",
            auth_token="my-api-key",
        )

        assert handler.headers["X-API-Key"] == "my-api-key"

    def test_authentication_api_key_custom_header(self, webhook_url):
        """Test API key authentication with custom header name."""
        handler = WebhookAlertHandler(
            webhook_url=webhook_url,
            auth_type="api_key",
            auth_token="my-api-key",
            api_key_header="X-Secret-Key",
        )

        assert handler.headers["X-Secret-Key"] == "my-api-key"

    def test_authentication_basic_already_encoded(self, webhook_url):
        """Test basic authentication with already encoded credentials."""
        handler = WebhookAlertHandler(
            webhook_url=webhook_url,
            auth_type="basic",
            auth_token="dXNlcjpwYXNz",  # base64 encoded "user:pass"
        )

        assert handler.headers["Authorization"] == "Basic dXNlcjpwYXNz"

    def test_authentication_basic_raw_credentials(self, webhook_url):
        """Test basic authentication with raw credentials."""
        handler = WebhookAlertHandler(
            webhook_url=webhook_url,
            auth_type="basic",
            auth_token="user:pass",  # raw credentials
        )

        # Should be encoded to base64
        assert handler.headers["Authorization"] == "Basic dXNlcjpwYXNz"

    def test_authentication_basic_no_colon_warning(self, webhook_url, caplog):
        """Test basic authentication warns when credentials lack colon."""
        import logging

        with caplog.at_level(
            logging.WARNING, logger="paidsearchnav.alerts.handlers.webhook"
        ):
            handler = WebhookAlertHandler(
                webhook_url=webhook_url,
                auth_type="basic",
                auth_token="user@pass123",  # missing colon, invalid base64
            )

        # Should still encode but warn
        assert handler.headers["Authorization"].startswith("Basic ")
        assert "should be in 'username:password' format" in caplog.text

    def test_ssl_verification_disabled_warning(self, webhook_url, caplog):
        """Test warning when SSL verification is disabled."""
        handler = WebhookAlertHandler(webhook_url=webhook_url, ssl_verify=False)

        assert "SSL verification disabled" in caplog.text
        assert "trusted internal endpoints" in caplog.text

    def test_authentication_custom(self, webhook_url):
        """Test custom authentication configuration."""
        handler = WebhookAlertHandler(
            webhook_url=webhook_url,
            auth_type="custom",
            auth_token="custom-token",
            custom_auth_header="X-Auth-Token",
        )

        assert handler.headers["X-Auth-Token"] == "custom-token"

    def test_format_payload_default(self, webhook_handler, log_record):
        """Test default payload formatting."""
        payload = webhook_handler._format_payload(log_record)

        assert payload["alert_type"] == "error"
        assert payload["message"] == "Test error message"
        assert payload["severity"] == "ERROR"
        assert payload["timestamp"] == log_record.created
        assert payload["logger"] == "test.logger"
        assert payload["context"]["customer_id"] == "1234567890"
        assert payload["context"]["job_id"] == "job-123"
        assert payload["context"]["analysis_id"] == "analysis-456"

    def test_format_payload_with_exception(self, webhook_handler):
        """Test payload formatting with exception info."""
        try:
            raise ValueError("Test exception")
        except ValueError:
            import sys

            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test.logger",
            level=logging.ERROR,
            pathname="test.py",
            lineno=10,
            msg="Test error with exception",
            args=(),
            exc_info=exc_info,
        )

        payload = webhook_handler._format_payload(record)

        assert "exception" in payload
        assert payload["exception"]["type"] == "ValueError"
        assert payload["exception"]["message"] == "Test exception"
        assert len(payload["exception"]["traceback"]) > 0

    def test_apply_template(self, webhook_handler):
        """Test template application."""
        data = {
            "message": "Test message",
            "severity": "ERROR",
            "context": {
                "customer_id": "123",
                "job_id": "job-456",
            },
            "nested": {"deep": {"value": "deep-value"}},
        }

        template = {
            "text": "{{message}}",
            "level": "{{severity}}",
            "customer": "{{context.customer_id}}",
            "job": "{{context.job_id}}",
            "deep_value": "{{nested.deep.value}}",
            "literal": "static-value",
            "missing": "{{nonexistent.path}}",
        }

        result = webhook_handler._apply_template(data, template)

        assert result["text"] == "Test message"
        assert result["level"] == "ERROR"
        assert result["customer"] == "123"
        assert result["job"] == "job-456"
        assert result["deep_value"] == "deep-value"
        assert result["literal"] == "static-value"
        assert result["missing"] is None

    def test_apply_template_nested(self, webhook_handler):
        """Test nested template application."""
        data = {
            "alert": {
                "type": "error",
                "details": {"code": "ERR001", "message": "Something went wrong"},
            }
        }

        template = {
            "notification": {
                "alert_type": "{{alert.type}}",
                "error_details": {
                    "code": "{{alert.details.code}}",
                    "text": "{{alert.details.message}}",
                },
            }
        }

        result = webhook_handler._apply_template(data, template)

        assert result["notification"]["alert_type"] == "error"
        assert result["notification"]["error_details"]["code"] == "ERR001"
        assert result["notification"]["error_details"]["text"] == "Something went wrong"

    def test_calculate_backoff_exponential(self, webhook_handler):
        """Test exponential backoff calculation."""
        webhook_handler.retry_backoff = "exponential"

        assert webhook_handler._calculate_backoff(0) == 1.0
        assert webhook_handler._calculate_backoff(1) == 2.0
        assert webhook_handler._calculate_backoff(2) == 4.0
        assert webhook_handler._calculate_backoff(3) == 8.0
        assert webhook_handler._calculate_backoff(10) == 30.0  # Capped at 30

    def test_calculate_backoff_linear(self, webhook_handler):
        """Test linear backoff calculation."""
        webhook_handler.retry_backoff = "linear"

        assert webhook_handler._calculate_backoff(0) == 1.0
        assert webhook_handler._calculate_backoff(1) == 2.0
        assert webhook_handler._calculate_backoff(2) == 3.0
        assert webhook_handler._calculate_backoff(3) == 4.0
        assert webhook_handler._calculate_backoff(15) == 10.0  # Capped at 10

    def test_calculate_backoff_unknown(self, webhook_handler):
        """Test unknown backoff strategy defaults to 1 second."""
        webhook_handler.retry_backoff = "unknown"

        assert webhook_handler._calculate_backoff(0) == 1.0
        assert webhook_handler._calculate_backoff(5) == 1.0

    @patch.object(WebhookAlertHandler, "_send_with_retry")
    def test_emit_calls_send(self, mock_send, webhook_handler, log_record):
        """Test emit method calls send with formatted payload."""
        webhook_handler.emit(log_record)

        mock_send.assert_called_once()
        payload = mock_send.call_args[0][0]
        assert payload["message"] == "Test error message"
        assert payload["severity"] == "ERROR"

    @patch.object(WebhookAlertHandler, "_send_with_retry")
    def test_emit_handles_exceptions(self, mock_send, webhook_handler, log_record):
        """Test emit method handles exceptions gracefully."""
        mock_send.side_effect = Exception("Send failed")

        # Should not raise exception
        webhook_handler.emit(log_record)

    @patch.object(WebhookAlertHandler, "_send_with_retry")
    def test_emit_respects_should_alert(self, mock_send, webhook_handler):
        """Test emit respects should_alert decision."""
        # Create INFO level record (below ERROR threshold)
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Info message",
            args=(),
            exc_info=None,
        )

        webhook_handler.emit(record)

        # Should not send alert for INFO level
        mock_send.assert_not_called()

    @patch("time.sleep")  # Mock sleep to speed up tests
    def test_send_with_retry_success(self, mock_sleep, webhook_handler):
        """Test successful send without retries."""
        mock_response = Mock(spec=Response)
        mock_response.is_success = True
        mock_response.status_code = 200

        with patch.object(webhook_handler, "_send_request", return_value=mock_response):
            webhook_handler._send_with_retry({"test": "payload"})

        mock_sleep.assert_not_called()

    @patch("time.sleep")  # Mock sleep to speed up tests
    def test_send_with_retry_server_error(self, mock_sleep, webhook_handler):
        """Test retry on server error (5xx)."""
        mock_response = Mock(spec=Response)
        mock_response.is_success = False
        mock_response.status_code = 500

        with patch.object(webhook_handler, "_send_request", return_value=mock_response):
            webhook_handler._send_with_retry({"test": "payload"})

        # Should retry 3 times (default), so 2 sleeps between retries
        assert mock_sleep.call_count == 2

    @patch("time.sleep")  # Mock sleep to speed up tests
    def test_send_with_retry_client_error_no_retry(self, mock_sleep, webhook_handler):
        """Test no retry on client error (4xx)."""
        mock_response = Mock(spec=Response)
        mock_response.is_success = False
        mock_response.status_code = 400

        with patch.object(webhook_handler, "_send_request", return_value=mock_response):
            webhook_handler._send_with_retry({"test": "payload"})

        # Should not retry on client error
        mock_sleep.assert_not_called()

    @patch("time.sleep")  # Mock sleep to speed up tests
    def test_send_with_retry_exception(self, mock_sleep, webhook_handler):
        """Test retry on exception."""
        with patch.object(
            webhook_handler,
            "_send_request",
            side_effect=httpx.ConnectError("Connection failed"),
        ):
            webhook_handler._send_with_retry({"test": "payload"})

        # Should retry 3 times, so 2 sleeps
        assert mock_sleep.call_count == 2

    def test_send_request_json(self, webhook_handler):
        """Test send request with JSON content type."""
        webhook_handler.headers["Content-Type"] = "application/json"
        payload = {"test": "data"}

        with patch.object(webhook_handler.client, "request") as mock_request:
            webhook_handler._send_request(payload)

        mock_request.assert_called_once_with(
            method="POST",
            url=webhook_handler.webhook_url,
            headers=webhook_handler.headers,
            json=payload,
            data=None,
        )

    def test_send_request_form(self, webhook_handler):
        """Test send request with form content type."""
        webhook_handler.headers["Content-Type"] = "application/x-www-form-urlencoded"
        payload = {"test": "data"}

        with patch.object(webhook_handler.client, "request") as mock_request:
            webhook_handler._send_request(payload)

        mock_request.assert_called_once_with(
            method="POST",
            url=webhook_handler.webhook_url,
            headers=webhook_handler.headers,
            json=None,
            data=payload,
        )

    def test_send_request_other_content_type(self, webhook_handler):
        """Test send request with other content types."""
        webhook_handler.headers["Content-Type"] = "text/plain"
        payload = {"test": "data"}

        with patch.object(webhook_handler.client, "request") as mock_request:
            webhook_handler._send_request(payload)

        mock_request.assert_called_once_with(
            method="POST",
            url=webhook_handler.webhook_url,
            headers=webhook_handler.headers,
            json=None,
            data=str(payload),  # text/plain uses str() not json.dumps()
        )

    def test_cleanup_on_delete(self, webhook_url):
        """Test client cleanup on handler deletion."""
        handler = WebhookAlertHandler(webhook_url=webhook_url)
        mock_client = Mock()
        handler.client = mock_client

        # Trigger cleanup
        handler.__del__()

        mock_client.close.assert_called_once()


class TestBatchWebhookAlertHandler:
    """Tests for BatchWebhookAlertHandler."""

    def test_initialization(self, webhook_url):
        """Test batch handler initialization."""
        handler = BatchWebhookAlertHandler(webhook_url=webhook_url, batch_size=5)

        assert handler.batch_size == 5
        assert handler.alert_buffer == []

    def test_emit_adds_to_buffer(self, batch_webhook_handler, log_record):
        """Test emit adds alerts to buffer."""
        batch_webhook_handler.emit(log_record)

        assert len(batch_webhook_handler.alert_buffer) == 1
        assert batch_webhook_handler.alert_buffer[0]["message"] == "Test error message"

    @patch.object(BatchWebhookAlertHandler, "flush")
    def test_emit_flushes_when_full(
        self, mock_flush, batch_webhook_handler, log_record
    ):
        """Test emit flushes buffer when full."""
        # Fill buffer to just below batch size
        for _ in range(2):
            batch_webhook_handler.emit(log_record)

        mock_flush.assert_not_called()

        # Add one more to trigger flush
        batch_webhook_handler.emit(log_record)

        mock_flush.assert_called_once()

    def test_emit_handles_exceptions(self, batch_webhook_handler, log_record):
        """Test emit handles exceptions gracefully."""
        with patch.object(
            batch_webhook_handler,
            "_format_payload",
            side_effect=Exception("Format failed"),
        ):
            # Should not raise exception
            batch_webhook_handler.emit(log_record)

    @patch.object(BatchWebhookAlertHandler, "_send_with_retry")
    def test_flush_sends_batch(self, mock_send, batch_webhook_handler, log_record):
        """Test flush sends batch payload."""
        # Add alerts to buffer
        for i in range(3):
            record = logging.LogRecord(
                name="test.logger",
                level=logging.ERROR,
                pathname="test.py",
                lineno=10,
                msg=f"Error {i}",
                args=(),
                exc_info=None,
            )
            record.created = 1000 + i  # Different timestamps
            batch_webhook_handler.alert_buffer.append(
                batch_webhook_handler._format_payload(record)
            )

        batch_webhook_handler.flush()

        mock_send.assert_called_once()
        batch_payload = mock_send.call_args[0][0]
        assert len(batch_payload["alerts"]) == 3
        assert batch_payload["batch_size"] == 3
        assert batch_payload["timestamp"] == 1000  # First alert's timestamp

        # Buffer should be cleared
        assert len(batch_webhook_handler.alert_buffer) == 0

    @patch.object(BatchWebhookAlertHandler, "_send_with_retry")
    def test_flush_empty_buffer(self, mock_send, batch_webhook_handler):
        """Test flush with empty buffer does nothing."""
        batch_webhook_handler.flush()

        mock_send.assert_not_called()

    @patch.object(BatchWebhookAlertHandler, "_send_with_retry")
    def test_flush_handles_exceptions(
        self, mock_send, batch_webhook_handler, log_record
    ):
        """Test flush handles send exceptions gracefully."""
        mock_send.side_effect = Exception("Send failed")

        # Add alert to buffer
        batch_webhook_handler.emit(log_record)
        buffer_size = len(batch_webhook_handler.alert_buffer)

        # Flush should not raise exception
        batch_webhook_handler.flush()

        # Buffer should still contain alerts after failed send
        assert len(batch_webhook_handler.alert_buffer) == buffer_size

    @patch.object(BatchWebhookAlertHandler, "flush")
    def test_close_flushes_buffer(self, mock_flush, batch_webhook_handler):
        """Test close method flushes remaining alerts."""
        batch_webhook_handler.close()

        mock_flush.assert_called_once()


@pytest.mark.integration
class TestWebhookAlertHandlerIntegration:
    """Integration tests for webhook handler with real HTTP calls."""

    @pytest.mark.asyncio
    async def test_webhook_handler_with_httpbin(self):
        """Test webhook handler with httpbin.org echo service."""
        webhook_url = "https://httpbin.org/post"

        handler = WebhookAlertHandler(
            webhook_url=webhook_url,
            auth_type="bearer",
            auth_token="test-token",
            retry_attempts=1,
        )

        record = logging.LogRecord(
            name="test.logger",
            level=logging.ERROR,
            pathname="test.py",
            lineno=10,
            msg="Test integration message",
            args=(),
            exc_info=None,
        )

        # Emit should succeed without exceptions
        handler.emit(record)

        # Cleanup
        handler.client.close()
