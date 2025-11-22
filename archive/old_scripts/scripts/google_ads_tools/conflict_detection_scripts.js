/**
 * Google Ads Scripts for Automated Conflict Detection System
 * 
 * This script implements real-time automated detection of:
 * - Positive/negative keyword conflicts
 * - Cross-campaign keyword conflicts  
 * - Campaign functionality issues
 * - Geographic targeting conflicts
 * 
 * Based on PaidSearchNav Issue #464
 */

// Configuration constants
const CONFIG = {
  // Email settings for alerts
  EMAIL_RECIPIENTS: {{EMAIL_RECIPIENTS}},
  
  // S3 settings for report storage
  S3_BUCKET: '{{S3_BUCKET}}',
  
  // Detection thresholds
  THRESHOLDS: {{DETECTION_THRESHOLDS}},
  
  // Report settings
  REPORT_RETENTION_DAYS: {{REPORT_RETENTION_DAYS}},
  MAX_CONFLICTS_PER_EMAIL: {{MAX_CONFLICTS_PER_EMAIL}},
};

/**
 * Main function to run conflict detection analysis
 */
function main() {
  console.log('🔍 Starting Automated Conflict Detection System');
  console.log('='.repeat(60));
  
  try {
    // Initialize conflict detection results
    const conflictResults = {
      positiveNegativeConflicts: [],
      crossCampaignConflicts: [],
      functionalityIssues: [],
      geographicConflicts: [],
      performanceImpacts: [],
      timestamp: new Date().toISOString(),
    };
    
    // Run conflict detection modules
    conflictResults.positiveNegativeConflicts = detectPositiveNegativeConflicts();
    conflictResults.crossCampaignConflicts = detectCrossCampaignConflicts();
    conflictResults.functionalityIssues = validateCampaignFunctionality();
    conflictResults.geographicConflicts = detectGeographicConflicts();
    
    // Calculate performance impacts
    conflictResults.performanceImpacts = calculatePerformanceImpacts(conflictResults);
    
    // Generate reports and alerts
    const reportSummary = generateConflictReport(conflictResults);
    sendConflictAlerts(conflictResults, reportSummary);
    
    // Store results for historical tracking
    storeConflictResults(conflictResults);
    
    console.log(`✅ Conflict detection completed. Found ${getTotalConflicts(conflictResults)} issues.`);
    
  } catch (error) {
    console.error(`❌ Conflict detection failed: ${error.message}`);
    sendErrorAlert(error);
  }
}

/**
 * Detect conflicts between positive keywords and negative keyword lists
 */
function detectPositiveNegativeConflicts() {
  console.log('🚫 Detecting positive/negative keyword conflicts...');
  
  const conflicts = [];
  
  try {
    const negativeKeywordLists = getNegativeKeywordLists();
    
    // Get all campaigns with error handling
    const campaignIterator = AdsApp.campaigns()
      .withCondition('CampaignStatus = ENABLED')
      .get();
      
    while (campaignIterator.hasNext()) {
      try {
        const campaign = campaignIterator.next();
        
        // Check campaign-level negative keywords
        const campaignConflicts = checkCampaignNegativeConflicts(campaign, negativeKeywordLists);
        conflicts.push(...campaignConflicts);
        
        // Check ad group level conflicts with error handling
        try {
          const adGroupIterator = campaign.adGroups()
            .withCondition('AdGroupStatus = ENABLED')
            .get();
            
          while (adGroupIterator.hasNext()) {
            try {
              const adGroup = adGroupIterator.next();
              const adGroupConflicts = checkAdGroupNegativeConflicts(adGroup, negativeKeywordLists);
              conflicts.push(...adGroupConflicts);
            } catch (adGroupError) {
              console.log(`Warning: Error processing ad group: ${adGroupError.message}`);
              continue;
            }
          }
        } catch (adGroupIteratorError) {
          console.log(`Warning: Error getting ad groups for campaign ${campaign.getName()}: ${adGroupIteratorError.message}`);
          continue;
        }
      } catch (campaignError) {
        console.log(`Warning: Error processing campaign: ${campaignError.message}`);
        continue;
      }
    }
  } catch (error) {
    console.error(`Error in detectPositiveNegativeConflicts: ${error.message}`);
    // Return partial results instead of failing completely
  }
  
  console.log(`   Found ${conflicts.length} positive/negative conflicts`);
  return conflicts;
}

/**
 * Check for conflicts between campaign keywords and negative lists
 */
function checkCampaignNegativeConflicts(campaign, negativeKeywordLists) {
  const conflicts = [];
  
  // Get campaign keywords
  const keywordIterator = campaign.keywords()
    .withCondition('KeywordStatus = ENABLED')
    .get();
    
  while (keywordIterator.hasNext()) {
    const keyword = keywordIterator.next();
    const keywordText = keyword.getText().toLowerCase();
    const matchType = keyword.getMatchType();
    
    // Check against account-level negative lists
    for (const negList of negativeKeywordLists) {
      const negativeIterator = negList.negativeKeywords().get();
      
      while (negativeIterator.hasNext()) {
        const negativeKeyword = negativeIterator.next();
        const conflict = checkKeywordConflict(keyword, negativeKeyword, campaign.getName());
        
        if (conflict) {
          conflicts.push({
            type: 'POSITIVE_NEGATIVE_CONFLICT',
            severity: calculateConflictSeverity(keyword, negativeKeyword),
            keyword: keywordText,
            keywordMatchType: matchType,
            negativeKeyword: negativeKeyword.getText(),
            negativeMatchType: negativeKeyword.getMatchType(),
            campaign: campaign.getName(),
            adGroup: null,
            negativeList: negList.getName(),
            level: 'CAMPAIGN',
            estimatedImpact: estimateConflictImpact(keyword),
            detectedAt: new Date().toISOString(),
          });
        }
      }
    }
    
    // Check against campaign-level negative keywords
    const campaignNegatives = campaign.negativeKeywords().get();
    while (campaignNegatives.hasNext()) {
      const negativeKeyword = campaignNegatives.next();
      const conflict = checkKeywordConflict(keyword, negativeKeyword, campaign.getName());
      
      if (conflict) {
        conflicts.push({
          type: 'POSITIVE_NEGATIVE_CONFLICT',
          severity: calculateConflictSeverity(keyword, negativeKeyword),
          keyword: keywordText,
          keywordMatchType: matchType,
          negativeKeyword: negativeKeyword.getText(),
          negativeMatchType: negativeKeyword.getMatchType(),
          campaign: campaign.getName(),
          adGroup: null,
          negativeList: 'Campaign Level',
          level: 'CAMPAIGN',
          estimatedImpact: estimateConflictImpact(keyword),
          detectedAt: new Date().toISOString(),
        });
      }
    }
  }
  
  return conflicts;
}

/**
 * Check for conflicts at ad group level
 */
function checkAdGroupNegativeConflicts(adGroup, negativeKeywordLists) {
  const conflicts = [];
  
  const keywordIterator = adGroup.keywords()
    .withCondition('KeywordStatus = ENABLED')
    .get();
    
  while (keywordIterator.hasNext()) {
    const keyword = keywordIterator.next();
    
    // Check against ad group negative keywords
    const adGroupNegatives = adGroup.negativeKeywords().get();
    while (adGroupNegatives.hasNext()) {
      const negativeKeyword = adGroupNegatives.next();
      const conflict = checkKeywordConflict(keyword, negativeKeyword, adGroup.getCampaign().getName());
      
      if (conflict) {
        conflicts.push({
          type: 'POSITIVE_NEGATIVE_CONFLICT',
          severity: calculateConflictSeverity(keyword, negativeKeyword),
          keyword: keyword.getText().toLowerCase(),
          keywordMatchType: keyword.getMatchType(),
          negativeKeyword: negativeKeyword.getText(),
          negativeMatchType: negativeKeyword.getMatchType(),
          campaign: adGroup.getCampaign().getName(),
          adGroup: adGroup.getName(),
          negativeList: 'Ad Group Level',
          level: 'AD_GROUP',
          estimatedImpact: estimateConflictImpact(keyword),
          detectedAt: new Date().toISOString(),
        });
      }
    }
  }
  
  return conflicts;
}

/**
 * Check if a positive keyword conflicts with a negative keyword
 */
function checkKeywordConflict(positiveKeyword, negativeKeyword, campaignName) {
  const positiveText = positiveKeyword.getText().toLowerCase().replace(/[\[\]"]/g, '');
  const negativeText = negativeKeyword.getText().toLowerCase().replace(/[\[\]"]/g, '');
  const positiveMatchType = positiveKeyword.getMatchType();
  const negativeMatchType = negativeKeyword.getMatchType();
  
  // Handle different match type combinations
  if (negativeMatchType === 'EXACT') {
    return positiveText === negativeText;
  }
  
  if (negativeMatchType === 'PHRASE') {
    return positiveText.includes(negativeText);
  }
  
  if (negativeMatchType === 'BROAD') {
    // For broad match negatives, check if any words overlap
    const positiveWords = positiveText.split(' ');
    const negativeWords = negativeText.split(' ');
    
    return negativeWords.every(negWord => 
      positiveWords.some(posWord => posWord.includes(negWord) || negWord.includes(posWord))
    );
  }
  
  return false;
}

/**
 * Detect cross-campaign keyword conflicts (same keywords in multiple campaigns)
 */
function detectCrossCampaignConflicts() {
  console.log('⚔️ Detecting cross-campaign keyword conflicts...');
  
  const conflicts = [];
  const keywordMap = new Map(); // keyword -> [campaign info]
  
  // Build keyword map across all campaigns
  const campaignIterator = AdsApp.campaigns()
    .withCondition('CampaignStatus = ENABLED')
    .get();
    
  while (campaignIterator.hasNext()) {
    const campaign = campaignIterator.next();
    
    const keywordIterator = campaign.keywords()
      .withCondition('KeywordStatus = ENABLED')
      .get();
      
    while (keywordIterator.hasNext()) {
      const keyword = keywordIterator.next();
      const normalizedText = normalizeKeyword(keyword.getText());
      
      if (!keywordMap.has(normalizedText)) {
        keywordMap.set(normalizedText, []);
      }
      
      keywordMap.get(normalizedText).push({
        keyword: keyword,
        campaign: campaign,
        adGroup: keyword.getAdGroup(),
        bid: keyword.bidding().getCpc(),
        qualityScore: keyword.getQualityScore(),
        stats: getKeywordStats(keyword),
      });
    }
  }
  
  // Find conflicts (keywords in multiple campaigns)
  for (const [keywordText, campaignInfos] of keywordMap.entries()) {
    if (campaignInfos.length > 1) {
      conflicts.push({
        type: 'CROSS_CAMPAIGN_CONFLICT',
        severity: calculateCrossCampaignSeverity(campaignInfos),
        keyword: keywordText,
        campaigns: campaignInfos.map(info => ({
          name: info.campaign.getName(),
          adGroup: info.adGroup.getName(),
          bid: info.bid,
          qualityScore: info.qualityScore,
          stats: info.stats,
        })),
        bidCompetition: calculateBidCompetition(campaignInfos),
        estimatedWastedSpend: estimateWastedSpend(campaignInfos),
        detectedAt: new Date().toISOString(),
      });
    }
  }
  
  console.log(`   Found ${conflicts.length} cross-campaign conflicts`);
  return conflicts;
}

/**
 * Validate campaign functionality (landing pages, targeting consistency)
 */
function validateCampaignFunctionality() {
  console.log('🔧 Validating campaign functionality...');
  
  const issues = [];
  
  const campaignIterator = AdsApp.campaigns()
    .withCondition('CampaignStatus = ENABLED')
    .get();
    
  while (campaignIterator.hasNext()) {
    const campaign = campaignIterator.next();
    
    // Check landing page accessibility
    const landingPageIssues = validateLandingPages(campaign);
    issues.push(...landingPageIssues);
    
    // Check targeting consistency
    const targetingIssues = validateTargetingConsistency(campaign);
    issues.push(...targetingIssues);
    
    // Check budget allocation conflicts
    const budgetIssues = validateBudgetAllocation(campaign);
    issues.push(...budgetIssues);
  }
  
  console.log(`   Found ${issues.length} functionality issues`);
  return issues;
}

/**
 * Detect geographic targeting conflicts
 */
function detectGeographicConflicts() {
  console.log('🗺️ Detecting geographic targeting conflicts...');
  
  const conflicts = [];
  
  const campaignIterator = AdsApp.campaigns()
    .withCondition('CampaignStatus = ENABLED')
    .get();
    
  while (campaignIterator.hasNext()) {
    const campaign = campaignIterator.next();
    
    // Get campaign targeting
    const targetedLocations = getTargetedLocations(campaign);
    const excludedLocations = getExcludedLocations(campaign);
    
    // Check for location-specific keyword conflicts
    const locationConflicts = checkLocationKeywordConflicts(campaign, targetedLocations, excludedLocations);
    conflicts.push(...locationConflicts);
    
    // Check for overlapping location targeting
    const overlapConflicts = checkLocationOverlaps(campaign, targetedLocations);
    conflicts.push(...overlapConflicts);
  }
  
  console.log(`   Found ${conflicts.length} geographic conflicts`);
  return conflicts;
}

/**
 * Calculate performance impact of detected conflicts
 */
function calculatePerformanceImpacts(conflictResults) {
  console.log('📊 Calculating performance impacts...');
  
  const impacts = [];
  
  // Calculate impact for each conflict type
  for (const conflict of conflictResults.positiveNegativeConflicts) {
    impacts.push(calculatePositiveNegativeImpact(conflict));
  }
  
  for (const conflict of conflictResults.crossCampaignConflicts) {
    impacts.push(calculateCrossCampaignImpact(conflict));
  }
  
  for (const issue of conflictResults.functionalityIssues) {
    impacts.push(calculateFunctionalityImpact(issue));
  }
  
  return impacts;
}

/**
 * Helper functions for conflict detection
 */

function getNegativeKeywordLists() {
  const lists = [];
  
  try {
    const listIterator = AdsApp.negativeKeywordLists().get();
    
    while (listIterator.hasNext()) {
      try {
        lists.push(listIterator.next());
      } catch (listError) {
        console.log(`Warning: Error processing negative keyword list: ${listError.message}`);
        continue;
      }
    }
  } catch (error) {
    console.error(`Error getting negative keyword lists: ${error.message}`);
  }
  
  return lists;
}

function normalizeKeyword(keywordText) {
  return keywordText.toLowerCase()
    .replace(/[\[\]"]/g, '') // Remove match type brackets/quotes
    .trim();
}

function getKeywordStats(keyword) {
  const stats = keyword.getStatsFor('LAST_30_DAYS');
  return {
    clicks: stats.getClicks(),
    impressions: stats.getImpressions(),
    cost: stats.getCost(),
    conversions: stats.getConversions(),
    ctr: stats.getCtr(),
    averageCpc: stats.getAverageCpc(),
  };
}

function calculateConflictSeverity(positiveKeyword, negativeKeyword) {
  const stats = getKeywordStats(positiveKeyword);
  
  if (stats.cost > CONFIG.THRESHOLDS.HIGH_COST_THRESHOLD && stats.conversions === 0) {
    return 'HIGH';
  } else if (stats.clicks > CONFIG.THRESHOLDS.MIN_CLICKS_FOR_ANALYSIS) {
    return 'MEDIUM';
  } else {
    return 'LOW';
  }
}

function calculateCrossCampaignSeverity(campaignInfos) {
  const totalCost = campaignInfos.reduce((sum, info) => sum + info.stats.cost, 0);
  const maxBidDiff = Math.max(...campaignInfos.map(info => info.bid)) - 
                    Math.min(...campaignInfos.map(info => info.bid));
  
  if (totalCost > 100 && maxBidDiff > CONFIG.THRESHOLDS.BID_COMPETITION_THRESHOLD) {
    return 'HIGH';
  } else if (totalCost > 50 || maxBidDiff > 0.05) {
    return 'MEDIUM';
  } else {
    return 'LOW';
  }
}

function calculateBidCompetition(campaignInfos) {
  const bids = campaignInfos.map(info => info.bid);
  const maxBid = Math.max(...bids);
  const minBid = Math.min(...bids);
  
  return {
    maxBid: maxBid,
    minBid: minBid,
    difference: maxBid - minBid,
    competitionLevel: (maxBid - minBid) / maxBid,
  };
}

function estimateConflictImpact(keyword) {
  const stats = getKeywordStats(keyword);
  
  return {
    blockedImpressions: Math.round(stats.impressions * 0.8), // Estimate 80% blocked
    lostClicks: Math.round(stats.clicks * 0.8),
    wastedSpend: stats.cost * 0.8,
    lostConversions: stats.conversions * 0.8,
  };
}

function estimateWastedSpend(campaignInfos) {
  // Estimate wasted spend from internal competition
  const totalSpend = campaignInfos.reduce((sum, info) => sum + info.stats.cost, 0);
  const competitionFactor = Math.min(campaignInfos.length * 0.15, 0.5); // 15% per competing campaign, max 50%
  
  return totalSpend * competitionFactor;
}

/**
 * Landing page validation
 */
function validateLandingPages(campaign) {
  const issues = [];
  
  const adIterator = campaign.ads()
    .withCondition('AdStatus = ENABLED')
    .get();
    
  while (adIterator.hasNext()) {
    const ad = adIterator.next();
    const finalUrl = ad.urls().getFinalUrl();
    
    if (finalUrl) {
      try {
        // Note: Google Ads Scripts have limited HTTP capabilities
        // In practice, this would need to be implemented differently
        const urlCheck = validateUrl(finalUrl);
        
        if (!urlCheck.isAccessible) {
          issues.push({
            type: 'LANDING_PAGE_ISSUE',
            severity: 'HIGH',
            campaign: campaign.getName(),
            adGroup: ad.getAdGroup().getName(),
            ad: ad.getHeadlinePart1(),
            url: finalUrl,
            issue: urlCheck.issue,
            detectedAt: new Date().toISOString(),
          });
        }
      } catch (error) {
        // Log URL validation errors
        console.log(`Warning: Could not validate URL ${finalUrl}: ${error.message}`);
      }
    }
  }
  
  return issues;
}

function validateUrl(url) {
  // Simplified URL validation - in practice this would need external service
  try {
    new URL(url);
    return { isAccessible: true };
  } catch (error) {
    return { 
      isAccessible: false, 
      issue: 'Invalid URL format' 
    };
  }
}

function validateTargetingConsistency(campaign) {
  const issues = [];
  const campaignName = campaign.getName().toLowerCase();
  
  // Check if location targeting matches campaign name intent
  const targetedLocations = getTargetedLocations(campaign);
  
  // Extract location indicators from campaign name
  const locationKeywords = extractLocationKeywords(campaignName);
  
  if (locationKeywords.length > 0 && targetedLocations.length > 0) {
    const hasMatchingLocation = targetedLocations.some(location => 
      locationKeywords.some(keyword => 
        location.getName().toLowerCase().includes(keyword)
      )
    );
    
    if (!hasMatchingLocation) {
      issues.push({
        type: 'TARGETING_CONSISTENCY_ISSUE',
        severity: 'MEDIUM',
        campaign: campaign.getName(),
        issue: 'Campaign name suggests location targeting but no matching locations found',
        expectedLocations: locationKeywords,
        actualLocations: targetedLocations.map(loc => loc.getName()),
        detectedAt: new Date().toISOString(),
      });
    }
  }
  
  return issues;
}

function validateBudgetAllocation(campaign) {
  const issues = [];
  
  // Check for budget competition indicators
  const budget = campaign.getBudget();
  const spent = campaign.getStatsFor('LAST_30_DAYS').getCost();
  const utilization = spent / (budget.getAmount() * 30); // Rough daily spend vs budget
  
  if (utilization > 0.95) {
    issues.push({
      type: 'BUDGET_ALLOCATION_ISSUE',
      severity: 'HIGH',
      campaign: campaign.getName(),
      issue: 'Campaign consistently hitting budget limit',
      budgetUtilization: utilization,
      suggestion: 'Review budget allocation or reduce competing campaigns',
      detectedAt: new Date().toISOString(),
    });
  }
  
  return issues;
}

/**
 * Geographic conflict detection helpers
 */
function getTargetedLocations(campaign) {
  const locations = [];
  const locationIterator = campaign.targeting().targetedLocations().get();
  
  while (locationIterator.hasNext()) {
    locations.push(locationIterator.next());
  }
  
  return locations;
}

function getExcludedLocations(campaign) {
  const locations = [];
  const locationIterator = campaign.targeting().excludedLocations().get();
  
  while (locationIterator.hasNext()) {
    locations.push(locationIterator.next());
  }
  
  return locations;
}

function checkLocationKeywordConflicts(campaign, targetedLocations, excludedLocations) {
  const conflicts = [];
  
  // Get campaign keywords
  const keywordIterator = campaign.keywords()
    .withCondition('KeywordStatus = ENABLED')
    .get();
    
  while (keywordIterator.hasNext()) {
    const keyword = keywordIterator.next();
    const keywordText = keyword.getText().toLowerCase();
    
    // Check if keyword contains location terms that conflict with targeting
    const keywordLocations = extractLocationKeywords(keywordText);
    
    for (const keywordLocation of keywordLocations) {
      // Check if keyword location is excluded
      const isExcluded = excludedLocations.some(loc => 
        loc.getName().toLowerCase().includes(keywordLocation)
      );
      
      if (isExcluded) {
        conflicts.push({
          type: 'GEOGRAPHIC_CONFLICT',
          severity: 'HIGH',
          campaign: campaign.getName(),
          keyword: keywordText,
          issue: 'Keyword contains location term that is excluded from targeting',
          keywordLocation: keywordLocation,
          excludedLocation: excludedLocations.find(loc => 
            loc.getName().toLowerCase().includes(keywordLocation)
          ).getName(),
          detectedAt: new Date().toISOString(),
        });
      }
    }
  }
  
  return conflicts;
}

function checkLocationOverlaps(campaign, targetedLocations) {
  // This would check for overlapping geographic targeting
  // between campaigns competing for same audiences
  return []; // Simplified for this implementation
}

function extractLocationKeywords(text) {
  // Extract location-related terms from text
  const locationPatterns = [
    'dallas', 'houston', 'austin', 'san antonio', 'fort worth',
    'plano', 'arlington', 'garland', 'irving', 'frisco',
    'texas', 'tx', 'near me', 'nearby', 'local'
  ];
  
  return locationPatterns.filter(pattern => text.includes(pattern));
}

/**
 * Performance impact calculation functions
 */
function calculatePositiveNegativeImpact(conflict) {
  return {
    type: 'POSITIVE_NEGATIVE_IMPACT',
    conflictId: generateConflictId(conflict),
    estimatedDailyCost: conflict.estimatedImpact.wastedSpend / 30,
    estimatedMonthlyLoss: conflict.estimatedImpact.wastedSpend,
    blockedImpressions: conflict.estimatedImpact.blockedImpressions,
    lostConversions: conflict.estimatedImpact.lostConversions,
    severity: conflict.severity,
  };
}

function calculateCrossCampaignImpact(conflict) {
  return {
    type: 'CROSS_CAMPAIGN_IMPACT',
    conflictId: generateConflictId(conflict),
    estimatedWastedSpend: conflict.estimatedWastedSpend,
    bidInflation: conflict.bidCompetition.difference,
    affectedCampaigns: conflict.campaigns.length,
    severity: conflict.severity,
  };
}

function calculateFunctionalityImpact(issue) {
  // Estimate impact based on issue type
  let estimatedImpact = 0;
  
  switch (issue.type) {
    case 'LANDING_PAGE_ISSUE':
      estimatedImpact = 500; // High impact for broken landing pages
      break;
    case 'TARGETING_CONSISTENCY_ISSUE':
      estimatedImpact = 200; // Medium impact for targeting issues
      break;
    case 'BUDGET_ALLOCATION_ISSUE':
      estimatedImpact = 300; // Medium-high impact for budget issues
      break;
  }
  
  return {
    type: 'FUNCTIONALITY_IMPACT',
    issueId: generateConflictId(issue),
    estimatedMonthlyLoss: estimatedImpact,
    issueType: issue.type,
    severity: issue.severity,
  };
}

/**
 * Report generation and alerting
 */
function generateConflictReport(conflictResults) {
  const totalConflicts = getTotalConflicts(conflictResults);
  const highSeverityCount = getHighSeverityCount(conflictResults);
  const totalEstimatedLoss = calculateTotalEstimatedLoss(conflictResults);
  
  const reportSummary = {
    timestamp: conflictResults.timestamp,
    totalConflicts: totalConflicts,
    highSeverityConflicts: highSeverityCount,
    estimatedMonthlyLoss: totalEstimatedLoss,
    conflictBreakdown: {
      positiveNegative: conflictResults.positiveNegativeConflicts.length,
      crossCampaign: conflictResults.crossCampaignConflicts.length,
      functionality: conflictResults.functionalityIssues.length,
      geographic: conflictResults.geographicConflicts.length,
    },
  };
  
  // Generate detailed CSV report
  const csvReport = generateCsvReport(conflictResults);
  
  // Store reports (this would typically upload to cloud storage)
  storeReport(csvReport, `conflict_report_${new Date().toISOString().split('T')[0]}.csv`);
  
  return reportSummary;
}

function sendConflictAlerts(conflictResults, reportSummary) {
  if (reportSummary.highSeverityConflicts > 0) {
    const alertSubject = `🚨 High Priority Google Ads Conflicts Detected - ${reportSummary.highSeverityConflicts} issues`;
    const alertBody = generateAlertEmail(conflictResults, reportSummary);
    
    MailApp.sendEmail({
      to: CONFIG.EMAIL_RECIPIENTS.join(','),
      subject: alertSubject,
      htmlBody: alertBody,
    });
    
    console.log(`📧 Alert email sent for ${reportSummary.highSeverityConflicts} high-priority conflicts`);
  }
  
  if (reportSummary.totalConflicts > 0) {
    console.log(`📊 Daily report generated with ${reportSummary.totalConflicts} total conflicts`);
  }
}

function generateAlertEmail(conflictResults, reportSummary) {
  let html = `
    <h2>🚨 Google Ads Conflict Detection Alert</h2>
    <p><strong>Detection Time:</strong> ${new Date(reportSummary.timestamp).toLocaleString()}</p>
    
    <h3>📊 Summary</h3>
    <ul>
      <li><strong>Total Conflicts:</strong> ${reportSummary.totalConflicts}</li>
      <li><strong>High Severity:</strong> ${reportSummary.highSeverityConflicts}</li>
      <li><strong>Estimated Monthly Loss:</strong> $${reportSummary.estimatedMonthlyLoss.toFixed(2)}</li>
    </ul>
    
    <h3>🔍 Conflict Breakdown</h3>
    <ul>
      <li><strong>Positive/Negative Conflicts:</strong> ${reportSummary.conflictBreakdown.positiveNegative}</li>
      <li><strong>Cross-Campaign Conflicts:</strong> ${reportSummary.conflictBreakdown.crossCampaign}</li>
      <li><strong>Functionality Issues:</strong> ${reportSummary.conflictBreakdown.functionality}</li>
      <li><strong>Geographic Conflicts:</strong> ${reportSummary.conflictBreakdown.geographic}</li>
    </ul>
  `;
  
  // Add top high-severity conflicts
  html += '<h3>🚨 Top High-Severity Conflicts</h3><ul>';
  
  const highSeverityConflicts = getAllHighSeverityConflicts(conflictResults)
    .slice(0, CONFIG.MAX_CONFLICTS_PER_EMAIL);
    
  for (const conflict of highSeverityConflicts) {
    html += `<li><strong>${conflict.type}:</strong> ${formatConflictForEmail(conflict)}</li>`;
  }
  
  html += '</ul>';
  
  html += `
    <h3>📋 Next Steps</h3>
    <ol>
      <li>Review the detailed conflicts in the full report</li>
      <li>Prioritize high-severity conflicts for immediate resolution</li>
      <li>Implement recommended fixes using bulk actions</li>
      <li>Monitor performance impact after changes</li>
    </ol>
    
    <p><em>This alert was generated by the PaidSearchNav Automated Conflict Detection System.</em></p>
  `;
  
  return html;
}

function generateCsvReport(conflictResults) {
  let csv = 'Type,Severity,Campaign,AdGroup,Keyword,Issue,EstimatedImpact,DetectedAt\n';
  
  // Add positive/negative conflicts
  for (const conflict of conflictResults.positiveNegativeConflicts) {
    csv += `"${conflict.type}","${conflict.severity}","${conflict.campaign}","${conflict.adGroup || ''}","${conflict.keyword}","Conflicts with negative: ${conflict.negativeKeyword}","$${conflict.estimatedImpact.wastedSpend.toFixed(2)}","${conflict.detectedAt}"\n`;
  }
  
  // Add cross-campaign conflicts
  for (const conflict of conflictResults.crossCampaignConflicts) {
    csv += `"${conflict.type}","${conflict.severity}","${conflict.campaigns.map(c => c.name).join('; ')}","","${conflict.keyword}","Competing in multiple campaigns","$${conflict.estimatedWastedSpend.toFixed(2)}","${conflict.detectedAt}"\n`;
  }
  
  // Add functionality issues
  for (const issue of conflictResults.functionalityIssues) {
    csv += `"${issue.type}","${issue.severity}","${issue.campaign}","${issue.adGroup || ''}","","${issue.issue}","","${issue.detectedAt}"\n`;
  }
  
  // Add geographic conflicts
  for (const conflict of conflictResults.geographicConflicts) {
    csv += `"${conflict.type}","${conflict.severity}","${conflict.campaign}","","${conflict.keyword}","${conflict.issue}","","${conflict.detectedAt}"\n`;
  }
  
  return csv;
}

/**
 * Utility functions
 */
function getTotalConflicts(conflictResults) {
  return conflictResults.positiveNegativeConflicts.length +
         conflictResults.crossCampaignConflicts.length +
         conflictResults.functionalityIssues.length +
         conflictResults.geographicConflicts.length;
}

function getHighSeverityCount(conflictResults) {
  let count = 0;
  
  count += conflictResults.positiveNegativeConflicts.filter(c => c.severity === 'HIGH').length;
  count += conflictResults.crossCampaignConflicts.filter(c => c.severity === 'HIGH').length;
  count += conflictResults.functionalityIssues.filter(c => c.severity === 'HIGH').length;
  count += conflictResults.geographicConflicts.filter(c => c.severity === 'HIGH').length;
  
  return count;
}

function getAllHighSeverityConflicts(conflictResults) {
  const highSeverity = [];
  
  highSeverity.push(...conflictResults.positiveNegativeConflicts.filter(c => c.severity === 'HIGH'));
  highSeverity.push(...conflictResults.crossCampaignConflicts.filter(c => c.severity === 'HIGH'));
  highSeverity.push(...conflictResults.functionalityIssues.filter(c => c.severity === 'HIGH'));
  highSeverity.push(...conflictResults.geographicConflicts.filter(c => c.severity === 'HIGH'));
  
  return highSeverity;
}

function calculateTotalEstimatedLoss(conflictResults) {
  let total = 0;
  
  for (const impact of conflictResults.performanceImpacts) {
    if (impact.estimatedMonthlyLoss) {
      total += impact.estimatedMonthlyLoss;
    }
    if (impact.estimatedWastedSpend) {
      total += impact.estimatedWastedSpend;
    }
  }
  
  return total;
}

function formatConflictForEmail(conflict) {
  switch (conflict.type) {
    case 'POSITIVE_NEGATIVE_CONFLICT':
      return `Keyword "${conflict.keyword}" in ${conflict.campaign} conflicts with negative "${conflict.negativeKeyword}"`;
    case 'CROSS_CAMPAIGN_CONFLICT':
      return `Keyword "${conflict.keyword}" competing across ${conflict.campaigns.length} campaigns`;
    case 'LANDING_PAGE_ISSUE':
      return `Landing page issue in ${conflict.campaign}: ${conflict.issue}`;
    case 'GEOGRAPHIC_CONFLICT':
      return `Geographic conflict in ${conflict.campaign}: ${conflict.issue}`;
    default:
      return `${conflict.issue || 'Unknown conflict'}`;
  }
}

function generateConflictId(conflict) {
  const source = `${conflict.type}_${conflict.campaign || ''}_${conflict.keyword || ''}_${Date.now()}`;
  return source.replace(/[^a-zA-Z0-9]/g, '_').substring(0, 50);
}

function storeConflictResults(conflictResults) {
  // Store results for historical tracking
  // In practice, this would upload to cloud storage or database
  console.log(`📁 Storing conflict results: ${JSON.stringify(conflictResults).length} bytes`);
}

function storeReport(csvContent, filename) {
  // Store CSV report
  // In practice, this would upload to S3 or similar storage
  console.log(`📄 Storing report: ${filename} (${csvContent.length} bytes)`);
}

function sendErrorAlert(error) {
  const alertSubject = '❌ Google Ads Conflict Detection Script Error';
  const alertBody = `
    <h2>❌ Conflict Detection Script Error</h2>
    <p><strong>Error Time:</strong> ${new Date().toLocaleString()}</p>
    <p><strong>Error Message:</strong> ${error.message}</p>
    <p><strong>Stack Trace:</strong> <pre>${error.stack || 'Not available'}</pre></p>
    
    <p>Please check the script configuration and Google Ads account permissions.</p>
  `;
  
  try {
    MailApp.sendEmail({
      to: CONFIG.EMAIL_RECIPIENTS.join(','),
      subject: alertSubject,
      htmlBody: alertBody,
    });
  } catch (emailError) {
    console.error(`Failed to send error alert: ${emailError.message}`);
  }
}

// Export main function for testing
if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    main,
    detectPositiveNegativeConflicts,
    detectCrossCampaignConflicts,
    validateCampaignFunctionality,
    detectGeographicConflicts,
  };
}