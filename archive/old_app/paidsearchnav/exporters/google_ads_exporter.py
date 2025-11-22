"""Google Ads Export Service for generating import-ready files."""

import asyncio
import logging
import tempfile
import uuid
import zipfile
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional

from paidsearchnav.core.models.analysis import (
    Recommendation,
    RecommendationType,
)
from paidsearchnav.core.models.export_models import (
    BidAdjustment,
    BidAdjustmentsFile,
    CampaignChange,
    CampaignChangesFile,
    ExportRequest,
    ExportResult,
    ExportStatus,
    ImportPackage,
    KeywordChange,
    KeywordChangesFile,
    NegativeKeyword,
    NegativeKeywordsFile,
)
from paidsearchnav.exporters.formatters import (
    BidAdjustmentFormatter,
    CampaignFormatter,
    KeywordFormatter,
    NegativeKeywordFormatter,
)
from paidsearchnav.exporters.validators import FormatValidator, ImportSimulator
from paidsearchnav.storage.repository import AnalysisRepository

# Optional import for S3 file management
try:
    from paidsearchnav.services.file_manager import AuditFileManagerService
except ImportError:
    AuditFileManagerService = None

logger = logging.getLogger(__name__)


class GoogleAdsExportService:
    """Service for generating Google Ads import-ready files from analysis results."""

    def __init__(
        self,
        repository: AnalysisRepository,
        file_manager: Optional[Any] = None,
    ):
        """
        Initialize the Google Ads export service.

        Args:
            repository: Analysis repository for fetching results
            file_manager: Optional file manager for S3 storage
        """
        self.repository = repository
        self.file_manager = file_manager
        self.temp_files = []  # Track temporary files for cleanup

        # Initialize formatters
        self.keyword_formatter = KeywordFormatter()
        self.negative_formatter = NegativeKeywordFormatter()
        self.bid_formatter = BidAdjustmentFormatter()
        self.campaign_formatter = CampaignFormatter()

        # Initialize validators
        self.format_validator = FormatValidator()
        self.import_simulator = ImportSimulator()

    @contextmanager
    def _temp_file_manager(self, suffix: str = ".csv", mode: str = "w"):
        """Context manager for temporary file creation and cleanup."""
        temp_file = None
        temp_path = None
        try:
            temp_file = tempfile.NamedTemporaryFile(
                mode=mode,
                suffix=suffix,
                delete=False,
                encoding="utf-8" if "b" not in mode else None,
            )
            temp_path = Path(temp_file.name)
            self.temp_files.append(temp_path)
            yield temp_file, temp_path
        finally:
            if temp_file:
                temp_file.close()

    def cleanup_temp_files(self):
        """Clean up all temporary files created during export."""
        for temp_path in self.temp_files:
            try:
                if temp_path.exists():
                    temp_path.unlink()
            except Exception as e:
                logger.warning(f"Failed to cleanup temp file {temp_path}: {e}")
        self.temp_files.clear()

    async def generate_keyword_changes(
        self, analysis_id: str, recommendations: List[Recommendation]
    ) -> KeywordChangesFile:
        """
        Generate keyword changes file from recommendations.

        Args:
            analysis_id: Analysis ID
            recommendations: List of recommendations

        Returns:
            KeywordChangesFile with formatted data
        """
        logger.info(f"Generating keyword changes for analysis {analysis_id}")

        # Filter relevant recommendations
        keyword_recs = [
            r
            for r in recommendations
            if r.type
            in [
                RecommendationType.ADD_KEYWORD,
                RecommendationType.CHANGE_MATCH_TYPE,
                RecommendationType.PAUSE_KEYWORD,
            ]
        ]

        # Convert recommendations to keyword changes
        changes = []
        for rec in keyword_recs:
            change = self._recommendation_to_keyword_change(rec)
            if change:
                changes.append(change)

        # Create and validate file
        file = self.keyword_formatter.create_file(changes, validate=True)

        # Generate CSV content if valid
        if not file.validation_errors and changes:
            try:
                csv_content = self.keyword_formatter.format_to_csv(changes)

                # Save to temp file using context manager
                with self._temp_file_manager(suffix=".csv", mode="w") as (f, temp_path):
                    f.write(csv_content)
                    file.file_path = temp_path
            except Exception as e:
                logger.error(f"Failed to write keyword changes CSV: {e}")
                file.validation_errors.append(f"Failed to generate CSV: {str(e)}")

        logger.info(
            f"Generated keyword changes file with {len(changes)} changes, "
            f"{len(file.validation_errors)} errors"
        )
        return file

    async def generate_negative_keywords(
        self, analysis_id: str, negative_recommendations: List[Recommendation]
    ) -> NegativeKeywordsFile:
        """
        Generate negative keywords file from recommendations.

        Args:
            analysis_id: Analysis ID
            negative_recommendations: List of negative keyword recommendations

        Returns:
            NegativeKeywordsFile with formatted data
        """
        logger.info(f"Generating negative keywords for analysis {analysis_id}")

        # Filter negative keyword recommendations
        negative_recs = [
            r
            for r in negative_recommendations
            if r.type
            in [
                RecommendationType.ADD_NEGATIVE,
                RecommendationType.ADD_NEGATIVE_KEYWORDS,
            ]
        ]

        # Convert recommendations to negative keywords
        negatives = []
        for rec in negative_recs:
            negative = self._recommendation_to_negative_keyword(rec)
            if negative:
                negatives.append(negative)

        # Create and validate file
        file = self.negative_formatter.create_file(negatives, validate=True)

        # Generate CSV content if valid
        if not file.validation_errors and negatives:
            try:
                csv_content = self.negative_formatter.format_to_csv(negatives)

                # Save to temp file using context manager
                with self._temp_file_manager(suffix=".csv", mode="w") as (f, temp_path):
                    f.write(csv_content)
                    file.file_path = temp_path
            except Exception as e:
                logger.error(f"Failed to write negative keywords CSV: {e}")
                file.validation_errors.append(f"Failed to generate CSV: {str(e)}")

        logger.info(
            f"Generated negative keywords file with {len(negatives)} negatives, "
            f"{len(file.validation_errors)} errors"
        )
        return file

    async def generate_bid_adjustments(
        self, analysis_id: str, bid_recommendations: List[Recommendation]
    ) -> BidAdjustmentsFile:
        """
        Generate bid adjustments file from recommendations.

        Args:
            analysis_id: Analysis ID
            bid_recommendations: List of bid adjustment recommendations

        Returns:
            BidAdjustmentsFile with formatted data
        """
        logger.info(f"Generating bid adjustments for analysis {analysis_id}")

        # Filter bid adjustment recommendations
        bid_recs = [
            r
            for r in bid_recommendations
            if r.type
            in [
                RecommendationType.ADJUST_BID,
                RecommendationType.OPTIMIZE_LOCATION,
                RecommendationType.OPTIMIZE_BIDDING,
            ]
        ]

        # Convert recommendations to bid adjustments
        adjustments = []
        for rec in bid_recs:
            adjustment = self._recommendation_to_bid_adjustment(rec)
            if adjustment:
                adjustments.append(adjustment)

        # Create and validate file
        file = self.bid_formatter.create_file(adjustments, validate=True)

        # Generate CSV content if valid
        if not file.validation_errors and adjustments:
            try:
                csv_content = self.bid_formatter.format_to_csv(adjustments)

                # Save to temp file using context manager
                with self._temp_file_manager(suffix=".csv", mode="w") as (f, temp_path):
                    f.write(csv_content)
                    file.file_path = temp_path
            except Exception as e:
                logger.error(f"Failed to write bid adjustments CSV: {e}")
                file.validation_errors.append(f"Failed to generate CSV: {str(e)}")

        logger.info(
            f"Generated bid adjustments file with {len(adjustments)} adjustments, "
            f"{len(file.validation_errors)} errors"
        )
        return file

    async def generate_campaign_changes(
        self, analysis_id: str, campaign_recommendations: List[Recommendation]
    ) -> CampaignChangesFile:
        """
        Generate campaign changes file from recommendations.

        Args:
            analysis_id: Analysis ID
            campaign_recommendations: List of campaign recommendations

        Returns:
            CampaignChangesFile with formatted data
        """
        logger.info(f"Generating campaign changes for analysis {analysis_id}")

        # Filter campaign change recommendations
        campaign_recs = [
            r
            for r in campaign_recommendations
            if r.type
            in [
                RecommendationType.BUDGET_OPTIMIZATION,
                RecommendationType.OPTIMIZE_BIDDING,
            ]
        ]

        # Convert recommendations to campaign changes
        changes = []
        for rec in campaign_recs:
            change = self._recommendation_to_campaign_change(rec)
            if change:
                changes.append(change)

        # Create and validate file
        file = self.campaign_formatter.create_file(changes, validate=True)

        # Generate CSV content if valid
        if not file.validation_errors and changes:
            try:
                csv_content = self.campaign_formatter.format_to_csv(changes)

                # Save to temp file using context manager
                with self._temp_file_manager(suffix=".csv", mode="w") as (f, temp_path):
                    f.write(csv_content)
                    file.file_path = temp_path
            except Exception as e:
                logger.error(f"Failed to write campaign changes CSV: {e}")
                file.validation_errors.append(f"Failed to generate CSV: {str(e)}")

        logger.info(
            f"Generated campaign changes file with {len(changes)} changes, "
            f"{len(file.validation_errors)} errors"
        )
        return file

    async def create_import_package(self, analysis_id: str) -> ImportPackage:
        """
        Create a complete import package with all export files.

        Args:
            analysis_id: Analysis ID to export from

        Returns:
            ImportPackage with ZIP file containing all exports
        """
        logger.info(f"Creating import package for analysis {analysis_id}")

        try:
            # Fetch analysis result
            analysis = await self.repository.get_analysis(analysis_id)
            if not analysis:
                raise ValueError(f"Analysis {analysis_id} not found")

            # Extract customer ID
            customer_id = analysis.customer_id

            # Validate recommendations exist
            if not analysis.recommendations:
                logger.warning(f"No recommendations found for analysis {analysis_id}")
                return ImportPackage(
                    package_id=str(uuid.uuid4()),
                    analysis_id=analysis_id,
                    customer_id=customer_id,
                    files=[],
                    status=ExportStatus.COMPLETED,
                    total_changes=0,
                )

            # Generate all export files
            tasks = [
                self.generate_keyword_changes(analysis_id, analysis.recommendations),
                self.generate_negative_keywords(analysis_id, analysis.recommendations),
                self.generate_bid_adjustments(analysis_id, analysis.recommendations),
                self.generate_campaign_changes(analysis_id, analysis.recommendations),
            ]

            files = await asyncio.gather(*tasks)

            # Create package
            package = ImportPackage(
                package_id=str(uuid.uuid4()),
                analysis_id=analysis_id,
                customer_id=customer_id,
                files=[
                    f for f in files if f and f.row_count > 0
                ],  # Only include non-empty files
                status=ExportStatus.PROCESSING,
            )

            # Calculate total changes
            package.total_changes = sum(f.row_count for f in package.files)

            # Create ZIP file if there are files to package
            if package.files:
                try:
                    zip_path = await self._create_zip_package(package)
                    package.package_path = zip_path

                    # Upload to S3 if file manager available
                    if self.file_manager:
                        s3_key, s3_url = await self._upload_package_to_s3(
                            package, customer_id
                        )
                        package.s3_key = s3_key
                        package.s3_url = s3_url
                except Exception as e:
                    logger.error(f"Failed to create/upload package: {e}")
                    package.errors.append(f"Package creation failed: {str(e)}")

            # Run import simulation
            simulation_success, simulation_issues = await self._run_import_simulation(
                package
            )
            if not simulation_success:
                for issue_type, issues in simulation_issues.items():
                    package.errors.extend(
                        [f"{issue_type}: {issue}" for issue in issues]
                    )

            # Update status
            package.status = (
                ExportStatus.COMPLETED if package.is_valid else ExportStatus.FAILED
            )

            logger.info(
                f"Created import package with {len(package.files)} files, "
                f"{package.total_changes} total changes"
            )
            return package

        finally:
            # Always cleanup temporary files
            self.cleanup_temp_files()

    async def export_from_analysis(self, request: ExportRequest) -> ExportResult:
        """
        Export Google Ads import files from an analysis.

        Args:
            request: Export request with configuration

        Returns:
            ExportResult with generated files or errors
        """
        logger.info(f"Starting export for analysis {request.analysis_id}")

        result = ExportResult(request=request, status=ExportStatus.PROCESSING)

        try:
            # Fetch analysis
            analysis = await self.repository.get_analysis(request.analysis_id)
            if not analysis:
                result.errors.append(f"Analysis {request.analysis_id} not found")
                result.status = ExportStatus.FAILED
                result.mark_completed()
                return result

            # Validate customer ID matches
            if analysis.customer_id != request.customer_id:
                result.errors.append("Customer ID mismatch")
                result.status = ExportStatus.FAILED
                result.mark_completed()
                return result

            # Create import package if requested
            if request.create_package:
                package = await self.create_import_package(request.analysis_id)
                result.package = package

                # Add any package errors to result
                if package.errors:
                    result.errors.extend(package.errors)

                # Add validation warnings
                for file in package.files:
                    if file.validation_warnings:
                        result.warnings.extend(file.validation_warnings)
            else:
                # Generate individual files as requested
                files = []
                if request.include_keyword_changes:
                    file = await self.generate_keyword_changes(
                        request.analysis_id, analysis.recommendations
                    )
                    files.append(file)

                if request.include_negative_keywords:
                    file = await self.generate_negative_keywords(
                        request.analysis_id, analysis.recommendations
                    )
                    files.append(file)

                if request.include_bid_adjustments:
                    file = await self.generate_bid_adjustments(
                        request.analysis_id, analysis.recommendations
                    )
                    files.append(file)

                if request.include_campaign_changes:
                    file = await self.generate_campaign_changes(
                        request.analysis_id, analysis.recommendations
                    )
                    files.append(file)

                # Create minimal package
                result.package = ImportPackage(
                    package_id=str(uuid.uuid4()),
                    analysis_id=request.analysis_id,
                    customer_id=request.customer_id,
                    files=files,
                    status=ExportStatus.COMPLETED,
                )

            result.mark_completed()

        except Exception as e:
            logger.error(f"Export failed for analysis {request.analysis_id}: {e}")
            result.errors.append(str(e))
            result.status = ExportStatus.FAILED
            result.mark_completed()

        return result

    def _recommendation_to_keyword_change(
        self, recommendation: Recommendation
    ) -> Optional[KeywordChange]:
        """Convert a recommendation to a keyword change."""
        try:
            data = recommendation.action_data

            # Handle different recommendation types
            if recommendation.type == RecommendationType.ADD_KEYWORD:
                return KeywordChange(
                    customer_id=data.get("customer_id", ""),
                    campaign=data.get("campaign", ""),
                    ad_group=data.get("ad_group", ""),
                    keyword=data.get("keyword", ""),
                    match_type=data.get("match_type", "Exact"),
                    status="Enabled",
                    max_cpc=data.get("max_cpc"),
                    final_url=data.get("final_url"),
                )

            elif recommendation.type == RecommendationType.CHANGE_MATCH_TYPE:
                return KeywordChange(
                    customer_id=data.get("customer_id", ""),
                    campaign=data.get("campaign", ""),
                    ad_group=data.get("ad_group", ""),
                    keyword=data.get("keyword", ""),
                    match_type=data.get("new_match_type", "Exact"),
                    status="Enabled",
                    max_cpc=data.get("max_cpc"),
                )

            elif recommendation.type == RecommendationType.PAUSE_KEYWORD:
                return KeywordChange(
                    customer_id=data.get("customer_id", ""),
                    campaign=data.get("campaign", ""),
                    ad_group=data.get("ad_group", ""),
                    keyword=data.get("keyword", ""),
                    match_type=data.get("match_type", "Exact"),
                    status="Paused",
                )

        except Exception as e:
            logger.warning(f"Failed to convert recommendation to keyword change: {e}")

        return None

    def _recommendation_to_negative_keyword(
        self, recommendation: Recommendation
    ) -> Optional[NegativeKeyword]:
        """Convert a recommendation to a negative keyword."""
        try:
            data = recommendation.action_data

            return NegativeKeyword(
                customer_id=data.get("customer_id", ""),
                campaign=data.get("campaign", ""),
                ad_group=data.get("ad_group"),  # None for campaign-level
                keyword=data.get("keyword", ""),
                match_type=data.get("match_type", "Exact"),
            )

        except Exception as e:
            logger.warning(f"Failed to convert recommendation to negative keyword: {e}")

        return None

    def _recommendation_to_bid_adjustment(
        self, recommendation: Recommendation
    ) -> Optional[BidAdjustment]:
        """Convert a recommendation to a bid adjustment."""
        try:
            data = recommendation.action_data

            # Format adjustment value
            adj_value = data.get("adjustment_value", 0)
            if isinstance(adj_value, (int, float)):
                adj_str = f"+{adj_value}%" if adj_value > 0 else f"{adj_value}%"
            else:
                adj_str = str(adj_value)

            return BidAdjustment(
                customer_id=data.get("customer_id", ""),
                campaign=data.get("campaign", ""),
                location=data.get("location"),
                device=data.get("device"),
                bid_adjustment=adj_str,
            )

        except Exception as e:
            logger.warning(f"Failed to convert recommendation to bid adjustment: {e}")

        return None

    def _recommendation_to_campaign_change(
        self, recommendation: Recommendation
    ) -> Optional[CampaignChange]:
        """Convert a recommendation to a campaign change."""
        try:
            data = recommendation.action_data

            return CampaignChange(
                customer_id=data.get("customer_id", ""),
                campaign=data.get("campaign", ""),
                status=data.get("status"),
                budget=data.get("budget"),
                bid_strategy=data.get("bid_strategy"),
                target_cpa=data.get("target_cpa"),
                target_roas=data.get("target_roas"),
            )

        except Exception as e:
            logger.warning(f"Failed to convert recommendation to campaign change: {e}")

        return None

    async def _create_zip_package(self, package: ImportPackage) -> Path:
        """Create a ZIP file containing all export files."""
        # Use NamedTemporaryFile for security (avoid deprecated mktemp)
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp_file:
            zip_path = Path(tmp_file.name)

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for file in package.files:
                if file.file_path and file.file_path.exists():
                    zf.write(file.file_path, file.file_name)

        return zip_path

    async def _upload_package_to_s3(
        self, package: ImportPackage, customer_id: str
    ) -> tuple[str, str]:
        """Upload package to S3 and return key and URL."""
        if not self.file_manager:
            return "", ""

        # Generate S3 key
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        s3_key = (
            f"customers/{customer_id}/actionable_files/{timestamp}_import_package.zip"
        )

        # Upload file
        with open(package.package_path, "rb") as f:
            content = f.read()
            result = await self.file_manager.upload_actionable_file(
                customer_id=customer_id,
                file_name=f"{timestamp}_import_package.zip",
                content=content,
                content_type="application/zip",
            )

        return s3_key, result.get("url", "")

    async def _run_import_simulation(self, package: ImportPackage) -> tuple[bool, dict]:
        """Run import simulation on package files."""
        # Extract data from files
        keyword_changes = []
        negative_keywords = []
        bid_adjustments = []
        campaign_changes = []

        for file in package.files:
            if isinstance(file, KeywordChangesFile):
                keyword_changes.extend(file.changes)
            elif isinstance(file, NegativeKeywordsFile):
                negative_keywords.extend(file.negatives)
            elif isinstance(file, BidAdjustmentsFile):
                bid_adjustments.extend(file.adjustments)
            elif isinstance(file, CampaignChangesFile):
                campaign_changes.extend(file.changes)

        # Run simulation (only pass non-empty lists)
        return self.import_simulator.run_full_simulation(
            keyword_changes=keyword_changes or None,
            negative_keywords=negative_keywords or None,
            bid_adjustments=bid_adjustments or None,
            campaign_changes=campaign_changes or None,
        )
