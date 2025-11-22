# PaidSearchNav CSV Parser Specification

## Overview

This document provides the complete specification for implementing a CSV parser module for PaidSearchNav, a Python-based Google Ads audit automation tool. The parser will handle Google Ads export files and convert them into Pydantic models for analysis.

## 1️⃣ Backend Folder Structure

```
paidsearchnav/
├── __init__.py
├── __main__.py                     # Main module entry point
│
├── analyzers/                      # Core analysis modules
│   ├── __init__.py
│   ├── keyword_match.py            # KeywordMatchAnalyzer
│   ├── search_terms.py             # SearchTermsAnalyzer
│   ├── negative_conflicts.py       # NegativeConflictAnalyzer
│   ├── geo_performance.py          # GeoPerformanceAnalyzer
│   ├── pmax.py                     # PerformanceMaxAnalyzer
│   └── campaign_overlap.py         # CampaignOverlapAnalyzer
│
├── api/                            # FastAPI backend
│   ├── main.py                     # FastAPI app
│   ├── run.py                      # API runner
│   └── v1/                         # API endpoints
│       ├── audits.py
│       └── reports.py
│
├── cli/                            # CLI interface
│   └── main.py                     # Click CLI
│
├── core/                           # Core business logic
│   ├── config.py
│   ├── models/                     # Data models
│   │   ├── keyword.py
│   │   ├── search_term.py
│   │   └── geo_performance.py
│   └── interfaces.py
│
└── parsers/                        # NEW: CSV parsers
    ├── __init__.py
    ├── base.py                     # Base parser interface
    ├── csv_parser.py               # Main CSV parser
    └── field_mappings.py           # CSV field mappings
```

## 2️⃣ Example Pydantic Models

### Keyword Model

```python
from enum import Enum
from pydantic import Field
from paidsearchnav.core.models.base import BasePSNModel

class KeywordMatchType(str, Enum):
    EXACT = "EXACT"
    PHRASE = "PHRASE"
    BROAD = "BROAD"

class Keyword(BasePSNModel):
    """Keyword representation."""
    
    # Identifiers
    keyword_id: str = Field(..., description="Google Ads keyword ID")
    campaign_id: str = Field(..., description="Parent campaign ID")
    campaign_name: str = Field(..., description="Parent campaign name")
    ad_group_id: str = Field(..., description="Parent ad group ID")
    ad_group_name: str = Field(..., description="Parent ad group name")
    
    # Keyword details
    text: str = Field(..., description="Keyword text")
    match_type: KeywordMatchType = Field(..., description="Match type")
    status: str = Field(..., description="Keyword status")
    
    # Quality metrics
    quality_score: int | None = Field(None, description="Quality score (1-10)")
    
    # Performance metrics
    impressions: int = Field(default=0)
    clicks: int = Field(default=0)
    cost: float = Field(default=0.0)
    conversions: float = Field(default=0.0)
    conversion_value: float = Field(default=0.0)
    
    @property
    def ctr(self) -> float:
        """Calculate Click-Through Rate."""
        return (self.clicks / self.impressions * 100) if self.impressions > 0 else 0.0
    
    @property
    def cpa(self) -> float:
        """Calculate Cost Per Acquisition."""
        return self.cost / self.conversions if self.conversions > 0 else 0.0
```

### SearchTerm Model

```python
class SearchTerm(BasePSNModel):
    """Search term representation from search terms report."""
    
    # Identifiers
    campaign_id: str = Field(..., description="Campaign ID")
    campaign_name: str = Field(..., description="Campaign name")
    ad_group_id: str = Field(..., description="Ad group ID")
    ad_group_name: str = Field(..., description="Ad group name")
    
    # Search term details
    search_term: str = Field(..., description="The actual search query")
    keyword_text: str | None = Field(None, description="Triggering keyword text")
    match_type: str | None = Field(None, description="Match type that triggered")
    
    # Performance metrics
    impressions: int = Field(default=0)
    clicks: int = Field(default=0)
    cost: float = Field(default=0.0)
    conversions: float = Field(default=0.0)
    
    # Local intent indicators
    has_near_me: bool = Field(default=False, description="Contains 'near me'")
    has_location: bool = Field(default=False, description="Contains location terms")
    
    @property
    def is_local_intent(self) -> bool:
        """Check if search term has local intent."""
        return self.has_near_me or self.has_location
```

### GeoPerformance Model

```python
class GeoPerformanceData(BasePSNModel):
    """Geographic performance metrics for a specific location."""
    
    # Identifiers
    customer_id: str = Field(..., description="Google Ads customer ID")
    campaign_id: str = Field(..., description="Campaign ID")
    campaign_name: str = Field(..., description="Campaign name")
    
    # Geographic identifiers
    location_name: str = Field(..., description="Name of the geographic location")
    location_id: str | None = Field(None, description="Google location ID")
    city: str | None = Field(None, description="City name")
    region_code: str | None = Field(None, description="State/region code")
    country_code: str | None = Field(None, description="ISO country code")
    
    # Performance metrics
    impressions: int = Field(0, description="Total impressions")
    clicks: int = Field(0, description="Total clicks")
    conversions: float = Field(0.0, description="Total conversions")
    cost: float = Field(0.0, description="Total cost")
    
    @property
    def cpa(self) -> float:
        """Cost per acquisition."""
        return self.cost / self.conversions if self.conversions > 0 else 0.0
```

## 3️⃣ Google Ads CSV Field Mappings

```python
# paidsearchnav/parsers/field_mappings.py

KEYWORD_CSV_MAPPING = {
    # CSV Column Name -> Model Field Name
    "Keyword ID": "keyword_id",
    "Campaign ID": "campaign_id",
    "Campaign": "campaign_name",
    "Ad group ID": "ad_group_id",
    "Ad group": "ad_group_name",
    "Keyword": "text",
    "Match type": "match_type",
    "Keyword state": "status",
    "Quality Score": "quality_score",
    "Impressions": "impressions",
    "Clicks": "clicks",
    "Cost": "cost",
    "Conversions": "conversions",
    "Conv. value": "conversion_value",
}

SEARCH_TERM_CSV_MAPPING = {
    # CSV Column Name -> Model Field Name
    "Campaign ID": "campaign_id",
    "Campaign": "campaign_name",
    "Ad group ID": "ad_group_id",
    "Ad group": "ad_group_name",
    "Search term": "search_term",
    "Keyword": "keyword_text",
    "Match type": "match_type",
    "Impressions": "impressions",
    "Clicks": "clicks",
    "Cost": "cost",
    "Conversions": "conversions",
}

GEO_PERFORMANCE_CSV_MAPPING = {
    # CSV Column Name -> Model Field Name
    "Customer ID": "customer_id",
    "Campaign ID": "campaign_id",
    "Campaign": "campaign_name",
    "Location": "location_name",
    "Location ID": "location_id",
    "City": "city",
    "Region": "region_code",
    "Country": "country_code",
    "Impressions": "impressions",
    "Clicks": "clicks",
    "Conversions": "conversions",
    "Cost": "cost",
}
```

## 4️⃣ CSV Parser Module Implementation

### Base Parser Interface

```python
# paidsearchnav/parsers/base.py
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TypeVar, Generic, Type
import pandas as pd

T = TypeVar('T')

class BaseCSVParser(ABC, Generic[T]):
    """Base CSV parser interface."""
    
    @abstractmethod
    def parse(self, file_path: Path) -> list[T]:
        """Parse CSV file and return list of model instances."""
        pass
    
    @abstractmethod
    def validate_headers(self, df: pd.DataFrame) -> None:
        """Validate CSV has required headers."""
        pass
```

### Main CSV Parser

```python
# paidsearchnav/parsers/csv_parser.py
import pandas as pd
from pathlib import Path
from typing import Type, TypeVar
from pydantic import BaseModel

from paidsearchnav.core.models.keyword import Keyword
from paidsearchnav.core.models.search_term import SearchTerm
from paidsearchnav.core.models.geo_performance import GeoPerformanceData
from .field_mappings import (
    KEYWORD_CSV_MAPPING,
    SEARCH_TERM_CSV_MAPPING,
    GEO_PERFORMANCE_CSV_MAPPING
)

T = TypeVar('T', bound=BaseModel)

class GoogleAdsCSVParser:
    """Universal CSV parser for Google Ads exports."""
    
    def __init__(self):
        self.mappings = {
            Keyword: KEYWORD_CSV_MAPPING,
            SearchTerm: SEARCH_TERM_CSV_MAPPING,
            GeoPerformanceData: GEO_PERFORMANCE_CSV_MAPPING,
        }
    
    def parse_csv(
        self, 
        file_path: Path, 
        model_class: Type[T],
        encoding: str = 'utf-8'
    ) -> list[T]:
        """Parse CSV file into list of model instances."""
        
        # Read CSV
        df = pd.read_csv(file_path, encoding=encoding)
        
        # Get mapping for this model
        mapping = self.mappings.get(model_class)
        if not mapping:
            raise ValueError(f"No mapping found for {model_class.__name__}")
        
        # Rename columns to match model fields
        df = df.rename(columns=mapping)
        
        # Convert to models
        records = df.to_dict('records')
        models = []
        
        for record in records:
            # Clean record (remove unmapped fields)
            clean_record = {
                k: v for k, v in record.items() 
                if k in model_class.__fields__
            }
            
            # Handle special conversions
            if model_class == SearchTerm:
                # Detect local intent
                term = model_class(**clean_record)
                term.detect_local_intent()
                models.append(term)
            else:
                models.append(model_class(**clean_record))
        
        return models
```

### CLI Integration

```python
# paidsearchnav/cli/parsers.py
import click
from pathlib import Path
from paidsearchnav.parsers.csv_parser import GoogleAdsCSVParser
from paidsearchnav.core.models.keyword import Keyword
from paidsearchnav.core.models.search_term import SearchTerm
from paidsearchnav.core.models.geo_performance import GeoPerformanceData

@click.command()
@click.option('--file', '-f', type=click.Path(exists=True), required=True)
@click.option('--type', '-t', type=click.Choice(['keyword', 'search_term', 'geo']))
def parse_csv(file: str, type: str):
    """Parse Google Ads CSV export."""
    parser = GoogleAdsCSVParser()
    
    model_map = {
        'keyword': Keyword,
        'search_term': SearchTerm,
        'geo': GeoPerformanceData
    }
    
    results = parser.parse_csv(Path(file), model_map[type])
    click.echo(f"Parsed {len(results)} records")
```

### API Integration

```python
# paidsearchnav/api/v1/uploads.py
from fastapi import APIRouter, UploadFile, File
from pathlib import Path
from paidsearchnav.parsers.csv_parser import GoogleAdsCSVParser
from paidsearchnav.core.models.keyword import Keyword

router = APIRouter()

@router.post("/upload/csv")
async def upload_csv(
    file: UploadFile = File(...),
    data_type: str = "keyword"
):
    """Upload and parse CSV file."""
    
    # Save uploaded file temporarily
    temp_path = Path(f"/tmp/{file.filename}")
    with open(temp_path, "wb") as f:
        content = await file.read()
        f.write(content)
    
    # Parse CSV
    parser = GoogleAdsCSVParser()
    models = parser.parse_csv(temp_path, Keyword)
    
    # Process models (save to DB, analyze, etc.)
    return {"parsed": len(models)}
```

## Recommendations

1. **Module Location**: Place the CSV parser module at `paidsearchnav/parsers/csv_parser.py`

2. **Integration Points**:
   - **CLI**: Add command `paidsearchnav parse-csv -f keywords.csv -t keyword`
   - **API**: Add endpoint `POST /api/v1/upload/csv`

3. **Error Handling**: Implement robust error handling for:
   - Missing required columns
   - Invalid data formats
   - Large file handling
   - Encoding issues

4. **Performance Considerations**:
   - Use pandas chunking for large files
   - Implement progress tracking for CLI
   - Add validation before parsing

5. **Testing**: Create test fixtures with sample CSV files for each data type

This modular design allows easy extension for new CSV formats and seamless integration with existing analyzers.