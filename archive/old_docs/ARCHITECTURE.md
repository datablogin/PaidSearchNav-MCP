# PaidSearchNav Architecture

This document describes the architecture and design decisions for the PaidSearchNav project.

## 🏗️ System Overview

PaidSearchNav is a modular Python application designed to audit Google Ads accounts for retail businesses. The architecture emphasizes:

- **Modularity**: Each analyzer can work independently
- **Extensibility**: Easy to add new analyzers or data sources
- **Testability**: Clear interfaces and dependency injection
- **Performance**: Efficient handling of large datasets

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   CLI/Scheduler │────▶│   Core Engine   │────▶│     Reports     │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │     Analyzers       │
                    │  ┌───────────────┐  │
                    │  │ Keyword Match │  │
                    │  ├───────────────┤  │
                    │  │ Search Terms  │  │
                    │  ├───────────────┤  │
                    │  │ Geo Analysis  │  │
                    │  ├───────────────┤  │
                    │  │     PMax      │  │
                    │  └───────────────┘  │
                    └─────────────────────┘
                               │
                    ┌──────────┴──────────┐
                    ▼                     ▼
            ┌──────────────┐     ┌──────────────┐
            │ Google Ads   │     │   Storage    │
            │     API      │     │  (DB/Files)  │
            └──────────────┘     └──────────────┘
```

## 📦 Package Structure

```
paidsearchnav/
├── core/                    # Core functionality
│   ├── interfaces.py       # Abstract base classes
│   ├── models/            # Data models
│   ├── config.py          # Configuration management
│   └── exceptions.py      # Custom exceptions
├── platforms/             # External platform integrations
│   └── google/           # Google Ads specific
│       ├── client.py     # API client wrapper
│       ├── auth.py       # OAuth2 authentication
│       └── models.py     # Platform-specific models
├── analyzers/            # Audit analyzers
│   ├── base.py          # Base analyzer class
│   ├── keyword_match.py
│   ├── search_terms.py
│   └── ...
├── storage/             # Data persistence
│   ├── repository.py    # Storage interface
│   └── backends/       # Storage implementations
├── reports/            # Report generation
│   ├── generator.py
│   └── templates/
├── api/                # REST API (Issue #86)
│   ├── __init__.py
│   ├── main.py        # FastAPI app initialization
│   ├── dependencies.py # Shared dependencies
│   ├── middleware.py   # Custom middleware
│   ├── v1/            # API v1 endpoints
│   │   ├── __init__.py
│   │   ├── auth.py    # Auth endpoints
│   │   ├── audits.py  # Audit endpoints
│   │   ├── schedules.py # Schedule endpoints
│   │   ├── results.py  # Results endpoints
│   │   ├── reports.py  # Report endpoints
│   │   └── websocket.py # WebSocket handlers
│   └── models/         # API-specific models
│       ├── __init__.py
│       ├── requests.py # API request models
│       └── responses.py # API response models
└── cli/               # Command-line interface
    └── main.py
```

## 🔌 Core Interfaces

All components implement these interfaces from `core/interfaces.py`:

### DataProvider

```python
from abc import ABC, abstractmethod
from typing import Any, Dict, List

class DataProvider(ABC):
    """Interface for data sources."""
    
    @abstractmethod
    async def fetch_campaigns(self, customer_id: str) -> List[Campaign]:
        """Fetch campaign data."""
        pass
    
    @abstractmethod
    async def fetch_keywords(self, campaign_id: str) -> List[Keyword]:
        """Fetch keyword data for a campaign."""
        pass
    
    @abstractmethod
    async def fetch_search_terms(self, campaign_id: str, days: int = 90) -> List[SearchTerm]:
        """Fetch search term report data."""
        pass
```

### Analyzer

```python
class Analyzer(ABC):
    """Base interface for all analyzers."""
    
    @abstractmethod
    async def analyze(self, data_provider: DataProvider, config: Dict[str, Any]) -> AnalysisResult:
        """Run the analysis and return results."""
        pass
    
    @abstractmethod
    def get_name(self) -> str:
        """Return analyzer name."""
        pass
    
    @abstractmethod
    def get_description(self) -> str:
        """Return analyzer description."""
        pass
```

### Storage

```python
class Storage(ABC):
    """Interface for data persistence."""
    
    @abstractmethod
    async def save_analysis(self, result: AnalysisResult) -> str:
        """Save analysis results and return ID."""
        pass
    
    @abstractmethod
    async def get_analysis(self, analysis_id: str) -> AnalysisResult:
        """Retrieve analysis by ID."""
        pass
    
    @abstractmethod
    async def list_analyses(self, customer_id: str) -> List[AnalysisResult]:
        """List all analyses for a customer."""
        pass
```

### ReportGenerator

```python
class ReportGenerator(ABC):
    """Interface for report generation."""
    
    @abstractmethod
    async def generate(self, results: List[AnalysisResult], format: str) -> bytes:
        """Generate report in specified format."""
        pass
    
    @abstractmethod
    def get_supported_formats(self) -> List[str]:
        """Return list of supported formats."""
        pass
```

## 📊 Data Models

Core data models in `core/models/`:

### Campaign Model
```python
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List

class Campaign(BaseModel):
    """Google Ads campaign representation."""
    id: str
    name: str
    status: str
    type: str
    budget: float
    bidding_strategy: str
    created_date: datetime
    modified_date: datetime
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "123456789",
                "name": "Store Visit - Seattle",
                "status": "ENABLED",
                "type": "SEARCH",
                "budget": 1000.0,
                "bidding_strategy": "TARGET_CPA"
            }
        }
```

### Keyword Model
```python
class Keyword(BaseModel):
    """Keyword representation."""
    id: str
    campaign_id: str
    ad_group_id: str
    text: str
    match_type: str  # BROAD, PHRASE, EXACT
    status: str
    bid: Optional[float]
    quality_score: Optional[int]
    
    # Performance metrics
    impressions: int
    clicks: int
    conversions: float
    cost: float
    
    @property
    def ctr(self) -> float:
        """Calculate click-through rate."""
        return self.clicks / self.impressions if self.impressions > 0 else 0.0
    
    @property
    def cpa(self) -> float:
        """Calculate cost per acquisition."""
        return self.cost / self.conversions if self.conversions > 0 else 0.0
```

### AnalysisResult Model
```python
class AnalysisResult(BaseModel):
    """Result from an analyzer."""
    analyzer_name: str
    timestamp: datetime
    customer_id: str
    summary: Dict[str, Any]
    findings: List[Finding]
    recommendations: List[Recommendation]
    metrics: Dict[str, float]
    
class Finding(BaseModel):
    """A specific finding from analysis."""
    severity: str  # HIGH, MEDIUM, LOW
    category: str
    description: str
    impact: str
    affected_items: List[str]
    
class Recommendation(BaseModel):
    """An actionable recommendation."""
    priority: int
    action: str
    expected_impact: str
    effort: str  # HIGH, MEDIUM, LOW
    items: List[str]
```

## 🔧 Configuration

Configuration uses environment variables with the `PSN_` prefix:

```python
# core/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Google Ads
    google_ads_developer_token: str
    google_ads_client_id: str
    google_ads_client_secret: str
    
    # Storage
    storage_backend: str = "postgresql"
    storage_connection_string: str
    
    # Features
    enable_pmax_analysis: bool = True
    enable_geo_dashboard: bool = True
    
    class Config:
        env_prefix = "PSN_"
```

## 🚀 Analyzer Implementation

Example analyzer implementation:

```python
# analyzers/keyword_match.py
from typing import Dict, Any, List
from paidsearchnav.core.interfaces import Analyzer, DataProvider
from paidsearchnav.core.models import AnalysisResult, Finding, Recommendation

class KeywordMatchAnalyzer(Analyzer):
    """Analyzes keyword match type distribution and performance."""
    
    async def analyze(self, data_provider: DataProvider, config: Dict[str, Any]) -> AnalysisResult:
        # Fetch data
        campaigns = await data_provider.fetch_campaigns(config["customer_id"])
        
        all_keywords = []
        for campaign in campaigns:
            if campaign.type == "SEARCH":
                keywords = await data_provider.fetch_keywords(campaign.id)
                all_keywords.extend(keywords)
        
        # Analyze match type distribution
        match_type_stats = self._calculate_match_type_stats(all_keywords)
        
        # Find issues
        findings = self._identify_issues(match_type_stats)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(findings)
        
        return AnalysisResult(
            analyzer_name=self.get_name(),
            timestamp=datetime.utcnow(),
            customer_id=config["customer_id"],
            summary=match_type_stats,
            findings=findings,
            recommendations=recommendations,
            metrics={
                "total_keywords": len(all_keywords),
                "broad_match_percentage": match_type_stats["broad"]["percentage"],
                "wasted_spend": match_type_stats["broad"]["wasted_spend"]
            }
        )
    
    def _calculate_match_type_stats(self, keywords: List[Keyword]) -> Dict[str, Any]:
        # Implementation details...
        pass
```

## 🗄️ Storage Layer

The storage layer abstracts data persistence:

```python
# storage/repository.py
from typing import Optional
from paidsearchnav.core.interfaces import Storage
from paidsearchnav.storage.backends import get_backend

class Repository(Storage):
    """Main storage repository."""
    
    def __init__(self, settings: Settings):
        self.backend = get_backend(settings.storage_backend, settings)
    
    async def save_analysis(self, result: AnalysisResult) -> str:
        return await self.backend.save(result)
    
    async def get_analysis(self, analysis_id: str) -> Optional[AnalysisResult]:
        return await self.backend.get(analysis_id)
```

## 🧪 Testing Strategy

### Unit Tests
- Mock all external dependencies
- Test each analyzer independently
- Test data models and validation
- Test configuration loading

### Integration Tests
- Test with Google Ads sandbox account
- Test storage backends
- Test end-to-end workflows

### Test Structure
```
tests/
├── unit/
│   ├── analyzers/
│   │   ├── test_keyword_match.py
│   │   └── test_search_terms.py
│   ├── core/
│   │   ├── test_models.py
│   │   └── test_config.py
│   └── platforms/
│       └── google/
│           └── test_client.py
└── integration/
    ├── test_google_ads_api.py
    └── test_storage.py
```

## 🔒 Security Considerations

1. **API Credentials**: Never stored in code, always use environment variables
2. **OAuth2 Tokens**: Encrypted at rest, automatic refresh
3. **Data Privacy**: No PII stored, only aggregate metrics
4. **Access Control**: MCC-level permissions required
5. **Audit Logging**: All API calls logged for compliance

## 🎯 Performance Considerations

1. **Batch API Calls**: Fetch data in batches to minimize API calls
2. **Async Operations**: Use async/await for concurrent operations
3. **Caching**: Cache API responses for repeated analyses
4. **Pagination**: Handle large datasets with pagination
5. **Rate Limiting**: Respect Google Ads API rate limits

## 🔄 Error Handling

```python
# core/exceptions.py
class PaidSearchNavError(Exception):
    """Base exception for all custom errors."""
    pass

class APIError(PaidSearchNavError):
    """API-related errors."""
    pass

class AnalysisError(PaidSearchNavError):
    """Analysis-related errors."""
    pass

class ConfigurationError(PaidSearchNavError):
    """Configuration-related errors."""
    pass
```

## 📝 Logging

Structured logging using JSON format:

```python
import logging
from pythonjsonlogger import jsonlogger

# Configure JSON logging
logHandler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter()
logHandler.setFormatter(formatter)
logger = logging.getLogger()
logger.addHandler(logHandler)
logger.setLevel(logging.INFO)
```

## 🌐 REST API Layer (Issue #86)

The REST API layer provides HTTP endpoints for web UI and third-party integrations using FastAPI.

### API Architecture

The API layer sits between external clients and the core engine:

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Web UI/3rd    │────▶│   REST API      │────▶│   Core Engine   │
│     Party       │     │   (FastAPI)     │     │                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                               │
                               ├── Authentication (OAuth2)
                               ├── Rate Limiting
                               ├── CORS Handling
                               └── WebSocket Support
```

### Endpoint Structure

```
# Authentication
POST   /api/v1/auth/google/init      # Initiate OAuth2 flow
POST   /api/v1/auth/google/callback  # Handle OAuth2 callback
DELETE /api/v1/auth/revoke           # Revoke customer tokens

# Customers
GET    /api/v1/customers             # List authenticated customers
GET    /api/v1/customers/{id}        # Get customer details

# Audits
POST   /api/v1/audits                # Trigger new audit
GET    /api/v1/audits/{id}           # Get audit status/results
GET    /api/v1/audits                # List audits (paginated)
DELETE /api/v1/audits/{id}           # Cancel audit

# Audit Lifecycle States:
# PENDING → RUNNING → COMPLETED/FAILED/CANCELLED

# Schedules
POST   /api/v1/schedules             # Create audit schedule
GET    /api/v1/schedules             # List schedules
PUT    /api/v1/schedules/{id}        # Update schedule
DELETE /api/v1/schedules/{id}        # Delete schedule

# Results
GET    /api/v1/results/{audit_id}    # Get all results
GET    /api/v1/results/{audit_id}/{analyzer} # Get specific analyzer results

# Reports
POST   /api/v1/reports/{audit_id}/generate # Generate report
GET    /api/v1/reports/{audit_id}/download # Download report

# Dashboard
GET    /api/v1/dashboard/{audit_id}  # Get dashboard data

# Real-time
WS     /ws/v1/audits/{id}            # WebSocket for updates
GET    /api/v1/events                # Server-sent events

# System
GET    /api/v1/health                # Health check
GET    /api/v1/metrics               # Prometheus metrics

# API Versioning Strategy
# Current: /api/v1/...
# Future:  /api/v2/... (for breaking changes)
```

### API Implementation Details

#### Security & Middleware
- **Authentication**: OAuth2 flow integration with Google
- **API Keys**: Service-to-service authentication support
- **Rate Limiting**: Per-customer request limits using slowapi
  - Standard endpoints: 60 requests/minute
  - Batch operations: 10 requests/minute with burst allowance
  - Different limits configurable per endpoint category
- **CORS**: Configurable origins for web UI access
- **Request Validation**: Pydantic models for input validation

#### Real-time Features
- **WebSockets**: Live audit progress updates
- **Server-Sent Events**: Fallback for clients without WebSocket support
- **Polling Endpoints**: Traditional polling for compatibility

#### Performance Requirements
- Response time: <100ms for most endpoints
- Concurrent connections: Support for multiple audit streams
- Async/await throughout for non-blocking operations

#### Standardized Error Responses
All errors follow a consistent format:
```json
{
  "error": "ERROR_CODE",
  "message": "Human-readable error message",
  "details": {
    "field": "Additional context if applicable"
  },
  "request_id": "unique-request-identifier"
}
```

Common error codes:
- `VALIDATION_ERROR`: Invalid request data
- `AUTHENTICATION_ERROR`: Invalid or missing credentials
- `AUTHORIZATION_ERROR`: Insufficient permissions
- `RATE_LIMIT_ERROR`: Too many requests
- `NOT_FOUND`: Resource not found
- `INTERNAL_ERROR`: Server-side error

### API Configuration

Configuration is managed through environment variables:

```python
# API settings in core/config.py
api_host: str = "0.0.0.0"
api_port: int = 8000
api_key_required: bool = False
api_key: str | None = None
jwt_secret_key: str = "your-secret-key-change-in-production"
jwt_algorithm: str = "HS256"
jwt_expire_minutes: int = 60
cors_origins: list[str] = ["http://localhost:3000"]
rate_limit_per_minute: int = 60
```

### API Dependencies

The REST API requires these additional dependencies:

```toml
# In pyproject.toml
fastapi = "==0.104.1"
uvicorn = { version = "==0.24.0", extras = ["standard"] }
python-multipart = "==0.0.6"
python-jose = { version = "==3.3.0", extras = ["cryptography"] }
passlib = { version = "==1.7.4", extras = ["bcrypt"] }
slowapi = "==0.1.9"
prometheus-fastapi-instrumentator = "==6.1.0"
```

## 🚦 Future Considerations

1. **Plugin System**: Allow third-party analyzers
2. **Real-time Analysis**: WebSocket support for live monitoring (Partially implemented in API)
3. **Multi-platform**: Support for Facebook Ads, Microsoft Ads
4. **Machine Learning**: Predictive analysis and anomaly detection
5. **API Service**: REST API for integration with other tools (Issue #86 - In Development)

## 📚 References

- [Google Ads API Documentation](https://developers.google.com/google-ads/api/docs/start)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [Python Async/Await](https://docs.python.org/3/library/asyncio.html)
- [Clean Architecture](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)