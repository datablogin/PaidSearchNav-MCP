"""Lead quality scoring system using machine learning and rule-based approaches."""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

try:
    import numpy as np
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.preprocessing import StandardScaler

    SKLEARN_AVAILABLE = True
except ImportError:
    # Provide mock implementations if sklearn is not available
    SKLEARN_AVAILABLE = False
    np = None
    RandomForestClassifier = None
    StandardScaler = None

from .base import Lead, LeadQuality, LeadStage

logger = logging.getLogger(__name__)


@dataclass
class ScoringFeatures:
    """Features used for lead scoring."""

    # Engagement features
    time_to_conversion: Optional[float] = None  # Hours from click to lead
    page_views: int = 0
    time_on_site: float = 0.0  # Minutes
    form_completion_time: Optional[float] = None  # Seconds

    # Source features
    campaign_cpc: Optional[float] = None
    keyword_quality_score: Optional[float] = None
    ad_position: Optional[float] = None
    device_type: Optional[str] = None

    # Behavioral features
    downloaded_resources: int = 0
    video_watch_percentage: Optional[float] = None
    return_visits: int = 0
    form_abandonment_count: int = 0

    # Demographics (if available)
    company_size: Optional[str] = None
    industry: Optional[str] = None
    job_title_seniority: Optional[str] = None

    # Historical performance
    similar_leads_conversion_rate: Optional[float] = None
    campaign_conversion_rate: Optional[float] = None


class LeadQualityScorer:
    """Scores lead quality using a combination of ML and business rules."""

    def __init__(self, model_path: Optional[str] = None):
        self.model = None
        self.scaler = StandardScaler() if SKLEARN_AVAILABLE else None
        self.feature_importance = {}
        self.rules_weight = 0.3  # 30% rules, 70% ML
        self.ml_weight = 0.7

        if SKLEARN_AVAILABLE:
            if model_path:
                self._load_model(model_path)
            else:
                self._initialize_default_model()
        else:
            logger.warning("scikit-learn not available. ML scoring disabled.")
            self.rules_weight = 1.0  # Use rules only
            self.ml_weight = 0.0

    def score_lead(
        self, lead: Lead, features: ScoringFeatures, use_ml: bool = True
    ) -> Tuple[LeadQuality, float, Dict[str, Any]]:
        """Score a lead's quality.

        Args:
            lead: The lead to score
            features: Scoring features for the lead
            use_ml: Whether to use ML model (if False, uses rules only)

        Returns:
            Tuple of (quality category, score 0-100, scoring details)
        """
        scoring_details = {
            "timestamp": datetime.utcnow().isoformat(),
            "lead_id": lead.id,
            "components": {},
        }

        # Rule-based scoring
        rule_score, rule_details = self._apply_business_rules(lead, features)
        scoring_details["components"]["rules"] = rule_details

        if use_ml and self.model:
            # ML-based scoring
            ml_score, ml_details = self._apply_ml_scoring(features)
            scoring_details["components"]["ml"] = ml_details

            # Combine scores
            final_score = (rule_score * self.rules_weight) + (ml_score * self.ml_weight)
        else:
            final_score = rule_score

        # Determine quality category
        quality = self._score_to_quality(final_score)

        scoring_details["final_score"] = final_score
        scoring_details["quality"] = quality.value

        return quality, final_score, scoring_details

    def batch_score_leads(
        self, leads_with_features: List[Tuple[Lead, ScoringFeatures]]
    ) -> List[Tuple[Lead, LeadQuality, float]]:
        """Score multiple leads in batch.

        Args:
            leads_with_features: List of (lead, features) tuples

        Returns:
            List of (lead, quality, score) tuples
        """
        results = []

        for lead, features in leads_with_features:
            quality, score, _ = self.score_lead(lead, features)
            results.append((lead, quality, score))

        return results

    def _apply_business_rules(
        self, lead: Lead, features: ScoringFeatures
    ) -> Tuple[float, Dict[str, Any]]:
        """Apply business rules for lead scoring.

        Returns:
            Tuple of (score 0-100, scoring details)
        """
        score = 50.0  # Start with neutral score
        details = {"rules_applied": [], "adjustments": []}

        # Time to conversion rule
        if features.time_to_conversion is not None:
            if features.time_to_conversion < 1:  # Less than 1 hour
                score += 20
                details["rules_applied"].append("fast_conversion")
            elif features.time_to_conversion > 72:  # More than 3 days
                score -= 15
                details["rules_applied"].append("slow_conversion")

        # Engagement rules
        if features.page_views > 5:
            score += 10
            details["rules_applied"].append("high_engagement")
        elif features.page_views < 2:
            score -= 10
            details["rules_applied"].append("low_engagement")

        if features.time_on_site > 5:  # More than 5 minutes
            score += 10
            details["rules_applied"].append("high_time_on_site")

        if features.downloaded_resources > 0:
            score += 15
            details["rules_applied"].append("resource_download")

        # Source quality rules
        if features.keyword_quality_score and features.keyword_quality_score >= 7:
            score += 10
            details["rules_applied"].append("high_quality_keyword")

        if features.campaign_cpc and features.campaign_cpc > 10:
            score += 5  # Higher CPC often indicates more competitive/valuable keywords
            details["rules_applied"].append("high_cpc_source")

        # Lead stage bonus
        if lead.stage in [LeadStage.PROPOSAL, LeadStage.NEGOTIATION]:
            score += 20
            details["rules_applied"].append("advanced_stage")

        # Form abandonment penalty
        if features.form_abandonment_count > 0:
            score -= 10 * min(features.form_abandonment_count, 3)
            details["rules_applied"].append("form_abandonment")

        # Company size bonus (B2B)
        if features.company_size in ["enterprise", "large"]:
            score += 15
            details["rules_applied"].append("enterprise_lead")

        # Ensure score is within bounds
        score = max(0, min(100, score))
        details["final_rule_score"] = score

        return score, details

    def _apply_ml_scoring(
        self, features: ScoringFeatures
    ) -> Tuple[float, Dict[str, Any]]:
        """Apply ML model for lead scoring.

        Returns:
            Tuple of (score 0-100, scoring details)
        """
        if not SKLEARN_AVAILABLE:
            return 50.0, {"error": "scikit-learn not available"}

        if not self.model:
            return 50.0, {"error": "No ML model available"}

        try:
            # Prepare features for ML model
            feature_vector = self._prepare_features(features)

            # Scale features
            feature_vector_scaled = self.scaler.transform([feature_vector])

            # Get prediction probability
            probabilities = self.model.predict_proba(feature_vector_scaled)[0]

            # Convert to score (probability of high quality * 100)
            ml_score = probabilities[1] * 100  # Assuming binary classification

            details = {
                "model_confidence": float(max(probabilities)),
                "feature_importance": self._get_top_features(feature_vector),
                "prediction_probability": float(probabilities[1]),
            }

            return ml_score, details

        except Exception as e:
            logger.error(f"ML scoring failed: {e}")
            return 50.0, {"error": str(e)}

    def _prepare_features(self, features: ScoringFeatures) -> List[float]:
        """Prepare features for ML model input."""
        # Convert features to numerical array
        # This is a simplified version - in production, use proper feature engineering
        feature_vector = [
            features.time_to_conversion or 24.0,
            float(features.page_views),
            features.time_on_site,
            features.form_completion_time or 60.0,
            features.campaign_cpc or 5.0,
            features.keyword_quality_score or 5.0,
            features.ad_position or 3.0,
            1.0 if features.device_type == "mobile" else 0.0,
            float(features.downloaded_resources),
            features.video_watch_percentage or 0.0,
            float(features.return_visits),
            float(features.form_abandonment_count),
            1.0 if features.company_size in ["enterprise", "large"] else 0.0,
            features.similar_leads_conversion_rate or 0.1,
            features.campaign_conversion_rate or 0.05,
        ]

        return feature_vector

    def _score_to_quality(self, score: float) -> LeadQuality:
        """Convert numerical score to quality category."""
        if score >= 80:
            return LeadQuality.HIGH
        elif score >= 60:
            return LeadQuality.MEDIUM
        elif score >= 40:
            return LeadQuality.LOW
        else:
            return LeadQuality.UNQUALIFIED

    def _get_top_features(
        self, feature_vector: List[float], n: int = 5
    ) -> Dict[str, float]:
        """Get top contributing features for the score."""
        if not self.feature_importance:
            return {}

        # This would use actual feature importance from the model
        # For now, return placeholder
        return {
            "time_to_conversion": 0.25,
            "page_views": 0.20,
            "downloaded_resources": 0.15,
            "campaign_quality": 0.10,
            "engagement_time": 0.10,
        }

    def _initialize_default_model(self):
        """Initialize a default ML model with synthetic training data."""
        if not SKLEARN_AVAILABLE:
            logger.warning("Cannot initialize ML model without scikit-learn")
            return

        # In production, this would load a pre-trained model
        # For now, create a simple model with synthetic data
        try:
            # Generate synthetic training data with realistic patterns
            n_samples = 1000

            # Create features with realistic patterns
            X_train = []
            y_train = []

            for _ in range(n_samples):
                # Generate correlated features
                time_to_conversion = np.random.exponential(24.0)  # Hours, average 24
                page_views = np.random.poisson(3.0) + 1
                time_on_site = page_views * np.random.gamma(
                    2.0, 2.0
                )  # Correlated with page views
                form_completion_time = np.random.normal(60.0, 20.0)
                campaign_cpc = np.random.lognormal(1.5, 0.8)
                keyword_quality = (
                    np.random.beta(7, 3) * 10
                )  # Skewed towards higher scores
                ad_position = np.random.gamma(2.0, 0.5)
                is_mobile = np.random.binomial(1, 0.6)
                downloads = np.random.binomial(3, 0.3)
                video_percentage = (
                    np.random.beta(2, 5) * 100 if np.random.random() > 0.7 else 0
                )
                return_visits = np.random.binomial(5, 0.2)
                abandonments = np.random.binomial(2, 0.1)
                is_enterprise = np.random.binomial(1, 0.2)
                similar_lead_rate = np.random.beta(2, 8)
                campaign_rate = np.random.beta(2, 10)

                # Create feature vector
                features = [
                    time_to_conversion,
                    page_views,
                    time_on_site,
                    form_completion_time,
                    campaign_cpc,
                    keyword_quality,
                    ad_position,
                    is_mobile,
                    downloads,
                    video_percentage,
                    return_visits,
                    abandonments,
                    is_enterprise,
                    similar_lead_rate,
                    campaign_rate,
                ]
                X_train.append(features)

                # Generate label based on feature interactions
                # High quality leads have: fast conversion, high engagement, enterprise, low abandonment
                quality_score = (
                    (24 / (time_to_conversion + 1)) * 0.3
                    + min(page_views / 10, 1.0) * 0.2
                    + min(downloads / 3, 1.0) * 0.2
                    + is_enterprise * 0.2
                    + (1 - abandonments / 2) * 0.1
                )
                y_train.append(1 if quality_score > 0.5 else 0)

            X_train = np.array(X_train)
            y_train = np.array(y_train)

            # Fit scaler
            self.scaler.fit(X_train)

            # Train model
            self.model = RandomForestClassifier(
                n_estimators=100, max_depth=10, random_state=42
            )
            self.model.fit(self.scaler.transform(X_train), y_train)

            logger.info("Initialized default ML model")

        except Exception as e:
            logger.error(f"Failed to initialize default model: {e}")
            self.model = None

    def _load_model(self, model_path: str):
        """Load a pre-trained model from disk."""
        # Implementation would load actual saved model
        logger.info(f"Loading model from {model_path}")
        self._initialize_default_model()  # For now, use default

    def update_model(
        self, training_data: List[Tuple[ScoringFeatures, LeadQuality]]
    ) -> bool:
        """Update the ML model with new training data.

        Args:
            training_data: List of (features, actual_quality) tuples

        Returns:
            True if update successful
        """
        if not SKLEARN_AVAILABLE:
            logger.warning("Cannot update model without scikit-learn")
            return False

        try:
            # Prepare training data
            X = [self._prepare_features(features) for features, _ in training_data]
            y = [
                1 if quality == LeadQuality.HIGH else 0 for _, quality in training_data
            ]

            # Update scaler
            self.scaler.fit(X)

            # Retrain model
            self.model.fit(self.scaler.transform(X), y)

            # Update feature importance
            if hasattr(self.model, "feature_importances_"):
                self.feature_importance = dict(
                    enumerate(self.model.feature_importances_)
                )

            logger.info(f"Model updated with {len(training_data)} samples")
            return True

        except Exception as e:
            logger.error(f"Failed to update model: {e}")
            return False
