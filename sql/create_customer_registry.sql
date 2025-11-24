-- Customer Registry Table
-- This table maps Google Ads customer IDs to their BigQuery projects
-- Used by MCP server to dynamically route BigQuery queries to correct projects

CREATE TABLE IF NOT EXISTS `topgolf-460202.paidsearchnav_production.customer_registry` (
  customer_id STRING NOT NULL,
  project_id STRING NOT NULL,
  dataset STRING NOT NULL,
  google_ads_account_name STRING,
  status STRING DEFAULT 'active',
  onboarded_date DATE,
  notes STRING,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
)
OPTIONS(
  description="Registry of customers and their BigQuery project mappings for MCP server dynamic routing"
);

-- Insert initial customers
INSERT INTO `topgolf-460202.paidsearchnav_production.customer_registry`
  (customer_id, project_id, dataset, google_ads_account_name, status, onboarded_date, notes)
VALUES
  ('5777461198', 'topgolf-460202', 'paidsearchnav_production', 'Topgolf', 'active', '2024-01-15', 'Original account'),
  ('9097587272', 'puttery-golf-001', 'paidsearchnav_production', 'Puttery', 'active', '2024-06-20', 'Topgolf subsidiary');

-- Query to verify
SELECT * FROM `topgolf-460202.paidsearchnav_production.customer_registry`;
