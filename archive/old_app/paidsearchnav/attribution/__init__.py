"""Cross-platform attribution engine for PaidSearchNav.

This package provides advanced attribution models combining Google Ads, GA4,
and business data for comprehensive customer journey analysis.
"""

from paidsearchnav.attribution.engine import AttributionEngine
from paidsearchnav.attribution.journey_builder import CustomerJourneyBuilder
from paidsearchnav.attribution.models import (
    AttributionModel,
    AttributionResult,
    AttributionTouch,
    CustomerJourney,
)

__all__ = [
    "AttributionEngine",
    "CustomerJourneyBuilder",
    "AttributionTouch",
    "CustomerJourney",
    "AttributionModel",
    "AttributionResult",
]
