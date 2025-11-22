// ========================================
// ADVANCED APIS DIAGNOSTIC SCRIPT
// Test each Advanced API individually
// ========================================

function main() {
    Logger.log("🔍 ADVANCED APIS DIAGNOSTIC TEST");
    Logger.log("======================================");
    Logger.log("");
    
    // Test 1: Check if Advanced APIs are mentioned in global scope
    Logger.log("📋 TEST 1: Global Object Detection");
    Logger.log("----------------------------------");
    
    var globalObjects = [
        "Analytics",
        "AnalyticsReporting", 
        "GoogleAnalytics",
        "BigQuery",
        "Bigquery",
        "YouTube",
        "YouTubeAnalytics",
        "FusionTables",
        "Fusion",
        "Drive",
        "Gmail",
        "Calendar"
    ];
    
    globalObjects.forEach(function(objName) {
        try {
            var obj = eval("typeof " + objName);
            Logger.log("  " + objName + ": " + obj);
        } catch (e) {
            Logger.log("  " + objName + ": ERROR - " + e.message);
        }
    });
    
    Logger.log("");
    Logger.log("📊 TEST 2: Analytics API Tests");
    Logger.log("------------------------------");
    
    // Test Analytics in different ways
    var analyticsTests = [
        function() { return typeof Analytics; },
        function() { return typeof AnalyticsReporting; },
        function() { return typeof GoogleAnalytics; },
        function() { return Analytics; },
        function() { return AnalyticsReporting; }
    ];
    
    analyticsTests.forEach(function(test, index) {
        try {
            var result = test();
            Logger.log("  Analytics Test " + (index + 1) + ": " + result);
        } catch (e) {
            Logger.log("  Analytics Test " + (index + 1) + ": ERROR - " + e.message);
        }
    });
    
    Logger.log("");
    Logger.log("🗄️ TEST 3: BigQuery API Tests");
    Logger.log("-----------------------------");
    
    // Test BigQuery in different ways
    var bigqueryTests = [
        function() { return typeof BigQuery; },
        function() { return typeof Bigquery; },
        function() { return BigQuery; },
        function() { return Bigquery; }
    ];
    
    bigqueryTests.forEach(function(test, index) {
        try {
            var result = test();
            Logger.log("  BigQuery Test " + (index + 1) + ": " + result);
        } catch (e) {
            Logger.log("  BigQuery Test " + (index + 1) + ": ERROR - " + e.message);
        }
    });
    
    Logger.log("");
    Logger.log("📺 TEST 4: YouTube Analytics API Tests");
    Logger.log("--------------------------------------");
    
    try {
        Logger.log("  YouTube typeof: " + typeof YouTube);
        Logger.log("  YouTubeAnalytics typeof: " + typeof YouTubeAnalytics);
    } catch (e) {
        Logger.log("  YouTube APIs: ERROR - " + e.message);
    }
    
    Logger.log("");
    Logger.log("📋 TEST 5: Fusion Tables API Tests");
    Logger.log("----------------------------------");
    
    try {
        Logger.log("  FusionTables typeof: " + typeof FusionTables);
        Logger.log("  Fusion typeof: " + typeof Fusion);
    } catch (e) {
        Logger.log("  Fusion APIs: ERROR - " + e.message);
    }
    
    Logger.log("");
    Logger.log("🔑 TEST 6: Advanced API Enablement Check");
    Logger.log("----------------------------------------");
    
    // Try to access Advanced API methods that should exist
    try {
        // Check if we can access Analytics methods
        if (typeof Analytics !== 'undefined' && Analytics) {
            Logger.log("  Analytics.Reports: " + typeof Analytics.Reports);
            Logger.log("  Analytics.Data: " + typeof Analytics.Data);
        } else {
            Logger.log("  Analytics object not available");
        }
        
        // Check if we can access BigQuery methods
        if (typeof BigQuery !== 'undefined' && BigQuery) {
            Logger.log("  BigQuery.Jobs: " + typeof BigQuery.Jobs);
            Logger.log("  BigQuery.Datasets: " + typeof BigQuery.Datasets);
        } else {
            Logger.log("  BigQuery object not available");
        }
    } catch (e) {
        Logger.log("  Advanced API methods check failed: " + e.message);
    }
    
    Logger.log("");
    Logger.log("🎯 TEST 7: Simple API Calls");
    Logger.log("---------------------------");
    
    // Try simple API calls to see if they work
    try {
        Logger.log("Testing simple Analytics call...");
        // This would be a real Analytics API call
        // var response = Analytics.Reports.batchGet({...});
        Logger.log("  Analytics call: Would need actual implementation");
    } catch (e) {
        Logger.log("  Analytics call failed: " + e.message);
    }
    
    try {
        Logger.log("Testing simple BigQuery call...");
        // This would be a real BigQuery API call  
        // var response = BigQuery.Jobs.query({...});
        Logger.log("  BigQuery call: Would need actual implementation");
    } catch (e) {
        Logger.log("  BigQuery call failed: " + e.message);
    }
    
    Logger.log("");
    Logger.log("📊 TEST 8: Environment Information");
    Logger.log("---------------------------------");
    
    try {
        Logger.log("  Script execution environment: Google Ads Scripts");
        Logger.log("  Account ID: " + AdsApp.currentAccount().getCustomerId());
        Logger.log("  Script timezone: " + AdsApp.currentAccount().getTimeZone());
        Logger.log("  Current date: " + new Date());
        
        // Check if we're in preview mode
        try {
            Logger.log("  Preview mode: " + (typeof preview !== 'undefined'));
        } catch (e) {
            Logger.log("  Preview mode: Unknown");
        }
    } catch (e) {
        Logger.log("  Environment check failed: " + e.message);
    }
    
    Logger.log("");
    Logger.log("🔧 TEST 9: Advanced APIs Configuration Check");
    Logger.log("--------------------------------------------");
    
    // Check if there are any configuration objects or hints about Advanced APIs
    var configObjects = [
        "AdvancedApis",
        "EnabledApis", 
        "ScriptConfig",
        "ApiConfig",
        "GoogleApis"
    ];
    
    configObjects.forEach(function(objName) {
        try {
            var obj = eval("typeof " + objName);
            Logger.log("  " + objName + ": " + obj);
            if (obj !== 'undefined') {
                var value = eval(objName);
                Logger.log("    Value: " + JSON.stringify(value));
            }
        } catch (e) {
            Logger.log("  " + objName + ": ERROR - " + e.message);
        }
    });
    
    Logger.log("");
    Logger.log("🎉 DIAGNOSTIC COMPLETE");
    Logger.log("======================");
    Logger.log("");
    Logger.log("📝 SUMMARY:");
    Logger.log("  - If you see 'undefined' for all Advanced APIs, they're not enabled");
    Logger.log("  - If you see 'object' or 'function', the API is available");
    Logger.log("  - ReferenceError means the API name doesn't exist in this environment");
    Logger.log("");
    Logger.log("🔍 Next Steps:");
    Logger.log("  1. Check Google Ads Scripts console Advanced APIs settings");
    Logger.log("  2. Verify billing is enabled for your Google Cloud project");
    Logger.log("  3. Ensure APIs are enabled in Google Cloud Console");
    Logger.log("  4. Check if your Google Ads account has Advanced APIs access");
    Logger.log("");
    
    return {
        "diagnostic_complete": true,
        "timestamp": new Date().toISOString(),
        "account_id": AdsApp.currentAccount().getCustomerId()
    };
}