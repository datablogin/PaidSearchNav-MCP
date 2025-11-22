"""Cross-campaign Performance Max analysis scripts.

This module implements Google Ads Scripts for analyzing Performance Max campaigns
in relation to Search campaigns, identifying conflicts, and optimizing overall account structure.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List

from paidsearchnav_mcp.platforms.google.client import GoogleAdsClient

from .base import ScriptBase, ScriptConfig, ScriptResult, ScriptStatus, ScriptType

logger = logging.getLogger(__name__)


class PerformanceMaxCrossCampaignScript(ScriptBase):
    """Script for Performance Max vs Search campaign cross-analysis and optimization."""

    def __init__(self, client: GoogleAdsClient, config: ScriptConfig):
        super().__init__(client, config)
        self.script_type = ScriptType.PERFORMANCE_MAX_CROSS_CAMPAIGN

    def get_required_parameters(self) -> List[str]:
        """Get required parameters for cross-campaign analysis."""
        return ["date_range", "customer_id"]

    def generate_script(self) -> str:
        """Generate Google Ads Script for cross-campaign analysis."""
        date_range = self.config.parameters.get("date_range", "LAST_30_DAYS")
        overlap_threshold = self.config.parameters.get("overlap_threshold", 0.2)
        min_cost_for_analysis = self.config.parameters.get(
            "min_cost_for_analysis", 20.0
        )
        budget_reallocation_threshold = self.config.parameters.get(
            "budget_reallocation_threshold", 0.3
        )

        script = f'''
function main() {{
    // Performance Max vs Search Campaign Cross-Analysis Script
    // Generated on: {datetime.utcnow().isoformat()}

    var dateRange = "{date_range}";
    var overlapThreshold = {overlap_threshold};
    var minCostForAnalysis = {min_cost_for_analysis};
    var budgetReallocationThreshold = {budget_reallocation_threshold};

    var results = {{
        performanceMaxData: [],
        searchCampaignData: [],
        crossCampaignAnalysis: [],
        searchTermOverlap: [],
        budgetAnalysis: [],
        conflictAnalysis: [],
        recommendations: []
    }};

    Logger.log("Starting Performance Max vs Search campaign cross-analysis...");

    // Step 1: Extract Performance Max campaign data
    extractPerformanceMaxData();

    // Step 2: Extract Search campaign data
    extractSearchCampaignData();

    // Step 3: Analyze search term overlap
    analyzeSearchTermOverlap();

    // Step 4: Perform cross-campaign performance analysis
    performCrossCampaignAnalysis();

    // Step 5: Analyze budget allocation
    analyzeBudgetAllocation();

    // Step 6: Identify conflicts and cannibalization
    identifyConflicts();

    // Step 7: Generate cross-campaign recommendations
    generateCrossCampaignRecommendations();

    // Step 8: Export cross-campaign results
    exportCrossCampaignResults();

    Logger.log("Cross-campaign analysis completed.");
}}

function extractPerformanceMaxData() {{
    // Extract comprehensive Performance Max campaign data
    var query = `
        SELECT
            campaign.id,
            campaign.name,
            campaign.status,
            campaign.bidding_strategy_type,
            campaign.target_roas,
            campaign.target_cpa_micros,
            campaign.budget.budget_id,
            campaign.budget.amount_micros,
            metrics.cost_micros,
            metrics.impressions,
            metrics.clicks,
            metrics.conversions,
            metrics.conversions_value,
            metrics.all_conversions,
            metrics.view_through_conversions,
            segments.date
        FROM campaign
        WHERE campaign.advertising_channel_type = 'PERFORMANCE_MAX'
            AND campaign.status = 'ENABLED'
            AND segments.date DURING ${{dateRange}}
            AND metrics.cost_micros >= ${{minCostForAnalysis * 1000000}}
        ORDER BY metrics.cost_micros DESC
    `;

    var pmaxReport = AdsApp.report(query);
    var rows = pmaxReport.rows();

    while (rows.hasNext()) {{
        var row = rows.next();

        var pmaxData = {{
            campaignId: row['campaign.id'],
            campaignName: row['campaign.name'],
            campaignType: 'PERFORMANCE_MAX',
            status: row['campaign.status'],
            biddingStrategy: row['campaign.bidding_strategy_type'],
            targetRoas: parseFloat(row['campaign.target_roas'] || 0),
            targetCpa: parseFloat(row['campaign.target_cpa_micros'] || 0) / 1000000,
            budgetId: row['campaign.budget.budget_id'],
            dailyBudget: parseFloat(row['campaign.budget.amount_micros']) / 1000000,
            cost: parseFloat(row['metrics.cost_micros']) / 1000000,
            impressions: parseInt(row['metrics.impressions']),
            clicks: parseInt(row['metrics.clicks']),
            conversions: parseFloat(row['metrics.conversions']),
            conversionValue: parseFloat(row['metrics.conversions_value']),
            allConversions: parseFloat(row['metrics.all_conversions']),
            viewThroughConversions: parseFloat(row['metrics.view_through_conversions']),
            date: row['segments.date']
        }};

        // Calculate performance metrics
        pmaxData.ctr = pmaxData.impressions > 0 ?
            (pmaxData.clicks / pmaxData.impressions * 100) : 0;
        pmaxData.cpc = pmaxData.clicks > 0 ?
            (pmaxData.cost / pmaxData.clicks) : 0;
        pmaxData.cpa = pmaxData.conversions > 0 ?
            (pmaxData.cost / pmaxData.conversions) : 0;
        pmaxData.roas = pmaxData.cost > 0 ?
            (pmaxData.conversionValue / pmaxData.cost) : 0;
        pmaxData.conversionRate = pmaxData.clicks > 0 ?
            (pmaxData.conversions / pmaxData.clicks * 100) : 0;

        results.performanceMaxData.push(pmaxData);
    }}

    Logger.log("Extracted " + results.performanceMaxData.length + " Performance Max campaigns");
}}

function extractSearchCampaignData() {{
    // Extract Search campaign data for comparison
    var query = `
        SELECT
            campaign.id,
            campaign.name,
            campaign.status,
            campaign.bidding_strategy_type,
            campaign.target_roas,
            campaign.target_cpa_micros,
            campaign.budget.budget_id,
            campaign.budget.amount_micros,
            metrics.cost_micros,
            metrics.impressions,
            metrics.clicks,
            metrics.conversions,
            metrics.conversions_value,
            metrics.all_conversions,
            segments.date
        FROM campaign
        WHERE campaign.advertising_channel_type = 'SEARCH'
            AND campaign.status = 'ENABLED'
            AND segments.date DURING ${{dateRange}}
            AND metrics.cost_micros >= ${{minCostForAnalysis * 1000000}}
        ORDER BY metrics.cost_micros DESC
    `;

    var searchReport = AdsApp.report(query);
    var rows = searchReport.rows();

    while (rows.hasNext()) {{
        var row = rows.next();

        var searchData = {{
            campaignId: row['campaign.id'],
            campaignName: row['campaign.name'],
            campaignType: 'SEARCH',
            status: row['campaign.status'],
            biddingStrategy: row['campaign.bidding_strategy_type'],
            targetRoas: parseFloat(row['campaign.target_roas'] || 0),
            targetCpa: parseFloat(row['campaign.target_cpa_micros'] || 0) / 1000000,
            budgetId: row['campaign.budget.budget_id'],
            dailyBudget: parseFloat(row['campaign.budget.amount_micros']) / 1000000,
            cost: parseFloat(row['metrics.cost_micros']) / 1000000,
            impressions: parseInt(row['metrics.impressions']),
            clicks: parseInt(row['metrics.clicks']),
            conversions: parseFloat(row['metrics.conversions']),
            conversionValue: parseFloat(row['metrics.conversions_value']),
            allConversions: parseFloat(row['metrics.all_conversions']),
            date: row['segments.date']
        }};

        // Calculate performance metrics
        searchData.ctr = searchData.impressions > 0 ?
            (searchData.clicks / searchData.impressions * 100) : 0;
        searchData.cpc = searchData.clicks > 0 ?
            (searchData.cost / searchData.clicks) : 0;
        searchData.cpa = searchData.conversions > 0 ?
            (searchData.cost / searchData.conversions) : 0;
        searchData.roas = searchData.cost > 0 ?
            (searchData.conversionValue / searchData.cost) : 0;
        searchData.conversionRate = searchData.clicks > 0 ?
            (searchData.conversions / searchData.clicks * 100) : 0;

        results.searchCampaignData.push(searchData);
    }}

    Logger.log("Extracted " + results.searchCampaignData.length + " Search campaigns");
}}

function analyzeSearchTermOverlap() {{
    // Analyze search term overlap between Performance Max and Search campaigns

    // Get Performance Max search terms
    var pmaxSearchTerms = getSearchTermsForCampaigns('PERFORMANCE_MAX',
        results.performanceMaxData.map(function(c) {{ return c.campaignId; }}));

    // Get Search campaign search terms
    var searchTerms = getSearchTermsForCampaigns('SEARCH',
        results.searchCampaignData.map(function(c) {{ return c.campaignId; }}));

    // Find overlapping terms
    var pmaxTermsMap = {{}};
    var searchTermsMap = {{}};

    // Build Performance Max terms map
    for (var i = 0; i < pmaxSearchTerms.length; i++) {{
        var term = pmaxSearchTerms[i];
        var normalizedTerm = term.searchTerm.toLowerCase().trim();
        if (!pmaxTermsMap[normalizedTerm]) {{
            pmaxTermsMap[normalizedTerm] = [];
        }}
        pmaxTermsMap[normalizedTerm].push(term);
    }}

    // Build Search terms map and find overlaps
    for (var i = 0; i < searchTerms.length; i++) {{
        var term = searchTerms[i];
        var normalizedTerm = term.searchTerm.toLowerCase().trim();

        if (!searchTermsMap[normalizedTerm]) {{
            searchTermsMap[normalizedTerm] = [];
        }}
        searchTermsMap[normalizedTerm].push(term);

        // Check for overlap with Performance Max
        if (pmaxTermsMap[normalizedTerm]) {{
            var pmaxTerms = pmaxTermsMap[normalizedTerm];
            var searchTermsForTerm = searchTermsMap[normalizedTerm];

            for (var j = 0; j < pmaxTerms.length; j++) {{
                for (var k = 0; k < searchTermsForTerm.length; k++) {{
                    var pmaxTerm = pmaxTerms[j];
                    var searchTerm = searchTermsForTerm[k];

                    var overlapData = {{
                        searchTerm: normalizedTerm,
                        pmaxCampaignId: pmaxTerm.campaignId,
                        pmaxCampaignName: pmaxTerm.campaignName,
                        searchCampaignId: searchTerm.campaignId,
                        searchCampaignName: searchTerm.campaignName,
                        pmaxCost: pmaxTerm.cost,
                        searchCost: searchTerm.cost,
                        totalCost: pmaxTerm.cost + searchTerm.cost,
                        pmaxConversions: pmaxTerm.conversions,
                        searchConversions: searchTerm.conversions,
                        pmaxCpa: pmaxTerm.conversions > 0 ? pmaxTerm.cost / pmaxTerm.conversions : 0,
                        searchCpa: searchTerm.conversions > 0 ? searchTerm.cost / searchTerm.conversions : 0,
                        pmaxRoas: pmaxTerm.cost > 0 ? pmaxTerm.conversionValue / pmaxTerm.cost : 0,
                        searchRoas: searchTerm.cost > 0 ? searchTerm.conversionValue / searchTerm.cost : 0
                    }};

                    // Determine better performer
                    overlapData.betterPerformer = determineBetterPerformer(pmaxTerm, searchTerm);
                    overlapData.overlapSeverity = calculateOverlapSeverity(overlapData);
                    overlapData.recommendation = generateOverlapRecommendation(overlapData);

                    results.searchTermOverlap.push(overlapData);
                }}
            }}
        }}
    }}

    Logger.log("Identified " + results.searchTermOverlap.length + " overlapping search terms");
}}

function getSearchTermsForCampaigns(campaignType, campaignIds) {{
    if (campaignIds.length === 0) return [];

    var campaignIdsStr = campaignIds.join(',');
    var query = `
        SELECT
            search_term_view.search_term,
            campaign.id,
            campaign.name,
            ad_group.id,
            ad_group.name,
            metrics.cost_micros,
            metrics.impressions,
            metrics.clicks,
            metrics.conversions,
            metrics.conversions_value,
            segments.date
        FROM search_term_view
        WHERE campaign.id IN (${{campaignIdsStr}})
            AND campaign.advertising_channel_type = '${{campaignType}}'
            AND segments.date DURING ${{dateRange}}
            AND metrics.cost_micros > 0
        ORDER BY metrics.cost_micros DESC
        LIMIT 5000
    `;

    var searchTerms = [];
    var report = AdsApp.report(query);
    var rows = report.rows();

    while (rows.hasNext()) {{
        var row = rows.next();
        searchTerms.push({{
            searchTerm: row['search_term_view.search_term'],
            campaignId: row['campaign.id'],
            campaignName: row['campaign.name'],
            adGroupId: row['ad_group.id'],
            adGroupName: row['ad_group.name'],
            cost: parseFloat(row['metrics.cost_micros']) / 1000000,
            impressions: parseInt(row['metrics.impressions']),
            clicks: parseInt(row['metrics.clicks']),
            conversions: parseFloat(row['metrics.conversions']),
            conversionValue: parseFloat(row['metrics.conversions_value']),
            date: row['segments.date']
        }});
    }}

    return searchTerms;
}}

function determineBetterPerformer(pmaxTerm, searchTerm) {{
    // Determine which campaign type performs better for this term
    var pmaxScore = 0;
    var searchScore = 0;

    // CPA comparison (lower is better)
    var pmaxCpa = pmaxTerm.conversions > 0 ? pmaxTerm.cost / pmaxTerm.conversions : 1000;
    var searchCpa = searchTerm.conversions > 0 ? searchTerm.cost / searchTerm.conversions : 1000;

    if (pmaxCpa < searchCpa * 0.8) pmaxScore += 2;
    else if (pmaxCpa < searchCpa) pmaxScore += 1;
    else if (searchCpa < pmaxCpa * 0.8) searchScore += 2;
    else if (searchCpa < pmaxCpa) searchScore += 1;

    // ROAS comparison (higher is better)
    var pmaxRoas = pmaxTerm.cost > 0 ? pmaxTerm.conversionValue / pmaxTerm.cost : 0;
    var searchRoas = searchTerm.cost > 0 ? searchTerm.conversionValue / searchTerm.cost : 0;

    if (pmaxRoas > searchRoas * 1.2) pmaxScore += 2;
    else if (pmaxRoas > searchRoas) pmaxScore += 1;
    else if (searchRoas > pmaxRoas * 1.2) searchScore += 2;
    else if (searchRoas > pmaxRoas) searchScore += 1;

    // Conversion volume (more is better for control)
    if (pmaxTerm.conversions > searchTerm.conversions * 1.5) pmaxScore += 1;
    else if (searchTerm.conversions > pmaxTerm.conversions * 1.5) searchScore += 1;

    if (pmaxScore > searchScore) return 'PERFORMANCE_MAX';
    else if (searchScore > pmaxScore) return 'SEARCH';
    else return 'SIMILAR';
}}

function calculateOverlapSeverity(overlapData) {{
    // Calculate severity of overlap based on cost and performance difference
    if (overlapData.totalCost > 200) {{
        return 'HIGH';
    }} else if (overlapData.totalCost > 50) {{
        return 'MEDIUM';
    }} else {{
        return 'LOW';
    }}
}}

function generateOverlapRecommendation(overlapData) {{
    var recommendation = '';

    if (overlapData.betterPerformer === 'PERFORMANCE_MAX') {{
        recommendation = 'Consider adding "' + overlapData.searchTerm + '" as negative keyword to Search campaign';
    }} else if (overlapData.betterPerformer === 'SEARCH') {{
        recommendation = 'Consider adding "' + overlapData.searchTerm + '" as negative keyword to Performance Max campaign';
    }} else {{
        recommendation = 'Monitor performance and test negative keywords in lower performing campaign';
    }}

    return recommendation;
}}

function performCrossCampaignAnalysis() {{
    // Comprehensive cross-campaign performance analysis

    var totalPmaxSpend = results.performanceMaxData.reduce(function(sum, c) {{ return sum + c.cost; }}, 0);
    var totalSearchSpend = results.searchCampaignData.reduce(function(sum, c) {{ return sum + c.cost; }}, 0);
    var totalSpend = totalPmaxSpend + totalSearchSpend;

    var totalPmaxConversions = results.performanceMaxData.reduce(function(sum, c) {{ return sum + c.conversions; }}, 0);
    var totalSearchConversions = results.searchCampaignData.reduce(function(sum, c) {{ return sum + c.conversions; }}, 0);

    var totalPmaxConversionValue = results.performanceMaxData.reduce(function(sum, c) {{ return sum + c.conversionValue; }}, 0);
    var totalSearchConversionValue = results.searchCampaignData.reduce(function(sum, c) {{ return sum + c.conversionValue; }}, 0);

    var crossAnalysis = {{
        accountOverview: {{
            totalSpend: totalSpend,
            pmaxSpend: totalPmaxSpend,
            searchSpend: totalSearchSpend,
            pmaxSpendPercentage: totalSpend > 0 ? (totalPmaxSpend / totalSpend * 100) : 0,
            searchSpendPercentage: totalSpend > 0 ? (totalSearchSpend / totalSpend * 100) : 0
        }},
        performanceComparison: {{
            pmaxAverageCpa: totalPmaxConversions > 0 ? (totalPmaxSpend / totalPmaxConversions) : 0,
            searchAverageCpa: totalSearchConversions > 0 ? (totalSearchSpend / totalSearchConversions) : 0,
            pmaxAverageRoas: totalPmaxSpend > 0 ? (totalPmaxConversionValue / totalPmaxSpend) : 0,
            searchAverageRoas: totalSearchSpend > 0 ? (totalSearchConversionValue / totalSearchSpend) : 0,
            pmaxConversions: totalPmaxConversions,
            searchConversions: totalSearchConversions,
            totalConversions: totalPmaxConversions + totalSearchConversions
        }},
        budgetDistribution: {{
            pmaxCampaignCount: results.performanceMaxData.length,
            searchCampaignCount: results.searchCampaignData.length,
            averagePmaxBudget: results.performanceMaxData.length > 0 ?
                (results.performanceMaxData.reduce(function(sum, c) {{ return sum + c.dailyBudget; }}, 0) / results.performanceMaxData.length) : 0,
            averageSearchBudget: results.searchCampaignData.length > 0 ?
                (results.searchCampaignData.reduce(function(sum, c) {{ return sum + c.dailyBudget; }}, 0) / results.searchCampaignData.length) : 0
        }},
        overlapAnalysis: {{
            overlappingTermsCount: results.searchTermOverlap.length,
            totalOverlapCost: results.searchTermOverlap.reduce(function(sum, o) {{ return sum + o.totalCost; }}, 0),
            highSeverityOverlaps: results.searchTermOverlap.filter(function(o) {{ return o.overlapSeverity === 'HIGH'; }}).length,
            averageOverlapCost: results.searchTermOverlap.length > 0 ?
                (results.searchTermOverlap.reduce(function(sum, o) {{ return sum + o.totalCost; }}, 0) / results.searchTermOverlap.length) : 0
        }}
    }};

    results.crossCampaignAnalysis.push(crossAnalysis);
}}

function analyzeBudgetAllocation() {{
    // Analyze budget allocation efficiency between Performance Max and Search

    var analysis = results.crossCampaignAnalysis[0];
    var pmaxEfficiency = analysis.performanceComparison.pmaxAverageRoas;
    var searchEfficiency = analysis.performanceComparison.searchAverageRoas;

    var budgetAnalysis = {{
        currentAllocation: {{
            pmaxPercentage: analysis.accountOverview.pmaxSpendPercentage,
            searchPercentage: analysis.accountOverview.searchSpendPercentage
        }},
        efficiencyAnalysis: {{
            pmaxRoas: pmaxEfficiency,
            searchRoas: searchEfficiency,
            efficiencyGap: Math.abs(pmaxEfficiency - searchEfficiency),
            moreEfficientChannel: pmaxEfficiency > searchEfficiency ? 'PERFORMANCE_MAX' : 'SEARCH'
        }},
        recommendations: []
    }};

    // Generate budget reallocation recommendations
    if (budgetAnalysis.efficiencyAnalysis.efficiencyGap > 1.0) {{
        var moreEfficient = budgetAnalysis.efficiencyAnalysis.moreEfficientChannel;
        var reallocationAmount = analysis.accountOverview.totalSpend * budgetReallocationThreshold;

        budgetAnalysis.recommendations.push({{
            type: 'BUDGET_REALLOCATION',
            recommendation: 'Reallocate budget to ' + moreEfficient + ' campaigns',
            suggestedAmount: reallocationAmount,
            expectedImpact: 'Improve overall account ROAS by ' +
                           (budgetAnalysis.efficiencyAnalysis.efficiencyGap * 0.1).toFixed(1) + '%'
        }});
    }}

    results.budgetAnalysis.push(budgetAnalysis);
}}

function identifyConflicts() {{
    // Identify specific conflicts between Performance Max and Search campaigns

    // Keyword conflicts (where Search keywords might be blocked by Performance Max)
    var keywordConflicts = [];

    // Budget conflicts (shared budgets causing issues)
    var budgetConflicts = [];

    // Performance conflicts (campaigns competing inefficiently)
    var performanceConflicts = [];

    // Analyze high-severity overlaps for conflicts
    var highSeverityOverlaps = results.searchTermOverlap.filter(function(o) {{
        return o.overlapSeverity === 'HIGH';
    }});

    for (var i = 0; i < highSeverityOverlaps.length; i++) {{
        var overlap = highSeverityOverlaps[i];

        var conflict = {{
            type: 'SEARCH_TERM_CONFLICT',
            searchTerm: overlap.searchTerm,
            pmaxCampaign: overlap.pmaxCampaignName,
            searchCampaign: overlap.searchCampaignName,
            totalWastedSpend: overlap.totalCost * 0.3, // Estimate 30% waste
            severity: overlap.overlapSeverity,
            recommendation: overlap.recommendation
        }};

        keywordConflicts.push(conflict);
    }}

    // Check for budget conflicts (campaigns sharing budgets inefficiently)
    var budgetIds = {{}};

    // Check Performance Max budgets
    for (var i = 0; i < results.performanceMaxData.length; i++) {{
        var campaign = results.performanceMaxData[i];
        if (!budgetIds[campaign.budgetId]) {{
            budgetIds[campaign.budgetId] = [];
        }}
        budgetIds[campaign.budgetId].push(campaign);
    }}

    // Check Search campaign budgets
    for (var i = 0; i < results.searchCampaignData.length; i++) {{
        var campaign = results.searchCampaignData[i];
        if (budgetIds[campaign.budgetId]) {{
            // Mixed campaign types sharing budget
            budgetConflicts.push({{
                type: 'SHARED_BUDGET_CONFLICT',
                budgetId: campaign.budgetId,
                campaigns: budgetIds[campaign.budgetId].concat([campaign]),
                issue: 'Performance Max and Search campaigns sharing budget',
                recommendation: 'Separate budgets for better control'
            }});
        }}
    }}

    results.conflictAnalysis = {{
        keywordConflicts: keywordConflicts,
        budgetConflicts: budgetConflicts,
        performanceConflicts: performanceConflicts,
        totalConflicts: keywordConflicts.length + budgetConflicts.length + performanceConflicts.length
    }};

    Logger.log("Identified " + results.conflictAnalysis.totalConflicts + " conflicts");
}}

function generateCrossCampaignRecommendations() {{
    // Generate comprehensive cross-campaign optimization recommendations

    // Overlap resolution recommendations
    var highValueOverlaps = results.searchTermOverlap.filter(function(o) {{
        return o.totalCost > 100;
    }});

    if (highValueOverlaps.length > 0) {{
        results.recommendations.push({{
            type: 'RESOLVE_OVERLAPS',
            priority: 'HIGH',
            title: 'Resolve ' + highValueOverlaps.length + ' high-value search term overlaps',
            totalWastedSpend: highValueOverlaps.reduce(function(sum, o) {{ return sum + o.totalCost * 0.3; }}, 0),
            overlaps: highValueOverlaps.length,
            recommendation: 'Add negative keywords to lower-performing campaign for each overlapping term',
            potentialImpact: 'Reduce wasted spend and improve overall efficiency'
        }});
    }}

    // Budget reallocation recommendations
    if (results.budgetAnalysis.length > 0 && results.budgetAnalysis[0].recommendations.length > 0) {{
        var budgetRec = results.budgetAnalysis[0].recommendations[0];
        results.recommendations.push({{
            type: 'BUDGET_OPTIMIZATION',
            priority: 'HIGH',
            title: 'Reallocate budget between campaign types',
            recommendation: budgetRec.recommendation,
            suggestedAmount: budgetRec.suggestedAmount,
            expectedImpact: budgetRec.expectedImpact
        }});
    }}

    // Conflict resolution recommendations
    if (results.conflictAnalysis.totalConflicts > 0) {{
        results.recommendations.push({{
            type: 'RESOLVE_CONFLICTS',
            priority: 'HIGH',
            title: 'Resolve ' + results.conflictAnalysis.totalConflicts + ' campaign conflicts',
            keywordConflicts: results.conflictAnalysis.keywordConflicts.length,
            budgetConflicts: results.conflictAnalysis.budgetConflicts.length,
            recommendation: 'Implement negative keywords and separate budgets to eliminate conflicts',
            potentialImpact: 'Improve campaign efficiency and control'
        }});
    }}

    // Account structure optimization
    var analysis = results.crossCampaignAnalysis[0];
    if (analysis.accountOverview.pmaxSpendPercentage > 70) {{
        results.recommendations.push({{
            type: 'DIVERSIFY_STRATEGY',
            priority: 'MEDIUM',
            title: 'Diversify campaign strategy beyond Performance Max',
            pmaxPercentage: analysis.accountOverview.pmaxSpendPercentage,
            recommendation: 'Consider expanding Search campaigns for better control and testing',
            potentialImpact: 'Improve account resilience and testing capabilities'
        }});
    }} else if (analysis.accountOverview.pmaxSpendPercentage < 20) {{
        results.recommendations.push({{
            type: 'EXPAND_PERFORMANCE_MAX',
            priority: 'MEDIUM',
            title: 'Consider expanding Performance Max usage',
            pmaxPercentage: analysis.accountOverview.pmaxSpendPercentage,
            recommendation: 'Performance Max may provide opportunities for automated optimization',
            potentialImpact: 'Leverage machine learning for broader reach'
        }});
    }}
}}

function exportCrossCampaignResults() {{
    var summary = {{
        executionDate: new Date().toISOString(),
        dateRange: dateRange,
        pmaxCampaignsAnalyzed: results.performanceMaxData.length,
        searchCampaignsAnalyzed: results.searchCampaignData.length,
        searchTermOverlaps: results.searchTermOverlap.length,
        totalConflicts: results.conflictAnalysis.totalConflicts,
        recommendationsGenerated: results.recommendations.length,
        accountAnalysis: results.crossCampaignAnalysis[0]
    }};

    Logger.log("=== Cross-Campaign Analysis Summary ===");
    Logger.log("Performance Max campaigns: " + summary.pmaxCampaignsAnalyzed);
    Logger.log("Search campaigns: " + summary.searchCampaignsAnalyzed);
    Logger.log("Search term overlaps: " + summary.searchTermOverlaps);
    Logger.log("Total conflicts identified: " + summary.totalConflicts);
    Logger.log("Recommendations generated: " + summary.recommendationsGenerated);
    Logger.log("Performance Max spend %: " + summary.accountAnalysis.accountOverview.pmaxSpendPercentage.toFixed(1) + "%");
    Logger.log("Search spend %: " + summary.accountAnalysis.accountOverview.searchSpendPercentage.toFixed(1) + "%");

    // Export detailed cross-campaign analysis
    Logger.log("Cross-campaign analysis results ready for export");
}}
        '''.strip()

        return script

    def process_results(self, results: Dict[str, Any]) -> ScriptResult:
        """Process the results from cross-campaign analysis script execution."""
        status = ScriptStatus.COMPLETED.value
        errors = []
        warnings = []

        rows_processed = results.get("rows_processed", 0)
        changes_made = 0  # Cross-campaign analysis is read-only

        if results.get("success", False):
            if rows_processed == 0:
                warnings.append("No campaign data found for cross-campaign analysis")
        else:
            status = ScriptStatus.FAILED.value
            errors.append("Cross-campaign analysis script execution failed")

        details = {
            "script_type": "performance_max_cross_campaign",
            "pmax_campaigns_analyzed": results.get("details", {}).get(
                "pmax_campaigns_analyzed", 0
            ),
            "search_campaigns_analyzed": results.get("details", {}).get(
                "search_campaigns_analyzed", 0
            ),
            "search_term_overlaps": results.get("details", {}).get(
                "search_term_overlaps", 0
            ),
            "conflicts_identified": results.get("details", {}).get(
                "conflicts_identified", 0
            ),
            "budget_analysis_performed": results.get("details", {}).get(
                "budget_analysis_performed", False
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
