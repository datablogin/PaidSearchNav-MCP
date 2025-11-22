# PaidSearchNav REST API Guide

## Table of Contents
- [Overview](#overview)
- [Getting Started](#getting-started)
- [Authentication](#authentication)
- [API Endpoints](#api-endpoints)
- [Real-time Features](#real-time-features)
- [Error Handling](#error-handling)
- [Rate Limiting](#rate-limiting)
- [Examples](#examples)

## Overview

The PaidSearchNav REST API provides a comprehensive interface for managing Google Ads audits, schedules, and reports. Built with FastAPI, it offers:

- **RESTful Design**: Clean, predictable URLs and standard HTTP methods
- **Real-time Updates**: WebSocket and Server-Sent Events for live audit progress
- **Comprehensive Documentation**: Auto-generated OpenAPI docs at `/docs`
- **Security**: JWT-based authentication with Google OAuth2 integration
- **Performance**: Async operations, rate limiting, and efficient data handling

## Getting Started

### Running the API

1. **Install dependencies**:
```bash
pip install -e ".[dev,test]"
```

2. **Set environment variables**:
```bash
# Required
export PSN_JWT_SECRET_KEY="your-secret-key"
export PSN_GOOGLE_OAUTH_CLIENT_ID="your-client-id"
export PSN_GOOGLE_OAUTH_CLIENT_SECRET="your-client-secret"

# Optional
export PSN_API_CORS_ORIGINS="http://localhost:3000,https://app.example.com"
export PSN_JWT_EXPIRE_MINUTES=60
```

3. **Start the server**:
```bash
cd paidsearchnav/api
python run.py
```

The API will be available at `http://localhost:8000`

### API Documentation

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI Schema**: http://localhost:8000/openapi.json

### Quick Test

Check if the API is running:
```bash
curl http://localhost:8000/api/v1/health
```

Response:
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "timestamp": "2024-06-25T12:00:00Z",
  "services": {
    "database": true,
    "google_ads": true,
    "scheduler": true
  }
}
```

## Authentication

The API uses JWT tokens with Google OAuth2 for authentication.

### OAuth2 Flow

1. **Initialize OAuth2**:
```bash
curl -X POST http://localhost:8000/api/v1/auth/google/init \
  -H "Content-Type: application/json" \
  -d '{
    "redirect_uri": "http://localhost:3000/auth/callback",
    "state": "random-state-string"
  }'
```

Response:
```json
{
  "auth_url": "https://accounts.google.com/o/oauth2/v2/auth?client_id=...",
  "state": "random-state-string"
}
```

2. **Complete OAuth2** (after user authorizes):
```bash
curl -X POST http://localhost:8000/api/v1/auth/google/callback \
  -H "Content-Type: application/json" \
  -d '{
    "code": "authorization-code-from-google",
    "state": "random-state-string",
    "redirect_uri": "http://localhost:3000/auth/callback"
  }'
```

Response:
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

3. **Use the token** in subsequent requests:
```bash
curl http://localhost:8000/api/v1/audits \
  -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc..."
```

### API Key Authentication

For service-to-service communication:
```bash
curl http://localhost:8000/api/v1/health \
  -H "X-API-Key: your-api-key"
```

## API Endpoints

### Customer Management

#### List Customers
```http
GET /api/v1/customers
```

Query parameters:
- `offset`: Number of items to skip (default: 0)
- `limit`: Number of items to return (default: 20, max: 100)

Example:
```bash
curl http://localhost:8000/api/v1/customers?limit=10 \
  -H "Authorization: Bearer $TOKEN"
```

Response:
```json
{
  "items": [
    {
      "id": "customer-123",
      "name": "Acme Corp",
      "google_ads_customer_id": "123-456-7890",
      "is_active": true,
      "last_audit_date": "2024-06-01T00:00:00Z"
    }
  ],
  "total": 25,
  "offset": 0,
  "limit": 10
}
```

#### Get Customer Details
```http
GET /api/v1/customers/{customer_id}
```

Example:
```bash
curl http://localhost:8000/api/v1/customers/customer-123 \
  -H "Authorization: Bearer $TOKEN"
```

### Audit Management

#### Create Audit
```http
POST /api/v1/audits
```

Request body:
```json
{
  "name": "Q4 2024 Audit",
  "analyzers": [
    "keyword_match",
    "search_terms",
    "negative_conflicts",
    "geo_performance"
  ],
  "config": {
    "date_range": 90,
    "include_paused": false
  }
}
```

Example:
```bash
curl -X POST http://localhost:8000/api/v1/audits \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Monthly Audit",
    "analyzers": ["keyword_match", "search_terms"]
  }'
```

Response:
```json
{
  "audit_id": "audit-456",
  "message": "Audit created successfully"
}
```

#### Get Audit Status
```http
GET /api/v1/audits/{audit_id}
```

Example:
```bash
curl http://localhost:8000/api/v1/audits/audit-456 \
  -H "Authorization: Bearer $TOKEN"
```

Response:
```json
{
  "id": "audit-456",
  "name": "Monthly Audit",
  "status": "running",
  "progress": 45,
  "created_at": "2024-06-25T10:00:00Z",
  "analyzers": ["keyword_match", "search_terms"],
  "results_summary": null
}
```

#### List Audits
```http
GET /api/v1/audits
```

Query parameters:
- `status`: Filter by status (pending, running, completed, failed)
- `offset`: Pagination offset
- `limit`: Items per page

Example:
```bash
curl "http://localhost:8000/api/v1/audits?status=completed&limit=5" \
  -H "Authorization: Bearer $TOKEN"
```

#### Cancel Audit
```http
DELETE /api/v1/audits/{audit_id}
```

Example:
```bash
curl -X DELETE http://localhost:8000/api/v1/audits/audit-456 \
  -H "Authorization: Bearer $TOKEN"
```

### Schedule Management

#### Create Schedule
```http
POST /api/v1/schedules
```

Request body:
```json
{
  "name": "Weekly Audit",
  "cron_expression": "0 0 * * 0",
  "analyzers": ["keyword_match", "search_terms"],
  "config": {"date_range": 7},
  "enabled": true
}
```

Example:
```bash
curl -X POST http://localhost:8000/api/v1/schedules \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Monthly Audit",
    "cron_expression": "0 0 1 * *",
    "analyzers": ["keyword_match"],
    "enabled": true
  }'
```

#### Update Schedule
```http
PUT /api/v1/schedules/{schedule_id}
```

Example:
```bash
curl -X PUT http://localhost:8000/api/v1/schedules/schedule-123 \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"enabled": false}'
```

### Results & Reports

#### Get Audit Results
```http
GET /api/v1/results/{audit_id}
```

Example:
```bash
curl http://localhost:8000/api/v1/results/audit-456 \
  -H "Authorization: Bearer $TOKEN"
```

Response:
```json
{
  "audit_id": "audit-456",
  "status": "completed",
  "analyzers": [
    {
      "analyzer_name": "keyword_match",
      "status": "completed",
      "findings": [
        {
          "type": "broad_match_overuse",
          "keyword": "shoes",
          "current_match_type": "broad",
          "recommended_match_type": "phrase",
          "estimated_savings": 250.50
        }
      ],
      "metrics": {
        "total_keywords_analyzed": 1543,
        "issues_found": 234,
        "potential_savings": 5670.25
      }
    }
  ],
  "summary": {
    "total_recommendations": 47,
    "critical_issues": 12,
    "estimated_savings": 8560.75
  }
}
```

#### Get Specific Analyzer Results
```http
GET /api/v1/results/{audit_id}/{analyzer}
```

Example:
```bash
curl http://localhost:8000/api/v1/results/audit-456/keyword_match \
  -H "Authorization: Bearer $TOKEN"
```

#### Generate Report
```http
POST /api/v1/reports/{audit_id}/generate
```

Request body:
```json
{
  "format": "pdf",
  "template": "executive_summary",
  "include_recommendations": true,
  "include_charts": true
}
```

Example:
```bash
curl -X POST http://localhost:8000/api/v1/reports/audit-456/generate \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"format": "pdf"}'
```

Response:
```json
{
  "report_id": "report-789",
  "message": "Report generation started",
  "download_url": "/api/v1/reports/audit-456/download?report_id=report-789"
}
```

#### Download Report
```http
GET /api/v1/reports/{audit_id}/download?report_id={report_id}
```

Example:
```bash
curl http://localhost:8000/api/v1/reports/audit-456/download?report_id=report-789 \
  -H "Authorization: Bearer $TOKEN" \
  -o report.pdf
```

### Dashboard

#### Get Dashboard Data
```http
GET /api/v1/dashboard/{audit_id}
```

Example:
```bash
curl http://localhost:8000/api/v1/dashboard/audit-456 \
  -H "Authorization: Bearer $TOKEN"
```

Response includes aggregated metrics:
```json
{
  "audit": {
    "id": "audit-456",
    "name": "Monthly Audit",
    "status": "completed"
  },
  "summary": {
    "total_keywords": 1543,
    "total_spend": 125430.50,
    "wasted_spend": 18750.25,
    "potential_savings_percent": 15.0
  },
  "kpis": {
    "avg_cpc": 2.35,
    "avg_ctr": 3.2,
    "avg_conversion_rate": 2.8,
    "avg_cpa": 84.50,
    "roas": 3.2
  },
  "geographic_performance": {
    "top_performing_locations": [...],
    "distance_performance": [...]
  },
  "keyword_insights": {
    "match_type_distribution": {...},
    "negative_conflicts": 23
  },
  "recommendations_summary": {
    "high_priority": 12,
    "top_recommendations": [...]
  }
}
```

## Real-time Features

### WebSocket Connection

Connect to receive real-time audit updates:

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/v1/audits/audit-456?token=your-jwt-token');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Audit update:', data);
};

ws.send(JSON.stringify({
  type: 'subscribe',
  audit_id: 'audit-456'
}));
```

Message types:
- `audit_started`: Audit has begun processing
- `analyzer_progress`: Individual analyzer progress update
- `analyzer_completed`: Analyzer finished
- `audit_completed`: Entire audit finished
- `error`: Error occurred during processing

### Server-Sent Events

Alternative to WebSocket for one-way updates:

```javascript
const eventSource = new EventSource(
  'http://localhost:8000/api/v1/events?audit_id=audit-456',
  {
    headers: {
      'Authorization': 'Bearer your-jwt-token'
    }
  }
);

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Event:', data);
};
```

## Error Handling

The API returns consistent error responses:

```json
{
  "detail": "Error message",
  "code": "ERROR_CODE",
  "field": "field_name"  // For validation errors
}
```

Common HTTP status codes:
- `400`: Bad Request - Invalid input
- `401`: Unauthorized - Missing or invalid authentication
- `403`: Forbidden - Insufficient permissions
- `404`: Not Found - Resource doesn't exist
- `422`: Unprocessable Entity - Validation error
- `429`: Too Many Requests - Rate limit exceeded
- `500`: Internal Server Error

## Rate Limiting

The API implements rate limiting on critical endpoints:

- **Audit creation**: 5 per minute per user
- **Report generation**: 3 per hour per user
- **API calls**: 1000 per hour per IP

Rate limit headers:
```
X-RateLimit-Limit: 5
X-RateLimit-Remaining: 3
X-RateLimit-Reset: 1719321600
```

## Examples

### Complete Audit Workflow

```python
import asyncio
from examples.api_client_example import PaidSearchNavClient

async def run_audit():
    # Initialize client
    client = PaidSearchNavClient()
    
    # Authenticate
    auth_data = await client.init_google_auth("http://localhost:3000/callback")
    print(f"Visit: {auth_data['auth_url']}")
    
    # After user authorizes, complete auth
    code = input("Enter authorization code: ")
    token = await client.complete_google_auth(code)
    
    # Create audit
    audit = await client.create_audit(
        customer_id="123-456-7890",
        name="Q4 2024 Audit",
        analyzers=["keyword_match", "search_terms", "geo_performance"]
    )
    print(f"Created audit: {audit['audit_id']}")
    
    # Poll for completion
    while True:
        status = await client.get_audit(audit['audit_id'])
        print(f"Status: {status['status']} - Progress: {status['progress']}%")
        
        if status['status'] in ['completed', 'failed']:
            break
            
        await asyncio.sleep(5)
    
    # Get results
    if status['status'] == 'completed':
        results = await client.get_results(audit['audit_id'])
        print(f"Found {results['summary']['total_recommendations']} recommendations")
        
        # Generate report
        report = await client.generate_report(
            audit['audit_id'],
            format="pdf",
            template="executive_summary"
        )
        print(f"Report available at: {report['download_url']}")

if __name__ == "__main__":
    asyncio.run(run_audit())
```

### Using cURL

```bash
# Set your token
TOKEN="your-jwt-token"

# Create audit
AUDIT_ID=$(curl -s -X POST http://localhost:8000/api/v1/audits \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "API Test Audit",
    "analyzers": ["keyword_match"]
  }' | jq -r '.audit_id')

echo "Created audit: $AUDIT_ID"

# Check status
curl -s http://localhost:8000/api/v1/audits/$AUDIT_ID \
  -H "Authorization: Bearer $TOKEN" | jq '.status'

# Get results when complete
curl -s http://localhost:8000/api/v1/results/$AUDIT_ID \
  -H "Authorization: Bearer $TOKEN" | jq '.summary'
```

### JavaScript/TypeScript Client

```typescript
class PaidSearchNavAPI {
  private baseUrl: string;
  private token: string | null = null;

  constructor(baseUrl: string = 'http://localhost:8000') {
    this.baseUrl = baseUrl;
  }

  async authenticate(code: string, redirectUri: string): Promise<void> {
    const response = await fetch(`${this.baseUrl}/api/v1/auth/google/callback`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code, redirect_uri: redirectUri })
    });
    
    const data = await response.json();
    this.token = data.access_token;
  }

  async createAudit(name: string, analyzers: string[]): Promise<any> {
    const response = await fetch(`${this.baseUrl}/api/v1/audits`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${this.token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ name, analyzers })
    });
    
    return response.json();
  }

  streamAuditUpdates(auditId: string, onUpdate: (data: any) => void): EventSource {
    const eventSource = new EventSource(
      `${this.baseUrl}/api/v1/events?audit_id=${auditId}`,
      {
        headers: { 'Authorization': `Bearer ${this.token}` }
      }
    );
    
    eventSource.onmessage = (event) => {
      onUpdate(JSON.parse(event.data));
    };
    
    return eventSource;
  }
}
```

## Best Practices

1. **Authentication**: Always use HTTPS in production to protect JWT tokens
2. **Error Handling**: Implement retry logic for transient failures
3. **Rate Limiting**: Respect rate limits and implement backoff strategies
4. **Pagination**: Use pagination for list endpoints to handle large datasets
5. **Caching**: Cache results for completed audits as they don't change
6. **WebSocket**: Prefer WebSocket over polling for real-time updates
7. **Timeouts**: Set reasonable timeouts for long-running operations

## Troubleshooting

### Common Issues

1. **401 Unauthorized**
   - Check if JWT token is expired
   - Ensure Authorization header format is correct: `Bearer <token>`

2. **429 Rate Limited**
   - Implement exponential backoff
   - Consider caching responses

3. **WebSocket Connection Failed**
   - Check if token is passed correctly
   - Ensure WebSocket support in proxy/load balancer

4. **CORS Errors**
   - Verify your origin is in `PSN_API_CORS_ORIGINS`
   - Check browser console for specific CORS headers

### Debug Mode

Enable debug logging:
```bash
export PSN_DEBUG=true
export PSN_LOGGING_LEVEL=DEBUG
```

View API logs:
```bash
tail -f logs/paidsearchnav.log
```

## API Versioning

The API uses URL-based versioning. Current version: `v1`

Future versions will maintain backward compatibility where possible. Breaking changes will be documented with migration guides.

## Support

- **Documentation**: This guide and auto-generated API docs at `/docs`
- **Issues**: https://github.com/datablogin/PaidSearchNav/issues
- **Examples**: See `examples/api_client_example.py` for a complete client implementation