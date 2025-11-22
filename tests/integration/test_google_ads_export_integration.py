"""Integration tests for Google Ads export functionality."""

import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from paidsearchnav_mcp.models.analysis import (
    AnalysisMetrics,
    AnalysisResult,
    Recommendation,
    RecommendationPriority,
    RecommendationType,
)
from paidsearchnav_mcp.models.export_models import (
    ExportRequest,
    ExportStatus,
)
from paidsearchnav_mcp.exporters.google_ads_exporter import GoogleAdsExportService


@pytest.fixture
def complete_analysis():
    """Create a complete analysis with various recommendations."""
    return AnalysisResult(
        analysis_id="integration-test-123",
        customer_id="9876543210",
        analysis_type="comprehensive",
        analyzer_name="IntegrationTestAnalyzer",
        start_date=datetime(2024, 1, 1),
        end_date=datetime(2024, 3, 31),
        status="completed",
        metrics=AnalysisMetrics(
            total_keywords_analyzed=1000,
            total_search_terms_analyzed=5000,
            total_campaigns_analyzed=10,
            issues_found=25,
            critical_issues=5,
            potential_cost_savings=2500.00,
            potential_conversion_increase=15.0,
        ),
        recommendations=[
            # Keyword recommendations
            Recommendation(
                type=RecommendationType.ADD_KEYWORD,
                priority=RecommendationPriority.HIGH,
                title="Add high-value keyword",
                description="Strong performance in search terms",
                campaign_id="camp-001",
                ad_group_id="ag-001",
                estimated_cost_savings=100.00,
                action_data={
                    "customer_id": "9876543210",
                    "campaign": "Brand Campaign",
                    "ad_group": "Core Products",
                    "keyword": "premium running shoes",
                    "match_type": "Exact",
                    "max_cpc": 2.50,
                    "final_url": "https://example.com/running-shoes",
                },
            ),
            Recommendation(
                type=RecommendationType.CHANGE_MATCH_TYPE,
                priority=RecommendationPriority.MEDIUM,
                title="Change match type for better control",
                description="Too broad, causing irrelevant traffic",
                campaign_id="camp-001",
                ad_group_id="ag-002",
                keyword_id="kw-123",
                action_data={
                    "customer_id": "9876543210",
                    "campaign": "Brand Campaign",
                    "ad_group": "Accessories",
                    "keyword": "shoe accessories",
                    "old_match_type": "Broad",
                    "new_match_type": "Phrase",
                    "max_cpc": 1.75,
                },
            ),
            Recommendation(
                type=RecommendationType.PAUSE_KEYWORD,
                priority=RecommendationPriority.HIGH,
                title="Pause underperforming keyword",
                description="High cost, no conversions in 90 days",
                campaign_id="camp-002",
                ad_group_id="ag-003",
                keyword_id="kw-456",
                estimated_cost_savings=500.00,
                action_data={
                    "customer_id": "9876543210",
                    "campaign": "Generic Campaign",
                    "ad_group": "Broad Terms",
                    "keyword": "shoes online",
                    "match_type": "Broad",
                },
            ),
            # Negative keyword recommendations
            Recommendation(
                type=RecommendationType.ADD_NEGATIVE,
                priority=RecommendationPriority.HIGH,
                title="Add negative to block irrelevant traffic",
                description="'free' queries never convert",
                campaign_id="camp-001",
                estimated_cost_savings=200.00,
                action_data={
                    "customer_id": "9876543210",
                    "campaign": "Brand Campaign",
                    "keyword": "free",
                    "match_type": "Broad",
                },
            ),
            Recommendation(
                type=RecommendationType.ADD_NEGATIVE_KEYWORDS,
                priority=RecommendationPriority.MEDIUM,
                title="Add ad group negative",
                description="Block competitor terms",
                campaign_id="camp-001",
                ad_group_id="ag-001",
                action_data={
                    "customer_id": "9876543210",
                    "campaign": "Brand Campaign",
                    "ad_group": "Core Products",
                    "keyword": "competitor brand",
                    "match_type": "Phrase",
                },
            ),
            # Bid adjustment recommendations
            Recommendation(
                type=RecommendationType.OPTIMIZE_LOCATION,
                priority=RecommendationPriority.MEDIUM,
                title="Increase bid for high-performing location",
                description="New York shows 50% better conversion rate",
                campaign_id="camp-001",
                estimated_conversion_increase=10.0,
                action_data={
                    "customer_id": "9876543210",
                    "campaign": "Brand Campaign",
                    "location": "New York",
                    "adjustment_value": 25,
                },
            ),
            Recommendation(
                type=RecommendationType.ADJUST_BID,
                priority=RecommendationPriority.LOW,
                title="Decrease mobile bid",
                description="Mobile traffic underperforming",
                campaign_id="camp-002",
                action_data={
                    "customer_id": "9876543210",
                    "campaign": "Generic Campaign",
                    "device": "Mobile",
                    "adjustment_type": "device",
                    "adjustment_value": -20,
                },
            ),
            # Campaign recommendations
            Recommendation(
                type=RecommendationType.BUDGET_OPTIMIZATION,
                priority=RecommendationPriority.HIGH,
                title="Increase budget for constrained campaign",
                description="Campaign losing impression share due to budget",
                campaign_id="camp-001",
                estimated_conversion_increase=20.0,
                action_data={
                    "customer_id": "9876543210",
                    "campaign": "Brand Campaign",
                    "budget": 500.00,
                    "bid_strategy": "Target CPA",
                    "target_cpa": 30.00,
                },
            ),
            Recommendation(
                type=RecommendationType.OPTIMIZE_BIDDING,
                priority=RecommendationPriority.MEDIUM,
                title="Switch to Target ROAS",
                description="Campaign has consistent ROAS, automate bidding",
                campaign_id="camp-002",
                action_data={
                    "customer_id": "9876543210",
                    "campaign": "Generic Campaign",
                    "bid_strategy": "Target ROAS",
                    "target_roas": 4.50,
                },
            ),
        ],
    )


class TestGoogleAdsExportIntegration:
    """Integration tests for Google Ads export service."""

    @pytest.mark.asyncio
    async def test_end_to_end_export_with_validation(self, complete_analysis):
        """Test complete export process with validation."""
        # Setup mock repository
        mock_repo = AsyncMock()
        mock_repo.get_analysis = AsyncMock(return_value=complete_analysis)

        # Create service without file manager (local only)
        service = GoogleAdsExportService(mock_repo)

        # Create export request
        request = ExportRequest(
            analysis_id="integration-test-123",
            customer_id="9876543210",
            include_keyword_changes=True,
            include_negative_keywords=True,
            include_bid_adjustments=True,
            include_campaign_changes=True,
            create_package=True,
            validate_before_export=True,
        )

        # Execute export
        with patch("tempfile.mktemp") as mock_mktemp:
            temp_dir = tempfile.mkdtemp()
            mock_mktemp.return_value = str(Path(temp_dir) / "package.zip")

            result = await service.export_from_analysis(request)

        # Verify result
        assert result.status == ExportStatus.COMPLETED
        assert result.package is not None
        assert len(result.package.files) == 4  # All file types
        assert result.package.total_changes > 0

        # Verify individual files
        keyword_file = next(
            f for f in result.package.files if f.file_name == "keyword_changes.csv"
        )
        assert keyword_file.row_count == 3  # ADD, CHANGE_MATCH_TYPE, PAUSE

        negative_file = next(
            f for f in result.package.files if f.file_name == "negative_keywords.csv"
        )
        assert negative_file.row_count == 2  # Campaign and ad group level

        bid_file = next(
            f for f in result.package.files if f.file_name == "bid_adjustments.csv"
        )
        assert bid_file.row_count == 2  # Location and device

        campaign_file = next(
            f for f in result.package.files if f.file_name == "campaign_changes.csv"
        )
        assert campaign_file.row_count == 2  # Budget and bidding changes

    @pytest.mark.asyncio
    async def test_export_with_s3_upload(self, complete_analysis):
        """Test export with S3 upload."""
        # Setup mocks
        mock_repo = AsyncMock()
        mock_repo.get_analysis = AsyncMock(return_value=complete_analysis)

        mock_file_manager = AsyncMock()
        mock_file_manager.upload_actionable_file = AsyncMock(
            return_value={
                "url": "https://s3.amazonaws.com/bucket/customers/9876543210/actionable_files/package.zip",
                "key": "customers/9876543210/actionable_files/20240101_120000_import_package.zip",
            }
        )

        # Create service with file manager
        service = GoogleAdsExportService(mock_repo, mock_file_manager)

        # Create package
        with patch("tempfile.mktemp") as mock_mktemp:
            temp_dir = tempfile.mkdtemp()
            mock_mktemp.return_value = str(Path(temp_dir) / "package.zip")

            package = await service.create_import_package("integration-test-123")

        # Verify S3 upload was called
        assert package.s3_url is not None
        assert "actionable_files" in package.s3_url
        mock_file_manager.upload_actionable_file.assert_called_once()

    @pytest.mark.asyncio
    async def test_export_with_validation_errors(self):
        """Test export handling validation errors."""
        # Create analysis with invalid data
        invalid_analysis = AnalysisResult(
            analysis_id="invalid-test",
            customer_id="123",  # Invalid customer ID
            analysis_type="test",
            analyzer_name="TestAnalyzer",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 3, 31),
            recommendations=[
                Recommendation(
                    type=RecommendationType.ADD_KEYWORD,
                    priority=RecommendationPriority.HIGH,
                    title="Invalid keyword",
                    description="Test",
                    action_data={
                        "customer_id": "123",  # Invalid
                        "campaign": "",  # Empty
                        "ad_group": "Test",
                        "keyword": "test@keyword",  # Invalid character
                        "match_type": "Invalid",  # Invalid match type
                    },
                )
            ],
        )

        mock_repo = AsyncMock()
        mock_repo.get_analysis = AsyncMock(return_value=invalid_analysis)

        service = GoogleAdsExportService(mock_repo)

        request = ExportRequest(
            analysis_id="invalid-test",
            customer_id="123",
            validate_before_export=True,
        )

        result = await service.export_from_analysis(request)

        # Should complete but with validation errors
        assert result.status == ExportStatus.COMPLETED
        assert result.package is not None

        # Check for validation errors
        keyword_file = next(
            (f for f in result.package.files if f.file_name == "keyword_changes.csv"),
            None,
        )
        if keyword_file:
            assert len(keyword_file.validation_errors) > 0

    @pytest.mark.asyncio
    async def test_export_with_import_simulation(self, complete_analysis):
        """Test export with import simulation detecting conflicts."""
        # Add conflicting recommendations
        complete_analysis.recommendations.append(
            Recommendation(
                type=RecommendationType.ADD_NEGATIVE,
                priority=RecommendationPriority.HIGH,
                title="Conflicting negative",
                description="This will block an existing keyword",
                action_data={
                    "customer_id": "9876543210",
                    "campaign": "Brand Campaign",
                    "keyword": "premium running shoes",  # Conflicts with ADD_KEYWORD
                    "match_type": "Exact",
                },
            )
        )

        mock_repo = AsyncMock()
        mock_repo.get_analysis = AsyncMock(return_value=complete_analysis)

        service = GoogleAdsExportService(mock_repo)

        with patch("tempfile.mktemp") as mock_mktemp:
            temp_dir = tempfile.mkdtemp()
            mock_mktemp.return_value = str(Path(temp_dir) / "package.zip")

            package = await service.create_import_package("integration-test-123")

        # Should detect the conflict
        assert len(package.errors) > 0
        assert any("would block" in error for error in package.errors)

    @pytest.mark.asyncio
    async def test_export_package_zip_creation(self, complete_analysis):
        """Test that ZIP package is created correctly."""
        mock_repo = AsyncMock()
        mock_repo.get_analysis = AsyncMock(return_value=complete_analysis)

        service = GoogleAdsExportService(mock_repo)

        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = Path(temp_dir) / "test_package.zip"

            with patch("tempfile.mktemp") as mock_mktemp:
                mock_mktemp.return_value = str(zip_path)

                package = await service.create_import_package("integration-test-123")

            # Verify ZIP file was created
            assert package.package_path is not None
            assert package.package_path.exists()

            # Verify ZIP contents
            with zipfile.ZipFile(package.package_path, "r") as zf:
                file_list = zf.namelist()
                assert "keyword_changes.csv" in file_list
                assert "negative_keywords.csv" in file_list
                assert "bid_adjustments.csv" in file_list
                assert "campaign_changes.csv" in file_list

    @pytest.mark.asyncio
    async def test_selective_export(self, complete_analysis):
        """Test exporting only specific file types."""
        mock_repo = AsyncMock()
        mock_repo.get_analysis = AsyncMock(return_value=complete_analysis)

        service = GoogleAdsExportService(mock_repo)

        # Request only keyword changes and negatives
        request = ExportRequest(
            analysis_id="integration-test-123",
            customer_id="9876543210",
            include_keyword_changes=True,
            include_negative_keywords=True,
            include_bid_adjustments=False,
            include_campaign_changes=False,
            create_package=False,  # Don't create ZIP
        )

        result = await service.export_from_analysis(request)

        assert result.status == ExportStatus.COMPLETED
        assert result.package is not None
        assert len(result.package.files) == 2

        file_names = [f.file_name for f in result.package.files]
        assert "keyword_changes.csv" in file_names
        assert "negative_keywords.csv" in file_names
        assert "bid_adjustments.csv" not in file_names
        assert "campaign_changes.csv" not in file_names

    @pytest.mark.asyncio
    async def test_empty_analysis_export(self):
        """Test exporting analysis with no recommendations."""
        empty_analysis = AnalysisResult(
            analysis_id="empty-test",
            customer_id="9876543210",
            analysis_type="test",
            analyzer_name="TestAnalyzer",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 3, 31),
            recommendations=[],  # No recommendations
        )

        mock_repo = AsyncMock()
        mock_repo.get_analysis = AsyncMock(return_value=empty_analysis)

        service = GoogleAdsExportService(mock_repo)

        request = ExportRequest(
            analysis_id="empty-test",
            customer_id="9876543210",
        )

        result = await service.export_from_analysis(request)

        assert result.status == ExportStatus.COMPLETED
        assert result.package is not None
        # Should have files but with 0 rows
        assert all(f.row_count == 0 for f in result.package.files)
