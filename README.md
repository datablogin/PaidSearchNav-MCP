# PaidSearchNav MCP Server

A lightweight [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server providing access to Google Ads and BigQuery data for PaidSearchNav analyzers.

This is part of the PaidSearchNav refactoring effort to separate data connectivity (MCP server) from analysis logic (Claude Skills). See [thoughts/shared/research/2025-11-22-mcp-skills-refactoring-strategy.md](thoughts/shared/research/2025-11-22-mcp-skills-refactoring-strategy.md) for more details.

> **Note**: The original monolithic PaidSearchNav application has been archived to `archive/`. See [archive/README.md](archive/README.md) for reference material.

## Overview

The PaidSearchNav MCP server is a **minimal, containerized service** (~200MB Docker image) that provides:

- ✅ Google Ads API access via MCP tools
- ✅ BigQuery query execution- ✅ Campaign, keyword, and search terms data retrieval
- ✅ Geographic performance data
- ✅ Negative keyword conflict detection
- ✅ Redis-based caching for performance

## Architecture

\`\`\`
┌─────────────────────────────────────────┐
│  Claude with Skills (24 analyzer skills)│
│  - Cost efficiency analysis methodology  │
│  - Keyword match type optimization rules │
│  - Reporting format standards            │
└─────────────┬───────────────────────────┘
              │ MCP Protocol
              ▼
┌─────────────────────────────────────────┐
│  MCP Server (Docker Container ~200MB)   │
│  - Google Ads API tools                  │
│  - BigQuery data resources               │
│  - Campaign health check tools           │
└─────────────────────────────────────────┘
\`\`\`

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

### Test 4: Verify Data is Returned

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

### Google Ads Tools

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
│       ├── clients/               # API clients
│       │   ├── google/            # Google Ads client
│       │   ├── bigquery/          # BigQuery client
│       │   └── ga4/               # GA4 client
│       ├── models/                # Data models
│       └── data_providers/        # Data provider interfaces
├── tests/
│   └── test_server.py
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
