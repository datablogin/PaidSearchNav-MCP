"""FastMCP server for PaidSearchNav Google Ads data access."""

import logging
import os
from datetime import datetime
from typing import Any

from fastmcp import FastMCP
from pydantic import BaseModel, Field

from paidsearchnav_mcp.clients.google.client import GoogleAdsAPIClient

logger = logging.getLogger(__name__)


# Initialize MCP server
mcp = FastMCP("PaidSearchNav MCP Server")


# ============================================================================
# Helper Functions
# ============================================================================


def _get_google_ads_client() -> GoogleAdsAPIClient:
    """
    Create and return a configured Google Ads API client.

    Reads credentials from environment variables:
    - GOOGLE_ADS_DEVELOPER_TOKEN
    - GOOGLE_ADS_CLIENT_ID
    - GOOGLE_ADS_CLIENT_SECRET
    - GOOGLE_ADS_REFRESH_TOKEN
    - GOOGLE_ADS_LOGIN_CUSTOMER_ID (optional, for MCC accounts)

    Returns:
        Configured GoogleAdsAPIClient instance

    Raises:
        ValueError: If required environment variables are not set
    """
    developer_token = os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN")
    client_id = os.getenv("GOOGLE_ADS_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_ADS_CLIENT_SECRET")
    refresh_token = os.getenv("GOOGLE_ADS_REFRESH_TOKEN")
    login_customer_id = os.getenv("GOOGLE_ADS_LOGIN_CUSTOMER_ID")

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

    return GoogleAdsAPIClient(
        developer_token=developer_token,
        client_id=client_id,
        client_secret=client_secret,
        refresh_token=refresh_token,
        login_customer_id=login_customer_id,
        settings=None,  # Optional settings for rate limiting
    )


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
        # Initialize client
        client = _get_google_ads_client()

        # Parse dates
        start_date = datetime.strptime(request.start_date, "%Y-%m-%d")
        end_date = datetime.strptime(request.end_date, "%Y-%m-%d")

        # Call the client method
        search_terms = await client.get_search_terms(
            customer_id=request.customer_id,
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

        return {
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

    except ValueError as e:
        logger.error(f"Invalid date format or configuration: {e}")
        return {"status": "error", "message": f"Invalid input: {str(e)}", "data": []}
    except Exception as e:
        logger.error(f"Error fetching search terms: {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"Failed to fetch search terms: {str(e)}",
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
        # Initialize client
        client = _get_google_ads_client()

        # Call the client method
        keywords = await client.get_keywords(
            customer_id=request.customer_id,
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

        return {
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

    except ValueError as e:
        logger.error(f"Invalid configuration: {e}")
        return {"status": "error", "message": f"Invalid input: {str(e)}", "data": []}
    except Exception as e:
        logger.error(f"Error fetching keywords: {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"Failed to fetch keywords: {str(e)}",
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
        # Initialize client
        client = _get_google_ads_client()

        # Parse dates
        start_date = datetime.strptime(request.start_date, "%Y-%m-%d")
        end_date = datetime.strptime(request.end_date, "%Y-%m-%d")

        # Call the client method
        campaigns = await client.get_campaigns(
            customer_id=request.customer_id,
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

        return {
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

    except ValueError as e:
        logger.error(f"Invalid date format or configuration: {e}")
        return {"status": "error", "message": f"Invalid input: {str(e)}", "data": []}
    except Exception as e:
        logger.error(f"Error fetching campaigns: {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"Failed to fetch campaigns: {str(e)}",
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
        # Initialize client
        client = _get_google_ads_client()

        # Call the client method
        negative_keywords = await client.get_negative_keywords(
            customer_id=request.customer_id,
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

        return {
            "status": "success",
            "message": f"Retrieved {len(data)} negative keywords",
            "metadata": {
                "customer_id": request.customer_id,
                "campaign_id": request.campaign_id,
                "record_count": len(data),
            },
            "data": data,
        }

    except ValueError as e:
        logger.error(f"Invalid configuration: {e}")
        return {"status": "error", "message": f"Invalid input: {str(e)}", "data": []}
    except Exception as e:
        logger.error(f"Error fetching negative keywords: {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"Failed to fetch negative keywords: {str(e)}",
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
        # Initialize client
        client = _get_google_ads_client()

        # Parse dates
        start_date = datetime.strptime(request.start_date, "%Y-%m-%d")
        end_date = datetime.strptime(request.end_date, "%Y-%m-%d")

        # Call the client method
        geo_data = await client.get_geographic_performance(
            customer_id=request.customer_id,
            start_date=start_date,
            end_date=end_date,
            geographic_level="CITY",  # Default to city-level data
        )

        # The data is already in dictionary format from the client
        return {
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

    except ValueError as e:
        logger.error(f"Invalid date format or configuration: {e}")
        return {"status": "error", "message": f"Invalid input: {str(e)}", "data": []}
    except Exception as e:
        logger.error(f"Error fetching geographic performance: {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"Failed to fetch geographic performance: {str(e)}",
            "data": [],
        }


# ============================================================================
# Tools - BigQuery
# ============================================================================


@mcp.tool()
async def query_bigquery(request: BigQueryRequest) -> dict[str, Any]:
    """
    Execute a SQL query against BigQuery.

    Allows running custom BigQuery queries for advanced analysis,
    historical data retrieval, or cross-platform attribution.
    Useful for joining Google Ads data with GA4 or other data sources.
    """
    # TODO: Implement actual BigQuery query execution
    return {
        "status": "success",
        "message": "BigQuery query execution not yet implemented",
        "request": {
            "query_preview": request.query[:100] + "..."
            if len(request.query) > 100
            else request.query,
            "project_id": request.project_id,
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
        "google_ads_configured": bool(os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN")),
        "bigquery_configured": bool(os.getenv("GOOGLE_APPLICATION_CREDENTIALS")),
        "tools_available": [
            "get_search_terms",
            "get_keywords",
            "get_campaigns",
            "get_negative_keywords",
            "get_geo_performance",
            "query_bigquery",
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
                "enabled": bool(os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN")),
                "api_version": "v17",
            },
            "bigquery": {
                "enabled": bool(os.getenv("GOOGLE_APPLICATION_CREDENTIALS")),
                "default_project": os.getenv("GCP_PROJECT_ID", "not-configured"),
            },
            "caching": {
                "enabled": bool(os.getenv("REDIS_URL")),
                "backend": "redis" if os.getenv("REDIS_URL") else "memory",
            },
        },
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
