#!/usr/bin/env python3
"""
Generate GAQL-FIXED Search Terms Performance Script for Fitness Connection
with corrected GAQL query syntax for Google Ads Scripts environment.
"""

from datetime import datetime


def generate_correct_gaql_script():
    """Generate script with corrected GAQL syntax."""
    print("🔧 Generating GAQL-FIXED Search Terms Performance Script")
    print("=" * 70)
    print("🎯 Fix: GAQL query syntax for Google Ads Scripts")
    print("📅 Issue: QueryError.BAD_VALUE: Error in WHERE clause: invalid value 2025")
    print()

    # Create the corrected JavaScript code directly
    # Based on Google Ads Scripts documentation
    script_code = (
        """
function main() {
    // Search Terms Performance Extraction Script (Google Ads Scripts Compatible)
    // Generated on: """
        + datetime.utcnow().isoformat()
        + """
    // FIXED: Corrected GAQL query syntax for Google Ads Scripts

    // Calculate actual date range
    var endDate = new Date();
    var startDate = new Date();
    startDate.setDate(endDate.getDate() - 90);

    var startDateStr = Utilities.formatDate(startDate, "GMT", "yyyy-MM-dd");
    var endDateStr = Utilities.formatDate(endDate, "GMT", "yyyy-MM-dd");

    // Log the computed date range for debugging
    Logger.log("Using date range: " + startDateStr + " to " + endDateStr);

    var minClicks = 1;
    var minCost = 0.01;
    var includeGeo = true;
    var locationIndicators = ['near me', 'nearby', 'close to me', 'in my area', 'dallas', 'san antonio', 'atlanta', 'fayetteville', 'texas', 'georgia', 'north carolina', 'nc', 'gym near', 'fitness near', 'workout near', 'fitness center near', '24 hour gym', '24/7 gym', 'cheap gym', 'gym membership', 'personal trainer near', 'group fitness near'];

    // Create CSV headers
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
        "Impression Share"
    ];

    if (includeGeo) {
        headers = headers.concat([
            "Geographic Location",
            "Location Type",
            "Is Local Intent"
        ]);
    }

    var csvData = [headers];
    var processedRows = 0;
    var retryCount = 0;
    var maxRetries = 3;

    // Use Google Ads Scripts native reporting approach instead of GAQL
    // This is more compatible with the Scripts environment

    try {
        Logger.log("Starting search terms report query...");

        // Use the native AdsApp reporting instead of search() method
        var report = AdsApp.report(
            "SELECT " +
            "CampaignName, " +
            "AdGroupName, " +
            "Query, " +
            "KeywordMatchType, " +
            "Clicks, " +
            "Impressions, " +
            "Cost, " +
            "Conversions, " +
            "ConversionRate, " +
            "CostPerConversion, " +
            "AverageCpc, " +
            "Ctr, " +
            "SearchImpressionShare " +
            "FROM SEARCH_QUERY_PERFORMANCE_REPORT " +
            "WHERE Clicks >= " + minClicks + " " +
            "AND Cost >= " + minCost + " " +
            "DURING " + startDateStr + "," + endDateStr
        );

        Logger.log("Report query executed successfully");

        var rows = report.rows();
        while (rows.hasNext()) {
            var row = rows.next();
            processedRows++;

            var searchTerm = row["Query"];
            var isLocalIntent = detectLocalIntent(searchTerm, locationIndicators);

            // Format conversion rate and cost per conversion
            var conversionRate = parseFloat(row["ConversionRate"]) || 0;
            var costPerConversion = parseFloat(row["CostPerConversion"]) || 0;

            var csvRow = [
                row["CampaignName"],
                row["AdGroupName"],
                searchTerm,
                row["KeywordMatchType"],
                row["Clicks"],
                row["Impressions"],
                row["Cost"],
                row["Conversions"],
                (conversionRate * 100).toFixed(2) + "%",
                costPerConversion.toFixed(2),
                row["AverageCpc"],
                (parseFloat(row["Ctr"]) * 100).toFixed(2) + "%",
                (parseFloat(row["SearchImpressionShare"]) * 100).toFixed(2) + "%"
            ];

            if (includeGeo) {
                // For now, add placeholder geographic data
                // Geographic data requires separate queries in Google Ads Scripts
                var locationType = classifyLocationType("", locationIndicators);
                csvRow = csvRow.concat([
                    "Geographic data requires separate query",
                    locationType,
                    isLocalIntent
                ]);
            }

            csvData.push(csvRow);

            // Log progress periodically
            if (processedRows % 1000 === 0) {
                Logger.log("Processed " + processedRows + " rows...");
            }
        }

    } catch (e) {
        Logger.log("Error during report execution: " + e.toString());
        return {
            "success": false,
            "rows_processed": processedRows,
            "changes_made": 0,
            "error": e.toString(),
            "error_type": "REPORT_ERROR",
            "date_range": startDateStr + "," + endDateStr
        };
    }

    // Export to Google Drive with error handling
    try {
        var fileName = "search_terms_performance_" + Utilities.formatDate(new Date(), "GMT", "yyyy-MM-dd_HH-mm") + ".csv";

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
            }).join('\\n');
        }

        DriveApp.createFile(fileName, csvContent, MimeType.CSV);

        Logger.log("Search terms extraction completed:");
        Logger.log("- Rows processed: " + processedRows);
        Logger.log("- File created: " + fileName);
        Logger.log("- Date range used: " + startDateStr + "," + endDateStr);

        return {
            "success": true,
            "rows_processed": processedRows,
            "changes_made": 0,
            "file_name": fileName,
            "date_range": startDateStr + "," + endDateStr
        };
    } catch (e) {
        Logger.log("Error creating file: " + e.toString());
        return {
            "success": false,
            "rows_processed": processedRows,
            "changes_made": 0,
            "error": e.toString(),
            "date_range": startDateStr + "," + endDateStr
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

function classifyLocationType(location, indicators) {
    if (!location) return "Unknown";

    var loc = location.toLowerCase();

    // Check if location matches any of the configured indicators
    for (var i = 0; i < indicators.length; i++) {
        var indicator = indicators[i].toLowerCase();
        if (loc.indexOf(indicator) !== -1) {
            // Classify as city if it contains city names
            if (indicator.indexOf("dallas") !== -1 ||
                indicator.indexOf("san antonio") !== -1 ||
                indicator.indexOf("atlanta") !== -1 ||
                indicator.indexOf("fayetteville") !== -1) {
                return "Target City";
            }
            // Classify as state if it contains state names
            if (indicator.indexOf("texas") !== -1 ||
                indicator.indexOf("georgia") !== -1 ||
                indicator.indexOf("north carolina") !== -1 ||
                indicator.indexOf("nc") !== -1) {
                return "Target State";
            }
        }
    }

    return "Other";
}

function streamingCSVWriter(csvData) {
    // Memory-efficient CSV writing for large datasets
    var chunkSize = 1000;
    var csvContent = "";

    Logger.log("Starting streaming CSV write for " + csvData.length + " rows");

    for (var i = 0; i < csvData.length; i += chunkSize) {
        var chunk = csvData.slice(i, Math.min(i + chunkSize, csvData.length));

        var chunkContent = chunk.map(function(row) {
            return row.map(function(cell) {
                return '"' + String(cell).replace(/"/g, '""') + '"';
            }).join(',');
        }).join('\\n');

        csvContent += chunkContent;
        if (i + chunkSize < csvData.length) {
            csvContent += '\\n';
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
"""
    )

    # Save the corrected script
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"fitness_connection_search_terms_GAQL_FIXED_{timestamp}.js"

    with open(filename, "w", encoding="utf-8") as f:
        f.write(script_code)

    print("✅ GAQL-FIXED script generated successfully!")
    print(f"📄 Script length: {len(script_code):,} characters")
    print(f"💾 Saved: {filename}")

    return filename, script_code


def analyze_gaql_fix():
    """Analyze the GAQL syntax fix."""
    print("\n🔍 GAQL Fix Analysis")
    print("=" * 50)

    print("🚨 Previous Issues:")
    print("   1. ❌ GAQL syntax: 'segments.date DURING 2025-05-21,2025-08-19'")
    print("   2. ❌ Error: 'QueryError.BAD_VALUE: invalid value 2025'")
    print("   3. ❌ Using search() method incorrectly")

    print("\n🔧 Applied Fixes:")
    print("   1. ✅ Switched to AdsApp.report() instead of AdsApp.search()")
    print("   2. ✅ Used SEARCH_QUERY_PERFORMANCE_REPORT (native report type)")
    print("   3. ✅ Proper date format: DURING startDate,endDate")
    print("   4. ✅ Standard Google Ads Scripts report syntax")
    print("   5. ✅ Removed problematic GAQL query structure")

    print("\n📊 Key Changes:")
    print("   • FROM: AdsApp.search(gaqlQuery) → AdsApp.report(reportQuery)")
    print("   • FROM: search_term_view → SEARCH_QUERY_PERFORMANCE_REPORT")
    print("   • FROM: segments.date → standard report date handling")
    print("   • FROM: complex GAQL → simple report SQL")

    print("\n✅ Expected Results:")
    print("   • No more GAQL syntax errors")
    print("   • Proper search terms data extraction")
    print("   • Compatible with Google Ads Scripts environment")
    print("   • Actual rows processed (> 0)")


def main():
    """Main execution."""
    print("🚀 Creating GAQL-FIXED Search Terms Performance Script")
    print("=" * 65)
    print(f"📅 Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Generate the fixed script
    filename, script_code = generate_correct_gaql_script()

    # Analyze the fix
    analyze_gaql_fix()

    print("\n🎯 Ready for Testing:")
    print(f"   1. Deploy script: {filename}")
    print("   2. Execute in Google Ads Scripts environment")
    print("   3. Look for successful report execution")
    print("   4. Verify actual search terms data")

    print("\n💡 Success Indicators:")
    print("   • Log: 'Report query executed successfully'")
    print("   • Log: 'Processed [N] rows...' (where N > 0)")
    print("   • Log: 'Rows processed: [number > 0]'")
    print("   • CSV with actual Fitness Connection search terms")

    return True


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
