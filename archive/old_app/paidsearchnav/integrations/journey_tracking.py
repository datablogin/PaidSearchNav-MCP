"""Customer journey tracking and attribution modeling."""

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from .base import CustomerJourney, OfflineConversion

logger = logging.getLogger(__name__)


class TouchpointType(Enum):
    """Types of customer touchpoints."""

    AD_CLICK = "ad_click"
    ORGANIC_SEARCH = "organic_search"
    DIRECT_VISIT = "direct_visit"
    EMAIL_CLICK = "email_click"
    SOCIAL_CLICK = "social_click"
    PHONE_CALL = "phone_call"
    STORE_VISIT = "store_visit"
    FORM_SUBMISSION = "form_submission"
    CHAT_INTERACTION = "chat_interaction"
    OFFLINE_CONVERSION = "offline_conversion"


class AttributionModel(Enum):
    """Attribution models for conversion credit assignment."""

    LAST_CLICK = "last_click"
    FIRST_CLICK = "first_click"
    LINEAR = "linear"
    TIME_DECAY = "time_decay"
    POSITION_BASED = "position_based"  # U-shaped
    DATA_DRIVEN = "data_driven"


@dataclass
class Touchpoint:
    """Represents a single touchpoint in the customer journey."""

    touchpoint_id: str
    timestamp: datetime
    type: TouchpointType
    channel: str
    source: Optional[str] = None
    medium: Optional[str] = None
    campaign_id: Optional[str] = None
    ad_group_id: Optional[str] = None
    keyword: Optional[str] = None
    device: Optional[str] = None
    location: Optional[Dict[str, Any]] = None
    value: float = 0.0
    interaction_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class JourneyMetrics:
    """Metrics for analyzing customer journeys."""

    total_touchpoints: int = 0
    unique_channels: int = 0
    journey_duration_days: float = 0.0
    average_days_between_touchpoints: float = 0.0
    paid_touchpoints: int = 0
    organic_touchpoints: int = 0
    offline_touchpoints: int = 0
    conversion_probability: float = 0.0
    engagement_score: float = 0.0


class CustomerJourneyTracker:
    """Tracks and analyzes customer journeys across online and offline touchpoints."""

    def __init__(
        self, attribution_model: AttributionModel = AttributionModel.LAST_CLICK
    ):
        self.attribution_model = attribution_model
        self.journeys: Dict[str, CustomerJourney] = {}
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def create_journey(
        self, gclid: str, first_touchpoint: Touchpoint
    ) -> CustomerJourney:
        """Create a new customer journey.

        Args:
            gclid: Google Click ID
            first_touchpoint: The first touchpoint in the journey

        Returns:
            New CustomerJourney instance
        """
        journey_id = f"journey_{gclid}_{datetime.utcnow().timestamp()}"

        journey = CustomerJourney(
            journey_id=journey_id,
            gclid=gclid,
            first_touch=first_touchpoint.timestamp,
            last_touch=first_touchpoint.timestamp,
            touchpoints=[self._touchpoint_to_dict(first_touchpoint)],
            attribution_model=self.attribution_model.value,
        )

        self.journeys[journey_id] = journey
        self.logger.info(f"Created new journey {journey_id} for GCLID {gclid}")

        return journey

    def add_touchpoint(
        self, journey_id: str, touchpoint: Touchpoint
    ) -> Optional[CustomerJourney]:
        """Add a touchpoint to an existing journey.

        Args:
            journey_id: The journey ID
            touchpoint: The touchpoint to add

        Returns:
            Updated journey or None if not found
        """
        journey = self.journeys.get(journey_id)
        if not journey:
            self.logger.warning(f"Journey {journey_id} not found")
            return None

        journey.touchpoints.append(self._touchpoint_to_dict(touchpoint))
        journey.last_touch = touchpoint.timestamp

        # Sort touchpoints by timestamp
        journey.touchpoints.sort(key=lambda x: x["timestamp"])

        self.logger.info(
            f"Added {touchpoint.type.value} touchpoint to journey {journey_id}"
        )

        return journey

    def find_journey_by_gclid(self, gclid: str) -> Optional[CustomerJourney]:
        """Find a journey by GCLID.

        Args:
            gclid: Google Click ID

        Returns:
            CustomerJourney if found
        """
        for journey in self.journeys.values():
            if journey.gclid == gclid:
                return journey
        return None

    def add_offline_conversion(
        self, journey_id: str, conversion: OfflineConversion
    ) -> bool:
        """Add an offline conversion to a journey.

        Args:
            journey_id: The journey ID
            conversion: The offline conversion

        Returns:
            True if added successfully
        """
        journey = self.journeys.get(journey_id)
        if not journey:
            return False

        journey.conversions.append(conversion)
        journey.total_value = journey.calculate_total_value()

        # Add conversion as touchpoint
        touchpoint = Touchpoint(
            touchpoint_id=conversion.conversion_id,
            timestamp=conversion.conversion_time,
            type=TouchpointType.OFFLINE_CONVERSION,
            channel="offline",
            value=conversion.conversion_value,
            interaction_data={"conversion_name": conversion.conversion_name},
        )

        self.add_touchpoint(journey_id, touchpoint)

        return True

    def calculate_attribution(
        self, journey: CustomerJourney
    ) -> Dict[str, Dict[str, float]]:
        """Calculate attribution for conversions in a journey.

        Args:
            journey: The customer journey

        Returns:
            Attribution results by channel and campaign
        """
        if not journey.conversions:
            return {}

        total_value = journey.calculate_total_value()
        touchpoints = [self._dict_to_touchpoint(tp) for tp in journey.touchpoints]

        # Filter touchpoints before conversion
        conversion_time = journey.conversions[0].conversion_time
        pre_conversion_touchpoints = [
            tp for tp in touchpoints if tp.timestamp < conversion_time
        ]

        if not pre_conversion_touchpoints:
            return {}

        # Calculate attribution based on model
        if self.attribution_model == AttributionModel.LAST_CLICK:
            attribution = self._last_click_attribution(
                pre_conversion_touchpoints, total_value
            )
        elif self.attribution_model == AttributionModel.FIRST_CLICK:
            attribution = self._first_click_attribution(
                pre_conversion_touchpoints, total_value
            )
        elif self.attribution_model == AttributionModel.LINEAR:
            attribution = self._linear_attribution(
                pre_conversion_touchpoints, total_value
            )
        elif self.attribution_model == AttributionModel.TIME_DECAY:
            attribution = self._time_decay_attribution(
                pre_conversion_touchpoints, total_value
            )
        elif self.attribution_model == AttributionModel.POSITION_BASED:
            attribution = self._position_based_attribution(
                pre_conversion_touchpoints, total_value
            )
        else:
            # Default to last click
            attribution = self._last_click_attribution(
                pre_conversion_touchpoints, total_value
            )

        return attribution

    def analyze_journey(self, journey: CustomerJourney) -> JourneyMetrics:
        """Analyze a customer journey and calculate metrics.

        Args:
            journey: The journey to analyze

        Returns:
            Journey metrics
        """
        touchpoints = [self._dict_to_touchpoint(tp) for tp in journey.touchpoints]

        if not touchpoints:
            return JourneyMetrics()

        # Calculate basic metrics
        metrics = JourneyMetrics(
            total_touchpoints=len(touchpoints),
            journey_duration_days=(journey.last_touch - journey.first_touch).days,
        )

        # Unique channels
        channels = set(tp.channel for tp in touchpoints)
        metrics.unique_channels = len(channels)

        # Average days between touchpoints
        if len(touchpoints) > 1:
            time_diffs = [
                (touchpoints[i + 1].timestamp - touchpoints[i].timestamp).days
                for i in range(len(touchpoints) - 1)
            ]
            metrics.average_days_between_touchpoints = (
                sum(time_diffs) / len(time_diffs) if time_diffs else 0
            )

        # Count touchpoint types
        for tp in touchpoints:
            if tp.channel in ["paid_search", "display", "shopping"]:
                metrics.paid_touchpoints += 1
            elif tp.channel in ["organic", "direct"]:
                metrics.organic_touchpoints += 1
            elif tp.type == TouchpointType.STORE_VISIT:
                metrics.offline_touchpoints += 1

        # Calculate engagement score (0-100)
        metrics.engagement_score = self._calculate_engagement_score(touchpoints)

        # Estimate conversion probability
        if journey.conversions:
            metrics.conversion_probability = 1.0
        else:
            # Use heuristics or ML model to estimate
            metrics.conversion_probability = self._estimate_conversion_probability(
                metrics
            )

        return metrics

    def get_journey_insights(self, journey_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """Get insights across multiple journeys.

        Args:
            journey_ids: List of journey IDs to analyze

        Returns:
            Aggregated insights
        """
        insights = {
            "summary": {
                "total_journeys": len(journey_ids),
                "converted_journeys": 0,
                "total_value": 0.0,
                "average_touchpoints": 0.0,
                "average_journey_days": 0.0,
            },
            "channel_performance": defaultdict(
                lambda: {"touchpoints": 0, "conversions": 0, "value": 0.0}
            ),
            "top_paths": [],
            "attribution_summary": defaultdict(float),
        }

        journey_metrics = []

        for journey_id in journey_ids:
            journey = self.journeys.get(journey_id)
            if not journey:
                continue

            # Analyze journey
            metrics = self.analyze_journey(journey)
            journey_metrics.append(metrics)

            # Update summary
            if journey.conversions:
                insights["summary"]["converted_journeys"] += 1
                insights["summary"]["total_value"] += journey.total_value

            # Calculate attribution
            attribution = self.calculate_attribution(journey)
            for channel, data in attribution.items():
                insights["attribution_summary"][channel] += data.get("value", 0)

        # Calculate averages
        if journey_metrics:
            insights["summary"]["average_touchpoints"] = sum(
                m.total_touchpoints for m in journey_metrics
            ) / len(journey_metrics)
            insights["summary"]["average_journey_days"] = sum(
                m.journey_duration_days for m in journey_metrics
            ) / len(journey_metrics)

        return dict(insights)

    def _touchpoint_to_dict(self, touchpoint: Touchpoint) -> Dict[str, Any]:
        """Convert Touchpoint to dictionary."""
        return {
            "touchpoint_id": touchpoint.touchpoint_id,
            "timestamp": touchpoint.timestamp.isoformat(),
            "type": touchpoint.type.value,
            "channel": touchpoint.channel,
            "source": touchpoint.source,
            "medium": touchpoint.medium,
            "campaign_id": touchpoint.campaign_id,
            "ad_group_id": touchpoint.ad_group_id,
            "keyword": touchpoint.keyword,
            "device": touchpoint.device,
            "location": touchpoint.location,
            "value": touchpoint.value,
            "interaction_data": touchpoint.interaction_data,
        }

    def _dict_to_touchpoint(self, data: Dict[str, Any]) -> Touchpoint:
        """Convert dictionary to Touchpoint."""
        return Touchpoint(
            touchpoint_id=data["touchpoint_id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            type=TouchpointType(data["type"]),
            channel=data["channel"],
            source=data.get("source"),
            medium=data.get("medium"),
            campaign_id=data.get("campaign_id"),
            ad_group_id=data.get("ad_group_id"),
            keyword=data.get("keyword"),
            device=data.get("device"),
            location=data.get("location"),
            value=data.get("value", 0.0),
            interaction_data=data.get("interaction_data", {}),
        )

    def _last_click_attribution(
        self, touchpoints: List[Touchpoint], total_value: float
    ) -> Dict[str, Dict[str, float]]:
        """Last click attribution model."""
        if not touchpoints:
            return {}

        last_tp = touchpoints[-1]
        return {
            last_tp.channel: {
                "value": total_value,
                "credit": 1.0,
                "campaign_id": last_tp.campaign_id,
            }
        }

    def _first_click_attribution(
        self, touchpoints: List[Touchpoint], total_value: float
    ) -> Dict[str, Dict[str, float]]:
        """First click attribution model."""
        if not touchpoints:
            return {}

        first_tp = touchpoints[0]
        return {
            first_tp.channel: {
                "value": total_value,
                "credit": 1.0,
                "campaign_id": first_tp.campaign_id,
            }
        }

    def _linear_attribution(
        self, touchpoints: List[Touchpoint], total_value: float
    ) -> Dict[str, Dict[str, float]]:
        """Linear attribution model - equal credit to all touchpoints."""
        if not touchpoints:
            return {}

        credit_per_touchpoint = 1.0 / len(touchpoints)
        value_per_touchpoint = total_value / len(touchpoints)

        attribution = defaultdict(lambda: {"value": 0.0, "credit": 0.0})

        for tp in touchpoints:
            attribution[tp.channel]["value"] += value_per_touchpoint
            attribution[tp.channel]["credit"] += credit_per_touchpoint
            attribution[tp.channel]["campaign_id"] = tp.campaign_id

        return dict(attribution)

    def _time_decay_attribution(
        self, touchpoints: List[Touchpoint], total_value: float, half_life_days: int = 7
    ) -> Dict[str, Dict[str, float]]:
        """Time decay attribution - more credit to recent touchpoints."""
        if not touchpoints:
            return {}

        conversion_time = touchpoints[-1].timestamp

        # Calculate decay weights
        weights = []
        for tp in touchpoints:
            # Use max to handle same-day touchpoints
            days_before_conversion = max(
                0.1, (conversion_time - tp.timestamp).total_seconds() / 86400
            )
            weight = max(0.01, 0.5 ** (days_before_conversion / half_life_days))
            weights.append(weight)

        total_weight = sum(weights)
        attribution = defaultdict(lambda: {"value": 0.0, "credit": 0.0})

        for tp, weight in zip(touchpoints, weights):
            credit = weight / total_weight
            attribution[tp.channel]["value"] += total_value * credit
            attribution[tp.channel]["credit"] += credit
            attribution[tp.channel]["campaign_id"] = tp.campaign_id

        return dict(attribution)

    def _position_based_attribution(
        self, touchpoints: List[Touchpoint], total_value: float
    ) -> Dict[str, Dict[str, float]]:
        """Position-based (U-shaped) attribution - 40% first, 40% last, 20% middle."""
        if not touchpoints:
            return {}

        attribution = defaultdict(lambda: {"value": 0.0, "credit": 0.0})

        if len(touchpoints) == 1:
            # All credit to single touchpoint
            tp = touchpoints[0]
            attribution[tp.channel] = {
                "value": total_value,
                "credit": 1.0,
                "campaign_id": tp.campaign_id,
            }
        elif len(touchpoints) == 2:
            # 50% each to first and last
            for i, tp in enumerate(touchpoints):
                attribution[tp.channel]["value"] += total_value * 0.5
                attribution[tp.channel]["credit"] += 0.5
                attribution[tp.channel]["campaign_id"] = tp.campaign_id
        else:
            # 40% first, 40% last, 20% distributed among middle
            first_tp = touchpoints[0]
            last_tp = touchpoints[-1]
            middle_tps = touchpoints[1:-1]

            # First touchpoint
            attribution[first_tp.channel]["value"] += total_value * 0.4
            attribution[first_tp.channel]["credit"] += 0.4
            attribution[first_tp.channel]["campaign_id"] = first_tp.campaign_id

            # Last touchpoint
            attribution[last_tp.channel]["value"] += total_value * 0.4
            attribution[last_tp.channel]["credit"] += 0.4
            attribution[last_tp.channel]["campaign_id"] = last_tp.campaign_id

            # Middle touchpoints
            if middle_tps:
                middle_credit = 0.2 / len(middle_tps)
                middle_value = total_value * middle_credit

                for tp in middle_tps:
                    attribution[tp.channel]["value"] += middle_value
                    attribution[tp.channel]["credit"] += middle_credit
                    attribution[tp.channel]["campaign_id"] = tp.campaign_id

        return dict(attribution)

    def _calculate_engagement_score(self, touchpoints: List[Touchpoint]) -> float:
        """Calculate engagement score based on touchpoint patterns."""
        if not touchpoints:
            return 0.0

        score = 0.0

        # More touchpoints = higher engagement
        score += min(len(touchpoints) * 10, 40)

        # Multiple channels = higher engagement
        channels = set(tp.channel for tp in touchpoints)
        score += min(len(channels) * 15, 30)

        # High-value interactions
        for tp in touchpoints:
            if tp.type == TouchpointType.FORM_SUBMISSION:
                score += 10
            elif tp.type == TouchpointType.PHONE_CALL:
                score += 8
            elif tp.type == TouchpointType.STORE_VISIT:
                score += 12

        return min(score, 100)

    def _estimate_conversion_probability(self, metrics: JourneyMetrics) -> float:
        """Estimate conversion probability based on journey metrics."""
        # Simple heuristic model
        prob = 0.1  # Base probability

        # Engagement factors
        if metrics.engagement_score > 70:
            prob += 0.3
        elif metrics.engagement_score > 50:
            prob += 0.2

        # Touchpoint factors
        if metrics.total_touchpoints > 5:
            prob += 0.2
        elif metrics.total_touchpoints > 3:
            prob += 0.1

        # Channel diversity
        if metrics.unique_channels > 2:
            prob += 0.1

        # Recent activity (assuming shorter journey = higher intent)
        if metrics.journey_duration_days < 7:
            prob += 0.1

        return min(prob, 0.95)
