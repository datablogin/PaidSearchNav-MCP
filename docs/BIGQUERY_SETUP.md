# BigQuery Setup Guide

This guide walks you through setting up BigQuery access for PaidSearchNav, enabling you to analyze historical Google Ads data beyond the API's 90-day limit.

## Overview

BigQuery integration provides:
- **Historical Data Access**: Query Google Ads data beyond the 90-day API limitation
- **Advanced Analytics**: Perform complex aggregations and trend analysis
- **Cost Efficiency**: Reduce API calls by querying historical data from BigQuery
- **Data Warehouse**: Centralized storage for long-term performance tracking

## Prerequisites

- Google Cloud Platform (GCP) account
- Access to the GCP project where your Google Ads data will be stored
- Google Ads account with admin access (for linking to BigQuery)

## Step 1: Create a GCP Service Account

1. **Navigate to the GCP Console**
   - Go to [console.cloud.google.com](https://console.cloud.google.com)
   - Select your project (or create a new one)

2. **Create Service Account**
   ```
   Navigation: IAM & Admin > Service Accounts > Create Service Account
   ```

   - **Service account name**: `paidsearchnav-bigquery`
   - **Service account ID**: `paidsearchnav-bigquery` (auto-generated)
   - **Description**: "Service account for PaidSearchNav BigQuery access"
   - Click **Create and Continue**

3. **Grant BigQuery Permissions**

   Add the following roles:
   - **BigQuery Data Viewer**: Read access to BigQuery datasets and tables
   - **BigQuery Job User**: Permission to run BigQuery queries

   Click **Continue**, then **Done**

4. **Create Service Account Key**
   - Click on the newly created service account
   - Go to the **Keys** tab
   - Click **Add Key** > **Create new key**
   - Select **JSON** format
   - Click **Create**
   - The JSON key file will download automatically

5. **Secure the Key File**
   ```bash
   # Create a secure directory for credentials
   mkdir -p ~/.config/gcp
   chmod 700 ~/.config/gcp

   # Move the downloaded key file
   mv ~/Downloads/paidsearchnav-bigquery-*.json ~/.config/gcp/service-account.json
   chmod 600 ~/.config/gcp/service-account.json
   ```

## Step 2: Configure Environment Variables

Add the following to your shell configuration file (`.bashrc`, `.zshrc`, or `.bash_profile`):

```bash
# BigQuery Configuration
export GOOGLE_APPLICATION_CREDENTIALS="$HOME/.config/gcp/service-account.json"
export GCP_PROJECT_ID="your-gcp-project-id"
```

Replace `your-gcp-project-id` with your actual GCP project ID.

**Apply the changes:**
```bash
source ~/.bashrc  # or ~/.zshrc
```

**Verify the environment variables:**
```bash
echo $GOOGLE_APPLICATION_CREDENTIALS
echo $GCP_PROJECT_ID
```

## Step 3: Link Google Ads to BigQuery (Recommended)

Linking your Google Ads account to BigQuery enables automatic daily data exports.

1. **Access Google Ads**
   - Sign in to [ads.google.com](https://ads.google.com)
   - Select your Google Ads account

2. **Navigate to BigQuery Export**
   ```
   Tools & Settings > Setup > Linked accounts > BigQuery
   ```

3. **Set Up Data Transfer**
   - Click **Details** under BigQuery
   - Click **Link** or **Set up data transfer**
   - Select your GCP project
   - Choose a dataset name (e.g., `google_ads_data`)
   - Configure export settings:
     - **Data location**: Choose your preferred region (e.g., US, EU)
     - **Resource level**: Choose account level or MCC level
     - **Export tables**: Select all relevant tables (recommended)

4. **Grant Permissions**
   - Google Ads will request permission to write to your BigQuery project
   - Click **Accept** to grant permissions

5. **Verify Export Settings**
   - Historical data backfill: Google typically loads 13 months of historical data
   - Daily exports: New data is exported daily at approximately 12:00 PM Pacific Time
   - Export delay: Data from day N is typically available on day N+1

## Step 4: Verify BigQuery Dataset

After linking (allow 24-48 hours for initial data export):

1. **Navigate to BigQuery Console**
   - Go to [console.cloud.google.com/bigquery](https://console.cloud.google.com/bigquery)
   - Select your project

2. **Check for Google Ads Dataset**
   - Look for a dataset named `google_ads_data` (or your chosen name)
   - Expand the dataset to see available tables
   - Common tables include:
     - `SearchTermStats_*` - Search term performance (sharded by date)
     - `CampaignStats_*` - Campaign performance
     - `AdGroupStats_*` - Ad group performance
     - `KeywordStats_*` - Keyword performance
     - `GeoStats_*` - Geographic performance

## Step 5: Test the Connection

### Option A: Using the BigQuery Console

1. Go to [console.cloud.google.com/bigquery](https://console.cloud.google.com/bigquery)
2. Click **Compose New Query**
3. Run a simple test query:

```sql
-- List all available Google Ads tables
SELECT
  table_name,
  ROUND(size_bytes / (1024 * 1024), 2) as size_mb,
  row_count
FROM `your-project-id.google_ads_data.__TABLES__`
ORDER BY table_name
```

### Option B: Using Python (Recommended for PaidSearchNav)

Create a test script `test_bigquery_connection.py`:

```python
from google.cloud import bigquery
import os

def test_bigquery_connection():
    """Test BigQuery connection and list available tables."""

    # Verify environment variables
    credentials_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    project_id = os.getenv('GCP_PROJECT_ID')

    if not credentials_path:
        print("ERROR: GOOGLE_APPLICATION_CREDENTIALS not set")
        return False

    if not project_id:
        print("ERROR: GCP_PROJECT_ID not set")
        return False

    print(f"Credentials: {credentials_path}")
    print(f"Project ID: {project_id}")

    try:
        # Initialize BigQuery client
        client = bigquery.Client(project=project_id)

        # List datasets
        datasets = list(client.list_datasets())
        print(f"\nAvailable datasets: {len(datasets)}")
        for dataset in datasets:
            print(f"  - {dataset.dataset_id}")

        # Try to query a Google Ads table (adjust dataset name as needed)
        query = """
        SELECT table_name, row_count
        FROM `google_ads_data.__TABLES__`
        ORDER BY table_name
        LIMIT 10
        """

        print("\nRunning test query...")
        query_job = client.query(query)
        results = query_job.result()

        print("\nGoogle Ads tables found:")
        for row in results:
            print(f"  - {row.table_name}: {row.row_count:,} rows")

        print("\nBigQuery connection successful!")
        return True

    except Exception as e:
        print(f"\nERROR: {str(e)}")
        return False

if __name__ == "__main__":
    test_bigquery_connection()
```

**Run the test:**
```bash
python test_bigquery_connection.py
```

## Step 6: Install Required Python Libraries

If not already installed, add BigQuery support to your environment:

```bash
# Using uv (faster)
uv pip install google-cloud-bigquery

# Or using pip
pip install google-cloud-bigquery
```

## Troubleshooting

### Authentication Errors

**Error**: `Could not automatically determine credentials`

**Solution**:
- Verify `GOOGLE_APPLICATION_CREDENTIALS` environment variable is set
- Ensure the JSON key file exists at the specified path
- Check file permissions (should be readable)

### Permission Denied Errors

**Error**: `Permission denied on dataset/table`

**Solution**:
- Verify service account has the required roles:
  - BigQuery Data Viewer
  - BigQuery Job User
- Check that the service account is in the correct GCP project
- Wait a few minutes for IAM changes to propagate

### No Data Found

**Issue**: Tables exist but have no data

**Solution**:
- Check Google Ads to BigQuery export status
- Verify export has completed (can take 24-48 hours for initial backfill)
- Check for any error messages in Google Ads export settings
- Ensure your Google Ads account has historical data

### Dataset Not Found

**Error**: `Dataset google_ads_data not found`

**Solution**:
- Verify the dataset name in your BigQuery export settings
- Check that data export has been successfully configured
- Wait for the initial export to complete (up to 48 hours)
- Use the correct project ID in your queries

## Data Retention and Costs

### BigQuery Storage Costs
- **First 10 GB per month**: Free
- **Beyond 10 GB**: $0.02 per GB per month (as of 2025)
- **Long-term storage** (90+ days): $0.01 per GB per month

### BigQuery Query Costs
- **First 1 TB per month**: Free
- **Beyond 1 TB**: $5 per TB processed

### Cost Optimization Tips
1. **Use Partitioned Tables**: Query specific date ranges to reduce data scanned
2. **Select Specific Columns**: Avoid `SELECT *` queries
3. **Use Table Preview**: Free preview of table data (first 10 rows)
4. **Set Query Limits**: Use `LIMIT` clauses to control result size
5. **Monitor Query Costs**: Check query validator for estimated bytes processed

## Security Best Practices

1. **Never Commit Credentials**
   - Add `*.json` to `.gitignore`
   - Store credentials outside the repository
   - Use environment variables for configuration

2. **Restrict Service Account Access**
   - Grant minimum required permissions
   - Use separate service accounts for different environments
   - Regularly audit service account usage

3. **Rotate Keys Regularly**
   - Create new keys every 90 days
   - Delete old keys after rotation
   - Monitor service account activity

4. **Use Secret Management**
   - Consider using Google Secret Manager for production
   - Use environment-specific credentials
   - Implement credential validation at runtime

## Next Steps

- Review [BIGQUERY_EXAMPLES.md](BIGQUERY_EXAMPLES.md) for practical query examples
- Integrate BigQuery queries into PaidSearchNav workflows
- Set up monitoring and alerting for data exports
- Configure automated reports using BigQuery Scheduled Queries

## Additional Resources

- [BigQuery Documentation](https://cloud.google.com/bigquery/docs)
- [Google Ads Data Transfer](https://support.google.com/google-ads/answer/10125311)
- [BigQuery Pricing](https://cloud.google.com/bigquery/pricing)
- [BigQuery Best Practices](https://cloud.google.com/bigquery/docs/best-practices)
