# UI Integration Guide for PaidSearchNav

This guide provides comprehensive instructions for building a user interface that connects to the PaidSearchNav backend.

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [Backend Services](#backend-services)
3. [Data Models](#data-models)
4. [Authentication Flow](#authentication-flow)
5. [API Endpoints Required](#api-endpoints-required)
6. [Implementation Steps](#implementation-steps)
7. [Real-time Updates](#real-time-updates)
8. [Error Handling](#error-handling)
9. [Best Practices](#best-practices)

## Architecture Overview

PaidSearchNav is a Python-based Google Ads audit tool with:
- **Core Backend**: Python with async support
- **Data Storage**: SQLAlchemy (SQLite/PostgreSQL)
- **Job Scheduling**: APScheduler
- **Authentication**: OAuth2 with Google Ads
- **Report Generation**: HTML, PDF, CSV, JSON formats

### Current State
- ✅ Complete backend business logic
- ✅ Programmatic API (`SchedulerAPI`)
- ❌ No HTTP server layer
- ❌ No web UI framework

## Backend Services

### 1. Analyzers (Business Logic)
Located in `paidsearchnav/analyzers/`:

```python
# Each analyzer implements the Analyzer interface
- SearchTermsAnalyzer      # Find keyword opportunities/waste
- KeywordMatchAnalyzer     # Optimize match types
- NegativeConflictsAnalyzer # Find blocking negatives
- GeoPerformanceAnalyzer   # Location insights
- PerformanceMaxAnalyzer   # PMax campaign analysis
- SharedNegativesValidator # Cross-campaign validation
```

### 2. Core Components

#### SchedulerAPI (`paidsearchnav/scheduler/api.py`)
Main programmatic interface with methods:
```python
async def trigger_audit(request: TriggerAuditRequest) -> JobStatusResponse
async def schedule_audit(request: ScheduleAuditRequest) -> JobStatusResponse
async def get_job_status(job_id: str) -> JobStatusResponse
async def get_job_history(customer_id: str, limit: int, offset: int) -> JobHistoryResponse
async def cancel_job(job_id: str) -> Dict[str, Any]
async def trigger_single_analyzer(request: TriggerSingleAnalyzerRequest) -> JobStatusResponse
```

#### GoogleAdsClient (`paidsearchnav/platforms/google/client.py`)
Handles all Google Ads API interactions:
- Fetches campaigns, keywords, search terms
- Manages API quotas and retries
- Streams large datasets efficiently

#### OAuth2TokenManager (`paidsearchnav/platforms/google/auth.py`)
Manages Google OAuth2 authentication:
- Handles OAuth2 flow
- Stores encrypted tokens
- Auto-refreshes expired tokens
- Supports multiple storage backends

## Data Models

All models use Pydantic for validation. Key models in `paidsearchnav/core/models/`:

### Input Models
```python
class TriggerAuditRequest(BaseModel):
    customer_id: str
    analyzers: Optional[List[str]] = None  # Run specific analyzers
    date_range: Optional[DateRange] = None  # Custom date range
    config_overrides: Optional[Dict[str, Any]] = None

class ScheduleAuditRequest(BaseModel):
    customer_id: str
    cron_expression: str  # e.g., "0 0 1 */3 *" for quarterly
    analyzers: Optional[List[str]] = None
    enabled: bool = True
```

### Output Models
```python
class AnalysisResult(BaseModel):
    analyzer_name: str
    timestamp: datetime
    summary: str
    recommendations: List[Recommendation]
    metrics: Dict[str, Any]
    metadata: Dict[str, Any]

class Recommendation(BaseModel):
    priority: Priority  # HIGH, MEDIUM, LOW
    category: str
    description: str
    impact: str
    action_data: Dict[str, Any]  # Specific data for UI actions
```

### Google Ads Models
```python
class Keyword(BaseModel):
    resource_name: str
    text: str
    match_type: str
    status: str
    campaign_id: str
    ad_group_id: str
    metrics: KeywordMetrics

class SearchTerm(BaseModel):
    query: str
    campaign_id: str
    ad_group_id: str
    keyword_id: str
    metrics: SearchTermMetrics
```

## Authentication Flow

### 1. Initial OAuth2 Setup
```javascript
// UI initiates OAuth2 flow
const authUrl = await fetch('/api/auth/google', {
  method: 'POST',
  body: JSON.stringify({ 
    customer_id: 'customer123',
    redirect_uri: 'http://localhost:3000/auth/callback'
  })
});

// Redirect user to Google
window.location.href = authUrl.url;
```

### 2. Handle OAuth2 Callback
```javascript
// After Google redirects back
const response = await fetch('/api/auth/callback', {
  method: 'POST',
  body: JSON.stringify({
    code: authCode,
    state: state,
    customer_id: 'customer123'
  })
});
```

### 3. Token Storage
Backend automatically:
- Encrypts tokens with Fernet
- Stores in configured backend (local/AWS/GCP/Vault)
- Associates with customer_id
- Handles refresh automatically

## API Endpoints Required

### Web Framework Layer (To Be Implemented)
```python
# Example using FastAPI
from fastapi import FastAPI, Depends, HTTPException
from paidsearchnav.scheduler.api import SchedulerAPI

app = FastAPI()

# Authentication
POST   /api/auth/google              # Initiate OAuth2
POST   /api/auth/callback            # OAuth2 callback
DELETE /api/auth/revoke/{customer_id} # Revoke access

# Customer Management
GET    /api/customers                # List authenticated customers
GET    /api/customers/{id}/status    # Check auth status

# Audit Operations
POST   /api/audits/trigger           # Run immediate audit
POST   /api/audits/schedule          # Schedule recurring audit
GET    /api/audits/{job_id}          # Get audit status/results
GET    /api/audits/history           # List past audits (paginated)
DELETE /api/audits/{job_id}          # Cancel scheduled audit

# Analysis Results
GET    /api/results/{audit_id}       # Get full audit results
GET    /api/results/{audit_id}/{analyzer} # Get specific analyzer results

# Reports
GET    /api/reports/{audit_id}/generate # Generate report
GET    /api/reports/{audit_id}/download # Download generated report
GET    /api/reports/formats          # Available report formats

# Dashboard
GET    /api/dashboard/{audit_id}     # Get dashboard data
GET    /api/dashboard/{audit_id}/geo # Geographic performance data

# Real-time Updates
WS     /ws/audits/{job_id}          # WebSocket for live updates
```

## Implementation Steps

### Step 1: Add Web Framework
```python
# requirements.txt additions
fastapi==0.104.1
uvicorn==0.24.0
python-multipart==0.0.6
websockets==12.0

# main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from paidsearchnav.scheduler.api import SchedulerAPI

app = FastAPI(title="PaidSearchNav API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize backend services
scheduler_api = SchedulerAPI()
```

### Step 2: Implement Authentication Endpoints
```python
from fastapi import APIRouter, HTTPException
from paidsearchnav.platforms.google.auth import OAuth2TokenManager

auth_router = APIRouter(prefix="/api/auth")
token_manager = OAuth2TokenManager()

@auth_router.post("/google")
async def initiate_oauth(customer_id: str, redirect_uri: str):
    auth_url = token_manager.get_authorization_url(
        customer_id=customer_id,
        redirect_uri=redirect_uri
    )
    return {"url": auth_url}

@auth_router.post("/callback")
async def oauth_callback(code: str, state: str, customer_id: str):
    try:
        await token_manager.exchange_code_for_token(
            code=code,
            customer_id=customer_id
        )
        return {"status": "success", "customer_id": customer_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
```

### Step 3: Implement Audit Endpoints
```python
@app.post("/api/audits/trigger")
async def trigger_audit(request: TriggerAuditRequest):
    try:
        result = await scheduler_api.trigger_audit(request)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/audits/{job_id}")
async def get_audit_status(job_id: str):
    try:
        status = await scheduler_api.get_job_status(job_id)
        return status
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))
```

### Step 4: Add WebSocket Support
```python
from fastapi import WebSocket
from asyncio import create_task
import json

@app.websocket("/ws/audits/{job_id}")
async def audit_websocket(websocket: WebSocket, job_id: str):
    await websocket.accept()
    
    async def send_updates():
        while True:
            status = await scheduler_api.get_job_status(job_id)
            await websocket.send_json(status.dict())
            
            if status.status in ["completed", "failed", "cancelled"]:
                break
                
            await asyncio.sleep(2)  # Poll every 2 seconds
    
    task = create_task(send_updates())
    
    try:
        while True:
            await websocket.receive_text()  # Keep connection alive
    except:
        task.cancel()
        await websocket.close()
```

## Real-time Updates

### WebSocket Connection (Frontend)
```javascript
class AuditWebSocket {
  constructor(jobId) {
    this.ws = new WebSocket(`ws://localhost:8000/ws/audits/${jobId}`);
    
    this.ws.onmessage = (event) => {
      const status = JSON.parse(event.data);
      this.updateUI(status);
      
      if (['completed', 'failed', 'cancelled'].includes(status.status)) {
        this.ws.close();
      }
    };
  }
  
  updateUI(status) {
    // Update progress bar
    document.getElementById('progress').value = status.progress;
    
    // Update status text
    document.getElementById('status').textContent = status.status;
    
    // Show results when complete
    if (status.status === 'completed') {
      this.loadResults(status.job_id);
    }
  }
}
```

### Polling Alternative
```javascript
async function pollAuditStatus(jobId) {
  const interval = setInterval(async () => {
    const response = await fetch(`/api/audits/${jobId}`);
    const status = await response.json();
    
    updateUI(status);
    
    if (['completed', 'failed', 'cancelled'].includes(status.status)) {
      clearInterval(interval);
    }
  }, 2000);
}
```

## Error Handling

### Backend Error Response Format
```python
class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
    code: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)
```

### Frontend Error Handling
```javascript
class APIClient {
  async request(url, options = {}) {
    try {
      const response = await fetch(url, {
        ...options,
        headers: {
          'Content-Type': 'application/json',
          ...options.headers
        }
      });
      
      if (!response.ok) {
        const error = await response.json();
        throw new APIError(error.error, error.detail, error.code);
      }
      
      return await response.json();
    } catch (error) {
      if (error instanceof APIError) {
        this.handleAPIError(error);
      } else {
        this.handleNetworkError(error);
      }
      throw error;
    }
  }
  
  handleAPIError(error) {
    switch (error.code) {
      case 'AUTH_REQUIRED':
        this.redirectToAuth();
        break;
      case 'QUOTA_EXCEEDED':
        this.showQuotaWarning();
        break;
      default:
        this.showErrorNotification(error.message);
    }
  }
}
```

## Best Practices

### 1. State Management
```javascript
// Use a state management library (Redux, Zustand, etc.)
const useAuditStore = create((set) => ({
  currentAudit: null,
  auditHistory: [],
  isLoading: false,
  error: null,
  
  triggerAudit: async (customerId, analyzers) => {
    set({ isLoading: true, error: null });
    try {
      const result = await apiClient.triggerAudit({ 
        customer_id: customerId, 
        analyzers 
      });
      set({ currentAudit: result, isLoading: false });
      return result;
    } catch (error) {
      set({ error: error.message, isLoading: false });
      throw error;
    }
  }
}));
```

### 2. Caching Strategy
```javascript
// Cache analysis results
const resultCache = new Map();

async function getAnalysisResults(auditId, useCache = true) {
  const cacheKey = `results-${auditId}`;
  
  if (useCache && resultCache.has(cacheKey)) {
    return resultCache.get(cacheKey);
  }
  
  const results = await apiClient.getResults(auditId);
  resultCache.set(cacheKey, results);
  
  // Expire cache after 5 minutes
  setTimeout(() => resultCache.delete(cacheKey), 5 * 60 * 1000);
  
  return results;
}
```

### 3. Progressive Loading
```javascript
// Load critical data first
async function loadAuditDashboard(auditId) {
  // Load summary immediately
  const summary = await apiClient.getAuditSummary(auditId);
  displaySummary(summary);
  
  // Load detailed results in background
  Promise.all([
    apiClient.getKeywordAnalysis(auditId),
    apiClient.getSearchTermAnalysis(auditId),
    apiClient.getGeoPerformance(auditId)
  ]).then(([keywords, searchTerms, geo]) => {
    displayDetailedResults({ keywords, searchTerms, geo });
  });
}
```

### 4. Error Recovery
```javascript
// Implement retry logic
async function retryableRequest(fn, maxRetries = 3) {
  let lastError;
  
  for (let i = 0; i < maxRetries; i++) {
    try {
      return await fn();
    } catch (error) {
      lastError = error;
      
      // Don't retry auth errors
      if (error.code === 'AUTH_REQUIRED') {
        throw error;
      }
      
      // Exponential backoff
      await new Promise(resolve => 
        setTimeout(resolve, Math.pow(2, i) * 1000)
      );
    }
  }
  
  throw lastError;
}
```

### 5. UI Component Structure
```
src/
├── api/
│   ├── client.js         # API client wrapper
│   ├── auth.js           # Auth-specific API calls
│   └── audits.js         # Audit-specific API calls
├── components/
│   ├── audit/
│   │   ├── AuditTrigger.jsx
│   │   ├── AuditStatus.jsx
│   │   └── AuditResults.jsx
│   ├── dashboard/
│   │   ├── GeoDashboard.jsx
│   │   ├── MetricCards.jsx
│   │   └── RecommendationsList.jsx
│   └── reports/
│       ├── ReportGenerator.jsx
│       └── ReportViewer.jsx
├── hooks/
│   ├── useAudit.js       # Audit-related hooks
│   ├── useAuth.js        # Auth state hooks
│   └── useWebSocket.js   # WebSocket connection hook
└── stores/
    ├── auditStore.js     # Audit state management
    └── authStore.js      # Auth state management
```

## Security Considerations

1. **HTTPS Only**: Always use HTTPS in production
2. **CORS Configuration**: Restrict to specific origins
3. **Rate Limiting**: Implement per-customer rate limits
4. **Input Validation**: Validate all inputs on backend
5. **Token Security**: Never expose tokens to frontend
6. **API Keys**: Use environment variables, never commit

## Performance Optimization

1. **Pagination**: Use limit/offset for large datasets
2. **Lazy Loading**: Load analyzer results on-demand
3. **Compression**: Enable gzip for API responses
4. **CDN**: Serve static assets from CDN
5. **Database Indexing**: Ensure proper indexes on queries

## Development Workflow

1. **Start Backend Services**:
   ```bash
   # Start PostgreSQL (if using)
   docker-compose up -d postgres
   
   # Run migrations
   alembic upgrade head
   
   # Start API server
   uvicorn main:app --reload --port 8000
   ```

2. **Start Frontend Development**:
   ```bash
   # React example
   npm install
   npm start
   ```

3. **Test OAuth Flow**:
   - Use Google Ads test account
   - Configure OAuth2 credentials
   - Test token refresh

4. **Monitor Performance**:
   - Use backend logging
   - Implement frontend error tracking
   - Monitor API response times

## Common Integration Issues

1. **CORS Errors**: Ensure backend allows frontend origin
2. **Token Expiry**: Frontend should handle 401 responses
3. **WebSocket Disconnects**: Implement reconnection logic
4. **Large Datasets**: Use streaming/pagination
5. **Timezone Issues**: Always use UTC in API

## Next Steps

1. Choose a frontend framework (React, Vue, Angular)
2. Implement the web server layer (FastAPI recommended)
3. Set up development environment
4. Start with authentication flow
5. Build audit triggering UI
6. Add results visualization
7. Implement report generation
8. Add scheduling interface

This guide should provide everything needed to build a robust UI that integrates seamlessly with the PaidSearchNav backend.