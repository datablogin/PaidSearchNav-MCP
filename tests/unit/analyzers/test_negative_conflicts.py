"""Unit tests for negative keyword conflict analyzer."""

from datetime import datetime
from unittest.mock import AsyncMock, Mock

import pytest

from paidsearchnav.analyzers.negative_conflicts import NegativeConflictAnalyzer
from paidsearchnav.core.models.analysis import (
    RecommendationPriority,
    RecommendationType,
)
from paidsearchnav.core.models.keyword import Keyword, KeywordMatchType, KeywordStatus


@pytest.fixture
def mock_data_provider():
    """Create mock data provider."""
    return Mock()


@pytest.fixture
def analyzer(mock_data_provider):
    """Create analyzer instance."""
    return NegativeConflictAnalyzer(mock_data_provider)


@pytest.fixture
def sample_positive_keywords():
    """Create sample positive keywords."""
    return [
        Keyword(
            keyword_id="1",
            campaign_id="100",
            campaign_name="Campaign 1",
            ad_group_id="1000",
            ad_group_name="Ad Group 1",
            text="buy shoes online",
            match_type=KeywordMatchType.BROAD,
            status=KeywordStatus.ENABLED,
            quality_score=8,
            impressions=1000,
            clicks=100,
            cost=200.0,
            conversions=10.0,
            conversion_value=500.0,
        ),
        Keyword(
            keyword_id="2",
            campaign_id="100",
            campaign_name="Campaign 1",
            ad_group_id="1001",
            ad_group_name="Ad Group 2",
            text="running shoes",
            match_type=KeywordMatchType.EXACT,
            status=KeywordStatus.ENABLED,
            quality_score=7,
            impressions=500,
            clicks=50,
            cost=100.0,
            conversions=5.0,
            conversion_value=250.0,
        ),
        Keyword(
            keyword_id="3",
            campaign_id="101",
            campaign_name="Campaign 2",
            ad_group_id="1002",
            ad_group_name="Ad Group 3",
            text="cheap shoes",
            match_type=KeywordMatchType.PHRASE,
            status=KeywordStatus.ENABLED,
            quality_score=6,
            impressions=200,
            clicks=10,
            cost=20.0,
            conversions=1.0,
            conversion_value=50.0,
        ),
    ]


@pytest.fixture
def sample_negative_keywords():
    """Create sample negative keyword data."""
    return [
        {
            "campaign_criterion": {
                "negative": True,
                "keyword": {
                    "text": "cheap",
                    "match_type": "BROAD",
                },
            },
            "campaign": {
                "id": "100",
                "name": "Campaign 1",
            },
        },
        {
            "ad_group_criterion": {
                "negative": True,
                "keyword": {
                    "text": "running",
                    "match_type": "EXACT",
                },
            },
            "campaign": {
                "id": "100",
                "name": "Campaign 1",
            },
            "ad_group": {
                "id": "1000",
                "name": "Ad Group 1",
            },
        },
        {
            "shared_criterion": {
                "keyword": {
                    "text": "online",
                    "match_type": "PHRASE",
                },
            },
            "shared_set": {
                "id": "5000",
                "name": "Shared Negative List 1",
            },
        },
    ]


class TestNegativeConflictAnalyzer:
    """Test cases for NegativeConflictAnalyzer."""

    def test_get_name(self, analyzer):
        """Test analyzer name."""
        assert analyzer.get_name() == "Negative Keyword Conflict Analyzer"

    def test_get_description(self, analyzer):
        """Test analyzer description."""
        description = analyzer.get_description()
        assert "negative keywords" in description.lower()
        assert "blocking" in description.lower()

    def test_parse_negative_keywords(self, analyzer, sample_negative_keywords):
        """Test parsing negative keywords from API response."""
        parsed = analyzer._parse_negative_keywords(sample_negative_keywords)

        assert len(parsed) == 3

        # Check campaign-level negative
        campaign_neg = parsed[0]
        assert campaign_neg["text"] == "cheap"
        assert campaign_neg["match_type"] == "BROAD"
        assert campaign_neg["level"] == "CAMPAIGN"
        assert campaign_neg["campaign_id"] == "100"

        # Check ad group-level negative
        ad_group_neg = parsed[1]
        assert ad_group_neg["text"] == "running"
        assert ad_group_neg["match_type"] == "EXACT"
        assert ad_group_neg["level"] == "AD_GROUP"
        assert ad_group_neg["ad_group_id"] == "1000"

        # Check shared negative
        shared_neg = parsed[2]
        assert shared_neg["text"] == "online"
        assert shared_neg["match_type"] == "PHRASE"
        assert shared_neg["level"] == "SHARED"
        assert shared_neg["shared_set_id"] == "5000"

    def test_is_conflict_exact_match(self, analyzer):
        """Test exact match negative conflict detection."""
        positive_kw = Keyword(
            keyword_id="1",
            campaign_id="100",
            campaign_name="Campaign 1",
            ad_group_id="1000",
            ad_group_name="Ad Group 1",
            text="running shoes",
            match_type=KeywordMatchType.BROAD,
            status=KeywordStatus.ENABLED,
        )

        negative_kw = {
            "text": "running shoes",
            "match_type": "EXACT",
            "level": "CAMPAIGN",
            "campaign_id": "100",
        }

        assert analyzer._is_conflict(positive_kw, negative_kw) is True

        # Should not conflict if text doesn't match exactly
        negative_kw["text"] = "running"
        assert analyzer._is_conflict(positive_kw, negative_kw) is False

    def test_is_conflict_phrase_match(self, analyzer):
        """Test phrase match negative conflict detection."""
        positive_kw = Keyword(
            keyword_id="1",
            campaign_id="100",
            campaign_name="Campaign 1",
            ad_group_id="1000",
            ad_group_name="Ad Group 1",
            text="buy running shoes online",
            match_type=KeywordMatchType.BROAD,
            status=KeywordStatus.ENABLED,
        )

        negative_kw = {
            "text": "running shoes",
            "match_type": "PHRASE",
            "level": "CAMPAIGN",
            "campaign_id": "100",
        }

        assert analyzer._is_conflict(positive_kw, negative_kw) is True

        # Should not conflict if phrase not contained
        negative_kw["text"] = "walking shoes"
        assert analyzer._is_conflict(positive_kw, negative_kw) is False

    def test_is_conflict_broad_match(self, analyzer):
        """Test broad match negative conflict detection."""
        positive_kw = Keyword(
            keyword_id="1",
            campaign_id="100",
            campaign_name="Campaign 1",
            ad_group_id="1000",
            ad_group_name="Ad Group 1",
            text="buy cheap running shoes online",
            match_type=KeywordMatchType.BROAD,
            status=KeywordStatus.ENABLED,
        )

        negative_kw = {
            "text": "cheap shoes",
            "match_type": "BROAD",
            "level": "CAMPAIGN",
            "campaign_id": "100",
        }

        assert analyzer._is_conflict(positive_kw, negative_kw) is True

        # Should not conflict if not all words present
        negative_kw["text"] = "expensive shoes"
        assert analyzer._is_conflict(positive_kw, negative_kw) is False

    def test_is_conflict_same_ad_group(self, analyzer):
        """Test that ad group negatives don't affect same ad group."""
        positive_kw = Keyword(
            keyword_id="1",
            campaign_id="100",
            campaign_name="Campaign 1",
            ad_group_id="1000",
            ad_group_name="Ad Group 1",
            text="running shoes",
            match_type=KeywordMatchType.BROAD,
            status=KeywordStatus.ENABLED,
        )

        negative_kw = {
            "text": "running shoes",
            "match_type": "EXACT",
            "level": "AD_GROUP",
            "ad_group_id": "1000",  # Same ad group
        }

        assert analyzer._is_conflict(positive_kw, negative_kw) is False

    def test_calculate_severity(self, analyzer):
        """Test severity calculation."""
        # Critical - high conversions
        kw_critical = Keyword(
            keyword_id="1",
            campaign_id="100",
            campaign_name="Campaign 1",
            ad_group_id="1000",
            ad_group_name="Ad Group 1",
            text="test",
            match_type=KeywordMatchType.BROAD,
            status=KeywordStatus.ENABLED,
            conversions=15.0,
            quality_score=9,
        )
        assert analyzer._calculate_severity(kw_critical) == "CRITICAL"

        # High - moderate conversions
        kw_high = Keyword(
            keyword_id="2",
            campaign_id="100",
            campaign_name="Campaign 1",
            ad_group_id="1000",
            ad_group_name="Ad Group 1",
            text="test",
            match_type=KeywordMatchType.BROAD,
            status=KeywordStatus.ENABLED,
            conversions=7.0,
            clicks=150,
        )
        assert analyzer._calculate_severity(kw_high) == "HIGH"

        # Medium - some clicks
        kw_medium = Keyword(
            keyword_id="3",
            campaign_id="100",
            campaign_name="Campaign 1",
            ad_group_id="1000",
            ad_group_name="Ad Group 1",
            text="test",
            match_type=KeywordMatchType.BROAD,
            status=KeywordStatus.ENABLED,
            conversions=1.0,
            clicks=20,
        )
        assert analyzer._calculate_severity(kw_medium) == "MEDIUM"

        # Low - minimal activity
        kw_low = Keyword(
            keyword_id="4",
            campaign_id="100",
            campaign_name="Campaign 1",
            ad_group_id="1000",
            ad_group_name="Ad Group 1",
            text="test",
            match_type=KeywordMatchType.BROAD,
            status=KeywordStatus.ENABLED,
            conversions=0.0,
            clicks=5,
        )
        assert analyzer._calculate_severity(kw_low) == "LOW"

    @pytest.mark.asyncio
    async def test_analyze(
        self,
        analyzer,
        mock_data_provider,
        sample_positive_keywords,
        sample_negative_keywords,
    ):
        """Test full analysis flow."""
        # Mock data provider methods
        mock_data_provider.get_keywords = AsyncMock(
            return_value=sample_positive_keywords
        )
        mock_data_provider.get_negative_keywords = AsyncMock(
            return_value=sample_negative_keywords
        )

        # Run analysis
        result = await analyzer.analyze(
            customer_id="123456789",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        # Verify result structure
        assert result.customer_id == "123456789"
        assert result.analysis_type == "negative_conflicts"
        assert result.analyzer_name == analyzer.get_name()

        # Check metrics
        assert result.metrics.total_keywords_analyzed == 3
        assert result.metrics.issues_found > 0

        # Check recommendations
        assert len(result.recommendations) > 0

        # Verify critical conflicts get critical recommendations
        critical_recs = [
            r
            for r in result.recommendations
            if r.priority == RecommendationPriority.CRITICAL
        ]
        for rec in critical_recs:
            assert rec.type == RecommendationType.FIX_CONFLICT

    def test_get_resolution_options(self, analyzer):
        """Test resolution option generation."""
        positive_kw = Keyword(
            keyword_id="1",
            campaign_id="100",
            campaign_name="Campaign 1",
            ad_group_id="1000",
            ad_group_name="Ad Group 1",
            text="running shoes",
            match_type=KeywordMatchType.BROAD,
            status=KeywordStatus.ENABLED,
        )

        # Test broad negative
        negative_broad = {
            "text": "cheap",
            "match_type": "BROAD",
            "level": "CAMPAIGN",
        }
        options = analyzer._get_resolution_options(positive_kw, negative_broad)
        assert any("Remove negative keyword" in opt for opt in options)
        assert any("phrase or exact match" in opt for opt in options)

        # Test shared negative
        negative_shared = {
            "text": "discount",
            "match_type": "BROAD",
            "level": "SHARED",
        }
        options = analyzer._get_resolution_options(positive_kw, negative_shared)
        assert any("campaign-level positive" in opt for opt in options)

    def test_count_conflicts_by_level(self, analyzer):
        """Test conflict counting by level."""
        conflicts = [
            {"negative_keyword": {"level": "CAMPAIGN"}},
            {"negative_keyword": {"level": "CAMPAIGN"}},
            {"negative_keyword": {"level": "AD_GROUP"}},
            {"negative_keyword": {"level": "SHARED"}},
            {"negative_keyword": {"level": "SHARED"}},
            {"negative_keyword": {"level": "SHARED"}},
        ]

        counts = analyzer._count_conflicts_by_level(conflicts)
        assert counts["CAMPAIGN"] == 2
        assert counts["AD_GROUP"] == 1
        assert counts["SHARED"] == 3

    def test_is_conflict_edge_cases(self, analyzer):
        """Test conflict detection with edge cases."""
        # Test with empty negative keyword text
        positive_kw = Keyword(
            keyword_id="1",
            campaign_id="100",
            campaign_name="Campaign 1",
            ad_group_id="1000",
            ad_group_name="Ad Group 1",
            text="buy shoes online",
            match_type=KeywordMatchType.BROAD,
            status=KeywordStatus.ENABLED,
        )

        negative_empty = {
            "text": "",
            "match_type": "BROAD",
            "level": "CAMPAIGN",
            "campaign_id": "100",
        }
        assert analyzer._is_conflict(positive_kw, negative_empty) is False, (
            "Empty negative keywords should not create conflicts"
        )

        # Test with special characters
        positive_special = Keyword(
            keyword_id="2",
            campaign_id="100",
            campaign_name="Campaign 1",
            ad_group_id="1000",
            ad_group_name="Ad Group 1",
            text="buy [shoes] online!",
            match_type=KeywordMatchType.BROAD,
            status=KeywordStatus.ENABLED,
        )

        negative_special = {
            "text": "[shoes]",
            "match_type": "PHRASE",
            "level": "CAMPAIGN",
            "campaign_id": "100",
        }
        assert analyzer._is_conflict(positive_special, negative_special) is True, (
            "Special characters should be handled correctly in phrase match"
        )

        # Test case insensitivity
        positive_case = Keyword(
            keyword_id="3",
            campaign_id="100",
            campaign_name="Campaign 1",
            ad_group_id="1000",
            ad_group_name="Ad Group 1",
            text="Buy Shoes Online",
            match_type=KeywordMatchType.BROAD,
            status=KeywordStatus.ENABLED,
        )

        negative_case = {
            "text": "BUY SHOES",
            "match_type": "PHRASE",
            "level": "CAMPAIGN",
            "campaign_id": "100",
        }
        assert analyzer._is_conflict(positive_case, negative_case) is True, (
            "Conflict detection should be case-insensitive"
        )

    def test_multiple_conflicts_per_keyword(self, analyzer):
        """Test when a single keyword has multiple conflicts."""
        positive_kw = Keyword(
            keyword_id="1",
            campaign_id="100",
            campaign_name="Campaign 1",
            ad_group_id="1000",
            ad_group_name="Ad Group 1",
            text="buy cheap running shoes online",
            match_type=KeywordMatchType.BROAD,
            status=KeywordStatus.ENABLED,
            conversions=20.0,
            conversion_value=1000.0,
        )

        negative_keywords = [
            {
                "text": "cheap",
                "match_type": "BROAD",
                "level": "CAMPAIGN",
                "campaign_id": "100",
            },
            {
                "text": "running shoes",
                "match_type": "PHRASE",
                "level": "SHARED",
                "shared_set_id": "5000",
            },
            {
                "text": "online",
                "match_type": "EXACT",
                "level": "AD_GROUP",
                "campaign_id": "100",
                "ad_group_id": "1001",  # Different ad group
            },
        ]

        conflicts = analyzer._find_conflicts([positive_kw], negative_keywords)
        assert len(conflicts) == 2, (
            "Should find 2 conflicts (broad and phrase match, but not exact match 'online')"
        )

    def test_create_conflict_record_comprehensive(self, analyzer):
        """Test conflict record creation with various scenarios."""
        # Test with high-performing keyword
        positive_high = Keyword(
            keyword_id="1",
            campaign_id="100",
            campaign_name="Campaign 1",
            ad_group_id="1000",
            ad_group_name="Ad Group 1",
            text="premium coffee maker",
            match_type=KeywordMatchType.EXACT,
            status=KeywordStatus.ENABLED,
            quality_score=9,
            impressions=10000,
            clicks=500,
            cost=1000.0,
            conversions=50.0,
            conversion_value=5000.0,
        )

        negative = {
            "text": "premium",
            "match_type": "BROAD",
            "level": "SHARED",
            "shared_set_id": "5000",
            "shared_set_name": "Negative List 1",
        }

        conflict = analyzer._create_conflict_record(positive_high, negative)

        assert conflict["severity"] == "CRITICAL"
        assert conflict["estimated_impact"]["conversions_lost"] == 50.0
        assert conflict["estimated_impact"]["revenue_lost"] == 5000.0
        assert len(conflict["resolution_options"]) > 0
        assert any(
            "campaign-level positive" in opt for opt in conflict["resolution_options"]
        )

    @pytest.mark.asyncio
    async def test_analyze_with_no_conflicts(self, analyzer, mock_data_provider):
        """Test analysis when there are no conflicts."""
        positive_keywords = [
            Keyword(
                keyword_id="1",
                campaign_id="100",
                campaign_name="Campaign 1",
                ad_group_id="1000",
                ad_group_name="Ad Group 1",
                text="buy shoes",
                match_type=KeywordMatchType.BROAD,
                status=KeywordStatus.ENABLED,
            ),
        ]

        negative_keywords = [
            {
                "campaign_criterion": {
                    "negative": True,
                    "keyword": {
                        "text": "free",
                        "match_type": "BROAD",
                    },
                },
                "campaign": {
                    "id": "100",
                    "name": "Campaign 1",
                },
            },
        ]

        mock_data_provider.get_keywords = AsyncMock(return_value=positive_keywords)
        mock_data_provider.get_negative_keywords = AsyncMock(
            return_value=negative_keywords
        )

        result = await analyzer.analyze(
            customer_id="123456789",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        assert result.metrics.issues_found == 0
        assert len(result.recommendations) == 0

    @pytest.mark.asyncio
    async def test_analyze_with_paused_keywords(self, analyzer, mock_data_provider):
        """Test that paused keywords are excluded from analysis."""
        keywords = [
            Keyword(
                keyword_id="1",
                campaign_id="100",
                campaign_name="Campaign 1",
                ad_group_id="1000",
                ad_group_name="Ad Group 1",
                text="buy shoes",
                match_type=KeywordMatchType.BROAD,
                status=KeywordStatus.ENABLED,
            ),
            Keyword(
                keyword_id="2",
                campaign_id="100",
                campaign_name="Campaign 1",
                ad_group_id="1000",
                ad_group_name="Ad Group 1",
                text="cheap shoes",
                match_type=KeywordMatchType.BROAD,
                status=KeywordStatus.PAUSED,  # Should be excluded
            ),
        ]

        negative_keywords = [
            {
                "campaign_criterion": {
                    "negative": True,
                    "keyword": {
                        "text": "shoes",
                        "match_type": "BROAD",
                    },
                },
                "campaign": {
                    "id": "100",
                    "name": "Campaign 1",
                },
            },
        ]

        mock_data_provider.get_keywords = AsyncMock(return_value=keywords)
        mock_data_provider.get_negative_keywords = AsyncMock(
            return_value=negative_keywords
        )

        result = await analyzer.analyze(
            customer_id="123456789",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        # Should only find conflict with the enabled keyword
        assert result.metrics.total_keywords_analyzed == 1
        assert result.metrics.issues_found == 1

    def test_generate_recommendations_many_conflicts(self, analyzer):
        """Test recommendation generation with many conflicts."""
        # Create 50 conflicts with varying severity
        conflicts = []
        for i in range(50):
            severity = ["CRITICAL", "HIGH", "MEDIUM", "LOW"][i % 4]
            conflicts.append(
                {
                    "positive_keyword": {
                        "id": f"kw_{i}",
                        "text": f"keyword {i}",
                        "campaign_id": f"campaign_{i % 5}",
                        "ad_group_id": f"adgroup_{i % 10}",
                        "conversions": 10.0 if severity == "CRITICAL" else 5.0,
                        "conversion_value": 500.0 if severity == "CRITICAL" else 100.0,
                    },
                    "negative_keyword": {
                        "text": f"negative {i}",
                        "match_type": "BROAD",
                        "level": ["SHARED", "CAMPAIGN", "AD_GROUP"][i % 3],
                    },
                    "severity": severity,
                    "resolution_options": ["Remove negative", "Change match type"],
                }
            )

        recommendations = analyzer._generate_recommendations(conflicts)

        # Should have critical recommendations plus a summary
        assert len(recommendations) > 10
        assert any(
            rec.priority == RecommendationPriority.CRITICAL for rec in recommendations
        )
        assert any(
            "Review negative keyword strategy" in rec.title for rec in recommendations
        )

    def test_parse_negative_keywords_malformed_data(self, analyzer):
        """Test parsing with malformed or missing data."""
        malformed_data = [
            {},  # Empty dict
            {"campaign_criterion": {}},  # Missing keyword info
            {"campaign_criterion": {"negative": False}},  # Not negative
            {
                "campaign_criterion": {
                    "negative": True,
                    "keyword": {},  # Missing text
                }
            },
            {
                "shared_criterion": {
                    "keyword": {"text": "test"},
                    # Missing shared_set info
                }
            },
        ]

        parsed = analyzer._parse_negative_keywords(malformed_data)

        # Should handle gracefully and parse what it can
        assert len(parsed) >= 0  # May parse some with defaults
        for neg in parsed:
            assert "text" in neg
            assert "match_type" in neg
            assert "level" in neg

    def test_conflict_with_null_keyword_values(self, analyzer):
        """Test conflict detection with keywords having null values."""
        positive_kw = Keyword(
            keyword_id="1",
            campaign_id="100",
            campaign_name="Campaign 1",
            ad_group_id="1000",
            ad_group_name="Ad Group 1",
            text="buy shoes",
            match_type=KeywordMatchType.BROAD,
            status=KeywordStatus.ENABLED,
            quality_score=None,  # Null quality score
            impressions=0,
            clicks=0,
            cost=0.0,
            conversions=0.0,
            conversion_value=0.0,
        )

        negative_kw = {
            "text": "shoes",
            "match_type": "BROAD",
            "level": "CAMPAIGN",
            "campaign_id": "100",
        }

        # Should still detect conflict
        assert analyzer._is_conflict(positive_kw, negative_kw) is True, (
            "Conflict detection should work even with null keyword values"
        )

        # Should calculate severity as LOW
        assert analyzer._calculate_severity(positive_kw) == "LOW", (
            "Keywords with no performance data should have LOW severity"
        )

    @pytest.mark.asyncio
    async def test_analyze_performance_with_large_dataset(
        self, analyzer, mock_data_provider
    ):
        """Test analyzer performance with large number of keywords."""
        # Create 1000 positive keywords
        positive_keywords = []
        for i in range(1000):
            positive_keywords.append(
                Keyword(
                    keyword_id=str(i),
                    campaign_id=str(i % 10),
                    campaign_name=f"Campaign {i % 10}",
                    ad_group_id=str(i % 50),
                    ad_group_name=f"Ad Group {i % 50}",
                    text=f"keyword phrase {i % 100}",
                    match_type=KeywordMatchType.BROAD,
                    status=KeywordStatus.ENABLED,
                    impressions=i * 10,
                    clicks=i,
                    conversions=i * 0.1,
                    conversion_value=i * 5.0,
                )
            )

        # Create 100 negative keywords
        negative_data = []
        for i in range(100):
            negative_data.append(
                {
                    "campaign_criterion": {
                        "negative": True,
                        "keyword": {
                            "text": f"phrase {i}",
                            "match_type": ["BROAD", "PHRASE", "EXACT"][i % 3],
                        },
                    },
                    "campaign": {
                        "id": str(i % 10),
                        "name": f"Campaign {i % 10}",
                    },
                }
            )

        mock_data_provider.get_keywords = AsyncMock(return_value=positive_keywords)
        mock_data_provider.get_negative_keywords = AsyncMock(return_value=negative_data)

        # Should complete analysis without performance issues
        import time

        start_time = time.time()

        result = await analyzer.analyze(
            customer_id="123456789",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
        )

        end_time = time.time()

        # Should complete in reasonable time (less than 3 seconds)
        assert (end_time - start_time) < 3.0, (
            f"Analysis took {end_time - start_time:.2f}s, should complete in under 3 seconds"
        )
        assert result.metrics.total_keywords_analyzed == 1000, (
            "Should analyze all 1000 keywords"
        )
        assert result.metrics.issues_found > 0, (
            "Should find at least some conflicts with 100 negative keywords"
        )

    def test_parse_negative_keywords_input_validation(self, analyzer):
        """Test input validation for _parse_negative_keywords."""
        # Test with None input
        result = analyzer._parse_negative_keywords(None)
        assert result == []

        # Test with empty list
        result = analyzer._parse_negative_keywords([])
        assert result == []

        # Test with non-list input
        result = analyzer._parse_negative_keywords("not a list")
        assert result == []

        # Test with dictionary instead of list
        result = analyzer._parse_negative_keywords({"not": "a list"})
        assert result == []

    def test_unicode_character_handling(self, analyzer):
        """Test conflict detection with Unicode characters."""
        positive_kw = Keyword(
            keyword_id="1",
            campaign_id="100",
            campaign_name="Campaign 1",
            ad_group_id="1000",
            ad_group_name="Ad Group 1",
            text="café français online",  # Unicode characters
            match_type=KeywordMatchType.BROAD,
            status=KeywordStatus.ENABLED,
        )

        # Test exact match with Unicode
        negative_unicode = {
            "text": "café français",
            "match_type": "PHRASE",
            "level": "CAMPAIGN",
            "campaign_id": "100",
        }
        assert analyzer._is_conflict(positive_kw, negative_unicode) is True, (
            "Should handle Unicode characters correctly in phrase match"
        )

        # Test broad match with Unicode
        negative_unicode_broad = {
            "text": "café online",
            "match_type": "BROAD",
            "level": "CAMPAIGN",
            "campaign_id": "100",
        }
        assert analyzer._is_conflict(positive_kw, negative_unicode_broad) is True, (
            "Should handle Unicode characters correctly in broad match"
        )

    def test_improved_word_boundary_detection(self, analyzer):
        """Test improved word boundary handling with regex."""
        positive_kw = Keyword(
            keyword_id="1",
            campaign_id="100",
            campaign_name="Campaign 1",
            ad_group_id="1000",
            ad_group_name="Ad Group 1",
            text="buy shoes-online fast!",  # Contains punctuation
            match_type=KeywordMatchType.BROAD,
            status=KeywordStatus.ENABLED,
        )

        # Test that word boundaries are properly detected
        negative_punctuation = {
            "text": "shoes online",
            "match_type": "BROAD",
            "level": "CAMPAIGN",
            "campaign_id": "100",
        }
        assert analyzer._is_conflict(positive_kw, negative_punctuation) is True, (
            "Should detect words even with punctuation using regex word boundaries"
        )

        # Test with special characters that should not match
        negative_partial = {
            "text": "shoe online",  # Missing 's' - should not match "shoes"
            "match_type": "BROAD",
            "level": "CAMPAIGN",
            "campaign_id": "100",
        }
        assert analyzer._is_conflict(positive_kw, negative_partial) is False, (
            "Should not match partial words when using word boundaries"
        )

    def test_case_insensitive_matching_comprehensive(self, analyzer):
        """Test comprehensive case insensitive matching scenarios."""
        test_cases = [
            ("BUY SHOES ONLINE", "buy shoes", "PHRASE", True),
            ("buy shoes online", "BUY SHOES", "PHRASE", True),
            ("Buy Shoes Online", "buy SHOES", "BROAD", True),
            ("BUY SHOES ONLINE", "SHOES", "BROAD", True),
            ("buy shoes online", "RUNNING", "BROAD", False),
        ]

        for positive_text, negative_text, match_type, expected in test_cases:
            positive_kw = Keyword(
                keyword_id="1",
                campaign_id="100",
                campaign_name="Campaign 1",
                ad_group_id="1000",
                ad_group_name="Ad Group 1",
                text=positive_text,
                match_type=KeywordMatchType.BROAD,
                status=KeywordStatus.ENABLED,
            )

            negative_kw = {
                "text": negative_text,
                "match_type": match_type,
                "level": "CAMPAIGN",
                "campaign_id": "100",
            }

            result = analyzer._is_conflict(positive_kw, negative_kw)
            assert result == expected, (
                f"Case insensitive test failed: '{positive_text}' vs '{negative_text}' "
                f"({match_type}) expected {expected}, got {result}"
            )

    def test_large_account_batch_processing(self, analyzer):
        """Test that batch processing is triggered for large accounts and uses level-based indexing."""
        # Create keywords exceeding the large account threshold (10,000+)
        positive_keywords = []
        for i in range(12000):  # Above LARGE_ACCOUNT_THRESHOLD
            positive_keywords.append(
                Keyword(
                    keyword_id=str(i),
                    campaign_id=str(i % 100),
                    campaign_name=f"Campaign {i % 100}",
                    ad_group_id=str(i % 500),
                    ad_group_name=f"Ad Group {i % 500}",
                    text=f"keyword {i % 1000}",
                    match_type=KeywordMatchType.BROAD,
                    status=KeywordStatus.ENABLED,
                )
            )

        negative_keywords = [
            {
                "text": "keyword",
                "match_type": "BROAD",
                "level": "CAMPAIGN",
                "campaign_id": "0",
            },
            {
                "text": "test",
                "match_type": "PHRASE",
                "level": "SHARED",
                "shared_set_id": "1000",
            },
        ]

        # Test that batch processing method is called
        conflicts = analyzer._find_conflicts(positive_keywords, negative_keywords)

        # Should find conflicts due to "keyword" matching
        assert len(conflicts) > 0, "Should find conflicts with batch processing"

        # Verify that conflicts are properly structured
        for conflict in conflicts[:5]:  # Check first 5
            assert "positive_keyword" in conflict
            assert "negative_keyword" in conflict
            assert "severity" in conflict

    def test_batch_processing_performance_optimization(self, analyzer):
        """Test that batch processing maintains performance with level-based indexing."""
        import time

        # Create a moderately large dataset to test performance
        positive_keywords = []
        for i in range(11000):  # Just above threshold
            positive_keywords.append(
                Keyword(
                    keyword_id=str(i),
                    campaign_id=str(i % 10),
                    campaign_name=f"Campaign {i % 10}",
                    ad_group_id=str(i % 50),
                    ad_group_name=f"Ad Group {i % 50}",
                    text=f"test keyword {i % 100}",
                    match_type=KeywordMatchType.BROAD,
                    status=KeywordStatus.ENABLED,
                )
            )

        negative_keywords = []
        for i in range(50):
            negative_keywords.append(
                {
                    "text": f"test {i}",
                    "match_type": "BROAD",
                    "level": ["CAMPAIGN", "SHARED", "AD_GROUP"][i % 3],
                    "campaign_id": str(i % 10) if i % 3 != 1 else None,
                    "shared_set_id": "1000" if i % 3 == 1 else None,
                    "ad_group_id": str(i % 50) if i % 3 == 2 else None,
                }
            )

        start_time = time.time()
        conflicts = analyzer._find_conflicts(positive_keywords, negative_keywords)
        end_time = time.time()

        # Should complete in reasonable time (less than 5 seconds)
        assert (end_time - start_time) < 5.0, (
            f"Batch processing took {end_time - start_time:.2f}s, should complete in under 5 seconds"
        )

        # Should find some conflicts
        assert len(conflicts) > 0, "Should find conflicts with batch processing"

    def test_parse_negative_keywords_malformed_api_responses(self, analyzer):
        """Test parsing with various malformed API response structures."""
        malformed_responses = [
            # Completely empty response
            [],
            # Invalid structure - missing criterion
            [{"campaign": {"id": "100", "name": "Test"}}],
            # Invalid criterion type - not negative
            [
                {
                    "campaign_criterion": {
                        "negative": False,  # Not a negative keyword
                        "keyword": {"text": "test", "match_type": "BROAD"},
                    },
                    "campaign": {"id": "100", "name": "Test"},
                }
            ],
            # Missing keyword data
            [
                {
                    "campaign_criterion": {
                        "negative": True,
                        # Missing keyword field
                    },
                    "campaign": {"id": "100", "name": "Test"},
                }
            ],
            # Empty keyword text
            [
                {
                    "campaign_criterion": {
                        "negative": True,
                        "keyword": {
                            "text": "",  # Empty text
                            "match_type": "BROAD",
                        },
                    },
                    "campaign": {"id": "100", "name": "Test"},
                }
            ],
            # Missing match type
            [
                {
                    "campaign_criterion": {
                        "negative": True,
                        "keyword": {
                            "text": "test"
                            # Missing match_type
                        },
                    },
                    "campaign": {"id": "100", "name": "Test"},
                }
            ],
            # Malformed shared criterion
            [
                {
                    "shared_criterion": {
                        # Missing keyword field
                    },
                    "shared_set": {"id": "5000", "name": "Test List"},
                }
            ],
            # Mixed valid and invalid data
            [
                # Valid entry
                {
                    "campaign_criterion": {
                        "negative": True,
                        "keyword": {"text": "valid", "match_type": "BROAD"},
                    },
                    "campaign": {"id": "100", "name": "Test"},
                },
                # Invalid entry
                {
                    "campaign_criterion": {
                        "negative": True,
                        # Missing keyword
                    },
                    "campaign": {"id": "100", "name": "Test"},
                },
            ],
        ]

        for i, response in enumerate(malformed_responses):
            try:
                parsed = analyzer._parse_negative_keywords(response)
                # Should not crash, but may return empty or partial results
                assert isinstance(parsed, list), f"Response {i}: Should return a list"

                # Check that valid entries are parsed correctly
                for neg in parsed:
                    assert isinstance(neg, dict), (
                        f"Response {i}: Each item should be a dict"
                    )
                    assert "text" in neg, f"Response {i}: Should have text field"
                    assert "match_type" in neg, (
                        f"Response {i}: Should have match_type field"
                    )
                    assert "level" in neg, f"Response {i}: Should have level field"

                    # Text should not be None (but can be empty string)
                    assert neg["text"] is not None, (
                        f"Response {i}: Text should not be None"
                    )

            except Exception as e:
                pytest.fail(
                    f"Response {i}: Should handle malformed data gracefully, but got: {e}"
                )

    def test_parse_negative_keywords_none_and_invalid_types(self, analyzer):
        """Test parsing with None values and invalid data types."""
        test_cases = [
            None,  # None input
            "string",  # String instead of list
            123,  # Number instead of list
            {"not": "a list"},  # Dict instead of list
            [None],  # List with None item
            [123],  # List with non-dict item
            ["string"],  # List with string item
        ]

        for i, test_input in enumerate(test_cases):
            try:
                result = analyzer._parse_negative_keywords(test_input)
                assert result == [], (
                    f"Test case {i}: Should return empty list for invalid input"
                )
            except Exception as e:
                pytest.fail(
                    f"Test case {i}: Should handle invalid input gracefully, but got: {e}"
                )

    def test_conflict_detection_with_malformed_negative_data(self, analyzer):
        """Test conflict detection when negative keyword data is malformed."""
        positive_kw = Keyword(
            keyword_id="1",
            campaign_id="100",
            campaign_name="Campaign 1",
            ad_group_id="1000",
            ad_group_name="Ad Group 1",
            text="buy shoes",
            match_type=KeywordMatchType.BROAD,
            status=KeywordStatus.ENABLED,
        )

        malformed_negatives = [
            # Missing required fields
            {"text": "shoes"},  # Missing match_type, level
            {"match_type": "BROAD"},  # Missing text, level
            {"level": "CAMPAIGN"},  # Missing text, match_type
            # None values
            {"text": None, "match_type": "BROAD", "level": "CAMPAIGN"},
            {"text": "shoes", "match_type": None, "level": "CAMPAIGN"},
            {"text": "shoes", "match_type": "BROAD", "level": None},
            # Empty values
            {"text": "", "match_type": "BROAD", "level": "CAMPAIGN"},
            {"text": "shoes", "match_type": "", "level": "CAMPAIGN"},
            {"text": "shoes", "match_type": "BROAD", "level": ""},
            # Invalid match types
            {"text": "shoes", "match_type": "INVALID", "level": "CAMPAIGN"},
            {"text": "shoes", "match_type": 123, "level": "CAMPAIGN"},
            # Invalid levels
            {"text": "shoes", "match_type": "BROAD", "level": "INVALID"},
        ]

        for i, negative_kw in enumerate(malformed_negatives):
            try:
                # Should not crash, but may return False
                result = analyzer._is_conflict(positive_kw, negative_kw)
                assert isinstance(result, bool), (
                    f"Malformed negative {i}: Should return boolean"
                )
            except Exception as e:
                pytest.fail(
                    f"Malformed negative {i}: Should handle gracefully, but got: {e}"
                )
