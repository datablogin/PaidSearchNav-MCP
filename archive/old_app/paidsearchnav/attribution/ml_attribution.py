"""ML-powered attribution analyzer with predictive insights."""

import logging
import pickle
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from paidsearchnav.attribution.models import (
    AttributionInsight,
    AttributionTouch,
    CustomerJourney,
    MLAttributionModel,
    TouchpointType,
)
from paidsearchnav.ml.causal_service import CausalMLService

logger = logging.getLogger(__name__)


class MLAttributionAnalyzer:
    """ML-powered attribution analyzer for predictive customer insights."""

    def __init__(
        self, causal_service: CausalMLService, models_dir: str = "models/attribution"
    ):
        """Initialize ML attribution analyzer.

        Args:
            causal_service: Causal inference service for attribution modeling
            models_dir: Directory for storing trained models
        """
        self.causal_service = causal_service
        self.models_dir = Path(models_dir)
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self._model_cache: Dict[str, Any] = {}

    async def train_attribution_model(
        self,
        customer_id: str,
        historical_journeys: List[CustomerJourney],
        journey_touches: Dict[str, List[AttributionTouch]],
        model_type: str = "xgboost",
        target_metric: str = "conversion_value",
    ) -> MLAttributionModel:
        """Train ML model for data-driven attribution.

        Args:
            customer_id: Customer identifier
            historical_journeys: Historical journey data for training
            journey_touches: Historical touchpoints data
            model_type: ML algorithm type
            target_metric: Target metric to predict

        Returns:
            Trained ML attribution model metadata
        """
        logger.info(
            f"Training {model_type} attribution model for customer {customer_id}"
        )

        try:
            # Prepare training data
            features_df, target_series = self._prepare_training_data(
                historical_journeys, journey_touches, target_metric
            )

            if features_df.empty:
                raise ValueError("No training data available")

            # Train model using causal service
            training_config = {
                "algorithm": model_type,
                "target_column": target_metric,
                "feature_columns": features_df.columns.tolist(),
                "validation_split": 0.2,
                "random_state": 42,
            }

            model_result = await self.causal_service.train_model(
                features_df, target_series, training_config
            )

            # Save model artifacts
            model_filename = f"attribution_{customer_id}_{model_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pkl"
            model_path = self.models_dir / model_filename

            with open(model_path, "wb") as f:
                pickle.dump(model_result.model, f)

            # Create model metadata
            ml_model = MLAttributionModel(
                customer_id=customer_id,
                model_name=f"Attribution Model {model_type}",
                model_type=model_type,
                training_start_date=min(j.first_touch for j in historical_journeys),
                training_end_date=max(j.last_touch for j in historical_journeys),
                training_sample_size=len(historical_journeys),
                validation_sample_size=int(len(historical_journeys) * 0.2),
                feature_columns=features_df.columns.tolist(),
                target_column=target_metric,
                feature_importance=dict(
                    zip(features_df.columns, model_result.feature_importance)
                ),
                accuracy_score=model_result.metrics.get("accuracy"),
                precision_score=model_result.metrics.get("precision"),
                recall_score=model_result.metrics.get("recall"),
                f1_score=model_result.metrics.get("f1"),
                auc_score=model_result.metrics.get("auc"),
                rmse=model_result.metrics.get("rmse"),
                mae=model_result.metrics.get("mae"),
                status="active",
                deployed_at=datetime.utcnow(),
                model_file_path=str(model_path),
            )

            # Cache the model
            self._model_cache[ml_model.model_id] = model_result.model

            logger.info(f"Successfully trained attribution model {ml_model.model_id}")
            return ml_model

        except Exception as e:
            logger.error(f"Failed to train attribution model: {e}")
            raise

    def _prepare_training_data(
        self,
        journeys: List[CustomerJourney],
        journey_touches: Dict[str, List[AttributionTouch]],
        target_metric: str,
    ) -> Tuple[pd.DataFrame, pd.Series]:
        """Prepare feature matrix and target variable for ML training."""
        features = []
        targets = []

        for journey in journeys:
            touches = journey_touches.get(journey.journey_id, [])
            if not touches:
                continue

            # Extract features for this journey
            journey_features = self._extract_journey_features(journey, touches)
            features.append(journey_features)

            # Extract target value
            if target_metric == "conversion_value":
                target_value = journey.conversion_value
            elif target_metric == "conversion_probability":
                target_value = 1.0 if journey.converted else 0.0
            else:
                target_value = getattr(journey, target_metric, 0.0)

            targets.append(target_value)

        # Convert to DataFrame
        features_df = pd.DataFrame(features)
        target_series = pd.Series(targets)

        # Handle categorical variables
        features_df = self._encode_categorical_features(features_df)

        # Handle missing values
        features_df = features_df.fillna(0.0)

        return features_df, target_series

    def _extract_journey_features(
        self, journey: CustomerJourney, touches: List[AttributionTouch]
    ) -> Dict[str, any]:
        """Extract ML features from customer journey."""
        # Basic journey features
        features = {
            "journey_length_days": journey.journey_length_days,
            "total_touches": journey.total_touches,
            "total_sessions": journey.total_sessions,
            "is_multi_channel": 1 if journey.is_multi_channel else 0,
            "is_multi_device": 1 if journey.is_multi_device else 0,
            "unique_countries": len(journey.countries_visited),
            "unique_devices": len(journey.devices_used),
        }

        # Time-based features
        if journey.first_touch and journey.last_touch:
            features["hour_of_first_touch"] = journey.first_touch.hour
            features["day_of_week_first_touch"] = journey.first_touch.weekday()
            features["hour_of_last_touch"] = journey.last_touch.hour
            features["day_of_week_last_touch"] = journey.last_touch.weekday()

        # Touchpoint type features
        touchpoint_counts = {}
        for touch_type in TouchpointType:
            count = sum(1 for touch in touches if touch.touchpoint_type == touch_type)
            touchpoint_counts[f"count_{touch_type.value}"] = count
        features.update(touchpoint_counts)

        # Channel features
        channel_features = self._extract_channel_features(touches)
        features.update(channel_features)

        # Engagement features
        features["total_engagement_time"] = journey.total_engagement_time_msec
        features["avg_engagement_per_touch"] = (
            journey.total_engagement_time_msec / journey.total_touches
            if journey.total_touches > 0
            else 0
        )

        # GCLID features
        gclid_touches = [t for t in touches if t.gclid]
        features["gclid_match_count"] = len(gclid_touches)
        features["gclid_match_rate"] = (
            len(gclid_touches) / len(touches) if touches else 0
        )

        # Revenue features (excluding target variable)
        if journey.converted:
            features["has_revenue"] = 1
            features["is_high_value"] = 1 if journey.conversion_value > 100 else 0
        else:
            features["has_revenue"] = 0
            features["is_high_value"] = 0

        # Temporal features
        features.update(self._extract_temporal_features(touches))

        # Geographic features
        features.update(self._extract_geographic_features(touches))

        return features

    def _extract_channel_features(
        self, touches: List[AttributionTouch]
    ) -> Dict[str, int]:
        """Extract channel-based features from touchpoints."""
        features = {}

        # Count touches by source
        sources = [touch.source for touch in touches if touch.source]
        for source in ["google", "facebook", "bing", "direct", "(none)"]:
            features[f"source_{source}_count"] = sources.count(source)

        # Count touches by medium
        mediums = [touch.medium for touch in touches if touch.medium]
        for medium in ["cpc", "organic", "display", "social", "email", "(none)"]:
            features[f"medium_{medium}_count"] = mediums.count(medium)

        # Sequence features
        if len(touches) >= 2:
            first_source = touches[0].source or "unknown"
            last_source = touches[-1].source or "unknown"
            features["starts_with_google"] = 1 if first_source == "google" else 0
            features["ends_with_google"] = 1 if last_source == "google" else 0
            features["source_consistency"] = 1 if first_source == last_source else 0

        return features

    def _extract_temporal_features(
        self, touches: List[AttributionTouch]
    ) -> Dict[str, float]:
        """Extract temporal patterns from touchpoints."""
        features = {}

        if len(touches) < 2:
            return features

        # Time gaps between touches
        time_gaps = []
        for i in range(1, len(touches)):
            gap = (
                touches[i].timestamp - touches[i - 1].timestamp
            ).total_seconds() / 3600
            time_gaps.append(gap)

        if time_gaps:
            features["avg_time_gap_hours"] = np.mean(time_gaps)
            features["max_time_gap_hours"] = np.max(time_gaps)
            features["min_time_gap_hours"] = np.min(time_gaps)
            features["time_gap_variance"] = np.var(time_gaps)

        # Touch frequency patterns
        total_duration = (
            touches[-1].timestamp - touches[0].timestamp
        ).total_seconds() / 86400
        features["touch_frequency_per_day"] = len(touches) / max(total_duration, 1)

        # Peak activity analysis
        hours = [touch.timestamp.hour for touch in touches]
        features["peak_activity_hour"] = (
            max(set(hours), key=hours.count) if hours else 0
        )
        features["weekend_touches"] = sum(
            1 for touch in touches if touch.timestamp.weekday() >= 5
        )

        return features

    def _extract_geographic_features(
        self, touches: List[AttributionTouch]
    ) -> Dict[str, any]:
        """Extract geographic features from touchpoints."""
        features = {}

        countries = [touch.country for touch in touches if touch.country]
        if countries:
            unique_countries = list(set(countries))
            features["unique_countries_count"] = len(unique_countries)
            features["primary_country"] = max(set(countries), key=countries.count)
            features["geo_consistency"] = 1 if len(unique_countries) == 1 else 0
        else:
            features["unique_countries_count"] = 0
            features["primary_country"] = "unknown"
            features["geo_consistency"] = 0

        return features

    def _encode_categorical_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Encode categorical features for ML training."""
        # One-hot encode categorical columns
        categorical_columns = df.select_dtypes(include=["object"]).columns

        for col in categorical_columns:
            if col != "target":  # Don't encode target variable
                # Create dummy variables
                dummies = pd.get_dummies(df[col], prefix=col)
                df = pd.concat([df, dummies], axis=1)
                df = df.drop(columns=[col])

        return df

    async def predict_attribution_weights(
        self,
        journey: CustomerJourney,
        touches: List[AttributionTouch],
        model: MLAttributionModel,
    ) -> List[float]:
        """Predict attribution weights using trained ML model.

        Args:
            journey: Customer journey
            touches: Journey touchpoints
            model: Trained ML attribution model

        Returns:
            Predicted attribution weights for each touchpoint
        """
        try:
            # Load model if not cached
            if model.model_id not in self._model_cache:
                with open(model.model_file_path, "rb") as f:
                    self._model_cache[model.model_id] = pickle.load(f)

            ml_model = self._model_cache[model.model_id]

            # Prepare features for each touchpoint
            touchpoint_features = []
            for i, touch in enumerate(touches):
                features = self._extract_touchpoint_features(touch, touches, i, journey)
                touchpoint_features.append(features)

            features_df = pd.DataFrame(touchpoint_features)

            # Ensure feature columns match training
            for col in model.feature_columns:
                if col not in features_df.columns:
                    features_df[col] = 0.0

            features_df = features_df[model.feature_columns]
            features_df = features_df.fillna(0.0)

            # Predict attribution weights
            predictions = ml_model.predict_proba(features_df)

            # Convert to attribution weights (normalize to sum to 1.0)
            if len(predictions.shape) > 1:
                weights = predictions[:, 1]  # Probability of being attributable
            else:
                weights = predictions

            # Normalize weights
            total_weight = np.sum(weights)
            if total_weight > 0:
                weights = weights / total_weight
            else:
                weights = np.ones(len(touches)) / len(touches)  # Equal fallback

            return weights.tolist()

        except Exception as e:
            logger.error(f"ML attribution prediction failed: {e}")
            # Fallback to equal weights
            return [1.0 / len(touches)] * len(touches)

    def _extract_touchpoint_features(
        self,
        touch: AttributionTouch,
        all_touches: List[AttributionTouch],
        touch_index: int,
        journey: CustomerJourney,
    ) -> Dict[str, any]:
        """Extract ML features for individual touchpoint."""
        features = {
            # Position features
            "touch_position": touch_index + 1,
            "is_first_touch": 1 if touch_index == 0 else 0,
            "is_last_touch": 1 if touch_index == len(all_touches) - 1 else 0,
            "position_ratio": (touch_index + 1) / len(all_touches),
            # Time features
            "hour_of_touch": touch.timestamp.hour,
            "day_of_week": touch.timestamp.weekday(),
            "is_weekend": 1 if touch.timestamp.weekday() >= 5 else 0,
            # Touchpoint type features
            "is_google_ads": 1
            if touch.touchpoint_type == TouchpointType.GOOGLE_ADS_CLICK
            else 0,
            "is_organic": 1
            if touch.source == "google" and touch.medium == "organic"
            else 0,
            "is_direct": 1 if touch.source == "direct" else 0,
            "is_social": 1 if touch.medium == "social" else 0,
            # Engagement features
            "engagement_time": touch.engagement_time_msec or 0,
            "page_views": touch.page_views or 0,
            "events_count": touch.events_count or 0,
            # Journey context features
            "journey_length_days": journey.journey_length_days,
            "total_journey_touches": len(all_touches),
            "journey_has_gclid": 1 if any(t.gclid for t in all_touches) else 0,
        }

        # Time-relative features
        if len(all_touches) > 1:
            first_touch_time = all_touches[0].timestamp
            last_touch_time = all_touches[-1].timestamp
            journey_duration = (last_touch_time - first_touch_time).total_seconds()

            if journey_duration > 0:
                time_from_start = (touch.timestamp - first_touch_time).total_seconds()
                features["time_ratio_from_start"] = time_from_start / journey_duration

                time_to_end = (last_touch_time - touch.timestamp).total_seconds()
                features["time_ratio_to_end"] = time_to_end / journey_duration

        # Previous touch features
        if touch_index > 0:
            prev_touch = all_touches[touch_index - 1]
            features["time_since_prev_touch_hours"] = (
                touch.timestamp - prev_touch.timestamp
            ).total_seconds() / 3600
            features["same_source_as_prev"] = (
                1 if touch.source == prev_touch.source else 0
            )
            features["same_device_as_prev"] = (
                1 if touch.device_category == prev_touch.device_category else 0
            )

        # Next touch features
        if touch_index < len(all_touches) - 1:
            next_touch = all_touches[touch_index + 1]
            features["time_to_next_touch_hours"] = (
                next_touch.timestamp - touch.timestamp
            ).total_seconds() / 3600

        return features

    async def predict_customer_ltv(
        self,
        journey: CustomerJourney,
        touches: List[AttributionTouch],
        model: MLAttributionModel,
    ) -> float:
        """Predict customer lifetime value using attribution data.

        Args:
            journey: Customer journey
            touches: Journey touchpoints
            model: Trained ML model

        Returns:
            Predicted customer lifetime value
        """
        try:
            # Extract LTV prediction features
            ltv_features = self._extract_ltv_features(journey, touches)
            features_df = pd.DataFrame([ltv_features])

            # Load LTV model (separate from attribution model)
            ltv_model_path = model.model_file_path.replace(".pkl", "_ltv.pkl")

            if not Path(ltv_model_path).exists():
                logger.warning("LTV model not found, using fallback calculation")
                return self._calculate_fallback_ltv(journey, touches)

            if ltv_model_path not in self._model_cache:
                with open(ltv_model_path, "rb") as f:
                    self._model_cache[ltv_model_path] = pickle.load(f)

            ltv_model = self._model_cache[ltv_model_path]

            # Make prediction
            ltv_prediction = ltv_model.predict(features_df)[0]

            return max(0.0, float(ltv_prediction))

        except Exception as e:
            logger.error(f"LTV prediction failed: {e}")
            return self._calculate_fallback_ltv(journey, touches)

    def _extract_ltv_features(
        self, journey: CustomerJourney, touches: List[AttributionTouch]
    ) -> Dict[str, any]:
        """Extract features for customer LTV prediction."""
        features = {
            # Journey characteristics
            "conversion_value": journey.conversion_value,
            "journey_length_days": journey.journey_length_days,
            "total_touches": journey.total_touches,
            "engagement_intensity": journey.total_engagement_time_msec
            / max(journey.total_touches, 1),
            # Channel mix
            "google_ads_touches": sum(
                1
                for t in touches
                if t.touchpoint_type == TouchpointType.GOOGLE_ADS_CLICK
            ),
            "organic_touches": sum(
                1 for t in touches if t.source == "google" and t.medium == "organic"
            ),
            "direct_touches": sum(1 for t in touches if t.source == "direct"),
            # Behavioral indicators
            "repeat_visitor": 1 if journey.total_sessions > 1 else 0,
            "cross_device_user": 1 if journey.is_multi_device else 0,
            "high_engagement": 1
            if journey.total_engagement_time_msec > 300000
            else 0,  # > 5 minutes
            # First touch characteristics
            "first_touch_google_ads": 1
            if journey.first_touch_source == "google"
            and journey.first_touch_medium == "cpc"
            else 0,
            "first_touch_organic": 1
            if journey.first_touch_source == "google"
            and journey.first_touch_medium == "organic"
            else 0,
            "first_touch_direct": 1 if journey.first_touch_source == "direct" else 0,
        }

        return features

    def _calculate_fallback_ltv(
        self, journey: CustomerJourney, touches: List[AttributionTouch]
    ) -> float:
        """Calculate fallback LTV using heuristic methods."""
        # Simple heuristic: base LTV on conversion value and journey characteristics
        base_ltv = journey.conversion_value * 2.5  # Assume 2.5x multiplier

        # Adjust based on journey characteristics
        if journey.is_multi_channel:
            base_ltv *= 1.2  # Multi-channel customers worth more

        if journey.is_multi_device:
            base_ltv *= 1.1  # Cross-device usage indicates engagement

        if journey.journey_length_days > 7:
            base_ltv *= 1.15  # Longer consideration indicates higher value

        # Adjust based on touchpoint quality
        gclid_rate = sum(1 for t in touches if t.gclid) / len(touches) if touches else 0
        if gclid_rate > 0.7:
            base_ltv *= 1.1  # High GCLID matching indicates good tracking

        return base_ltv

    async def generate_predictive_insights(
        self,
        customer_id: str,
        journeys: List[CustomerJourney],
        journey_touches: Dict[str, List[AttributionTouch]],
        model: MLAttributionModel,
    ) -> List[AttributionInsight]:
        """Generate predictive insights using ML attribution analysis.

        Args:
            customer_id: Customer identifier
            journeys: Customer journeys to analyze
            journey_touches: Journey touchpoints
            model: Trained ML model

        Returns:
            List of actionable attribution insights
        """
        insights = []

        try:
            # Analyze journey patterns with ML
            journey_predictions = []

            for journey in journeys:
                touches = journey_touches.get(journey.journey_id, [])
                if not touches:
                    continue

                # Predict LTV for this journey
                predicted_ltv = await self.predict_customer_ltv(journey, touches, model)

                # Predict optimal next touchpoint
                optimal_touchpoint = await self._predict_optimal_touchpoint(
                    journey, touches, model
                )

                journey_predictions.append(
                    {
                        "journey_id": journey.journey_id,
                        "predicted_ltv": predicted_ltv,
                        "optimal_touchpoint": optimal_touchpoint,
                        "journey": journey,
                        "touches": touches,
                    }
                )

            # Generate insights from predictions
            insights.extend(
                self._generate_channel_optimization_insights(
                    journey_predictions, customer_id
                )
            )
            insights.extend(
                self._generate_touchpoint_sequence_insights(
                    journey_predictions, customer_id
                )
            )
            insights.extend(
                self._generate_ltv_insights(journey_predictions, customer_id)
            )

            logger.info(f"Generated {len(insights)} predictive insights")
            return insights

        except Exception as e:
            logger.error(f"Failed to generate predictive insights: {e}")
            return []

    def _generate_channel_optimization_insights(
        self, journey_predictions: List[Dict], customer_id: str
    ) -> List[AttributionInsight]:
        """Generate channel optimization insights from ML predictions."""
        insights = []

        # Analyze channel performance by predicted LTV
        channel_ltv = {}

        for pred in journey_predictions:
            journey = pred["journey"]
            first_channel = f"{journey.first_touch_source}/{journey.first_touch_medium}"

            if first_channel not in channel_ltv:
                channel_ltv[first_channel] = []

            channel_ltv[first_channel].append(pred["predicted_ltv"])

        # Find underperforming channels
        for channel, ltv_values in channel_ltv.items():
            if len(ltv_values) < 5:  # Need minimum sample
                continue

            avg_ltv = np.mean(ltv_values)
            overall_avg_ltv = np.mean(
                [pred["predicted_ltv"] for pred in journey_predictions]
            )

            if avg_ltv < overall_avg_ltv * 0.7:  # 30% below average
                insight = AttributionInsight(
                    customer_id=customer_id,
                    analysis_period_start=min(
                        p["journey"].first_touch for p in journey_predictions
                    ),
                    analysis_period_end=max(
                        p["journey"].last_touch for p in journey_predictions
                    ),
                    insight_type="underperforming_channel",
                    priority="high" if avg_ltv < overall_avg_ltv * 0.5 else "medium",
                    confidence=0.8,
                    title=f"Low LTV Performance: {channel}",
                    description=f"Channel '{channel}' shows predicted LTV of ${avg_ltv:.2f}, which is {(1 - avg_ltv / overall_avg_ltv) * 100:.1f}% below average",
                    impact_description=f"Optimizing this channel could increase LTV by ${overall_avg_ltv - avg_ltv:.2f} per customer",
                    supporting_data={
                        "channel": channel,
                        "avg_predicted_ltv": avg_ltv,
                        "overall_avg_ltv": overall_avg_ltv,
                        "sample_size": len(ltv_values),
                    },
                    recommended_actions=[
                        f"Review targeting and creative for {channel} campaigns",
                        "Analyze landing page performance for this channel",
                        "Consider bid adjustments or budget reallocation",
                        "Implement audience exclusions for low-value segments",
                    ],
                    projected_revenue_impact=len(ltv_values)
                    * (overall_avg_ltv - avg_ltv),
                    implementation_effort="medium",
                )
                insights.append(insight)

        return insights

    def _generate_touchpoint_sequence_insights(
        self, journey_predictions: List[Dict], customer_id: str
    ) -> List[AttributionInsight]:
        """Generate insights about optimal touchpoint sequences."""
        insights = []

        # Analyze touchpoint sequences by LTV
        sequence_performance = {}

        for pred in journey_predictions:
            touches = pred["touches"]
            if len(touches) < 2:
                continue

            # Create sequence representation
            sequence = " → ".join(
                [
                    f"{t.source}/{t.medium}"
                    for t in sorted(touches, key=lambda x: x.timestamp)
                ]
            )

            if sequence not in sequence_performance:
                sequence_performance[sequence] = []

            sequence_performance[sequence].append(pred["predicted_ltv"])

        # Find high-performing sequences
        top_sequences = []
        for sequence, ltv_values in sequence_performance.items():
            if len(ltv_values) >= 3:  # Minimum sample size
                avg_ltv = np.mean(ltv_values)
                top_sequences.append((sequence, avg_ltv, len(ltv_values)))

        top_sequences.sort(key=lambda x: x[1], reverse=True)

        # Generate insight for top sequence
        if top_sequences:
            best_sequence, best_ltv, sample_size = top_sequences[0]
            overall_avg = np.mean(
                [pred["predicted_ltv"] for pred in journey_predictions]
            )

            if best_ltv > overall_avg * 1.3:  # 30% above average
                insight = AttributionInsight(
                    customer_id=customer_id,
                    analysis_period_start=min(
                        p["journey"].first_touch for p in journey_predictions
                    ),
                    analysis_period_end=max(
                        p["journey"].last_touch for p in journey_predictions
                    ),
                    insight_type="high_value_sequence",
                    priority="high",
                    confidence=min(
                        0.9, sample_size / 10
                    ),  # Higher confidence with more samples
                    title="High-Value Customer Journey Sequence Identified",
                    description=f"The sequence '{best_sequence}' shows predicted LTV of ${best_ltv:.2f}, which is {(best_ltv / overall_avg - 1) * 100:.1f}% above average",
                    impact_description=f"Replicating this sequence could increase average LTV by ${best_ltv - overall_avg:.2f}",
                    supporting_data={
                        "sequence": best_sequence,
                        "avg_ltv": best_ltv,
                        "overall_avg_ltv": overall_avg,
                        "sample_size": sample_size,
                    },
                    recommended_actions=[
                        f"Design campaigns to replicate the '{best_sequence}' customer journey",
                        "Increase budget allocation to channels that start this sequence",
                        "Create retargeting campaigns to guide users through this path",
                        "Optimize landing pages for the first touchpoint in this sequence",
                    ],
                    projected_revenue_impact=sample_size * (best_ltv - overall_avg),
                    implementation_effort="high",
                )
                insights.append(insight)

        return insights

    def _generate_ltv_insights(
        self, journey_predictions: List[Dict], customer_id: str
    ) -> List[AttributionInsight]:
        """Generate insights about customer lifetime value predictions."""
        insights = []

        # Analyze LTV distribution
        ltv_values = [pred["predicted_ltv"] for pred in journey_predictions]

        if not ltv_values:
            return insights

        avg_ltv = np.mean(ltv_values)
        ltv_std = np.std(ltv_values)

        # Identify high-value customer characteristics
        high_ltv_threshold = avg_ltv + ltv_std
        high_ltv_journeys = [
            pred
            for pred in journey_predictions
            if pred["predicted_ltv"] > high_ltv_threshold
        ]

        if len(high_ltv_journeys) >= 3:
            # Analyze characteristics of high-LTV journeys
            characteristics = self._analyze_high_ltv_characteristics(high_ltv_journeys)

            insight = AttributionInsight(
                customer_id=customer_id,
                analysis_period_start=min(
                    p["journey"].first_touch for p in journey_predictions
                ),
                analysis_period_end=max(
                    p["journey"].last_touch for p in journey_predictions
                ),
                insight_type="high_ltv_patterns",
                priority="high",
                confidence=0.85,
                title="High-Value Customer Patterns Identified",
                description=f"Identified {len(high_ltv_journeys)} high-LTV customers (${high_ltv_threshold:.2f}+ predicted LTV) with distinct patterns",
                impact_description=f"Targeting similar patterns could increase average LTV by ${high_ltv_threshold - avg_ltv:.2f}",
                supporting_data=characteristics,
                recommended_actions=[
                    "Create lookalike audiences based on high-LTV customer characteristics",
                    "Increase bid multipliers for high-LTV customer segments",
                    "Develop specialized landing pages for high-value prospects",
                    "Implement enhanced conversion tracking for this segment",
                ],
                projected_revenue_impact=len(high_ltv_journeys)
                * (high_ltv_threshold - avg_ltv),
                implementation_effort="medium",
            )
            insights.append(insight)

        return insights

    def _analyze_high_ltv_characteristics(
        self, high_ltv_journeys: List[Dict]
    ) -> Dict[str, any]:
        """Analyze characteristics of high-LTV customer journeys."""
        characteristics = {}

        # Common first touch channels
        first_channels = [j["journey"].first_touch_source for j in high_ltv_journeys]
        characteristics["common_first_touch_sources"] = {
            source: first_channels.count(source) / len(first_channels)
            for source in set(first_channels)
            if first_channels.count(source) >= 2
        }

        # Journey length patterns
        journey_lengths = [j["journey"].journey_length_days for j in high_ltv_journeys]
        characteristics["avg_journey_length"] = np.mean(journey_lengths)
        characteristics["journey_length_variance"] = np.var(journey_lengths)

        # Touch patterns
        touch_counts = [j["journey"].total_touches for j in high_ltv_journeys]
        characteristics["avg_touches"] = np.mean(touch_counts)
        characteristics["multi_touch_rate"] = sum(
            1 for count in touch_counts if count > 1
        ) / len(touch_counts)

        # Device and channel diversity
        multi_device_rate = sum(
            1 for j in high_ltv_journeys if j["journey"].is_multi_device
        ) / len(high_ltv_journeys)
        multi_channel_rate = sum(
            1 for j in high_ltv_journeys if j["journey"].is_multi_channel
        ) / len(high_ltv_journeys)

        characteristics["multi_device_rate"] = multi_device_rate
        characteristics["multi_channel_rate"] = multi_channel_rate

        return characteristics

    async def _predict_optimal_touchpoint(
        self,
        journey: CustomerJourney,
        touches: List[AttributionTouch],
        model: MLAttributionModel,
    ) -> Optional[str]:
        """Predict optimal next touchpoint for customer journey."""
        try:
            # This would use a sequence prediction model
            # For now, return based on successful patterns

            # Analyze successful journey patterns
            if journey.converted:
                return None  # Journey already converted

            # Simple heuristic: recommend based on journey stage
            if len(touches) == 1:
                # Early stage - recommend remarketing
                return "google/display"
            elif len(touches) < 5:
                # Middle stage - recommend organic engagement
                return "google/organic"
            else:
                # Late stage - recommend direct engagement
                return "direct/(none)"

        except Exception as e:
            logger.error(f"Optimal touchpoint prediction failed: {e}")
            return None

    async def retrain_model_if_needed(
        self,
        model: MLAttributionModel,
        recent_journeys: List[CustomerJourney],
        journey_touches: Dict[str, List[AttributionTouch]],
    ) -> Optional[MLAttributionModel]:
        """Retrain attribution model if performance degrades."""
        try:
            # Check if retraining is needed
            days_since_training = (
                (datetime.utcnow() - model.deployed_at).days
                if model.deployed_at
                else 999
            )

            needs_retrain = (
                days_since_training >= model.retrain_frequency_days
                or (
                    model.model_accuracy
                    and model.model_accuracy < model.performance_threshold
                )
                or len(recent_journeys)
                > model.training_sample_size * 1.5  # Significant new data
            )

            if not needs_retrain:
                return None

            logger.info(f"Retraining attribution model {model.model_id}")

            # Retrain with recent data
            new_model = await self.train_attribution_model(
                model.customer_id,
                recent_journeys,
                journey_touches,
                model.model_type,
                model.target_column,
            )

            # Compare performance
            if new_model.model_accuracy and new_model.model_accuracy > (
                model.model_accuracy or 0
            ):
                # New model is better, deprecate old one
                model.status = "deprecated"
                return new_model

            return None

        except Exception as e:
            logger.error(f"Model retraining failed: {e}")
            return None
