# PaidSearchNav Skill Catalog

## Overview
This catalog lists all available Claude Skills for Google Ads optimization, organized by tier and category.

## Tier 1: Cost Efficiency Suite ✅

These 5 skills form the core of quarterly keyword audits and provide the highest ROI.

### 1. KeywordMatchAnalyzer
**Status**: ✅ Available
**Version**: 1.0.0
**Purpose**: Identifies exact match keyword opportunities
**Typical Impact**: $1,500-5,000/month savings
**Use Case**: Every quarterly audit
**Category**: Cost Efficiency
**Required MCP Tools**: `get_keywords`, `get_search_terms`

**Key Features**:
- Match type conversion analysis (Broad/Phrase → Exact)
- Performance threshold validation
- Search term concentration analysis
- Cost efficiency improvements

**When to Use**: Quarterly audits, when CPC is high, after campaign restructuring

---

### 2. SearchTermAnalyzer
**Status**: ✅ Available
**Version**: 1.0.0
**Purpose**: Identifies negative keyword opportunities to eliminate wasted spend
**Typical Impact**: $2,000-7,000/month savings
**Use Case**: Every quarterly audit
**Category**: Cost Efficiency
**Required MCP Tools**: `get_search_terms`, `get_negative_keywords`

**Key Features**:
- Zero conversion waste identification
- Intent classification (Transactional, Informational, Navigational, Local)
- Multi-level negative recommendations (Account, Campaign, Ad Group)
- Irrelevant pattern detection

**When to Use**: Quarterly audits, when wasted spend is high, before budget increases

---

### 3. NegativeConflictAnalyzer
**Status**: ✅ Available
**Version**: 1.0.0
**Purpose**: Finds negative keywords blocking positive keywords
**Typical Impact**: 5-10% impression share recovery
**Use Case**: Campaign health checks, quarterly audits
**Category**: Campaign Health
**Required MCP Tools**: `get_keywords`, `get_negative_keywords`

**Key Features**:
- Multi-level conflict detection (Shared, Campaign, Ad Group)
- Match type conflict analysis
- Severity assessment (Critical, High, Medium, Low)
- Resolution recommendations (Remove, Change match type, Refine)

**When to Use**: When impression share is low, after adding many negatives, quarterly audits

---

### 4. GeoPerformanceAnalyzer
**Status**: ✅ Available
**Version**: 1.0.0
**Purpose**: Optimizes geographic targeting and location bid adjustments
**Typical Impact**: 15-25% ROAS improvement
**Use Case**: Retail businesses with physical locations
**Category**: Geographic Optimization
**Required MCP Tools**: `get_geo_performance`

**Key Features**:
- Location performance analysis by DMA/city
- Store proximity correlation
- Bid adjustment recommendations (+/-20% to +/-50%)
- Location exclusion suggestions
- "Near me" search optimization

**When to Use**: For retail/local businesses, quarterly audits, before opening new locations

---

### 5. PMaxAnalyzer
**Status**: ✅ Available
**Version**: 1.0.0
**Purpose**: Prevents Performance Max from cannibalizing Search campaigns
**Typical Impact**: 10-20% CPA improvement
**Use Case**: Accounts running both PMax and Search campaigns
**Category**: Campaign Overlap
**Required MCP Tools**: `get_search_terms`, `get_campaigns`

**Key Features**:
- Search term overlap detection
- Performance comparison (PMax vs Search)
- Cannibalization impact calculation
- PMax negative keyword recommendations
- Strategic guidance on campaign balance

**When to Use**: Monthly for PMax accounts, when CPA increases, quarterly audits

---

## How to Use Skills

### Prerequisites
1. **Claude Desktop** or Claude API access
2. **PaidSearchNav MCP Server** connected and configured
3. **Google Ads Account** access via MCP server
4. **Minimum Data**: 90 days of campaign performance data

### Loading Skills

**Option 1: Upload Packaged Skills** (Recommended)
1. Download .zip files from `dist/` directory
2. Upload to Claude Desktop
3. Skills are automatically available

**Option 2: Direct Prompt**
1. Copy contents of `skills/{skill_name}/prompt.md`
2. Paste into Claude conversation
3. Claude operates as that analyzer

### Running Individual Skills

```
Analyze keyword match types for customer ID 1234567890
over the last 90 days.
```

### Running the Full Suite

```
Run a complete quarterly audit using the Cost Efficiency Suite
for customer ID 1234567890 covering the last 90 days.
```

---

## Skill Selection Guide

### By Business Type

**Retail with Physical Stores**:
1. GeoPerformanceAnalyzer (highest priority)
2. SearchTermAnalyzer
3. KeywordMatchAnalyzer
4. NegativeConflictAnalyzer
5. PMaxAnalyzer (if running PMax)

**E-commerce Only**:
1. SearchTermAnalyzer (highest priority)
2. KeywordMatchAnalyzer
3. PMaxAnalyzer (if running PMax)
4. NegativeConflictAnalyzer

**Service Area Business**:
1. GeoPerformanceAnalyzer (highest priority)
2. SearchTermAnalyzer
3. KeywordMatchAnalyzer

### By Problem

**High CPA**: KeywordMatchAnalyzer, SearchTermAnalyzer
**Low Impression Share**: NegativeConflictAnalyzer
**Wasted Spend**: SearchTermAnalyzer
**Poor ROAS in Locations**: GeoPerformanceAnalyzer
**PMax Issues**: PMaxAnalyzer

---

## Tier 2 & 3 Skills (Future)

### Tier 2: Advanced Optimization (Planned)
- Ad Group Performance Analyzer
- Device Performance Analyzer
- Dayparting Analyzer
- Landing Page Analyzer
- Demographics Analyzer

### Tier 3: Strategic Insights (Planned)
- Competitor Insights Analyzer
- Attribution Analyzer
- Campaign Overlap Analyzer
- Shared Negatives Manager
- Bulk Operations Tool

---

## Skill Development

New skills are being developed following this priority order:
1. **Tier 1** (Complete): Core cost efficiency - highest ROI
2. **Tier 2** (In Progress): Advanced optimization - performance tuning
3. **Tier 3** (Planned): Strategic insights - long-term planning

See [development roadmap](../thoughts/shared/plans/2025-11-22-mcp-skills-refactoring-implementation.md) for details.

---

## Support & Feedback

- **GitHub Issues**: https://github.com/datablogin/PaidSearchNav/issues
- **Documentation**: See individual skill README.md files
- **Examples**: See individual skill examples.md files

---

## Version History

### 1.0.0 (2025-11-24)
- Initial release of Tier 1 Cost Efficiency Suite
- 5 core skills available
- All skills tested and validated
- Complete documentation and examples
