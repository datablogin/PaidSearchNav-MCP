"""Geographic Performance Max optimization scripts.

This module implements Google Ads Scripts for geographic performance analysis
and local business optimization within Performance Max campaigns.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List

from paidsearchnav_mcp.platforms.google.client import GoogleAdsClient

from .base import ScriptBase, ScriptConfig, ScriptResult, ScriptStatus, ScriptType

logger = logging.getLogger(__name__)


class PerformanceMaxGeographicScript(ScriptBase):
    """Script for Performance Max geographic performance analysis and optimization."""

    def __init__(self, client: GoogleAdsClient, config: ScriptConfig):
        super().__init__(client, config)
        self.script_type = ScriptType.PERFORMANCE_MAX_GEOGRAPHIC

    def get_required_parameters(self) -> List[str]:
        """Get required parameters for geographic analysis."""
        return ["date_range", "customer_id"]

    def generate_script(self) -> str:
        """Generate Google Ads Script for geographic performance analysis."""
        date_range = self.config.parameters.get("date_range", "LAST_30_DAYS")
        target_locations = self.config.parameters.get(
            "target_locations",
            [
                {"name": "Dallas", "state": "Texas", "criterion_id": "1026201"},
                {"name": "San Antonio", "state": "Texas", "criterion_id": "1026216"},
                {"name": "Atlanta", "state": "Georgia", "criterion_id": "1015254"},
                {
                    "name": "Fayetteville",
                    "state": "North Carolina",
                    "criterion_id": "1022442",
                },
            ],
        )
        radius_analysis = self.config.parameters.get("radius_analysis", True)
        store_locations = self.config.parameters.get("store_locations", [])
        local_intent_indicators = self.config.parameters.get(
            "local_intent_indicators",
            [
                "near me",
                "nearby",
                "directions",
                "hours",
                "location",
                "store",
                "gym near",
                "fitness near",
            ],
        )

        script = f'''
function main() {{
    // Performance Max Geographic Performance Analysis Script
    // Generated on: {datetime.utcnow().isoformat()}

    var dateRange = "{date_range}";
    var targetLocations = {target_locations};
    var radiusAnalysis = {str(radius_analysis).lower()};
    var storeLocations = {store_locations};
    var localIntentIndicators = {local_intent_indicators};

    var results = {{
        geographicPerformance: [],
        radiusAnalysis: [],
        storePerformance: [],
        localIntentAnalysis: [],
        competitiveAnalysis: [],
        recommendations: []
    }};

    Logger.log("Starting Performance Max geographic analysis...");

    // Step 1: Analyze performance by geographic location
    analyzeGeographicPerformance();

    // Step 2: Analyze radius performance around store locations
    if (radiusAnalysis && storeLocations.length > 0) {{
        analyzeRadiusPerformance();
    }}

    // Step 3: Analyze store-level performance
    if (storeLocations.length > 0) {{
        analyzeStorePerformance();
    }}

    // Step 4: Analyze local intent search terms
    analyzeLocalIntentTerms();

    // Step 5: Competitive analysis by location
    analyzeCompetitivePerformance();

    // Step 6: Generate geographic recommendations
    generateGeographicRecommendations();

    // Step 7: Export geographic results
    exportGeographicResults();

    Logger.log("Geographic analysis completed.");
}}

function analyzeGeographicPerformance() {{
    // Analyze Performance Max performance by geographic location
    var query = `
        SELECT
            geographic_view.location_type,
            geographic_view.country_criterion_id,
            geographic_view.region_criterion_id,
            geographic_view.metro_criterion_id,
            campaign.id,
            campaign.name,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.conversions,
            metrics.conversions_value,
            metrics.all_conversions,
            metrics.view_through_conversions,
            segments.date
        FROM geographic_view
        WHERE campaign.advertising_channel_type = 'PERFORMANCE_MAX'
            AND campaign.status = 'ENABLED'
            AND segments.date DURING ${{dateRange}}
            AND metrics.impressions > 0
        ORDER BY metrics.cost_micros DESC
        LIMIT 2000
    `;

    var geoReport = AdsApp.report(query);
    var rows = geoReport.rows();

    var locationData = {{}};

    while (rows.hasNext()) {{
        var row = rows.next();
        var locationId = row['geographic_view.metro_criterion_id'] ||
                        row['geographic_view.region_criterion_id'] ||
                        row['geographic_view.country_criterion_id'];

        if (!locationData[locationId]) {{
            locationData[locationId] = {{
                locationId: locationId,
                locationType: row['geographic_view.location_type'],
                campaignIds: [],
                totalImpressions: 0,
                totalClicks: 0,
                totalCost: 0,
                totalConversions: 0,
                totalConversionValue: 0,
                allConversions: 0,
                viewThroughConversions: 0,
                campaigns: []
            }};
        }}

        var location = locationData[locationId];
        var campaignId = row['campaign.id'];

        if (location.campaignIds.indexOf(campaignId) === -1) {{
            location.campaignIds.push(campaignId);
        }}

        // Aggregate metrics
        location.totalImpressions += parseInt(row['metrics.impressions']);
        location.totalClicks += parseInt(row['metrics.clicks']);
        location.totalCost += parseFloat(row['metrics.cost_micros']) / 1000000;
        location.totalConversions += parseFloat(row['metrics.conversions']);
        location.totalConversionValue += parseFloat(row['metrics.conversions_value']);
        location.allConversions += parseFloat(row['metrics.all_conversions']);
        location.viewThroughConversions += parseFloat(row['metrics.view_through_conversions']);

        location.campaigns.push({{
            campaignId: campaignId,
            campaignName: row['campaign.name'],
            impressions: parseInt(row['metrics.impressions']),
            clicks: parseInt(row['metrics.clicks']),
            cost: parseFloat(row['metrics.cost_micros']) / 1000000,
            conversions: parseFloat(row['metrics.conversions']),
            conversionValue: parseFloat(row['metrics.conversions_value']),
            date: row['segments.date']
        }});
    }}

    // Calculate metrics for each location
    for (var locationId in locationData) {{
        var location = locationData[locationId];

        location.ctr = location.totalImpressions > 0 ?
            (location.totalClicks / location.totalImpressions * 100) : 0;
        location.cpc = location.totalClicks > 0 ?
            (location.totalCost / location.totalClicks) : 0;
        location.cpa = location.totalConversions > 0 ?
            (location.totalCost / location.totalConversions) : 0;
        location.roas = location.totalCost > 0 ?
            (location.totalConversionValue / location.totalCost) : 0;
        location.conversionRate = location.totalClicks > 0 ?
            (location.totalConversions / location.totalClicks * 100) : 0;

        // Match to target locations
        location.targetLocationMatch = findTargetLocationMatch(locationId);

        // Performance classification
        location.performanceCategory = classifyLocationPerformance(location);

        results.geographicPerformance.push(location);
    }}

    Logger.log("Analyzed " + Object.keys(locationData).length + " geographic locations");
}}

function findTargetLocationMatch(locationId) {{
    // Match geographic criterion ID to target locations
    for (var i = 0; i < targetLocations.length; i++) {{
        if (targetLocations[i].criterion_id === locationId.toString()) {{
            return {{
                name: targetLocations[i].name,
                state: targetLocations[i].state,
                isPriority: true
            }};
        }}
    }}

    return {{
        name: "Unknown Location",
        state: "Unknown",
        isPriority: false
    }};
}}

function classifyLocationPerformance(location) {{
    // Classify location performance based on multiple factors
    var score = 0;

    // ROAS factor (40% weight)
    if (location.roas > 4.0) score += 40;
    else if (location.roas > 2.0) score += 25;
    else if (location.roas > 1.0) score += 10;

    // Conversion rate factor (30% weight)
    if (location.conversionRate > 5.0) score += 30;
    else if (location.conversionRate > 2.0) score += 20;
    else if (location.conversionRate > 1.0) score += 10;

    // Volume factor (30% weight)
    if (location.totalConversions > 50) score += 30;
    else if (location.totalConversions > 10) score += 20;
    else if (location.totalConversions > 2) score += 10;

    if (score >= 80) return 'EXCELLENT';
    else if (score >= 60) return 'GOOD';
    else if (score >= 40) return 'FAIR';
    else return 'POOR';
}}

function analyzeRadiusPerformance() {{
    // Analyze performance by distance from store locations
    // This requires sophisticated geographic analysis

    Logger.log("Analyzing radius performance around " + storeLocations.length + " store locations");

    for (var i = 0; i < storeLocations.length; i++) {{
        var store = storeLocations[i];

        // Create radius analysis for this store
        var radiusData = {{
            storeId: store.id || i.toString(),
            storeName: store.name,
            storeAddress: store.address,
            latitude: store.latitude,
            longitude: store.longitude,
            radiusPerformance: []
        }};

        // Analyze different radius zones (e.g., 0-5 miles, 5-15 miles, 15-30 miles)
        var radiusZones = [
            {{ name: "0-5 miles", minRadius: 0, maxRadius: 5 }},
            {{ name: "5-15 miles", minRadius: 5, maxRadius: 15 }},
            {{ name: "15-30 miles", minRadius: 15, maxRadius: 30 }}
        ];

        for (var j = 0; j < radiusZones.length; j++) {{
            var zone = radiusZones[j];

            // In a full implementation, this would use geographic targeting
            // and location extensions to determine performance by radius
            var zonePerformance = {{
                zoneName: zone.name,
                minRadius: zone.minRadius,
                maxRadius: zone.maxRadius,
                estimatedImpressions: 1000 * (Math.random() + 0.5), // Simulated
                estimatedClicks: 50 * (Math.random() + 0.5),
                estimatedCost: 200 * (Math.random() + 0.5),
                estimatedConversions: 5 * (Math.random() + 0.5),
                estimatedConversionValue: 500 * (Math.random() + 0.5)
            }};

            zonePerformance.ctr = zonePerformance.estimatedImpressions > 0 ?
                (zonePerformance.estimatedClicks / zonePerformance.estimatedImpressions * 100) : 0;
            zonePerformance.cpa = zonePerformance.estimatedConversions > 0 ?
                (zonePerformance.estimatedCost / zonePerformance.estimatedConversions) : 0;
            zonePerformance.roas = zonePerformance.estimatedCost > 0 ?
                (zonePerformance.estimatedConversionValue / zonePerformance.estimatedCost) : 0;

            radiusData.radiusPerformance.push(zonePerformance);
        }}

        results.radiusAnalysis.push(radiusData);
    }}
}}

function analyzeStorePerformance() {{
    // Analyze Performance Max performance for individual store locations
    Logger.log("Analyzing performance for " + storeLocations.length + " store locations");

    for (var i = 0; i < storeLocations.length; i++) {{
        var store = storeLocations[i];

        var storePerformanceData = {{
            storeId: store.id || i.toString(),
            storeName: store.name,
            storeAddress: store.address,
            city: store.city,
            state: store.state,
            zipCode: store.zipCode,
            storeType: store.type || 'standard',
            performanceMetrics: {{}},
            localCompetition: {{}},
            recommendations: []
        }};

        // In a full implementation, this would analyze:
        // 1. Location extension performance
        // 2. Store visits conversions
        // 3. Call conversions from the store
        // 4. Driving directions requests

        // Simulated store performance data
        storePerformanceData.performanceMetrics = {{
            storeVisits: Math.floor(Math.random() * 100) + 20,
            callsFromAd: Math.floor(Math.random() * 20) + 5,
            directionsRequests: Math.floor(Math.random() * 50) + 10,
            localImpressions: Math.floor(Math.random() * 5000) + 1000,
            localClicks: Math.floor(Math.random() * 200) + 50,
            localConversions: Math.floor(Math.random() * 15) + 3,
            localCost: Math.random() * 500 + 100
        }};

        var metrics = storePerformanceData.performanceMetrics;
        metrics.localCtr = metrics.localImpressions > 0 ?
            (metrics.localClicks / metrics.localImpressions * 100) : 0;
        metrics.localCpa = metrics.localConversions > 0 ?
            (metrics.localCost / metrics.localConversions) : 0;
        metrics.storeVisitRate = metrics.localClicks > 0 ?
            (metrics.storeVisits / metrics.localClicks * 100) : 0;

        // Store performance evaluation
        storePerformanceData.performanceRating = evaluateStorePerformance(metrics);

        results.storePerformance.push(storePerformanceData);
    }}
}}

function evaluateStorePerformance(metrics) {{
    var score = 0;

    // Store visit rate (40% weight)
    if (metrics.storeVisitRate > 20) score += 40;
    else if (metrics.storeVisitRate > 10) score += 25;
    else if (metrics.storeVisitRate > 5) score += 10;

    // Local CTR (30% weight)
    if (metrics.localCtr > 3.0) score += 30;
    else if (metrics.localCtr > 1.5) score += 20;
    else if (metrics.localCtr > 0.8) score += 10;

    // Local CPA efficiency (30% weight)
    if (metrics.localCpa < 30) score += 30;
    else if (metrics.localCpa < 60) score += 20;
    else if (metrics.localCpa < 100) score += 10;

    if (score >= 80) return 'EXCELLENT';
    else if (score >= 60) return 'GOOD';
    else if (score >= 40) return 'FAIR';
    else return 'NEEDS_IMPROVEMENT';
}}

function analyzeLocalIntentTerms() {{
    // Analyze search terms with local intent in Performance Max campaigns
    var query = `
        SELECT
            search_term_view.search_term,
            campaign.id,
            campaign.name,
            ad_group.id,
            ad_group.name,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.conversions,
            metrics.conversions_value,
            segments.date
        FROM search_term_view
        WHERE campaign.advertising_channel_type = 'PERFORMANCE_MAX'
            AND campaign.status = 'ENABLED'
            AND segments.date DURING ${{dateRange}}
            AND metrics.impressions > 10
        ORDER BY metrics.cost_micros DESC
        LIMIT 2000
    `;

    var searchTermReport = AdsApp.report(query);
    var rows = searchTermReport.rows();

    while (rows.hasNext()) {{
        var row = rows.next();
        var searchTerm = row['search_term_view.search_term'].toLowerCase();

        // Check for local intent indicators
        var hasLocalIntent = false;
        var localIndicators = [];

        for (var i = 0; i < localIntentIndicators.length; i++) {{
            var indicator = localIntentIndicators[i].toLowerCase();
            if (searchTerm.includes(indicator)) {{
                hasLocalIntent = true;
                localIndicators.push(indicator);
            }}
        }}

        // Check for target location mentions
        var mentionedLocations = [];
        for (var i = 0; i < targetLocations.length; i++) {{
            var location = targetLocations[i];
            if (searchTerm.includes(location.name.toLowerCase()) ||
                searchTerm.includes(location.state.toLowerCase())) {{
                hasLocalIntent = true;
                mentionedLocations.push(location.name);
            }}
        }}

        if (hasLocalIntent) {{
            var localTermData = {{
                searchTerm: row['search_term_view.search_term'],
                campaignId: row['campaign.id'],
                campaignName: row['campaign.name'],
                localIndicators: localIndicators,
                mentionedLocations: mentionedLocations,
                impressions: parseInt(row['metrics.impressions']),
                clicks: parseInt(row['metrics.clicks']),
                cost: parseFloat(row['metrics.cost_micros']) / 1000000,
                conversions: parseFloat(row['metrics.conversions']),
                conversionValue: parseFloat(row['metrics.conversions_value']),
                date: row['segments.date']
            }};

            // Calculate local intent metrics
            localTermData.ctr = localTermData.impressions > 0 ?
                (localTermData.clicks / localTermData.impressions * 100) : 0;
            localTermData.cpa = localTermData.conversions > 0 ?
                (localTermData.cost / localTermData.conversions) : 0;
            localTermData.roas = localTermData.cost > 0 ?
                (localTermData.conversionValue / localTermData.cost) : 0;

            // Classify local intent type
            localTermData.intentType = classifyLocalIntentType(searchTerm, localIndicators);

            results.localIntentAnalysis.push(localTermData);
        }}
    }}

    Logger.log("Identified " + results.localIntentAnalysis.length + " local intent search terms");
}}

function classifyLocalIntentType(searchTerm, indicators) {{
    // Classify the type of local intent
    if (indicators.includes('near me') || indicators.includes('nearby')) {{
        return 'PROXIMITY_SEARCH';
    }} else if (indicators.includes('directions') || indicators.includes('hours')) {{
        return 'STORE_INFORMATION';
    }} else if (indicators.includes('location') || indicators.includes('store')) {{
        return 'STORE_FINDER';
    }} else {{
        return 'LOCATION_SPECIFIC';
    }}
}}

function analyzeCompetitivePerformance() {{
    // Analyze competitive landscape by location
    // This would use auction insights data in a full implementation

    Logger.log("Analyzing competitive performance by location...");

    // Simulated competitive analysis
    for (var i = 0; i < targetLocations.length; i++) {{
        var location = targetLocations[i];

        var competitiveData = {{
            locationName: location.name,
            locationState: location.state,
            competitiveMetrics: {{
                impressionShare: Math.random() * 40 + 30, // 30-70%
                overlapRate: Math.random() * 30 + 10, // 10-40%
                positionAboveRate: Math.random() * 50 + 20, // 20-70%
                competitorCount: Math.floor(Math.random() * 10) + 5 // 5-15 competitors
            }},
            recommendations: []
        }};

        // Generate competitive recommendations
        if (competitiveData.competitiveMetrics.impressionShare < 50) {{
            competitiveData.recommendations.push({{
                type: 'INCREASE_BIDS',
                message: 'Low impression share - consider increasing bids for this location'
            }});
        }}

        if (competitiveData.competitiveMetrics.positionAboveRate < 30) {{
            competitiveData.recommendations.push({{
                type: 'IMPROVE_QUALITY',
                message: 'Competitors frequently rank above - focus on ad quality improvements'
            }});
        }}

        results.competitiveAnalysis.push(competitiveData);
    }}
}}

function generateGeographicRecommendations() {{
    // Generate location-specific optimization recommendations

    // Analyze geographic performance
    var topLocations = results.geographicPerformance
        .filter(function(loc) {{ return loc.performanceCategory === 'EXCELLENT'; }})
        .sort(function(a, b) {{ return b.roas - a.roas; }})
        .slice(0, 5);

    var poorLocations = results.geographicPerformance
        .filter(function(loc) {{ return loc.performanceCategory === 'POOR'; }})
        .sort(function(a, b) {{ return b.totalCost - a.totalCost; }})
        .slice(0, 5);

    if (topLocations.length > 0) {{
        results.recommendations.push({{
            type: 'SCALE_TOP_LOCATIONS',
            priority: 'HIGH',
            title: 'Scale budget to top-performing locations',
            description: 'Increase investment in ' + topLocations.length + ' high-performing locations',
            locations: topLocations.map(function(loc) {{ return loc.targetLocationMatch.name; }}),
            potentialImpact: 'Increase overall ROAS by focusing on efficient locations'
        }});
    }}

    if (poorLocations.length > 0) {{
        results.recommendations.push({{
            type: 'OPTIMIZE_POOR_LOCATIONS',
            priority: 'MEDIUM',
            title: 'Optimize or reduce spend in underperforming locations',
            description: 'Review targeting and creative for ' + poorLocations.length + ' underperforming locations',
            locations: poorLocations.map(function(loc) {{ return loc.targetLocationMatch.name; }}),
            potentialImpact: 'Reduce wasted spend and improve efficiency'
        }});
    }}

    // Store performance recommendations
    if (results.storePerformance.length > 0) {{
        var underperformingStores = results.storePerformance.filter(function(store) {{
            return store.performanceRating === 'NEEDS_IMPROVEMENT';
        }});

        if (underperformingStores.length > 0) {{
            results.recommendations.push({{
                type: 'IMPROVE_STORE_PERFORMANCE',
                priority: 'MEDIUM',
                title: 'Improve local performance for ' + underperformingStores.length + ' stores',
                description: 'Focus on local SEO and location-specific optimizations',
                storeCount: underperformingStores.length,
                potentialImpact: 'Increase store visits and local conversions'
            }});
        }}
    }}

    // Local intent recommendations
    if (results.localIntentAnalysis.length > 0) {{
        var highValueLocalTerms = results.localIntentAnalysis.filter(function(term) {{
            return term.roas > 3.0 && term.conversions > 0;
        }});

        if (highValueLocalTerms.length > 0) {{
            results.recommendations.push({{
                type: 'ENHANCE_LOCAL_TARGETING',
                priority: 'HIGH',
                title: 'Enhance local targeting based on ' + highValueLocalTerms.length + ' high-value terms',
                description: 'Create location-specific campaigns or ad groups for high-performing local searches',
                termCount: highValueLocalTerms.length,
                potentialImpact: 'Better capture local intent and improve relevance'
            }});
        }}
    }}
}}

function exportGeographicResults() {{
    var summary = {{
        executionDate: new Date().toISOString(),
        dateRange: dateRange,
        locationsAnalyzed: results.geographicPerformance.length,
        storesAnalyzed: results.storePerformance.length,
        localIntentTerms: results.localIntentAnalysis.length,
        competitiveLocations: results.competitiveAnalysis.length,
        recommendationsGenerated: results.recommendations.length
    }};

    Logger.log("=== Geographic Performance Summary ===");
    Logger.log("Locations analyzed: " + summary.locationsAnalyzed);
    Logger.log("Stores analyzed: " + summary.storesAnalyzed);
    Logger.log("Local intent terms: " + summary.localIntentTerms);
    Logger.log("Competitive locations: " + summary.competitiveLocations);
    Logger.log("Recommendations generated: " + summary.recommendationsGenerated);

    // Export detailed geographic analysis
    Logger.log("Geographic analysis results ready for export");
}}
        '''.strip()

        return script

    def process_results(self, results: Dict[str, Any]) -> ScriptResult:
        """Process the results from geographic performance script execution."""
        status = ScriptStatus.COMPLETED.value
        errors = []
        warnings = []

        rows_processed = results.get("rows_processed", 0)
        changes_made = 0  # Geographic analysis is read-only

        if results.get("success", False):
            if rows_processed == 0:
                warnings.append("No geographic performance data found")
        else:
            status = ScriptStatus.FAILED.value
            errors.append("Geographic performance script execution failed")

        details = {
            "script_type": "performance_max_geographic",
            "locations_analyzed": results.get("details", {}).get(
                "locations_analyzed", 0
            ),
            "stores_analyzed": results.get("details", {}).get("stores_analyzed", 0),
            "local_intent_terms": results.get("details", {}).get(
                "local_intent_terms", 0
            ),
            "competitive_locations": results.get("details", {}).get(
                "competitive_locations", 0
            ),
            "radius_analysis_performed": results.get("details", {}).get(
                "radius_analysis_performed", False
            ),
            "recommendations_generated": results.get("details", {}).get(
                "recommendations_generated", 0
            ),
            "parameters_used": self.config.parameters,
            "execution_timestamp": datetime.utcnow().isoformat(),
        }

        return ScriptResult(
            status=status,
            execution_time=results.get("execution_time", 0.0),
            rows_processed=rows_processed,
            changes_made=changes_made,
            errors=errors,
            warnings=warnings,
            details=details,
        )


class PerformanceMaxBiddingOptimizationScript(ScriptBase):
    """Script for Performance Max bidding strategy optimization and monitoring."""

    def __init__(self, client: GoogleAdsClient, config: ScriptConfig):
        super().__init__(client, config)
        self.script_type = ScriptType.PERFORMANCE_MAX_BIDDING

    def get_required_parameters(self) -> List[str]:
        """Get required parameters for bidding optimization."""
        return ["date_range", "customer_id"]

    def generate_script(self) -> str:
        """Generate Google Ads Script for bidding strategy optimization."""
        date_range = self.config.parameters.get("date_range", "LAST_30_DAYS")
        target_roas_threshold = self.config.parameters.get("target_roas_threshold", 3.0)
        target_cpa_threshold = self.config.parameters.get("target_cpa_threshold", 50.0)
        min_conversions_for_analysis = self.config.parameters.get(
            "min_conversions_for_analysis", 5
        )
        performance_lookback_days = self.config.parameters.get(
            "performance_lookback_days", 30
        )

        script = f'''
function main() {{
    // Performance Max Bidding Strategy Optimization Script
    // Generated on: {datetime.utcnow().isoformat()}

    var dateRange = "{date_range}";
    var targetRoasThreshold = {target_roas_threshold};
    var targetCpaThreshold = {target_cpa_threshold};
    var minConversionsForAnalysis = {min_conversions_for_analysis};
    var performanceLookbackDays = {performance_lookback_days};

    var results = {{
        biddingStrategyPerformance: [],
        campaignBiddingAnalysis: [],
        targetVsActualAnalysis: [],
        optimizationOpportunities: [],
        smartBiddingInsights: [],
        recommendations: []
    }};

    Logger.log("Starting Performance Max bidding strategy optimization...");

    // Step 1: Analyze current bidding strategy performance
    analyzeBiddingStrategyPerformance();

    // Step 2: Campaign-level bidding analysis
    analyzeCampaignBidding();

    // Step 3: Target vs Actual performance analysis
    analyzeTargetVsActual();

    // Step 4: Identify optimization opportunities
    identifyOptimizationOpportunities();

    // Step 5: Extract Smart Bidding insights
    extractSmartBiddingInsights();

    // Step 6: Generate bidding recommendations
    generateBiddingRecommendations();

    // Step 7: Export bidding optimization results
    exportBiddingResults();

    Logger.log("Bidding strategy optimization completed.");
}}

function analyzeBiddingStrategyPerformance() {{
    // Analyze Performance Max bidding strategies
    var query = `
        SELECT
            bidding_strategy.id,
            bidding_strategy.name,
            bidding_strategy.type,
            bidding_strategy.target_roas,
            bidding_strategy.target_cpa_micros,
            bidding_strategy.maximize_conversion_value.target_roas,
            bidding_strategy.maximize_conversions.target_cpa_micros,
            bidding_strategy.target_roas.target_roas,
            bidding_strategy.target_cpa.target_cpa_micros,
            campaign.id,
            campaign.name,
            metrics.cost_micros,
            metrics.impressions,
            metrics.clicks,
            metrics.conversions,
            metrics.conversions_value,
            metrics.all_conversions,
            metrics.all_conversions_value,
            segments.date
        FROM campaign
        WHERE campaign.advertising_channel_type = 'PERFORMANCE_MAX'
            AND campaign.status = 'ENABLED'
            AND segments.date DURING ${{dateRange}}
            AND metrics.conversions >= ${{minConversionsForAnalysis}}
        ORDER BY metrics.cost_micros DESC
    `;

    var biddingReport = AdsApp.report(query);
    var rows = biddingReport.rows();

    var strategyData = {{}};

    while (rows.hasNext()) {{
        var row = rows.next();
        var strategyId = row['bidding_strategy.id'];

        if (!strategyData[strategyId]) {{
            strategyData[strategyId] = {{
                strategyId: strategyId,
                strategyName: row['bidding_strategy.name'],
                strategyType: row['bidding_strategy.type'],
                targetRoas: parseFloat(row['bidding_strategy.target_roas'] ||
                           row['bidding_strategy.maximize_conversion_value.target_roas'] ||
                           row['bidding_strategy.target_roas.target_roas'] || 0),
                targetCpa: parseFloat(row['bidding_strategy.target_cpa_micros'] ||
                          row['bidding_strategy.maximize_conversions.target_cpa_micros'] ||
                          row['bidding_strategy.target_cpa.target_cpa_micros'] || 0) / 1000000,
                campaigns: [],
                totalCost: 0,
                totalImpressions: 0,
                totalClicks: 0,
                totalConversions: 0,
                totalConversionValue: 0,
                allConversions: 0,
                allConversionsValue: 0
            }};
        }}

        var strategy = strategyData[strategyId];

        // Add campaign data
        strategy.campaigns.push({{
            campaignId: row['campaign.id'],
            campaignName: row['campaign.name'],
            cost: parseFloat(row['metrics.cost_micros']) / 1000000,
            impressions: parseInt(row['metrics.impressions']),
            clicks: parseInt(row['metrics.clicks']),
            conversions: parseFloat(row['metrics.conversions']),
            conversionValue: parseFloat(row['metrics.conversions_value']),
            date: row['segments.date']
        }});

        // Aggregate metrics
        strategy.totalCost += parseFloat(row['metrics.cost_micros']) / 1000000;
        strategy.totalImpressions += parseInt(row['metrics.impressions']);
        strategy.totalClicks += parseInt(row['metrics.clicks']);
        strategy.totalConversions += parseFloat(row['metrics.conversions']);
        strategy.totalConversionValue += parseFloat(row['metrics.conversions_value']);
        strategy.allConversions += parseFloat(row['metrics.all_conversions']);
        strategy.allConversionsValue += parseFloat(row['metrics.all_conversions_value']);
    }}

    // Calculate performance metrics for each strategy
    for (var strategyId in strategyData) {{
        var strategy = strategyData[strategyId];

        strategy.actualCpa = strategy.totalConversions > 0 ?
            (strategy.totalCost / strategy.totalConversions) : 0;
        strategy.actualRoas = strategy.totalCost > 0 ?
            (strategy.totalConversionValue / strategy.totalCost) : 0;
        strategy.ctr = strategy.totalImpressions > 0 ?
            (strategy.totalClicks / strategy.totalImpressions * 100) : 0;
        strategy.conversionRate = strategy.totalClicks > 0 ?
            (strategy.totalConversions / strategy.totalClicks * 100) : 0;

        // Performance vs targets
        if (strategy.targetRoas > 0) {{
            strategy.roasPerformanceRatio = strategy.actualRoas / strategy.targetRoas;
            strategy.roasTargetMet = strategy.roasPerformanceRatio >= 0.9;
        }}

        if (strategy.targetCpa > 0) {{
            strategy.cpaPerformanceRatio = strategy.targetCpa / strategy.actualCpa;
            strategy.cpaTargetMet = strategy.cpaPerformanceRatio >= 0.9;
        }}

        // Strategy effectiveness classification
        strategy.effectiveness = classifyBiddingEffectiveness(strategy);

        results.biddingStrategyPerformance.push(strategy);
    }}

    Logger.log("Analyzed " + Object.keys(strategyData).length + " bidding strategies");
}}

function classifyBiddingEffectiveness(strategy) {{
    var score = 0;

    // Target achievement (50% weight)
    if (strategy.roasTargetMet && strategy.cpaTargetMet) score += 50;
    else if (strategy.roasTargetMet || strategy.cpaTargetMet) score += 25;

    // Volume performance (25% weight)
    if (strategy.totalConversions > 50) score += 25;
    else if (strategy.totalConversions > 20) score += 15;
    else if (strategy.totalConversions > 10) score += 10;

    // Efficiency performance (25% weight)
    if (strategy.actualRoas > 4.0) score += 25;
    else if (strategy.actualRoas > 2.5) score += 15;
    else if (strategy.actualRoas > 1.5) score += 10;

    if (score >= 80) return 'EXCELLENT';
    else if (score >= 60) return 'GOOD';
    else if (score >= 40) return 'FAIR';
    else return 'NEEDS_OPTIMIZATION';
}}

function analyzeCampaignBidding() {{
    // Analyze bidding performance at campaign level
    var query = `
        SELECT
            campaign.id,
            campaign.name,
            campaign.bidding_strategy_type,
            campaign.target_roas,
            campaign.target_cpa_micros,
            campaign.maximize_conversion_value.target_roas,
            campaign.maximize_conversions.target_cpa_micros,
            metrics.cost_micros,
            metrics.impressions,
            metrics.clicks,
            metrics.conversions,
            metrics.conversions_value,
            metrics.search_impression_share,
            metrics.search_budget_lost_impression_share,
            metrics.search_rank_lost_impression_share,
            segments.date
        FROM campaign
        WHERE campaign.advertising_channel_type = 'PERFORMANCE_MAX'
            AND campaign.status = 'ENABLED'
            AND segments.date DURING ${{dateRange}}
            AND metrics.cost_micros > 0
        ORDER BY metrics.cost_micros DESC
    `;

    var campaignReport = AdsApp.report(query);
    var rows = campaignReport.rows();

    while (rows.hasNext()) {{
        var row = rows.next();

        var campaignData = {{
            campaignId: row['campaign.id'],
            campaignName: row['campaign.name'],
            biddingStrategyType: row['campaign.bidding_strategy_type'],
            targetRoas: parseFloat(row['campaign.target_roas'] ||
                       row['campaign.maximize_conversion_value.target_roas'] || 0),
            targetCpa: parseFloat(row['campaign.target_cpa_micros'] ||
                      row['campaign.maximize_conversions.target_cpa_micros'] || 0) / 1000000,
            cost: parseFloat(row['metrics.cost_micros']) / 1000000,
            impressions: parseInt(row['metrics.impressions']),
            clicks: parseInt(row['metrics.clicks']),
            conversions: parseFloat(row['metrics.conversions']),
            conversionValue: parseFloat(row['metrics.conversions_value']),
            impressionShare: parseFloat(row['metrics.search_impression_share'] || 0),
            budgetLostIS: parseFloat(row['metrics.search_budget_lost_impression_share'] || 0),
            rankLostIS: parseFloat(row['metrics.search_rank_lost_impression_share'] || 0),
            date: row['segments.date']
        }};

        // Calculate actual metrics
        campaignData.actualCpa = campaignData.conversions > 0 ?
            (campaignData.cost / campaignData.conversions) : 0;
        campaignData.actualRoas = campaignData.cost > 0 ?
            (campaignData.conversionValue / campaignData.cost) : 0;
        campaignData.ctr = campaignData.impressions > 0 ?
            (campaignData.clicks / campaignData.impressions * 100) : 0;
        campaignData.conversionRate = campaignData.clicks > 0 ?
            (campaignData.conversions / campaignData.clicks * 100) : 0;

        // Bidding opportunity analysis
        campaignData.biddingOpportunities = [];

        if (campaignData.budgetLostIS > 10) {{
            campaignData.biddingOpportunities.push({{
                type: 'BUDGET_CONSTRAINT',
                impact: 'HIGH',
                description: 'Lost ' + campaignData.budgetLostIS.toFixed(1) + '% impression share due to budget',
                recommendation: 'Consider increasing daily budget'
            }});
        }}

        if (campaignData.rankLostIS > 15) {{
            campaignData.biddingOpportunities.push({{
                type: 'BID_TOO_LOW',
                impact: 'HIGH',
                description: 'Lost ' + campaignData.rankLostIS.toFixed(1) + '% impression share due to rank',
                recommendation: 'Consider increasing target ROAS or decreasing target CPA'
            }});
        }}

        // Performance vs targets
        if (campaignData.targetRoas > 0) {{
            campaignData.roasPerformance = analyzeRoasPerformance(
                campaignData.actualRoas,
                campaignData.targetRoas
            );
        }}

        if (campaignData.targetCpa > 0) {{
            campaignData.cpaPerformance = analyzeCpaPerformance(
                campaignData.actualCpa,
                campaignData.targetCpa
            );
        }}

        results.campaignBiddingAnalysis.push(campaignData);
    }}
}}

function analyzeRoasPerformance(actual, target) {{
    var ratio = actual / target;
    var status, recommendation;

    if (ratio >= 1.1) {{
        status = 'EXCEEDING_TARGET';
        recommendation = 'Consider increasing target ROAS to capture more volume';
    }} else if (ratio >= 0.9) {{
        status = 'MEETING_TARGET';
        recommendation = 'Performance is on target - monitor and maintain';
    }} else if (ratio >= 0.7) {{
        status = 'BELOW_TARGET';
        recommendation = 'Consider decreasing target ROAS or improving conversion value';
    }} else {{
        status = 'SIGNIFICANTLY_BELOW';
        recommendation = 'Review targeting, assets, and bidding strategy urgently';
    }}

    return {{
        actualRoas: actual,
        targetRoas: target,
        performanceRatio: ratio,
        status: status,
        recommendation: recommendation
    }};
}}

function analyzeCpaPerformance(actual, target) {{
    var ratio = target / actual; // Higher ratio is better for CPA
    var status, recommendation;

    if (ratio >= 1.1) {{
        status = 'BETTER_THAN_TARGET';
        recommendation = 'Consider decreasing target CPA to capture more volume';
    }} else if (ratio >= 0.9) {{
        status = 'MEETING_TARGET';
        recommendation = 'Performance is on target - monitor and maintain';
    }} else if (ratio >= 0.7) {{
        status = 'ABOVE_TARGET';
        recommendation = 'Consider increasing target CPA or improving conversion rate';
    }} else {{
        status = 'SIGNIFICANTLY_ABOVE';
        recommendation = 'Review targeting, assets, and bidding strategy urgently';
    }}

    return {{
        actualCpa: actual,
        targetCpa: target,
        performanceRatio: ratio,
        status: status,
        recommendation: recommendation
    }};
}}

function analyzeTargetVsActual() {{
    // Comprehensive analysis of target vs actual performance across all campaigns
    var summary = {{
        totalCampaigns: results.campaignBiddingAnalysis.length,
        roasAnalysis: {{
            exceedingTarget: 0,
            meetingTarget: 0,
            belowTarget: 0,
            significantlyBelow: 0
        }},
        cpaAnalysis: {{
            betterThanTarget: 0,
            meetingTarget: 0,
            aboveTarget: 0,
            significantlyAbove: 0
        }},
        overallPerformance: {{}}
    }};

    var totalCost = 0;
    var totalConversions = 0;
    var totalConversionValue = 0;

    for (var i = 0; i < results.campaignBiddingAnalysis.length; i++) {{
        var campaign = results.campaignBiddingAnalysis[i];

        totalCost += campaign.cost;
        totalConversions += campaign.conversions;
        totalConversionValue += campaign.conversionValue;

        // ROAS analysis
        if (campaign.roasPerformance) {{
            switch (campaign.roasPerformance.status) {{
                case 'EXCEEDING_TARGET':
                    summary.roasAnalysis.exceedingTarget++;
                    break;
                case 'MEETING_TARGET':
                    summary.roasAnalysis.meetingTarget++;
                    break;
                case 'BELOW_TARGET':
                    summary.roasAnalysis.belowTarget++;
                    break;
                case 'SIGNIFICANTLY_BELOW':
                    summary.roasAnalysis.significantlyBelow++;
                    break;
            }}
        }}

        // CPA analysis
        if (campaign.cpaPerformance) {{
            switch (campaign.cpaPerformance.status) {{
                case 'BETTER_THAN_TARGET':
                    summary.cpaAnalysis.betterThanTarget++;
                    break;
                case 'MEETING_TARGET':
                    summary.cpaAnalysis.meetingTarget++;
                    break;
                case 'ABOVE_TARGET':
                    summary.cpaAnalysis.aboveTarget++;
                    break;
                case 'SIGNIFICANTLY_ABOVE':
                    summary.cpaAnalysis.significantlyAbove++;
                    break;
            }}
        }}
    }}

    // Calculate overall metrics
    summary.overallPerformance = {{
        totalSpend: totalCost,
        totalConversions: totalConversions,
        totalConversionValue: totalConversionValue,
        averageCpa: totalConversions > 0 ? (totalCost / totalConversions) : 0,
        averageRoas: totalCost > 0 ? (totalConversionValue / totalCost) : 0
    }};

    results.targetVsActualAnalysis = summary;
}}

function identifyOptimizationOpportunities() {{
    // Identify specific optimization opportunities

    for (var i = 0; i < results.campaignBiddingAnalysis.length; i++) {{
        var campaign = results.campaignBiddingAnalysis[i];

        // High impression share loss opportunities
        if (campaign.budgetLostIS > 20 || campaign.rankLostIS > 20) {{
            results.optimizationOpportunities.push({{
                type: 'IMPRESSION_SHARE',
                campaignId: campaign.campaignId,
                campaignName: campaign.campaignName,
                opportunity: 'High impression share loss',
                budgetLost: campaign.budgetLostIS,
                rankLost: campaign.rankLostIS,
                potentialImpact: 'Increase reach and conversions',
                recommendation: generateImpressionShareRecommendation(campaign)
            }});
        }}

        // Target adjustment opportunities
        if (campaign.roasPerformance &&
            (campaign.roasPerformance.status === 'EXCEEDING_TARGET' ||
             campaign.roasPerformance.status === 'SIGNIFICANTLY_BELOW')) {{
            results.optimizationOpportunities.push({{
                type: 'TARGET_ADJUSTMENT',
                campaignId: campaign.campaignId,
                campaignName: campaign.campaignName,
                opportunity: 'ROAS target adjustment needed',
                currentRoas: campaign.actualRoas,
                targetRoas: campaign.targetRoas,
                status: campaign.roasPerformance.status,
                recommendation: campaign.roasPerformance.recommendation
            }});
        }}

        // CPA optimization opportunities
        if (campaign.cpaPerformance &&
            (campaign.cpaPerformance.status === 'BETTER_THAN_TARGET' ||
             campaign.cpaPerformance.status === 'SIGNIFICANTLY_ABOVE')) {{
            results.optimizationOpportunities.push({{
                type: 'CPA_OPTIMIZATION',
                campaignId: campaign.campaignId,
                campaignName: campaign.campaignName,
                opportunity: 'CPA target adjustment needed',
                currentCpa: campaign.actualCpa,
                targetCpa: campaign.targetCpa,
                status: campaign.cpaPerformance.status,
                recommendation: campaign.cpaPerformance.recommendation
            }});
        }}
    }}
}}

function generateImpressionShareRecommendation(campaign) {{
    if (campaign.budgetLostIS > campaign.rankLostIS) {{
        return 'Primary issue is budget constraint - increase daily budget by ' +
               Math.round(campaign.budgetLostIS) + '%';
    }} else {{
        return 'Primary issue is bid/rank - consider adjusting target bids or improving quality score';
    }}
}}

function extractSmartBiddingInsights() {{
    // Extract insights about Smart Bidding performance
    var insights = {{
        strategyDistribution: {{}},
        performanceByStrategy: {{}},
        learningPeriodAnalysis: {{}},
        volumeVsEfficiencyTrend: {{}}
    }};

    // Strategy distribution
    for (var i = 0; i < results.biddingStrategyPerformance.length; i++) {{
        var strategy = results.biddingStrategyPerformance[i];
        var type = strategy.strategyType;

        if (!insights.strategyDistribution[type]) {{
            insights.strategyDistribution[type] = 0;
        }}
        insights.strategyDistribution[type]++;

        // Performance by strategy type
        if (!insights.performanceByStrategy[type]) {{
            insights.performanceByStrategy[type] = {{
                count: 0,
                totalCost: 0,
                totalConversions: 0,
                totalConversionValue: 0,
                averageRoas: 0,
                averageCpa: 0
            }};
        }}

        var perf = insights.performanceByStrategy[type];
        perf.count++;
        perf.totalCost += strategy.totalCost;
        perf.totalConversions += strategy.totalConversions;
        perf.totalConversionValue += strategy.totalConversionValue;
    }}

    // Calculate averages
    for (var type in insights.performanceByStrategy) {{
        var perf = insights.performanceByStrategy[type];
        perf.averageRoas = perf.totalCost > 0 ? (perf.totalConversionValue / perf.totalCost) : 0;
        perf.averageCpa = perf.totalConversions > 0 ? (perf.totalCost / perf.totalConversions) : 0;
    }}

    results.smartBiddingInsights = insights;
}}

function generateBiddingRecommendations() {{
    // Generate specific bidding optimization recommendations

    // Strategy-level recommendations
    for (var i = 0; i < results.biddingStrategyPerformance.length; i++) {{
        var strategy = results.biddingStrategyPerformance[i];

        if (strategy.effectiveness === 'NEEDS_OPTIMIZATION') {{
            results.recommendations.push({{
                type: 'STRATEGY_OPTIMIZATION',
                priority: 'HIGH',
                strategyId: strategy.strategyId,
                strategyName: strategy.strategyName,
                issue: 'Bidding strategy underperforming',
                currentEffectiveness: strategy.effectiveness,
                recommendation: generateStrategyRecommendation(strategy),
                potentialImpact: 'Improve campaign efficiency and performance'
            }});
        }}
    }}

    // Impression share opportunities
    var highImpactOpportunities = results.optimizationOpportunities.filter(function(opp) {{
        return opp.type === 'IMPRESSION_SHARE' &&
               (opp.budgetLost > 15 || opp.rankLost > 15);
    }});

    if (highImpactOpportunities.length > 0) {{
        results.recommendations.push({{
            type: 'IMPRESSION_SHARE_OPTIMIZATION',
            priority: 'HIGH',
            title: 'Address impression share losses in ' + highImpactOpportunities.length + ' campaigns',
            opportunities: highImpactOpportunities.length,
            averageBudgetLost: calculateAverage(highImpactOpportunities, 'budgetLost'),
            averageRankLost: calculateAverage(highImpactOpportunities, 'rankLost'),
            recommendation: 'Increase budgets and optimize bids to capture lost impression share',
            potentialImpact: 'Increase conversions by 15-30% through improved reach'
        }});
    }}

    // Target adjustment recommendations
    var targetOpportunities = results.optimizationOpportunities.filter(function(opp) {{
        return opp.type === 'TARGET_ADJUSTMENT';
    }});

    if (targetOpportunities.length > 0) {{
        results.recommendations.push({{
            type: 'TARGET_ADJUSTMENT',
            priority: 'MEDIUM',
            title: 'Adjust targets for ' + targetOpportunities.length + ' campaigns',
            opportunities: targetOpportunities.length,
            recommendation: 'Review and adjust ROAS/CPA targets based on actual performance',
            potentialImpact: 'Optimize volume vs efficiency balance'
        }});
    }}

    // Overall account recommendations
    var summary = results.targetVsActualAnalysis;
    if (summary.roasAnalysis.significantlyBelow > 0 || summary.cpaAnalysis.significantlyAbove > 0) {{
        results.recommendations.push({{
            type: 'ACCOUNT_OPTIMIZATION',
            priority: 'HIGH',
            title: 'Account-level bidding optimization needed',
            underperformingCampaigns: summary.roasAnalysis.significantlyBelow + summary.cpaAnalysis.significantlyAbove,
            recommendation: 'Comprehensive review of targeting, assets, and bidding strategies',
            potentialImpact: 'Improve overall account performance and efficiency'
        }});
    }}
}}

function generateStrategyRecommendation(strategy) {{
    if (strategy.actualRoas < 1.5 && strategy.actualCpa > 100) {{
        return 'Consider switching to maximize conversions or target CPA strategy';
    }} else if (!strategy.roasTargetMet && !strategy.cpaTargetMet) {{
        return 'Review target settings and consider more conservative targets';
    }} else if (strategy.totalConversions < 15) {{
        return 'Allow more time for learning period or increase budget';
    }} else {{
        return 'Review campaign assets, targeting, and landing page quality';
    }}
}}

function calculateAverage(array, property) {{
    if (array.length === 0) return 0;
    var sum = array.reduce(function(total, item) {{ return total + (item[property] || 0); }}, 0);
    return sum / array.length;
}}

function exportBiddingResults() {{
    var summary = {{
        executionDate: new Date().toISOString(),
        dateRange: dateRange,
        biddingStrategiesAnalyzed: results.biddingStrategyPerformance.length,
        campaignsAnalyzed: results.campaignBiddingAnalysis.length,
        optimizationOpportunities: results.optimizationOpportunities.length,
        recommendationsGenerated: results.recommendations.length,
        overallPerformance: results.targetVsActualAnalysis.overallPerformance
    }};

    Logger.log("=== Bidding Strategy Optimization Summary ===");
    Logger.log("Strategies analyzed: " + summary.biddingStrategiesAnalyzed);
    Logger.log("Campaigns analyzed: " + summary.campaignsAnalyzed);
    Logger.log("Optimization opportunities: " + summary.optimizationOpportunities);
    Logger.log("Recommendations generated: " + summary.recommendationsGenerated);
    Logger.log("Average ROAS: " + summary.overallPerformance.averageRoas.toFixed(2));
    Logger.log("Average CPA: $" + summary.overallPerformance.averageCpa.toFixed(2));

    // Export detailed bidding analysis
    Logger.log("Bidding optimization results ready for export");
}}
        '''.strip()

        return script

    def process_results(self, results: Dict[str, Any]) -> ScriptResult:
        """Process the results from bidding optimization script execution."""
        status = ScriptStatus.COMPLETED.value
        errors = []
        warnings = []

        rows_processed = results.get("rows_processed", 0)
        changes_made = 0  # Bidding analysis is read-only

        if results.get("success", False):
            if rows_processed == 0:
                warnings.append("No bidding strategy data found for analysis")
        else:
            status = ScriptStatus.FAILED.value
            errors.append("Bidding optimization script execution failed")

        details = {
            "script_type": "performance_max_bidding_optimization",
            "strategies_analyzed": results.get("details", {}).get(
                "strategies_analyzed", 0
            ),
            "campaigns_analyzed": results.get("details", {}).get(
                "campaigns_analyzed", 0
            ),
            "optimization_opportunities": results.get("details", {}).get(
                "optimization_opportunities", 0
            ),
            "smart_bidding_insights": results.get("details", {}).get(
                "smart_bidding_insights", {}
            ),
            "recommendations_generated": results.get("details", {}).get(
                "recommendations_generated", 0
            ),
            "parameters_used": self.config.parameters,
            "execution_timestamp": datetime.utcnow().isoformat(),
        }

        return ScriptResult(
            status=status,
            execution_time=results.get("execution_time", 0.0),
            rows_processed=rows_processed,
            changes_made=changes_made,
            errors=errors,
            warnings=warnings,
            details=details,
        )
