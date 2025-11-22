# Local Docker Development Setup

This document describes how to run PaidSearchNav locally using Docker containers for PostgreSQL and Redis, instead of relying on AWS services.

## Overview

The local setup includes:
- PostgreSQL 15 database running in Docker (port 5434)
- Redis 7 cache running in Docker (port 6380)
- FastAPI application running locally with full database connectivity
- Customer initialization functionality (minus S3 integration)

## Prerequisites

- Docker and Docker Compose installed
- Python 3.10+ with virtual environment activated
- All project dependencies installed: `uv pip install -e ".[dev,test]"`

## Setup Instructions

### 1. Start Docker Containers

```bash
# Start PostgreSQL and Redis containers
docker-compose -f docker-compose.dev.yml up -d

# Verify containers are running and healthy
docker ps
```

You should see:
- `paidsearchnav-postgres-dev` on port 5434 (healthy)
- `paidsearchnav-redis-dev` on port 6380 (healthy)

### 2. Configure Environment

Use the `.env.dev` file for local development:

```bash
# Activate virtual environment
source .venv/bin/activate

# Load development environment variables
set -a && source .env.dev && set +a
```

Key configuration in `.env.dev`:
- Database: `postgresql+asyncpg://devuser:devpass123@localhost:5434/paidsearchnav_dev`
- Redis: `redis://localhost:6380/0`
- Debug mode enabled
- Google Ads API credentials configured
- S3 configuration commented out (not needed for local testing)

### 3. Initialize Database

The database tables are automatically created when the API server starts. You can verify with:

```bash
# Check database tables
docker exec paidsearchnav-postgres-dev psql -U devuser -d paidsearchnav_dev -c "\\dt"
```

### 4. Start API Server

```bash
# Start the FastAPI server
python -m paidsearchnav.api.run
```

The server will start on `http://localhost:8000` with:
- Health endpoint: `GET /health`
- API docs: `http://localhost:8000/docs`
- Customer endpoints: `/api/v1/customers/`

## Testing Customer Initialization

### Create Test Data and Test API

Use the provided test script:

```bash
python test_customer_init.py
```

This script will:
1. Create a test user and Fitness Connection customer in the database
2. Generate a JWT token for authentication
3. Test the health endpoint
4. Test customer retrieval
5. Test customer initialization (will fail at S3 step, which is expected)

### Manual API Testing

You can also test manually using curl:

```bash
# Health check
curl -X GET http://localhost:8000/health

# Get customer (requires auth token from test script)
curl -X GET http://localhost:8000/api/v1/customers/{customer_id} \\
  -H "Authorization: Bearer {your_jwt_token}"

# Initialize customer
curl -X POST http://localhost:8000/api/v1/customers/{customer_id}/initialize \\
  -H "Authorization: Bearer {your_jwt_token}" \\
  -H "Content-Type: application/json"
```

## Database Access

### Connect to PostgreSQL

```bash
# Using Docker exec
docker exec -it paidsearchnav-postgres-dev psql -U devuser -d paidsearchnav_dev

# Or if you have psql installed locally
PGPASSWORD=devpass123 psql -h localhost -p 5434 -U devuser -d paidsearchnav_dev
```

### Common Queries

```sql
-- Check users
SELECT * FROM users;

-- Check customers
SELECT id, name, google_ads_customer_id FROM customers;

-- Check customer access
SELECT user_id, customer_id, access_level FROM customer_access;

-- Check tables
\\dt
```

## Configuration Files

### docker-compose.dev.yml
- PostgreSQL 15 container with persistent data
- Redis 7 container with persistent data
- Health checks for both services
- Isolated from other PostgreSQL instances (uses port 5434)

### .env.dev
- Complete development environment configuration
- Database connection strings for both sync and async operations
- Google Ads API credentials
- JWT configuration for authentication
- Debug settings enabled

## Important Fixes Applied

During setup, several issues were resolved:

1. **Token Blacklist Initialization**: Fixed `AttributeError` in token blacklist module
2. **Database Schema Mismatch**: Updated repository queries to use `created_by` instead of `user_id`
3. **Environment Variables**: Ensured all required variables are properly set
4. **Server Reload**: Fixed uvicorn reload configuration for development

## Limitations

### S3 Integration
Customer initialization will fail at the S3 folder creation step because:
- No AWS credentials configured locally
- S3 bucket not available in local environment

For full customer initialization to work, you would need:
```bash
# Add to .env.dev
PSN_AWS_ACCESS_KEY_ID=your_aws_access_key
PSN_AWS_SECRET_ACCESS_KEY=your_aws_secret_key
PSN_AWS_S3_BUCKET=your_s3_bucket_name
PSN_AWS_REGION=us-east-1
```

### Google Ads Validation
Google Ads account validation will use the configured API credentials but may require actual OAuth tokens for full functionality.

## Cleanup

```bash
# Stop containers
docker-compose -f docker-compose.dev.yml down

# Remove containers and volumes (WARNING: deletes all data)
docker-compose -f docker-compose.dev.yml down -v

# Remove test script
rm test_customer_init.py
```

## Troubleshooting

### Container Issues
```bash
# Check container logs
docker logs paidsearchnav-postgres-dev
docker logs paidsearchnav-redis-dev

# Restart containers
docker-compose -f docker-compose.dev.yml restart
```

### Database Connection Issues
```bash
# Verify database is accessible
docker exec paidsearchnav-postgres-dev pg_isready -U devuser -d paidsearchnav_dev
```

### API Server Issues
```bash
# Check if port 8000 is in use
lsof -i :8000

# Check environment variables are loaded
printenv | grep PSN_
```

## Summary

This local Docker setup provides a fully functional development environment for PaidSearchNav without requiring AWS services. The core application functionality, including customer management and database operations, works completely. Only the S3 integration requires AWS credentials for full functionality.

The setup is ideal for:
- Local development and testing
- Database schema validation
- API endpoint testing
- Customer initialization flow testing (up to S3 step)
- Integration testing without external dependencies