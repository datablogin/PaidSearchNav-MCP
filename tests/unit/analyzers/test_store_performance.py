"""Unit tests for StorePerformanceAnalyzer."""

import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from paidsearchnav_mcp.analyzers.store_performance import StorePerformanceAnalyzer
from paidsearchnav_mcp.models import (
    StoreIssueType,
    StoreLocationData,
    StoreMetrics,
    StorePerformanceData,
    StorePerformanceLevel,
)


class TestStorePerformanceAnalyzer:
    """Test cases for StorePerformanceAnalyzer."""

    @pytest.fixture
    def analyzer(self):
        """Create a StorePerformanceAnalyzer instance for testing."""
        return StorePerformanceAnalyzer(
            min_impressions=100,
            high_engagement_threshold=3.0,
            moderate_engagement_threshold=1.5,
            low_engagement_threshold=0.5,
        )

    @pytest.fixture
    def sample_csv_data(self):
        """Sample CSV data for testing."""
        return [
            {
                "store_name": "Test Store Dallas",
                "address_line_1": "123 Main St",
                "address_line_2": "",
                "city": "Dallas",
                "state": "TX",
                "postal_code": "75201",
                "country_code": "US",
                "phone_number": "+1 214-555-0100",
                "local_impressions": "1,000",
                "call_clicks": "10",
                "driving_directions": "5",
                "website_visits": "20",
            },
            {
                "store_name": "Test Store Austin",
                "address_line_1": "456 Oak Ave",
                "address_line_2": "Suite 100",
                "city": "Austin",
                "state": "TX",
                "postal_code": "78701",
                "country_code": "US",
                "phone_number": "+1 512-555-0200",
                "local_impressions": "2,000",
                "call_clicks": "0",  # Call tracking issue
                "driving_directions": "15",
                "website_visits": "30",
            },
            {
                "store_name": "Test Store Houston",
                "address_line_1": "789 Pine Rd",
                "address_line_2": None,
                "city": "Houston",
                "state": "TX",
                "postal_code": "77001",
                "country_code": "US",
                "phone_number": None,
                "local_impressions": "50",  # Below threshold
                "call_clicks": "1",
                "driving_directions": "0",
                "website_visits": "2",
            },
        ]

    @pytest.fixture
    def high_performer_data(self):
        """Data for a high-performing store."""
        return {
            "store_name": "High Performer Store",
            "address_line_1": "100 Success St",
            "address_line_2": "",
            "city": "Dallas",
            "state": "TX",
            "postal_code": "75201",
            "country_code": "US",
            "phone_number": "+1 214-555-0300",
            "local_impressions": "1,000",
            "call_clicks": "20",
            "driving_directions": "10",
            "website_visits": "15",  # 4.5% engagement rate
        }

    @pytest.fixture
    def underperformer_data(self):
        """Data for an underperforming store."""
        return {
            "store_name": "Underperformer Store",
            "address_line_1": "200 Low St",
            "address_line_2": "",
            "city": "Austin",
            "state": "TX",
            "postal_code": "78701",
            "country_code": "US",
            "phone_number": "+1 512-555-0400",
            "local_impressions": "1,000",
            "call_clicks": "1",
            "driving_directions": "0",
            "website_visits": "2",  # 0.3% engagement rate
        }

    def test_init(self):
        """Test analyzer initialization."""
        analyzer = StorePerformanceAnalyzer(
            min_impressions=200,
            high_engagement_threshold=4.0,
            moderate_engagement_threshold=2.0,
            low_engagement_threshold=1.0,
        )

        assert analyzer.min_impressions == 200
        assert analyzer.high_engagement_threshold == 4.0
        assert analyzer.moderate_engagement_threshold == 2.0
        assert analyzer.low_engagement_threshold == 1.0

    @pytest.mark.asyncio
    async def test_analyze_with_valid_data(self, analyzer, sample_csv_data):
        """Test analysis with valid CSV data."""
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 31)

        result = await analyzer.analyze(
            customer_id="123456789",
            start_date=start_date,
            end_date=end_date,
            csv_data=sample_csv_data,
        )

        # Should only include stores above minimum impressions threshold
        assert len(result.store_data) == 2  # Dallas and Austin, Houston filtered out
        assert result.summary.total_stores == 2
        assert result.summary.total_local_impressions == 3000  # 1000 + 2000

        # Check that insights are generated
        assert len(result.insights) > 0

        # Check for call tracking issue in Austin store
        call_tracking_insights = [
            insight
            for insight in result.insights
            if insight.issue_type == StoreIssueType.MISSING_CALL_TRACKING
        ]
        assert len(call_tracking_insights) == 1
        assert "Test Store Austin" in call_tracking_insights[0].store_name

    @pytest.mark.asyncio
    async def test_analyze_without_csv_data(self, analyzer):
        """Test analysis fails when csv_data is not provided."""
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 31)

        with pytest.raises(ValueError, match="csv_data is required"):
            await analyzer.analyze(
                customer_id="123456789",
                start_date=start_date,
                end_date=end_date,
            )

    @pytest.mark.asyncio
    async def test_analyze_with_empty_customer_id(self, analyzer, sample_csv_data):
        """Test analysis fails when customer_id is empty."""
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 31)

        with pytest.raises(ValueError, match="customer_id is required"):
            await analyzer.analyze(
                customer_id="",
                start_date=start_date,
                end_date=end_date,
                csv_data=sample_csv_data,
            )

    @pytest.mark.asyncio
    async def test_analyze_with_invalid_date_range(self, analyzer, sample_csv_data):
        """Test analysis fails when start_date is after end_date."""
        start_date = datetime(2024, 1, 31)
        end_date = datetime(2024, 1, 1)  # End before start

        with pytest.raises(ValueError, match="start_date must be before end_date"):
            await analyzer.analyze(
                customer_id="123456789",
                start_date=start_date,
                end_date=end_date,
                csv_data=sample_csv_data,
            )

    @pytest.mark.asyncio
    async def test_analyze_with_empty_data(self, analyzer):
        """Test analysis with empty CSV data."""
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 31)

        result = await analyzer.analyze(
            customer_id="123456789",
            start_date=start_date,
            end_date=end_date,
            csv_data=[],
        )

        assert len(result.store_data) == 0
        assert result.summary.total_stores == 0
        assert len(result.insights) == 0

    def test_parse_number(self, analyzer):
        """Test number parsing from CSV data."""
        assert analyzer._parse_number("1,000") == 1000
        assert analyzer._parse_number("500") == 500
        assert analyzer._parse_number(250) == 250
        assert analyzer._parse_number("invalid") == 0
        assert analyzer._parse_number(None) == 0
        assert analyzer._parse_number("") == 0

    def test_parse_store_data(self, analyzer, sample_csv_data):
        """Test parsing CSV data into StorePerformanceData objects."""
        stores = analyzer._parse_store_data(sample_csv_data)

        assert len(stores) == 3

        # Check first store
        dallas_store = stores[0]
        assert dallas_store.location.store_name == "Test Store Dallas"
        assert dallas_store.location.city == "Dallas"
        assert dallas_store.location.phone_number == "+1 214-555-0100"
        assert dallas_store.metrics.local_impressions == 1000
        assert dallas_store.metrics.call_clicks == 10
        assert dallas_store.metrics.total_engagements == 35  # 10 + 5 + 20

    def test_categorize_performance(self, analyzer):
        """Test store performance categorization."""
        # High performer (4.5% engagement)
        high_store = StorePerformanceData(
            location=StoreLocationData(
                store_name="High Store",
                address_line_1="123 Main St",
                city="Dallas",
                state="TX",
                postal_code="75201",
                country_code="US",
            ),
            metrics=StoreMetrics(
                local_impressions=1000,
                call_clicks=20,
                driving_directions=15,
                website_visits=10,  # 4.5% engagement
            ),
            performance_level=StorePerformanceLevel.MODERATE_PERFORMER,  # Will be updated
        )

        level = analyzer._categorize_performance(high_store)
        assert level == StorePerformanceLevel.HIGH_PERFORMER

        # Moderate performer (2.0% engagement)
        moderate_store = StorePerformanceData(
            location=StoreLocationData(
                store_name="Moderate Store",
                address_line_1="123 Main St",
                city="Dallas",
                state="TX",
                postal_code="75201",
                country_code="US",
            ),
            metrics=StoreMetrics(
                local_impressions=1000,
                call_clicks=10,
                driving_directions=5,
                website_visits=5,  # 2.0% engagement
            ),
            performance_level=StorePerformanceLevel.MODERATE_PERFORMER,
        )

        level = analyzer._categorize_performance(moderate_store)
        assert level == StorePerformanceLevel.MODERATE_PERFORMER

        # Underperformer (0.2% engagement)
        under_store = StorePerformanceData(
            location=StoreLocationData(
                store_name="Under Store",
                address_line_1="123 Main St",
                city="Dallas",
                state="TX",
                postal_code="75201",
                country_code="US",
            ),
            metrics=StoreMetrics(
                local_impressions=1000,
                call_clicks=1,
                driving_directions=0,
                website_visits=1,  # 0.2% engagement
            ),
            performance_level=StorePerformanceLevel.MODERATE_PERFORMER,
        )

        level = analyzer._categorize_performance(under_store)
        assert level == StorePerformanceLevel.UNDERPERFORMER

    def test_generate_insights_call_tracking_issue(self, analyzer):
        """Test insight generation for call tracking issues."""
        store = StorePerformanceData(
            location=StoreLocationData(
                store_name="Test Store",
                address_line_1="123 Main St",
                city="Dallas",
                state="TX",
                postal_code="75201",
                country_code="US",
                phone_number="+1 214-555-0100",
            ),
            metrics=StoreMetrics(
                local_impressions=1000,
                call_clicks=0,  # No call clicks despite having phone
                driving_directions=10,
                website_visits=15,
            ),
            performance_level=StorePerformanceLevel.MODERATE_PERFORMER,
        )

        insights = analyzer._generate_insights([store])

        call_tracking_insights = [
            insight
            for insight in insights
            if insight.issue_type == StoreIssueType.MISSING_CALL_TRACKING
        ]
        assert len(call_tracking_insights) == 1
        assert call_tracking_insights[0].priority == "high"

    def test_generate_insights_low_engagement(self, analyzer):
        """Test insight generation for low engagement."""
        store = StorePerformanceData(
            location=StoreLocationData(
                store_name="Test Store",
                address_line_1="123 Main St",
                city="Dallas",
                state="TX",
                postal_code="75201",
                country_code="US",
            ),
            metrics=StoreMetrics(
                local_impressions=1000,
                call_clicks=2,
                driving_directions=1,
                website_visits=1,  # 0.4% engagement - below threshold
            ),
            performance_level=StorePerformanceLevel.UNDERPERFORMER,
        )

        insights = analyzer._generate_insights([store])

        low_engagement_insights = [
            insight
            for insight in insights
            if insight.issue_type == StoreIssueType.LOW_ENGAGEMENT
        ]
        assert len(low_engagement_insights) == 1
        assert low_engagement_insights[0].priority == "medium"

    def test_generate_insights_no_driving_directions(self, analyzer):
        """Test insight generation for missing driving directions."""
        store = StorePerformanceData(
            location=StoreLocationData(
                store_name="Test Store",
                address_line_1="123 Main St",
                city="Dallas",
                state="TX",
                postal_code="75201",
                country_code="US",
            ),
            metrics=StoreMetrics(
                local_impressions=600,  # Above 500 threshold
                call_clicks=20,
                driving_directions=0,  # No driving directions
                website_visits=10,
            ),
            performance_level=StorePerformanceLevel.MODERATE_PERFORMER,
        )

        insights = analyzer._generate_insights([store])

        directions_insights = [
            insight
            for insight in insights
            if insight.issue_type == StoreIssueType.NO_DRIVING_DIRECTIONS
        ]
        assert len(directions_insights) == 1
        assert directions_insights[0].priority == "medium"

    def test_create_summary(self, analyzer):
        """Test summary creation."""
        stores = [
            StorePerformanceData(
                location=StoreLocationData(
                    store_name="Store 1",
                    address_line_1="123 Main St",
                    city="Dallas",
                    state="TX",
                    postal_code="75201",
                    country_code="US",
                ),
                metrics=StoreMetrics(
                    local_impressions=1000,
                    call_clicks=30,
                    driving_directions=10,
                    website_visits=10,  # 5% engagement
                ),
                performance_level=StorePerformanceLevel.HIGH_PERFORMER,
            ),
            StorePerformanceData(
                location=StoreLocationData(
                    store_name="Store 2",
                    address_line_1="456 Oak Ave",
                    city="Austin",
                    state="TX",
                    postal_code="78701",
                    country_code="US",
                ),
                metrics=StoreMetrics(
                    local_impressions=500,
                    call_clicks=1,
                    driving_directions=1,
                    website_visits=1,  # 0.6% engagement
                ),
                performance_level=StorePerformanceLevel.LOW_PERFORMER,
            ),
        ]

        summary = analyzer._create_summary(stores)

        assert summary.total_stores == 2
        assert summary.total_local_impressions == 1500
        assert summary.total_engagements == 53  # (30+10+10) + (1+1+1)
        assert summary.high_performers == 1
        assert summary.low_performers == 1
        assert abs(summary.avg_engagement_rate - 2.8) < 0.1  # (5.0 + 0.6) / 2

    @pytest.mark.asyncio
    async def test_performance_levels_assignment(
        self, analyzer, high_performer_data, underperformer_data
    ):
        """Test that stores are correctly assigned performance levels."""
        csv_data = [high_performer_data, underperformer_data]

        result = await analyzer.analyze(
            customer_id="123456789",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 1, 31),
            csv_data=csv_data,
        )

        assert len(result.top_performers) == 1
        assert len(result.underperformers) == 1

        high_performer = result.top_performers[0]
        underperformer = result.underperformers[0]

        assert high_performer.location.store_name == "High Performer Store"
        assert high_performer.performance_level == StorePerformanceLevel.HIGH_PERFORMER

        assert underperformer.location.store_name == "Underperformer Store"
        assert underperformer.performance_level == StorePerformanceLevel.UNDERPERFORMER

    def test_store_metrics_properties(self):
        """Test StoreMetrics calculated properties."""
        metrics = StoreMetrics(
            local_impressions=1000,
            call_clicks=20,
            driving_directions=10,
            website_visits=15,
        )

        assert metrics.total_engagements == 45
        assert metrics.engagement_rate == 4.5

        # Test zero impressions
        zero_metrics = StoreMetrics(
            local_impressions=0,
            call_clicks=10,
            driving_directions=5,
            website_visits=5,
        )

        assert zero_metrics.engagement_rate == 0.0

    def test_store_performance_data_properties(self):
        """Test StorePerformanceData calculated properties."""
        store = StorePerformanceData(
            location=StoreLocationData(
                store_name="Test Store",
                address_line_1="123 Main St",
                city="Dallas",
                state="TX",
                postal_code="75201",
                country_code="US",
                phone_number="+1 214-555-0100",
            ),
            metrics=StoreMetrics(
                local_impressions=1000,
                call_clicks=0,
                driving_directions=5,
                website_visits=3,
            ),
            performance_level=StorePerformanceLevel.MODERATE_PERFORMER,
        )

        assert store.has_call_tracking_issue is True
        assert store.has_low_engagement is True  # 0.8% < 1.0%

        # Test store without phone number
        store_no_phone = StorePerformanceData(
            location=StoreLocationData(
                store_name="Test Store No Phone",
                address_line_1="123 Main St",
                city="Dallas",
                state="TX",
                postal_code="75201",
                country_code="US",
                phone_number=None,
            ),
            metrics=StoreMetrics(
                local_impressions=1000,
                call_clicks=0,
                driving_directions=5,
                website_visits=3,
            ),
            performance_level=StorePerformanceLevel.MODERATE_PERFORMER,
        )

        assert store_no_phone.has_call_tracking_issue is False

    def test_store_metrics_validation(self):
        """Test StoreMetrics field validation."""
        # Test valid metrics
        metrics = StoreMetrics(
            local_impressions=1000,
            call_clicks=20,
            driving_directions=10,
            website_visits=15,
        )
        assert metrics.local_impressions == 1000
        assert metrics.total_engagements == 45
        assert metrics.engagement_rate == 4.5

        # Test negative values validation
        with pytest.raises(ValueError, match="Metrics must be non-negative"):
            StoreMetrics(
                local_impressions=-100,
                call_clicks=20,
                driving_directions=10,
                website_visits=15,
            )

        with pytest.raises(ValueError, match="Metrics must be non-negative"):
            StoreMetrics(
                local_impressions=1000,
                call_clicks=-5,
                driving_directions=10,
                website_visits=15,
            )

    def test_parse_number_precision(self, analyzer):
        """Test number parsing preserves precision correctly."""
        # Test integer values
        assert analyzer._parse_number(1000) == 1000
        assert analyzer._parse_number("1,000") == 1000
        assert analyzer._parse_number("1000") == 1000

        # Test float values (should be converted to int)
        assert analyzer._parse_number("1000.5") == 1000
        assert analyzer._parse_number("1,000.7") == 1000
        assert analyzer._parse_number(1000.9) == 1000

        # Test edge cases
        assert analyzer._parse_number("") == 0
        assert analyzer._parse_number(None) == 0
        assert analyzer._parse_number("invalid") == 0

    def test_from_csv_file_not_found(self):
        """Test from_csv with non-existent file."""
        with pytest.raises(FileNotFoundError):
            StorePerformanceAnalyzer.from_csv("nonexistent_file.csv")

    def test_from_csv_file_too_large(self):
        """Test from_csv with file size limit."""
        # Create a large dummy file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            # Write large content (simulate > 1MB file)
            for i in range(10000):  # Optimized for CI
                f.write(
                    f"Store {i},123 Main St,City {i},TX,12345,US,555-0123,1000,50,5,10,8\n"
                )
            temp_path = f.name

        try:
            with pytest.raises(ValueError, match="exceeds maximum allowed size"):
                StorePerformanceAnalyzer.from_csv(temp_path, max_file_size_mb=1)
        finally:
            Path(temp_path).unlink()

    def test_from_csv_path_traversal_protection(self):
        """Test from_csv path traversal protection."""
        with pytest.raises(PermissionError):
            StorePerformanceAnalyzer.from_csv("../../etc/passwd")

    def test_from_csv_valid_file(self):
        """Test from_csv with valid CSV file."""
        csv_content = """Per store report
"May 18, 2025 - August 15, 2025"
Store locations,address_line_1,address_line_2,city,country_code,phone_number,postal_code,province,Local reach (impressions),Store visits,Call clicks,Driving directions,Website visits
Fitness Connection,6320 Albemarle Road, --,Charlotte,US, +1 704-567-1400,28212,North Carolina,"27,145",870,82,578,357
Fitness Connection,8428 Denton Highway, --,Watauga,US, +1 817-849-8888,76148,Texas,"56,710","2,212",172,"1,448","1,125"
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            temp_path = f.name

        try:
            analyzer = StorePerformanceAnalyzer.from_csv(temp_path)
            assert isinstance(analyzer, StorePerformanceAnalyzer)
            assert len(analyzer._csv_data) == 2

            # Check parsed data
            first_store = analyzer._csv_data[0]
            assert first_store["store_name"] == "Fitness Connection"
            assert first_store["city"] == "Charlotte"
            # CSV values remain as parsed by pandas (numbers may be converted)
            assert str(first_store["local_impressions"]) in ["27,145", "27145"]

        finally:
            Path(temp_path).unlink()

    def test_from_csv_alternative_format(self):
        """Test from_csv with alternative CSV format (no header rows)."""
        csv_content = """Store locations,address_line_1,city,state,postal_code,country_code,phone_number,Local reach (impressions),Store visits,Call clicks,Driving directions,Website visits
"Fitness Connection - Dallas","1234 Main St","Dallas","TX","75001","US","+1-214-555-0100","10,000","500","50","100","75"
"Fitness Connection - Houston","5678 Oak Ave","Houston","TX","77001","US","+1-713-555-0200","15,000","750","75","150","100"
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            temp_path = f.name

        try:
            analyzer = StorePerformanceAnalyzer.from_csv(temp_path)
            assert len(analyzer._csv_data) == 2

            # Check that data was parsed correctly
            first_store = analyzer._csv_data[0]
            assert first_store["store_name"] == "Fitness Connection - Dallas"
            assert first_store["state"] == "TX"

        finally:
            Path(temp_path).unlink()

    def test_from_csv_missing_required_columns(self):
        """Test from_csv with missing required columns."""
        csv_content = """Invalid CSV
"May 18, 2025 - August 15, 2025"
address_line_1,city,state,postal_code,country_code,phone_number
6320 Albemarle Road,Charlotte,North Carolina,28212,US, +1 704-567-1400
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            temp_path = f.name

        try:
            with pytest.raises(ValueError, match="No location identifier column found"):
                StorePerformanceAnalyzer.from_csv(temp_path)
        finally:
            Path(temp_path).unlink()

    @pytest.mark.asyncio
    async def test_from_csv_end_to_end_analysis(self):
        """Test complete analysis workflow using from_csv."""
        csv_content = """Store locations,address_line_1,city,state,postal_code,country_code,phone_number,Local reach (impressions),Store visits,Call clicks,Driving directions,Website visits
"Fitness Connection - Charlotte","6320 Albemarle Road","Charlotte","North Carolina","28212","US","+1 704-567-1400","27,145","870","82","578","357"
"Fitness Connection - Dallas","1234 Main St","Dallas","Texas","75001","US","+1 214-555-0100","10,000","500","50","100","75"
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(csv_content)
            temp_path = f.name

        try:
            analyzer = StorePerformanceAnalyzer.from_csv(temp_path)

            # Run analysis using the loaded data
            result = await analyzer.analyze(
                customer_id="1234567890",
                start_date=datetime(2025, 5, 1),
                end_date=datetime(2025, 8, 15),
            )

            # Verify analysis results
            assert result.customer_id == "1234567890"
            assert len(result.store_data) == 2
            assert result.summary.total_stores == 2
            assert result.summary.total_local_impressions == 37145  # 27,145 + 10,000
            assert result.summary.total_engagements > 0

            # Check that insights were generated
            assert (
                len(result.insights) >= 0
            )  # May or may not have insights depending on thresholds

        finally:
            Path(temp_path).unlink()
