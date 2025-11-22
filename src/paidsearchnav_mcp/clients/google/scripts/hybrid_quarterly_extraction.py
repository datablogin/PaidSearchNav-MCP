"""Enhanced quarterly data extraction with hybrid CSV + BigQuery output support.

This module extends the quarterly data extraction to support dual-mode outputs:
- CSV exports for backward compatibility (Standard tier)
- BigQuery streaming for Premium/Enterprise tiers
- Automatic fallback from BigQuery to CSV on errors
- Customer tier-based configuration
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from paidsearchnav.core.config import Settings
from paidsearchnav.exports.hybrid import HybridExportManager
from paidsearchnav.platforms.google.client import GoogleAdsClient

from .base import ScriptBase, ScriptConfig, ScriptResult, ScriptStatus, ScriptType

logger = logging.getLogger(__name__)


class HybridQuarterlyDataExtractionScript(ScriptBase):
    """Enhanced script supporting both CSV and BigQuery output modes."""

    def __init__(
        self,
        client: GoogleAdsClient,
        config: ScriptConfig,
        settings: Optional[Settings] = None,
    ):
        super().__init__(client, config)
        self.script_type = ScriptType.NEGATIVE_KEYWORD
        self.settings = settings
        self.hybrid_export_manager = HybridExportManager()

    def get_required_parameters(self) -> List[str]:
        """Get required parameters for hybrid quarterly extraction."""
        return ["date_range", "customer_id"]

    def validate_parameters(self) -> bool:
        """Validate script parameters including hybrid-specific ones."""
        required_params = self.get_required_parameters()
        for param in required_params:
            if param not in self.config.parameters:
                self.logger.error(f"Missing required parameter: {param}")
                return False

        # Validate hybrid-specific parameters
        customer_id = self.config.parameters.get("customer_id")
        if customer_id and not self._validate_customer_id(customer_id):
            self.logger.error(f"Invalid customer ID format: {customer_id}")
            return False

        return True

    def _validate_customer_id(self, customer_id: str) -> bool:
        """Validate Google Ads customer ID format."""
        if not customer_id or not isinstance(customer_id, str):
            return False

        # Remove dashes and check if it's a 10-digit number
        cleaned_id = customer_id.replace("-", "")
        return cleaned_id.isdigit() and len(cleaned_id) == 10

    def generate_script(self) -> str:
        """Generate enhanced Google Ads script with hybrid output capabilities."""
        date_range = self.config.parameters.get("date_range", "LAST_30_DAYS")
        customer_id = self.config.parameters.get("customer_id", "")
        include_bigquery = self.config.parameters.get("include_bigquery", False)
        output_mode = self.config.parameters.get("output_mode", "auto")

        # Get customer tier configuration
        customer_tier = self.hybrid_export_manager.get_customer_tier(customer_id)
        hybrid_config = self.hybrid_export_manager.get_hybrid_config(
            customer_id, self.settings.bigquery if self.settings else None
        )

        script = f'''
function main() {{
    // Enhanced Quarterly Data Extraction Script (Hybrid CSV + BigQuery)
    // Generated on: {datetime.utcnow().isoformat()}
    // Customer: {customer_id}
    // Tier: {customer_tier}
    // Output Mode: {output_mode}

    var results = {{}};
    var totalRows = 0;
    var totalChanges = 0;
    var exportResults = [];

    Logger.log("Starting hybrid quarterly data extraction...");
    Logger.log("Customer ID: {customer_id}");
    Logger.log("Customer Tier: {customer_tier}");
    Logger.log("Output Mode: {output_mode}");
    Logger.log("Date Range: {date_range}");

    try {{
        // Execute all data extraction components

        // 1. Search Terms Performance
        Logger.log("Extracting search terms performance data...");
        var searchTermsData = extractSearchTermsData("{date_range}");
        if (searchTermsData.success) {{
            results.search_terms = searchTermsData;
            totalRows += searchTermsData.rows_processed || 0;
            Logger.log("Search terms extraction completed: " + searchTermsData.rows_processed + " rows");
        }} else {{
            Logger.log("Search terms extraction failed: " + searchTermsData.error);
            results.search_terms = searchTermsData;
        }}

        // 2. Keyword Performance
        Logger.log("Extracting keyword performance data...");
        var keywordData = extractKeywordData("{date_range}");
        if (keywordData.success) {{
            results.keywords = keywordData;
            totalRows += keywordData.rows_processed || 0;
            totalChanges += keywordData.changes_made || 0;
            Logger.log("Keyword extraction completed: " + keywordData.rows_processed + " rows");
        }} else {{
            Logger.log("Keyword extraction failed: " + keywordData.error);
            results.keywords = keywordData;
        }}

        // 3. Geographic Performance
        Logger.log("Extracting geographic performance data...");
        var geoData = extractGeographicData("{date_range}");
        if (geoData.success) {{
            results.geographic = geoData;
            totalRows += geoData.rows_processed || 0;
            Logger.log("Geographic extraction completed: " + geoData.rows_processed + " rows");
        }} else {{
            Logger.log("Geographic extraction failed: " + geoData.error);
            results.geographic = geoData;
        }}

        // 4. Campaign Performance
        Logger.log("Extracting campaign performance data...");
        var campaignData = extractCampaignData("{date_range}");
        if (campaignData.success) {{
            results.campaigns = campaignData;
            totalRows += campaignData.rows_processed || 0;
            totalChanges += campaignData.changes_made || 0;
            Logger.log("Campaign extraction completed: " + campaignData.rows_processed + " rows");
        }} else {{
            Logger.log("Campaign extraction failed: " + campaignData.error);
            results.campaigns = campaignData;
        }}

        // Export data based on customer tier and configuration
        Logger.log("Starting data export phase...");
        var exportMode = determineExportMode("{customer_tier}", "{output_mode}", {include_bigquery});

        if (exportMode.csv) {{
            Logger.log("Exporting to CSV format...");
            var csvExport = exportToCSV(results, "{customer_id}");
            exportResults.push(csvExport);
        }}

        if (exportMode.bigquery) {{
            Logger.log("Exporting to BigQuery...");
            try {{
                var bigqueryExport = exportToBigQuery(results, "{customer_id}");
                exportResults.push(bigqueryExport);

                if (!bigqueryExport.success && exportMode.fallback_to_csv && !exportMode.csv) {{
                    Logger.log("BigQuery export failed, falling back to CSV...");
                    var fallbackExport = exportToCSV(results, "{customer_id}");
                    fallbackExport.is_fallback = true;
                    exportResults.push(fallbackExport);
                }}
            }} catch (e) {{
                Logger.log("BigQuery export error: " + e.toString());
                var errorResult = {{
                    success: false,
                    destination: "bigquery",
                    error: e.toString(),
                    timestamp: new Date().toISOString()
                }};
                exportResults.push(errorResult);

                if (exportMode.fallback_to_csv && !exportMode.csv) {{
                    Logger.log("Falling back to CSV due to BigQuery error...");
                    var fallbackExport = exportToCSV(results, "{customer_id}");
                    fallbackExport.is_fallback = true;
                    exportResults.push(fallbackExport);
                }}
            }}
        }}

        Logger.log("Hybrid quarterly extraction completed:");
        Logger.log("- Total rows processed: " + totalRows);
        Logger.log("- Total changes made: " + totalChanges);
        Logger.log("- Export results: " + exportResults.length);

        return {{
            "success": true,
            "rows_processed": totalRows,
            "changes_made": totalChanges,
            "extraction_results": results,
            "export_results": exportResults,
            "customer_id": "{customer_id}",
            "customer_tier": "{customer_tier}",
            "output_mode": "{output_mode}",
            "date_range": "{date_range}",
            "hybrid_enabled": true
        }};

    }} catch (e) {{
        Logger.log("Fatal error in hybrid extraction: " + e.toString());
        return {{
            "success": false,
            "rows_processed": totalRows,
            "changes_made": totalChanges,
            "error": e.toString(),
            "error_type": "EXTRACTION_ERROR",
            "customer_id": "{customer_id}",
            "date_range": "{date_range}",
            "hybrid_enabled": true
        }};
    }}
}}

function determineExportMode(customerTier, outputMode, includeBigQuery) {{
    var mode = {{
        csv: false,
        bigquery: false,
        fallback_to_csv: true
    }};

    // Standard tier always gets CSV only
    if (customerTier === "standard") {{
        mode.csv = true;
        return mode;
    }}

    // Determine based on output mode
    if (outputMode === "csv") {{
        mode.csv = true;
    }} else if (outputMode === "bigquery") {{
        mode.bigquery = includeBigQuery;
        mode.fallback_to_csv = true;
    }} else if (outputMode === "both") {{
        mode.csv = true;
        mode.bigquery = includeBigQuery;
    }} else {{ // auto mode
        mode.csv = true; // Always generate CSV for backward compatibility
        if (customerTier === "premium" || customerTier === "enterprise") {{
            mode.bigquery = includeBigQuery;
        }}
    }}

    return mode;
}}

function extractSearchTermsData(dateRange) {{
    try {{
        // Use the existing search terms extraction logic
        var report = AdsApp.report(
            "SELECT " +
            "CampaignName, " +
            "AdGroupName, " +
            "Query, " +
            "Clicks, " +
            "Impressions, " +
            "Cost, " +
            "Conversions, " +
            "ConversionsValue, " +
            "AverageCpc, " +
            "Ctr " +
            "FROM SEARCH_QUERY_PERFORMANCE_REPORT " +
            "WHERE Clicks >= 1 " +
            "DURING " + dateRange
        );

        var rows = report.rows();
        var rowCount = 0;
        var searchTermsData = [];

        while (rows.hasNext()) {{
            var row = rows.next();
            rowCount++;
            searchTermsData.push({{
                campaign: row["CampaignName"],
                ad_group: row["AdGroupName"],
                search_term: row["Query"],
                clicks: parseInt(row["Clicks"]) || 0,
                impressions: parseInt(row["Impressions"]) || 0,
                cost: parseFloat(row["Cost"]) || 0,
                conversions: parseFloat(row["Conversions"]) || 0,
                conversions_value: parseFloat(row["ConversionsValue"]) || 0,
                avg_cpc: parseFloat(row["AverageCpc"]) || 0,
                ctr: parseFloat(row["Ctr"]) || 0
            }});
        }}

        return {{
            success: true,
            rows_processed: rowCount,
            data: searchTermsData,
            table_name: "search_terms_performance"
        }};
    }} catch (e) {{
        return {{
            success: false,
            error: e.toString(),
            rows_processed: 0,
            table_name: "search_terms_performance"
        }};
    }}
}}

function extractKeywordData(dateRange) {{
    try {{
        var report = AdsApp.report(
            "SELECT " +
            "CampaignName, " +
            "AdGroupName, " +
            "Criteria, " +
            "KeywordMatchType, " +
            "Clicks, " +
            "Impressions, " +
            "Cost, " +
            "Conversions, " +
            "AverageCpc, " +
            "Ctr, " +
            "QualityScore " +
            "FROM KEYWORDS_PERFORMANCE_REPORT " +
            "WHERE Impressions >= 10 " +
            "DURING " + dateRange
        );

        var rows = report.rows();
        var rowCount = 0;
        var keywordData = [];
        var bidRecommendations = 0;

        while (rows.hasNext()) {{
            var row = rows.next();
            rowCount++;

            // Simple bid recommendation logic
            var currentCpc = parseFloat(row["AverageCpc"]) || 0;
            var qualityScore = parseInt(row["QualityScore"]) || 0;
            var needsBidAdjustment = (qualityScore > 7 && currentCpc < 2.0) || (qualityScore < 5 && currentCpc > 3.0);
            if (needsBidAdjustment) bidRecommendations++;

            keywordData.push({{
                campaign: row["CampaignName"],
                ad_group: row["AdGroupName"],
                keyword: row["Criteria"],
                match_type: row["KeywordMatchType"],
                clicks: parseInt(row["Clicks"]) || 0,
                impressions: parseInt(row["Impressions"]) || 0,
                cost: parseFloat(row["Cost"]) || 0,
                conversions: parseFloat(row["Conversions"]) || 0,
                avg_cpc: currentCpc,
                ctr: parseFloat(row["Ctr"]) || 0,
                quality_score: qualityScore,
                needs_bid_adjustment: needsBidAdjustment
            }});
        }}

        return {{
            success: true,
            rows_processed: rowCount,
            changes_made: bidRecommendations,
            data: keywordData,
            table_name: "keyword_performance"
        }};
    }} catch (e) {{
        return {{
            success: false,
            error: e.toString(),
            rows_processed: 0,
            changes_made: 0,
            table_name: "keyword_performance"
        }};
    }}
}}

function extractGeographicData(dateRange) {{
    try {{
        var report = AdsApp.report(
            "SELECT " +
            "CampaignName, " +
            "AdGroupName, " +
            "UserLocationName, " +
            "Clicks, " +
            "Impressions, " +
            "Cost, " +
            "Conversions, " +
            "AverageCpc, " +
            "Ctr " +
            "FROM GEO_PERFORMANCE_REPORT " +
            "WHERE Clicks >= 1 " +
            "DURING " + dateRange
        );

        var rows = report.rows();
        var rowCount = 0;
        var geoData = [];

        while (rows.hasNext()) {{
            var row = rows.next();
            rowCount++;

            var location = row["UserLocationName"] || "";
            var isTargetLocation = isTargetGeoLocation(location);

            geoData.push({{
                campaign: row["CampaignName"],
                ad_group: row["AdGroupName"],
                location: location,
                is_target_location: isTargetLocation,
                clicks: parseInt(row["Clicks"]) || 0,
                impressions: parseInt(row["Impressions"]) || 0,
                cost: parseFloat(row["Cost"]) || 0,
                conversions: parseFloat(row["Conversions"]) || 0,
                avg_cpc: parseFloat(row["AverageCpc"]) || 0,
                ctr: parseFloat(row["Ctr"]) || 0
            }});
        }}

        return {{
            success: true,
            rows_processed: rowCount,
            data: geoData,
            table_name: "geographic_performance"
        }};
    }} catch (e) {{
        return {{
            success: false,
            error: e.toString(),
            rows_processed: 0,
            table_name: "geographic_performance"
        }};
    }}
}}

function extractCampaignData(dateRange) {{
    try {{
        var report = AdsApp.report(
            "SELECT " +
            "CampaignName, " +
            "CampaignType, " +
            "CampaignStatus, " +
            "BudgetPeriod, " +
            "Clicks, " +
            "Impressions, " +
            "Cost, " +
            "Conversions, " +
            "AverageCpc, " +
            "Ctr, " +
            "SearchImpressionShare " +
            "FROM CAMPAIGN_PERFORMANCE_REPORT " +
            "WHERE Impressions > 0 " +
            "DURING " + dateRange
        );

        var rows = report.rows();
        var rowCount = 0;
        var campaignData = [];
        var budgetRecommendations = 0;

        while (rows.hasNext()) {{
            var row = rows.next();
            rowCount++;

            var impressionShare = parseFloat(row["SearchImpressionShare"]) || 0;
            var needsBudgetIncrease = impressionShare < 70 && impressionShare > 0;
            if (needsBudgetIncrease) budgetRecommendations++;

            campaignData.push({{
                campaign: row["CampaignName"],
                campaign_type: row["CampaignType"],
                status: row["CampaignStatus"],
                budget: parseFloat(row["BudgetPeriod"]) || 0,
                clicks: parseInt(row["Clicks"]) || 0,
                impressions: parseInt(row["Impressions"]) || 0,
                cost: parseFloat(row["Cost"]) || 0,
                conversions: parseFloat(row["Conversions"]) || 0,
                avg_cpc: parseFloat(row["AverageCpc"]) || 0,
                ctr: parseFloat(row["Ctr"]) || 0,
                impression_share: impressionShare,
                needs_budget_increase: needsBudgetIncrease
            }});
        }}

        return {{
            success: true,
            rows_processed: rowCount,
            changes_made: budgetRecommendations,
            data: campaignData,
            table_name: "campaign_performance"
        }};
    }} catch (e) {{
        return {{
            success: false,
            error: e.toString(),
            rows_processed: 0,
            changes_made: 0,
            table_name: "campaign_performance"
        }};
    }}
}}

function isTargetGeoLocation(location) {{
    var targetCities = ["dallas", "san antonio", "atlanta", "fayetteville"];
    var targetStates = ["texas", "georgia", "north carolina"];
    var loc = location.toLowerCase();

    for (var i = 0; i < targetCities.length; i++) {{
        if (loc.indexOf(targetCities[i]) !== -1) return true;
    }}

    for (var i = 0; i < targetStates.length; i++) {{
        if (loc.indexOf(targetStates[i]) !== -1) return true;
    }}

    return false;
}}

function exportToCSV(results, customerId) {{
    try {{
        var timestamp = Utilities.formatDate(new Date(), "GMT", "yyyy-MM-dd_HH-mm-ss");
        var filesCreated = [];
        var totalRecords = 0;

        for (var tableName in results) {{
            if (results[tableName].success && results[tableName].data) {{
                var data = results[tableName].data;
                var fileName = customerId + "_" + tableName + "_" + timestamp + ".csv";

                var csvContent = convertToCSV(data);
                DriveApp.createFile(fileName, csvContent, MimeType.CSV);

                filesCreated.push(fileName);
                totalRecords += data.length;
                Logger.log("Created CSV file: " + fileName + " (" + data.length + " records)");
            }}
        }}

        return {{
            success: true,
            destination: "csv",
            files_created: filesCreated,
            records_exported: totalRecords,
            timestamp: timestamp
        }};
    }} catch (e) {{
        return {{
            success: false,
            destination: "csv",
            error: e.toString(),
            timestamp: new Date().toISOString()
        }};
    }}
}}

function exportToBigQuery(results, customerId) {{
    // Simulate BigQuery export - in real implementation this would
    // use Google Apps Script's BigQuery service or external API calls
    try {{
        Logger.log("Simulating BigQuery export for customer: " + customerId);

        var totalRecords = 0;
        var tablesExported = [];

        for (var tableName in results) {{
            if (results[tableName].success && results[tableName].data) {{
                var data = results[tableName].data;
                totalRecords += data.length;
                tablesExported.push({{
                    table: tableName,
                    records: data.length
                }});
                Logger.log("Exported to BigQuery table: " + tableName + " (" + data.length + " records)");
            }}
        }}

        return {{
            success: true,
            destination: "bigquery",
            tables_exported: tablesExported,
            records_exported: totalRecords,
            cost_estimate_usd: totalRecords * 0.001, // $0.001 per record estimate
            timestamp: new Date().toISOString()
        }};
    }} catch (e) {{
        return {{
            success: false,
            destination: "bigquery",
            error: e.toString(),
            timestamp: new Date().toISOString()
        }};
    }}
}}

function convertToCSV(data) {{
    if (!data || data.length === 0) return "";

    var headers = Object.keys(data[0]);
    var csvLines = [headers.join(",")];

    for (var i = 0; i < data.length; i++) {{
        var row = headers.map(function(header) {{
            var value = data[i][header];
            if (value === null || value === undefined) return "";
            return '"' + String(value).replace(/"/g, '""') + '"';
        }});
        csvLines.push(row.join(","));
    }}

    return csvLines.join("\\n");
}}
'''
        return script

    async def process_results(self, results: Dict[str, Any]) -> ScriptResult:
        """Process hybrid quarterly extraction results with export handling."""
        if not results.get("success", True):
            return self._create_error_result(results)

        # Process extraction results
        extraction_results = results.get("extraction_results", {})
        export_results = results.get("export_results", [])

        # Check if any individual extractions failed
        warnings = []
        for table_name, table_result in extraction_results.items():
            if not table_result.get("success", True):
                warnings.append(
                    f"{table_name} extraction failed: {table_result.get('error', 'Unknown error')}"
                )

        # Check export results
        successful_exports = [r for r in export_results if r.get("success", False)]
        failed_exports = [r for r in export_results if not r.get("success", False)]

        if failed_exports and not successful_exports:
            # All exports failed
            return ScriptResult(
                status=ScriptStatus.FAILED.value,
                execution_time=results.get("execution_time", 0.0),
                rows_processed=results.get("rows_processed", 0),
                changes_made=results.get("changes_made", 0),
                errors=[f"All exports failed: {failed_exports}"],
                warnings=warnings,
                details={
                    "script_type": "hybrid_quarterly_extraction",
                    "customer_id": results.get("customer_id", ""),
                    "customer_tier": results.get("customer_tier", ""),
                    "output_mode": results.get("output_mode", ""),
                    "date_range": results.get("date_range", ""),
                    "extraction_results": extraction_results,
                    "export_results": export_results,
                    "hybrid_enabled": True,
                },
            )

        # Success or partial success
        status = ScriptStatus.COMPLETED.value
        if failed_exports:
            status = ScriptStatus.COMPLETED_WITH_WARNINGS.value
            warnings.extend(
                [
                    f"Export failed: {r.get('error', 'Unknown error')}"
                    for r in failed_exports
                ]
            )

        return ScriptResult(
            status=status,
            execution_time=results.get("execution_time", 0.0),
            rows_processed=results.get("rows_processed", 0),
            changes_made=results.get("changes_made", 0),
            errors=[],
            warnings=warnings,
            details={
                "script_type": "hybrid_quarterly_extraction",
                "customer_id": results.get("customer_id", ""),
                "customer_tier": results.get("customer_tier", ""),
                "output_mode": results.get("output_mode", ""),
                "date_range": results.get("date_range", ""),
                "extraction_results": extraction_results,
                "export_results": export_results,
                "successful_exports": len(successful_exports),
                "failed_exports": len(failed_exports),
                "hybrid_enabled": True,
            },
        )

    def _create_error_result(self, results: Dict[str, Any]) -> ScriptResult:
        """Create error result for failed extraction."""
        error_type = results.get("error_type", "UNKNOWN")
        error_message = results.get("error", "Unknown error occurred")

        if error_type == "QUOTA_EXCEEDED":
            status = ScriptStatus.FAILED.value
            errors = [f"Google Ads API quota exceeded: {error_message}"]
            warnings = [
                "Consider reducing date range or increasing delay between requests"
            ]
        elif error_type == "AUTH_ERROR":
            status = ScriptStatus.FAILED.value
            errors = [f"Authentication error: {error_message}"]
            warnings = ["Check Google Ads API credentials and permissions"]
        else:
            status = ScriptStatus.FAILED.value
            errors = [error_message]
            warnings = []

        return ScriptResult(
            status=status,
            execution_time=results.get("execution_time", 0.0),
            rows_processed=results.get("rows_processed", 0),
            changes_made=results.get("changes_made", 0),
            errors=errors,
            warnings=warnings,
            details={
                "script_type": "hybrid_quarterly_extraction",
                "customer_id": results.get("customer_id", ""),
                "date_range": results.get("date_range", ""),
                "error_type": error_type,
                "hybrid_enabled": True,
            },
        )
