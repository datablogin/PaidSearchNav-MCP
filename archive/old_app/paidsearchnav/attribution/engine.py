"""Core attribution engine for cross-platform customer journey analysis."""

import logging
import math
from typing import Dict, List, Tuple

from paidsearchnav.attribution.models import (
    AttributionModel,
    AttributionModelType,
    AttributionResult,
    AttributionTouch,
    CustomerJourney,
)

logger = logging.getLogger(__name__)


class AttributionEngine:
    """Core engine for calculating multi-touch attribution across platforms."""

    def __init__(self, ml_service=None):
        """Initialize attribution engine.

        Args:
            ml_service: Optional ML service for data-driven attribution
        """
        self.ml_service = ml_service
        self._model_cache: Dict[str, AttributionModel] = {}

    async def calculate_attribution(
        self,
        journey: CustomerJourney,
        touches: List[AttributionTouch],
        model: AttributionModel,
    ) -> AttributionResult:
        """Calculate attribution weights for a customer journey.

        Args:
            journey: Customer journey to analyze
            touches: All touchpoints in the journey
            model: Attribution model configuration

        Returns:
            Attribution analysis result
        """
        logger.info(
            f"Calculating attribution for journey {journey.journey_id} using {model.model_type}"
        )

        try:
            # Validate inputs
            if not touches:
                raise ValueError("No touchpoints provided for attribution")

            if not journey.converted and model.require_conversion:
                logger.warning(
                    f"Journey {journey.journey_id} did not convert, skipping attribution"
                )
                return self._create_empty_result(journey, model)

            # Sort touches by timestamp
            sorted_touches = sorted(touches, key=lambda x: x.timestamp)

            # Apply the attribution model
            if model.model_type == AttributionModelType.FIRST_TOUCH:
                attribution_weights = self._calculate_first_touch(sorted_touches)
            elif model.model_type == AttributionModelType.LAST_TOUCH:
                attribution_weights = self._calculate_last_touch(sorted_touches)
            elif model.model_type == AttributionModelType.LINEAR:
                attribution_weights = self._calculate_linear(sorted_touches)
            elif model.model_type == AttributionModelType.TIME_DECAY:
                attribution_weights = self._calculate_time_decay(
                    sorted_touches, model.time_decay_half_life_days or 7.0
                )
            elif model.model_type == AttributionModelType.POSITION_BASED:
                attribution_weights = self._calculate_position_based(
                    sorted_touches,
                    model.position_based_first_weight or 0.4,
                    model.position_based_last_weight or 0.4,
                )
            elif model.model_type == AttributionModelType.DATA_DRIVEN:
                attribution_weights = await self._calculate_data_driven(
                    sorted_touches, journey, model
                )
            elif model.model_type == AttributionModelType.CUSTOM:
                attribution_weights = self._calculate_custom(sorted_touches, model)
            else:
                raise ValueError(f"Unsupported attribution model: {model.model_type}")

            # Apply attribution weights to revenue
            total_revenue = journey.conversion_value
            touch_attributions = []
            channel_attribution = {}
            campaign_attribution = {}

            for i, touch in enumerate(sorted_touches):
                weight = attribution_weights.get(i, 0.0)
                attributed_revenue = total_revenue * weight

                # Update touch with attribution weight
                touch.attribution_weight = weight
                touch.revenue_attributed = attributed_revenue

                # Create touch attribution entry
                touch_attributions.append(
                    {
                        "touch_id": touch.touch_id,
                        "touchpoint_type": touch.touchpoint_type,
                        "weight": weight,
                        "attributed_revenue": attributed_revenue,
                        "timestamp": touch.timestamp.isoformat(),
                    }
                )

                # Aggregate by channel
                channel_key = (
                    f"{touch.source}/{touch.medium}"
                    if touch.source and touch.medium
                    else "unknown"
                )
                channel_attribution[channel_key] = (
                    channel_attribution.get(channel_key, 0.0) + attributed_revenue
                )

                # Aggregate by campaign
                if touch.campaign_name:
                    campaign_attribution[touch.campaign_name] = (
                        campaign_attribution.get(touch.campaign_name, 0.0)
                        + attributed_revenue
                    )

            # Calculate aggregated metrics
            google_ads_revenue = sum(
                touch.revenue_attributed
                for touch in sorted_touches
                if touch.touchpoint_type
                in ["google_ads_click", "google_ads_impression"]
            )

            organic_revenue = sum(
                touch.revenue_attributed
                for touch in sorted_touches
                if touch.source == "google" and touch.medium == "organic"
            )

            direct_revenue = sum(
                touch.revenue_attributed
                for touch in sorted_touches
                if touch.source == "direct"
            )

            # Create result
            result = AttributionResult(
                customer_journey_id=journey.journey_id,
                customer_id=journey.customer_id,
                attribution_model_id=model.model_id,
                total_conversion_value=total_revenue,
                total_attributed_value=sum(
                    touch.revenue_attributed for touch in sorted_touches
                ),
                attribution_confidence=self._calculate_confidence(
                    sorted_touches, model
                ),
                touch_attributions=touch_attributions,
                channel_attribution=channel_attribution,
                campaign_attribution=campaign_attribution,
            )

            # Add time-based attribution
            result.attribution_by_day = self._calculate_daily_attribution(
                sorted_touches
            )
            result.attribution_by_hour = self._calculate_hourly_attribution(
                sorted_touches
            )

            # Add geographic attribution
            result.location_attribution = self._calculate_location_attribution(
                sorted_touches
            )

            # Add device attribution
            result.device_attribution = self._calculate_device_attribution(
                sorted_touches
            )

            logger.info(
                f"Attribution calculation completed for journey {journey.journey_id}"
            )
            return result

        except Exception as e:
            logger.error(
                f"Attribution calculation failed for journey {journey.journey_id}: {e}"
            )
            raise

    def _calculate_first_touch(
        self, touches: List[AttributionTouch]
    ) -> Dict[int, float]:
        """Calculate first-touch attribution weights."""
        if not touches:
            return {}

        # Give 100% credit to first touch
        return {0: 1.0}

    def _calculate_last_touch(
        self, touches: List[AttributionTouch]
    ) -> Dict[int, float]:
        """Calculate last-touch attribution weights."""
        if not touches:
            return {}

        # Give 100% credit to last touch
        return {len(touches) - 1: 1.0}

    def _calculate_linear(self, touches: List[AttributionTouch]) -> Dict[int, float]:
        """Calculate linear attribution weights."""
        if not touches:
            return {}

        # Equal credit to all touches
        weight = 1.0 / len(touches)
        return {i: weight for i in range(len(touches))}

    def _calculate_time_decay(
        self, touches: List[AttributionTouch], half_life_days: float
    ) -> Dict[int, float]:
        """Calculate time-decay attribution weights.

        Args:
            touches: Sorted touchpoints
            half_life_days: Half-life for exponential decay
        """
        if not touches:
            return {}

        if len(touches) == 1:
            return {0: 1.0}

        # Calculate time-based weights using exponential decay
        conversion_time = touches[-1].timestamp  # Assume last touch is conversion
        weights = {}
        total_weight = 0.0

        for i, touch in enumerate(touches):
            days_before_conversion = (
                conversion_time - touch.timestamp
            ).total_seconds() / 86400

            # Exponential decay: weight = 2^(-days_before_conversion / half_life)
            weight = math.pow(2, -days_before_conversion / half_life_days)
            weights[i] = weight
            total_weight += weight

        # Normalize weights to sum to 1.0
        if total_weight > 0:
            weights = {i: w / total_weight for i, w in weights.items()}

        return weights

    def _calculate_position_based(
        self,
        touches: List[AttributionTouch],
        first_weight: float,
        last_weight: float,
    ) -> Dict[int, float]:
        """Calculate position-based attribution weights (default 40/20/40).

        Args:
            touches: Sorted touchpoints
            first_weight: Weight for first touch
            last_weight: Weight for last touch
        """
        if not touches:
            return {}

        if len(touches) == 1:
            return {0: 1.0}

        if len(touches) == 2:
            return {0: first_weight, 1: last_weight}

        # Distribute remaining weight among middle touches
        middle_weight = 1.0 - first_weight - last_weight
        middle_touches = len(touches) - 2
        weight_per_middle = (
            middle_weight / middle_touches if middle_touches > 0 else 0.0
        )

        weights = {}
        weights[0] = first_weight  # First touch
        weights[len(touches) - 1] = last_weight  # Last touch

        # Middle touches get equal share of remaining weight
        for i in range(1, len(touches) - 1):
            weights[i] = weight_per_middle

        return weights

    async def _calculate_data_driven(
        self,
        touches: List[AttributionTouch],
        journey: CustomerJourney,
        model: AttributionModel,
    ) -> Dict[int, float]:
        """Calculate data-driven attribution using ML models."""
        if not self.ml_service:
            logger.warning(
                "ML service not available, falling back to linear attribution"
            )
            return self._calculate_linear(touches)

        try:
            # Prepare features for ML model
            features = self._prepare_features_for_ml(touches, journey)

            # Get predictions from ML service
            predictions = await self.ml_service.predict_attribution_weights(
                features, model.ml_model_path
            )

            # Convert predictions to weight dictionary
            weights = {}
            total_weight = sum(predictions)

            for i, pred in enumerate(predictions):
                weights[i] = pred / total_weight if total_weight > 0 else 0.0

            return weights

        except Exception as e:
            logger.error(f"Data-driven attribution failed: {e}")
            # Fallback to time-decay model
            return self._calculate_time_decay(touches, 7.0)

    def _calculate_custom(
        self, touches: List[AttributionTouch], model: AttributionModel
    ) -> Dict[int, float]:
        """Calculate custom attribution weights based on model configuration."""
        if not model.custom_weights:
            logger.warning("No custom weights defined, falling back to linear")
            return self._calculate_linear(touches)

        weights = {}
        total_weight = 0.0

        for i, touch in enumerate(touches):
            # Get weight for this touchpoint type
            touchpoint_weight = model.custom_weights.get(touch.touchpoint_type, 0.0)
            weights[i] = touchpoint_weight
            total_weight += touchpoint_weight

        # Normalize weights
        if total_weight > 0:
            weights = {i: w / total_weight for i, w in weights.items()}
        else:
            # Fall back to linear if no weights match
            return self._calculate_linear(touches)

        return weights

    def _prepare_features_for_ml(
        self, touches: List[AttributionTouch], journey: CustomerJourney
    ) -> Dict[str, any]:
        """Prepare features for ML attribution model."""
        features = {
            "journey_length_days": journey.journey_length_days,
            "total_touches": len(touches),
            "conversion_value": journey.conversion_value,
        }

        # Touchpoint type features
        touchpoint_counts = {}
        for touch in touches:
            touchpoint_counts[touch.touchpoint_type] = (
                touchpoint_counts.get(touch.touchpoint_type, 0) + 1
            )

        features.update(
            {f"count_{tp}": count for tp, count in touchpoint_counts.items()}
        )

        # Time features
        if len(touches) > 1:
            time_between_first_last = (
                touches[-1].timestamp - touches[0].timestamp
            ).total_seconds() / 3600
            features["hours_first_to_last"] = time_between_first_last

        # Channel diversity
        unique_sources = len(set(touch.source for touch in touches if touch.source))
        unique_mediums = len(set(touch.medium for touch in touches if touch.medium))
        features["unique_sources"] = unique_sources
        features["unique_mediums"] = unique_mediums

        # Device diversity
        unique_devices = len(
            set(touch.device_category for touch in touches if touch.device_category)
        )
        features["unique_devices"] = unique_devices

        return features

    def _calculate_confidence(
        self, touches: List[AttributionTouch], model: AttributionModel
    ) -> float:
        """Calculate confidence score for attribution results."""
        if not touches:
            return 0.0

        # Base confidence starts at 0.5
        confidence = 0.5

        # Increase confidence with more touchpoints (up to 0.3 boost)
        touchpoint_boost = min(0.3, len(touches) * 0.05)
        confidence += touchpoint_boost

        # Increase confidence if we have GCLID matches (up to 0.2 boost)
        gclid_matches = sum(1 for touch in touches if touch.gclid)
        gclid_boost = min(0.2, gclid_matches / len(touches) * 0.2)
        confidence += gclid_boost

        # Decrease confidence if journey is very short (quick bounces)
        if len(touches) <= 2 and touches:
            journey_duration = (
                touches[-1].timestamp - touches[0].timestamp
            ).total_seconds()
            if journey_duration < 300:  # Less than 5 minutes
                confidence -= 0.1

        return max(0.0, min(1.0, confidence))

    def _calculate_daily_attribution(
        self, touches: List[AttributionTouch]
    ) -> Dict[str, float]:
        """Calculate attribution breakdown by day."""
        daily_attribution = {}

        for touch in touches:
            day_key = touch.timestamp.strftime("%Y-%m-%d")
            daily_attribution[day_key] = (
                daily_attribution.get(day_key, 0.0) + touch.revenue_attributed
            )

        return daily_attribution

    def _calculate_hourly_attribution(
        self, touches: List[AttributionTouch]
    ) -> Dict[str, float]:
        """Calculate attribution breakdown by hour of day."""
        hourly_attribution = {}

        for touch in touches:
            hour_key = str(touch.timestamp.hour)
            hourly_attribution[hour_key] = (
                hourly_attribution.get(hour_key, 0.0) + touch.revenue_attributed
            )

        return hourly_attribution

    def _calculate_location_attribution(
        self, touches: List[AttributionTouch]
    ) -> Dict[str, float]:
        """Calculate attribution breakdown by location."""
        location_attribution = {}

        for touch in touches:
            if touch.country:
                location_attribution[touch.country] = (
                    location_attribution.get(touch.country, 0.0)
                    + touch.revenue_attributed
                )

        return location_attribution

    def _calculate_device_attribution(
        self, touches: List[AttributionTouch]
    ) -> Dict[str, float]:
        """Calculate attribution breakdown by device category."""
        device_attribution = {}

        for touch in touches:
            if touch.device_category:
                device_attribution[touch.device_category] = (
                    device_attribution.get(touch.device_category, 0.0)
                    + touch.revenue_attributed
                )

        return device_attribution

    def _create_empty_result(
        self, journey: CustomerJourney, model: AttributionModel
    ) -> AttributionResult:
        """Create empty attribution result for non-converting journeys."""
        return AttributionResult(
            customer_journey_id=journey.journey_id,
            customer_id=journey.customer_id,
            attribution_model_id=model.model_id,
            total_conversion_value=0.0,
            total_attributed_value=0.0,
            attribution_confidence=0.0,
        )

    def calculate_incremental_value(
        self,
        attribution_results: List[AttributionResult],
        baseline_period_results: List[AttributionResult],
        channel: str,
    ) -> Dict[str, float]:
        """Calculate incremental value of a channel using attribution data.

        Args:
            attribution_results: Current period attribution results
            baseline_period_results: Baseline/control period results
            channel: Channel to analyze (e.g., "google/cpc")

        Returns:
            Incremental value metrics
        """
        # Calculate total attributed revenue for channel
        current_revenue = sum(
            result.channel_attribution.get(channel, 0.0)
            for result in attribution_results
        )

        baseline_revenue = sum(
            result.channel_attribution.get(channel, 0.0)
            for result in baseline_period_results
        )

        # Calculate incremental metrics
        incremental_revenue = current_revenue - baseline_revenue
        lift_percentage = (
            (incremental_revenue / baseline_revenue * 100)
            if baseline_revenue > 0
            else 0.0
        )

        return {
            "channel": channel,
            "current_attributed_revenue": current_revenue,
            "baseline_attributed_revenue": baseline_revenue,
            "incremental_revenue": incremental_revenue,
            "lift_percentage": lift_percentage,
        }

    async def compare_attribution_models(
        self,
        journey: CustomerJourney,
        touches: List[AttributionTouch],
        models: List[AttributionModel],
    ) -> Dict[str, AttributionResult]:
        """Compare multiple attribution models for the same journey.

        Args:
            journey: Customer journey to analyze
            touches: Touchpoints in the journey
            models: Attribution models to compare

        Returns:
            Attribution results for each model
        """
        results = {}

        for model in models:
            try:
                result = await self.calculate_attribution(journey, touches, model)
                results[model.model_name] = result
            except Exception as e:
                logger.error(f"Model {model.model_name} failed: {e}")
                results[model.model_name] = self._create_empty_result(journey, model)

        return results

    def identify_top_converting_sequences(
        self, attribution_results: List[AttributionResult], min_occurrences: int = 5
    ) -> List[Dict[str, any]]:
        """Identify most effective touchpoint sequences.

        Args:
            attribution_results: List of attribution results to analyze
            min_occurrences: Minimum occurrences to include sequence

        Returns:
            Top converting touchpoint sequences
        """
        sequence_performance = {}

        for result in attribution_results:
            if result.total_conversion_value > 0:
                # Build sequence from touch attributions
                sequence = []
                for touch_attr in sorted(
                    result.touch_attributions, key=lambda x: x["timestamp"]
                ):
                    sequence.append(touch_attr["touchpoint_type"])

                sequence_key = " → ".join(sequence)

                if sequence_key not in sequence_performance:
                    sequence_performance[sequence_key] = {
                        "sequence": sequence_key,
                        "occurrences": 0,
                        "total_revenue": 0.0,
                        "avg_journey_length": 0.0,
                        "conversion_rate": 0.0,
                    }

                perf = sequence_performance[sequence_key]
                perf["occurrences"] += 1
                perf["total_revenue"] += result.total_conversion_value

        # Filter by minimum occurrences and calculate metrics
        top_sequences = []
        for sequence_key, perf in sequence_performance.items():
            if perf["occurrences"] >= min_occurrences:
                perf["avg_revenue_per_conversion"] = (
                    perf["total_revenue"] / perf["occurrences"]
                )
                top_sequences.append(perf)

        # Sort by total revenue
        return sorted(top_sequences, key=lambda x: x["total_revenue"], reverse=True)

    def calculate_attribution_lift(
        self,
        test_results: List[AttributionResult],
        control_results: List[AttributionResult],
        confidence_level: float = 0.95,
    ) -> Dict[str, float]:
        """Calculate statistical significance of attribution lift."""
        # Aggregate revenue by channel for both groups
        test_revenue = self._aggregate_revenue_by_channel(test_results)
        control_revenue = self._aggregate_revenue_by_channel(control_results)

        lift_metrics = {}

        for channel in set(list(test_revenue.keys()) + list(control_revenue.keys())):
            test_rev = test_revenue.get(channel, 0.0)
            control_rev = control_revenue.get(channel, 0.0)

            if control_rev > 0:
                lift = (test_rev - control_rev) / control_rev
                lift_metrics[channel] = {
                    "lift_percentage": lift * 100,
                    "test_revenue": test_rev,
                    "control_revenue": control_rev,
                    "statistical_significance": self._calculate_significance(
                        test_rev, control_rev, len(test_results), len(control_results)
                    ),
                }

        return lift_metrics

    def _aggregate_revenue_by_channel(
        self, results: List[AttributionResult]
    ) -> Dict[str, float]:
        """Aggregate attributed revenue by channel."""
        channel_revenue = {}

        for result in results:
            for channel, revenue in result.channel_attribution.items():
                channel_revenue[channel] = channel_revenue.get(channel, 0.0) + revenue

        return channel_revenue

    def _calculate_significance(
        self, test_value: float, control_value: float, test_n: int, control_n: int
    ) -> float:
        """Calculate statistical significance of difference (simplified)."""
        if test_n == 0 or control_n == 0 or control_value == 0:
            return 0.0

        # Simplified significance calculation
        # In practice, this would use proper statistical tests
        relative_diff = abs(test_value - control_value) / control_value
        sample_adjustment = math.sqrt(min(test_n, control_n) / 100)

        return min(1.0, relative_diff * sample_adjustment)

    async def optimize_attribution_model(
        self,
        historical_journeys: List[CustomerJourney],
        historical_touches: Dict[str, List[AttributionTouch]],
        validation_metric: str = "revenue_accuracy",
    ) -> Tuple[AttributionModel, float]:
        """Find optimal attribution model for historical data.

        Args:
            historical_journeys: Historical customer journeys
            historical_touches: Historical touchpoints by journey ID
            validation_metric: Metric to optimize for

        Returns:
            Best performing attribution model and its score
        """
        # Define models to test
        test_models = [
            AttributionModel(
                model_name="First Touch",
                model_type=AttributionModelType.FIRST_TOUCH,
            ),
            AttributionModel(
                model_name="Last Touch",
                model_type=AttributionModelType.LAST_TOUCH,
            ),
            AttributionModel(
                model_name="Linear",
                model_type=AttributionModelType.LINEAR,
            ),
            AttributionModel(
                model_name="Time Decay (7 days)",
                model_type=AttributionModelType.TIME_DECAY,
                time_decay_half_life_days=7.0,
            ),
            AttributionModel(
                model_name="Time Decay (14 days)",
                model_type=AttributionModelType.TIME_DECAY,
                time_decay_half_life_days=14.0,
            ),
            AttributionModel(
                model_name="Position Based 40/20/40",
                model_type=AttributionModelType.POSITION_BASED,
                position_based_first_weight=0.4,
                position_based_last_weight=0.4,
            ),
        ]

        model_scores = {}

        for model in test_models:
            try:
                # Calculate attribution for all journeys
                scores = []

                for journey in historical_journeys:
                    touches = historical_touches.get(journey.journey_id, [])
                    if touches:
                        result = await self.calculate_attribution(
                            journey, touches, model
                        )

                        # Calculate validation score based on metric
                        if validation_metric == "revenue_accuracy":
                            score = self._calculate_revenue_accuracy(result, journey)
                        else:
                            score = result.attribution_confidence

                        scores.append(score)

                model_scores[model.model_name] = (
                    sum(scores) / len(scores) if scores else 0.0
                )

            except Exception as e:
                logger.error(f"Model {model.model_name} evaluation failed: {e}")
                model_scores[model.model_name] = 0.0

        # Find best model
        best_model_name = max(model_scores, key=model_scores.get)
        best_score = model_scores[best_model_name]

        # Return corresponding model
        best_model = next(m for m in test_models if m.model_name == best_model_name)

        return best_model, best_score

    def _calculate_revenue_accuracy(
        self, result: AttributionResult, actual_journey: CustomerJourney
    ) -> float:
        """Calculate accuracy of revenue attribution."""
        if actual_journey.conversion_value == 0:
            return 1.0 if result.total_attributed_value == 0 else 0.0

        accuracy = (
            1.0
            - abs(result.total_attributed_value - actual_journey.conversion_value)
            / actual_journey.conversion_value
        )

        return max(0.0, accuracy)

    def get_attribution_summary(
        self, results: List[AttributionResult]
    ) -> Dict[str, any]:
        """Get high-level attribution summary across multiple results."""
        if not results:
            return {}

        # Aggregate metrics
        total_conversions = len(results)
        total_revenue = sum(r.total_conversion_value for r in results)
        avg_confidence = sum(r.attribution_confidence for r in results) / len(results)

        # Channel performance
        all_channels = set()
        for result in results:
            all_channels.update(result.channel_attribution.keys())

        channel_summary = {}
        for channel in all_channels:
            channel_revenue = sum(
                r.channel_attribution.get(channel, 0.0) for r in results
            )
            channel_conversions = sum(
                1 for r in results if r.channel_attribution.get(channel, 0.0) > 0
            )

            channel_summary[channel] = {
                "attributed_revenue": channel_revenue,
                "conversions": channel_conversions,
                "avg_revenue_per_conversion": channel_revenue / channel_conversions
                if channel_conversions > 0
                else 0.0,
                "revenue_share": (channel_revenue / total_revenue * 100)
                if total_revenue > 0
                else 0.0,
            }

        return {
            "period_summary": {
                "total_conversions": total_conversions,
                "total_attributed_revenue": total_revenue,
                "average_attribution_confidence": avg_confidence,
            },
            "channel_performance": channel_summary,
            "top_channels_by_revenue": sorted(
                channel_summary.items(),
                key=lambda x: x[1]["attributed_revenue"],
                reverse=True,
            )[:5],
        }
