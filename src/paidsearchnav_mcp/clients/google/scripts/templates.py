"""Script template management system."""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from jinja2 import StrictUndefined, select_autoescape
from jinja2.sandbox import SandboxedEnvironment

from .base import ScriptType

logger = logging.getLogger(__name__)


@dataclass
class ScriptTemplate:
    """Represents a Google Ads Script template."""

    id: str
    name: str
    type: ScriptType
    description: str
    version: str
    code_template: str
    parameters: List[Dict[str, Any]] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    _env: Optional[SandboxedEnvironment] = field(default=None, init=False, repr=False)

    def __post_init__(self):
        """Initialize the Jinja2 environment."""
        # Use different delimiters to avoid conflicts with JavaScript curly braces
        self._env = SandboxedEnvironment(
            undefined=StrictUndefined,
            autoescape=select_autoescape(default_for_string=False),
            trim_blocks=True,
            lstrip_blocks=True,
            variable_start_string="<<",
            variable_end_string=">>",
            block_start_string="<%",
            block_end_string="%>",
            comment_start_string="<#",
            comment_end_string="#>",
        )
        # Add safe filters and functions
        self._env.filters["jsonify"] = json.dumps
        self._env.globals["min"] = min
        self._env.globals["max"] = max
        self._env.globals["len"] = len

    def render(self, params: Dict[str, Any]) -> str:
        """Render the template with given parameters using sandboxed Jinja2."""
        try:
            # Validate parameters first
            errors = self.validate_params(params)
            if errors:
                raise ValueError(f"Template validation errors: {'; '.join(errors)}")

            # Create template from string
            template = self._env.from_string(self.code_template)

            # Render with parameters
            return template.render(**params)
        except Exception as e:
            logger.error(f"Template rendering failed: {e}")
            raise ValueError(f"Failed to render template: {e}")

    def validate_params(self, params: Dict[str, Any]) -> List[str]:
        """Validate parameters against template requirements."""
        errors = []
        required_params = [
            p["name"] for p in self.parameters if p.get("required", True)
        ]

        for param in required_params:
            if param not in params:
                errors.append(f"Missing required parameter: {param}")

        # Type validation
        for param_def in self.parameters:
            param_name = param_def["name"]
            if param_name in params:
                expected_type = param_def.get("type", "string")
                if not self._validate_type(params[param_name], expected_type):
                    errors.append(
                        f"Parameter '{param_name}' has invalid type. "
                        f"Expected: {expected_type}"
                    )

        return errors

    def _validate_type(self, value: Any, expected_type: str) -> bool:
        """Validate parameter type."""
        type_map = {
            "string": str,
            "number": (int, float),
            "boolean": bool,
            "array": list,
            "object": dict,
        }

        expected = type_map.get(expected_type, str)
        return isinstance(value, expected)


class TemplateManager:
    """Manages script templates."""

    def __init__(self, template_dir: Optional[Path] = None):
        self.template_dir = template_dir or Path(__file__).parent / "templates"
        self._templates: Dict[str, ScriptTemplate] = {}
        self._load_builtin_templates()

    def _load_builtin_templates(self):
        """Load built-in script templates."""
        # Built-in templates
        self._templates.update(
            {
                "negative_keyword_performance": ScriptTemplate(
                    id="negative_keyword_performance",
                    name="Performance-Based Negative Keywords",
                    type=ScriptType.NEGATIVE_KEYWORD,
                    description="Identifies and adds negative keywords based on performance metrics",
                    version="1.0.0",
                    code_template=NEGATIVE_KEYWORD_PERFORMANCE_TEMPLATE,
                    parameters=[
                        {
                            "name": "cost_threshold",
                            "type": "number",
                            "description": "Minimum cost threshold for consideration",
                            "required": True,
                            "default": 50.0,
                        },
                        {
                            "name": "conversion_threshold",
                            "type": "number",
                            "description": "Maximum conversions allowed",
                            "required": True,
                            "default": 0,
                        },
                        {
                            "name": "lookback_days",
                            "type": "number",
                            "description": "Number of days to analyze",
                            "required": False,
                            "default": 30,
                        },
                    ],
                    tags=["performance", "automation", "negative-keywords"],
                ),
                "conflict_detection": ScriptTemplate(
                    id="conflict_detection",
                    name="Negative Keyword Conflict Detector",
                    type=ScriptType.CONFLICT_DETECTION,
                    description="Detects conflicts between negative and positive keywords",
                    version="1.0.0",
                    code_template=CONFLICT_DETECTION_TEMPLATE,
                    parameters=[
                        {
                            "name": "check_campaign_level",
                            "type": "boolean",
                            "description": "Check campaign-level negative keywords",
                            "required": False,
                            "default": True,
                        },
                        {
                            "name": "check_adgroup_level",
                            "type": "boolean",
                            "description": "Check ad group-level negative keywords",
                            "required": False,
                            "default": True,
                        },
                    ],
                    tags=["conflict", "validation", "negative-keywords"],
                ),
                "placement_audit": ScriptTemplate(
                    id="placement_audit",
                    name="Placement Performance Audit",
                    type=ScriptType.PLACEMENT_AUDIT,
                    description="Audits placement performance and suggests exclusions",
                    version="1.0.0",
                    code_template=PLACEMENT_AUDIT_TEMPLATE,
                    parameters=[
                        {
                            "name": "min_impressions",
                            "type": "number",
                            "description": "Minimum impressions for analysis",
                            "required": False,
                            "default": 100,
                        },
                        {
                            "name": "max_cpa_ratio",
                            "type": "number",
                            "description": "Maximum CPA ratio vs account average",
                            "required": False,
                            "default": 2.0,
                        },
                    ],
                    tags=["placement", "audit", "performance"],
                ),
            }
        )

    def get_template(self, template_id: str) -> Optional[ScriptTemplate]:
        """Get a template by ID."""
        return self._templates.get(template_id)

    def list_templates(
        self, script_type: Optional[ScriptType] = None
    ) -> List[ScriptTemplate]:
        """List available templates."""
        templates = list(self._templates.values())
        if script_type:
            templates = [t for t in templates if t.type == script_type]
        return templates

    def register_template(self, template: ScriptTemplate) -> None:
        """Register a custom template."""
        self._templates[template.id] = template
        logger.info(f"Registered template: {template.id}")

    def load_from_file(self, file_path: Path) -> ScriptTemplate:
        """Load a template from a JSON file."""
        with open(file_path, "r") as f:
            data = json.load(f)

        template = ScriptTemplate(
            id=data["id"],
            name=data["name"],
            type=ScriptType(data["type"]),
            description=data["description"],
            version=data["version"],
            code_template=data["code_template"],
            parameters=data.get("parameters", []),
            tags=data.get("tags", []),
        )

        self.register_template(template)
        return template

    def save_to_file(self, template: ScriptTemplate, file_path: Path) -> None:
        """Save a template to a JSON file."""
        data = {
            "id": template.id,
            "name": template.name,
            "type": template.type.value,
            "description": template.description,
            "version": template.version,
            "code_template": template.code_template,
            "parameters": template.parameters,
            "tags": template.tags,
        }

        with open(file_path, "w") as f:
            json.dump(data, f, indent=2)


# Built-in template code
NEGATIVE_KEYWORD_PERFORMANCE_TEMPLATE = """
function main() {{
  var costThreshold = << cost_threshold >>;
  var conversionThreshold = << conversion_threshold >>;
  var lookbackDays = << lookback_days >>;

  var endDate = new Date();
  var startDate = new Date();
  startDate.setDate(endDate.getDate() - lookbackDays);

  var dateRange = formatDate(startDate) + "," + formatDate(endDate);

  var report = AdsApp.report(
    "SELECT SearchTerm, Cost, Conversions, CampaignName, AdGroupName " +
    "FROM SEARCH_TERM_PERFORMANCE_REPORT " +
    "WHERE Cost > " + costThreshold + " " +
    "AND Conversions <= " + conversionThreshold + " " +
    "DURING " + dateRange
  );

  var negativeKeywords = [];
  var rows = report.rows();

  while (rows.hasNext()) {
    var row = rows.next();
    negativeKeywords.push({
      keyword: row["SearchTerm"],
      campaign: row["CampaignName"],
      adGroup: row["AdGroupName"],
      cost: parseFloat(row["Cost"]),
      conversions: parseInt(row["Conversions"])
    });
  }

  // Apply negative keywords
  negativeKeywords.forEach(function(nk) {{
    var adGroup = getAdGroup(nk.campaign, nk.adGroup);
    if (adGroup) {{
      adGroup.createNegativeKeyword(nk.keyword);
      Logger.log("Added negative keyword: " + nk.keyword);
    }}
  }});

  return {{
    success: true,
    negativeKeywordsAdded: negativeKeywords.length,
    details: negativeKeywords
  }};
}}

function formatDate(date) {{
  return Utilities.formatDate(date, "PST", "yyyyMMdd");
}}

function getAdGroup(campaignName, adGroupName) {{
  var adGroups = AdsApp.adGroups()
    .withCondition("CampaignName = '" + campaignName + "'")
    .withCondition("Name = '" + adGroupName + "'")
    .get();

  if (adGroups.hasNext()) {{
    return adGroups.next();
  }}
  return null;
}}
"""

CONFLICT_DETECTION_TEMPLATE = """
function main() {{
  var checkCampaignLevel = << check_campaign_level >>;
  var checkAdGroupLevel = << check_adgroup_level >>;

  var conflicts = [];

  // Get all active keywords
  var keywords = AdsApp.keywords()
    .withCondition("Status = ENABLED")
    .get();

  while (keywords.hasNext()) {{
    var keyword = keywords.next();
    var keywordText = keyword.getText();
    var campaign = keyword.getCampaign();
    var adGroup = keyword.getAdGroup();

    // Check campaign-level negative keywords
    if (checkCampaignLevel) {{
      var campaignNegatives = campaign.negativeKeywords().get();
      while (campaignNegatives.hasNext()) {{
        var negative = campaignNegatives.next();
        if (isConflict(keywordText, negative.getText())) {{
          conflicts.push({{
            type: "campaign",
            keyword: keywordText,
            negativeKeyword: negative.getText(),
            campaign: campaign.getName(),
            adGroup: adGroup.getName()
          }});
        }}
      }}
    }}

    // Check ad group-level negative keywords
    if (checkAdGroupLevel) {{
      var adGroupNegatives = adGroup.negativeKeywords().get();
      while (adGroupNegatives.hasNext()) {{
        var negative = adGroupNegatives.next();
        if (isConflict(keywordText, negative.getText())) {{
          conflicts.push({{
            type: "adgroup",
            keyword: keywordText,
            negativeKeyword: negative.getText(),
            campaign: campaign.getName(),
            adGroup: adGroup.getName()
          }});
        }}
      }}
    }}
  }}

  return {{
    success: true,
    conflictsFound: conflicts.length,
    conflicts: conflicts
  }};
}}

function isConflict(keyword, negativeKeyword) {{
  // Simple conflict detection - can be enhanced
  keyword = keyword.toLowerCase().replace(/[+\"]/g, "");
  negativeKeyword = negativeKeyword.toLowerCase().replace(/[-\"]/g, "");

  return keyword.indexOf(negativeKeyword) !== -1;
}}
"""

PLACEMENT_AUDIT_TEMPLATE = """
function main() {{
  var minImpressions = << min_impressions >>;
  var maxCpaRatio = << max_cpa_ratio >>;

  // Get account average CPA
  var accountStats = AdsApp.currentAccount().getStatsFor("LAST_30_DAYS");
  var accountCpa = accountStats.getCost() / accountStats.getConversions();

  var report = AdsApp.report(
    "SELECT Domain, Cost, Conversions, Impressions, Clicks " +
    "FROM AUTOMATIC_PLACEMENTS_PERFORMANCE_REPORT " +
    "WHERE Impressions > " + minImpressions + " " +
    "DURING LAST_30_DAYS"
  );

  var problematicPlacements = [];
  var rows = report.rows();

  while (rows.hasNext()) {{
    var row = rows.next();
    var cost = parseFloat(row["Cost"]);
    var conversions = parseInt(row["Conversions"]);
    var cpa = conversions > 0 ? cost / conversions : Infinity;

    if (cpa > accountCpa * maxCpaRatio || conversions === 0) {{
      problematicPlacements.push({{
        domain: row["Domain"],
        cost: cost,
        conversions: conversions,
        impressions: parseInt(row["Impressions"]),
        clicks: parseInt(row["Clicks"]),
        cpa: cpa,
        cpaRatio: cpa / accountCpa
      }});
    }}
  }}

  // Sort by cost descending
  problematicPlacements.sort(function(a, b) {{
    return b.cost - a.cost;
  }});

  return {{
    success: true,
    placementsAnalyzed: rows.length,
    problematicPlacements: problematicPlacements.length,
    accountCpa: accountCpa,
    placements: problematicPlacements
  }};
}}
"""
