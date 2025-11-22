"""Custom logging handlers for alerts and external services."""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import httpx


class AlertHandler(logging.Handler):
    """Base class for alert handlers."""

    def should_alert(self, record: logging.LogRecord) -> bool:
        """Determine if this record should trigger an alert.

        Args:
            record: Log record to check

        Returns:
            True if alert should be sent
        """
        # Check if we've seen this error recently (prevent spam)
        # This is a simple implementation - could be enhanced with Redis/cache
        return record.levelno >= logging.ERROR


class SlackAlertHandler(AlertHandler):
    """Send alerts to Slack via webhook."""

    def __init__(self, webhook_url: str, channel: str | None = None):
        """Initialize Slack handler.

        Args:
            webhook_url: Slack webhook URL
            channel: Optional channel override
        """
        super().__init__()
        self.webhook_url = webhook_url
        self.channel = channel

    def emit(self, record: logging.LogRecord) -> None:
        """Send log record to Slack.

        Args:
            record: Log record to send
        """
        if not self.should_alert(record):
            return

        try:
            # Build Slack message
            color = {
                logging.WARNING: "warning",
                logging.ERROR: "danger",
                logging.CRITICAL: "danger",
            }.get(record.levelno, "info")

            attachment = {
                "color": color,
                "title": f"{record.levelname}: {record.getMessage()[:100]}",
                "text": record.getMessage(),
                "fields": [
                    {"title": "Logger", "value": record.name, "short": True},
                    {"title": "Module", "value": record.module, "short": True},
                ],
                "footer": "PaidSearchNav",
                "ts": int(record.created),
            }

            # Add context fields
            for field in ["customer_id", "analysis_id", "job_id"]:
                if hasattr(record, field):
                    attachment["fields"].append(
                        {
                            "title": field.replace("_", " ").title(),
                            "value": str(getattr(record, field)),
                            "short": True,
                        }
                    )

            # Add exception info
            if record.exc_info:
                attachment["fields"].append(
                    {
                        "title": "Exception",
                        "value": f"{record.exc_info[0].__name__}: {record.exc_info[1]}",
                        "short": False,
                    }
                )

            payload = {"attachments": [attachment]}
            if self.channel:
                payload["channel"] = self.channel

            # Send to Slack
            with httpx.Client() as client:
                response = client.post(
                    self.webhook_url,
                    json=payload,
                    timeout=5.0,
                )
                response.raise_for_status()

        except Exception as e:
            # Don't let logging errors break the application
            print(f"Failed to send Slack alert: {e}")


class EmailAlertHandler(AlertHandler):
    """Send alerts via email."""

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        smtp_username: str | None,
        smtp_password: str | None,
        from_email: str,
        to_emails: list[str],
        use_tls: bool = True,
    ):
        """Initialize email handler.

        Args:
            smtp_host: SMTP server hostname
            smtp_port: SMTP server port
            smtp_username: Optional SMTP username
            smtp_password: Optional SMTP password
            from_email: Sender email address
            to_emails: List of recipient emails
            use_tls: Whether to use TLS
        """
        super().__init__()
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_username = smtp_username
        self.smtp_password = smtp_password
        self.from_email = from_email
        self.to_emails = to_emails
        self.use_tls = use_tls

    def emit(self, record: logging.LogRecord) -> None:
        """Send log record via email.

        Args:
            record: Log record to send
        """
        if not self.should_alert(record):
            return

        try:
            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = (
                f"[PaidSearchNav] {record.levelname}: {record.getMessage()[:50]}"
            )
            msg["From"] = self.from_email
            msg["To"] = ", ".join(self.to_emails)

            # Build email body
            text_body = self._format_text_body(record)
            html_body = self._format_html_body(record)

            msg.attach(MIMEText(text_body, "plain"))
            msg.attach(MIMEText(html_body, "html"))

            # Send email
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()
                if self.smtp_username and self.smtp_password:
                    server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)

        except Exception as e:
            # Don't let logging errors break the application
            print(f"Failed to send email alert: {e}")

    def _format_text_body(self, record: logging.LogRecord) -> str:
        """Format plain text email body.

        Args:
            record: Log record

        Returns:
            Plain text body
        """
        lines = [
            f"Level: {record.levelname}",
            f"Time: {record.asctime if hasattr(record, 'asctime') else 'N/A'}",
            f"Logger: {record.name}",
            f"Module: {record.module}",
            f"Function: {record.funcName}",
            f"Line: {record.lineno}",
            "",
            "Message:",
            record.getMessage(),
        ]

        # Add context
        for field in ["customer_id", "analysis_id", "job_id"]:
            if hasattr(record, field):
                lines.insert(
                    6, f"{field.replace('_', ' ').title()}: {getattr(record, field)}"
                )

        # Add exception
        if record.exc_info:
            lines.extend(
                [
                    "",
                    "Exception:",
                    f"{record.exc_info[0].__name__}: {record.exc_info[1]}",
                ]
            )

        return "\n".join(lines)

    def _format_html_body(self, record: logging.LogRecord) -> str:
        """Format HTML email body.

        Args:
            record: Log record

        Returns:
            HTML body
        """
        level_color = {
            logging.WARNING: "#ff9800",
            logging.ERROR: "#f44336",
            logging.CRITICAL: "#d32f2f",
        }.get(record.levelno, "#2196f3")

        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif;">
            <div style="background-color: {level_color}; color: white; padding: 10px;">
                <h2>{record.levelname}</h2>
            </div>
            <div style="padding: 20px;">
                <table style="width: 100%; border-collapse: collapse;">
                    <tr><td style="font-weight: bold; padding: 5px;">Time:</td><td>{record.asctime if hasattr(record, "asctime") else "N/A"}</td></tr>
                    <tr><td style="font-weight: bold; padding: 5px;">Logger:</td><td>{record.name}</td></tr>
                    <tr><td style="font-weight: bold; padding: 5px;">Module:</td><td>{record.module}</td></tr>
                    <tr><td style="font-weight: bold; padding: 5px;">Function:</td><td>{record.funcName}</td></tr>
                    <tr><td style="font-weight: bold; padding: 5px;">Line:</td><td>{record.lineno}</td></tr>
        """

        # Add context
        for field in ["customer_id", "analysis_id", "job_id"]:
            if hasattr(record, field):
                html += f'<tr><td style="font-weight: bold; padding: 5px;">{field.replace("_", " ").title()}:</td><td>{getattr(record, field)}</td></tr>'

        html += f"""
                </table>
                <h3>Message:</h3>
                <pre style="background-color: #f5f5f5; padding: 10px; border-radius: 5px;">{record.getMessage()}</pre>
        """

        # Add exception
        if record.exc_info:
            html += f"""
                <h3>Exception:</h3>
                <pre style="background-color: #ffebee; padding: 10px; border-radius: 5px; color: #d32f2f;">{record.exc_info[0].__name__}: {record.exc_info[1]}</pre>
            """

        html += """
            </div>
        </body>
        </html>
        """

        return html


class SentryHandler(logging.Handler):
    """Send errors to Sentry for tracking."""

    def __init__(self, dsn: str, environment: str = "development"):
        """Initialize Sentry handler.

        Args:
            dsn: Sentry DSN
            environment: Environment name
        """
        super().__init__()
        try:
            import sentry_sdk

            sentry_sdk.init(
                dsn=dsn,
                environment=environment,
                traces_sample_rate=0.1,
            )
            self.sentry_sdk = sentry_sdk
            self.enabled = True
        except ImportError:
            print("Sentry SDK not installed. Sentry logging disabled.")
            self.enabled = False

    def emit(self, record: logging.LogRecord) -> None:
        """Send log record to Sentry.

        Args:
            record: Log record to send
        """
        if not self.enabled or record.levelno < logging.ERROR:
            return

        try:
            # Set context
            with self.sentry_sdk.push_scope() as scope:
                # Add log context
                scope.set_context(
                    "log_record",
                    {
                        "logger": record.name,
                        "module": record.module,
                        "function": record.funcName,
                        "line": record.lineno,
                    },
                )

                # Add custom fields
                for field in ["customer_id", "analysis_id", "job_id"]:
                    if hasattr(record, field):
                        scope.set_tag(field, getattr(record, field))

                # Capture exception or message
                if record.exc_info:
                    self.sentry_sdk.capture_exception(record.exc_info)
                else:
                    self.sentry_sdk.capture_message(
                        record.getMessage(),
                        level=record.levelname.lower(),
                    )

        except Exception as e:
            # Don't let logging errors break the application
            print(f"Failed to send to Sentry: {e}")
