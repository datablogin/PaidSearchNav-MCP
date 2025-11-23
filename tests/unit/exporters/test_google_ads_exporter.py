"""Unit tests for Google Ads export service."""

from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from paidsearchnav_mcp.models.analysis import (
    AnalysisResult,
    Recommendation,
    RecommendationPriority,
    RecommendationType,
)
from paidsearchnav_mcp.models.export_models import (
    ExportRequest,
    ExportStatus,
    ImportPackage,
)
from paidsearchnav_mcp.exporters.google_ads_exporter import GoogleAdsExportService


@pytest.fixture
def mock_repository():
    """Create a mock repository."""
    repo = AsyncMock()
    return repo


@pytest.fixture
def mock_file_manager():
    """Create a mock file manager."""
    manager = AsyncMock()
    manager.upload_actionable_file = AsyncMock(
        return_value={"url": "https://s3.example.com/test.zip"}
    )
    return manager


@pytest.fixture
def export_service(mock_repository, mock_file_manager):
    """Create an export service instance."""
    return GoogleAdsExportService(mock_repository, mock_file_manager)


@pytest.fixture
def sample_recommendations():
    """Create sample recommendations for testing."""
    return [
        Recommendation(
            type=RecommendationType.ADD_KEYWORD,
            priority=RecommendationPriority.HIGH,
            title="Add high-performing keyword",
            description="Add this keyword based on search term performance",
            campaign_id="123",
            ad_group_id="456",
            action_data={
                "customer_id": "1234567890",
                "campaign": "Test Campaign",
                "ad_group": "Test Ad Group",
                "keyword": "running shoes",
                "match_type": "Exact",
                "max_cpc": 1.50,
            },
        ),
        Recommendation(
            type=RecommendationType.ADD_NEGATIVE,
            priority=RecommendationPriority.MEDIUM,
            title="Add negative keyword",
            description="Block irrelevant traffic",
            campaign_id="123",
            action_data={
                "customer_id": "1234567890",
                "campaign": "Test Campaign",
                "keyword": "cheap shoes",
                "match_type": "Phrase",
            },
        ),
        Recommendation(
            type=RecommendationType.PAUSE_KEYWORD,
            priority=RecommendationPriority.HIGH,
            title="Pause underperforming keyword",
            description="Keyword has poor performance",
            campaign_id="123",
            ad_group_id="456",
            keyword_id="789",
            action_data={
                "customer_id": "1234567890",
                "campaign": "Test Campaign",
                "ad_group": "Test Ad Group",
                "keyword": "old shoes",
                "match_type": "Broad",
            },
        ),
        Recommendation(
            type=RecommendationType.OPTIMIZE_LOCATION,
            priority=RecommendationPriority.MEDIUM,
            title="Adjust location bid",
            description="Increase bid for high-performing location",
            campaign_id="123",
            action_data={
                "customer_id": "1234567890",
                "campaign": "Test Campaign",
                "location": "New York",
                "adjustment_value": 20,
            },
        ),
        Recommendation(
            type=RecommendationType.BUDGET_OPTIMIZATION,
            priority=RecommendationPriority.HIGH,
            title="Increase campaign budget",
            description="Campaign is budget-constrained",
            campaign_id="123",
            action_data={
                "customer_id": "1234567890",
                "campaign": "Test Campaign",
                "budget": 100.00,
                "bid_strategy": "Target CPA",
                "target_cpa": 25.00,
            },
        ),
    ]


@pytest.fixture
def sample_analysis(sample_recommendations):
    """Create a sample analysis result."""
    return AnalysisResult(
        analysis_id="test-analysis-123",
        customer_id="1234567890",
        analysis_type="keyword_match",
        analyzer_name="KeywordMatchAnalyzer",
        start_date=datetime(2024, 1, 1),
        end_date=datetime(2024, 3, 31),
        recommendations=sample_recommendations,
    )


class TestGoogleAdsExportService:
    """Test Google Ads export service."""

    @pytest.mark.asyncio
    async def test_generate_keyword_changes(
        self, export_service, sample_recommendations
    ):
        """Test generating keyword changes file."""
        file = await export_service.generate_keyword_changes(
            "test-analysis", sample_recommendations
        )

        assert file is not None
        assert file.row_count == 2  # ADD_KEYWORD and PAUSE_KEYWORD
        assert len(file.changes) == 2
        assert file.file_name == "keyword_changes.csv"

        # Check specific changes
        add_change = next(c for c in file.changes if c.status == "Enabled")
        assert add_change.keyword == "running shoes"
        assert add_change.match_type == "Exact"
        assert add_change.max_cpc == 1.50

        pause_change = next(c for c in file.changes if c.status == "Paused")
        assert pause_change.keyword == "old shoes"
        assert pause_change.match_type == "Broad"

    @pytest.mark.asyncio
    async def test_generate_negative_keywords(
        self, export_service, sample_recommendations
    ):
        """Test generating negative keywords file."""
        file = await export_service.generate_negative_keywords(
            "test-analysis", sample_recommendations
        )

        assert file is not None
        assert file.row_count == 1
        assert len(file.negatives) == 1
        assert file.file_name == "negative_keywords.csv"

        negative = file.negatives[0]
        assert negative.keyword == "cheap shoes"
        assert negative.match_type == "Phrase"
        assert negative.campaign == "Test Campaign"

    @pytest.mark.asyncio
    async def test_generate_bid_adjustments(
        self, export_service, sample_recommendations
    ):
        """Test generating bid adjustments file."""
        file = await export_service.generate_bid_adjustments(
            "test-analysis", sample_recommendations
        )

        assert file is not None
        assert file.row_count == 1
        assert len(file.adjustments) == 1
        assert file.file_name == "bid_adjustments.csv"

        adjustment = file.adjustments[0]
        assert adjustment.location == "New York"
        assert adjustment.bid_adjustment == "+20%"
        assert adjustment.campaign == "Test Campaign"

    @pytest.mark.asyncio
    async def test_generate_campaign_changes(
        self, export_service, sample_recommendations
    ):
        """Test generating campaign changes file."""
        file = await export_service.generate_campaign_changes(
            "test-analysis", sample_recommendations
        )

        assert file is not None
        assert file.row_count == 1
        assert len(file.changes) == 1
        assert file.file_name == "campaign_changes.csv"

        change = file.changes[0]
        assert change.budget == 100.00
        assert change.bid_strategy == "Target CPA"
        assert change.target_cpa == 25.00

    @pytest.mark.asyncio
    async def test_create_import_package(
        self, export_service, mock_repository, sample_analysis
    ):
        """Test creating a complete import package."""
        mock_repository.get_analysis = AsyncMock(return_value=sample_analysis)

        with patch("tempfile.mktemp") as mock_mktemp:
            mock_mktemp.return_value = "/tmp/test_package.zip"

            # Mock Path.exists to return True
            with patch.object(Path, "exists", return_value=True):
                package = await export_service.create_import_package(
                    "test-analysis-123"
                )

        assert package is not None
        assert package.analysis_id == "test-analysis-123"
        assert package.customer_id == "1234567890"
        assert len(package.files) > 0
        assert package.total_changes > 0
        assert package.status in [ExportStatus.COMPLETED, ExportStatus.FAILED]

    @pytest.mark.asyncio
    async def test_export_from_analysis(
        self, export_service, mock_repository, sample_analysis
    ):
        """Test full export from analysis."""
        mock_repository.get_analysis = AsyncMock(return_value=sample_analysis)

        request = ExportRequest(
            analysis_id="test-analysis-123",
            customer_id="1234567890",
            include_keyword_changes=True,
            include_negative_keywords=True,
            include_bid_adjustments=True,
            include_campaign_changes=True,
            create_package=True,
        )

        with patch("tempfile.mktemp") as mock_mktemp:
            mock_mktemp.return_value = "/tmp/test_package.zip"

            # Mock Path.exists to return True
            with patch.object(Path, "exists", return_value=True):
                result = await export_service.export_from_analysis(request)

        assert result is not None
        assert result.status in [ExportStatus.COMPLETED, ExportStatus.FAILED]
        assert result.package is not None
        assert result.duration_seconds is not None

    @pytest.mark.asyncio
    async def test_export_analysis_not_found(self, export_service, mock_repository):
        """Test export when analysis is not found."""
        mock_repository.get_analysis = AsyncMock(return_value=None)

        request = ExportRequest(
            analysis_id="nonexistent",
            customer_id="1234567890",
        )

        result = await export_service.export_from_analysis(request)

        assert result.status == ExportStatus.FAILED
        assert "not found" in result.errors[0]

    @pytest.mark.asyncio
    async def test_export_customer_id_mismatch(
        self, export_service, mock_repository, sample_analysis
    ):
        """Test export with customer ID mismatch."""
        mock_repository.get_analysis = AsyncMock(return_value=sample_analysis)

        request = ExportRequest(
            analysis_id="test-analysis-123",
            customer_id="9999999999",  # Wrong customer ID
        )

        result = await export_service.export_from_analysis(request)

        assert result.status == ExportStatus.FAILED
        assert "Customer ID mismatch" in result.errors[0]

    def test_recommendation_to_keyword_change(
        self, export_service, sample_recommendations
    ):
        """Test converting recommendation to keyword change."""
        rec = sample_recommendations[0]  # ADD_KEYWORD
        change = export_service._recommendation_to_keyword_change(rec)

        assert change is not None
        assert change.keyword == "running shoes"
        assert change.match_type == "Exact"
        assert change.status == "Enabled"
        assert change.max_cpc == 1.50

    def test_recommendation_to_negative_keyword(
        self, export_service, sample_recommendations
    ):
        """Test converting recommendation to negative keyword."""
        rec = sample_recommendations[1]  # ADD_NEGATIVE
        negative = export_service._recommendation_to_negative_keyword(rec)

        assert negative is not None
        assert negative.keyword == "cheap shoes"
        assert negative.match_type == "Phrase"
        assert negative.campaign == "Test Campaign"

    def test_recommendation_to_bid_adjustment(
        self, export_service, sample_recommendations
    ):
        """Test converting recommendation to bid adjustment."""
        rec = sample_recommendations[3]  # OPTIMIZE_LOCATION
        adjustment = export_service._recommendation_to_bid_adjustment(rec)

        assert adjustment is not None
        assert adjustment.location == "New York"
        assert adjustment.bid_adjustment == "+20%"

    def test_recommendation_to_campaign_change(
        self, export_service, sample_recommendations
    ):
        """Test converting recommendation to campaign change."""
        rec = sample_recommendations[4]  # BUDGET_OPTIMIZATION
        change = export_service._recommendation_to_campaign_change(rec)

        assert change is not None
        assert change.budget == 100.00
        assert change.bid_strategy == "Target CPA"
        assert change.target_cpa == 25.00

    @pytest.mark.asyncio
    async def test_upload_package_to_s3(self, export_service, mock_file_manager):
        """Test uploading package to S3."""
        package = ImportPackage(
            package_id="test-package",
            analysis_id="test-analysis",
            customer_id="1234567890",
            package_path=Path("/tmp/test.zip"),
        )

        # Create a temporary file for testing
        with patch("builtins.open", mock_open(read_data=b"test content")):
            s3_key, s3_url = await export_service._upload_package_to_s3(
                package, "1234567890"
            )

        assert "customers/1234567890/actionable_files/" in s3_key
        assert s3_url == "https://s3.example.com/test.zip"
        mock_file_manager.upload_actionable_file.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_with_empty_recommendations(self, export_service):
        """Test generating files with empty recommendation list."""
        # Test with empty list
        file = await export_service.generate_keyword_changes("test-analysis", [])

        assert file is not None
        assert file.row_count == 0
        assert len(file.changes) == 0
        assert file.file_path is None  # No file should be created for empty list

    @pytest.mark.asyncio
    async def test_create_package_with_no_recommendations(
        self, export_service, mock_repository
    ):
        """Test creating package when analysis has no recommendations."""
        empty_analysis = AnalysisResult(
            analysis_id="empty-analysis",
            customer_id="1234567890",
            analysis_type="test",
            analyzer_name="TestAnalyzer",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 3, 31),
            recommendations=[],  # Empty recommendations
        )

        mock_repository.get_analysis = AsyncMock(return_value=empty_analysis)

        package = await export_service.create_import_package("empty-analysis")

        assert package is not None
        assert package.status == ExportStatus.COMPLETED
        assert len(package.files) == 0
        assert package.total_changes == 0
        assert package.package_path is None  # No ZIP should be created

    @pytest.mark.asyncio
    async def test_cleanup_temp_files(self, export_service):
        """Test that temporary files are cleaned up properly."""
        # Create some temporary files
        export_service.temp_files = [
            Path("/tmp/test1.csv"),
            Path("/tmp/test2.csv"),
        ]

        # Mock Path.exists and Path.unlink
        with patch.object(Path, "exists", return_value=True):
            with patch.object(Path, "unlink") as mock_unlink:
                export_service.cleanup_temp_files()

        assert mock_unlink.call_count == 2
        assert len(export_service.temp_files) == 0


# Mock for open()
def mock_open(read_data=None):
    """Create a mock for open()."""
    m = MagicMock(spec=open)
    handle = MagicMock()
    handle.__enter__.return_value = handle
    handle.read.return_value = read_data
    m.return_value = handle
    return m
