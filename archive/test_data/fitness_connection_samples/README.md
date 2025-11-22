# Fitness Connection Sample Test Data

This directory contains sample data files extracted from real Fitness Connection Google Ads reports to support development and testing of new analyzers.

## Sample Files

### Demographics Data
- `age_report_sample.csv` - Age demographic performance sample (Issue #435)
- `gender_report_sample.csv` - Gender demographic performance sample (Issue #435) 
- `household_income_sample.csv` - Household income performance sample (Issue #435)

### Store Performance Data
- `per_store_sample.csv` - Store visit and local reach sample (Issue #436)

### Creative Performance Data
- `video_report_sample.csv` - Video performance sample (Issue #437)
- `ad_asset_sample.csv` - Creative asset performance sample (Issue #437)

## Usage in Tests

### Unit Tests
Use these sample files for fast unit tests:
```python
def test_demographics_analyzer():
    age_data = pd.read_csv('test_data/fitness_connection_samples/age_report_sample.csv')
    gender_data = pd.read_csv('test_data/fitness_connection_samples/gender_report_sample.csv')
    # ... test logic
```

### Integration Tests
For integration tests, use the full datasets from S3:
```python
def test_full_demographics_analysis():
    # Load full datasets from S3 for comprehensive testing
    pass
```

## Data Characteristics

### Fitness Connection Context
- Multi-location fitness chain with stores in Texas, North Carolina, etc.
- Diverse demographic targeting across age, gender, income segments
- Mix of search and video campaigns
- Local store visit tracking enabled

### Sample Data Properties
- **Age Demographics**: Covers major age groups (25-34, 35-44, 45-54, etc.)
- **Gender Targeting**: Male, Female, and Unknown segments
- **Income Brackets**: Various household income percentiles (11-20%, 41-50%, etc.)
- **Store Locations**: Multiple markets including Charlotte, Watauga
- **Video Content**: Mix of promotional content and YouTube Shorts
- **Creative Assets**: Business logos, automatically created assets

## Test Data Validation

### KPI Thresholds for Valid Test Data
- Minimum 50 impressions per demographic segment
- At least 5 interactions for meaningful analysis
- Geographic coverage across multiple markets
- Video content with varying performance levels

### Real Data Benefits
- Authentic performance patterns from fitness industry
- Realistic demographic distributions
- Actual creative performance variations
- True multi-location complexity

## Development Guidelines

### When to Use Sample vs. Full Data
- **Unit Tests**: Use sample files for speed and reliability
- **Integration Tests**: Use full S3 datasets for accuracy
- **Manual Testing**: Use sample files for quick verification
- **Performance Testing**: Use full datasets to test scalability

### Data Privacy
- Sample data contains aggregated metrics only
- No personal or sensitive information included
- All data is from legitimate business reporting

## File Formats

All sample files follow Google Ads report format:
- Line 1: Report title
- Line 2: Date range  
- Line 3: Column headers
- Line 4+: Data rows

This matches the expected input format for PaidSearchNav analyzers.