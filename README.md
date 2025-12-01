# PaidSearchNav MCP Server

A lightweight [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server providing access to Google Ads and BigQuery data for PaidSearchNav analyzers.

This is part of the PaidSearchNav refactoring effort to separate data connectivity (MCP server) from analysis logic (Claude Skills). See [thoughts/shared/research/2025-11-22-mcp-skills-refactoring-strategy.md](thoughts/shared/research/2025-11-22-mcp-skills-refactoring-strategy.md) for more details.

> **Note**: The original monolithic PaidSearchNav application has been archived to `archive/`. See [archive/README.md](archive/README.md) for reference material.

## Overview

The PaidSearchNav MCP server is a **minimal, containerized service** (~200MB Docker image) that provides:

- ✅ Google Ads API access via MCP tools
- ✅ BigQuery query execution
- ✅ Campaign, keyword, and search terms data retrieval
- ✅ Geographic performance data
- ✅ Negative keyword conflict detection
- ✅ **NEW: Orchestration tools for server-side analysis** (Phase 2.5 - 2/5 complete)
- ✅ Redis-based caching for performance

## Architecture

**Phase 2.5 Two-Layer Design** (solves context window limitations):

\`\`\`
┌─────────────────────────────────────────────────────────────┐
│  Claude Desktop with Lightweight Skills                     │
│  - Skills are 20-50 line prompts (minimal context usage)   │
│  - Call orchestration tools (not raw data tools)           │
│  - Format results for user display                         │
└─────────────────────┬───────────────────────────────────────┘
                      │ MCP Protocol
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  PaidSearchNav MCP Server (Docker) - ORCHESTRATION LAYER    │
│                                                              │
│  Layer 1: Orchestration Tools (Phase 2.5 - 4/5 Complete ✅)│
│  ├─ analyze_keyword_match_types()     → Summary + Top 10 ✅│
│  ├─ analyze_search_term_waste()       → Summary + Top 10 ✅│
│  ├─ analyze_negative_conflicts()      → Summary + Top 10 ✅│
│  ├─ analyze_geo_performance()         → Summary + Top 10 ⚠️│
│  └─ analyze_pmax_cannibalization()    → Summary + Top 10 ✅│
│                                                              │
│  Layer 2: Data Retrieval Tools (Complete)                  │
│  ├─ get_keywords()          → Raw data (paginated)         │
│  ├─ get_search_terms()      → Raw data (paginated)         │
│  ├─ get_campaigns()         → Raw data                     │
│  ├─ get_negative_keywords() → Raw data                     │
│  ├─ get_geo_performance()   → Raw data                     │
│  └─ query_bigquery()        → Raw data                     │
│                                                              │
│  Infrastructure:                                            │
│  - Redis caching (TTL-based)                                │
│  - Google Ads API client                                   │
│  - BigQuery client                                          │
│  - Error handling & rate limiting                          │
└─────────────────────────────────────────────────────────────┘
\`\`\`

**Key Innovation**: Server performs analysis and returns compact summaries (11-34 lines) instead of raw data (thousands of lines), eliminating Claude Desktop's context window limitations.

## Quick Start

### Prerequisites

- Python 3.12+
- Docker & Docker Compose (for containerized deployment)
- Google Ads API credentials
- GCP service account for BigQuery (optional)

### Local Development Setup

1. **Clone the repository:**
   \`\`\`bash
   git clone <repository-url>
   cd PaidSearchNav-MCP
   \`\`\`

2. **Create and activate virtual environment:**
   \`\`\`bash
   python3 -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\\Scripts\\activate
   \`\`\`

3. **Install dependencies:**
   \`\`\`bash
   pip install -e ".[dev]"
   \`\`\`

4. **Configure environment variables:**
   \`\`\`bash
   cp .env.example .env
   # Edit .env with your credentials
   \`\`\`

5. **Run tests:**
   \`\`\`bash
   pytest tests/test_server.py -v
   \`\`\`

6. **Start the MCP server:**
   \`\`\`bash
   python -m paidsearchnav_mcp.server
   \`\`\`

### Docker Deployment

1. **Build and run with Docker Compose:**
   \`\`\`bash
   docker-compose up -d
   \`\`\`

2. **Check health:**
   \`\`\`bash
   curl http://localhost:8080/health
   \`\`\`

3. **View logs:**
   \`\`\`bash
   docker-compose logs -f mcp-server
   \`\`\`

## Configuration

### Environment Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| \`GOOGLE_ADS_DEVELOPER_TOKEN\` | Google Ads API developer token | Yes | - |
| \`GOOGLE_ADS_CLIENT_ID\` | OAuth client ID | Yes | - |
| \`GOOGLE_ADS_CLIENT_SECRET\` | OAuth client secret | Yes | - |
| \`GOOGLE_ADS_REFRESH_TOKEN\` | OAuth refresh token | Yes | - |
| \`GOOGLE_ADS_LOGIN_CUSTOMER_ID\` | Manager account ID (without dashes) | Yes | - |
| \`GOOGLE_ADS_API_VERSION\` | Google Ads API version | No | \`v17\` |
| \`GOOGLE_APPLICATION_CREDENTIALS\` | Path to GCP service account JSON | Optional | - |
| \`GCP_PROJECT_ID\` | GCP project ID for BigQuery | Optional | - |
| \`REDIS_URL\` | Redis connection URL | No | \`redis://localhost:6379/0\` |
| \`REDIS_TTL\` | Cache TTL in seconds | No | \`3600\` |
| \`ENVIRONMENT\` | Environment name (development/production) | No | \`development\` |

For detailed instructions on obtaining Google Ads API credentials, see [docs/GOOGLE_ADS_SETUP.md](docs/GOOGLE_ADS_SETUP.md).

## Quick Test

Once you have your credentials configured, you can quickly test the MCP server functionality.

### Test 1: Verify Server Health

Start the server and check the health endpoint:

\`\`\`bash
# Terminal 1: Start the MCP server
python -m paidsearchnav_mcp.server

# Terminal 2: Check health (if HTTP endpoint is available)
curl http://localhost:8080/health
\`\`\`

### Test 2: Configure MCP Client

Add the server to your Claude Desktop configuration (\`~/Library/Application Support/Claude/claude_desktop_config.json\` on macOS):

\`\`\`json
{
  "mcpServers": {
    "paidsearchnav": {
      "command": "python",
      "args": ["-m", "paidsearchnav_mcp.server"],
      "env": {
        "GOOGLE_ADS_DEVELOPER_TOKEN": "your_token",
        "GOOGLE_ADS_CLIENT_ID": "your_client_id.apps.googleusercontent.com",
        "GOOGLE_ADS_CLIENT_SECRET": "your_client_secret",
        "GOOGLE_ADS_REFRESH_TOKEN": "your_refresh_token",
        "GOOGLE_ADS_LOGIN_CUSTOMER_ID": "1234567890",
        "REDIS_URL": "redis://localhost:6379/0"
      }
    }
  }
}
\`\`\`

Or use environment variables from your \`.env\` file:

\`\`\`json
{
  "mcpServers": {
    "paidsearchnav": {
      "command": "python",
      "args": ["-m", "paidsearchnav_mcp.server"],
      "cwd": "/path/to/PaidSearchNav-MCP"
    }
  }
}
\`\`\`

### Test 3: Query Sample Data

Restart Claude Desktop and test with these sample queries:

**Get campaigns for a customer:**
\`\`\`
Use the get_campaigns tool to fetch campaigns for customer ID 1234567890
\`\`\`

**Fetch search terms:**
\`\`\`
Use the get_search_terms tool to get search terms data for customer 1234567890
from the last 30 days
\`\`\`

**Get keywords with match types:**
\`\`\`
Use the get_keywords tool to retrieve all keywords for customer 1234567890,
showing match types and quality scores
\`\`\`

### Test 4: Verify Redis Caching (Optional)

If you've configured Redis caching, verify it's working:

**1. Check Redis connection:**

\`\`\`bash
redis-cli ping  # Should return PONG
\`\`\`

**2. Make the same query twice:**

\`\`\`
Use the get_campaigns tool twice with the same parameters:
Customer ID: 1234567890, dates: 2024-01-01 to 2024-01-31
\`\`\`

**3. Check the logs for cache hits:**

\`\`\`
First request: "Cache miss for campaigns query: customer=1234567890"
Second request: "Cache hit for campaigns query: customer=1234567890"
\`\`\`

**4. Verify performance improvement:**

- First request: ~500-1000ms (API call)
- Second request: ~10-50ms (cache hit)

**Cache TTL:** Results are cached for 1-4 hours depending on data type (configurable via \`REDIS_TTL\` in \`.env\`)

### Test 5: Verify Data is Returned

Successful responses should include:

- **Campaigns**: Campaign ID, name, status, budget, targeting settings
- **Search Terms**: Query text, match type, clicks, impressions, cost, conversions
- **Keywords**: Keyword text, match type, quality score, performance metrics

Example expected output:
\`\`\`json
{
  "campaigns": [
    {
      "id": "1234567890",
      "name": "Brand Campaign",
      "status": "ENABLED",
      "budget": 100.0,
      "bidding_strategy": "MAXIMIZE_CONVERSIONS"
    }
  ]
}
\`\`\`

### Test 5: Docker Environment Test

Test the containerized setup:

\`\`\`bash
# Start services with docker-compose
docker-compose up -d

# Check server logs
docker-compose logs -f mcp-server

# Test health endpoint
curl http://localhost:8080/health

# Verify Redis is running
docker-compose exec redis redis-cli ping
# Should return: PONG
\`\`\`

### Troubleshooting Quick Tests

If you encounter issues:

1. **Authentication errors**: Verify all credentials in \`.env\` are correct
2. **No data returned**: Check that the customer ID has accessible campaigns
3. **Connection timeouts**: Ensure Redis is running (\`docker-compose ps\`)
4. **Permission errors**: Verify your OAuth token has the correct scopes

See [docs/GOOGLE_ADS_SETUP.md](docs/GOOGLE_ADS_SETUP.md) for detailed troubleshooting steps.

## MCP Tools

The server exposes the following MCP tools:

### Orchestration Tools (Phase 2.5 - COMPLETE ✅)

**NEW**: Five server-side analyzers that return compact summaries (<100 lines) instead of raw data:

- **\`analyze_search_term_waste\`** ✅ - Identify wasted spend and recommend negative keywords (PRODUCTION READY)
  - **Savings Identified**: $1,553.43/month (from test account)
  - **Performance**: 18.24s, 34 lines output

- **\`analyze_negative_conflicts\`** ✅ - Detect negative keywords blocking positive keywords (PRODUCTION READY)
  - **Value**: Revenue protection, 12,282 conflicts detected
  - **Performance**: 19.38s, 34 lines output

- **\`analyze_pmax_cannibalization\`** ✅ - Identify PMax/Search overlap (PRODUCTION READY)
  - **Value**: ROI optimization
  - **Performance**: 25.47s, 11 lines output

- **\`analyze_keyword_match_types\`** ✅ - Recommend match type optimizations (PRODUCTION READY)
  - **Savings Identified**: $20.80/month (from test account)
  - **Performance**: 27.35s, 15 lines output

- **\`analyze_geo_performance\`** ⚠️ - Suggest geographic bid adjustments (FIX IN PROGRESS - Issue #20)
  - **Status**: GAQL query fixed, ROAS calculation bug being addressed
  - **Expected**: Ready within 24 hours

**Status**: 4/5 production-ready (80%), 1 fix in progress

**Business Value Demonstrated**: $1,574.23/month in optimization opportunities identified from single test account

**Architecture Achievement**: Solved context window issue - 95% reduction in response size (800 lines → 23 lines avg)

See [Phase 2.5 Completion Report](docs/reports/phase-2.5-completion-report.md) for detailed analysis.

### Data Retrieval Tools (Google Ads API)

- **\`get_search_terms\`** - Fetch search terms data with performance metrics
- **\`get_keywords\`** - Retrieve keywords with match types and quality scores
- **\`get_campaigns\`** - Get campaign settings and performance data
- **\`get_negative_keywords\`** - Fetch negative keywords and shared lists
- **\`get_geo_performance\`** - Geographic performance by location

### BigQuery Tools

- **\`query_bigquery\`** - Execute custom SQL queries against BigQuery

## MCP Resources

- **\`resource://health\`** - Server health status and configuration
- **\`resource://config\`** - Feature availability and settings

## Development

### Project Structure

\`\`\`
PaidSearchNav-MCP/
├── src/
│   └── paidsearchnav_mcp/
│       ├── __init__.py
│       ├── server.py              # MCP server entry point
│       ├── analyzers/             # NEW: Orchestration layer (Phase 2.5)
│       │   ├── base.py            # BaseAnalyzer + AnalysisSummary
│       │   ├── keyword_match.py   # KeywordMatchAnalyzer
│       │   ├── search_term_waste.py        # SearchTermWasteAnalyzer ✅
│       │   ├── negative_conflicts.py       # NegativeConflictAnalyzer ✅
│       │   ├── geo_performance.py          # GeoPerformanceAnalyzer
│       │   └── pmax_cannibalization.py     # PMaxCannibalizationAnalyzer
│       ├── clients/               # API clients
│       │   ├── google/            # Google Ads client
│       │   ├── bigquery/          # BigQuery client
│       │   └── ga4/               # GA4 client
│       ├── models/                # Data models
│       └── data_providers/        # Data provider interfaces
├── tests/
│   ├── test_server.py
│   ├── test_analyzers.py          # NEW: Analyzer unit tests
│   ├── test_orchestration_tools.py # NEW: Orchestration tool tests
│   └── bugs/                      # NEW: Bug reproduction tests
├── scripts/
│   ├── test_orchestration_direct.py      # NEW: Integration tests
│   └── test_orchestration_integration.py
├── docs/
│   └── bugs/                      # NEW: Bug reports
│       ├── README.md
│       ├── 2025-11-27-keyword-match-no-data.md
│       ├── 2025-11-27-geo-performance-gaql-error.md
│       └── 2025-11-27-pmax-analyzer-slow.md
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── README.md
\`\`\`

### Running Tests

\`\`\`bash
# Specific test file (recommended for now)
pytest tests/test_server.py -v

# With coverage
pytest tests/test_server.py --cov=paidsearchnav_mcp --cov-report=html
\`\`\`

### Code Quality

\`\`\`bash
# Format code
ruff format src/

# Lint
ruff check src/

# Type check
mypy src/
\`\`\`

## Deployment

### Docker Image Size

The production Docker image is optimized to be ~200MB (vs 1.5GB for the original PaidSearchNav app):

- Python 3.12-slim base image
- Only 8 core dependencies
- No database or web framework overhead

## License

[Your License Here]

## Support

For issues and questions:
- GitHub Issues: https://github.com/datablogin/PaidSearchNav-MCP/issues
- Documentation: https://github.com/datablogin/PaidSearchNav
