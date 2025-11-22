"""Negative keyword automation scripts."""

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List

from .base import ScriptBase, ScriptConfig, ScriptResult, ScriptStatus
from .templates import TemplateManager

logger = logging.getLogger(__name__)


@dataclass
class NegativeKeywordSuggestion:
    """Represents a negative keyword suggestion."""

    keyword: str
    campaign_name: str
    ad_group_name: str
    cost: float
    conversions: int
    clicks: int
    impressions: int
    reason: str
    confidence_score: float


class NegativeKeywordScript(ScriptBase):
    """Script for automated negative keyword management."""

    def __init__(self, client, config: ScriptConfig):
        super().__init__(client, config)
        self.template_manager = TemplateManager()

    def get_required_parameters(self) -> List[str]:
        """Get required parameters for negative keyword scripts."""
        script_subtype = self.config.parameters.get("subtype", "performance")

        if script_subtype == "performance":
            return ["cost_threshold", "conversion_threshold"]
        elif script_subtype == "n_gram":
            return ["n_gram_length", "min_occurrences"]
        elif script_subtype == "master_list":
            return ["list_name", "apply_to_campaigns"]
        else:
            return []

    def generate_script(self) -> str:
        """Generate the negative keyword script code."""
        script_subtype = self.config.parameters.get("subtype", "performance")

        if script_subtype == "performance":
            return self._generate_performance_script()
        elif script_subtype == "n_gram":
            return self._generate_ngram_script()
        elif script_subtype == "master_list":
            return self._generate_master_list_script()
        else:
            raise ValueError(f"Unknown script subtype: {script_subtype}")

    def _generate_performance_script(self) -> str:
        """Generate performance-based negative keyword script."""
        template = self.template_manager.get_template("negative_keyword_performance")
        if not template:
            raise ValueError("Performance template not found")

        # Set default values for optional parameters
        params = {
            "cost_threshold": self.config.parameters.get("cost_threshold", 50.0),
            "conversion_threshold": self.config.parameters.get(
                "conversion_threshold", 0
            ),
            "lookback_days": self.config.parameters.get("lookback_days", 30),
        }

        return template.render(params)

    def _generate_ngram_script(self) -> str:
        """Generate N-gram analysis script."""
        n_gram_length = self.config.parameters.get("n_gram_length", 2)
        min_occurrences = self.config.parameters.get("min_occurrences", 10)
        min_cost = self.config.parameters.get("min_cost", 100)

        script = f"""
function main() {{
  var nGramLength = {n_gram_length};
  var minOccurrences = {min_occurrences};
  var minCost = {min_cost};

  var report = AdsApp.report(
    "SELECT SearchTerm, Cost, Conversions, Clicks, Impressions " +
    "FROM SEARCH_TERM_PERFORMANCE_REPORT " +
    "WHERE Impressions > 0 " +
    "DURING LAST_30_DAYS"
  );

  var nGramMap = {{}};
  var rows = report.rows();

  while (rows.hasNext()) {{
    var row = rows.next();
    var searchTerm = row["SearchTerm"].toLowerCase();
    var cost = parseFloat(row["Cost"]);
    var conversions = parseInt(row["Conversions"]);

    // Extract n-grams
    var words = searchTerm.split(/\\s+/);
    for (var i = 0; i <= words.length - nGramLength; i++) {{
      var nGram = words.slice(i, i + nGramLength).join(" ");

      if (!nGramMap[nGram]) {{
        nGramMap[nGram] = {{
          occurrences: 0,
          totalCost: 0,
          totalConversions: 0,
          terms: []
        }};
      }}

      nGramMap[nGram].occurrences++;
      nGramMap[nGram].totalCost += cost;
      nGramMap[nGram].totalConversions += conversions;
      nGramMap[nGram].terms.push(searchTerm);
    }}
  }}

  // Find problematic n-grams
  var negativeNGrams = [];

  for (var nGram in nGramMap) {{
    var data = nGramMap[nGram];

    if (data.occurrences >= minOccurrences &&
        data.totalCost >= minCost &&
        data.totalConversions === 0) {{
      negativeNGrams.push({{
        nGram: nGram,
        occurrences: data.occurrences,
        cost: data.totalCost,
        conversions: data.totalConversions,
        sampleTerms: data.terms.slice(0, 5)
      }});
    }}
  }}

  // Sort by cost descending
  negativeNGrams.sort(function(a, b) {{
    return b.cost - a.cost;
  }});

  return {{
    success: true,
    nGramsAnalyzed: Object.keys(nGramMap).length,
    negativeNGramsFound: negativeNGrams.length,
    nGrams: negativeNGrams
  }};
}}
"""
        return script

    def _generate_master_list_script(self) -> str:
        """Generate master negative list management script."""
        list_name = self.config.parameters.get("list_name", "Master Negative List")
        apply_to_campaigns = self.config.parameters.get("apply_to_campaigns", [])

        script = f"""
function main() {{
  var listName = "{list_name}";
  var campaignNames = {json.dumps(apply_to_campaigns) if apply_to_campaigns else "[]"};

  // Get or create negative keyword list
  var negativeList = getNegativeKeywordList(listName);
  if (!negativeList) {{
    negativeList = AdsApp.newNegativeKeywordListBuilder()
      .withName(listName)
      .build()
      .getResult();
  }}

  // Apply to campaigns
  var campaignsUpdated = 0;

  if (campaignNames.length > 0) {{
    // Apply to specific campaigns
    campaignNames.forEach(function(campaignName) {{
      var campaigns = AdsApp.campaigns()
        .withCondition("Name = '" + campaignName + "'")
        .get();

      if (campaigns.hasNext()) {{
        var campaign = campaigns.next();
        campaign.addNegativeKeywordList(negativeList);
        campaignsUpdated++;
      }}
    }});
  }} else {{
    // Apply to all active campaigns
    var campaigns = AdsApp.campaigns()
      .withCondition("Status = ENABLED")
      .get();

    while (campaigns.hasNext()) {{
      var campaign = campaigns.next();
      campaign.addNegativeKeywordList(negativeList);
      campaignsUpdated++;
    }}
  }}

  return {{
    success: true,
    listName: listName,
    campaignsUpdated: campaignsUpdated,
    keywordsInList: negativeList.negativeKeywords().get().totalNumEntities()
  }};
}}

function getNegativeKeywordList(name) {{
  var lists = AdsApp.negativeKeywordLists()
    .withCondition("Name = '" + name + "'")
    .get();

  if (lists.hasNext()) {{
    return lists.next();
  }}
  return null;
}}
"""
        return script

    def process_results(self, results: Dict[str, Any]) -> ScriptResult:
        """Process script execution results."""
        if not results.get("success", False):
            return ScriptResult(
                status=ScriptStatus.FAILED.value,
                execution_time=0.0,
                rows_processed=0,
                changes_made=0,
                errors=results.get("errors", ["Unknown error"]),
                warnings=[],
                details=results,
            )

        script_subtype = self.config.parameters.get("subtype", "performance")

        if script_subtype == "performance":
            return self._process_performance_results(results)
        elif script_subtype == "n_gram":
            return self._process_ngram_results(results)
        elif script_subtype == "master_list":
            return self._process_master_list_results(results)
        else:
            return ScriptResult(
                status=ScriptStatus.COMPLETED.value,
                execution_time=0.0,
                rows_processed=0,
                changes_made=0,
                errors=[],
                warnings=[],
                details=results,
            )

    def _process_performance_results(self, results: Dict[str, Any]) -> ScriptResult:
        """Process performance-based script results."""
        negative_keywords_added = results.get("negativeKeywordsAdded", 0)
        details = results.get("details", [])

        return ScriptResult(
            status=ScriptStatus.COMPLETED.value,
            execution_time=0.0,
            rows_processed=len(details),
            changes_made=negative_keywords_added,
            errors=[],
            warnings=[],
            details={
                "negative_keywords_added": negative_keywords_added,
                "keywords": details[:10],  # First 10 for summary
                "total_cost_saved": sum(kw.get("cost", 0) for kw in details),
            },
        )

    def _process_ngram_results(self, results: Dict[str, Any]) -> ScriptResult:
        """Process N-gram analysis results."""
        n_grams_analyzed = results.get("nGramsAnalyzed", 0)
        negative_n_grams = results.get("negativeNGramsFound", 0)

        return ScriptResult(
            status=ScriptStatus.COMPLETED.value,
            execution_time=0.0,
            rows_processed=n_grams_analyzed,
            changes_made=0,  # N-gram analysis doesn't make changes directly
            errors=[],
            warnings=[],
            details={
                "n_grams_analyzed": n_grams_analyzed,
                "negative_n_grams_found": negative_n_grams,
                "top_n_grams": results.get("nGrams", [])[:10],
            },
        )

    def _process_master_list_results(self, results: Dict[str, Any]) -> ScriptResult:
        """Process master list management results."""
        campaigns_updated = results.get("campaignsUpdated", 0)

        return ScriptResult(
            status=ScriptStatus.COMPLETED.value,
            execution_time=0.0,
            rows_processed=campaigns_updated,
            changes_made=campaigns_updated,
            errors=[],
            warnings=[],
            details={
                "list_name": results.get("listName", ""),
                "campaigns_updated": campaigns_updated,
                "keywords_in_list": results.get("keywordsInList", 0),
            },
        )

    def analyze_search_terms(
        self, campaign_ids: List[str], lookback_days: int = 30
    ) -> List[NegativeKeywordSuggestion]:
        """Analyze search terms and suggest negative keywords."""
        suggestions = []

        # This would typically call the Google Ads API
        # For now, return empty list as placeholder

        return suggestions

    def apply_negative_keywords(
        self, suggestions: List[NegativeKeywordSuggestion], auto_apply: bool = False
    ) -> Dict[str, Any]:
        """Apply negative keyword suggestions."""
        if not auto_apply:
            return {
                "applied": 0,
                "suggestions": len(suggestions),
                "message": "Auto-apply disabled. Review suggestions before applying.",
            }

        # This would apply the suggestions via Google Ads API
        # For now, return mock result

        return {
            "applied": len(suggestions),
            "suggestions": len(suggestions),
            "message": f"Applied {len(suggestions)} negative keywords.",
        }
