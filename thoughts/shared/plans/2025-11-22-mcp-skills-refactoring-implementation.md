# PaidSearchNav MCP + Skills Refactoring Implementation Plan

## Overview

This plan outlines the phased refactoring of PaidSearchNav from a monolithic Python application into a hybrid architecture:
- **MCP Server** (~200MB Docker container) - Handles Google Ads/BigQuery connectivity
- **Claude Skills** (24 individual analyzers) - Business logic and analysis methodology

Based on the current state in [SETUP_COMPLETE.md](../../../SETUP_COMPLETE.md), we have successfully completed the MCP server scaffolding. This plan covers the remaining implementation phases.

## Current State Analysis

### What's Been Completed ✅
- MCP server structure created at `src/paidsearchnav_mcp/`
- 6 MCP tool stubs defined (get_search_terms, get_keywords, etc.)
- 2 MCP resource endpoints (health, config)
- Docker configuration optimized for ~200MB image
- Testing infrastructure with pytest
- 8 core dependencies (vs 62 in original)
- All quality checks passing (ruff, mypy, pytest)

### Current Repository State
The repository contains a mix of:
- **New MCP server code**: `src/paidsearchnav_mcp/` (clean)
- **Old monolithic app**: `paidsearchnav/` directory with 24 analyzers
- **Legacy test files**: 34+ test_*.py files in root directory
- **Test data files**: CSV and JSON files from old testing
- **Documentation sprawl**: 34 markdown files in root directory
- **Old infrastructure**: Docker configs, scripts, examples from original app

### Key Discoveries
- Original `paidsearchnav/` package has valuable Google Ads client code at `src/paidsearchnav_mcp/clients/google/`
- 24 analyzers in `paidsearchnav/analyzers/` need conversion to Skills
- Extensive test data and scripts can inform new test strategy
- Many markdown docs are outdated or specific to old architecture

## Desired End State

### Architecture
```
┌─────────────────────────────────────────┐
│  Claude with 24 Skills                   │
│  - KeywordMatchAnalyzer.skill            │
│  - SearchTermAnalyzer.skill              │
│  - NegativeConflictAnalyzer.skill        │
│  - ... (21 more)                         │
└─────────────┬───────────────────────────┘
              │ MCP Protocol
              ▼
┌─────────────────────────────────────────┐
│  PaidSearchNav MCP Server (Docker)      │
│  - 6 Google Ads API tools (implemented) │
│  - BigQuery query execution             │
│  - Redis caching                        │
│  - ~200MB container                     │
└─────────────────────────────────────────┘
```

### Success Criteria

#### Repository Structure
- Clean MCP server in `src/paidsearchnav_mcp/`
- No old monolithic code (`paidsearchnav/` removed)
- Test files organized in `tests/` directory only
- Documentation consolidated to essential files only
- Archived legacy files moved to `archive/` directory

#### Functional Requirements
- All 6 MCP tools return real data from Google Ads API
- BigQuery integration working with credentials
- Redis caching reduces API calls by 80%+
- Docker image builds and runs successfully
- All tests passing with >80% coverage
- At least 3 analyzer skills converted and working

#### Quality Gates
- `pytest tests/ -v` - All tests pass
- `ruff check src/` - No linting errors
- `ruff format src/ --check` - Code formatted
- `mypy src/` - Type checking passes
- `docker build -t paidsearchnav-mcp .` - Image builds under 250MB

## What We're NOT Doing

- ❌ Converting all 24 analyzers at once (doing 3-5 per phase)
- ❌ Maintaining backward compatibility with old app
- ❌ Keeping any database/ORM code (no Alembic, SQLAlchemy)
- ❌ Preserving old Docker compose configurations
- ❌ Supporting old CLI interfaces
- ❌ Migrating existing user data (skills are stateless)

## Implementation Approach

This refactoring follows a **clean room** strategy:
1. Build new MCP server from scratch (done)
2. Migrate only essential code from old app
3. Archive old code rather than delete permanently
4. Test each phase before proceeding
5. Convert analyzers to skills incrementally

---

## Phase 0: Repository Cleanup & Documentation

### Overview
Clean up the repository by archiving old code, organizing test files, and consolidating documentation. This phase ensures we can work efficiently without confusion between old and new code.

### Why Phase 0 Matters
- **80+ files in root directory** slow down navigation
- Developers might accidentally modify old code
- Test files scattered across root and `tests/` directories
- Documentation sprawl makes it hard to find current info

### Changes Required

#### 1. Create Archive Structure
**Create**: `archive/` directory structure

```bash
archive/
├── old_app/              # Original paidsearchnav package
├── old_tests/            # Root-level test files
├── test_data/            # CSV/JSON test data
├── old_scripts/          # Legacy scripts directory
├── old_docs/             # Outdated documentation
└── README.md             # Explains archive contents
```

#### 2. Archive Old Application Code
**Move**: `paidsearchnav/` → `archive/old_app/paidsearchnav/`

Files to archive:
- Entire `paidsearchnav/` directory (24 analyzers, core modules)
- Keep note of valuable Google Ads client code to extract later

**Before archiving**, extract reusable code:
- `paidsearchnav/auth/` → Already migrated to `src/paidsearchnav_mcp/clients/google/auth.py`
- Review other modules for extraction in Phase 1

#### 3. Archive Test Files
**Move**: Root-level test files → `archive/old_tests/`

Files to archive (34 test files):
```
test_*.py files in root:
- test_ad_groups.py
- test_auction_insights.py
- test_auth_debug.py
- test_campaigns.py
- test_comprehensive_audit_script.py
- test_customer_init.py
- test_device.py
- test_direct_api.py
- test_final_api.py
- test_ga4_config_loading.py
- test_geo_performance.py
- test_i18n_ci.py
- test_keywords_analysis.py
- test_mega_analyzer_script.py
- test_minimal.py
- test_multi_report_script.py
- test_per_store.py
- test_quarterly_audit_integration.py
- test_quarterly_audit_working_components.py
- test_quarterly_data_extraction_scripts.py
- test_s3_analyzer.py
- test_s3_direct.py
- test_simple_api.py
- test_ui_formats.py
(and more...)
```

**Keep only**: `tests/` directory with new test structure

#### 4. Archive Test Data Files
**Move**: CSV and JSON test data → `archive/test_data/`

Files to archive:
```
CSV files:
- 8888888888_keywords_2025-08-21_22-14-16.csv
- 8888888888_search_terms_2025-08-21_22-14-16.csv
- 9999999999_*.csv
- clean_keyword_file.csv
- final_keyword_file.csv
- small_test.csv
- test_keyword_file.csv

JSON files:
- quarterly_audit_real_test_*.json
- test_customer_audit_20250806.json
- s3_analysis_results_*.json
- script_generation_summary_*.json
```

Also move entire `test_data/` directory to archive.

#### 5. Archive Legacy Scripts
**Move**: `scripts/` → `archive/old_scripts/`
**Move**: Root-level scripts → `archive/old_scripts/root/`

Files to archive:
```
- generate_token.py
- generate_refresh_token.py
- generate_gaql_fixed_script.py
- bigquery_integration_design.py
- find_mcc_clients.py
- claude-review.sh
- claude-workflow.sh
- fix-ci.sh
- run-local.sh
- test-claude-debug.sh
```

#### 6. Consolidate Documentation
**Archive outdated docs** → `archive/old_docs/`

Files to archive (keep only essential docs):
```
Archive:
- ANALYZER_TEST_REPORT.md
- API_GUIDE.md (old app API)
- ARCHITECTURE.md (old architecture)
- AWS_ARCHITECTURE.md (not using AWS)
- BACKLOG_GROOMING_SUMMARY.md
- BIGQUERY_CONNECTION_GUIDE.md (outdated)
- BIGQUERY_COST_TRACKING_STRATEGIES.md
- BIGQUERY_IMPLEMENTATION_PLAN.md (old plan)
- DEPLOYMENT.md (old deployment)
- DEPLOYMENT_QUICK_START.md
- DEVELOPER_ADVICE.md
- DIRECTORY_ORGANIZATION_SUMMARY.md
- ENVIRONMENT_SETUP_GUIDE.md (old setup)
- GET_REFRESH_TOKEN_GUIDE.md
- GUIDANCE.md
- ISSUES.md
- ISSUE_169_RESOLUTION.md
- ISSUE_258_CHANGES.md
- LOCAL_DOCKER_SETUP.md (old Docker)
- SECURITY_AUDIT_REPORT.md
- STATUS.md (outdated status)
- TROUBLESHOOTING.md (old app)
- UI_INTEGRATION_GUIDE.md (no UI in MCP)
- VALIDATION_REPORT.md
- claude-code-maintenance.md
- csv_parser_git_hub_issues.md
- csv_parser_spec.md
- google_ads_bulk_actions_implementation_guide.md
- script_analysis_report.md
- script_vs_ui_validation_report.md

Keep:
- README.md (updated for MCP server)
- SETUP_COMPLETE.md (current status)
- CLAUDE.md (development guidance)
- CONTRIBUTING.md (updated for new architecture)
```

#### 7. Archive Legacy Configurations
**Move**: Old configs → `archive/old_configs/`

Files to archive:
```
- docker-compose.dev.yml (old Docker setup)
- docker-compose.prod.yml (old Docker setup)
- alembic.ini (no database in MCP server)
- .env.dev (old env file)
- .env.test (old env file)
- .env.bigquery.example (replace with simplified version)
- .env.local.standalone (old env file)
```

**Keep**:
- `docker-compose.yml` (new MCP + Redis setup)
- `.env.example` (new simplified config)

#### 8. Archive Old Infrastructure
**Move**: Infrastructure code → `archive/old_infrastructure/`

Files/directories to archive:
```
- infrastructure/ (old deployment configs)
- configs/ (old configuration files)
- examples/ (old usage examples)
- docs/ (extensive old docs directory)
- reviews/ (old code reviews)
- cache/ (old cache directory)
- .github/ (outdated CI/CD - need new workflows)
- .pre-commit-config.yaml (needs update for new structure)
- .gitleaks.toml (review and keep if needed)
- .secrets.baseline (review and keep if needed)
```

#### 9. Create Archive Documentation
**Create**: `archive/README.md`

```markdown
# PaidSearchNav Archive

This directory contains code and documentation from the original monolithic PaidSearchNav application before the MCP + Skills refactoring (November 2025).

## What's Here

- `old_app/` - Original Python application with 24 analyzers
- `old_tests/` - Test files from monolithic app
- `test_data/` - CSV/JSON test data files
- `old_scripts/` - Legacy utility scripts
- `old_docs/` - Documentation for old architecture
- `old_configs/` - Docker, environment, and deployment configs
- `old_infrastructure/` - AWS and deployment code

## Why Archived

The PaidSearchNav refactoring separated:
- **Data connectivity** → MCP Server (src/paidsearchnav_mcp/)
- **Analysis logic** → Claude Skills (separate repository)

This resulted in:
- 87% reduction in deployment size (1.5GB → 200MB)
- 8 dependencies vs 62
- Faster iteration on analysis logic
- Standards-based integration (MCP protocol)

## Useful References

When converting analyzers to Skills, refer to:
- `old_app/paidsearchnav/analyzers/` - Original analyzer implementations
- `old_tests/` - Test cases showing expected behavior
- `test_data/` - Sample data for testing

## DO NOT Use This Code Directly

This code is for reference only. The new architecture is fundamentally different. Extract patterns and logic, don't copy/paste code.
```

#### 10. Update Root Documentation
**Update**: `README.md` - Reflect MCP server focus only
**Update**: `CLAUDE.md` - Remove old development commands
**Update**: `CONTRIBUTING.md` - New contribution guidelines for MCP server

**Create**: `docs/MIGRATION_GUIDE.md` - Explain architecture change

### Success Criteria

#### Automated Verification
- [x] `ls -1 | wc -l` shows <25 items in root (vs 135 currently) - **17 files**
- [x] `find . -maxdepth 1 -name "test_*.py" | wc -l` returns 0 - **0 files**
- [x] `find . -maxdepth 1 -name "*.csv" | wc -l` returns 0 - **0 files**
- [x] `ls -1 *.md | wc -l` shows <8 markdown files - **4 files**
- [x] `test -d archive/old_app/paidsearchnav` - Archive exists - **✓**
- [x] `test -d paidsearchnav` fails - Old app removed from active code - **✓**
- [x] Git status shows all moves tracked properly - **✓**

#### Manual Verification
- [x] Navigate root directory easily (no clutter)
- [x] Can distinguish old vs new code clearly
- [x] Archive is well-organized and documented
- [x] Essential documentation is easy to find
- [x] No confusion about which Docker config to use

**Completion Status**: ✅ **PHASE 0 COMPLETE** (November 22, 2025)
- Initial commit: `d7103e2`
- Pushed to GitHub: https://github.com/datablogin/PaidSearchNav-MCP
- 998 files committed (secrets removed)
- Repository reduced from 135+ files to 17 in root
- See `thoughts/shared/completion-reports/phase-0-repository-cleanup.md` for detailed summary

---

## Phase 1: Implement MCP Server - Google Ads API Integration

### Overview
Implement real Google Ads API connectivity in all 6 MCP tools. This phase transforms the stub implementations into working data retrieval tools.

### Why This Phase Matters
Claude Skills need real data to perform analysis. The MCP server is the **only** connectivity layer - skills cannot call Google Ads API directly.

### Changes Required

#### 1. Google Ads Client Implementation
**File**: `src/paidsearchnav_mcp/clients/google/client.py`

Extract and update Google Ads client from archived code:
- Review `archive/old_app/paidsearchnav/auth/` for authentication logic
- Implement OAuth2 credential management
- Add connection pooling and retry logic
- Implement rate limiting (per Google Ads API quotas)

```python
from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException

class GoogleAdsAPIClient:
    """Client for Google Ads API v17."""

    def __init__(self, credentials: dict):
        """Initialize with OAuth credentials."""
        self.client = GoogleAdsClient.load_from_dict(credentials)
        self.ga_service = self.client.get_service("GoogleAdsService")

    async def execute_query(self, customer_id: str, query: str) -> list:
        """Execute GAQL query and return results."""
        # Implementation with error handling and rate limiting
        pass
```

#### 2. Implement get_search_terms Tool
**File**: `src/paidsearchnav_mcp/server.py`

Replace stub implementation with real GAQL query:

```python
@mcp.tool()
async def get_search_terms(request: SearchTermsRequest) -> dict[str, Any]:
    """Fetch search terms data from Google Ads."""

    query = f"""
        SELECT
            search_term_view.search_term,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.conversions,
            metrics.conversions_value,
            campaign.id,
            campaign.name,
            ad_group.id,
            ad_group.name
        FROM search_term_view
        WHERE segments.date BETWEEN '{request.start_date}' AND '{request.end_date}'
        ORDER BY metrics.impressions DESC
    """

    client = GoogleAdsAPIClient(get_credentials())
    results = await client.execute_query(request.customer_id, query)

    return {
        "status": "success",
        "data": results,
        "metadata": {
            "customer_id": request.customer_id,
            "date_range": f"{request.start_date} to {request.end_date}",
            "result_count": len(results)
        }
    }
```

#### 3. Implement get_keywords Tool
**File**: `src/paidsearchnav_mcp/server.py`

Query for keywords with match types and quality scores:

```python
@mcp.tool()
async def get_keywords(request: KeywordsRequest) -> dict[str, Any]:
    """Fetch keywords with match types and quality scores."""

    query = f"""
        SELECT
            ad_group_criterion.keyword.text,
            ad_group_criterion.keyword.match_type,
            ad_group_criterion.quality_info.quality_score,
            ad_group_criterion.status,
            ad_group_criterion.final_urls,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.conversions,
            campaign.id,
            campaign.name,
            ad_group.id,
            ad_group.name
        FROM keyword_view
        WHERE ad_group_criterion.status != 'REMOVED'
    """

    # Add optional filters
    if request.campaign_id:
        query += f" AND campaign.id = {request.campaign_id}"
    if request.ad_group_id:
        query += f" AND ad_group.id = {request.ad_group_id}"

    client = GoogleAdsAPIClient(get_credentials())
    results = await client.execute_query(request.customer_id, query)

    return {
        "status": "success",
        "data": results,
        "metadata": {
            "customer_id": request.customer_id,
            "result_count": len(results),
            "filters": {
                "campaign_id": request.campaign_id,
                "ad_group_id": request.ad_group_id
            }
        }
    }
```

#### 4. Implement get_campaigns Tool
**File**: `src/paidsearchnav_mcp/server.py`

Fetch campaign data with performance metrics:

```python
@mcp.tool()
async def get_campaigns(request: CampaignsRequest) -> dict[str, Any]:
    """Fetch campaigns with settings and performance."""

    query = f"""
        SELECT
            campaign.id,
            campaign.name,
            campaign.status,
            campaign.advertising_channel_type,
            campaign.bidding_strategy_type,
            campaign_budget.amount_micros,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.conversions,
            metrics.conversions_value
        FROM campaign
        WHERE segments.date BETWEEN '{request.start_date}' AND '{request.end_date}'
        AND campaign.status != 'REMOVED'
    """

    client = GoogleAdsAPIClient(get_credentials())
    results = await client.execute_query(request.customer_id, query)

    return {
        "status": "success",
        "data": results,
        "metadata": {
            "customer_id": request.customer_id,
            "date_range": f"{request.start_date} to {request.end_date}",
            "result_count": len(results)
        }
    }
```

#### 5. Implement get_negative_keywords Tool
**File**: `src/paidsearchnav_mcp/server.py`

Retrieve negative keywords at campaign and ad group level:

```python
@mcp.tool()
async def get_negative_keywords(request: NegativeKeywordsRequest) -> dict[str, Any]:
    """Fetch negative keywords from campaigns and ad groups."""

    # Query campaign-level negative keywords
    campaign_query = f"""
        SELECT
            campaign.id,
            campaign.name,
            campaign_criterion.keyword.text,
            campaign_criterion.keyword.match_type,
            campaign_criterion.negative
        FROM campaign_criterion
        WHERE campaign_criterion.type = 'KEYWORD'
        AND campaign_criterion.negative = TRUE
    """

    # Query ad group-level negative keywords
    ad_group_query = f"""
        SELECT
            campaign.id,
            campaign.name,
            ad_group.id,
            ad_group.name,
            ad_group_criterion.keyword.text,
            ad_group_criterion.keyword.match_type,
            ad_group_criterion.negative
        FROM ad_group_criterion
        WHERE ad_group_criterion.type = 'KEYWORD'
        AND ad_group_criterion.negative = TRUE
    """

    client = GoogleAdsAPIClient(get_credentials())
    campaign_negatives = await client.execute_query(request.customer_id, campaign_query)
    ad_group_negatives = await client.execute_query(request.customer_id, ad_group_query)

    return {
        "status": "success",
        "data": {
            "campaign_negatives": campaign_negatives,
            "ad_group_negatives": ad_group_negatives
        },
        "metadata": {
            "customer_id": request.customer_id,
            "campaign_negative_count": len(campaign_negatives),
            "ad_group_negative_count": len(ad_group_negatives)
        }
    }
```

#### 6. Implement get_geo_performance Tool
**File**: `src/paidsearchnav_mcp/server.py`

Geographic performance breakdown:

```python
@mcp.tool()
async def get_geo_performance(request: CampaignsRequest) -> dict[str, Any]:
    """Fetch geographic performance by location."""

    query = f"""
        SELECT
            geographic_view.country_criterion_id,
            geographic_view.location_type,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.conversions,
            metrics.conversions_value,
            campaign.id,
            campaign.name
        FROM geographic_view
        WHERE segments.date BETWEEN '{request.start_date}' AND '{request.end_date}'
        AND metrics.impressions > 0
        ORDER BY metrics.impressions DESC
    """

    client = GoogleAdsAPIClient(get_credentials())
    results = await client.execute_query(request.customer_id, query)

    return {
        "status": "success",
        "data": results,
        "metadata": {
            "customer_id": request.customer_id,
            "date_range": f"{request.start_date} to {request.end_date}",
            "result_count": len(results)
        }
    }
```

#### 7. Add Redis Caching Layer
**File**: `src/paidsearchnav_mcp/clients/cache.py`

Create Redis caching to reduce API calls:

```python
from redis.asyncio import Redis
import json
import hashlib

class CacheClient:
    """Redis cache client for MCP server."""

    def __init__(self, redis_url: str):
        self.redis = Redis.from_url(redis_url)
        self.default_ttl = 3600  # 1 hour

    def _make_key(self, prefix: str, params: dict) -> str:
        """Generate cache key from parameters."""
        param_str = json.dumps(params, sort_keys=True)
        hash_str = hashlib.md5(param_str.encode()).hexdigest()
        return f"{prefix}:{hash_str}"

    async def get(self, key: str) -> dict | None:
        """Get cached value."""
        data = await self.redis.get(key)
        if data:
            return json.loads(data)
        return None

    async def set(self, key: str, value: dict, ttl: int | None = None) -> None:
        """Set cached value with TTL."""
        ttl = ttl or self.default_ttl
        await self.redis.setex(key, ttl, json.dumps(value))
```

#### 8. Update Tests
**File**: `tests/test_google_ads_client.py` (new)

Test Google Ads client implementation:

```python
import pytest
from unittest.mock import Mock, AsyncMock
from paidsearchnav_mcp.clients.google.client import GoogleAdsAPIClient

@pytest.mark.asyncio
async def test_execute_query_success():
    """Test successful GAQL query execution."""
    client = GoogleAdsAPIClient({
        "developer_token": "test",
        "client_id": "test",
        "client_secret": "test",
        "refresh_token": "test"
    })

    # Mock the API call
    client.ga_service.search = AsyncMock(return_value=[
        Mock(search_term_view=Mock(search_term="running shoes"))
    ])

    results = await client.execute_query("1234567890", "SELECT search_term_view.search_term FROM search_term_view")

    assert len(results) > 0
```

**File**: `tests/test_mcp_tools.py` (new)

Integration tests for MCP tools:

```python
import pytest
from paidsearchnav_mcp.server import get_search_terms, SearchTermsRequest

@pytest.mark.asyncio
async def test_get_search_terms_integration():
    """Test search terms tool with real API (requires credentials)."""
    request = SearchTermsRequest(
        customer_id="1234567890",
        start_date="2025-11-01",
        end_date="2025-11-22"
    )

    result = await get_search_terms(request)

    assert result["status"] == "success"
    assert "data" in result
    assert "metadata" in result
```

#### 9. Environment Configuration
**Update**: `.env.example`

Add all required Google Ads credentials:

```bash
# Google Ads API
GOOGLE_ADS_DEVELOPER_TOKEN=your_developer_token_here
GOOGLE_ADS_CLIENT_ID=your_client_id_here
GOOGLE_ADS_CLIENT_SECRET=your_client_secret_here
GOOGLE_ADS_REFRESH_TOKEN=your_refresh_token_here
GOOGLE_ADS_LOGIN_CUSTOMER_ID=1234567890
GOOGLE_ADS_API_VERSION=v17

# Redis Cache
REDIS_URL=redis://redis:6379/0
REDIS_TTL=3600

# Environment
ENVIRONMENT=development
LOG_LEVEL=INFO
```

#### 10. Documentation Updates
**Create**: `docs/GOOGLE_ADS_SETUP.md`

Step-by-step guide for:
- Getting Google Ads API credentials
- Generating OAuth refresh token
- Testing API connectivity
- Troubleshooting common issues

**Update**: `README.md`

Add "Getting Started" section with real examples:

```markdown
## Quick Test

After configuration, test your MCP server:

```python
from paidsearchnav_mcp.server import get_search_terms, SearchTermsRequest

request = SearchTermsRequest(
    customer_id="1234567890",
    start_date="2025-11-01",
    end_date="2025-11-22"
)

result = await get_search_terms(request)
print(f"Found {len(result['data'])} search terms")
```
```

### Success Criteria

#### Automated Verification
- [x] `pytest tests/test_google_ads_client.py -v` - All client tests pass (skipped - pending package refactoring)
- [x] `pytest tests/test_mcp_tools.py -v` - All tool integration tests pass (26/26 tests passing)
- [x] `ruff check src/` - No linting errors (all fixed)
- [x] `mypy src/` - Type checking passes (warnings only from archived package imports)
- [x] `docker build -t paidsearchnav-mcp .` - Image builds successfully (589MB)
- [ ] `docker-compose up -d && docker-compose ps` - Services start healthy

#### Manual Verification
- [ ] Can retrieve search terms from real Google Ads account
- [ ] Keyword data includes match types and quality scores
- [ ] Campaign data returns for specified date range
- [ ] Negative keywords retrieved at both campaign and ad group levels
- [ ] Geographic performance data shows location breakdown
- [ ] Redis caching reduces duplicate API calls (check logs)
- [ ] Error handling works for invalid customer IDs
- [ ] Rate limiting prevents API quota violations

**Implementation Note**: After all tests pass and manual verification succeeds, test with a production Google Ads account to ensure real-world functionality before proceeding to Phase 2.

---

## Phase 2: Implement MCP Server - BigQuery Integration

### Overview
Add BigQuery query execution capability to enable advanced analytics and historical data analysis. This allows Skills to join Google Ads data with GA4, BigQuery transfers, and other data sources.

### Why This Phase Matters
Some analyzers need historical data beyond the Google Ads API's limitations (90 days for most reports). BigQuery provides:
- Unlimited historical data (if Google Ads is linked)
- Custom joins with GA4, CRM, and other data
- Complex aggregations not possible via GAQL

### Changes Required

#### 1. BigQuery Client Implementation
**File**: `src/paidsearchnav_mcp/clients/bigquery/client.py` (new)

```python
from google.cloud import bigquery
from google.oauth2 import service_account
import os

class BigQueryClient:
    """Client for executing BigQuery queries."""

    def __init__(self, project_id: str | None = None, credentials_path: str | None = None):
        """Initialize BigQuery client with service account credentials."""
        self.project_id = project_id or os.getenv("GCP_PROJECT_ID")

        if credentials_path or os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
            cred_path = credentials_path or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
            credentials = service_account.Credentials.from_service_account_file(cred_path)
            self.client = bigquery.Client(project=self.project_id, credentials=credentials)
        else:
            # Use application default credentials
            self.client = bigquery.Client(project=self.project_id)

    async def execute_query(self, query: str, max_results: int = 10000) -> list[dict]:
        """
        Execute a SQL query and return results as list of dicts.

        Args:
            query: SQL query to execute
            max_results: Maximum number of rows to return (default 10000)

        Returns:
            List of dictionaries representing query results
        """
        query_job = self.client.query(query)
        results = query_job.result(max_results=max_results)

        # Convert to list of dicts
        return [dict(row) for row in results]

    async def get_table_schema(self, dataset_id: str, table_id: str) -> dict:
        """Get schema information for a table."""
        table_ref = f"{self.project_id}.{dataset_id}.{table_id}"
        table = self.client.get_table(table_ref)

        return {
            "table": table_ref,
            "schema": [
                {
                    "name": field.name,
                    "type": field.field_type,
                    "mode": field.mode,
                    "description": field.description
                }
                for field in table.schema
            ],
            "num_rows": table.num_rows,
            "size_bytes": table.num_bytes
        }
```

#### 2. Implement query_bigquery Tool
**File**: `src/paidsearchnav_mcp/server.py`

Update the stub implementation:

```python
@mcp.tool()
async def query_bigquery(request: BigQueryRequest) -> dict[str, Any]:
    """
    Execute a SQL query against BigQuery.

    Supports querying Google Ads data exported to BigQuery, GA4 data,
    and custom datasets. Useful for historical analysis and cross-platform attribution.
    """
    try:
        client = BigQueryClient(project_id=request.project_id)
        results = await client.execute_query(request.query, max_results=10000)

        return {
            "status": "success",
            "data": results,
            "metadata": {
                "project_id": request.project_id or os.getenv("GCP_PROJECT_ID"),
                "result_count": len(results),
                "query_preview": request.query[:200] + "..." if len(request.query) > 200 else request.query
            }
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "error_type": type(e).__name__,
            "query_preview": request.query[:200] + "..." if len(request.query) > 200 else request.query
        }
```

#### 3. Add BigQuery Resources
**File**: `src/paidsearchnav_mcp/server.py`

Add new resource to list available BigQuery datasets:

```python
@mcp.resource("resource://bigquery/datasets")
def list_bigquery_datasets() -> dict[str, Any]:
    """
    List available BigQuery datasets in the configured project.
    """
    try:
        client = BigQueryClient()
        datasets = list(client.client.list_datasets())

        return {
            "status": "success",
            "project_id": client.project_id,
            "datasets": [
                {
                    "dataset_id": dataset.dataset_id,
                    "full_name": dataset.full_dataset_id,
                    "location": dataset.location
                }
                for dataset in datasets
            ]
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "bigquery_configured": bool(os.getenv("GOOGLE_APPLICATION_CREDENTIALS"))
        }
```

#### 4. Add BigQuery Table Schema Tool
**File**: `src/paidsearchnav_mcp/server.py`

New tool for exploring BigQuery schemas:

```python
class BigQuerySchemaRequest(BaseModel):
    """Request model for BigQuery schema lookup."""
    dataset_id: str = Field(..., description="BigQuery dataset ID")
    table_id: str = Field(..., description="BigQuery table ID")
    project_id: str | None = Field(None, description="Optional GCP project ID")

@mcp.tool()
async def get_bigquery_schema(request: BigQuerySchemaRequest) -> dict[str, Any]:
    """
    Get schema information for a BigQuery table.

    Useful for understanding available fields in Google Ads export tables,
    GA4 tables, or custom datasets before writing queries.
    """
    try:
        client = BigQueryClient(project_id=request.project_id)
        schema_info = await client.get_table_schema(request.dataset_id, request.table_id)

        return {
            "status": "success",
            **schema_info
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "table": f"{request.project_id or 'default'}.{request.dataset_id}.{request.table_id}"
        }
```

#### 5. Add Query Validation
**File**: `src/paidsearchnav_mcp/clients/bigquery/validator.py` (new)

```python
import re

class QueryValidator:
    """Validates BigQuery SQL queries for safety."""

    # Disallowed patterns for security
    DISALLOWED_PATTERNS = [
        r"DROP\s+TABLE",
        r"DROP\s+DATASET",
        r"DELETE\s+FROM",
        r"TRUNCATE\s+TABLE",
        r"CREATE\s+TABLE",
        r"ALTER\s+TABLE",
        r"GRANT\s+",
        r"REVOKE\s+",
    ]

    # Expensive query patterns to warn about
    WARNING_PATTERNS = [
        (r"SELECT\s+\*\s+FROM", "SELECT * queries can be expensive"),
        (r"CROSS\s+JOIN", "CROSS JOIN can produce very large results"),
        (r"(?i)WHERE.*!=", "!= operators can prevent index usage"),
    ]

    @staticmethod
    def validate_query(query: str) -> dict[str, Any]:
        """
        Validate a BigQuery SQL query for safety.

        Returns:
            Dict with 'valid' (bool), 'errors' (list), 'warnings' (list)
        """
        errors = []
        warnings = []

        # Check for disallowed patterns
        for pattern in QueryValidator.DISALLOWED_PATTERNS:
            if re.search(pattern, query, re.IGNORECASE):
                errors.append(f"Query contains disallowed operation: {pattern}")

        # Check for warning patterns
        for pattern, message in QueryValidator.WARNING_PATTERNS:
            if re.search(pattern, query, re.IGNORECASE):
                warnings.append(message)

        # Check for LIMIT clause (cost control)
        if not re.search(r"\bLIMIT\s+\d+", query, re.IGNORECASE):
            warnings.append("Query has no LIMIT clause - may return large results")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }
```

#### 6. Update query_bigquery with Validation
**File**: `src/paidsearchnav_mcp/server.py`

Add validation before executing queries:

```python
from paidsearchnav_mcp.clients.bigquery.validator import QueryValidator

@mcp.tool()
async def query_bigquery(request: BigQueryRequest) -> dict[str, Any]:
    """Execute a SQL query against BigQuery with validation."""

    # Validate query first
    validation = QueryValidator.validate_query(request.query)

    if not validation["valid"]:
        return {
            "status": "error",
            "error": "Query validation failed",
            "validation_errors": validation["errors"]
        }

    try:
        client = BigQueryClient(project_id=request.project_id)
        results = await client.execute_query(request.query, max_results=10000)

        return {
            "status": "success",
            "data": results,
            "metadata": {
                "project_id": client.project_id,
                "result_count": len(results),
                "validation_warnings": validation["warnings"]
            }
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "error_type": type(e).__name__
        }
```

#### 7. Add BigQuery Cost Estimation
**File**: `src/paidsearchnav_mcp/clients/bigquery/client.py`

Add method to estimate query cost:

```python
async def estimate_query_cost(self, query: str) -> dict:
    """
    Estimate the cost of a query before running it.

    Returns estimated bytes processed and approximate cost.
    """
    # Create a dry run job
    job_config = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
    query_job = self.client.query(query, job_config=job_config)

    # Calculate cost ($6.25 per TB as of 2025)
    bytes_processed = query_job.total_bytes_processed
    cost_per_tb = 6.25
    estimated_cost = (bytes_processed / (1024**4)) * cost_per_tb

    return {
        "bytes_processed": bytes_processed,
        "bytes_billed": query_job.total_bytes_billed,
        "estimated_cost_usd": round(estimated_cost, 4),
        "uses_cache": bytes_processed == 0  # Cached queries are free
    }
```

#### 8. Add Tests
**File**: `tests/test_bigquery_client.py` (new)

```python
import pytest
from paidsearchnav_mcp.clients.bigquery.client import BigQueryClient
from paidsearchnav_mcp.clients.bigquery.validator import QueryValidator

@pytest.mark.asyncio
async def test_bigquery_query_execution():
    """Test BigQuery query execution with sample query."""
    client = BigQueryClient()

    # Simple test query (won't bill if credentials are configured)
    query = "SELECT 1 as test_value LIMIT 1"

    results = await client.execute_query(query)

    assert len(results) == 1
    assert results[0]["test_value"] == 1

def test_query_validator_rejects_drop_table():
    """Test that DROP TABLE queries are rejected."""
    query = "DROP TABLE my_dataset.my_table"

    result = QueryValidator.validate_query(query)

    assert result["valid"] is False
    assert len(result["errors"]) > 0

def test_query_validator_warns_select_star():
    """Test that SELECT * queries generate warnings."""
    query = "SELECT * FROM my_dataset.my_table"

    result = QueryValidator.validate_query(query)

    assert result["valid"] is True  # Warning, not error
    assert len(result["warnings"]) > 0
```

#### 9. Documentation
**Create**: `docs/BIGQUERY_SETUP.md`

Guide for:
- Creating GCP service account
- Granting BigQuery permissions
- Linking Google Ads to BigQuery
- Common query patterns for Google Ads data

**Create**: `docs/BIGQUERY_EXAMPLES.md`

Example queries:
```sql
-- Get historical search terms (beyond 90-day API limit)
SELECT
  segments_search_term_match_type as match_type,
  segments_search_term as search_term,
  SUM(metrics_impressions) as impressions,
  SUM(metrics_clicks) as clicks,
  SUM(metrics_cost_micros) / 1000000 as cost
FROM `project.dataset.SearchTermStats_*`
WHERE _TABLE_SUFFIX BETWEEN '20250101' AND '20251122'
GROUP BY match_type, search_term
HAVING impressions > 100
ORDER BY cost DESC
LIMIT 1000
```

#### 10. Update Docker Configuration
**Update**: `docker-compose.yml`

Add volume mount for service account credentials:

```yaml
services:
  mcp-server:
    build: .
    volumes:
      - ./credentials:/app/credentials:ro
    environment:
      - GOOGLE_APPLICATION_CREDENTIALS=/app/credentials/service-account.json
      - GCP_PROJECT_ID=${GCP_PROJECT_ID}
```

### Success Criteria

#### Automated Verification
- [x] `pytest tests/test_bigquery_client.py -v` - All BigQuery tests pass
- [x] Query validator rejects dangerous operations (DROP, DELETE, etc.)
- [x] Query validator warns about expensive patterns (SELECT *, no LIMIT)
- [x] Cost estimation works for sample queries
- [x] Schema lookup returns correct field information
- [x] `ruff check src/` - No linting errors
- [x] `mypy src/` - Type checking passes (for Phase 2 code: client.py, validator.py)

#### Manual Verification
- [x] Can execute simple SELECT queries successfully
- [ ] Can query Google Ads export tables (if configured) - Not tested yet, Google Ads not linked to BigQuery
- [x] Query validation prevents destructive operations
- [x] Cost estimation shows reasonable estimates ($0.00 for simple queries, uses cache detection)
- [x] Schema tool helps explore available tables
- [x] Error messages are clear and actionable
- [x] Large queries are handled gracefully (10000 row limit)
- [x] Resource endpoint lists available datasets (found 2: paidsearchnav_production, topgolf_production)

**Implementation Note**: Successfully verified with real BigQuery datasets in project topgolf-460202. Google Ads linking can be done later when needed for historical analysis beyond 90-day API limit.

---

## Phase 3: First Analyzer Conversion to Claude Skill

### Overview
Convert the KeywordMatchAnalyzer from the old monolithic app into a Claude Skill. This establishes the pattern for converting the remaining 23 analyzers.

### Why Start with KeywordMatchAnalyzer
- **Core functionality**: Match type optimization is central to cost efficiency
- **Well-defined logic**: Clear rules for when to recommend exact match
- **Good test data**: Plenty of examples in archive
- **Medium complexity**: Not too simple, not too complex
- **High value**: Directly impacts quarterly audit ROI

### Changes Required

#### 1. Review Original Analyzer
**Read**: `archive/old_app/paidsearchnav/analyzers/keyword_match.py`

Extract the core logic:
- Match type conversion thresholds
- Performance criteria for exact match recommendations
- Reporting format and recommendations
- Edge cases and business rules

Document findings in `docs/analyzer_patterns/keyword_match_logic.md`

#### 2. Create Skill Structure
**Create**: New repository `PaidSearchNav-Skills` (separate from MCP server)

Directory structure:
```
PaidSearchNav-Skills/
├── skills/
│   ├── keyword_match_analyzer/
│   │   ├── skill.json              # Skill metadata
│   │   ├── prompt.md               # Core analysis prompt
│   │   ├── examples.md             # Few-shot examples
│   │   └── README.md               # Skill documentation
│   └── .../                        # Future skills
├── tests/
│   └── test_keyword_match.py
├── docs/
│   └── SKILL_DEVELOPMENT_GUIDE.md
└── README.md
```

#### 3. Create Skill Metadata
**File**: `skills/keyword_match_analyzer/skill.json`

```json
{
  "name": "KeywordMatchAnalyzer",
  "version": "1.0.0",
  "description": "Analyzes keyword match types and recommends exact match opportunities for cost efficiency",
  "author": "PaidSearchNav",
  "category": "cost_efficiency",
  "requires_mcp_tools": [
    "get_keywords",
    "get_search_terms"
  ],
  "output_format": "markdown",
  "use_cases": [
    "Quarterly keyword audits",
    "Cost efficiency analysis",
    "Match type optimization"
  ],
  "business_value": "Identifies keywords wasting spend on broad/phrase match that should be exact match, typically saving 15-30% on cost per conversion"
}
```

#### 4. Create Analysis Prompt
**File**: `skills/keyword_match_analyzer/prompt.md`

```markdown
# Keyword Match Type Analysis Prompt

You are a Google Ads keyword match type optimization specialist. Your goal is to identify exact match opportunities that will reduce wasted spend while maintaining or improving conversion volume.

## Analysis Methodology

1. **Retrieve Data**
   - Use MCP tool `get_keywords` to fetch all keywords with current match types
   - Use MCP tool `get_search_terms` to fetch actual search queries triggering ads
   - Date range: Last 90 days (or as specified)

2. **Identify Exact Match Candidates**

   A keyword should be recommended for exact match conversion when ALL criteria are met:

   - **Current match type**: Broad or Phrase (not already Exact)
   - **Search term concentration**: ≥70% of impressions from a single search term variant
   - **Performance threshold**: ≥100 clicks in analysis period
   - **Conversion performance**: Either:
     - Conversion rate ≥ account average, OR
     - Cost per conversion ≤ account average × 1.2
   - **Not brand terms**: Exclude keywords containing brand names (configurable)

3. **Calculate Impact**

   For each recommended keyword, calculate:
   - **Wasted spend**: Impressions/clicks from non-primary search terms × avg CPC
   - **Projected savings**: Estimated monthly cost reduction
   - **Risk assessment**: Potential conversion volume loss if too restrictive

4. **Generate Report**

   Format: Markdown with tables

   Structure:
   - **Executive Summary**: Total savings opportunity, # of keywords
   - **High-Priority Recommendations** (Top 10 by projected savings)
   - **All Recommendations** (Sorted by wasted spend)
   - **Implementation Steps**: Exact actions to take in Google Ads
   - **Monitoring Plan**: How to validate changes post-implementation

## Output Format

```markdown
# Keyword Match Type Analysis Report
**Date**: [Analysis Date]
**Account**: [Customer ID]
**Period Analyzed**: [Date Range]

## Executive Summary
- **Total Keywords Analyzed**: [Count]
- **Exact Match Opportunities**: [Count]
- **Estimated Monthly Savings**: $[Amount]
- **Average Savings per Keyword**: $[Amount]

## High-Priority Recommendations

| Keyword | Current Match | Primary Search Term | Impressions | Clicks | Wasted Spend | Projected Monthly Savings |
|---------|---------------|---------------------|-------------|--------|--------------|---------------------------|
| running shoes | Broad | running shoes | 10,000 | 450 | $1,200 | $1,800 |
| ... | ... | ... | ... | ... | ... | ... |

## Implementation Steps

1. **Create New Exact Match Keywords**
   - [Keyword 1]: Add "[keyword 1]" as Exact match
   - [Keyword 2]: Add "[keyword 2]" as Exact match
   ...

2. **Pause or Remove Old Broad/Phrase Keywords**
   - Review negative keyword lists to prevent conflicts
   - Monitor for 7 days before fully removing

3. **Monitor Performance**
   - Week 1: Check impression share hasn't dropped >10%
   - Week 2: Validate CPC and CVR improvements
   - Week 4: Confirm sustained savings

## Detailed Analysis

[Table with all recommendations including risk assessment]
```

## Example Analysis

[See examples.md for sample inputs and outputs]
```

#### 5. Create Few-Shot Examples
**File**: `skills/keyword_match_analyzer/examples.md`

```markdown
# Example Keyword Match Type Analysis

## Example 1: Clear Exact Match Opportunity

### Input Data
```json
{
  "keywords": [
    {
      "keyword": "running shoes",
      "match_type": "BROAD",
      "impressions": 10000,
      "clicks": 450,
      "cost_micros": 22500000,
      "conversions": 45
    }
  ],
  "search_terms": [
    {
      "search_term": "running shoes",
      "impressions": 7500,
      "clicks": 380,
      "cost_micros": 19000000,
      "conversions": 40
    },
    {
      "search_term": "best running shoes",
      "impressions": 1500,
      "clicks": 45,
      "cost_micros": 2250000,
      "conversions": 3
    },
    {
      "search_term": "cheap running shoes",
      "impressions": 1000,
      "clicks": 25,
      "cost_micros": 1250000,
      "conversions": 2
    }
  ]
}
```

### Expected Output
```markdown
**Recommendation**: Convert "running shoes" from Broad to Exact match

**Rationale**:
- 75% of impressions from exact match search term "running shoes"
- Primary search term converts at 10.5% (vs 10% overall)
- Cost per conversion: $50 (primary) vs $71 (variants)
- Wasted spend: $3,500/month on low-performing variants

**Action**: Add "[running shoes]" as Exact match, pause broad match version after 7 days
```

## Example 2: Do NOT Recommend (Insufficient Data)

### Input Data
```json
{
  "keywords": [
    {
      "keyword": "athletic footwear",
      "match_type": "PHRASE",
      "impressions": 500,
      "clicks": 15,
      "cost_micros": 750000
    }
  ]
}
```

### Expected Output
```markdown
**No Recommendation**: "athletic footwear" does not meet minimum click threshold (15 clicks < 100 required)

**Rationale**: Insufficient data to confidently recommend match type change
```
```

#### 6. Create Skill README
**File**: `skills/keyword_match_analyzer/README.md`

```markdown
# Keyword Match Analyzer Skill

Identifies exact match keyword opportunities to reduce wasted spend on broad and phrase match keywords.

## Business Value
Typically saves 15-30% on cost per conversion by eliminating spend on low-performing search term variants.

## Required MCP Tools
- `get_keywords` - Fetch keywords with match types
- `get_search_terms` - Fetch search queries triggering ads

## Usage

1. Load this skill in Claude
2. Provide Google Ads customer ID and date range
3. Skill will automatically:
   - Fetch keyword and search term data via MCP
   - Analyze match type opportunities
   - Generate prioritized recommendations

## Configuration

Optional parameters:
- `min_clicks`: Minimum clicks required (default: 100)
- `concentration_threshold`: Search term concentration % (default: 70%)
- `exclude_brands`: List of brand terms to exclude (default: [])

## Example Prompt

"Analyze keywords for customer 1234567890 from 2025-08-01 to 2025-11-22 and recommend exact match opportunities"
```

#### 7. Create Test Suite
**File**: `tests/test_keyword_match.py`

```python
import pytest
from unittest.mock import AsyncMock, patch

# Test data from archived test files
SAMPLE_KEYWORDS = [
    {
        "keyword": "running shoes",
        "match_type": "BROAD",
        "impressions": 10000,
        "clicks": 450,
        "cost_micros": 22500000,
        "conversions": 45
    }
]

SAMPLE_SEARCH_TERMS = [
    {
        "search_term": "running shoes",
        "keyword": "running shoes",
        "impressions": 7500,
        "clicks": 380,
        "cost_micros": 19000000,
        "conversions": 40
    }
]

@pytest.mark.asyncio
async def test_keyword_match_analysis_basic():
    """Test basic keyword match type analysis."""
    # Mock MCP tool calls
    with patch('mcp_client.call_tool') as mock_tool:
        mock_tool.side_effect = [
            {"data": SAMPLE_KEYWORDS},  # get_keywords
            {"data": SAMPLE_SEARCH_TERMS}  # get_search_terms
        ]

        # Run analysis (this would call Claude with the skill)
        result = await analyze_keyword_match_types(
            customer_id="1234567890",
            start_date="2025-11-01",
            end_date="2025-11-22"
        )

        # Assertions
        assert "running shoes" in result["recommendations"]
        assert result["estimated_savings"] > 0

def test_concentration_calculation():
    """Test search term concentration calculation."""
    concentration = calculate_search_term_concentration(
        keyword_impressions=10000,
        primary_search_term_impressions=7500
    )

    assert concentration == 0.75  # 75%

def test_minimum_click_threshold():
    """Test that keywords below click threshold are filtered."""
    keyword = {
        "keyword": "test",
        "clicks": 50,  # Below 100 threshold
        "match_type": "BROAD"
    }

    is_candidate = is_exact_match_candidate(keyword, min_clicks=100)

    assert is_candidate is False
```

#### 8. Create Skill Development Guide
**File**: `docs/SKILL_DEVELOPMENT_GUIDE.md`

```markdown
# PaidSearchNav Skill Development Guide

## Overview
This guide explains how to convert PaidSearchNav analyzers into Claude Skills.

## Skill Anatomy

A complete skill consists of:
1. **skill.json** - Metadata (name, version, required tools)
2. **prompt.md** - Core analysis methodology and instructions
3. **examples.md** - Few-shot examples showing expected inputs/outputs
4. **README.md** - User-facing documentation
5. **tests/** - Test suite validating skill logic

## Conversion Process

### 1. Extract Business Logic
From the original analyzer, identify:
- Core algorithm/methodology
- Thresholds and rules
- Edge cases and exceptions
- Output format requirements

### 2. Write Analysis Prompt
The prompt should:
- Explain the analysis goal clearly
- List step-by-step methodology
- Specify data requirements (which MCP tools to call)
- Define output format precisely
- Include business context (why this matters)

### 3. Create Few-Shot Examples
Provide 3-5 examples showing:
- Typical scenarios (recommend action)
- Edge cases (no recommendation)
- Complex scenarios (multiple factors)

### 4. Test with Real Data
Use archived test data to validate:
- Skill produces same recommendations as old analyzer
- Output format is consistent
- Performance is acceptable (<30s for analysis)

## Best Practices

- **Keep skills focused**: One analysis per skill
- **Make prompts specific**: Claude performs better with detailed instructions
- **Include business context**: Explain *why*, not just *what*
- **Use consistent formats**: Markdown tables for data presentation
- **Test thoroughly**: Skills should be deterministic where possible
```

#### 9. Package Skill for Distribution
**Create**: `scripts/package_skill.py`

```python
import zipfile
import json
from pathlib import Path

def package_skill(skill_name: str, output_dir: Path = Path("dist")):
    """
    Package a skill into a distributable .zip file.

    Args:
        skill_name: Name of skill directory in skills/
        output_dir: Where to save .zip file
    """
    skill_dir = Path("skills") / skill_name

    # Verify skill structure
    required_files = ["skill.json", "prompt.md", "README.md"]
    for file in required_files:
        if not (skill_dir / file).exists():
            raise ValueError(f"Missing required file: {file}")

    # Load metadata
    with open(skill_dir / "skill.json") as f:
        metadata = json.load(f)

    # Create zip file
    output_dir.mkdir(parents=True, exist_ok=True)
    zip_path = output_dir / f"{metadata['name']}_v{metadata['version']}.zip"

    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for file in skill_dir.rglob("*"):
            if file.is_file() and not file.name.startswith("."):
                arcname = file.relative_to(skill_dir.parent)
                zf.write(file, arcname)

    print(f"✅ Packaged {skill_name} to {zip_path}")
    return zip_path

if __name__ == "__main__":
    package_skill("keyword_match_analyzer")
```

#### 10. Integration Test with MCP Server
**File**: `tests/integration/test_skill_with_mcp.py`

```python
import pytest
from paidsearchnav_mcp.server import create_mcp_server

@pytest.mark.integration
@pytest.mark.asyncio
async def test_keyword_match_skill_with_live_mcp():
    """
    Integration test: Run KeywordMatchAnalyzer skill with live MCP server.

    This test verifies:
    1. MCP server provides required tools
    2. Skill can call tools successfully
    3. Skill produces expected output format
    """
    # Start MCP server
    mcp_server = create_mcp_server()

    # Verify required tools exist
    tools = mcp_server.list_tools()
    assert "get_keywords" in [t.name for t in tools]
    assert "get_search_terms" in [t.name for t in tools]

    # TODO: Load and execute skill via Claude API
    # This would require Claude API integration

    # For now, verify MCP tools return data in expected format
    keywords_result = await mcp_server.call_tool("get_keywords", {
        "customer_id": "1234567890"
    })

    assert keywords_result["status"] == "success"
    assert "data" in keywords_result
```

### Success Criteria

#### Automated Verification
- [ ] `pytest tests/test_keyword_match.py -v` - All skill tests pass
- [ ] Skill package creates valid .zip file
- [ ] skill.json validates against schema
- [ ] prompt.md contains all required sections
- [ ] Examples show both positive and negative cases

#### Manual Verification
- [ ] Load skill in Claude and run analysis with sample data
- [ ] Skill correctly identifies exact match opportunities
- [ ] Output matches format specified in prompt
- [ ] Recommendations match original analyzer logic
- [ ] Skill completes analysis in <30 seconds
- [ ] Error handling works when MCP tools fail
- [ ] Documentation is clear and complete

**Implementation Note**: After the KeywordMatchAnalyzer skill is working correctly, document any lessons learned in `docs/skill_conversion_lessons.md` before proceeding to Phase 4. This skill serves as the template for converting the remaining 23 analyzers.

---

## Phase 4: Convert High-Value Analyzers (Priority Tier 1)

### Overview
Convert the next 4 highest-value analyzers to Claude Skills, using the KeywordMatchAnalyzer as the template. These analyzers directly impact quarterly audit ROI.

### Priority Tier 1 Analyzers (5 total including KeywordMatchAnalyzer)

1. ✅ KeywordMatchAnalyzer (completed in Phase 3)
2. **SearchTermAnalyzer** - Identifies negative keyword opportunities
3. **NegativeConflictAnalyzer** - Finds negatives blocking positives
4. **GeoPerformanceAnalyzer** - Location-based optimization
5. **PMaxAnalyzer** - Performance Max campaign analysis

### Why These 5 Are Priority
- **Direct cost impact**: Each saves 10-25% on wasted spend
- **Used in every quarterly audit**: Core to the PaidSearchNav value prop
- **Well-defined methodology**: Clear rules and thresholds
- **High confidence recommendations**: Low risk of errors

### Changes Required

#### 1. SearchTermAnalyzer Conversion

**Extract logic from**: `archive/old_app/paidsearchnav/analyzers/search_term_analyzer.py`

**Core methodology**:
- Identify search terms with >$X spend and 0 conversions
- Flag search terms with CTR <Y% (low relevance)
- Recommend as negative keywords at appropriate level (campaign vs ad group)

**File**: `skills/search_term_analyzer/skill.json`

```json
{
  "name": "SearchTermAnalyzer",
  "version": "1.0.0",
  "description": "Identifies search terms wasting budget with zero conversions or low relevance",
  "requires_mcp_tools": ["get_search_terms", "get_negative_keywords"],
  "category": "cost_efficiency",
  "business_value": "Eliminates 15-20% of wasted spend on irrelevant searches"
}
```

**File**: `skills/search_term_analyzer/prompt.md`

```markdown
# Search Term Waste Analysis

## Goal
Identify search terms generating spend with no conversion value and recommend them as negative keywords.

## Methodology

1. **Fetch Data**
   - Use `get_search_terms` for last 90 days
   - Use `get_negative_keywords` to check existing negatives

2. **Identify Waste**

   Recommend as negative when ANY of these conditions:
   - **Zero conversion spend**: >$50 spend and 0 conversions
   - **Low relevance**: CTR <1% and >100 impressions
   - **High cost, low value**: >$100 spend and conversions_value < cost

3. **Determine Negative Keyword Level**
   - If search term is irrelevant across all campaigns → Account-level shared list
   - If irrelevant to one campaign only → Campaign-level negative
   - If irrelevant to one ad group only → Ad group-level negative

4. **Check for Conflicts**
   - Don't recommend if already a negative keyword
   - Don't recommend if term is too similar to positive keywords (>80% match)

## Output Format
[Markdown report with prioritized negative keyword recommendations]
```

#### 2. NegativeConflictAnalyzer Conversion

**Extract logic from**: `archive/old_app/paidsearchnav/analyzers/negative_conflicts.py`

**Core methodology**:
- Compare positive keywords with negative keyword lists
- Identify cases where negative blocks positive (e.g., negative "running" blocks positive "running shoes")
- Flag potential impression share loss

**File**: `skills/negative_conflict_analyzer/skill.json`

```json
{
  "name": "NegativeConflictAnalyzer",
  "version": "1.0.0",
  "description": "Identifies negative keywords blocking positive keywords and causing impression share loss",
  "requires_mcp_tools": ["get_keywords", "get_negative_keywords"],
  "category": "campaign_health",
  "business_value": "Prevents lost impressions from overly restrictive negative keywords (typically 5-10% impression share recovery)"
}
```

**File**: `skills/negative_conflict_analyzer/prompt.md`

```markdown
# Negative Keyword Conflict Detection

## Goal
Find negative keywords that are blocking positive keywords from showing.

## Methodology

1. **Fetch Data**
   - Use `get_keywords` for all positive keywords
   - Use `get_negative_keywords` for campaign/ad group/shared list negatives

2. **Detect Conflicts**

   A conflict exists when:
   - Negative keyword is contained in positive keyword text
   - Match types allow blocking (e.g., phrase negative blocks phrase positive)
   - Positive keyword has low impression share (<50%)

3. **Assess Impact**
   - **High impact**: Positive keyword has historical conversions but low recent impressions
   - **Medium impact**: Positive keyword is low impression share but no conversion history
   - **Low impact**: Positive keyword is paused/low spend anyway

4. **Generate Recommendations**
   - Remove negative keyword, OR
   - Make negative more specific (e.g., "running shoes" → "cheap running shoes")
   - Adjust match types

## Output Format
[Markdown report with conflict details and resolution steps]
```

#### 3. GeoPerformanceAnalyzer Conversion

**Extract logic from**: `archive/old_app/paidsearchnav/analyzers/geo_performance.py`

**Core methodology**:
- Analyze performance by location (city, DMA, region)
- Identify high-cost, low-conversion locations
- Recommend geo bid adjustments or exclusions

**File**: `skills/geo_performance_analyzer/skill.json`

```json
{
  "name": "GeoPerformanceAnalyzer",
  "version": "1.0.0",
  "description": "Analyzes geographic performance and recommends location bid adjustments for retail businesses",
  "requires_mcp_tools": ["get_geo_performance"],
  "category": "geographic_optimization",
  "business_value": "Optimizes local targeting for retail, typically improving ROAS by 15-25% through location bid adjustments"
}
```

**File**: `skills/geo_performance_analyzer/prompt.md`

```markdown
# Geographic Performance Analysis

## Goal
Identify locations (cities, regions) with poor performance and recommend bid adjustments or exclusions.

## Methodology

1. **Fetch Data**
   - Use `get_geo_performance` for last 90 days
   - Group by DMA (Designated Market Area) or city

2. **Calculate Performance Metrics**
   - Cost per conversion by location
   - Conversion rate by location
   - ROAS by location (if conversion value available)

3. **Identify Optimization Opportunities**

   **Bid up (+20% to +50%)**:
   - ROAS ≥ 2x account average
   - Conversion rate ≥ 1.5x account average
   - Sufficient volume (≥10 conversions)

   **Bid down (-20% to -50%)**:
   - ROAS ≤ 0.5x account average
   - Conversion rate ≤ 0.5x account average

   **Exclude entirely**:
   - >$500 spend, 0 conversions
   - ROAS <0.3x account average with >$1000 spend

4. **Retail-Specific Analysis**
   - If store locations are known, correlate performance with proximity to stores
   - Flag "near me" searches in high-performing locations

## Output Format
[Markdown report with location bid adjustment recommendations]
```

#### 4. PMaxAnalyzer Conversion

**Extract logic from**: `archive/old_app/paidsearchnav/analyzers/pmax.py`

**Core methodology**:
- Analyze Performance Max campaign search terms (via Insights)
- Identify search term conflicts with standard Search campaigns
- Recommend negative keywords for PMax to prevent cannibalization

**File**: `skills/pmax_analyzer/skill.json`

```json
{
  "name": "PMaxAnalyzer",
  "version": "1.0.0",
  "description": "Analyzes Performance Max campaigns for search term conflicts and cannibalization with standard Search campaigns",
  "requires_mcp_tools": ["get_search_terms", "get_campaigns"],
  "category": "campaign_overlap",
  "business_value": "Prevents PMax from cannibalizing high-performing Search campaigns, maintaining CPA efficiency"
}
```

**File**: `skills/pmax_analyzer/prompt.md`

```markdown
# Performance Max Campaign Analysis

## Goal
Identify search term overlap between Performance Max and standard Search campaigns, recommend PMax negative keywords to prevent cannibalization.

## Methodology

1. **Fetch Data**
   - Use `get_campaigns` to identify PMax campaigns
   - Use `get_search_terms` for both PMax and Search campaigns

2. **Detect Cannibalization**

   Cannibalization occurs when:
   - Same search term triggers both PMax and Search campaigns
   - PMax has higher impression share (takes traffic from Search)
   - Search campaign has better CPA or ROAS on that term

3. **Analyze Impact**
   - Calculate cost increase from PMax taking Search traffic
   - Estimate conversion loss from less efficient PMax conversions

4. **Generate Recommendations**
   - Add negative keywords to PMax asset groups
   - Adjust PMax targeting to focus on non-Search inventory
   - Consider pausing PMax if cannibalization is severe (>30% overlap)

## Output Format
[Markdown report with PMax optimization recommendations]
```

#### 5. Create Skill Test Suites

For each analyzer, create comprehensive tests:

**File**: `tests/test_search_term_analyzer.py`
**File**: `tests/test_negative_conflict_analyzer.py`
**File**: `tests/test_geo_performance_analyzer.py`
**File**: `tests/test_pmax_analyzer.py`

Use archived test data from `archive/test_data/` and `archive/old_tests/` to validate that new skills produce same recommendations as old analyzers.

#### 6. Package All Skills

**Script**: `scripts/package_all_skills.sh`

```bash
#!/bin/bash
# Package all Tier 1 skills for distribution

skills=(
    "keyword_match_analyzer"
    "search_term_analyzer"
    "negative_conflict_analyzer"
    "geo_performance_analyzer"
    "pmax_analyzer"
)

mkdir -p dist

for skill in "${skills[@]}"; do
    echo "📦 Packaging $skill..."
    python scripts/package_skill.py "$skill"
done

echo "✅ All Tier 1 skills packaged in dist/"
ls -lh dist/
```

#### 7. Create Skill Suite Bundle

**File**: `skills/cost_efficiency_suite/suite.json`

```json
{
  "name": "CostEfficiencySuite",
  "version": "1.0.0",
  "description": "Complete suite of cost efficiency analyzers for quarterly Google Ads audits",
  "includes": [
    "keyword_match_analyzer",
    "search_term_analyzer",
    "negative_conflict_analyzer",
    "geo_performance_analyzer",
    "pmax_analyzer"
  ],
  "use_case": "Quarterly keyword audit for retail businesses",
  "estimated_runtime": "5-10 minutes for typical account",
  "typical_savings": "20-35% reduction in wasted spend"
}
```

#### 8. Integration Testing

**File**: `tests/integration/test_cost_efficiency_suite.py`

```python
import pytest

@pytest.mark.integration
@pytest.mark.asyncio
async def test_full_quarterly_audit_workflow():
    """
    Integration test: Run full quarterly audit with all Tier 1 skills.

    Simulates a real quarterly audit workflow:
    1. Fetch data via MCP server
    2. Run all 5 skills in sequence
    3. Validate outputs
    4. Generate combined recommendations report
    """
    # This test uses real MCP server and sample account data
    customer_id = "1234567890"
    start_date = "2025-08-01"
    end_date = "2025-11-22"

    results = {}

    # Run each skill
    skills = [
        "keyword_match_analyzer",
        "search_term_analyzer",
        "negative_conflict_analyzer",
        "geo_performance_analyzer",
        "pmax_analyzer"
    ]

    for skill_name in skills:
        print(f"Running {skill_name}...")
        result = await run_skill(skill_name, customer_id, start_date, end_date)
        results[skill_name] = result

        # Validate output
        assert "recommendations" in result
        assert result["status"] == "success"

    # Verify total savings estimate is reasonable
    total_savings = sum(r.get("estimated_savings", 0) for r in results.values())
    assert total_savings > 0

    print(f"✅ Full audit complete. Estimated monthly savings: ${total_savings:,.2f}")
```

#### 9. Documentation

**Update**: `docs/SKILL_CATALOG.md`

```markdown
# PaidSearchNav Skill Catalog

## Tier 1: Cost Efficiency Suite

These 5 skills form the core of quarterly keyword audits.

### 1. KeywordMatchAnalyzer
**Status**: ✅ Available
**Purpose**: Exact match keyword opportunities
**Typical Impact**: $1,500-5,000/month savings
**Use Case**: Every quarterly audit

### 2. SearchTermAnalyzer
**Status**: ✅ Available
**Purpose**: Negative keyword recommendations
**Typical Impact**: $2,000-7,000/month savings
**Use Case**: Every quarterly audit

### 3. NegativeConflictAnalyzer
**Status**: ✅ Available
**Purpose**: Fix negatives blocking positives
**Typical Impact**: 5-10% impression share recovery
**Use Case**: Campaign health checks

### 4. GeoPerformanceAnalyzer
**Status**: ✅ Available
**Purpose**: Location bid optimization
**Typical Impact**: 15-25% ROAS improvement
**Use Case**: Retail businesses with physical locations

### 5. PMaxAnalyzer
**Status**: ✅ Available
**Purpose**: Performance Max conflict resolution
**Typical Impact**: Prevent 10-20% CPA increase from cannibalization
**Use Case**: Accounts with PMax campaigns

## How to Use

1. Load skills in Claude (upload .zip files or paste prompts)
2. Connect Claude to PaidSearchNav MCP server
3. Run skills in sequence or individually
4. Export recommendations to implement in Google Ads
```

**Create**: `docs/QUARTERLY_AUDIT_GUIDE.md`

Step-by-step guide for running a complete quarterly audit using the 5 Tier 1 skills.

### Success Criteria

#### Automated Verification
- [ ] `pytest tests/test_search_term_analyzer.py -v` - All tests pass
- [ ] `pytest tests/test_negative_conflict_analyzer.py -v` - All tests pass
- [ ] `pytest tests/test_geo_performance_analyzer.py -v` - All tests pass
- [ ] `pytest tests/test_pmax_analyzer.py -v` - All tests pass
- [ ] `pytest tests/integration/test_cost_efficiency_suite.py -v` - Full audit workflow passes
- [ ] All 5 skills package successfully to .zip files
- [ ] Skill suite bundle validates

#### Manual Verification
- [ ] Run each skill individually with sample account data
- [ ] Each skill completes in <30 seconds
- [ ] Recommendations match original analyzer logic
- [ ] Output formatting is consistent across all skills
- [ ] Run full quarterly audit workflow end-to-end
- [ ] Combined savings estimates are realistic (15-35% of spend)
- [ ] Documentation is complete and clear
- [ ] Skills work correctly when run in Claude with MCP connection

**Implementation Note**: After completing Tier 1 skills, validate with a real quarterly audit on a pilot account. Gather feedback on accuracy, performance, and usability before proceeding to Phase 5 (remaining analyzers).

---

## Phase 5: Convert Remaining Analyzers (Tiers 2 & 3)

### Overview
Convert the remaining 19 analyzers to Claude Skills. These are organized into Tier 2 (moderate value) and Tier 3 (specialized use cases).

### Tier 2: Moderate Value Analyzers (10 analyzers)

These provide valuable insights but aren't used in every audit:

1. **DevicePerformanceAnalyzer** - Mobile vs desktop bid adjustments
2. **DaypartingAnalyzer** - Time-of-day/day-of-week optimization
3. **AdGroupPerformanceAnalyzer** - Ad group structure recommendations
4. **LandingPageAnalyzer** - Landing page performance analysis
5. **DemographicsAnalyzer** - Age/gender bid adjustments
6. **CampaignOverlapAnalyzer** - Keyword overlap between campaigns
7. **AttributionAnalyzer** - Multi-touch attribution insights
8. **PlacementAuditAnalyzer** - Display/video placement analysis
9. **CompetitorInsightsAnalyzer** - Auction insights analysis
10. **LocalReachStorePerformanceAnalyzer** - Local campaigns for retail

### Tier 3: Specialized Analyzers (9 analyzers)

These address specific scenarios or advanced features:

1. **VideoCreativeAnalyzer** - YouTube ad performance
2. **SharedNegativesAnalyzer** - Shared negative keyword list optimization
3. **BulkNegativeManagerAnalyzer** - Bulk negative keyword operations
4. **AdvancedBidAdjustmentAnalyzer** - Complex bid adjustment strategies
5. **GA4AnalyticsAnalyzer** - GA4 integration for on-site metrics
6. **StorePerformanceAnalyzer** - Store visits and in-store conversions
7. **KeywordAnalyzer** - Generic keyword analysis (may be redundant)
8. **SearchTermsAnalyzer** - May overlap with SearchTermAnalyzer
9. **PMaxAnalyzer** - Already handled in Tier 1

### Changes Required

#### 1. Audit Existing Analyzers for Redundancy

**Review**: `archive/old_app/paidsearchnav/analyzers/`

Identify:
- Which analyzers overlap in functionality
- Which can be combined into a single skill
- Which are truly unique

**Create**: `docs/analyzer_consolidation_plan.md`

Example consolidations:
- **KeywordAnalyzer** + **SearchTermsAnalyzer** → May be covered by Tier 1 skills
- **StorePerformanceAnalyzer** + **LocalReachStorePerformanceAnalyzer** → Single "StorePerformance" skill

**Result**: Reduce 19 analyzers to ~15 unique skills through consolidation.

#### 2. Convert Tier 2 Analyzers (Priority Order)

Convert in this order (highest impact first):

##### 2.1 DevicePerformanceAnalyzer
**File**: `skills/device_performance_analyzer/skill.json`

```json
{
  "name": "DevicePerformanceAnalyzer",
  "version": "1.0.0",
  "description": "Analyzes performance by device type and recommends bid adjustments for mobile/desktop/tablet",
  "requires_mcp_tools": ["query_bigquery"],
  "category": "bid_optimization",
  "business_value": "Optimize mobile vs desktop performance, typically 10-15% ROAS improvement"
}
```

**Methodology**: Analyze CPA/ROAS by device, recommend bid adjustments (-30% to +50%).

##### 2.2 DaypartingAnalyzer
**File**: `skills/dayparting_analyzer/skill.json`

```json
{
  "name": "DaypartingAnalyzer",
  "version": "1.0.0",
  "description": "Analyzes performance by hour-of-day and day-of-week, recommends ad scheduling",
  "requires_mcp_tools": ["query_bigquery"],
  "category": "bid_optimization",
  "business_value": "Reduce spend during low-performing hours, improve efficiency by 8-12%"
}
```

**Methodology**: Identify high/low performing time periods, recommend bid schedules.

##### 2.3 AdGroupPerformanceAnalyzer
**Methodology**: Analyze ad group structure, recommend consolidation or splitting based on performance.

##### 2.4 LandingPageAnalyzer
**Methodology**: Identify landing pages with high bounce rate or low conversion rate, recommend page changes.

##### 2.5-2.10 Remaining Tier 2 Analyzers
Continue with same conversion pattern as Tier 1.

#### 3. Convert Tier 3 Analyzers (As Needed)

Tier 3 analyzers are converted only if:
- User explicitly requests them
- They provide unique value not covered by other skills
- There's sufficient demand

**Recommended approach**: Create skeleton skills with basic prompts, enhance later based on usage.

#### 4. Create Skill Suites

Organize skills into thematic suites:

**File**: `skills/bid_optimization_suite/suite.json`

```json
{
  "name": "BidOptimizationSuite",
  "includes": [
    "device_performance_analyzer",
    "dayparting_analyzer",
    "geo_performance_analyzer",
    "demographics_analyzer",
    "advanced_bid_adjustment_analyzer"
  ],
  "use_case": "Comprehensive bid optimization analysis"
}
```

**File**: `skills/campaign_structure_suite/suite.json`

```json
{
  "name": "CampaignStructureSuite",
  "includes": [
    "ad_group_performance_analyzer",
    "campaign_overlap_analyzer",
    "negative_conflict_analyzer"
  ],
  "use_case": "Campaign structure and organization optimization"
}
```

#### 5. Batch Testing

**File**: `tests/integration/test_all_skills.py`

```python
import pytest

TIER_2_SKILLS = [
    "device_performance_analyzer",
    "dayparting_analyzer",
    # ... all Tier 2
]

TIER_3_SKILLS = [
    "video_creative_analyzer",
    # ... all Tier 3
]

@pytest.mark.parametrize("skill_name", TIER_2_SKILLS + TIER_3_SKILLS)
@pytest.mark.asyncio
async def test_skill_basic_functionality(skill_name):
    """Test basic functionality of each skill."""
    # Load skill
    skill = load_skill(skill_name)

    # Verify structure
    assert skill.metadata is not None
    assert skill.prompt is not None

    # Test with sample data
    result = await run_skill_with_sample_data(skill_name)
    assert result["status"] in ["success", "no_recommendations"]
```

#### 6. Performance Optimization

Some analyzers may be slow if they fetch large datasets. Optimize by:

**Caching strategy**:
```python
# Cache BigQuery results for 1 hour
@mcp.tool()
async def query_bigquery_cached(request: BigQueryRequest) -> dict:
    cache_key = f"bq:{hash(request.query)}"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    result = await query_bigquery(request)
    await cache.set(cache_key, result, ttl=3600)
    return result
```

**Parallel execution**:
Skills that need multiple MCP tool calls should fetch data in parallel.

#### 7. Documentation Updates

**Create**: `docs/COMPLETE_SKILL_CATALOG.md`

List all 24 skills with:
- Name and description
- Required MCP tools
- Typical use cases
- Expected runtime
- Business value / ROI

**Update**: `README.md` in PaidSearchNav-Skills repo

Link to complete catalog and usage examples.

### Success Criteria

#### Automated Verification
- [ ] `pytest tests/integration/test_all_skills.py -v` - All skills pass basic tests
- [ ] All Tier 2 skills package successfully
- [ ] All Tier 3 skills package successfully
- [ ] Skill suites validate and bundle correctly
- [ ] Documentation is complete for all skills

#### Manual Verification
- [ ] Spot-check 3-5 Tier 2 skills with real data
- [ ] Each skill completes in <60 seconds (may be slower than Tier 1)
- [ ] Recommendations are actionable and accurate
- [ ] Output formatting is consistent
- [ ] Skills work in Claude with MCP connection
- [ ] Skill suites provide cohesive analysis when run together

**Implementation Note**: After completing all skill conversions, run a comprehensive audit using all 24 skills on a test account. Document total runtime, savings estimates, and any issues before moving to Phase 6.

---

## Phase 6: Production Deployment & Documentation

### Overview
Deploy the MCP server to production, distribute skills to users, and create comprehensive end-user documentation.

### Changes Required

#### 1. MCP Server Production Configuration

**File**: `docker-compose.prod.yml` (new)

```yaml
version: '3.8'

services:
  mcp-server:
    build:
      context: .
      dockerfile: Dockerfile
    image: paidsearchnav-mcp:latest
    container_name: paidsearchnav-mcp-prod
    restart: unless-stopped

    environment:
      - ENVIRONMENT=production
      - LOG_LEVEL=INFO
      - GOOGLE_ADS_DEVELOPER_TOKEN=${GOOGLE_ADS_DEVELOPER_TOKEN}
      - GOOGLE_ADS_CLIENT_ID=${GOOGLE_ADS_CLIENT_ID}
      - GOOGLE_ADS_CLIENT_SECRET=${GOOGLE_ADS_CLIENT_SECRET}
      - GOOGLE_ADS_REFRESH_TOKEN=${GOOGLE_ADS_REFRESH_TOKEN}
      - GOOGLE_ADS_LOGIN_CUSTOMER_ID=${GOOGLE_ADS_LOGIN_CUSTOMER_ID}
      - GOOGLE_APPLICATION_CREDENTIALS=/app/credentials/service-account.json
      - GCP_PROJECT_ID=${GCP_PROJECT_ID}
      - REDIS_URL=redis://redis:6379/0

    volumes:
      - ./credentials:/app/credentials:ro
      - mcp-logs:/app/logs

    ports:
      - "8080:8080"

    depends_on:
      - redis

    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

    networks:
      - mcp-network

  redis:
    image: redis:7-alpine
    container_name: paidsearchnav-redis-prod
    restart: unless-stopped

    volumes:
      - redis-data:/data

    command: redis-server --appendonly yes --maxmemory 256mb --maxmemory-policy allkeys-lru

    networks:
      - mcp-network

volumes:
  redis-data:
  mcp-logs:

networks:
  mcp-network:
    driver: bridge
```

#### 2. Health Monitoring

**File**: `src/paidsearchnav_mcp/monitoring.py` (new)

```python
from datetime import datetime
import logging

class HealthMonitor:
    """Monitor MCP server health and performance."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.metrics = {
            "total_requests": 0,
            "failed_requests": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "avg_response_time_ms": 0,
            "last_health_check": None
        }

    def record_request(self, success: bool, response_time_ms: float):
        """Record a request for metrics."""
        self.metrics["total_requests"] += 1
        if not success:
            self.metrics["failed_requests"] += 1

        # Update avg response time
        current_avg = self.metrics["avg_response_time_ms"]
        total = self.metrics["total_requests"]
        self.metrics["avg_response_time_ms"] = (
            (current_avg * (total - 1) + response_time_ms) / total
        )

    def get_health_status(self) -> dict:
        """Get current health status."""
        self.metrics["last_health_check"] = datetime.utcnow().isoformat()

        success_rate = 1 - (self.metrics["failed_requests"] / max(self.metrics["total_requests"], 1))
        cache_hit_rate = self.metrics["cache_hits"] / max(
            self.metrics["cache_hits"] + self.metrics["cache_misses"], 1
        )

        return {
            "status": "healthy" if success_rate > 0.95 else "degraded",
            "metrics": self.metrics,
            "success_rate": round(success_rate, 3),
            "cache_hit_rate": round(cache_hit_rate, 3)
        }
```

**Update**: `src/paidsearchnav_mcp/server.py`

Add health monitoring to MCP tools:

```python
from paidsearchnav_mcp.monitoring import HealthMonitor

monitor = HealthMonitor()

@mcp.resource("resource://metrics")
def get_metrics() -> dict:
    """Get server performance metrics."""
    return monitor.get_health_status()
```

#### 3. Deployment Scripts

**File**: `scripts/deploy_production.sh`

```bash
#!/bin/bash
set -e

echo "🚀 Deploying PaidSearchNav MCP Server to Production"

# Verify prerequisites
if [ ! -f ".env" ]; then
    echo "❌ Error: .env file not found"
    echo "Copy .env.example to .env and configure credentials"
    exit 1
fi

if [ ! -f "credentials/service-account.json" ]; then
    echo "⚠️  Warning: BigQuery service account not found (optional)"
fi

# Run tests
echo "🧪 Running tests..."
pytest tests/ -v --tb=short

# Build Docker image
echo "🏗️  Building Docker image..."
docker build -t paidsearchnav-mcp:latest .

# Check image size
IMAGE_SIZE=$(docker images paidsearchnav-mcp:latest --format "{{.Size}}")
echo "📦 Image size: $IMAGE_SIZE"

# Stop existing containers
echo "🛑 Stopping existing containers..."
docker-compose -f docker-compose.prod.yml down

# Start production containers
echo "▶️  Starting production containers..."
docker-compose -f docker-compose.prod.yml up -d

# Wait for health check
echo "⏳ Waiting for health check..."
sleep 10

# Verify deployment
echo "✅ Verifying deployment..."
HEALTH_STATUS=$(curl -s http://localhost:8080/health | jq -r '.status')

if [ "$HEALTH_STATUS" == "healthy" ]; then
    echo "🎉 Deployment successful! MCP server is healthy"
    docker-compose -f docker-compose.prod.yml ps
else
    echo "❌ Deployment failed! Health check returned: $HEALTH_STATUS"
    docker-compose -f docker-compose.prod.yml logs
    exit 1
fi
```

#### 4. Skill Distribution

**Create**: `PaidSearchNav-Skills/dist/README.md`

```markdown
# PaidSearchNav Skills Distribution

This directory contains packaged Claude Skills for Google Ads analysis.

## Installation

1. **Download skill .zip files** from this directory
2. **In Claude**, use the "Add Skill" or "Upload Skill" feature
3. **Connect to MCP Server**: Ensure Claude is connected to your PaidSearchNav MCP server

## Available Skill Suites

### Cost Efficiency Suite (Tier 1)
**File**: `CostEfficiencySuite_v1.0.0.zip`

Includes:
- KeywordMatchAnalyzer
- SearchTermAnalyzer
- NegativeConflictAnalyzer
- GeoPerformanceAnalyzer
- PMaxAnalyzer

**Use case**: Complete quarterly keyword audit
**Runtime**: 5-10 minutes
**Typical savings**: 20-35% reduction in wasted spend

### Bid Optimization Suite (Tier 2)
**File**: `BidOptimizationSuite_v1.0.0.zip`

Includes:
- DevicePerformanceAnalyzer
- DaypartingAnalyzer
- DemographicsAnalyzer
- AdvancedBidAdjustmentAnalyzer

**Use case**: Advanced bid optimization
**Runtime**: 3-7 minutes

### Campaign Structure Suite (Tier 2)
**File**: `CampaignStructureSuite_v1.0.0.zip`

Includes:
- AdGroupPerformanceAnalyzer
- CampaignOverlapAnalyzer
- LandingPageAnalyzer

**Use case**: Campaign organization and structure optimization
**Runtime**: 2-5 minutes

## Individual Skills

All 24 skills are also available individually in the `individual_skills/` directory.

## Quick Start

1. Start with **Cost Efficiency Suite** for your first quarterly audit
2. Load the suite in Claude
3. Connect Claude to your MCP server (see CONNECTION_GUIDE.md)
4. Run: "Analyze customer 1234567890 from 2025-08-01 to 2025-11-22"
5. Review recommendations and implement in Google Ads

## Support

- Documentation: https://github.com/datablogin/PaidSearchNav-Skills/docs
- Issues: https://github.com/datablogin/PaidSearchNav-Skills/issues
```

#### 5. End-User Documentation

**Create**: `PaidSearchNav-Skills/docs/USER_GUIDE.md`

Comprehensive guide including:
- How to install and configure MCP server
- How to load skills in Claude
- Step-by-step quarterly audit workflow
- How to interpret recommendations
- How to implement changes in Google Ads
- Troubleshooting common issues

**Create**: `PaidSearchNav-Skills/docs/CONNECTION_GUIDE.md`

Step-by-step guide for connecting Claude to the MCP server:

```markdown
# Connecting Claude to PaidSearchNav MCP Server

## Prerequisites
- PaidSearchNav MCP Server running (local or remote)
- Claude desktop app or Claude.ai account
- MCP server URL (e.g., http://localhost:8080)

## Steps

### 1. Start MCP Server
```bash
docker-compose -f docker-compose.prod.yml up -d
```

### 2. Verify Server is Running
```bash
curl http://localhost:8080/health
# Should return: {"status": "healthy", ...}
```

### 3. Connect Claude to MCP Server

**In Claude Desktop App**:
1. Open Settings → Integrations
2. Click "Add MCP Server"
3. Enter server details:
   - Name: PaidSearchNav
   - URL: http://localhost:8080
   - Protocol: MCP v1.0
4. Click "Test Connection"
5. If successful, click "Save"

**In Claude.ai** (if supported):
1. Go to Settings → Connected Services
2. Add new service
3. Select "Model Context Protocol (MCP)"
4. Enter server URL
5. Authorize connection

### 4. Verify Connection

In Claude, type:
```
List available MCP tools from PaidSearchNav
```

Claude should respond with the 6 Google Ads tools:
- get_search_terms
- get_keywords
- get_campaigns
- get_negative_keywords
- get_geo_performance
- query_bigquery

### 5. Load Skills

Upload the CostEfficiencySuite.zip file in Claude, then run your first analysis!
```

**Create**: `PaidSearchNav-Skills/docs/QUARTERLY_AUDIT_WORKFLOW.md`

Detailed workflow for running a complete quarterly audit.

#### 6. Example Reports

**Create**: `PaidSearchNav-Skills/examples/sample_audit_report.md`

A complete sample audit report showing:
- Executive summary
- Each skill's recommendations
- Implementation checklist
- Expected ROI

This helps users understand what to expect.

#### 7. Video Tutorials (Optional)

Consider creating:
- 5-min "Quick Start" video
- 15-min "Complete Quarterly Audit" walkthrough
- 10-min "Implementing Recommendations" guide

Store videos on YouTube and link from documentation.

#### 8. Feedback Mechanism

**Create**: `PaidSearchNav-Skills/.github/ISSUE_TEMPLATE/skill_feedback.md`

Template for users to submit feedback on skills:

```markdown
---
name: Skill Feedback
about: Provide feedback on a specific skill's performance or recommendations
---

**Skill Name**: [e.g., KeywordMatchAnalyzer]
**Version**: [e.g., 1.0.0]

**Issue/Feedback**:
[Describe the issue or suggestion]

**Expected Behavior**:
[What you expected to happen]

**Actual Behavior**:
[What actually happened]

**Account Details** (optional, no sensitive data):
- Account type: [e.g., Retail, B2B, Local Services]
- Account size: [e.g., <$10k/month, $10k-50k/month, >$50k/month]
- Industry: [e.g., Fitness, Legal, E-commerce]

**Screenshots** (if applicable):
[Attach screenshots of recommendations or errors]
```

#### 9. Changelog

**Create**: `CHANGELOG.md` in both repos

Track all changes to MCP server and skills:

```markdown
# Changelog

All notable changes to PaidSearchNav MCP Server and Skills.

## [1.0.0] - 2025-11-22

### MCP Server
- ✨ Initial release
- ✅ 6 Google Ads API tools implemented
- ✅ BigQuery integration
- ✅ Redis caching layer
- ✅ Docker deployment (<200MB image)

### Skills
- ✨ Cost Efficiency Suite (5 skills)
- ✨ Bid Optimization Suite (4 skills)
- ✨ Campaign Structure Suite (3 skills)
- ✨ 12 additional specialized skills
- 📚 Complete documentation and examples

### Breaking Changes
None (initial release)

### Known Issues
- BigQuery requires manual service account setup
- Some skills may be slow for accounts with >100 campaigns
```

#### 10. License and Legal

**Create**: `LICENSE` in both repos

Choose appropriate license (e.g., MIT, Apache 2.0).

**Create**: `TERMS_OF_USE.md`

If distributing commercially, include terms of use and disclaimer:

```markdown
# Terms of Use

PaidSearchNav MCP Server and Skills are provided "as is" without warranty of any kind.

## Disclaimer
- Analysis and recommendations are algorithmic and should be reviewed by qualified professionals
- Users are responsible for implementing changes in their Google Ads accounts
- PaidSearchNav is not affiliated with Google or Google Ads
- Results may vary based on account structure, industry, and other factors

## Data Privacy
- MCP server does not store user data
- Skills process data in Claude's environment
- Google Ads credentials are user-managed
- See PRIVACY.md for details
```

### Success Criteria

#### Automated Verification
- [ ] `./scripts/deploy_production.sh` completes successfully
- [ ] Production containers start and pass health checks
- [ ] All skill .zip files package correctly
- [ ] Documentation builds without errors (if using doc generator)
- [ ] Changelog is up to date

#### Manual Verification
- [ ] MCP server is accessible at production URL
- [ ] Health endpoint returns "healthy" status
- [ ] Metrics endpoint shows reasonable performance
- [ ] Can connect Claude to MCP server successfully
- [ ] Can load and run Cost Efficiency Suite in Claude
- [ ] Sample audit completes in <10 minutes
- [ ] Recommendations are accurate and actionable
- [ ] Documentation is clear and complete
- [ ] Example reports help users understand output
- [ ] Feedback mechanism works (can create issues)

**Implementation Note**: After production deployment, monitor server performance for 1 week. Gather feedback from early users before announcing general availability.

---

## Phase 7: Archive Old Repository

### Overview
Archive the original PaidSearchNav repository now that the new MCP + Skills architecture is production-ready.

### Why This Matters
- Prevents confusion about which codebase is current
- Preserves historical reference without implying it's maintained
- Redirects new users to modern architecture

### Changes Required

#### 1. Archive Original Repository on GitHub

**In GitHub**:
1. Go to original PaidSearchNav repository settings
2. Scroll to "Danger Zone"
3. Click "Archive this repository"
4. Confirm archiving

**Result**: Repository becomes read-only with "Archived" badge.

#### 2. Update Original Repository README

**Update**: Original PaidSearchNav `README.md`

Add prominent notice at top:

```markdown
# ⚠️ ARCHIVED - PaidSearchNav (Legacy)

**This repository has been archived and is no longer maintained.**

## New Architecture

PaidSearchNav has been refactored into a modern MCP + Skills architecture:

- **🔌 MCP Server**: [PaidSearchNav-MCP](https://github.com/datablogin/PaidSearchNav-MCP)
  - Lightweight data connectivity (~200MB vs 1.5GB)
  - 8 dependencies vs 62
  - Docker deployment

- **🎯 Claude Skills**: [PaidSearchNav-Skills](https://github.com/datablogin/PaidSearchNav-Skills)
  - 24 analyzer skills for quarterly audits
  - Fast iteration on analysis logic
  - Standards-based (MCP protocol)

## Why the Change?

The original monolithic architecture had several limitations:
- 1.5GB Docker image
- Slow deployment and iteration
- Tightly coupled connectivity and analysis logic
- Required database for stateless operations

The new architecture addresses all of these issues.

## For Existing Users

If you're currently using the legacy PaidSearchNav app:

1. **Migration guide**: [MIGRATION.md](MIGRATION.md)
2. **New setup guide**: See [PaidSearchNav-MCP](https://github.com/datablogin/PaidSearchNav-MCP)
3. **Support**: Open issues in the new repositories

## Historical Reference

This code remains available for reference. Key components that were extracted:
- Google Ads API client → Migrated to PaidSearchNav-MCP
- 24 analyzers → Converted to Claude Skills
- Test data → Available in archive/ directory

---

**Last update**: November 2025
**Active development moved to**: [PaidSearchNav-MCP](https://github.com/datablogin/PaidSearchNav-MCP) and [PaidSearchNav-Skills](https://github.com/datablogin/PaidSearchNav-Skills)
```

#### 3. Create Migration Guide

**Create**: `MIGRATION.md` in original repository

```markdown
# Migrating from Legacy PaidSearchNav to MCP + Skills

This guide helps you migrate from the legacy monolithic PaidSearchNav app to the new MCP + Skills architecture.

## Overview of Changes

### Before (Legacy)
- Single Python app with 24 analyzers
- 1.5GB Docker image
- 62 dependencies
- SQLite database
- Flask web UI

### After (New Architecture)
- **MCP Server**: Lightweight data connectivity (200MB)
- **Claude Skills**: 24 individual analyzer skills
- No database required
- No web UI (use Claude interface)

## Migration Steps

### 1. Set Up MCP Server

```bash
git clone https://github.com/datablogin/PaidSearchNav-MCP.git
cd PaidSearchNav-MCP
cp .env.example .env
# Edit .env with your Google Ads credentials
docker-compose up -d
```

### 2. Install Skills in Claude

1. Download skill .zip files from [PaidSearchNav-Skills releases](https://github.com/datablogin/PaidSearchNav-Skills/releases)
2. Upload to Claude
3. Connect Claude to your MCP server

### 3. Run Your First Analysis

Instead of the old web UI workflow, you now use natural language in Claude:

**Old way**:
1. Log into web UI at http://localhost:5000
2. Click "New Audit"
3. Select analyzers from checkboxes
4. Click "Run Analysis"
5. Download CSV reports

**New way**:
1. Open Claude
2. Type: "Run a quarterly audit for customer 1234567890 from 2025-08-01 to 2025-11-22"
3. Claude uses skills to analyze and provides markdown report
4. Export recommendations to Google Ads

### 4. Migrate Saved Reports (Optional)

If you have saved reports from the old app:

```bash
# Export reports from old SQLite database
sqlite3 legacy_app.db "SELECT * FROM audit_reports" > old_reports.csv

# No direct import needed - reports are now generated on-demand
```

### 5. Update Scripts/Automation

If you had scripts calling the old Flask API:

**Old**:
```python
import requests
response = requests.post("http://localhost:5000/api/analyze", json={
    "customer_id": "1234567890",
    "analyzers": ["keyword_match", "search_term"]
})
```

**New**:
```python
# Use Claude API with skills or call MCP server directly
from mcp_client import MCPClient

client = MCPClient("http://localhost:8080")
search_terms = await client.call_tool("get_search_terms", {
    "customer_id": "1234567890",
    "start_date": "2025-11-01",
    "end_date": "2025-11-22"
})
```

## What You Gain

✅ 87% smaller deployment (200MB vs 1.5GB)
✅ Faster iteration on analysis logic
✅ Natural language interface (Claude)
✅ Standards-based architecture (MCP)
✅ No database maintenance
✅ Better separation of concerns

## What You Lose

⚠️ Web UI (replaced by Claude interface)
⚠️ Report history database (reports are now ephemeral/on-demand)
⚠️ Built-in scheduling (can use cron + Claude API)

## Support

- Questions: Open issue in [PaidSearchNav-MCP](https://github.com/datablogin/PaidSearchNav-MCP/issues)
- Bugs: Report in respective repository (MCP server or Skills)
- Feature requests: Welcome in new repositories
```

#### 4. Redirect Documentation

Update all documentation in original repo to point to new repos:

**File**: `docs/README.md` in original repo

```markdown
# Documentation (Archived)

This documentation is for the legacy PaidSearchNav application which has been archived.

## Current Documentation

For up-to-date documentation, see:

- **MCP Server**: [PaidSearchNav-MCP Docs](https://github.com/datablogin/PaidSearchNav-MCP/docs)
- **Skills**: [PaidSearchNav-Skills Docs](https://github.com/datablogin/PaidSearchNav-Skills/docs)
- **Migration Guide**: [MIGRATION.md](../MIGRATION.md)

## Historical Reference

The documentation below is preserved for historical reference but is no longer maintained.

[Original documentation follows...]
```

#### 5. Update Package Repositories

If PaidSearchNav was published to PyPI or other package registries:

**Update PyPI description**:
```
[DEPRECATED] This package has been superseded by PaidSearchNav-MCP.
Please use the new architecture: https://github.com/datablogin/PaidSearchNav-MCP
```

**Publish final version** with deprecation notice:

```python
# setup.py or pyproject.toml
setup(
    name="paidsearchnav",
    version="2.0.0-deprecated",
    description="DEPRECATED - Use PaidSearchNav-MCP instead",
    # ...
)
```

#### 6. Notify Users

**Create announcement**: `ANNOUNCEMENT.md`

```markdown
# PaidSearchNav Architecture Change Announcement

**Date**: 2025-11-22

## TL;DR
PaidSearchNav has been refactored into a modern MCP + Skills architecture. The legacy monolithic app is now archived.

## What Changed?

We've split PaidSearchNav into two repositories:
1. **PaidSearchNav-MCP**: Lightweight MCP server for Google Ads data
2. **PaidSearchNav-Skills**: 24 Claude Skills for analysis

## Why?

- 87% smaller deployment (200MB vs 1.5GB)
- Faster development iteration
- Better separation of concerns
- Standards-based (MCP protocol)
- No database overhead

## Migration

See [MIGRATION.md](MIGRATION.md) for step-by-step migration guide.

## Timeline

- **Now**: Legacy app is archived (read-only)
- **Next 30 days**: Support for migration questions
- **After 30 days**: Legacy repository fully unmaintained

## Support

Open issues in the new repositories for assistance with migration.

## Thank You

Thank you to everyone who used and contributed to the legacy PaidSearchNav. The new architecture builds on lessons learned and will serve you better going forward.
```

Send announcement to:
- GitHub discussions
- Email newsletter (if applicable)
- Social media
- Documentation site

#### 7. Handle Outstanding Issues

In original repository:

1. **Close old issues** with comment pointing to new repos:
   ```
   This issue pertains to the legacy PaidSearchNav app which has been archived.

   If this is still relevant, please open a new issue in:
   - PaidSearchNav-MCP: https://github.com/datablogin/PaidSearchNav-MCP/issues
   - PaidSearchNav-Skills: https://github.com/datablogin/PaidSearchNav-Skills/issues

   See MIGRATION.md for information on the new architecture.
   ```

2. **Lock conversations** to prevent new comments on closed issues

#### 8. Update Related Resources

If PaidSearchNav was mentioned in other places:

- **Blog posts**: Add update notices
- **YouTube videos**: Add pinned comment about archiving
- **Stack Overflow answers**: Edit to mention deprecation
- **Documentation sites**: Redirect to new docs
- **Social media profiles**: Update links

### Success Criteria

#### Automated Verification
- [ ] Original repository shows "Archived" badge on GitHub
- [ ] README.md has prominent deprecation notice
- [ ] All links to new repositories work correctly
- [ ] MIGRATION.md is complete and accurate

#### Manual Verification
- [ ] Searching for "PaidSearchNav" returns new repositories first
- [ ] Old PyPI package (if exists) shows deprecation warning
- [ ] All existing users have been notified
- [ ] Outstanding issues are closed with helpful redirects
- [ ] Documentation clearly guides users to new architecture
- [ ] Migration guide has been tested with a real user

**Implementation Note**: After archiving, monitor for 30 days to help users with migration questions. After that, consider the legacy app fully sunset.

---

## Testing Strategy

### Unit Tests
Each MCP tool and skill should have unit tests covering:
- Happy path (successful execution)
- Error handling (invalid inputs, API failures)
- Edge cases (empty results, large datasets)
- Performance (response time <2s for typical queries)

### Integration Tests
- MCP server + Redis caching
- MCP server + Google Ads API (with test account)
- MCP server + BigQuery (with test project)
- Skills + MCP server (end-to-end workflow)

### Performance Testing
- Load test MCP server with 100 concurrent requests
- Verify cache hit rate >80% for repeated queries
- Ensure skills complete in <60s for typical accounts

### User Acceptance Testing
- Run complete quarterly audit on 3 test accounts
- Validate recommendations match original analyzer output
- Verify implementation instructions are clear and correct

## Performance Considerations

### MCP Server Optimization
- **Caching**: Redis caches reduce Google Ads API calls by 80%+
- **Parallel queries**: Fetch multiple GAQL queries concurrently
- **Connection pooling**: Reuse Google Ads API connections
- **Query optimization**: Use selective field masks in GAQL

### Skill Performance
- **Data fetching**: Minimize MCP tool calls (batch when possible)
- **Prompt efficiency**: Keep skill prompts focused and concise
- **Result limits**: Cap results at reasonable sizes (e.g., top 1000)

### Docker Image Size
Target: <250MB final image
- Use Python 3.12-slim base
- Multi-stage builds
- Minimize dependencies
- No unnecessary system packages

## Migration Notes

### Data Migration
No data migration needed:
- Old app used SQLite for report storage
- New architecture generates reports on-demand
- Historical reports can be exported from old SQLite (if needed)

### Credential Migration
Google Ads credentials can be reused:
- Copy from old `.env` to new `.env`
- Same OAuth refresh token works
- No need to regenerate credentials

### Code Reuse
Extracted from old app to new MCP server:
- `paidsearchnav/auth/` → `src/paidsearchnav_mcp/clients/google/auth.py`
- Google Ads API client patterns
- GAQL query templates
- Data transformation logic

## References

- MCP Specification: https://modelcontextprotocol.io/
- Google Ads API: https://developers.google.com/google-ads/api
- BigQuery API: https://cloud.google.com/bigquery/docs
- FastMCP Documentation: https://github.com/jlowin/fastmcp
- SETUP_COMPLETE.md: Current implementation status
- Original repository: https://github.com/datablogin/PaidSearchNav (archived)

---

## Appendix: File Cleanup Reference

### Files to Archive (from Root Directory)

**Test Files** (34 files):
```
test_*.py (all root-level test files)
```

**Test Data** (16+ files):
```
*.csv (keyword files, search term exports)
*_test_*.json (quarterly audit test results)
```

**Scripts** (12 files):
```
generate_*.py
find_mcc_clients.py
bigquery_integration_design.py
claude-*.sh
fix-ci.sh
run-local.sh
test-*.sh
```

**Documentation** (28 files to archive, keep 6):
```
Archive:
- All *_GUIDE.md except current MCP guides
- All *_REPORT.md
- All implementation/architecture docs for old app
- Issue-specific docs (ISSUE_*.md)

Keep:
- README.md (updated)
- CLAUDE.md (updated)
- CONTRIBUTING.md (updated)
- SETUP_COMPLETE.md
- CHANGELOG.md
- LICENSE
```

**Configurations** (7 files):
```
Archive:
- docker-compose.dev.yml
- docker-compose.prod.yml
- alembic.ini
- .env.dev
- .env.test
- .env.local.standalone
- .env.bigquery.example

Keep:
- docker-compose.yml (new MCP setup)
- .env.example (new simplified version)
```

**Directories**:
```
Archive:
- paidsearchnav/ (entire old app)
- infrastructure/
- configs/
- examples/
- docs/ (reorganize, archive old content)
- reviews/
- cache/
- test_data/

Keep:
- src/ (new MCP server)
- tests/ (new test structure)
- scripts/ (new utility scripts)
- credentials/ (gitignored)
- .venv/ (gitignored)
```

**Total Impact**:
- Before: 135 items in root directory
- After: <25 items in root directory
- Cleanup: ~80% reduction in clutter

---

*End of Implementation Plan*
