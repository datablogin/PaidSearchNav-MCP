"""FastMCP server for PaidSearchNav Google Ads data access."""

import logging
import os
import re
from datetime import datetime
from enum import Enum
from typing import Any

from fastmcp import FastMCP
from pydantic import BaseModel, Field

from paidsearchnav_mcp.clients.bigquery.client import BigQueryClient
from paidsearchnav_mcp.clients.bigquery.validator import QueryValidator
from paidsearchnav_mcp.clients.cache import CacheClient
from paidsearchnav_mcp.clients.google.client import GoogleAdsAPIClient
from paidsearchnav_mcp.core.exceptions import (
    APIError,
    AuthenticationError,
    RateLimitError,
)

logger = logging.getLogger(__name__)
# Warn if debug logging is enabled in production
if os.getenv("ENVIRONMENT") == "production" and logger.level <= logging.DEBUG:
    logger.warning(
        "DEBUG logging enabled in production environment. "
        "This may expose sensitive information in logs. "
        "Set ENVIRONMENT=production and logging level to INFO or higher."
    )


# ============================================================================
# Error Codes
# ============================================================================


class ErrorCode(str, Enum):
    """Error codes for programmatic error handling."""

    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    INVALID_CUSTOMER_ID = "INVALID_CUSTOMER_ID"
    INVALID_INPUT = "INVALID_INPUT"
    SEARCH_TERMS_FETCH_ERROR = "SEARCH_TERMS_FETCH_ERROR"
    KEYWORDS_FETCH_ERROR = "KEYWORDS_FETCH_ERROR"
    CAMPAIGNS_FETCH_ERROR = "CAMPAIGNS_FETCH_ERROR"
    NEGATIVE_KEYWORDS_FETCH_ERROR = "NEGATIVE_KEYWORDS_FETCH_ERROR"
    GEO_PERFORMANCE_FETCH_ERROR = "GEO_PERFORMANCE_FETCH_ERROR"
    BIGQUERY_FETCH_ERROR = "BIGQUERY_FETCH_ERROR"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    INTERNAL_ERROR = "INTERNAL_ERROR"


# Initialize MCP server
mcp = FastMCP("PaidSearchNav MCP Server")


# ============================================================================
# Helper Functions
# ============================================================================


def sanitize_error_message(msg: str) -> str:
    """Remove potential credentials from error messages.

    This prevents accidental logging of sensitive data like tokens,
    API keys, and email addresses in error messages.

    Args:
        msg: Original error message

    Returns:
        Sanitized error message with credentials redacted

    Examples:
        >>> sanitize_error_message("Token abc123xyz failed")
        "Token [REDACTED] failed"
        >>> sanitize_error_message("user@example.com authentication failed")
        "[EMAIL_REDACTED] authentication failed"
    """
    # Remove anything that looks like a token (20+ alphanumeric/dash/underscore)
    msg = re.sub(r"[A-Za-z0-9_-]{20,}", "[REDACTED]", msg)

    # Remove anything that looks like an email address
    msg = re.sub(r"\b[\w.-]+@[\w.-]+\.\w+\b", "[EMAIL_REDACTED]", msg)

    # Remove anything that looks like a customer ID (10 digits)
    msg = re.sub(r"\b\d{10}\b", "[CUSTOMER_ID_REDACTED]", msg)

    # Remove anything that looks like an API key pattern
    msg = re.sub(
        r"(api[_-]?key|token|secret|password|credential)[\"']?\s*[:=]\s*[\"']?[^\s\"']+",
        r"\1=[REDACTED]",
        msg,
        flags=re.IGNORECASE,
    )

    return msg


# Global client instance for reuse across requests
_client_instance: GoogleAdsAPIClient | None = None
_cache_instance: CacheClient | None = None


def reset_client_for_testing():
    """Reset the singleton client instance (for testing only)."""
    global _client_instance
    _client_instance = None


def _get_google_ads_client() -> GoogleAdsAPIClient:
    """
    Get or create a configured Google Ads API client (singleton pattern).

    The client instance is reused across requests to:
    - Share circuit breaker state
    - Reuse rate limiter state
    - Optimize connection pooling
    - Maintain metrics across requests

    Reads credentials from environment variables (supports both prefixes):
    - PSN_GOOGLE_ADS_DEVELOPER_TOKEN or GOOGLE_ADS_DEVELOPER_TOKEN
    - PSN_GOOGLE_ADS_CLIENT_ID or GOOGLE_ADS_CLIENT_ID
    - PSN_GOOGLE_ADS_CLIENT_SECRET or GOOGLE_ADS_CLIENT_SECRET
    - PSN_GOOGLE_ADS_REFRESH_TOKEN or GOOGLE_ADS_REFRESH_TOKEN
    - PSN_GOOGLE_ADS_LOGIN_CUSTOMER_ID or GOOGLE_ADS_LOGIN_CUSTOMER_ID (optional, for MCC accounts)

    Returns:
        Configured GoogleAdsAPIClient instance

    Raises:
        ValueError: If required environment variables are not set
    """
    global _client_instance

    # Return existing instance if available
    if _client_instance is not None:
        return _client_instance

    # Create new instance
    # Support both PSN_GOOGLE_ADS_* and GOOGLE_ADS_* prefixes
    developer_token = os.getenv("PSN_GOOGLE_ADS_DEVELOPER_TOKEN") or os.getenv(
        "GOOGLE_ADS_DEVELOPER_TOKEN"
    )
    client_id = os.getenv("PSN_GOOGLE_ADS_CLIENT_ID") or os.getenv(
        "GOOGLE_ADS_CLIENT_ID"
    )
    client_secret = os.getenv("PSN_GOOGLE_ADS_CLIENT_SECRET") or os.getenv(
        "GOOGLE_ADS_CLIENT_SECRET"
    )
    refresh_token = os.getenv("PSN_GOOGLE_ADS_REFRESH_TOKEN") or os.getenv(
        "GOOGLE_ADS_REFRESH_TOKEN"
    )
    login_customer_id = os.getenv("PSN_GOOGLE_ADS_LOGIN_CUSTOMER_ID") or os.getenv(
        "GOOGLE_ADS_LOGIN_CUSTOMER_ID"
    )

    if not all([developer_token, client_id, client_secret, refresh_token]):
        missing = []
        if not developer_token:
            missing.append("GOOGLE_ADS_DEVELOPER_TOKEN")
        if not client_id:
            missing.append("GOOGLE_ADS_CLIENT_ID")
        if not client_secret:
            missing.append("GOOGLE_ADS_CLIENT_SECRET")
        if not refresh_token:
            missing.append("GOOGLE_ADS_REFRESH_TOKEN")
        raise ValueError(
            f"Missing required environment variables: {', '.join(missing)}"
        )

    # Create and cache the client instance
    _client_instance = GoogleAdsAPIClient(
        developer_token=developer_token,
        client_id=client_id,
        client_secret=client_secret,
        refresh_token=refresh_token,
        login_customer_id=login_customer_id,
        settings=None,  # Optional settings for rate limiting
    )

    return _client_instance


def _get_cache_client() -> CacheClient | None:
    """
    Get cache client if Redis is configured (singleton pattern).

    The cache client instance is reused across requests to maintain
    connection pooling and optimize performance.

    Reads configuration from environment variables:
    - REDIS_URL: Redis connection URL (e.g., "redis://localhost:6379/0")
    - REDIS_TTL: Default TTL in seconds (default: 3600)

    Returns:
        CacheClient instance if REDIS_URL is set, None otherwise

    Note:
        Returns None if Redis is not configured, allowing the server
        to operate without caching when Redis is unavailable.
    """
    global _cache_instance

    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        logger.debug("Redis not configured, caching disabled")
        return None

    # Return existing instance if available
    if _cache_instance is not None:
        return _cache_instance

    # Create new instance
    try:
        redis_ttl = int(os.getenv("REDIS_TTL", "3600"))
        _cache_instance = CacheClient(redis_url, default_ttl=redis_ttl)
        logger.info(f"Cache client initialized with TTL={redis_ttl}s")
        return _cache_instance
    except Exception as e:
        logger.error(
            f"Failed to initialize cache client: {sanitize_error_message(str(e))}"
        )
        return None


def validate_customer_id(customer_id: str) -> str:
    """Validate and normalize customer ID format.

    Args:
        customer_id: Customer ID with or without dashes

    Returns:
        Normalized customer ID (10 digits, no dashes)

    Raises:
        ValueError: If customer ID is invalid
    """
    # Remove dashes and whitespace
    cleaned = customer_id.replace("-", "").replace(" ", "").strip()

    # Validate format
    if not cleaned.isdigit():
        raise ValueError(f"Customer ID must contain only digits: {customer_id}")

    if len(cleaned) != 10:
        raise ValueError(
            f"Customer ID must be exactly 10 digits: {customer_id} (got {len(cleaned)})"
        )

    return cleaned


def validate_date_format(date_str: str, field_name: str = "date") -> datetime:
    """Validate date string is in YYYY-MM-DD format.

    Args:
        date_str: Date string to validate
        field_name: Name of the field for error messages

    Returns:
        Parsed datetime object

    Raises:
        ValueError: If date format is invalid
    """
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        raise ValueError(
            f"Invalid {field_name} format: {date_str}. Expected YYYY-MM-DD"
        )


def validate_date_range(
    start_date: datetime,
    end_date: datetime,
    start_name: str = "start_date",
    end_name: str = "end_date",
) -> None:
    """Validate that start_date is before end_date.

    Args:
        start_date: Start datetime
        end_date: End datetime
        start_name: Name of start field for error messages
        end_name: Name of end field for error messages

    Raises:
        ValueError: If date range is invalid
    """
    if start_date > end_date:
        raise ValueError(f"{start_name} must be before {end_name}")


# ============================================================================
# Models
# ============================================================================


class SearchTermsRequest(BaseModel):
    """Request model for fetching search terms data."""

    customer_id: str = Field(..., description="Google Ads customer ID (without dashes)")
    start_date: str = Field(..., description="Start date in YYYY-MM-DD format")
    end_date: str = Field(..., description="End date in YYYY-MM-DD format")
    campaign_id: str | None = Field(
        None, description="Optional campaign ID to filter by"
    )


class KeywordsRequest(BaseModel):
    """Request model for fetching keywords data."""

    customer_id: str = Field(..., description="Google Ads customer ID (without dashes)")
    campaign_id: str | None = Field(
        None, description="Optional campaign ID to filter by"
    )
    ad_group_id: str | None = Field(
        None, description="Optional ad group ID to filter by"
    )


class CampaignsRequest(BaseModel):
    """Request model for fetching campaigns data."""

    customer_id: str = Field(..., description="Google Ads customer ID (without dashes)")
    start_date: str = Field(..., description="Start date in YYYY-MM-DD format")
    end_date: str = Field(..., description="End date in YYYY-MM-DD format")


class NegativeKeywordsRequest(BaseModel):
    """Request model for fetching negative keywords."""

    customer_id: str = Field(..., description="Google Ads customer ID (without dashes)")
    campaign_id: str | None = Field(
        None, description="Optional campaign ID to filter by"
    )


class BigQueryRequest(BaseModel):
    """Request model for executing BigQuery queries."""

    query: str = Field(..., description="SQL query to execute")
    project_id: str | None = Field(
        None, description="Optional GCP project ID (uses default if not provided)"
    )


class BigQuerySchemaRequest(BaseModel):
    """Request model for BigQuery schema lookup."""

    dataset_id: str = Field(..., description="BigQuery dataset ID")
    table_id: str = Field(..., description="BigQuery table ID")
    project_id: str | None = Field(
        None, description="Optional GCP project ID (uses default if not provided)"
    )


# ============================================================================
# Tools - Google Ads
# ============================================================================


@mcp.tool()
async def get_search_terms(request: SearchTermsRequest) -> dict[str, Any]:
    """
    Fetch search terms data from Google Ads for the specified date range.

    This tool retrieves actual user search queries that triggered your ads,
    along with performance metrics (impressions, clicks, cost, conversions).
    Essential for quarterly keyword audits and cost efficiency analysis.
    """
    try:
        # Validate inputs
        customer_id = validate_customer_id(request.customer_id)
        start_date = validate_date_format(request.start_date, "start_date")
        end_date = validate_date_format(request.end_date, "end_date")
        validate_date_range(start_date, end_date)

        # Initialize clients
        client = _get_google_ads_client()
        cache = _get_cache_client()

        # Try cache first
        if cache:
            cache_key = cache._make_key(
                "search_terms",
                {
                    "customer_id": customer_id,
                    "start_date": request.start_date,
                    "end_date": request.end_date,
                    "campaign_id": request.campaign_id,
                },
            )
            cached_data = await cache.get(cache_key)
            if cached_data:
                logger.info(
                    f"Cache hit for search terms query: customer={customer_id}, "
                    f"date_range={request.start_date}:{request.end_date}"
                )
                return cached_data
            else:
                logger.debug(
                    f"Cache miss for search terms query: customer={customer_id}, "
                    f"date_range={request.start_date}:{request.end_date}"
                )

        # Call the client method
        search_terms = await client.get_search_terms(
            customer_id=customer_id,
            start_date=start_date,
            end_date=end_date,
            campaigns=[request.campaign_id] if request.campaign_id else None,
        )

        # Convert SearchTerm objects to dictionaries
        data = [
            {
                "customer_id": st.customer_id,
                "campaign_id": st.campaign_id,
                "campaign_name": st.campaign_name,
                "ad_group_id": st.ad_group_id,
                "ad_group_name": st.ad_group_name,
                "search_term": st.search_term,
                "keyword_text": st.keyword_text,
                "match_type": st.match_type,
                "metrics": {
                    "impressions": st.metrics.impressions,
                    "clicks": st.metrics.clicks,
                    "cost": st.metrics.cost,
                    "conversions": st.metrics.conversions,
                    "conversion_value": st.metrics.conversion_value,
                    "ctr": st.metrics.ctr,
                    "avg_cpc": st.metrics.avg_cpc,
                    "conversion_rate": st.metrics.conversion_rate,
                },
            }
            for st in search_terms
        ]

        result = {
            "status": "success",
            "message": f"Retrieved {len(data)} search terms",
            "metadata": {
                "customer_id": request.customer_id,
                "start_date": request.start_date,
                "end_date": request.end_date,
                "campaign_id": request.campaign_id,
                "record_count": len(data),
            },
            "data": data,
        }

        # Cache the result (only on success, TTL=1 hour for frequently changing data)
        if cache and result["status"] == "success":
            try:
                await cache.set(cache_key, result, ttl=3600)
                logger.debug(
                    f"Cached search terms result: customer={customer_id}, "
                    f"records={len(data)}, ttl=3600s"
                )
            except Exception as cache_error:
                # Log but don't fail the request if caching fails
                logger.warning(f"Failed to cache search terms result: {cache_error}")

        return result

    except ValueError as e:
        logger.error(
            f"Invalid date format or configuration: {sanitize_error_message(str(e))}",
            exc_info=True,
        )
        return {
            "status": "error",
            "error_code": ErrorCode.INVALID_INPUT,
            "message": f"Invalid input: {str(e)}",
            "details": {"error_type": "validation", "retry_allowed": False},
            "data": [],
        }
    except AuthenticationError as e:
        logger.error(
            f"Authentication failed: {sanitize_error_message(str(e))}", exc_info=True
        )
        return {
            "status": "error",
            "error_code": ErrorCode.INVALID_CREDENTIALS,
            "message": "Authentication failed. Please check your credentials.",
            "details": {"error_type": "authentication", "retry_allowed": False},
            "data": [],
        }
    except RateLimitError as e:
        logger.warning(f"Rate limit exceeded: {sanitize_error_message(str(e))}")
        return {
            "status": "error",
            "error_code": ErrorCode.RATE_LIMIT_EXCEEDED,
            "message": "API rate limit exceeded. Please try again later.",
            "details": {
                "error_type": "rate_limit",
                "retry_allowed": True,
                "retry_after_seconds": 60,
            },
            "data": [],
        }
    except APIError as e:
        logger.error(
            f"Google Ads API error: {sanitize_error_message(str(e))}", exc_info=True
        )
        return {
            "status": "error",
            "error_code": ErrorCode.SEARCH_TERMS_FETCH_ERROR,
            "message": f"Google Ads API error: {str(e)}",
            "details": {"error_type": "api_error", "retry_allowed": True},
            "data": [],
        }
    except Exception as e:
        logger.error(
            f"Unexpected error: {sanitize_error_message(str(e))}", exc_info=True
        )
        return {
            "status": "error",
            "error_code": ErrorCode.INTERNAL_ERROR,
            "message": "An unexpected error occurred. Please contact support if this persists.",
            "details": {"error_type": "unexpected"},
            "data": [],
        }


@mcp.tool()
async def get_keywords(request: KeywordsRequest) -> dict[str, Any]:
    """
    Fetch keywords data from Google Ads campaigns.

    Retrieves all keywords in your account with their match types, bids,
    quality scores, and performance metrics. Used for keyword match type
    optimization and identifying exact match opportunities.
    """
    try:
        # Validate inputs
        customer_id = validate_customer_id(request.customer_id)

        # Initialize clients
        client = _get_google_ads_client()
        cache = _get_cache_client()

        # Try cache first
        if cache:
            cache_key = cache._make_key(
                "keywords",
                {
                    "customer_id": customer_id,
                    "campaign_id": request.campaign_id,
                    "ad_group_id": request.ad_group_id,
                },
            )
            cached_data = await cache.get(cache_key)
            if cached_data:
                logger.info(
                    f"Cache hit for keywords query: customer={customer_id}, "
                    f"campaign={request.campaign_id}"
                )
                return cached_data
            else:
                logger.debug(
                    f"Cache miss for keywords query: customer={customer_id}, "
                    f"campaign={request.campaign_id}"
                )

        # Call the client method
        keywords = await client.get_keywords(
            customer_id=customer_id,
            campaign_id=request.campaign_id,
            ad_groups=[request.ad_group_id] if request.ad_group_id else None,
        )

        # Convert Keyword objects to dictionaries
        data = [
            {
                "keyword_id": kw.keyword_id,
                "customer_id": kw.customer_id,
                "campaign_id": kw.campaign_id,
                "campaign_name": kw.campaign_name,
                "ad_group_id": kw.ad_group_id,
                "ad_group_name": kw.ad_group_name,
                "keyword_text": kw.keyword_text,
                "match_type": kw.match_type,
                "status": kw.status,
                "max_cpc": kw.max_cpc,
                "quality_score": kw.quality_score,
                "impressions": kw.impressions,
                "clicks": kw.clicks,
                "cost": kw.cost,
                "conversions": kw.conversions,
                "conversion_value": kw.conversion_value,
            }
            for kw in keywords
        ]

        result = {
            "status": "success",
            "message": f"Retrieved {len(data)} keywords",
            "metadata": {
                "customer_id": request.customer_id,
                "campaign_id": request.campaign_id,
                "ad_group_id": request.ad_group_id,
                "record_count": len(data),
            },
            "data": data,
        }

        # Cache the result (only on success, TTL=2 hours for less frequently changing data)
        if cache and result["status"] == "success":
            try:
                await cache.set(cache_key, result, ttl=7200)
                logger.debug(
                    f"Cached keywords result: customer={customer_id}, "
                    f"records={len(data)}, ttl=7200s"
                )
            except Exception as cache_error:
                logger.warning(f"Failed to cache keywords result: {cache_error}")

        return result

    except ValueError as e:
        logger.error(
            f"Invalid configuration: {sanitize_error_message(str(e))}", exc_info=True
        )
        return {
            "status": "error",
            "error_code": ErrorCode.INVALID_INPUT,
            "message": f"Invalid input: {str(e)}",
            "details": {"error_type": "validation", "retry_allowed": False},
            "data": [],
        }
    except AuthenticationError as e:
        logger.error(
            f"Authentication failed: {sanitize_error_message(str(e))}", exc_info=True
        )
        return {
            "status": "error",
            "error_code": ErrorCode.INVALID_CREDENTIALS,
            "message": "Authentication failed. Please check your credentials.",
            "details": {"error_type": "authentication", "retry_allowed": False},
            "data": [],
        }
    except RateLimitError as e:
        logger.warning(f"Rate limit exceeded: {sanitize_error_message(str(e))}")
        return {
            "status": "error",
            "error_code": ErrorCode.RATE_LIMIT_EXCEEDED,
            "message": "API rate limit exceeded. Please try again later.",
            "details": {
                "error_type": "rate_limit",
                "retry_allowed": True,
                "retry_after_seconds": 60,
            },
            "data": [],
        }
    except APIError as e:
        logger.error(
            f"Google Ads API error: {sanitize_error_message(str(e))}", exc_info=True
        )
        return {
            "status": "error",
            "error_code": ErrorCode.KEYWORDS_FETCH_ERROR,
            "message": f"Google Ads API error: {str(e)}",
            "details": {"error_type": "api_error", "retry_allowed": True},
            "data": [],
        }
    except Exception as e:
        logger.error(
            f"Unexpected error: {sanitize_error_message(str(e))}", exc_info=True
        )
        return {
            "status": "error",
            "error_code": ErrorCode.INTERNAL_ERROR,
            "message": "An unexpected error occurred. Please contact support if this persists.",
            "details": {"error_type": "unexpected"},
            "data": [],
        }


@mcp.tool()
async def get_campaigns(request: CampaignsRequest) -> dict[str, Any]:
    """
    Fetch campaigns data from Google Ads.

    Retrieves campaign-level data including settings, budgets, status,
    and performance metrics. Used for campaign overlap analysis and
    Performance Max integration checks.
    """
    try:
        # Validate inputs
        customer_id = validate_customer_id(request.customer_id)
        start_date = validate_date_format(request.start_date, "start_date")
        end_date = validate_date_format(request.end_date, "end_date")
        validate_date_range(start_date, end_date)

        # Initialize clients
        client = _get_google_ads_client()
        cache = _get_cache_client()

        # Try cache first
        if cache:
            cache_key = cache._make_key(
                "campaigns",
                {
                    "customer_id": customer_id,
                    "start_date": request.start_date,
                    "end_date": request.end_date,
                },
            )
            cached_data = await cache.get(cache_key)
            if cached_data:
                logger.info(
                    f"Cache hit for campaigns query: customer={customer_id}, "
                    f"date_range={request.start_date}:{request.end_date}"
                )
                return cached_data
            else:
                logger.debug(
                    f"Cache miss for campaigns query: customer={customer_id}, "
                    f"date_range={request.start_date}:{request.end_date}"
                )

        # Call the client method
        campaigns = await client.get_campaigns(
            customer_id=customer_id,
            start_date=start_date,
            end_date=end_date,
        )

        # Convert Campaign objects to dictionaries
        data = [
            {
                "campaign_id": camp.campaign_id,
                "customer_id": camp.customer_id,
                "name": camp.name,
                "status": camp.status,
                "type": camp.type,
                "budget_amount": camp.budget_amount,
                "budget_currency": camp.budget_currency,
                "bidding_strategy": camp.bidding_strategy,
                "target_cpa": camp.target_cpa,
                "target_roas": camp.target_roas,
                "impressions": camp.impressions,
                "clicks": camp.clicks,
                "cost": camp.cost,
                "conversions": camp.conversions,
                "conversion_value": camp.conversion_value,
            }
            for camp in campaigns
        ]

        result = {
            "status": "success",
            "message": f"Retrieved {len(data)} campaigns",
            "metadata": {
                "customer_id": request.customer_id,
                "start_date": request.start_date,
                "end_date": request.end_date,
                "record_count": len(data),
            },
            "data": data,
        }

        # Cache the result (only on success, TTL=2 hours for less frequently changing data)
        if cache and result["status"] == "success":
            try:
                await cache.set(cache_key, result, ttl=7200)
                logger.debug(
                    f"Cached campaigns result: customer={customer_id}, "
                    f"records={len(data)}, ttl=7200s"
                )
            except Exception as cache_error:
                logger.warning(f"Failed to cache campaigns result: {cache_error}")

        return result

    except ValueError as e:
        logger.error(
            f"Invalid date format or configuration: {sanitize_error_message(str(e))}",
            exc_info=True,
        )
        return {
            "status": "error",
            "error_code": ErrorCode.INVALID_INPUT,
            "message": f"Invalid input: {str(e)}",
            "details": {"error_type": "validation", "retry_allowed": False},
            "data": [],
        }
    except AuthenticationError as e:
        logger.error(
            f"Authentication failed: {sanitize_error_message(str(e))}", exc_info=True
        )
        return {
            "status": "error",
            "error_code": ErrorCode.INVALID_CREDENTIALS,
            "message": "Authentication failed. Please check your credentials.",
            "details": {"error_type": "authentication", "retry_allowed": False},
            "data": [],
        }
    except RateLimitError as e:
        logger.warning(f"Rate limit exceeded: {sanitize_error_message(str(e))}")
        return {
            "status": "error",
            "error_code": ErrorCode.RATE_LIMIT_EXCEEDED,
            "message": "API rate limit exceeded. Please try again later.",
            "details": {
                "error_type": "rate_limit",
                "retry_allowed": True,
                "retry_after_seconds": 60,
            },
            "data": [],
        }
    except APIError as e:
        logger.error(
            f"Google Ads API error: {sanitize_error_message(str(e))}", exc_info=True
        )
        return {
            "status": "error",
            "error_code": ErrorCode.CAMPAIGNS_FETCH_ERROR,
            "message": f"Google Ads API error: {str(e)}",
            "details": {"error_type": "api_error", "retry_allowed": True},
            "data": [],
        }
    except Exception as e:
        logger.error(
            f"Unexpected error: {sanitize_error_message(str(e))}", exc_info=True
        )
        return {
            "status": "error",
            "error_code": ErrorCode.INTERNAL_ERROR,
            "message": "An unexpected error occurred. Please contact support if this persists.",
            "details": {"error_type": "unexpected"},
            "data": [],
        }


@mcp.tool()
async def get_negative_keywords(request: NegativeKeywordsRequest) -> dict[str, Any]:
    """
    Fetch negative keywords from Google Ads campaigns.

    Retrieves all negative keywords at campaign and ad group level,
    including shared negative keyword lists. Essential for identifying
    conflicts where negative keywords block positive keywords.
    """
    try:
        # Validate inputs
        customer_id = validate_customer_id(request.customer_id)

        # Initialize clients
        client = _get_google_ads_client()
        cache = _get_cache_client()

        # Try cache first
        if cache:
            cache_key = cache._make_key(
                "negative_keywords",
                {
                    "customer_id": customer_id,
                    "campaign_id": request.campaign_id,
                },
            )
            cached_data = await cache.get(cache_key)
            if cached_data:
                logger.info(
                    f"Cache hit for negative keywords query: customer={customer_id}, "
                    f"campaign={request.campaign_id}"
                )
                return cached_data
            else:
                logger.debug(
                    f"Cache miss for negative keywords query: customer={customer_id}, "
                    f"campaign={request.campaign_id}"
                )

        # Call the client method
        negative_keywords = await client.get_negative_keywords(
            customer_id=customer_id,
            include_shared_sets=True,
        )

        # The data is already in dictionary format from the client
        # Filter by campaign_id if provided
        if request.campaign_id:
            data = [
                nk
                for nk in negative_keywords
                if nk.get("campaign_id") == request.campaign_id
            ]
        else:
            data = negative_keywords

        result = {
            "status": "success",
            "message": f"Retrieved {len(data)} negative keywords",
            "metadata": {
                "customer_id": request.customer_id,
                "campaign_id": request.campaign_id,
                "record_count": len(data),
            },
            "data": data,
        }

        # Cache the result (only on success, TTL=4 hours for rarely changing data)
        if cache and result["status"] == "success":
            try:
                await cache.set(cache_key, result, ttl=14400)
                logger.debug(
                    f"Cached negative keywords result: customer={customer_id}, "
                    f"records={len(data)}, ttl=14400s"
                )
            except Exception as cache_error:
                logger.warning(
                    f"Failed to cache negative keywords result: {cache_error}"
                )

        return result

    except ValueError as e:
        logger.error(
            f"Invalid configuration: {sanitize_error_message(str(e))}", exc_info=True
        )
        return {
            "status": "error",
            "error_code": ErrorCode.INVALID_INPUT,
            "message": f"Invalid input: {str(e)}",
            "details": {"error_type": "validation", "retry_allowed": False},
            "data": [],
        }
    except AuthenticationError as e:
        logger.error(
            f"Authentication failed: {sanitize_error_message(str(e))}", exc_info=True
        )
        return {
            "status": "error",
            "error_code": ErrorCode.INVALID_CREDENTIALS,
            "message": "Authentication failed. Please check your credentials.",
            "details": {"error_type": "authentication", "retry_allowed": False},
            "data": [],
        }
    except RateLimitError as e:
        logger.warning(f"Rate limit exceeded: {sanitize_error_message(str(e))}")
        return {
            "status": "error",
            "error_code": ErrorCode.RATE_LIMIT_EXCEEDED,
            "message": "API rate limit exceeded. Please try again later.",
            "details": {
                "error_type": "rate_limit",
                "retry_allowed": True,
                "retry_after_seconds": 60,
            },
            "data": [],
        }
    except APIError as e:
        logger.error(
            f"Google Ads API error: {sanitize_error_message(str(e))}", exc_info=True
        )
        return {
            "status": "error",
            "error_code": ErrorCode.NEGATIVE_KEYWORDS_FETCH_ERROR,
            "message": f"Google Ads API error: {str(e)}",
            "details": {"error_type": "api_error", "retry_allowed": True},
            "data": [],
        }
    except Exception as e:
        logger.error(
            f"Unexpected error: {sanitize_error_message(str(e))}", exc_info=True
        )
        return {
            "status": "error",
            "error_code": ErrorCode.INTERNAL_ERROR,
            "message": "An unexpected error occurred. Please contact support if this persists.",
            "details": {"error_type": "unexpected"},
            "data": [],
        }


@mcp.tool()
async def get_geo_performance(request: CampaignsRequest) -> dict[str, Any]:
    """
    Fetch geographic performance data from Google Ads.

    Retrieves performance metrics broken down by location (city, region, DMA).
    Critical for retail businesses to optimize local targeting and store
    performance analysis.
    """
    try:
        # Validate inputs
        customer_id = validate_customer_id(request.customer_id)
        start_date = validate_date_format(request.start_date, "start_date")
        end_date = validate_date_format(request.end_date, "end_date")
        validate_date_range(start_date, end_date)

        # Initialize clients
        client = _get_google_ads_client()
        cache = _get_cache_client()

        # Try cache first
        if cache:
            cache_key = cache._make_key(
                "geo_performance",
                {
                    "customer_id": customer_id,
                    "start_date": request.start_date,
                    "end_date": request.end_date,
                    "geographic_level": "CITY",
                },
            )
            cached_data = await cache.get(cache_key)
            if cached_data:
                logger.info(
                    f"Cache hit for geo performance query: customer={customer_id}, "
                    f"date_range={request.start_date}:{request.end_date}"
                )
                return cached_data
            else:
                logger.debug(
                    f"Cache miss for geo performance query: customer={customer_id}, "
                    f"date_range={request.start_date}:{request.end_date}"
                )

        # Call the client method
        geo_data = await client.get_geographic_performance(
            customer_id=customer_id,
            start_date=start_date,
            end_date=end_date,
            geographic_level="CITY",  # Default to city-level data
        )

        # The data is already in dictionary format from the client
        result = {
            "status": "success",
            "message": f"Retrieved {len(geo_data)} geographic performance records",
            "metadata": {
                "customer_id": request.customer_id,
                "start_date": request.start_date,
                "end_date": request.end_date,
                "geographic_level": "CITY",
                "record_count": len(geo_data),
            },
            "data": geo_data,
        }

        # Cache the result (only on success, TTL=1 hour for frequently changing data)
        if cache and result["status"] == "success":
            try:
                await cache.set(cache_key, result, ttl=3600)
                logger.debug(
                    f"Cached geo performance result: customer={customer_id}, "
                    f"records={len(geo_data)}, ttl=3600s"
                )
            except Exception as cache_error:
                logger.warning(f"Failed to cache geo performance result: {cache_error}")

        return result

    except ValueError as e:
        logger.error(
            f"Invalid date format or configuration: {sanitize_error_message(str(e))}",
            exc_info=True,
        )
        return {
            "status": "error",
            "error_code": ErrorCode.INVALID_INPUT,
            "message": f"Invalid input: {str(e)}",
            "details": {"error_type": "validation", "retry_allowed": False},
            "data": [],
        }
    except AuthenticationError as e:
        logger.error(
            f"Authentication failed: {sanitize_error_message(str(e))}", exc_info=True
        )
        return {
            "status": "error",
            "error_code": ErrorCode.INVALID_CREDENTIALS,
            "message": "Authentication failed. Please check your credentials.",
            "details": {"error_type": "authentication", "retry_allowed": False},
            "data": [],
        }
    except RateLimitError as e:
        logger.warning(f"Rate limit exceeded: {sanitize_error_message(str(e))}")
        return {
            "status": "error",
            "error_code": ErrorCode.RATE_LIMIT_EXCEEDED,
            "message": "API rate limit exceeded. Please try again later.",
            "details": {
                "error_type": "rate_limit",
                "retry_allowed": True,
                "retry_after_seconds": 60,
            },
            "data": [],
        }
    except APIError as e:
        logger.error(
            f"Google Ads API error: {sanitize_error_message(str(e))}", exc_info=True
        )
        return {
            "status": "error",
            "error_code": ErrorCode.GEO_PERFORMANCE_FETCH_ERROR,
            "message": f"Google Ads API error: {str(e)}",
            "details": {"error_type": "api_error", "retry_allowed": True},
            "data": [],
        }
    except Exception as e:
        logger.error(
            f"Unexpected error: {sanitize_error_message(str(e))}", exc_info=True
        )
        return {
            "status": "error",
            "error_code": ErrorCode.INTERNAL_ERROR,
            "message": "An unexpected error occurred. Please contact support if this persists.",
            "details": {"error_type": "unexpected"},
            "data": [],
        }


# ============================================================================
# Tools - BigQuery
# ============================================================================


@mcp.tool()
async def query_bigquery(request: BigQueryRequest) -> dict[str, Any]:
    """
    Execute a SQL query against BigQuery.

    Supports querying Google Ads data exported to BigQuery, GA4 data,
    and custom datasets. Useful for historical analysis and cross-platform attribution.
    Includes query validation to prevent destructive operations.
    """
    try:
        # Validate query first
        validation = QueryValidator.validate_query(request.query)

        if not validation["valid"]:
            logger.warning(f"BigQuery query validation failed: {validation['errors']}")
            return {
                "status": "error",
                "error_code": ErrorCode.INVALID_INPUT,
                "message": "Query validation failed",
                "details": {
                    "error_type": "validation",
                    "validation_errors": validation["errors"],
                    "retry_allowed": False,
                },
                "data": [],
            }

        # Initialize BigQuery client
        client = BigQueryClient(project_id=request.project_id)

        # Execute query
        results = await client.execute_query(request.query, max_results=10000)

        # Prepare response
        result = {
            "status": "success",
            "message": f"Query executed successfully, returned {len(results)} rows",
            "metadata": {
                "project_id": client.project_id,
                "result_count": len(results),
                "query_preview": request.query[:200] + "..."
                if len(request.query) > 200
                else request.query,
                "validation_warnings": validation["warnings"],
            },
            "data": results,
        }

        return result

    except ValueError as e:
        logger.error(
            f"Invalid BigQuery configuration: {sanitize_error_message(str(e))}",
            exc_info=True,
        )
        return {
            "status": "error",
            "error_code": ErrorCode.INVALID_INPUT,
            "message": f"Invalid input: {str(e)}",
            "details": {"error_type": "validation", "retry_allowed": False},
            "data": [],
        }
    except Exception as e:
        logger.error(
            f"BigQuery query error: {sanitize_error_message(str(e))}", exc_info=True
        )
        return {
            "status": "error",
            "error_code": ErrorCode.BIGQUERY_FETCH_ERROR,
            "message": f"BigQuery error: {str(e)}",
            "details": {
                "error_type": type(e).__name__,
                "retry_allowed": True,
                "query_preview": request.query[:200] + "..."
                if len(request.query) > 200
                else request.query,
            },
            "data": [],
        }


@mcp.tool()
async def get_bigquery_schema(request: BigQuerySchemaRequest) -> dict[str, Any]:
    """
    Get schema information for a BigQuery table.

    Useful for understanding available fields in Google Ads export tables,
    GA4 tables, or custom datasets before writing queries.
    """
    try:
        # Initialize BigQuery client
        client = BigQueryClient(project_id=request.project_id)

        # Get table schema
        schema_info = await client.get_table_schema(
            request.dataset_id, request.table_id
        )

        return {
            "status": "success",
            "message": f"Retrieved schema for {schema_info['table']}",
            "metadata": {
                "table": schema_info["table"],
                "num_rows": schema_info["num_rows"],
                "size_bytes": schema_info["size_bytes"],
                "field_count": len(schema_info["schema"]),
            },
            "data": schema_info["schema"],
        }

    except ValueError as e:
        logger.error(
            f"Invalid BigQuery configuration: {sanitize_error_message(str(e))}",
            exc_info=True,
        )
        return {
            "status": "error",
            "error_code": ErrorCode.INVALID_INPUT,
            "message": f"Invalid input: {str(e)}",
            "details": {"error_type": "validation", "retry_allowed": False},
            "data": [],
        }
    except Exception as e:
        logger.error(
            f"BigQuery schema error: {sanitize_error_message(str(e))}", exc_info=True
        )
        table_ref = (
            f"{request.project_id or 'default'}.{request.dataset_id}.{request.table_id}"
        )
        return {
            "status": "error",
            "error_code": ErrorCode.BIGQUERY_FETCH_ERROR,
            "message": f"Failed to retrieve schema: {str(e)}",
            "details": {
                "error_type": type(e).__name__,
                "retry_allowed": True,
                "table": table_ref,
            },
            "data": [],
        }


# ============================================================================
# Resources
# ============================================================================


@mcp.resource("resource://health")
def health_check() -> dict[str, Any]:
    """
    Provides server health status and configuration information.
    """
    return {
        "status": "healthy",
        "version": "1.0.0",
        "server": "PaidSearchNav MCP Server",
        "google_ads_configured": bool(
            os.getenv("PSN_GOOGLE_ADS_DEVELOPER_TOKEN")
            or os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN")
        ),
        "bigquery_configured": bool(os.getenv("GOOGLE_APPLICATION_CREDENTIALS")),
        "tools_available": [
            "get_search_terms",
            "get_keywords",
            "get_campaigns",
            "get_negative_keywords",
            "get_geo_performance",
            "query_bigquery",
            "get_bigquery_schema",
        ],
    }


@mcp.resource("resource://config")
def get_config() -> dict[str, Any]:
    """
    Provides the server's configuration status (without exposing secrets).
    """
    return {
        "server_version": "1.0.0",
        "environment": os.getenv("ENVIRONMENT", "development"),
        "features": {
            "google_ads": {
                "enabled": bool(
                    os.getenv("PSN_GOOGLE_ADS_DEVELOPER_TOKEN")
                    or os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN")
                ),
                "api_version": "v17",
            },
            "bigquery": {
                "enabled": bool(os.getenv("GOOGLE_APPLICATION_CREDENTIALS")),
                "default_project_configured": bool(os.getenv("GCP_PROJECT_ID")),
            },
            "caching": {
                "enabled": bool(os.getenv("REDIS_URL")),
                "backend": "redis" if os.getenv("REDIS_URL") else "memory",
            },
        },
    }


@mcp.resource("resource://bigquery/datasets")
def list_bigquery_datasets() -> dict[str, Any]:
    """
    List available BigQuery datasets in the configured project.

    Provides an overview of all datasets accessible to the service account,
    which is useful for discovering available data sources before querying.
    """
    try:
        # Initialize BigQuery client
        client = BigQueryClient()

        # List datasets
        datasets = list(client.client.list_datasets())

        return {
            "status": "success",
            "message": f"Found {len(datasets)} datasets",
            "metadata": {
                "project_id": client.project_id,
                "dataset_count": len(datasets),
            },
            "datasets": [
                {
                    "dataset_id": dataset.dataset_id,
                    "full_name": dataset.full_dataset_id,
                    "location": dataset.location,
                }
                for dataset in datasets
            ],
        }

    except Exception as e:
        logger.error(
            f"Failed to list BigQuery datasets: {sanitize_error_message(str(e))}",
            exc_info=True,
        )
        return {
            "status": "error",
            "error": str(e),
            "error_type": type(e).__name__,
            "bigquery_configured": bool(os.getenv("GOOGLE_APPLICATION_CREDENTIALS")),
            "datasets": [],
        }


# ============================================================================
# Server Factory
# ============================================================================


def create_mcp_server() -> FastMCP:
    """
    Create and return the configured MCP server instance.

    Returns:
        FastMCP: The configured server instance ready to run.
    """
    return mcp


# ============================================================================
# Entry Point
# ============================================================================

if __name__ == "__main__":
    # Run the MCP server
    mcp.run()
