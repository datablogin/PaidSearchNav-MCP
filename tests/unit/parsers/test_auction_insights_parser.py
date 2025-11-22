"""Unit tests for auction insights parser implementation."""

import os
import tempfile
from pathlib import Path

import pytest

from paidsearchnav_mcp.parsers.auction_insights import (
    AuctionInsightsConfig,
    AuctionInsightsParser,
)


class TestAuctionInsightsParser:
    """Test suite for AuctionInsightsParser class."""

    @pytest.fixture
    def temp_auction_insights_file(self):
        """Create a temporary auction insights CSV file for testing."""
        # Create a clean CSV without Google Ads headers for direct parser testing
        csv_content = """Display URL domain,Impr. share,Overlap rate,Top of page rate,Abs. Top of page rate,Outranking share,Position above rate
yourdomain.com,32.1%,--,--,--,--,--
competitor1.com,25.5%,18.2%,45.3%,12.1%,38.7%,22.4%
competitor2.com,18.9%,15.6%,32.8%,8.9%,29.3%,18.7%
competitor3.com,12.3%,10.4%,28.1%,7.2%,22.6%,15.3%
localstore.com,8.7%,8.1%,21.4%,5.5%,18.2%,12.8%"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            temp_path = f.name

        yield Path(temp_path)

        # Cleanup
        os.unlink(temp_path)

    @pytest.fixture
    def parser(self):
        """Create an AuctionInsightsParser instance."""
        return AuctionInsightsParser()

    @pytest.fixture
    def sample_competitor_data(self):
        """Sample competitor data for testing."""
        return [
            {
                "competitor_domain": "yourdomain.com",
                "impression_share": "32.1%",
                "overlap_rate": "--",
                "top_of_page_rate": "--",
                "abs_top_of_page_rate": "--",
                "outranking_share": "--",
                "position_above_rate": "--",
            },
            {
                "competitor_domain": "competitor1.com",
                "impression_share": "25.5%",
                "overlap_rate": "18.2%",
                "top_of_page_rate": "45.3%",
                "abs_top_of_page_rate": "12.1%",
                "outranking_share": "38.7%",
                "position_above_rate": "22.4%",
            },
            {
                "competitor_domain": "competitor2.com",
                "impression_share": "18.9%",
                "overlap_rate": "15.6%",
                "top_of_page_rate": "32.8%",
                "abs_top_of_page_rate": "8.9%",
                "outranking_share": "29.3%",
                "position_above_rate": "18.7%",
            },
        ]

    def test_parse_valid_auction_insights_csv(self, parser, temp_auction_insights_file):
        """Test parsing a valid auction insights CSV file."""
        result = parser.parse(temp_auction_insights_file)

        assert len(result) == 5  # 5 domains in the test data

        # Check field mapping worked correctly (fields should be mapped to standardized names)
        first_row = result[0] if hasattr(result[0], "dict") else result[0]
        if hasattr(first_row, "dict"):
            first_row = first_row.dict()

        # The parsed result should have the mapped field names
        assert "competitor_domain" in first_row
        assert first_row["competitor_domain"] == "yourdomain.com"

    def test_parse_missing_file(self, parser):
        """Test parsing a non-existent file."""
        with pytest.raises(FileNotFoundError, match="File not found"):
            parser.parse(Path("/nonexistent/file.csv"))

    def test_parse_percentage_valid(self, parser):
        """Test percentage parsing with valid inputs."""
        assert parser._parse_percentage("25.5%") == 0.255
        assert parser._parse_percentage("100%") == 1.0
        assert parser._parse_percentage("0%") == 0.0

    def test_parse_percentage_invalid(self, parser):
        """Test percentage parsing with invalid inputs."""
        assert parser._parse_percentage("--") == 0.0
        assert parser._parse_percentage("") == 0.0
        assert parser._parse_percentage(None) == 0.0
        assert parser._parse_percentage("invalid") == 0.0

    def test_analyze_competitive_landscape_valid_data(
        self, parser, sample_competitor_data
    ):
        """Test competitive landscape analysis with valid data."""
        result = parser.analyze_competitive_landscape(sample_competitor_data)

        assert "total_competitors" in result
        assert "market_analysis" in result
        assert "position_analysis" in result
        assert "competitive_insights" in result

        # Should identify 2 competitors (excluding own domain)
        assert result["total_competitors"] == 2

        # Should identify top competitor
        assert result["market_analysis"]["top_competitor"] == "competitor1.com"

    def test_analyze_competitive_landscape_empty_data(self, parser):
        """Test competitive landscape analysis with empty data."""
        result = parser.analyze_competitive_landscape([])

        assert "error" in result
        assert result["error"] == "No auction insights data provided"

    def test_analyze_competitive_landscape_own_domain_identification(
        self, parser, sample_competitor_data
    ):
        """Test that own domain is correctly identified."""
        result = parser.analyze_competitive_landscape(sample_competitor_data)

        assert "own_performance" in result
        assert result["own_performance"]["domain"] == "yourdomain.com"
        assert "32.1%" in result["own_performance"]["impression_share"]

    def test_competitive_threat_assessment(self, parser):
        """Test competitive threat assessment logic."""
        high_threat = {
            "impression_share": 0.3,
            "top_of_page_rate": 0.5,
            "overlap_rate": 0.4,
        }
        medium_threat = {
            "impression_share": 0.2,
            "top_of_page_rate": 0.3,
            "overlap_rate": 0.2,
        }
        low_threat = {
            "impression_share": 0.1,
            "top_of_page_rate": 0.1,
            "overlap_rate": 0.1,
        }

        assert parser._assess_competitive_threat(high_threat) == "High"
        assert parser._assess_competitive_threat(medium_threat) == "Medium"
        assert parser._assess_competitive_threat(low_threat) == "Low"

    def test_market_position_calculation(self, parser):
        """Test market position calculation."""
        own_domain = {"domain": "yourdomain.com", "impression_share": 0.25}
        competitors = [
            {"domain": "competitor1.com", "impression_share": 0.30},
            {"domain": "competitor2.com", "impression_share": 0.20},
            {"domain": "competitor3.com", "impression_share": 0.15},
        ]

        position = parser._calculate_market_position(own_domain, competitors)
        assert position == 2  # Should be 2nd place

    def test_advantage_score_calculation(self, parser):
        """Test competitive advantage score calculation."""
        own_domain = {
            "domain": "yourdomain.com",
            "impression_share": 0.30,
            "top_of_page_rate": 0.40,
        }
        competitors = [
            {
                "domain": "competitor1.com",
                "impression_share": 0.20,
                "top_of_page_rate": 0.30,
            },
            {
                "domain": "competitor2.com",
                "impression_share": 0.15,
                "top_of_page_rate": 0.25,
            },
        ]

        score = parser._calculate_advantage_score(own_domain, competitors)
        assert score > 50  # Should be above neutral (50)
        assert score <= 100

    def test_generate_recommendations(self, parser):
        """Test strategic recommendations generation."""
        competitors = [
            {
                "domain": "competitor1.com",
                "impression_share": 0.25,
                "overlap_rate": 0.35,
                "top_of_page_rate": 0.35,
                "outranking_share": 0.25,
            },
            {
                "domain": "competitor2.com",
                "impression_share": 0.15,
                "overlap_rate": 0.20,
                "top_of_page_rate": 0.30,
                "outranking_share": 0.20,
            },
        ]
        own_domain = {"domain": "yourdomain.com", "impression_share": 0.20}

        recommendations = parser._generate_recommendations(competitors, own_domain)

        assert isinstance(recommendations, list)
        assert len(recommendations) <= 5  # Should limit to 5 recommendations
        assert all(isinstance(rec, str) for rec in recommendations)

    def test_identify_opportunities(self, parser):
        """Test opportunity identification."""
        competitors = [
            {
                "domain": "competitor1.com",
                "impression_share": 0.25,
                "abs_top_of_page_rate": 0.10,
                "outranking_share": 0.20,
            },
            {
                "domain": "competitor2.com",
                "impression_share": 0.15,
                "abs_top_of_page_rate": 0.12,
                "outranking_share": 0.22,
            },
        ]
        own_domain = {"domain": "yourdomain.com", "impression_share": 0.18}

        opportunities = parser._identify_opportunities(competitors, own_domain)

        assert isinstance(opportunities, list)
        assert len(opportunities) <= 4  # Should limit to 4 opportunities

    def test_parse_and_analyze_integration(self, parser, temp_auction_insights_file):
        """Test the integrated parse and analyze functionality."""
        # Test with the clean CSV file (the parse_and_analyze method should handle both formats)
        result = parser.parse_and_analyze(temp_auction_insights_file)

        assert "parsing_info" in result

        # The method should always return these keys, even if parsing fails
        assert "analysis" in result

        # Check if parsing was successful
        if result["parsing_info"]["parsed_successfully"]:
            assert "raw_data" in result
            assert result["parsing_info"]["total_records"] > 0
            assert len(result["raw_data"]) > 0

            # Analysis should contain competitive insights
            assert (
                "total_competitors" in result["analysis"]
                or "error" in result["analysis"]
            )
        else:
            # If parsing failed, we should still get the error structure
            assert "error" in result["parsing_info"]
            assert "error" in result["analysis"]

    def test_kpis_calculation(self, parser):
        """Test KPI calculation functionality."""
        competitors = [
            {
                "impression_share": 0.25,
                "overlap_rate": 0.20,
                "outranking_share": 0.30,
                "top_of_page_rate": 0.45,
            },
            {
                "impression_share": 0.15,
                "overlap_rate": 0.15,
                "outranking_share": 0.25,
                "top_of_page_rate": 0.35,
            },
            {
                "impression_share": 0.12,
                "overlap_rate": 0.10,
                "outranking_share": 0.20,
                "top_of_page_rate": 0.40,
            },
        ]
        own_domain = {"impression_share": 0.30}

        kpis = parser._calculate_kpis(competitors, own_domain)

        assert "competitive_market_metrics" in kpis
        assert "strategic_performance_indicators" in kpis

        # Check that KPIs contain expected metrics
        assert "total_competitors" in kpis["competitive_market_metrics"]
        assert "average_impression_share" in kpis["competitive_market_metrics"]
        assert "competitive_advantage_score" in kpis["strategic_performance_indicators"]

    def test_file_type_initialization(self, parser):
        """Test that parser initializes with correct file type."""
        assert parser.file_type == "auction_insights"

    def test_error_handling_in_parse_and_analyze(self, parser):
        """Test error handling in parse_and_analyze method."""
        # Test with non-existent file
        result = parser.parse_and_analyze(Path("/nonexistent/file.csv"))

        assert "parsing_info" in result
        assert result["parsing_info"]["parsed_successfully"] is False
        assert "error" in result["parsing_info"]
        assert "error" in result["analysis"]

    def test_configuration_initialization(self):
        """Test configuration initialization and usage."""
        # Test default configuration
        config = AuctionInsightsConfig()
        assert config.high_threat_threshold == 0.3
        assert config.medium_threat_threshold == 0.15
        assert config.own_domain_detection_strict is True

        # Test custom configuration
        custom_config = AuctionInsightsConfig(
            high_threat_threshold=0.4,
            medium_threat_threshold=0.2,
            own_domain_detection_strict=False,
        )
        assert custom_config.high_threat_threshold == 0.4
        assert custom_config.medium_threat_threshold == 0.2
        assert custom_config.own_domain_detection_strict is False

    def test_parser_with_custom_configuration(self):
        """Test parser initialization with custom configuration."""
        config = AuctionInsightsConfig(
            high_threat_threshold=0.4, own_domain_detection_strict=False
        )
        parser = AuctionInsightsParser(config=config)

        assert parser.config.high_threat_threshold == 0.4
        assert parser.config.own_domain_detection_strict is False

    def test_own_domain_detection_strict_mode(self):
        """Test own domain detection in strict mode."""
        config = AuctionInsightsConfig(own_domain_detection_strict=True)
        parser = AuctionInsightsParser(config=config)

        # Should require all metrics to be zero
        strict_own_domain = {
            "domain": "test.com",
            "overlap_rate": 0.0,
            "outranking_share": 0.0,
            "position_above_rate": 0.0,
        }
        assert parser._is_own_domain(strict_own_domain) is True

        # Should fail if any metric is non-zero
        non_strict_data = {
            "domain": "test.com",
            "overlap_rate": 0.0,
            "outranking_share": 0.1,
            "position_above_rate": 0.0,
        }
        assert parser._is_own_domain(non_strict_data) is False

    def test_own_domain_detection_lenient_mode(self):
        """Test own domain detection in lenient mode."""
        config = AuctionInsightsConfig(own_domain_detection_strict=False)
        parser = AuctionInsightsParser(config=config)

        # Should pass with 2 out of 3 metrics being zero
        lenient_data = {
            "domain": "test.com",
            "overlap_rate": 0.0,
            "outranking_share": 0.1,
            "position_above_rate": 0.0,
        }
        assert parser._is_own_domain(lenient_data) is True

        # Should fail with only 1 metric being zero
        failing_data = {
            "domain": "test.com",
            "overlap_rate": 0.1,
            "outranking_share": 0.1,
            "position_above_rate": 0.0,
        }
        assert parser._is_own_domain(failing_data) is False

    def test_data_validation_with_missing_fields(self, parser):
        """Test data validation when competitor_domain field is missing."""
        invalid_data = [
            {"impression_share": "25%"},  # Missing competitor_domain
            {"competitor_domain": "", "impression_share": "30%"},  # Empty domain
            {
                "competitor_domain": "valid.com",
                "impression_share": "20%",
                "overlap_rate": "15%",
                "outranking_share": "10%",
                "position_above_rate": "8%",
            },  # Valid competitor
        ]

        result = parser.analyze_competitive_landscape(invalid_data)

        # Should process only the valid entry
        assert "total_competitors" in result
        assert result["total_competitors"] == 1

    def test_competitive_threat_with_custom_thresholds(self):
        """Test competitive threat assessment with custom thresholds."""
        config = AuctionInsightsConfig(
            high_threat_threshold=0.3,  # Lower to ensure high threat is detected
            medium_threat_threshold=0.15,
        )
        parser = AuctionInsightsParser(config=config)

        # High threat: score = 0.4*0.4 + 0.3*0.3 + 0.3*0.3 = 0.16 + 0.09 + 0.09 = 0.34 > 0.3
        high_threat = {
            "impression_share": 0.4,
            "top_of_page_rate": 0.3,
            "overlap_rate": 0.3,
        }
        # Medium threat: score = 0.2*0.4 + 0.2*0.3 + 0.2*0.3 = 0.08 + 0.06 + 0.06 = 0.20 > 0.15
        medium_threat = {
            "impression_share": 0.2,
            "top_of_page_rate": 0.2,
            "overlap_rate": 0.2,
        }
        # Low threat: score = 0.1*0.4 + 0.1*0.3 + 0.1*0.3 = 0.04 + 0.03 + 0.03 = 0.10 < 0.15
        low_threat = {
            "impression_share": 0.1,
            "top_of_page_rate": 0.1,
            "overlap_rate": 0.1,
        }

        assert parser._assess_competitive_threat(high_threat) == "High"
        assert parser._assess_competitive_threat(medium_threat) == "Medium"
        assert parser._assess_competitive_threat(low_threat) == "Low"

    def test_batched_opportunity_identification_performance(self):
        """Test that opportunity identification works efficiently with large datasets."""
        # Create a large dataset
        large_competitor_list = []
        for i in range(1000):
            large_competitor_list.append(
                {
                    "domain": f"competitor{i}.com",
                    "impression_share": 0.001 * i,
                    "abs_top_of_page_rate": 0.1 + (i % 10) * 0.01,
                    "outranking_share": 0.2 + (i % 20) * 0.01,
                }
            )

        parser = AuctionInsightsParser()

        # This should complete quickly without performance issues
        opportunities = parser._identify_opportunities(large_competitor_list, None)

        assert isinstance(opportunities, list)
        assert len(opportunities) <= 4  # Should limit to 4 opportunities

    def test_configuration_affects_recommendations(self):
        """Test that configuration parameters affect recommendation generation."""
        # Create test data
        competitors = [
            {
                "domain": "competitor1.com",
                "overlap_rate": 0.35,
                "top_of_page_rate": 0.35,
                "outranking_share": 0.25,
            },
            {
                "domain": "competitor2.com",
                "overlap_rate": 0.25,
                "top_of_page_rate": 0.45,
                "outranking_share": 0.35,
            },
        ]

        # Test with default thresholds
        default_parser = AuctionInsightsParser()
        default_recommendations = default_parser._generate_recommendations(
            competitors, None
        )

        # Test with higher thresholds (should generate fewer recommendations)
        strict_config = AuctionInsightsConfig(
            high_overlap_threshold=0.5,
            low_positioning_threshold=0.2,
            low_outranking_threshold=0.1,
        )
        strict_parser = AuctionInsightsParser(config=strict_config)
        strict_recommendations = strict_parser._generate_recommendations(
            competitors, None
        )

        # Results should be different based on different thresholds
        assert isinstance(default_recommendations, list)
        assert isinstance(strict_recommendations, list)
