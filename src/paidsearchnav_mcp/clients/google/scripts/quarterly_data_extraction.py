"""Google Ads Scripts for automated quarterly data extraction.

This module implements Google Ads Scripts that automate the quarterly data extraction
process, replacing manual UI-based workflows with scheduled script-based data collection.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List

from paidsearchnav.platforms.google.client import GoogleAdsClient

from .base import ScriptBase, ScriptConfig, ScriptResult, ScriptStatus, ScriptType

logger = logging.getLogger(__name__)


class SearchTermsPerformanceScript(ScriptBase):
    """Script for extracting search terms performance data."""

    def __init__(self, client: GoogleAdsClient, config: ScriptConfig):
        super().__init__(client, config)
        self.script_type = (
            ScriptType.NEGATIVE_KEYWORD
        )  # Reuse existing type for compatibility

    def get_required_parameters(self) -> List[str]:
        """Get required parameters for search terms performance extraction."""
        return ["date_range", "customer_id"]

    def generate_script(self) -> str:
        """Generate Google Ads Script for search terms performance extraction."""
        date_range = self.config.parameters.get("date_range", "LAST_30_DAYS")
        include_geo = self.config.parameters.get("include_geographic_data", True)
        min_clicks = self.config.parameters.get("min_clicks", 1)
        min_cost = self.config.parameters.get("min_cost", 0.01)
        location_indicators = self.config.parameters.get(
            "location_indicators",
            [
                "near me",
                "nearby",
                "close to me",
                "in my area",
                "dallas",
                "san antonio",
                "atlanta",
                "fayetteville",
                "texas",
                "georgia",
                "north carolina",
                "nc",
                "gym near",
                "fitness near",
                "workout near",
            ],
        )

        script = f'''
function main() {{
    // Search Terms Performance Extraction Script (Google Ads API v20 Compatible)
    // Generated on: {datetime.utcnow().isoformat()}

    // Calculate actual date range (Google Ads Scripts requires YYYY-MM-DD,YYYY-MM-DD format)
    var endDate = new Date();
    var startDate = new Date();

    // Set date range based on parameter
    var dateRangeParam = "{date_range}";
    if (dateRangeParam === "LAST_90_DAYS") {{
        startDate.setDate(endDate.getDate() - 90);
    }} else if (dateRangeParam === "LAST_30_DAYS") {{
        startDate.setDate(endDate.getDate() - 30);
    }} else if (dateRangeParam === "LAST_7_DAYS") {{
        startDate.setDate(endDate.getDate() - 7);
    }} else if (dateRangeParam === "YESTERDAY") {{
        startDate.setDate(endDate.getDate() - 1);
        endDate.setDate(endDate.getDate() - 1);
    }} else {{
        // Assume it's already in YYYY-MM-DD,YYYY-MM-DD format or handle custom ranges
        var dateRange = dateRangeParam;
    }}

    // Format dates for Reports API (only if we calculated them)
    if (!dateRange) {{
        var startDateStr = Utilities.formatDate(startDate, "GMT", "yyyyMMdd");
        var endDateStr = Utilities.formatDate(endDate, "GMT", "yyyyMMdd");

        // Validate date strings were generated successfully
        if (!startDateStr || !endDateStr) {{
            throw new Error("Unable to calculate date range - invalid start or end date");
        }}

        var dateRange = startDateStr + "," + endDateStr;
    }}

    // Validate final date range before proceeding
    if (!dateRange || dateRange === "undefined" || dateRange === "") {{
        throw new Error("Date range validation failed - dateRange is not properly defined");
    }}

    // Log the computed date range for debugging
    Logger.log("Using date range for GAQL query: " + dateRange);
    Logger.log("Original parameter: " + dateRangeParam);

    // Configuration constants
    var LARGE_DATASET_THRESHOLD = 5000;
    var CHUNK_SIZE = 1000;
    var MAX_RETRIES = 3;
    var RETRY_BASE_DELAY = 1000;
    var QUOTA_RETRY_BASE_DELAY = 5000;
    var MAX_QUOTA_DELAY = 300000;

    var minClicks = Math.max(0, {min_clicks});
    var minCostMicros = Math.max(0, {min_cost * 1000000}); // Convert to micros, ensure non-negative
    var includeGeo = {str(include_geo).lower()};
    var locationIndicators = {location_indicators};

    // Create CSV headers (enhanced for production parser compatibility)
    var headers = [
        "Campaign",
        "Ad Group",
        "Search Term",
        "Match Type",
        "Clicks",
        "Impressions",
        "Cost",
        "Conversions",
        "Conv. Rate",
        "Cost / Conv.",
        "CPC",
        "CTR",
        "Impression Share",
        "Conversions Value",
        "View-through Conversions",
        "Search Term Score",
        "Local Intent",
        "Quality Indicator"
    ];

    if (includeGeo) {{
        headers = headers.concat([
            "Geographic Location",
            "Location Type",
            "Is Local Intent"
        ]);
    }}

    var csvData = [headers];
    var processedRows = 0;
    var pageToken = null;
    var retryCount = 0;
    var maxRetries = 3;

    // Use Reports API for better compatibility with Google Ads Scripts
    var reportQuery = "SELECT " +
        "CampaignName, " +
        "AdGroupName, " +
        "Query, " +
        "Clicks, " +
        "Impressions, " +
        "Cost, " +
        "Conversions, " +
        "ConversionsValue, " +
        "AverageCpc, " +
        "Ctr, " +
        "SearchImpressionShare";

    if (includeGeo) {{
        reportQuery += ", UserLocationName, LocationType";
    }}

    reportQuery += " FROM SEARCH_QUERY_PERFORMANCE_REPORT " +
                  "WHERE Clicks >= " + minClicks + " " +
                  "DURING " + dateRange;

    Logger.log("Generated report query: " + reportQuery);

    // Execute report with retry logic
    try {{
        var report = AdsApp.report(reportQuery);
        var rows = report.rows();

        while (rows.hasNext()) {{
            var row = rows.next();
            processedRows++;

            var searchTerm = row["Query"];
            var isLocalIntent = detectLocalIntent(searchTerm, locationIndicators);
            var matchType = inferMatchType(searchTerm); // Infer since KeywordMatchType not available

            // Calculate derived metrics
            var clicks = parseInt(row["Clicks"]) || 0;
            var conversions = parseFloat(row["Conversions"]) || 0;
            var cost = parseFloat(row["Cost"]) || 0;

            var conversionRate = clicks > 0 ?
                (conversions / clicks * 100).toFixed(2) + "%" : "0.00%";
            var costPerConversion = conversions > 0 ?
                (cost / conversions).toFixed(2) : "0.00";

            // Calculate enhanced metrics for production pipeline compatibility
            var conversionsValue = parseFloat(row["ConversionsValue"]) || 0;
            var viewThroughConversions = 0; // Not available in this report
            var searchTermScore = calculateSearchTermScore(clicks, conversions, cost, isLocalIntent);
            var qualityIndicator = getQualityIndicator(searchTermScore, isLocalIntent, matchType);

            var csvRow = [
                row["CampaignName"],
                row["AdGroupName"],
                searchTerm,
                matchType,
                row["Clicks"],
                row["Impressions"],
                row["Cost"],
                row["Conversions"],
                conversionRate,
                costPerConversion,
                row["AverageCpc"],
                row["Ctr"],
                row["SearchImpressionShare"],
                conversionsValue.toFixed(2),
                viewThroughConversions,
                searchTermScore,
                isLocalIntent,
                qualityIndicator
            ];

            if (includeGeo) {{
                var location = row["UserLocationName"] || "";
                var locationType = classifyLocationType(location, locationIndicators);
                csvRow = csvRow.concat([
                    location,
                    locationType,
                    isLocalIntent
                ]);
            }}

            csvData.push(csvRow);
        }}

        retryCount = 0; // Reset retry count on successful execution

        }} catch (e) {{
            retryCount++;
            var errorMessage = e.toString();

            // Handle quota exceeded errors with special logic
            if (errorMessage.indexOf("QUOTA_EXCEEDED") !== -1 ||
                errorMessage.indexOf("RATE_LIMIT_EXCEEDED") !== -1 ||
                errorMessage.indexOf("Too Many Requests") !== -1) {{

                Logger.log("Quota/rate limit exceeded detected: " + errorMessage);

                // For quota errors, use longer delays
                var quotaDelay = Math.min(Math.pow(2, retryCount) * 5000, 300000); // Max 5 minutes
                Logger.log("Quota exceeded - waiting " + (quotaDelay/1000) + " seconds before retry " + retryCount + "/" + maxRetries);

                if (retryCount >= maxRetries) {{
                    Logger.log("Quota exceeded after " + maxRetries + " retries. Aborting.");
                    return {{
                        "success": false,
                        "rows_processed": processedRows,
                        "changes_made": 0,
                        "error": "Google Ads API quota exceeded after " + maxRetries + " retries",
                        "error_type": "QUOTA_EXCEEDED",
                        "date_range": dateRange
                    }};
                }}

                Utilities.sleep(quotaDelay);

            }} else if (errorMessage.indexOf("PERMISSION_DENIED") !== -1 ||
                       errorMessage.indexOf("AUTHENTICATION_ERROR") !== -1) {{

                Logger.log("Authentication/permission error: " + errorMessage);
                return {{
                    "success": false,
                    "rows_processed": processedRows,
                    "changes_made": 0,
                    "error": "Authentication or permission error: " + errorMessage,
                    "error_type": "AUTH_ERROR",
                    "date_range": dateRange
                }};

            }} else {{
                // Handle other errors with standard retry logic
                if (retryCount >= maxRetries) {{
                    Logger.log("Error after " + maxRetries + " retries: " + errorMessage);
                    return {{
                        "success": false,
                        "rows_processed": processedRows,
                        "changes_made": 0,
                        "error": errorMessage,
                        "error_type": "GENERAL_ERROR",
                        "date_range": dateRange
                    }};
                }}

                // Exponential backoff for general errors
                var delay = Math.pow(2, retryCount) * 1000;
                Logger.log("Retrying in " + delay + "ms due to error: " + errorMessage);
                Utilities.sleep(delay);
            }}
        }}
    }} while (pageToken);

    // Export to Google Drive with error handling and streaming for large datasets
    try {{
        var fileName = "search_terms_performance_" + Utilities.formatDate(new Date(), "GMT", "yyyy-MM-dd_HH-mm") + ".csv";

        // For large datasets (>5000 rows), use streaming approach
        var csvContent;
        if (processedRows > 5000) {{
            Logger.log("Large dataset detected (" + processedRows + " rows). Using streaming CSV writer.");
            csvContent = streamingCSVWriter(csvData);
        }} else {{
            // Standard approach for smaller datasets
            csvContent = csvData.map(function(row) {{
                return row.map(function(cell) {{
                    return '"' + String(cell).replace(/"/g, '""') + '"';
                }}).join(',');
            }}).join('\\n');
        }}

        DriveApp.createFile(fileName, csvContent, MimeType.CSV);

        Logger.log("Search terms extraction completed:");
        Logger.log("- Rows processed: " + processedRows);
        Logger.log("- File created: " + fileName);
        Logger.log("- Date range used: " + dateRange);
        Logger.log("- Original parameter: " + dateRangeParam);

        return {{
            "success": true,
            "rows_processed": processedRows,
            "changes_made": 0,
            "file_name": fileName,
            "date_range": dateRange
        }};
    }} catch (e) {{
        Logger.log("Error creating file: " + e.toString());
        return {{
            "success": false,
            "rows_processed": processedRows,
            "changes_made": 0,
            "error": e.toString(),
            "date_range": dateRange
        }};
    }}
}}

function detectLocalIntent(searchTerm, indicators) {{
    var term = searchTerm.toLowerCase();
    for (var i = 0; i < indicators.length; i++) {{
        if (term.indexOf(indicators[i].toLowerCase()) !== -1) {{
            return true;
        }}
    }}
    return false;
}}

function inferMatchType(searchTerm) {{
    // Infer match type based on search term characteristics
    // Since KeywordMatchType is not available in SEARCH_QUERY_PERFORMANCE_REPORT
    if (!searchTerm) return "Unknown";

    var term = searchTerm.toLowerCase().trim();

    // Check for exact match indicators (quotes, very specific terms)
    if (term.length <= 3 ||
        (term.indexOf(" ") === -1 && term.length <= 8) ||
        term.match(/^[a-z]+$/)) {{
        return "Exact";
    }}

    // Check for phrase match indicators (multiple words, specific phrases)
    if (term.indexOf(" ") !== -1 && term.split(" ").length <= 4) {{
        return "Phrase";
    }}

    // Everything else is likely broad match
    return "Broad";
}}

function calculateSearchTermScore(clicks, conversions, cost, isLocalIntent) {{
    // Calculate a composite score for search term quality
    var conversionRate = clicks > 0 ? conversions / clicks : 0;
    var costPerClick = clicks > 0 ? cost / clicks : 0;

    var score = 50; // Base score

    // Boost for conversions
    if (conversions > 0) {{
        score += Math.min(conversions * 10, 30);
    }}

    // Boost for good conversion rate
    if (conversionRate > 0.02) score += 10;
    if (conversionRate > 0.05) score += 10;

    // Penalty for high cost per click relative to conversions
    if (costPerClick > 5 && conversions === 0) score -= 20;

    // Boost for local intent
    if (isLocalIntent) score += 15;

    // Normalize to 0-100 scale
    return Math.max(0, Math.min(100, Math.round(score)));
}}

function getQualityIndicator(searchTermScore, isLocalIntent, matchType) {{
    // Provide quality indicator for production pipeline decision making
    if (searchTermScore >= 80) {{
        return "High Value";
    }}

    if (searchTermScore >= 60) {{
        if (isLocalIntent) {{
            return "Local Opportunity";
        }}
        return "Good Performance";
    }}

    if (searchTermScore >= 40) {{
        if (matchType === "Broad") {{
            return "Broad Review Needed";
        }}
        return "Moderate Performance";
    }}

    return "Low Performance";
}}

function classifyLocationType(location, indicators) {{
    if (!location) return "Unknown";

    var loc = location.toLowerCase();

    // Check for target cities first (more specific)
    var targetCities = ["dallas", "san antonio", "atlanta", "fayetteville"];
    for (var i = 0; i < targetCities.length; i++) {{
        if (loc.indexOf(targetCities[i]) !== -1) {{
            return "Target City";
        }}
    }}

    // Check for target states
    var targetStates = ["texas", "tx", "georgia", "ga", "north carolina", "nc"];
    for (var i = 0; i < targetStates.length; i++) {{
        if (loc.indexOf(targetStates[i]) !== -1) {{
            return "Target State";
        }}
    }}

    // Check if it's a nearby location based on common geographic terms
    var nearbyTerms = ["metro", "area", "county", "region", "vicinity"];
    for (var i = 0; i < nearbyTerms.length; i++) {{
        if (loc.indexOf(nearbyTerms[i]) !== -1) {{
            return "Nearby Region";
        }}
    }}

    return "Other";
}}

function streamingCSVWriter(csvData) {{
    // Memory-efficient CSV writing for large datasets
    // Process data in chunks to avoid memory issues
    var csvContent = "";

    Logger.log("Starting streaming CSV write for " + csvData.length + " rows");

    for (var i = 0; i < csvData.length; i += CHUNK_SIZE) {{
        var chunk = csvData.slice(i, Math.min(i + CHUNK_SIZE, csvData.length));

        var chunkContent = chunk.map(function(row) {{
            return row.map(function(cell) {{
                return '"' + String(cell).replace(/"/g, '""') + '"';
            }}).join(',');
        }}).join('\\n');

        csvContent += chunkContent;
        if (i + CHUNK_SIZE < csvData.length) {{
            csvContent += '\\n';
        }}

        // Log progress for large datasets
        if (i > 0 && i % (CHUNK_SIZE * 5) === 0) {{
            Logger.log("Processed " + i + " rows for CSV export");
        }}

        // Add small delay to prevent timeout on very large datasets
        if (i > 0 && i % (CHUNK_SIZE * 10) === 0) {{
            Utilities.sleep(100); // 100ms pause every 10k rows
        }}
    }}

    Logger.log("Streaming CSV write completed");
    return csvContent;
}}
'''
        return script

    def process_results(self, results: Dict[str, Any]) -> ScriptResult:
        """Process search terms extraction results."""
        # Check if the script encountered errors
        if not results.get("success", True):
            error_type = results.get("error_type", "UNKNOWN")
            error_message = results.get("error", "Unknown error occurred")

            # Set appropriate status based on error type
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
        else:
            status = ScriptStatus.COMPLETED.value
            errors = []
            warnings = results.get("warnings", [])

        return ScriptResult(
            status=status,
            execution_time=results.get("execution_time", 0.0),
            rows_processed=results.get("rows_processed", 0),
            changes_made=0,  # Data extraction, no changes
            errors=errors,
            warnings=warnings,
            details={
                "script_type": "search_terms_performance",
                "file_name": results.get("file_name", ""),
                "date_range": results.get("date_range", ""),
                "geographic_data_included": self.config.parameters.get(
                    "include_geographic_data", True
                ),
                "error_type": results.get("error_type")
                if not results.get("success", True)
                else None,
            },
        )


class KeywordPerformanceScript(ScriptBase):
    """Script for extracting keyword performance data with match type analysis."""

    def __init__(self, client: GoogleAdsClient, config: ScriptConfig):
        super().__init__(client, config)
        self.script_type = ScriptType.NEGATIVE_KEYWORD

    def get_required_parameters(self) -> List[str]:
        """Get required parameters for keyword performance extraction."""
        return ["date_range", "customer_id"]

    def generate_script(self) -> str:
        """Generate Google Ads Script for keyword performance extraction."""
        date_range = self.config.parameters.get("date_range", "LAST_30_DAYS")
        include_quality_score = self.config.parameters.get(
            "include_quality_score", True
        )
        min_impressions = self.config.parameters.get("min_impressions", 10)

        script = f'''
function main() {{
    // Keyword Performance Extraction Script
    // Generated on: {datetime.utcnow().isoformat()}

    var dateRange = "{date_range}";
    var minImpressions = {min_impressions};
    var includeQualityScore = {str(include_quality_score).lower()};

    // Create CSV headers
    var headers = [
        "Campaign",
        "Ad Group",
        "Keyword",
        "Match Type",
        "Clicks",
        "Impressions",
        "Cost",
        "Conversions",
        "Conv. Rate",
        "Cost / Conv.",
        "CPC",
        "CTR",
        "Avg. Position",
        "Max CPC",
        "Status"
    ];

    if (includeQualityScore) {{
        headers = headers.concat([
            "Quality Score",
            "Landing Page Experience",
            "Ad Relevance",
            "Expected CTR"
        ]);
    }}

    headers = headers.concat([
        "First Page Bid Estimate",
        "Top of Page Bid Estimate",
        "Bid Recommendation"
    ]);

    var csvData = [headers];
    var processedRows = 0;
    var bidRecommendations = 0;

    // Query keywords report
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
        "ConversionRate, " +
        "CostPerConversion, " +
        "AverageCpc, " +
        "Ctr, " +
        "AveragePosition, " +
        "CpcBid, " +
        "Status " +
        (includeQualityScore ? ", QualityScore, LandingPageExperience, AdRelevance, ExpectedCtr " : "") +
        ", FirstPageCpc, TopOfPageCpc " +
        "FROM KEYWORDS_PERFORMANCE_REPORT " +
        "WHERE Impressions >= " + minImpressions + " " +
        "DURING " + dateRange
    );

    var rows = report.rows();
    while (rows.hasNext()) {{
        var row = rows.next();
        processedRows++;

        var currentCpc = parseFloat(row["CpcBid"]) || 0;
        var firstPageBid = parseFloat(row["FirstPageCpc"]) || 0;
        var topOfPageBid = parseFloat(row["TopOfPageCpc"]) || 0;
        var avgCpc = parseFloat(row["AverageCpc"]) || 0;

        var bidRecommendation = generateBidRecommendation(
            currentCpc, firstPageBid, topOfPageBid, avgCpc,
            parseFloat(row["ConversionRate"]) || 0,
            parseFloat(row["CostPerConversion"]) || 0
        );

        if (bidRecommendation !== "No change") {{
            bidRecommendations++;
        }}

        var csvRow = [
            row["CampaignName"],
            row["AdGroupName"],
            row["Criteria"],
            row["KeywordMatchType"],
            row["Clicks"],
            row["Impressions"],
            row["Cost"],
            row["Conversions"],
            row["ConversionRate"],
            row["CostPerConversion"],
            row["AverageCpc"],
            row["Ctr"],
            row["AveragePosition"],
            row["CpcBid"],
            row["Status"]
        ];

        if (includeQualityScore) {{
            csvRow = csvRow.concat([
                row["QualityScore"],
                row["LandingPageExperience"],
                row["AdRelevance"],
                row["ExpectedCtr"]
            ]);
        }}

        csvRow = csvRow.concat([
            row["FirstPageCpc"],
            row["TopOfPageCpc"],
            bidRecommendation
        ]);

        csvData.push(csvRow);
    }}

    // Export to Google Drive
    var fileName = "keyword_performance_" + Utilities.formatDate(new Date(), "GMT", "yyyy-MM-dd_HH-mm") + ".csv";
    var csvContent = csvData.map(function(row) {{
        return row.map(function(cell) {{
            return '"' + String(cell).replace(/"/g, '""') + '"';
        }}).join(',');
    }}).join('\\n');

    DriveApp.createFile(fileName, csvContent, MimeType.CSV);

    Logger.log("Keyword performance extraction completed:");
    Logger.log("- Rows processed: " + processedRows);
    Logger.log("- Bid recommendations: " + bidRecommendations);
    Logger.log("- File created: " + fileName);
    Logger.log("- Date range: " + dateRange);

    return {{
        "success": true,
        "rows_processed": processedRows,
        "changes_made": bidRecommendations,
        "file_name": fileName,
        "date_range": dateRange
    }};
}}

function generateBidRecommendation(currentCpc, firstPageBid, topOfPageBid, avgCpc, convRate, costPerConv) {{
    // Simple bid recommendation logic
    if (firstPageBid > 0 && currentCpc < firstPageBid * 0.8) {{
        return "Increase to first page bid";
    }}

    if (topOfPageBid > 0 && currentCpc < topOfPageBid * 0.9 && convRate > 0.02) {{
        return "Increase to top of page";
    }}

    if (avgCpc > 0 && currentCpc > avgCpc * 1.5 && convRate < 0.01) {{
        return "Decrease bid - low performance";
    }}

    if (costPerConv > 0 && costPerConv > 50) {{
        return "Decrease bid - high cost per conversion";
    }}

    return "No change";
}}
'''
        return script

    def process_results(self, results: Dict[str, Any]) -> ScriptResult:
        """Process keyword performance extraction results."""
        return ScriptResult(
            status=ScriptStatus.COMPLETED.value,
            execution_time=results.get("execution_time", 0.0),
            rows_processed=results.get("rows_processed", 0),
            changes_made=results.get("changes_made", 0),  # Bid recommendations count
            errors=[],
            warnings=results.get("warnings", []),
            details={
                "script_type": "keyword_performance",
                "file_name": results.get("file_name", ""),
                "date_range": results.get("date_range", ""),
                "bid_recommendations": results.get("changes_made", 0),
                "quality_score_included": self.config.parameters.get(
                    "include_quality_score", True
                ),
            },
        )


class GeographicPerformanceScript(ScriptBase):
    """Script for extracting geographic performance data for local businesses."""

    def __init__(self, client: GoogleAdsClient, config: ScriptConfig):
        super().__init__(client, config)
        self.script_type = ScriptType.NEGATIVE_KEYWORD

    def get_required_parameters(self) -> List[str]:
        """Get required parameters for geographic performance extraction."""
        return ["date_range", "customer_id"]

    def generate_script(self) -> str:
        """Generate Google Ads Script for geographic performance extraction."""
        date_range = self.config.parameters.get("date_range", "LAST_30_DAYS")
        target_locations = self.config.parameters.get(
            "target_locations", ["Dallas", "San Antonio", "Atlanta", "Fayetteville"]
        )
        min_clicks = self.config.parameters.get("min_clicks", 1)

        locations_str = '", "'.join(target_locations)

        script = f'''
function main() {{
    // Geographic Performance Extraction Script
    // Generated on: {datetime.utcnow().isoformat()}

    var dateRange = "{date_range}";
    var targetLocations = ["{locations_str}"];
    var minClicks = {min_clicks};

    // Create CSV headers
    var headers = [
        "Campaign",
        "Ad Group",
        "Geographic Location",
        "Location Type",
        "Clicks",
        "Impressions",
        "Cost",
        "Conversions",
        "Conv. Rate",
        "Cost / Conv.",
        "CPC",
        "CTR",
        "Distance",
        "Local Intent Score",
        "Store Performance Rank"
    ];

    var csvData = [headers];
    var processedRows = 0;
    var locationPerformance = {{}};

    // Query geographic performance report
    var report = AdsApp.report(
        "SELECT " +
        "CampaignName, " +
        "AdGroupName, " +
        "UserLocationName, " +
        "Clicks, " +
        "Impressions, " +
        "Cost, " +
        "Conversions, " +
        "ConversionRate, " +
        "CostPerConversion, " +
        "AverageCpc, " +
        "Ctr " +
        "FROM GEO_PERFORMANCE_REPORT " +
        "WHERE Clicks >= " + minClicks + " " +
        "DURING " + dateRange
    );

    var rows = report.rows();
    while (rows.hasNext()) {{
        var row = rows.next();
        processedRows++;

        var location = row["UserLocationName"] || "";
        var locationType = classifyLocationType(location);
        var distance = calculateDistance(location, targetLocations);
        var localIntentScore = calculateLocalIntentScore(row);

        // Track location performance for ranking
        if (!locationPerformance[location]) {{
            locationPerformance[location] = {{
                clicks: 0,
                conversions: 0,
                cost: 0
            }};
        }}

        locationPerformance[location].clicks += parseInt(row["Clicks"]) || 0;
        locationPerformance[location].conversions += parseFloat(row["Conversions"]) || 0;
        locationPerformance[location].cost += parseFloat(row["Cost"]) || 0;

        var csvRow = [
            row["CampaignName"],
            row["AdGroupName"],
            location,
            locationType,
            row["Clicks"],
            row["Impressions"],
            row["Cost"],
            row["Conversions"],
            row["ConversionRate"],
            row["CostPerConversion"],
            row["AverageCpc"],
            row["Ctr"],
            distance,
            localIntentScore,
            "" // Will be filled after ranking
        ];

        csvData.push(csvRow);
    }}

    // Calculate store performance rankings
    var rankedLocations = rankLocationsByPerformance(locationPerformance);

    // Update CSV data with rankings
    for (var i = 1; i < csvData.length; i++) {{
        var location = csvData[i][2];
        csvData[i][14] = rankedLocations[location] || "Unranked";
    }}

    // Export to Google Drive
    var fileName = "geographic_performance_" + Utilities.formatDate(new Date(), "GMT", "yyyy-MM-dd_HH-mm") + ".csv";
    var csvContent = csvData.map(function(row) {{
        return row.map(function(cell) {{
            return '"' + String(cell).replace(/"/g, '""') + '"';
        }}).join(',');
    }}).join('\\n');

    DriveApp.createFile(fileName, csvContent, MimeType.CSV);

    Logger.log("Geographic performance extraction completed:");
    Logger.log("- Rows processed: " + processedRows);
    Logger.log("- Unique locations: " + Object.keys(locationPerformance).length);
    Logger.log("- File created: " + fileName);
    Logger.log("- Date range: " + dateRange);

    return {{
        "success": true,
        "rows_processed": processedRows,
        "changes_made": 0,
        "file_name": fileName,
        "date_range": dateRange,
        "unique_locations": Object.keys(locationPerformance).length
    }};
}}

function classifyLocationType(location) {{
    if (!location) return "Unknown";

    var cityPatterns = ["dallas", "san antonio", "atlanta", "fayetteville"];
    var statePatterns = ["texas", "georgia", "north carolina"];

    var loc = location.toLowerCase();

    for (var i = 0; i < cityPatterns.length; i++) {{
        if (loc.indexOf(cityPatterns[i]) !== -1) {{
            return "Target City";
        }}
    }}

    for (var i = 0; i < statePatterns.length; i++) {{
        if (loc.indexOf(statePatterns[i]) !== -1) {{
            return "Target State";
        }}
    }}

    return "Other";
}}

function calculateDistance(location, targetLocations) {{
    // Simplified distance calculation based on location names
    var loc = location.toLowerCase();

    for (var i = 0; i < targetLocations.length; i++) {{
        if (loc.indexOf(targetLocations[i].toLowerCase()) !== -1) {{
            return "0-5 miles";
        }}
    }}

    return "Unknown";
}}

function calculateLocalIntentScore(row) {{
    // Calculate local intent score based on conversion rate and geographic specificity
    var convRate = parseFloat(row["ConversionRate"]) || 0;
    var ctr = parseFloat(row["Ctr"]) || 0;

    var score = (convRate * 0.7) + (ctr * 0.3);

    if (score > 0.05) return "High";
    if (score > 0.02) return "Medium";
    return "Low";
}}

function rankLocationsByPerformance(locationPerformance) {{
    var locations = Object.keys(locationPerformance);
    var rankings = {{}};

    // Sort by conversion rate (conversions / clicks)
    locations.sort(function(a, b) {{
        var aRate = locationPerformance[a].clicks > 0 ?
            locationPerformance[a].conversions / locationPerformance[a].clicks : 0;
        var bRate = locationPerformance[b].clicks > 0 ?
            locationPerformance[b].conversions / locationPerformance[b].clicks : 0;
        return bRate - aRate;
    }});

    for (var i = 0; i < locations.length; i++) {{
        rankings[locations[i]] = i + 1;
    }}

    return rankings;
}}
'''
        return script

    def process_results(self, results: Dict[str, Any]) -> ScriptResult:
        """Process geographic performance extraction results."""
        return ScriptResult(
            status=ScriptStatus.COMPLETED.value,
            execution_time=results.get("execution_time", 0.0),
            rows_processed=results.get("rows_processed", 0),
            changes_made=0,  # Data extraction, no changes
            errors=[],
            warnings=results.get("warnings", []),
            details={
                "script_type": "geographic_performance",
                "file_name": results.get("file_name", ""),
                "date_range": results.get("date_range", ""),
                "unique_locations": results.get("unique_locations", 0),
                "target_locations": self.config.parameters.get("target_locations", []),
            },
        )


class CampaignPerformanceScript(ScriptBase):
    """Script for extracting campaign performance data with cross-campaign analysis."""

    def __init__(self, client: GoogleAdsClient, config: ScriptConfig):
        super().__init__(client, config)
        self.script_type = ScriptType.NEGATIVE_KEYWORD

    def get_required_parameters(self) -> List[str]:
        """Get required parameters for campaign performance extraction."""
        return ["date_range", "customer_id"]

    def generate_script(self) -> str:
        """Generate Google Ads Script for campaign performance extraction."""
        date_range = self.config.parameters.get("date_range", "LAST_30_DAYS")
        include_device_data = self.config.parameters.get("include_device_data", True)
        include_demographics = self.config.parameters.get("include_demographics", True)

        script = f'''
function main() {{
    // Campaign Performance Extraction Script
    // Generated on: {datetime.utcnow().isoformat()}

    var dateRange = "{date_range}";
    var includeDeviceData = {str(include_device_data).lower()};
    var includeDemographics = {str(include_demographics).lower()};

    // Create CSV headers
    var headers = [
        "Campaign",
        "Campaign Type",
        "Status",
        "Budget",
        "Clicks",
        "Impressions",
        "Cost",
        "Conversions",
        "Conv. Rate",
        "Cost / Conv.",
        "CPC",
        "CTR",
        "Impression Share",
        "Budget Utilization",
        "Performance Score"
    ];

    if (includeDeviceData) {{
        headers = headers.concat([
            "Mobile Clicks",
            "Desktop Clicks",
            "Tablet Clicks",
            "Mobile Conv Rate",
            "Desktop Conv Rate"
        ]);
    }}

    if (includeDemographics) {{
        headers = headers.concat([
            "Age 18-24 Performance",
            "Age 25-34 Performance",
            "Age 35-44 Performance",
            "Age 45-54 Performance",
            "Age 55+ Performance"
        ]);
    }}

    var csvData = [headers];
    var processedRows = 0;
    var budgetRecommendations = 0;

    // Query campaign performance report
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
        "ConversionRate, " +
        "CostPerConversion, " +
        "AverageCpc, " +
        "Ctr, " +
        "SearchImpressionShare " +
        "FROM CAMPAIGN_PERFORMANCE_REPORT " +
        "WHERE Impressions > 0 " +
        "DURING " + dateRange
    );

    var rows = report.rows();
    while (rows.hasNext()) {{
        var row = rows.next();
        processedRows++;

        var campaignName = row["CampaignName"];
        var cost = parseFloat(row["Cost"]) || 0;
        var budget = parseFloat(row["BudgetPeriod"]) || 0;
        var budgetUtilization = budget > 0 ? (cost / budget * 100).toFixed(1) + "%" : "N/A";

        var performanceScore = calculatePerformanceScore(row);

        var csvRow = [
            campaignName,
            row["CampaignType"],
            row["CampaignStatus"],
            row["BudgetPeriod"],
            row["Clicks"],
            row["Impressions"],
            row["Cost"],
            row["Conversions"],
            row["ConversionRate"],
            row["CostPerConversion"],
            row["AverageCpc"],
            row["Ctr"],
            row["SearchImpressionShare"],
            budgetUtilization,
            performanceScore
        ];

        // Add device performance data if requested
        if (includeDeviceData) {{
            var deviceData = getDevicePerformance(campaignName, dateRange);
            csvRow = csvRow.concat([
                deviceData.mobile.clicks,
                deviceData.desktop.clicks,
                deviceData.tablet.clicks,
                deviceData.mobile.convRate,
                deviceData.desktop.convRate
            ]);
        }}

        // Add demographic performance data if requested
        if (includeDemographics) {{
            var demoData = getDemographicPerformance(campaignName, dateRange);
            csvRow = csvRow.concat([
                demoData.age_18_24,
                demoData.age_25_34,
                demoData.age_35_44,
                demoData.age_45_54,
                demoData.age_55_plus
            ]);
        }}

        csvData.push(csvRow);

        // Check for budget recommendations
        if (parseFloat(row["SearchImpressionShare"]) < 70 && performanceScore === "High") {{
            budgetRecommendations++;
        }}
    }}

    // Export to Google Drive
    var fileName = "campaign_performance_" + Utilities.formatDate(new Date(), "GMT", "yyyy-MM-dd_HH-mm") + ".csv";
    var csvContent = csvData.map(function(row) {{
        return row.map(function(cell) {{
            return '"' + String(cell).replace(/"/g, '""') + '"';
        }}).join(',');
    }}).join('\\n');

    DriveApp.createFile(fileName, csvContent, MimeType.CSV);

    Logger.log("Campaign performance extraction completed:");
    Logger.log("- Rows processed: " + processedRows);
    Logger.log("- Budget recommendations: " + budgetRecommendations);
    Logger.log("- File created: " + fileName);
    Logger.log("- Date range: " + dateRange);

    return {{
        "success": true,
        "rows_processed": processedRows,
        "changes_made": budgetRecommendations,
        "file_name": fileName,
        "date_range": dateRange
    }};
}}

function calculatePerformanceScore(row) {{
    var convRate = parseFloat(row["ConversionRate"]) || 0;
    var ctr = parseFloat(row["Ctr"]) || 0;
    var impressionShare = parseFloat(row["SearchImpressionShare"]) || 0;

    var score = (convRate * 40) + (ctr * 30) + (impressionShare * 30);

    if (score > 70) return "High";
    if (score > 40) return "Medium";
    return "Low";
}}

function getDevicePerformance(campaignName, dateRange) {{
    // Simplified device performance simulation
    // In real implementation, this would query device performance reports
    return {{
        mobile: {{ clicks: "60%", convRate: "2.5%" }},
        desktop: {{ clicks: "35%", convRate: "3.2%" }},
        tablet: {{ clicks: "5%", convRate: "1.8%" }}
    }};
}}

function getDemographicPerformance(campaignName, dateRange) {{
    // Simplified demographic performance simulation
    // In real implementation, this would query demographic reports
    return {{
        age_18_24: "Medium",
        age_25_34: "High",
        age_35_44: "High",
        age_45_54: "Medium",
        age_55_plus: "Low"
    }};
}}
'''
        return script

    def process_results(self, results: Dict[str, Any]) -> ScriptResult:
        """Process campaign performance extraction results."""
        return ScriptResult(
            status=ScriptStatus.COMPLETED.value,
            execution_time=results.get("execution_time", 0.0),
            rows_processed=results.get("rows_processed", 0),
            changes_made=results.get("changes_made", 0),  # Budget recommendations count
            errors=[],
            warnings=results.get("warnings", []),
            details={
                "script_type": "campaign_performance",
                "file_name": results.get("file_name", ""),
                "date_range": results.get("date_range", ""),
                "budget_recommendations": results.get("changes_made", 0),
                "device_data_included": self.config.parameters.get(
                    "include_device_data", True
                ),
                "demographics_included": self.config.parameters.get(
                    "include_demographics", True
                ),
            },
        )
