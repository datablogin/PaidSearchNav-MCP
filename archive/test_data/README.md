# Test Data Directory

This directory contains Google Ads export data for testing the PaidSearchNav analyzers with real data.

## Directory Structure

```
test_data/
├── google_ads_exports/          # Raw CSV exports from Google Ads
│   ├── keywords/               # Keyword performance reports
│   │   ├── raw/               # Original CSV files from Google Ads
│   │   └── processed/         # Parsed and validated data
│   ├── search_terms/          # Search terms reports
│   │   ├── raw/              
│   │   └── processed/        
│   ├── campaigns/             # Campaign performance data
│   │   ├── raw/              
│   │   └── processed/        
│   ├── geo_performance/       # Geographic performance reports
│   │   ├── raw/              
│   │   └── processed/        
│   └── negative_keywords/     # Negative keyword lists
│       ├── raw/              
│       └── processed/        
├── sample_data/               # Small sample files for quick testing
├── analysis_results/          # Output from analyzer runs
└── logs/                      # Logs from processing and analysis
```

## File Naming Convention

To keep files organized, use this naming pattern:
- `{report_type}_{customer_id}_{date_range}_{export_date}.csv`
- Example: `keywords_1234567890_2024Q4_20250116.csv`

## How to Use

1. **Export data from Google Ads Console:**
   - Go to Reports in Google Ads
   - Select the report type (Keywords, Search terms, etc.)
   - Choose your date range
   - Export as CSV

2. **Place files in appropriate directories:**
   ```bash
   # Example: Copy keyword report
   cp ~/Downloads/keywords_report.csv test_data/google_ads_exports/keywords/raw/
   ```

3. **Run analysis:**
   ```bash
   # Using the CLI
   python -m paidsearchnav.cli analyze-csv \
     --input test_data/google_ads_exports/keywords/raw/keywords_report.csv \
     --output test_data/analysis_results/
   ```

## Supported Report Types

### 1. Keywords Performance Report
Required columns:
- Campaign
- Ad group
- Keyword
- Match type
- Status
- Impressions
- Clicks
- Cost
- Conversions
- Quality Score

### 2. Search Terms Report
Required columns:
- Search term
- Campaign
- Ad group
- Keyword
- Match type
- Impressions
- Clicks
- Cost
- Conversions

### 3. Campaign Performance Report
Required columns:
- Campaign
- Campaign type
- Status
- Budget
- Impressions
- Clicks
- Cost
- Conversions

### 4. Geographic Report
Required columns:
- Campaign
- Country/Territory
- Region
- City
- Impressions
- Clicks
- Cost
- Conversions

### 5. Negative Keywords List
Required columns:
- Campaign
- Ad group (optional)
- Negative keyword
- Match type

## Privacy & Security

⚠️ **Important**: This directory is gitignored to protect sensitive data.
- Never commit real customer data to version control
- Use anonymized data for unit tests
- Keep production data separate from test data

## Sample Data

The `sample_data/` directory contains anonymized sample files that can be used for:
- Quick functionality testing
- Documentation examples
- Unit test development

## Analysis Results

Results from analyzer runs are saved in `analysis_results/` with timestamps:
- `{analyzer_name}_{timestamp}.json` - Raw analysis output
- `{analyzer_name}_{timestamp}_report.html` - Human-readable report