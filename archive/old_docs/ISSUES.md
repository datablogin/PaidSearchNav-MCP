### GitHub Issues for Quarterly Google Ads Keyword Audit (Retail Focus)

Each issue below is formatted using a GitHub-compatible issue template and represents a concrete task a developer or analyst could own to support or implement the audit process. These assume access to Google Ads API, scripts, or reporting tools.

---

#### Issue: Implement Keyword Match Type Audit Script
**Description:**
Create a script to audit all keywords in the account, grouped by match type (Broad, Phrase, Exact), and report conversion and cost performance by match type.

**Acceptance Criteria:**
- Exports keyword data with match types and performance metrics
- Aggregates data to compare CPA and ROAS across match types
- Highlights high-cost, low-ROI Broad match keywords

**Labels:** `audit`, `scripts`, `keywords`

---

#### Issue: Automate Search Terms Report Analysis
**Description:**
Build a script that reviews the search terms report from the past 90 days and identifies:
- High-cost queries with no conversions
- Converting queries that aren’t in the keyword list
- Irrelevant or brand-damaging queries

**Acceptance Criteria:**
- Outputs spreadsheet or Looker Studio-compatible CSV
- Classifies terms as "Add Candidate", "Negative Candidate", or "Already Covered"
- Runs via schedule or on-demand

**Labels:** `audit`, `scripts`, `search-terms`

---

#### Issue: Detect and Resolve Negative Keyword Conflicts
**Description:**
Write a tool or use an existing script to detect negative keywords that block active keywords.

**Acceptance Criteria:**
- Compares all negative keywords against positive keywords (by match type and scope)
- Flags any overlapping conflicts with details (campaign, ad group, match type)
- Outputs resolution suggestions (e.g., remove negative, narrow match)

**Labels:** `keywords`, `negatives`, `conflict-detection`

---

#### Issue: Geo Performance Dashboard
**Description:**
Create a dashboard (Looker Studio or Python + GSheets) that shows:
- CPA and ROAS by geographic region
- Distance report if location extensions are enabled
- Store-specific performance metrics (if multiple locations)

**Acceptance Criteria:**
- Map-based visualization by region
- Flags high/low performing locations
- Data sourced from Google Ads API

**Labels:** `reporting`, `geo`, `local-intent`

---

#### Issue: Add Local Intent Keywords
**Description:**
Review existing keyword and search term lists to identify local-intent variants (e.g., "near me", city names, zip codes) and add them explicitly to keyword sets.

**Acceptance Criteria:**
- Adds new keywords to ad groups that lack localized intent
- Tests both Phrase and Exact match variants
- Validates ad copy coverage for these terms

**Labels:** `keywords`, `local`, `intent`

---

#### Issue: Performance Max Search Term Analyzer
**Description:**
Use the new PMax search terms report to identify:
- High-performing search queries worth porting to Search campaigns
- Irrelevant queries for account-level negative list
- Potential overlaps with Search campaigns

**Acceptance Criteria:**
- Pulls PMax queries and identifies overlaps with Search keywords
- Annotates intent and conversion metrics
- Suggests changes to account-level negative list or keyword additions

**Labels:** `performance-max`, `search-terms`, `optimization`

---

#### Issue: Shared Negative List Validator
**Description:**
Ensure that all campaigns (especially Performance Max and Local Search) are consistently using a shared negative keyword list.

**Acceptance Criteria:**
- Reports campaigns missing the shared list
- Optionally auto-applies the shared list to missing campaigns
- Warns if list contents conflict with campaign goals

**Labels:** `negatives`, `shared-settings`, `automation`

---

#### Issue: Audit Report Generator Template
**Description:**
Create a reusable report template (in Looker Studio or Slides/PDF) that summarizes audit results:
- Match type breakdown
- Negative keyword conflicts
- Geo performance
- Search term opportunities

**Acceptance Criteria:**
- Accepts data from prior audit scripts
- Can be auto-filled with updated inputs
- Supports white-label branding for clients

**Labels:** `reporting`, `template`, `client-ready`

---

### System & Infrastructure Issues (for Full Audit App Deployment)

#### Issue: Google Ads API Integration Layer
**Description:**
Develop a robust integration layer using Google Ads API to pull campaign, keyword, search term, geo, and asset data.

**Acceptance Criteria:**
- Handles token authentication, pagination, and rate limits
- Retrieves data for search and PMax campaigns
- Provides endpoints for downstream scripts or dashboards

**Labels:** `api`, `integration`, `ads`

---

#### Issue: OAuth2 Token Manager
**Description:**
Implement secure OAuth2 flow and persistent token storage for user and MCC access.

**Acceptance Criteria:**
- Supports refresh token handling
- Stores tokens encrypted using vault or secrets manager
- Handles user/client revocation gracefully

**Labels:** `auth`, `oauth`, `security`

---

#### Issue: Account Mapper for MCC Structure
**Description:**
Support multi-account auditing by linking MCCs with child accounts and metadata.

**Acceptance Criteria:**
- Lists accessible Google Ads accounts for each MCC login
- Stores customer_id and account name
- Supports per-account opt-in/opt-out

**Labels:** `accounts`, `multi-tenant`, `integration`

---

#### Issue: Secure Environment Variable Management
**Description:**
Set up .env and/or secrets store for audit app configuration.

**Acceptance Criteria:**
- Uses .env, AWS/GCP Secret Manager, or Vault for sensitive credentials
- Provides fallback config for local/dev environments
- Logs missing/invalid config on boot

**Labels:** `config`, `env`, `security`

---

#### Issue: Audit Scheduler
**Description:**
Develop a scheduling layer (e.g. CRON, Celery, Cloud Scheduler) to trigger audits quarterly and on-demand.

**Acceptance Criteria:**
- Executes scripts per account on defined schedule
- Logs and retries failed jobs
- Supports manual run trigger via API or dashboard

**Labels:** `scheduler`, `automation`, `jobs`

---

#### Issue: Data Storage & History Tracker
**Description:**
Design a schema and database layer to persist audit data, diffs, and metadata.

**Acceptance Criteria:**
- Normalizes keywords, queries, negatives, conflicts into tables
- Tracks change history between audits
- Supports BigQuery, PostgreSQL, or Firestore

**Labels:** `database`, `history`, `audit`

---

#### Issue: Logging and Monitoring Setup
**Description:**
Implement logging for errors, job failures, and alerts using centralized logging.

**Acceptance Criteria:**
- Logs output from all audit jobs and scripts
- Sends error alerts to Slack/email
- Optionally integrates with Sentry or Stackdriver

**Labels:** `logging`, `monitoring`, `observability`

---

Let me know if you’d like deployment scaffolding, Docker Compose, or CI scripts added as well.
