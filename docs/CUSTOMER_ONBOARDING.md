# Customer Onboarding Guide

This document outlines the process for onboarding new customers to the PaidSearchNav MCP server.

## Overview

The MCP server uses a **Customer Registry** to dynamically route BigQuery queries to the correct GCP project based on customer ID. When onboarding a new customer, you must register their Google Ads customer ID and BigQuery project mapping.

## Prerequisites

1. Customer has a Google Ads account
2. Customer's Google Ads data is exported to BigQuery
3. Service account has access to the customer's BigQuery project

## Onboarding Steps

### Step 1: Verify Google Ads Access

Ensure the MCP server has API access to the customer's Google Ads account:

```bash
# Test Google Ads API access
# Should return campaigns without error
customer_id="1234567890"  # Replace with actual customer ID
```

Use the MCP tool `get_campaigns` to verify access.

### Step 2: Verify BigQuery Project Access

Confirm the service account has access to the customer's BigQuery project:

```sql
-- List datasets in customer's project
SELECT * FROM `<project-id>.INFORMATION_SCHEMA.SCHEMATA`;

-- Example: puttery-golf-001
SELECT * FROM `puttery-golf-001.INFORMATION_SCHEMA.SCHEMATA`;
```

### Step 3: Register Customer in Registry

Add the customer to the customer registry table:

```sql
INSERT INTO `topgolf-460202.paidsearchnav_production.customer_registry`
  (customer_id, project_id, dataset, google_ads_account_name, status, onboarded_date, notes)
VALUES
  (
    '1234567890',                    -- Google Ads customer ID (10 digits)
    'customer-project-id',           -- GCP project containing BigQuery data
    'paidsearchnav_production',      -- Dataset name
    'Customer Account Name',         -- Friendly name
    'active',                        -- Status: active, inactive, suspended
    CURRENT_DATE(),                  -- Today's date
    'Optional notes about account'   -- Any additional context
  );
```

**Example - Onboarding Puttery**:
```sql
INSERT INTO `topgolf-460202.paidsearchnav_production.customer_registry`
  (customer_id, project_id, dataset, google_ads_account_name, status, onboarded_date, notes)
VALUES
  (
    '9097587272',
    'puttery-golf-001',
    'paidsearchnav_production',
    'Puttery',
    'active',
    '2024-11-24',
    'Topgolf subsidiary - mini golf experiences'
  );
```

### Step 4: Grant Service Account Access (if needed)

If the service account doesn't have access to the customer's BigQuery project, grant it:

```bash
# Get service account email from credentials
SERVICE_ACCOUNT=$(jq -r .client_email < $GOOGLE_APPLICATION_CREDENTIALS)

# Grant BigQuery Data Viewer role
gcloud projects add-iam-policy-binding <customer-project-id> \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/bigquery.dataViewer"

# Grant BigQuery Job User role (to run queries)
gcloud projects add-iam-policy-binding <customer-project-id> \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/bigquery.jobUser"
```

### Step 5: Test MCP Access

Verify the MCP server can access the customer's BigQuery data:

```
# In Claude Desktop with MCP connected:
Can you run this query to test access to customer 1234567890's BigQuery data:

SELECT COUNT(*) as row_count
FROM `<project-id>.paidsearchnav_production.ads_SearchQueryStats_<customer_id>`
LIMIT 1
```

The query should execute successfully (not "access denied").

### Step 6: Clear Registry Cache

After adding a new customer, clear the MCP server's cache:

```python
# In Python console or restart MCP server
from paidsearchnav_mcp.clients.bigquery.customer_registry import CustomerRegistry

registry = CustomerRegistry()
registry.clear_cache()
```

Or simply **restart the MCP server** (recommended):
```bash
# In Claude Desktop: Cmd+Q, then relaunch
```

## Verification Checklist

After onboarding, verify:

- [ ] Customer appears in registry: `SELECT * FROM customer_registry WHERE customer_id = 'XXXXX'`
- [ ] Google Ads API access works: `get_campaigns` returns data
- [ ] BigQuery access works: `query_bigquery` can read customer's tables
- [ ] MCP server routes queries to correct project (check logs)

## Offboarding

To deactivate a customer (without deleting history):

```sql
UPDATE `topgolf-460202.paidsearchnav_production.customer_registry`
SET status = 'inactive', updated_at = CURRENT_TIMESTAMP()
WHERE customer_id = '1234567890';
```

## Troubleshooting

### Issue: "Access Denied" when querying BigQuery

**Cause**: Service account lacks permissions on customer's project.

**Solution**: Grant BigQuery Data Viewer + Job User roles (Step 4).

---

### Issue: "Customer not found in registry"

**Cause**: Customer not added to registry table, or status is 'inactive'.

**Solution**: Run INSERT query (Step 3) or update status to 'active'.

---

### Issue: MCP server still uses old project after registry update

**Cause**: Cache not cleared.

**Solution**: Restart MCP server or call `registry.clear_cache()`.

---

### Issue: BigQuery tables don't exist for customer

**Cause**: Google Ads → BigQuery export not configured for customer.

**Solution**: Set up BigQuery export in Google Ads account:
1. Go to Google Ads → Tools & Settings → Linked accounts
2. Link BigQuery project
3. Enable data export
4. Wait 24-48 hours for initial data sync

## Registry Table Schema

```sql
CREATE TABLE `topgolf-460202.paidsearchnav_production.customer_registry` (
  customer_id STRING NOT NULL,           -- Google Ads customer ID
  project_id STRING NOT NULL,            -- GCP project for BigQuery
  dataset STRING NOT NULL,               -- BigQuery dataset name
  google_ads_account_name STRING,        -- Friendly account name
  status STRING DEFAULT 'active',        -- active, inactive, suspended
  onboarded_date DATE,                   -- Date customer was added
  notes STRING,                          -- Additional context
  created_at TIMESTAMP,                  -- Auto-generated
  updated_at TIMESTAMP                   -- Auto-updated
);
```

## Future Enhancements

Potential improvements to the onboarding process:

1. **Automated onboarding script**: CLI tool to run all steps
2. **Self-service portal**: Web UI for account managers to onboard customers
3. **Health monitoring**: Periodic checks for BigQuery export freshness
4. **Multi-region support**: Handle customers in different GCP regions
5. **Cost tracking**: Monitor BigQuery query costs per customer

## Support

For questions about customer onboarding, contact:
- Technical issues: [Your support channel]
- Access requests: [IAM admin contact]
