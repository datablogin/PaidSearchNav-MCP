# CSV Upload and Analysis API Endpoints

This document describes the API endpoints for uploading and analyzing Google Ads CSV exports.

## Base URL
All endpoints are prefixed with: `/api/v1`

## Authentication
All endpoints require authentication via Bearer token in the Authorization header:
```
Authorization: Bearer <token>
```

## Endpoints

### 1. Upload CSV File
**POST** `/upload/csv`

Upload a Google Ads CSV export file for parsing and validation.

#### Request
- **Content-Type**: `multipart/form-data`
- **Body**:
  - `file`: CSV file (required)
  - `data_type`: Type of CSV data (required)

#### Query Parameters
- `data_type` (required): One of:
  - `search_terms` - Search terms report
  - `keywords` - Keywords report  
  - `geo_performance` - Geographic performance report
  - `campaigns` - Campaign performance report
  - `ad_groups` - Ad group performance report
  - `negative_keywords` - Negative keywords report
  - `device` - Device performance report
  - `ad_schedule` - Ad schedule (dayparting) report
  - `per_store` - Store-level performance report
  - `auction_insights` - Auction insights report

#### Response
```json
{
  "count": 1234,
  "data_type": "keywords",
  "filename": "keywords_export.csv",
  "message": "Successfully parsed 1234 keywords records"
}
```

#### Error Responses
- `400 Bad Request`: Invalid file format or missing required fields
- `500 Internal Server Error`: Processing error

### 2. Analyze Single CSV
**POST** `/csv/analyze`

Upload and analyze a CSV file in one operation.

#### Request
- **Content-Type**: `multipart/form-data`
- **Body**:
  - `file`: CSV file (required)

#### Query Parameters
- `data_type` (required): One of `search_terms`, `keywords`, `geo_performance`, `negative_keywords`
- `customer_id` (required): Google Ads customer ID
- `start_date` (required): Analysis start date (YYYY-MM-DD)
- `end_date` (required): Analysis end date (YYYY-MM-DD)

#### Response
```json
{
  "analysis_type": "keyword_analysis",
  "total_records": 1234,
  "metrics": {
    "total_keywords_analyzed": 1234,
    "issues_found": 45,
    "critical_issues": 12,
    "potential_cost_savings": 2500.50,
    "potential_conversion_increase": 150.0
  },
  "recommendations": [
    {
      "type": "PAUSE_KEYWORD",
      "priority": "HIGH", 
      "title": "Pause low-performing keywords",
      "description": "15 keywords have 0 conversions despite high spend",
      "estimated_impact": {
        "cost_savings": 500.0
      }
    }
  ],
  "insights": {
    "total_keywords": 1234,
    "avg_quality_score": 7.2,
    "median_cpc": 2.50,
    "median_cpa": 25.00,
    "optimization_opportunities": 45
  }
}
```

### 3. Analyze Multiple CSV Files
**POST** `/csv/analyze-multiple`

Analyze multiple CSV files together for cross-report insights (e.g., negative keyword conflicts).

#### Request
- **Content-Type**: `multipart/form-data`
- **Body** (all optional, but at least one required):
  - `keyword_file`: Keywords report CSV
  - `search_term_file`: Search terms report CSV
  - `negative_keyword_file`: Negative keywords report CSV

#### Query Parameters
- `customer_id` (required): Google Ads customer ID
- `start_date` (required): Analysis start date (YYYY-MM-DD)
- `end_date` (required): Analysis end date (YYYY-MM-DD)

#### Response
```json
{
  "summary": {
    "keywords": 1234,
    "search_terms": 5678,
    "negative_keywords": 890
  },
  "negative_conflict_analysis": {
    "total_conflicts": 23,
    "conflicts": [
      {
        "negative_keyword": "cheap",
        "conflicting_keyword": "cheap shoes",
        "match_type": "BROAD",
        "campaign": "Summer Sale",
        "estimated_lost_conversions": 15
      }
    ],
    "recommendations": [
      {
        "type": "REFINE_NEGATIVE",
        "priority": "HIGH",
        "title": "Refine overly broad negative keywords",
        "description": "Change 'cheap' from broad to phrase match to avoid blocking converting keywords"
      }
    ]
  }
}
```

## Example Usage

### JavaScript/TypeScript Example

```typescript
// Upload and analyze keywords
async function analyzeKeywords(file: File) {
  const formData = new FormData();
  formData.append('file', file);
  
  const params = new URLSearchParams({
    data_type: 'keywords',
    customer_id: '123-456-7890',
    start_date: '2024-01-01',
    end_date: '2024-03-31'
  });
  
  const response = await fetch(`/api/v1/csv/analyze?${params}`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`
    },
    body: formData
  });
  
  if (!response.ok) {
    throw new Error(`Upload failed: ${response.statusText}`);
  }
  
  return response.json();
}

// Analyze multiple files for conflicts
async function analyzeConflicts(keywordFile: File, negativeFile: File) {
  const formData = new FormData();
  formData.append('keyword_file', keywordFile);
  formData.append('negative_keyword_file', negativeFile);
  
  const params = new URLSearchParams({
    customer_id: '123-456-7890',
    start_date: '2024-01-01', 
    end_date: '2024-03-31'
  });
  
  const response = await fetch(`/api/v1/csv/analyze-multiple?${params}`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`
    },
    body: formData
  });
  
  return response.json();
}
```

## File Format Requirements

### General Requirements
- Files must be valid CSV format
- Maximum file size: 10MB
- Encoding: UTF-8 (preferred) or UTF-16
- Must include header row with column names

### Report-Specific Requirements

#### Keywords Report
Required columns:
- Keyword ID
- Campaign ID
- Campaign
- Ad group ID
- Ad group
- Keyword
- Match type
- Status

#### Search Terms Report  
Required columns:
- Campaign ID
- Campaign
- Ad group ID
- Ad group
- Search term

#### Geographic Performance Report
Required columns:
- Customer ID
- Campaign ID
- Campaign
- Location type
- Location

#### Negative Keywords Report
Required columns:
- Negative keyword
- Match type
- Level (Campaign or Ad group)

## Error Handling

All endpoints return consistent error responses:

```json
{
  "detail": "Error message describing what went wrong"
}
```

Common error scenarios:
- `400`: Invalid file format, missing required columns, or invalid data
- `401`: Authentication required
- `403`: Insufficient permissions
- `413`: File too large (>10MB)
- `429`: Rate limit exceeded
- `500`: Internal server error

## Rate Limits
- Upload endpoints: 10 requests per minute per user
- Analysis endpoints: 5 requests per minute per user