"""Fallback and graceful degradation system for analyzer failures."""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from paidsearchnav.core.models import (
    Recommendation,
    RecommendationPriority,
    RecommendationType,
)
from paidsearchnav.core.models.analysis import AnalysisMetrics, AnalysisResult

logger = logging.getLogger(__name__)


class FallbackDataSource:
    """Manages fallback data when live API is unavailable."""

    def __init__(
        self,
        cache_directory: Union[str, Path] = "cache/analyzer_fallbacks",
        cache_retention_days: int = 7,
    ):
        """Initialize fallback data source.

        Args:
            cache_directory: Directory to store cached fallback data
            cache_retention_days: Number of days to retain cached data
        """
        self.cache_directory = Path(cache_directory)
        self.cache_directory.mkdir(parents=True, exist_ok=True)
        self.cache_retention_days = cache_retention_days

    async def get_fallback_result(
        self,
        analyzer_name: str,
        customer_id: str,
        start_date: datetime,
        end_date: datetime,
    ) -> Optional[AnalysisResult]:
        """Get fallback result from cached data.

        Args:
            analyzer_name: Name of the analyzer
            customer_id: Customer ID
            start_date: Analysis start date
            end_date: Analysis end date

        Returns:
            Cached analysis result or None if not available
        """
        try:
            # Look for recent cached results (within last 7 days)
            cache_pattern = (
                f"{analyzer_name.lower().replace(' ', '_')}_{customer_id}_*.json"
            )
            cache_files = list(self.cache_directory.glob(cache_pattern))

            if not cache_files:
                logger.info(f"No fallback cache found for {analyzer_name}")
                return None

            # Find most recent cache file
            cache_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
            most_recent = cache_files[0]

            # Check if cache is recent enough (within 7 days)
            cache_age = datetime.now() - datetime.fromtimestamp(
                most_recent.stat().st_mtime
            )
            if cache_age > timedelta(days=self.cache_retention_days):
                logger.info(
                    f"Fallback cache too old for {analyzer_name}: {cache_age.days} days"
                )
                return None

            # Load and adapt cached result
            with open(most_recent, "r", encoding="utf-8") as f:
                cached_data = json.load(f)

            # Create fallback result
            fallback_result = self._create_fallback_result(
                cached_data, analyzer_name, customer_id, start_date, end_date
            )

            logger.info(
                f"Using fallback data for {analyzer_name} from {cache_age.days} days ago",
                extra={
                    "analyzer": analyzer_name,
                    "customer_id": customer_id,
                    "cache_file": str(most_recent),
                    "cache_age_days": cache_age.days,
                },
            )

            return fallback_result

        except Exception as e:
            logger.error(f"Failed to load fallback data for {analyzer_name}: {e}")
            return None

    def _create_fallback_result(
        self,
        cached_data: Dict[str, Any],
        analyzer_name: str,
        customer_id: str,
        start_date: datetime,
        end_date: datetime,
    ) -> AnalysisResult:
        """Create fallback analysis result from cached data.

        Args:
            cached_data: Cached analysis data
            analyzer_name: Name of the analyzer
            customer_id: Customer ID
            start_date: Analysis start date
            end_date: Analysis end date

        Returns:
            Fallback analysis result
        """
        # Extract recommendations from cached data
        recommendations = []
        cached_recs = cached_data.get("recommendations", [])

        for rec_data in cached_recs[:10]:  # Limit to top 10 recommendations
            try:
                rec = Recommendation(
                    type=getattr(
                        RecommendationType,
                        rec_data.get("type", "OPTIMIZE_KEYWORDS"),
                        RecommendationType.OPTIMIZE_KEYWORDS,
                    ),
                    priority=getattr(
                        RecommendationPriority,
                        rec_data.get("priority", "MEDIUM"),
                        RecommendationPriority.MEDIUM,
                    ),
                    title=f"[CACHED] {rec_data.get('title', 'Cached recommendation')}",
                    description=f"Based on recent historical data: {rec_data.get('description', 'No description')}",
                )
                recommendations.append(rec)
            except Exception as e:
                logger.warning(f"Could not deserialize cached recommendation: {e}")
                continue

        # Add fallback disclaimer
        fallback_rec = Recommendation(
            type=RecommendationType.OPTIMIZE_KEYWORDS,
            priority=RecommendationPriority.LOW,
            title="⚠️ Fallback Data Used",
            description=(
                "This analysis used cached fallback data due to API unavailability. "
                "Results may not reflect current performance. "
                "Please retry when API access is restored for up-to-date insights."
            ),
        )
        recommendations.insert(0, fallback_rec)

        # Create metrics from cached data
        cached_metrics = cached_data.get("metrics", {})
        metrics = AnalysisMetrics(
            total_keywords_analyzed=cached_metrics.get("total_keywords_analyzed", 0),
            total_search_terms_analyzed=cached_metrics.get(
                "total_search_terms_analyzed", 0
            ),
            issues_found=len(recommendations) - 1,  # Exclude fallback disclaimer
            critical_issues=0,  # Conservative for fallback data
            potential_cost_savings=cached_metrics.get("potential_cost_savings", 0.0)
            * 0.5,  # Reduce estimates
            potential_conversion_increase=cached_metrics.get(
                "potential_conversion_increase", 0.0
            )
            * 0.5,
            custom_metrics={"is_fallback": True, "cache_source": True},
        )

        return AnalysisResult(
            customer_id=customer_id,
            analysis_type=cached_data.get("analysis_type", "fallback"),
            analyzer_name=analyzer_name,
            start_date=start_date,
            end_date=end_date,
            recommendations=recommendations,
            metrics=metrics,
            raw_data={
                "fallback_notice": "This analysis used cached fallback data",
                "original_timestamp": cached_data.get("timestamp"),
                "cached_data_summary": {
                    "recommendations_count": len(cached_recs),
                    "original_analyzer": cached_data.get("analyzer"),
                },
            },
        )

    async def cache_successful_result(
        self,
        analyzer_name: str,
        customer_id: str,
        result_data: Dict[str, Any],
    ) -> None:
        """Cache a successful analysis result for fallback use.

        Args:
            analyzer_name: Name of the analyzer
            customer_id: Customer ID
            result_data: Analysis result data to cache
        """
        try:
            cache_filename = (
                f"{analyzer_name.lower().replace(' ', '_')}_{customer_id}_"
                f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            )
            cache_path = self.cache_directory / cache_filename

            # Add cache metadata
            cache_data = {
                **result_data,
                "cache_metadata": {
                    "cached_at": datetime.now().isoformat(),
                    "analyzer": analyzer_name,
                    "customer_id": customer_id,
                    "cache_type": "successful_execution",
                },
            }

            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(cache_data, f, indent=2, ensure_ascii=False)

            logger.debug(f"Cached successful result for {analyzer_name}: {cache_path}")

            # Clean up old cache files (keep last 5 for each analyzer/customer)
            await self._cleanup_old_cache(analyzer_name, customer_id)

        except Exception as e:
            logger.warning(f"Failed to cache result for {analyzer_name}: {e}")

    async def _cleanup_old_cache(self, analyzer_name: str, customer_id: str) -> None:
        """Clean up old cache files, keeping only the most recent ones.

        Args:
            analyzer_name: Name of the analyzer
            customer_id: Customer ID
        """
        try:
            cache_pattern = (
                f"{analyzer_name.lower().replace(' ', '_')}_{customer_id}_*.json"
            )
            cache_files = list(self.cache_directory.glob(cache_pattern))

            if len(cache_files) > 5:
                # Sort by modification time and remove oldest
                cache_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
                for old_file in cache_files[5:]:
                    old_file.unlink()
                    logger.debug(f"Removed old cache file: {old_file}")

        except Exception as e:
            logger.warning(f"Failed to cleanup old cache files: {e}")


class PartialResultHandler:
    """Handles partial results when analyzer execution is interrupted."""

    @staticmethod
    def create_partial_result(
        analyzer_name: str,
        customer_id: str,
        start_date: datetime,
        end_date: datetime,
        partial_data: Optional[Dict[str, Any]] = None,
        error_context: Optional[str] = None,
    ) -> AnalysisResult:
        """Create a partial result when full analysis cannot be completed.

        Args:
            analyzer_name: Name of the analyzer
            customer_id: Customer ID
            start_date: Analysis start date
            end_date: Analysis end date
            partial_data: Any partial data that was collected
            error_context: Context about what caused the partial result

        Returns:
            Partial analysis result
        """
        # Create conservative recommendations based on common issues
        recommendations = [
            Recommendation(
                type=RecommendationType.OPTIMIZE_KEYWORDS,
                priority=RecommendationPriority.LOW,
                title="⚠️ Partial Analysis Completed",
                description=(
                    f"Analysis was interrupted but partial data suggests reviewing "
                    f"recent campaign performance. Full analysis recommended when "
                    f"API access is restored. Error context: {error_context or 'Unknown error'}"
                ),
            )
        ]

        # Add data-specific recommendations if we have partial data
        if partial_data:
            if partial_data.get("high_cost_keywords"):
                recommendations.append(
                    Recommendation(
                        type=RecommendationType.PAUSE_KEYWORDS,
                        priority=RecommendationPriority.MEDIUM,
                        title="Review High-Cost Keywords (Partial Data)",
                        description=(
                            "Partial analysis identified potential high-cost keywords. "
                            "Manual review recommended for cost optimization."
                        ),
                    )
                )

        metrics = AnalysisMetrics(
            total_keywords_analyzed=partial_data.get("keywords_processed", 0)
            if partial_data
            else 0,
            total_search_terms_analyzed=partial_data.get("search_terms_processed", 0)
            if partial_data
            else 0,
            issues_found=len(recommendations),
            critical_issues=0,  # Conservative for partial data
            potential_cost_savings=0.0,  # Cannot estimate from partial data
            potential_conversion_increase=0.0,
            metadata={"is_partial": True, "error_context": error_context},
        )

        return AnalysisResult(
            customer_id=customer_id,
            analysis_type="partial",
            analyzer_name=analyzer_name,
            start_date=start_date,
            end_date=end_date,
            recommendations=recommendations,
            metrics=metrics,
            raw_data={
                "partial_data_notice": "This is a partial analysis due to execution interruption",
                "partial_data": partial_data or {},
                "error_context": error_context,
                "completion_percentage": partial_data.get("completion_percentage", 0)
                if partial_data
                else 0,
            },
        )


class GracefulDegradationManager:
    """Manages graceful degradation strategies for analyzer failures."""

    def __init__(self, fallback_data_source: FallbackDataSource):
        """Initialize graceful degradation manager.

        Args:
            fallback_data_source: Source for fallback data
        """
        self.fallback_data_source = fallback_data_source
        self.partial_result_handler = PartialResultHandler()

    async def handle_analyzer_failure(
        self,
        analyzer_name: str,
        customer_id: str,
        start_date: datetime,
        end_date: datetime,
        error: Exception,
        partial_data: Optional[Dict[str, Any]] = None,
    ) -> AnalysisResult:
        """Handle analyzer failure with graceful degradation.

        Args:
            analyzer_name: Name of the failed analyzer
            customer_id: Customer ID
            start_date: Analysis start date
            end_date: Analysis end date
            error: The error that caused the failure
            partial_data: Any partial data collected before failure

        Returns:
            Fallback or partial analysis result
        """
        logger.info(
            f"Attempting graceful degradation for {analyzer_name}",
            extra={
                "analyzer": analyzer_name,
                "customer_id": customer_id,
                "error_type": type(error).__name__,
            },
        )

        # Strategy 1: Try to use cached fallback data
        fallback_result = await self.fallback_data_source.get_fallback_result(
            analyzer_name, customer_id, start_date, end_date
        )

        if fallback_result:
            logger.info(f"Using cached fallback data for {analyzer_name}")
            return fallback_result

        # Strategy 2: Create partial result from any data we collected
        if partial_data and partial_data.get("completion_percentage", 0) > 10:
            logger.info(
                f"Creating partial result for {analyzer_name} with {partial_data.get('completion_percentage', 0)}% completion"
            )
            return self.partial_result_handler.create_partial_result(
                analyzer_name,
                customer_id,
                start_date,
                end_date,
                partial_data,
                str(error),
            )

        # Strategy 3: Create minimal result with basic recommendations
        logger.info(f"Creating minimal fallback result for {analyzer_name}")
        return self._create_minimal_result(
            analyzer_name, customer_id, start_date, end_date, error
        )

    def _create_minimal_result(
        self,
        analyzer_name: str,
        customer_id: str,
        start_date: datetime,
        end_date: datetime,
        error: Exception,
    ) -> AnalysisResult:
        """Create minimal result when no fallback data is available.

        Args:
            analyzer_name: Name of the analyzer
            customer_id: Customer ID
            start_date: Analysis start date
            end_date: Analysis end date
            error: The error that caused the failure

        Returns:
            Minimal analysis result with basic recommendations
        """
        # Create generic recommendations based on analyzer type
        recommendations = self._get_generic_recommendations(analyzer_name, error)

        metrics = AnalysisMetrics(
            total_keywords_analyzed=0,
            total_search_terms_analyzed=0,
            issues_found=len(recommendations),
            critical_issues=0,
            potential_cost_savings=0.0,
            potential_conversion_increase=0.0,
            custom_metrics={
                "is_minimal_fallback": True,
                "original_error": str(error),
                "error_type": type(error).__name__,
            },
        )

        return AnalysisResult(
            customer_id=customer_id,
            analysis_type="minimal_fallback",
            analyzer_name=analyzer_name,
            start_date=start_date,
            end_date=end_date,
            recommendations=recommendations,
            metrics=metrics,
            raw_data={
                "fallback_notice": "Minimal fallback result due to analyzer failure",
                "error": str(error),
                "suggested_actions": [
                    "Check API connectivity and authentication",
                    "Verify quota availability",
                    "Retry analysis when conditions improve",
                    "Contact support if issues persist",
                ],
            },
        )

    def _get_generic_recommendations(
        self, analyzer_name: str, error: Exception
    ) -> List[Recommendation]:
        """Get generic recommendations based on analyzer type and error.

        Args:
            analyzer_name: Name of the analyzer
            error: The error that occurred

        Returns:
            List of generic recommendations
        """
        recommendations = []
        error_str = str(error).lower()

        # Error-specific recommendations
        if "quota" in error_str or "rate limit" in error_str:
            recommendations.append(
                Recommendation(
                    type=RecommendationType.OPTIMIZE_KEYWORDS,
                    priority=RecommendationPriority.HIGH,
                    title="API Quota Issue Detected",
                    description=(
                        "Analysis failed due to API quota limitations. "
                        "Consider scheduling analyzer runs during off-peak hours "
                        "or implementing quota management."
                    ),
                )
            )
        elif "authentication" in error_str or "unauthorized" in error_str:
            recommendations.append(
                Recommendation(
                    type=RecommendationType.OPTIMIZE_KEYWORDS,
                    priority=RecommendationPriority.CRITICAL,
                    title="Authentication Issue Detected",
                    description=(
                        "Analysis failed due to authentication problems. "
                        "Please verify your Google Ads API credentials and refresh tokens."
                    ),
                )
            )
        elif "timeout" in error_str:
            recommendations.append(
                Recommendation(
                    type=RecommendationType.OPTIMIZE_KEYWORDS,
                    priority=RecommendationPriority.MEDIUM,
                    title="Performance Issue Detected",
                    description=(
                        "Analysis failed due to timeout. Consider analyzing smaller "
                        "date ranges or using filters to reduce data volume."
                    ),
                )
            )

        # Analyzer-specific generic recommendations
        if "keyword" in analyzer_name.lower():
            recommendations.append(
                Recommendation(
                    type=RecommendationType.OPTIMIZE_KEYWORDS,
                    priority=RecommendationPriority.LOW,
                    title="General Keyword Optimization",
                    description=(
                        "While waiting for full analysis, consider reviewing "
                        "top-spending keywords manually for obvious optimization opportunities."
                    ),
                )
            )
        elif "search term" in analyzer_name.lower():
            recommendations.append(
                Recommendation(
                    type=RecommendationType.ADD_NEGATIVE_KEYWORDS,
                    priority=RecommendationPriority.LOW,
                    title="General Search Term Review",
                    description=(
                        "Consider reviewing search terms report manually for "
                        "obvious negative keyword opportunities and new keyword ideas."
                    ),
                )
            )

        return recommendations


class CheckpointSystem:
    """System for saving analyzer progress checkpoints during long-running operations."""

    def __init__(self, checkpoint_directory: Union[str, Path] = "cache/checkpoints"):
        """Initialize checkpoint system.

        Args:
            checkpoint_directory: Directory to store checkpoint files
        """
        self.checkpoint_directory = Path(checkpoint_directory)
        self.checkpoint_directory.mkdir(parents=True, exist_ok=True)

    async def save_checkpoint(
        self,
        analyzer_name: str,
        customer_id: str,
        execution_id: str,
        progress_data: Dict[str, Any],
        completion_percentage: float,
    ) -> None:
        """Save a checkpoint of analyzer progress.

        Args:
            analyzer_name: Name of the analyzer
            customer_id: Customer ID
            execution_id: Unique execution ID
            progress_data: Current progress data
            completion_percentage: Completion percentage (0.0 to 100.0)
        """
        try:
            checkpoint_filename = f"{execution_id}_checkpoint.json"
            checkpoint_path = self.checkpoint_directory / checkpoint_filename

            checkpoint_data = {
                "execution_id": execution_id,
                "analyzer_name": analyzer_name,
                "customer_id": customer_id,
                "completion_percentage": completion_percentage,
                "checkpoint_timestamp": datetime.now().isoformat(),
                "progress_data": progress_data,
            }

            with open(checkpoint_path, "w", encoding="utf-8") as f:
                json.dump(checkpoint_data, f, indent=2, ensure_ascii=False)

            logger.debug(
                f"Checkpoint saved for {analyzer_name}: {completion_percentage:.1f}% complete"
            )

        except Exception as e:
            logger.warning(f"Failed to save checkpoint for {execution_id}: {e}")

    async def load_checkpoint(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """Load checkpoint data for resuming execution.

        Args:
            execution_id: Unique execution ID

        Returns:
            Checkpoint data or None if not found
        """
        try:
            checkpoint_filename = f"{execution_id}_checkpoint.json"
            checkpoint_path = self.checkpoint_directory / checkpoint_filename

            if not checkpoint_path.exists():
                return None

            with open(checkpoint_path, "r", encoding="utf-8") as f:
                checkpoint_data = json.load(f)

            # Check if checkpoint is recent (within 1 hour)
            checkpoint_time = datetime.fromisoformat(
                checkpoint_data["checkpoint_timestamp"]
            )
            if datetime.now() - checkpoint_time > timedelta(hours=1):
                logger.info(f"Checkpoint too old for {execution_id}, ignoring")
                return None

            logger.info(
                f"Loaded checkpoint for {checkpoint_data['analyzer_name']}: "
                f"{checkpoint_data['completion_percentage']:.1f}% complete"
            )

            return checkpoint_data

        except Exception as e:
            logger.warning(f"Failed to load checkpoint for {execution_id}: {e}")
            return None

    async def cleanup_checkpoints(self, max_age_hours: int = 24) -> None:
        """Clean up old checkpoint files.

        Args:
            max_age_hours: Maximum age of checkpoints to keep
        """
        try:
            cutoff_time = datetime.now() - timedelta(hours=max_age_hours)

            for checkpoint_file in self.checkpoint_directory.glob("*_checkpoint.json"):
                file_time = datetime.fromtimestamp(checkpoint_file.stat().st_mtime)
                if file_time < cutoff_time:
                    checkpoint_file.unlink()
                    logger.debug(f"Cleaned up old checkpoint: {checkpoint_file}")

        except Exception as e:
            logger.warning(f"Failed to cleanup checkpoints: {e}")
