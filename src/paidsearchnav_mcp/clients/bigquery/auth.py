"""BigQuery authentication and client management."""

import json
import logging

logger = logging.getLogger(__name__)


class BigQueryAuthenticator:
    """Handles BigQuery authentication using multiple methods."""

    def __init__(self, config):
        """Initialize authenticator with BigQuery config."""
        self.config = config
        self._client = None

    async def get_client(self):
        """Get authenticated BigQuery client with caching."""
        if self._client is not None:
            return self._client

        try:
            import google.auth
            from google.cloud import bigquery
            from google.oauth2 import service_account

            if self.config.service_account_path:
                logger.info("Authenticating with service account file")
                credentials = service_account.Credentials.from_service_account_file(
                    self.config.service_account_path
                )
                self._client = bigquery.Client(
                    project=self.config.project_id,
                    credentials=credentials,
                    location=self.config.location,
                )

            elif self.config.service_account_json:
                logger.info("Authenticating with service account JSON")
                service_account_info = json.loads(
                    self.config.service_account_json.get_secret_value()
                )
                credentials = service_account.Credentials.from_service_account_info(
                    service_account_info
                )
                self._client = bigquery.Client(
                    project=self.config.project_id,
                    credentials=credentials,
                    location=self.config.location,
                )

            else:
                logger.info("Using default Google Cloud credentials")
                credentials, project = google.auth.default()
                self._client = bigquery.Client(
                    project=self.config.project_id or project,
                    credentials=credentials,
                    location=self.config.location,
                )

            logger.info(
                f"BigQuery client initialized for project: {self._client.project}"
            )
            return self._client

        except ImportError as e:
            logger.error(f"Google Cloud BigQuery library not installed: {e}")
            raise ImportError(
                "Google Cloud BigQuery library is required. "
                "Install with: pip install google-cloud-bigquery"
            )
        except FileNotFoundError as e:
            logger.error(f"Service account file not found: {e}")
            raise ValueError(
                f"Service account file not found at {self.config.service_account_path}. "
                "Please check the file path and ensure the file exists."
            )
        except json.JSONDecodeError as e:
            logger.error(f"Invalid service account JSON: {e}")
            raise ValueError(
                "Invalid service account JSON format. Please check the JSON content."
            )
        except ValueError as e:
            if "could not determine" in str(e).lower():
                logger.error(f"BigQuery project ID could not be determined: {e}")
                raise ValueError(
                    "Project ID is required. Set project_id in BigQuery configuration "
                    "or ensure default credentials have a valid project."
                )
            raise
        except Exception as e:
            error_msg = str(e).lower()
            if "permission denied" in error_msg or "forbidden" in error_msg:
                logger.error(f"BigQuery permission denied: {e}")
                raise PermissionError(
                    "Insufficient permissions for BigQuery access. "
                    "Ensure the service account has BigQuery User and Data Editor roles."
                )
            elif "quota exceeded" in error_msg:
                logger.error(f"BigQuery quota exceeded: {e}")
                raise RuntimeError(
                    "BigQuery quota exceeded. Please check your quota limits and usage."
                )
            elif "authentication" in error_msg or "credential" in error_msg:
                logger.error(f"BigQuery authentication failed: {e}")
                raise ValueError(
                    "BigQuery authentication failed. Please check your credentials "
                    "and ensure they are valid and properly configured."
                )
            else:
                logger.error(f"Unexpected BigQuery error: {e}")
                raise RuntimeError(f"Failed to initialize BigQuery client: {e}")

    def invalidate_cache(self):
        """Invalidate cached client (useful for testing or credential rotation)."""
        self._client = None
        logger.info("BigQuery client cache invalidated")
