"""Google Ads Scripts for Performance Max campaign optimization.

This module implements Google Ads Scripts for automated Performance Max campaign monitoring,
optimization, and integration with location-based businesses, focusing on bidding strategy
management and asset performance tracking.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List

from paidsearchnav.platforms.google.client import GoogleAdsClient

from .base import ScriptBase, ScriptConfig, ScriptResult, ScriptStatus, ScriptType

logger = logging.getLogger(__name__)


class PerformanceMaxMonitoringScript(ScriptBase):
    """Script for Performance Max campaign monitoring and performance analysis."""

    def __init__(self, client: GoogleAdsClient, config: ScriptConfig):
        super().__init__(client, config)
        self.script_type = ScriptType.PERFORMANCE_MAX_MONITORING

    def get_required_parameters(self) -> List[str]:
        """Get required parameters for Performance Max monitoring."""
        return ["date_range", "customer_id"]

    def generate_script(self) -> str:
        """Generate Google Ads Script for Performance Max monitoring."""
        date_range = self.config.parameters.get("date_range", "LAST_30_DAYS")
        min_spend = self.config.parameters.get("min_spend", 50.0)
        target_roas_threshold = self.config.parameters.get("target_roas_threshold", 3.0)
        include_asset_data = self.config.parameters.get("include_asset_data", True)
        include_geographic_data = self.config.parameters.get(
            "include_geographic_data", True
        )
        locations_of_interest = self.config.parameters.get(
            "locations_of_interest",
            [
                "Dallas",
                "San Antonio",
                "Atlanta",
                "Fayetteville",
                "Texas",
                "Georgia",
                "North Carolina",
            ],
        )

        script = f'''
function main() {{
    // Performance Max Campaign Monitoring Script
    // Generated on: {datetime.utcnow().isoformat()}
    // Monitors Performance Max campaigns for optimization opportunities

    var dateRange = "{date_range}";
    var minSpend = {min_spend};
    var targetRoasThreshold = {target_roas_threshold};
    var includeAssetData = {str(include_asset_data).lower()};
    var includeGeoData = {str(include_geographic_data).lower()};
    var locationsOfInterest = {locations_of_interest};

    // Initialize tracking variables
    var results = {{
        campaignPerformance: [],
        assetGroupPerformance: [],
        searchTermInsights: [],
        geographicPerformance: [],
        biddingStrategyAnalysis: [],
        recommendations: []
    }};

    // Step 1: Analyze Performance Max Campaign Performance
    Logger.log("Starting Performance Max campaign analysis...");
    analyzePerformanceMaxCampaigns();

    // Step 2: Analyze Asset Group Performance
    if (includeAssetData) {{
        Logger.log("Analyzing asset group performance...");
        analyzeAssetGroupPerformance();
    }}

    // Step 3: Extract Search Term Insights
    Logger.log("Extracting search term insights...");
    analyzeSearchTermInsights();

    // Step 4: Geographic Performance Analysis
    if (includeGeoData) {{
        Logger.log("Analyzing geographic performance...");
        analyzeGeographicPerformance();
    }}

    // Step 5: Bidding Strategy Analysis
    Logger.log("Analyzing bidding strategies...");
    analyzeBiddingStrategies();

    // Step 6: Generate Optimization Recommendations
    generateOptimizationRecommendations();

    // Step 7: Export results to Google Sheets and/or Cloud Storage
    exportResults();

    Logger.log("Performance Max monitoring completed. Processed " +
               results.campaignPerformance.length + " campaigns.");
}}

function analyzePerformanceMaxCampaigns() {{
    var query = `
        SELECT
            campaign.id,
            campaign.name,
            campaign.advertising_channel_type,
            campaign.status,
            campaign.bidding_strategy_type,
            campaign.target_roas,
            campaign.target_cpa_micros,
            metrics.cost_micros,
            metrics.impressions,
            metrics.clicks,
            metrics.conversions,
            metrics.conversions_value,
            metrics.all_conversions,
            metrics.all_conversions_value,
            metrics.view_through_conversions,
            segments.date
        FROM campaign
        WHERE campaign.advertising_channel_type = 'PERFORMANCE_MAX'
            AND campaign.status = 'ENABLED'
            AND segments.date DURING ${{dateRange}}
            AND metrics.cost_micros >= ${{minSpend * 1000000}}
        ORDER BY metrics.cost_micros DESC
    `;

    var campaignReport = AdsApp.report(query);
    var rows = campaignReport.rows();

    while (rows.hasNext()) {{
        var row = rows.next();
        var campaignData = {{
            campaignId: row['campaign.id'],
            campaignName: row['campaign.name'],
            status: row['campaign.status'],
            biddingStrategy: row['campaign.bidding_strategy_type'],
            targetRoas: parseFloat(row['campaign.target_roas'] || 0),
            targetCpa: parseFloat(row['campaign.target_cpa_micros'] || 0) / 1000000,
            cost: parseFloat(row['metrics.cost_micros']) / 1000000,
            impressions: parseInt(row['metrics.impressions']),
            clicks: parseInt(row['metrics.clicks']),
            conversions: parseFloat(row['metrics.conversions']),
            conversionValue: parseFloat(row['metrics.conversions_value']),
            allConversions: parseFloat(row['metrics.all_conversions']),
            allConversionsValue: parseFloat(row['metrics.all_conversions_value']),
            viewThroughConversions: parseFloat(row['metrics.view_through_conversions']),
            date: row['segments.date']
        }};

        // Calculate performance metrics
        campaignData.ctr = campaignData.impressions > 0 ?
            (campaignData.clicks / campaignData.impressions * 100) : 0;
        campaignData.cpc = campaignData.clicks > 0 ?
            (campaignData.cost / campaignData.clicks) : 0;
        campaignData.cpa = campaignData.conversions > 0 ?
            (campaignData.cost / campaignData.conversions) : 0;
        campaignData.roas = campaignData.cost > 0 ?
            (campaignData.conversionValue / campaignData.cost) : 0;
        campaignData.conversionRate = campaignData.clicks > 0 ?
            (campaignData.conversions / campaignData.clicks * 100) : 0;

        // Flag performance issues
        campaignData.performanceFlags = [];
        if (campaignData.roas < targetRoasThreshold) {{
            campaignData.performanceFlags.push('LOW_ROAS');
        }}
        if (campaignData.ctr < 1.0) {{
            campaignData.performanceFlags.push('LOW_CTR');
        }}
        if (campaignData.conversionRate < 2.0) {{
            campaignData.performanceFlags.push('LOW_CONVERSION_RATE');
        }}

        results.campaignPerformance.push(campaignData);
    }}
}}

function analyzeAssetGroupPerformance() {{
    if (!includeAssetData) return;

    var query = `
        SELECT
            asset_group.id,
            asset_group.name,
            asset_group.campaign,
            asset_group.status,
            metrics.cost_micros,
            metrics.impressions,
            metrics.clicks,
            metrics.conversions,
            metrics.conversions_value,
            segments.date
        FROM asset_group
        WHERE asset_group.campaign IN (
            SELECT campaign.id
            FROM campaign
            WHERE campaign.advertising_channel_type = 'PERFORMANCE_MAX'
                AND campaign.status = 'ENABLED'
        )
        AND segments.date DURING ${{dateRange}}
        AND metrics.cost_micros > 0
        ORDER BY metrics.cost_micros DESC
    `;

    var assetGroupReport = AdsApp.report(query);
    var rows = assetGroupReport.rows();

    while (rows.hasNext()) {{
        var row = rows.next();
        var assetGroupData = {{
            assetGroupId: row['asset_group.id'],
            assetGroupName: row['asset_group.name'],
            campaignId: row['asset_group.campaign'],
            status: row['asset_group.status'],
            cost: parseFloat(row['metrics.cost_micros']) / 1000000,
            impressions: parseInt(row['metrics.impressions']),
            clicks: parseInt(row['metrics.clicks']),
            conversions: parseFloat(row['metrics.conversions']),
            conversionValue: parseFloat(row['metrics.conversions_value']),
            date: row['segments.date']
        }};

        // Calculate asset group metrics
        assetGroupData.ctr = assetGroupData.impressions > 0 ?
            (assetGroupData.clicks / assetGroupData.impressions * 100) : 0;
        assetGroupData.cpc = assetGroupData.clicks > 0 ?
            (assetGroupData.cost / assetGroupData.clicks) : 0;
        assetGroupData.cpa = assetGroupData.conversions > 0 ?
            (assetGroupData.cost / assetGroupData.conversions) : 0;
        assetGroupData.roas = assetGroupData.cost > 0 ?
            (assetGroupData.conversionValue / assetGroupData.cost) : 0;

        results.assetGroupPerformance.push(assetGroupData);
    }}
}}

function analyzeSearchTermInsights() {{
    var query = `
        SELECT
            search_term_view.search_term,
            campaign.id,
            campaign.name,
            ad_group.id,
            ad_group.name,
            search_term_view.status,
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
            AND metrics.impressions > 0
        ORDER BY metrics.cost_micros DESC
        LIMIT 5000
    `;

    var searchTermReport = AdsApp.report(query);
    var rows = searchTermReport.rows();

    while (rows.hasNext()) {{
        var row = rows.next();
        var searchTerm = row['search_term_view.search_term'].toLowerCase();

        var searchTermData = {{
            searchTerm: row['search_term_view.search_term'],
            campaignId: row['campaign.id'],
            campaignName: row['campaign.name'],
            adGroupId: row['ad_group.id'],
            adGroupName: row['ad_group.name'],
            status: row['search_term_view.status'],
            impressions: parseInt(row['metrics.impressions']),
            clicks: parseInt(row['metrics.clicks']),
            cost: parseFloat(row['metrics.cost_micros']) / 1000000,
            conversions: parseFloat(row['metrics.conversions']),
            conversionValue: parseFloat(row['metrics.conversions_value']),
            date: row['segments.date']
        }};

        // Calculate search term metrics
        searchTermData.ctr = searchTermData.impressions > 0 ?
            (searchTermData.clicks / searchTermData.impressions * 100) : 0;
        searchTermData.cpc = searchTermData.clicks > 0 ?
            (searchTermData.cost / searchTermData.clicks) : 0;
        searchTermData.cpa = searchTermData.conversions > 0 ?
            (searchTermData.cost / searchTermData.conversions) : 0;
        searchTermData.roas = searchTermData.cost > 0 ?
            (searchTermData.conversionValue / searchTermData.cost) : 0;

        // Classify search term intent
        searchTermData.localIntent = false;
        searchTermData.brandIntent = false;
        searchTermData.commercialIntent = false;

        // Check for local intent
        var localIndicators = ['near me', 'nearby', 'close to', 'local', 'directions', 'hours'];
        for (var i = 0; i < localIndicators.length; i++) {{
            if (searchTerm.includes(localIndicators[i])) {{
                searchTermData.localIntent = true;
                break;
            }}
        }}

        // Check for location-specific terms
        for (var i = 0; i < locationsOfInterest.length; i++) {{
            if (searchTerm.includes(locationsOfInterest[i].toLowerCase())) {{
                searchTermData.localIntent = true;
                searchTermData.specificLocation = locationsOfInterest[i];
                break;
            }}
        }}

        // Check for commercial intent
        var commercialIndicators = ['buy', 'purchase', 'deal', 'sale', 'discount', 'coupon', 'free'];
        for (var i = 0; i < commercialIndicators.length; i++) {{
            if (searchTerm.includes(commercialIndicators[i])) {{
                searchTermData.commercialIntent = true;
                break;
            }}
        }}

        // Flag potential negative keywords
        if (searchTermData.cost > 10 && searchTermData.conversions === 0 && searchTermData.clicks > 5) {{
            searchTermData.negativeCandidate = true;
            searchTermData.negativeReason = 'High cost, no conversions';
        }} else if (searchTermData.ctr < 0.5 && searchTermData.impressions > 1000) {{
            searchTermData.negativeCandidate = true;
            searchTermData.negativeReason = 'Very low CTR';
        }}

        // Flag high-performing terms for Search campaign porting
        if (searchTermData.roas > 5.0 && searchTermData.conversions >= 2) {{
            searchTermData.searchPortCandidate = true;
            searchTermData.portReason = 'High ROAS performance';
        }}

        results.searchTermInsights.push(searchTermData);
    }}
}}

function analyzeGeographicPerformance() {{
    if (!includeGeoData) return;

    var query = `
        SELECT
            geographic_view.country_criterion_id,
            geographic_view.location_type,
            campaign.id,
            campaign.name,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.conversions,
            metrics.conversions_value,
            segments.date
        FROM geographic_view
        WHERE campaign.advertising_channel_type = 'PERFORMANCE_MAX'
            AND campaign.status = 'ENABLED'
            AND segments.date DURING ${{dateRange}}
            AND metrics.impressions > 0
        ORDER BY metrics.cost_micros DESC
        LIMIT 1000
    `;

    var geoReport = AdsApp.report(query);
    var rows = geoReport.rows();

    while (rows.hasNext()) {{
        var row = rows.next();
        var geoData = {{
            countryCriterionId: row['geographic_view.country_criterion_id'],
            locationType: row['geographic_view.location_type'],
            campaignId: row['campaign.id'],
            campaignName: row['campaign.name'],
            impressions: parseInt(row['metrics.impressions']),
            clicks: parseInt(row['metrics.clicks']),
            cost: parseFloat(row['metrics.cost_micros']) / 1000000,
            conversions: parseFloat(row['metrics.conversions']),
            conversionValue: parseFloat(row['metrics.conversions_value']),
            date: row['segments.date']
        }};

        // Calculate geographic metrics
        geoData.ctr = geoData.impressions > 0 ?
            (geoData.clicks / geoData.impressions * 100) : 0;
        geoData.cpc = geoData.clicks > 0 ?
            (geoData.cost / geoData.clicks) : 0;
        geoData.cpa = geoData.conversions > 0 ?
            (geoData.cost / geoData.conversions) : 0;
        geoData.roas = geoData.cost > 0 ?
            (geoData.conversionValue / geoData.cost) : 0;

        results.geographicPerformance.push(geoData);
    }}
}}

function analyzeBiddingStrategies() {{
    var query = `
        SELECT
            bidding_strategy.id,
            bidding_strategy.name,
            bidding_strategy.type,
            bidding_strategy.target_roas,
            bidding_strategy.target_cpa_micros,
            campaign.id,
            campaign.name,
            metrics.cost_micros,
            metrics.conversions,
            metrics.conversions_value,
            segments.date
        FROM campaign
        WHERE campaign.advertising_channel_type = 'PERFORMANCE_MAX'
            AND campaign.status = 'ENABLED'
            AND segments.date DURING ${{dateRange}}
            AND metrics.cost_micros > 0
        ORDER BY metrics.cost_micros DESC
    `;

    var biddingReport = AdsApp.report(query);
    var rows = biddingReport.rows();

    while (rows.hasNext()) {{
        var row = rows.next();
        var biddingData = {{
            biddingStrategyId: row['bidding_strategy.id'],
            biddingStrategyName: row['bidding_strategy.name'],
            biddingStrategyType: row['bidding_strategy.type'],
            targetRoas: parseFloat(row['bidding_strategy.target_roas'] || 0),
            targetCpa: parseFloat(row['bidding_strategy.target_cpa_micros'] || 0) / 1000000,
            campaignId: row['campaign.id'],
            campaignName: row['campaign.name'],
            cost: parseFloat(row['metrics.cost_micros']) / 1000000,
            conversions: parseFloat(row['metrics.conversions']),
            conversionValue: parseFloat(row['metrics.conversions_value']),
            date: row['segments.date']
        }};

        // Calculate actual vs target performance
        biddingData.actualRoas = biddingData.cost > 0 ?
            (biddingData.conversionValue / biddingData.cost) : 0;
        biddingData.actualCpa = biddingData.conversions > 0 ?
            (biddingData.cost / biddingData.conversions) : 0;

        // Compare to targets
        if (biddingData.targetRoas > 0) {{
            biddingData.roasPerformanceRatio = biddingData.actualRoas / biddingData.targetRoas;
            biddingData.roasTargetMet = biddingData.roasPerformanceRatio >= 0.9; // 90% threshold
        }}

        if (biddingData.targetCpa > 0) {{
            biddingData.cpaPerformanceRatio = biddingData.targetCpa / biddingData.actualCpa;
            biddingData.cpaTargetMet = biddingData.cpaPerformanceRatio >= 0.9; // 90% threshold
        }}

        results.biddingStrategyAnalysis.push(biddingData);
    }}
}}

function generateOptimizationRecommendations() {{
    // Analyze campaign performance for recommendations
    for (var i = 0; i < results.campaignPerformance.length; i++) {{
        var campaign = results.campaignPerformance[i];

        if (campaign.performanceFlags.includes('LOW_ROAS')) {{
            results.recommendations.push({{
                type: 'BIDDING_STRATEGY',
                priority: 'HIGH',
                campaignId: campaign.campaignId,
                campaignName: campaign.campaignName,
                issue: 'Low ROAS Performance',
                recommendation: 'Consider adjusting target ROAS or improving asset quality',
                currentRoas: campaign.roas,
                targetRoas: targetRoasThreshold,
                potentialImpact: 'Improve efficiency by 20-30%'
            }});
        }}

        if (campaign.performanceFlags.includes('LOW_CTR')) {{
            results.recommendations.push({{
                type: 'CREATIVE_OPTIMIZATION',
                priority: 'MEDIUM',
                campaignId: campaign.campaignId,
                campaignName: campaign.campaignName,
                issue: 'Low Click-Through Rate',
                recommendation: 'Refresh creative assets and test new ad copy variations',
                currentCtr: campaign.ctr,
                potentialImpact: 'Improve CTR by 15-25%'
            }});
        }}
    }}

    // Analyze search terms for recommendations
    var negativeCount = 0;
    var portToSearchCount = 0;

    for (var i = 0; i < results.searchTermInsights.length; i++) {{
        var term = results.searchTermInsights[i];

        if (term.negativeCandidate) {{
            negativeCount++;
        }}

        if (term.searchPortCandidate) {{
            portToSearchCount++;
        }}
    }}

    if (negativeCount > 0) {{
        results.recommendations.push({{
            type: 'NEGATIVE_KEYWORDS',
            priority: 'HIGH',
            issue: 'Irrelevant Search Terms',
            recommendation: `Add ${{negativeCount}} identified terms to negative keyword lists`,
            count: negativeCount,
            potentialImpact: 'Reduce wasted spend by 10-20%'
        }});
    }}

    if (portToSearchCount > 0) {{
        results.recommendations.push({{
            type: 'SEARCH_EXPANSION',
            priority: 'MEDIUM',
            issue: 'High-Performing PMax Terms',
            recommendation: `Consider adding ${{portToSearchCount}} high-performing terms to Search campaigns`,
            count: portToSearchCount,
            potentialImpact: 'Increase conversion control and volume'
        }});
    }}
}}

function exportResults() {{
    // Create summary report
    var summary = {{
        executionDate: new Date().toISOString(),
        dateRange: dateRange,
        campaignsAnalyzed: results.campaignPerformance.length,
        assetGroupsAnalyzed: results.assetGroupPerformance.length,
        searchTermsAnalyzed: results.searchTermInsights.length,
        geoLocationsAnalyzed: results.geographicPerformance.length,
        recommendationsGenerated: results.recommendations.length
    }};

    // Log key findings
    Logger.log("=== Performance Max Monitoring Summary ===");
    Logger.log("Campaigns analyzed: " + summary.campaignsAnalyzed);
    Logger.log("Asset groups analyzed: " + summary.assetGroupsAnalyzed);
    Logger.log("Search terms analyzed: " + summary.searchTermsAnalyzed);
    Logger.log("Recommendations generated: " + summary.recommendationsGenerated);

    // In production, export to Google Sheets or Cloud Storage
    // This would integrate with existing CSV export functionality
    Logger.log("Results ready for export to external storage");
}}

// Utility functions
function formatCurrency(amount) {{
    return "$" + amount.toFixed(2);
}}

function formatPercentage(rate) {{
    return (rate * 100).toFixed(2) + "%";
}}
        '''.strip()

        return script

    def process_results(self, results: Dict[str, Any]) -> ScriptResult:
        """Process the results from Performance Max monitoring script execution."""
        status = ScriptStatus.COMPLETED.value
        errors = []
        warnings = []

        # Extract key metrics from results
        rows_processed = results.get("rows_processed", 0)
        changes_made = 0  # Performance Max monitoring is read-only

        # Check for any issues in results
        if results.get("success", False):
            if rows_processed == 0:
                warnings.append(
                    "No Performance Max campaigns found or no data in date range"
                )
        else:
            status = ScriptStatus.FAILED.value
            errors.append("Script execution failed")

        # Extract detailed results
        details = {
            "script_type": "performance_max_monitoring",
            "campaigns_analyzed": results.get("details", {}).get(
                "campaigns_analyzed", 0
            ),
            "asset_groups_analyzed": results.get("details", {}).get(
                "asset_groups_analyzed", 0
            ),
            "search_terms_analyzed": results.get("details", {}).get(
                "search_terms_analyzed", 0
            ),
            "geographic_locations_analyzed": results.get("details", {}).get(
                "geo_locations_analyzed", 0
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


class PerformanceMaxAssetOptimizationScript(ScriptBase):
    """Script for Performance Max asset performance tracking and optimization."""

    def __init__(self, client: GoogleAdsClient, config: ScriptConfig):
        super().__init__(client, config)
        self.script_type = ScriptType.PERFORMANCE_MAX_ASSETS

    def get_required_parameters(self) -> List[str]:
        """Get required parameters for asset optimization."""
        return ["date_range", "customer_id"]

    def generate_script(self) -> str:
        """Generate Google Ads Script for asset optimization."""
        date_range = self.config.parameters.get("date_range", "LAST_30_DAYS")
        min_impressions = self.config.parameters.get("min_impressions", 100)
        zombie_threshold_days = self.config.parameters.get("zombie_threshold_days", 30)
        asset_strength_threshold = self.config.parameters.get(
            "asset_strength_threshold", "GOOD"
        )

        script = f'''
function main() {{
    // Performance Max Asset Optimization Script
    // Generated on: {datetime.utcnow().isoformat()}

    var dateRange = "{date_range}";
    var minImpressions = {min_impressions};
    var zombieThresholdDays = {zombie_threshold_days};
    var assetStrengthThreshold = "{asset_strength_threshold}";

    var results = {{
        assetAnalysis: [],
        zombieAssets: [],
        topPerformingAssets: [],
        assetCombinations: [],
        recommendations: []
    }};

    Logger.log("Starting Performance Max asset optimization analysis...");

    // Step 1: Analyze asset performance
    analyzeAssetPerformance();

    // Step 2: Identify zombie assets
    identifyZombieAssets();

    // Step 3: Find top-performing assets
    identifyTopPerformingAssets();

    // Step 4: Analyze asset combinations
    analyzeAssetCombinations();

    // Step 5: Generate asset recommendations
    generateAssetRecommendations();

    // Step 6: Export results
    exportAssetResults();

    Logger.log("Asset optimization analysis completed.");
}}

function analyzeAssetPerformance() {{
    // Analyze different asset types: images, videos, headlines, descriptions
    analyzeImageAssets();
    analyzeVideoAssets();
    analyzeTextAssets();
}}

function analyzeImageAssets() {{
    // Note: Asset-level performance data requires specific API access
    // This is a framework for when Google provides more asset-level reporting

    var query = `
        SELECT
            asset.id,
            asset.name,
            asset.type,
            asset_group_asset.field_type,
            asset_group.id,
            asset_group.name,
            campaign.id,
            campaign.name,
            metrics.impressions,
            metrics.clicks,
            metrics.conversions,
            segments.date
        FROM asset_group_asset
        WHERE campaign.advertising_channel_type = 'PERFORMANCE_MAX'
            AND campaign.status = 'ENABLED'
            AND asset.type = 'IMAGE'
            AND segments.date DURING ${{dateRange}}
            AND metrics.impressions >= ${{minImpressions}}
        ORDER BY metrics.impressions DESC
        LIMIT 1000
    `;

    try {{
        var imageReport = AdsApp.report(query);
        var rows = imageReport.rows();

        while (rows.hasNext()) {{
            var row = rows.next();
            var assetData = {{
                assetId: row['asset.id'],
                assetName: row['asset.name'] || 'Unnamed Asset',
                assetType: 'IMAGE',
                fieldType: row['asset_group_asset.field_type'],
                assetGroupId: row['asset_group.id'],
                assetGroupName: row['asset_group.name'],
                campaignId: row['campaign.id'],
                campaignName: row['campaign.name'],
                impressions: parseInt(row['metrics.impressions']),
                clicks: parseInt(row['metrics.clicks']),
                conversions: parseFloat(row['metrics.conversions']),
                date: row['segments.date']
            }};

            // Calculate performance metrics
            assetData.ctr = assetData.impressions > 0 ?
                (assetData.clicks / assetData.impressions * 100) : 0;
            assetData.conversionRate = assetData.clicks > 0 ?
                (assetData.conversions / assetData.clicks * 100) : 0;

            // Categorize performance
            if (assetData.ctr > 3.0 && assetData.conversions > 0) {{
                assetData.performanceCategory = 'HIGH';
            }} else if (assetData.ctr > 1.0) {{
                assetData.performanceCategory = 'MEDIUM';
            }} else {{
                assetData.performanceCategory = 'LOW';
            }}

            results.assetAnalysis.push(assetData);
        }}
    }} catch (error) {{
        Logger.log("Asset-level reporting may not be available: " + error.message);
        // Fallback to asset group level analysis
        analyzeAssetGroupLevel();
    }}
}}

function analyzeVideoAssets() {{
    // Similar structure for video assets
    Logger.log("Analyzing video asset performance...");
    // Implementation would follow similar pattern to image assets
}}

function analyzeTextAssets() {{
    // Analyze headlines and descriptions
    Logger.log("Analyzing text asset performance...");
    // Implementation would analyze headline and description performance
}}

function analyzeAssetGroupLevel() {{
    // Fallback analysis at asset group level when asset-level data isn't available
    var query = `
        SELECT
            asset_group.id,
            asset_group.name,
            asset_group.ad_strength,
            campaign.id,
            campaign.name,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.conversions,
            metrics.conversions_value,
            segments.date
        FROM asset_group
        WHERE campaign.advertising_channel_type = 'PERFORMANCE_MAX'
            AND campaign.status = 'ENABLED'
            AND asset_group.status = 'ENABLED'
            AND segments.date DURING ${{dateRange}}
            AND metrics.impressions >= ${{minImpressions}}
        ORDER BY metrics.cost_micros DESC
    `;

    var assetGroupReport = AdsApp.report(query);
    var rows = assetGroupReport.rows();

    while (rows.hasNext()) {{
        var row = rows.next();
        var groupData = {{
            assetGroupId: row['asset_group.id'],
            assetGroupName: row['asset_group.name'],
            adStrength: row['asset_group.ad_strength'],
            campaignId: row['campaign.id'],
            campaignName: row['campaign.name'],
            impressions: parseInt(row['metrics.impressions']),
            clicks: parseInt(row['metrics.clicks']),
            cost: parseFloat(row['metrics.cost_micros']) / 1000000,
            conversions: parseFloat(row['metrics.conversions']),
            conversionValue: parseFloat(row['metrics.conversions_value']),
            date: row['segments.date']
        }};

        // Calculate metrics
        groupData.ctr = groupData.impressions > 0 ?
            (groupData.clicks / groupData.impressions * 100) : 0;
        groupData.cpc = groupData.clicks > 0 ?
            (groupData.cost / groupData.clicks) : 0;
        groupData.cpa = groupData.conversions > 0 ?
            (groupData.cost / groupData.conversions) : 0;
        groupData.roas = groupData.cost > 0 ?
            (groupData.conversionValue / groupData.cost) : 0;

        // Flag ad strength issues
        if (groupData.adStrength !== 'EXCELLENT' && groupData.adStrength !== 'GOOD') {{
            groupData.needsImprovement = true;
            groupData.improvementReason = 'Low ad strength: ' + groupData.adStrength;
        }}

        results.assetAnalysis.push(groupData);
    }}
}}

function identifyZombieAssets() {{
    // Identify assets with impressions but no clicks over extended period
    for (var i = 0; i < results.assetAnalysis.length; i++) {{
        var asset = results.assetAnalysis[i];

        if (asset.impressions >= minImpressions && asset.clicks === 0) {{
            results.zombieAssets.push({{
                assetId: asset.assetId || asset.assetGroupId,
                assetName: asset.assetName || asset.assetGroupName,
                assetType: asset.assetType || 'ASSET_GROUP',
                impressions: asset.impressions,
                daysActive: zombieThresholdDays, // Simplified - would calculate actual days
                reason: 'No clicks despite ' + asset.impressions + ' impressions',
                recommendation: 'Remove or replace asset'
            }});
        }}
    }}

    Logger.log("Identified " + results.zombieAssets.length + " zombie assets");
}}

function identifyTopPerformingAssets() {{
    // Sort assets by performance and identify top performers
    var sortedAssets = results.assetAnalysis.slice().sort(function(a, b) {{
        // Sort by CTR * conversion rate combination
        var scoreA = a.ctr * (a.conversionRate || 0);
        var scoreB = b.ctr * (b.conversionRate || 0);
        return scoreB - scoreA;
    }});

    // Take top 20% or minimum 5 assets
    var topCount = Math.max(5, Math.floor(sortedAssets.length * 0.2));
    results.topPerformingAssets = sortedAssets.slice(0, topCount).map(function(asset) {{
        return {{
            assetId: asset.assetId || asset.assetGroupId,
            assetName: asset.assetName || asset.assetGroupName,
            assetType: asset.assetType || 'ASSET_GROUP',
            ctr: asset.ctr,
            conversionRate: asset.conversionRate || 0,
            performanceScore: asset.ctr * (asset.conversionRate || 0),
            reason: 'High CTR and conversion performance'
        }};
    }});

    Logger.log("Identified " + results.topPerformingAssets.length + " top performing assets");
}}

function analyzeAssetCombinations() {{
    // Analyze which combinations of assets work well together
    // This is a simplified version - full implementation would analyze correlation

    if (results.assetAnalysis.length >= 2) {{
        // Group by campaign and analyze combinations
        var campaignGroups = {{}};

        for (var i = 0; i < results.assetAnalysis.length; i++) {{
            var asset = results.assetAnalysis[i];
            var campaignId = asset.campaignId;

            if (!campaignGroups[campaignId]) {{
                campaignGroups[campaignId] = [];
            }}
            campaignGroups[campaignId].push(asset);
        }}

        // Analyze combinations within each campaign
        for (var campaignId in campaignGroups) {{
            var assets = campaignGroups[campaignId];
            if (assets.length >= 2) {{
                // Find best performing asset group in this campaign
                var bestAsset = assets.reduce(function(best, current) {{
                    return (current.ctr > best.ctr) ? current : best;
                }});

                results.assetCombinations.push({{
                    campaignId: campaignId,
                    campaignName: bestAsset.campaignName,
                    bestPerformingAssetGroup: bestAsset.assetGroupName,
                    combinationScore: bestAsset.ctr,
                    recommendation: 'Scale successful patterns from this asset group'
                }});
            }}
        }}
    }}
}}

function generateAssetRecommendations() {{
    // Generate specific asset recommendations

    // Zombie asset removal
    if (results.zombieAssets.length > 0) {{
        results.recommendations.push({{
            type: 'REMOVE_ZOMBIES',
            priority: 'HIGH',
            title: 'Remove ' + results.zombieAssets.length + ' zombie assets',
            description: 'Assets with impressions but no clicks are wasting budget',
            impact: 'Improve overall campaign efficiency',
            assetCount: results.zombieAssets.length
        }});
    }}

    // Asset refresh for low performers
    var lowPerformingCount = results.assetAnalysis.filter(function(asset) {{
        return asset.performanceCategory === 'LOW' || asset.needsImprovement;
    }}).length;

    if (lowPerformingCount > 0) {{
        results.recommendations.push({{
            type: 'REFRESH_ASSETS',
            priority: 'MEDIUM',
            title: 'Refresh ' + lowPerformingCount + ' underperforming assets',
            description: 'Replace or update assets with poor performance',
            impact: 'Improve CTR and conversion rates',
            assetCount: lowPerformingCount
        }});
    }}

    // Scale top performers
    if (results.topPerformingAssets.length > 0) {{
        results.recommendations.push({{
            type: 'SCALE_WINNERS',
            priority: 'MEDIUM',
            title: 'Scale top performing asset patterns',
            description: 'Create more assets similar to top performers',
            impact: 'Increase overall campaign performance',
            topAssetCount: results.topPerformingAssets.length
        }});
    }}

    // Ad strength improvements
    var weakAdStrengthCount = results.assetAnalysis.filter(function(asset) {{
        return asset.adStrength && asset.adStrength !== 'EXCELLENT' && asset.adStrength !== 'GOOD';
    }}).length;

    if (weakAdStrengthCount > 0) {{
        results.recommendations.push({{
            type: 'IMPROVE_AD_STRENGTH',
            priority: 'HIGH',
            title: 'Improve ad strength for ' + weakAdStrengthCount + ' asset groups',
            description: 'Add more diverse assets to improve ad strength scores',
            impact: 'Better ad auction performance',
            assetGroupCount: weakAdStrengthCount
        }});
    }}
}}

function exportAssetResults() {{
    var summary = {{
        executionDate: new Date().toISOString(),
        dateRange: dateRange,
        assetsAnalyzed: results.assetAnalysis.length,
        zombieAssetsFound: results.zombieAssets.length,
        topPerformersIdentified: results.topPerformingAssets.length,
        recommendationsGenerated: results.recommendations.length
    }};

    Logger.log("=== Asset Optimization Summary ===");
    Logger.log("Assets analyzed: " + summary.assetsAnalyzed);
    Logger.log("Zombie assets found: " + summary.zombieAssetsFound);
    Logger.log("Top performers identified: " + summary.topPerformersIdentified);
    Logger.log("Recommendations generated: " + summary.recommendationsGenerated);

    // Export detailed results for further analysis
    Logger.log("Asset optimization results ready for export");
}}
        '''.strip()

        return script

    def process_results(self, results: Dict[str, Any]) -> ScriptResult:
        """Process the results from asset optimization script execution."""
        status = ScriptStatus.COMPLETED.value
        errors = []
        warnings = []

        rows_processed = results.get("rows_processed", 0)
        changes_made = 0  # Asset optimization is analysis-only

        if results.get("success", False):
            if rows_processed == 0:
                warnings.append("No asset data found for analysis")
        else:
            status = ScriptStatus.FAILED.value
            errors.append("Asset optimization script execution failed")

        details = {
            "script_type": "performance_max_asset_optimization",
            "assets_analyzed": results.get("details", {}).get("assets_analyzed", 0),
            "zombie_assets_found": results.get("details", {}).get(
                "zombie_assets_found", 0
            ),
            "top_performers_identified": results.get("details", {}).get(
                "top_performers_identified", 0
            ),
            "asset_combinations_analyzed": results.get("details", {}).get(
                "asset_combinations_analyzed", 0
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
