"""Placement audit scripts for automated placement exclusions."""

import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from .base import ScriptBase, ScriptConfig, ScriptResult, ScriptStatus
from .templates import TemplateManager

logger = logging.getLogger(__name__)


class PlacementQuality(Enum):
    """Quality levels for placements."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    POOR = "poor"
    SUSPICIOUS = "suspicious"


@dataclass
class PlacementAnalysis:
    """Analysis results for a placement."""

    domain: str
    impressions: int
    clicks: int
    cost: float
    conversions: int
    ctr: float
    cpc: float
    cpa: Optional[float]
    quality_score: float
    quality_level: PlacementQuality
    issues: List[str]
    character_sets: Set[str]
    recommendation: str


class PlacementAuditScript(ScriptBase):
    """Script for auditing placement performance and quality."""

    def __init__(self, client, config: ScriptConfig):
        super().__init__(client, config)
        self.template_manager = TemplateManager()

    def get_required_parameters(self) -> List[str]:
        """Get required parameters for placement audit."""
        # All parameters are optional with defaults
        return []

    def generate_script(self) -> str:
        """Generate the placement audit script code."""
        template = self.template_manager.get_template("placement_audit")
        if template:
            params = {
                "min_impressions": self.config.parameters.get("min_impressions", 100),
                "max_cpa_ratio": self.config.parameters.get("max_cpa_ratio", 2.0),
            }
            return template.render(params)
        else:
            return self._generate_advanced_placement_script()

    def _generate_advanced_placement_script(self) -> str:
        """Generate advanced placement audit script with character detection."""
        min_impressions = self.config.parameters.get("min_impressions", 100)
        max_cpa_ratio = self.config.parameters.get("max_cpa_ratio", 2.0)
        min_ctr = self.config.parameters.get("min_ctr", 0.001)  # 0.1%
        check_character_sets = str(
            self.config.parameters.get("check_character_sets", True)
        ).lower()

        script = f"""
function main() {{
  var minImpressions = {min_impressions};
  var maxCpaRatio = {max_cpa_ratio};
  var minCtr = {min_ctr};
  var checkCharacterSets = {check_character_sets};

  // Get account performance benchmarks
  var accountStats = AdsApp.currentAccount().getStatsFor("LAST_30_DAYS");
  var accountCtr = accountStats.getCtr();
  var accountCpc = accountStats.getAverageCpc();
  var accountCpa = accountStats.getCost() / Math.max(accountStats.getConversions(), 1);

  // Query placement performance
  var report = AdsApp.report(
    "SELECT Domain, Impressions, Clicks, Cost, Conversions, Ctr, AverageCpc " +
    "FROM AUTOMATIC_PLACEMENTS_PERFORMANCE_REPORT " +
    "WHERE Impressions > " + minImpressions + " " +
    "DURING LAST_30_DAYS"
  );

  var placements = [];
  var rows = report.rows();

  while (rows.hasNext()) {{
    var row = rows.next();
    var domain = row["Domain"];
    var impressions = parseInt(row["Impressions"]);
    var clicks = parseInt(row["Clicks"]);
    var cost = parseFloat(row["Cost"]);
    var conversions = parseFloat(row["Conversions"]);
    var ctr = parseFloat(row["Ctr"]);
    var cpc = parseFloat(row["AverageCpc"]);

    var placement = {{
      domain: domain,
      impressions: impressions,
      clicks: clicks,
      cost: cost,
      conversions: conversions,
      ctr: ctr,
      cpc: cpc,
      cpa: conversions > 0 ? cost / conversions : null,
      issues: [],
      characterSets: []
    }};

    // Analyze placement quality
    analyzePlacement(placement, accountCtr, accountCpc, accountCpa, checkCharacterSets);

    placements.push(placement);
  }}

  // Sort by quality score (worst first)
  placements.sort(function(a, b) {{
    return a.qualityScore - b.qualityScore;
  }});

  // Categorize placements
  var categories = categorizePlacements(placements);

  // Generate exclusion recommendations
  var exclusions = generateExclusions(categories);

  return {{
    success: true,
    placementsAnalyzed: placements.length,
    accountBenchmarks: {{
      ctr: accountCtr,
      cpc: accountCpc,
      cpa: accountCpa
    }},
    categories: categories,
    exclusions: exclusions,
    topIssues: getTopIssues(placements)
  }};
}}

function analyzePlacement(placement, accountCtr, accountCpc, accountCpa, checkCharacterSets) {{
  var score = 100;

  // Performance analysis
  if (placement.ctr < accountCtr * 0.5) {{
    placement.issues.push("Low CTR (< 50% of account average)");
    score -= 20;
  }}

  if (placement.cpc > accountCpc * 2) {{
    placement.issues.push("High CPC (> 2x account average)");
    score -= 15;
  }}

  if (placement.cpa !== null && placement.cpa > accountCpa * 2.5) {{
    placement.issues.push("High CPA (> 2.5x account average)");
    score -= 25;
  }}

  if (placement.conversions === 0 && placement.cost > 50) {{
    placement.issues.push("No conversions with significant spend");
    score -= 30;
  }}

  // Character set analysis
  if (checkCharacterSets) {{
    var charSets = detectCharacterSets(placement.domain);
    placement.characterSets = charSets;

    if (charSets.indexOf("cyrillic") > -1) {{
      placement.issues.push("Contains Cyrillic characters");
      score -= 10;
    }}

    if (charSets.indexOf("arabic") > -1) {{
      placement.issues.push("Contains Arabic characters");
      score -= 10;
    }}

    if (charSets.indexOf("chinese") > -1) {{
      placement.issues.push("Contains Chinese characters");
      score -= 10;
    }}
  }}

  // Domain quality checks
  if (isDomainSuspicious(placement.domain)) {{
    placement.issues.push("Suspicious domain pattern");
    score -= 20;
  }}

  // Set quality level
  placement.qualityScore = Math.max(score, 0);

  if (score >= 80) {{
    placement.qualityLevel = "high";
  }} else if (score >= 60) {{
    placement.qualityLevel = "medium";
  }} else if (score >= 40) {{
    placement.qualityLevel = "low";
  }} else if (score >= 20) {{
    placement.qualityLevel = "poor";
  }} else {{
    placement.qualityLevel = "suspicious";
  }}

  // Generate recommendation
  if (placement.qualityLevel === "suspicious" || placement.qualityLevel === "poor") {{
    placement.recommendation = "Exclude immediately";
  }} else if (placement.qualityLevel === "low") {{
    placement.recommendation = "Monitor closely, consider exclusion";
  }} else {{
    placement.recommendation = "Continue running";
  }}
}}

function detectCharacterSets(domain) {{
  var charSets = [];

  // Latin
  if (/[a-zA-Z]/.test(domain)) {{
    charSets.push("latin");
  }}

  // Cyrillic
  if (/[\\u0400-\\u04FF]/.test(domain)) {{
    charSets.push("cyrillic");
  }}

  // Arabic
  if (/[\\u0600-\\u06FF]/.test(domain)) {{
    charSets.push("arabic");
  }}

  // Chinese
  if (/[\\u4E00-\\u9FFF]/.test(domain)) {{
    charSets.push("chinese");
  }}

  // Japanese
  if (/[\\u3040-\\u309F\\u30A0-\\u30FF]/.test(domain)) {{
    charSets.push("japanese");
  }}

  // Korean
  if (/[\\uAC00-\\uD7AF]/.test(domain)) {{
    charSets.push("korean");
  }}

  return charSets;
}}

function isDomainSuspicious(domain) {{
  // Check for suspicious patterns
  var suspiciousPatterns = [
    /^\\d+\\./, // Starts with numbers
    /\\.(tk|ml|ga|cf)$/, // Free TLDs often used for spam
    /-{{3,}}/, // Multiple consecutive hyphens
    /xn--/, // Punycode (internationalized domains)
    /(click|traffic|ads|money|cash)/, // Suspicious keywords
  ];

  for (var i = 0; i < suspiciousPatterns.length; i++) {{
    if (suspiciousPatterns[i].test(domain.toLowerCase())) {{
      return true;
    }}
  }}

  // Check for excessive length
  if (domain.length > 50) {{
    return true;
  }}

  return false;
}}

function categorizePlacements(placements) {{
  var categories = {{
    high: [],
    medium: [],
    low: [],
    poor: [],
    suspicious: []
  }};

  placements.forEach(function(placement) {{
    categories[placement.qualityLevel].push(placement);
  }});

  return categories;
}}

function generateExclusions(categories) {{
  var exclusions = {{
    immediate: [],
    recommended: [],
    totalCostSavings: 0
  }};

  // Immediate exclusions: suspicious and poor quality
  categories.suspicious.forEach(function(p) {{
    exclusions.immediate.push({{
      domain: p.domain,
      reason: p.issues.join("; "),
      costSavings: p.cost
    }});
    exclusions.totalCostSavings += p.cost;
  }});

  categories.poor.forEach(function(p) {{
    exclusions.immediate.push({{
      domain: p.domain,
      reason: p.issues.join("; "),
      costSavings: p.cost
    }});
    exclusions.totalCostSavings += p.cost;
  }});

  // Recommended exclusions: low quality with no conversions
  categories.low.forEach(function(p) {{
    if (p.conversions === 0) {{
      exclusions.recommended.push({{
        domain: p.domain,
        reason: p.issues.join("; "),
        costSavings: p.cost
      }});
    }}
  }});

  return exclusions;
}}

function getTopIssues(placements) {{
  var issueCounts = {{}};

  placements.forEach(function(p) {{
    p.issues.forEach(function(issue) {{
      if (!issueCounts[issue]) {{
        issueCounts[issue] = 0;
      }}
      issueCounts[issue]++;
    }});
  }});

  // Convert to array and sort
  var topIssues = [];
  for (var issue in issueCounts) {{
    topIssues.push({{
      issue: issue,
      count: issueCounts[issue]
    }});
  }}

  topIssues.sort(function(a, b) {{
    return b.count - a.count;
  }});

  return topIssues.slice(0, 10);
}}
"""
        return script

    def process_results(self, results: Dict[str, Any]) -> ScriptResult:
        """Process placement audit results."""
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

        placements_analyzed = results.get("placementsAnalyzed", 0)
        exclusions = results.get("exclusions", {})
        categories = results.get("categories", {})

        # Generate warnings
        warnings = []
        suspicious_count = len(categories.get("suspicious", []))
        if suspicious_count > 0:
            warnings.append(f"Found {suspicious_count} suspicious placements")

        immediate_exclusions = len(exclusions.get("immediate", []))
        if immediate_exclusions > 10:
            warnings.append(
                f"High number of exclusions recommended: {immediate_exclusions}"
            )

        return ScriptResult(
            status=ScriptStatus.COMPLETED.value,
            execution_time=0.0,
            rows_processed=placements_analyzed,
            changes_made=0,  # Audit doesn't make changes directly
            errors=[],
            warnings=warnings,
            details={
                "placements_analyzed": placements_analyzed,
                "account_benchmarks": results.get("accountBenchmarks", {}),
                "quality_distribution": {
                    level: len(placements) for level, placements in categories.items()
                },
                "immediate_exclusions": immediate_exclusions,
                "recommended_exclusions": len(exclusions.get("recommended", [])),
                "potential_cost_savings": exclusions.get("totalCostSavings", 0),
                "top_issues": results.get("topIssues", []),
            },
        )

    def analyze_placements(
        self, campaign_ids: Optional[List[str]] = None, lookback_days: int = 30
    ) -> List[PlacementAnalysis]:
        """Analyze placement performance and quality."""
        analyses = []

        # This would typically call the Google Ads API
        # For now, return empty list as placeholder

        return analyses

    def apply_exclusions(
        self,
        exclusions: List[Dict[str, Any]],
        campaign_ids: Optional[List[str]] = None,
        dry_run: bool = True,
    ) -> Dict[str, Any]:
        """Apply placement exclusions to campaigns."""
        if dry_run:
            return {
                "applied": 0,
                "exclusions": len(exclusions),
                "message": "Dry run mode. No exclusions applied.",
                "preview": exclusions[:10],
            }

        # This would apply exclusions via Google Ads API
        # For now, return mock result

        applied = 0
        errors = []

        for exclusion in exclusions:
            try:
                # Mock application
                applied += 1
            except Exception as e:
                errors.append(
                    {
                        "domain": exclusion["domain"],
                        "error": str(e),
                    }
                )

        return {
            "applied": applied,
            "exclusions": len(exclusions),
            "errors": errors,
            "message": f"Applied {applied} placement exclusions.",
        }

    def detect_placement_patterns(
        self, placements: List[PlacementAnalysis]
    ) -> Dict[str, Any]:
        """Detect patterns in placement data for bulk exclusions."""
        patterns = {
            "domain_patterns": {},
            "tld_distribution": {},
            "character_set_distribution": {},
            "quality_patterns": [],
        }

        for placement in placements:
            # TLD analysis
            tld = placement.domain.split(".")[-1]
            patterns["tld_distribution"][tld] = (
                patterns["tld_distribution"].get(tld, 0) + 1
            )

            # Character set analysis
            for charset in placement.character_sets:
                patterns["character_set_distribution"][charset] = (
                    patterns["character_set_distribution"].get(charset, 0) + 1
                )

            # Quality pattern detection
            if placement.quality_level == PlacementQuality.POOR:
                # Look for common patterns in poor quality placements
                if len(placement.domain) > 40:
                    patterns["quality_patterns"].append("Long domain names")
                if re.search(r"\d{3,}", placement.domain):
                    patterns["quality_patterns"].append("Multiple consecutive digits")

        # Remove duplicates from quality patterns
        patterns["quality_patterns"] = list(set(patterns["quality_patterns"]))

        return patterns
