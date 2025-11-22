"""Tests for the CSVDataProvider."""

from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from paidsearchnav_mcp.core.exceptions import DataError
from paidsearchnav_mcp.models.keyword import Keyword
from paidsearchnav_mcp.models.search_term import SearchTerm
from paidsearchnav_mcp.data_providers.csv_provider import CSVDataProvider


class TestCSVDataProvider:
    """Test the CSV data provider implementation."""

    @pytest.fixture
    def temp_data_dir(self, tmp_path):
        """Create a temporary directory for test CSV files."""
        data_dir = tmp_path / "csv_data"
        data_dir.mkdir()
        return data_dir

    @pytest.fixture
    def provider(self, temp_data_dir):
        """Create a CSVDataProvider with temporary directory."""
        return CSVDataProvider(data_directory=temp_data_dir)

    @pytest.fixture
    def date_range(self):
        """Create a standard date range for testing."""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        return start_date, end_date

    def test_initialization(self, temp_data_dir):
        """Test provider initialization."""
        # With directory
        provider = CSVDataProvider(data_directory=temp_data_dir)
        assert provider.data_directory == temp_data_dir

        # Without directory (uses cwd)
        provider = CSVDataProvider()
        assert provider.data_directory == Path.cwd()

    def test_find_csv_file(self, provider, temp_data_dir):
        """Test CSV file finding logic."""
        # Create test files
        (temp_data_dir / "search_terms.csv").touch()
        (temp_data_dir / "keywords_export.csv").touch()

        # Test exact match
        assert (
            provider._find_csv_file("search_terms")
            == temp_data_dir / "search_terms.csv"
        )

        # Test pattern match
        assert (
            provider._find_csv_file("keywords") == temp_data_dir / "keywords_export.csv"
        )

        # Test not found
        assert provider._find_csv_file("nonexistent") is None

        # Test path traversal prevention
        with pytest.raises(ValueError, match="Invalid file pattern"):
            provider._find_csv_file("../etc/passwd")

        with pytest.raises(ValueError, match="Invalid file pattern"):
            provider._find_csv_file("subdir/file")

    @pytest.mark.asyncio
    async def test_get_search_terms_no_file(self, provider, date_range):
        """Test get_search_terms when no file exists."""
        start_date, end_date = date_range

        terms = await provider.get_search_terms(
            customer_id="test",
            start_date=start_date,
            end_date=end_date,
        )

        assert terms == []

    @pytest.mark.asyncio
    async def test_get_search_terms_with_mock_parser(
        self, provider, temp_data_dir, date_range
    ):
        """Test get_search_terms with mocked parser."""
        start_date, end_date = date_range

        # Create a dummy CSV file
        csv_file = temp_data_dir / "search_terms.csv"
        csv_file.write_text("dummy,data\n")

        # Mock the parser
        mock_parser = Mock()
        from paidsearchnav.core.models.search_term import SearchTermMetrics

        mock_terms = [
            SearchTerm(
                campaign_id="camp_1",
                campaign_name="Campaign 1",
                ad_group_id="ag_1",
                ad_group_name="Ad Group 1",
                search_term="test term 1",
                match_type="EXACT",
                metrics=SearchTermMetrics(
                    impressions=100,
                    clicks=10,
                    cost=5.0,
                    conversions=1.0,
                    conversion_value=50.0,
                ),
                date_start=(start_date + timedelta(days=1)).date(),
            ),
            SearchTerm(
                campaign_id="camp_2",
                campaign_name="Campaign 2",
                ad_group_id="ag_2",
                ad_group_name="Ad Group 2",
                search_term="test term 2",
                match_type="BROAD",
                metrics=SearchTermMetrics(
                    impressions=200,
                    clicks=20,
                    cost=10.0,
                    conversions=2.0,
                    conversion_value=100.0,
                ),
                date_start=(start_date + timedelta(days=2)).date(),
            ),
            SearchTerm(
                campaign_id="camp_1",
                campaign_name="Campaign 1",
                ad_group_id="ag_1",
                ad_group_name="Ad Group 1",
                search_term="old term",
                match_type="EXACT",
                metrics=SearchTermMetrics(
                    impressions=50,
                    clicks=5,
                    cost=2.5,
                    conversions=0.5,
                    conversion_value=25.0,
                ),
                date_start=(
                    start_date - timedelta(days=10)
                ).date(),  # Outside date range
            ),
        ]
        mock_parser.parse.return_value = mock_terms
        provider._parser_cache["search_terms"] = mock_parser

        # Test basic retrieval
        terms = await provider.get_search_terms(
            customer_id="test",
            start_date=start_date,
            end_date=end_date,
        )

        # Should filter out the term outside date range
        assert len(terms) == 2
        assert all(start_date.date() <= t.date_start <= end_date.date() for t in terms)

        # Test campaign filtering
        terms = await provider.get_search_terms(
            customer_id="test",
            start_date=start_date,
            end_date=end_date,
            campaigns=["Campaign 1"],
        )

        assert len(terms) == 1
        assert all(t.campaign_name == "Campaign 1" for t in terms)

        # Test ad group filtering
        terms = await provider.get_search_terms(
            customer_id="test",
            start_date=start_date,
            end_date=end_date,
            ad_groups=["Ad Group 2"],
        )

        assert len(terms) == 1
        assert all(t.ad_group_name == "Ad Group 2" for t in terms)

    @pytest.mark.asyncio
    async def test_get_keywords_with_mock_parser(self, provider, temp_data_dir):
        """Test get_keywords with mocked parser."""
        # Create a dummy CSV file
        csv_file = temp_data_dir / "keywords.csv"
        csv_file.write_text("dummy,data\n")

        # Mock the parser
        mock_parser = Mock()
        mock_keywords = [
            Keyword(
                keyword_id="kw_1",
                text="keyword 1",
                match_type="EXACT",
                status="ENABLED",
                campaign_id="camp_1",
                campaign_name="Campaign 1",
                ad_group_id="ag_1",
                ad_group_name="Ad Group 1",
            ),
            Keyword(
                keyword_id="kw_2",
                text="keyword 2",
                match_type="BROAD",
                status="ENABLED",
                campaign_id="camp_2",
                campaign_name="Campaign 2",
                ad_group_id="ag_2",
                ad_group_name="Ad Group 2",
            ),
        ]
        mock_parser.parse.return_value = mock_keywords
        provider._parser_cache["keywords"] = mock_parser

        # Test basic retrieval
        keywords = await provider.get_keywords(customer_id="test")
        assert len(keywords) == 2

        # Test campaign filtering
        keywords = await provider.get_keywords(
            customer_id="test",
            campaigns=["Campaign 1"],
        )
        assert len(keywords) == 1
        assert all(k.campaign_name == "Campaign 1" for k in keywords)

        # Test campaign_id filtering
        keywords = await provider.get_keywords(
            customer_id="test",
            campaign_id="camp_2",
        )
        assert len(keywords) == 1
        assert all(k.campaign_id == "camp_2" for k in keywords)

    @pytest.mark.asyncio
    async def test_get_negative_keywords_with_mock_parser(
        self, provider, temp_data_dir
    ):
        """Test get_negative_keywords with mocked parser."""
        # Create a dummy CSV file
        csv_file = temp_data_dir / "negative_keywords.csv"
        csv_file.write_text("dummy,data\n")

        # Mock the parser
        mock_parser = Mock()
        mock_negatives = [
            Mock(
                text="free",
                match_type="BROAD",
                level="CAMPAIGN",
                campaign_name="Campaign 1",
                ad_group_name="",
                shared_set_name="",
            ),
            Mock(
                text="cheap",
                match_type="PHRASE",
                level="SHARED_SET",
                campaign_name="",
                ad_group_name="",
                shared_set_name="Universal Negatives",
            ),
        ]
        mock_parser.parse.return_value = mock_negatives

        with patch.object(provider, "_get_parser") as mock_get_parser:
            mock_get_parser.return_value = mock_parser

            # Test with shared sets
            negatives = await provider.get_negative_keywords(
                customer_id="test",
                include_shared_sets=True,
            )

            assert len(negatives) == 2

            # Test without shared sets
            negatives = await provider.get_negative_keywords(
                customer_id="test",
                include_shared_sets=False,
            )

            assert len(negatives) == 1
            assert all(n["shared_set_name"] == "" for n in negatives)

    @pytest.mark.asyncio
    async def test_get_campaigns_with_mock_parser(self, provider, temp_data_dir):
        """Test get_campaigns with mocked parser."""
        # Create a dummy CSV file
        csv_file = temp_data_dir / "campaigns.csv"
        csv_file.write_text("dummy,data\n")

        # Mock the parser
        mock_parser = Mock()
        mock_campaigns = [
            Mock(
                id="camp_1",
                name="Campaign 1",
                status="ENABLED",
                campaign_type="SEARCH",
                budget=1000.0,
            ),
            Mock(
                id="camp_2",
                name="Campaign 2",
                status="ENABLED",
                campaign_type="PERFORMANCE_MAX",
                budget=2000.0,
            ),
        ]
        mock_parser.parse.return_value = mock_campaigns
        provider._parser_cache["campaigns"] = mock_parser

        # Test basic retrieval
        campaigns = await provider.get_campaigns(customer_id="test")
        assert len(campaigns) == 2

        # Test type filtering
        campaigns = await provider.get_campaigns(
            customer_id="test",
            campaign_types=["SEARCH"],
        )
        assert len(campaigns) == 1
        assert all(getattr(c, "campaign_type", "SEARCH") == "SEARCH" for c in campaigns)

    @pytest.mark.asyncio
    async def test_get_placement_data_with_mock_parser(
        self, provider, temp_data_dir, date_range
    ):
        """Test get_placement_data with mocked parser."""
        start_date, end_date = date_range

        # Create a dummy CSV file
        csv_file = temp_data_dir / "placements.csv"
        csv_file.write_text("dummy,data\n")

        # Mock the parser
        mock_parser = Mock()
        mock_placements = [
            Mock(
                placement_id="pl_1",
                placement_name="example.com",
                display_name="Example Site",
                impressions=1000,
                clicks=50,
                cost=25.0,
                conversions=5.0,
                conversion_value=250.0,
                campaign_id="camp_1",
                ad_group_id="ag_1",
            ),
            Mock(
                placement_id="pl_2",
                placement_name="test.com",
                display_name="Test Site",
                impressions=500,
                clicks=25,
                cost=12.5,
                conversions=2.5,
                conversion_value=125.0,
                campaign_id="camp_2",
                ad_group_id="ag_2",
            ),
        ]

        # Add missing attributes with defaults
        for p in mock_placements:
            for attr in ["ctr", "cpc", "cpa", "roas"]:
                if not hasattr(p, attr):
                    setattr(p, attr, 0.0)

        mock_parser.parse.return_value = mock_placements

        with patch.object(provider, "_get_parser") as mock_get_parser:
            mock_get_parser.return_value = mock_parser

            # Test basic retrieval
            placements = await provider.get_placement_data(
                customer_id="test",
                start_date=start_date,
                end_date=end_date,
            )

            assert len(placements) == 2

            # Test campaign filtering
            placements = await provider.get_placement_data(
                customer_id="test",
                start_date=start_date,
                end_date=end_date,
                campaigns=["camp_1"],
            )

            assert len(placements) == 1
            assert all("camp_1" in p["campaign_ids"] for p in placements)

    def test_load_search_terms_direct(self, provider, temp_data_dir):
        """Test the direct load_search_terms method."""
        # Test with non-existent file
        with pytest.raises(DataError, match="File not found"):
            provider.load_search_terms("nonexistent.csv")

        # Create a dummy file
        csv_file = temp_data_dir / "direct_terms.csv"
        csv_file.write_text("dummy,data\n")

        # Mock the parser
        mock_parser = Mock()
        from paidsearchnav.core.models.search_term import SearchTermMetrics

        mock_terms = [
            SearchTerm(
                campaign_id="camp_1",
                campaign_name="Campaign 1",
                ad_group_id="ag_1",
                ad_group_name="Ad Group 1",
                search_term="direct term",
                match_type="EXACT",
                metrics=SearchTermMetrics(
                    impressions=100,
                    clicks=10,
                    cost=5.0,
                    conversions=1.0,
                    conversion_value=50.0,
                ),
            )
        ]
        mock_parser.parse.return_value = mock_terms
        provider._parser_cache["search_terms"] = mock_parser

        # Test loading
        terms = provider.load_search_terms(csv_file)
        assert len(terms) == 1
        assert terms[0].search_term == "direct term"

    @pytest.mark.asyncio
    async def test_error_handling(self, provider, temp_data_dir, date_range):
        """Test error handling in various methods."""
        start_date, end_date = date_range

        # Create a CSV file that will cause parser to fail
        csv_file = temp_data_dir / "search_terms.csv"
        csv_file.write_text("dummy,data\n")

        # Mock parser to raise exception
        mock_parser = Mock()
        mock_parser.parse.side_effect = Exception("Parse error")
        provider._parser_cache["search_terms"] = mock_parser

        # Test that DataError is raised
        with pytest.raises(
            DataError, match="Unexpected error loading search terms from CSV"
        ):
            await provider.get_search_terms(
                customer_id="test",
                start_date=start_date,
                end_date=end_date,
            )
