"""Unit tests for storage repository."""

import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio

from paidsearchnav.core.config import Settings
from paidsearchnav.core.models.analysis import (
    AnalysisMetrics,
    AnalysisResult,
    Recommendation,
    RecommendationPriority,
    RecommendationType,
)
from paidsearchnav.storage.repository import AnalysisRepository


@pytest.fixture
def temp_db_path():
    """Create a temporary database file."""
    # Create a unique temp file for each test
    import uuid

    temp_dir = Path(tempfile.gettempdir())
    db_path = temp_dir / f"test_{uuid.uuid4()}.db"
    yield db_path
    # Cleanup
    db_path.unlink(missing_ok=True)


@pytest.fixture
def settings(temp_db_path):
    """Create test settings with temporary database."""
    # Use the temp_db_path directly as data_dir
    # so the database file will be created as temp_db_path/paidsearchnav.db
    settings = Settings(
        environment="development",
        data_dir=temp_db_path.parent,
        debug=False,
    )
    # Override the database path to use our specific temp file
    settings.data_dir = temp_db_path.parent
    return settings


@pytest_asyncio.fixture
async def repository(settings, temp_db_path, monkeypatch):
    """Create a repository instance."""
    # Create a unique database name for this test
    import uuid

    unique_db_name = f"test_{uuid.uuid4()}.db"

    # Monkey patch the repository to use our unique database
    def mock_init(self, settings):
        self.settings = settings
        # Configure session metrics (required by AnalysisRepository)
        from paidsearchnav.storage.session_metrics import get_session_metrics

        self.session_metrics = get_session_metrics()
        if hasattr(settings.logging, "session_logging"):
            self.session_metrics.enabled = settings.logging.session_logging.enabled
            self.session_metrics.log_interval = (
                settings.logging.session_logging.metrics_interval
            )
            self.detailed_logging = settings.logging.session_logging.detailed_logging
        else:
            self.detailed_logging = False
        # Use a unique database for this test
        db_path = settings.data_dir / unique_db_name
        db_url = f"sqlite:///{db_path}"
        async_db_url = f"sqlite+aiosqlite:///{db_path}"

        # Create engines
        from sqlalchemy import create_engine
        from sqlalchemy.ext.asyncio import (
            AsyncSession,
            async_sessionmaker,
            create_async_engine,
        )
        from sqlalchemy.orm import sessionmaker

        self.engine = create_engine(db_url, echo=settings.debug)
        self.async_engine = create_async_engine(async_db_url, echo=settings.debug)

        # Create session factories
        self.SessionLocal = sessionmaker(
            bind=self.engine, autocommit=False, autoflush=False
        )
        self.AsyncSessionLocal = async_sessionmaker(
            self.async_engine, expire_on_commit=False, class_=AsyncSession
        )

        # Create tables
        from paidsearchnav.storage.models import Base

        Base.metadata.create_all(bind=self.engine)

    monkeypatch.setattr(AnalysisRepository, "__init__", mock_init)

    repo = AnalysisRepository(settings)
    yield repo

    # Cleanup
    repo.engine.dispose()
    await repo.async_engine.dispose()

    # Clean up the unique database file
    unique_db_path = settings.data_dir / unique_db_name
    if unique_db_path.exists():
        unique_db_path.unlink()


@pytest.fixture
def sample_analysis_result():
    """Create a sample analysis result."""
    return AnalysisResult(
        customer_id="1234567890",
        analysis_type="keyword_match_audit",
        analyzer_name="KeywordMatchAnalyzer",
        start_date=datetime.now(timezone.utc) - timedelta(days=30),
        end_date=datetime.now(timezone.utc),
        status="completed",
        metrics=AnalysisMetrics(
            total_keywords_analyzed=1000,
            issues_found=50,
            critical_issues=5,
            potential_cost_savings=500.0,
            potential_conversion_increase=10.0,
            custom_metrics={
                "broad_match_percentage": 35.5,
                "low_quality_keywords": 25,
            },
        ),
        recommendations=[
            Recommendation(
                type=RecommendationType.CHANGE_MATCH_TYPE,
                priority=RecommendationPriority.HIGH,
                title="Convert high-performing broad to exact",
                description="20 broad match keywords with high conversions should be exact match",
                campaign_id="111",
                estimated_cost_savings=200.0,
                action_data={
                    "keywords": ["shoes", "running shoes", "athletic footwear"],
                    "current_match_type": "BROAD",
                    "recommended_match_type": "EXACT",
                },
            ),
            Recommendation(
                type=RecommendationType.PAUSE_KEYWORD,
                priority=RecommendationPriority.CRITICAL,
                title="Pause low quality score keywords",
                description="5 keywords with quality score < 3 and no conversions",
                campaign_id="111",
                estimated_cost_savings=100.0,
                action_data={
                    "keywords": ["cheap shoes", "discount footwear"],
                },
            ),
        ],
        raw_data={
            "match_type_distribution": {
                "BROAD": 355,
                "PHRASE": 400,
                "EXACT": 245,
            }
        },
    )


class TestAnalysisRepository:
    """Test AnalysisRepository functionality."""

    @pytest.mark.asyncio
    async def test_save_analysis(self, repository, sample_analysis_result):
        """Test saving an analysis result."""
        # Save the analysis
        analysis_id = await repository.save_analysis(sample_analysis_result)

        # Verify ID was returned
        assert analysis_id is not None
        assert len(analysis_id) == 36  # UUID format

        # Verify the result was updated with ID
        assert sample_analysis_result.analysis_id == analysis_id

    @pytest.mark.asyncio
    async def test_get_analysis(self, repository, sample_analysis_result):
        """Test retrieving an analysis by ID."""
        # Save first
        analysis_id = await repository.save_analysis(sample_analysis_result)

        # Retrieve
        retrieved = await repository.get_analysis(analysis_id)

        # Verify
        assert retrieved is not None
        assert retrieved.analysis_id == analysis_id
        assert retrieved.customer_id == sample_analysis_result.customer_id
        assert retrieved.analysis_type == sample_analysis_result.analysis_type
        assert len(retrieved.recommendations) == 2
        assert retrieved.metrics.total_keywords_analyzed == 1000

    @pytest.mark.asyncio
    async def test_get_nonexistent_analysis(self, repository):
        """Test retrieving non-existent analysis returns None."""
        result = await repository.get_analysis("non-existent-id")
        assert result is None

    @pytest.mark.asyncio
    async def test_list_analyses(self, repository, sample_analysis_result):
        """Test listing analyses with filters."""
        # Save multiple analyses
        result1 = sample_analysis_result
        await repository.save_analysis(result1)

        # Create and save another with different type
        result2 = AnalysisResult(
            customer_id="1234567890",
            analysis_type="search_terms_audit",
            analyzer_name="SearchTermsAnalyzer",
            start_date=datetime.now(timezone.utc) - timedelta(days=30),
            end_date=datetime.now(timezone.utc),
            metrics=AnalysisMetrics(),
        )
        await repository.save_analysis(result2)

        # Create and save for different customer
        result3 = AnalysisResult(
            customer_id="9876543210",
            analysis_type="keyword_match_audit",
            analyzer_name="KeywordMatchAnalyzer",
            start_date=datetime.now(timezone.utc) - timedelta(days=30),
            end_date=datetime.now(timezone.utc),
            metrics=AnalysisMetrics(),
        )
        await repository.save_analysis(result3)

        # Test listing all
        all_results = await repository.list_analyses()
        assert len(all_results) == 3

        # Test filter by customer
        customer_results = await repository.list_analyses(customer_id="1234567890")
        assert len(customer_results) == 2

        # Test filter by type
        type_results = await repository.list_analyses(
            analysis_type="keyword_match_audit"
        )
        assert len(type_results) == 2

        # Test combined filters
        filtered_results = await repository.list_analyses(
            customer_id="1234567890", analysis_type="search_terms_audit"
        )
        assert len(filtered_results) == 1
        assert filtered_results[0].analysis_type == "search_terms_audit"

    @pytest.mark.asyncio
    async def test_list_analyses_with_date_filters(
        self, repository, sample_analysis_result
    ):
        """Test listing analyses with date filters."""
        # Save analysis
        await repository.save_analysis(sample_analysis_result)

        # Test with start date filter
        results = await repository.list_analyses(
            start_date=datetime.now(timezone.utc) - timedelta(hours=1)
        )
        assert len(results) == 1

        # Test with end date filter in past (should find none)
        results = await repository.list_analyses(
            end_date=datetime.now(timezone.utc) - timedelta(days=1)
        )
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_delete_analysis(self, repository, sample_analysis_result):
        """Test deleting an analysis."""
        # Save first
        analysis_id = await repository.save_analysis(sample_analysis_result)

        # Verify it exists
        result = await repository.get_analysis(analysis_id)
        assert result is not None

        # Delete
        deleted = await repository.delete_analysis(analysis_id)
        assert deleted is True

        # Verify it's gone
        result = await repository.get_analysis(analysis_id)
        assert result is None

        # Try deleting again
        deleted = await repository.delete_analysis(analysis_id)
        assert deleted is False

    @pytest.mark.asyncio
    async def test_compare_analyses(self, repository):
        """Test comparing two analyses."""
        # Create first analysis
        analysis1 = AnalysisResult(
            customer_id="1234567890",
            analysis_type="keyword_match_audit",
            analyzer_name="KeywordMatchAnalyzer",
            start_date=datetime.now(timezone.utc) - timedelta(days=60),
            end_date=datetime.now(timezone.utc) - timedelta(days=30),
            metrics=AnalysisMetrics(
                potential_cost_savings=300.0,
                potential_conversion_increase=5.0,
            ),
            recommendations=[
                Recommendation(
                    type=RecommendationType.PAUSE_KEYWORD,
                    priority=RecommendationPriority.HIGH,
                    title="Pause keyword A",
                    description="No conversions",
                    action_data={"keyword_text": "keyword_a"},
                ),
                Recommendation(
                    type=RecommendationType.PAUSE_KEYWORD,
                    priority=RecommendationPriority.HIGH,
                    title="Pause keyword B",
                    description="Low quality",
                    action_data={"keyword_text": "keyword_b"},
                ),
            ],
        )
        id1 = await repository.save_analysis(analysis1)

        # Create second analysis (resolved one issue, found new one)
        analysis2 = AnalysisResult(
            customer_id="1234567890",
            analysis_type="keyword_match_audit",
            analyzer_name="KeywordMatchAnalyzer",
            start_date=datetime.now(timezone.utc) - timedelta(days=30),
            end_date=datetime.now(timezone.utc),
            metrics=AnalysisMetrics(
                potential_cost_savings=400.0,
                potential_conversion_increase=8.0,
            ),
            recommendations=[
                Recommendation(
                    type=RecommendationType.PAUSE_KEYWORD,
                    priority=RecommendationPriority.HIGH,
                    title="Pause keyword B",
                    description="Low quality",
                    action_data={"keyword_text": "keyword_b"},
                ),
                Recommendation(
                    type=RecommendationType.PAUSE_KEYWORD,
                    priority=RecommendationPriority.HIGH,
                    title="Pause keyword C",
                    description="New issue",
                    action_data={"keyword_text": "keyword_c"},
                ),
            ],
        )
        id2 = await repository.save_analysis(analysis2)

        # Compare
        comparison = await repository.compare_analyses(id1, id2)

        # Verify comparison results
        assert comparison["changes"]["recommendations_added"] == 1  # keyword_c
        assert comparison["changes"]["recommendations_resolved"] == 1  # keyword_a
        assert comparison["changes"]["recommendations_unchanged"] == 1  # keyword_b
        assert comparison["changes"]["cost_savings_change"] == 100.0
        assert comparison["changes"]["conversion_change"] == 3.0

    @pytest.mark.asyncio
    async def test_compare_analyses_validation(self, repository):
        """Test compare analyses validation."""
        # Create analyses for different customers
        analysis1 = AnalysisResult(
            customer_id="1111111111",
            analysis_type="keyword_match_audit",
            analyzer_name="KeywordMatchAnalyzer",
            start_date=datetime.now(timezone.utc) - timedelta(days=30),
            end_date=datetime.now(timezone.utc),
            metrics=AnalysisMetrics(),
        )
        id1 = await repository.save_analysis(analysis1)

        analysis2 = AnalysisResult(
            customer_id="2222222222",
            analysis_type="keyword_match_audit",
            analyzer_name="KeywordMatchAnalyzer",
            start_date=datetime.now(timezone.utc) - timedelta(days=30),
            end_date=datetime.now(timezone.utc),
            metrics=AnalysisMetrics(),
        )
        id2 = await repository.save_analysis(analysis2)

        # Should raise error for different customers
        with pytest.raises(ValueError, match="different customers"):
            await repository.compare_analyses(id1, id2)

    @pytest.mark.asyncio
    async def test_get_latest_analysis(self, repository):
        """Test getting the latest analysis."""
        customer_id = "1234567890"
        analysis_type = "keyword_match_audit"

        # Save multiple analyses with different dates
        for i in range(3):
            analysis = AnalysisResult(
                customer_id=customer_id,
                analysis_type=analysis_type,
                analyzer_name="KeywordMatchAnalyzer",
                start_date=datetime.now(timezone.utc) - timedelta(days=30 + i * 30),
                end_date=datetime.now(timezone.utc) - timedelta(days=i * 30),
                metrics=AnalysisMetrics(custom_metrics={"index": i}),
            )
            await repository.save_analysis(analysis)
            # Small delay to ensure different timestamps
            import asyncio

            await asyncio.sleep(0.1)

        # Get latest
        latest = await repository.get_latest_analysis(customer_id, analysis_type)

        assert latest is not None
        assert latest.metrics.custom_metrics["index"] == 2  # Last one saved

    @pytest.mark.asyncio
    async def test_repository_with_production_settings(self):
        """Test repository initialization with production settings."""
        settings = Settings(
            environment="production",
            database_url="postgresql://user:pass@localhost/db",
            data_dir=Path("/tmp"),
            debug=False,
        )

        # Mock the create_engine calls to avoid needing pg8000
        with (
            patch("paidsearchnav.storage.repository.create_engine") as mock_engine,
            patch(
                "paidsearchnav.storage.repository.create_async_engine"
            ) as mock_async_engine,
            patch("paidsearchnav.storage.repository.Base"),
        ):
            # Create mock engines
            mock_engine_instance = MagicMock()
            mock_async_engine_instance = MagicMock()
            mock_engine.return_value = mock_engine_instance
            mock_async_engine.return_value = mock_async_engine_instance

            AnalysisRepository(settings)

            # Verify PostgreSQL URLs were used
            mock_engine.assert_called_once()
            args = mock_engine.call_args[0]
            assert "postgresql://" in args[0]

            mock_async_engine.assert_called_once()
            args = mock_async_engine.call_args[0]
            assert "postgresql+asyncpg://" in args[0]
