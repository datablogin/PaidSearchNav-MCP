"""Local Keyword Expansion and Landing Page Optimization for Google Ads Scripts."""

import json
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from paidsearchnav_mcp.platforms.google.client import GoogleAdsClient

from .base import ScriptBase, ScriptConfig, ScriptResult, ScriptStatus, ScriptType
from .local_intent_optimization import StoreLocation

logger = logging.getLogger(__name__)


class KeywordExpansionType(Enum):
    """Types of local keyword expansion."""

    GEOGRAPHIC_MODIFIER = "geographic_modifier"
    DISTANCE_MODIFIER = "distance_modifier"
    LANDMARK_REFERENCE = "landmark_reference"
    COMPETITOR_REFERENCE = "competitor_reference"
    SEASONAL_MODIFIER = "seasonal_modifier"
    SERVICE_LOCATION = "service_location"


class LandingPageMatchType(Enum):
    """Types of landing page optimization matches."""

    STORE_SPECIFIC = "store_specific"
    CITY_SPECIFIC = "city_specific"
    SERVICE_SPECIFIC = "service_specific"
    PROMOTIONAL = "promotional"
    DEFAULT_FALLBACK = "default_fallback"


@dataclass
class KeywordOpportunity:
    """Represents a local keyword expansion opportunity."""

    base_keyword: str
    expanded_keyword: str
    expansion_type: KeywordExpansionType
    matched_stores: List[StoreLocation]
    search_volume_estimate: int
    competition_level: str
    suggested_bid: float
    confidence_score: float
    landing_page_recommendation: Optional[str] = None
    reasoning: str = ""


@dataclass
class LandingPageRecommendation:
    """Represents a landing page optimization recommendation."""

    search_term: str
    current_landing_page: str
    recommended_landing_page: str
    match_type: LandingPageMatchType
    matched_store: Optional[StoreLocation]
    confidence_score: float
    expected_improvement: Dict[str, float]
    reasoning: str


@dataclass
class LocalMarketOpportunity:
    """Represents a local market expansion opportunity."""

    market_identifier: str
    market_name: str
    opportunity_type: str
    search_volume: int
    competition_density: float
    nearest_store_distance: float
    market_penetration_score: float
    recommended_keywords: List[str]
    estimated_performance: Dict[str, float]


class LocalKeywordExpansionEngine(ScriptBase):
    """Engine for local keyword expansion and landing page optimization."""

    def __init__(self, client: GoogleAdsClient, config: ScriptConfig):
        super().__init__(client, config)
        self.store_locations: List[StoreLocation] = []
        self.geographic_modifiers = self._build_geographic_modifiers()
        self.competitor_keywords = self._build_competitor_keywords()
        self.seasonal_modifiers = self._build_seasonal_modifiers()

    def _build_geographic_modifiers(self) -> Dict[str, List[str]]:
        """Build geographic modifier lists for keyword expansion."""
        return {
            "cities": [
                "dallas",
                "san antonio",
                "houston",
                "austin",
                "fort worth",
                "plano",
                "garland",
                "irving",
                "arlington",
                "mesquite",
            ],
            "neighborhoods": [
                "downtown",
                "uptown",
                "midtown",
                "deep ellum",
                "bishop arts",
                "design district",
                "knox henderson",
                "lower greenville",
            ],
            "directions": [
                "north",
                "south",
                "east",
                "west",
                "northeast",
                "northwest",
                "southeast",
                "southwest",
                "northern",
                "southern",
                "eastern",
                "western",
            ],
            "proximity": [
                "near me",
                "nearby",
                "close to me",
                "around me",
                "local",
                "in my area",
                "close by",
                "within miles",
            ],
            "landmarks": [
                "mall",
                "airport",
                "stadium",
                "university",
                "hospital",
                "galleria",
                "centro",
                "legacy",
                "downtown",
                "plaza",
            ],
        }

    def _build_competitor_keywords(self) -> Dict[str, List[str]]:
        """Build competitor-related keyword modifiers."""
        return {
            "fitness": [
                "vs planet fitness",
                "better than la fitness",
                "alternative to 24 hour fitness",
                "compared to anytime fitness",
                "instead of gold's gym",
            ],
            "retail": [
                "vs walmart",
                "better than target",
                "alternative to costco",
                "compared to home depot",
                "instead of lowes",
            ],
            "restaurants": [
                "vs mcdonalds",
                "better than subway",
                "alternative to chipotle",
                "compared to panera",
                "instead of starbucks",
            ],
        }

    def _build_seasonal_modifiers(self) -> Dict[str, List[str]]:
        """Build seasonal and temporal modifiers."""
        return {
            "seasonal": [
                "summer",
                "winter",
                "spring",
                "fall",
                "holiday",
                "christmas",
                "new year",
                "valentine's day",
                "easter",
                "memorial day",
            ],
            "temporal": [
                "24 hours",
                "early morning",
                "late night",
                "weekend",
                "weekday",
                "open now",
                "open late",
                "24/7",
                "all day",
            ],
            "events": [
                "back to school",
                "graduation",
                "wedding season",
                "tax season",
                "black friday",
                "cyber monday",
                "labor day",
                "independence day",
            ],
        }

    def generate_script(self) -> str:
        """Generate Google Ads Script for local keyword expansion."""
        modifier_data_js = self._generate_modifier_data_js()
        expansion_config_js = self._generate_expansion_config_js()

        return f"""
/**
 * Local Keyword Expansion and Landing Page Optimization
 * Generated by PaidSearchNav Issue #468
 */

{modifier_data_js}

{expansion_config_js}

function main() {{
  console.log('🔍 Starting Local Keyword Expansion and Landing Page Optimization');
  console.log('=' * 100);

  try {{
    const results = {{
      keywordExpansions: [],
      landingPageOptimizations: [],
      marketOpportunities: [],
      competitiveKeywords: [],
      seasonalExpansions: [],
      performancePredictions: [],
      qualityScoreImprovements: [],
      timestamp: new Date().toISOString(),
    }};

    // Generate local keyword expansion opportunities
    console.log('📈 Generating local keyword expansion opportunities...');
    results.keywordExpansions = generateLocalKeywordExpansions();

    // Optimize landing page matches
    console.log('🔗 Optimizing landing page matches...');
    results.landingPageOptimizations = optimizeLandingPageMatches();

    // Identify market expansion opportunities
    console.log('🎯 Identifying market expansion opportunities...');
    results.marketOpportunities = identifyMarketOpportunities();

    // Generate competitive keyword variations
    console.log('⚔️ Generating competitive keyword variations...');
    results.competitiveKeywords = generateCompetitiveKeywords();

    // Create seasonal keyword expansions
    console.log('📅 Creating seasonal keyword expansions...');
    results.seasonalExpansions = generateSeasonalExpansions();

    // Predict performance for new keywords
    console.log('📊 Predicting performance for new keywords...');
    results.performancePredictions = predictKeywordPerformance(results.keywordExpansions);

    // Identify quality score improvement opportunities
    console.log('⭐ Identifying quality score improvements...');
    results.qualityScoreImprovements = identifyQualityScoreImprovements();

    // Generate comprehensive expansion report
    const expansionReport = generateExpansionReport(results);
    console.log('✅ Local keyword expansion analysis complete');

    return results;

  }} catch (error) {{
    console.error('❌ Local keyword expansion failed:', error);
    throw error;
  }}
}}

/**
 * Generate local keyword expansion opportunities
 */
function generateLocalKeywordExpansions() {{
  const expansions = [];

  // Get existing keywords from all campaigns
  const existingKeywords = getExistingKeywords();
  const baseKeywords = extractBaseKeywords(existingKeywords);

  console.log(`Found ${{baseKeywords.length}} base keywords for expansion`);

  for (const baseKeyword of baseKeywords) {{
    // Skip if keyword is already very location-specific
    if (isAlreadyLocationSpecific(baseKeyword)) {{
      continue;
    }}

    // Generate geographic expansions
    const geoExpansions = generateGeographicExpansions(baseKeyword);

    // Generate proximity expansions
    const proximityExpansions = generateProximityExpansions(baseKeyword);

    // Generate landmark expansions
    const landmarkExpansions = generateLandmarkExpansions(baseKeyword);

    // Generate directional expansions
    const directionalExpansions = generateDirectionalExpansions(baseKeyword);

    // Combine all expansions
    const allExpansions = [
      ...geoExpansions,
      ...proximityExpansions,
      ...landmarkExpansions,
      ...directionalExpansions
    ];

    // Filter and score expansions
    const qualifiedExpansions = filterAndScoreExpansions(baseKeyword, allExpansions);

    expansions.push(...qualifiedExpansions);
  }}

  // Remove duplicates and sort by opportunity score
  const uniqueExpansions = removeDuplicateKeywords(expansions);
  const sortedExpansions = uniqueExpansions.sort((a, b) => b.opportunityScore - a.opportunityScore);

  console.log(`Generated ${{sortedExpansions.length}} qualified keyword expansion opportunities`);
  return sortedExpansions.slice(0, CONFIG.MAX_KEYWORD_SUGGESTIONS);
}}

/**
 * Generate geographic variations of base keywords
 */
function generateGeographicExpansions(baseKeyword) {{
  const expansions = [];

  for (const city of GEOGRAPHIC_MODIFIERS.cities) {{
    // Before keyword: "dallas gym equipment"
    const beforeKeyword = `${{city}} ${{baseKeyword}}`;
    if (!keywordExists(beforeKeyword)) {{
      const expansion = createKeywordExpansion(
        baseKeyword,
        beforeKeyword,
        'geographic_modifier',
        city
      );
      if (expansion.opportunityScore >= CONFIG.MIN_OPPORTUNITY_SCORE) {{
        expansions.push(expansion);
      }}
    }}

    // After keyword: "gym equipment dallas"
    const afterKeyword = `${{baseKeyword}} ${{city}}`;
    if (!keywordExists(afterKeyword)) {{
      const expansion = createKeywordExpansion(
        baseKeyword,
        afterKeyword,
        'geographic_modifier',
        city
      );
      if (expansion.opportunityScore >= CONFIG.MIN_OPPORTUNITY_SCORE) {{
        expansions.push(expansion);
      }}
    }}

    // In city format: "gym equipment in dallas"
    const inCityKeyword = `${{baseKeyword}} in ${{city}}`;
    if (!keywordExists(inCityKeyword)) {{
      const expansion = createKeywordExpansion(
        baseKeyword,
        inCityKeyword,
        'geographic_modifier',
        city
      );
      if (expansion.opportunityScore >= CONFIG.MIN_OPPORTUNITY_SCORE) {{
        expansions.push(expansion);
      }}
    }}
  }}

  return expansions;
}}

/**
 * Generate proximity-based keyword variations
 */
function generateProximityExpansions(baseKeyword) {{
  const expansions = [];

  for (const proximityModifier of GEOGRAPHIC_MODIFIERS.proximity) {{
    const expandedKeyword = `${{baseKeyword}} ${{proximityModifier}}`;

    if (!keywordExists(expandedKeyword)) {{
      const expansion = createKeywordExpansion(
        baseKeyword,
        expandedKeyword,
        'distance_modifier',
        proximityModifier
      );

      // "Near me" terms typically have higher intent
      if (proximityModifier.includes('near me')) {{
        expansion.opportunityScore += 0.2;
        expansion.suggestedBid *= 1.3;
      }}

      if (expansion.opportunityScore >= CONFIG.MIN_OPPORTUNITY_SCORE) {{
        expansions.push(expansion);
      }}
    }}
  }}

  return expansions;
}}

/**
 * Generate landmark-based keyword variations
 */
function generateLandmarkExpansions(baseKeyword) {{
  const expansions = [];

  for (const landmark of GEOGRAPHIC_MODIFIERS.landmarks) {{
    // Near landmark format: "gym equipment near galleria"
    const nearLandmarkKeyword = `${{baseKeyword}} near ${{landmark}}`;

    if (!keywordExists(nearLandmarkKeyword)) {{
      const expansion = createKeywordExpansion(
        baseKeyword,
        nearLandmarkKeyword,
        'landmark_reference',
        landmark
      );

      if (expansion.opportunityScore >= CONFIG.MIN_OPPORTUNITY_SCORE) {{
        expansions.push(expansion);
      }}
    }}

    // By landmark format: "gym equipment by downtown"
    const byLandmarkKeyword = `${{baseKeyword}} by ${{landmark}}`;

    if (!keywordExists(byLandmarkKeyword)) {{
      const expansion = createKeywordExpansion(
        baseKeyword,
        byLandmarkKeyword,
        'landmark_reference',
        landmark
      );

      if (expansion.opportunityScore >= CONFIG.MIN_OPPORTUNITY_SCORE) {{
        expansions.push(expansion);
      }}
    }}
  }}

  return expansions;
}}

/**
 * Optimize landing page matches for search terms
 */
function optimizeLandingPageMatches() {{
  const optimizations = [];

  // Get search terms report with current landing pages
  const searchTermsReport = AdsApp.report(
    'SELECT SearchTerm, Impressions, Clicks, Conversions, ' +
    'CampaignName, AdGroupName, AdId, KeywordTextMatchingQuery ' +
    'FROM SEARCH_QUERY_PERFORMANCE_REPORT ' +
    'WHERE Impressions > ' + CONFIG.MIN_IMPRESSIONS + ' ' +
    'DURING LAST_' + CONFIG.LOOKBACK_DAYS + '_DAYS'
  );

  const searchTermsIterator = searchTermsReport.rows();

  while (searchTermsIterator.hasNext()) {{
    const row = searchTermsIterator.next();
    const searchTerm = row['SearchTerm'].toLowerCase();
    const campaignName = row['CampaignName'];
    const adGroupName = row['AdGroupName'];

    // Detect local intent in search term
    const localIntent = detectLocalIntentInSearchTerm(searchTerm);

    if (localIntent && localIntent.confidenceScore >= CONFIG.MIN_CONFIDENCE_SCORE) {{
      // Find the best matching store and landing page
      const bestMatch = findBestStoreMatch(localIntent);

      if (bestMatch && bestMatch.landingPage) {{
        // Get current landing page for this ad group
        const currentLandingPage = getCurrentLandingPage(campaignName, adGroupName);

        if (currentLandingPage && currentLandingPage !== bestMatch.landingPage) {{
          const optimization = {{
            searchTerm: searchTerm,
            campaignName: campaignName,
            adGroupName: adGroupName,
            currentLandingPage: currentLandingPage,
            recommendedLandingPage: bestMatch.landingPage,
            matchType: determineMatchType(localIntent, bestMatch),
            matchedStore: bestMatch.store,
            confidenceScore: bestMatch.confidence,
            localIntent: localIntent,

            // Performance data
            impressions: parseInt(row['Impressions']),
            clicks: parseInt(row['Clicks']),
            conversions: parseInt(row['Conversions']),

            // Expected improvement estimates
            expectedImprovements: {{
              conversionRateIncrease: estimateConversionRateImprovement(localIntent, bestMatch),
              qualityScoreImprovement: estimateQualityScoreImprovement(localIntent, bestMatch),
              storeVisitIncrease: estimateStoreVisitIncrease(localIntent, bestMatch),
            }},

            // Implementation details
            implementationPriority: calculateImplementationPriority(
              parseInt(row['Impressions']),
              parseInt(row['Clicks']),
              bestMatch.confidence
            ),

            reasoning: generateLandingPageReasoning(localIntent, bestMatch),
          }};

          optimizations.push(optimization);
        }}
      }}
    }}
  }}

  // Sort by implementation priority and expected impact
  return optimizations.sort((a, b) => {{
    return (b.expectedImprovements.conversionRateIncrease * b.confidenceScore) -
           (a.expectedImprovements.conversionRateIncrease * a.confidenceScore);
  }});
}}

/**
 * Identify market expansion opportunities
 */
function identifyMarketOpportunities() {{
  const opportunities = [];

  // Analyze search volume data by geographic region
  const geoReport = AdsApp.report(
    'SELECT CityCriteriaId, LocationType, Impressions, Clicks, ' +
    'SearchImpressionShare, AveragePosition ' +
    'FROM GEO_PERFORMANCE_REPORT ' +
    'WHERE Impressions > 0 ' +
    'DURING LAST_' + CONFIG.LOOKBACK_DAYS + '_DAYS'
  );

  const marketData = {{}};
  const geoIterator = geoReport.rows();

  while (geoIterator.hasNext()) {{
    const row = geoIterator.next();
    const cityId = row['CityCriteriaId'];
    const cityName = getCityName(cityId);

    if (!marketData[cityId]) {{
      marketData[cityId] = {{
        cityName: cityName,
        totalImpressions: 0,
        totalClicks: 0,
        searchImpressionShare: 0,
        avgPosition: 0,
        entryCount: 0,
      }};
    }}

    const market = marketData[cityId];
    market.totalImpressions += parseInt(row['Impressions']);
    market.totalClicks += parseInt(row['Clicks']);
    market.searchImpressionShare += parseFloat(row['SearchImpressionShare']);
    market.avgPosition += parseFloat(row['AveragePosition']);
    market.entryCount += 1;
  }}

  // Calculate opportunity scores for each market
  for (const [cityId, market] of Object.entries(marketData)) {{
    // Calculate average metrics
    market.avgSearchImpressionShare = market.searchImpressionShare / market.entryCount;
    market.avgPosition = market.avgPosition / market.entryCount;

    // Find nearest store
    const nearestStore = findNearestStoreToCity(cityId);
    const distanceToStore = nearestStore ? calculateDistanceToCity(nearestStore, cityId) : Infinity;

    // Calculate opportunity score based on multiple factors
    const opportunityScore = calculateMarketOpportunityScore({{
      impressions: market.totalImpressions,
      clicks: market.totalClicks,
      impressionShare: market.avgSearchImpressionShare,
      position: market.avgPosition,
      distanceToStore: distanceToStore,
      competitionLevel: estimateCompetitionLevel(cityId),
    }});

    if (opportunityScore >= CONFIG.MIN_MARKET_OPPORTUNITY_SCORE) {{
      // Generate keyword recommendations for this market
      const recommendedKeywords = generateMarketSpecificKeywords(market.cityName);

      opportunities.push({{
        marketIdentifier: cityId,
        marketName: market.cityName,
        opportunityType: categorizeMarketOpportunity(opportunityScore, distanceToStore),
        searchVolume: market.totalImpressions,
        competitionDensity: estimateCompetitionLevel(cityId),
        nearestStoreDistance: distanceToStore,
        marketPenetrationScore: market.avgSearchImpressionShare,
        opportunityScore: opportunityScore,
        recommendedKeywords: recommendedKeywords,

        // Performance estimates
        estimatedPerformance: {{
          expectedImpressions: market.totalImpressions * 1.5,
          expectedClicks: market.totalClicks * 1.3,
          expectedConversions: market.totalClicks * 0.05,
          estimatedCost: market.totalClicks * 2.5,
        }},

        // Implementation recommendations
        implementationStrategy: generateMarketImplementationStrategy(
          market, nearestStore, opportunityScore
        ),
      }});
    }}
  }}

  return opportunities.sort((a, b) => b.opportunityScore - a.opportunityScore);
}}

/**
 * Generate competitive keyword variations
 */
function generateCompetitiveKeywords() {{
  const competitiveKeywords = [];

  // Get business category from store data
  const businessCategory = determineBusinessCategory(STORE_DATA);
  const competitorModifiers = COMPETITOR_KEYWORDS[businessCategory] || [];

  // Get high-performing existing keywords
  const topKeywords = getTopPerformingKeywords(20);

  for (const keyword of topKeywords) {{
    for (const competitorModifier of competitorModifiers) {{
      const competitiveKeyword = `${{keyword}} ${{competitorModifier}}`;

      if (!keywordExists(competitiveKeyword)) {{
        const opportunity = {{
          baseKeyword: keyword,
          expandedKeyword: competitiveKeyword,
          expansionType: 'competitor_reference',
          competitorReference: competitorModifier,

          // Estimate performance based on base keyword
          searchVolumeEstimate: estimateCompetitiveSearchVolume(keyword, competitorModifier),
          competitionLevel: 'medium', // Competitive keywords usually have medium competition
          suggestedBid: calculateCompetitiveBid(keyword),

          opportunityScore: calculateCompetitiveOpportunityScore(keyword, competitorModifier),
          confidenceScore: 0.75, // Moderate confidence for competitive keywords

          reasoning: `Targets users comparing with competitors, high conversion intent`,
        }};

        if (opportunity.opportunityScore >= CONFIG.MIN_OPPORTUNITY_SCORE) {{
          competitiveKeywords.push(opportunity);
        }}
      }}
    }}
  }}

  return competitiveKeywords.sort((a, b) => b.opportunityScore - a.opportunityScore);
}}

/**
 * Generate seasonal keyword expansions
 */
function generateSeasonalExpansions() {{
  const seasonalExpansions = [];

  // Get current season/time period
  const currentSeason = getCurrentSeason();
  const relevantModifiers = getRelevantSeasonalModifiers(currentSeason);

  // Get base keywords for expansion
  const baseKeywords = getSeasonallyRelevantKeywords();

  for (const keyword of baseKeywords) {{
    for (const modifier of relevantModifiers) {{
      const seasonalKeyword = `${{keyword}} ${{modifier}}`;

      if (!keywordExists(seasonalKeyword)) {{
        const seasonalTrend = getSeasonalTrend(keyword, modifier);

        const expansion = {{
          baseKeyword: keyword,
          expandedKeyword: seasonalKeyword,
          expansionType: 'seasonal_modifier',
          seasonalModifier: modifier,

          searchVolumeEstimate: estimateSeasonalSearchVolume(keyword, modifier, seasonalTrend),
          competitionLevel: estimateSeasonalCompetition(modifier),
          suggestedBid: calculateSeasonalBid(keyword, seasonalTrend),

          // Seasonal-specific metrics
          seasonalTrend: seasonalTrend,
          peakMonths: getPeakMonths(modifier),
          trendStrength: seasonalTrend.strength,

          opportunityScore: calculateSeasonalOpportunityScore(keyword, modifier, seasonalTrend),
          confidenceScore: seasonalTrend.confidence,

          reasoning: `Seasonal opportunity for ${{modifier}}, trend strength: ${{seasonalTrend.strength}}`,
        }};

        if (expansion.opportunityScore >= CONFIG.MIN_OPPORTUNITY_SCORE) {{
          seasonalExpansions.push(expansion);
        }}
      }}
    }}
  }}

  return seasonalExpansions.sort((a, b) => b.trendStrength - a.trendStrength);
}}

/**
 * Predict performance for new keyword opportunities
 */
function predictKeywordPerformance(keywordExpansions) {{
  const predictions = [];

  for (const expansion of keywordExpansions) {{
    // Get historical performance of similar keywords
    const similarKeywords = findSimilarKeywords(expansion.expandedKeyword);
    const baselinePerformance = calculateBaselinePerformance(similarKeywords);

    // Adjust predictions based on expansion type and local factors
    const localFactors = calculateLocalPerformanceFactors(expansion);

    const prediction = {{
      keyword: expansion.expandedKeyword,
      expansionType: expansion.expansionType,

      // Performance predictions
      expectedImpressions: Math.round(baselinePerformance.impressions * localFactors.impressionMultiplier),
      expectedClicks: Math.round(baselinePerformance.clicks * localFactors.clickMultiplier),
      expectedConversions: Math.round(baselinePerformance.conversions * localFactors.conversionMultiplier),
      expectedCost: Math.round(baselinePerformance.cost * localFactors.costMultiplier * 100) / 100,

      // Calculated metrics
      expectedCTR: (baselinePerformance.ctr * localFactors.clickMultiplier * 100) / 100,
      expectedCPC: (baselinePerformance.cpc * localFactors.costMultiplier * 100) / 100,
      expectedConversionRate: (baselinePerformance.conversionRate * localFactors.conversionMultiplier * 100) / 100,

      // Quality and competition estimates
      expectedQualityScore: estimateQualityScore(expansion),
      competitionLevel: expansion.competitionLevel,

      // Confidence and risk assessment
      predictionConfidence: calculatePredictionConfidence(baselinePerformance, localFactors),
      riskAssessment: assessKeywordRisk(expansion),

      // ROI projections
      expectedROI: calculateExpectedROI(expansion, baselinePerformance, localFactors),
      breakEvenPoint: calculateBreakEvenPoint(expansion, baselinePerformance),
    }};

    predictions.push(prediction);
  }}

  return predictions.sort((a, b) => b.expectedROI - a.expectedROI);
}}

/**
 * Generate comprehensive expansion report
 */
function generateExpansionReport(results) {{
  const summary = {{
    totalKeywordOpportunities: results.keywordExpansions.length,
    landingPageOptimizations: results.landingPageOptimizations.length,
    marketExpansionOpportunities: results.marketOpportunities.length,
    competitiveKeywordOpportunities: results.competitiveKeywords.length,
    seasonalOpportunities: results.seasonalExpansions.length,

    // High-priority opportunities
    highPriorityKeywords: results.keywordExpansions.filter(k => k.opportunityScore > 0.8).length,
    highImpactLandingPages: results.landingPageOptimizations.filter(
      lp => lp.expectedImprovements.conversionRateIncrease > 20
    ).length,

    // Performance projections
    totalExpectedImpressions: results.performancePredictions.reduce(
      (sum, p) => sum + p.expectedImpressions, 0
    ),
    totalExpectedClicks: results.performancePredictions.reduce(
      (sum, p) => sum + p.expectedClicks, 0
    ),
    totalExpectedConversions: results.performancePredictions.reduce(
      (sum, p) => sum + p.expectedConversions, 0
    ),

    // Investment and return estimates
    estimatedAdditionalCost: results.performancePredictions.reduce(
      (sum, p) => sum + p.expectedCost, 0
    ),
    estimatedROIIncrease: calculateOverallROIIncrease(results),
  }};

  console.log('📊 Local Keyword Expansion Summary:');
  console.log(`- Total Keyword Opportunities: ${{summary.totalKeywordOpportunities}}`);
  console.log(`- Landing Page Optimizations: ${{summary.landingPageOptimizations}}`);
  console.log(`- Market Expansion Opportunities: ${{summary.marketExpansionOpportunities}}`);
  console.log(`- Competitive Keywords: ${{summary.competitiveKeywordOpportunities}}`);
  console.log(`- Seasonal Opportunities: ${{summary.seasonalOpportunities}}`);
  console.log(`- Expected Additional Impressions: ${{summary.totalExpectedImpressions.toLocaleString()}}`);
  console.log(`- Expected Additional Clicks: ${{summary.totalExpectedClicks.toLocaleString()}}`);
  console.log(`- Expected Additional Conversions: ${{summary.totalExpectedConversions}}`);

  return summary;
}}

// Additional utility functions would continue here...
"""

    def _generate_modifier_data_js(self) -> str:
        """Generate JavaScript representation of modifier data."""
        return f"""
// Geographic and Expansion Modifiers
const GEOGRAPHIC_MODIFIERS = {json.dumps(self.geographic_modifiers, indent=2)};

const COMPETITOR_KEYWORDS = {json.dumps(self.competitor_keywords, indent=2)};

const SEASONAL_MODIFIERS = {json.dumps(self.seasonal_modifiers, indent=2)};"""

    def _generate_expansion_config_js(self) -> str:
        """Generate JavaScript configuration for keyword expansion."""
        return f"""
// Keyword Expansion Configuration
const CONFIG = {{
  LOOKBACK_DAYS: {self.config.parameters.get("lookback_days", 30)},
  MIN_IMPRESSIONS: {self.config.parameters.get("min_impressions", 100)},
  MIN_OPPORTUNITY_SCORE: {self.config.parameters.get("min_opportunity_score", 0.6)},
  MIN_CONFIDENCE_SCORE: {self.config.parameters.get("min_confidence_score", 0.7)},
  MIN_MARKET_OPPORTUNITY_SCORE: {self.config.parameters.get("min_market_opportunity_score", 0.5)},
  MAX_KEYWORD_SUGGESTIONS: {self.config.parameters.get("max_keyword_suggestions", 100)},
  EXPANSION_BID_MULTIPLIER: {self.config.parameters.get("expansion_bid_multiplier", 0.8)},
}};"""

    def process_results(self, results: Dict[str, Any]) -> ScriptResult:
        """Process local keyword expansion results."""
        try:
            keyword_expansions = results.get("keywordExpansions", [])
            landing_page_optimizations = results.get("landingPageOptimizations", [])
            market_opportunities = results.get("marketOpportunities", [])
            competitive_keywords = results.get("competitiveKeywords", [])
            seasonal_expansions = results.get("seasonalExpansions", [])
            performance_predictions = results.get("performancePredictions", [])

            # Calculate total opportunities
            total_opportunities = (
                len(keyword_expansions)
                + len(landing_page_optimizations)
                + len(market_opportunities)
                + len(competitive_keywords)
                + len(seasonal_expansions)
            )

            # Generate warnings for high-priority items
            warnings = []

            # High-impact landing page optimizations
            high_impact_landing_pages = [
                lp
                for lp in landing_page_optimizations
                if lp.get("expectedImprovements", {}).get("conversionRateIncrease", 0)
                > 25
            ]
            if high_impact_landing_pages:
                warnings.append(
                    f"{len(high_impact_landing_pages)} landing pages with >25% conversion rate improvement potential"
                )

            # High-opportunity keywords
            high_opportunity_keywords = [
                kw for kw in keyword_expansions if kw.get("opportunityScore", 0) > 0.85
            ]
            if high_opportunity_keywords:
                warnings.append(
                    f"{len(high_opportunity_keywords)} keywords with very high opportunity scores"
                )

            # High-volume market opportunities
            high_volume_markets = [
                mo for mo in market_opportunities if mo.get("searchVolume", 0) > 10000
            ]
            if high_volume_markets:
                warnings.append(
                    f"{len(high_volume_markets)} markets with high search volume potential"
                )

            return ScriptResult(
                status=ScriptStatus.COMPLETED.value,
                execution_time=0.0,  # Will be set by executor
                rows_processed=total_opportunities,
                changes_made=len(landing_page_optimizations),
                errors=[],
                warnings=warnings,
                details={
                    "keyword_expansion": {
                        "total_opportunities": len(keyword_expansions),
                        "high_opportunity_keywords": len(high_opportunity_keywords),
                        "geographic_expansions": len(
                            [
                                kw
                                for kw in keyword_expansions
                                if kw.get("expansionType") == "geographic_modifier"
                            ]
                        ),
                        "proximity_expansions": len(
                            [
                                kw
                                for kw in keyword_expansions
                                if kw.get("expansionType") == "distance_modifier"
                            ]
                        ),
                    },
                    "landing_page_optimization": {
                        "total_optimizations": len(landing_page_optimizations),
                        "high_impact_optimizations": len(high_impact_landing_pages),
                        "store_specific_matches": len(
                            [
                                lp
                                for lp in landing_page_optimizations
                                if lp.get("matchType") == "store_specific"
                            ]
                        ),
                    },
                    "market_opportunities": {
                        "total_markets": len(market_opportunities),
                        "high_volume_markets": len(high_volume_markets),
                        "underserved_markets": len(
                            [
                                mo
                                for mo in market_opportunities
                                if mo.get("marketPenetrationScore", 1.0) < 0.3
                            ]
                        ),
                    },
                    "competitive_analysis": {
                        "competitive_opportunities": len(competitive_keywords),
                        "high_intent_competitive": len(
                            [
                                ck
                                for ck in competitive_keywords
                                if ck.get("opportunityScore", 0) > 0.8
                            ]
                        ),
                    },
                    "seasonal_analysis": {
                        "seasonal_opportunities": len(seasonal_expansions),
                        "current_season_relevant": len(
                            [
                                se
                                for se in seasonal_expansions
                                if se.get("trendStrength", 0) > 0.7
                            ]
                        ),
                    },
                    "performance_predictions": {
                        "total_predicted_impressions": sum(
                            p.get("expectedImpressions", 0)
                            for p in performance_predictions
                        ),
                        "total_predicted_clicks": sum(
                            p.get("expectedClicks", 0) for p in performance_predictions
                        ),
                        "total_predicted_conversions": sum(
                            p.get("expectedConversions", 0)
                            for p in performance_predictions
                        ),
                        "high_roi_keywords": len(
                            [
                                p
                                for p in performance_predictions
                                if p.get("expectedROI", 0) > 200
                            ]
                        ),
                    },
                },
            )

        except Exception as e:
            logger.error(f"Error processing local keyword expansion results: {str(e)}")
            return ScriptResult(
                status=ScriptStatus.FAILED.value,
                execution_time=0.0,
                rows_processed=0,
                changes_made=0,
                errors=[f"Results processing error: {str(e)}"],
                warnings=[],
                details={},
            )

    def get_required_parameters(self) -> List[str]:
        """Get required parameters for local keyword expansion."""
        return [
            "store_locations",  # List of store location data
            "lookback_days",  # Days to analyze
            "min_impressions",  # Minimum impressions threshold
        ]

    def generate_keyword_opportunities(
        self, base_keywords: List[str], store_locations: List[StoreLocation]
    ) -> List[KeywordOpportunity]:
        """Generate keyword expansion opportunities."""
        opportunities = []

        for base_keyword in base_keywords:
            # Generate geographic variations
            for location in store_locations:
                geo_variations = self._generate_geographic_variations(
                    base_keyword, location
                )
                opportunities.extend(geo_variations)

            # Generate proximity variations
            proximity_variations = self._generate_proximity_variations(base_keyword)
            opportunities.extend(proximity_variations)

        return opportunities

    def _generate_geographic_variations(
        self, base_keyword: str, location: StoreLocation
    ) -> List[KeywordOpportunity]:
        """Generate geographic variations for a keyword."""
        variations = []

        # City-specific variations
        city_variations = [
            f"{location.city} {base_keyword}",
            f"{base_keyword} {location.city}",
            f"{base_keyword} in {location.city}",
        ]

        for variation in city_variations:
            opportunity = KeywordOpportunity(
                base_keyword=base_keyword,
                expanded_keyword=variation,
                expansion_type=KeywordExpansionType.GEOGRAPHIC_MODIFIER,
                matched_stores=[location],
                search_volume_estimate=self._estimate_search_volume(variation),
                competition_level="medium",
                suggested_bid=self._calculate_suggested_bid(base_keyword, location),
                confidence_score=0.8,
                landing_page_recommendation=location.landing_page,
                reasoning=f"Geographic variation targeting {location.city} market",
            )
            variations.append(opportunity)

        return variations

    def _generate_proximity_variations(
        self, base_keyword: str
    ) -> List[KeywordOpportunity]:
        """Generate proximity-based variations for a keyword."""
        variations = []

        proximity_modifiers = ["near me", "nearby", "close to me", "in my area"]

        for modifier in proximity_modifiers:
            variation = f"{base_keyword} {modifier}"
            opportunity = KeywordOpportunity(
                base_keyword=base_keyword,
                expanded_keyword=variation,
                expansion_type=KeywordExpansionType.DISTANCE_MODIFIER,
                matched_stores=self.store_locations,
                search_volume_estimate=self._estimate_search_volume(variation),
                competition_level="high",  # "Near me" terms are competitive
                suggested_bid=self._calculate_suggested_bid(base_keyword)
                * 1.2,  # Premium for local intent
                confidence_score=0.9,
                reasoning=f"High-intent local search with '{modifier}' modifier",
            )
            variations.append(opportunity)

        return variations

    def _estimate_search_volume(self, keyword: str) -> int:
        """Estimate search volume for a keyword."""
        # This would integrate with keyword planning APIs
        # For now, return placeholder estimates
        base_volume = 1000

        # Adjust based on keyword characteristics
        if "near me" in keyword:
            base_volume = int(base_volume * 0.7)  # Lower volume but higher intent
        if any(city in keyword for city in ["dallas", "houston", "austin"]):
            base_volume = int(base_volume * 1.5)  # Higher volume for major cities

        return base_volume

    def _calculate_suggested_bid(
        self, base_keyword: str, location: Optional[StoreLocation] = None
    ) -> float:
        """Calculate suggested bid for expanded keyword."""
        # Base bid estimation
        base_bid = 2.50

        # Adjust for location factors
        if location:
            # Higher bids for major markets
            if location.city.lower() in ["dallas", "houston", "austin"]:
                base_bid *= 1.2
            # Lower bids for smaller markets
            else:
                base_bid *= 0.9

        return round(base_bid, 2)


def create_local_keyword_expansion_config(
    store_locations: List[Dict[str, Any]],
    lookback_days: int = 30,
    min_impressions: int = 100,
) -> ScriptConfig:
    """Create configuration for local keyword expansion script."""
    return ScriptConfig(
        name="Local Keyword Expansion and Landing Page Optimization",
        type=ScriptType.MASTER_NEGATIVE_LIST,  # Using existing enum for compatibility
        description="Local keyword expansion opportunities and landing page optimization for maximum local performance",
        parameters={
            "store_locations": store_locations,
            "lookback_days": lookback_days,
            "min_impressions": min_impressions,
            "min_opportunity_score": 0.6,
            "min_confidence_score": 0.7,
            "min_market_opportunity_score": 0.5,
            "max_keyword_suggestions": 100,
            "expansion_bid_multiplier": 0.8,
        },
    )
