"""Shared fixtures for API tests."""

import asyncio
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest
import pytest_asyncio
import respx
from httpx import AsyncClient
from jose import jwt
from pydantic import SecretStr

from paidsearchnav.api.dependencies import get_repository, get_settings
from paidsearchnav.api.main import app
from paidsearchnav.core.config import Settings
from paidsearchnav.storage.api_repository import APIRepository

# Test constants to reduce duplication and ensure consistency
TEST_CUSTOMER_ID = "1234567890"
TEST_USER_ID = "test-user-123"
TEST_AUDIT_ID = "test-audit-123"
TEST_SCHEDULE_ID = "test-schedule-123"
TEST_REPORT_ID = "report-123"
DIFFERENT_CUSTOMER_ID = "different-customer-456"
TEST_EMAIL = "test@example.com"


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
def reset_sse_starlette_state():
    """Reset sse-starlette state to prevent event loop binding issues."""
    # Clear any existing AppStatus to prevent event loop binding conflicts
    try:
        from sse_starlette.sse import AppStatus

        # Reset the AppStatus event if it exists (None allows new event loop binding)
        if hasattr(AppStatus, "should_exit_event"):
            AppStatus.should_exit_event = None
    except ImportError:
        pass


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Reset slowapi rate limiter storage between tests to prevent 429 errors."""
    # Clear the rate limiter's storage to prevent test interference
    # Note: Uses _storage (private API) because slowapi doesn't expose a public reset API
    try:
        from paidsearchnav.api.main import app
        from paidsearchnav.api.v1.audits import limiter as audits_limiter
        from paidsearchnav.api.v1.reports import limiter as reports_limiter

        # Clear global app limiter
        if hasattr(app.state, "limiter"):
            app_limiter = app.state.limiter
            storage = getattr(app_limiter, "_storage", None)
            if storage and hasattr(storage, "reset"):
                storage.reset()

        # Clear individual router limiters - these are separate Limiter instances
        for limiter in [reports_limiter, audits_limiter]:
            storage = getattr(limiter, "_storage", None)
            if storage and hasattr(storage, "reset"):
                storage.reset()

    except (ImportError, AttributeError, TypeError):
        pass


@pytest.fixture
def base_datetime() -> datetime:
    """Standard datetime for consistent test data.

    Returns a timezone-aware datetime in UTC for proper handling
    of timestamps in tests, especially for JWT expiration times.
    """
    from datetime import timezone

    return datetime.now(timezone.utc)


@pytest.fixture
def mock_settings() -> Settings:
    """Create mock settings for testing."""
    from paidsearchnav.core.config import GoogleAdsConfig

    settings = Settings(
        environment="development",  # type: ignore[arg-type]
        database_url="sqlite+aiosqlite:///:memory:",
        jwt_secret_key=SecretStr("test-secret-key-for-jwt-signing"),
        google_oauth_client_id="test-client-id",
        google_oauth_client_secret=SecretStr("test-client-secret"),
        api_cors_origins=["http://localhost:3000"],
        google_ads=GoogleAdsConfig(
            developer_token=SecretStr("test-developer-token"),
            client_id="test-client-id",
            client_secret=SecretStr("test-client-secret"),
            refresh_token=SecretStr("test-refresh-token"),
            login_customer_id="1234567890",
            api_version="v18",
        ),
    )
    return settings


@pytest.fixture
def mock_repository(mock_settings: Settings, base_datetime: datetime) -> APIRepository:
    """Create a mock repository for testing."""
    repo = AsyncMock()

    # Configure mock methods - return async values
    repo.check_connection.return_value = True

    # Mock user access - allow access to test customers but deny access to different-customer-456
    def mock_user_access(user_id: str, customer_id: str) -> bool:
        """
        Mock user access control for testing.

        Allows access to:
        - TEST_CUSTOMER_ID (1234567890): Primary test customer
        - test-customer-123: Legacy test customer ID for backward compatibility

        Denies access to:
        - DIFFERENT_CUSTOMER_ID (different-customer-456): Used for permission testing
        """
        return (
            customer_id in [TEST_CUSTOMER_ID, "test-customer-123"]
            and customer_id != DIFFERENT_CUSTOMER_ID
        )

    repo.user_has_customer_access.side_effect = mock_user_access
    repo.get_customer.return_value = {
        "id": TEST_CUSTOMER_ID,
        "name": "Test Customer",
        "email": TEST_EMAIL,
        "created_at": base_datetime,
        "updated_at": base_datetime,
        "settings": {},
        "is_active": True,
    }

    # Default get_audit behavior - use return_value so unit tests can override
    repo.get_audit.return_value = {
        "id": TEST_AUDIT_ID,
        "customer_id": TEST_CUSTOMER_ID,
        "name": "Test Audit",
        "status": "completed",
        "progress": 100,
        "created_at": base_datetime,
        "started_at": base_datetime,
        "completed_at": base_datetime,
        "analyzers": ["keyword_match", "search_terms"],
    }

    def get_audit_side_effect(audit_id):
        # Handle dynamic audit IDs for concurrent operations
        AUDIT_ID_PREFIX = "audit-"
        if audit_id.startswith(AUDIT_ID_PREFIX):
            name_suffix = audit_id.split("-")[-1]
            name = f"Concurrent Audit {name_suffix}"
        else:
            name = "Test Audit"

        return {
            "id": audit_id,
            "customer_id": TEST_CUSTOMER_ID,
            "name": name,
            "status": "completed",
            "progress": 100,
            "created_at": base_datetime,
            "started_at": base_datetime,
            "completed_at": base_datetime,
            "analyzers": ["keyword_match", "search_terms"],
        }

    # Store the side_effect function for integration tests to use
    repo._get_audit_side_effect = get_audit_side_effect

    # Support dynamic audit ID creation for concurrent tests
    def create_audit_side_effect(*args, **kwargs):
        # APIRepository.create_audit(self, customer_id, name, analyzers, config, user_id)
        AUDIT_ID_PREFIX = "audit-"
        CONCURRENT_AUDIT_KEYWORD = "Concurrent"
        name = kwargs.get("name", args[2] if len(args) > 2 else "Test Audit")
        if CONCURRENT_AUDIT_KEYWORD in name:
            audit_id = f"{AUDIT_ID_PREFIX}{name.split()[-1]}"
            return audit_id
        return TEST_AUDIT_ID

    repo.create_audit.side_effect = create_audit_side_effect
    repo.list_audits.return_value = ([], 0)
    repo.cancel_audit.return_value = True
    repo.create_schedule.return_value = TEST_SCHEDULE_ID
    repo.get_schedule.return_value = {
        "id": TEST_SCHEDULE_ID,
        "customer_id": TEST_CUSTOMER_ID,
        "name": "Test Schedule",
        "cron_expression": "0 0 1 * *",
        "analyzers": ["keyword_match", "search_terms"],
        "config": {"date_range": 90},
        "enabled": True,
        "created_at": base_datetime,
        "last_run": None,
        "next_run": None,
    }
    repo.list_schedules.return_value = (
        [
            {
                "id": "schedule-0",
                "customer_id": TEST_CUSTOMER_ID,
                "name": "Test Schedule 0",
                "cron_expression": "0 0 1 * *",
                "analyzers": ["keyword_match", "search_terms"],
                "config": {"date_range": 90},
                "enabled": True,
                "created_at": base_datetime,
                "last_run": None,
                "next_run": None,
            }
        ],
        1,
    )
    repo.update_schedule.return_value = True
    repo.delete_schedule.return_value = True
    repo.get_customers_for_user.return_value = []
    repo.count_customers_for_user.return_value = 0

    # Mock methods for reports and results endpoints
    repo.get_audit_results.return_value = {
        "audit_id": TEST_AUDIT_ID,
        "status": "completed",
        "created_at": base_datetime,
        "analyzers": [
            {
                "analyzer_name": "keyword_match",
                "status": "completed",
                "started_at": base_datetime,
                "completed_at": base_datetime,
                "findings": [
                    {
                        "type": "match_type_optimization",
                        "severity": "high",
                        "keyword": "test keyword",
                    }
                ],
                "recommendations": [
                    {
                        "action": "change_match_type",
                        "priority": "high",
                        "description": "Change match type",
                    }
                ],
                "metrics": {"total_findings": 5, "recommendations": 3},
            },
            {
                "analyzer_name": "search_terms",
                "status": "completed",
                "started_at": base_datetime,
                "completed_at": base_datetime,
                "findings": [
                    {
                        "type": "irrelevant_query",
                        "severity": "medium",
                        "query": "test query",
                    }
                ],
                "recommendations": [
                    {
                        "action": "add_negative",
                        "priority": "medium",
                        "description": "Add negative keyword",
                    }
                ],
                "metrics": {"total_findings": 10, "recommendations": 8},
            },
        ],
        "summary": {"total_findings": 15, "high_priority": 3},
    }

    repo.get_analyzer_result.return_value = {
        "analyzer_name": "keyword_match",
        "status": "completed",
        "started_at": base_datetime,
        "completed_at": base_datetime,
        "findings": [
            {
                "type": "match_type_optimization",
                "severity": "high",
                "keyword": "test keyword",
            }
        ],
        "recommendations": [
            {
                "action": "change_match_type",
                "priority": "high",
                "description": "Change match type",
            }
        ],
        "metrics": {"total_findings": 5, "recommendations": 3},
        "error": None,
    }

    # Additional methods can be added as they are implemented in APIRepository

    return repo


def clear_token_blacklist():
    """Helper to clear token blacklist state for test isolation."""
    try:
        from paidsearchnav.api.token_blacklist import get_token_blacklist

        blacklist = get_token_blacklist()
        blacklist._blacklisted_tokens.clear()
        blacklist._token_expiry.clear()
    except (ImportError, AttributeError):
        # Handle case where blacklist structure changes or is not available
        pass


def clear_lockout_manager():
    """Helper to clear lockout manager state for test isolation."""
    try:
        from paidsearchnav.api.auth_security import get_lockout_manager

        lockout_manager = get_lockout_manager()
        # Clear internal state using private attributes
        with lockout_manager._lock:
            lockout_manager._failed_attempts.clear()
            lockout_manager._locked_accounts.clear()
    except (ImportError, AttributeError):
        # Handle case where lockout manager structure changes or is not available
        pass


@pytest_asyncio.fixture
async def async_client(
    mock_settings: Settings, mock_repository: APIRepository
) -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client."""
    # Clear token blacklist and lockout manager to prevent state pollution between tests
    clear_token_blacklist()
    clear_lockout_manager()

    # Initialize versioning system for tests
    from paidsearchnav.api.version_config import initialize_api_versions
    from paidsearchnav.api.version_transformers import initialize_transformers
    from paidsearchnav.api.versioning import version_registry

    # Clear existing versions first
    version_registry._versions.clear()
    version_registry._current_version = None
    version_registry._minimum_version = None

    # Initialize versions
    initialize_api_versions()
    initialize_transformers()

    # Override dependencies
    app.dependency_overrides[get_settings] = lambda: mock_settings
    app.dependency_overrides[get_repository] = lambda: mock_repository

    async with AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client

    # Clear overrides
    app.dependency_overrides.clear()

    # Clear token blacklist and lockout manager after test as well
    clear_token_blacklist()
    clear_lockout_manager()


@pytest.fixture
def auth_headers(mock_settings: Settings, base_datetime: datetime) -> dict[str, str]:
    """Create authentication headers with a valid JWT token."""
    # Create a test JWT token
    payload = {
        "sub": TEST_USER_ID,
        "customer_id": TEST_CUSTOMER_ID,
        "email": TEST_EMAIL,
        "exp": base_datetime + timedelta(hours=1),
        "iat": base_datetime,
    }

    token = jwt.encode(
        payload, mock_settings.jwt_secret_key.get_secret_value(), algorithm="HS256"
    )

    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def expired_auth_headers(
    mock_settings: Settings, base_datetime: datetime
) -> dict[str, str]:
    """Create authentication headers with an expired JWT token."""
    payload = {
        "sub": TEST_USER_ID,
        "customer_id": TEST_CUSTOMER_ID,
        "email": TEST_EMAIL,
        "exp": base_datetime - timedelta(hours=1),  # Expired
        "iat": base_datetime - timedelta(hours=2),
    }

    token = jwt.encode(
        payload, mock_settings.jwt_secret_key.get_secret_value(), algorithm="HS256"
    )

    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def api_key_headers() -> dict[str, str]:
    """Create API key authentication headers."""
    return {"X-API-Key": "test-api-key-123"}


@pytest.fixture
def mock_audit_data(base_datetime: datetime) -> dict[str, Any]:
    """Create mock audit data for testing."""
    return {
        "id": TEST_AUDIT_ID,
        "customer_id": TEST_CUSTOMER_ID,
        "name": "Test Audit",
        "status": "running",
        "progress": 50,
        "created_at": base_datetime,
        "started_at": base_datetime,
        "completed_at": None,
        "analyzers": ["keyword_match", "search_terms", "negative_conflicts"],
        "results_summary": {
            "total_recommendations": 0,
            "critical_issues": 0,
            "potential_savings": 0.0,
        },
        "error": None,
    }


@pytest.fixture
def mock_schedule_data(base_datetime: datetime) -> dict[str, Any]:
    """Create mock schedule data for testing."""
    return {
        "id": TEST_SCHEDULE_ID,
        "customer_id": TEST_CUSTOMER_ID,
        "name": "Test Schedule",
        "cron_expression": "0 0 1 * *",  # Monthly
        "analyzers": ["keyword_match", "search_terms"],
        "config": {"date_range": 90},
        "enabled": True,
        "created_at": base_datetime,
        "last_run": None,
        "next_run": base_datetime + timedelta(days=30),
    }


@pytest.fixture
def mock_analyzer_result(base_datetime: datetime) -> dict[str, Any]:
    """Create mock analyzer result data."""
    return {
        "analyzer_name": "keyword_match",
        "status": "completed",
        "started_at": base_datetime,
        "completed_at": base_datetime,
        "findings": [
            {
                "type": "broad_match_overuse",
                "severity": "high",
                "keyword": "shoes",
                "current_match_type": "broad",
                "recommended_match_type": "phrase",
                "estimated_savings": 250.50,
            }
        ],
        "recommendations": [
            {
                "action": "change_match_type",
                "priority": "high",
                "description": "Change 'shoes' from broad to phrase match",
                "impact": "Reduce irrelevant traffic by 30%",
            }
        ],
        "metrics": {
            "total_keywords_analyzed": 1543,
            "issues_found": 234,
            "potential_savings": 5670.25,
        },
        "error": None,
    }


# OAuth2 Mock Fixtures
@pytest.fixture
def oauth2_token_response():
    """Mock OAuth2 token response data."""
    return {
        "access_token": "mock_access_token_12345",
        "refresh_token": "mock_refresh_token_67890",
        "expires_in": 3600,
        "token_type": "Bearer",
        "scope": "https://www.googleapis.com/auth/adwords",
    }


@pytest.fixture
def oauth2_user_response():
    """Mock OAuth2 user info response data."""
    return {
        "id": "test-user-oauth-123",
        "email": "oauth-test@example.com",
        "name": "OAuth Test User",
        "given_name": "OAuth",
        "family_name": "User",
        "picture": "https://example.com/avatar.jpg",
        "verified_email": True,
    }


@pytest.fixture
def oauth2_error_response():
    """Mock OAuth2 error response data."""
    return {
        "error": "invalid_grant",
        "error_description": "Invalid authorization code",
    }


@pytest.fixture
def oauth2_respx_mock():
    """Create a respx mock for OAuth2 endpoints with default success responses."""
    with respx.mock(assert_all_called=False) as respx_mock:
        # Mock Google OAuth2 token endpoint
        respx_mock.post("https://oauth2.googleapis.com/token").mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "mock_access_token_12345",
                    "refresh_token": "mock_refresh_token_67890",
                    "expires_in": 3600,
                    "token_type": "Bearer",
                    "scope": "https://www.googleapis.com/auth/adwords",
                },
            )
        )

        # Mock Google OAuth2 userinfo endpoint
        respx_mock.get("https://www.googleapis.com/oauth2/v1/userinfo").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "test-user-oauth-123",
                    "email": "oauth-test@example.com",
                    "name": "OAuth Test User",
                    "given_name": "OAuth",
                    "family_name": "User",
                    "picture": "https://example.com/avatar.jpg",
                    "verified_email": True,
                },
            )
        )

        yield respx_mock


@pytest.fixture
def oauth2_respx_mock_failure():
    """Create a respx mock for OAuth2 endpoints with failure responses."""
    with respx.mock(assert_all_called=False) as respx_mock:
        # Mock failed token exchange
        respx_mock.post("https://oauth2.googleapis.com/token").mock(
            return_value=httpx.Response(
                400,
                json={
                    "error": "invalid_grant",
                    "error_description": "Invalid authorization code",
                },
            )
        )

        yield respx_mock


@pytest.fixture
def oauth2_respx_mock_custom():
    """Create a customizable respx mock for OAuth2 endpoints with proper context management."""

    def _create_mock(
        token_response=None,
        user_response=None,
        token_status_code=200,
        user_status_code=200,
    ):
        # Default responses
        default_token_response = {
            "access_token": "mock_access_token_12345",
            "refresh_token": "mock_refresh_token_67890",
            "expires_in": 3600,
            "token_type": "Bearer",
            "scope": "https://www.googleapis.com/auth/adwords",
        }

        default_user_response = {
            "id": "test-user-oauth-123",
            "email": "oauth-test@example.com",
            "name": "OAuth Test User",
            "given_name": "OAuth",
            "family_name": "User",
            "picture": "https://example.com/avatar.jpg",
            "verified_email": True,
        }

        # Use provided responses or defaults
        token_data = token_response or default_token_response
        user_data = user_response or default_user_response

        # Create and return context manager for proper lifecycle management
        mock_context = respx.mock(assert_all_called=False)
        mock_context.post("https://oauth2.googleapis.com/token").mock(
            return_value=httpx.Response(token_status_code, json=token_data)
        )
        mock_context.get("https://www.googleapis.com/oauth2/v1/userinfo").mock(
            return_value=httpx.Response(user_status_code, json=user_data)
        )

        return mock_context

    return _create_mock
