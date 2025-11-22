"""Tests for the advanced search term analyzer."""

from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from paidsearchnav.analyzers.search_term_analyzer import (
    SearchTermAnalyzer,
    SearchTermIntent,
)
from paidsearchnav.core.models import (
    AnalysisResult,
    Keyword,
    MatchType,
    RecommendationPriority,
    RecommendationType,
    SearchTerm,
    SearchTermMetrics,
)


@pytest.fixture
def mock_data_provider():
    """Create a mock data provider."""
    return AsyncMock()


@pytest.fixture
def analyzer(mock_data_provider):
    """Create analyzer instance."""
    return SearchTermAnalyzer(mock_data_provider)


@pytest.fixture
def sample_search_terms():
    """Create sample search terms for testing."""
    return [
        SearchTerm(
            campaign_id="123",
            campaign_name="Test Campaign",
            ad_group_id="456",
            ad_group_name="Test Ad Group",
            search_term="best coffee shop near me",
            keyword_id="789",
            keyword_text="coffee shop",
            match_type="BROAD",
            metrics=SearchTermMetrics(
                impressions=1000,
                clicks=100,
                cost=150.0,
                conversions=5.0,
                conversion_value=250.0,
            ),
        ),
        SearchTerm(
            campaign_id="123",
            campaign_name="Test Campaign",
            ad_group_id="456",
            ad_group_name="Test Ad Group",
            search_term="coffee shop hours",
            keyword_id="790",
            keyword_text="coffee shop",
            match_type="BROAD",
            metrics=SearchTermMetrics(
                impressions=500,
                clicks=50,
                cost=75.0,
                conversions=2.0,
                conversion_value=100.0,
            ),
        ),
        SearchTerm(
            campaign_id="123",
            campaign_name="Test Campaign",
            ad_group_id="456",
            ad_group_name="Test Ad Group",
            search_term="how to make coffee at home",
            keyword_id="791",
            keyword_text="coffee",
            match_type="BROAD",
            metrics=SearchTermMetrics(
                impressions=2000,
                clicks=20,
                cost=10.0,
                conversions=0.0,
                conversion_value=0.0,
            ),
        ),
        SearchTerm(
            campaign_id="123",
            campaign_name="Test Campaign",
            ad_group_id="456",
            ad_group_name="Test Ad Group",
            search_term="buy coffee machine online",
            keyword_id="792",
            keyword_text="coffee machine",
            match_type="PHRASE",
            metrics=SearchTermMetrics(
                impressions=800,
                clicks=80,
                cost=120.0,
                conversions=8.0,
                conversion_value=800.0,
            ),
        ),
        SearchTerm(
            campaign_id="123",
            campaign_name="Test Campaign",
            ad_group_id="456",
            ad_group_name="Test Ad Group",
            search_term="coffee jobs hiring",
            keyword_id="793",
            keyword_text="coffee",
            match_type="BROAD",
            metrics=SearchTermMetrics(
                impressions=1500,
                clicks=150,
                cost=200.0,
                conversions=0.0,
                conversion_value=0.0,
            ),
        ),
    ]


@pytest.fixture
def sample_keywords():
    """Create sample keywords for testing."""
    return [
        Keyword(
            keyword_id="789",
            ad_group_id="456",
            ad_group_name="Test Ad Group",
            campaign_id="123",
            campaign_name="Test Campaign",
            text="coffee shop",
            match_type=MatchType.BROAD,
            status="ENABLED",
            impressions=5000,
            clicks=500,
            cost=750.0,
            conversions=25.0,
            conversion_value=1250.0,
        ),
        Keyword(
            keyword_id="792",
            ad_group_id="456",
            ad_group_name="Test Ad Group",
            campaign_id="123",
            campaign_name="Test Campaign",
            text="coffee machine",
            match_type=MatchType.PHRASE,
            status="ENABLED",
            impressions=3000,
            clicks=300,
            cost=450.0,
            conversions=30.0,
            conversion_value=3000.0,
        ),
    ]


class TestSearchTermAnalyzer:
    """Test the SearchTermAnalyzer class."""

    def test_get_name(self, analyzer):
        """Test analyzer name."""
        assert analyzer.get_name() == "Advanced Search Term Analyzer"

    def test_get_description(self, analyzer):
        """Test analyzer description."""
        description = analyzer.get_description()
        assert "intent classification" in description
        assert "pattern recognition" in description

    @pytest.mark.asyncio
    async def test_analyze_basic(
        self, analyzer, mock_data_provider, sample_search_terms, sample_keywords
    ):
        """Test basic analysis functionality."""
        # Setup mock
        mock_data_provider.get_search_terms.return_value = sample_search_terms
        mock_data_provider.get_keywords.return_value = sample_keywords

        # Run analysis
        result = await analyzer.analyze(
            customer_id="12345",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        # Verify result type
        assert isinstance(result, AnalysisResult)
        assert result.analysis_type == "advanced_search_terms"
        assert result.analyzer_name == "Advanced Search Term Analyzer"

        # Verify calls
        mock_data_provider.get_search_terms.assert_called_once()
        mock_data_provider.get_keywords.assert_called_once()

    @pytest.mark.asyncio
    async def test_intent_classification(
        self, analyzer, mock_data_provider, sample_search_terms, sample_keywords
    ):
        """Test search intent classification."""
        # Setup mock
        mock_data_provider.get_search_terms.return_value = sample_search_terms
        mock_data_provider.get_keywords.return_value = sample_keywords

        # Run analysis
        result = await analyzer.analyze(
            customer_id="12345",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        # Check intent analysis in raw data
        intent_analysis = result.raw_data.get("intent_analysis", {})
        assert SearchTermIntent.LOCAL in intent_analysis  # "near me" query
        assert SearchTermIntent.TRANSACTIONAL in intent_analysis  # "buy" query
        assert SearchTermIntent.INFORMATIONAL in intent_analysis  # "how to" query

    @pytest.mark.asyncio
    async def test_negative_keyword_mining(
        self, analyzer, mock_data_provider, sample_search_terms, sample_keywords
    ):
        """Test negative keyword identification."""
        # Setup mock
        mock_data_provider.get_search_terms.return_value = sample_search_terms
        mock_data_provider.get_keywords.return_value = sample_keywords

        # Run analysis
        result = await analyzer.analyze(
            customer_id="12345",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        # Check negative analysis in raw data first
        negative_analysis = result.raw_data.get("negative_analysis", {})

        # Check that we found some negative keywords
        all_negatives = []
        for category in negative_analysis.values():
            if isinstance(category, list):
                all_negatives.extend(category)

        assert len(all_negatives) > 0, (
            f"No negative keywords found. Raw data: {negative_analysis}"
        )

        # Check for negative keyword recommendations
        negative_recs = [
            r
            for r in result.recommendations
            if r.type == RecommendationType.ADD_NEGATIVE
        ]
        assert len(negative_recs) > 0, (
            f"No negative recommendations found. All recommendations: {[(r.type, r.title) for r in result.recommendations]}"
        )

        # Should identify "coffee jobs hiring" as negative (jobs pattern)
        irrelevant_negatives = negative_analysis.get("irrelevant", [])
        assert any("jobs" in neg["term"] for neg in irrelevant_negatives)

    @pytest.mark.asyncio
    async def test_opportunity_mining(
        self, analyzer, mock_data_provider, sample_search_terms, sample_keywords
    ):
        """Test new keyword opportunity identification."""
        # Add a high-converting term not in keywords
        new_term = SearchTerm(
            campaign_id="123",
            campaign_name="Test Campaign",
            ad_group_id="456",
            ad_group_name="Test Ad Group",
            search_term="premium coffee beans",
            keyword_id="794",
            keyword_text="coffee",
            match_type="BROAD",
            metrics=SearchTermMetrics(
                impressions=600,
                clicks=60,
                cost=90.0,
                conversions=6.0,
                conversion_value=600.0,
            ),
        )
        terms_with_opportunity = sample_search_terms + [new_term]

        # Setup mock
        mock_data_provider.get_search_terms.return_value = terms_with_opportunity
        mock_data_provider.get_keywords.return_value = sample_keywords

        # Run analysis
        result = await analyzer.analyze(
            customer_id="12345",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        # Check for add keyword recommendations
        add_recs = [
            r
            for r in result.recommendations
            if r.type == RecommendationType.ADD_KEYWORD
        ]
        assert len(add_recs) > 0

    @pytest.mark.asyncio
    async def test_local_intent_analysis(
        self, analyzer, mock_data_provider, sample_search_terms, sample_keywords
    ):
        """Test local intent analysis."""
        # Setup mock
        mock_data_provider.get_search_terms.return_value = sample_search_terms
        mock_data_provider.get_keywords.return_value = sample_keywords

        # Run analysis
        result = await analyzer.analyze(
            customer_id="12345",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        # Check local intent analysis
        local_analysis = result.raw_data.get("local_analysis", {})
        near_me_data = local_analysis.get("near_me_analysis", {})
        assert len(near_me_data.get("terms", [])) > 0  # Should find "near me" term

        # Check for location optimization recommendations
        location_recs = [
            r
            for r in result.recommendations
            if r.type == RecommendationType.OPTIMIZE_LOCATION
        ]
        assert len(location_recs) > 0

    @pytest.mark.asyncio
    async def test_ngram_analysis(
        self, analyzer, mock_data_provider, sample_search_terms, sample_keywords
    ):
        """Test n-gram pattern analysis."""
        # Setup mock
        mock_data_provider.get_search_terms.return_value = sample_search_terms
        mock_data_provider.get_keywords.return_value = sample_keywords

        # Run analysis
        result = await analyzer.analyze(
            customer_id="12345",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        # Check n-gram analysis in metrics
        custom_metrics = result.metrics.custom_metrics
        top_ngrams = custom_metrics.get("top_ngrams", [])
        assert len(top_ngrams) > 0
        assert all("ngram" in ng for ng in top_ngrams)

    @pytest.mark.asyncio
    async def test_pattern_analysis(
        self, analyzer, mock_data_provider, sample_search_terms, sample_keywords
    ):
        """Test query pattern analysis."""
        # Setup mock
        mock_data_provider.get_search_terms.return_value = sample_search_terms
        mock_data_provider.get_keywords.return_value = sample_keywords

        # Run analysis
        result = await analyzer.analyze(
            customer_id="12345",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        # Check pattern analysis in raw data
        pattern_analysis = result.raw_data.get("pattern_analysis", {})
        assert "query_length" in pattern_analysis
        assert "modifiers" in pattern_analysis
        assert "performance_patterns" in pattern_analysis

    @pytest.mark.asyncio
    async def test_recommendations_priority(
        self, analyzer, mock_data_provider, sample_search_terms, sample_keywords
    ):
        """Test that recommendations have appropriate priorities."""
        # Setup mock
        mock_data_provider.get_search_terms.return_value = sample_search_terms
        mock_data_provider.get_keywords.return_value = sample_keywords

        # Run analysis
        result = await analyzer.analyze(
            customer_id="12345",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        # Check recommendation priorities
        assert len(result.recommendations) > 0

        # High cost negative keywords should be critical priority
        critical_recs = [
            r
            for r in result.recommendations
            if r.priority == RecommendationPriority.CRITICAL
        ]
        assert any(r.type == RecommendationType.ADD_NEGATIVE for r in critical_recs)

    @pytest.mark.asyncio
    async def test_intent_classification_methods(self, analyzer):
        """Test individual intent classification."""
        # Test transactional
        assert (
            analyzer._classify_intent("buy coffee online")
            == SearchTermIntent.TRANSACTIONAL
        )
        assert (
            analyzer._classify_intent("coffee for sale")
            == SearchTermIntent.TRANSACTIONAL
        )

        # Test informational
        assert (
            analyzer._classify_intent("how to make coffee")
            == SearchTermIntent.INFORMATIONAL
        )
        assert (
            analyzer._classify_intent("what is espresso")
            == SearchTermIntent.INFORMATIONAL
        )

        # Test navigational
        assert (
            analyzer._classify_intent("starbucks.com") == SearchTermIntent.NAVIGATIONAL
        )
        assert (
            analyzer._classify_intent("coffee shop official website")
            == SearchTermIntent.NAVIGATIONAL
        )

        # Test local
        assert analyzer._classify_intent("coffee near me") == SearchTermIntent.LOCAL
        assert (
            analyzer._classify_intent("closest coffee shop") == SearchTermIntent.LOCAL
        )

    def test_get_base_form(self, analyzer):
        """Test base form extraction."""
        # "shop" is now removed as a shopping modifier
        assert analyzer._get_base_form("best coffee shop near me") == "coffee"
        assert analyzer._get_base_form("cheap coffee online") == "coffee"
        assert analyzer._get_base_form("coffee") == "coffee"
        # Test that meaningful words are kept
        assert (
            analyzer._get_base_form("best laptop computer online") == "laptop computer"
        )

    @pytest.mark.asyncio
    async def test_empty_search_terms(
        self, analyzer, mock_data_provider, sample_keywords
    ):
        """Test handling of empty search terms."""
        # Setup mock with empty search terms
        mock_data_provider.get_search_terms.return_value = []
        mock_data_provider.get_keywords.return_value = sample_keywords

        # Run analysis
        result = await analyzer.analyze(
            customer_id="12345",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        # Should complete without errors
        assert result.status == "completed"
        assert result.metrics.total_search_terms_analyzed == 0

    @pytest.mark.asyncio
    async def test_question_analysis(
        self, analyzer, mock_data_provider, sample_search_terms, sample_keywords
    ):
        """Test question query analysis."""
        # Add more question queries
        question_terms = [
            SearchTerm(
                campaign_id="123",
                campaign_name="Test Campaign",
                ad_group_id="456",
                ad_group_name="Test Ad Group",
                search_term="what is the best coffee maker",
                keyword_id="795",
                keyword_text="coffee maker",
                match_type="BROAD",
                metrics=SearchTermMetrics(
                    impressions=300,
                    clicks=30,
                    cost=45.0,
                    conversions=2.0,
                    conversion_value=200.0,
                ),
            ),
            SearchTerm(
                campaign_id="123",
                campaign_name="Test Campaign",
                ad_group_id="456",
                ad_group_name="Test Ad Group",
                search_term="where to buy coffee beans",
                keyword_id="796",
                keyword_text="coffee beans",
                match_type="BROAD",
                metrics=SearchTermMetrics(
                    impressions=200,
                    clicks=20,
                    cost=30.0,
                    conversions=1.0,
                    conversion_value=100.0,
                ),
            ),
        ]

        # Setup mock
        mock_data_provider.get_search_terms.return_value = (
            sample_search_terms + question_terms
        )
        mock_data_provider.get_keywords.return_value = sample_keywords

        # Run analysis
        result = await analyzer.analyze(
            customer_id="12345",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        # Check raw data contains question analysis
        assert "intent_analysis" in result.raw_data
        intent_data = result.raw_data["intent_analysis"]

        # Should have informational intent queries
        assert SearchTermIntent.INFORMATIONAL in intent_data
        informational_terms = intent_data[SearchTermIntent.INFORMATIONAL]["terms"]
        assert any("how to" in t.search_term.lower() for t in informational_terms)

        # Check that we found some question terms (may be classified as different intents)
        all_terms = []
        for intent_terms in intent_data.values():
            if isinstance(intent_terms, dict) and "terms" in intent_terms:
                all_terms.extend(intent_terms["terms"])

        assert any("what is" in t.search_term.lower() for t in all_terms)
        assert any("where to" in t.search_term.lower() for t in all_terms)

    @pytest.mark.asyncio
    async def test_modifier_analysis(
        self, analyzer, mock_data_provider, sample_keywords
    ):
        """Test modifier word analysis."""
        # Create terms with various modifiers
        modifier_terms = [
            SearchTerm(
                campaign_id="123",
                campaign_name="Test Campaign",
                ad_group_id="456",
                ad_group_name="Test Ad Group",
                search_term="best coffee maker 2024",
                keyword_id="797",
                keyword_text="coffee maker",
                match_type="BROAD",
                metrics=SearchTermMetrics(
                    impressions=500,
                    clicks=50,
                    cost=75.0,
                    conversions=5.0,
                    conversion_value=500.0,
                ),
            ),
            SearchTerm(
                campaign_id="123",
                campaign_name="Test Campaign",
                ad_group_id="456",
                ad_group_name="Test Ad Group",
                search_term="cheap coffee beans",
                keyword_id="798",
                keyword_text="coffee beans",
                match_type="BROAD",
                metrics=SearchTermMetrics(
                    impressions=400,
                    clicks=40,
                    cost=40.0,
                    conversions=2.0,
                    conversion_value=100.0,
                ),
            ),
        ]

        # Setup mock
        mock_data_provider.get_search_terms.return_value = modifier_terms
        mock_data_provider.get_keywords.return_value = sample_keywords

        # Run analysis
        result = await analyzer.analyze(
            customer_id="12345",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        # Check pattern analysis contains modifier data
        pattern_analysis = result.raw_data.get("pattern_analysis", {})
        modifiers = pattern_analysis.get("modifiers", {})

        assert "quality" in modifiers  # Should find "best"
        assert "price" in modifiers  # Should find "cheap"
        assert modifiers["quality"]["term_count"] > 0
        assert modifiers["price"]["term_count"] > 0
