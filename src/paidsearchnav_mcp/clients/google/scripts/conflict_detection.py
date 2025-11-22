"""Conflict detection scripts for negative keywords."""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from .base import ScriptBase, ScriptConfig, ScriptResult, ScriptStatus
from .templates import TemplateManager

logger = logging.getLogger(__name__)


class ConflictType(Enum):
    """Types of keyword conflicts."""

    EXACT_MATCH = "exact_match"
    PHRASE_MATCH = "phrase_match"
    BROAD_MATCH = "broad_match"
    CONTAINS = "contains"


@dataclass
class KeywordConflict:
    """Represents a conflict between positive and negative keywords."""

    positive_keyword: str
    negative_keyword: str
    campaign_name: str
    ad_group_name: str
    conflict_type: ConflictType
    negative_level: str  # "campaign" or "adgroup"
    impact_score: float  # 0-1, higher means more severe
    resolution_suggestion: str


class ConflictDetectionScript(ScriptBase):
    """Script for detecting conflicts between positive and negative keywords."""

    def __init__(self, client, config: ScriptConfig):
        super().__init__(client, config)
        self.template_manager = TemplateManager()

    def get_required_parameters(self) -> List[str]:
        """Get required parameters for conflict detection."""
        # All parameters are optional with defaults
        return []

    def generate_script(self) -> str:
        """Generate the conflict detection script code."""
        template = self.template_manager.get_template("conflict_detection")
        if not template:
            # Use enhanced conflict detection script
            return self._generate_enhanced_conflict_script()

        params = {
            "check_campaign_level": self.config.parameters.get(
                "check_campaign_level", True
            ),
            "check_adgroup_level": self.config.parameters.get(
                "check_adgroup_level", True
            ),
        }

        return template.render(params)

    def _generate_enhanced_conflict_script(self) -> str:
        """Generate enhanced conflict detection script with match type support."""
        check_campaign_level = str(
            self.config.parameters.get("check_campaign_level", True)
        ).lower()
        check_adgroup_level = str(
            self.config.parameters.get("check_adgroup_level", True)
        ).lower()
        check_list_level = str(
            self.config.parameters.get("check_list_level", True)
        ).lower()

        script = f"""
function main() {{
  var checkCampaignLevel = {check_campaign_level};
  var checkAdGroupLevel = {check_adgroup_level};
  var checkListLevel = {check_list_level};

  var conflicts = [];
  var keywordsChecked = 0;

  // Get all active keywords
  var keywords = AdsApp.keywords()
    .withCondition("Status = ENABLED")
    .get();

  while (keywords.hasNext()) {{
    var keyword = keywords.next();
    var keywordText = keyword.getText();
    var keywordMatchType = keyword.getMatchType();
    var campaign = keyword.getCampaign();
    var adGroup = keyword.getAdGroup();

    keywordsChecked++;

    // Check campaign-level negative keywords
    if (checkCampaignLevel) {{
      var campaignNegatives = campaign.negativeKeywords().get();
      while (campaignNegatives.hasNext()) {{
        var negative = campaignNegatives.next();
        var conflict = checkConflict(
          keywordText,
          keywordMatchType,
          negative.getText(),
          negative.getMatchType()
        );

        if (conflict) {{
          conflicts.push({{
            type: "campaign",
            keyword: keywordText,
            keywordMatchType: keywordMatchType,
            negativeKeyword: negative.getText(),
            negativeMatchType: negative.getMatchType(),
            campaign: campaign.getName(),
            adGroup: adGroup.getName(),
            conflictType: conflict
          }});
        }}
      }}
    }}

    // Check ad group-level negative keywords
    if (checkAdGroupLevel) {{
      var adGroupNegatives = adGroup.negativeKeywords().get();
      while (adGroupNegatives.hasNext()) {{
        var negative = adGroupNegatives.next();
        var conflict = checkConflict(
          keywordText,
          keywordMatchType,
          negative.getText(),
          negative.getMatchType()
        );

        if (conflict) {{
          conflicts.push({{
            type: "adgroup",
            keyword: keywordText,
            keywordMatchType: keywordMatchType,
            negativeKeyword: negative.getText(),
            negativeMatchType: negative.getMatchType(),
            campaign: campaign.getName(),
            adGroup: adGroup.getName(),
            conflictType: conflict
          }});
        }}
      }}
    }}

    // Check negative keyword lists
    if (checkListLevel) {{
      var lists = campaign.negativeKeywordLists().get();
      while (lists.hasNext()) {{
        var list = lists.next();
        var listNegatives = list.negativeKeywords().get();

        while (listNegatives.hasNext()) {{
          var negative = listNegatives.next();
          var conflict = checkConflict(
            keywordText,
            keywordMatchType,
            negative.getText(),
            negative.getMatchType()
          );

          if (conflict) {{
            conflicts.push({{
              type: "list",
              keyword: keywordText,
              keywordMatchType: keywordMatchType,
              negativeKeyword: negative.getText(),
              negativeMatchType: negative.getMatchType(),
              campaign: campaign.getName(),
              adGroup: adGroup.getName(),
              listName: list.getName(),
              conflictType: conflict
            }});
          }}
        }}
      }}
    }}
  }}

  // Calculate impact scores
  conflicts = conflicts.map(function(conflict) {{
    conflict.impactScore = calculateImpactScore(conflict);
    return conflict;
  }});

  // Sort by impact score descending
  conflicts.sort(function(a, b) {{
    return b.impactScore - a.impactScore;
  }});

  return {{
    success: true,
    keywordsChecked: keywordsChecked,
    conflictsFound: conflicts.length,
    conflicts: conflicts,
    summary: generateSummary(conflicts)
  }};
}}

function checkConflict(keyword, keywordMatchType, negativeKeyword, negativeMatchType) {{
  // Clean keywords
  keyword = keyword.toLowerCase().replace(/[+\"\\[\\]]/g, "").trim();
  negativeKeyword = negativeKeyword.toLowerCase().replace(/[-\"\\[\\]]/g, "").trim();

  // Check based on negative match type
  if (negativeMatchType === "EXACT") {{
    // Exact match negative blocks only exact matches
    if (keyword === negativeKeyword) {{
      return "exact_match";
    }}
  }} else if (negativeMatchType === "PHRASE") {{
    // Phrase match negative blocks if keyword contains the phrase
    if (keyword.indexOf(negativeKeyword) !== -1) {{
      return "phrase_match";
    }}
  }} else {{
    // Broad match negative - check all word permutations
    var negativeWords = negativeKeyword.split(/\\s+/);
    var keywordWords = keyword.split(/\\s+/);

    // Check if all negative words appear in keyword
    var allWordsFound = negativeWords.every(function(negWord) {{
      return keywordWords.some(function(keyWord) {{
        return keyWord.indexOf(negWord) !== -1;
      }});
    }});

    if (allWordsFound) {{
      return "broad_match";
    }}
  }}

  return null;
}}

function calculateImpactScore(conflict) {{
  // Base score based on conflict type
  var score = 0;

  if (conflict.conflictType === "exact_match") {{
    score = 1.0;
  }} else if (conflict.conflictType === "phrase_match") {{
    score = 0.8;
  }} else if (conflict.conflictType === "broad_match") {{
    score = 0.6;
  }}

  // Adjust based on negative level
  if (conflict.type === "adgroup") {{
    score *= 0.9;  // Ad group level is slightly less impactful
  }} else if (conflict.type === "list") {{
    score *= 1.1;  // List level affects multiple campaigns
  }}

  return Math.min(score, 1.0);
}}

function generateSummary(conflicts) {{
  var summary = {{
    byType: {{}},
    byLevel: {{}},
    topConflicts: []
  }};

  // Count by conflict type
  conflicts.forEach(function(conflict) {{
    if (!summary.byType[conflict.conflictType]) {{
      summary.byType[conflict.conflictType] = 0;
    }}
    summary.byType[conflict.conflictType]++;

    if (!summary.byLevel[conflict.type]) {{
      summary.byLevel[conflict.type] = 0;
    }}
    summary.byLevel[conflict.type]++;
  }});

  // Get top 5 conflicts
  summary.topConflicts = conflicts.slice(0, 5);

  return summary;
}}
"""
        return script

    def process_results(self, results: Dict[str, Any]) -> ScriptResult:
        """Process conflict detection results."""
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

        keywords_checked = results.get("keywordsChecked", 0)
        conflicts_found = results.get("conflictsFound", 0)
        conflicts = results.get("conflicts", [])
        summary = results.get("summary", {})

        # Generate warnings for high-impact conflicts
        warnings = []
        high_impact_conflicts = [c for c in conflicts if c.get("impactScore", 0) >= 0.8]
        if high_impact_conflicts:
            warnings.append(
                f"Found {len(high_impact_conflicts)} high-impact conflicts "
                f"that may significantly affect campaign performance"
            )

        return ScriptResult(
            status=ScriptStatus.COMPLETED.value,
            execution_time=0.0,
            rows_processed=keywords_checked,
            changes_made=0,  # Conflict detection doesn't make changes
            errors=[],
            warnings=warnings,
            details={
                "keywords_checked": keywords_checked,
                "conflicts_found": conflicts_found,
                "conflicts_by_type": summary.get("byType", {}),
                "conflicts_by_level": summary.get("byLevel", {}),
                "top_conflicts": summary.get("topConflicts", []),
                "all_conflicts": conflicts[:50],  # Limit to first 50
            },
        )

    def analyze_conflicts(
        self, campaign_ids: Optional[List[str]] = None
    ) -> List[KeywordConflict]:
        """Analyze keyword conflicts in specified campaigns."""
        conflicts = []

        # This would typically call the Google Ads API
        # For now, return empty list as placeholder

        return conflicts

    def suggest_resolutions(self, conflicts: List[KeywordConflict]) -> Dict[str, Any]:
        """Suggest resolutions for detected conflicts."""
        resolutions = {
            "remove_negatives": [],
            "modify_negatives": [],
            "modify_positives": [],
            "no_action_needed": [],
        }

        for conflict in conflicts:
            if conflict.impact_score >= 0.9:
                # High impact - suggest removing negative
                resolutions["remove_negatives"].append(
                    {
                        "conflict": conflict,
                        "reason": "High-impact conflict blocking valuable traffic",
                    }
                )
            elif conflict.impact_score >= 0.7:
                # Medium impact - suggest modifying negative
                resolutions["modify_negatives"].append(
                    {
                        "conflict": conflict,
                        "suggestion": f"Change to exact match: [{conflict.negative_keyword}]",
                        "reason": "Reduce conflict scope while maintaining protection",
                    }
                )
            elif conflict.impact_score >= 0.5:
                # Low impact - consider modifying positive
                resolutions["modify_positives"].append(
                    {
                        "conflict": conflict,
                        "suggestion": "Review keyword performance before taking action",
                        "reason": "Low-impact conflict that may be intentional",
                    }
                )
            else:
                # Very low impact - no action needed
                resolutions["no_action_needed"].append(
                    {
                        "conflict": conflict,
                        "reason": "Minimal impact on campaign performance",
                    }
                )

        return resolutions

    def export_conflicts_report(
        self, conflicts: List[KeywordConflict], format: str = "csv"
    ) -> str:
        """Export conflicts to a report format."""
        if format == "csv":
            # Generate CSV report
            lines = [
                "Campaign,Ad Group,Positive Keyword,Negative Keyword,"
                "Conflict Type,Negative Level,Impact Score,Resolution"
            ]

            for conflict in conflicts:
                lines.append(
                    f'"{conflict.campaign_name}","{conflict.ad_group_name}",'
                    f'"{conflict.positive_keyword}","{conflict.negative_keyword}",'
                    f'"{conflict.conflict_type.value}","{conflict.negative_level}",'
                    f'{conflict.impact_score:.2f},"{conflict.resolution_suggestion}"'
                )

            return "\n".join(lines)
        else:
            raise ValueError(f"Unsupported format: {format}")
