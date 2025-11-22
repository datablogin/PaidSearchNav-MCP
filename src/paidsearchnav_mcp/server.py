"""FastMCP server for PaidSearchNav Google Ads data access."""

import os
from typing import Any

from fastmcp import FastMCP
from pydantic import BaseModel, Field


# Initialize MCP server
mcp = FastMCP("PaidSearchNav MCP Server")


# ============================================================================
# Models
# ============================================================================

class SearchTermsRequest(BaseModel):
    """Request model for fetching search terms data."""
    customer_id: str = Field(..., description="Google Ads customer ID (without dashes)")
    start_date: str = Field(..., description="Start date in YYYY-MM-DD format")
    end_date: str = Field(..., description="End date in YYYY-MM-DD format")
    campaign_id: str | None = Field(None, description="Optional campaign ID to filter by")


class KeywordsRequest(BaseModel):
    """Request model for fetching keywords data."""
    customer_id: str = Field(..., description="Google Ads customer ID (without dashes)")
    campaign_id: str | None = Field(None, description="Optional campaign ID to filter by")
    ad_group_id: str | None = Field(None, description="Optional ad group ID to filter by")


class CampaignsRequest(BaseModel):
    """Request model for fetching campaigns data."""
    customer_id: str = Field(..., description="Google Ads customer ID (without dashes)")
    start_date: str = Field(..., description="Start date in YYYY-MM-DD format")
    end_date: str = Field(..., description="End date in YYYY-MM-DD format")


class NegativeKeywordsRequest(BaseModel):
    """Request model for fetching negative keywords."""
    customer_id: str = Field(..., description="Google Ads customer ID (without dashes)")
    campaign_id: str | None = Field(None, description="Optional campaign ID to filter by")


class BigQueryRequest(BaseModel):
    """Request model for executing BigQuery queries."""
    query: str = Field(..., description="SQL query to execute")
    project_id: str | None = Field(None, description="Optional GCP project ID (uses default if not provided)")


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
    # TODO: Implement actual Google Ads API call
    return {
        "status": "success",
        "message": "Search terms data retrieval not yet implemented",
        "request": request.model_dump(),
        "data": []
    }


@mcp.tool()
async def get_keywords(request: KeywordsRequest) -> dict[str, Any]:
    """
    Fetch keywords data from Google Ads campaigns.

    Retrieves all keywords in your account with their match types, bids,
    quality scores, and performance metrics. Used for keyword match type
    optimization and identifying exact match opportunities.
    """
    # TODO: Implement actual Google Ads API call
    return {
        "status": "success",
        "message": "Keywords data retrieval not yet implemented",
        "request": request.model_dump(),
        "data": []
    }


@mcp.tool()
async def get_campaigns(request: CampaignsRequest) -> dict[str, Any]:
    """
    Fetch campaigns data from Google Ads.

    Retrieves campaign-level data including settings, budgets, status,
    and performance metrics. Used for campaign overlap analysis and
    Performance Max integration checks.
    """
    # TODO: Implement actual Google Ads API call
    return {
        "status": "success",
        "message": "Campaigns data retrieval not yet implemented",
        "request": request.model_dump(),
        "data": []
    }


@mcp.tool()
async def get_negative_keywords(request: NegativeKeywordsRequest) -> dict[str, Any]:
    """
    Fetch negative keywords from Google Ads campaigns.

    Retrieves all negative keywords at campaign and ad group level,
    including shared negative keyword lists. Essential for identifying
    conflicts where negative keywords block positive keywords.
    """
    # TODO: Implement actual Google Ads API call
    return {
        "status": "success",
        "message": "Negative keywords data retrieval not yet implemented",
        "request": request.model_dump(),
        "data": []
    }


@mcp.tool()
async def get_geo_performance(request: CampaignsRequest) -> dict[str, Any]:
    """
    Fetch geographic performance data from Google Ads.

    Retrieves performance metrics broken down by location (city, region, DMA).
    Critical for retail businesses to optimize local targeting and store
    performance analysis.
    """
    # TODO: Implement actual Google Ads API call
    return {
        "status": "success",
        "message": "Geographic performance data retrieval not yet implemented",
        "request": request.model_dump(),
        "data": []
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
            "query_preview": request.query[:100] + "..." if len(request.query) > 100 else request.query,
            "project_id": request.project_id
        },
        "data": []
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
            "query_bigquery"
        ]
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
                "api_version": "v17"
            },
            "bigquery": {
                "enabled": bool(os.getenv("GOOGLE_APPLICATION_CREDENTIALS")),
                "default_project": os.getenv("GCP_PROJECT_ID", "not-configured")
            },
            "caching": {
                "enabled": bool(os.getenv("REDIS_URL")),
                "backend": "redis" if os.getenv("REDIS_URL") else "memory"
            }
        }
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
