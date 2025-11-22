# Quick Start Guide for Test Data

## 1. Directory Structure is Ready

Your test data directory is set up at:
```
PaidSearchNav/test_data/
```

## 2. How to Add Your Google Ads CSV Exports

1. Export your data from Google Ads Console
2. Place the CSV files in the appropriate `raw` directory:
   - Keywords → `test_data/google_ads_exports/keywords/raw/`
   - Search Terms → `test_data/google_ads_exports/search_terms/raw/`
   - Campaigns → `test_data/google_ads_exports/campaigns/raw/`
   - Geographic → `test_data/google_ads_exports/geo_performance/raw/`
   - Negative Keywords → `test_data/google_ads_exports/negative_keywords/raw/`

## 3. Process Your Data

```bash
# List available files
cd test_data
python process_test_data.py list-files

# Process all keywords files
python process_test_data.py process --type keywords

# Process all search terms files
python process_test_data.py process --type search_terms

# Process a specific file
python process_test_data.py process --type keywords --file path/to/your/file.csv
```

## 4. Test with Sample Data

We've included sample data files that you can use to test:

```bash
cd test_data
python process_test_data.py test-sample
```

This will process:
- `sample_data/sample_keywords.csv` - 10 sample keywords
- `sample_data/sample_search_terms.csv` - 15 sample search terms

## 5. View Results

- Parsed data is saved in `processed/` directories
- Analysis results will be in `analysis_results/`
- Logs are in `logs/processing.log`

## 6. Security Notes

- The `test_data` directory is gitignored
- Never commit real customer data
- Keep production data separate from test data

## 7. Next Steps

Once you have CSV files in the test data directory, you can:

1. Run individual analyzers on the data
2. Test the full analysis pipeline
3. Generate reports
4. Validate the analysis results

Example using the CLI:
```bash
# Run keyword analysis
python -m paidsearchnav.cli analyze-keywords \
  --input test_data/google_ads_exports/keywords/raw/your_keywords.csv

# Run search terms analysis  
python -m paidsearchnav.cli analyze-search-terms \
  --input test_data/google_ads_exports/search_terms/raw/your_search_terms.csv
```