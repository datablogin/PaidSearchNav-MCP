"""Unit tests for SearchTermsAnalyzer."""

from datetime import datetime

import pytest

from paidsearchnav_mcp.analyzers.search_terms import SearchTermsAnalyzer
from paidsearchnav_mcp.models import (
    Keyword,
    MatchType,
    SearchTerm,
    SearchTermClassification,
    SearchTermMetrics,
)


def create_search_term(
    search_term: str,
    campaign_id: str = "123",
    campaign_name: str = "Widgets Campaign",
    ad_group_id: str = "456",
    ad_group_name: str = "Widget Ad Group",
    keyword_id: str | None = None,
    keyword_text: str | None = None,
    match_type: str | None = None,
    impressions: int = 0,
    clicks: int = 0,
    cost: float = 0.0,
    conversions: float = 0.0,
    conversion_value: float = 0.0,
) -> SearchTerm:
    """Helper function to create SearchTerm objects for testing."""
    return SearchTerm(
        search_term=search_term,
        campaign_id=campaign_id,
        campaign_name=campaign_name,
        ad_group_id=ad_group_id,
        ad_group_name=ad_group_name,
        keyword_id=keyword_id,
        keyword_text=keyword_text,
        match_type=match_type,
        date_start=datetime.now().date(),
        date_end=datetime.now().date(),
        metrics=SearchTermMetrics(
            impressions=impressions,
            clicks=clicks,
            cost=cost,
            conversions=conversions,
            conversion_value=conversion_value,
        ),
    )


class MockDataProvider:
    """Mock data provider for testing."""

    def __init__(self):
        self.search_terms_data = []
        self.keywords_data = []

    async def get_search_terms(
        self,
        customer_id,
        start_date,
        end_date,
        campaigns=None,
        ad_groups=None,
        page_size=None,
        max_results=None,
    ):
        """Return mock search terms data."""
        return self.search_terms_data

    async def get_keywords(
        self,
        customer_id,
        campaigns=None,
        ad_groups=None,
        campaign_id=None,
        include_metrics=True,
        start_date=None,
        end_date=None,
        page_size=None,
        max_results=None,
    ):
        """Return mock keywords data."""
        return self.keywords_data

    async def get_negative_keywords(self, customer_id, include_shared_sets=True):
        """Return mock negative keywords data."""
        return []

    async def get_campaigns(self, customer_id, campaign_types=None):
        """Return mock campaigns data."""
        return []


@pytest.fixture
def mock_data_provider():
    """Create a mock data provider."""
    return MockDataProvider()


@pytest.fixture
def analyzer(mock_data_provider):
    """Create a SearchTermsAnalyzer instance."""
    from paidsearchnav.core.config import AnalyzerThresholds

    thresholds = AnalyzerThresholds(
        min_impressions=10,
        min_clicks_for_negative=10,
        max_cpa_multiplier=2.0,
        min_conversions_for_add=1.0,
    )
    return SearchTermsAnalyzer(
        data_provider=mock_data_provider,
        thresholds=thresholds,
    )


@pytest.fixture
def sample_search_terms_data():
    """Sample search terms data."""
    return [
        SearchTerm(
            search_term="widget near me",
            campaign_id="123",
            campaign_name="Widgets Campaign",
            ad_group_id="456",
            ad_group_name="Widget Ad Group",
            keyword_id="789",
            keyword_text="widgets",
            match_type="BROAD",
            date_start=datetime.now().date(),
            date_end=datetime.now().date(),
            metrics=SearchTermMetrics(
                impressions=1000,
                clicks=50,
                cost=100.0,  # $100
                conversions=5.0,
                conversion_value=500.0,
            ),
        ),
        SearchTerm(
            search_term="cheap widgets online",
            campaign_id="123",
            campaign_name="Widgets Campaign",
            ad_group_id="456",
            ad_group_name="Widget Ad Group",
            keyword_id="789",
            keyword_text="widgets",
            match_type="BROAD",
            date_start=datetime.now().date(),
            date_end=datetime.now().date(),
            metrics=SearchTermMetrics(
                impressions=500,
                clicks=20,
                cost=50.0,  # $50
                conversions=0.0,
                conversion_value=0.0,
            ),
        ),
        SearchTerm(
            search_term="widget repair",
            campaign_id="123",
            campaign_name="Widgets Campaign",
            ad_group_id="456",
            ad_group_name="Widget Ad Group",
            keyword_id="789",
            keyword_text="widgets",
            match_type="BROAD",
            date_start=datetime.now().date(),
            date_end=datetime.now().date(),
            metrics=SearchTermMetrics(
                impressions=200,
                clicks=2,
                cost=5.0,  # $5
                conversions=0.0,
                conversion_value=0.0,
            ),
        ),
    ]


@pytest.fixture
def sample_keywords_data():
    """Sample keywords data."""
    return [
        Keyword(
            keyword_id="789",
            ad_group_id="456",
            ad_group_name="Widget Ad Group",
            campaign_id="123",
            campaign_name="Widgets Campaign",
            text="widgets",
            match_type=MatchType.BROAD,
            status="ENABLED",
            quality_score=7,
            impressions=10000,
            clicks=500,
            cost=1000.0,  # $1000
            conversions=50.0,
            conversion_value=5000.0,
        ),
        Keyword(
            keyword_id="790",
            ad_group_id="456",
            ad_group_name="Widget Ad Group",
            campaign_id="123",
            campaign_name="Widgets Campaign",
            text="widget store",
            match_type=MatchType.PHRASE,
            status="ENABLED",
            quality_score=8,
            impressions=5000,
            clicks=250,
            cost=500.0,  # $500
            conversions=25.0,
            conversion_value=2500.0,
        ),
    ]


class TestSearchTermsAnalyzer:
    """Test SearchTermsAnalyzer functionality."""

    def test_analyzer_initialization(self, analyzer):
        """Test analyzer is properly initialized."""
        assert analyzer.thresholds.min_impressions == 10
        assert analyzer.thresholds.min_clicks_for_negative == 10
        assert analyzer.thresholds.max_cpa_multiplier == 2.0
        assert analyzer.thresholds.min_conversions_for_add == 1.0

    def test_analyzer_metadata(self, analyzer):
        """Test analyzer metadata methods."""
        assert analyzer.get_name() == "Search Terms Analyzer"
        assert "search terms report" in analyzer.get_description().lower()

    @pytest.mark.asyncio
    async def test_analyze_basic(
        self,
        analyzer,
        mock_data_provider,
        sample_search_terms_data,
        sample_keywords_data,
    ):
        """Test basic analysis functionality."""
        mock_data_provider.search_terms_data = sample_search_terms_data
        mock_data_provider.keywords_data = sample_keywords_data

        result = await analyzer.analyze(
            customer_id="12345",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        assert result.customer_id == "12345"
        assert result.total_search_terms == 3
        assert result.total_impressions == 1700
        assert result.total_clicks == 72
        assert result.total_cost == 155.0
        assert result.total_conversions == 5.0

    @pytest.mark.asyncio
    async def test_classification_add_candidate(
        self, analyzer, mock_data_provider, sample_keywords_data
    ):
        """Test classification of high-performing search terms."""
        # High converting term not in keywords
        search_terms_data = [
            create_search_term(
                search_term="premium widgets",
                impressions=500,
                clicks=50,
                cost=100.0,  # $100
                conversions=10.0,
                conversion_value=1000.0,
            )
        ]

        mock_data_provider.search_terms_data = search_terms_data
        mock_data_provider.keywords_data = sample_keywords_data

        result = await analyzer.analyze(
            customer_id="12345",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        assert len(result.add_candidates) == 1
        assert result.add_candidates[0].search_term == "premium widgets"
        assert (
            result.add_candidates[0].classification
            == SearchTermClassification.ADD_CANDIDATE
        )

    @pytest.mark.asyncio
    async def test_classification_negative_candidate(
        self, analyzer, mock_data_provider, sample_keywords_data
    ):
        """Test classification of wasteful search terms."""
        # High cost, no conversions
        search_terms_data = [
            create_search_term(
                search_term="free widgets",
                impressions=1000,
                clicks=50,
                cost=200.0,  # $200
                conversions=0.0,
                conversion_value=0.0,
            )
        ]

        mock_data_provider.search_terms_data = search_terms_data
        mock_data_provider.keywords_data = sample_keywords_data

        result = await analyzer.analyze(
            customer_id="12345",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        assert len(result.negative_candidates) == 1
        assert result.negative_candidates[0].search_term == "free widgets"
        assert (
            result.negative_candidates[0].classification
            == SearchTermClassification.NEGATIVE_CANDIDATE
        )

    @pytest.mark.asyncio
    async def test_classification_already_covered(
        self, analyzer, mock_data_provider, sample_keywords_data
    ):
        """Test classification of terms already covered by keywords."""
        # Exact match with existing keyword
        search_terms_data = [
            create_search_term(
                search_term="widgets",  # Matches existing keyword
                impressions=100,
                clicks=10,
                cost=20.0,  # $20
                conversions=1.0,
                conversion_value=100.0,
            )
        ]

        mock_data_provider.search_terms_data = search_terms_data
        mock_data_provider.keywords_data = sample_keywords_data

        result = await analyzer.analyze(
            customer_id="12345",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        assert len(result.already_covered) == 1
        assert result.already_covered[0].search_term == "widgets"
        assert (
            result.already_covered[0].classification
            == SearchTermClassification.ALREADY_COVERED
        )

    @pytest.mark.asyncio
    async def test_local_intent_detection(
        self, analyzer, mock_data_provider, sample_keywords_data
    ):
        """Test detection of local intent in search terms."""
        search_terms_data = [
            create_search_term(
                search_term="widgets near me",
                impressions=500,
                clicks=50,
                cost=100.0,
                conversions=5.0,
                conversion_value=500.0,
            ),
            create_search_term(
                search_term="widgets in chicago",
                impressions=300,
                clicks=30,
                cost=60.0,
                conversions=3.0,
                conversion_value=300.0,
            ),
        ]

        mock_data_provider.search_terms_data = search_terms_data
        mock_data_provider.keywords_data = sample_keywords_data

        result = await analyzer.analyze(
            customer_id="12345",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        assert result.near_me_terms == 1
        assert (
            result.local_intent_terms == 1
        )  # Only "near me" is detected as local intent

        # Check individual terms
        near_me_term = next(
            st for st in result.add_candidates if "near me" in st.search_term.lower()
        )
        assert near_me_term.contains_near_me is True
        assert near_me_term.is_local_intent is True

        # Check non-near-me term
        chicago_term = next(
            st for st in result.add_candidates if "chicago" in st.search_term.lower()
        )
        assert chicago_term.contains_near_me is False
        assert (
            chicago_term.is_local_intent is False
        )  # Not detected as local without specific pattern

    @pytest.mark.asyncio
    async def test_recommendations_generation(
        self,
        analyzer,
        mock_data_provider,
        sample_search_terms_data,
        sample_keywords_data,
    ):
        """Test generation of recommendations."""
        mock_data_provider.search_terms_data = sample_search_terms_data
        mock_data_provider.keywords_data = sample_keywords_data

        result = await analyzer.analyze(
            customer_id="12345",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        assert len(result.recommendations) > 0
        # Should have recommendations about add candidates and negative candidates
        recommendations_text = " ".join(
            r.description for r in result.recommendations
        ).lower()
        assert "add" in recommendations_text or "negative" in recommendations_text

    @pytest.mark.asyncio
    async def test_poor_ctr_classification(
        self, analyzer, mock_data_provider, sample_keywords_data
    ):
        """Test classification based on poor CTR."""
        search_terms_data = [
            create_search_term(
                search_term="unrelated widgets",
                impressions=1000,
                clicks=5,  # 0.5% CTR
                cost=10.0,  # $10
                conversions=0.0,
                conversion_value=0.0,
            )
        ]

        mock_data_provider.search_terms_data = search_terms_data
        mock_data_provider.keywords_data = sample_keywords_data

        result = await analyzer.analyze(
            customer_id="12345",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        assert len(result.negative_candidates) == 1
        assert (
            "poor relevance"
            in result.negative_candidates[0].classification_reason.lower()
        )

    @pytest.mark.asyncio
    async def test_review_needed_classification(
        self, analyzer, mock_data_provider, sample_keywords_data
    ):
        """Test classification of borderline search terms."""
        search_terms_data = [
            create_search_term(
                search_term="widget accessories",
                impressions=200,
                clicks=10,
                cost=30.0,  # $30
                conversions=0.5,  # Below add threshold
                conversion_value=50.0,
            )
        ]

        mock_data_provider.search_terms_data = search_terms_data
        mock_data_provider.keywords_data = sample_keywords_data

        result = await analyzer.analyze(
            customer_id="12345",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        assert len(result.review_needed) == 1
        assert (
            result.review_needed[0].classification
            == SearchTermClassification.REVIEW_NEEDED
        )

    @pytest.mark.asyncio
    async def test_minimum_impressions_filter(
        self, analyzer, mock_data_provider, sample_keywords_data
    ):
        """Test that terms below minimum impressions are filtered out."""
        search_terms_data = [
            create_search_term(
                search_term="rare widget query",
                impressions=5,  # Below minimum
                clicks=1,
                cost=2.0,
                conversions=0.0,
                conversion_value=0.0,
            )
        ]

        mock_data_provider.search_terms_data = search_terms_data
        mock_data_provider.keywords_data = sample_keywords_data

        result = await analyzer.analyze(
            customer_id="12345",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        assert result.total_search_terms == 0

    @pytest.mark.asyncio
    async def test_potential_impact_calculation(
        self,
        analyzer,
        mock_data_provider,
        sample_search_terms_data,
        sample_keywords_data,
    ):
        """Test calculation of potential savings and revenue."""
        mock_data_provider.search_terms_data = sample_search_terms_data
        mock_data_provider.keywords_data = sample_keywords_data

        result = await analyzer.analyze(
            customer_id="12345",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        # Should calculate potential savings from negative candidates
        assert result.potential_savings >= 0
        # Should calculate potential revenue from add candidates
        assert result.potential_revenue >= 0


def test_detect_local_intent_patterns():
    """Test detection of local intent patterns in search terms."""
    from paidsearchnav.core.models import SearchTerm, SearchTermMetrics

    # Test "near me" detection
    st1 = SearchTerm(
        campaign_id="123",
        campaign_name="Test Campaign",
        ad_group_id="456",
        ad_group_name="Test Ad Group",
        search_term="pizza delivery near me",
        metrics=SearchTermMetrics(
            impressions=100, clicks=10, cost=20.0, conversions=2.0
        ),
    )
    st1.detect_local_intent()
    assert st1.has_near_me is True
    assert st1.is_local_intent is True
    assert st1.contains_near_me is True
    assert "near me" in st1.location_terms

    # Test other local patterns
    st2 = SearchTerm(
        campaign_id="123",
        campaign_name="Test Campaign",
        ad_group_id="456",
        ad_group_name="Test Ad Group",
        search_term="closest hardware store",
        metrics=SearchTermMetrics(impressions=50, clicks=5, cost=10.0, conversions=1.0),
    )
    st2.detect_local_intent()
    assert st2.has_near_me is False
    assert st2.has_location is True
    assert st2.is_local_intent is True
    assert "closest" in st2.location_terms

    # Test multiple local patterns
    st3 = SearchTerm(
        campaign_id="123",
        campaign_name="Test Campaign",
        ad_group_id="456",
        ad_group_name="Test Ad Group",
        search_term="local plumber nearby in my area",
        metrics=SearchTermMetrics(impressions=30, clicks=3, cost=15.0, conversions=1.0),
    )
    st3.detect_local_intent()
    assert st3.is_local_intent is True
    assert len(st3.location_terms) == 3  # "local", "nearby", "in my area"
    assert "local" in st3.location_terms
    assert "nearby" in st3.location_terms
    assert "in my area" in st3.location_terms

    # Test non-local intent
    st4 = SearchTerm(
        campaign_id="123",
        campaign_name="Test Campaign",
        ad_group_id="456",
        ad_group_name="Test Ad Group",
        search_term="best smartphone 2024",
        metrics=SearchTermMetrics(
            impressions=200, clicks=20, cost=40.0, conversions=0.0
        ),
    )
    st4.detect_local_intent()
    assert st4.is_local_intent is False
    assert st4.has_near_me is False
    assert st4.has_location is False
    assert len(st4.location_terms) == 0


def test_priority_score_with_local_intent():
    """Test priority score calculation includes local intent bonus."""
    from paidsearchnav.core.models import SearchTerm, SearchTermMetrics

    # Search term with local intent
    st_local = SearchTerm(
        campaign_id="123",
        campaign_name="Test Campaign",
        ad_group_id="456",
        ad_group_name="Test Ad Group",
        search_term="dentist near me",
        metrics=SearchTermMetrics(
            impressions=150,  # > 100, gets 20 points
            clicks=15,
            cost=75.0,
            conversions=3.0,  # CPA = 25
        ),
    )
    st_local.detect_local_intent()

    # Same metrics without local intent
    st_regular = SearchTerm(
        campaign_id="123",
        campaign_name="Test Campaign",
        ad_group_id="456",
        ad_group_name="Test Ad Group",
        search_term="dentist appointment",
        metrics=SearchTermMetrics(
            impressions=150,  # > 100, gets 20 points
            clicks=15,
            cost=75.0,
            conversions=3.0,  # CPA = 25
        ),
    )
    st_regular.detect_local_intent()

    # Calculate scores with account avg CPA of 30
    score_local = st_local.calculate_priority_score(account_avg_cpa=30.0)
    score_regular = st_regular.calculate_priority_score(account_avg_cpa=30.0)

    # Local intent should add 10 points
    assert score_local == score_regular + 10
    assert st_local.priority_score > st_regular.priority_score


@pytest.mark.asyncio
async def test_local_intent_recommendations(analyzer, mock_data_provider):
    """Test that local intent generates appropriate recommendations."""
    # Prepare test data with local intent terms
    mock_data_provider.search_terms_data = [
        create_search_term(
            search_term="coffee shop near me",
            campaign_id="123",
            campaign_name="Coffee Campaign",
            ad_group_id="456",
            ad_group_name="Coffee Ad Group",
            keyword_id="789",
            keyword_text="coffee shop",
            match_type="BROAD",
            impressions=500,
            clicks=50,
            cost=100.0,  # $100
            conversions=10.0,
            conversion_value=400.0,
        ),
        create_search_term(
            search_term="nearest coffee place",
            campaign_id="123",
            campaign_name="Coffee Campaign",
            ad_group_id="456",
            ad_group_name="Coffee Ad Group",
            keyword_id="789",
            keyword_text="coffee shop",
            match_type="BROAD",
            impressions=300,
            clicks=30,
            cost=60.0,  # $60
            conversions=6.0,
            conversion_value=240.0,
        ),
        create_search_term(
            search_term="local barista training",
            campaign_id="123",
            campaign_name="Coffee Campaign",
            ad_group_id="456",
            ad_group_name="Coffee Ad Group",
            keyword_id="789",
            keyword_text="coffee shop",
            match_type="BROAD",
            impressions=200,
            clicks=20,
            cost=50.0,  # $50
            conversions=2.0,
            conversion_value=200.0,
        ),
    ]

    mock_data_provider.keywords_data = []  # No existing keywords

    result = await analyzer.analyze(
        customer_id="123456789",
        start_date=datetime.now(),
        end_date=datetime.now(),
    )

    # Check that local intent recommendations were generated
    recommendations = [r.description for r in result.recommendations]
    assert any("local intent" in r for r in recommendations)
    assert any("location-specific ad groups" in r for r in recommendations)

    # Check near me specific recommendation
    assert any("'near me' searches" in r for r in recommendations)
    assert any("location extensions" in r for r in recommendations)

    # Verify search terms were properly classified with local intent
    all_search_terms = (
        result.add_candidates
        + result.negative_candidates
        + result.already_covered
        + result.review_needed
    )

    # Check that local intent was detected
    local_terms_count = sum(1 for st in all_search_terms if st.is_local_intent)
    assert local_terms_count >= 3  # All 3 terms should have local intent

    # Verify specific terms
    for st in result.add_candidates:
        if (
            "near me" in st.search_term
            or "nearest" in st.search_term
            or "local" in st.search_term
        ):
            assert st.is_local_intent is True


def test_case_insensitive_local_detection():
    """Test that local intent detection is case insensitive."""
    from paidsearchnav.core.models import SearchTerm, SearchTermMetrics

    test_cases = [
        "Pizza NEAR ME",
        "NEAREST restaurant",
        "Local PLUMBER",
        "Store Close To Me",
        "NEARBY shops",
    ]

    for term in test_cases:
        st = SearchTerm(
            campaign_id="123",
            campaign_name="Test",
            ad_group_id="456",
            ad_group_name="Test",
            search_term=term,
            metrics=SearchTermMetrics(),
        )
        st.detect_local_intent()
        assert st.is_local_intent is True, f"Failed to detect local intent in: {term}"


class TestSearchTermsAnalyzerEdgeCases:
    """Test edge cases for SearchTermsAnalyzer."""

    @pytest.mark.asyncio
    async def test_batch_size_validation(self, mock_data_provider):
        """Test batch size validation."""
        from paidsearchnav.core.config import AnalyzerThresholds

        thresholds = AnalyzerThresholds()

        # Test minimum batch size validation
        with pytest.raises(ValueError, match="batch_size must be at least 100"):
            SearchTermsAnalyzer(
                data_provider=mock_data_provider,
                thresholds=thresholds,
                batch_size=50,
            )

        # Test maximum batch size validation
        with pytest.raises(ValueError, match="batch_size cannot exceed 10000"):
            SearchTermsAnalyzer(
                data_provider=mock_data_provider,
                thresholds=thresholds,
                batch_size=20000,
            )

        # Test valid batch sizes
        analyzer = SearchTermsAnalyzer(
            data_provider=mock_data_provider,
            thresholds=thresholds,
            batch_size=500,
        )
        assert analyzer.batch_size == 500

        # Test default batch size
        analyzer = SearchTermsAnalyzer(
            data_provider=mock_data_provider,
            thresholds=thresholds,
        )
        assert analyzer.batch_size == 1000

    @pytest.mark.asyncio
    async def test_empty_dataset_handling(self, mock_data_provider):
        """Test handling of empty datasets."""
        from paidsearchnav.core.config import AnalyzerThresholds

        thresholds = AnalyzerThresholds()
        analyzer = SearchTermsAnalyzer(
            data_provider=mock_data_provider,
            thresholds=thresholds,
        )

        # Set empty data
        mock_data_provider.search_terms_data = []
        mock_data_provider.keywords_data = []

        result = await analyzer.analyze(
            customer_id="12345",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        # Verify empty result handling
        assert result.total_search_terms == 0
        assert result.total_impressions == 0
        assert result.total_clicks == 0
        assert result.total_cost == 0.0
        assert result.total_conversions == 0.0
        assert len(result.add_candidates) == 0
        assert len(result.negative_candidates) == 0
        assert len(result.already_covered) == 0
        assert len(result.review_needed) == 0

    @pytest.mark.asyncio
    async def test_very_large_batch_processing(self, mock_data_provider):
        """Test processing with very large batches."""
        from paidsearchnav.core.config import AnalyzerThresholds

        thresholds = AnalyzerThresholds(min_impressions=1)
        analyzer = SearchTermsAnalyzer(
            data_provider=mock_data_provider,
            thresholds=thresholds,
            batch_size=5000,  # Large batch size
        )

        # Create large dataset
        large_dataset = []
        for i in range(5000):
            st = create_search_term(
                search_term=f"large test term {i}",
                impressions=100,
                clicks=10,
                cost=5.0,
                conversions=0.5 if i % 10 == 0 else 0,
            )
            large_dataset.append(st)

        mock_data_provider.search_terms_data = large_dataset
        mock_data_provider.keywords_data = []

        result = await analyzer.analyze(
            customer_id="12345",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        # Verify all data was processed
        assert result.total_search_terms == 5000
        assert result.total_impressions == 500000
        assert result.total_clicks == 50000
        assert result.total_cost == 25000.0

    @pytest.mark.asyncio
    async def test_single_item_batch(self, mock_data_provider):
        """Test with batch size of minimum allowed (100)."""
        from paidsearchnav.core.config import AnalyzerThresholds

        thresholds = AnalyzerThresholds(min_impressions=1)
        analyzer = SearchTermsAnalyzer(
            data_provider=mock_data_provider,
            thresholds=thresholds,
            batch_size=100,  # Minimum allowed batch size
        )

        # Create dataset slightly larger than batch size
        dataset = []
        for i in range(150):
            st = create_search_term(
                search_term=f"small batch term {i}",
                impressions=10,
                clicks=1,
                cost=1.0,
            )
            dataset.append(st)

        mock_data_provider.search_terms_data = dataset
        mock_data_provider.keywords_data = []

        result = await analyzer.analyze(
            customer_id="12345",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        # Verify all data was processed despite small batch size
        assert result.total_search_terms == 150
        assert result.total_impressions == 1500
        assert result.total_clicks == 150
        assert result.total_cost == 150.0
