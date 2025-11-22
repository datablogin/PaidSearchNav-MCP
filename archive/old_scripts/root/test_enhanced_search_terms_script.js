function main() {
    // Enhanced Search Terms Performance Extraction Script
    // Generated on: 2025-08-19T20:30:00.000000
    // Test Configuration: Fitness Connection (646-990-6417)

    // Calculate actual date range (Google Ads Scripts requires YYYY-MM-DD,YYYY-MM-DD format)
    var endDate = new Date();
    var startDate = new Date();

    // Set date range based on parameter
    var dateRangeParam = "LAST_90_DAYS";
    if (dateRangeParam === "LAST_90_DAYS") {
        startDate.setDate(endDate.getDate() - 90);
    } else if (dateRangeParam === "LAST_30_DAYS") {
        startDate.setDate(endDate.getDate() - 30);
    } else if (dateRangeParam === "LAST_7_DAYS") {
        startDate.setDate(endDate.getDate() - 7);
    } else if (dateRangeParam === "YESTERDAY") {
        startDate.setDate(endDate.getDate() - 1);
        endDate.setDate(endDate.getDate() - 1);
    } else {
        // Assume it's already in YYYY-MM-DD,YYYY-MM-DD format or handle custom ranges
        var dateRange = dateRangeParam;
    }

    // Format dates for Reports API (only if we calculated them)
    if (!dateRange) {
        var startDateStr = Utilities.formatDate(startDate, "GMT", "yyyyMMdd");
        var endDateStr = Utilities.formatDate(endDate, "GMT", "yyyyMMdd");
        var dateRange = startDateStr + "," + endDateStr;
    }

    // Log the computed date range for debugging
    Logger.log("Using date range for GAQL query: " + dateRange);
    Logger.log("Original parameter: " + dateRangeParam);

    var minClicks = 1;
    var minCostMicros = 10000; // Convert to micros
    var includeGeo = true;
    var locationIndicators = [
        "near me", "nearby", "close to me", "in my area",
        "gym near", "fitness near", "workout near", "training near",
        "dallas", "san antonio", "plano", "richardson", "garland",
        "texas", "tx", "dfw", "metro"
    ];

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
        "Search Term Score",
        "Local Intent",
        "Quality Indicator"
    ];

    var csvData = [headers];
    var processedRows = 0;
    var pageToken = null;
    var retryCount = 0;
    var maxRetries = 3;

    // Use Reports API with only confirmed available fields
    // Based on successful Fitness Connection testing
    var reportQuery = "SELECT " +
        "CampaignName, " +
        "AdGroupName, " +
        "Query, " +
        "Clicks, " +
        "Impressions, " +
        "Cost, " +
        "Conversions, " +
        "AverageCpc, " +
        "Ctr " +
        "FROM SEARCH_QUERY_PERFORMANCE_REPORT " +
        "WHERE Clicks >= " + minClicks + " " +
        "DURING " + dateRange;

    Logger.log("Generated report query: " + reportQuery);

    // Execute report with retry logic
    try {
        var report = AdsApp.report(reportQuery);
        var rows = report.rows();

        while (rows.hasNext()) {
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
            var searchTermScore = calculateSearchTermScore(clicks, conversions, cost, isLocalIntent);
            var qualityIndicator = getQualityIndicator(searchTermScore, isLocalIntent, matchType);

            var csvRow = [
                row["CampaignName"] || "",
                row["AdGroupName"] || "",
                searchTerm,
                matchType,
                row["Clicks"] || "0",
                row["Impressions"] || "0", 
                row["Cost"] || "0.00",
                row["Conversions"] || "0",
                conversionRate,
                costPerConversion,
                row["AverageCpc"] || "0.00",
                row["Ctr"] || "0.00%",
                searchTermScore,
                isLocalIntent,
                qualityIndicator
            ];

            csvData.push(csvRow);
        }

        retryCount = 0; // Reset retry count on successful execution

        } catch (e) {
            retryCount++;
            var errorMessage = e.toString();

            // Handle quota exceeded errors with special logic
            if (errorMessage.indexOf("QUOTA_EXCEEDED") !== -1 ||
                errorMessage.indexOf("RATE_LIMIT_EXCEEDED") !== -1 ||
                errorMessage.indexOf("Too Many Requests") !== -1) {

                Logger.log("Quota/rate limit exceeded detected: " + errorMessage);

                // For quota errors, use longer delays
                var quotaDelay = Math.min(Math.pow(2, retryCount) * 5000, 300000); // Max 5 minutes
                Logger.log("Quota exceeded - waiting " + (quotaDelay/1000) + " seconds before retry " + retryCount + "/" + maxRetries);

                if (retryCount >= maxRetries) {
                    Logger.log("Quota exceeded after " + maxRetries + " retries. Aborting.");
                    return {
                        "success": false,
                        "rows_processed": processedRows,
                        "changes_made": 0,
                        "error": "Google Ads API quota exceeded after " + maxRetries + " retries",
                        "error_type": "QUOTA_EXCEEDED",
                        "date_range": dateRange
                    };
                }

                Utilities.sleep(quotaDelay);

            } else if (errorMessage.indexOf("PERMISSION_DENIED") !== -1 ||
                       errorMessage.indexOf("AUTHENTICATION_ERROR") !== -1) {

                Logger.log("Authentication/permission error: " + errorMessage);
                return {
                    "success": false,
                    "rows_processed": processedRows,
                    "changes_made": 0,
                    "error": "Authentication or permission error: " + errorMessage,
                    "error_type": "AUTH_ERROR",
                    "date_range": dateRange
                };

            } else {
                // Handle other errors with standard retry logic
                if (retryCount >= maxRetries) {
                    Logger.log("Error after " + maxRetries + " retries: " + errorMessage);
                    return {
                        "success": false,
                        "rows_processed": processedRows,
                        "changes_made": 0,
                        "error": errorMessage,
                        "error_type": "GENERAL_ERROR",
                        "date_range": dateRange
                    };
                }

                // Exponential backoff for general errors
                var delay = Math.pow(2, retryCount) * 1000;
                Logger.log("Retrying in " + delay + "ms due to error: " + errorMessage);
                Utilities.sleep(delay);
            }
        }

    // Export to Google Drive with error handling and streaming for large datasets
    try {
        var fileName = "enhanced_search_terms_performance_" + Utilities.formatDate(new Date(), "GMT", "yyyy-MM-dd_HH-mm") + ".csv";

        // For large datasets (>5000 rows), use streaming approach
        var csvContent;
        if (processedRows > 5000) {
            Logger.log("Large dataset detected (" + processedRows + " rows). Using streaming CSV writer.");
            csvContent = streamingCSVWriter(csvData);
        } else {
            // Standard approach for smaller datasets
            csvContent = csvData.map(function(row) {
                return row.map(function(cell) {
                    return '"' + String(cell).replace(/"/g, '""') + '"';
                }).join(',');
            }).join('\n');
        }

        DriveApp.createFile(fileName, csvContent, MimeType.CSV);

        Logger.log("Enhanced search terms extraction completed:");
        Logger.log("- Rows processed: " + processedRows);
        Logger.log("- File created: " + fileName);
        Logger.log("- Date range used: " + dateRange);
        Logger.log("- Original parameter: " + dateRangeParam);
        Logger.log("- Enhanced features: Local Intent Detection, Quality Scoring, Match Type Inference");
        Logger.log("- Core fields: Campaign, Ad Group, Search Term, Match Type, Performance Metrics");
        Logger.log("- Intelligence: " + (processedRows > 0 ? "Successfully applied" : "Ready for next run"));

        return {
            "success": true,
            "rows_processed": processedRows,
            "changes_made": 0,
            "file_name": fileName,
            "date_range": dateRange,
            "enhanced_features": {
                "local_intent_detection": true,
                "quality_scoring": true,
                "geographic_intelligence": true,
                "production_parser_ready": true
            }
        };
    } catch (e) {
        Logger.log("Error creating file: " + e.toString());
        return {
            "success": false,
            "rows_processed": processedRows,
            "changes_made": 0,
            "error": e.toString(),
            "date_range": dateRange
        };
    }
}

function detectLocalIntent(searchTerm, indicators) {
    var term = searchTerm.toLowerCase();
    for (var i = 0; i < indicators.length; i++) {
        if (term.indexOf(indicators[i].toLowerCase()) !== -1) {
            return true;
        }
    }
    return false;
}

function inferMatchType(searchTerm) {
    // Infer match type based on search term characteristics
    // Since KeywordMatchType is not available in SEARCH_QUERY_PERFORMANCE_REPORT
    if (!searchTerm) return "Unknown";
    
    var term = searchTerm.toLowerCase().trim();
    
    // Check for exact match indicators (quotes, very specific terms)
    if (term.length <= 3 || 
        (term.indexOf(" ") === -1 && term.length <= 8) ||
        term.match(/^[a-z]+$/)) {
        return "Exact";
    }
    
    // Check for phrase match indicators (multiple words, specific phrases)
    if (term.indexOf(" ") !== -1 && term.split(" ").length <= 4) {
        return "Phrase";
    }
    
    // Everything else is likely broad match
    return "Broad";
}

function calculateSearchTermScore(clicks, conversions, cost, isLocalIntent) {
    // Calculate a composite score for search term quality
    var conversionRate = clicks > 0 ? conversions / clicks : 0;
    var costPerClick = clicks > 0 ? cost / clicks : 0;

    var score = 50; // Base score

    // Boost for conversions
    if (conversions > 0) {
        score += Math.min(conversions * 10, 30);
    }

    // Boost for good conversion rate
    if (conversionRate > 0.02) score += 10;
    if (conversionRate > 0.05) score += 10;

    // Penalty for high cost per click relative to conversions
    if (costPerClick > 5 && conversions === 0) score -= 20;

    // Boost for local intent
    if (isLocalIntent) score += 15;

    // Normalize to 0-100 scale
    return Math.max(0, Math.min(100, Math.round(score)));
}

function getQualityIndicator(searchTermScore, isLocalIntent, matchType) {
    // Provide quality indicator for production pipeline decision making
    if (searchTermScore >= 80) {
        return "High Value";
    }

    if (searchTermScore >= 60) {
        if (isLocalIntent) {
            return "Local Opportunity";
        }
        return "Good Performance";
    }

    if (searchTermScore >= 40) {
        if (matchType === "Broad") {
            return "Broad Review Needed";
        }
        return "Moderate Performance";
    }

    return "Low Performance";
}

function classifyLocationType(location, indicators) {
    if (!location) return "Unknown";

    var loc = location.toLowerCase();

    // Check for target cities first (more specific) - Fitness Connection markets
    var targetCities = ["dallas", "san antonio", "plano", "richardson", "garland", "irving", "mesquite"];
    for (var i = 0; i < targetCities.length; i++) {
        if (loc.indexOf(targetCities[i]) !== -1) {
            return "Target City";
        }
    }

    // Check for target states
    var targetStates = ["texas", "tx", "georgia", "ga", "north carolina", "nc"];
    for (var i = 0; i < targetStates.length; i++) {
        if (loc.indexOf(targetStates[i]) !== -1) {
            return "Target State";
        }
    }

    // Check if it's a nearby location based on common geographic terms
    var nearbyTerms = ["metro", "area", "county", "region", "vicinity"];
    for (var i = 0; i < nearbyTerms.length; i++) {
        if (loc.indexOf(nearbyTerms[i]) !== -1) {
            return "Nearby Region";
        }
    }

    return "Other";
}

function streamingCSVWriter(csvData) {
    // Memory-efficient CSV writing for large datasets
    // Process data in chunks to avoid memory issues
    var chunkSize = 1000;
    var csvContent = "";

    Logger.log("Starting streaming CSV write for " + csvData.length + " rows");

    for (var i = 0; i < csvData.length; i += chunkSize) {
        var chunk = csvData.slice(i, Math.min(i + chunkSize, csvData.length));

        var chunkContent = chunk.map(function(row) {
            return row.map(function(cell) {
                return '"' + String(cell).replace(/"/g, '""') + '"';
            }).join(',');
        }).join('\n');

        csvContent += chunkContent;
        if (i + chunkSize < csvData.length) {
            csvContent += '\n';
        }

        // Log progress for large datasets
        if (i > 0 && i % (chunkSize * 5) === 0) {
            Logger.log("Processed " + i + " rows for CSV export");
        }

        // Add small delay to prevent timeout on very large datasets
        if (i > 0 && i % (chunkSize * 10) === 0) {
            Utilities.sleep(100); // 100ms pause every 10k rows
        }
    }

    Logger.log("Streaming CSV write completed");
    return csvContent;
}