"""Unit tests for placement audit analyzer."""

from datetime import datetime
from unittest.mock import AsyncMock, Mock

import pytest

from paidsearchnav_mcp.analyzers.placement_audit import PlacementAuditAnalyzer
from paidsearchnav_mcp.models.analysis import (
    PlacementCategory,
    PlacementQualityScore,
    PlacementType,
    RecommendationPriority,
    RecommendationType,
)


@pytest.fixture
def mock_data_provider():
    """Create mock data provider."""
    return Mock()


@pytest.fixture
def analyzer(mock_data_provider):
    """Create analyzer instance."""
    return PlacementAuditAnalyzer(mock_data_provider)


@pytest.fixture
def sample_placement_data():
    """Create sample placement data."""
    return [
        {
            "placement_id": "placement_1",
            "placement_name": "example.com",
            "display_name": "Example News Site",
            "impressions": 10000,
            "clicks": 100,
            "cost": 200.0,
            "conversions": 5.0,
            "conversion_value": 250.0,
            "ctr": 1.0,
            "cpc": 2.0,
            "cpa": 40.0,
            "roas": 1.25,
            "campaign_ids": ["campaign_1"],
            "ad_group_ids": ["adgroup_1"],
            "is_brand_safe": True,
        },
        {
            "placement_id": "placement_2",
            "placement_name": "spamsite.net",
            "display_name": "Low Quality Site",
            "impressions": 50000,
            "clicks": 10,
            "cost": 500.0,
            "conversions": 0.0,
            "conversion_value": 0.0,
            "ctr": 0.02,
            "cpc": 50.0,
            "cpa": 0.0,
            "roas": 0.0,
            "campaign_ids": ["campaign_1"],
            "ad_group_ids": ["adgroup_1"],
            "is_brand_safe": False,
        },
        {
            "placement_id": "placement_3",
            "placement_name": "youtube.com/watch?v=12345",
            "display_name": "YouTube Video",
            "impressions": 5000,
            "clicks": 250,
            "cost": 100.0,
            "conversions": 10.0,
            "conversion_value": 500.0,
            "ctr": 5.0,
            "cpc": 0.4,
            "cpa": 10.0,
            "roas": 5.0,
            "campaign_ids": ["campaign_2"],
            "ad_group_ids": ["adgroup_2"],
            "is_brand_safe": True,
        },
        {
            "placement_id": "placement_4",
            "placement_name": "мойсайт.рф",
            "display_name": "Russian Website",
            "impressions": 2000,
            "clicks": 20,
            "cost": 150.0,
            "conversions": 1.0,
            "conversion_value": 50.0,
            "ctr": 1.0,
            "cpc": 7.5,
            "cpa": 150.0,
            "roas": 0.33,
            "campaign_ids": ["campaign_1"],
            "ad_group_ids": ["adgroup_1"],
            "is_brand_safe": True,
        },
        {
            "placement_id": "placement_5",
            "placement_name": "amazon.com",
            "display_name": "Amazon Shopping",
            "impressions": 15000,
            "clicks": 300,
            "cost": 300.0,
            "conversions": 15.0,
            "conversion_value": 750.0,
            "ctr": 2.0,
            "cpc": 1.0,
            "cpa": 20.0,
            "roas": 2.5,
            "campaign_ids": ["campaign_2"],
            "ad_group_ids": ["adgroup_2"],
            "is_brand_safe": True,
        },
    ]


@pytest.mark.asyncio
async def test_analyzer_initialization(mock_data_provider):
    """Test analyzer initialization with custom parameters."""
    analyzer = PlacementAuditAnalyzer(
        data_provider=mock_data_provider,
        min_impressions=200,
        min_ctr_threshold=1.0,
        max_cpa_multiplier=2.5,
        spam_threshold=80.0,
        high_cost_threshold=150.0,
    )

    assert analyzer.min_impressions == 200
    assert analyzer.min_ctr_threshold == 1.0
    assert analyzer.max_cpa_multiplier == 2.5
    assert analyzer.spam_threshold == 80.0
    assert analyzer.high_cost_threshold == 150.0


def test_get_name(analyzer):
    """Test analyzer name."""
    assert analyzer.get_name() == "Placement Audit Analyzer"


def test_get_description(analyzer):
    """Test analyzer description."""
    description = analyzer.get_description()
    assert "placement performance" in description.lower()
    assert "exclusion recommendations" in description.lower()


def test_determine_placement_type(analyzer):
    """Test placement type determination."""
    # Website
    assert analyzer._determine_placement_type("example.com") == PlacementType.WEBSITE
    assert (
        analyzer._determine_placement_type("https://example.com")
        == PlacementType.WEBSITE
    )

    # YouTube video
    assert (
        analyzer._determine_placement_type("youtube.com/watch?v=12345")
        == PlacementType.YOUTUBE_VIDEO
    )

    # YouTube channel
    assert (
        analyzer._determine_placement_type("youtube.com/channel/UC123")
        == PlacementType.YOUTUBE_CHANNEL
    )
    assert (
        analyzer._determine_placement_type("youtube.com/c/mychannel")
        == PlacementType.YOUTUBE_CHANNEL
    )

    # Video
    assert (
        analyzer._determine_placement_type("video.example.com") == PlacementType.VIDEO
    )

    # Mobile app
    assert (
        analyzer._determine_placement_type("com.example.app")
        == PlacementType.MOBILE_APP
    )
    assert (
        analyzer._determine_placement_type("mobile.example.com")
        == PlacementType.MOBILE_APP
    )

    # Unknown
    assert analyzer._determine_placement_type("") == PlacementType.UNKNOWN


def test_categorize_placement(analyzer):
    """Test placement categorization."""
    # News
    assert analyzer._categorize_placement("cnn.com") == PlacementCategory.NEWS
    assert analyzer._categorize_placement("news.example.com") == PlacementCategory.NEWS

    # Entertainment
    assert (
        analyzer._categorize_placement("entertainment.com")
        == PlacementCategory.ENTERTAINMENT
    )
    assert (
        analyzer._categorize_placement("netflix.com") == PlacementCategory.ENTERTAINMENT
    )

    # Retail
    assert analyzer._categorize_placement("amazon.com") == PlacementCategory.RETAIL
    assert (
        analyzer._categorize_placement("shop.example.com") == PlacementCategory.RETAIL
    )

    # Technology
    assert (
        analyzer._categorize_placement("tech.example.com")
        == PlacementCategory.TECHNOLOGY
    )
    assert (
        analyzer._categorize_placement("software.com") == PlacementCategory.TECHNOLOGY
    )

    # Other
    assert (
        analyzer._categorize_placement("random.example.com") == PlacementCategory.OTHER
    )

    # Unknown
    assert analyzer._categorize_placement("") == PlacementCategory.UNKNOWN


def test_detect_character_set(analyzer):
    """Test character set detection."""
    # Latin/English
    assert analyzer._detect_character_set("example.com") == "Latin"
    assert analyzer._detect_character_set("test123") == "Latin"

    # Chinese
    assert analyzer._detect_character_set("测试网站.com") == "Chinese"

    # Cyrillic
    assert analyzer._detect_character_set("тест.рф") == "Cyrillic"

    # Arabic
    assert analyzer._detect_character_set("تجربة.com") == "Arabic"

    # Japanese
    assert analyzer._detect_character_set("テスト.jp") == "Japanese"

    # Korean
    assert analyzer._detect_character_set("테스트.kr") == "Korean"

    # Non-Latin (unspecified)
    assert analyzer._detect_character_set("ñoño.com") == "Non-Latin"

    # None
    assert analyzer._detect_character_set("") is None


def test_calculate_quality_score(analyzer):
    """Test quality score calculation."""
    from paidsearchnav.core.models.analysis import PlacementMetrics

    # Excellent quality (high CTR, conversion rate, ROAS)
    excellent_metrics = PlacementMetrics(
        impressions=1000,
        clicks=50,
        cost=100.0,
        conversions=5.0,
        conversion_value=500.0,
        ctr=5.0,
        cpc=2.0,
        cpa=20.0,
        roas=5.0,
    )
    data = {"is_brand_safe": True}
    quality = analyzer._calculate_quality_score(excellent_metrics, data)
    assert quality == PlacementQualityScore.EXCELLENT

    # Poor quality (low CTR, no conversions)
    poor_metrics = PlacementMetrics(
        impressions=10000,
        clicks=5,
        cost=100.0,
        conversions=0.0,
        conversion_value=0.0,
        ctr=0.05,
        cpc=20.0,
        cpa=0.0,
        roas=0.0,
    )
    data = {"is_brand_safe": False}
    quality = analyzer._calculate_quality_score(poor_metrics, data)
    assert quality in [PlacementQualityScore.VERY_POOR, PlacementQualityScore.POOR]


@pytest.mark.asyncio
async def test_convert_to_placements(analyzer, sample_placement_data):
    """Test conversion of raw data to Placement objects."""
    placements = await analyzer._convert_to_placements(sample_placement_data)

    assert len(placements) == 5

    # Check first placement
    placement = placements[0]
    assert placement.placement_id == "placement_1"
    assert placement.placement_name == "example.com"
    assert placement.placement_type == PlacementType.WEBSITE
    assert placement.metrics.impressions == 10000
    assert placement.metrics.cost == 200.0
    assert placement.character_set == "Latin"

    # Check YouTube placement
    youtube_placement = placements[2]
    assert youtube_placement.placement_type == PlacementType.YOUTUBE_VIDEO
    assert youtube_placement.quality_score == PlacementQualityScore.EXCELLENT

    # Check Russian placement
    russian_placement = placements[3]
    assert russian_placement.character_set == "Cyrillic"

    # Check Amazon placement
    amazon_placement = placements[4]
    assert amazon_placement.category == PlacementCategory.RETAIL


def test_calculate_account_averages(analyzer):
    """Test account averages calculation."""
    from paidsearchnav.core.models.analysis import (
        Placement,
        PlacementCategory,
        PlacementMetrics,
        PlacementQualityScore,
        PlacementType,
    )

    placements = [
        Placement(
            placement_id="1",
            placement_name="test1.com",
            display_name="Test 1",
            placement_type=PlacementType.WEBSITE,
            category=PlacementCategory.OTHER,
            quality_score=PlacementQualityScore.GOOD,
            metrics=PlacementMetrics(
                impressions=1000,
                clicks=100,
                cost=200.0,
                conversions=10.0,
                conversion_value=500.0,
            ),
        ),
        Placement(
            placement_id="2",
            placement_name="test2.com",
            display_name="Test 2",
            placement_type=PlacementType.WEBSITE,
            category=PlacementCategory.OTHER,
            quality_score=PlacementQualityScore.FAIR,
            metrics=PlacementMetrics(
                impressions=2000,
                clicks=50,
                cost=100.0,
                conversions=5.0,
                conversion_value=250.0,
            ),
        ),
    ]

    averages = analyzer._calculate_account_averages(placements)

    assert averages["ctr"] == 5.0  # (150 clicks / 3000 impressions) * 100
    assert averages["cpa"] == 20.0  # 300 cost / 15 conversions
    assert averages["roas"] == 2.5  # 750 value / 300 cost


def test_should_exclude_placement(analyzer):
    """Test placement exclusion logic."""
    from paidsearchnav.core.models.analysis import (
        Placement,
        PlacementCategory,
        PlacementMetrics,
        PlacementQualityScore,
        PlacementType,
    )

    account_averages = {"ctr": 2.0, "cpa": 20.0, "roas": 2.0}

    # High spam risk placement
    spam_placement = Placement(
        placement_id="spam",
        placement_name="spam.com",
        display_name="Spam Site",
        placement_type=PlacementType.WEBSITE,
        category=PlacementCategory.OTHER,
        quality_score=PlacementQualityScore.VERY_POOR,
        metrics=PlacementMetrics(
            impressions=10000,
            clicks=5,
            cost=200.0,
            conversions=0.0,
        ),
    )

    assert analyzer._should_exclude_placement(spam_placement, account_averages)

    # Good performing placement
    good_placement = Placement(
        placement_id="good",
        placement_name="good.com",
        display_name="Good Site",
        placement_type=PlacementType.WEBSITE,
        category=PlacementCategory.OTHER,
        quality_score=PlacementQualityScore.EXCELLENT,
        metrics=PlacementMetrics(
            impressions=1000,
            clicks=50,
            cost=100.0,
            conversions=10.0,
            ctr=5.0,
            cpa=10.0,
        ),
    )

    assert not analyzer._should_exclude_placement(good_placement, account_averages)


@pytest.mark.asyncio
async def test_analyze_with_mock_data(
    analyzer, mock_data_provider, sample_placement_data
):
    """Test full analysis with mock data."""
    # Setup mock
    mock_data_provider.get_placement_data = AsyncMock(
        return_value=sample_placement_data
    )

    # Run analysis
    start_date = datetime(2024, 1, 1)
    end_date = datetime(2024, 1, 31)
    result = await analyzer.analyze(
        customer_id="123456789",
        start_date=start_date,
        end_date=end_date,
        campaigns=["campaign_1"],
    )

    # Verify result structure
    assert result.customer_id == "123456789"
    assert result.analysis_type == "placement_audit"
    assert result.analyzer_name == "Placement Audit Analyzer"
    assert result.start_date == start_date
    assert result.end_date == end_date
    assert result.total_placements == 5

    # Verify placements were analyzed
    assert len(result.all_placements) == 5
    assert result.total_placement_cost > 0
    assert result.total_placement_conversions > 0

    # Verify categorization
    assert len(result.underperforming_placements) > 0
    assert len(result.exclusion_recommendations) > 0

    # Verify recommendations
    assert len(result.recommendations) > 0
    assert any(
        r.priority == RecommendationPriority.CRITICAL for r in result.recommendations
    )


def test_analyze_category_performance(analyzer):
    """Test category performance analysis."""
    from paidsearchnav.core.models.analysis import (
        Placement,
        PlacementCategory,
        PlacementMetrics,
        PlacementQualityScore,
        PlacementType,
    )

    placements = [
        Placement(
            placement_id="1",
            placement_name="news.com",
            display_name="News Site",
            placement_type=PlacementType.WEBSITE,
            category=PlacementCategory.NEWS,
            quality_score=PlacementQualityScore.GOOD,
            metrics=PlacementMetrics(
                impressions=1000,
                clicks=100,
                cost=200.0,
                conversions=10.0,
            ),
        ),
        Placement(
            placement_id="2",
            placement_name="shop.com",
            display_name="Shopping Site",
            placement_type=PlacementType.WEBSITE,
            category=PlacementCategory.RETAIL,
            quality_score=PlacementQualityScore.EXCELLENT,
            metrics=PlacementMetrics(
                impressions=2000,
                clicks=200,
                cost=300.0,
                conversions=20.0,
            ),
        ),
    ]

    category_perf = analyzer._analyze_category_performance(placements)

    assert PlacementCategory.NEWS in category_perf
    assert PlacementCategory.RETAIL in category_perf

    news_stats = category_perf[PlacementCategory.NEWS]
    assert news_stats["count"] == 1
    assert news_stats["cost"] == 200.0
    assert news_stats["conversions"] == 10.0
    assert news_stats["ctr"] == 10.0  # 100/1000 * 100


def test_analyze_quality_distribution(analyzer):
    """Test quality distribution analysis."""
    from paidsearchnav.core.models.analysis import (
        Placement,
        PlacementCategory,
        PlacementMetrics,
        PlacementQualityScore,
        PlacementType,
    )

    placements = [
        Placement(
            placement_id="1",
            placement_name="good.com",
            display_name="Good Site",
            placement_type=PlacementType.WEBSITE,
            category=PlacementCategory.OTHER,
            quality_score=PlacementQualityScore.EXCELLENT,
            metrics=PlacementMetrics(),
        ),
        Placement(
            placement_id="2",
            placement_name="bad.com",
            display_name="Bad Site",
            placement_type=PlacementType.WEBSITE,
            category=PlacementCategory.OTHER,
            quality_score=PlacementQualityScore.POOR,
            metrics=PlacementMetrics(),
        ),
        Placement(
            placement_id="3",
            placement_name="okay.com",
            display_name="Okay Site",
            placement_type=PlacementType.WEBSITE,
            category=PlacementCategory.OTHER,
            quality_score=PlacementQualityScore.GOOD,
            metrics=PlacementMetrics(),
        ),
    ]

    distribution = analyzer._analyze_quality_distribution(placements)

    assert distribution[PlacementQualityScore.EXCELLENT] == 1
    assert distribution[PlacementQualityScore.GOOD] == 1
    assert distribution[PlacementQualityScore.POOR] == 1


def test_generate_recommendations(analyzer):
    """Test recommendation generation."""
    from paidsearchnav.core.models.analysis import (
        Placement,
        PlacementCategory,
        PlacementMetrics,
        PlacementQualityScore,
        PlacementType,
    )

    # Create test placements
    spam_placement = Placement(
        placement_id="spam",
        placement_name="spam.com",
        display_name="Spam Site",
        placement_type=PlacementType.WEBSITE,
        category=PlacementCategory.OTHER,
        quality_score=PlacementQualityScore.VERY_POOR,
        metrics=PlacementMetrics(cost=100.0, conversions=0.0),
    )

    high_cost_placement = Placement(
        placement_id="expensive",
        placement_name="expensive.com",
        display_name="Expensive Site",
        placement_type=PlacementType.WEBSITE,
        category=PlacementCategory.OTHER,
        quality_score=PlacementQualityScore.POOR,
        metrics=PlacementMetrics(cost=200.0, conversions=0.0),
    )

    underperforming_placement = Placement(
        placement_id="under",
        placement_name="under.com",
        display_name="Underperforming Site",
        placement_type=PlacementType.WEBSITE,
        category=PlacementCategory.OTHER,
        quality_score=PlacementQualityScore.FAIR,
        metrics=PlacementMetrics(cost=50.0, conversions=1.0),
    )

    account_averages = {"ctr": 2.0, "cpa": 20.0, "roas": 2.0}

    recommendations = analyzer._generate_recommendations(
        underperforming=[underperforming_placement],
        high_cost=[high_cost_placement],
        spam_placements=[spam_placement],
        exclusion_recommendations=[spam_placement, high_cost_placement],
        account_averages=account_averages,
    )

    assert len(recommendations) >= 2

    # Check for critical spam recommendation
    spam_recs = [
        r for r in recommendations if r.priority == RecommendationPriority.CRITICAL
    ]
    assert len(spam_recs) > 0
    assert spam_recs[0].type == RecommendationType.ADD_NEGATIVE

    # Check for high priority cost recommendation
    high_recs = [
        r for r in recommendations if r.priority == RecommendationPriority.HIGH
    ]
    assert len(high_recs) > 0


def test_placement_properties():
    """Test placement property methods."""
    from paidsearchnav.core.models.analysis import (
        Placement,
        PlacementCategory,
        PlacementMetrics,
        PlacementQualityScore,
        PlacementType,
    )

    # Underperforming placement
    underperforming = Placement(
        placement_id="under",
        placement_name="under.com",
        display_name="Underperforming",
        placement_type=PlacementType.WEBSITE,
        category=PlacementCategory.OTHER,
        quality_score=PlacementQualityScore.POOR,
        metrics=PlacementMetrics(ctr=0.3),  # Below 0.5% threshold
    )

    assert underperforming.is_underperforming

    # High cost placement
    high_cost = Placement(
        placement_id="expensive",
        placement_name="expensive.com",
        display_name="Expensive",
        placement_type=PlacementType.WEBSITE,
        category=PlacementCategory.OTHER,
        quality_score=PlacementQualityScore.FAIR,
        metrics=PlacementMetrics(cost=150.0, cpa=60.0),  # Above thresholds
    )

    assert high_cost.is_high_cost

    # Spam risk score
    spam = Placement(
        placement_id="spam",
        placement_name="spam.com",
        display_name="Spam",
        placement_type=PlacementType.WEBSITE,
        category=PlacementCategory.OTHER,
        quality_score=PlacementQualityScore.VERY_POOR,
        metrics=PlacementMetrics(
            impressions=15000,  # High volume
            ctr=0.05,  # Very low CTR
            cost=100.0,  # High cost
            conversions=0.0,  # No conversions
        ),
    )

    spam_score = spam.spam_risk_score
    assert spam_score >= 70.0  # Should be high spam risk


def test_result_helper_methods(analyzer):
    """Test result helper methods."""
    from paidsearchnav.core.models.analysis import (
        Placement,
        PlacementAuditAnalysisResult,
        PlacementCategory,
        PlacementMetrics,
        PlacementQualityScore,
        PlacementType,
    )

    # Create test placements
    placements = [
        Placement(
            placement_id="1",
            placement_name="news.com",
            display_name="News",
            placement_type=PlacementType.WEBSITE,
            category=PlacementCategory.NEWS,
            quality_score=PlacementQualityScore.EXCELLENT,
            metrics=PlacementMetrics(cost=100.0),
            character_set="Latin",
        ),
        Placement(
            placement_id="2",
            placement_name="тест.рф",
            display_name="Russian",
            placement_type=PlacementType.WEBSITE,
            category=PlacementCategory.OTHER,
            quality_score=PlacementQualityScore.POOR,
            metrics=PlacementMetrics(cost=50.0),
            character_set="Cyrillic",
        ),
    ]

    result = PlacementAuditAnalysisResult(
        customer_id="123",
        analysis_type="placement_audit",
        analyzer_name="Test",
        start_date=datetime.now(),
        end_date=datetime.now(),
        all_placements=placements,
        exclusion_recommendations=placements,
    )

    # Test filtering methods
    news_placements = result.get_placements_by_category(PlacementCategory.NEWS)
    assert len(news_placements) == 1
    assert news_placements[0].placement_id == "1"

    excellent_placements = result.get_placements_by_quality(
        PlacementQualityScore.EXCELLENT
    )
    assert len(excellent_placements) == 1
    assert excellent_placements[0].placement_id == "1"

    non_english = result.get_non_english_placements()
    assert len(non_english) == 1
    assert non_english[0].placement_id == "2"

    top_exclusions = result.get_top_exclusion_candidates(limit=1)
    assert len(top_exclusions) == 1
    assert top_exclusions[0].placement_id == "1"  # Higher cost, so first in sorted list


@pytest.mark.asyncio
async def test_analyze_empty_data(analyzer, mock_data_provider):
    """Test analysis with empty placement data."""
    # Setup mock with empty data
    mock_data_provider.get_placement_data = AsyncMock(return_value=[])

    # Run analysis
    result = await analyzer.analyze(
        customer_id="123456789",
        start_date=datetime(2024, 1, 1),
        end_date=datetime(2024, 1, 31),
    )

    # Verify empty result
    assert result.total_placements == 0
    assert len(result.all_placements) == 0
    assert len(result.recommendations) == 0
    assert result.total_placement_cost == 0.0


@pytest.mark.asyncio
async def test_analyze_with_filters(
    analyzer, mock_data_provider, sample_placement_data
):
    """Test analysis with campaign and ad group filters."""
    # Setup mock
    mock_data_provider.get_placement_data = AsyncMock(
        return_value=sample_placement_data
    )

    # Run analysis with filters
    result = await analyzer.analyze(
        customer_id="123456789",
        start_date=datetime(2024, 1, 1),
        end_date=datetime(2024, 1, 31),
        campaigns=["campaign_1", "campaign_2"],
        ad_groups=["adgroup_1"],
    )

    # Verify mock was called with filters
    mock_data_provider.get_placement_data.assert_called_once()
    call_args = mock_data_provider.get_placement_data.call_args
    assert call_args[1]["campaigns"] == ["campaign_1", "campaign_2"]
    assert call_args[1]["ad_groups"] == ["adgroup_1"]


@pytest.mark.asyncio
async def test_analyze_error_handling(analyzer, mock_data_provider):
    """Test error handling in analysis."""
    # Setup mock to raise exception
    mock_data_provider.get_placement_data = AsyncMock(
        side_effect=Exception("API Error")
    )

    # Run analysis
    result = await analyzer.analyze(
        customer_id="123456789",
        start_date=datetime(2024, 1, 1),
        end_date=datetime(2024, 1, 31),
    )

    # Should return empty result gracefully
    assert result.total_placements == 0
    assert len(result.all_placements) == 0
    assert len(result.recommendations) == 0


def test_placement_audit_config():
    """Test placement audit configuration class."""
    from paidsearchnav.analyzers.placement_audit import PlacementAuditConfig

    # Test default configuration
    config = PlacementAuditConfig()
    assert config.CTR_EXCELLENT == 2.0
    assert config.QUALITY_EXCELLENT == 90.0
    assert config.SPAM_VOLUME_SCORE == 30.0

    # Test custom configuration
    custom_config = PlacementAuditConfig(
        CTR_EXCELLENT=3.0,
        QUALITY_EXCELLENT=95.0,
    )
    assert custom_config.CTR_EXCELLENT == 3.0
    assert custom_config.QUALITY_EXCELLENT == 95.0


def test_to_summary_dict():
    """Test summary dictionary generation."""
    from paidsearchnav.core.models.analysis import (
        Placement,
        PlacementAuditAnalysisResult,
        PlacementCategory,
        PlacementMetrics,
        PlacementQualityScore,
        PlacementType,
        Recommendation,
        RecommendationPriority,
        RecommendationType,
    )

    # Create real placement objects instead of mocks
    test_placements = [
        Placement(
            placement_id="1",
            placement_name="test1.com",
            display_name="Test 1",
            placement_type=PlacementType.WEBSITE,
            category=PlacementCategory.OTHER,
            quality_score=PlacementQualityScore.POOR,
            metrics=PlacementMetrics(cost=100.0),
        ),
        Placement(
            placement_id="2",
            placement_name="test2.com",
            display_name="Test 2",
            placement_type=PlacementType.WEBSITE,
            category=PlacementCategory.OTHER,
            quality_score=PlacementQualityScore.FAIR,
            metrics=PlacementMetrics(cost=150.0),
        ),
        Placement(
            placement_id="3",
            placement_name="test3.com",
            display_name="Test 3",
            placement_type=PlacementType.WEBSITE,
            category=PlacementCategory.OTHER,
            quality_score=PlacementQualityScore.GOOD,
            metrics=PlacementMetrics(cost=200.0),
        ),
    ]

    result = PlacementAuditAnalysisResult(
        customer_id="123456789",
        analysis_type="placement_audit",
        analyzer_name="Test Analyzer",
        start_date=datetime(2024, 1, 1),
        end_date=datetime(2024, 1, 31),
        total_placements=100,
        total_placement_cost=1000.0,
        total_placement_conversions=50.0,
        avg_placement_ctr=1.5,
        avg_placement_cpa=20.0,
        wasted_spend_percentage=25.0,
        underperforming_placements=[test_placements[0]],
        high_cost_placements=[test_placements[1], test_placements[2]],
        spam_placements=[test_placements[0]],
        exclusion_recommendations=test_placements,
        potential_cost_savings=250.0,
        quality_distribution={
            PlacementQualityScore.EXCELLENT: 20,
            PlacementQualityScore.GOOD: 30,
            PlacementQualityScore.FAIR: 25,
            PlacementQualityScore.POOR: 15,
            PlacementQualityScore.VERY_POOR: 10,
        },
        recommendations=[
            Recommendation(
                type=RecommendationType.ADD_NEGATIVE,
                priority=RecommendationPriority.CRITICAL,
                title="Critical recommendation",
                description="Test",
            ),
        ],
    )

    summary = result.to_summary_dict()

    # Verify summary structure
    assert summary["account"] == "123456789"
    assert summary["summary"]["total_placements"] == 100
    assert summary["summary"]["total_cost"] == 1000.0
    assert summary["summary"]["wasted_spend_percentage"] == 25.0
    assert summary["issues"]["underperforming_placements"] == 1
    assert summary["issues"]["high_cost_placements"] == 2
    assert summary["issues"]["spam_placements"] == 1
    assert summary["issues"]["exclusion_recommendations"] == 3
    assert summary["potential_impact"]["cost_savings"] == 250.0
    assert summary["potential_impact"]["placements_to_exclude"] == 3
    assert len(summary["top_recommendations"]) == 1
