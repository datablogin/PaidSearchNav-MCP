# Storage Module

This module provides persistent storage for analysis results using SQLAlchemy with support for both SQLite (development) and PostgreSQL (production).

## Features

- Async SQLAlchemy implementation
- Automatic database selection based on environment
- Full CRUD operations for analysis results
- Analysis comparison functionality
- Database migrations with Alembic
- Support for querying by customer, type, and date range

## Usage

### Basic Usage

```python
from paidsearchnav.core.config import Settings
from paidsearchnav.storage.repository import AnalysisRepository
from paidsearchnav.core.models.analysis import AnalysisResult

# Initialize repository
settings = Settings()
repo = AnalysisRepository(settings)

# Save an analysis
analysis = AnalysisResult(
    customer_id="1234567890",
    analysis_type="keyword_match_audit",
    analyzer_name="KeywordMatchAnalyzer",
    start_date=start_date,
    end_date=end_date,
    metrics=metrics,
    recommendations=recommendations
)
analysis_id = await repo.save_analysis(analysis)

# Retrieve analysis
result = await repo.get_analysis(analysis_id)

# List analyses with filters
results = await repo.list_analyses(
    customer_id="1234567890",
    analysis_type="keyword_match_audit",
    limit=10
)

# Compare two analyses
comparison = await repo.compare_analyses(analysis_id_1, analysis_id_2)

# Delete analysis
deleted = await repo.delete_analysis(analysis_id)
```

### Database Configuration

#### Development (SQLite)
By default, the storage uses SQLite in development:
- Database location: `{data_dir}/paidsearchnav.db`
- No additional configuration needed

#### Production (PostgreSQL)
Set the following environment variables:
```bash
PSN_ENVIRONMENT=production
PSN_DATABASE_URL=postgresql://user:password@host:port/database
# Or individual components:
PSN_DB_HOST=localhost
PSN_DB_PORT=5432
PSN_DB_USER=paidsearchnav
PSN_DB_PASSWORD=secret
PSN_DB_NAME=paidsearchnav
```

### Database Migrations

Initialize Alembic (first time only):
```bash
alembic init paidsearchnav/storage/migrations
```

Create a new migration:
```bash
alembic revision --autogenerate -m "Description of changes"
```

Apply migrations:
```bash
alembic upgrade head
```

Rollback migrations:
```bash
alembic downgrade -1
```

## Data Models

### AnalysisRecord
Stores the main analysis results with:
- Customer ID
- Analysis type and analyzer name
- Time range (start_date, end_date)
- Status
- Summary metrics for quick queries
- Full JSON result data
- Timestamps

### ComparisonRecord
Stores comparisons between analyses:
- IDs of analyses being compared
- Comparison type
- Summary of changes
- Full comparison data

## Indexes

The following indexes are created for performance:
- `customer_id, created_at` - For listing customer analyses
- `analysis_type, created_at` - For listing by type
- `customer_id, analysis_type` - For filtered queries

## Error Handling

The repository handles:
- Database connection errors
- Invalid data validation
- Transaction rollbacks on failure
- Proper async context management

## Testing

Run the storage tests:
```bash
pytest tests/unit/storage/test_repository.py -v
```

The tests use a temporary SQLite database that's cleaned up after each test run.