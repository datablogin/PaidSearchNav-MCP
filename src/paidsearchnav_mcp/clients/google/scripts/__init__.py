"""Google Ads Scripts integration module.

Provides automation capabilities for negative keyword management,
conflict detection, placement audits, and Performance Max optimization
through Google Ads Scripts API.
"""

from .base import ScriptBase, ScriptExecutor
from .conflict_detection import ConflictDetectionScript
from .negative_keywords import NegativeKeywordScript
from .performance_max_cross_campaign import PerformanceMaxCrossCampaignScript
from .performance_max_geographic import (
    PerformanceMaxBiddingOptimizationScript,
    PerformanceMaxGeographicScript,
)
from .performance_max_monitoring import (
    PerformanceMaxAssetOptimizationScript,
    PerformanceMaxMonitoringScript,
)
from .placement_audit import PlacementAuditScript
from .quarterly_data_extraction import (
    CampaignPerformanceScript,
    GeographicPerformanceScript,
    KeywordPerformanceScript,
    SearchTermsPerformanceScript,
)
from .quarterly_scheduler import QuarterlyDataExtractionScheduler
from .runner import GoogleAdsScriptRunner
from .templates import ScriptTemplate, TemplateManager

__all__ = [
    "ScriptBase",
    "ScriptExecutor",
    "GoogleAdsScriptRunner",
    "ScriptTemplate",
    "TemplateManager",
    "NegativeKeywordScript",
    "ConflictDetectionScript",
    "PlacementAuditScript",
    "SearchTermsPerformanceScript",
    "KeywordPerformanceScript",
    "GeographicPerformanceScript",
    "CampaignPerformanceScript",
    "QuarterlyDataExtractionScheduler",
    # Performance Max Scripts
    "PerformanceMaxMonitoringScript",
    "PerformanceMaxAssetOptimizationScript",
    "PerformanceMaxGeographicScript",
    "PerformanceMaxBiddingOptimizationScript",
    "PerformanceMaxCrossCampaignScript",
]
